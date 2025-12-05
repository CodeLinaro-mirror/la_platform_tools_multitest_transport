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

"""Tests for tfc_client."""
import os
import threading
from unittest import mock

from absl.testing import absltest
import apiclient

from multitest_transport.util import olcs_lab_info_stub
from multitest_transport.util import tfc_client
from tradefed_cluster import api_messages
from tradefed_cluster import testbed_dependent_test
from tradefed_cluster.plugins import base as tfc_plugins


class TfcClientTest(testbed_dependent_test.TestbedDependentTest):

  def setUp(self):
    super(TfcClientTest, self).setUp()
    tfc_client._tls = threading.local()

  @mock.patch.object(apiclient.discovery, 'build')
  def testGetAPIClient(self, mock_build):
    self.mock_app_manager.GetInfo.return_value = tfc_plugins.AppInfo(
        name='default', hostname='hostname')

    api_client = tfc_client._GetAPIClient()

    mock_build.assert_called_with(
        tfc_client.API_NAME, tfc_client.API_VERSION, http=mock.ANY,
        discoveryServiceUrl=tfc_client.API_DISCOVERY_URL_FORMAT % (
            'hostname', tfc_client.API_NAME, tfc_client.API_VERSION))
    self.assertEqual(mock_build(), api_client)

  @mock.patch.object(tfc_client, '_GetOlcsLabInfoStub')
  def testListDevices_omniLabPagination(self, mock_get_olcs_lab_info_stub):
    os.environ['IS_OMNILAB_BASED'] = 'true'
    mock_stub = mock.MagicMock()
    mock_get_olcs_lab_info_stub.return_value = mock_stub
    device_info1 = api_messages.DeviceInfo(device_serial='device1')
    device_info2 = api_messages.DeviceInfo(device_serial='device2')
    response1 = api_messages.DeviceInfoCollection(
        device_infos=[device_info1], more=True, next_cursor='1'
    )
    response2 = api_messages.DeviceInfoCollection(
        device_infos=[device_info2], more=False
    )
    mock_stub.ListDevices.side_effect = [response1, response2]

    result = tfc_client.ListDevices()

    self.assertLen(result.device_infos, 2)
    self.assertEqual(result.device_infos[0], device_info1)
    self.assertEqual(result.device_infos[1], device_info2)
    mock_stub.ListDevices.assert_has_calls([
        mock.call(
            olcs_lab_info_stub.ListDevicesOptions(count=1000, cursor=None)
        ),
        mock.call(
            olcs_lab_info_stub.ListDevicesOptions(count=1000, cursor='1')
        ),
    ])
    del os.environ['IS_OMNILAB_BASED']


if __name__ == '__main__':
  absltest.main()
