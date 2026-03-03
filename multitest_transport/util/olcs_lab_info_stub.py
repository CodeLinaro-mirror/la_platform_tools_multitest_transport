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

"""A OLCS lab info service stub that fetches device and lab info from OLCS."""

import datetime
import functools
import re
from typing import List, Optional

import endpoints
from multitest_transport.util import olcs_lab_info_client
from protorpc import messages
from tradefed_cluster import api_messages
from tradefed_cluster import common

from com_google_deviceinfra.src.devtools.mobileharness.api.model.proto import device_pb2
from com_google_deviceinfra.src.devtools.mobileharness.shared.labinfo.proto import lab_info_service_pb2

# Local virtual device id pattern: <hostname>:<port> or <ip>:<port>.
LOCAL_VIRTUAL_DEVICE_ID_PATTERN = r'^([\w\.]+):local-virtual-device-(\d+)$'

# Remote virtual device id pattern:
# gce-device-<server_ip>-<instance_index>-<username>.
REMOTE_VIRTUAL_DEVICE_ID_PATTERN = r'gce-device-([\d.]+)-(\d+)-([^-]+)'
CVD_BASE_PORT = 6520


class ListDevicesOptions:
  """Options for OlcsLabInfoStub.ListDevices."""

  def __init__(
      self,
      cursor: Optional[str] = None,
      count: int = 100,
      hostname: Optional[str] = None,
      hostnames: Optional[List[str]] = None,
      device_serial: Optional[List[str]] = None,
      host_groups: Optional[List[str]] = None,
      device_states: Optional[List[str]] = None,
      device_types: Optional[List['api_messages.DeviceTypeMessage']] = None,
      test_harnesses: Optional[List[str]] = None,
      run_targets: Optional[List[str]] = None,
      pools: Optional[List[str]] = None,
  ):
    self.cursor = cursor
    self.count = count
    self.hostname = hostname
    self.hostnames = hostnames
    self.device_serial = device_serial
    self.host_groups = host_groups
    self.device_states = device_states
    self.device_types = device_types
    self.test_harnesses = test_harnesses
    self.run_targets = run_targets
    self.pools = pools

  def __eq__(self, other):
    if not isinstance(other, ListDevicesOptions):
      return NotImplemented
    return self.__dict__ == other.__dict__


@functools.lru_cache(maxsize=None)
def GetSharedStub():
  """Returns a shared OlcsLabInfoStub instance."""
  return OlcsLabInfoStub(None)


