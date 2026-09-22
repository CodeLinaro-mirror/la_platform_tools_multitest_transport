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

"""Process execution data plane for MTT Node.

Provides execution adapters for Docker Compose infrastructure services and
MTT application containers.
"""

import dataclasses
import json
import logging
import os
import re
from typing import Any, Optional, Sequence
from multitest_transport.cli import command_util
from multitest_transport.cli import common
import yaml

logger = logging.getLogger(__name__)


@dataclasses.dataclass(frozen=True)
class DockerComposeConfig:
  """Immutable configuration data for Docker Compose."""

  compose_files: Sequence[str] = ()
  env_file: Optional[str] = None
  project_name: Optional[str] = None
  project_dir: Optional[str] = None
  profiles: Sequence[str] = ()


@dataclasses.dataclass(frozen=True)
class MttConfig:
  """Immutable configuration data for MTT application execution."""

  lab_config_path: Optional[str] = None
  network: Optional[str] = None
  image_name: Optional[str] = None
  extra_args: Sequence[str] = ()


@dataclasses.dataclass
class ExecutionResult:
  """Structured outcome of a process execution or health verification."""

  command_result: common.CommandResult
  failed_services: dict[str, str] = dataclasses.field(default_factory=dict)

  @property
  def success(self) -> bool:
    return self.command_result.return_code == 0

  @property
  def return_code(self) -> int:
    """Returns the process exit code.

    An unset (None) return code denotes a command that never produced an exit
    status, which `success` already treats as a failure. Reporting 1 instead of
    0 keeps `return_code` consistent with `success`.

    Returns:
      The command exit code, or 1 if the underlying return code is unset.
    """
    if self.command_result.return_code is None:
      return 1
    return self.command_result.return_code

  @property
  def stdout(self) -> str:
    return self.command_result.stdout or ""

  @property
  def stderr(self) -> str:
    return self.command_result.stderr or ""

  @property
  def error_message(self) -> Optional[str]:
    if self.success:
      return None
    if self.failed_services:
      details = "; ".join(
          f"{svc}: {log.strip()}" for svc, log in self.failed_services.items()
      )
      return f"Execution failed: {details}"
    return (
        self.stderr.strip()
        or self.stdout.strip()
        or f"Command failed with return code {self.return_code}"
    )


class Error(Exception):
  """Base error for process execution failures."""


