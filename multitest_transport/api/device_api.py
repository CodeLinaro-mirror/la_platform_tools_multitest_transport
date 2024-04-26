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
from multitest_transport.util import olcs_lab_record_client
from protorpc import message_types
from protorpc import messages
from protorpc import remote
from tradefed_cluster import api_messages
from tradefed_cluster import common

from com_google_deviceinfra.src.devtools.mobileharness.api.model.proto import device_pb2
from com_google_deviceinfra.src.devtools.mobileharness.infra.master.rpc.proto import lab_record_service_pb2
from com_google_deviceinfra.src.devtools.mobileharness.shared.labinfo.proto import lab_info_service_pb2


@base.MTT_API.api_class(resource_name='device', path='devices')
class DeviceApi(remote.Service):
  """A class for device API service."""

  def __init__(
      self,
      lab_info_client: Optional[olcs_lab_info_client.OlcsLabInfoClient] = None,
      lab_record_client: Optional[
          olcs_lab_record_client.OlcsLabRecordClient
      ] = None,
  ):
    if lab_info_client:
      self._olcs_lab_info_client = lab_info_client
    else:
      self._olcs_lab_info_client = (
          olcs_lab_info_client.OlcsLabInfoClient.create()
      )
    if lab_record_client:
      self._olcs_lab_record_client = lab_record_client
    else:
      self._olcs_lab_record_client = (
          olcs_lab_record_client.OlcsLabRecordClient.create()
      )

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

    get_lab_info_request.page.offset = 0
    get_lab_info_request.page.limit = 1000
    get_lab_info_request.lab_query.device_view_request.device_limit = 0

    if request.hostname:
      lab_match_condition = (
          get_lab_info_request.lab_query.filter.lab_filter.lab_match_condition.add()
      )
      lab_match_condition.lab_host_name_match_condition.condition.include.expected.append(
          request.hostname
      )
    if request.hostnames:
      lab_match_condition = (
          get_lab_info_request.lab_query.filter.lab_filter.lab_match_condition.add()
      )
      for hostname in request.hostnames:
        lab_match_condition.lab_host_name_match_condition.condition.include.expected.append(
            hostname
        )
    if request.device_serial:
      device_match_condition = (
          get_lab_info_request.lab_query.filter.device_filter.device_match_condition.add()
      )
      for device_serial in request.device_serial:
        device_match_condition.device_uuid_match_condition.condition.include.expected.append(
            device_serial
        )

    response = self._olcs_lab_info_client.get_lab_info(get_lab_info_request)
    ats_device_infos = []
    for (
        device_info
    ) in (
        response.lab_query_result.device_view.grouped_devices.device_list.device_info
    ):
      ats_device_info = DeviceApi.ConvertDeviceInfo(
          device_info, response.lab_query_result.timestamp
      )
      if DeviceApi.DeviceInfoMatchFilter(ats_device_info, request):
        ats_device_infos.append(ats_device_info)

    total_device_count = len(ats_device_infos)
    returned_ats_device_infos = ats_device_infos[offset : offset + page_size]
    returned_device_count = len(returned_ats_device_infos)
    return api_messages.DeviceInfoCollection(
        device_infos=returned_ats_device_infos,
        next_cursor=str(offset + returned_device_count)
        if offset + returned_device_count < total_device_count
        else '',
        prev_cursor=str(offset) if offset > 0 else '',
        more=True
        if offset + returned_device_count < total_device_count
        else False,
    )

  @staticmethod
  def DeviceInfoMatchFilter(
      device_info: api_messages.DeviceInfo, request
  ) -> bool:
    return (
        (
            not request.host_groups
            or device_info.host_group in request.host_groups
        )
        and (
            not request.device_states
            or device_info.state in request.device_states
        )
        and (
            not request.device_types
            or device_info.device_type in request.device_types
        )
        and (
            not request.test_harnesses
            or device_info.test_harness in request.test_harnesses
        )
        and (
            not request.run_targets
            or device_info.run_target in request.run_targets
        )
        and (
            not request.pools
            or set(request.pools).intersection(device_info.pools) != set()
        )
    )

  DEVICE_GET_RESOURCE = endpoints.ResourceContainer(
      message_types.VoidMessage,
      device_serial=messages.StringField(1, required=True),
      include_notes=messages.BooleanField(2, default=False),
      include_history=messages.BooleanField(3, default=False),
      include_utilization=messages.BooleanField(4, default=False),
      hostname=messages.StringField(5),
  )

  @base.ApiMethod(
      DEVICE_GET_RESOURCE,
      api_messages.DeviceInfo,
      path='{device_serial}',
      http_method='GET',
      name='get',
  )
  def GetDevice(self, request):
    """Fetches the information and notes of a given device.

    Args:
      request: an API request.

    Returns:
      a DeviceInfo object.
    Raises:
      endpoints.NotFoundException: If the given device does not exist.
    """
    device_serial = request.device_serial
    get_lab_info_request = lab_info_service_pb2.GetLabInfoRequest()

    get_lab_info_request.page.offset = 0
    get_lab_info_request.page.limit = 50
    get_lab_info_request.lab_query.device_view_request.device_limit = 0

    device_match_condition = (
        get_lab_info_request.lab_query.filter.device_filter.device_match_condition.add()
    )
    device_match_condition.device_uuid_match_condition.condition.include.expected.append(
        device_serial
    )

    response = self._olcs_lab_info_client.get_lab_info(get_lab_info_request)

    device_info_list = (
        response.lab_query_result.device_view.grouped_devices.device_list.device_info
    )
    if device_info_list:
      return DeviceApi.ConvertDeviceInfo(
          device_info_list[0], response.lab_query_result.timestamp
      )
    raise endpoints.NotFoundException(
        "Device {0} doesn't exist.".format(device_serial)
    )

  HISTORIES_LIST_RESOURCE = endpoints.ResourceContainer(
      device_serial=messages.StringField(1, required=True),
      count=messages.IntegerField(2, default=100),
      cursor=messages.StringField(3),
      backwards=messages.BooleanField(4, default=False),
  )

  @base.ApiMethod(
      HISTORIES_LIST_RESOURCE,
      api_messages.DeviceInfoHistoryCollection,
      path='{device_serial}/histories',
      http_method='GET',
      name='listHistories',
  )
  def ListHistories(self, request):
    """List histories of a device.

    Args:
      request: an API request.

    Returns:
      an api_messages.DeviceInfoHistoryCollection object.
    """
    get_device_record_request = lab_record_service_pb2.GetDeviceRecordRequest()
    get_device_record_request.device_record_query.filter.device_uuid = (
        request.device_serial
    )

    get_device_record_response = self._olcs_lab_record_client.get_device_record(
        get_device_record_request
    )
    device_record_list = (
        get_device_record_response.device_record_query_result.device_record
    )
    histories = []
    for device_record in device_record_list:
      histories.append(
          DeviceApi.ConvertDeviceInfo(
              device_record.device_info, device_record.timestamp
          )
      )

    return api_messages.DeviceInfoHistoryCollection(
        histories=histories, next_cursor='', prev_cursor=''
    )

  @staticmethod
  def ConvertDeviceInfo(device_info, timestamp) -> api_messages.DeviceInfo:
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
    state = common.DeviceState.UNKNOWN
    if device_info.device_status == device_pb2.DeviceStatus.IDLE:
      state = common.DeviceState.AVAILABLE
    elif device_info.device_status == device_pb2.DeviceStatus.INIT:
      state = common.DeviceState.INIT
    elif device_info.device_status == device_pb2.DeviceStatus.BUSY:
      state = common.DeviceState.ALLOCATED
    elif device_info.device_status == device_pb2.DeviceStatus.DYING:
      state = common.DeviceState.DYING
    elif device_info.device_status == device_pb2.DeviceStatus.DIRTY:
      state = common.DeviceState.DIRTY
    elif device_info.device_status == device_pb2.DeviceStatus.PREPPING:
      state = common.DeviceState.PREPPING
    elif device_info.device_status == device_pb2.DeviceStatus.LAMEDUCK:
      state = common.DeviceState.LAMEDUCK
    elif device_info.device_status == device_pb2.DeviceStatus.MISSING:
      state = common.DeviceState.GONE

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
    control_id = device_info.device_locator.id
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
      elif dimension.name == 'control_id':
        control_id = dimension.value

    return api_messages.DeviceInfo(
        device_serial=device_info.device_locator.id,
        lab_name=lab_name,
        hostname=device_info.device_locator.lab_locator.host_name,
        run_target=product,
        build_id=build_id,
        product=product,
        product_variant=product,
        sdk_version=sdk_version,
        state=state,
        timestamp=datetime.datetime.utcfromtimestamp(timestamp.seconds),
        battery_level=battery_level,
        hidden=False,
        notes=[],
        history=[],
        utilization=0.0,
        cluster=pools[0] if pools else 'default',
        host_group=pools[0] if pools else 'default',
        pools=pools if pools else ['default'],
        device_type=device_type,
        mac_address=mac_address,
        group_name='',
        sim_state='READY' if sim_card_info else 'ABSENT',
        sim_operator=sim_card_info,
        extra_info=[
            api_messages.KeyValuePair(key='battery_level', value=battery_level),
            api_messages.KeyValuePair(key='sdk_version', value=sdk_version),
            api_messages.KeyValuePair(key='build_id', value=build_id),
            api_messages.KeyValuePair(key='product', value=product),
            api_messages.KeyValuePair(key='product_variant', value=product),
        ],
        flated_extra_info=[],
        test_harness='OMNILAB',
        recovery_state='',
        last_recovery_time=datetime.datetime.utcfromtimestamp(0),
        is_stub_device=False,
        display_serial=control_id,
        preconfigured_ip=device_info.device_locator.lab_locator.ip,
        preconfigured_device_num_offset=0,
    )
