# Copyright 2026 Google LLC
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

"""GCP Parameter Manager client for MTT Node configuration management."""

import base64
import datetime
import logging
from typing import Any, Optional
import google.auth.credentials
from googleapiclient import discovery
from googleapiclient import errors
from multitest_transport.cli import gcp_api_util
from multitest_transport.cli import google_auth_util

logger = logging.getLogger(__name__)


class GcpParamManagerClient:
  """Client for parameters in GCP Parameter Manager."""

  def __init__(self, service: Any):
    """Initializes client with a pre-built Resource instance.

    Args:
      service: Pre-built googleapiclient Resource instance.
    """
    self._service = service

  @classmethod
  def FromCredentials(
      cls, credentials: Optional[google.auth.credentials.Credentials] = None
  ) -> "GcpParamManagerClient":
    """Factory to create client using credentials, defaulting to ADC.

    Args:
      credentials: Optional Google Auth credentials. If None, resolves
        Application Default Credentials (ADC) with Parameter Manager scope.

    Returns:
      Instantiated GcpParamManagerClient.
    """
    creds = credentials or google_auth_util.GetDefaultCredential(
        [google_auth_util.AUTH_SCOPE]
    )
    service = discovery.build("parametermanager", "v1", credentials=creds)
    return cls(service=service)

  @classmethod
  def FromServiceAccountKeyFile(
      cls, service_account_key_path: str
  ) -> "GcpParamManagerClient":
    """Factory to create client using a service account JSON key file.

    Args:
      service_account_key_path: Path to the service account JSON key file.

    Returns:
      Instantiated GcpParamManagerClient.
    """
    credentials = google_auth_util.CreateCredentialFromServiceAccount(
        service_account_key_path, [google_auth_util.AUTH_SCOPE]
    )
    return cls.FromCredentials(credentials=credentials)

  def FetchUnformatted(self, param_version_path: str) -> str:
    """Renders and decodes an UNFORMATTED parameter version payload as a string.

    Args:
      param_version_path: Resource name path of the parameter version (e.g.
        'projects/123/locations/global/parameters/my-param/versions/latest').

    Returns:
      Decoded UTF-8 string payload.
    """
    name = param_version_path.strip("/")
    try:
      response = (
          self._service.projects()
          .locations()
          .parameters()
          .versions()
          .render(name=name)
          .execute()
      )
    except Exception as e:
      raise RuntimeError(
          f"Failed to fetch parameter version {name} from GCP Parameter"
          f" Manager: {e}"
      ) from e

    payload_base64 = response.get("renderedPayload")
    if not payload_base64:
      raise ValueError(
          f"No payload data in response for {name}. Response: {response}"
      )

    try:
      payload_bytes = base64.b64decode(payload_base64)
      return payload_bytes.decode("utf-8")
    except Exception as e:
      raise ValueError(f"Failed to decode payload for {name}: {e}") from e

  def StoreUnformatted(
      self,
      param_version_path: str,
      payload_str: str,
      version_id: Optional[str] = None,
  ) -> str:
    """Stores a new parameter version with the given UNFORMATTED payload string.

    Args:
      param_version_path: Resource name path of the parameter or parameter
        version (e.g. 'projects/123/locations/global/parameters/my-param' or
        'projects/123/locations/global/parameters/my-param/versions/latest'). If
        a versioned path is provided, the parent parameter resource path is
        automatically extracted.
      payload_str: UTF-8 string content to store in the new version.
      version_id: Optional explicit parameter version ID. If None, defaults to
        the current UTC timestamp formatted as 'YYYYMMDD_HHMMSS'.

    Returns:
      Resource name of the created parameter version (e.g.
      'projects/123/locations/global/parameters/my-param/versions/20260917_163105').
    """
    parent = param_version_path.strip("/")
    if "/versions/" in parent:
      parent = parent.rsplit("/versions/", 1)[0]

    if version_id is None:
      version_id = datetime.datetime.now(datetime.timezone.utc).strftime(
          "%Y%m%d_%H%M%S"
      )

    b64_data = base64.b64encode(payload_str.encode("utf-8")).decode("utf-8")
    body = {
        "payload": {
            "data": b64_data,
        }
    }
    try:
      response = (
          self._service.projects()
          .locations()
          .parameters()
          .versions()
          .create(parent=parent, parameterVersionId=version_id, body=body)
          .execute()
      )
    except Exception as e:
      raise RuntimeError(
          f"Failed to store version under {parent} in GCP Parameter Manager:"
          f" {e}"
      ) from e
    return response.get("name", "")

  def ListParameters(
      self, project_id: str, location: str = "global"
  ) -> list[str]:
    """Lists all parameter IDs under the specified project and location.

    Args:
      project_id: Target GCP Project ID.
      location: Location string (defaults to 'global').

    Returns:
      List of parameter ID strings (e.g. ['tenant_config', 'pool_config']).
    """
    parent = f"projects/{project_id}/locations/{location}"
    collection = self._service.projects().locations().parameters()
    request = collection.list(parent=parent)
    param_ids: list[str] = []
    try:
      for item in gcp_api_util.iterate_paginated_api(
          resource_collection=collection,
          initial_request=request,
          items_key="parameters",
      ):
        name = item.get("name", "")
        if name:
          param_ids.append(name.split("/")[-1])
    except Exception as e:
      raise RuntimeError(
          f"Failed to list parameters under {parent} in GCP Parameter"
          f" Manager: {e}"
      ) from e
    return sorted(param_ids)

  def ParameterExists(
      self, project_id: str, parameter_id: str, location: str = "global"
  ) -> bool:
    """Checks whether a parameter exists in GCP Parameter Manager.

    Args:
      project_id: Target GCP Project ID.
      parameter_id: Parameter ID string (e.g. 'my-node_node_config').
      location: Location string (defaults to 'global').

    Returns:
      True if the parameter exists, False if 404 Not Found.
    """
    param_path = (
        f"projects/{project_id}/locations/{location}/parameters/{parameter_id}"
    )
    try:
      self._service.projects().locations().parameters().get(
          name=param_path
      ).execute()
      return True
    except errors.HttpError as e:
      if e.resp.status == 404:
        return False
      raise RuntimeError(
          f"Failed to check parameter {param_path} in GCP Parameter"
          f" Manager: {e}"
      ) from e
    except Exception as e:
      raise RuntimeError(
          f"Failed to check parameter {param_path} in GCP Parameter"
          f" Manager: {e}"
      ) from e

  def CreateParameter(
      self, project_id: str, parameter_id: str, location: str = "global"
  ) -> str:
    """Creates a new parameter in GCP Parameter Manager with UNFORMATTED format.

    Args:
      project_id: Target GCP Project ID.
      parameter_id: Parameter ID string (e.g. 'my-node_node_config').
      location: Location string (defaults to 'global').

    Returns:
      Resource name of the created parameter.
    """
    parent = f"projects/{project_id}/locations/{location}"
    body = {
        "format": "UNFORMATTED",
    }
    try:
      response = (
          self._service.projects()
          .locations()
          .parameters()
          .create(parent=parent, parameterId=parameter_id, body=body)
          .execute()
      )
    except Exception as e:
      raise RuntimeError(
          f"Failed to create parameter {parameter_id} under {parent} in GCP"
          f" Parameter Manager: {e}"
      ) from e
    return response.get("name", "")
