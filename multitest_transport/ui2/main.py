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

"""ATS UI flask server."""
import os

import flask


from multitest_transport.models import ndb_models
from multitest_transport.util import env

ROOT_PATH = os.path.dirname(__file__)
STATIC_PATH = os.path.join(ROOT_PATH, 'static')

APP = flask.Flask(
    __name__,
    root_path=ROOT_PATH,
    static_folder=None,
    template_folder=ROOT_PATH)


@APP.route('/static/<path:path>')
def Static(path):
  """Returns static files."""
  return flask.send_from_directory(STATIC_PATH, path, conditional=False)


@APP.route('/app.js')
def App():
  """Returns application script."""
  script = 'dev_sources.concat.js' if env.IS_DEV_MODE else 'app.js'
  return flask.send_from_directory(ROOT_PATH, script, conditional=False)


@APP.route('/newUI/', defaults={'path': ''})
@APP.route('/newUI/<path:path>')
def NewUI(path):
  """Redirects requests for /newUI/* to the Node.js Lab Console UI server.

  The new Lab Console UI is embedded in an iframe within the host/device
  details pages. To avoid specifying the port number in the frontend client
  code, which could be a security risk.
  The iframe's 'src' is set to a path like '/newUI/devices/123'. This
  request hits the main MTT server, which then redirects the browser to the
  actual location of the new UI server
  (e.g., http://localhost:4200/devices/123), running on env.LAB_CONSOLE_PORT.

  Args:
    path: subpath to redirect to on new UI server.
  """
  hostname = flask.request.host.split(':')[0]
  port = env.LAB_CONSOLE_PORT or '4200'
  query_string = flask.request.query_string.decode('utf-8')
  new_url = f'{flask.request.scheme}://{hostname}:{port}/{path}'
  if query_string:
    new_url = f'{new_url}?{query_string}'
  return flask.redirect(new_url)


@APP.route('/', defaults={'_': ''})
@APP.route('/<path:_>')
def Root(_):
  """Routes all other requests to index.html and angular."""
  private_node_config = ndb_models.GetPrivateNodeConfig()
  analytics_tracking_id = ''
  if not env.IS_DEV_MODE and private_node_config.metrics_enabled:
    analytics_tracking_id = 'UA-140187490-1'
  return flask.render_template(
      'index.html',
      analytics_tracking_id=analytics_tracking_id,
      env=env,
      private_node_config=private_node_config)
