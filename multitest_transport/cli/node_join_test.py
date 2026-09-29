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

"""Unit tests for multitest_transport.cli.node_join."""

import grp
import json
import os
import re
import shutil
import stat
import tempfile
from typing import Optional
from unittest import mock
from absl.testing import absltest
from multitest_transport.cli import gcp_endpoints_client
from multitest_transport.cli import gcp_param_manager
from multitest_transport.cli import node_config
from multitest_transport.cli import node_join
from multitest_transport.cli import node_permissions
import yaml

# Parameter ID derived from the hostname the join tests mock out.
_WORKER_HOST_PARAM = "worker-host-1-69c3d3a75a60_node_config"


class FakePrompter(node_join.Prompter):
  """Fake Prompter that serves queued responses without interactive I/O."""

  def __init__(
      self,
      text_responses: Optional[list[str]] = None,
      password_responses: Optional[list[str]] = None,
      choice_responses: Optional[list[str]] = None,
  ):
    super().__init__(isatty_check=False)
    self._text_queue = list(text_responses or [])
    self._password_queue = list(password_responses or [])
    self._choice_queue = list(choice_responses or [])
    self.printed_messages: list[str] = []

  def CheckTty(self) -> None:
    pass

  def Text(
      self,
      message: str,
      validator=None,
      error_message: str = "",
      max_retries: int = 3,
  ) -> str:
    del error_message, max_retries
    val = self._text_queue.pop(0)
    if validator and not validator(val):
      raise ValueError(f"Validation failed for '{val}'")
    return val

  def Password(
      self,
      message: str,
      validator=None,
      error_message: str = "",
      max_retries: int = 3,
  ) -> str:
    del error_message, max_retries
    val = self._password_queue.pop(0)
    if validator and not validator(val):
      raise ValueError(f"Validation failed for '{val}'")
    return val

  def Choice(
      self,
      message: str,
      options=(),
      display_fn=None,
      max_retries: int = 3,
  ) -> str:
    del display_fn, max_retries
    choice_val = self._choice_queue.pop(0)
    if choice_val not in options:
      raise ValueError(f"Choice '{choice_val}' not in options {options}")
    return choice_val


