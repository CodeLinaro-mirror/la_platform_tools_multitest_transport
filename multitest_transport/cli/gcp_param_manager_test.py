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

"""Unit tests for multitest_transport.cli.gcp_param_manager."""

import base64
from typing import Any
from unittest import mock
from absl.testing import absltest
from googleapiclient import errors
from multitest_transport.cli import gcp_param_manager


class _MockHttpResponse:
  """Mock spec for httplib2 response."""

  def __init__(self, status: int):
    self.status = status


class _MockHttpRequest:
  """Mock spec for googleapiclient HttpRequest."""

  def execute(self) -> Any:
    pass


class _MockParameterVersionsResource:
  """Mock spec for GCP Parameter Manager Versions resource."""

  def render(self, name: str) -> _MockHttpRequest:
    del name
    return _MockHttpRequest()

  def create(  
      self, parent: str, parameterVersionId: str, body: dict[str, Any]
  ) -> _MockHttpRequest:
    del parent, parameterVersionId, body
    return _MockHttpRequest()


class _MockParametersResource:
  """Mock spec for GCP Parameter Manager Parameters resource."""

  def versions(self) -> _MockParameterVersionsResource:
    return _MockParameterVersionsResource()

  def list(self, parent: str) -> _MockHttpRequest:
    del parent
    return _MockHttpRequest()

  def list_next(  
      self, previous_request: Any, previous_response: Any
  ) -> Any:
    del previous_request, previous_response
    return None

  def get(self, name: str) -> _MockHttpRequest:
    del name
    return _MockHttpRequest()

  def create(  
      self, parent: str, parameterId: str, body: dict[str, Any]
  ) -> _MockHttpRequest:
    del parent, parameterId, body
    return _MockHttpRequest()


class _MockLocationsResource:
  """Mock spec for GCP Parameter Manager Locations resource."""

  def parameters(self) -> _MockParametersResource:
    return _MockParametersResource()


class _MockProjectsResource:
  """Mock spec for GCP Parameter Manager Projects resource."""

  def locations(self) -> _MockLocationsResource:
    return _MockLocationsResource()


class _MockParameterManagerService:
  """Mock spec for GCP Parameter Manager root service."""

  def projects(self) -> _MockProjectsResource:
    return _MockProjectsResource()