class DockerComposeExecutor:
  """Executes docker compose infrastructure lifecycle commands and monitors health."""

  def __init__(
      self,
      config: Optional[DockerComposeConfig] = None,
      docker_context: Optional[command_util.DockerContext] = None,
  ):
    self._config = config or DockerComposeConfig()
    self._docker_context = docker_context or command_util.DockerContext(
        command_util.CommandContext(), login=False
    )

  @staticmethod
  def _BuildBaseArgs(config: DockerComposeConfig) -> list[str]:
    """Converts a DockerComposeConfig into base docker compose arguments."""
    args = ["compose"]
    if config.project_name:
      args.extend(["-p", config.project_name])
    if config.project_dir:
      args.extend(["--project-directory", config.project_dir])
    if config.env_file:
      args.extend(["--env-file", config.env_file])
    for profile in config.profiles:
      args.extend(["--profile", profile])
    for compose_file in config.compose_files:
      args.extend(["-f", compose_file])
    return args

  def _Up(
      self,
      detach: bool = True,
      wait: bool = False,
      wait_timeout_sec: Optional[int] = None,
      pull: Optional[str] = None,
      services: Sequence[str] = (),
      timeout_sec: int = 60,
  ) -> common.CommandResult:
    """Pure CLI wrapper for `docker compose up`."""
    args = self._BuildBaseArgs(self._config) + ["up"]
    if detach:
      args.append("-d")
    if wait:
      args.append("--wait")
      if wait_timeout_sec:
        args.extend(["--wait-timeout", str(wait_timeout_sec)])
    if pull:
      args.extend(["--pull", pull])
    if services:
      args.extend(services)

    logger.info("Running docker compose up: %s", " ".join(args))
    return self._docker_context.Run(
        args, raise_on_failure=False, timeout=timeout_sec
    )

  def _Down(
      self,
      remove_volumes: bool = False,
      remove_orphans: bool = False,
      timeout_sec: int = 30,
  ) -> common.CommandResult:
    """Pure CLI wrapper for `docker compose down`."""
    args = self._BuildBaseArgs(self._config) + ["down"]
    if remove_volumes:
      args.append("-v")
    if remove_orphans:
      args.append("--remove-orphans")

    logger.info("Running docker compose down: %s", " ".join(args))
    return self._docker_context.Run(
        args, raise_on_failure=False, timeout=timeout_sec
    )

  def _Logs(self, service: str, tail: int = 50) -> str:
    """Pure CLI wrapper for `docker compose logs --tail`."""
    args = self._BuildBaseArgs(self._config) + [
        "logs",
        "--tail",
        str(tail),
        service,
    ]
    res = self._docker_context.Run(args, raise_on_failure=False, timeout=15)
    # Wrapped rather than read directly: on timeout `Run` returns stdout=None,
    # and this runs on an already-unhealthy host where that timeout is likely.
    result = ExecutionResult(command_result=res)
    return result.stdout.strip() or result.stderr.strip()

  def _Ps(
      self,
      all_containers: bool = True,
      services: Sequence[str] = (),
  ) -> list[dict[str, Any]]:
    """Executes `docker compose ps [--all] --format json`."""
    args = self._BuildBaseArgs(self._config) + ["ps", "--format", "json"]
    if all_containers:
      args.append("--all")
    if services:
      args.extend(services)

    res = self._docker_context.Run(args, raise_on_failure=False, timeout=15)
    if res.return_code != 0 or not res.stdout.strip():
      return []

    services_list = []
    raw = res.stdout.strip()
    try:
      parsed = json.loads(raw)
      if isinstance(parsed, list):
        services_list.extend(parsed)
      elif isinstance(parsed, dict):
        services_list.append(parsed)
    except json.JSONDecodeError:
      for line in raw.splitlines():
        line = line.strip()
        if line:
          try:
            services_list.append(json.loads(line))
          except json.JSONDecodeError:
            pass
    return services_list

  @staticmethod
  def _FindAllFailedServices(
      services_info: Sequence[dict[str, Any]],
  ) -> list[dict[str, Any]]:
    """Filters and returns all services that are unhealthy or not running.

    A service that declares no container healthcheck reports no `Health`, and
    passes on `State == "running"` alone.
    """
    failed = []
    for s in services_info:
      state = s.get("State", "").lower()
      health = s.get("Health", "").lower()
      if (health and health != "healthy") or state != "running":
        failed.append(s)
    return failed

  def _DiagnoseFailure(
      self, services: Sequence[str] = (), tail: int = 50
  ) -> dict[str, str]:
    """Diagnoses failed services and returns mapping of service name -> status & logs."""
    all_services = self._Ps(all_containers=True, services=services)
    failed_services = self._FindAllFailedServices(all_services)

    diagnostics: dict[str, str] = {}
    for s in failed_services:
      svc_name = s.get("Service") or s.get("Name", "unknown")
      state = s.get("State", "")
      health = s.get("Health", "")
      logs = self._Logs(svc_name, tail=tail)

      status_str = f"state={state}" + (f", health={health}" if health else "")
      log_content = logs or "<no logs available>"
      diagnostics[svc_name] = (
          f"Status: {status_str}\nLogs (tail {tail}):\n{log_content}"
      )

    if not diagnostics and services:
      for svc_name in services:
        logs = self._Logs(svc_name, tail=tail)
        diagnostics[svc_name] = logs or "<no logs available>"

    return diagnostics

  def CheckHealthy(self, services: Sequence[str] = ()) -> ExecutionResult:
    """Checks whether all running compose services are healthy via `ps`.

    Unlike `StartAndAwaitHealthy`, this inspects existing containers without
    starting, recreating, or waiting on them.

    Args:
      services: Optional subset of service names to inspect.

    Returns:
      An ExecutionResult with success=True only when compose reports at least
      one service and none are stopped or unhealthy.
    """
    all_services = self._Ps(all_containers=True, services=services)
    if not all_services:
      return ExecutionResult(
          command_result=common.CommandResult(
              1, "", "No compose services are running"
          ),
      )

    failed = self._FindAllFailedServices(all_services)
    if failed:
      failed_services = self._DiagnoseFailure(services=services)
      return ExecutionResult(
          command_result=common.CommandResult(
              1, "", "Compose services are unhealthy"
          ),
          failed_services=failed_services,
      )

    return ExecutionResult(
        command_result=common.CommandResult(0, "", ""),
    )

  def StartAndAwaitHealthy(
      self,
      timeout_sec: int = 120,
      wait_timeout_sec: Optional[int] = None,
      pull: Optional[str] = None,
      services: Sequence[str] = (),
  ) -> ExecutionResult:
    """Starts compose services and blocks until healthy via `--wait`."""
    cmd_res = self._Up(
        detach=True,
        wait=True,
        wait_timeout_sec=wait_timeout_sec,
        pull=pull,
        services=services,
        timeout_sec=timeout_sec,
    )
    failed_services = {}
    if cmd_res.return_code != 0:
      failed_services = self._DiagnoseFailure(services=services)

    return ExecutionResult(
        command_result=cmd_res,
        failed_services=failed_services,
    )

  def Stop(
      self,
      remove_volumes: bool = False,
      remove_orphans: bool = False,
      timeout_sec: int = 30,
  ) -> ExecutionResult:
    """Stops and tears down compose services."""
    cmd_res = self._Down(
        remove_volumes=remove_volumes,
        remove_orphans=remove_orphans,
        timeout_sec=timeout_sec,
    )
    return ExecutionResult(
        command_result=cmd_res,
    )

  @classmethod
  def FromConfigFiles(
      cls,
      env_file: Optional[str] = None,
      project_dir: Optional[str] = None,
      compose_files: Sequence[str] = (),
      profiles: Sequence[str] = (),
      project_name: Optional[str] = None,
      docker_context: Optional[command_util.DockerContext] = None,
  ) -> "DockerComposeExecutor":
    """Constructs a DockerComposeExecutor from explicit configuration parameters."""
    config = DockerComposeConfig(
        env_file=env_file,
        project_dir=project_dir,
        compose_files=tuple(compose_files),
        profiles=tuple(profiles),
        project_name=project_name,
    )
    return cls(config=config, docker_context=docker_context)


