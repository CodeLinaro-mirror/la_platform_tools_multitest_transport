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

"""Unit tests for ReleaseDirectoryManager."""

import os
import shutil
import stat
import tempfile
from absl.testing import absltest
from multitest_transport.cli import node_permissions
from multitest_transport.cli import release_directory
import yaml

ReleaseDirectoryManager = release_directory.ReleaseDirectoryManager
_SanitizeImageRef = release_directory._SanitizeImageRef


class ReleaseDirectoryTest(absltest.TestCase):

  def setUp(self):
    super().setUp()
    self.test_dir = tempfile.mkdtemp()
    self.manager = ReleaseDirectoryManager(self.test_dir)

  def tearDown(self):
    shutil.rmtree(self.test_dir, ignore_errors=True)
    super().tearDown()

  def _populate_config(
      self,
      image_name: str = "mtt-worker",
      tag: str = "v1",
      flags: tuple[str, ...] = ("--force_update",),
  ) -> None:
    with open(self.manager.config_lab_config_path, "w", encoding="utf-8") as f:
      f.write("""host_config:
  hostname: localhost
""")
    flags_data = {
        "image_name": image_name,
        "tag": tag,
        "flags": list(flags),
    }
    with open(self.manager.config_flags_path, "w", encoding="utf-8") as f:
      yaml.dump(flags_data, f)
    with open(self.manager.config_compose_env_path, "w", encoding="utf-8") as f:
      f.write("COMPOSE_PROJECT_NAME=mtt-infra\n")

  def testSanitizeDigest(self):
    image_ref = "asia-docker.pkg.dev/ats-dev-418504/ats/ats@sha256:7f9a2b3c4d"
    sanitized = _SanitizeImageRef(image_ref)
    self.assertEqual(
        sanitized,
        "asia-docker.pkg.dev_ats-dev-418504_ats_ats_sha256_7f9a2b3c4d",
    )
    self.assertEqual(_SanitizeImageRef("v1.0.0"), "v1.0.0")

  def testStageTunnelEnv(self):
    self._populate_config()
    env_path = self.manager.StageTunnelEnv()

    self.assertEqual(env_path, self.manager.tunnel_compose_env_path)
    self.assertTrue(os.path.exists(env_path))
    with open(env_path, "r", encoding="utf-8") as f:
      content = f.read()
    self.assertIn("COMPOSE_PROJECT_NAME=mtt-infra", content)

  def testStageTunnelEnv_missingRaisesError(self):
    with self.assertRaises(FileNotFoundError):
      self.manager.StageTunnelEnv()

  def testStageTunnelEnv_customSourceDir(self):
    custom_dir = os.path.join(self.test_dir, "custom_config")
    os.makedirs(custom_dir, exist_ok=True)
    custom_env = os.path.join(custom_dir, "docker-compose.env")
    with open(custom_env, "w", encoding="utf-8") as f:
      f.write("CUSTOM_ENV=1\n")

    env_path = self.manager.StageTunnelEnv(source_dir=custom_dir)

    self.assertEqual(env_path, self.manager.tunnel_compose_env_path)
    self.assertTrue(os.path.exists(env_path))
    with open(env_path, "r", encoding="utf-8") as f:
      content = f.read()
    self.assertIn("CUSTOM_ENV=1", content)

  def testStageTunnelEnv_setsBaseFileMode(self):
    self._populate_config()
    # Files arrive from static_dir at 0640. Copying the mode bits across would
    # be permanent drift against the 0660 base_dir policy.
    os.chmod(self.manager.config_compose_env_path, 0o640)

    env_path = self.manager.StageTunnelEnv()

    self.assertEqual(
        stat.S_IMODE(os.stat(env_path).st_mode),
        node_permissions.BASE_FILE_MODE,
    )

  def testStageTunnelEnv_repairsExistingDestinationMode(self):
    self._populate_config()
    env_path = self.manager.StageTunnelEnv()
    os.chmod(env_path, 0o600)

    self.manager.StageTunnelEnv()

    # shutil.copyfile would have left the destination at 0600.
    self.assertEqual(
        stat.S_IMODE(os.stat(env_path).st_mode),
        node_permissions.BASE_FILE_MODE,
    )

  def testStageRelease_setsBaseFileModeOnLabConfig(self):
    self._populate_config()
    os.chmod(self.manager.config_lab_config_path, 0o640)

    release_dir = self.manager.StageRelease(
        "gcr.io/proj/mtt-worker@sha256:abc12345"
    )

    self.assertEqual(
        stat.S_IMODE(
            os.stat(os.path.join(release_dir, "lab_config.yaml")).st_mode
        ),
        node_permissions.BASE_FILE_MODE,
    )

  def testStageRelease(self):
    self._populate_config(
        image_name="mtt-worker",
        tag="latest",
        flags=("--force_update", "--enable_cache"),
    )
    release_dir = self.manager.StageRelease(
        "gcr.io/proj/mtt-worker@sha256:abc12345"
    )

    self.assertTrue(os.path.isdir(release_dir))
    self.assertTrue(
        os.path.exists(os.path.join(release_dir, "lab_config.yaml"))
    )
    flags_file = os.path.join(release_dir, "pinned_mtt_flags.yaml")
    self.assertTrue(os.path.exists(flags_file))

    with open(flags_file, "r", encoding="utf-8") as f:
      flags_data = yaml.safe_load(f)
    self.assertEqual(
        flags_data.get("image_ref"), "gcr.io/proj/mtt-worker@sha256:abc12345"
    )
    # The mutable identity is intentionally not carried into the pin.
    self.assertNotIn("image_name", flags_data)
    self.assertNotIn("tag", flags_data)
    self.assertEqual(
        flags_data.get("flags"), ["--force_update", "--enable_cache"]
    )

    self.assertTrue(self.manager.has_staging_release)
    self.assertFalse(self.manager.has_active_release)
    self.assertEqual(self.manager._staging_release_dir, release_dir)

    staging_config = self.manager.staging_config_path
    self.assertTrue(os.path.exists(staging_config))
    staging_flags = self.manager.staging_flags_path
    self.assertTrue(os.path.exists(staging_flags))

  def testStageRelease_customSourceDir(self):
    custom_dir = os.path.join(self.test_dir, "custom_config")
    os.makedirs(custom_dir, exist_ok=True)
    with open(
        os.path.join(custom_dir, "lab_config.yaml"), "w", encoding="utf-8"
    ) as f:
      f.write("""host_config:
  hostname: custom-host
""")
    with open(
        os.path.join(custom_dir, "mtt_flags.yaml"), "w", encoding="utf-8"
    ) as f:
      yaml.dump({"image_name": "custom-img", "flags": ["--custom_flag"]}, f)

    release_dir = self.manager.StageRelease(
        "custom-img@sha256:custom_digest", source_dir=custom_dir
    )

    self.assertTrue(os.path.isdir(release_dir))
    self.assertTrue(self.manager.has_staging_release)
    self.assertTrue(os.path.exists(self.manager.staging_config_path))
    self.assertTrue(os.path.exists(self.manager.staging_flags_path))

    with open(self.manager.staging_flags_path, "r", encoding="utf-8") as f:
      flags_data = yaml.safe_load(f)
    self.assertEqual(
        flags_data.get("image_ref"), "custom-img@sha256:custom_digest"
    )
    self.assertEqual(flags_data.get("flags"), ["--custom_flag"])

  def testStageRelease_withoutLabConfig(self):
    custom_dir = os.path.join(self.test_dir, "no_lab_config")
    os.makedirs(custom_dir, exist_ok=True)
    with open(
        os.path.join(custom_dir, "mtt_flags.yaml"), "w", encoding="utf-8"
    ) as f:
      yaml.dump({"image_name": "mtt-worker", "flags": []}, f)

    release_dir = self.manager.StageRelease(
        "sha256:no_lab", source_dir=custom_dir
    )

    self.assertTrue(os.path.isdir(release_dir))
    self.assertFalse(
        os.path.exists(os.path.join(release_dir, "lab_config.yaml"))
    )
    self.assertTrue(
        os.path.exists(os.path.join(release_dir, "pinned_mtt_flags.yaml"))
    )

  def testPromoteStagingToActive(self):
    self._populate_config(image_name="mtt-worker")
    release_dir = self.manager.StageRelease("mtt-worker@sha256:v1")

    self.manager.PromoteStagingToActive()

    self.assertTrue(self.manager.has_active_release)
    self.assertFalse(self.manager.has_staging_release)
    self.assertEqual(self.manager._active_release_dir, release_dir)
    self.assertTrue(os.path.exists(self.manager.active_config_path))
    self.assertTrue(os.path.exists(self.manager.active_flags_path))

  def testPromoteStagingToActive_prunesOldRelease(self):
    self._populate_config(image_name="mtt-worker")
    release_dir1 = self.manager.StageRelease("mtt-worker@sha256:v1")
    self.manager.PromoteStagingToActive()

    release_dir2 = self.manager.StageRelease("sha256:v2")

    self.assertEqual(self.manager._active_release_dir, release_dir1)
    self.assertEqual(self.manager._staging_release_dir, release_dir2)

    self.manager.PromoteStagingToActive()

    self.assertEqual(self.manager._active_release_dir, release_dir2)
    self.assertFalse(self.manager.has_staging_release)
    self.assertFalse(os.path.exists(release_dir1))
    self.assertTrue(os.path.exists(release_dir2))

  def testDiscardStaging_preservesActive(self):
    self._populate_config(image_name="mtt-worker")
    release_dir1 = self.manager.StageRelease("mtt-worker@sha256:v1")
    self.manager.PromoteStagingToActive()

    release_dir2 = self.manager.StageRelease("sha256:v2")

    self.manager.DiscardStaging()

    self.assertFalse(self.manager.has_staging_release)
    self.assertTrue(self.manager.has_active_release)
    self.assertEqual(self.manager._active_release_dir, release_dir1)
    self.assertTrue(os.path.exists(release_dir1))
    self.assertFalse(os.path.exists(release_dir2))

  def testPromoteStagingToActive_withoutStagingRaisesError(self):
    with self.assertRaises(ValueError):
      self.manager.PromoteStagingToActive()

  def testStageRelease_missingConfigRaisesError(self):
    with self.assertRaises(FileNotFoundError):
      self.manager.StageRelease("sha256:missing")

  def testPruneReleases_removesUnreferenced(self):
    self._populate_config(image_name="mtt-worker")
    rel1 = self.manager.StageRelease("mtt-worker@sha256:v1")
    self.manager.PromoteStagingToActive()
    releases_dir = os.path.join(self.test_dir, "core", "releases")
    rel2 = os.path.join(releases_dir, "sha256_v2_manual")
    os.makedirs(rel2, exist_ok=True)

    pruned = self.manager._PruneReleases()

    self.assertIn("sha256_v2_manual", pruned)
    self.assertTrue(os.path.exists(rel1))
    self.assertFalse(os.path.exists(rel2))


if __name__ == "__main__":
  absltest.main()
