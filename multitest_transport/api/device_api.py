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
from typing import Optional

import endpoints
from multitest_transport.api import base
from multitest_transport.util import olcs_lab_info_client
from multitest_transport.util import olcs_lab_info_stub
from multitest_transport.util import olcs_lab_record_client
from protorpc import message_types
from protorpc import messages
from protorpc import remote
from tradefed_cluster import api_messages

from com_google_deviceinfra.src.devtools.mobileharness.infra.master.rpc.proto import lab_record_service_pb2


@base.MTT_API.api_class(resource_name='device', path='devices')
class DeviceApi(remote.Service):
  """A class for device API service."""

  def __init__(
      self,
      lab_info_client: Optional[olcs_lab_info_client.OlcsLabInfoClient] = None,
      lab_record_client: Optional[
          olcs_lab_record_client.OlcsLabRecordClient
      ] = None,
      lab_info_stub: Optional[olcs_lab_info_stub.OlcsLabInfoStub] = None,
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
    if lab_info_stub:
      self._olcs_lab_info_stub = lab_info_stub
    else:
      self._olcs_lab_info_stub = olcs_lab_info_stub.OlcsLabInfoStub(None)

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
    all_test_harnesses = []
    if request.test_harnesses:
      all_test_harnesses.extend(request.test_harnesses)
    if request.test_harness:
      all_test_harnesses.extend(request.test_harness)
    # TODO: support all filter fields.
    options = olcs_lab_info_stub.ListDevicesOptions(
        hostname=request.hostname,
        hostnames=request.hostnames,
        device_serial=request.device_serial,
        cursor=request.cursor,
        count=request.count,
        host_groups=request.host_groups,
        device_states=request.device_states,
        device_types=request.device_types,
        test_harnesses=all_test_harnesses,
        run_targets=request.run_targets,
        pools=request.pools,
    )
    return self._olcs_lab_info_stub.ListDevices(options)

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
    device_info = self._olcs_lab_info_stub.GetDevice(device_serial)
    if device_info:
      return device_info
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
          olcs_lab_info_stub.OlcsLabInfoStub.ConvertDeviceInfo(
              device_record.device_info, device_record.timestamp
          )
      )

    return api_messages.DeviceInfoHistoryCollection(
        histories=histories, next_cursor='', prev_cursor=''
    )
