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
import requests


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


def _Proxy(port, path):
  """Proxies requests to a backend server.

  This function acts as a reverse proxy. It receives incoming requests from
  clients on one of in-class methods(e.g. LabUIProxy or LabApiProxy),
  forwards them to another server (e.g. Lab Console UI or BE server)
  running on localhost at a specified port, and then returns the
  response from that server back to the original client.

  Args:
    port: The port on localhost where the backend server is running.
    path: The API path to which the request should be forwarded on the backend
      server.

  Returns:
    A Flask Response object containing the response from the backend server,
    or a 502 Bad Gateway response if the backend server cannot be reached.
  """
  # We assume that the backend server we want to proxy to is running on the
  # same machine (localhost).
  hostname = 'localhost'
  # Construct the full URL for the backend server by combining the hostname,
  # port, and path.
  url = f'http://{hostname}:{port}/{path}'
  try:
    # When forwarding the request, we want to include most of the headers from
    # the original request, such as authentication or content type.
    # However, we exclude the 'Host' header because the request is now being
    # sent to localhost, not the original host seen by the client.
    req_headers = {
        k: v for k, v in flask.request.headers if k.lower() != 'host'
    }
    # We use the 'requests' library to send a new request to the backend server.
    # This new request uses the same HTTP method (GET, POST, etc.), query
    # parameters, and data as the original incoming request.
    # 'stream=True' allows us to handle large responses efficiently without
    # loading everything into memory at once.
    # 'allow_redirects=False' prevents 'requests' from automatically following
    # redirect responses; we want to pass them back to the client instead.
    resp = requests.request(
        method=flask.request.method,
        url=url,
        params=flask.request.args,
        data=flask.request.get_data(),
        headers=req_headers,
        stream=True,
        allow_redirects=False,
    )
    # Some headers from the backend response should not be passed directly
    # back to the client, as they might interfere with how Flask or
    # intermediate proxies handle the connection. These include headers
    # related to content encoding and transfer that are managed by the proxy
    # itself.
    excluded_headers = [
        'content-encoding',
        'content-length',
        'transfer-encoding',
        'connection',
    ]
    # We filter the headers from the backend response, excluding those in
    # excluded_headers.
    headers = [
        (name, value)
        for (name, value) in resp.headers.items()
        if name.lower() not in excluded_headers
    ]
    # We create a new Flask Response.
    # 'flask.stream_with_context' ensures that the response content is streamed
    # from the backend server to the client piece by piece (in chunks of 1024
    # bytes), which is memory-efficient for large files or data streams.
    # We also pass through the status code (e.g., 200 OK, 404 Not Found) and
    # the filtered headers from the backend response.
    return flask.Response(
        flask.stream_with_context(resp.iter_content(chunk_size=1024)),
        status=resp.status_code,
        headers=headers,
    )
  except requests.exceptions.ConnectionError:
    # If we fail to connect to the backend server (e.g., if it's not running),
    # we return a 502 Bad Gateway error to the client, indicating that the
    # proxy could not reach the upstream server.
    return flask.Response(
        f'Could not connect to backend on port {port}', status=502
    )


# This decorator registers the LabUIProxy function to handle requests for
# paths starting with '/labui/'.
# It accepts various HTTP methods needed for a web UI and its assets.
# For example, a request to '/labui/foo' will call LabUIProxy(path='foo').
# A request to '/labui/' will call LabUIProxy(path='').
# Since the labui route is only handling some static files request, no need
# to proxy other method like POST, PUT, DELETE, etc.
@APP.route(
    '/labui/',
    defaults={'path': ''},
    methods=['GET'],
)
@APP.route(
    '/labui/<path:path>',
    methods=['GET'],
)
def LabUIProxy(path):
  """Proxies requests for /labui/* to the Node.js Lab Console UI server.

  This allows the Lab Console UI, running on a different port (e.g., 4200),
  to be accessed through the main application's port (e.g., 8000) under the
  /labui/ path. This is useful when only port 8000 is exposed to users.

  Args:
    path: The path requested under /labui/, which will be forwarded to the Lab
      Console UI server.

  Returns:
    A Flask Response proxied from the Lab Console UI server.
  """
  # We retrieve the port of the Lab Console UI server from environment
  # variables, defaulting to '4200' if not set.
  port = env.LAB_CONSOLE_PORT or '4200'
  # We call the generic _Proxy function to handle the forwarding.
  return _Proxy(port, path)


# This decorator registers the LabApiProxy function to handle requests for
# paths starting with '/labapi/'.
# It accepts various HTTP methods needed for a REST API.
# For example, a request to '/labapi/devices' will call
# LabApiProxy(path='devices').
@APP.route(
    '/labapi/',
    defaults={'path': ''},
    methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'OPTIONS'],
)
@APP.route(
    '/labapi/<path:path>',
    methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'OPTIONS'],
)
def LabApiProxy(path):
  """Proxies requests for /labapi/* to the Lab Console BE server.

  This allows the Lab Console UI (which may be running under /labui/ or
  on its own domain) to make API calls to its backend through the main
  application's port (e.g., 8000) under the /labapi/ path.

  Args:
    path: The API path requested under /labapi/, which will be forwarded to the
      Lab Console BE server.

  Returns:
    A Flask Response proxied from the Lab Console BE server.
  """
  # We retrieve the port of the Lab Console backend server from environment
  # variables, defaulting to '9000' if not set.
  port = env.LABCONSOLE_SERVER_REST_PORT or '9000'
  # We call the generic _Proxy function to handle the forwarding.
  return _Proxy(port, path)


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
