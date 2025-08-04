# Copyright 2019 Google LLC
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

"""A utility for running actions on multiple remote hosts."""
import collections
from concurrent import futures
import functools
import getpass
import logging
import socket
import time


from multitest_transport.cli import command_util
from multitest_transport.cli import control_server_util
from multitest_transport.cli import gcs_file_util
from multitest_transport.cli import google_auth_util
from multitest_transport.cli import ssh_util
from tradefed_cluster.configs import lab_config


logger = logging.getLogger(__name__)


THREAD_WAIT_TIMEOUT_SECONDS = 0.01
THREAD_POLL_INTERVAL_SECONDS = 10
_DEFAULT_DOCKERIZED_TF_IMAGE = 'gcr.io/dockerized-tradefed/tradefed:golden'
_DEFAULT_MTT_IMAGE = 'gcr.io/android-mtt/mtt:prod'
_MTT_PROJECT = 'android-mtt'
_MAX_LOGGING_TIME_GAP_IN_SEC = 180
_DISCOVERY_URL = '{}/$discovery/rest?version=v1'
_HOST_UPDATE_STATE_CHANGED_EVENT_TYPE = 'HOST_UPDATE_STATE_CHANGED'
_DEFAULT_HTTP_TIMEOUT_SECONDS = 60


class ConfigurationError(Exception):
  """Configuration-related error."""


class ExecutionError(Exception):
  """Error for execution action on host."""


class HostExecutionState(object):
  """Execution stat for host."""
  UNKNOWN = 'UNKNOWN'
  COMPLETED = 'COMPLETED'
  ERROR = 'ERROR'


# LINT.IfChange(host_update_state)
class HostUpdateState(object):
  """Host update state."""
  UNKNOWN = 'UNKNOWN'
  PENDING = 'PENDING'
  SYNCING = 'SYNCING'
  SHUTTING_DOWN = 'SHUTTING_DOWN'
  RESTARTING = 'RESTARTING'
  SUCCEEDED = 'SUCCEEDED'
  ERRORED = 'ERRORED'
# LINT.ThenChange(//depot/google3/third_party/py/tradefed_cluster/\
#                   common.py:host_update_state)


