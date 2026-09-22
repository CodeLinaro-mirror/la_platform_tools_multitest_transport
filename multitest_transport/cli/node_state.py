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

"""Control plane for MTT Node.

A node runs two groups of services: the tunnel sidecars and the MTT core
container. The control plane observes both groups, decides the whole plan, and
only then acts, through Data Plane abstractions (`node_config`,
`ReleaseDirectoryManager`, `DockerImageExecutor`, `DockerComposeExecutor`,
`MttExecutor`, `MttStopExecutor`).

The module is organized in three kinds of code:

  * Observations (`ObserveTunnel`, `ObserveCore`, `EvaluateCoreRecoverable`)
    change nothing and are never journaled. Nothing else probes Docker.
  * Blocks (`@Block`) are the basic steps. A setup block touches disk or the
    registry; a service block moves exactly one group in one direction.
  * Pipelines (`@Pipeline`) are the commands. They compose blocks, and abort on
    the first failure without undoing anything already done.

No condition is stored: `journal.json` records what the most recent pipeline
did, never what the node is.
"""

import dataclasses
import datetime
import enum
import functools
import json
import logging
import os
import sys
from typing import Any, Callable, NoReturn, Optional
import uuid
from multitest_transport.cli import compose_directory
from multitest_transport.cli import docker_image
from multitest_transport.cli import host_env as host_env_lib
from multitest_transport.cli import node_config
from multitest_transport.cli import node_permissions
from multitest_transport.cli import process_executor
from multitest_transport.cli import release_directory
import yaml

logger = logging.getLogger(__name__)

_JOURNAL_FILENAME = "journal.json"
_CORE_CONTAINER_NAME = "mtt"

_ENV_OVERLAY_COMPOSE_FILES: dict[str, str] = {
    host_env_lib.HostEnvironment.GCE.value: "docker-compose.gce.yml",
}


class TerminalAbortError(Exception):
  """Raised internally to immediately abort pipeline execution on failure."""


class NodeRole(enum.Enum):
  """Operational roles for MTT Node."""

  WORKER = "worker"
  CONTROLLER = "controller"


class TunnelCondition(enum.Enum):
  """What the tunnel sidecars are doing.

  There is no version condition. `start` and `restart` leave a HEALTHY tunnel
  alone; only `tunnel upgrade` recreates it (`docker compose up -d --wait --pull
  always`).
  """

  DOWN = "down"
  HEALTHY = "healthy"


class CoreCondition(enum.Enum):
  """What the core container is doing, relative to a candidate image.

  The core is classified, unlike the tunnel, because stopping it ends running
  tests: the question has to be settled before acting. With no candidate to
  compare against, a running core reports UP_CURRENT; there is nothing it could
  be stale against.
  """

  DOWN = "down"
  UP_STALE = "up_stale"
  UP_CURRENT = "up_current"

  @property
  def is_up(self) -> bool:
    return self is not CoreCondition.DOWN


class _Release(enum.Enum):
  """Which of the two release pointers a core block operates on."""

  STAGING = "staging"
  ACTIVE = "active"


@dataclasses.dataclass
class BlockResult:
  """Result returned by every block."""

  success: bool
  error_message: Optional[str] = None
  failed_services: dict[str, str] = dataclasses.field(default_factory=dict)

  def __bool__(self) -> bool:
    return self.success


@dataclasses.dataclass(frozen=True)
class NodeStatus:
  """What `status` observed, one entry per service group."""

  tunnel: TunnelCondition
  core: CoreCondition


def _Now() -> str:
  """Returns the current UTC time as an ISO-8601 string."""
  return datetime.datetime.now(datetime.timezone.utc).isoformat(
      timespec="seconds"
  )


def Block(func: Callable[..., BlockResult]) -> Callable[..., BlockResult]:
  """Marks a basic step and appends its outcome to the journal.

  Takes no arguments: a block reports what happened, it does not declare where
  the node ended up. An uncaught exception is converted into a failed
  BlockResult so that the pipeline, not the stack, decides what happens next.

  Args:
    func: The block method, which must return a BlockResult.

  Returns:
    The wrapped block method.
  """

  @functools.wraps(func)
  def Wrapper(self: Any, *args: Any, **kwargs: Any) -> BlockResult:
    
    name = getattr(func, "__name__", str(func)).lstrip("_")
    started_at = _Now()
    try:
      res = func(self, *args, **kwargs)
    except Exception as e:  
      logger.exception("Uncaught exception in block %s: %s", name, e)
      res = BlockResult(
          False, error_message=f"Unexpected {type(e).__name__} in {name}: {e}"
      )
    self._RecordBlock(name, started_at, res)
    return res

  return Wrapper


