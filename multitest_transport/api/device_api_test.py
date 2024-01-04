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
from protorpc import protojson
from tradefed_cluster import api_messages

from com_google_deviceinfra.src.devtools.mobileharness.api.model.proto import device_pb2
from com_google_deviceinfra.src.devtools.mobileharness.infra.master.rpc.proto import lab_info_service_pb2


class DeviceApiTest(api_test_util.TestCase):

  class DeviceApiForTest(device_api.DeviceApi):

    def __init__(self):
      self._olcs_lab_info_client = mock.create_autospec(
          olcs_lab_info_client.OlcsLabInfoClient, spec_set=True
      )
      self._olcs_lab_info_client.get_lab_info = mock.MagicMock()
      response = lab_info_service_pb2.GetLabInfoResponse()
      response.lab_query_result.timestamp.seconds = 60
      device_info = (
          response.lab_query_result.device_view.grouped_devices.device_list.device_info.add()
      )
      device_info.device_locator.id = 'device1'
      device_info.device_locator.lab_locator.ip = '127.0.0.1'
      device_info.device_locator.lab_locator.host_name = 'localhost'
      device_info.device_uuid = 'device_uuid1'
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

      self._olcs_lab_info_client.get_lab_info.return_value = response

  def setUp(self):
    super(DeviceApiTest, self).setUp(DeviceApiTest.DeviceApiForTest)

  def testListDevices(self):
    res = self.app.get('/_ah/api/mtt/v1/devices')
    res_msg = protojson.decode_message(
        api_messages.DeviceInfoCollection, res.body
    )
    self.assertLen(res_msg.device_infos, 1)
    self.assertEqual(
        res_msg.device_infos[0],
        api_messages.DeviceInfo(
            device_serial='device_uuid1',
            lab_name='bej',
            hostname='localhost',
            run_target='panther',
            build_id='aosp_arm64-userdebug',
            product='panther',
            product_variant='panther',
            sdk_version='34',
            state='AVAILABLE',
            timestamp=datetime.datetime.fromtimestamp(60),
            battery_level='90',
            hidden=False,
            notes=[],
            history=[],
            utilization=0.0,
            cluster='',
            host_group='',
            pools=['presubmit'],
            device_type=api_messages.DeviceTypeMessage.PHYSICAL,
            mac_address='00:90:4c:d2:b1:9e',
            group_name='',
            sim_state='READY',
            sim_operator='T-mobile',
            extra_info=[
                api_messages.KeyValuePair(key='battery_level', value='90')
            ],
            flated_extra_info=[],
            test_harness='OMNILAB',
            recovery_state='',
            last_recovery_time=datetime.datetime.fromtimestamp(0),
            is_stub_device=False,
            display_serial='device1',
            preconfigured_ip='127.0.0.1',
            preconfigured_device_num_offset=0,
        ),
    )


if __name__ == '__main__':
  absltest.main()
