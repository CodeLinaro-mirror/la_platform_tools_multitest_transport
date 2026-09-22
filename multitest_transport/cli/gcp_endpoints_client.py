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

"""Google Cloud Service Management client for Cloud Endpoints discovery."""

from typing import Any, Optional
import google.auth.credentials
from googleapiclient import discovery
from multitest_transport.cli import gcp_api_util
from multitest_transport.cli import google_auth_util

_SERVICE_MANAGEMENT_SCOPES = ["https://www.googleapis.com/auth/cloud-platform"]


class GcpEndpointsClient:
  """Client wrapper for Google Cloud Service Management v1 API."""

  def __init__(self, service: Any):
    """Initializes GcpEndpointsClient with a pre-built Resource instance.

    Args:
      service: Pre-built googleapiclient Resource instance.
    """
    self._service = service

  @classmethod
  def FromCredentials(
      cls, credentials: Optional[google.auth.credentials.Credentials] = None
  ) -> "GcpEndpointsClient":
    """Instantiates client using Google credentials (defaults to ADC).

    Args:
      credentials: Optional Google Auth credentials. If None, resolves
        Application Default Credentials (ADC) with service management scopes.

    Returns:
      Instantiated GcpEndpointsClient.
    """
    creds = credentials or google_auth_util.GetDefaultCredential(
        _SERVICE_MANAGEMENT_SCOPES
    )
    service = discovery.build("servicemanagement", "v1", credentials=creds)
    return cls(service=service)

  @classmethod
  def FromServiceAccountKeyFile(cls, key_path: str) -> "GcpEndpointsClient":
    """Instantiates client using a service account JSON key file.

    Args:
      key_path: Path to the service account JSON key file.

    Returns:
      Instantiated GcpEndpointsClient.
    """
    credentials = google_auth_util.CreateCredentialFromServiceAccount(
        key_path, _SERVICE_MANAGEMENT_SCOPES
    )
    return cls.FromCredentials(credentials=credentials)

  def ListServiceNames(self, project_id: str) -> list[str]:
    """Lists all Cloud Endpoints service names in the specified project.

    Equivalent to `gcloud endpoints services list --project=<project_id>`.

    Args:
      project_id: Target GCP Project ID.

    Returns:
      List of service name strings (e.g. ['api.endpoints.proj.cloud.goog']).

    Raises:
      RuntimeError: If the Service Management API call fails. Raised by
        gcp_api_util.iterate_paginated_api, which chains the underlying error.
    """
    collection = self._service.services()
    request = collection.list(producerProjectId=project_id)
    service_names: list[str] = []
    for item in gcp_api_util.iterate_paginated_api(
        resource_collection=collection,
        initial_request=request,
        items_key="services",
    ):
      name = item.get("serviceName")
      if name:
        service_names.append(name)
    return sorted(service_names)
