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

"""A module to provide test APIs."""
# Non-standard docstrings are used to generate the API documentation.

import endpoints
from protorpc import message_types
from protorpc import messages
from protorpc import remote


from multitest_transport.api import base

from tradefed_cluster import api_messages


@base.MTT_API.api_class(resource_name="device", path="devices")
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

  @base.ApiMethod(
      DEVICE_LIST_RESOURCE,
      api_messages.DeviceInfoCollection,
      path="/devices",
      http_method="GET",
      name="list",
  )
  def ListDevices(self, request):
    """Fetches a list of devices.

    Args:
      request: an API request.

    Returns:
      a DeviceInfoCollection object.
    """
    # TODO: Add real implementation to query devices from OLCS.
    return api_messages.DeviceInfoCollection(
        device_infos=[], next_cursor="", prev_cursor="", more=False
    )
