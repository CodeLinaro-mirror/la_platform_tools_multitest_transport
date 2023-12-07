# Copyright 2023 Google LLC
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

from absl.testing import absltest
from multitest_transport.util import olcs_session_client

from com_google_deviceinfra.src.devtools.mobileharness.infra.client.longrunningservice.proto import session_service_pb2


class OlcsSessionClientTest(absltest.TestCase):

  def setUp(self):
    super().setUp()
    mock_stub = mock.create_autospec(session_service_pb2.SessionServiceStub)
    self.stubby_client = olcs_session_client.OlcsSessionClient(mock_stub)

  def testCreateSession(self):
    request = session_service_pb2.CreateSessionRequest()
    response = session_service_pb2.CreateSessionResponse()
    self.stubby_client._stub.CreateSession.return_value = response
    result = self.stubby_client.create_session(request)
    self.stubby_client._stub.CreateSession.assert_called_once_with(request)
    self.assertEqual(result, response)

  def testRunSession(self):
    request = session_service_pb2.RunSessionRequest()
    response = session_service_pb2.RunSessionResponse()
    self.stubby_client._stub.RunSession.return_value = response
    result = self.stubby_client.run_session(request)
    self.stubby_client._stub.RunSession.assert_called_once_with(request)
    self.assertEqual(result, response)

  def testGetSession(self):
    request = session_service_pb2.GetSessionRequest()
    response = session_service_pb2.GetSessionResponse()
    self.stubby_client._stub.GetSession.return_value = response
    result = self.stubby_client.get_session(request)
    self.stubby_client._stub.GetSession.assert_called_once_with(request)
    self.assertEqual(result, response)

  def testGetAllSessions(self):
    request = session_service_pb2.GetAllSessionsRequest()
    response = session_service_pb2.GetAllSessionsResponse()
    self.stubby_client._stub.GetAllSessions.return_value = response
    result = self.stubby_client.get_all_sessions(request)
    self.stubby_client._stub.GetAllSessions.assert_called_once_with(request)
    self.assertEqual(result, response)


if __name__ == "__main__":
  absltest.main()
