# Copyright 2025 Google LLC
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

"""Client for sending requests to the worker lab server's Health service."""
from typing import Optional
import grpc
from multitest_transport.util import channel_util
from com_google_deviceinfra.src.devtools.common.metrics.stability.util import grpc_error_util
from com_google_deviceinfra.src.devtools.deviceinfra.host.daemon.proto import health_pb2
from com_google_deviceinfra.src.devtools.deviceinfra.host.daemon.proto import health_pb2_grpc


class WorkerLabHealthRpcError(Exception):
  """Raises error when sending requests to the worker lab server's Health service."""


class WorkerLabHealthClient:
  """The client for worker lab server's Health service."""

  def __init__(self, channel: grpc.Channel):
    """Initializer."""
    self._stub = health_pb2_grpc.HealthStub(channel)

  @classmethod
  def create(
      cls, server_address: Optional[str] = None
  ) -> 'WorkerLabHealthClient':
    """Create worker lab server's Health service client."""
    channel = channel_util.WorkerLabServerChannel(server_address).get_channel()  # pyrefly: ignore[bad-argument-type]
    return WorkerLabHealthClient(channel)

  def drain(
      self, request: health_pb2.DrainServerRequest
  ) -> health_pb2.DrainServerResponse:
    try:
      return self._stub.Drain(request)
    except grpc.RpcError as e:
      exception_detail = grpc_error_util.to_exception_detail(e)
      raise WorkerLabHealthRpcError(
          exception_detail.summary.message
          if exception_detail and exception_detail.summary.message
          else ''
      ) from e

  def check(
      self, request: health_pb2.CheckStatusRequest
  ) -> health_pb2.CheckStatusResponse:
    try:
      return self._stub.Check(request)
    except grpc.RpcError as e:
      exception_detail = grpc_error_util.to_exception_detail(e)
      raise WorkerLabHealthRpcError(
          exception_detail.summary.message
          if exception_detail and exception_detail.summary.message
          else ''
      ) from e
