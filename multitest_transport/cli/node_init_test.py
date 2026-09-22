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

"""Unit tests for MTT Node non-interactive initialization."""

import grp
import os
import shutil
import stat
import tempfile
from absl.testing import absltest
from multitest_transport.cli import host_env
from multitest_transport.cli import node_init
from multitest_transport.cli import node_permissions
import yaml


class NodeInitTest(absltest.TestCase):

  def setUp(self):
    super().setUp()
    self.test_dir = tempfile.mkdtemp()
    self.static_dir = os.path.join(self.test_dir, "etc_mtt")
    self.base_dir = os.path.join(self.test_dir, "var_lib_mttnode")
    os.makedirs(self.static_dir, exist_ok=True)
    # A group the test process already belongs to: chown to any other group is
    # EPERM for a non-root process, and Forge shards are not root.
    self.mtt_group = grp.getgrgid(os.getgid()).gr_name

    # Dummy key file
    self.dummy_key_path = os.path.join(self.test_dir, "test-sa-key.json")
    with open(self.dummy_key_path, "w", encoding="utf-8") as f:
      f.write('{"client_email": "test@gserviceaccount.com"}')

    # Dummy lab config file
    self.dummy_lab_config_path = os.path.join(
        self.test_dir, "test_lab_config.yaml"
    )
    with open(self.dummy_lab_config_path, "w", encoding="utf-8") as f:
      f.write("host_config:\n  hostname: localhost\n")

  def tearDown(self):
    shutil.rmtree(self.test_dir, ignore_errors=True)
    super().tearDown()

  # =========================================================================
  # Controller Init Tests
  # =========================================================================

  def testInitController_minimal(self):
    node_init.InitController(
        static_dir=self.static_dir,
        base_dir=self.base_dir,
        mtt_group=self.mtt_group,
        host_environment=host_env.HostEnvironment.DEFAULT,
    )

    flags_file = os.path.join(self.static_dir, "config", "mtt_flags.yaml")
    self.assertTrue(os.path.exists(flags_file))
    with open(flags_file, "r", encoding="utf-8") as f:
      flags_data = yaml.safe_load(f)
    self.assertEqual(flags_data.get("image_name"), "gcr.io/android-mtt/mtt")
    self.assertEqual(flags_data.get("tag"), "latest")
    self.assertEqual(flags_data.get("flags"), [])

    env_file = os.path.join(self.static_dir, "config", "docker-compose.env")
    self.assertTrue(os.path.exists(env_file))

  def testInitController_full(self):
    node_init.InitController(
        static_dir=self.static_dir,
        base_dir=self.base_dir,
        mtt_group=self.mtt_group,
        image_name="my-custom-controller",
        tag="v2",
        dcon_acceptor_addr="acceptor.example.com",
        otel=True,
        service_account_json_key_path=self.dummy_key_path,
        unrecognized_flags=["--port=8080", "--verbose"],
        host_environment=host_env.HostEnvironment.GCE,
    )

    # Verify copied secrets key
    secret_key = os.path.join(self.static_dir, "secrets", "sa-key.json")
    self.assertTrue(os.path.exists(secret_key))
    self.assertEqual(
        stat.S_IMODE(os.stat(secret_key).st_mode),
        node_permissions.STATIC_FILE_MODE,
    )

    # Verify docker-compose.env
    env_file = os.path.join(self.static_dir, "config", "docker-compose.env")
    with open(env_file, "r", encoding="utf-8") as f:
      env_content = f.read()
    self.assertIn("DCON_ACCEPTOR_ADDR=acceptor.example.com", env_content)
    self.assertIn(
        "OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4317", env_content
    )
    self.assertIn("SA_KEY_FILE=/etc/secrets/sa-key.json", env_content)

    # Verify mtt_flags.yaml
    flags_file = os.path.join(self.static_dir, "config", "mtt_flags.yaml")
    with open(flags_file, "r", encoding="utf-8") as f:
      flags_data = yaml.safe_load(f)
    self.assertEqual(flags_data.get("image_name"), "my-custom-controller")
    self.assertEqual(flags_data.get("tag"), "v2")
    self.assertEqual(
        flags_data.get("flags"),
        [
            f"--service_account_json_key_path={secret_key}",
            "--port=8080",
            "--verbose",
        ],
    )

  def testInitController_missingKeyFileRaisesError(self):
    with self.assertRaises(FileNotFoundError):
      node_init.InitController(
          static_dir=self.static_dir,
          base_dir=self.base_dir,
          mtt_group=self.mtt_group,
          service_account_json_key_path="/nonexistent/path/sa.json",
          host_environment=host_env.HostEnvironment.DEFAULT,
      )

  def testInitController_gcpWithoutAcceptorAddrRaisesError(self):
    with self.assertRaisesRegex(ValueError, "--dcon_acceptor_addr is required"):
      node_init.InitController(
          static_dir=self.static_dir,
          base_dir=self.base_dir,
          mtt_group=self.mtt_group,
          host_environment=host_env.HostEnvironment.GCE,
      )

  def testInitController_nonGcpWithAcceptorAddrRaisesError(self):
    with self.assertRaisesRegex(ValueError, "not GCP"):
      node_init.InitController(
          static_dir=self.static_dir,
          base_dir=self.base_dir,
          mtt_group=self.mtt_group,
          dcon_acceptor_addr="acceptor.example.com",
          host_environment=host_env.HostEnvironment.LAB,
      )

  # =========================================================================
  # Worker Init Tests
  # =========================================================================

  def testInitWorker_minimalWithoutLabConfig(self):
    node_init.InitWorker(
        dcon_acceptor_target="wss://acceptor.example.com",
        static_dir=self.static_dir,
        base_dir=self.base_dir,
        mtt_group=self.mtt_group,
    )

    env_file = os.path.join(self.static_dir, "config", "docker-compose.env")
    self.assertTrue(os.path.exists(env_file))
    with open(env_file, "r", encoding="utf-8") as f:
      env_content = f.read()
    self.assertIn("ACCEPTOR_TARGET=wss://acceptor.example.com", env_content)
    self.assertNotIn("USE_SA_TOKEN", env_content)

    flags_file = os.path.join(self.static_dir, "config", "mtt_flags.yaml")
    self.assertTrue(os.path.exists(flags_file))

    lab_config_file = os.path.join(self.static_dir, "config", "lab_config.yaml")
    self.assertFalse(os.path.exists(lab_config_file))

  def testInitWorker_fullWithLabConfig(self):
    node_init.InitWorker(
        dcon_acceptor_target="wss://acceptor.example.com",
        static_dir=self.static_dir,
        base_dir=self.base_dir,
        mtt_group=self.mtt_group,
        image_name="mtt-worker-custom",
        tag="v1.2",
        otel=True,
        service_account_json_key_path=self.dummy_key_path,
        lab_config_path=self.dummy_lab_config_path,
        unrecognized_flags=["--max_concurrent_tests=4"],
    )

    # Verify lab_config.yaml
    lab_cfg = os.path.join(self.static_dir, "config", "lab_config.yaml")
    self.assertTrue(os.path.exists(lab_cfg))
    with open(lab_cfg, "r", encoding="utf-8") as f:
      self.assertIn("hostname: localhost", f.read())

    # Verify secrets key
    secret_key = os.path.join(self.static_dir, "secrets", "sa-key.json")
    self.assertTrue(os.path.exists(secret_key))

    # Verify docker-compose.env
    env_file = os.path.join(self.static_dir, "config", "docker-compose.env")
    with open(env_file, "r", encoding="utf-8") as f:
      env_content = f.read()
    self.assertIn("ACCEPTOR_TARGET=wss://acceptor.example.com", env_content)
    self.assertIn("USE_SA_TOKEN=true", env_content)
    self.assertIn("SA_KEY_FILE=/etc/secrets/sa-key.json", env_content)
    self.assertIn(
        "OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4317", env_content
    )

    # Verify mtt_flags.yaml
    flags_file = os.path.join(self.static_dir, "config", "mtt_flags.yaml")
    with open(flags_file, "r", encoding="utf-8") as f:
      flags_data = yaml.safe_load(f)
    self.assertEqual(flags_data.get("image_name"), "mtt-worker-custom")
    self.assertEqual(flags_data.get("tag"), "v1.2")
    self.assertEqual(
        flags_data.get("flags"),
        [
            f"--service_account_json_key_path={secret_key}",
            "--max_concurrent_tests=4",
        ],
    )

  def testInitWorker_missingTargetRaisesError(self):
    with self.assertRaises(ValueError):
      node_init.InitWorker(
          dcon_acceptor_target="",
          static_dir=self.static_dir,
          base_dir=self.base_dir,
          mtt_group=self.mtt_group,
      )

  def testInitWorker_missingLabConfigRaisesError(self):
    with self.assertRaises(FileNotFoundError):
      node_init.InitWorker(
          dcon_acceptor_target="wss://acceptor.example.com",
          static_dir=self.static_dir,
          base_dir=self.base_dir,
          mtt_group=self.mtt_group,
          lab_config_path="/nonexistent/lab_config.yaml",
      )

  def testInitController_removesStaleLabConfig(self):
    config_dir = os.path.join(self.static_dir, "config")
    os.makedirs(config_dir, exist_ok=True)
    stale_lab_config = os.path.join(config_dir, "lab_config.yaml")
    with open(stale_lab_config, "w", encoding="utf-8") as f:
      f.write("lab_name: old\n")

    node_init.InitController(
        static_dir=self.static_dir,
        base_dir=self.base_dir,
        mtt_group=self.mtt_group,
        host_environment=host_env.HostEnvironment.LAB,
    )
    self.assertFalse(os.path.exists(stale_lab_config))

  def testInitWorker_withoutLabConfigRemovesStaleFile(self):
    config_dir = os.path.join(self.static_dir, "config")
    os.makedirs(config_dir, exist_ok=True)
    stale_lab_config = os.path.join(config_dir, "lab_config.yaml")
    with open(stale_lab_config, "w", encoding="utf-8") as f:
      f.write("lab_name: old\n")

    node_init.InitWorker(
        dcon_acceptor_target="wss://acceptor.example.com",
        static_dir=self.static_dir,
        base_dir=self.base_dir,
        mtt_group=self.mtt_group,
        lab_config_path=None,
    )
    self.assertFalse(os.path.exists(stale_lab_config))

  # =========================================================================
  # Permission model
  # =========================================================================

  def testInitWorker_appliesPermissionPolicy(self):
    node_init.InitWorker(
        dcon_acceptor_target="wss://acceptor.example.com",
        static_dir=self.static_dir,
        base_dir=self.base_dir,
        mtt_group=self.mtt_group,
        service_account_json_key_path=self.dummy_key_path,
    )
    self.assertEqual(
        stat.S_IMODE(os.stat(self.static_dir).st_mode),
        node_permissions.STATIC_DIR_MODE,
    )
    self.assertEqual(
        stat.S_IMODE(os.stat(os.path.join(self.static_dir, "secrets")).st_mode),
        node_permissions.STATIC_DIR_MODE,
    )
    self.assertEqual(
        stat.S_IMODE(os.stat(self.base_dir).st_mode),
        node_permissions.BASE_DIR_MODE,
    )
    self.assertEqual(os.stat(self.static_dir).st_gid, os.getgid())

  def testInitWorker_producesDriftFreeTrees(self):
    node_init.InitWorker(
        dcon_acceptor_target="wss://acceptor.example.com",
        static_dir=self.static_dir,
        base_dir=self.base_dir,
        mtt_group=self.mtt_group,
        service_account_json_key_path=self.dummy_key_path,
    )
    # The tree init produces must pass init's own drift check, which is what
    # the removed hardcoded 0700/0600 chmods used to break.
    self.assertEmpty(
        node_permissions.DetectDrift(self.static_dir, self.base_dir)
    )

  def testInitController_producesDriftFreeTrees(self):
    node_init.InitController(
        static_dir=self.static_dir,
        base_dir=self.base_dir,
        mtt_group=self.mtt_group,
        service_account_json_key_path=self.dummy_key_path,
        host_environment=host_env.HostEnvironment.LAB,
    )
    self.assertEmpty(
        node_permissions.DetectDrift(self.static_dir, self.base_dir)
    )

  def testInitWorker_missingGroupFailsBeforeWriting(self):
    with self.assertRaises(node_permissions.PermissionPolicyError):
      node_init.InitWorker(
          dcon_acceptor_target="wss://acceptor.example.com",
          static_dir=self.static_dir,
          base_dir=self.base_dir,
          mtt_group="no_such_mtt_group",
      )
    self.assertFalse(os.path.exists(os.path.join(self.static_dir, "config")))


if __name__ == "__main__":
  absltest.main()
