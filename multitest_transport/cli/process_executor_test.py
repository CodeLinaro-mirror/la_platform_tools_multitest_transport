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

"""Unit tests for DockerComposeExecutor, MttExecutor and MttStopExecutor."""

import os
import shutil
import tempfile
from unittest import mock

from absl.testing import absltest
from multitest_transport.cli import command_util
from multitest_transport.cli import common
from multitest_transport.cli import process_executor
import yaml

DockerComposeConfig = process_executor.DockerComposeConfig
DockerComposeExecutor = process_executor.DockerComposeExecutor
MttConfig = process_executor.MttConfig
MttExecutor = process_executor.MttExecutor
MttStopExecutor = process_executor.MttStopExecutor
ExecutionResult = process_executor.ExecutionResult


class ExecutionResultTest(absltest.TestCase):

  def testReturnCode_success(self):
    result = ExecutionResult(common.CommandResult(0, "ok", ""))
    self.assertTrue(result.success)
    self.assertEqual(result.return_code, 0)

  def testReturnCode_failure(self):
    result = ExecutionResult(common.CommandResult(2, "", "boom"))
    self.assertFalse(result.success)
    self.assertEqual(result.return_code, 2)

  def testReturnCode_unsetIsNonzero(self):
    result = ExecutionResult(common.CommandResult(None, "", ""))
    self.assertFalse(result.success)
    self.assertNotEqual(result.return_code, 0)

  def testErrorMessage_unsetOutputs(self):
    # A timed out Run returns every field unset; error_message must not report
    # a literal "None" exit code nor crash on None.strip().
    result = ExecutionResult(common.CommandResult(None, None, None))
    self.assertEqual(result.error_message, "Command failed with return code 1")


