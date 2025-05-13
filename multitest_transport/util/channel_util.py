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

"""Utilities for gRPC channels."""

import json
import grpc
from multitest_transport.util import env
from multitest_transport.util import util


class OlcsChannel(metaclass=util.Singleton):
  """Singleton OLCS gRPC channel."""

  def __init__(
      self,
      server_address: str = env.OLCS_SERVER_ADDRESS,
      credential_type: env.CredentialType = env.OLCS_CREDENTIAL_TYPE,
  ):
    self._channel = _create_channel(server_address, credential_type)

  def get_channel(self) -> grpc.Channel:
    return self._channel


class WorkerLabServerChannel(metaclass=util.Singleton):
  """Singleton Worker Lab Server gRPC channel."""

  def __init__(
      self,
      server_address: str = env.WORKER_LAB_SERVER_ADDRESS,
  ):
    self._channel = _create_channel(server_address, env.CredentialType.LOCAL)

  def get_channel(self) -> grpc.Channel:
    return self._channel


def _create_channel(
    server_address: str,
    credential_type: env.CredentialType,
):
  """Create a gRPC channel."""
  service_config_json = json.dumps({
      "methodConfig": [{
          "name": [{}],  # Apply retry to all methods
          "retryPolicy": {
              "maxAttempts": 5,
              "initialBackoff": "0.1s",
              "maxBackoff": "1s",
              "backoffMultiplier": 2,
              "retryableStatusCodes": ["UNAVAILABLE"],
          },
      }]
  })
  options = []
  options.append(("grpc.enable_retries", 1))
  options.append(("grpc.service_config", service_config_json))
  if credential_type is env.CredentialType.ALTS:
    return grpc.secure_channel(
        server_address, grpc.alts_channel_credentials(), options=options
    )
  elif credential_type is env.CredentialType.SSL:
    return grpc.secure_channel(
        server_address, grpc.ssl_channel_credentials(), options=options
    )
  elif credential_type is env.CredentialType.LOCAL:
    return grpc.secure_channel(
        server_address, grpc.local_channel_credentials(), options=options
    )
  else:
    return grpc.insecure_channel(server_address)
