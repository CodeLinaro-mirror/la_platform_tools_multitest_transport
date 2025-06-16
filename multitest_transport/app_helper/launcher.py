# Copyright 2020 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""ATS module launcher.

Example usage (launches two WSGI modules at ports 1234 and 1235, respectively):
python launcher.py
  --application_id="test"
  --port="1234"
  --datastore_emulator_host="localhost:1236"
  --module="api=test.api:APP"
  --module="backend=test.backend:APP"
"""
import functools
import logging
import multiprocessing
import os
import socket
import threading
import time
import urllib.parse

from absl import app as absl_app
from absl import flags
import attr
from google.appengine.api import full_app_id
import gunicorn.app.base
from gunicorn.util import import_app
import requests
from tradefed_cluster import common
from tradefed_cluster import env_config
from tradefed_cluster.plugins import base
from tradefed_cluster.util import ndb_shim as ndb


from multitest_transport.app_helper import rabbitmq_plugin
from multitest_transport.models import test_run_hook

FLAGS = flags.FLAGS
flags.DEFINE_string('application_id', None, 'Application ID')
flags.DEFINE_string('host', '127.0.0.1', 'Host')
flags.DEFINE_integer('port', 8000, 'Primary port')
flags.DEFINE_multi_string(
    'module', None, 'Module name and app, e.g. default=path.to.module:APP')
flags.DEFINE_string('datastore_emulator_host', None, 'Datastore emulator host')
flags.DEFINE_enum(
    'log_level',
    'INFO', ['DEBUG', 'INFO', 'WARN', 'ERROR', 'CRITICAL'],
    'Log level',
    case_sensitive=False)
flags.DEFINE_bool('live_reload', False, 'Restart modules when code changes')
flags.DEFINE_string('init', None, 'Init request. e.g. module:/init')
flags.DEFINE_integer('workers', 4, 'Number of workers')

LOG_FORMAT = ('%(levelname)s\t%(asctime)s '
              '{module}:%(filename)s:%(lineno)d] %(message)s')
LOG_CONFIG = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'default': {
            'class': 'logging.StreamHandler',
            'formatter': 'default',
        },
    },
    'loggers': {},
    'root': {
        'level': 'INFO',
        'handlers': ['default'],
    },
    'formatters': {
        'default': {
            'class': 'logging.Formatter',
            'format': LOG_FORMAT
        }
    }
}
LAUNCH_TIMEOUT_SECONDS = 60


class RawPathMiddleware(object):
  """Middleware that routes using the path prior to percent-decoding."""

  def __init__(self, app):
    self.app = app

  def __call__(self, environ, start_response):
    # Gunicorn passes the raw URI using the non-standard 'RAW_URI' environ key
    # Replace PATH_INFO to route based on the value prior to percent-decoding
    # https://werkzeug.palletsprojects.com/en/1.0.x/wsgi/#raw-request-uri-and-path-encoding
    raw_uri = environ.get('RAW_URI')
    if raw_uri:
      environ['PATH_INFO'] = urllib.parse.urlsplit(raw_uri).path
    return self.app(environ, start_response)


class CloudNdbMiddleware(object):
  """Middleware that creates an NDB context for each request."""

  def __init__(self, app):
    self.client = ndb.Client()
    self.app = app

  def __call__(self, environ, start_response):
    """Wraps each request call inside an NDB context."""
    with self.client.context(legacy_data=False):
      return self.app(environ, start_response)


@attr.s(frozen=True)
class Module(object):
  """Application module information."""
  name = attr.ib()  # Module name
  path = attr.ib()  # Module app path
  port = attr.ib()  # Module port

  @property
  def hostname(self):
    return '%s:%d' % (socket.gethostname(), self.port)

  @property
  def app(self):
    return import_app(self.path)  # Re-import to support live reloading


class InMemoryAppManager(base.AppManager):
  """Manages application information in-memory."""

  def __init__(self, modules):
    self.modules = modules

  def GetInfo(self, name):
    module = self.modules.get(name)
    return base.AppInfo(name=name, hostname=module.hostname)


class ModuleApplication(gunicorn.app.base.BaseApplication):
  """Gunicorn application corresponding to a module."""

  def __init__(
      self, module, host=None, log_level=None, live_reload=None, workers=None
  ):
    self.module = module
    self.bind_address = self.format_host_port(
        host or FLAGS.host, self.module.port
    )
    self.log_level = log_level or FLAGS.log_level
    self.live_reload = live_reload or FLAGS.live_reload
    self.workers = workers or FLAGS.workers
    super(ModuleApplication, self).__init__()

  @staticmethod
  def format_host_port(host, port):
    """Format an IPv4/IPv6 address and a port into a URL component."""
    if ':' in host:
      return '[%s]:%d' % (host, port)
    return '%s:%d' % (host, port)

  def load_config(self):
    # Set environment variables
    os.environ['DEFAULT_VERSION_HOSTNAME'] = self.module.hostname
    os.environ['GAE_SERVICE'] = self.module.name
    # Set gunicorn config
    self.cfg.set('accesslog', '-')  # Log requests to stdout
    self.cfg.set('bind', self.bind_address)
    self.cfg.set('logconfig_dict', self.get_log_config())
    self.cfg.set('post_worker_init', lambda _: self.post_worker_init())
    self.cfg.set('reload', self.live_reload)
    self.cfg.set('threads', 10)  # Default max_concurrent_requests value
    # Increase worker timeout as errors may cause test runs to fail
    self.cfg.set('timeout', 5 * 60)
    self.cfg.set('worker_class', 'gthread')
    self.cfg.set(
        'workers', self.workers
    )  # Have multiple workers to ensure availability

  def load(self):
    return RawPathMiddleware(CloudNdbMiddleware(self.module.app))

  def get_log_config(self):
    log_config = LOG_CONFIG.copy()
    log_config['root']['level'] = self.log_level  # pytype: disable=unsupported-operands
    log_format = LOG_FORMAT.format(module=self.module.name)
    log_config['formatters']['default']['format'] = log_format
    return log_config

  def post_worker_init(self):
    threading.Thread(target=self.start_server).start()

  def start_server(self):
    response = requests.get('http://%s/_ah/start' % self.bind_address)
    status_code = response.status_code
    if 200 <= status_code <= 299 or status_code == 404:
      logging.info('Module %s started', self.module.name)
      return True  # Successfully started or no start handler defined
    logging.critical('Module %s failed to start', self.module.name)
    return False


def monkeypatch_default_auth():
  """Use anonymous credentials and application ID as the defaults."""
  from google import auth  
  from google.auth.credentials import AnonymousCredentials  
  auth.default = lambda **_: (AnonymousCredentials(), FLAGS.application_id)


def monkeypatch_crypt_rsa():
  """Use a pure-python RSA implementation which supports pickling."""
  from google.auth import crypt  
  from google.auth.crypt import _python_rsa  
  crypt.RSASigner = _python_rsa.RSASigner
  crypt.RSAVerifier = _python_rsa.RSAVerifier


def monkeypatch_read_consistency():
  """Use eventually consistent NDB queries by default (b/203420251).

  ATS uses the cloud datastore emulator which can leak memory if all queries
  (including those outside transactions) are forced to be strongly consistent.
  """
  from google.cloud.ndb import _datastore_api  
  _datastore_api.get_read_options = functools.partial(
      _datastore_api.get_read_options,
      default_read_consistency=_datastore_api.EVENTUAL)


def monkeypatch_grpc_message_length():
  """Remove the default gRPC message length limit used by NDB (b/195488504)."""
  import grpc  
  grpc.insecure_channel = functools.partial(
      grpc.insecure_channel, options=[('grpc.max_receive_message_length', -1)])


def set_env_variables():
  """Set the environment variables."""
  full_app_id.put(FLAGS.application_id)
  os.environ['DATASTORE_EMULATOR_HOST'] = FLAGS.datastore_emulator_host


def set_env_config(modules):
  """Set the TFC env_config and injects an InMemoryAppManager."""
  env_config.CONFIG = env_config.EnvConfig(
      device_info_snapshot_file_format='/device_info_snapshots/%s.gz',
      plugin=test_run_hook.TfcTaskInterceptor(),
      should_send_report=False,
      use_admin_api=False,
      use_google_api=False,
      should_sync_lab_config=False,
      should_sync_harness_image=False,
      should_manage_harness_update=False,
      event_queue_name='tfc-event-queue',
      object_event_filter=[
          common.ObjectEventType.REQUEST_STATE_CHANGED,
          common.ObjectEventType.COMMAND_ATTEMPT_STATE_CHANGED
      ],
      app_manager=InMemoryAppManager(modules),
      task_scheduler=rabbitmq_plugin.TaskScheduler())


def _wait_for_port(host, port, timeout):
  """Wait for a port to be ready."""
  end_time = time.time() + timeout
  while time.time() < end_time:
    try:
      with socket.create_connection((host, port), timeout=timeout):
        return
    except OSError:
      time.sleep(0.1)
  raise TimeoutError(
      '%s:%s not ready within %s seconds' % (host, port, timeout))


def main(_):
  # Parse module information and assign ports
  modules = {}
  for index, value in enumerate(FLAGS.module):
    name, path = value.split('=', 2)
    module = Module(name=name, path=path, port=FLAGS.port + index)
    modules[name] = module

  # Apply monkey patches and configure environment
  monkeypatch_default_auth()
  monkeypatch_crypt_rsa()
  monkeypatch_read_consistency()
  monkeypatch_grpc_message_length()
  set_env_variables()
  set_env_config(modules)

  # Spawn a child process for each module
  for module in modules.values():
    module_app = ModuleApplication(module)
    multiprocessing.Process(target=module_app.run).start()

  # Call init handler.
  if FLAGS.init:
    name, path = FLAGS.init.split(':', 2)
    _wait_for_port(FLAGS.host, modules[name].port, LAUNCH_TIMEOUT_SECONDS)
    url = 'http://%s:%s%s' % (FLAGS.host, modules[name].port, path)
    logging.info('Sending a init request: url=%s', url)
    response = requests.get(url)
    if response.ok:
      logging.info('The init complete!.')
    else:
      logging.critical('The init failed: response=%s', response)

if __name__ == '__main__':
  flags.mark_flag_as_required('application_id')
  flags.mark_flag_as_required('module')
  flags.mark_flag_as_required('datastore_emulator_host')
  absl_app.run(main)