class DockerComposeExecutorTest(absltest.TestCase):

  def setUp(self):
    super().setUp()
    self.mock_docker_context = mock.create_autospec(
        command_util.DockerContext, instance=True
    )
    self.config = DockerComposeConfig(
        compose_files=["/path/to/compose.yaml"],
        env_file="/path/to/compose.env",
        project_dir="/path/to/project",
        project_name="my_proj",
        profiles=["infra"],
    )
    self.executor = DockerComposeExecutor(
        config=self.config,
        docker_context=self.mock_docker_context,
    )

  def testBuildBaseArgs(self):
    args = DockerComposeExecutor._BuildBaseArgs(self.config)
    self.assertEqual(
        args,
        [
            "compose",
            "-p",
            "my_proj",
            "--project-directory",
            "/path/to/project",
            "--env-file",
            "/path/to/compose.env",
            "--profile",
            "infra",
            "-f",
            "/path/to/compose.yaml",
        ],
    )

  def testStartAndAwaitHealthy(self):
    self.mock_docker_context.Run.return_value = common.CommandResult(
        0, "Container started and healthy", ""
    )

    res = self.executor.StartAndAwaitHealthy(
        timeout_sec=120, wait_timeout_sec=30
    )

    self.assertTrue(res.success)
    self.assertEqual(res.return_code, 0)
    self.mock_docker_context.Run.assert_called_once_with(
        [
            "compose",
            "-p",
            "my_proj",
            "--project-directory",
            "/path/to/project",
            "--env-file",
            "/path/to/compose.env",
            "--profile",
            "infra",
            "-f",
            "/path/to/compose.yaml",
            "up",
            "-d",
            "--wait",
            "--wait-timeout",
            "30",
        ],
        raise_on_failure=False,
        timeout=120,
    )

  def testStartAndAwaitHealthy_failureWithDiagnostics(self):
    ps_output = (
        '[{"Service": "sidecar", "State": "exited", "Health": "unhealthy"},'
        ' {"Service": "redis", "State": "running", "Health": "healthy"}]'
    )
    self.mock_docker_context.Run.side_effect = [
        common.CommandResult(1, "", "Failed to start sidecar"),
        common.CommandResult(0, ps_output, ""),
        common.CommandResult(0, "Error: bind failed\nFatal crash", ""),
    ]

    res = self.executor.StartAndAwaitHealthy(timeout_sec=60)

    self.assertFalse(res.success)
    self.assertEqual(res.return_code, 1)
    self.assertEqual(res.stderr, "Failed to start sidecar")
    self.assertIn("sidecar", res.failed_services)
    self.assertIn("Error: bind failed", res.failed_services["sidecar"])
    self.assertNotIn("redis", res.failed_services)

  def testStartAndAwaitHealthy_failureWithLogsTimeout(self):
    # `docker compose logs` is most likely to hit its 15s timeout on exactly
    # the unhealthy host being diagnosed, and a timed out Run yields
    # stdout=None. Previously this raised AttributeError out of _Logs and the
    # operator lost the whole diagnostic.
    ps_output = '[{"Service": "sidecar", "State": "exited", "Health": ""}]'
    self.mock_docker_context.Run.side_effect = [
        common.CommandResult(1, "", "Failed to start sidecar"),
        common.CommandResult(0, ps_output, ""),
        common.CommandResult(None, None, "timed out after 15 seconds"),
    ]

    res = self.executor.StartAndAwaitHealthy(timeout_sec=60)

    self.assertFalse(res.success)
    self.assertIn("sidecar", res.failed_services)
    self.assertIn("timed out after 15 seconds", res.failed_services["sidecar"])

  def testFindAllFailedServices(self):
    services_info = [
        {"Service": "s1", "State": "running", "Health": "healthy"},
        {"Service": "s2", "State": "running", "Health": "unhealthy"},
        {"Service": "s3", "State": "exited", "Health": ""},
        {"Service": "s4", "State": "dead", "Health": ""},
        {"Service": "s5", "State": "restarting", "Health": ""},
        {"Service": "s6", "State": "running", "Health": ""},
    ]

    failed = DockerComposeExecutor._FindAllFailedServices(services_info)
    failed_names = [s["Service"] for s in failed]

    self.assertEqual(failed_names, ["s2", "s3", "s4", "s5"])

  def testStop(self):
    self.mock_docker_context.Run.return_value = common.CommandResult(
        0, "Container stopped", ""
    )

    res = self.executor.Stop(remove_volumes=True, remove_orphans=True)

    self.assertTrue(res.success)
    self.mock_docker_context.Run.assert_called_once_with(
        [
            "compose",
            "-p",
            "my_proj",
            "--project-directory",
            "/path/to/project",
            "--env-file",
            "/path/to/compose.env",
            "--profile",
            "infra",
            "-f",
            "/path/to/compose.yaml",
            "down",
            "-v",
            "--remove-orphans",
        ],
        raise_on_failure=False,
        timeout=30,
    )

  def testCheckHealthy_allHealthy(self):
    ps_json = '[{"Service": "dialer", "State": "running", "Health": "healthy"}]'
    self.mock_docker_context.Run.return_value = common.CommandResult(
        0, ps_json, ""
    )

    res = self.executor.CheckHealthy()

    self.assertTrue(res.success)
    self.assertEqual(res.return_code, 0)

  def testCheckHealthy_noServicesRunning(self):
    self.mock_docker_context.Run.return_value = common.CommandResult(0, "", "")

    res = self.executor.CheckHealthy()

    self.assertFalse(res.success)
    self.assertIn("No compose services are running", res.error_message or "")

  def testCheckHealthy_unhealthyServiceDiagnosed(self):
    ps_json = (
        '[{"Service": "dialer", "State": "running", "Health": "unhealthy"}]'
    )
    self.mock_docker_context.Run.side_effect = [
        common.CommandResult(0, ps_json, ""),
        common.CommandResult(0, ps_json, ""),
        common.CommandResult(0, "dialer connection failed", ""),
    ]

    res = self.executor.CheckHealthy()

    self.assertFalse(res.success)
    self.assertIn("dialer", res.failed_services)
    self.assertIn("dialer connection failed", res.error_message or "")


