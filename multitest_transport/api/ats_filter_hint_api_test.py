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
from multitest_transport.api import api_test_util
from multitest_transport.api import ats_filter_hint_api
from multitest_transport.util import olcs_lab_info_client
from protorpc import protojson
from tradefed_cluster import api_messages

from com_google_deviceinfra.src.devtools.mobileharness.api.model.proto import device_pb2
from com_google_deviceinfra.src.devtools.mobileharness.api.model.proto import lab_pb2
from com_google_deviceinfra.src.devtools.mobileharness.shared.labinfo.proto import lab_info_service_pb2


class AtsFilterHintApiTest(api_test_util.TestCase):

  class AtsFilterHintApiForTest(ats_filter_hint_api.AtsFilterHintApi):

    def __init__(self):
      self._olcs_lab_info_client = mock.create_autospec(
          olcs_lab_info_client.OlcsLabInfoClient, spec_set=True
      )
      self._olcs_lab_info_client.get_lab_info = mock.MagicMock()
      lab_view_response = lab_info_service_pb2.GetLabInfoResponse()
      lab_view_response.lab_query_result.timestamp.seconds = 60
      lab_data = lab_view_response.lab_query_result.lab_view.lab_data.add()
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
      device_info_1 = lab_data.device_list.device_info.add()
      self._init_device_info(device_info_1)

      device_view_response = lab_info_service_pb2.GetLabInfoResponse()
      device_view_response.lab_query_result.timestamp.seconds = 60
      device_info_2 = (
          device_view_response.lab_query_result.device_view.grouped_devices.device_list.device_info.add()
      )
      self._init_device_info(device_info_2)

      self._olcs_lab_info_client.get_lab_info.side_effect = (
          lambda request: device_view_response
          if request.lab_query.HasField('device_view_request')
          else lab_view_response
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

  def setUp(self):
    super(AtsFilterHintApiTest, self).setUp(
        AtsFilterHintApiTest.AtsFilterHintApiForTest
    )

  def testListPoolFilterHints(self):
    res = self.app.get('/_ah/api/mtt/v1/filterHints?type=POOL')
    res_msg = protojson.decode_message(
        api_messages.FilterHintCollection, res.body
    )
    self.assertEqual(
        [api_messages.FilterHintMessage(value='presubmit')],
        res_msg.filter_hints
    )

  def testListLabFilterHints(self):
    res = self.app.get('/_ah/api/mtt/v1/filterHints?type=LAB')
    res_msg = protojson.decode_message(
        api_messages.FilterHintCollection, res.body
    )
    self.assertEqual(
        [api_messages.FilterHintMessage(value='bej')],
        res_msg.filter_hints
    )

  def testListHostFilterHints(self):
    res = self.app.get('/_ah/api/mtt/v1/filterHints?type=HOST')
    res_msg = protojson.decode_message(
        api_messages.FilterHintCollection, res.body
    )
    self.assertEqual(
        [api_messages.FilterHintMessage(value='localhost')],
        res_msg.filter_hints
    )

  def testListTestHarnessFilterHints(self):
    res = self.app.get('/_ah/api/mtt/v1/filterHints?type=TEST_HARNESS')
    res_msg = protojson.decode_message(
        api_messages.FilterHintCollection, res.body
    )
    self.assertEqual(
        [api_messages.FilterHintMessage(value='OMNILAB')],
        res_msg.filter_hints
    )

  def testListTestHarnessVersionFilterHints(self):
    res = self.app.get('/_ah/api/mtt/v1/filterHints?type=TEST_HARNESS_VERSION')
    res_msg = protojson.decode_message(
        api_messages.FilterHintCollection, res.body
    )
    self.assertEqual(
        [api_messages.FilterHintMessage(value='4.100.0')],
        res_msg.filter_hints
    )

  def testListHostStateFilterHints(self):
    res = self.app.get('/_ah/api/mtt/v1/filterHints?type=HOST_STATE')
    res_msg = protojson.decode_message(
        api_messages.FilterHintCollection, res.body
    )
    self.assertEqual(
        [api_messages.FilterHintMessage(value='RUNNING')],
        res_msg.filter_hints
    )

  def testListDeviceStateFilterHints(self):
    res = self.app.get('/_ah/api/mtt/v1/filterHints?type=DEVICE_STATE')
    res_msg = protojson.decode_message(
        api_messages.FilterHintCollection, res.body
    )
    self.assertEqual(
        [api_messages.FilterHintMessage(value='Available')],
        res_msg.filter_hints
    )

  def testListHostGroupFilterHints(self):
    res = self.app.get('/_ah/api/mtt/v1/filterHints?type=HOST_GROUP')
    res_msg = protojson.decode_message(
        api_messages.FilterHintCollection, res.body
    )
    self.assertEqual(
        [api_messages.FilterHintMessage(value='presubmit')],
        res_msg.filter_hints
    )

  def testListUpdateStateFilterHints(self):
    res = self.app.get('/_ah/api/mtt/v1/filterHints?type=UPDATE_STATE')
    res_msg = protojson.decode_message(
        api_messages.FilterHintCollection, res.body
    )
    self.assertEqual(
        [api_messages.FilterHintMessage(value='SUCCEEDED')],
        res_msg.filter_hints
    )

  def testListProductFilterHints(self):
    res = self.app.get('/_ah/api/mtt/v1/filterHints?type=PRODUCT')
    res_msg = protojson.decode_message(
        api_messages.FilterHintCollection, res.body
    )
    self.assertEqual(
        [api_messages.FilterHintMessage(value='panther')],
        res_msg.filter_hints
    )

  def testListProductVariantFilterHints(self):
    res = self.app.get('/_ah/api/mtt/v1/filterHints?type=PRODUCT_VARIANT')
    res_msg = protojson.decode_message(
        api_messages.FilterHintCollection, res.body
    )
    self.assertEqual(
        [api_messages.FilterHintMessage(value='panther')],
        res_msg.filter_hints
    )


if __name__ == '__main__':
  absltest.main()