class Host(object):
  """Host is a simple wrap which has host config and host context."""

  def __init__(
      self,
      host_config,
      ssh_config=None,
      sudo_ssh_config=None,
      context=None,
      metadata=None):
    self._config = host_config
    self._context = context
    self._ssh_config = ssh_config
    self._sudo_ssh_config = sudo_ssh_config
    self._execution_step = 0
    self._execution_state = HostExecutionState.UNKNOWN
    self._execution_start_time = None
    self._execution_end_time = None
    self._error = None
    self._control_server_client = None
    self._metadata = metadata or {}

  def StartExecutionTimer(self):
    self._execution_start_time = _GetCurrentTime()

  def StopExecutionTimer(self):
    self._execution_end_time = _GetCurrentTime()

  def InitControlServerClient(self):
    return self.control_server_client

  @property
  def name(self):
    return self._config.hostname

  @property
  def config(self):
    return self._config

  @config.setter
  def config(self, val):
    self._config = val

  @property
  def context(self):
    """Get remote context for the host."""
    if not self._context:
      try:
        self.execution_state = 'Connect to host'
        self._context = command_util.CommandContext(
            self.name,
            self.config.host_login_name,
            ssh_config=self._ssh_config,
            sudo_ssh_config=self._sudo_ssh_config)
      except command_util.AuthenticationError as e:
        logger.debug(e)
        raise
    return self._context

  @context.setter
  def context(self, context):
    self._context = context

  @property
  def metadata(self):
    return self._metadata

  @metadata.setter
  def metadata(self, metadata):
    self._metadata = metadata or {}

  @property
  def error(self):
    return self._error

  @error.setter
  def error(self, error):
    self._error = error

  @property
  def execution_state(self):
    return self._execution_state

  @property
  def execution_step(self):
    return self._execution_step

  @execution_state.setter
  def execution_state(self, state):
    self._execution_step += 1
    self._execution_state = state

  @property
  def execution_time_elapsed(self):
    """Get the execution time expression in text of host command."""
    if not self._execution_start_time:
      time_status = 'not started'
      time_elapsed_sec = 0
    elif not self._execution_end_time:
      time_status = 'running'
      time_elapsed_sec = _GetCurrentTime() - self._execution_start_time
    else:
      time_status = 'ended'
      time_elapsed_sec = self._execution_end_time - self._execution_start_time
    time_elapsed_text = '%d min %d s' % (
        time_elapsed_sec // 60, time_elapsed_sec % 60)
    return 'Time elapsed: %s(%s)' % (time_elapsed_text, time_status)

  @property
  def control_server_client(self):
    """Lazy load the instance of ControlServerClient.

    This allows use modified host config to create the client, after the
    instance of Host is initiated.
    """
    if not self._control_server_client:
      self._control_server_client = control_server_util.ControlServerClient(
          self.config.control_server_url,
          self.config.service_account_json_key_path,
          self.config.engprod_api_key)
    return self._control_server_client


def CreateHost(args):
  """Create a Host object for local host."""
  key_path = getattr(args, 'service_account_json_key_path', None)
  if not args.lab_config_path:
    # MTT standalone mode
    logger.info('No lab config path set; using standalone mode config')
    host_config = lab_config.CreateHostConfig(
        cluster_name='default',
        hostname=socket.getfqdn(),
        docker_image=_DEFAULT_MTT_IMAGE,
        shutdown_timeout_sec=60)
  else:
    host_config = _GetHostConfig(
        lab_config_path=args.lab_config_path, key_path=key_path)
    if not host_config.docker_image:
      host_config = host_config.SetDockerImage(_DEFAULT_DOCKERIZED_TF_IMAGE)
  host = Host(host_config, context=command_util.CommandContext())
  # override host configs from input args.
  if key_path:
    host.config = host.config.SetServiceAccountJsonKeyPath(key_path)
  return host


def _GetHostConfig(lab_config_path, key_path=None):
  """Get host config for local hosts."""
  # For dockerized tf, there should always be a lab config.
  lab_config_pool = BuildLabConfigPool(lab_config_path, key_path)
  for hostname in [socket.gethostname(), socket.getfqdn()]:
    host_config = lab_config_pool.GetHostConfig(hostname)
    if host_config:
      return host_config
  raise ConfigurationError(
      'There is no configuration for %s or %s in %s.' % (
          socket.gethostname(), socket.getfqdn(), lab_config_path))


def _GetMaxWorker(args, hosts):
  """Get max_worker for thread pool.

  Args:
    args: parsed args to pass to the function.
    hosts: a list of Hosts

  Returns:
    An int, the number of max worker thread.
  """
  
  if args.parallel is True:
    return len(hosts)
  elif args.parallel is False or args.parallel < 1:
    return 1
  
  else:
    return args.parallel


def _GetCurrentTime():
  """Get the current time in int sec.

  Returns:
    An int, the current time in sec.
  """
  return int(time.time())


def _ParallelExecute(host_func, args, hosts, execution_state_printer=None):
  """Execute a func on multiple contexts parallel.

  Args:
    host_func: the function to run.
    args: parsed args to pass to the function.
    hosts: a list of Hosts.
    execution_state_printer: to print execution_state.
  """
  max_workers = _GetMaxWorker(args, hosts)
  logger.info('Parallel executing %r on %r hosts with %r parallel threads.',
              host_func.__name__, len(hosts), max_workers)
  for host in hosts:
    host.InitControlServerClient()
  with futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
    future_to_host = {executor.submit(host_func, args, host): host
                      for host in hosts}
    running_futures = future_to_host.keys()
    while running_futures:
      # The timeout is important. Without timeout, the wait will block
      # all interactions such as interrupt key.
      finished_futures, running_futures = futures.wait(
          running_futures, timeout=THREAD_WAIT_TIMEOUT_SECONDS,
          return_when=futures.FIRST_COMPLETED)
      for f in finished_futures:
        host = future_to_host[f]
        try:
          f.result()
        except Exception as e:  
          logger.error('Failed %s on %s: %s.', host_func.__name__, host.name, e)
          host.control_server_client.SubmitHostUpdateStateChangedEvent(
              host.config.hostname, HostUpdateState.ERRORED,
              display_message=str(e), target_image=host.config.docker_image)
        else:
          logger.info('Succeeded %s on %s.', host_func.__name__, host.name)
      # Instead of blocking on the futures.wait, we waiting with sleep,
      # since sleep can be interrupted.
      if running_futures:
        if execution_state_printer:
          execution_state_printer.PrintState()
        time.sleep(THREAD_POLL_INTERVAL_SECONDS)


class ExecutionStatePrinter(object):
  """Logging exection state with less noisy."""

  def __init__(self, hosts):
    self._hosts = hosts
    self._previous_print_time = None
    self._previous_overview = None

  def PrintState(self):
    """Print hosts' state."""
    executing_hosts, completed_hosts, error_hosts = (
        self._GroupHostByState(self._hosts))
    overview = [
        (HostExecutionState.COMPLETED, len(completed_hosts)),
        (HostExecutionState.ERROR, len(error_hosts))]
    overview += [(state, len(hosts)) for state, hosts in executing_hosts]
    now = _GetCurrentTime()
    if (self._previous_overview and self._previous_overview == overview and
        self._previous_print_time and
        self._previous_print_time + _MAX_LOGGING_TIME_GAP_IN_SEC > now):
      return
    if completed_hosts:
      logger.info(
          '%r of %r hosts completed.', len(completed_hosts), len(self._hosts))
    if error_hosts:
      logger.error(
          '%r of %r hosts errored: %s',
          len(error_hosts), len(self._hosts),
          ' '.join([h.name for h in error_hosts]))
    for state, hosts_in_state in executing_hosts:
      logger.info(
          '%r of %r hosts in "%s": %s',
          len(hosts_in_state), len(self._hosts), state,
          ' '.join([h.name for h in hosts_in_state]))
    self._previous_print_time = now
    self._previous_overview = overview

  def PrintResult(self):
    """Print execution result."""
    executing_hosts, completed_hosts, error_hosts = (
        self._GroupHostByState(self._hosts))
    summary = []
    summary.append('Total: %r' % len(self._hosts))
    summary.append('Completed: %r' % len(completed_hosts))
    logger.info(
        '%r of %r hosts completed:', len(completed_hosts), len(self._hosts))
    for host in completed_hosts:
      logger.info('%s [%s]', host.name, host.execution_time_elapsed)

    summary.append('Error: %r' % len(error_hosts))
    error_msg = []
    if error_hosts:
      msg = '%r of %r hosts errored:' % (len(error_hosts), len(self._hosts))
      logger.error(msg)
      error_msg.append(msg + ' ' + ' '.join([h.name for h in error_hosts]))
      for host in error_hosts:
        logger.error('%s [%s]', host.name, host.execution_time_elapsed)
    if executing_hosts:
      for state, hosts in executing_hosts:
        summary.append('%s: %r' % (state, len(hosts)))
        msg = '%r of %r hosts in "%s":' % (len(hosts), len(self._hosts), state)
        logger.error(msg)
        error_msg.append(msg + ' ' + ' '.join([h.name for h in hosts]))
        for host in hosts:
          logger.error('%s [%s]', host.name, host.execution_time_elapsed)
    logger.info(', '.join(summary))
    if error_msg:
      error_msg = '\n'.join(error_msg)
      raise ExecutionError(error_msg)

  def _GroupHostByState(self, hosts):
    """Group hosts by their stat."""
    step_to_hosts = collections.defaultdict(list)
    error_hosts = []
    completed_hosts = []
    for host in hosts:
      if host.execution_state == HostExecutionState.ERROR:
        error_hosts.append(host)
      elif host.execution_state == HostExecutionState.COMPLETED:
        completed_hosts.append(host)
      else:
        step_to_hosts[(host.execution_step, host.execution_state)].append(host)
    executing_hosts = []
    for step in sorted(step_to_hosts.keys()):
      executing_hosts.append((step[1], step_to_hosts.get(step)))
    return executing_hosts, completed_hosts, error_hosts


def _SequentialExecute(
    host_func, args, hosts, exit_on_error=False, execution_state_printer=None):
  """Execute a func on multiple contexts sequentially.

  Args:
    host_func: the function to run on host.
    args: parsed args to pass to the function.
    hosts: a list of Hosts
    exit_on_error: exit on error or continue to execute.
    execution_state_printer: to print execution state.
  """
  # Run the function on a list of remote hosts sequentially.
  for host in hosts:
    host.InitControlServerClient()
    try:
      host_func(args, host)
      execution_state_printer.PrintState()
    except Exception as e:  
      logger.exception('Failed to run "%s" on %s.',
                       host_func.__name__, host.name)
      host.control_server_client.SubmitHostUpdateStateChangedEvent(
          host.config.hostname, HostUpdateState.ERRORED,
          target_image=host.config.docker_image)
      if exit_on_error:
        raise


def _WrapFuncForSetHost(host_func):
  """Create a wrapper for host_func so host's state will be set up."""

  @functools.wraps(host_func)
  def _Wrapper(args, host):
    """A wrapper over host_func so host's state will be set up."""
    if host.execution_state == HostExecutionState.ERROR:
      logger.debug(
          '%s already failed to run %s due to %s.',
          host.name, host_func.__name__, host.error)
      if host.error:
        raise host.error
      return
    if host.execution_state == HostExecutionState.COMPLETED:
      logger.debug('%s was completed for %s.', host.name, host_func.__name__)
      return
    host.StartExecutionTimer()
    try:
      host_func(args, host)
      host.execution_state = HostExecutionState.COMPLETED
    except Exception as e:  
      logger.debug(
          '%s failed to run %s due to %s.',
          host.name, host_func.__name__, e)
      host.error = e
      host.execution_state = HostExecutionState.ERROR
      raise
    finally:
      host.StopExecutionTimer()
  return _Wrapper


def BuildLabConfigPool(lab_config_path, key_path=None):
  """Build lab config pool based on configured config path."""
  if not lab_config_path:
    logger.debug('No lab config path set.')
    lab_config_pool = lab_config.LabConfigPool()
  elif lab_config_path.startswith('gs:'):
    logger.debug('Use lab config path %s.', lab_config_path)
    if key_path:
      cred = google_auth_util.CreateCredentialFromServiceAccount(
          key_path,
          scopes=[google_auth_util.GCS_READ_SCOPE])
    else:
      cred = google_auth_util.GetGCloudCredential(
          command_util.CommandContext())
    gcs_client = gcs_file_util.CreateGCSClient(_MTT_PROJECT, cred)
    lab_config_pool = lab_config.LabConfigPool(
        gcs_file_util.GCSFileEnumerator(
            gcs_client, lab_config_path, lab_config.IsYaml))
  else:
    logger.debug('Use lab config path %s.', lab_config_path)
    if lab_config.IsYaml(lab_config_path):
      lab_config_pool = lab_config.LabConfigPool(
          lab_config.LocalFileEnumerator(
              lab_config_path, lab_config.IsYaml))
    elif lab_config.IsUnifiedLabConfig(lab_config_path):
      lab_config_pool = lab_config.UnifiedLabConfigPool(lab_config_path)
    else:
      raise lab_config.ConfigError(
          f'{lab_config_path} is neither yaml lab config nor unified lab'
          ' config.'
      )
  lab_config_pool.LoadConfigs()
  return lab_config_pool


def _GetHostConfigs(lab_config_pool, hosts_or_clusters):
  """Get host configs for clusters.

  Args:
    lab_config_pool: a lab config pool
    hosts_or_clusters: a list of hosts or clusters.
  Returns:
    a list of HostConfigs.
  """
  if not hosts_or_clusters:
    return lab_config_pool.GetHostConfigs()
  host_configs = collections.OrderedDict()
  for host_or_cluster in hosts_or_clusters:
    host_config = lab_config_pool.GetHostConfig(host_or_cluster)
    if host_config:
      logger.debug('Found config for host %s.', host_or_cluster)
      host_configs[host_config.hostname] = host_config
      continue
    logger.debug('No host configured for %s.', host_or_cluster)
    host_configs_for_cluster = lab_config_pool.GetHostConfigs(
        host_or_cluster)
    if host_configs_for_cluster:
      logger.debug('Found config for cluster %s.', host_or_cluster)
      for host_config in host_configs_for_cluster:
        host_configs[host_config.hostname] = host_config
      continue
    logger.error('There is no config for %s, will skip.',
                 host_or_cluster)
  return list(host_configs.values())


def Execute(args, lab_config_pool=None):
  """Execute a command on hosts."""
  lab_config_pool = lab_config_pool or BuildLabConfigPool(
      args.lab_config_path, args.service_account_json_key_path)
  host_configs = _GetHostConfigs(lab_config_pool, args.hosts_or_clusters)
  if not host_configs:
    logger.warning('No host configured in %s for %s.',
                   args.lab_config_path,
                   args.hosts_or_clusters)
    return

  login_password = None
  if args.ask_login_password:
    login_password = getpass.getpass('Enter the login password:')
  sudo_password = None
  if args.ask_sudo_password:
    sudo_password = getpass.getpass('Enter the sudo password:')
  if not args.no_use_native_ssh:
    if args.use_native_ssh:
      logger.debug('Using native ssh instead of fabric.')
    if args.ssh_arg:
      logger.debug('Use ssh arg: %s', args.ssh_arg)
  else:
    logger.warning('Using fabric is deprecated, please use native ssh.')
  host_configs.sort(key=lambda host_config: host_config.hostname)
  hosts = []
  for host_config in host_configs:
    if (args.service_account_json_key_path and
        not host_config.service_account_json_key_path):
      host_config = host_config.SetServiceAccountJsonKeyPath(
          args.service_account_json_key_path)
    ssh_args = args.ssh_arg or host_config.ssh_arg
    if args.no_use_native_ssh:
      use_native_ssh = False
    else:
      # only native ssh support ssh_args
      use_native_ssh = bool(args.use_native_ssh or ssh_args)
    ssh_config = ssh_util.SshConfig(
        hostname=host_config.hostname,
        user=host_config.host_login_name,
        password=login_password,
        ssh_args=ssh_args,
        ssh_key=args.ssh_key,
        use_native_ssh=use_native_ssh)
    sudo_ssh_config = None
    if args.sudo_user or sudo_password:
      sudo_ssh_config = ssh_util.SshConfig(
          hostname=host_config.hostname,
          user=args.sudo_user or host_config.host_login_name,
          password=sudo_password or login_password,
          ssh_args=ssh_args,
          ssh_key=args.ssh_key,
          use_native_ssh=use_native_ssh)
    hosts.append(
        Host(host_config,
             ssh_config=ssh_config,
             sudo_ssh_config=sudo_ssh_config))
  execution_state_printer = ExecutionStatePrinter(hosts)
  try:
    f = _WrapFuncForSetHost(args.host_func)
    if args.parallel:
      _ParallelExecute(f, args, hosts, execution_state_printer)
    else:
      _SequentialExecute(
          f, args, hosts,
          exit_on_error=args.exit_on_error,
          execution_state_printer=execution_state_printer)
  except KeyboardInterrupt:
    logger.info('Receive KeyboardInterrupt.')
  finally:
    for host in hosts:
      try:
        if host.context:
          logger.debug('Closing %s.', host.name)
          host.context.Close()
      except Exception as e:  
        logger.error('Failed to close %s: %s.', host.name, e)
    logger.info('Finished executing "%s".', args.host_func.__name__)
    execution_state_printer.PrintResult()
