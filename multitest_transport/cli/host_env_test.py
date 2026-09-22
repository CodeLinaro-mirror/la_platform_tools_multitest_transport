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

"""Unit tests for MTT Node host environment detection."""

from unittest import mock
from absl.testing import absltest
from multitest_transport.cli import host_env


class IsGceInstanceTest(absltest.TestCase):

  def testIsGceInstance(self):
    temp_file = self.create_tempfile(content="Google Compute Engine\n")
    self.assertTrue(
        host_env.IsGceInstance(product_name_path=temp_file.full_path)
    )

  def testIsGceInstance_differentContent(self):
    temp_file = self.create_tempfile(content="Dell Inc.\n")
    self.assertFalse(
        host_env.IsGceInstance(product_name_path=temp_file.full_path)
    )

  def testIsGceInstance_nonexistentFile(self):
    self.assertFalse(
        host_env.IsGceInstance(
            product_name_path="/nonexistent/path/product_name"
        )
    )


class HostEnvironmentTest(absltest.TestCase):

  def testIsGcp_gce(self):
    self.assertTrue(host_env.HostEnvironment.GCE.IsGcp())

  def testIsGcp_lab(self):
    self.assertFalse(host_env.HostEnvironment.LAB.IsGcp())

  def testIsGcp_default(self):
    self.assertFalse(host_env.HostEnvironment.DEFAULT.IsGcp())


class DetectTest(absltest.TestCase):

  @mock.patch.object(host_env, "IsGceInstance")
  def testDetect_gce(self, mock_is_gce):
    mock_is_gce.return_value = True

    self.assertEqual(host_env.Detect(), host_env.HostEnvironment.GCE)

  @mock.patch.object(host_env, "IsGceInstance")
  def testDetect_unknownHostFallsBackToDefault(self, mock_is_gce):
    mock_is_gce.return_value = False

    self.assertEqual(host_env.Detect(), host_env.HostEnvironment.DEFAULT)


if __name__ == "__main__":
  absltest.main()
