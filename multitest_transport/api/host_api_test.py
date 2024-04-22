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
from multitest_transport.api import api_test_util
from multitest_transport.api import host_api
from multitest_transport.util import olcs_lab_info_client
from multitest_transport.util import olcs_lab_record_client
from protorpc import protojson
from tradefed_cluster import api_messages

from com_google_deviceinfra.src.devtools.mobileharness.api.model.proto import device_pb2
from com_google_deviceinfra.src.devtools.mobileharness.api.model.proto import lab_pb2
from com_google_deviceinfra.src.devtools.mobileharness.infra.master.rpc.proto import lab_record_service_pb2
from com_google_deviceinfra.src.devtools.mobileharness.shared.labinfo.proto import lab_info_service_pb2


EXPECTED_HOST_INFO = api_messages.HostInfo(
    hostname='localhost',
    lab_name='bej',
    cluster='presubmit',
    host_group='presubmit',
    test_runner='OMNILAB',
    test_runner_version='4.100.0',
    device_infos=[
        api_messages.DeviceInfo(
            device_serial='device_uuid1',
            lab_name='',
            hostname='localhost',
            run_target='panther',
            build_id='',
            product='panther',
            product_variant='panther',
            sdk_version='',
            state='AVAILABLE',
            timestamp=datetime.datetime.utcfromtimestamp(60),
            battery_level='100',
            hidden=False,
            notes=[],
            history=[],
            utilization=0.0,
            cluster='default',
            host_group='default',
            pools=['default'],
            device_type=api_messages.DeviceTypeMessage.PHYSICAL,
            mac_address='',
            group_name='',
            sim_state='ABSENT',
            sim_operator='',
            extra_info=[
                api_messages.KeyValuePair(key='battery_level', value='100'),
                api_messages.KeyValuePair(key='sdk_version', value=''),
                api_messages.KeyValuePair(key='build_id', value=''),
                api_messages.KeyValuePair(key='product', value='panther'),
                api_messages.KeyValuePair(
                    key='product_variant', value='panther'
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
    timestamp=datetime.datetime.utcfromtimestamp(60),
    total_devices=1,
    offline_devices=0,
    available_devices=1,
    allocated_devices=0,
    device_count_timestamp=datetime.datetime.utcfromtimestamp(60),
    hidden=False,
    notes=[],
    extra_info=[],
    next_cluster_ids=[],
    pools=['presubmit'],
    host_state='RUNNING',
    state_history=[],
    assignee='',
    device_count_summaries=[
        api_messages.DeviceCountSummary(
            run_target='panther',
            total=1,
            allocated=0,
            available=1,
            offline=0,
            timestamp=datetime.datetime.utcfromtimestamp(60),
        )
    ],
    is_bad=False,
    test_harness='OMNILAB',
    test_harness_version='4.100.0',
    flated_extra_info=[],
    last_recovery_time=datetime.datetime.utcfromtimestamp(0),
    recovery_state='',
    update_state='SUCCEEDED',
    update_state_display_message='',
    bad_reason='',
    update_timestamp=datetime.datetime.utcfromtimestamp(60),
)


class HostApiTest(api_test_util.TestCase):

  class HostApiForTest(host_api.HostApi):

    def __init__(self):
      self._olcs_lab_info_client = mock.create_autospec(
          olcs_lab_info_client.OlcsLabInfoClient, spec_set=True
      )
      self._olcs_lab_info_client.get_lab_info = mock.MagicMock()
      get_lab_info_response = lab_info_service_pb2.GetLabInfoResponse()
      get_lab_info_response.lab_query_result.timestamp.seconds = 60
      lab_data = get_lab_info_response.lab_query_result.lab_view.lab_data.add()
      lab_data.lab_info.lab_locator.ip = '127.0.0.1'
      lab_data.lab_info.lab_locator.host_name = 'localhost'
      lab_data.lab_info.lab_status = lab_pb2.LabStatus.LAB_RUNNING
      host_property = (
          lab_data.lab_info.lab_server_feature.host_properties.host_property.add()
      )
      host_property.key = 'lab_location'
      host_property.value = 'bej'
      host_property = (
          lab_data.lab_info.lab_server_feature.host_properties.host_property.add()
      )
      host_property.key = 'host_version'
      host_property.value = '4.100.0'
      host_property = (
          lab_data.lab_info.lab_server_feature.host_properties.host_property.add()
      )
      host_property.key = 'host_group'
      host_property.value = 'presubmit'
      device_info = lab_data.device_list.device_info.add()
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
      dimension.name = 'control_id'
      dimension.value = 'device1'

      self._olcs_lab_info_client.get_lab_info.return_value = (
          get_lab_info_response
      )

      self._olcs_lab_record_client = mock.create_autospec(
          olcs_lab_record_client.OlcsLabRecordClient, spec_set=True
      )
      self._olcs_lab_record_client.get_lab_record = mock.MagicMock()
      get_lab_record_response = lab_record_service_pb2.GetLabRecordResponse()
      lab_record = (
          get_lab_record_response.lab_record_query_result.lab_record.add()
      )
      lab_record.timestamp.seconds = 60
      lab_record.lab_info.CopyFrom(lab_data.lab_info)
      self._olcs_lab_record_client.get_lab_record.return_value = (
          get_lab_record_response
      )

  def setUp(self):
    super(HostApiTest, self).setUp(HostApiTest.HostApiForTest)

  def testListHosts(self):
    res = self.app.get('/_ah/api/mtt/v1/hosts')
    res_msg = protojson.decode_message(
        api_messages.HostInfoCollection, res.body
    )
    self.assertLen(res_msg.host_infos, 1)
    self.assertEqual(res_msg.host_infos[0], EXPECTED_HOST_INFO)

  def testGetHost(self):
    res = self.app.get('/_ah/api/mtt/v1/hosts/%s' % 'localhost')
    res_msg = protojson.decode_message(api_messages.HostInfo, res.body)
    self.assertEqual(res_msg, EXPECTED_HOST_INFO)

  def testListHostHistory(self):
    res = self.app.get('/_ah/api/mtt/v1/hosts/%s/histories' % 'localhost')
    res_msg = protojson.decode_message(
        api_messages.HostInfoHistoryCollection, res.body
    )
    self.assertEqual(
        res_msg.histories[0],
        api_messages.HostInfo(
            hostname='localhost',
            lab_name='bej',
            cluster='presubmit',
            host_group='presubmit',
            test_runner='OMNILAB',
            test_runner_version='4.100.0',
            device_infos=[],
            timestamp=datetime.datetime.utcfromtimestamp(60),
            total_devices=0,
            offline_devices=0,
            available_devices=0,
            allocated_devices=0,
            device_count_timestamp=datetime.datetime.utcfromtimestamp(60),
            hidden=False,
            notes=[],
            extra_info=[],
            next_cluster_ids=[],
            pools=['presubmit'],
            host_state='RUNNING',
            state_history=[],
            assignee='',
            device_count_summaries=[],
            is_bad=False,
            test_harness='OMNILAB',
            test_harness_version='4.100.0',
            flated_extra_info=[],
            last_recovery_time=datetime.datetime.utcfromtimestamp(0),
            recovery_state='',
            update_state='SUCCEEDED',
            update_state_display_message='',
            bad_reason='',
            update_timestamp=datetime.datetime.utcfromtimestamp(60),
        ),
    )


if __name__ == '__main__':
  absltest.main()
