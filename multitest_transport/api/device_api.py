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

"""A module to provide device APIs."""
import datetime
from typing import Optional

import endpoints
from multitest_transport.api import base
from multitest_transport.util import olcs_lab_info_client
from protorpc import message_types
from protorpc import messages
from protorpc import remote
from tradefed_cluster import api_messages

from com_google_deviceinfra.src.devtools.mobileharness.api.model.proto import device_pb2
from com_google_deviceinfra.src.devtools.mobileharness.infra.master.rpc.proto import lab_info_service_pb2


@base.MTT_API.api_class(resource_name='device', path='devices')
class DeviceApi(remote.Service):
  """A class for device API service."""

  DEVICE_LIST_RESOURCE = endpoints.ResourceContainer(
      message_types.VoidMessage,
      lab_name=messages.StringField(1),
      hostname=messages.StringField(2),
      cluster_id=messages.StringField(3),
      device_types=messages.EnumField(
          api_messages.DeviceTypeMessage, 4, repeated=True
      ),
      include_hidden=messages.BooleanField(5, default=False),
      include_offline_devices=messages.BooleanField(6, default=True),
      cursor=messages.StringField(7),
      count=messages.IntegerField(
          8, variant=messages.Variant.INT32, default=100
      ),
      product=messages.StringField(9),
      test_harnesses=messages.StringField(10, repeated=True),
      run_targets=messages.StringField(11, repeated=True),
      hostnames=messages.StringField(12, repeated=True),
      pools=messages.StringField(13, repeated=True),
      device_states=messages.StringField(14, repeated=True),
      host_groups=messages.StringField(15, repeated=True),
      device_serial=messages.StringField(16, repeated=True),
      flated_extra_info=messages.StringField(17),
      test_harness=messages.StringField(18, repeated=True),
      elastic_query=messages.StringField(19),
  )

  def __init__(
      self,
      olcs_client: Optional[olcs_lab_info_client.OlcsLabInfoClient] = None,
  ):
    if olcs_client:
      self._olcs_lab_info_client = olcs_client
    else:
      self._olcs_lab_info_client = (
          olcs_lab_info_client.OlcsLabInfoClient.create()
      )

  @base.ApiMethod(
      DEVICE_LIST_RESOURCE,
      api_messages.DeviceInfoCollection,
      path='/devices',
      http_method='GET',
      name='list',
  )
  def ListDevices(self, request):
    """Fetches a list of devices.

    Args:
      request: an API request.

    Returns:
      a DeviceInfoCollection object.
    """
    offset = (
        int(request.cursor)
        if request.cursor and request.cursor.isdigit()
        else 0
    )
    page_size = request.count
    get_lab_info_request = lab_info_service_pb2.GetLabInfoRequest()

    get_lab_info_request.page.offset = offset
    get_lab_info_request.page.limit = page_size
    get_lab_info_request.lab_query.device_view_request.device_limit = 0

    response = self._olcs_lab_info_client.get_lab_info(get_lab_info_request)
    returned_device_count = len(
        response.lab_query_result.device_view.grouped_devices.device_list.device_info
    )
    total_device_count = (
        response.lab_query_result.device_view.grouped_devices.device_list.device_total_count
    )
    device_infos = []
    for (
        device_info
    ) in (
        response.lab_query_result.device_view.grouped_devices.device_list.device_info
    ):
      device_infos.append(
          DeviceApi.ConvertDeviceInfo(
              device_info, response.lab_query_result.timestamp
          )
      )

    return api_messages.DeviceInfoCollection(
        device_infos=device_infos,
        next_cursor=str(offset + returned_device_count)
        if offset + returned_device_count < total_device_count
        else '',
        prev_cursor=str(offset) if offset > 0 else '',
        more=True
        if offset + returned_device_count < total_device_count
        else False,
    )

  @staticmethod
  def ConvertDeviceInfo(device_info, timestamp):
    """Converts an OmniLab device info to an ATS device info.

    Args:
      device_info: the OmniLab device info
      timestamp: the timestamp when this device info is returned

    Returns:
      an ATS device info
    """
    device_type = api_messages.DeviceTypeMessage.PHYSICAL
    if 'AndroidRealDevice' in device_info.device_feature.type:
      device_type = api_messages.DeviceTypeMessage.PHYSICAL
    elif 'NoOpDevice' in device_info.device_feature.type:
      device_type = api_messages.DeviceTypeMessage.NULL
    state = 'UNKNOWN'
    if device_info.device_status == device_pb2.DeviceStatus.IDLE:
      state = 'AVAILABLE'
    elif device_info.device_status == device_pb2.DeviceStatus.INIT:
      state = 'INIT'
    elif device_info.device_status == device_pb2.DeviceStatus.BUSY:
      state = 'ALLOCATED'
    elif device_info.device_status == device_pb2.DeviceStatus.DYING:
      state = 'DYING'
    elif device_info.device_status == device_pb2.DeviceStatus.DIRTY:
      state = 'DIRTY'
    elif device_info.device_status == device_pb2.DeviceStatus.PREPPING:
      state = 'PREPPING'
    elif device_info.device_status == device_pb2.DeviceStatus.LAMEDUCK:
      state = 'DIRTY'
    elif device_info.device_status == device_pb2.DeviceStatus.MISSING:
      state = 'MISSING'

    build_id = ''
    product = ''
    sdk_version = ''
    pools = []
    mac_address = ''
    dimensions = (
        device_info.device_feature.composite_dimension.supported_dimension
    )
    lab_name = ''
    battery_level = '100'
    sim_card_info = ''
    for dimension in dimensions:
      if dimension.name == 'build':
        build_id = dimension.value
      elif dimension.name == 'product_board':
        product = dimension.value
      elif dimension.name == 'sdk_version':
        sdk_version = dimension.value
      elif dimension.name == 'cluster':
        pools.append(dimension.value)
      elif dimension.name == 'mac_address':
        mac_address = dimension.value
      elif dimension.name == 'lab_location':
        lab_name = dimension.value
      elif dimension.name == 'battery_level':
        battery_level = dimension.value
      elif dimension.name == 'sim_card_info':
        sim_card_info = dimension.value

    return api_messages.DeviceInfo(
        device_serial=device_info.device_uuid,
        lab_name=lab_name,
        hostname=device_info.device_locator.lab_locator.host_name,
        run_target=product,
        build_id=build_id,
        product=product,
        product_variant=product,
        sdk_version=sdk_version,
        state=state,
        timestamp=datetime.datetime.fromtimestamp(timestamp.seconds),
        battery_level=battery_level,
        hidden=False,
        notes=[],
        history=[],
        utilization=0.0,
        cluster='',
        host_group='',
        pools=pools,
        device_type=device_type,
        mac_address=mac_address,
        group_name='',
        sim_state='READY' if sim_card_info else 'ABSENT',
        sim_operator=sim_card_info,
        extra_info=[
            api_messages.KeyValuePair(key='battery_level', value=battery_level)
        ],
        flated_extra_info=[],
        test_harness='OMNILAB',
        recovery_state='',
        last_recovery_time=datetime.datetime.fromtimestamp(0),
        is_stub_device=False,
        display_serial=device_info.device_locator.id,
        preconfigured_ip=device_info.device_locator.lab_locator.ip,
        preconfigured_device_num_offset=0,
    )