def Pipeline(func: Callable[..., bool]) -> Callable[..., bool]:
  """Marks a command, and opens and closes its journal.

  Clears the journal of the previous run, catches TerminalAbortError, and
  writes the closing outcome entry.

  Args:
    func: The pipeline method, which must return a bool.

  Returns:
    The wrapped pipeline method.
  """

  @functools.wraps(func)
  def Wrapper(self: Any, *args: Any, **kwargs: Any) -> bool:
    
    name = getattr(func, "__name__", str(func))
    self._OpenJournal(name)
    success = False
    try:
      success = func(self, *args, **kwargs)
    except TerminalAbortError:
      success = False
    finally:
      self._CloseJournal(success)
    return success

  return Wrapper


class NodeStateManager:
  """Control plane coordinating the tunnel and the core."""

  def __init__(
      self,
      base_dir: str = ".",
      static_dir: str = "/etc/mtt",
      release_mgr: Optional[release_directory.ReleaseDirectoryManager] = None,
      compose_mgr: Optional[compose_directory.ComposeDirectoryManager] = None,
      image_executor: Optional[docker_image.DockerImageExecutor] = None,
      role: NodeRole = NodeRole.WORKER,
      host_env: Optional[host_env_lib.HostEnvironment] = None,
      mtt_cli_path: Optional[str] = None,
  ):
    self._base_dir = os.path.abspath(base_dir)
    self._static_dir = os.path.abspath(static_dir)
    self._journal_file = os.path.join(self._base_dir, _JOURNAL_FILENAME)
    self._release_mgr = release_mgr or (
        release_directory.ReleaseDirectoryManager(self._base_dir)
    )
    self._compose_mgr = compose_mgr or (
        compose_directory.ComposeDirectoryManager(self._base_dir)
    )
    self._image_executor = image_executor or docker_image.DockerImageExecutor()
    self._role = role
    self._host_env = host_env
    self._mtt_cli_path = mtt_cli_path or "mtt"
    self._candidate_image_ref: Optional[str] = None
    self._journal: Optional[dict[str, Any]] = None

  @property
  def base_dir(self) -> str:
    return self._base_dir

  @property
  def static_dir(self) -> str:
    return self._static_dir

  @property
  def journal_file(self) -> str:
    return self._journal_file

  @property
  def release_manager(self) -> release_directory.ReleaseDirectoryManager:
    return self._release_mgr

  @property
  def compose_manager(self) -> compose_directory.ComposeDirectoryManager:
    return self._compose_mgr

  @property
  def role(self) -> NodeRole:
    return self._role

  @property
  def host_env(self) -> Optional[host_env_lib.HostEnvironment]:
    return self._host_env

  @property
  def mtt_cli_path(self) -> str:
    return self._mtt_cli_path

  # ==========================================================================
  # Journal
  # ==========================================================================

  def _OpenJournal(self, command: str) -> None:
    """Starts a journal for a pipeline, discarding the previous run's."""
    self._journal = {
        "command": command,
        "started_at": _Now(),
        "steps": [],
    }
    self._WriteJournal()

  def _RecordBlock(
      self, name: str, started_at: str, res: BlockResult
  ) -> None:
    """Appends one block's outcome to the open journal."""
    if not res.success:
      summary = (res.error_message or "step failed").splitlines()[0]
      logger.error("Step %s failed: %s", name, summary)
    if self._journal is None:
      return
    step: dict[str, Any] = {
        "step": name,
        "started_at": started_at,
        "finished_at": _Now(),
        "success": res.success,
    }
    if res.error_message:
      step["error_message"] = res.error_message
    if res.failed_services:
      step["failed_services"] = res.failed_services
    self._journal["steps"].append(step)
    self._WriteJournal()

  def _CloseJournal(self, success: bool) -> None:
    """Writes the pipeline's outcome and closes the journal."""
    if self._journal is None:
      return
    command = self._journal.get("command", "Command")
    failed_steps = [
        s["step"]
        for s in self._journal.get("steps", [])
        if not s.get("success", True)
    ]
    self._journal["finished_at"] = _Now()
    self._journal["success"] = success
    # Only on failure. A recursive walk of both trees is pure cost when the
    # command did what it was asked to do.
    drift = (
        node_permissions.DetectDrift(self._static_dir, self._base_dir)
        if not success
        else []
    )
    if drift:
      self._journal["permission_drift"] = drift
    written = self._WriteJournal()
    self._journal = None
    if success:
      logger.info("%s completed successfully.", command)
    else:
      step_info = f" at step {', '.join(failed_steps)}" if failed_steps else ""
      if written:
        logger.error(
            "%s failed%s. See journal for full details: %s",
            command,
            step_info,
            self._journal_file,
        )
      else:
        logger.error("%s failed%s.", command, step_info)
    if drift:
      self._ReportDrift(drift, journal_written=written)

  def _ReportDrift(
      self, drift: list[dict[str, Any]], journal_written: bool
  ) -> None:
    """Points the operator at the drift, or dumps it when it cannot be filed."""
    repair = f"Repair with: sudo mtt node {self._role.value} init"
    if journal_written:
      print(
          f"WARNING: {len(drift)} filesystem permission differences were"
          f" recorded in {self._journal_file}.\n{repair}",
          file=sys.stderr,
      )
      return
    # A pointer to a file that was never written is worse than no pointer, so
    # the table goes straight to the terminal instead.
    print(
        f"ERROR: cannot write {self._journal_file}.\n"
        + node_permissions.FormatDrift(drift, self._role.value),
        file=sys.stderr,
    )

  def _WriteJournal(self) -> bool:
    """Rewrites journal.json atomically, so a reader never sees a partial file.

    Returns:
      True if the journal now reflects the in-memory state.
    """
    if self._journal is None:
      return False
    temp_file = f"{self._journal_file}.tmp.{os.getpid()}_{uuid.uuid4().hex[:6]}"
    try:
      with open(temp_file, "w", encoding="utf-8") as f:
        json.dump(self._journal, f, indent=2)
      os.chmod(temp_file, node_permissions.BASE_FILE_MODE)
      os.replace(temp_file, self._journal_file)
      return True
    except OSError:
      # The journal is a report, not a dependency: losing it must not fail a
      # pipeline that is otherwise able to run.
      logger.exception("Failed to write journal: %s", self._journal_file)
      if os.path.exists(temp_file):
        try:
          os.remove(temp_file)
        except OSError:
          pass
      return False

  # ==========================================================================
  # Observations (never journaled)
  # ==========================================================================

  def ObserveTunnel(self) -> TunnelCondition:
    """Reports whether the tunnel sidecars are up and healthy.

    Returns:
      DOWN when the tunnel was never started on this node, or when compose
      reports no service or an unhealthy one.
    """
    env_path = self._release_mgr.tunnel_compose_env_path
    if not os.path.exists(env_path):
      # No applied environment was ever recorded, so no compose project of
      # ours exists to inspect.
      return TunnelCondition.DOWN
    res = self._GetTunnelComposeExecutor(env_path).CheckHealthy()
    return TunnelCondition.HEALTHY if res.success else TunnelCondition.DOWN

  def ObserveCore(self, candidate: Optional[str] = None) -> CoreCondition:
    """Reports what the core container is running, against a candidate image.

    Args:
      candidate: Image reference the core is expected to run, or None when the
        caller has nothing to compare against.

    Returns:
      DOWN, UP_STALE or UP_CURRENT. Without a candidate, a running healthy core
      is UP_CURRENT; a stopped or unhealthy core is DOWN.
    """
    status = self._image_executor.GetContainerStatus(_CORE_CONTAINER_NAME)
    if status != docker_image.ContainerStatus.HEALTHY:
      return CoreCondition.DOWN
    if not candidate:
      return CoreCondition.UP_CURRENT
    if self._image_executor.DoesContainerMatchImage(
        _CORE_CONTAINER_NAME, candidate
    ):
      return CoreCondition.UP_CURRENT
    return CoreCondition.UP_STALE

  def EvaluateCoreRecoverable(self, failed_services: dict[str, str]) -> bool:
    """Judges whether rolling back could plausibly fix a core failure.

    Currently a placeholder that always reports the failure as recoverable, so
    a caller with rollback enabled always attempts it.

    TODO: Inspect failed_services to distinguish candidate
    specific application faults (recoverable via rollback) from host
    environment failures such as a missing Docker daemon or exhausted disk,
    which rollback cannot fix.

    Args:
      failed_services: Diagnostics from the failed core start.

    Returns:
      True while the classification is unimplemented.
    """
    del failed_services
    return True

  def GetStatus(self) -> NodeStatus:
    """Observes both groups, writing nothing.

    It does read: ObserveTunnel stats <base_dir>/tunnel/docker-compose.env and,
    when it is there, reads that env and the compose files. os.path.exists
    reports EACCES as False, so a caller who cannot traverse base_dir is told
    the tunnel is DOWN rather than that they lack access. The CLI therefore
    gates `status` on group membership like every other command.

    Returns:
      The observed tunnel and core conditions.
    """
    return NodeStatus(tunnel=self.ObserveTunnel(), core=self.ObserveCore())

  # ==========================================================================
  # Setup blocks (touch disk or the registry, move no service)
  # ==========================================================================

  def _ValidateWorkerEnv(
      self, env: dict[str, str], env_path: str
  ) -> BlockResult:
    """Validates the materialized compose env for a worker.

    Args:
      env: Parsed contents of the materialized config docker-compose.env.
      env_path: Path the env was read from, for error messages.

    Returns:
      A failed BlockResult when ACCEPTOR_TARGET is missing or empty.
    """
    # A worker runs the `dialer`, whose --acceptor_target is bound directly to
    # ACCEPTOR_TARGET with no fallback. Compose would substitute an empty
    # string and start the container with a useless target, so reject it here
    # instead, before anything is pulled, staged, or stopped.
    if not env.get("ACCEPTOR_TARGET"):
      return BlockResult(
          False,
          error_message=(
              f"Missing ACCEPTOR_TARGET in {env_path}. A worker requires the"
              " DualConduit acceptor URL; set it with `mtt node worker init"
              " --dcon_acceptor_target=...` or re-run `mtt node worker join`."
          ),
      )
    return BlockResult(True)

  def _ValidateControllerEnv(
      self, env: dict[str, str], env_path: str
  ) -> BlockResult:
    """Validates the materialized compose env for a controller.

    Args:
      env: Parsed contents of the materialized config docker-compose.env.
      env_path: Path the env was read from, for error messages.

    Returns:
      A failed BlockResult when DCON_ACCEPTOR_ADDR does not agree with the host
      environment.
    """
    # The controller's acceptor is reached through the Cloud Endpoints proxy,
    # which only exists on GCP. `node_init` enforces the same pairing, but the
    # config is editable afterwards, so re-check what was actually
    # materialized.
    is_gcp = bool(self._host_env and self._host_env.IsGcp())
    acceptor_addr = env.get("DCON_ACCEPTOR_ADDR")
    if is_gcp and not acceptor_addr:
      return BlockResult(
          False,
          error_message=(
              f"Missing DCON_ACCEPTOR_ADDR in {env_path}. A controller on GCP"
              " serves the DualConduit acceptor through the Cloud Endpoints"
              " proxy, which needs the service name; re-run `mtt node"
              " controller init --dcon_acceptor_addr=...`."
          ),
      )
    if acceptor_addr and not is_gcp:
      return BlockResult(
          False,
          error_message=(
              f"DCON_ACCEPTOR_ADDR is set in {env_path} but this host is not"
              " on GCP. The Cloud Endpoints proxy is a GCP-only service and"
              " will not be started, so the address would be silently"
              " ignored."
          ),
      )
    return BlockResult(True)

  @Block
  def _MaterializeAndValidateConfig(self) -> BlockResult:
    """Materializes and validates configuration from static_dir to config_dir."""
    try:
      node_config.MaterializeNodeConfig(
          static_dir=self._static_dir,
          var_config_dir=self._release_mgr.config_dir,
      )
    except Exception as e:  
      logger.exception("Failed to materialize node configuration: %s", e)
      return BlockResult(False, error_message=str(e))

    flags_path = self._release_mgr.config_flags_path
    if not os.path.exists(flags_path):
      return BlockResult(
          False,
          error_message=f"Missing config mtt_flags.yaml at {flags_path}",
      )

    env_path = self._release_mgr.config_compose_env_path
    if not os.path.exists(env_path):
      return BlockResult(
          False,
          error_message=f"Missing config docker-compose.env at {env_path}",
      )
    env = self._ReadComposeEnv(env_path)

    if self._role == NodeRole.WORKER:
      return self._ValidateWorkerEnv(env, env_path)
    if self._role == NodeRole.CONTROLLER:
      return self._ValidateControllerEnv(env, env_path)
    return BlockResult(
        False, error_message=f"Unsupported node role: {self._role}"
    )

  def _ResolveServiceAccountKeyPath(
      self, config_flags: Optional[dict[str, Any]] = None
  ) -> Optional[str]:
    """Returns the service account JSON key path if configured or provisioned."""
    if config_flags is None and os.path.exists(
        self._release_mgr.config_flags_path
    ):
      try:
        with open(
            self._release_mgr.config_flags_path, "r", encoding="utf-8"
        ) as f:
          loaded = yaml.safe_load(f)
          config_flags = loaded if isinstance(loaded, dict) else {}
      except (OSError, yaml.YAMLError):
        config_flags = {}

    if not isinstance(config_flags, dict):
      config_flags = {}

    configured = config_flags.get("service_account_json_key_path")
    if configured:
      return str(configured)

    flags_list = config_flags.get("flags")
    if isinstance(flags_list, list):
      for idx, flag in enumerate(flags_list):
        flag_str = str(flag).strip()
        if flag_str.startswith("--service_account_json_key_path="):
          val = flag_str.split("=", 1)[1].strip()
          if val:
            return val
        elif (
            flag_str == "--service_account_json_key_path"
            and idx + 1 < len(flags_list)
        ):
          val = str(flags_list[idx + 1]).strip()
          if val:
            return val

    default_key = os.path.join(self._static_dir, "secrets", "sa-key.json")
    if os.path.isfile(default_key):
      return default_key
    return None

  def _ResolveTunnelRepo(self) -> str:
    """Returns the DCON_REPO configured in docker-compose.env, or its default."""
    env = self._ReadComposeEnv(self._release_mgr.config_compose_env_path)
    return env.get("DCON_REPO") or "us-docker.pkg.dev/android-mtt"

  @Block
  def _ResolveCandidate(self) -> BlockResult:
    """Pulls the configured image and resolves it to an immutable reference."""
    image_name = ""
    tag = ""
    config_flags: dict[str, Any] = {}
    try:
      if os.path.exists(self._release_mgr.config_flags_path):
        with open(
            self._release_mgr.config_flags_path, "r", encoding="utf-8"
        ) as f:
          loaded = yaml.safe_load(f)
          config_flags = loaded if isinstance(loaded, dict) else {}
        image_name = str(config_flags.get("image_name") or "").strip()
        tag = str(config_flags.get("tag") or "").strip()

      last_segment = image_name.rsplit("/", 1)[-1]
      has_tag_or_digest = "@" in image_name or ":" in last_segment
      if image_name and not has_tag_or_digest and tag:
        image_ref = f"{image_name}:{tag}"
      else:
        image_ref = image_name or "mtt:latest"

      sa_key_path = self._ResolveServiceAccountKeyPath(config_flags)
      self._candidate_image_ref = self._image_executor.PullAndResolveImageRef(
          image_ref,
          service_account_json_key_path=sa_key_path,
      )
    except (docker_image.Error, ValueError, OSError, yaml.YAMLError) as e:
      logger.error("Failed to pull and resolve image: %s", e)
      return BlockResult(False, error_message=str(e))
    return BlockResult(True)

  @Block
  def _StageRelease(self) -> BlockResult:
    """Stages a release folder for the resolved candidate image reference."""
    if not self._candidate_image_ref:
      return BlockResult(
          False, error_message="No candidate image reference to stage"
      )
    self._release_mgr.StageRelease(self._candidate_image_ref)
    return BlockResult(True)

  @Block
  def _StageComposeFiles(self) -> BlockResult:
    """Extracts bundled compose definitions to the compose/ directory."""
    self._compose_mgr.ExtractComposeFiles()
    return BlockResult(True)

  @Block
  def _RecordAppliedTunnelEnv(self) -> BlockResult:
    """Copies the env the tunnel was just started with from config/ to tunnel/.

    Runs after a successful start, never before: `up` reads the desired
    environment from config/, and only a successful start makes it the applied
    one. Recording it first would leave the record ahead of reality, and
    nothing is undone after a failure.

    Returns:
      A failed BlockResult if the copy could not be written.
    """
    try:
      self._release_mgr.StageTunnelEnv()
    except OSError as e:
      return BlockResult(False, error_message=str(e))
    return BlockResult(True)

  @Block
  def _PromoteStaging(self) -> BlockResult:
    """Promotes the candidate staging symlink to active."""
    self._release_mgr.PromoteStagingToActive()
    return BlockResult(True)

  @Block
  def _DiscardStaging(self) -> BlockResult:
    """Discards the candidate staging symlink."""
    self._release_mgr.DiscardStaging()
    return BlockResult(True)

  # ==========================================================================
  # Service blocks (move exactly one group, in one direction)
  # ==========================================================================

  @Block
  def _StartCore(self, release: _Release) -> BlockResult:
    """Starts the core container from a release and awaits healthiness.

    Args:
      release: Which release pointer to start from.

    Returns:
      A failed BlockResult carrying failed_services diagnostics when the
      container did not become healthy.
    """
    if release == _Release.STAGING:
      exists = self._release_mgr.has_staging_release
      lab_config_path = self._release_mgr.staging_config_path
      flags_path = self._release_mgr.staging_flags_path
    else:
      exists = self._release_mgr.has_active_release
      lab_config_path = self._release_mgr.active_config_path
      flags_path = self._release_mgr.active_flags_path

    if not exists:
      return BlockResult(
          False, error_message=f"No {release.value} release found"
      )

    core = process_executor.MttExecutor.FromConfigFiles(
        lab_config_path=(
            lab_config_path if os.path.exists(lab_config_path) else None
        ),
        pinned_mtt_flags_path=flags_path,
        mtt_bin=self._mtt_cli_path,
    )
    res = core.StartAndAwaitHealthy()
    if not res.success:
      return BlockResult(
          False,
          error_message=(
              res.error_message
              or f"Core container from {release.value} failed health check"
          ),
          failed_services=res.failed_services,
      )
    return BlockResult(True)

  @Block
  def _StopCore(
      self, drain: bool = False, timeout_sec: Optional[int] = None
  ) -> BlockResult:
    """Stops the running core container, if any.

    The guard is on the container rather than on the active release: `mtt stop`
    needs no config, so a container started outside the node framework is still
    stopped. Probing first avoids invoking the legacy stop path, and the
    control-server event it emits, on a node that has nothing running.

    Args:
      drain: Waits for in-flight test runs to finish before stopping.
      timeout_sec: Kills `mtt stop` after this many seconds. None, the
        default, lets `mtt stop` manage its own budget.

    Returns:
      A successful BlockResult if no container was running.
    """
    status = self._image_executor.GetContainerStatus(_CORE_CONTAINER_NAME)
    if not status.is_running:
      return BlockResult(True)
    stop_executor = process_executor.MttStopExecutor(mtt_bin=self._mtt_cli_path)
    res = stop_executor.Stop(drain=drain, timeout_sec=timeout_sec)
    if not res.success:
      return BlockResult(
          False,
          error_message=res.error_message or "Failed to stop MTT container",
      )
    return BlockResult(True)

  @Block
  def _StartTunnel(self, pull: Optional[str] = None) -> BlockResult:
    """Starts the tunnel sidecars from the desired env and awaits healthiness.

    Args:
      pull: Value for `docker compose up --pull`, or None to leave image
        selection to whatever is already on the host. Only `tunnel upgrade`
        passes a value: on `start`, re-pulling would recreate the sidecars
        whenever a new image was published, which by the coordination rule
        would restart a serving core.

    Returns:
      A failed BlockResult when the sidecars did not become healthy.
    """
    sa_key_path = self._ResolveServiceAccountKeyPath()
    if sa_key_path:
      try:
        self._image_executor.LoginWithServiceAccount(
            sa_key_path, self._ResolveTunnelRepo()
        )
      except docker_image.Error as e:
        logger.error("Failed to authenticate Docker for tunnel images: %s", e)
        return BlockResult(False, error_message=str(e))

    compose_executor = self._GetTunnelComposeExecutor(
        self._release_mgr.config_compose_env_path
    )
    res = compose_executor.StartAndAwaitHealthy(pull=pull)
    if not res.success:
      return BlockResult(
          False,
          error_message=(
              res.error_message or "Tunnel sidecars failed to start"
          ),
      )
    return BlockResult(True)

  @Block
  def _StopTunnel(self) -> BlockResult:
    """Stops the tunnel sidecars, using the env they were started with.

    Orphans are removed: a partially applied environment can leave containers
    the applied env no longer names, and nothing else would ever collect them.

    Returns:
      A successful BlockResult if the tunnel was never started on this node.
    """
    env_path = self._release_mgr.tunnel_compose_env_path
    if not os.path.exists(env_path):
      return BlockResult(True)
    compose_executor = self._GetTunnelComposeExecutor(env_path)
    res = compose_executor.Stop(remove_orphans=True)
    if not res.success:
      return BlockResult(
          False,
          error_message=(
              res.error_message or "Failed to stop tunnel compose sidecars"
          ),
      )
    return BlockResult(True)

  # ==========================================================================
  # Data plane helpers
  # ==========================================================================

  def _GetHostEnvOverlayFile(self) -> Optional[str]:
    """Returns the path to the host environment overlay compose file if present."""
    if (
        not self._host_env
        or self._host_env == host_env_lib.HostEnvironment.DEFAULT
    ):
      return None

    overlay_filename = _ENV_OVERLAY_COMPOSE_FILES.get(self._host_env.value)
    if not overlay_filename:
      return None

    overlay_path = self._compose_mgr.GetComposeFilePath(overlay_filename)
    return overlay_path if os.path.exists(overlay_path) else None

  def _ReadComposeEnv(self, env_path: str) -> dict[str, str]:
    """Parses a docker-compose.env file into a dict of stripped values.

    Args:
      env_path: Path to the env file. A missing or unreadable file yields an
        empty dict, so callers treat it the same as a file defining nothing.

    Returns:
      Mapping of variable name to value, with surrounding quotes removed.
      docker-compose.env values are quoted on write, so an explicitly empty
      value reads back as '""' and must be unquoted before any emptiness
      check.
    """
    env: dict[str, str] = {}
    if not os.path.exists(env_path):
      return env
    try:
      with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
          line = line.strip()
          if not line or line.startswith("#") or "=" not in line:
            continue
          key, value = line.split("=", 1)
          env[key.strip()] = value.strip().strip("\"'")
    except OSError:
      logger.warning("Could not read compose env file %s", env_path)
    return env

  def _HasOtelEndpoint(self, env: dict[str, str]) -> bool:
    """Checks if OTEL_EXPORTER_OTLP_ENDPOINT is defined in a compose env."""
    return bool(env.get("OTEL_EXPORTER_OTLP_ENDPOINT"))

  def _NeedsEspProxy(self, env: dict[str, str]) -> bool:
    """Checks whether the Cloud Endpoints proxy should run on this node.

    All three conditions are required. ESP fronts the controller's acceptor,
    so it is meaningless on a worker; it is a GCP-only product, so it cannot
    serve a lab host; and with no DCON_ACCEPTOR_ADDR it would start with an
    empty `--service` and proxy nothing.

    Args:
      env: Parsed compose env the tunnel command will run with.

    Returns:
      True if the esp compose profile should be selected.
    """
    if self._role != NodeRole.CONTROLLER:
      return False
    if not self._host_env or not self._host_env.IsGcp():
      return False
    return bool(env.get("DCON_ACCEPTOR_ADDR"))

  def _GetTunnelComposeExecutor(
      self, env_path: str
  ) -> process_executor.DockerComposeExecutor:
    """Builds a compose executor bound to one env file.

    The env file is a parameter because the two directions read different
    files: `up` applies the desired env from config/, while `down` and health
    checks must use the applied env recorded in tunnel/, which is what the
    running containers were created from.

    Args:
      env_path: Compose env file to run with; also selects the profiles.

    Returns:
      A DockerComposeExecutor for the `tunnel` compose project.
    """
    compose_files = [
        self._compose_mgr.GetComposeFilePath("docker-compose.distrib.yml")
    ]

    overlay_file = self._GetHostEnvOverlayFile()
    if overlay_file:
      compose_files.append(overlay_file)

    env = self._ReadComposeEnv(env_path)
    profiles = [self._role.value] if self._role else []
    if self._NeedsEspProxy(env):
      profiles.append("esp")
    if self._HasOtelEndpoint(env):
      profiles.append("otel")

    return process_executor.DockerComposeExecutor.FromConfigFiles(
        env_file=env_path,
        project_dir=self._compose_mgr.compose_dir,
        project_name="tunnel",
        compose_files=compose_files,
        profiles=profiles,
    )

  # ==========================================================================
  # Pipeline helpers
  # ==========================================================================

  def _Abort(self, msg: str, *args: Any) -> NoReturn:
    """Logs why the pipeline cannot continue and stops it.

    Args:
      msg: Operator-facing message, in `logger` %-format.
      *args: Arguments for `msg`.

    Raises:
      TerminalAbortError: Always.
    """
    logger.error(msg, *args)
    raise TerminalAbortError

  def _Require(self, res: BlockResult) -> None:
    """Aborts the pipeline when a block failed.

    Args:
      res: Result of the block that just ran.

    Raises:
      TerminalAbortError: If the block failed. Nothing already done is undone;
        the journal records where the pipeline stopped.
    """
    if not res.success:
      raise TerminalAbortError

  def _StartTunnelGroup(self, pull: Optional[str] = None) -> None:
    """Brings the tunnel up and records the environment it now runs with.

    Args:
      pull: Value for `docker compose up --pull`, or None.

    Raises:
      TerminalAbortError: If any block failed.
    """
    self._Require(self._StageComposeFiles())
    self._Require(self._StartTunnel(pull=pull))
    self._Require(self._RecordAppliedTunnelEnv())

  # ==========================================================================
  # Pipelines (the commands)
  # ==========================================================================

  @Pipeline
  def Start(self) -> bool:
    """Brings the node up on the image the configuration currently names.

    Never rolls back. `start` is a manual operation run when nothing is
    serving, so there is no previous release worth restoring; `core upgrade`
    is the command with a failure policy.

    Returns:
      True if the node is running the candidate image and the tunnel is
      healthy.
    """
    self._Require(self._MaterializeAndValidateConfig())
    self._Require(self._ResolveCandidate())

    core = self.ObserveCore(self._candidate_image_ref)
    tunnel = self.ObserveTunnel()
    role_str = self._role.value if self._role else "<role>"

    if core == CoreCondition.UP_STALE:
      running_image = (
          self._image_executor.GetContainerImage(_CORE_CONTAINER_NAME)
          or "unknown"
      )
      self._Abort(
          "Container 'mtt' is already running image %r, which differs from"
          " candidate %r. Run 'mtt node %s core upgrade' to replace it, or"
          " 'mtt node %s stop' and start again.",
          running_image,
          self._candidate_image_ref,
          role_str,
          role_str,
      )

    if core == CoreCondition.UP_CURRENT and tunnel == TunnelCondition.HEALTHY:
      logger.info(
          "Container 'mtt' is already running candidate image %s and the"
          " tunnel is healthy; nothing to do.",
          self._candidate_image_ref,
      )
      return True

    self._Require(self._StopCore())
    if tunnel == TunnelCondition.DOWN:
      self._StartTunnelGroup()

    self._Require(self._StageRelease())
    self._Require(self._StartCore(_Release.STAGING))
    self._Require(self._PromoteStaging())
    return True

  @Pipeline
  def Stop(
      self, drain: bool = False, timeout_sec: Optional[int] = None
  ) -> bool:
    """Stops the core container and then the tunnel sidecars.

    Args:
      drain: Wait for in-flight tests to finish before stopping. Defaults to
        False, matching native `mtt stop` and the `--drain` CLI flag.
      timeout_sec: Drain timeout in seconds, or None to let `mtt stop` manage
        its own budget.

    Returns:
      True if both groups are down. Either step is skipped when that group was
      already down, so this succeeds on a node that was never started.
    """
    self._Require(self._StopCore(drain=drain, timeout_sec=timeout_sec))
    self._Require(self._StopTunnel())
    return True

  @Pipeline
  def Restart(self) -> bool:
    """Stops and starts the core on the active release.

    Leaves a healthy tunnel alone: the core is restarted either way, so there
    is nothing to gain from bouncing sidecars that are serving.

    Returns:
      True if the core is running the active release and the tunnel is
      healthy.
    """
    role_str = self._role.value if self._role else "<role>"
    if not self._release_mgr.has_active_release:
      self._Abort(
          "No active release found. Run 'mtt node %s start' first.", role_str
      )

    tunnel = self.ObserveTunnel()
    self._Require(self._StopCore())
    if tunnel == TunnelCondition.DOWN:
      self._StartTunnelGroup()
    self._Require(self._StartCore(_Release.ACTIVE))
    return True

  @Pipeline
  def UpgradeCore(
      self,
      enable_rollback: bool = False,
      drain: bool = False,
      timeout_sec: Optional[int] = None,
  ) -> bool:
    """Moves the core to the image the configuration now names.

    Args:
      enable_rollback: Restart the active release if the candidate fails.
        Defaults to False, so recovery is opt-in: without it a failed
        candidate leaves the node stopped.
      drain: Wait for in-flight tests to finish before stopping the active
        core. Defaults to False so an interactive upgrade is not blocked by a
        long-running test; unattended callers should enable it.
      timeout_sec: Drain timeout in seconds, or None to let `mtt stop` manage
        its own budget.

    Returns:
      True if the core now runs the candidate image, or already did. False if
      the candidate was rejected, including when rollback restored the previous
      release: the node is serving in that case, but the upgrade did not
      happen.
    """
    role_str = self._role.value if self._role else "<role>"

    self._Require(self._MaterializeAndValidateConfig())

    if not self._release_mgr.has_active_release:
      self._Abort(
          "No active release found. Run 'mtt node %s start' first.", role_str
      )

    self._Require(self._ResolveCandidate())

    core = self.ObserveCore(self._candidate_image_ref)
    if core == CoreCondition.DOWN:
      self._Abort(
          "Container 'mtt' is not running or is unhealthy. Run 'mtt node %s"
          " start' first.",
          role_str,
      )

    if core == CoreCondition.UP_CURRENT:
      logger.info(
          "Running container 'mtt' already matches candidate image %s;"
          " nothing to upgrade.",
          self._candidate_image_ref,
      )
      return True

    if self.ObserveTunnel() != TunnelCondition.HEALTHY:
      self._Abort(
          "Tunnel sidecars are not healthy. Run 'mtt node %s tunnel upgrade'"
          " or 'mtt node %s start' first.",
          role_str,
          role_str,
      )

    running_image = (
        self._image_executor.GetContainerImage(_CORE_CONTAINER_NAME)
        or "unknown"
    )

    self._Require(self._StageRelease())
    self._Require(self._StopCore(drain=drain, timeout_sec=timeout_sec))

    candidate_res = self._StartCore(_Release.STAGING)
    if candidate_res:
      # A healthy candidate that cannot be promoted aborts here: rolling back
      # would restart the active release on top of a running candidate, so the
      # staging release is left in place for inspection.
      self._Require(self._PromoteStaging())
      return True

    if not enable_rollback:
      self._Abort(
          "Candidate %s failed its health check and rollback is disabled, so"
          " the node is left stopped. Run 'mtt node %s start' to recover.",
          self._candidate_image_ref,
          role_str,
      )

    if not self.EvaluateCoreRecoverable(candidate_res.failed_services):
      self._Abort(
          "Candidate %s failed for a host-level reason, which a rollback would"
          " only repeat. The node is left stopped.",
          self._candidate_image_ref,
      )

    self._Require(self._DiscardStaging())
    self._Require(self._StopCore())
    self._Require(self._StartCore(_Release.ACTIVE))
    logger.error(
        "Core upgrade to %s failed. The candidate was rejected and the"
        " previous active release %s was restored; the node is serving but"
        " was not upgraded.",
        self._candidate_image_ref,
        running_image,
    )
    return False

  @Pipeline
  def UpgradeTunnel(self) -> bool:
    """Applies a new tunnel environment or new sidecar images.

    The core is stopped first and started afterwards: it is not left holding
    sockets to sidecars that are being replaced.

    Returns:
      True if the tunnel is healthy and the core is running the active release.
    """
    role_str = self._role.value if self._role else "<role>"

    self._Require(self._MaterializeAndValidateConfig())

    if not self._release_mgr.has_active_release:
      self._Abort(
          "No active release found. Run 'mtt node %s start' first.", role_str
      )

    self._Require(self._StopCore())
    self._StartTunnelGroup(pull="always")
    self._Require(self._StartCore(_Release.ACTIVE))
    return True
