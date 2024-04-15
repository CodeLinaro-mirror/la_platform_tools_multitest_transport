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
"""A module to provide host APIs."""
import datetime
from typing import Optional

import endpoints
from multitest_transport.api import base
from multitest_transport.api import device_api
from multitest_transport.util import olcs_lab_info_client
from multitest_transport.util import olcs_lab_record_client
from protorpc import message_types
from protorpc import messages
from protorpc import remote
from tradefed_cluster import api_messages

from com_google_deviceinfra.src.devtools.mobileharness.api.model.proto import device_pb2
from com_google_deviceinfra.src.devtools.mobileharness.api.model.proto import lab_pb2
from com_google_deviceinfra.src.devtools.mobileharness.infra.master.rpc.proto import lab_record_service_pb2
from com_google_deviceinfra.src.devtools.mobileharness.shared.labinfo.proto import lab_info_service_pb2


class Operator(messages.Enum):
  """The types of operators."""

  UNKNOWN = 0
  EQUAL = 1
  LESS_THAN = 2
  LESS_THAN_OR_EQUAL = 3
  GREATER_THAN = 4
  GREATER_THAN_OR_EQUAL = 5


@base.MTT_API.api_class(resource_name='host', path='hosts')
class HostApi(remote.Service):
  """A class for host API service."""

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

  HOST_LIST_RESOURCE = endpoints.ResourceContainer(
      message_types.VoidMessage,
      lab_name=messages.StringField(1),
      include_hidden=messages.BooleanField(2, default=False),
      include_devices=messages.BooleanField(3, default=False),
      assignee=messages.StringField(4),
      is_bad=messages.BooleanField(5),
      hostnames=messages.StringField(6, repeated=True),
      host_groups=messages.StringField(7, repeated=True),
      test_harnesses=messages.StringField(8, repeated=True),
      test_harness_versions=messages.StringField(9, repeated=True),
      pools=messages.StringField(10, repeated=True),
      host_states=messages.EnumField(api_messages.HostState, 11, repeated=True),
      flated_extra_info=messages.StringField(12),
      cursor=messages.StringField(13),
      count=messages.IntegerField(
          14, variant=messages.Variant.INT32, default=100
      ),
      timestamp_operator=messages.EnumField(Operator, 15),
      timestamp=message_types.DateTimeField(16),
      recovery_states=messages.StringField(17, repeated=True),
      test_harness=messages.StringField(18, repeated=True),
      host_update_states=messages.EnumField(
          api_messages.HostUpdateState, 19, repeated=True
      ),
  )

  @base.ApiMethod(
      HOST_LIST_RESOURCE,
      api_messages.HostInfoCollection,
      path='/hosts',
      http_method='GET',
      name='list',
  )
  def ListHosts(self, request):
    """Fetches a list of hosts.

    Args:
      request: an API request.

    Returns:
      a HostInfoCollection object.
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

    response = self._olcs_lab_info_client.get_lab_info(get_lab_info_request)
    returned_host_count = len(response.lab_query_result.lab_view.lab_data)
    total_host_count = response.lab_query_result.lab_view.lab_total_count
    host_infos = []
    for host_info in response.lab_query_result.lab_view.lab_data:
      host_infos.append(
          HostApi.ConvertHostInfo(
              host_info, response.lab_query_result.timestamp
          )
      )
    return api_messages.HostInfoCollection(
        host_infos=host_infos,
        next_cursor=str(offset + returned_host_count)
        if offset + returned_host_count < total_host_count
        else '',
        prev_cursor=str(offset) if offset > 0 else '',
        more=True if offset + returned_host_count < total_host_count else False,
    )

  HOST_GET_RESOURCE = endpoints.ResourceContainer(
      message_types.VoidMessage,
      hostname=messages.StringField(1, required=True),
      include_notes=messages.BooleanField(2, default=False),
      include_hidden=messages.BooleanField(3, default=False),
      include_host_state_history=messages.BooleanField(4, default=False),
      host_state_history_limit=messages.IntegerField(5, default=10),
  )

  @base.ApiMethod(
      HOST_GET_RESOURCE,
      api_messages.HostInfo,
      path='{hostname}',
      http_method='GET',
      name='get',
  )
  def GetHost(self, request):
    """Fetches the information and notes of a given hostname.

    Args:
      request: an API request.

    Returns:
      a HostInfo object.
    Raises:
      endpoints.NotFoundException: If the given host does not exist.
    """
    host_name = request.hostname
    get_lab_info_request = lab_info_service_pb2.GetLabInfoRequest()

    get_lab_info_request.page.offset = 0
    get_lab_info_request.page.limit = 50
    response = self._olcs_lab_info_client.get_lab_info(get_lab_info_request)

    for host_info in response.lab_query_result.lab_view.lab_data:
      # TODO: Do the filter in OLC server.
      if host_info.lab_info.lab_locator.host_name == host_name:
        return HostApi.ConvertHostInfo(
            host_info, response.lab_query_result.timestamp
        )
    raise endpoints.NotFoundException(
        "Host {0} doesn't exist.".format(host_name)
    )

  HISTORIES_LIST_RESOURCE = endpoints.ResourceContainer(
      hostname=messages.StringField(1, required=True),
      count=messages.IntegerField(2, default=100),
      cursor=messages.StringField(3),
      backwards=messages.BooleanField(4, default=False),
  )

  @base.ApiMethod(
      HISTORIES_LIST_RESOURCE,
      api_messages.HostInfoHistoryCollection,
      path='{hostname}/histories',
      http_method='GET',
      name='listHistories',
  )
  def ListHistories(self, request):
    """List histories of a host.

    Args:
      request: an API request.

    Returns:
      an api_messages.HostInfoHistoryCollection object.
    """
    get_lab_record_request = lab_record_service_pb2.GetLabRecordRequest()
    get_lab_record_request.lab_record_query.filter.host_name = request.hostname

    get_lab_record_response = self._olcs_lab_record_client.get_lab_record(
        get_lab_record_request
    )
    lab_record_list = get_lab_record_response.lab_record_query_result.lab_record
    histories = []
    for lab_record in lab_record_list:
      histories.append(
          HostApi.ConvertLabInfo(lab_record.lab_info, lab_record.timestamp)
      )
    return api_messages.HostInfoHistoryCollection(
        histories=histories, next_cursor='', prev_cursor=''
    )

  @staticmethod
  def ConvertHostInfo(host_info, timestamp):
    """Converts an OmniLab host info to an ATS host info.

    Args:
      host_info: the OmniLab host info
      timestamp: the timestamp when this host info is returned

    Returns:
      an ATS host info
    """
    device_count_summaries = {}
    total_devices = 0
    available_devices = 0
    allocated_devices = 0
    offline_devices = 0
    device_infos = []
    for olcs_device_info in host_info.device_list.device_info:
      device_info = device_api.DeviceApi.ConvertDeviceInfo(
          olcs_device_info, timestamp
      )
      if device_info.run_target in device_count_summaries:
        device_count_summary = device_count_summaries[device_info.run_target]
      else:
        device_count_summary = api_messages.DeviceCountSummary(
            run_target=device_info.run_target,
            total=0,
            available=0,
            allocated=0,
            offline=0,
            timestamp=datetime.datetime.utcfromtimestamp(timestamp.seconds),
        )
        device_count_summaries[device_info.run_target] = device_count_summary
      total_devices += 1
      device_count_summary.total += 1
      if olcs_device_info.device_status in [device_pb2.DeviceStatus.IDLE]:
        available_devices += 1
        device_count_summary.available += 1
      elif olcs_device_info.device_status in [
          device_pb2.DeviceStatus.DIRTY,
          device_pb2.DeviceStatus.BUSY,
      ]:
        allocated_devices += 1
        device_count_summary.allocated += 1
      elif olcs_device_info.device_status in [
          device_pb2.DeviceStatus.DYING,
          device_pb2.DeviceStatus.INIT,
          device_pb2.DeviceStatus.LAMEDUCK,
          device_pb2.DeviceStatus.MISSING,
          device_pb2.DeviceStatus.PREPPING,
      ]:
        offline_devices += 1
        device_count_summary.offline += 1
      device_infos.append(device_info)
    ats_host_info = HostApi.ConvertLabInfo(host_info.lab_info, timestamp)

    return api_messages.HostInfo(
        hostname=ats_host_info.hostname,
        lab_name=ats_host_info.lab_name,
        cluster=ats_host_info.cluster,
        host_group=ats_host_info.host_group,
        test_runner=ats_host_info.test_runner,
        test_runner_version=ats_host_info.test_harness_version,
        device_infos=device_infos,
        timestamp=ats_host_info.timestamp,
        total_devices=total_devices,
        offline_devices=offline_devices,
        available_devices=available_devices,
        allocated_devices=allocated_devices,
        device_count_timestamp=ats_host_info.device_count_timestamp,
        hidden=ats_host_info.hidden,
        notes=ats_host_info.notes,
        extra_info=ats_host_info.extra_info,
        next_cluster_ids=ats_host_info.next_cluster_ids,
        pools=ats_host_info.pools,
        host_state=ats_host_info.host_state,
        state_history=ats_host_info.state_history,
        assignee=ats_host_info.assignee,
        device_count_summaries=list(device_count_summaries.values()),
        is_bad=ats_host_info.is_bad,
        test_harness=ats_host_info.test_harness,
        test_harness_version=ats_host_info.test_harness_version,
        flated_extra_info=ats_host_info.flated_extra_info,
        last_recovery_time=ats_host_info.last_recovery_time,
        recovery_state=ats_host_info.recovery_state,
        update_state=ats_host_info.update_state,
        update_state_display_message=ats_host_info.update_state_display_message,
        bad_reason=ats_host_info.bad_reason,
        update_timestamp=ats_host_info.update_timestamp,
    )

  @staticmethod
  def ConvertLabInfo(lab_info, timestamp):
    """Converts an OmniLab lab info to an ATS host info.

    Args:
      lab_info: the OmniLab host info
      timestamp: the timestamp when this host info is returned

    Returns:
      an ATS host info
    """
    lab_name = ''
    test_runner_version = ''
    host_group = 'default'
    for (
        host_property
    ) in lab_info.lab_server_feature.host_properties.host_property:
      if host_property.key == 'lab_location':
        lab_name = host_property.value
      elif host_property.key == 'host_version':
        test_runner_version = host_property.value
      elif host_property.key == 'host_group':
        host_group = host_property.value
    host_state = 'UNKNOWN'
    if lab_info.lab_status == lab_pb2.LabStatus.LAB_RUNNING:
      host_state = 'RUNNING'
    elif lab_info.lab_status == lab_pb2.LabStatus.LAB_MISSING:
      host_state = 'GONE'

    return api_messages.HostInfo(
        hostname=lab_info.lab_locator.host_name,
        lab_name=lab_name,
        cluster=host_group,
        host_group=host_group,
        test_runner='OMNILAB',
        test_runner_version=test_runner_version,
        device_infos=[],
        timestamp=datetime.datetime.utcfromtimestamp(timestamp.seconds),
        total_devices=0,
        offline_devices=0,
        available_devices=0,
        allocated_devices=0,
        device_count_timestamp=datetime.datetime.utcfromtimestamp(
            timestamp.seconds
        ),
        hidden=False,
        notes=[],
        extra_info=[],
        next_cluster_ids=[],
        pools=[],
        host_state=host_state,
        state_history=[],
        assignee='',
        device_count_summaries=[],
        is_bad=False,
        test_harness='OMNILAB',
        test_harness_version=test_runner_version,
        flated_extra_info=[],
        last_recovery_time=datetime.datetime.utcfromtimestamp(0),
        recovery_state='',
        update_state='',
        update_state_display_message='',
        bad_reason='',
        update_timestamp=datetime.datetime.utcfromtimestamp(timestamp.seconds),
    )
