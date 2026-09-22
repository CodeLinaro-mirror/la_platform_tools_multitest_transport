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

"""Unit tests for multitest_transport.cli.node_config declarative configuration layer."""

import os
import shutil
import tempfile
from unittest import mock
from absl.testing import absltest
from multitest_transport.cli import gcp_param_manager
from multitest_transport.cli import node_config
from tradefed_cluster.configs import lab_config
import yaml


class NodeConfigTest(absltest.TestCase):

  def setUp(self):
    super().setUp()
    self.test_dir = tempfile.mkdtemp()
    # Materialization probes Docker for the cache volume. Stub it out so no
    # test shells out to a daemon; the cache tests override the return value.
    self.mock_has_cache = mock.patch.object(
        node_config, "_HasCacheVolume", return_value=False
    ).start()
    self.addCleanup(mock.patch.stopall)

  def tearDown(self):
    shutil.rmtree(self.test_dir)
    super().tearDown()

  def testResolveBoolArgs(self):
    flags = ["enable_cache", "verbose", "no-enable_cache", "debug"]
    resolved = node_config._ResolveBoolArgs(flags)
    self.assertEqual(resolved, ["verbose", "no-enable_cache", "debug"])

    flags2 = ["no-sandbox", "sandbox"]
    resolved2 = node_config._ResolveBoolArgs(flags2)
    self.assertEqual(resolved2, ["sandbox"])

  def testCoerceBool_strings(self):
    for truthy in ("true", "True", " TRUE ", "1", "yes", "y"):
      self.assertTrue(node_config._CoerceBool(truthy), msg=truthy)
    for falsy in ("false", "False", " FALSE ", "0", "no", "n", "off", "on", ""):
      self.assertFalse(node_config._CoerceBool(falsy), msg=falsy)

  def testCoerceBool_nonStrings(self):
    self.assertTrue(node_config._CoerceBool(True))
    self.assertTrue(node_config._CoerceBool(1))
    self.assertFalse(node_config._CoerceBool(False))
    self.assertFalse(node_config._CoerceBool(0))
    self.assertFalse(node_config._CoerceBool(None))

  def testApplyDictToMessage_stringBools(self):
    host_config_pb = node_config.lab_config_pb2.HostConfig()
    bool_field = next(
        (
            f.name
            for f in host_config_pb.DESCRIPTOR.fields
            if f.type == f.TYPE_BOOL
        ),
        None,
    )
    self.assertIsNotNone(bool_field)

    node_config._ApplyDictToMessage(host_config_pb, {bool_field: "false"})
    self.assertFalse(getattr(host_config_pb, bool_field))

    node_config._ApplyDictToMessage(host_config_pb, {bool_field: "true"})
    self.assertTrue(getattr(host_config_pb, bool_field))

  def testCopyMaterializedConfig_overwritesExistingFiles(self):
    static_config_dir = os.path.join(self.test_dir, "static_config")
    var_config_dir = os.path.join(self.test_dir, "var_config")
    os.makedirs(static_config_dir)
    os.makedirs(var_config_dir)

    flags_name = "mtt_flags.yaml"
    with open(
        os.path.join(static_config_dir, flags_name), "w", encoding="utf-8"
    ) as f:
      f.write("image_name: new-image\n")
    stale_dst = os.path.join(var_config_dir, flags_name)
    with open(stale_dst, "w", encoding="utf-8") as f:
      f.write("image_name: stale-image\n")
    # Read-only destination must still be replaced.
    os.chmod(stale_dst, 0o400)

    node_config._CopyMaterializedConfig(static_config_dir, var_config_dir)

    with open(stale_dst, "r", encoding="utf-8") as f:
      self.assertEqual(f.read(), "image_name: new-image\n")

  def testConfigDto_toDictAndFromDict(self):
    dto = node_config.ConfigDTO(
        docker_compose_env={"FOO": "bar"},
        mtt_docker_env={"GCP_PROJECT": "my-project"},
        lab_server_opts={"dcon_dialer_address": "dialer:50051"},
        olc_server_opts={"enable_xds": True},
        lab_config_args={"lab_name": "sat_lab_1"},
        lab_config_bool_args=["enable_stackdriver"],
        cluster_config_args={"cluster_name": "sat_cluster_1"},
        cluster_config_bool_args=["graceful_shutdown"],
        host_config_args={"hostname": "host1", "max_local_virtual_devices": 4},
        host_config_bool_args=["enable_autoupdate"],
        host_config_mount_local_path=["/tmp/host:/tmp/container"],
        mtt_args={"custom_flag": "val"},
        mtt_bool_args=["custom_bool"],
        image_name="asia-docker.pkg.dev/my-proj/mtt",
        tag="latest",
    )
    d = dto.ToDict()
    restored = node_config.ConfigDTO.FromDict(d)
    self.assertEqual(restored.docker_compose_env, {"FOO": "bar"})
    self.assertEqual(restored.mtt_docker_env, {"GCP_PROJECT": "my-project"})
    self.assertEqual(
        restored.lab_server_opts, {"dcon_dialer_address": "dialer:50051"}
    )
    self.assertEqual(restored.olc_server_opts, {"enable_xds": True})
    self.assertEqual(restored.lab_config_args, {"lab_name": "sat_lab_1"})
    self.assertEqual(restored.lab_config_bool_args, ["enable_stackdriver"])
    self.assertEqual(
        restored.cluster_config_args, {"cluster_name": "sat_cluster_1"}
    )
    self.assertEqual(restored.cluster_config_bool_args, ["graceful_shutdown"])
    self.assertEqual(
        restored.host_config_args,
        {"hostname": "host1", "max_local_virtual_devices": 4},
    )
    self.assertEqual(restored.host_config_bool_args, ["enable_autoupdate"])
    self.assertEqual(
        restored.host_config_mount_local_path, ["/tmp/host:/tmp/container"]
    )
    self.assertEqual(restored.mtt_args, {"custom_flag": "val"})
    self.assertEqual(restored.mtt_bool_args, ["custom_bool"])
    self.assertEqual(restored.image_name, "asia-docker.pkg.dev/my-proj/mtt")
    self.assertEqual(restored.tag, "latest")

  def testConfigDto_tagInMttArgsRaisesError(self):
    with self.assertRaises(node_config.ConfigValidationError) as ctx:
      node_config.ConfigDTO(mtt_args={"tag": "sneaky"})
    self.assertIn("tag", str(ctx.exception))

  def testConfigDto_imageNameInMttArgsRaisesError(self):
    with self.assertRaises(node_config.ConfigValidationError) as ctx:
      node_config.ConfigDTO(mtt_args={"image_name": "evil/img"})
    self.assertIn("image_name", str(ctx.exception))

  def testToMttFlags(self):
    dto = node_config.ConfigDTO(
        mtt_args={
            "port": 8000,
            "timeout": 0,
            "log_dir": "/tmp/logs",
            "empty_opt": "",
            "none_opt": None,
        },
        mtt_bool_args=["sandbox", "enable_cache", "no-enable_cache"],
    )
    flags = dto.ToMttFlags()
    self.assertIn("--port=8000", flags)
    self.assertIn("--timeout=0", flags)
    self.assertIn("--log_dir=/tmp/logs", flags)
    self.assertIn("--empty_opt=", flags)
    self.assertIn("--none_opt=", flags)
    self.assertIn("--sandbox", flags)
    self.assertIn("--no-enable_cache", flags)
    self.assertNotIn("--enable_cache", flags)

  def testToLabConfigProto(self):
    dto = node_config.ConfigDTO(
        mtt_docker_env={"CUSTOM_VAR": "val1"},
        lab_server_opts={
            "file_transfer_cloud_bucket": "ats_dev",
            "dcon_dialer_address": "dialer:50051",
        },
        olc_server_opts={"enable_xds": True},
        lab_config_args={
            "lab_name": "test_lab",
            "operation_mode": "STANDALONE",
        },
        lab_config_bool_args=["enable_stackdriver"],
        cluster_config_args={"cluster_name": "test_cluster"},
        cluster_config_bool_args=["use_host_network"],
        host_config_args={
            "hostname": "test_host",
            "max_local_virtual_devices": "2",
        },
        host_config_bool_args=["enable_autoupdate"],
        host_config_mount_local_path=["/data:/data"],
        image_name="mtt",
        tag="v1",
    )
    proto = dto.ToLabConfigProto()

    self.assertEqual(proto.lab_name, "test_lab")
    self.assertTrue(proto.enable_stackdriver)
    self.assertEqual(
        proto.operation_mode,
        lab_config.lab_config_pb2.OperationMode.STANDALONE,
    )
    self.assertFalse(proto.HasField("docker_image"))

    self.assertLen(proto.cluster_configs, 1)
    cluster = proto.cluster_configs[0]
    self.assertEqual(cluster.cluster_name, "test_cluster")
    self.assertTrue(cluster.use_host_network)

    self.assertLen(cluster.host_configs, 1)
    host = cluster.host_configs[0]
    self.assertEqual(host.hostname, "test_host")
    self.assertEqual(host.max_local_virtual_devices, 2)
    self.assertTrue(host.enable_autoupdate)
    self.assertEqual(list(host.mount_local_paths), ["/data:/data"])

    extra_args_str = " ".join(host.extra_docker_args)
    self.assertIn(
        '-e LAB_SERVER_OPTS="--file_transfer_cloud_bucket=ats_dev'
        ' --dcon_dialer_address=dialer:50051"',
        extra_args_str,
    )
    self.assertIn('-e OLC_SERVER_OPTS="--enable_xds=true"', extra_args_str)
    self.assertIn('-e CUSTOM_VAR="val1"', extra_args_str)

  def testConvertJavaOptsDictToOptsList(self):
    opts = {
        "enable_xds": True,
        "disable_feature": False,
        "dcon_dialer_address": "dialer:50051",
        "timeout_ms": 5000,
    }
    opts_list = node_config._ConvertJavaOptsDictToOptsList(opts)
    self.assertEqual(
        opts_list,
        [
            "--enable_xds=true",
            "--disable_feature=false",
            "--dcon_dialer_address=dialer:50051",
            "--timeout_ms=5000",
        ],
    )
    formatted_str = node_config._FormatJavaServerOpts(opts)
    self.assertEqual(
        formatted_str,
        "--enable_xds=true --disable_feature=false"
        " --dcon_dialer_address=dialer:50051 --timeout_ms=5000",
    )

  def testMaterializeLabConfig(self):
    dto = node_config.ConfigDTO(
        mtt_docker_env={"TEST_KEY": "test_val"},
        lab_server_opts={"dcon_dialer_address": "dialer:50051"},
        lab_config_args={
            "lab_name": "lab_alpha",
            "operation_mode": "ON_PREMISE",
        },
        cluster_config_args={"cluster_name": "cluster_alpha"},
        host_config_args={"hostname": "host_alpha"},
        host_config_mount_local_path=["/tmp:/tmp"],
    )
    manager = node_config._NodeConfigManager()
    lab_config_file = os.path.join(self.test_dir, "lab_config.yaml")

    manager.MaterializeLabConfig(dto, lab_config_file)
    self.assertTrue(os.path.exists(lab_config_file))

    with open(lab_config_file, "r") as f:
      parsed_proto = lab_config.Parse(f)

    self.assertEqual(parsed_proto.lab_name, "lab_alpha")
    self.assertEqual(
        parsed_proto.operation_mode,
        lab_config.lab_config_pb2.OperationMode.ON_PREMISE,
    )
    self.assertEqual(
        parsed_proto.cluster_configs[0].cluster_name, "cluster_alpha"
    )
    self.assertEqual(
        parsed_proto.cluster_configs[0].host_configs[0].hostname, "host_alpha"
    )

  def testMaterializeMttFlags(self):
    dto = node_config.ConfigDTO(
        image_name="asia-docker.pkg.dev/ats-dev-418504/ats/ats",
        tag="latest",
        mtt_args={"port": 8000, "role": "worker"},
        mtt_bool_args=["sandbox"],
    )
    self.assertEqual(
        dto.pull_image_ref,
        "asia-docker.pkg.dev/ats-dev-418504/ats/ats:latest",
    )
    manager = node_config._NodeConfigManager()
    flags_file = os.path.join(self.test_dir, "mtt_flags.yaml")

    manager.MaterializeMttFlags(dto, flags_file)
    self.assertTrue(os.path.exists(flags_file))

    with open(flags_file, "r", encoding="utf-8") as f:
      flags_data = yaml.safe_load(f)

    self.assertEqual(
        flags_data.get("image_name"),
        "asia-docker.pkg.dev/ats-dev-418504/ats/ats",
    )
    self.assertEqual(flags_data.get("tag"), "latest")
    flags_list = flags_data.get("flags", [])
    self.assertIn("--port=8000", flags_list)
    self.assertIn("--role=worker", flags_list)
    self.assertIn("--sandbox", flags_list)

  def testMergeScopes_hierarchy(self):
    tenant_yaml = """
docker_compose_env:
  TENANT_VAR: "tenant_val"
  OVERRIDE_VAR: "tenant_override"
lab_config_args:
  lab_name: "tenant_lab"
lab_server_opts:
  opt_a: "tenant_a"
  opt_b: "tenant_b"
host_config_mount_local_path:
  - "/path/tenant"
host_config_bool_args:
  - "enable_ui_update"
"""
    pool_yaml = """
docker_compose_env:
  POOL_VAR: "pool_val"
  OVERRIDE_VAR: "pool_override"
cluster_config_args:
  cluster_name: "pool_cluster"
lab_server_opts:
  opt_b: "pool_b"
  opt_c: "pool_c"
host_config_mount_local_path:
  - "/path/pool"
"""
    node_yaml = """
docker_compose_env:
  OVERRIDE_VAR: "node_override"
mtt_docker_env:
  NODE_DOCKER: "node_val"
host_config_args:
  hostname: "node_1"
lab_server_opts:
  opt_c: "node_c"
host_config_mount_local_path: !reset
  - "/path/node_exclusive"
host_config_bool_args:
  - "no-enable_ui_update"
  - "enable_autoupdate"
mtt_args:
  extra_key: "extra_val"
"""
    configs = {
        "tenant": yaml.safe_load(tenant_yaml),
        "pool": yaml.safe_load(pool_yaml),
        "node": yaml.safe_load(node_yaml),
    }

    manager = node_config._NodeConfigManager()
    dto = manager.MergeScopes(configs)

    self.assertEqual(
        dto.docker_compose_env,
        {
            "TENANT_VAR": "tenant_val",
            "POOL_VAR": "pool_val",
            "OVERRIDE_VAR": "node_override",
        },
    )
    self.assertEqual(dto.mtt_docker_env, {"NODE_DOCKER": "node_val"})
    self.assertEqual(dto.lab_config_args, {"lab_name": "tenant_lab"})
    self.assertEqual(dto.cluster_config_args, {"cluster_name": "pool_cluster"})
    self.assertEqual(dto.host_config_args, {"hostname": "node_1"})
    self.assertEqual(
        dto.lab_server_opts,
        {
            "opt_a": "tenant_a",
            "opt_b": "pool_b",
            "opt_c": "node_c",
        },
    )
    self.assertEqual(dto.host_config_mount_local_path, ["/path/node_exclusive"])
    self.assertEqual(
        dto.host_config_bool_args, ["no-enable_ui_update", "enable_autoupdate"]
    )
    self.assertEqual(dto.mtt_args, {"extra_key": "extra_val"})

  @mock.patch.object(
      gcp_param_manager.GcpParamManagerClient, "FromServiceAccountKeyFile"
  )
  def testResolveFromManifest(self, mock_from_key):
    tenant_yaml = """
docker_compose_env:
  PROJECT_ID: "proj-123"
lab_config_args:
  lab_name: "prod_lab"
lab_server_opts:
  file_transfer_cloud_bucket: "tenant_bucket"
"""
    node_yaml = """
mtt_docker_env:
  CONTAINER_ROLE: "worker"
host_config_args:
  hostname: "prod_node"
lab_server_opts:
  dcon_dialer_address: "dialer:50051"
"""

    key_path = os.path.join(self.test_dir, "key.json")
    with open(key_path, "w", encoding="utf-8") as f:
      f.write('{"type": "service_account"}')

    manifest_file = os.path.join(self.test_dir, "manifest.yaml")
    with open(manifest_file, "w", encoding="utf-8") as f:
      f.write(f"""
service_account_key_path: {key_path}
{{% set tenant = param_manager('projects/1/locations/global/parameters/tenant-cfg/versions/latest', 'tenant') %}}
{{% set node = param_manager('projects/1/locations/global/parameters/node-cfg/versions/latest', 'node') %}}
""")

    mock_client = mock.create_autospec(
        gcp_param_manager.GcpParamManagerClient, instance=True, spec_set=True
    )

    def FetchSideEffect(path):
      if "tenant-cfg" in path:
        return tenant_yaml
      if "node-cfg" in path:
        return node_yaml
      return ""

    mock_client.FetchUnformatted.side_effect = FetchSideEffect
    mock_from_key.return_value = mock_client

    var_config_dir = os.path.join(self.test_dir, "var_config")
    node_config.MaterializeNodeConfig(
        static_dir=self.test_dir,
        var_config_dir=var_config_dir,
    )

    # Verify materialized files on disk
    self.assertTrue(
        os.path.exists(os.path.join(var_config_dir, "lab_config.yaml"))
    )
    self.assertTrue(
        os.path.exists(os.path.join(var_config_dir, "docker-compose.env"))
    )
    self.assertTrue(
        os.path.exists(os.path.join(var_config_dir, "mtt_flags.yaml"))
    )

  @mock.patch.object(
      gcp_param_manager.GcpParamManagerClient, "FromServiceAccountKeyFile"
  )
  def testParamManager(self, mock_from_key):
    mock_client = mock.create_autospec(
        gcp_param_manager.GcpParamManagerClient, instance=True, spec_set=True
    )
    yaml_payload = """
docker_compose_env:
  GCP_PARAM_ENV: "from_cloud"
lab_server_opts:
  remote_opt: "cloud_val"
"""
    mock_client.FetchUnformatted.return_value = yaml_payload
    mock_from_key.return_value = mock_client

    key_path = os.path.join(self.test_dir, "key.json")
    with open(key_path, "w", encoding="utf-8") as f:
      f.write('{"type": "service_account"}')

    manifest_file = os.path.join(self.test_dir, "manifest_cloud.yaml")
    with open(manifest_file, "w", encoding="utf-8") as f:
      f.write(f"""
service_account_key_path: {key_path}
{{% set tenant = param_manager('projects/123/locations/global/parameters/tenant-cfg/versions/latest', 'tenant') %}}
""")

    manager = node_config._NodeConfigManager()
    dto = manager.ResolveFromManifest(manifest_file)

    mock_client.FetchUnformatted.assert_called_once_with(
        "projects/123/locations/global/parameters/tenant-cfg/versions/latest"
    )
    self.assertEqual(dto.docker_compose_env.get("GCP_PARAM_ENV"), "from_cloud")
    self.assertEqual(dto.lab_server_opts, {"remote_opt": "cloud_val"})

  def testStoreNodeConfig(self):
    mock_client = mock.create_autospec(
        gcp_param_manager.GcpParamManagerClient, instance=True
    )
    mock_client.StoreUnformatted.return_value = (
        "projects/123/locations/global/parameters/node-cfg/versions/1"
    )

    dto = node_config.ConfigDTO(
        docker_compose_env={"PROJECT_ID": "p-1"},
        mtt_docker_env={"CONTAINER_ROLE": "worker"},
        lab_server_opts={"timeout": "30s"},
    )
    manager = node_config._NodeConfigManager()
    res = manager.StoreNodeConfig(
        "projects/123/locations/global/parameters/node-cfg/versions/latest",
        dto,
        client=mock_client,
    )

    self.assertEqual(
        res, "projects/123/locations/global/parameters/node-cfg/versions/1"
    )
    mock_client.StoreUnformatted.assert_called_once()
    call_args = mock_client.StoreUnformatted.call_args[0]
    self.assertEqual(
        call_args[0],
        "projects/123/locations/global/parameters/node-cfg/versions/latest",
    )
    stored_yaml = yaml.safe_load(call_args[1])
    self.assertEqual(stored_yaml["docker_compose_env"], {"PROJECT_ID": "p-1"})
    self.assertEqual(
        stored_yaml["mtt_docker_env"], {"CONTAINER_ROLE": "worker"}
    )

  def testPullImageRef(self):
    dto = node_config.ConfigDTO(
        image_name="asia-docker.pkg.dev/proj/img",
        tag="v1.0",
    )
    self.assertEqual(dto.pull_image_ref, "asia-docker.pkg.dev/proj/img:v1.0")

  def testPullImageRef_defaultsToLatestWhenTagMissing(self):
    dto = node_config.ConfigDTO(image_name="asia-docker.pkg.dev/proj/img")
    self.assertEqual(dto.pull_image_ref, "asia-docker.pkg.dev/proj/img:latest")

  def testFromDict_legacyImageFieldSplitsIntoNameAndTag(self):
    dto = node_config.ConfigDTO.FromDict(
        {"image": "asia-docker.pkg.dev/proj/img:v2"}
    )
    self.assertEqual(dto.image_name, "asia-docker.pkg.dev/proj/img")
    self.assertEqual(dto.tag, "v2")
    self.assertEqual(dto.pull_image_ref, "asia-docker.pkg.dev/proj/img:v2")

  def testFromManifest_missingKeyFileRaisesError(self):
    manifest_path = os.path.join(self.test_dir, "manifest.yaml")
    with open(manifest_path, "w", encoding="utf-8") as f:
      f.write(
          "service_account_key_path: /nonexistent/path/key.json\n"
          "tenant: {{ param_manager('projects/1/p/versions/1', 'tenant') }}\n"
      )

    manager = node_config._NodeConfigManager()
    with self.assertRaises(FileNotFoundError):
      manager.ResolveFromManifest(manifest_path)

  def testFromManifest_missingKeyFieldRaisesError(self):
    manifest_path = os.path.join(self.test_dir, "manifest.yaml")
    with open(manifest_path, "w", encoding="utf-8") as f:
      f.write(
          "tenant: {{ param_manager('projects/1/p/versions/1', 'tenant') }}\n"
      )

    manager = node_config._NodeConfigManager()
    with self.assertRaises(ValueError):
      manager.ResolveFromManifest(manifest_path)

  @mock.patch.object(
      gcp_param_manager.GcpParamManagerClient, "FromServiceAccountKeyFile"
  )
  def testFromManifest_validKeyFile(self, mock_from_key):
    key_path = os.path.join(self.test_dir, "key.json")
    with open(key_path, "w", encoding="utf-8") as f:
      f.write('{"type": "service_account"}')

    manifest_path = os.path.join(self.test_dir, "manifest.yaml")
    with open(manifest_path, "w", encoding="utf-8") as f:
      f.write(
          f"service_account_key_path: {key_path}\n"
          "tenant: {{ param_manager('projects/1/p/versions/1', 'tenant') }}\n"
      )

    mock_client = mock.create_autospec(
        gcp_param_manager.GcpParamManagerClient, instance=True
    )
    mock_client.FetchUnformatted.return_value = "image_name: ats\ntag: prod\n"
    mock_from_key.return_value = mock_client

    manager = node_config._NodeConfigManager()
    dto = manager.ResolveFromManifest(manifest_path)
    mock_from_key.assert_called_once_with(key_path)
    self.assertEqual(dto.image_name, "ats")
    self.assertEqual(dto.tag, "prod")

  @mock.patch.object(
      gcp_param_manager.GcpParamManagerClient, "FromServiceAccountKeyFile"
  )
  def testMaterializeNodeConfig_gcpPrecedenceOverStatic(
      self, mock_from_key
  ):
    # Set up GCP manifest.yaml
    manifest_path = os.path.join(self.test_dir, "manifest.yaml")
    with open(manifest_path, "w", encoding="utf-8") as f:
      f.write(
          "service_account_key_path: key.json\n"
          "tenant: {{ param_manager('projects/1/p/versions/1', 'tenant') }}\n"
      )
    key_path = os.path.join(self.test_dir, "key.json")
    with open(key_path, "w", encoding="utf-8") as f:
      f.write('{"type": "service_account"}')

    # Set up conflicting static config folder
    static_config_dir = os.path.join(self.test_dir, "config")
    os.makedirs(static_config_dir)
    with open(
        os.path.join(static_config_dir, "lab_config.yaml"),
        "w",
        encoding="utf-8",
    ) as f:
      f.write("lab_name: static_lab\n")
    with open(
        os.path.join(static_config_dir, "docker-compose.env"),
        "w",
        encoding="utf-8",
    ) as f:
      f.write("PROJECT_ID=static_proj\n")

    mock_client = mock.create_autospec(
        gcp_param_manager.GcpParamManagerClient, instance=True
    )
    mock_client.FetchUnformatted.return_value = (
        "lab_config_args:\n"
        "  lab_name: gcp_lab\n"
        "cluster_config_args:\n"
        "  cluster_name: gcp_cluster\n"
        "host_config_args:\n"
        "  hostname: gcp_host\n"
    )
    mock_from_key.return_value = mock_client

    var_config_dir = os.path.join(self.test_dir, "var_config")
    node_config.MaterializeNodeConfig(
        static_dir=self.test_dir,
        var_config_dir=var_config_dir,
    )

    # Verify GCP took precedence
    with open(
        os.path.join(var_config_dir, "lab_config.yaml"),
        "r",
        encoding="utf-8",
    ) as f:
      content = f.read()
      self.assertIn("gcp_lab", content)
      self.assertNotIn("static_lab", content)

    with open(
        os.path.join(var_config_dir, "mtt_flags.yaml"),
        "r",
        encoding="utf-8",
    ) as f:
      flags_data = yaml.safe_load(f)
      self.assertIn(
          f"--service_account_json_key_path={key_path}",
          flags_data["flags"],
      )

  def testMaterializeNodeConfig_static(self):
    static_config_dir = os.path.join(self.test_dir, "config")
    os.makedirs(static_config_dir)

    with open(
        os.path.join(static_config_dir, "lab_config.yaml"),
        "w",
        encoding="utf-8",
    ) as f:
      f.write("lab_name: static_lab\n")
    with open(
        os.path.join(static_config_dir, "docker-compose.env"),
        "w",
        encoding="utf-8",
    ) as f:
      f.write("KEY=VAL\n")
    with open(
        os.path.join(static_config_dir, "mtt_flags.yaml"),
        "w",
        encoding="utf-8",
    ) as f:
      f.write("image_name: static_img\n")

    var_config_dir = os.path.join(self.test_dir, "var_config")
    node_config.MaterializeNodeConfig(
        static_dir=self.test_dir, var_config_dir=var_config_dir
    )

    self.assertTrue(
        os.path.exists(os.path.join(var_config_dir, "lab_config.yaml"))
    )
    self.assertTrue(
        os.path.exists(os.path.join(var_config_dir, "docker-compose.env"))
    )
    self.assertTrue(
        os.path.exists(os.path.join(var_config_dir, "mtt_flags.yaml"))
    )

    with open(
        os.path.join(var_config_dir, "lab_config.yaml"),
        "r",
        encoding="utf-8",
    ) as f:
      self.assertEqual(f.read(), "lab_name: static_lab\n")

  def testMaterializeNodeConfig_staticController(self):
    static_config_dir = os.path.join(self.test_dir, "config")
    os.makedirs(static_config_dir)

    with open(
        os.path.join(static_config_dir, "docker-compose.env"),
        "w",
        encoding="utf-8",
    ) as f:
      f.write("KEY=VAL\n")
    with open(
        os.path.join(static_config_dir, "mtt_flags.yaml"),
        "w",
        encoding="utf-8",
    ) as f:
      f.write("image_name: controller_img\n")

    var_config_dir = os.path.join(self.test_dir, "var_config")
    node_config.MaterializeNodeConfig(
        static_dir=self.test_dir, var_config_dir=var_config_dir
    )

    self.assertFalse(
        os.path.exists(os.path.join(var_config_dir, "lab_config.yaml"))
    )
    self.assertTrue(
        os.path.exists(os.path.join(var_config_dir, "docker-compose.env"))
    )
    self.assertTrue(
        os.path.exists(os.path.join(var_config_dir, "mtt_flags.yaml"))
    )

  def testMaterializeNodeConfig_staticIncompleteRaisesError(self):
    static_config_dir = os.path.join(self.test_dir, "config")
    os.makedirs(static_config_dir)
    # Only create docker-compose.env, missing both lab_config.yaml and
    # mtt_flags.yaml.
    with open(
        os.path.join(static_config_dir, "docker-compose.env"),
        "w",
        encoding="utf-8",
    ) as f:
      f.write("KEY=VAL\n")

    var_config_dir = os.path.join(self.test_dir, "var_config")
    with self.assertRaises(FileNotFoundError):
      node_config.MaterializeNodeConfig(
          static_dir=self.test_dir, var_config_dir=var_config_dir
      )

  def testMaterializeNodeConfig_staticMissingMttFlagsRaisesError(self):
    static_config_dir = os.path.join(self.test_dir, "config")
    os.makedirs(static_config_dir)
    # lab_config.yaml alone is not enough: mtt_flags.yaml is always required.
    with open(
        os.path.join(static_config_dir, "lab_config.yaml"),
        "w",
        encoding="utf-8",
    ) as f:
      f.write("lab_name: static_lab\n")

    var_config_dir = os.path.join(self.test_dir, "var_config")
    with self.assertRaises(FileNotFoundError):
      node_config.MaterializeNodeConfig(
          static_dir=self.test_dir, var_config_dir=var_config_dir
      )

  def testMaterializeNodeConfig_neitherFoundRaisesError(self):
    var_config_dir = os.path.join(self.test_dir, "var_config")
    with self.assertRaises(FileNotFoundError):
      node_config.MaterializeNodeConfig(
          static_dir=self.test_dir, var_config_dir=var_config_dir
      )

  def _WriteStaticConfig(self, lab_config_yaml=None, mtt_flags_yaml=None):
    """Writes a minimal static config directory and returns var_config_dir."""
    static_config_dir = os.path.join(self.test_dir, "config")
    os.makedirs(static_config_dir, exist_ok=True)
    if lab_config_yaml is not None:
      with open(
          os.path.join(static_config_dir, "lab_config.yaml"),
          "w",
          encoding="utf-8",
      ) as f:
        f.write(lab_config_yaml)
    with open(
        os.path.join(static_config_dir, "mtt_flags.yaml"), "w", encoding="utf-8"
    ) as f:
      f.write(mtt_flags_yaml or "image_name: static_img\ntag: v1\n")
    return os.path.join(self.test_dir, "var_config")

  def testMaterializeNodeConfig_staticAutoupdateEnabledRaisesError(self):
    var_config_dir = self._WriteStaticConfig(
        lab_config_yaml=(
            "lab_name: static_lab\n"
            "cluster_configs:\n"
            "- cluster_name: static_cluster\n"
            "  host_configs:\n"
            "  - hostname: static_host\n"
            "    enable_autoupdate: true\n"
        )
    )
    with self.assertRaises(node_config.ConfigValidationError) as ctx:
      node_config.MaterializeNodeConfig(
          static_dir=self.test_dir, var_config_dir=var_config_dir
      )
    self.assertIn("enable_autoupdate", str(ctx.exception))
    self.assertIn("host level", str(ctx.exception))

  def testMaterializeNodeConfig_staticUiUpdateEnabledRaisesError(self):
    var_config_dir = self._WriteStaticConfig(
        lab_config_yaml="lab_name: static_lab\nenable_ui_update: true\n"
    )
    with self.assertRaises(node_config.ConfigValidationError) as ctx:
      node_config.MaterializeNodeConfig(
          static_dir=self.test_dir, var_config_dir=var_config_dir
      )
    self.assertIn("enable_ui_update", str(ctx.exception))
    self.assertIn("lab level", str(ctx.exception))

  def testMaterializeNodeConfig_staticAutoupdateDisabled(self):
    # An explicit opt-out is the desired state and must not be rejected.
    var_config_dir = self._WriteStaticConfig(
        lab_config_yaml=(
            "lab_name: static_lab\n"
            "enable_autoupdate: false\n"
            "enable_ui_update: false\n"
        )
    )
    node_config.MaterializeNodeConfig(
        static_dir=self.test_dir, var_config_dir=var_config_dir
    )
    self.assertTrue(
        os.path.exists(os.path.join(var_config_dir, "lab_config.yaml"))
    )

  def testMaterializeNodeConfig_staticForbiddenMttFlagRaisesError(self):
    var_config_dir = self._WriteStaticConfig(
        mtt_flags_yaml=(
            "image_name: static_img\n"
            "tag: v1\n"
            "flags:\n"
            "- --port=8000\n"
            "- --tag=other\n"
        )
    )
    with self.assertRaises(node_config.ConfigValidationError) as ctx:
      node_config.MaterializeNodeConfig(
          static_dir=self.test_dir, var_config_dir=var_config_dir
      )
    self.assertIn("--tag", str(ctx.exception))
    self.assertNotIn("--port", str(ctx.exception))

  def testMaterializeNodeConfig_staticAutoUpdateFlagRaisesError(self):
    var_config_dir = self._WriteStaticConfig(
        mtt_flags_yaml=(
            "image_name: static_img\nflags:\n- --enable_auto_update\n"
        )
    )
    with self.assertRaises(node_config.ConfigValidationError) as ctx:
      node_config.MaterializeNodeConfig(
          static_dir=self.test_dir, var_config_dir=var_config_dir
      )
    self.assertIn("--enable_auto_update", str(ctx.exception))

  def _WriteGcpManifest(self, mock_from_key, payload):
    """Wires a single-scope GCP manifest returning payload, returns var dir."""
    manifest_path = os.path.join(self.test_dir, "manifest.yaml")
    with open(manifest_path, "w", encoding="utf-8") as f:
      f.write(
          "service_account_key_path: key.json\n"
          "tenant: {{ param_manager('projects/1/p/versions/1', 'tenant') }}\n"
      )
    with open(
        os.path.join(self.test_dir, "key.json"), "w", encoding="utf-8"
    ) as f:
      f.write('{"type": "service_account"}')
    mock_client = mock.create_autospec(
        gcp_param_manager.GcpParamManagerClient, instance=True
    )
    mock_client.FetchUnformatted.return_value = payload
    mock_from_key.return_value = mock_client
    return os.path.join(self.test_dir, "var_config")

  @mock.patch.object(
      gcp_param_manager.GcpParamManagerClient, "FromServiceAccountKeyFile"
  )
  def testMaterializeNodeConfig_gcpAutoupdateEnabledRaisesError(
      self, mock_from_key
  ):
    var_config_dir = self._WriteGcpManifest(
        mock_from_key,
        "image_name: gcp_img\n"
        "tag: v1\n"
        "host_config_args:\n"
        "  hostname: gcp_host\n"
        "host_config_bool_args:\n"
        "- enable_autoupdate\n",
    )
    with self.assertRaises(node_config.ConfigValidationError) as ctx:
      node_config.MaterializeNodeConfig(
          static_dir=self.test_dir, var_config_dir=var_config_dir
      )
    self.assertIn("enable_autoupdate", str(ctx.exception))

  @mock.patch.object(
      gcp_param_manager.GcpParamManagerClient, "FromServiceAccountKeyFile"
  )
  def testMaterializeNodeConfig_gcpTagInMttArgsRaisesError(
      self, mock_from_key
  ):
    # image_name/tag are dedicated DTO fields; smuggling them through mtt_args
    # would emit --tag on the mtt command line and override the pinned digest.
    # ConfigDTO.__post_init__ rejects this while merging scopes, so nothing is
    # written to var_config_dir.
    var_config_dir = self._WriteGcpManifest(
        mock_from_key,
        "image_name: gcp_img\n"
        "tag: v1\n"
        "host_config_args:\n"
        "  hostname: gcp_host\n"
        "mtt_args:\n"
        "  tag: sneaky\n",
    )
    with self.assertRaises(node_config.ConfigValidationError) as ctx:
      node_config.MaterializeNodeConfig(
          static_dir=self.test_dir, var_config_dir=var_config_dir
      )
    self.assertIn("mtt_args", str(ctx.exception))
    self.assertFalse(
        os.path.exists(os.path.join(var_config_dir, "mtt_flags.yaml"))
    )

  @mock.patch.object(
      gcp_param_manager.GcpParamManagerClient, "FromServiceAccountKeyFile"
  )
  def testMaterializeNodeConfig_gcpWithoutHostConfig(self, mock_from_key):
    # An empty HostConfig submessage cannot be serialized by strictyaml, so an
    # otherwise valid lab-scope-only config must omit it rather than crash.
    var_config_dir = self._WriteGcpManifest(
        mock_from_key,
        "image_name: gcp_img\ntag: v1\nlab_config_args:\n  lab_name: gcp_lab\n",
    )
    node_config.MaterializeNodeConfig(
        static_dir=self.test_dir, var_config_dir=var_config_dir
    )
    with open(
        os.path.join(var_config_dir, "lab_config.yaml"), "r", encoding="utf-8"
    ) as f:
      written = yaml.safe_load(f.read())
    self.assertEqual(written.get("lab_name"), "gcp_lab")
    self.assertNotIn("cluster_configs", written)

  @mock.patch.object(
      gcp_param_manager.GcpParamManagerClient, "FromServiceAccountKeyFile"
  )
  def testMaterializeNodeConfig_gcpWithoutLabConfigSkipsFile(
      self, mock_from_key
  ):
    # Nothing maps onto lab_config.proto, so no lab_config.yaml is produced.
    var_config_dir = self._WriteGcpManifest(
        mock_from_key,
        "image_name: gcp_img\n"
        "tag: v1\n"
        "docker_compose_env:\n"
        "  PROJECT_ID: proj\n",
    )
    node_config.MaterializeNodeConfig(
        static_dir=self.test_dir, var_config_dir=var_config_dir
    )
    self.assertFalse(
        os.path.exists(os.path.join(var_config_dir, "lab_config.yaml"))
    )
    self.assertTrue(
        os.path.exists(os.path.join(var_config_dir, "mtt_flags.yaml"))
    )

  @mock.patch.object(
      gcp_param_manager.GcpParamManagerClient, "FromServiceAccountKeyFile"
  )
  def testMaterializeNodeConfig_gcpWithoutLabConfigRemovesStaleFile(
      self, mock_from_key
  ):
    var_config_dir = self._WriteGcpManifest(
        mock_from_key, "image_name: gcp_img\ntag: v1\n"
    )
    os.makedirs(var_config_dir, exist_ok=True)
    stale_path = os.path.join(var_config_dir, "lab_config.yaml")
    with open(stale_path, "w", encoding="utf-8") as f:
      f.write("lab_name: previously_resolved\n")

    node_config.MaterializeNodeConfig(
        static_dir=self.test_dir, var_config_dir=var_config_dir
    )
    self.assertFalse(os.path.exists(stale_path))

  def testMaterializeNodeConfig_staticWithoutLabConfigRemovesStaleFile(self):
    var_config_dir = self._WriteStaticConfig(lab_config_yaml=None)
    os.makedirs(var_config_dir, exist_ok=True)
    stale_path = os.path.join(var_config_dir, "lab_config.yaml")
    with open(stale_path, "w", encoding="utf-8") as f:
      f.write("lab_name: previously_static\n")

    node_config.MaterializeNodeConfig(
        static_dir=self.test_dir, var_config_dir=var_config_dir
    )
    self.assertFalse(os.path.exists(stale_path))

  # =========================================================================
  # Host-specific env injection
  # =========================================================================

  def _ReadEnv(self, var_config_dir: str) -> dict[str, str]:
    env = {}
    with open(
        os.path.join(var_config_dir, "docker-compose.env"),
        "r",
        encoding="utf-8",
    ) as f:
      for line in f.read().splitlines():
        if "=" in line:
          key, value = line.split("=", 1)
          env[key.strip()] = value.strip().strip('"')
    return env

  def _WriteStaticEnv(self, content: str) -> None:
    static_config_dir = os.path.join(self.test_dir, "config")
    os.makedirs(static_config_dir, exist_ok=True)
    with open(
        os.path.join(static_config_dir, "docker-compose.env"),
        "w",
        encoding="utf-8",
    ) as f:
      f.write(content)

  @mock.patch.object(node_config.socket, "gethostname", return_value="lab-host")
  @mock.patch.object(node_config.host_env, "IsGceInstance", return_value=False)
  def testMaterializeNodeConfig_staticInjectsHostSpecificEnv(
      self, unused_is_gce, unused_hostname
  ):
    var_config_dir = self._WriteStaticConfig()
    self._WriteStaticEnv("KEY=VAL\n")
    node_config.MaterializeNodeConfig(
        static_dir=self.test_dir, var_config_dir=var_config_dir
    )
    env = self._ReadEnv(var_config_dir)
    # Follows --static_dir rather than the compose file's /etc/mtt/secrets
    # default, which is the bug this injection exists to close.
    self.assertEqual(
        env["SECRETS_DIR"], os.path.join(self.test_dir, "secrets")
    )
    self.assertEqual(env["MTT_GID"], str(os.stat(self.test_dir).st_gid))
    self.assertEqual(env["OTEL_RESOURCE_ATTRIBUTES"], "host.name=lab-host")
    # The copied values survive the injection.
    self.assertEqual(env["KEY"], "VAL")

  @mock.patch.object(node_config.host_env, "IsGceInstance", return_value=True)
  def testMaterializeNodeConfig_gceDoesNotInjectOtelResourceAttributes(
      self, unused_is_gce
  ):
    var_config_dir = self._WriteStaticConfig()
    self._WriteStaticEnv("KEY=VAL\n")
    node_config.MaterializeNodeConfig(
        static_dir=self.test_dir, var_config_dir=var_config_dir
    )
    env = self._ReadEnv(var_config_dir)
    self.assertNotIn("OTEL_RESOURCE_ATTRIBUTES", env)

  def testMaterializeNodeConfig_injectionIsNotDuplicated(self):
    var_config_dir = self._WriteStaticConfig()
    self._WriteStaticEnv("KEY=VAL\n")
    node_config.MaterializeNodeConfig(
        static_dir=self.test_dir, var_config_dir=var_config_dir
    )
    node_config.MaterializeNodeConfig(
        static_dir=self.test_dir, var_config_dir=var_config_dir
    )
    with open(
        os.path.join(var_config_dir, "docker-compose.env"),
        "r",
        encoding="utf-8",
    ) as f:
      lines = f.read().splitlines()
    self.assertLen([l for l in lines if l.startswith("SECRETS_DIR=")], 1)

  @mock.patch.object(
      gcp_param_manager.GcpParamManagerClient, "FromServiceAccountKeyFile"
  )
  def testMaterializeNodeConfig_gcpInjectsHostSpecificEnv(self, mock_from_key):
    var_config_dir = self._WriteGcpManifest(
        mock_from_key,
        "image_name: gcp_img\n"
        "tag: v1\n"
        "host_config_args:\n"
        "  hostname: gcp_host\n",
    )
    node_config.MaterializeNodeConfig(
        static_dir=self.test_dir, var_config_dir=var_config_dir
    )
    env = self._ReadEnv(var_config_dir)
    # The GCP branch matters most: its docker-compose.env is regenerated from
    # a Parameter Manager payload shared across the pool, which cannot carry
    # either host-specific value.
    self.assertEqual(
        env["SECRETS_DIR"], os.path.join(self.test_dir, "secrets")
    )
    self.assertEqual(env["MTT_GID"], str(os.stat(self.test_dir).st_gid))

  # =========================================================================
  # Persistent cache detection
  # =========================================================================

  def _ReadFlags(self, var_config_dir: str) -> list[str]:
    with open(
        os.path.join(var_config_dir, "mtt_flags.yaml"), "r", encoding="utf-8"
    ) as f:
      return [str(flag) for flag in (yaml.safe_load(f) or {}).get("flags", [])]

  def testMaterializeNodeConfig_staticEnablesCacheWhenVolumeExists(self):
    self.mock_has_cache.return_value = True
    var_config_dir = self._WriteStaticConfig(
        mtt_flags_yaml=(
            "image_name: static_img\ntag: v1\nflags:\n- --port=8000\n"
        )
    )

    node_config.MaterializeNodeConfig(
        static_dir=self.test_dir, var_config_dir=var_config_dir
    )

    flags = self._ReadFlags(var_config_dir)
    self.assertIn("--bind_jfs_volume=mtt-jfs", flags)
    self.assertIn("--enable_persistent_cache", flags)
    # Unrelated flags survive.
    self.assertIn("--port=8000", flags)

  def testMaterializeNodeConfig_staticOmitsCacheWhenVolumeAbsent(self):
    var_config_dir = self._WriteStaticConfig()

    node_config.MaterializeNodeConfig(
        static_dir=self.test_dir, var_config_dir=var_config_dir
    )

    self.assertEmpty(self._ReadFlags(var_config_dir))

  def testMaterializeNodeConfig_staleCacheFlagIsStripped(self):
    # An operator-authored flag, or one inherited from a payload written
    # before the cache became host state, must not outlive the volume.
    var_config_dir = self._WriteStaticConfig(
        mtt_flags_yaml=(
            "image_name: static_img\n"
            "tag: v1\n"
            "flags:\n"
            "- --bind_jfs_volume=mtt-jfs\n"
            "- --enable_persistent_cache\n"
            "- --port=8000\n"
        )
    )

    node_config.MaterializeNodeConfig(
        static_dir=self.test_dir, var_config_dir=var_config_dir
    )

    flags = self._ReadFlags(var_config_dir)
    self.assertEqual(flags, ["--port=8000"])

  def testMaterializeNodeConfig_negatedCacheFlagIsStripped(self):
    self.mock_has_cache.return_value = True
    var_config_dir = self._WriteStaticConfig(
        mtt_flags_yaml=(
            "image_name: static_img\n"
            "tag: v1\n"
            "flags:\n"
            "- --no-enable_persistent_cache\n"
        )
    )

    node_config.MaterializeNodeConfig(
        static_dir=self.test_dir, var_config_dir=var_config_dir
    )

    flags = self._ReadFlags(var_config_dir)
    self.assertNotIn("--no-enable_persistent_cache", flags)
    self.assertIn("--enable_persistent_cache", flags)

  def testMaterializeNodeConfig_cacheFlagsAreNotDuplicated(self):
    self.mock_has_cache.return_value = True
    var_config_dir = self._WriteStaticConfig()

    node_config.MaterializeNodeConfig(
        static_dir=self.test_dir, var_config_dir=var_config_dir
    )
    node_config.MaterializeNodeConfig(
        static_dir=self.test_dir, var_config_dir=var_config_dir
    )

    flags = self._ReadFlags(var_config_dir)
    self.assertLen([f for f in flags if f.startswith("--bind_jfs_volume")], 1)

  @mock.patch.object(
      gcp_param_manager.GcpParamManagerClient, "FromServiceAccountKeyFile"
  )
  def testMaterializeNodeConfig_gcpEnablesCacheWhenVolumeExists(
      self, mock_from_key
  ):
    self.mock_has_cache.return_value = True
    var_config_dir = self._WriteGcpManifest(
        mock_from_key,
        "image_name: gcp_img\ntag: v1\nhost_config_args:\n  hostname: h\n",
    )

    node_config.MaterializeNodeConfig(
        static_dir=self.test_dir, var_config_dir=var_config_dir
    )

    self.assertIn("--bind_jfs_volume=mtt-jfs", self._ReadFlags(var_config_dir))

  def testHasCacheVolume_inspectsTheVolume(self):
    mock.patch.stopall()  # Probe the real implementation.
    with mock.patch.object(node_config.command_util, "CommandContext"):
      with mock.patch.object(node_config.command_util, "DockerContext") as ctx:
        ctx.return_value.Run.return_value = mock.Mock(return_code=0)

        self.assertTrue(node_config._HasCacheVolume())

      args = ctx.return_value.Run.call_args[0][0]
      self.assertEqual(args, ["volume", "inspect", "mtt-jfs"])

  def testHasCacheVolume_unavailableDockerIsNotAnError(self):
    mock.patch.stopall()  # Probe the real implementation.
    with mock.patch.object(node_config.command_util, "CommandContext"):
      with mock.patch.object(
          node_config.command_util,
          "DockerContext",
          side_effect=OSError("no docker"),
      ):
        # A cache probe must never be the reason a node fails to materialize.
        self.assertFalse(node_config._HasCacheVolume())


if __name__ == "__main__":
  absltest.main()
