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

"""An API server module."""
import endpoints
import flask
from tradefed_cluster import api as tfc_api


from multitest_transport.api import base
from multitest_transport.api import build_api
from multitest_transport.api import build_channel_api
from multitest_transport.api import build_channel_provider_api
from multitest_transport.api import config_set_api
from multitest_transport.api import device_action_api
from multitest_transport.api import device_api
from multitest_transport.api import request_api
from multitest_transport.api import file_cleaner_api
from multitest_transport.api import ats_filter_hint_api
from multitest_transport.api import host_api
from multitest_transport.api import node_config_api
from multitest_transport.api import netdata_api
from multitest_transport.api import openapi
from multitest_transport.api import private_node_config_api
from multitest_transport.api import test_api
from multitest_transport.api import test_plan_api
from multitest_transport.api import test_result_api
from multitest_transport.api import test_run_action_api
from multitest_transport.api import test_run_api
from multitest_transport.util import env

# List of REST API handlers
API_HANDLERS = [
    build_api.BuildApi,
    build_channel_api.BuildChannelApi,
    build_channel_provider_api.BuildChannelProviderApi,
    config_set_api.ConfigSetApi,
    device_api.DeviceApi,
    request_api.TestRequestApi,
    device_action_api.DeviceActionApi,
    file_cleaner_api.FileCleanerApi,
    ats_filter_hint_api.AtsFilterHintApi,
    host_api.HostApi,
    netdata_api.NetdataApi,
    node_config_api.NodeConfigApi,
    private_node_config_api.PrivateNodeConfigApi,
    test_api.TestApi,
    test_plan_api.TestPlanApi,
    test_result_api.TestResultApi,
    test_run_action_api.TestRunActionApi,
    test_run_api.TestRunApi,
]

# REST API WSGI app
APP = endpoints.api_server([base.MTT_API] + tfc_api.API_HANDLERS)

# API documentation WSGI app
DOCS_APP = flask.Flask(__name__, template_folder='.')


@DOCS_APP.route('/_ah/api_docs/api.json')
def GetApiSpec():
  """Returns the OpenAPI specification."""
  api_spec = openapi.DescriptiveOpenApiGenerator().get_openapi_dict(
      API_HANDLERS, hostname=env.HOSTNAME)
  return flask.jsonify(api_spec)


@DOCS_APP.route('/_ah/api_docs', strict_slashes=False, defaults={'path': ''})
@DOCS_APP.route('/_ah/api_docs/<path:path>')
def RenderApiExplorer(path):
  """Renders the API explorer page."""
  del path  # unused
  return flask.render_template('docs.html')
