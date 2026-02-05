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

from unittest import mock
from multitest_transport.api import api_test_util
from multitest_transport.api import request_api
from multitest_transport.util import olcs_session_stub
from protorpc import protojson
from tradefed_cluster import api_messages
from google3.testing.pybase import googletest


class RequestApiTest(api_test_util.TestCase):

  class RequestApiForTest(request_api.TestRequestApi):
    instance = None

    def __init__(self):
      RequestApiTest.RequestApiForTest.instance = self
      self._olcs_session_stub = mock.create_autospec(
          olcs_session_stub.OlcsSessionStub, spec_set=True
      )
      self._olcs_session_stub.GetRequest = mock.MagicMock()
      response = api_messages.RequestMessage()
      response.id = "request_id"
      command = api_messages.CommandMessage()
      command.id = "command_id"
      command.request_id = "request_id"
      command.command_line = "command_line"
      command.state = api_messages.CommandState.RUNNING
      command_attempt = api_messages.CommandAttemptMessage()
      command_attempt.attempt_id = "command_attempt_id"
      command_attempt.request_id = "request_id"
      command_attempt.command_id = "command_id"
      command_attempt.state = api_messages.CommandState.RUNNING
      command_attempt.task_id = "task_id"
      response.command_attempts = [command_attempt]
      response.commands = [command]
      response.next_attempt_session_id = "retry_request_id"

      retry_command_attempt = api_messages.CommandAttemptMessage()
      retry_command_attempt.attempt_id = "retry_command_attempt_id"
      retry_command_attempt.request_id = "retry_request_id"
      retry_command_attempt.command_id = "command_id"
      retry_command_attempt.state = api_messages.CommandState.RUNNING
      retry_command_attempt.task_id = "task_id"
      response.command_attempts.append(retry_command_attempt)

      self._olcs_session_stub.GetRequest.side_effect = (
          lambda request_id, **kwargs: {
              "request_id": response,
          }.get(request_id)
      )

  def setUp(self):
    super(RequestApiTest, self).setUp(RequestApiTest.RequestApiForTest)

  def testGetRequest(self):
    res = self.app.get("/_ah/api/mtt/v1/requests/%s" % "request_id")
    res_msg = protojson.decode_message(api_messages.RequestMessage, res.body)
    self.assertEqual(res_msg.id, "request_id")
    # Verify that GetRequest is called with notify_subscribers=False by default
    self.RequestApiForTest.instance._olcs_session_stub.GetRequest.assert_called_with(
        "request_id", notify_subscribers=False
    )

  def testGetRequest_force(self):
    res = self.app.get("/_ah/api/mtt/v1/requests/%s?force=true" % "request_id")
    res_msg = protojson.decode_message(api_messages.RequestMessage, res.body)
    self.assertEqual(res_msg.id, "request_id")
    # Verify that GetRequest is called with notify_subscribers=True
    self.RequestApiForTest.instance._olcs_session_stub.GetRequest.assert_called_with(
        "request_id", notify_subscribers=True
    )

  def testListCommandAttempts(self):
    res = self.app.get(
        "/_ah/api/mtt/v1/requests/%s/commands/%s/command_attempts"
        % ("request_id", "command_id")
    )
    res_msg = protojson.decode_message(
        api_messages.CommandAttemptMessageCollection, res.body
    )
    self.assertLen(res_msg.command_attempts, 2)
    command_attempt0 = res_msg.command_attempts[0]
    self.assertEqual(command_attempt0.attempt_id, "command_attempt_id")
    self.assertEqual(command_attempt0.request_id, "request_id")
    self.assertEqual(command_attempt0.command_id, "command_id")
    self.assertEqual(command_attempt0.state, api_messages.CommandState.RUNNING)

    command_attempt1 = res_msg.command_attempts[1]
    self.assertEqual(command_attempt1.attempt_id, "retry_command_attempt_id")
    self.assertEqual(command_attempt1.request_id, "retry_request_id")
    self.assertEqual(command_attempt1.command_id, "command_id")
    self.assertEqual(command_attempt1.state, api_messages.CommandState.RUNNING)

  def testGetStateStats(self):
    res = self.app.get(
        "/_ah/api/mtt/v1/requests/%s/commands/state_counts" % "request_id"
    )
    res_msg = protojson.decode_message(api_messages.CommandStateStats, res.body)
    command_state = res_msg.state_stats[0]
    self.assertEqual(command_state.state, api_messages.CommandState.RUNNING)
    self.assertEqual(command_state.count, 1)

  def testListCommands(self):
    res = self.app.get("/_ah/api/mtt/v1/requests/%s/commands" % "request_id")
    res_msg = protojson.decode_message(
        api_messages.CommandMessageCollection, res.body
    )
    command = res_msg.commands[0]
    self.assertEqual(command.id, "command_id")
    self.assertEqual(command.request_id, "request_id")


if __name__ == "__main__":
  googletest.main()
