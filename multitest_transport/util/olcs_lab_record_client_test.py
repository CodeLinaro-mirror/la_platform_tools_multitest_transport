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
from absl.testing import absltest
from multitest_transport.util import olcs_lab_record_client
from com_google_deviceinfra.src.devtools.mobileharness.infra.master.rpc.proto import lab_record_service_pb2


class OlcsLabRecordClientTest(absltest.TestCase):

  def setUp(self):
    super().setUp()
    mock_stub = mock.create_autospec(
        lab_record_service_pb2.LabRecordServiceStub
    )
    self.stubby_client = olcs_lab_record_client.OlcsLabRecordClient(mock_stub)

  def testGetLabRecord(self):
    request = lab_record_service_pb2.GetLabRecordRequest()
    response = lab_record_service_pb2.GetLabRecordResponse()
    self.stubby_client._stub.GetLabRecord.return_value = response
    result = self.stubby_client.get_lab_record(request)
    self.stubby_client._stub.GetLabRecord.assert_called_once_with(request)
    self.assertEqual(result, response)

  def testGetDeviceRecord(self):
    request = lab_record_service_pb2.GetDeviceRecordRequest()
    response = lab_record_service_pb2.GetDeviceRecordResponse()
    self.stubby_client._stub.GetDeviceRecord.return_value = response
    result = self.stubby_client.get_device_record(request)
    self.stubby_client._stub.GetDeviceRecord.assert_called_once_with(request)
    self.assertEqual(result, response)


if __name__ == "__main__":
  absltest.main()
