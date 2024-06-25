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

"""A OLCS(OmniLab Long-running Client Service) session service client module."""
from typing import Iterator
import grpc
from multitest_transport.util import channel_util
from com_google_deviceinfra.src.devtools.common.metrics.stability.util import grpc_error_util
# from google3.net.rpc.python import pywraprpc
from com_google_deviceinfra.src.devtools.mobileharness.infra.client.longrunningservice.proto import session_service_pb2
from com_google_deviceinfra.src.devtools.mobileharness.infra.client.longrunningservice.proto import session_service_pb2_grpc


class OlcsSessionRpcError(Exception):
  """Raises error when connecting to OLCS session service."""


class OlcsSessionClient:
  """The client for OCLS session service."""

  def __init__(self, channel: grpc.Channel):
    """Initializer."""
    self._stub = session_service_pb2_grpc.SessionServiceStub(channel)

  @classmethod
  def create(cls) -> 'OlcsSessionClient':
    """Create OLCS session service client."""
    channel = channel_util.OlcsChannel().get_channel()
    return OlcsSessionClient(channel)

  def create_session(
      self, request: session_service_pb2.CreateSessionRequest
  ) -> session_service_pb2.CreateSessionResponse:
    try:
      return self._stub.CreateSession(request)
    except grpc.RpcError as e:
      exception_detail = grpc_error_util.to_exception_detail(e)
      raise OlcsSessionRpcError(
          'Failed to create session %s' % exception_detail.summary
          if exception_detail
          else ''
      ) from e

  def run_session(
      self, request: session_service_pb2.RunSessionRequest
  ) -> session_service_pb2.RunSessionResponse:
    try:
      return self._stub.RunSession(request)
    except grpc.RpcError as e:
      exception_detail = grpc_error_util.to_exception_detail(e)
      raise OlcsSessionRpcError(
          'Failed to run session %s' % exception_detail.summary
          if exception_detail
          else ''
      ) from e

  def get_session(
      self, request: session_service_pb2.GetSessionRequest
  ) -> session_service_pb2.GetSessionResponse:
    try:
      return self._stub.GetSession(request)
    except grpc.RpcError as e:
      exception_detail = grpc_error_util.to_exception_detail(e)
      raise OlcsSessionRpcError(
          'Failed to get session %s' % exception_detail.summary
          if exception_detail
          else ''
      ) from e

  def get_all_sessions(
      self, request: session_service_pb2.GetAllSessionsRequest
  ) -> session_service_pb2.GetAllSessionsResponse:
    try:
      return self._stub.GetAllSessions(request)
    except grpc.RpcError as e:
      exception_detail = grpc_error_util.to_exception_detail(e)
      raise OlcsSessionRpcError(
          'Failed to get all sessions %s' % exception_detail.summary
          if exception_detail
          else ''
      ) from e

  def subscribe_session(
      self, request: Iterator[session_service_pb2.SubscribeSessionRequest]
  ) -> Iterator[session_service_pb2.SubscribeSessionResponse]:
    try:
      return self._stub.SubscribeSession(request)
    except grpc.RpcError as e:
      exception_detail = grpc_error_util.to_exception_detail(e)
      raise OlcsSessionRpcError(
          'Failed to subscribe session %s' % exception_detail.summary
          if exception_detail
          else ''
      ) from e
