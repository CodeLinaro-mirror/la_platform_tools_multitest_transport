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

"""Unit tests for NodeStateManager."""

import contextlib
import io
import json
import os
from unittest import mock
from absl.testing import absltest
from multitest_transport.cli import common
from multitest_transport.cli import compose_directory
from multitest_transport.cli import docker_image
from multitest_transport.cli import host_env
from multitest_transport.cli import node_config
from multitest_transport.cli import node_permissions
from multitest_transport.cli import node_state
from multitest_transport.cli import process_executor
from multitest_transport.cli import release_directory
import yaml

NodeRole = node_state.NodeRole
CoreCondition = node_state.CoreCondition
TunnelCondition = node_state.TunnelCondition
HostEnvironment = host_env.HostEnvironment
NodeStateManager = node_state.NodeStateManager
ExecutionResult = process_executor.ExecutionResult


# PullAndResolveImageRef returns a complete image reference, not a bare
# digest. Fixtures must match that contract so that callers which
# mishandle the reference fail here rather than in production.
_CANDIDATE_IMAGE_REF = "gcr.io/proj/mtt-worker@sha256:aaa111"
_ACTIVE_IMAGE_REF = "gcr.io/proj/mtt-worker@sha256:bbb222"


class NodeStateTest(absltest.TestCase):

  def setUp(self):
    super().setUp()
    previous_umask = os.umask(0o022)
    os.umask(previous_umask)
    self.addCleanup(os.umask, previous_umask)

    self.test_dir = self.create_tempdir().full_path
    self.static_dir = self.create_tempdir().full_path
    self.release_mgr = release_directory.ReleaseDirectoryManager(self.test_dir)
    self.compose_mgr = mock.create_autospec(
        compose_directory.ComposeDirectoryManager,
        instance=True,
        spec_set=True,
    )
    self.compose_mgr.compose_dir = os.path.join(self.test_dir, "compose")
    self.compose_mgr.GetComposeFilePath.side_effect = lambda path: os.path.join(
        self.compose_mgr.compose_dir, path
    )
    self.mock_image_executor = mock.create_autospec(
        docker_image.DockerImageExecutor, instance=True, spec_set=True
    )
    self.mock_image_executor.GetContainerStatus.return_value = (
        docker_image.ContainerStatus.NOT_RUNNING
    )
    self.mock_compose_executor = mock.create_autospec(
        process_executor.DockerComposeExecutor, instance=True, spec_set=True
    )
    self.mock_compose_executor.CheckHealthy.return_value = ExecutionResult(
        common.CommandResult(0, "", "")
    )
    self.mock_compose_executor.StartAndAwaitHealthy.return_value = (
        ExecutionResult(common.CommandResult(0, "tunnel up", ""))
    )
    self.mock_compose_executor.Stop.return_value = ExecutionResult(
        common.CommandResult(0, "", "")
    )

    self.patch_compose = mock.patch.object(
        process_executor.DockerComposeExecutor,
        "FromConfigFiles",
        return_value=self.mock_compose_executor,
    )
    self.mock_compose_factory = self.enterContext(self.patch_compose)

    self.mock_stop_executor = mock.create_autospec(
        process_executor.MttStopExecutor, instance=True, spec_set=True
    )
    self.mock_stop_executor.Stop.return_value = ExecutionResult(
        common.CommandResult(0, "", "")
    )
    self.enterContext(
        mock.patch.object(
            process_executor,
            "MttStopExecutor",
            return_value=self.mock_stop_executor,
        )
    )

    self.state_mgr = NodeStateManager(
        base_dir=self.test_dir,
        static_dir=self.static_dir,
        release_mgr=self.release_mgr,
        compose_mgr=self.compose_mgr,
        image_executor=self.mock_image_executor,
        role=NodeRole.WORKER,
    )

  # ==========================================================================
  # Fixtures
  # ==========================================================================

  def _PopulateStaticConfig(
      self,
      image_name: str = "mtt-worker",
      tag: str = "v1",
      flags: tuple[str, ...] = ("--port=8000",),
      is_controller: bool = False,
      otel_endpoint: str = "",
      acceptor_target: str = "wss://acceptor.example.com",
      acceptor_addr: str = "",
  ) -> None:
    static_cfg_dir = os.path.join(self.static_dir, "config")
    os.makedirs(static_cfg_dir, exist_ok=True)
    if not is_controller:
      with open(
          os.path.join(static_cfg_dir, "lab_config.yaml"),
          "w",
          encoding="utf-8",
      ) as f:
        f.write("host_config:\n  hostname: localhost\n")
    flags_data = {
        "image_name": image_name,
        "tag": tag,
        "flags": list(flags),
    }
    with open(
        os.path.join(static_cfg_dir, "mtt_flags.yaml"), "w", encoding="utf-8"
    ) as f:
      yaml.dump(flags_data, f)
    env_content = "COMPOSE_PROJECT_NAME=mtt-infra\n"
    if otel_endpoint:
      env_content += f"OTEL_EXPORTER_OTLP_ENDPOINT={otel_endpoint}\n"
    if acceptor_target:
      env_content += f"ACCEPTOR_TARGET={acceptor_target}\n"
    if acceptor_addr:
      env_content += f"DCON_ACCEPTOR_ADDR={acceptor_addr}\n"
    with open(
        os.path.join(static_cfg_dir, "docker-compose.env"),
        "w",
        encoding="utf-8",
    ) as f:
      f.write(env_content)

  def _PopulateRuntimeConfig(self) -> None:
    """Writes the materialized config a release is staged from."""
    os.makedirs(self.release_mgr.config_dir, exist_ok=True)
    with open(
        self.release_mgr.config_lab_config_path, "w", encoding="utf-8"
    ) as f:
      f.write("host_config:\n  hostname: localhost\n")
    with open(self.release_mgr.config_flags_path, "w", encoding="utf-8") as f:
      yaml.dump({"image_name": "mtt-worker", "tag": "v1", "flags": []}, f)
    with open(
        self.release_mgr.config_compose_env_path, "w", encoding="utf-8"
    ) as f:
      f.write("ACCEPTOR_TARGET=wss://acceptor.example.com\n")

  def _CreateActiveRelease(self, image_ref: str = _ACTIVE_IMAGE_REF) -> None:
    """Puts the node in the condition left by a previous successful start."""
    self._PopulateRuntimeConfig()
    self.release_mgr.StageRelease(image_ref)
    self.release_mgr.PromoteStagingToActive()

  def _RecordAppliedTunnelEnv(self) -> None:
    """Records an applied tunnel env, as a successful tunnel start would."""
    self._PopulateRuntimeConfig()
    self.release_mgr.StageTunnelEnv()

  def _MockCore(
      self, success: bool = True, error: str = ""
  ) -> mock.MagicMock:
    """Builds an MttExecutor whose start succeeds or fails."""
    core = mock.create_autospec(
        process_executor.MttExecutor, instance=True, spec_set=True
    )
    code = 0 if success else 1
    core.StartAndAwaitHealthy.return_value = ExecutionResult(
        common.CommandResult(code, "", error)
    )
    return core

  def _ReadJournal(self) -> dict[str, object]:
    with open(self.state_mgr.journal_file, "r", encoding="utf-8") as f:
      return json.load(f)

  def _JournalSteps(self) -> list[str]:
    return [step["step"] for step in self._ReadJournal()["steps"]]

  # ==========================================================================
  # Observations
  # ==========================================================================

  def testObserveTunnel_neverStartedIsDown(self):
    self.assertEqual(self.state_mgr.ObserveTunnel(), TunnelCondition.DOWN)
    self.mock_compose_executor.CheckHealthy.assert_not_called()

  def testObserveTunnel_healthy(self):
    self._RecordAppliedTunnelEnv()

    self.assertEqual(self.state_mgr.ObserveTunnel(), TunnelCondition.HEALTHY)

  def testObserveTunnel_unhealthyIsDown(self):
    self._RecordAppliedTunnelEnv()
    self.mock_compose_executor.CheckHealthy.return_value = ExecutionResult(
        common.CommandResult(1, "", "Compose services are unhealthy")
    )

    self.assertEqual(self.state_mgr.ObserveTunnel(), TunnelCondition.DOWN)

  def testObserveTunnel_readsAppliedEnv(self):
    self._RecordAppliedTunnelEnv()

    self.state_mgr.ObserveTunnel()

    self.assertEqual(
        self.mock_compose_factory.call_args.kwargs["env_file"],
        self.release_mgr.tunnel_compose_env_path,
    )

  def testObserveCore_noContainerIsDown(self):
    self.mock_image_executor.GetContainerStatus.return_value = (
        docker_image.ContainerStatus.NOT_RUNNING
    )

    self.assertEqual(
        self.state_mgr.ObserveCore(_CANDIDATE_IMAGE_REF), CoreCondition.DOWN
    )

  def testObserveCore_unhealthyContainerIsDown(self):
    self.mock_image_executor.GetContainerStatus.return_value = (
        docker_image.ContainerStatus.UNHEALTHY
    )

    self.assertEqual(
        self.state_mgr.ObserveCore(_CANDIDATE_IMAGE_REF), CoreCondition.DOWN
    )

  def testObserveCore_matchingImageIsCurrent(self):
    self.mock_image_executor.GetContainerStatus.return_value = (
        docker_image.ContainerStatus.HEALTHY
    )
    self.mock_image_executor.DoesContainerMatchImage.return_value = True

    self.assertEqual(
        self.state_mgr.ObserveCore(_CANDIDATE_IMAGE_REF),
        CoreCondition.UP_CURRENT,
    )

  def testObserveCore_otherImageIsStale(self):
    self.mock_image_executor.GetContainerStatus.return_value = (
        docker_image.ContainerStatus.HEALTHY
    )
    self.mock_image_executor.DoesContainerMatchImage.return_value = False

    self.assertEqual(
        self.state_mgr.ObserveCore(_CANDIDATE_IMAGE_REF),
        CoreCondition.UP_STALE,
    )

  def testObserveCore_noCandidateIsCurrent(self):
    self.mock_image_executor.GetContainerStatus.return_value = (
        docker_image.ContainerStatus.HEALTHY
    )

    self.assertEqual(self.state_mgr.ObserveCore(), CoreCondition.UP_CURRENT)
    self.mock_image_executor.DoesContainerMatchImage.assert_not_called()

  def testGetStatus_reportsBothGroups(self):
    self._RecordAppliedTunnelEnv()
    self.mock_image_executor.GetContainerStatus.return_value = (
        docker_image.ContainerStatus.HEALTHY
    )

    status = self.state_mgr.GetStatus()

    self.assertEqual(status.tunnel, TunnelCondition.HEALTHY)
    self.assertTrue(status.core.is_up)

  def testGetStatus_writesNoJournal(self):
    self.state_mgr.GetStatus()

    self.assertFalse(os.path.exists(self.state_mgr.journal_file))

  # ==========================================================================
  # Start
  # ==========================================================================

  @mock.patch.object(process_executor.MttExecutor, "FromConfigFiles")
  def testStart(self, mock_from_config_files):
    self._PopulateStaticConfig()
    self.mock_image_executor.PullAndResolveImageRef.return_value = (
        _CANDIDATE_IMAGE_REF
    )
    mock_from_config_files.return_value = self._MockCore()

    success = self.state_mgr.Start()

    self.assertTrue(success)
    self.assertTrue(self.release_mgr.has_active_release)
    self.mock_compose_executor.StartAndAwaitHealthy.assert_called_once_with(
        pull=None
    )
    self.assertTrue(
        os.path.exists(self.release_mgr.tunnel_compose_env_path)
    )

  @mock.patch.object(process_executor.MttExecutor, "FromConfigFiles")
  def testStart_authenticatesWithServiceAccountKey(
      self, mock_from_config_files
  ):
    self._PopulateStaticConfig()
    secrets_dir = os.path.join(self.static_dir, "secrets")
    os.makedirs(secrets_dir, exist_ok=True)
    sa_key_path = os.path.join(secrets_dir, "sa-key.json")
    with open(sa_key_path, "w", encoding="utf-8") as f:
      f.write("{}")
    self.mock_image_executor.PullAndResolveImageRef.return_value = (
        _CANDIDATE_IMAGE_REF
    )
    mock_from_config_files.return_value = self._MockCore()

    self.assertTrue(self.state_mgr.Start())

    self.mock_image_executor.PullAndResolveImageRef.assert_called_once_with(
        "mtt-worker:v1",
        service_account_json_key_path=sa_key_path,
    )
    self.mock_image_executor.LoginWithServiceAccount.assert_called_once_with(
        sa_key_path, "us-docker.pkg.dev/android-mtt"
    )

  @mock.patch.object(process_executor.MttExecutor, "FromConfigFiles")
  def testStart_controllerRole(self, mock_from_config_files):
    controller_mgr = NodeStateManager(
        base_dir=self.test_dir,
        static_dir=self.static_dir,
        release_mgr=self.release_mgr,
        compose_mgr=self.compose_mgr,
        image_executor=self.mock_image_executor,
        role=NodeRole.CONTROLLER,
    )
    self._PopulateStaticConfig(
        image_name="mtt-controller", tag="v1", is_controller=True
    )
    self.mock_image_executor.PullAndResolveImageRef.return_value = (
        _CANDIDATE_IMAGE_REF
    )
    mock_from_config_files.return_value = self._MockCore()

    success = controller_mgr.Start()

    self.assertTrue(success)
    mock_from_config_files.assert_called_with(
        lab_config_path=None,
        pinned_mtt_flags_path=self.release_mgr.staging_flags_path,
        mtt_bin="mtt",
    )

  def testStart_missingConfigAborts(self):
    success = self.state_mgr.Start()

    self.assertFalse(success)
    journal = self._ReadJournal()
    self.assertFalse(journal["success"])
    self.assertIn(
        "No configuration source found", journal["steps"][0]["error_message"]
    )

  def testStart_imagePullFailureAborts(self):
    self._PopulateStaticConfig()
    self.mock_image_executor.PullAndResolveImageRef.side_effect = (
        docker_image.Error("Registry timeout")
    )

    success = self.state_mgr.Start()

    self.assertFalse(success)
    self.assertEqual(
        self._JournalSteps(),
        ["MaterializeAndValidateConfig", "ResolveCandidate"],
    )

  def testStart_tunnelFailureAborts(self):
    self._PopulateStaticConfig()
    self.mock_image_executor.PullAndResolveImageRef.return_value = (
        _CANDIDATE_IMAGE_REF
    )
    self.mock_compose_executor.StartAndAwaitHealthy.return_value = (
        ExecutionResult(common.CommandResult(1, "", "Sidecar crash"))
    )

    success = self.state_mgr.Start()

    self.assertFalse(success)
    self.assertFalse(self.release_mgr.has_active_release)
    # The applied env is only recorded after the tunnel is actually up.
    self.assertFalse(
        os.path.exists(self.release_mgr.tunnel_compose_env_path)
    )

  def testStart_staleCoreAborts(self):
    self._PopulateStaticConfig()
    self.mock_image_executor.PullAndResolveImageRef.return_value = (
        _CANDIDATE_IMAGE_REF
    )
    self.mock_image_executor.GetContainerStatus.return_value = (
        docker_image.ContainerStatus.HEALTHY
    )
    self.mock_image_executor.DoesContainerMatchImage.return_value = False
    self.mock_image_executor.GetContainerImage.return_value = (
        _ACTIVE_IMAGE_REF
    )

    success = self.state_mgr.Start()

    self.assertFalse(success)
    self.mock_compose_executor.StartAndAwaitHealthy.assert_not_called()
    self.mock_stop_executor.Stop.assert_not_called()

  def testStart_currentCoreAndHealthyTunnelDoesNothing(self):
    self._PopulateStaticConfig()
    self._RecordAppliedTunnelEnv()
    self.mock_image_executor.PullAndResolveImageRef.return_value = (
        _CANDIDATE_IMAGE_REF
    )
    self.mock_image_executor.GetContainerStatus.return_value = (
        docker_image.ContainerStatus.HEALTHY
    )
    self.mock_image_executor.DoesContainerMatchImage.return_value = True

    success = self.state_mgr.Start()

    self.assertTrue(success)
    self.mock_compose_executor.StartAndAwaitHealthy.assert_not_called()
    self.mock_stop_executor.Stop.assert_not_called()
    self.assertFalse(self.release_mgr.has_staging_release)

  @mock.patch.object(process_executor.MttExecutor, "FromConfigFiles")
  def testStart_currentCoreAndDownTunnelStopsCore(
      self, mock_from_config_files
  ):
    self._PopulateStaticConfig()
    self.mock_image_executor.PullAndResolveImageRef.return_value = (
        _CANDIDATE_IMAGE_REF
    )
    self.mock_image_executor.GetContainerStatus.return_value = (
        docker_image.ContainerStatus.HEALTHY
    )
    self.mock_image_executor.DoesContainerMatchImage.return_value = True
    mock_from_config_files.return_value = self._MockCore()

    success = self.state_mgr.Start()

    self.assertTrue(success)
    # The tunnel was restarted, so the core has to follow it.
    self.mock_stop_executor.Stop.assert_called_once_with(
        drain=False, timeout_sec=None
    )
    self.assertIn("StopCore", self._JournalSteps())
    self.assertTrue(self.release_mgr.has_active_release)

  @mock.patch.object(process_executor.MttExecutor, "FromConfigFiles")
  def testStart_unhealthyCoreStopsCoreAndDeploys(
      self, mock_from_config_files
  ):
    self._PopulateStaticConfig()
    self._RecordAppliedTunnelEnv()
    self.mock_image_executor.PullAndResolveImageRef.return_value = (
        _CANDIDATE_IMAGE_REF
    )
    self.mock_image_executor.GetContainerStatus.return_value = (
        docker_image.ContainerStatus.UNHEALTHY
    )
    mock_from_config_files.return_value = self._MockCore()

    success = self.state_mgr.Start()

    self.assertTrue(success)
    self.mock_stop_executor.Stop.assert_called_once_with(
        drain=False, timeout_sec=None
    )
    self.assertTrue(self.release_mgr.has_active_release)

  @mock.patch.object(process_executor.MttExecutor, "FromConfigFiles")
  def testStart_coreFailureAbortsWithoutRollback(self, mock_from_config_files):
    self._CreateActiveRelease()
    self._PopulateStaticConfig()
    self.mock_image_executor.PullAndResolveImageRef.return_value = (
        _CANDIDATE_IMAGE_REF
    )
    mock_from_config_files.return_value = self._MockCore(
        success=False, error="Candidate crash"
    )

    success = self.state_mgr.Start()

    self.assertFalse(success)
    # Exactly one core start was attempted: start never rolls back.
    self.assertEqual(
        mock_from_config_files.return_value.StartAndAwaitHealthy.call_count, 1
    )
    self.assertEqual(self._JournalSteps()[-1], "StartCore")

  @mock.patch.object(process_executor.MttExecutor, "FromConfigFiles")
  def testStart_writesJournal(self, mock_from_config_files):
    self._PopulateStaticConfig()
    self.mock_image_executor.PullAndResolveImageRef.return_value = (
        _CANDIDATE_IMAGE_REF
    )
    mock_from_config_files.return_value = self._MockCore()

    self.state_mgr.Start()

    journal = self._ReadJournal()
    self.assertEqual(journal["command"], "Start")
    self.assertTrue(journal["success"])
    self.assertEqual(
        self._JournalSteps(),
        [
            "MaterializeAndValidateConfig",
            "ResolveCandidate",
            "StopCore",
            "StageComposeFiles",
            "StartTunnel",
            "RecordAppliedTunnelEnv",
            "StageRelease",
            "StartCore",
            "PromoteStaging",
        ],
    )

  @mock.patch.object(process_executor.MttExecutor, "FromConfigFiles")
  def testStart_journalReplacesPreviousRun(self, mock_from_config_files):
    self._PopulateStaticConfig()
    self.mock_image_executor.PullAndResolveImageRef.return_value = (
        _CANDIDATE_IMAGE_REF
    )
    mock_from_config_files.return_value = self._MockCore()
    self.state_mgr.Start()
    first_run_steps = len(self._JournalSteps())

    self.state_mgr.Stop()

    self.assertEqual(self._ReadJournal()["command"], "Stop")
    self.assertLess(len(self._JournalSteps()), first_run_steps)

  # ==========================================================================
  # Stop
  # ==========================================================================

  def testStop(self):
    self._RecordAppliedTunnelEnv()
    self.mock_image_executor.GetContainerStatus.return_value = (
        docker_image.ContainerStatus.HEALTHY
    )

    success = self.state_mgr.Stop()

    self.assertTrue(success)
    self.mock_stop_executor.Stop.assert_called_once_with(
        drain=False, timeout_sec=None
    )
    self.mock_compose_executor.Stop.assert_called_once_with(
        remove_orphans=True
    )

  def testStop_passesDrainTimeout(self):
    self._RecordAppliedTunnelEnv()
    self.mock_image_executor.GetContainerStatus.return_value = (
        docker_image.ContainerStatus.HEALTHY
    )

    self.state_mgr.Stop(drain=True, timeout_sec=120)

    self.mock_stop_executor.Stop.assert_called_once_with(
        drain=True, timeout_sec=120
    )

  def testStop_noContainerRunningSkipsCoreStop(self):
    self._RecordAppliedTunnelEnv()
    self.mock_image_executor.GetContainerStatus.return_value = (
        docker_image.ContainerStatus.NOT_RUNNING
    )

    success = self.state_mgr.Stop()

    self.assertTrue(success)
    self.mock_stop_executor.Stop.assert_not_called()
    self.mock_compose_executor.Stop.assert_called_once()

  def testStop_neverStartedTunnelSkipsTunnelStop(self):
    self.mock_image_executor.GetContainerStatus.return_value = (
        docker_image.ContainerStatus.NOT_RUNNING
    )

    success = self.state_mgr.Stop()

    self.assertTrue(success)
    self.mock_compose_executor.Stop.assert_not_called()

  def testStop_coreStopFailureAborts(self):
    self._RecordAppliedTunnelEnv()
    self.mock_image_executor.GetContainerStatus.return_value = (
        docker_image.ContainerStatus.HEALTHY
    )
    self.mock_stop_executor.Stop.return_value = ExecutionResult(
        common.CommandResult(1, "", "mtt stop failed")
    )

    success = self.state_mgr.Stop()

    self.assertFalse(success)
    self.mock_compose_executor.Stop.assert_not_called()

  # ==========================================================================
  # Restart
  # ==========================================================================

  def testRestart_noActiveReleaseFails(self):
    success = self.state_mgr.Restart()

    self.assertFalse(success)
    self.mock_stop_executor.Stop.assert_not_called()

  @mock.patch.object(process_executor.MttExecutor, "FromConfigFiles")
  def testRestart_healthyTunnelIsLeftAlone(self, mock_from_config_files):
    self._CreateActiveRelease()
    self._RecordAppliedTunnelEnv()
    self.mock_image_executor.GetContainerStatus.return_value = (
        docker_image.ContainerStatus.HEALTHY
    )
    mock_from_config_files.return_value = self._MockCore()

    success = self.state_mgr.Restart()

    self.assertTrue(success)
    self.mock_compose_executor.StartAndAwaitHealthy.assert_not_called()
    self.mock_stop_executor.Stop.assert_called_once()
    mock_from_config_files.assert_called_with(
        lab_config_path=self.release_mgr.active_config_path,
        pinned_mtt_flags_path=self.release_mgr.active_flags_path,
        mtt_bin="mtt",
    )

  @mock.patch.object(process_executor.MttExecutor, "FromConfigFiles")
  def testRestart_downTunnelIsStarted(self, mock_from_config_files):
    self._CreateActiveRelease()
    self.mock_image_executor.GetContainerStatus.return_value = (
        docker_image.ContainerStatus.HEALTHY
    )
    mock_from_config_files.return_value = self._MockCore()

    success = self.state_mgr.Restart()

    self.assertTrue(success)
    self.mock_compose_executor.StartAndAwaitHealthy.assert_called_once_with(
        pull=None
    )

  # ==========================================================================
  # Core upgrade
  # ==========================================================================

  def _PrepareCoreUpgrade(self) -> None:
    """Puts the node in the condition core upgrade requires."""
    self._CreateActiveRelease()
    self._RecordAppliedTunnelEnv()
    self._PopulateStaticConfig()
    self.mock_image_executor.PullAndResolveImageRef.return_value = (
        _CANDIDATE_IMAGE_REF
    )
    self.mock_image_executor.GetContainerStatus.return_value = (
        docker_image.ContainerStatus.HEALTHY
    )
    self.mock_image_executor.DoesContainerMatchImage.return_value = False
    self.mock_image_executor.GetContainerImage.return_value = (
        _ACTIVE_IMAGE_REF
    )

  @mock.patch.object(process_executor.MttExecutor, "FromConfigFiles")
  def testUpgradeCore_promotesCandidate(self, mock_from_config_files):
    self._PrepareCoreUpgrade()
    mock_from_config_files.return_value = self._MockCore()

    success = self.state_mgr.UpgradeCore()

    self.assertTrue(success)
    self.assertFalse(self.release_mgr.has_staging_release)
    self.assertIn("PromoteStaging", self._JournalSteps())

  @mock.patch.object(process_executor.MttExecutor, "FromConfigFiles")
  def testUpgradeCore_doesNotTouchTunnel(self, mock_from_config_files):
    self._PrepareCoreUpgrade()
    mock_from_config_files.return_value = self._MockCore()

    self.state_mgr.UpgradeCore()

    self.mock_compose_executor.StartAndAwaitHealthy.assert_not_called()
    self.mock_compose_executor.Stop.assert_not_called()

  def testUpgradeCore_alreadyOnCandidateSkips(self):
    self._PrepareCoreUpgrade()
    self.mock_image_executor.DoesContainerMatchImage.return_value = True

    success = self.state_mgr.UpgradeCore()

    self.assertTrue(success)
    self.mock_stop_executor.Stop.assert_not_called()
    self.assertNotIn("StageRelease", self._JournalSteps())

  def testUpgradeCore_noActiveReleaseFails(self):
    self._PopulateStaticConfig()

    success = self.state_mgr.UpgradeCore()

    self.assertFalse(success)
    self.mock_image_executor.PullAndResolveImageRef.assert_not_called()

  def testUpgradeCore_coreNotRunningFails(self):
    self._PrepareCoreUpgrade()
    self.mock_image_executor.GetContainerStatus.return_value = (
        docker_image.ContainerStatus.NOT_RUNNING
    )

    success = self.state_mgr.UpgradeCore()

    self.assertFalse(success)
    self.assertNotIn("StageRelease", self._JournalSteps())

  def testUpgradeCore_unhealthyTunnelFails(self):
    self._PrepareCoreUpgrade()
    self.mock_compose_executor.CheckHealthy.return_value = ExecutionResult(
        common.CommandResult(1, "", "Compose services are unhealthy")
    )

    success = self.state_mgr.UpgradeCore()

    self.assertFalse(success)
    self.mock_stop_executor.Stop.assert_not_called()

  @mock.patch.object(process_executor.MttExecutor, "FromConfigFiles")
  def testUpgradeCore_candidateFailureWithoutRollbackLeavesNodeStopped(
      self, mock_from_config_files
  ):
    self._PrepareCoreUpgrade()
    failing_core = self._MockCore(success=False, error="Candidate crash")
    mock_from_config_files.return_value = failing_core

    success = self.state_mgr.UpgradeCore(enable_rollback=False)

    self.assertFalse(success)
    self.assertEqual(failing_core.StartAndAwaitHealthy.call_count, 1)
    self.assertTrue(self.release_mgr.has_staging_release)

  @mock.patch.object(process_executor.MttExecutor, "FromConfigFiles")
  def testUpgradeCore_candidateFailureWithRollbackRestoresActive(
      self, mock_from_config_files
  ):
    self._PrepareCoreUpgrade()
    candidate_core = self._MockCore(success=False, error="Candidate crash")
    active_core = self._MockCore()

    def SelectExecutor(pinned_mtt_flags_path=None, **_):
      if pinned_mtt_flags_path == self.release_mgr.staging_flags_path:
        return candidate_core
      return active_core

    mock_from_config_files.side_effect = SelectExecutor

    success = self.state_mgr.UpgradeCore(enable_rollback=True)

    # A rollback is a failed upgrade, even though the node is serving again.
    self.assertFalse(success)
    active_core.StartAndAwaitHealthy.assert_called_once()
    self.assertFalse(self.release_mgr.has_staging_release)
    self.assertEqual(
        self._JournalSteps()[-3:],
        ["DiscardStaging", "StopCore", "StartCore"],
    )

  @mock.patch.object(process_executor.MttExecutor, "FromConfigFiles")
  def testUpgradeCore_unrecoverableFailureSkipsRollback(
      self, mock_from_config_files
  ):
    self._PrepareCoreUpgrade()
    mock_from_config_files.return_value = self._MockCore(
        success=False, error="No space left on device"
    )

    with mock.patch.object(
        self.state_mgr, "EvaluateCoreRecoverable", return_value=False
    ):
      success = self.state_mgr.UpgradeCore(enable_rollback=True)

    self.assertFalse(success)
    self.assertNotIn("DiscardStaging", self._JournalSteps())

  # ==========================================================================
  # Tunnel upgrade
  # ==========================================================================

  @mock.patch.object(process_executor.MttExecutor, "FromConfigFiles")
  def testUpgradeTunnel(self, mock_from_config_files):
    self._CreateActiveRelease()
    self._PopulateStaticConfig()
    self.mock_image_executor.GetContainerStatus.return_value = (
        docker_image.ContainerStatus.HEALTHY
    )
    mock_from_config_files.return_value = self._MockCore()

    success = self.state_mgr.UpgradeTunnel()

    self.assertTrue(success)
    self.mock_compose_executor.StartAndAwaitHealthy.assert_called_once_with(
        pull="always"
    )
    self.assertEqual(
        self._JournalSteps(),
        [
            "MaterializeAndValidateConfig",
            "StopCore",
            "StageComposeFiles",
            "StartTunnel",
            "RecordAppliedTunnelEnv",
            "StartCore",
        ],
    )

  def testUpgradeTunnel_noActiveReleaseFails(self):
    self._PopulateStaticConfig()

    success = self.state_mgr.UpgradeTunnel()

    self.assertFalse(success)
    self.mock_compose_executor.StartAndAwaitHealthy.assert_not_called()

  def testUpgradeTunnel_tunnelFailureLeavesCoreStopped(self):
    self._CreateActiveRelease()
    self._PopulateStaticConfig()
    self.mock_image_executor.GetContainerStatus.return_value = (
        docker_image.ContainerStatus.HEALTHY
    )
    self.mock_compose_executor.StartAndAwaitHealthy.return_value = (
        ExecutionResult(common.CommandResult(1, "", "Sidecar crash"))
    )

    success = self.state_mgr.UpgradeTunnel()

    self.assertFalse(success)
    self.mock_stop_executor.Stop.assert_called_once()
    self.assertEqual(self._JournalSteps()[-1], "StartTunnel")

  # ==========================================================================
  # Config validation
  # ==========================================================================

  def testStart_workerWithoutAcceptorTargetAborts(self):
    self._PopulateStaticConfig(acceptor_target="")

    success = self.state_mgr.Start()

    self.assertFalse(success)
    self.assertIn(
        "Missing ACCEPTOR_TARGET",
        self._ReadJournal()["steps"][0]["error_message"],
    )

  def testStart_controllerOnGcpWithoutAcceptorAddrAborts(self):
    controller_mgr = NodeStateManager(
        base_dir=self.test_dir,
        static_dir=self.static_dir,
        release_mgr=self.release_mgr,
        compose_mgr=self.compose_mgr,
        image_executor=self.mock_image_executor,
        role=NodeRole.CONTROLLER,
        host_env=HostEnvironment.GCE,
    )
    self._PopulateStaticConfig(is_controller=True, acceptor_target="")

    success = controller_mgr.Start()

    self.assertFalse(success)

  def testStart_controllerOffGcpWithAcceptorAddrAborts(self):
    controller_mgr = NodeStateManager(
        base_dir=self.test_dir,
        static_dir=self.static_dir,
        release_mgr=self.release_mgr,
        compose_mgr=self.compose_mgr,
        image_executor=self.mock_image_executor,
        role=NodeRole.CONTROLLER,
        host_env=HostEnvironment.LAB,
    )
    self._PopulateStaticConfig(
        is_controller=True,
        acceptor_target="",
        acceptor_addr="acceptor.endpoints.proj.cloud.goog",
    )

    success = controller_mgr.Start()

    self.assertFalse(success)

  # ==========================================================================
  # Compose profiles
  # ==========================================================================

  def testStartTunnel_selectsProfilesFromDesiredEnv(self):
    self._PopulateStaticConfig(otel_endpoint="http://collector:4317")
    node_config.MaterializeNodeConfig(
        static_dir=self.static_dir,
        var_config_dir=self.release_mgr.config_dir,
        role=NodeRole.WORKER,
    )

    self.state_mgr._StartTunnel()  

    kwargs = self.mock_compose_factory.call_args.kwargs
    self.assertEqual(
        kwargs["env_file"], self.release_mgr.config_compose_env_path
    )
    self.assertEqual(kwargs["project_dir"], self.compose_mgr.compose_dir)
    self.assertIn("otel", kwargs["profiles"])
    self.assertIn("worker", kwargs["profiles"])

  def testStartTunnel_selectsEspProfileForGcpController(self):
    controller_mgr = NodeStateManager(
        base_dir=self.test_dir,
        static_dir=self.static_dir,
        release_mgr=self.release_mgr,
        compose_mgr=self.compose_mgr,
        image_executor=self.mock_image_executor,
        role=NodeRole.CONTROLLER,
        host_env=HostEnvironment.GCE,
    )
    self._PopulateStaticConfig(
        is_controller=True,
        acceptor_target="",
        acceptor_addr="acceptor.endpoints.proj.cloud.goog",
    )
    node_config.MaterializeNodeConfig(
        static_dir=self.static_dir,
        var_config_dir=self.release_mgr.config_dir,
        role=NodeRole.CONTROLLER,
    )

    controller_mgr._StartTunnel()  

    self.assertIn(
        "esp", self.mock_compose_factory.call_args.kwargs["profiles"]
    )

  def testPipeline_unexpectedExceptionStillClosesJournal(self):
    self._PopulateStaticConfig()
    with mock.patch.object(
        self.state_mgr, "ObserveTunnel", side_effect=RuntimeError("boom")
    ):
      with self.assertRaisesRegex(RuntimeError, "boom"):
        self.state_mgr.Start()

    journal = self._ReadJournal()
    self.assertEqual(journal["command"], "Start")
    self.assertFalse(journal["success"])
    self.assertIsNotNone(journal["finished_at"])
    self.assertEqual(
        self._JournalSteps(),
        ["MaterializeAndValidateConfig", "ResolveCandidate"],
    )

  def testGetTunnelComposeExecutor_composeConfigValidatesPaths(self):
    real_compose_mgr = compose_directory.ComposeDirectoryManager(self.test_dir)
    real_compose_mgr.ExtractComposeFiles()
    self._PopulateRuntimeConfig()

    self.mock_compose_factory.side_effect = (
        self.patch_compose.temp_original.__get__(
            None, process_executor.DockerComposeExecutor
        )
    )
    with mock.patch.object(process_executor.command_util, "DockerContext"):
      for env in (HostEnvironment.LAB, HostEnvironment.GCE):
        mgr = NodeStateManager(
            base_dir=self.test_dir,
            static_dir=self.static_dir,
            release_mgr=self.release_mgr,
            compose_mgr=real_compose_mgr,
            image_executor=self.mock_image_executor,
            role=NodeRole.WORKER,
            host_env=env,
        )
        executor = mgr._GetTunnelComposeExecutor(  
            self.release_mgr.config_compose_env_path
        )
        config = executor._config  

        self.assertEqual(config.project_dir, real_compose_mgr.compose_dir)
        self.assertTrue(os.path.isdir(config.project_dir))
        self.assertEqual(
            config.env_file, self.release_mgr.config_compose_env_path
        )
        self.assertTrue(os.path.isfile(config.env_file))
        self.assertNotEmpty(config.compose_files)

        base_args = executor._BuildBaseArgs(config)  
        self.assertIn("--project-directory", base_args)
        self.assertIn(real_compose_mgr.compose_dir, base_args)
        self.assertIn("--env-file", base_args)
        self.assertIn(self.release_mgr.config_compose_env_path, base_args)

        for compose_file in config.compose_files:
          self.assertTrue(
              os.path.isfile(compose_file),
              msg=f"Missing compose file on disk: {compose_file}",
          )
          with open(compose_file, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
          for entry in data.get("include", []):
            include_rel = (
                entry["path"] if isinstance(entry, dict) else str(entry)
            )
            resolved_path = os.path.normpath(
                os.path.join(config.project_dir, include_rel)
            )
            self.assertTrue(
                os.path.isfile(resolved_path),
                msg=(
                    f"Include path '{include_rel}' in {compose_file} resolved"
                    f" to missing file '{resolved_path}' under project_dir"
                    f" '{config.project_dir}'"
                ),
            )

  # ==========================================================================
  # Permission drift
  # ==========================================================================

  def testCloseJournal_recordsDriftOnFailure(self):
    self._PopulateStaticConfig()
    node_permissions.ApplyPolicy(
        os.getgid(), static_dir=self.static_dir, base_dir=self.test_dir
    )
    os.chmod(os.path.join(self.static_dir, "config", "mtt_flags.yaml"), 0o600)

    self.state_mgr._OpenJournal("Start")  
    with contextlib.redirect_stderr(io.StringIO()):
      self.state_mgr._CloseJournal(False)  

    paths = [
        item["path"] for item in self._ReadJournal()["permission_drift"]
    ]
    self.assertIn("static:/config/mtt_flags.yaml", paths)

  def testCloseJournal_skipsDriftOnSuccess(self):
    self._PopulateStaticConfig()
    os.chmod(os.path.join(self.static_dir, "config", "mtt_flags.yaml"), 0o600)

    self.state_mgr._OpenJournal("Start")  
    with mock.patch.object(node_permissions, "DetectDrift") as mock_detect:
      self.state_mgr._CloseJournal(True)  

    # A recursive walk of both trees is pure cost when the command succeeded.
    mock_detect.assert_not_called()
    self.assertNotIn("permission_drift", self._ReadJournal())

  def testCloseJournal_writtenJournalPrintsPointerOnly(self):
    drift = [{
        "path": "static:/config",
        "expected": "docker 2750",
        "actual": "docker 0755",
    }]
    self.state_mgr._OpenJournal("Start")  
    stderr = io.StringIO()
    with mock.patch.object(node_permissions, "DetectDrift", return_value=drift):
      with contextlib.redirect_stderr(stderr):
        self.state_mgr._CloseJournal(False)  

    self.assertEqual(self._ReadJournal()["permission_drift"], drift)
    self.assertIn(self.state_mgr.journal_file, stderr.getvalue())
    self.assertIn("sudo mtt node worker init", stderr.getvalue())
    # The table stays out of the terminal once it has been filed.
    self.assertNotIn("static:/config", stderr.getvalue())

  def testCloseJournal_unwritableJournalDumpsDrift(self):
    drift = [{
        "path": "static:/config",
        "expected": "docker 2750",
        "actual": "docker 0755",
    }]
    self.state_mgr._OpenJournal("Start")  
    stderr = io.StringIO()
    with mock.patch.object(node_permissions, "DetectDrift", return_value=drift):
      with mock.patch.object(
          self.state_mgr, "_WriteJournal", return_value=False
      ):
        with contextlib.redirect_stderr(stderr):
          self.state_mgr._CloseJournal(False)  

    # A pointer to a file that was never written is worse than no pointer.
    self.assertIn("cannot write", stderr.getvalue())
    self.assertIn(
        "static:/config  expected docker 2750, actual docker 0755",
        stderr.getvalue(),
    )

  def testStart_failureOnPolicyCleanTreesRecordsNoDrift(self):
    self._PopulateStaticConfig()
    node_permissions.SetUmask()
    node_permissions.ApplyPolicy(
        os.getgid(), static_dir=self.static_dir, base_dir=self.test_dir
    )
    with mock.patch.object(
        self.state_mgr, "ObserveTunnel", side_effect=RuntimeError("boom")
    ):
      with contextlib.redirect_stderr(io.StringIO()):
        with self.assertRaisesRegex(RuntimeError, "boom"):
          self.state_mgr.Start()

    # Start materialized config/ before failing, creating files that did not
    # exist at provisioning time. With the policy check, none of them are
    # reported as drift.
    self.assertNotIn("permission_drift", self._ReadJournal())

  @mock.patch.object(process_executor.MttExecutor, "FromConfigFiles")
  def testStart_coreFailureLogsStepAndJournalPath(self, mock_from_config_files):
    self._PopulateStaticConfig()
    self.mock_image_executor.PullAndResolveImageRef.return_value = (
        _CANDIDATE_IMAGE_REF
    )
    mock_from_config_files.return_value = self._MockCore(success=False)
    with contextlib.redirect_stderr(io.StringIO()):
      with self.assertLogs(node_state.logger, level="ERROR") as cm:
        self.assertFalse(self.state_mgr.Start())
    joined_logs = "\n".join(cm.output)
    self.assertIn("Step StartCore failed:", joined_logs)
    self.assertIn("Start failed at step StartCore.", joined_logs)
    self.assertIn(self.state_mgr.journal_file, joined_logs)

  def testResolveServiceAccountKeyPath_readsFromFlagsList(self):
    os.makedirs(self.release_mgr.config_dir, exist_ok=True)
    with open(
        self.release_mgr.config_flags_path, "w", encoding="utf-8"
    ) as f:
      yaml.dump(
          {
              "image_name": "gcr.io/android-mtt/mtt",
              "tag": "latest",
              "flags": [
                  "--port=8000",
                  "--service_account_json_key_path=/custom/key.json",
              ],
          },
          f,
      )

    
    self.assertEqual(
        self.state_mgr._ResolveServiceAccountKeyPath(), "/custom/key.json"
    )

  def testResolveTunnelRepo_readsCustomDconRepo(self):
    os.makedirs(self.release_mgr.config_dir, exist_ok=True)
    with open(
        self.release_mgr.config_compose_env_path, "w", encoding="utf-8"
    ) as f:
      f.write('DCON_REPO="asia-docker.pkg.dev/custom-proj/dcon"\n')

    
    self.assertEqual(
        self.state_mgr._ResolveTunnelRepo(),
        "asia-docker.pkg.dev/custom-proj/dcon",
    )

  def testStartTunnel_loginFailureReturnsFailedBlockResult(self):
    secrets_dir = os.path.join(self.static_dir, "secrets")
    os.makedirs(secrets_dir, exist_ok=True)
    sa_key_path = os.path.join(secrets_dir, "sa-key.json")
    with open(sa_key_path, "w", encoding="utf-8") as f:
      f.write("{}")
    self.mock_image_executor.LoginWithServiceAccount.side_effect = (
        docker_image.Error("auth failed")
    )

    
    res = self.state_mgr._StartTunnel()
    self.assertFalse(res.success)
    self.assertIn("auth failed", res.error_message)
    self.mock_compose_executor.StartAndAwaitHealthy.assert_not_called()


if __name__ == "__main__":
  absltest.main()