class OlcsLabInfoStub:
  """The stub for OCLS lab info service."""

  def __init__(self, client: None):
    if client is None:
      self._client = olcs_lab_info_client.OlcsLabInfoClient.create()
    else:
      self._client = client

  def GetDevice(self, device_serial: str) -> Optional[api_messages.DeviceInfo]:
    """Fetches the information and notes of a given device.

    Args:
      device_serial: the serial number of the device.

    Returns:
      a DeviceInfo object.
    Raises:
      endpoints.NotFoundException: If the given device does not exist.
    """
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

    response = self._client.get_lab_info(get_lab_info_request)

    device_info_list = (
        response.lab_query_result.device_view.grouped_devices.device_list.device_info
    )
    if device_info_list:
      return OlcsLabInfoStub.ConvertDeviceInfo(
          device_info_list[0], response.lab_query_result.timestamp
      )
    return None

  def ListDevices(
      self, options: ListDevicesOptions
  ) -> api_messages.DeviceInfoCollection:
    """Fetches a list of devices.

    Args:
      options: a ListDevicesOptions object.

    Returns:
      a DeviceInfoCollection object.
    """
    offset = (
        int(options.cursor)
        if options.cursor and options.cursor.isdigit()
        else 0
    )
    page_size = options.count

    ats_device_infos = []
    backend_offset = 0
    backend_page_size = 1000
    timestamp = None

    while True:
      get_lab_info_request = lab_info_service_pb2.GetLabInfoRequest()
      get_lab_info_request.page.offset = backend_offset
      get_lab_info_request.page.limit = backend_page_size
      get_lab_info_request.lab_query.device_view_request.device_limit = 0

      if options.hostname:
        lab_match_condition = (
            get_lab_info_request.lab_query.filter.lab_filter.lab_match_condition.add()
        )
        lab_match_condition.lab_host_name_match_condition.condition.include.expected.append(
            options.hostname
        )
      if options.hostnames:
        lab_match_condition = (
            get_lab_info_request.lab_query.filter.lab_filter.lab_match_condition.add()
        )
        for hostname in options.hostnames:
          lab_match_condition.lab_host_name_match_condition.condition.include.expected.append(
              hostname
          )
      if options.device_serial:
        device_match_condition = (
            get_lab_info_request.lab_query.filter.device_filter.device_match_condition.add()
        )
        for device_serial in options.device_serial:
          device_match_condition.device_uuid_match_condition.condition.include.expected.append(
              device_serial
          )
      response = self._client.get_lab_info(get_lab_info_request)
      if not timestamp:
        timestamp = response.lab_query_result.timestamp
      device_list = (
          response.lab_query_result.device_view.grouped_devices.device_list.device_info
      )
      for device_info in device_list:
        ats_device_info = OlcsLabInfoStub.ConvertDeviceInfo(
            device_info, timestamp
        )
        if OlcsLabInfoStub.DeviceInfoMatchFilter(ats_device_info, options):
          ats_device_infos.append(ats_device_info)
      if len(device_list) < backend_page_size:
        break
      backend_offset += backend_page_size

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
      device_info: api_messages.DeviceInfo, options: ListDevicesOptions
  ) -> bool:
    return (
        (
            not options.host_groups
            or device_info.host_group in options.host_groups
        )
        and (
            not options.device_states
            or device_info.state in options.device_states
        )
        and (
            not options.device_types
            or device_info.device_type in options.device_types
        )
        and (
            not options.test_harnesses
            or device_info.test_harness in options.test_harnesses
        )
        and (
            not options.run_targets
            or device_info.run_target in options.run_targets
        )
        and (
            not options.pools
            or set(options.pools).intersection(device_info.pools) != set()
        )
    )

  HISTORIES_LIST_RESOURCE = endpoints.ResourceContainer(
      device_serial=messages.StringField(1, required=True),
      count=messages.IntegerField(2, default=100),
      cursor=messages.StringField(3),
      backwards=messages.BooleanField(4, default=False),
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
    preconfigured_device_num_offset = 0
    preconfigured_ip = device_info.device_locator.lab_locator.ip
    device_type = api_messages.DeviceTypeMessage.PHYSICAL
    if 'AndroidRealDevice' in device_info.device_feature.type:
      device_type = api_messages.DeviceTypeMessage.PHYSICAL
    elif 'NoOpDevice' in device_info.device_feature.type:
      device_type = api_messages.DeviceTypeMessage.NULL
    elif 'AndroidJitEmulator' in device_info.device_feature.type:
      local_match = re.match(
          LOCAL_VIRTUAL_DEVICE_ID_PATTERN, device_info.device_locator.id
      )
      remote_match = re.match(
          REMOTE_VIRTUAL_DEVICE_ID_PATTERN, device_info.device_locator.id
      )
      if local_match:
        device_type = api_messages.DeviceTypeMessage.LOCAL_VIRTUAL
        preconfigured_device_num_offset = int(local_match.group(2))
      elif remote_match:
        preconfigured_ip = remote_match.group(1)
        device_type = api_messages.DeviceTypeMessage.REMOTE_VIRTUAL
        preconfigured_device_num_offset = int(remote_match.group(2))
    state = common.DeviceState.UNKNOWN
    if device_info.device_status == device_pb2.DeviceStatus.IDLE:
      if 'FailedDevice' in device_info.device_feature.type:
        state = common.DeviceState.FAILED
      else:
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
    product_variant = ''
    sdk_version = ''
    pools = []
    mac_address = ''
    dimensions = (
        device_info.device_feature.composite_dimension.supported_dimension
    )
    lab_name = ''
    battery_level = '100'
    sim_operator_alpha = ''
    sim_state = 'ABSENT'
    control_id = device_info.device_locator.id
    product_name = ''
    for dimension in dimensions:
      if dimension.name == 'build':
        build_id = dimension.value
      elif dimension.name == 'product_board':
        product = dimension.value
      elif dimension.name == 'device':
        product_variant = dimension.value
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
      elif dimension.name == 'sim_operator_alpha':
        sim_operator_alpha = dimension.value
      elif dimension.name == 'sim_state':
        sim_state = dimension.value.upper() if dimension.value else sim_state
      elif dimension.name == 'control_id':
        control_id = dimension.value
      elif dimension.name == 'type':
        product_name = dimension.value

    return api_messages.DeviceInfo(
        device_serial=device_info.device_locator.id,
        lab_name=lab_name,
        hostname=device_info.device_locator.lab_locator.host_name,
        run_target=product,
        build_id=build_id,
        product=product,
        product_variant=product_variant,
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
        sim_operator=sim_operator_alpha,
        sim_state=sim_state,
        extra_info=[
            api_messages.KeyValuePair(key='battery_level', value=battery_level),
            api_messages.KeyValuePair(key='sdk_version', value=sdk_version),
            api_messages.KeyValuePair(key='build_id', value=build_id),
            api_messages.KeyValuePair(key='product', value=product),
            api_messages.KeyValuePair(
                key='product_variant', value=product_variant
            ),
            api_messages.KeyValuePair(key='product_name', value=product_name),
            api_messages.KeyValuePair(
                key='sim_operator', value=sim_operator_alpha
            ),
            api_messages.KeyValuePair(key='sim_state', value=sim_state),
        ],
        flated_extra_info=[],
        test_harness='OMNILAB',
        recovery_state='',
        last_recovery_time=datetime.datetime.utcfromtimestamp(0),
        is_stub_device=False,
        display_serial=control_id,
        preconfigured_ip=preconfigured_ip,
        preconfigured_device_num_offset=preconfigured_device_num_offset,
    )
