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
import logging
import re
from typing import Optional

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
    logging.info('device_type: %s', device_info.device_feature)
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
    product_variant = ''
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
      elif dimension.name == 'sim_card_info':
        sim_card_info = dimension.value
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
        sim_state='READY' if sim_card_info else 'ABSENT',
        sim_operator=sim_card_info,
        extra_info=[
            api_messages.KeyValuePair(key='battery_level', value=battery_level),
            api_messages.KeyValuePair(key='sdk_version', value=sdk_version),
            api_messages.KeyValuePair(key='build_id', value=build_id),
            api_messages.KeyValuePair(key='product', value=product),
            api_messages.KeyValuePair(
                key='product_variant', value=product_variant
            ),
            api_messages.KeyValuePair(key='product_name', value=product_name),
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
