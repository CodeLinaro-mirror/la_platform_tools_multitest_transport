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

"""A OLCS(OmniLab Long-running Client Service) lab record service client module."""
import grpc
from com_google_deviceinfra.src.devtools.common.metrics.stability.util import grpc_error_util
from com_google_deviceinfra.src.devtools.mobileharness.infra.master.rpc.proto import lab_record_service_pb2
from com_google_deviceinfra.src.devtools.mobileharness.infra.master.rpc.proto import lab_record_service_pb2_grpc

OLCS_SERVER_ADDRESS = 'localhost:7030'


class OlcsLabRecordRpcError(Exception):
  """Raises error when connecting to OLCS lab record service."""


class OlcsLabRecordClient:
  """The client for OCLS lab record service."""

  def __init__(self, stub):
    """Initializer."""
    self._stub = stub

  @classmethod
  def create(
      cls, server_address: str = OLCS_SERVER_ADDRESS
  ) -> 'OlcsLabRecordClient':
    """Create OLCS lab record service client."""
    channel = grpc.insecure_channel(server_address)
    return OlcsLabRecordClient(
        lab_record_service_pb2_grpc.LabRecordServiceStub(channel)
    )

  def get_lab_record(
      self, request: lab_record_service_pb2.GetLabRecordRequest
  ) -> lab_record_service_pb2.GetLabRecordResponse:
    try:
      return self._stub.GetLabRecord(request)
    except grpc.RpcError as e:
      exception_detail = grpc_error_util.to_exception_detail(e)
      raise OlcsLabRecordRpcError(
          'Failed to get lab record %s' % exception_detail.summary
          if exception_detail
          else ''
      ) from e

  def get_device_record(
      self, request: lab_record_service_pb2.GetDeviceRecordRequest
  ) -> lab_record_service_pb2.GetDeviceRecordResponse:
    try:
      return self._stub.GetDeviceRecord(request)
    except grpc.RpcError as e:
      exception_detail = grpc_error_util.to_exception_detail(e)
      raise OlcsLabRecordRpcError(
          'Failed to get device record %s' % exception_detail.summary
          if exception_detail
          else ''
      ) from e
