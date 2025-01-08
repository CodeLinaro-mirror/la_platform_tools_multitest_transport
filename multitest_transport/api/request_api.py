# Copyright 2024 Google LLC
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

"""Test request APIs."""
from typing import Optional

# Non-standard docstrings are used to generate the API documentation.

import endpoints
from protorpc import message_types
from protorpc import messages
from protorpc import remote


from multitest_transport.api import base
from tradefed_cluster import api_messages
from tradefed_cluster import common

from multitest_transport.util import olcs_session_stub


@base.MTT_API.api_class(resource_name='request', path='requests')
class TestRequestApi(remote.Service):
  """Test request API."""

  def __init__(
      self,
      olcs_client: Optional[olcs_session_stub.OlcsSessionStub] = None,
  ):
    if olcs_client:
      self._olcs_session_stub = olcs_client
    else:
      self._olcs_session_stub = olcs_session_stub.OlcsSessionStub(None)

  @base.ApiMethod(
      endpoints.ResourceContainer(
          message_types.VoidMessage,
          request_id=messages.StringField(1, required=True),
      ),
      api_messages.RequestMessage,
      path='{request_id}',
      http_method='GET',
      name='get',
  )
  def GetRequest(self, request):
    test_request = self._olcs_session_stub.GetRequest(request.request_id)
    return test_request

  @base.ApiMethod(
      endpoints.ResourceContainer(
          message_types.VoidMessage,
          request_id=messages.StringField(1, required=True),
          command_id=messages.StringField(2, required=True),
      ),
      api_messages.CommandAttemptMessageCollection,
      path='{request_id}/commands/{command_id}/command_attempts',
      http_method='GET',
      name='command_attempts',
  )
  def ListCommandAttempts(self, request):
    test_request = self._olcs_session_stub.GetRequest(request.request_id)
    attempt_list = []
    if test_request:
      for command_attempt in test_request.command_attempts:
        if command_attempt.command_id == request.command_id:
          attempt_list.append(command_attempt)
    attempt_collection = api_messages.CommandAttemptMessageCollection(
        command_attempts=attempt_list
    )
    return attempt_collection

  @base.ApiMethod(
      endpoints.ResourceContainer(
          message_types.VoidMessage,
          request_id=messages.StringField(1, required=True),
      ),
      api_messages.CommandStateStats,
      path='{request_id}/commands/state_counts',
      http_method='GET',
      name='state_counts',
  )
  def GetCommandStateStats(self, request):
    test_request = self._olcs_session_stub.GetRequest(request.request_id)
    state_count_map = {}
    for command in test_request.commands:
      if command.state in state_count_map:
        state_count_map[command.state] += 1
      else:
        state_count_map[command.state] = 1
    command_state_stats = api_messages.CommandStateStats()
    state_list = []
    for state, count in state_count_map.items():
      command_state = api_messages.CommandStateStat()
      command_state.state = state
      command_state.count = count
      state_list.append(command_state)
    command_state_stats.state_stats = state_list
    command_state_stats.create_time = test_request.start_time
    return command_state_stats

  # TODO: implement pages.
  @base.ApiMethod(
      endpoints.ResourceContainer(
          message_types.VoidMessage,
          request_id=messages.StringField(1, required=True),
          state=messages.EnumField(common.CommandState, 2),
          page_size=messages.IntegerField(3, default=10),
          page_token=messages.StringField(4, default=None),
      ),
      api_messages.CommandMessageCollection,
      path='{request_id}/commands',
      http_method='GET',
      name='commands',
  )
  def ListCommands(self, request):
    test_request = self._olcs_session_stub.GetRequest(request.request_id)
    command_collection = api_messages.CommandMessageCollection()
    command_collection.commands = test_request.commands
    command_collection.page_token = None
    return command_collection