_DOCKER_LOG_MARKERS = (
    re.compile(
        r"ATS replica failed to start in \d+s with docker log:\s*",
        re.IGNORECASE,
    ),
    re.compile(
        r"ATS failed to start with exception:\s*",
        re.IGNORECASE,
    ),
    re.compile(
        r"ATS server failed to start in \d+s(?:\s+with docker log:)?\s*",
        re.IGNORECASE,
    ),
)


# Timeout in seconds for MTT startup and restart. In cli.py, mtt start/restart
# polls container readiness for up to 300s (_MTT_SERVER_WAIT_TIME_SECONDS).
# We allow 360s to provide sufficient margin for cli.py to complete its checks.
_DEFAULT_MTT_TIMEOUT_SEC = 360


class MttExecutor:
  """Executes MTT application lifecycle commands."""

  def __init__(
      self,
      mtt_bin: str = "mtt",
      config: Optional[MttConfig] = None,
      command_context: Optional[command_util.CommandContext] = None,
  ):
    self._mtt_bin = mtt_bin
    self._config = config or MttConfig()
    self._cmd_context = command_context or command_util.CommandContext()

  @staticmethod
  def _BuildBaseArgs(config: MttConfig) -> list[str]:
    """Translates MttConfig into CLI arguments."""
    args = []
    if config.network:
      args.extend(["--network", config.network])
    if config.image_name:
      args.extend(["--image_name", config.image_name])
    if config.extra_args:
      args.extend(config.extra_args)
    if config.lab_config_path:
      args.append(config.lab_config_path)
    return args

  @staticmethod
  def _SeparateCliAndDockerLogs(
      raw_output: str,
  ) -> tuple[str, Optional[str]]:
    """Separates mtt CLI logs and embedded docker container logs."""
    docker_log = None
    cli_log = raw_output

    for marker in _DOCKER_LOG_MARKERS:
      match = marker.search(raw_output)
      if match:
        cli_log = raw_output[: match.end()].strip()
        docker_log = raw_output[match.end() :].strip()
        break

    cleaned_lines = [
        line
        for line in cli_log.splitlines()
        if not (
            (
                "running command:" in line.lower()
                and ("'logs'" in line.lower() or '"logs"' in line.lower())
            )
            or line.lower().startswith("stdout:")
            or line.lower().startswith("stderr:")
        )
    ]
    cleaned_cli_log = "\n".join(cleaned_lines).strip()
    return (cleaned_cli_log or cli_log, docker_log)

  def _Start(
      self, timeout_sec: int = _DEFAULT_MTT_TIMEOUT_SEC
  ) -> common.CommandResult:
    """Pure CLI wrapper for `mtt -vv start`."""
    args = [self._mtt_bin, "-vv", "start"] + self._BuildBaseArgs(self._config)
    logger.info("Executing MTT start: %s", " ".join(args))
    return self._cmd_context.Run(
        args, raise_on_failure=False, timeout=timeout_sec
    )

  def _EvaluateResult(self, cmd_res: common.CommandResult) -> ExecutionResult:
    """Wraps CommandResult into ExecutionResult and extracts diagnostics on failure."""
    # Note: `mtt start` in cli.py already blocks and polls internal container
    # readiness / health for up to 300s. Therefore, a return code of 0
    # indicates the application is healthy and ready.
    result = ExecutionResult(command_result=cmd_res)
    failed_services = {}

    if not result.success:
      combined_output = f"{result.stderr}\n{result.stdout}".strip()
      cleaned_cli_log, docker_log = self._SeparateCliAndDockerLogs(
          combined_output
      )
      if docker_log:
        failed_services["mtt"] = docker_log
      failed_services["mtt-cli"] = (
          f"Exit code: {result.return_code}\nCLI Log:\n{cleaned_cli_log}"
      )

    return ExecutionResult(
        command_result=cmd_res,
        failed_services=failed_services,
    )

  def StartAndAwaitHealthy(
      self, timeout_sec: int = _DEFAULT_MTT_TIMEOUT_SEC
  ) -> ExecutionResult:
    """Starts MTT and awaits healthiness (via mtt start)."""
    cmd_res = self._Start(timeout_sec=timeout_sec)
    return self._EvaluateResult(cmd_res)

  @classmethod
  def FromConfigFiles(
      cls,
      lab_config_path: Optional[str] = None,
      pinned_mtt_flags_path: Optional[str] = None,
      network: str = "mtt-net",
      mtt_bin: str = "mtt",
      command_context: Optional[command_util.CommandContext] = None,
  ) -> "MttExecutor":
    """Constructs an MttExecutor configured from explicit config file paths."""
    image_ref = ""
    flags = []
    if pinned_mtt_flags_path and os.path.exists(pinned_mtt_flags_path):
      try:
        with open(pinned_mtt_flags_path, "r", encoding="utf-8") as f:
          data = yaml.safe_load(f) or {}
        image_ref = data.get("image_ref", "")
        flags = data.get("flags", [])
      except (OSError, yaml.YAMLError) as e:
        logger.warning(
            "Failed to load flags from %s: %s", pinned_mtt_flags_path, e
        )

    # image_ref is already a complete reference (repo@sha256:... or a bare
    # local image ID) and is passed through untouched. Reconstructing it from
    # separate name and digest parts is what produced malformed references
    # such as `repo/mtt@repo/mtt@sha256:...`.
    config = MttConfig(
        network=network,
        image_name=image_ref or None,
        extra_args=flags,
        lab_config_path=(
            lab_config_path
            if (lab_config_path and os.path.exists(lab_config_path))
            else None
        ),
    )
    return cls(
        mtt_bin=mtt_bin,
        config=config,
        command_context=command_context,
    )


