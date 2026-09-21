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

"""Unit tests for ComposeDirectoryManager."""

from importlib import resources
import os
from unittest import mock

from absl.testing import absltest
from multitest_transport.cli import compose_directory


# Every file bundled under multitest_transport/cli/compose/, listed explicitly
# so that adding a compose file without also extending the setup.py
# package_data globs fails here instead of in a release.
_BUNDLED_COMPOSE_FILES = (
    "docker-compose.distrib.yml",
    "docker-compose.gce.yml",
    os.path.join("infra", "dcon.yml"),
    os.path.join("infra", "esp.yml"),
    os.path.join("infra", "network.yml"),
    os.path.join("infra", "otel.yml"),
)


class ComposeDirectoryManagerTest(absltest.TestCase):

  def setUp(self):
    super().setUp()
    self.test_dir = self.create_tempdir().full_path
    self.compose_mgr = compose_directory.ComposeDirectoryManager(self.test_dir)

  def testGetComposeFilePath(self):
    self.assertEqual(self.compose_mgr.base_dir, self.test_dir)
    self.assertEqual(
        self.compose_mgr.compose_dir, os.path.join(self.test_dir, "compose")
    )
    self.assertEqual(
        self.compose_mgr.GetComposeFilePath("docker-compose.distrib.yml"),
        os.path.join(self.test_dir, "compose", "docker-compose.distrib.yml"),
    )

  def testHasComposeFiles(self):
    self.assertFalse(self.compose_mgr.has_compose_files)

    os.makedirs(self.compose_mgr.compose_dir, exist_ok=True)
    self.assertFalse(self.compose_mgr.has_compose_files)

    with open(
        os.path.join(self.compose_mgr.compose_dir, "test.yml"),
        "w",
        encoding="utf-8",
    ) as f:
      f.write("services: {}")

    self.assertTrue(self.compose_mgr.has_compose_files)

  @mock.patch.object(resources, "files")
  def testExtractComposeFiles_missingResource(self, mock_files):
    mock_files.side_effect = ModuleNotFoundError("No module found")
    # Should not raise exception
    self.compose_mgr.ExtractComposeFiles()
    self.assertTrue(os.path.exists(self.compose_mgr.compose_dir))


class BundledComposeFileTest(absltest.TestCase):
  """Assertions over the real bundled compose definitions, not mocks.

  These extract through the same importlib.resources path that production
  uses, so a packaging change that hides compose/ from the resource API fails
  here rather than at runtime on a user's machine.
  """

  def setUp(self):
    super().setUp()
    self.compose_mgr = compose_directory.ComposeDirectoryManager(
        self.create_tempdir().full_path
    )
    self.compose_mgr.ExtractComposeFiles()

  def _ReadExtracted(self, *relative_parts: str) -> str:
    with open(
        self.compose_mgr.GetComposeFilePath(os.path.join(*relative_parts)),
        "r",
        encoding="utf-8",
    ) as f:
      return f.read()

  def testComposeResourcesAreLocatable(self):
    # ExtractComposeFiles only logs a warning when the resource lookup fails,
    # so assert the lookup separately to keep that failure distinguishable
    # from a compose file whose contents drifted.
    compose_resource = resources.files("multitest_transport.cli").joinpath(
        "compose"
    )
    self.assertTrue(compose_resource.is_dir())

  def testExtractComposeFiles_extractsEveryBundledFile(self):
    for relative_path in _BUNDLED_COMPOSE_FILES:
      self.assertTrue(
          os.path.exists(self.compose_mgr.GetComposeFilePath(relative_path)),
          f"{relative_path} was not extracted",
      )

  def testDconCompose_dialerDependsOnlyOnAcceptorTarget(self):
    dcon = self._ReadExtracted("infra", "dcon.yml")

    self.assertIn("--acceptor_target=${ACCEPTOR_TARGET}", dcon)
    # DCON_ACCEPTOR_ADDR is the controller-side Cloud Endpoints service name,
    # consumed only by ESP. No worker ever sets it, so a fallback to it here
    # could only ever yield the literal "wss://", turning a missing target
    # into a bad one instead of a failure.
    self.assertNotIn("DCON_ACCEPTOR_ADDR", dcon)

  def testEspCompose_usesAcceptorAddr(self):
    esp = self._ReadExtracted("infra", "esp.yml")

    self.assertIn("--service=${DCON_ACCEPTOR_ADDR:-}", esp)


if __name__ == "__main__":
  absltest.main()