class MttExecutorTest(absltest.TestCase):

  def setUp(self):
    super().setUp()
    self.mock_context = mock.create_autospec(
        command_util.CommandContext, instance=True
    )
    self.config = MttConfig(
        lab_config_path="staging/lab_config.yaml",
        network="mtt-net",
        image_name="asia-docker.pkg.dev/ats/ats:latest",
        extra_args=["--extra_flag"],
    )
    self.executor = MttExecutor(
        mtt_bin="/usr/bin/mtt",
        config=self.config,
        command_context=self.mock_context,
    )

  def testBuildBaseArgs(self):
    args = MttExecutor._BuildBaseArgs(self.config)
    self.assertEqual(
        args,
        [
            "--network",
            "mtt-net",
            "--image_name",
            "asia-docker.pkg.dev/ats/ats:latest",
            "--extra_flag",
            "staging/lab_config.yaml",
        ],
    )

  def testStartAndAwaitHealthy(self):
    self.mock_context.Run.return_value = common.CommandResult(
        0, "Lab started at http://localhost:8000", ""
    )

    res = self.executor.StartAndAwaitHealthy(timeout_sec=360)

    self.assertTrue(res.success)
    self.assertEqual(res.return_code, 0)
    self.mock_context.Run.assert_called_once_with(
        [
            "/usr/bin/mtt",
            "-vv",
            "start",
            "--network",
            "mtt-net",
            "--image_name",
            "asia-docker.pkg.dev/ats/ats:latest",
            "--extra_flag",
            "staging/lab_config.yaml",
        ],
        raise_on_failure=False,
        timeout=360,
    )

  def testStartAndAwaitHealthy_failureWithEmbeddedDockerLog(self):
    cli_output = (
        "INFO: Using image asia-docker.pkg.dev/ats/ats:latest\n"
        "DEBUG: Running command: ['docker', 'logs', 'mtt']\n"
        "DEBUG: stdout: intermediate log\n"
        "Traceback (most recent call last):\n"
        "  File 'cli.py', line 528, in Start\n"
        "RuntimeError: ATS replica failed to start in 300s with docker log:\n"
        "2026-08-17 09:00:00 [Main] Starting Lab Server...\n"
        "2026-08-17 09:01:00 [Worker] MariaDB connection failed"
    )
    self.mock_context.Run.return_value = common.CommandResult(1, "", cli_output)

    res = self.executor.StartAndAwaitHealthy(timeout_sec=360)

    self.assertFalse(res.success)
    self.assertEqual(res.return_code, 1)
    self.assertIn("mtt", res.failed_services)
    self.assertIn("mtt-cli", res.failed_services)
    # Check docker log extracted in full
    self.assertIn(
        "2026-08-17 09:00:00 [Main] Starting Lab Server...",
        res.failed_services["mtt"],
    )
    self.assertIn(
        "2026-08-17 09:01:00 [Worker] MariaDB connection failed",
        res.failed_services["mtt"],
    )
    # Check repetitive polling removed from mtt-cli
    self.assertNotIn("DEBUG: Running command", res.failed_services["mtt-cli"])
    self.assertIn(
        "RuntimeError: ATS replica failed to start",
        res.failed_services["mtt-cli"],
    )

  def testStartAndAwaitHealthy_failureCliOnly(self):
    cli_output = "ActionableError: Adb server port 5037 is not available."
    self.mock_context.Run.return_value = common.CommandResult(1, "", cli_output)

    res = self.executor.StartAndAwaitHealthy(timeout_sec=360)

    self.assertFalse(res.success)
    self.assertEqual(res.return_code, 1)
    self.assertNotIn("mtt", res.failed_services)
    self.assertIn("mtt-cli", res.failed_services)
    self.assertIn("Adb server port 5037", res.failed_services["mtt-cli"])

  def testStartAndAwaitHealthy_timeout(self):
    # A timed out Run has return_code=None and stdout=None. Reading those raw
    # would render the literal text "None" into the operator's diagnostics.
    self.mock_context.Run.return_value = common.CommandResult(
        None, None, "timed out after 360 seconds"
    )

    res = self.executor.StartAndAwaitHealthy(timeout_sec=360)

    self.assertFalse(res.success)
    self.assertEqual(res.return_code, 1)
    self.assertIn("mtt-cli", res.failed_services)
    self.assertIn("Exit code: 1", res.failed_services["mtt-cli"])
    self.assertNotIn("None", res.failed_services["mtt-cli"])

  def testFromConfigFiles(self):
    test_dir = tempfile.mkdtemp()
    try:
      flags_path = os.path.join(test_dir, "pinned_mtt_flags.yaml")
      lab_config_path = os.path.join(test_dir, "lab_config.yaml")
      with open(flags_path, "w", encoding="utf-8") as f:
        yaml.dump(
            {
                "image_ref": "gcr.io/proj/mtt-app@sha256:123456",
                "flags": ["--verbose"],
            },
            f,
        )
      with open(lab_config_path, "w", encoding="utf-8") as f:
        f.write("host: localhost\n")

      executor = MttExecutor.FromConfigFiles(
          lab_config_path=lab_config_path,
          pinned_mtt_flags_path=flags_path,
          network="mtt-net",
          mtt_bin="/usr/local/bin/mtt",
          command_context=self.mock_context,
      )

      self.assertEqual(executor._mtt_bin, "/usr/local/bin/mtt")
      self.assertEqual(executor._config.network, "mtt-net")
      # Passed through verbatim, never recombined with a repository name.
      self.assertEqual(
          executor._config.image_name, "gcr.io/proj/mtt-app@sha256:123456"
      )
      self.assertEqual(executor._config.extra_args, ["--verbose"])
      self.assertEqual(executor._config.lab_config_path, lab_config_path)
    finally:
      shutil.rmtree(test_dir, ignore_errors=True)

  def testFromConfigFiles_localImageId(self):
    # A locally built image has no RepoDigests, so the pinned reference is a
    # bare image ID. It must reach --image_name unchanged.
    test_dir = tempfile.mkdtemp()
    try:
      flags_path = os.path.join(test_dir, "pinned_mtt_flags.yaml")
      with open(flags_path, "w", encoding="utf-8") as f:
        yaml.dump({"image_ref": "sha256:abc123", "flags": []}, f)

      executor = MttExecutor.FromConfigFiles(
          pinned_mtt_flags_path=flags_path,
          command_context=self.mock_context,
      )

      self.assertEqual(executor._config.image_name, "sha256:abc123")
    finally:
      shutil.rmtree(test_dir, ignore_errors=True)


