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

"""A module to provide node config APIs."""
# Non-standard docstrings are used to generate the API documentation.

import datetime

from protorpc import message_types
from protorpc import remote


from multitest_transport.api import base
from multitest_transport.models import config_encoder
from multitest_transport.models import messages
from multitest_transport.models import ndb_models
from multitest_transport.util import env


@base.MTT_API.api_class(resource_name='node_config', path='node_config')
class NodeConfigApi(remote.Service):
  """A handler for Node Config API."""

  @base.ApiMethod(message_types.VoidMessage, messages.NodeConfig,
                  http_method='GET', path='/node_config', name='get')
  def Get(self, request):
    """Fetches the server's node configuration."""
    node_config = ndb_models.GetNodeConfig()
    return messages.Convert(node_config, messages.NodeConfig)

  @base.ApiMethod(messages.NodeConfig, messages.NodeConfig,
                  http_method='PUT', path='/node_config', name='update')
  def Update(self, request):
    """Updates the server's node configuration.

    Body:
      Node configuration data
    """
    node_config = messages.Convert(
        request, ndb_models.NodeConfig, messages.NodeConfig)
    node_config.put()
    return messages.Convert(node_config, messages.NodeConfig)

  @base.ApiMethod(message_types.VoidMessage, messages.SimpleMessage,
                  http_method='GET', path='export', name='export')
  def ExportConfigData(self, request):
    """Exports the server's node configuration."""
    config_set = config_encoder.ConfigSet(
        node_config=ndb_models.GetNodeConfig(),
        build_channels=ndb_models.BuildChannelConfig.query().fetch(),
        device_actions=ndb_models.DeviceAction.query().fetch(),
        test_run_actions=ndb_models.TestRunAction.query().fetch(),
        # HIDDEN tests are exported as well.
        tests=ndb_models.Test.query().fetch(),
        file_cleaner=ndb_models.GetFileCleanerSettings(),
    )
    header = '# MTT Configuration - %s - %s\n' % (
        env.HOSTNAME, datetime.datetime.now())
    data = config_encoder.Encode(config_set)
    return messages.SimpleMessage(value=header + data)

  @base.ApiMethod(messages.SimpleMessage, message_types.VoidMessage,
                  http_method='POST', path='import', name='import')
  def ImportConfigData(self, request):
    """Imports another server's node configuration.

    Body:
      Exported node configuration data
    """
    config_set = config_encoder.Decode(request.value)
    config_encoder.Load(config_set)
    return message_types.VoidMessage()
