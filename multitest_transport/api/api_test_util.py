# Copyright 2019 Google LLC
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

"""A utility module for API tests."""

import endpoints
from tradefed_cluster import testbed_dependent_test
import webtest


class TestCase(testbed_dependent_test.TestbedDependentTest):
  """A base class for API test classes."""

  def setUp(self, api_class):  # pyrefly: ignore[bad-override]
    super(TestCase, self).setUp()
    self.api_server = endpoints.api_server([api_class])
    self.app = webtest.TestApp(self.api_server)