class MttStopExecutorTest(absltest.TestCase):

  def setUp(self):
    super().setUp()
    self.mock_context = mock.create_autospec(
        command_util.CommandContext, instance=True
    )
    self.executor = MttStopExecutor(
        mtt_bin="/usr/bin/mtt",
        command_context=self.mock_context,
    )

  def testStop_withDrain(self):
    self.mock_context.Run.return_value = common.CommandResult(
        0, "Lab stopped", ""
    )

    res = self.executor.Stop(drain=True, timeout_sec=60)

    self.assertTrue(res.success)
    self.mock_context.Run.assert_called_once_with(
        ["/usr/bin/mtt", "-vv", "stop", "--drain"],
        raise_on_failure=False,
        timeout=60,
    )

  def testStop_withoutDrain(self):
    self.mock_context.Run.return_value = common.CommandResult(
        0, "Lab stopped", ""
    )

    res = self.executor.Stop(drain=False, timeout_sec=60)

    self.assertTrue(res.success)
    self.mock_context.Run.assert_called_once_with(
        ["/usr/bin/mtt", "-vv", "stop"],
        raise_on_failure=False,
        timeout=60,
    )

  def testStop_noTimeoutByDefaultWithDrain(self):
    self.mock_context.Run.return_value = common.CommandResult(
        0, "Lab stopped", ""
    )

    res = self.executor.Stop(drain=True)

    self.assertTrue(res.success)
    self.mock_context.Run.assert_called_once_with(
        ["/usr/bin/mtt", "-vv", "stop", "--drain"],
        raise_on_failure=False,
        timeout=None,
    )

  def testStop_noTimeoutByDefaultWithoutDrain(self):
    # `mtt stop` waits up to 600s for the container to exit before force
    # killing it. The wrapper used to allow 60s, so it killed `mtt stop`
    # part-way through a shutdown that was working.
    self.mock_context.Run.return_value = common.CommandResult(
        0, "Lab stopped", ""
    )

    res = self.executor.Stop()

    self.assertTrue(res.success)
    self.mock_context.Run.assert_called_once_with(
        ["/usr/bin/mtt", "-vv", "stop"],
        raise_on_failure=False,
        timeout=None,
    )

  def testStop_failureReportsReturnCode(self):
    self.mock_context.Run.return_value = common.CommandResult(
        1, "", "no such container"
    )

    res = self.executor.Stop()

    self.assertFalse(res.success)
    self.assertEqual(res.return_code, 1)


if __name__ == "__main__":
  absltest.main()
