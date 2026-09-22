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

"""Unit tests for multitest_transport.cli.gcp_api_util."""

from typing import Any
from unittest import mock
from absl.testing import absltest
from multitest_transport.cli import gcp_api_util


class _MockRequest:

  def execute(self) -> Any:
    pass


class _MockCollection:

  def list_next(self, previous_request: Any, previous_response: Any) -> Any:
    del previous_request, previous_response
    pass


class GcpApiUtilTest(absltest.TestCase):

  def testIteratePaginatedApi_singlePage(self):
    mock_collection = mock.create_autospec(_MockCollection, instance=True)
    mock_req = mock.create_autospec(_MockRequest, instance=True)
    mock_req.execute.return_value = {
        "items": [{"name": "item1"}, {"name": "item2"}]
    }
    mock_collection.list_next.return_value = None

    results = list(
        gcp_api_util.iterate_paginated_api(
            resource_collection=mock_collection,
            initial_request=mock_req,
            items_key="items",
        )
    )

    self.assertEqual(results, [{"name": "item1"}, {"name": "item2"}])
    mock_collection.list_next.assert_called_once_with(
        previous_request=mock_req,
        previous_response={"items": [{"name": "item1"}, {"name": "item2"}]},
    )

  def testIteratePaginatedApi_multiplePages(self):
    mock_collection = mock.create_autospec(_MockCollection, instance=True)
    req1 = mock.create_autospec(_MockRequest, instance=True)
    req2 = mock.create_autospec(_MockRequest, instance=True)

    resp1 = {"items": [{"name": "item1"}]}
    resp2 = {"items": [{"name": "item2"}, {"name": "item3"}]}

    req1.execute.return_value = resp1
    req2.execute.return_value = resp2

    mock_collection.list_next.side_effect = [req2, None]

    results = list(
        gcp_api_util.iterate_paginated_api(
            resource_collection=mock_collection,
            initial_request=req1,
            items_key="items",
        )
    )

    self.assertEqual(
        results,
        [{"name": "item1"}, {"name": "item2"}, {"name": "item3"}],
    )
    self.assertEqual(mock_collection.list_next.call_count, 2)

  def testIteratePaginatedApi_emptyResponse(self):
    mock_collection = mock.create_autospec(_MockCollection, instance=True)
    mock_req = mock.create_autospec(_MockRequest, instance=True)
    mock_req.execute.return_value = {}
    mock_collection.list_next.return_value = None

    results = list(
        gcp_api_util.iterate_paginated_api(
            resource_collection=mock_collection,
            initial_request=mock_req,
            items_key="items",
        )
    )

    self.assertEqual(results, [])

  def testIteratePaginatedApi_errorRaisesRuntimeError(self):
    mock_collection = mock.create_autospec(_MockCollection, instance=True)
    mock_req = mock.create_autospec(_MockRequest, instance=True)
    mock_req.execute.side_effect = IOError("Connection reset")

    with self.assertRaisesRegex(RuntimeError, "GCP API pagination failed"):
      list(
          gcp_api_util.iterate_paginated_api(
              resource_collection=mock_collection,
              initial_request=mock_req,
              items_key="items",
          )
      )


if __name__ == "__main__":
  absltest.main()
