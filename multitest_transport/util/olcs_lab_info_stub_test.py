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


import datetime
from unittest import mock

from absl.testing import absltest
from multitest_transport.util import olcs_lab_info_client
from multitest_transport.util import olcs_lab_info_stub
from tradefed_cluster import api_messages

from com_google_deviceinfra.src.devtools.mobileharness.api.model.proto import device_pb2
from com_google_deviceinfra.src.devtools.mobileharness.shared.labinfo.proto import lab_info_service_pb2


class OlcsLabInfoStubTest(absltest.TestCase):

  def setUp(self):
    """Sets up the OlcsLabInfoStubTest."""
    super().setUp()
    self._olcs_lab_info_client = mock.create_autospec(
        olcs_lab_info_client.OlcsLabInfoClient, spec_set=True
    )
    self._olcs_lab_info_client.get_lab_info = mock.MagicMock()

    get_lab_info_response = lab_info_service_pb2.GetLabInfoResponse()
    get_lab_info_response.lab_query_result.timestamp.seconds = 60
    device_info = (
        get_lab_info_response.lab_query_result.device_view.grouped_devices.device_list.device_info.add()
    )
    self._init_device_info(device_info)

    self._olcs_lab_info_client.get_lab_info.return_value = get_lab_info_response
    self._olcs_lab_info_stub = olcs_lab_info_stub.OlcsLabInfoStub(
        self._olcs_lab_info_client
    )

  def _init_device_info(self, device_info):
    """Initializes the device info."""
    device_info.device_locator.id = 'device_uuid1'
    device_info.device_locator.lab_locator.ip = '127.0.0.1'
    device_info.device_locator.lab_locator.host_name = 'localhost'
    device_info.device_status = device_pb2.DeviceStatus.IDLE
    device_info.device_feature.type.append('AndroidRealDevice')
    dimension = (
        device_info.device_feature.composite_dimension.supported_dimension.add()
    )
    dimension.name = 'product_board'
    dimension.value = 'panther'
    dimension = (
        device_info.device_feature.composite_dimension.supported_dimension.add()
    )
    dimension.name = 'device'
    dimension.value = 'panther_variant'
    dimension = (
        device_info.device_feature.composite_dimension.supported_dimension.add()
    )
    dimension.name = 'build'
    dimension.value = 'aosp_arm64-userdebug'
    dimension = (
        device_info.device_feature.composite_dimension.supported_dimension.add()
    )
    dimension.name = 'sdk_version'
    dimension.value = '34'
    dimension = (
        device_info.device_feature.composite_dimension.supported_dimension.add()
    )
    dimension.name = 'cluster'
    dimension.value = 'presubmit'
    dimension = (
        device_info.device_feature.composite_dimension.supported_dimension.add()
    )
    dimension.name = 'mac_address'
    dimension.value = '00:90:4c:d2:b1:9e'
    dimension = (
        device_info.device_feature.composite_dimension.supported_dimension.add()
    )
    dimension.name = 'lab_location'
    dimension.value = 'bej'
    dimension = (
        device_info.device_feature.composite_dimension.supported_dimension.add()
    )
    dimension.name = 'battery_level'
    dimension.value = '90'
    dimension = (
        device_info.device_feature.composite_dimension.supported_dimension.add()
    )
    dimension.name = 'sim_operator_alpha'
    dimension.value = 'T-mobile'
    dimension = (
        device_info.device_feature.composite_dimension.supported_dimension.add()
    )
    dimension.name = 'sim_state'
    dimension.value = 'READY'
    dimension = (
        device_info.device_feature.composite_dimension.supported_dimension.add()
    )
    dimension.name = 'control_id'
    dimension.value = 'device1'
    dimension = (
        device_info.device_feature.composite_dimension.supported_dimension.add()
    )
    dimension.name = 'type'
    dimension.value = 'panther_name'

  def _create_list_devices_options(
      self,
      hostname=None,
      hostnames=None,
      device_serial=None,
      cursor=None,
      count=10,
      host_groups=None,
      device_states=None,
      device_types=None,
      test_harnesses=None,
      run_targets=None,
      pools=None,
  ):
    return olcs_lab_info_stub.ListDevicesOptions(
        hostname=hostname,
        hostnames=hostnames,
        device_serial=device_serial,
        cursor=cursor,
        count=count,
        host_groups=host_groups,
        device_states=device_states,
        device_types=device_types,
        test_harnesses=test_harnesses,
        run_targets=run_targets,
        pools=pools,
    )

  def testGetDevice(self):
    """Tests the GetDevice method."""
    device_info = self._olcs_lab_info_stub.GetDevice('device_uuid1')
    self.assertEqual(
        device_info,
        api_messages.DeviceInfo(
            device_serial='device_uuid1',
            lab_name='bej',
            hostname='localhost',
            run_target='panther',
            build_id='aosp_arm64-userdebug',
            product='panther',
            product_variant='panther_variant',
            sdk_version='34',
            state='Available',
            timestamp=datetime.datetime.utcfromtimestamp(60),
            battery_level='90',
            hidden=False,
            notes=[],
            history=[],
            utilization=0.0,
            cluster='presubmit',
            host_group='presubmit',
            pools=['presubmit'],
            device_type=api_messages.DeviceTypeMessage.PHYSICAL,
            mac_address='00:90:4c:d2:b1:9e',
            group_name='',
            sim_operator='T-mobile',
            sim_state='READY',
            extra_info=[
                api_messages.KeyValuePair(key='battery_level', value='90'),
                api_messages.KeyValuePair(key='sdk_version', value='34'),
                api_messages.KeyValuePair(
                    key='build_id', value='aosp_arm64-userdebug'
                ),
                api_messages.KeyValuePair(key='product', value='panther'),
                api_messages.KeyValuePair(
                    key='product_variant', value='panther_variant'
                ),
                api_messages.KeyValuePair(
                    key='product_name', value='panther_name'
                ),
                api_messages.KeyValuePair(key='sim_operator', value='T-mobile'),
                api_messages.KeyValuePair(key='sim_state', value='READY'),
            ],
            flated_extra_info=[],
            test_harness='OMNILAB',
            recovery_state='',
            last_recovery_time=datetime.datetime.utcfromtimestamp(0),
            is_stub_device=False,
            display_serial='device1',
            preconfigured_ip='127.0.0.1',
            preconfigured_device_num_offset=0,
        ),
    )

  def testGetDevice_failedDevice_returnsFailedState(self):
    """Tests that a device with FailedDevice type returns FAILED state."""
    get_lab_info_response = lab_info_service_pb2.GetLabInfoResponse()
    get_lab_info_response.lab_query_result.timestamp.seconds = 60
    device_info = (
        get_lab_info_response.lab_query_result.device_view.grouped_devices.device_list.device_info.add()
    )
    self._init_device_info(device_info)
    device_info.device_feature.type.append('FailedDevice')
    self._olcs_lab_info_client.get_lab_info.return_value = get_lab_info_response

    device_info = self._olcs_lab_info_stub.GetDevice('device_uuid1')

    self.assertEqual(device_info.state, 'FAILED')

  def testListDevices_match(self):
    """Tests the ListDevices method."""
    options = self._create_list_devices_options(
        hostname='localhost',
        host_groups=['presubmit'],
        device_states=['Available'],
        device_types=[api_messages.DeviceTypeMessage.PHYSICAL],
        test_harnesses=['OMNILAB'],
        run_targets=['panther'],
        pools=['presubmit'],
    )

    device_info_collection = self._olcs_lab_info_stub.ListDevices(options)
    self.assertLen(device_info_collection.device_infos, 1)
    self.assertEqual(
        device_info_collection.device_infos[0],
        self._olcs_lab_info_stub.GetDevice('device_uuid1'),
    )

  def testListDevices_noHostGroupMatch(self):
    options = self._create_list_devices_options(
        hostname='localhost',
        host_groups=['no_match'],
    )
    device_info_collection = self._olcs_lab_info_stub.ListDevices(options)
    self.assertEmpty(device_info_collection.device_infos)

  def testListDevices_noDeviceStateMatch(self):
    options = self._create_list_devices_options(
        hostname='localhost',
        device_states=['Allocated'],
    )
    device_info_collection = self._olcs_lab_info_stub.ListDevices(options)
    self.assertEmpty(device_info_collection.device_infos)

  def testListDevices_noDeviceTypeMatch(self):
    options = self._create_list_devices_options(
        hostname='localhost',
        device_types=[api_messages.DeviceTypeMessage.NULL],
    )
    device_info_collection = self._olcs_lab_info_stub.ListDevices(options)
    self.assertEmpty(device_info_collection.device_infos)

  def testListDevices_noTestHarnessMatch(self):
    options = self._create_list_devices_options(
        hostname='localhost',
        test_harnesses=['OTHER'],
    )
    device_info_collection = self._olcs_lab_info_stub.ListDevices(options)
    self.assertEmpty(device_info_collection.device_infos)

  def testListDevices_noRunTargetMatch(self):
    options = self._create_list_devices_options(
        hostname='localhost',
        run_targets=['no-match'],
    )
    device_info_collection = self._olcs_lab_info_stub.ListDevices(options)
    self.assertEmpty(device_info_collection.device_infos)

  def testListDevices_noPoolMatch(self):
    options = self._create_list_devices_options(
        hostname='localhost',
        pools=['no-match'],
    )
    device_info_collection = self._olcs_lab_info_stub.ListDevices(options)
    self.assertEmpty(device_info_collection.device_infos)

  def testListDevices_withPagination(self):
    get_lab_info_response = lab_info_service_pb2.GetLabInfoResponse()
    get_lab_info_response.lab_query_result.timestamp.seconds = 60
    device_info = (
        get_lab_info_response.lab_query_result.device_view.grouped_devices.device_list.device_info.add()
    )
    self._init_device_info(device_info)
    device_info_2 = (
        get_lab_info_response.lab_query_result.device_view.grouped_devices.device_list.device_info.add()
    )
    self._init_device_info(device_info_2)
    device_info_2.device_locator.id = 'device_uuid2'
    self._olcs_lab_info_client.get_lab_info.return_value = get_lab_info_response
    options = self._create_list_devices_options(count=1)

    device_info_collection = self._olcs_lab_info_stub.ListDevices(options)
    self.assertLen(device_info_collection.device_infos, 1)
    self.assertEqual(device_info_collection.next_cursor, '1')
    self.assertEqual(device_info_collection.prev_cursor, '')
    self.assertTrue(device_info_collection.more)

    options.cursor = '1'
    device_info_collection = self._olcs_lab_info_stub.ListDevices(options)
    self.assertLen(device_info_collection.device_infos, 1)
    self.assertEqual(device_info_collection.next_cursor, '')
    self.assertEqual(device_info_collection.prev_cursor, '1')
    self.assertFalse(device_info_collection.more)

  def testListDevices_withBackendPagination(self):
    get_lab_info_response1 = lab_info_service_pb2.GetLabInfoResponse()
    get_lab_info_response1.lab_query_result.timestamp.seconds = 60
    for i in range(1000):
      device_info = (
          get_lab_info_response1.lab_query_result.device_view.grouped_devices.device_list.device_info.add()
      )
      self._init_device_info(device_info)
      device_info.device_locator.id = f'device_uuid_{i}'

    get_lab_info_response2 = lab_info_service_pb2.GetLabInfoResponse()
    get_lab_info_response2.lab_query_result.timestamp.seconds = 60
    device_info = (
        get_lab_info_response2.lab_query_result.device_view.grouped_devices.device_list.device_info.add()
    )
    self._init_device_info(device_info)
    device_info.device_locator.id = 'device_uuid_1000'

    self._olcs_lab_info_client.get_lab_info.side_effect = [
        get_lab_info_response1,
        get_lab_info_response2,
    ]
    options = self._create_list_devices_options(count=1001)

    device_info_collection = self._olcs_lab_info_stub.ListDevices(options)

    self.assertLen(device_info_collection.device_infos, 1001)
    self.assertEqual(self._olcs_lab_info_client.get_lab_info.call_count, 2)
    # Check offsets in calls to get_lab_info
    args0, _ = self._olcs_lab_info_client.get_lab_info.call_args_list[0]
    args1, _ = self._olcs_lab_info_client.get_lab_info.call_args_list[1]
    self.assertEqual(args0[0].page.offset, 0)
    self.assertEqual(args1[0].page.offset, 1000)


if __name__ == '__main__':
  absltest.main()
