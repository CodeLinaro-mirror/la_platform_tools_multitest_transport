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

"""Unit tests for MTT Node CLI argument parsing and dispatching."""

import argparse
import contextlib
import io
import os
from unittest import mock
from absl.testing import absltest
from multitest_transport.cli import host_env
from multitest_transport.cli import node
from multitest_transport.cli import node_init
from multitest_transport.cli import node_join
from multitest_transport.cli import node_permissions
from multitest_transport.cli import node_state

NodeRole = node.NodeRole


class NodeCliTest(absltest.TestCase):

  def setUp(self):
    super().setUp()
    self.parser = argparse.ArgumentParser()
    subparsers = self.parser.add_subparsers(dest="action")
    node.AddNodeSubparsers(subparsers)
    # Every handler sets the umask process-wide, which would otherwise leak
    # into whatever test runs next in this process.
    previous_umask = os.umask(0o022)
    os.umask(previous_umask)
    self.addCleanup(os.umask, previous_umask)

  # =========================================================================
  # CLI Init Dispatch Tests
  # =========================================================================

  @mock.patch.object(os, "geteuid", return_value=0)
  @mock.patch.object(host_env, "Detect")
  @mock.patch.object(node_init, "InitController")
  def testHandleControllerInit(self, mock_init, mock_detect, unused_geteuid):
    mock_detect.return_value = host_env.HostEnvironment.GCE
    argv = [
        "node",
        "controller",
        "init",
        "--dcon_acceptor_addr=acceptor.proj.cloud.goog",
        "--otel",
        "--service_account_json_key_path=/path/sa.json",
        "--static_dir=/tmp/etc_mtt",
        "--base_dir=/tmp/var_mttnode",
        "--",
        "--port=8080",
        "--is_omnilab_based",
        "true",
    ]
    args = self.parser.parse_args(argv)
    self.assertEqual(args.node_role, "controller")
    self.assertEqual(args.node_command, "init")

    exit_code = args.func(args)
    self.assertEqual(exit_code, 0)
    mock_init.assert_called_once_with(
        static_dir="/tmp/etc_mtt",
        base_dir="/tmp/var_mttnode",
        mtt_group=node_permissions.DEFAULT_MTT_GROUP,
        image_name="gcr.io/android-mtt/mtt",
        tag="latest",
        dcon_acceptor_addr="acceptor.proj.cloud.goog",
        otel=True,
        service_account_json_key_path="/path/sa.json",
        unrecognized_flags=["--port=8080", "--is_omnilab_based", "true"],
        host_environment=host_env.HostEnvironment.GCE,
    )

  @mock.patch.object(os, "geteuid", return_value=0)
  @mock.patch.object(node_init, "InitWorker")
  def testHandleWorkerInit(self, mock_init, unused_geteuid):
    argv = [
        "node",
        "worker",
        "init",
        "--dcon_acceptor_target=wss://acceptor.proj.cloud.goog",
        "--otel",
        "--service_account_json_key_path=/path/sa.json",
        "--static_dir=/tmp/etc_mtt",
        "--mtt_group=mttgrp",
        "/path/to/lab.yaml",
        "--",
        "--extra_flag=1",
    ]
    args = self.parser.parse_args(argv)
    self.assertEqual(args.node_role, "worker")
    self.assertEqual(args.node_command, "init")
    self.assertEqual(args.lab_config_path, "/path/to/lab.yaml")

    exit_code = args.func(args)
    self.assertEqual(exit_code, 0)
    mock_init.assert_called_once_with(
        dcon_acceptor_target="wss://acceptor.proj.cloud.goog",
        static_dir="/tmp/etc_mtt",
        base_dir="/var/lib/mttnode",
        mtt_group="mttgrp",
        image_name="gcr.io/android-mtt/mtt",
        tag="latest",
        otel=True,
        service_account_json_key_path="/path/sa.json",
        lab_config_path="/path/to/lab.yaml",
        unrecognized_flags=["--extra_flag=1"],
    )

  @mock.patch.object(os, "geteuid", return_value=0)
  @mock.patch.object(node_init, "InitWorker")
  def testHandleWorkerInit_withoutLabConfigAndWithPassthroughFlags(
      self, mock_init, unused_geteuid
  ):
    argv = [
        "node",
        "worker",
        "init",
        "--dcon_acceptor_target=wss://acceptor.proj.cloud.goog",
        "--",
        "--extra_flag=1",
        "--is_omnilab_based",
        "true",
    ]
    args = self.parser.parse_args(argv)
    exit_code = args.func(args)
    self.assertEqual(exit_code, 0)
    mock_init.assert_called_once_with(
        dcon_acceptor_target="wss://acceptor.proj.cloud.goog",
        static_dir="/etc/mtt",
        base_dir="/var/lib/mttnode",
        mtt_group=node_permissions.DEFAULT_MTT_GROUP,
        image_name="gcr.io/android-mtt/mtt",
        tag="latest",
        otel=False,
        service_account_json_key_path=None,
        lab_config_path=None,
        unrecognized_flags=["--extra_flag=1", "--is_omnilab_based", "true"],
    )

  def testInit_rejectsUnrecognizedFlagBeforeDashDash(self):
    with self.assertRaises(SystemExit):
      self.parser.parse_args([
          "node",
          "controller",
          "init",
          "--dcon_acceptor_addr=acceptor.proj.cloud.goog",
          "--port=8080",
      ])

  @mock.patch.object(os, "geteuid", return_value=1000)
  @mock.patch.object(node_init, "InitWorker")
  def testHandleWorkerInit_requiresRoot(self, mock_init, unused_geteuid):
    argv = [
        "node",
        "worker",
        "init",
        "--dcon_acceptor_target=wss://acceptor.proj.cloud.goog",
    ]
    args, unknown = self.parser.parse_known_args(argv)

    self.assertEqual(args.func(args, unknown), 1)
    # Nothing must be provisioned when the caller cannot set ownership.
    mock_init.assert_not_called()

  def _MakePrompter(self, confirm=False) -> mock.Mock:
    """Builds a prompter whose Confirm answers (or raises) as configured."""
    prompter = mock.create_autospec(node_join.Prompter, instance=True)
    if isinstance(confirm, BaseException):
      prompter.Confirm.side_effect = confirm
    else:
      prompter.Confirm.return_value = confirm
    return prompter

  @mock.patch.object(os, "geteuid", return_value=0)
  @mock.patch.object(node_join, "Join")
  def testHandleWorkerJoin(self, mock_join, unused_geteuid):
    argv = [
        "node",
        "worker",
        "join",
        "--static_dir=/tmp/etc_mtt",
        "--base_dir=/tmp/custom_base",
    ]
    args = self.parser.parse_args(argv)
    self.assertEqual(args.node_role, "worker")
    self.assertEqual(args.node_command, "join")
    self.assertEqual(args.static_dir, "/tmp/etc_mtt")
    self.assertEqual(args.base_dir, "/tmp/custom_base")
    prompter = self._MakePrompter(confirm=False)

    exit_code = args.func(args, prompter)
    self.assertEqual(exit_code, 0)
    mock_join.assert_called_once_with(
        static_dir="/tmp/etc_mtt",
        var_config_dir="/tmp/custom_base/config",
        base_dir="/tmp/custom_base",
        mtt_group=node_permissions.DEFAULT_MTT_GROUP,
        prompter=prompter,
    )

  @mock.patch.object(os, "geteuid", return_value=0)
  @mock.patch.object(node_join, "Join")
  def testHandleWorkerJoin_userAbortReturnsErrorCode(
      self, mock_join, unused_geteuid
  ):
    mock_join.side_effect = node_join.UserAbortError("cancelled")
    args = self.parser.parse_args(["node", "worker", "join"])
    prompter = self._MakePrompter(confirm=False)

    exit_code = args.func(args, prompter)

    self.assertEqual(exit_code, 1)
    # The join never completed, so there is nothing to offer to start.
    prompter.Confirm.assert_not_called()

  # =========================================================================
  # Next-step message
  # =========================================================================

  def _RunAndCapture(self, args, *rest) -> tuple[int, str]:
    """Runs a handler, returning its exit code and everything it printed."""
    stdout = io.StringIO()
    with contextlib.redirect_stdout(stdout):
      exit_code = args.func(args, *rest)
    return exit_code, stdout.getvalue()

  @mock.patch.object(os, "geteuid", return_value=0)
  @mock.patch.object(node_init, "InitWorker")
  def testHandleWorkerInit_printsStartCommand(self, unused_init, unused_euid):
    argv = [
        "node",
        "worker",
        "init",
        "--dcon_acceptor_target=wss://acceptor.proj.cloud.goog",
    ]
    args, unknown = self.parser.parse_known_args(argv)

    exit_code, output = self._RunAndCapture(args, unknown)

    self.assertEqual(exit_code, 0)
    self.assertIn("mtt node worker start", output)
    # Default directories are not echoed back: the operator would only have to
    # delete them again.
    self.assertNotIn("--static_dir", output)
    self.assertNotIn("--base_dir", output)
    self.assertIn(node_permissions.DEFAULT_MTT_GROUP, output)

  @mock.patch.object(os, "geteuid", return_value=0)
  @mock.patch.object(node_init, "InitWorker")
  def testHandleWorkerInit_printsStartCommandWithCustomDirs(
      self, unused_init, unused_euid
  ):
    argv = [
        "node",
        "worker",
        "init",
        "--dcon_acceptor_target=wss://acceptor.proj.cloud.goog",
        "--static_dir=/tmp/etc_mtt",
        "--base_dir=/tmp/var_mttnode",
        "--mtt_group=mttgrp",
    ]
    args, unknown = self.parser.parse_known_args(argv)

    _, output = self._RunAndCapture(args, unknown)

    # `start` reads both directories, so a non-default init must hand back a
    # command that still works.
    self.assertIn(
        "mtt node worker start --static_dir /tmp/etc_mtt --base_dir"
        " /tmp/var_mttnode",
        output,
    )
    self.assertIn("mttgrp", output)

  @mock.patch.object(os, "geteuid", return_value=0)
  @mock.patch.object(host_env, "Detect")
  @mock.patch.object(node_init, "InitController")
  def testHandleControllerInit_printsStartCommand(
      self, unused_init, mock_detect, unused_euid
  ):
    mock_detect.return_value = host_env.HostEnvironment.GCE
    argv = [
        "node",
        "controller",
        "init",
        "--dcon_acceptor_addr=acceptor.proj.cloud.goog",
    ]
    args, unknown = self.parser.parse_known_args(argv)

    _, output = self._RunAndCapture(args, unknown)

    self.assertIn("mtt node controller start", output)

  @mock.patch.object(os, "geteuid", return_value=0)
  @mock.patch.object(node_join, "Join")
  def testHandleWorkerJoin_declinedStartPrintsStartCommand(
      self, unused_join, unused_euid
  ):
    args = self.parser.parse_args(["node", "worker", "join"])
    prompter = self._MakePrompter(confirm=False)

    exit_code, output = self._RunAndCapture(args, prompter)

    self.assertEqual(exit_code, 0)
    self.assertIn("mtt node worker start", output)

  @mock.patch.object(os, "geteuid", return_value=0)
  @mock.patch.object(node, "_HandleStart")
  @mock.patch.object(node_join, "Join")
  def testHandleWorkerJoin_acceptedStartRunsStart(
      self, unused_join, mock_start, unused_euid
  ):
    mock_start.return_value = 0
    args = self.parser.parse_args(["node", "worker", "join"])
    prompter = self._MakePrompter(confirm=True)

    exit_code, output = self._RunAndCapture(args, prompter)

    self.assertEqual(exit_code, 0)
    mock_start.assert_called_once_with(args, node_state.NodeRole.WORKER)
    # The node is already running, so telling the operator to start it would
    # be noise.
    self.assertNotIn("Next step", output)

  @mock.patch.object(os, "geteuid", return_value=0)
  @mock.patch.object(node, "_HandleStart")
  @mock.patch.object(node_join, "Join")
  def testHandleWorkerJoin_interruptedPromptSucceedsWithoutStarting(
      self, unused_join, mock_start, unused_euid
  ):
    args = self.parser.parse_args(["node", "worker", "join"])
    prompter = self._MakePrompter(
        confirm=node_join.UserAbortError("Not starting the worker now.")
    )

    exit_code, output = self._RunAndCapture(args, prompter)

    # The join is committed by this point: interrupting the follow-up question
    # declines the start, it does not undo or fail the join.
    self.assertEqual(exit_code, 0)
    mock_start.assert_not_called()
    self.assertIn("mtt node worker start", output)

  @mock.patch.object(os, "geteuid", return_value=0)
  @mock.patch.object(node, "_HandleStart")
  @mock.patch.object(node_join, "Join")
  def testHandleWorkerJoin_unreadablePromptSucceedsWithoutStarting(
      self, unused_join, mock_start, unused_euid
  ):
    # Prompter.Confirm raises RuntimeError once the retry limit is exhausted,
    # which would otherwise surface as a traceback after a successful join.
    args = self.parser.parse_args(["node", "worker", "join"])
    prompter = self._MakePrompter(confirm=RuntimeError("retries exhausted"))

    exit_code, output = self._RunAndCapture(args, prompter)

    self.assertEqual(exit_code, 0)
    mock_start.assert_not_called()
    self.assertIn("mtt node worker start", output)

  @mock.patch.object(os, "geteuid", return_value=0)
  @mock.patch.object(node, "_HandleStart")
  @mock.patch.object(node_join, "Join")
  def testHandleWorkerJoin_startFailureDoesNotBlameTheJoin(
      self, unused_join, mock_start, unused_euid
  ):
    mock_start.return_value = 1
    args = self.parser.parse_args(["node", "worker", "join"])
    prompter = self._MakePrompter(confirm=True)
    stderr = io.StringIO()

    with contextlib.redirect_stderr(stderr):
      exit_code = args.func(args, prompter)

    # Without this, a non-zero exit at the end of `join` reads as a failed
    # join and invites a re-run that redoes the Parameter Manager writes.
    self.assertEqual(exit_code, 1)
    self.assertIn("only the start failed", stderr.getvalue())

  @mock.patch.object(os, "geteuid", return_value=0)
  @mock.patch.object(node_init, "InitWorker")
  def testHandleWorkerInit_failurePrintsNoStartCommand(
      self, mock_init, unused_euid
  ):
    mock_init.side_effect = ValueError("boom")
    argv = [
        "node",
        "worker",
        "init",
        "--dcon_acceptor_target=wss://acceptor.proj.cloud.goog",
    ]
    args, unknown = self.parser.parse_known_args(argv)

    exit_code, output = self._RunAndCapture(args, unknown)

    # Nothing was provisioned, so pointing at `start` would only produce a
    # second, more confusing failure.
    self.assertEqual(exit_code, 1)
    self.assertNotIn("start", output)

  # =========================================================================
  # CLI Lifecycle Dispatch Tests
  # =========================================================================

  @mock.patch.object(node, "_DefaultStateManagerFactory")
  def testHandleStart(self, mock_factory):
    mock_mgr = mock.create_autospec(
        node_state.NodeStateManager, instance=True, spec_set=True
    )
    mock_mgr.Start.return_value = True
    mock_factory.return_value = mock_mgr

    args = self.parser.parse_args([
        "node",
        "worker",
        "start",
        "--base_dir=/tmp/base",
        "--static_dir=/tmp/static",
    ])
    exit_code = args.func(args)
    self.assertEqual(exit_code, 0)
    mock_mgr.Start.assert_called_once()
    mock_factory.assert_called_once_with(
        base_dir="/tmp/base",
        static_dir="/tmp/static",
        role=NodeRole.WORKER,
    )

  @mock.patch.object(node, "_DefaultStateManagerFactory")
  def testHandleStop(self, mock_factory):
    mock_mgr = mock.create_autospec(
        node_state.NodeStateManager, instance=True, spec_set=True
    )
    mock_mgr.Stop.return_value = True
    mock_factory.return_value = mock_mgr

    args = self.parser.parse_args([
        "node",
        "controller",
        "stop",
        "--base_dir=/tmp/base",
        "--static_dir=/tmp/static",
    ])
    exit_code = args.func(args)
    self.assertEqual(exit_code, 0)
    mock_mgr.Stop.assert_called_once_with(drain=False, timeout_sec=None)
    mock_factory.assert_called_once_with(
        base_dir="/tmp/base",
        static_dir="/tmp/static",
        role=NodeRole.CONTROLLER,
    )

  @mock.patch.object(node, "_DefaultStateManagerFactory")
  def testHandleStop_withDrainTimeout(self, mock_factory):
    mock_mgr = mock.create_autospec(
        node_state.NodeStateManager, instance=True, spec_set=True
    )
    mock_mgr.Stop.return_value = True
    mock_factory.return_value = mock_mgr

    args = self.parser.parse_args([
        "node",
        "worker",
        "stop",
        "--drain",
        "--drain_timeout=600",
        "--base_dir=/tmp/base",
        "--static_dir=/tmp/static",
    ])
    exit_code = args.func(args)
    self.assertEqual(exit_code, 0)
    mock_mgr.Stop.assert_called_once_with(drain=True, timeout_sec=600)
    mock_factory.assert_called_once_with(
        base_dir="/tmp/base",
        static_dir="/tmp/static",
        role=NodeRole.WORKER,
    )

  @mock.patch.object(node, "_DefaultStateManagerFactory")
  def testHandleRestart(self, mock_factory):
    mock_mgr = mock.create_autospec(
        node_state.NodeStateManager, instance=True, spec_set=True
    )
    mock_mgr.Restart.return_value = True
    mock_factory.return_value = mock_mgr

    args = self.parser.parse_args(["node", "worker", "restart"])
    exit_code = args.func(args)
    self.assertEqual(exit_code, 0)
    mock_mgr.Restart.assert_called_once()

  @mock.patch.object(node, "_DefaultStateManagerFactory")
  def testHandleStatus(self, mock_factory):
    mock_mgr = mock.create_autospec(
        node_state.NodeStateManager, instance=True, spec_set=True
    )
    mock_mgr.GetStatus.return_value = node_state.NodeStatus(
        tunnel=node_state.TunnelCondition.HEALTHY,
        core=node_state.CoreCondition.UP_CURRENT,
    )
    mock_factory.return_value = mock_mgr

    args = self.parser.parse_args(["node", "controller", "status"])
    with mock.patch("builtins.print") as mock_print:
      exit_code = args.func(args)

    self.assertEqual(exit_code, 0)
    mock_mgr.GetStatus.assert_called_once()
    mock_print.assert_has_calls([
        mock.call("role: controller"),
        mock.call("tunnel: healthy"),
        mock.call("core: running"),
    ])

  @mock.patch.object(node, "_DefaultStateManagerFactory")
  def testHandleStatus_downNodeStillExitsZero(self, mock_factory):
    mock_mgr = mock.create_autospec(
        node_state.NodeStateManager, instance=True, spec_set=True
    )
    mock_mgr.GetStatus.return_value = node_state.NodeStatus(
        tunnel=node_state.TunnelCondition.DOWN,
        core=node_state.CoreCondition.DOWN,
    )
    mock_factory.return_value = mock_mgr

    args = self.parser.parse_args(["node", "worker", "status"])
    with mock.patch("builtins.print") as mock_print:
      exit_code = args.func(args)

    self.assertEqual(exit_code, 0)
    mock_print.assert_has_calls([
        mock.call("tunnel: down"),
        mock.call("core: down"),
    ])

  @mock.patch.object(node, "_DefaultStateManagerFactory")
  def testHandleTunnelUpgrade(self, mock_factory):
    mock_mgr = mock.create_autospec(
        node_state.NodeStateManager, instance=True, spec_set=True
    )
    mock_mgr.UpgradeTunnel.return_value = True
    mock_factory.return_value = mock_mgr

    args = self.parser.parse_args(["node", "worker", "tunnel", "upgrade"])
    exit_code = args.func(args)
    self.assertEqual(exit_code, 0)
    mock_mgr.UpgradeTunnel.assert_called_once()

  @mock.patch.object(node, "_DefaultStateManagerFactory")
  def testHandleCoreUpgrade(self, mock_factory):
    mock_mgr = mock.create_autospec(
        node_state.NodeStateManager, instance=True, spec_set=True
    )
    mock_mgr.UpgradeCore.return_value = True
    mock_factory.return_value = mock_mgr

    args = self.parser.parse_args(
        ["node", "controller", "core", "upgrade"]
    )
    exit_code = args.func(args)
    self.assertEqual(exit_code, 0)
    mock_mgr.UpgradeCore.assert_called_once_with(
        enable_rollback=False, drain=False, timeout_sec=None
    )

  @mock.patch.object(node, "_DefaultStateManagerFactory")
  def testHandleCoreUpgrade_withRollbackAndDrain(self, mock_factory):
    mock_mgr = mock.create_autospec(
        node_state.NodeStateManager, instance=True, spec_set=True
    )
    mock_mgr.UpgradeCore.return_value = True
    mock_factory.return_value = mock_mgr

    args = self.parser.parse_args([
        "node",
        "worker",
        "core",
        "upgrade",
        "--enable_rollback",
        "--drain",
        "--drain_timeout",
        "120",
    ])
    exit_code = args.func(args)
    self.assertEqual(exit_code, 0)
    mock_mgr.UpgradeCore.assert_called_once_with(
        enable_rollback=True, drain=True, timeout_sec=120
    )

  @mock.patch.object(host_env, "IsGceInstance")
  def testDefaultStateManagerFactory_gce(self, mock_is_gce):
    mock_is_gce.return_value = True
    temp_dir = self.create_tempdir().full_path
    mgr = node._DefaultStateManagerFactory(
        base_dir=temp_dir, image_executor=mock.MagicMock()
    )
    self.assertEqual(mgr.host_env, host_env.HostEnvironment.GCE)

  @mock.patch.object(host_env, "IsGceInstance")
  def testDefaultStateManagerFactory_default(self, mock_is_gce):
    mock_is_gce.return_value = False
    temp_dir = self.create_tempdir().full_path
    mgr = node._DefaultStateManagerFactory(
        base_dir=temp_dir, image_executor=mock.MagicMock()
    )
    self.assertEqual(mgr.host_env, host_env.HostEnvironment.DEFAULT)

  @mock.patch.object(node_state.docker_image, "DockerImageExecutor")
  @mock.patch.object(host_env, "IsGceInstance", return_value=False)
  def testGetStateManager_forwardsCliPath(self, unused_is_gce, unused_docker):
    temp_dir = self.create_tempdir().full_path
    args = self.parser.parse_args([
        "node",
        "worker",
        "start",
        f"--base_dir={temp_dir}",
        f"--static_dir={temp_dir}",
    ])
    args.cli_path = "/home/mobileharness/mtt"
    mgr = node._GetStateManager(args, node.NodeRole.WORKER)
    self.assertEqual(mgr._mtt_cli_path, "/home/mobileharness/mtt")

  # =========================================================================
  # Membership preflight
  # =========================================================================

  def _ParseRoutineArgs(self, command: str) -> argparse.Namespace:
    return self.parser.parse_args([
        "node",
        "worker",
        command,
        "--base_dir=/tmp/base",
        "--static_dir=/tmp/static",
    ])

  @mock.patch.object(node, "_DefaultStateManagerFactory")
  @mock.patch.object(node_permissions, "CheckMembership")
  def testHandleStart_nonMemberIsRejected(self, mock_check, mock_factory):
    mock_check.side_effect = node_permissions.PermissionPolicyError("nope")
    args = self._ParseRoutineArgs("start")

    self.assertEqual(args.func(args), 1)
    mock_factory.assert_not_called()

  @mock.patch.object(node, "_DefaultStateManagerFactory")
  @mock.patch.object(node_permissions, "CheckMembership")
  def testHandleStatus_nonMemberIsRejected(self, mock_check, mock_factory):
    # status is gated exactly like start. Without the gate a non-member is
    # told the tunnel is DOWN, because ObserveTunnel uses os.path.exists and
    # that reports EACCES as False.
    mock_check.side_effect = node_permissions.PermissionPolicyError("nope")
    args = self._ParseRoutineArgs("status")

    self.assertEqual(args.func(args), 1)
    mock_factory.assert_not_called()

  @mock.patch.object(node, "_DefaultStateManagerFactory")
  @mock.patch.object(node_permissions, "CheckMembership")
  def testHandleStatus_memberIsObserved(self, mock_check, mock_factory):
    del mock_check
    mock_mgr = mock.create_autospec(
        node_state.NodeStateManager, instance=True, spec_set=True
    )
    mock_mgr.GetStatus.return_value = node_state.NodeStatus(
        tunnel=node_state.TunnelCondition.HEALTHY,
        core=node_state.CoreCondition.UP_CURRENT,
    )
    mock_factory.return_value = mock_mgr
    args = self._ParseRoutineArgs("status")

    self.assertEqual(args.func(args), 0)
    mock_mgr.GetStatus.assert_called_once()

  @mock.patch.object(node_permissions, "CheckMembership")
  def testRoutineCommands_areAllGated(self, mock_check):
    # One rule for every non-provisioning command, so a new subcommand cannot
    # quietly skip the check.
    mock_check.side_effect = node_permissions.PermissionPolicyError("nope")

    def CollectLeafCommands(
        parser: argparse.ArgumentParser, prefix: tuple[str, ...] = ()
    ) -> list[tuple[tuple[str, ...], argparse.ArgumentParser]]:
      subparser_actions = [
          action
          for action in parser._actions  
          if isinstance(action, argparse._SubParsersAction)  
      ]
      if not subparser_actions:
        return [(prefix, parser)] if parser.get_default("func") else []
      leaves = []
      for action in subparser_actions:
        for name, subparser in action.choices.items():
          leaves.extend(CollectLeafCommands(subparser, prefix + (name,)))
      return leaves

    leaves = CollectLeafCommands(self.parser)
    routine_leaves = [
        (path, leaf_parser)
        for path, leaf_parser in leaves
        if path[-1] not in ("init", "join")
    ]
    self.assertNotEmpty(routine_leaves)
    for path, _ in routine_leaves:
      args = self.parser.parse_args(list(path))
      self.assertEqual(args.func(args), 1, msg=" ".join(path))


if __name__ == "__main__":
  absltest.main()
