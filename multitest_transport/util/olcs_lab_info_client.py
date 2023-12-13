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

"""A OLCS(OmniLab Long-running Client Service) lab info service client module."""
import grpc
from com_google_deviceinfra.src.devtools.common.metrics.stability.util import grpc_error_util
from com_google_deviceinfra.src.devtools.mobileharness.infra.master.rpc.proto import lab_info_service_pb2
from com_google_deviceinfra.src.devtools.mobileharness.infra.master.rpc.proto import lab_info_service_pb2_grpc

OLCS_SERVER_ADDRESS = 'localhost:7030'


class OlcsLabInfoRpcError(Exception):
  """Raises error when connecting to OLCS lab info service."""


class OlcsLabInfoClient:
  """The client for OCLS lab info service."""

  def __init__(self, stub):
    """Initializer."""
    self._stub = stub

  @classmethod
  def create(
      cls, server_address: str = OLCS_SERVER_ADDRESS
  ) -> 'OlcsLabInfoClient':
    """Create OLCS lab info service client."""
    channel = grpc.insecure_channel(server_address)
    return OlcsLabInfoClient(
        lab_info_service_pb2_grpc.LabInfoServiceStub(channel)
    )

  def get_lab_info(
      self, request: lab_info_service_pb2.GetLabInfoRequest
  ) -> lab_info_service_pb2.GetLabInfoResponse:
    try:
      return self._stub.GetLabInfo(request)
    except grpc.RpcError as e:
      exception_detail = grpc_error_util.to_exception_detail(e)
      raise OlcsLabInfoRpcError(
          'Failed to get lab info %s' % exception_detail.summary
          if exception_detail
          else ''
      ) from e
