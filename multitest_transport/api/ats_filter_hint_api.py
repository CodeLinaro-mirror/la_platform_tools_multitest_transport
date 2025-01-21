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

"""A module to provide device APIs."""
import logging
from typing import Optional

import endpoints
from multitest_transport.api import base
from multitest_transport.api import host_api
from multitest_transport.util import olcs_lab_info_client
from multitest_transport.util import olcs_lab_info_stub
from protorpc import message_types
from protorpc import messages
from protorpc import remote
from tradefed_cluster import api_messages
from tradefed_cluster import common

from com_google_deviceinfra.src.devtools.mobileharness.shared.labinfo.proto import lab_info_service_pb2


@base.MTT_API.api_class(resource_name="filterHint", path="filterHints")
class AtsFilterHintApi(remote.Service):
  """A class for filter hint API service."""

  def __init__(
      self,
      lab_info_client: Optional[olcs_lab_info_client.OlcsLabInfoClient] = None,
  ):
    if lab_info_client:
      self._olcs_lab_info_client = lab_info_client
    else:
      self._olcs_lab_info_client = (
          olcs_lab_info_client.OlcsLabInfoClient.create()
      )

  FILTER_HINT_LIST_RESOURCE = endpoints.ResourceContainer(
      message_types.VoidMessage,
      type=messages.EnumField(common.FilterHintType, 1),
  )

  @base.ApiMethod(
      FILTER_HINT_LIST_RESOURCE,
      api_messages.FilterHintCollection,
      path="/filterHints",
      http_method="GET",
      name="list",
  )
  def ListFilterHints(self, request):
    """Fetches a list of filter hint by type.

    Args:
      request: an API request.

    Returns:
      a FilterHintCollection object.
    """
    logging.info("ListFilterHints %s", request)

    if request.type == common.FilterHintType.POOL:
      return self._ListPools()
    elif request.type == common.FilterHintType.LAB:
      return self._ListLabs()
    elif request.type == common.FilterHintType.RUN_TARGET:
      return self._ListRunTargets()
    elif request.type == common.FilterHintType.HOST:
      return self._ListHosts()
    elif request.type == common.FilterHintType.TEST_HARNESS:
      return self._ListTestHarness()
    elif request.type == common.FilterHintType.TEST_HARNESS_VERSION:
      return self._ListTestHarnessVersion()
    elif request.type == common.FilterHintType.HOST_STATE:
      return self._ListHostStates()
    elif request.type == common.FilterHintType.DEVICE_STATE:
      return self._ListDeviceStates()
    elif request.type == common.FilterHintType.HOST_GROUP:
      return self._ListHostGroup()
    elif request.type == common.FilterHintType.UPDATE_STATE:
      return self._ListHostUpdateStates()
    elif request.type == common.FilterHintType.PRODUCT:
      return self._ListProducts()
    elif request.type == common.FilterHintType.PRODUCT_VARIANT:
      return self._ListProductVariants()
    else:
      raise endpoints.BadRequestException("Invalid type: %s" % request.type)

  def _ListPools(self):
    infos = [
        api_messages.FilterHintMessage(value=pools)
        for pools in {
            ",".join(host_info.pools)
            for host_info in self._GetHostInfos()
        }
    ]
    return api_messages.FilterHintCollection(filter_hints=infos)

  def _ListLabs(self):
    """Fetches a list of labs."""
    infos = [
        api_messages.FilterHintMessage(value=lab_name)
        for lab_name in {
            host_info.lab_name
            for host_info in self._GetHostInfos()
        }
    ]
    return api_messages.FilterHintCollection(filter_hints=infos)

  def _ListRunTargets(self):
    """Fetches a list of run targets."""
    infos = [
        api_messages.FilterHintMessage(value=run_target)
        for run_target in {
            device_info.run_target
            for device_info in self._GetDeviceInfos()
        }
    ]
    return api_messages.FilterHintCollection(filter_hints=infos)

  def _ListHosts(self):
    """Fetches a list of hostnames."""
    infos = [
        api_messages.FilterHintMessage(value=hostname)
        for hostname in {
            host_info.hostname
            for host_info in self._GetHostInfos()
        }
    ]
    return api_messages.FilterHintCollection(filter_hints=infos)

  def _ListTestHarness(self):
    """Fetches a list of test harness."""
    infos = [
        api_messages.FilterHintMessage(value=test_harness)
        for test_harness in {
            host_info.test_harness
            for host_info in self._GetHostInfos()
        }
    ]
    return api_messages.FilterHintCollection(filter_hints=infos)

  def _ListTestHarnessVersion(self):
    """Fetches a list of test harness version."""
    infos = [
        api_messages.FilterHintMessage(value=test_harness_version)
        for test_harness_version in {
            host_info.test_harness_version
            for host_info in self._GetHostInfos()
        }
    ]
    return api_messages.FilterHintCollection(filter_hints=infos)

  def _ListHostStates(self):
    """Fetches a list of host state."""
    infos = [
        api_messages.FilterHintMessage(value=host_state)
        for host_state in {
            host_info.host_state
            for host_info in self._GetHostInfos()
        }
    ]
    return api_messages.FilterHintCollection(filter_hints=infos)

  def _ListDeviceStates(self):
    """Fetches a list of device state."""
    infos = [
        api_messages.FilterHintMessage(value=state)
        for state in {
            device_info.state
            for device_info in self._GetDeviceInfos()
        }
    ]
    return api_messages.FilterHintCollection(filter_hints=infos)

  def _ListHostGroup(self):
    """Fetches a list of host group."""
    infos = [
        api_messages.FilterHintMessage(value=host_group)
        for host_group in {
            host_info.host_group
            for host_info in self._GetHostInfos()
        }
    ]
    return api_messages.FilterHintCollection(filter_hints=infos)

  def _ListHostUpdateStates(self):
    """Fetches a list of host update states."""
    infos = [
        api_messages.FilterHintMessage(value=host_update_state)
        for host_update_state in {
            host_info.update_state
            for host_info in self._GetHostInfos()
        }
    ]
    return api_messages.FilterHintCollection(filter_hints=infos)

  def _ListProducts(self):
    """Fetches a list of distinct products."""
    infos = [
        api_messages.FilterHintMessage(value=product)
        for product in {
            device_info.product
            for device_info in self._GetDeviceInfos()
        }
    ]
    return api_messages.FilterHintCollection(filter_hints=infos)

  def _ListProductVariants(self):
    """Fetches a list of distinct product variants."""
    infos = [
        api_messages.FilterHintMessage(value=product_variant)
        for product_variant in {
            device_info.product_variant
            for device_info in self._GetDeviceInfos()
        }
    ]
    return api_messages.FilterHintCollection(filter_hints=infos)

  def _GetHostInfos(self) -> list[api_messages.HostInfo]:
    get_lab_info_request = lab_info_service_pb2.GetLabInfoRequest()
    response = self._olcs_lab_info_client.get_lab_info(get_lab_info_request)
    return [
        host_api.HostApi.ConvertHostInfo(
            data, response.lab_query_result.timestamp
        )
        for data in response.lab_query_result.lab_view.lab_data
    ]

  def _GetDeviceInfos(self) -> list[api_messages.DeviceInfo]:
    get_lab_info_request = lab_info_service_pb2.GetLabInfoRequest()
    get_lab_info_request.lab_query.device_view_request.device_limit = 0
    response = self._olcs_lab_info_client.get_lab_info(get_lab_info_request)
    return [
        olcs_lab_info_stub.OlcsLabInfoStub.ConvertDeviceInfo(
            data, response.lab_query_result.timestamp
        )
        for data in response.lab_query_result.device_view.grouped_devices.device_list.device_info
    ]