class GcpParamManagerTest(absltest.TestCase):

  def _create_mock_service_hierarchy(
      self,
  ) -> tuple[
      _MockParameterManagerService,
      _MockParametersResource,
      _MockParameterVersionsResource,
  ]:
    mock_service = mock.create_autospec(
        _MockParameterManagerService, instance=True, spec_set=True
    )
    mock_projects = mock.create_autospec(
        _MockProjectsResource, instance=True, spec_set=True
    )
    mock_locations = mock.create_autospec(
        _MockLocationsResource, instance=True, spec_set=True
    )
    mock_parameters = mock.create_autospec(
        _MockParametersResource, instance=True, spec_set=True
    )
    mock_parameters.list_next.return_value = None
    mock_versions = mock.create_autospec(
        _MockParameterVersionsResource, instance=True, spec_set=True
    )

    mock_service.projects.return_value = mock_projects
    mock_projects.locations.return_value = mock_locations
    mock_locations.parameters.return_value = mock_parameters
    mock_parameters.versions.return_value = mock_versions
    return mock_service, mock_parameters, mock_versions

  def testFetchUnformatted(self):
    mock_service, _, mock_versions = self._create_mock_service_hierarchy()

    raw_text = "test_yaml_content: 123"
    b64_encoded = base64.b64encode(raw_text.encode("utf-8")).decode("utf-8")

    mock_render_req = mock.create_autospec(
        _MockHttpRequest, instance=True, spec_set=True
    )
    mock_render_req.execute.return_value = {"renderedPayload": b64_encoded}
    mock_versions.render.return_value = mock_render_req

    client = gcp_param_manager.GcpParamManagerClient(service=mock_service)
    result = client.FetchUnformatted(
        "projects/p1/locations/global/parameters/cfg/versions/latest"
    )

    self.assertEqual(result, raw_text)
    mock_versions.render.assert_called_once_with(
        name="projects/p1/locations/global/parameters/cfg/versions/latest"
    )

  def testStoreUnformatted(self):
    mock_service, _, mock_versions = self._create_mock_service_hierarchy()

    mock_create_req = mock.create_autospec(
        _MockHttpRequest, instance=True, spec_set=True
    )
    mock_create_req.execute.return_value = {
        "name": "projects/p1/locations/global/parameters/cfg/versions/2"
    }
    mock_versions.create.return_value = mock_create_req

    client = gcp_param_manager.GcpParamManagerClient(service=mock_service)
    version_name = client.StoreUnformatted(
        "projects/p1/locations/global/parameters/cfg/versions/latest",
        "new_config_payload",
    )

    self.assertEqual(
        version_name, "projects/p1/locations/global/parameters/cfg/versions/2"
    )
    b64_expected = base64.b64encode(b"new_config_payload").decode("utf-8")
    mock_versions.create.assert_called_once()
    call_kwargs = mock_versions.create.call_args.kwargs
    self.assertEqual(
        call_kwargs["parent"], "projects/p1/locations/global/parameters/cfg"
    )
    self.assertEqual(call_kwargs["body"], {"payload": {"data": b64_expected}})
    self.assertRegex(call_kwargs["parameterVersionId"], r"^\d{8}_\d{6}$")

  def testListParameters(self):
    mock_service, mock_parameters, _ = self._create_mock_service_hierarchy()

    mock_list_req = mock.create_autospec(
        _MockHttpRequest, instance=True, spec_set=True
    )
    mock_list_req.execute.return_value = {
        "parameters": [
            {"name": "projects/p1/locations/global/parameters/tenant_config"},
            {"name": "projects/p1/locations/global/parameters/dda_pool_config"},
        ]
    }
    mock_parameters.list.return_value = mock_list_req

    client = gcp_param_manager.GcpParamManagerClient(service=mock_service)
    params = client.ListParameters("p1")

    self.assertEqual(params, ["dda_pool_config", "tenant_config"])
    mock_parameters.list.assert_called_once_with(
        parent="projects/p1/locations/global"
    )

  def testListParameters_paginated(self):
    mock_service, mock_parameters, _ = self._create_mock_service_hierarchy()

    req1 = mock.create_autospec(_MockHttpRequest, instance=True, spec_set=True)
    req2 = mock.create_autospec(_MockHttpRequest, instance=True, spec_set=True)
    req1.execute.return_value = {
        "parameters": [
            {"name": "projects/p1/locations/global/parameters/page1_param"},
        ]
    }
    req2.execute.return_value = {
        "parameters": [
            {"name": "projects/p1/locations/global/parameters/page2_param"},
        ]
    }
    mock_parameters.list.return_value = req1
    mock_parameters.list_next.side_effect = [req2, None]

    client = gcp_param_manager.GcpParamManagerClient(service=mock_service)
    params = client.ListParameters("p1")

    self.assertEqual(params, ["page1_param", "page2_param"])
    self.assertEqual(mock_parameters.list_next.call_count, 2)

  def testParameterExists_true(self):
    mock_service, mock_parameters, _ = self._create_mock_service_hierarchy()

    mock_get_req = mock.create_autospec(
        _MockHttpRequest, instance=True, spec_set=True
    )
    mock_get_req.execute.return_value = {
        "name": "projects/p1/locations/global/parameters/node1_node_config"
    }
    mock_parameters.get.return_value = mock_get_req

    client = gcp_param_manager.GcpParamManagerClient(service=mock_service)
    exists = client.ParameterExists("p1", "node1_node_config")

    self.assertTrue(exists)
    mock_parameters.get.assert_called_once_with(
        name="projects/p1/locations/global/parameters/node1_node_config"
    )

  def testParameterExists_falseOn404(self):
    mock_service, mock_parameters, _ = self._create_mock_service_hierarchy()

    mock_get_req = mock.create_autospec(
        _MockHttpRequest, instance=True, spec_set=True
    )
    mock_resp = _MockHttpResponse(status=404)
    mock_get_req.execute.side_effect = errors.HttpError(mock_resp, b"Not found")
    mock_parameters.get.return_value = mock_get_req

    client = gcp_param_manager.GcpParamManagerClient(service=mock_service)
    exists = client.ParameterExists("p1", "node1_node_config")

    self.assertFalse(exists)

  def testCreateParameter(self):
    mock_service, mock_parameters, _ = self._create_mock_service_hierarchy()

    mock_create_req = mock.create_autospec(
        _MockHttpRequest, instance=True, spec_set=True
    )
    mock_create_req.execute.return_value = {
        "name": "projects/p1/locations/global/parameters/node1_node_config"
    }
    mock_parameters.create.return_value = mock_create_req

    client = gcp_param_manager.GcpParamManagerClient(service=mock_service)
    name = client.CreateParameter("p1", "node1_node_config")

    self.assertEqual(
        name, "projects/p1/locations/global/parameters/node1_node_config"
    )
    mock_parameters.create.assert_called_once_with(
        parent="projects/p1/locations/global",
        parameterId="node1_node_config",
        body={"format": "UNFORMATTED"},
    )


if __name__ == "__main__":
  absltest.main()