class NodeJoinTest(absltest.TestCase):

  def setUp(self):
    super().setUp()
    self.test_dir = tempfile.mkdtemp()
    self.static_dir = os.path.join(self.test_dir, "etc_mtt")
    self.base_dir = os.path.join(self.test_dir, "var_lib_mttnode")
    self.var_config_dir = os.path.join(self.test_dir, "var_mtt_config")
    os.makedirs(self.static_dir, exist_ok=True)
    os.makedirs(self.var_config_dir, exist_ok=True)
    # A group the test process already belongs to: chown to any other group is
    # EPERM for a non-root process, and Forge shards are not root.
    self.mtt_group = grp.getgrgid(os.getgid()).gr_name

    self.sa_key_file = os.path.join(self.test_dir, "source_sa_key.json")
    with open(self.sa_key_file, "w", encoding="utf-8") as f:
      json.dump({"project_id": "test-project-123"}, f)

  def tearDown(self):
    shutil.rmtree(self.test_dir)
    super().tearDown()

  def _AssertNoSideEffects(self, mock_pm_client):
    """Asserts an aborted join wrote nothing locally and nothing to GCP.

    Args:
      mock_pm_client: The Parameter Manager client mock the join was given.
    """
    self.assertEmpty(os.listdir(self.static_dir))
    self.assertEmpty(os.listdir(self.var_config_dir))
    mock_pm_client.StoreUnformatted.assert_not_called()
    mock_pm_client.CreateParameter.assert_not_called()

  def testPrompter_textAndChoice(self):
    prompts_seen = []
    messages_seen = []

    def MockInput(prompt):
      prompts_seen.append(prompt)
      if len(prompts_seen) == 1:
        return ""  # Invalid empty
      if len(prompts_seen) == 2:
        return "valid_text"
      return "1"  # For choice

    prompter = node_join.Prompter(
        input_fn=MockInput,
        output_fn=messages_seen.append,
        isatty_check=False,
    )
    result = prompter.Text("Enter val: ", validator=lambda s: bool(s.strip()))
    self.assertEqual(result, "valid_text")

    chosen = prompter.Choice("Select:", options=["opt1", "opt2"])
    self.assertEqual(chosen, "opt1")

  def testPrompter_confirm(self):
    answers = ["", "y", "n"]

    def MockInput(prompt):
      del prompt
      return answers.pop(0)

    prompter = node_join.Prompter(
        input_fn=MockInput, output_fn=lambda _: None, isatty_check=False
    )
    self.assertTrue(prompter.Confirm("Confirm 1"))
    self.assertTrue(prompter.Confirm("Confirm 2"))
    self.assertFalse(prompter.Confirm("Confirm 3"))

  def testPrompter_confirmExhaustsRetries(self):
    prompter = node_join.Prompter(
        input_fn=lambda _: "maybe",
        output_fn=lambda _: None,
        isatty_check=False,
    )
    with self.assertRaisesRegex(RuntimeError, "Maximum retry limit exceeded"):
      prompter.Confirm("Confirm", max_retries=2)

  def testPrompter_raisesUserAbortOnInterrupt(self):
    def RaiseInterrupt(prompt):
      del prompt
      raise KeyboardInterrupt()

    def RaiseEof(prompt):
      del prompt
      raise EOFError()

    prompter = node_join.Prompter(
        input_fn=RaiseInterrupt,
        getpass_fn=RaiseEof,
        output_fn=lambda _: None,
        isatty_check=False,
    )
    with self.assertRaises(node_join.UserAbortError):
      prompter.Text("Enter val: ")
    with self.assertRaises(node_join.UserAbortError):
      prompter.Confirm("Confirm")
    with self.assertRaises(node_join.UserAbortError):
      prompter.Choice("Select:", options=["a", "b"])
    with self.assertRaises(node_join.UserAbortError):
      prompter.Password("Enter password: ")

  def testHostnameToNodeParamName(self):
    test_cases = [
        ("worker-host-1", _WORKER_HOST_PARAM),
        (
            "worker-host-1.corp.example.com",
            "worker-host-1-corp-example-com-50582349ce03_node_config",
        ),
        (
            "android-mtt-worker-0123.bej.lab.corp.google.com",
            "android-mtt-worker-0123-bej-lab-corp-g-59255627d82a_node_config",
        ),
    ]
    for hostname, expected_param in test_cases:
      self.assertEqual(
          node_join.HostnameToNodeParamName(hostname), expected_param
      )

  def testHostnameToNodeParamName_alwaysValidParameterId(self):
    # Parameter Manager enforces this server-side; see
    # cloud/security/parametermanager/shared/util/resourcepath/resourcepath.go
    param_id_pattern = re.compile(r"^[a-zA-Z0-9_][a-zA-Z0-9_-]{0,62}$")
    hostnames = [
        "h",
        "worker-host-1",
        "android-mtt-worker-0123.bej.lab.corp.google.com",
        "a" * 80,
        "host@domain",
        "host_with_underscores.corp",
        "a-café.lab",
        "lab-中文",
        "中" * 30,
        "----",
    ]
    for hostname in hostnames:
      param_name = node_join.HostnameToNodeParamName(hostname)
      self.assertRegex(param_name, param_id_pattern)
      self.assertEndsWith(param_name, "_node_config")

  def testHostnameToNodeParamName_distinctHostnamesDoNotCollide(self):
    # Every pair below renders to the same readable prefix, so only the digest
    # keeps them apart.
    hostnames = [
        "host.lab",
        "host-lab",
        "host_lab",
        "host@lab",
        "a-café.lab",
        "a-cafe-lab",
        "中" * 30,
        "文" * 30,
    ]

    param_names = [node_join.HostnameToNodeParamName(h) for h in hostnames]

    self.assertLen(set(param_names), len(hostnames))

  def testHostnameToNodeParamName_canonicalizesCaseAndTrailingDot(self):
    # DNS names are case-insensitive and the trailing root dot is optional, so
    # all three spellings name one machine and must map to one parameter.
    canonical = node_join.HostnameToNodeParamName("host.corp.example.com")

    self.assertEqual(
        node_join.HostnameToNodeParamName("HOST.Corp.Example.COM"), canonical
    )
    self.assertEqual(
        node_join.HostnameToNodeParamName("host.corp.example.com."), canonical
    )

  def testHostnameToNodeParamName_rejectsInvalidHostnames(self):
    with self.assertRaisesRegex(ValueError, "cannot be empty"):
      node_join.HostnameToNodeParamName("")
    with self.assertRaisesRegex(ValueError, "cannot be empty"):
      node_join.HostnameToNodeParamName("  ")
    with self.assertRaisesRegex(ValueError, "consecutive dots"):
      node_join.HostnameToNodeParamName("host..example.com")

  @mock.patch.object(node_config, "MaterializeNodeConfig")
  @mock.patch("socket.gethostname", return_value="worker-host-1")
  def testJoin_failureRestoresExistingFiles(
      self, mock_hostname, mock_materialize
  ):
    del mock_hostname
    mock_materialize.side_effect = RuntimeError("materialization exploded")

    # Simulate a host already provisioned by `mtt node worker init`.
    secrets_dir = os.path.join(self.static_dir, "secrets")
    config_dir = os.path.join(self.static_dir, "config")
    os.makedirs(secrets_dir, exist_ok=True)
    os.makedirs(config_dir, exist_ok=True)
    existing_sa_key = os.path.join(secrets_dir, "sa-key.json")
    existing_wifi = os.path.join(config_dir, "wifi.yaml")
    with open(existing_sa_key, "w", encoding="utf-8") as f:
      f.write("PREEXISTING_KEY")
    with open(existing_wifi, "w", encoding="utf-8") as f:
      f.write("PREEXISTING_WIFI")

    fake_prompter = FakePrompter(
        text_responses=[self.sa_key_file, "MyTestWifi"],
        password_responses=["MySecretPassword"],
        choice_responses=[
            "acceptor.endpoints.test-project-123.cloud.goog",
            "private_usage",
        ],
    )
    mock_ep_client = mock.create_autospec(
        gcp_endpoints_client.GcpEndpointsClient, instance=True, spec_set=True
    )
    mock_ep_client.ListServiceNames.return_value = [
        "acceptor.endpoints.test-project-123.cloud.goog"
    ]
    mock_pm_client = mock.create_autospec(
        gcp_param_manager.GcpParamManagerClient, instance=True, spec_set=True
    )
    mock_pm_client.ListParameters.return_value = [
        "tenant_config",
        "private_usage_pool_config",
    ]
    mock_pm_client.ParameterExists.return_value = True
    mock_pm_client.StoreUnformatted.return_value = "version_1"

    with self.assertRaises(RuntimeError):
      node_join.Join(
          static_dir=self.static_dir,
          var_config_dir=self.var_config_dir,
          base_dir=self.base_dir,
          mtt_group=self.mtt_group,
          prompter=fake_prompter,
          endpoints_client_factory=lambda _: mock_ep_client,
          param_manager_client_factory=lambda _: mock_pm_client,
      )

    # The previous provisioning must survive a failed join untouched.
    with open(existing_sa_key, "r", encoding="utf-8") as f:
      self.assertEqual(f.read(), "PREEXISTING_KEY")
    with open(existing_wifi, "r", encoding="utf-8") as f:
      self.assertEqual(f.read(), "PREEXISTING_WIFI")
    # The manifest did not exist before, so it must not exist after.
    self.assertFalse(
        os.path.exists(os.path.join(self.static_dir, "manifest.yaml"))
    )
    self.assertFalse(os.path.exists(f"{existing_sa_key}.join_bak"))
    self.assertFalse(os.path.exists(f"{existing_wifi}.join_bak"))

  @mock.patch.object(node_config, "MaterializeNodeConfig")
  @mock.patch("socket.gethostname", return_value="worker-host-1")
  def testJoin(
      self, mock_hostname, mock_materialize
  ):
    del mock_hostname
    fake_prompter = FakePrompter(
        text_responses=[self.sa_key_file, "MyTestWifi"],
        password_responses=["MySecretPassword"],
        choice_responses=[
            "acceptor.endpoints.test-project-123.cloud.goog",
            "private_usage",
        ],
    )

    mock_ep_client = mock.create_autospec(
        gcp_endpoints_client.GcpEndpointsClient, instance=True, spec_set=True
    )
    mock_ep_client.ListServiceNames.return_value = [
        "acceptor.endpoints.test-project-123.cloud.goog"
    ]

    mock_pm_client = mock.create_autospec(
        gcp_param_manager.GcpParamManagerClient, instance=True, spec_set=True
    )
    mock_pm_client.ListParameters.return_value = [
        "tenant_config",
        "private_usage_pool_config",
        "cts_testing_pool_config",
    ]
    mock_pm_client.ParameterExists.return_value = False
    mock_pm_client.CreateParameter.return_value = "created_param_name"
    mock_pm_client.StoreUnformatted.return_value = "version_1"

    node_join.Join(
        static_dir=self.static_dir,
        var_config_dir=self.var_config_dir,
        base_dir=self.base_dir,
        mtt_group=self.mtt_group,
        prompter=fake_prompter,
        endpoints_client_factory=lambda _: mock_ep_client,
        param_manager_client_factory=lambda _: mock_pm_client,
    )

    # 1. Verify GCP Calls
    mock_ep_client.ListServiceNames.assert_called_once_with("test-project-123")
    mock_pm_client.ListParameters.assert_called_once_with("test-project-123")
    mock_pm_client.ParameterExists.assert_called_once_with(
        "test-project-123", _WORKER_HOST_PARAM
    )
    mock_pm_client.CreateParameter.assert_called_once_with(
        "test-project-123", _WORKER_HOST_PARAM
    )
    mock_pm_client.StoreUnformatted.assert_called_once()
    stored_path, stored_payload = mock_pm_client.StoreUnformatted.call_args[0]
    self.assertEqual(
        stored_path,
        "projects/test-project-123/locations/global/parameters/"
        f"{_WORKER_HOST_PARAM}",
    )
    payload_dict = yaml.safe_load(stored_payload)
    self.assertEqual(
        payload_dict["cluster_config_args"]["omni_mode_usage"], "private_usage"
    )
    # Nothing host-specific belongs in the payload. The service account key
    # path is injected locally from manifest.yaml, and the persistent cache
    # follows the mtt-jfs volume, which the JuiceFS deployment can add or
    # remove at any time; recording either here would freeze a local fact into
    # durable remote config. Both collections end up empty, and ToDict drops
    # empty collections, so the keys are absent entirely.
    self.assertNotIn("mtt_args", payload_dict)
    self.assertNotIn("mtt_bool_args", payload_dict)
    self.assertNotIn("tag", payload_dict)
    # These keys must match the variables read by compose/infra/dcon.yml;
    # anything else leaves the dialer with an empty acceptor target.
    self.assertEqual(
        payload_dict["docker_compose_env"]["ACCEPTOR_TARGET"],
        "wss://acceptor.endpoints.test-project-123.cloud.goog",
    )
    self.assertEqual(
        payload_dict["docker_compose_env"]["USE_SA_TOKEN"], "true"
    )
    self.assertEqual(
        payload_dict["docker_compose_env"]["SA_KEY_FILE"],
        "/etc/secrets/sa-key.json",
    )

    # 2. Verify Local File Scaffolding
    sa_key_path = os.path.join(self.static_dir, "secrets", "sa-key.json")
    self.assertTrue(os.path.exists(sa_key_path))
    file_mode = stat.S_IMODE(os.stat(sa_key_path).st_mode)
    self.assertEqual(file_mode, node_permissions.STATIC_FILE_MODE)

    wifi_path = os.path.join(self.static_dir, "config", "wifi.yaml")
    self.assertTrue(os.path.exists(wifi_path))
    file_mode_wifi = stat.S_IMODE(os.stat(wifi_path).st_mode)
    self.assertEqual(file_mode_wifi, node_permissions.STATIC_FILE_MODE)
    with open(wifi_path, "r", encoding="utf-8") as f:
      wifi_doc = yaml.safe_load(f)
    self.assertEqual(wifi_doc["WIFI_SSID"], "MyTestWifi")
    self.assertEqual(wifi_doc["WIFI_PSK"], "MySecretPassword")

    manifest_path = os.path.join(self.static_dir, "manifest.yaml")
    self.assertTrue(os.path.exists(manifest_path))
    with open(manifest_path, "r", encoding="utf-8") as f:
      manifest_content = f.read()
    self.assertIn(sa_key_path, manifest_content)
    self.assertIn("tenant_config", manifest_content)
    self.assertIn("private_usage_pool_config", manifest_content)
    self.assertIn(_WORKER_HOST_PARAM, manifest_content)

    mock_materialize.assert_called_once_with(
        static_dir=self.static_dir,
        var_config_dir=self.var_config_dir,
        role=node_config.NodeRole.WORKER,
    )

    # Verify passing tag and android_service_account_key_path writes node-scope
    # overrides into Parameter Manager and copies android-sa-key.json.
    android_key_src = os.path.join(self.test_dir, "src_android_key.json")
    with open(android_key_src, "w", encoding="utf-8") as f:
      f.write('{"type": "service_account", "project_id": "android-proj"}')
    fake_prompter_tag = FakePrompter(
        text_responses=[self.sa_key_file, "MyTestWifi"],
        password_responses=["MySecretPassword"],
        choice_responses=[
            "acceptor.endpoints.test-project-123.cloud.goog",
            "private_usage",
        ],
    )
    node_join.Join(
        static_dir=self.static_dir,
        var_config_dir=self.var_config_dir,
        base_dir=self.base_dir,
        mtt_group=self.mtt_group,
        tag="custom_node_tag",
        android_service_account_key_path=android_key_src,
        prompter=fake_prompter_tag,
        endpoints_client_factory=lambda _: mock_ep_client,
        param_manager_client_factory=lambda _: mock_pm_client,
    )
    _, stored_payload_with_tag = mock_pm_client.StoreUnformatted.call_args[0]
    payload_with_overrides = yaml.safe_load(stored_payload_with_tag)
    self.assertEqual(payload_with_overrides["tag"], "custom_node_tag")
    expected_android_key_dest = os.path.join(
        self.static_dir, "secrets", "android-sa-key.json"
    )
    self.assertEqual(
        payload_with_overrides["mtt_args"],
        {"android_service_account_key_path": expected_android_key_dest},
    )
    self.assertTrue(os.path.exists(expected_android_key_dest))
    with open(expected_android_key_dest, "r", encoding="utf-8") as f:
      self.assertEqual(
          f.read(), '{"type": "service_account", "project_id": "android-proj"}'
      )
    self.assertEqual(
        stat.S_IMODE(os.stat(expected_android_key_dest).st_mode),
        node_permissions.STATIC_FILE_MODE,
    )

  def testJoin_tenantConfigMissing(self):
    fake_prompter = FakePrompter(
        text_responses=[self.sa_key_file],
        choice_responses=["ep1.cloud.goog"],
    )
    mock_ep_client = mock.create_autospec(
        gcp_endpoints_client.GcpEndpointsClient, instance=True, spec_set=True
    )
    mock_ep_client.ListServiceNames.return_value = ["ep1.cloud.goog"]

    mock_pm_client = mock.create_autospec(
        gcp_param_manager.GcpParamManagerClient, instance=True, spec_set=True
    )
    mock_pm_client.ListParameters.return_value = ["some_other_config"]

    with self.assertRaisesRegex(
        RuntimeError, "'tenant_config' parameter not found"
    ):
      node_join.Join(
          static_dir=self.static_dir,
          var_config_dir=self.var_config_dir,
          base_dir=self.base_dir,
          mtt_group=self.mtt_group,
          prompter=fake_prompter,
          endpoints_client_factory=lambda _: mock_ep_client,
          param_manager_client_factory=lambda _: mock_pm_client,
      )

    self._AssertNoSideEffects(mock_pm_client)

  def testJoin_noEndpoints(self):
    fake_prompter = FakePrompter(
        text_responses=[self.sa_key_file],
    )
    mock_ep_client = mock.create_autospec(
        gcp_endpoints_client.GcpEndpointsClient, instance=True, spec_set=True
    )
    mock_ep_client.ListServiceNames.return_value = []

    mock_pm_client = mock.create_autospec(
        gcp_param_manager.GcpParamManagerClient, instance=True, spec_set=True
    )

    with self.assertRaisesRegex(
        RuntimeError, "No Cloud Endpoints services found"
    ):
      node_join.Join(
          static_dir=self.static_dir,
          var_config_dir=self.var_config_dir,
          base_dir=self.base_dir,
          mtt_group=self.mtt_group,
          prompter=fake_prompter,
          endpoints_client_factory=lambda _: mock_ep_client,
          param_manager_client_factory=lambda _: mock_pm_client,
      )

    self._AssertNoSideEffects(mock_pm_client)


if __name__ == "__main__":
  absltest.main()
