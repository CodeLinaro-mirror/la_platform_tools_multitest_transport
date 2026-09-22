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

"""GCP API utility functions for MTT Node."""

from typing import Any, Dict, Iterable


def iterate_paginated_api(
    resource_collection: Any,
    initial_request: Any,
    items_key: str,
) -> Iterable[Dict[str, Any]]:
  """Generic generator to iterate over all items in a paginated GCP API.

  Args:
    resource_collection: The GCP API collection object (e.g.,
      service.projects().locations().parameters()).
    initial_request: The initial list request object.
    items_key: The key in the JSON response containing the list of items (e.g.,
      'parameters' or 'services').

  Yields:
    Individual item dictionaries from the API response.

  Raises:
    RuntimeError: If executing any API request fails.
  """
  request = initial_request
  while request is not None:
    try:
      response = request.execute()
    except Exception as e:
      raise RuntimeError(f"GCP API pagination failed: {e}") from e

    # Yield each item in the current page
    for item in response.get(items_key, []):
      yield item

    # Automatically extracts nextPageToken and creates the request for the
    # next page. Returns None if there are no more pages.
    request = resource_collection.list_next(
        previous_request=request,
        previous_response=response,
    )
