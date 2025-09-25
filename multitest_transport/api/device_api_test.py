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
import datetime
from unittest import mock

from absl.testing import absltest
from multitest_transport.api import api_test_util
from multitest_transport.api import device_api
from multitest_transport.util import olcs_lab_info_client
from multitest_transport.util import olcs_lab_info_stub
from multitest_transport.util import olcs_lab_record_client
from protorpc import protojson
from tradefed_cluster import api_messages

from com_google_deviceinfra.src.devtools.mobileharness.api.model.proto import device_pb2
from com_google_deviceinfra.src.devtools.mobileharness.infra.master.rpc.proto import lab_record_service_pb2
from com_google_deviceinfra.src.devtools.mobileharness.shared.labinfo.proto import lab_info_service_pb2


class DeviceApiTest(api_test_util.TestCase):

  class DeviceApiForTest(device_api.DeviceApi):

    def __init__(self):
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

      self._olcs_lab_info_client.get_lab_info.return_value = (
          get_lab_info_response
      )

      self._olcs_lab_record_client = mock.create_autospec(
          olcs_lab_record_client.OlcsLabRecordClient, spec_set=True
      )
      self._olcs_lab_record_client.get_lab_record = mock.MagicMock()
      get_device_record_response = (
          lab_record_service_pb2.GetDeviceRecordResponse()
      )
      device_record = (
          get_device_record_response.device_record_query_result.device_record.add()
      )
      device_record.timestamp.seconds = 60
      self._init_device_info(device_record.device_info)
      self._olcs_lab_record_client.get_device_record.return_value = (
          get_device_record_response
      )

      self._olcs_lab_info_stub = olcs_lab_info_stub.OlcsLabInfoStub(
          self._olcs_lab_info_client
      )

    def _init_device_info(self, device_info):
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
      dimension.name = 'sim_card_info'
      dimension.value = 'T-mobile'
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

  def setUp(self):
    super(DeviceApiTest, self).setUp(DeviceApiTest.DeviceApiForTest)

  def testListDevices(self):
    res = self.app.get('/_ah/api/mtt/v1/devices')
    res_msg = protojson.decode_message(
        api_messages.DeviceInfoCollection, res.body
    )
    self.assertEqual(
        [
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
                sim_state='READY',
                sim_operator='T-mobile',
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
                ],
                flated_extra_info=[],
                test_harness='OMNILAB',
                recovery_state='',
                last_recovery_time=datetime.datetime.utcfromtimestamp(0),
                is_stub_device=False,
                display_serial='device1',
                preconfigured_ip='127.0.0.1',
                preconfigured_device_num_offset=0,
            )
        ],
        res_msg.device_infos,
    )
    self.assertEqual('', res_msg.next_cursor)
    self.assertEqual('', res_msg.prev_cursor)
    self.assertEqual(False, res_msg.more)

  def testListDevices_NotMatchFilter(self):
    res = self.app.get('/_ah/api/mtt/v1/devices?host_groups=xxx')
    res_msg = protojson.decode_message(
        api_messages.DeviceInfoCollection, res.body
    )
    self.assertEqual(
        [],
        res_msg.device_infos,
    )
    self.assertEqual('', res_msg.next_cursor)
    self.assertEqual('', res_msg.prev_cursor)
    self.assertEqual(False, res_msg.more)

  def testGetDevice(self):
    res = self.app.get('/_ah/api/mtt/v1/devices/%s' % 'device_uuid1')
    res_msg = protojson.decode_message(api_messages.DeviceInfo, res.body)
    self.assertEqual(
        res_msg,
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
            sim_state='READY',
            sim_operator='T-mobile',
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

  def testListDeviceHistory(self):
    res = self.app.get('/_ah/api/mtt/v1/devices/%s/histories' % 'device_uuid1')
    res_msg = protojson.decode_message(
        api_messages.DeviceInfoHistoryCollection, res.body
    )
    self.assertEqual(
        res_msg.histories[0],
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
            sim_state='READY',
            sim_operator='T-mobile',
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


if __name__ == '__main__':
  absltest.main()
