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
from concurrent import futures

from absl.testing import absltest
import grpc
import grpc_testing
from multitest_transport.util import olcs_session_client

from com_google_deviceinfra.src.devtools.mobileharness.infra.client.longrunningservice.proto import session_pb2
from com_google_deviceinfra.src.devtools.mobileharness.infra.client.longrunningservice.proto import session_service_pb2


class OlcsSessionClientTest(absltest.TestCase):

  def setUp(self):
    super().setUp()
    self._executor = futures.ThreadPoolExecutor(max_workers=1)
    self._time = grpc_testing.strict_real_time()
    self._descriptor = session_service_pb2.DESCRIPTOR.services_by_name[
        'SessionService'
    ]
    self._channel = grpc_testing.channel(
        self._descriptor,
        grpc_testing.strict_real_time(),
    )
    self._stubby_client = olcs_session_client.OlcsSessionClient(self._channel)
    self._trailing_metadata = ()
    self._detailed_message = ''

  def tearDown(self):
    self._executor.shutdown(wait=True)
    super().tearDown()

  def testCreateSession(self):
    test_request = session_service_pb2.CreateSessionRequest()
    test_response = session_service_pb2.CreateSessionResponse()
    application_future = self._executor.submit(
        self._stubby_client.create_session, test_request
    )
    _, request, rpc = self._channel.take_unary_unary(
        self._descriptor.methods_by_name['CreateSession']
    )
    self.assertEqual(request, test_request)

    rpc.send_initial_metadata(())
    rpc.terminate(
        test_response,
        self._trailing_metadata,
        grpc.StatusCode.OK,
        self._detailed_message,
    )
    result = application_future.result()
    self.assertIs(result, test_response)

  def testRunSession(self):
    test_request = session_service_pb2.RunSessionRequest()
    test_response = session_service_pb2.RunSessionResponse()
    application_future = self._executor.submit(
        self._stubby_client.run_session, test_request
    )
    _, request, rpc = self._channel.take_unary_unary(
        self._descriptor.methods_by_name['RunSession']
    )
    self.assertEqual(request, test_request)

    rpc.send_initial_metadata(())
    rpc.terminate(
        test_response,
        self._trailing_metadata,
        grpc.StatusCode.OK,
        self._detailed_message,
    )
    result = application_future.result()
    self.assertIs(result, test_response)

  def testGetSession(self):
    test_request = session_service_pb2.GetSessionRequest()
    test_response = session_service_pb2.GetSessionResponse()
    application_future = self._executor.submit(
        self._stubby_client.get_session, test_request
    )
    _, request, rpc = self._channel.take_unary_unary(
        self._descriptor.methods_by_name['GetSession']
    )
    self.assertEqual(request, test_request)

    rpc.send_initial_metadata(())
    rpc.terminate(
        test_response,
        self._trailing_metadata,
        grpc.StatusCode.OK,
        self._detailed_message,
    )
    result = application_future.result()
    self.assertIs(result, test_response)

  def testGetAllSessions(self):
    test_request = session_service_pb2.GetAllSessionsRequest()
    test_response = session_service_pb2.GetAllSessionsResponse()
    application_future = self._executor.submit(
        self._stubby_client.get_all_sessions, test_request
    )
    _, request, rpc = self._channel.take_unary_unary(
        self._descriptor.methods_by_name['GetAllSessions']
    )
    self.assertEqual(request, test_request)

    rpc.send_initial_metadata(())
    rpc.terminate(
        test_response,
        self._trailing_metadata,
        grpc.StatusCode.OK,
        self._detailed_message,
    )
    result = application_future.result()
    self.assertIs(result, test_response)

  def testSubscribeSession(self):
    test_request = [session_service_pb2.SubscribeSessionRequest()]
    response_1 = session_service_pb2.SubscribeSessionResponse()
    response_1.get_session_response.session_detail.session_id.id = (
        'session_id_1'
    )
    response_1.get_session_response.session_detail.session_status = (
        session_pb2.SessionStatus.SESSION_RUNNING
    )
    response_2 = session_service_pb2.SubscribeSessionResponse()
    response_2.get_session_response.session_detail.session_id.id = (
        'session_id_1'
    )
    response_2.get_session_response.session_detail.session_status = (
        session_pb2.SessionStatus.SESSION_FINISHED
    )
    application_future = self._executor.submit(
        self._stubby_client.subscribe_session, iter(test_request)
    )
    _, rpc = self._channel.take_stream_stream(
        self._descriptor.methods_by_name['SubscribeSession']
    )

    rpc.send_initial_metadata(())
    first_request = rpc.take_request()
    rpc.send_response(response_1)
    rpc.send_response(response_2)
    rpc.requests_closed()
    rpc.terminate(
        self._trailing_metadata,
        grpc.StatusCode.OK,
        self._detailed_message,
    )
    result = application_future.result()
    self.assertEqual(first_request, test_request[0])
    self.assertCountEqual(result, [response_1, response_2])

  def testNotifySession(self):
    test_request = session_service_pb2.NotifySessionRequest()
    test_response = session_service_pb2.NotifySessionResponse()
    application_future = self._executor.submit(
        self._stubby_client.notify_session, test_request
    )
    _, request, rpc = self._channel.take_unary_unary(
        self._descriptor.methods_by_name['NotifySession']
    )
    self.assertEqual(request, test_request)

    rpc.send_initial_metadata(())
    rpc.terminate(
        test_response,
        self._trailing_metadata,
        grpc.StatusCode.OK,
        self._detailed_message,
    )
    result = application_future.result()
    self.assertIs(result, test_response)

  def testAbortSessions(self):
    test_request = session_service_pb2.AbortSessionsRequest()
    test_response = session_service_pb2.AbortSessionsResponse()
    application_future = self._executor.submit(
        self._stubby_client.abort_sessions, test_request
    )
    _, request, rpc = self._channel.take_unary_unary(
        self._descriptor.methods_by_name['AbortSessions']
    )
    self.assertEqual(request, test_request)

    rpc.send_initial_metadata(())
    rpc.terminate(
        test_response,
        self._trailing_metadata,
        grpc.StatusCode.OK,
        self._detailed_message,
    )
    result = application_future.result()
    self.assertIs(result, test_response)


if __name__ == '__main__':
  absltest.main()
