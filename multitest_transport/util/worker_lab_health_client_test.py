# Copyright 2025 Google LLC
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
from unittest import mock
from absl.testing import absltest
import grpc
import grpc_testing
from multitest_transport.util import channel_util
from multitest_transport.util import worker_lab_health_client
from com_google_deviceinfra.src.devtools.deviceinfra.host.daemon.proto import health_pb2


class WorkerLabHealthClientTest(absltest.TestCase):

  def setUp(self):
    super().setUp()
    self._executor = futures.ThreadPoolExecutor(max_workers=1)
    self._time = grpc_testing.strict_real_time()
    self._descriptor = health_pb2.DESCRIPTOR.services_by_name['Health']
    self._channel = grpc_testing.channel(
        self._descriptor,
        self._time,
    )
    self._trailing_metadata = ()
    self._detailed_message = ''

  def tearDown(self):
    self._executor.shutdown(wait=True)
    super().tearDown()

  @mock.patch.object(channel_util, 'WorkerLabServerChannel', autospec=True)
  def testCreate_withoutServerAddress(self, mock_worker_lab_server_channel):
    mock_worker_lab_server_channel_instance = (
        mock_worker_lab_server_channel.return_value
    )
    mock_worker_lab_server_channel_instance.get_channel.return_value = (
        self._channel
    )

    client = worker_lab_health_client.WorkerLabHealthClient.create()

    mock_worker_lab_server_channel.assert_called_once_with(None)
    self.assertIsInstance(
        client, worker_lab_health_client.WorkerLabHealthClient
    )

  @mock.patch.object(channel_util, 'WorkerLabServerChannel', autospec=True)
  def testCreate_withServerAddress(self, mock_worker_lab_server_channel):
    mock_worker_lab_server_channel_instance = (
        mock_worker_lab_server_channel.return_value
    )
    mock_worker_lab_server_channel_instance.get_channel.return_value = (
        self._channel
    )
    server_address = 'localhost:50001'

    client = worker_lab_health_client.WorkerLabHealthClient.create(
        server_address=server_address
    )

    mock_worker_lab_server_channel.assert_called_once_with(server_address)
    self.assertIsInstance(
        client, worker_lab_health_client.WorkerLabHealthClient
    )

  def testDrain(self):
    self._client = worker_lab_health_client.WorkerLabHealthClient(self._channel)
    request = health_pb2.DrainServerRequest()
    response = health_pb2.DrainServerResponse()

    application_future = self._executor.submit(self._client.drain, request)
    _, actual_request, rpc = self._channel.take_unary_unary(
        self._descriptor.methods_by_name['Drain']
    )
    rpc.send_initial_metadata(())
    rpc.terminate(
        response,
        self._trailing_metadata,
        grpc.StatusCode.OK,
        self._detailed_message,
    )

    actual_response = application_future.result()
    self.assertEqual(actual_request, request)
    self.assertEqual(actual_response, response)

  def testCheckDrainStatus(self):
    self._client = worker_lab_health_client.WorkerLabHealthClient(self._channel)
    request = health_pb2.CheckStatusRequest()
    response = health_pb2.CheckStatusResponse()

    application_future = self._executor.submit(self._client.check, request)
    _, actual_request, rpc = self._channel.take_unary_unary(
        self._descriptor.methods_by_name['Check']
    )
    rpc.send_initial_metadata(())
    rpc.terminate(
        response,
        self._trailing_metadata,
        grpc.StatusCode.OK,
        self._detailed_message,
    )

    actual_response = application_future.result()
    self.assertEqual(actual_request, request)
    self.assertEqual(actual_response, response)


if __name__ == '__main__':
  absltest.main()
