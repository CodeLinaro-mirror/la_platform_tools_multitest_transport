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
import datetime
from typing import Optional

# Non-standard docstrings are used to generate the API documentation.

import endpoints
from protorpc import message_types
from protorpc import messages
from protorpc import remote


from multitest_transport.api import base
from tradefed_cluster import api_messages
from tradefed_cluster import common
from multitest_transport.test_scheduler import tfc_event_handler

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
    if test_request and test_request.state:
      request_event = api_messages.RequestEventMessage(
          type=common.ObjectEventType.REQUEST_STATE_CHANGED,
          request_id=request.request_id,
          new_state=test_request.state,
          request=test_request,
          event_time=datetime.datetime.now(),
      )
      tfc_event_handler.ProcessRequestEvent(request_event)
    return test_request