class MttStopExecutor:
  """Executes `mtt stop`.

  Stopping is deliberately separated from MttExecutor: `mtt stop` addresses the
  container by name and needs no lab config, image reference or flags. Keeping
  it config-free allows stopping a container that was started outside the node
  framework, e.g. by the legacy `mtt start` CLI.
  """

  def __init__(
      self,
      mtt_bin: str = "mtt",
      command_context: Optional[command_util.CommandContext] = None,
  ):
    self._mtt_bin = mtt_bin
    self._cmd_context = command_context or command_util.CommandContext()

  def Stop(
      self, drain: bool = False, timeout_sec: Optional[int] = None
  ) -> ExecutionResult:
    """Stops the MTT application container.

    No timeout is imposed by default. `mtt stop` already bounds its own waits
    and force-kills the container at the end of them, so a second, smaller
    budget here could only interrupt a shutdown that was working: it sends TERM
    to TF, then waits up to 600s for the container to exit (3600s for a
    graceful shutdown). The wrapper previously allowed 60s, killing `mtt stop`
    part-way through and leaving the container in an unknown state.

    Args:
      drain: Wait for in-flight test runs to finish before stopping.
      timeout_sec: Kill `mtt stop` after this many seconds. None, the default,
        lets it manage its own budget. Only set this above the budget above,
        or the same failure returns.

    Returns:
      The result of the `mtt stop` invocation.
    """
    args = [self._mtt_bin, "-vv", "stop"]
    if drain:
      args.append("--drain")
    logger.info("Executing MTT stop: %s", " ".join(args))
    cmd_res = self._cmd_context.Run(
        args, raise_on_failure=False, timeout=timeout_sec
    )
    return ExecutionResult(command_result=cmd_res)

