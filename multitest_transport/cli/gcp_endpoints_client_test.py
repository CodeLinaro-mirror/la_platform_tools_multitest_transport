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

"""Unit tests for multitest_transport.cli.gcp_endpoints_client."""

from typing import Any
from unittest import mock
from absl.testing import absltest
from multitest_transport.cli import gcp_endpoints_client


class _MockHttpRequest:
  """Mock spec for googleapiclient HttpRequest."""

  def execute(self) -> Any:
    pass


class _MockServicesResource:
  """Mock spec for Service Management services resource."""

  def list(  
      self, producerProjectId: str
  ) -> _MockHttpRequest:
    del producerProjectId
    return _MockHttpRequest()

  def list_next(  
      self, previous_request: Any, previous_response: Any
  ) -> Any:
    del previous_request, previous_response
    return None


class _MockServiceManagementService:
  """Mock spec for Service Management root service."""

  def services(self) -> _MockServicesResource:
    return _MockServicesResource()


class GcpEndpointsClientTest(absltest.TestCase):

  def _create_mock_service_hierarchy(
      self,
  ) -> tuple[_MockServiceManagementService, _MockServicesResource]:
    mock_service = mock.create_autospec(
        _MockServiceManagementService, instance=True, spec_set=True
    )
    mock_services_resource = mock.create_autospec(
        _MockServicesResource, instance=True, spec_set=True
    )
    mock_services_resource.list_next.return_value = None
    mock_service.services.return_value = mock_services_resource
    return mock_service, mock_services_resource

  def testListServiceNames(self):
    mock_service, mock_services_res = self._create_mock_service_hierarchy()
    mock_req = mock.create_autospec(
        _MockHttpRequest, instance=True, spec_set=True
    )
    mock_req.execute.return_value = {
        "services": [
            {"serviceName": "ep2.endpoints.test-proj.cloud.goog"},
            {"serviceName": "ep1.endpoints.test-proj.cloud.goog"},
        ]
    }
    mock_services_res.list.return_value = mock_req

    client = gcp_endpoints_client.GcpEndpointsClient(service=mock_service)
    service_names = client.ListServiceNames("test-proj")

    self.assertEqual(
        service_names,
        [
            "ep1.endpoints.test-proj.cloud.goog",
            "ep2.endpoints.test-proj.cloud.goog",
        ],
    )
    mock_services_res.list.assert_called_once_with(
        producerProjectId="test-proj"
    )

  def testListServiceNames_empty(self):
    mock_service, mock_services_res = self._create_mock_service_hierarchy()
    mock_req = mock.create_autospec(
        _MockHttpRequest, instance=True, spec_set=True
    )
    mock_req.execute.return_value = {}
    mock_services_res.list.return_value = mock_req

    client = gcp_endpoints_client.GcpEndpointsClient(service=mock_service)
    service_names = client.ListServiceNames("test-proj")

    self.assertEqual(service_names, [])

  def testListServiceNames_paginated(self):
    mock_service, mock_services_res = self._create_mock_service_hierarchy()
    req1 = mock.create_autospec(_MockHttpRequest, instance=True, spec_set=True)
    req2 = mock.create_autospec(_MockHttpRequest, instance=True, spec_set=True)
    req1.execute.return_value = {
        "services": [{"serviceName": "ep-page1.endpoints.test-proj.cloud.goog"}]
    }
    req2.execute.return_value = {
        "services": [{"serviceName": "ep-page2.endpoints.test-proj.cloud.goog"}]
    }
    mock_services_res.list.return_value = req1
    mock_services_res.list_next.side_effect = [req2, None]

    client = gcp_endpoints_client.GcpEndpointsClient(service=mock_service)
    service_names = client.ListServiceNames("test-proj")

    self.assertEqual(
        service_names,
        [
            "ep-page1.endpoints.test-proj.cloud.goog",
            "ep-page2.endpoints.test-proj.cloud.goog",
        ],
    )
    self.assertEqual(mock_services_res.list_next.call_count, 2)

  def testListServiceNames_apiFailure(self):
    mock_service, mock_services_res = self._create_mock_service_hierarchy()
    mock_req = mock.create_autospec(
        _MockHttpRequest, instance=True, spec_set=True
    )
    original_error = ValueError("permission denied")
    mock_req.execute.side_effect = original_error
    mock_services_res.list.return_value = mock_req

    client = gcp_endpoints_client.GcpEndpointsClient(service=mock_service)

    # iterate_paginated_api converts any transport failure into a chained
    # RuntimeError, so callers never see a raw HttpError.
    with self.assertRaises(RuntimeError) as ctx:
      client.ListServiceNames("test-proj")

    self.assertIn("permission denied", str(ctx.exception))
    self.assertIs(ctx.exception.__cause__, original_error)


if __name__ == "__main__":
  absltest.main()
