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

"""MTT Node CLI commands for Controller and Worker orchestration."""

import argparse
import contextlib
import functools
import json
import logging
import os
import sys
from typing import Any, Callable, Iterator, Optional, Sequence
from multitest_transport.cli import host_env
from multitest_transport.cli import node_init
from multitest_transport.cli import node_join
from multitest_transport.cli import node_permissions
from multitest_transport.cli import node_provision
from multitest_transport.cli import node_state

logger = logging.getLogger(__name__)

NodeRole = node_state.NodeRole
NodeStateManager = node_state.NodeStateManager

# The node runtime directory, `base_dir`, is always
# `<base_parent_dir>/mttnode`; only its parent is configurable, through
# `--base_parent_dir`. `init` and `join` empty base_dir, and fixing its name
# means a mistyped flag can never point that at unrelated data. The parent
# defaults to /var/lib, so base_dir is /var/lib/mttnode. It is deliberately not
# /var/lib/mtt: that tree belongs to the legacy MTT daemon and holds the `mtt`
# executable.
_DEFAULT_BASE_PARENT_DIR = "/var/lib"
_BASE_DIR_NAME = "mttnode"
_BASE_PARENT_DIR_HELP = (
    "Parent of the node runtime directory; the node uses"
    f" <base_parent_dir>/{_BASE_DIR_NAME}"
    f" (default: {_DEFAULT_BASE_PARENT_DIR})."
)


def _BaseDir(base_parent_dir: str) -> str:
  """Returns the node runtime directory for a `--base_parent_dir` value.

  Every subcommand goes through this one helper, so no two commands can
  resolve different directories from the same flag.

  Args:
    base_parent_dir: Value of `--base_parent_dir`.

  Returns:
    Absolute path of `<base_parent_dir>/mttnode`.
  """
  return os.path.join(os.path.abspath(base_parent_dir), _BASE_DIR_NAME)


def _ArgsBaseDir(args: argparse.Namespace) -> str:
  """Returns the node runtime directory named by parsed CLI arguments."""
  return _BaseDir(
      getattr(args, "base_parent_dir", _DEFAULT_BASE_PARENT_DIR)
  )


def _DefaultStateManagerFactory(
    base_dir: str = _BaseDir(_DEFAULT_BASE_PARENT_DIR),
    static_dir: str = node_init.DEFAULT_STATIC_DIR,
    role: NodeRole = NodeRole.WORKER,
    host_environment: Optional[host_env.HostEnvironment] = None,
    **kwargs,
) -> NodeStateManager:
  """Creates NodeStateManager with auto-detected host environment."""
  return node_state.NodeStateManager(
      base_dir=base_dir,
      static_dir=static_dir,
      role=role,
      host_env=host_environment or host_env.Detect(),
      **kwargs,
  )


def _RequiresRoot(command: str) -> Callable[..., Any]:
  """Gates a provisioning handler on root.

  `init` and `join` are the only commands that create the host directories, so
  they are the only place the ownership and mode policy can be established.
  Letting them run as a normal user would produce a tree the next operator
  cannot write, which is the failure this model exists to prevent.

  Args:
    command: Command name quoted back to the operator.

  Returns:
    A decorator for a CLI handler.
  """

  def Decorator(handler: Callable[..., int]) -> Callable[..., int]:
    @functools.wraps(handler)
    def Wrapper(args: argparse.Namespace, *rest, **kwargs) -> int:
      node_permissions.SetUmask()
      try:
        node_permissions.RequireRoot(command)
      except node_permissions.PermissionPolicyError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
      return handler(args, *rest, **kwargs)

    return Wrapper

  return Decorator


def _RequiresMembership(handler: Callable[..., int]) -> Callable[..., int]:
  """Gates a routine handler on membership of the group owning static_dir.

  Applied to every non-provisioning command, `status` included. A non-member
  cannot traverse either tree, and `os.path.exists` reports EACCES as False,
  so an ungated `status` would report a healthy tunnel as DOWN instead of
  saying the caller lacks access.

  Args:
    handler: CLI handler to gate.

  Returns:
    The handler, wrapped so that a non-member gets an error and exit code 1.
  """

  @functools.wraps(handler)
  def Wrapper(args: argparse.Namespace, *rest, **kwargs) -> int:
    node_permissions.SetUmask()
    static_dir = getattr(args, "static_dir", node_init.DEFAULT_STATIC_DIR)
    try:
      node_permissions.CheckMembership(static_dir)
    except node_permissions.PermissionPolicyError as e:
      print(f"ERROR: {e}", file=sys.stderr)
      return 1
    return handler(args, *rest, **kwargs)

  return Wrapper


def _PrintNextSteps(
    role: NodeRole, static_dir: str, base_parent_dir: str, mtt_group: str
) -> None:
  """Tells the operator the command to run next.

  Provisioning leaves the node configured but stopped, and `start` is the only
  sensible follow-up. The directories are echoed back only when they are not
  the defaults, so the common case stays a short command the operator can paste
  verbatim.

  Args:
    role: Role that was just provisioned.
    static_dir: Static configuration root that was provisioned.
    base_parent_dir: Value of `--base_parent_dir` that was used.
    mtt_group: Group that now owns both directories.
  """
  command = f"mtt node {role.value} start"
  if static_dir != node_init.DEFAULT_STATIC_DIR:
    command += f" --static_dir {static_dir}"
  if base_parent_dir != _DEFAULT_BASE_PARENT_DIR:
    command += f" --base_parent_dir {base_parent_dir}"
  print(
      f"\n{role.value.capitalize()} provisioned in {static_dir}."
      f"\n\nNext step, start the node:\n  {command}\n"
      f"\nNo sudo needed: {static_dir} and {_BaseDir(base_parent_dir)} are"
      f" owned by the '{mtt_group}' group, so any member of it can run the"
      " command."
  )


@contextlib.contextmanager
def _Reprovisioning(args: argparse.Namespace) -> Iterator[Callable[[], None]]:
  """Holds the node for `init`/`join` and yields the runtime reset.

  The check does not depend on the role being provisioned: the node may
  currently run as the other role. Role-dependent host preparation, when there
  is some, runs after the reset and the new config inside this same hold.

  Args:
    args: Parsed CLI arguments of the provisioning command.

  Yields:
    A function that empties the node runtime directory.

  Raises:
    node_provision.ReprovisionError: If the node is running, `.lock` is held,
      or the node runtime directory cannot be reset safely.
  """
  static_dir = getattr(args, "static_dir", node_init.DEFAULT_STATIC_DIR)
  with node_provision.Reprovisioning(static_dir, _ArgsBaseDir(args)) as reset:
    yield reset


def _CreateLabConfigArgParser() -> argparse.ArgumentParser:
  """Creates argparser for lab config path arg."""
  parser = argparse.ArgumentParser(add_help=False)
  parser.add_argument(
      "lab_config_path",
      metavar="lab_config_path",
      type=str,
      nargs="?",
      help="Lab config path to use.",
  )
  return parser


def _CreateCommonInitArgParser() -> argparse.ArgumentParser:
  """Creates common arguments for non-interactive init."""
  parser = argparse.ArgumentParser(add_help=False)
  parser.add_argument(
      "--image_name",
      type=str,
      default=node_init.DEFAULT_IMAGE_NAME,
      help="MTT container image name.",
  )
  parser.add_argument(
      "--tag",
      type=str,
      default=node_init.DEFAULT_TAG,
      help="MTT container image tag.",
  )
  parser.add_argument(
      "--otel",
      action="store_true",
      default=False,
      help="Enable OpenTelemetry exporter.",
  )
  parser.add_argument(
      "--service_account_json_key_path",
      type=str,
      default=None,
      help="Path to GCP service account JSON key file.",
  )
  parser.add_argument(
      "--static_dir",
      type=str,
      default=node_init.DEFAULT_STATIC_DIR,
      help="Static configuration directory (default: /etc/mtt).",
  )
  parser.add_argument(
      "--base_parent_dir",
      type=str,
      default=_DEFAULT_BASE_PARENT_DIR,
      help=_BASE_PARENT_DIR_HELP,
  )
  parser.add_argument(
      "--mtt_group",
      type=str,
      default=node_permissions.DEFAULT_MTT_GROUP,
      help=(
          "Existing host group that owns both directories, so routine"
          " commands run without sudo (default:"
          f" {node_permissions.DEFAULT_MTT_GROUP}). The group is never"
          " created."
      ),
  )
  return parser


def _AttachPassthroughSeparator(parser: argparse.ArgumentParser) -> None:
  """Splits argv at '--' before argparse runs on an init subparser.

  In Python <= 3.13, `argparse._parse_known_args` calls `consume_positionals(0)`
  before `consume_optional(0)`; any `nargs='*'` or `REMAINDER` positional
  matches 0 items at index 0 when an `--option` comes first and is popped from
  `positionals`, leaving `--` and everything after it as unrecognized arguments.
  Splitting `args` on `--` before delegating to `parse_known_args` keeps all
  pre-`--` flags strictly validated by `argparse` while forwarding post-`--`
  tokens untouched across all Python versions.

  Args:
    parser: Subparser (`controller init` or `worker init`) to wrap.
  """
  orig_parse_known_args = parser.parse_known_args

  def _ParseKnownArgs(
      args: Optional[Sequence[str]] = None,
      namespace: Optional[argparse.Namespace] = None,
  ) -> tuple[argparse.Namespace, list[str]]:
    if args is not None and "--" in args:
      sep_idx = list(args).index("--")
      before_sep = list(args)[:sep_idx]
      after_sep = list(args)[sep_idx + 1 :]
    else:
      before_sep = args
      after_sep = []
    ns, remaining = orig_parse_known_args(before_sep, namespace)
    ns.passthrough_flags = after_sep
    return ns, remaining

  parser.parse_known_args = _ParseKnownArgs


def _ExtractInitArgs(
    args: argparse.Namespace,
    unrecognized_flags: Optional[Sequence[str]] = None,
    allow_lab_config: bool = False,
) -> tuple[Optional[str], list[str]]:
  """Extracts optional lab_config_path and '--'-separated passthrough flags."""
  lab_config_path = (
      getattr(args, "lab_config_path", None) if allow_lab_config else None
  )
  if unrecognized_flags is not None:
    flags = list(unrecognized_flags)
    if flags and flags[0] == "--":
      flags = flags[1:]
    return lab_config_path, flags

  raw_passthrough = list(getattr(args, "passthrough_flags", None) or [])
  if raw_passthrough and raw_passthrough[0] == "--":
    raw_passthrough = raw_passthrough[1:]
  return lab_config_path, raw_passthrough


@_RequiresRoot("mtt node controller init")
def _HandleControllerInit(
    args: argparse.Namespace,
    unrecognized_flags: Optional[Sequence[str]] = None,
) -> int:
  """Handler for `mtt node controller init`."""
  static_dir = getattr(args, "static_dir", node_init.DEFAULT_STATIC_DIR)
  base_parent_dir = getattr(args, "base_parent_dir", _DEFAULT_BASE_PARENT_DIR)
  mtt_group = getattr(args, "mtt_group", node_permissions.DEFAULT_MTT_GROUP)
  try:
    _, passthrough_flags = _ExtractInitArgs(
        args, unrecognized_flags=unrecognized_flags, allow_lab_config=False
    )
    with _Reprovisioning(args) as reset_runtime:
      node_init.InitController(
          static_dir=static_dir,
          base_dir=_BaseDir(base_parent_dir),
          mtt_group=mtt_group,
          image_name=getattr(args, "image_name", node_init.DEFAULT_IMAGE_NAME),
          tag=getattr(args, "tag", node_init.DEFAULT_TAG),
          dcon_acceptor_addr=getattr(args, "dcon_acceptor_addr", None),
          otel=getattr(args, "otel", False),
          service_account_json_key_path=getattr(
              args, "service_account_json_key_path", None
          ),
          unrecognized_flags=passthrough_flags,
          host_environment=host_env.Detect(),
          reset_runtime=reset_runtime,
      )
    _PrintNextSteps(
        NodeRole.CONTROLLER, static_dir, base_parent_dir, mtt_group
    )
    return 0
  except Exception as e:  
    logger.error("Failed to initialize controller: %s", e)
    return 1


@_RequiresRoot("mtt node worker init")
def _HandleWorkerInit(
    args: argparse.Namespace,
    unrecognized_flags: Optional[Sequence[str]] = None,
) -> int:
  """Handler for `mtt node worker init`."""
  static_dir = getattr(args, "static_dir", node_init.DEFAULT_STATIC_DIR)
  base_parent_dir = getattr(args, "base_parent_dir", _DEFAULT_BASE_PARENT_DIR)
  mtt_group = getattr(args, "mtt_group", node_permissions.DEFAULT_MTT_GROUP)
  try:
    lab_config_path, passthrough_flags = _ExtractInitArgs(
        args, unrecognized_flags=unrecognized_flags, allow_lab_config=True
    )
    with _Reprovisioning(args) as reset_runtime:
      node_init.InitWorker(
          dcon_acceptor_target=getattr(args, "dcon_acceptor_target", ""),
          static_dir=static_dir,
          base_dir=_BaseDir(base_parent_dir),
          mtt_group=mtt_group,
          image_name=getattr(args, "image_name", node_init.DEFAULT_IMAGE_NAME),
          tag=getattr(args, "tag", node_init.DEFAULT_TAG),
          otel=getattr(args, "otel", False),
          service_account_json_key_path=getattr(
              args, "service_account_json_key_path", None
          ),
          lab_config_path=lab_config_path,
          unrecognized_flags=passthrough_flags,
          reset_runtime=reset_runtime,
      )
    _PrintNextSteps(NodeRole.WORKER, static_dir, base_parent_dir, mtt_group)
    return 0
  except Exception as e:  
    logger.error("Failed to initialize worker: %s", e)
    return 1


def _ConfirmStartNow(prompter: node_join.Prompter) -> bool:
  """Asks whether to start the worker now, defaulting to yes.

  This is asked after the join has been committed, so neither an interrupt nor
  an exhausted retry limit may propagate: the only thing the operator can
  decline here is the start, and a traceback at this point would look like the
  join itself had failed.

  Args:
    prompter: Prompter used to ask the question.

  Returns:
    True if the worker should be started now.
  """
  try:
    return prompter.Confirm(
        "Start the worker now?",
        default=True,
        abort_message="Not starting the worker now.",
    )
  except (node_join.UserAbortError, RuntimeError):
    return False


@_RequiresRoot("mtt node worker join")
def _HandleWorkerJoin(
    args: argparse.Namespace, prompter: Optional[node_join.Prompter] = None
) -> int:
  """Handler for `mtt node worker join`."""
  static_dir = getattr(args, "static_dir", node_init.DEFAULT_STATIC_DIR)
  base_parent_dir = getattr(args, "base_parent_dir", _DEFAULT_BASE_PARENT_DIR)
  mtt_group = getattr(args, "mtt_group", node_permissions.DEFAULT_MTT_GROUP)
  base_dir = _BaseDir(base_parent_dir)
  ui = prompter or node_join.Prompter()
  tag = getattr(args, "tag", None)
  android_sa_key_path = getattr(args, "android_service_account_key_path", None)
  join_kwargs: dict[str, Any] = {}
  if tag:
    join_kwargs["tag"] = tag
  if android_sa_key_path:
    join_kwargs["android_service_account_key_path"] = android_sa_key_path
  try:
    # The node is held from before the first prompt until the runtime
    # directory has been reset, and released before the start handoff below,
    # which takes the lock itself.
    with _Reprovisioning(args) as reset_runtime:
      node_join.Join(
          static_dir=static_dir,
          var_config_dir=os.path.join(base_dir, "config"),
          base_dir=base_dir,
          mtt_group=mtt_group,
          prompter=ui,
          reset_runtime=reset_runtime,
          **join_kwargs,
      )
  except node_join.UserAbortError:
    logger.info("Worker join cancelled by user; no changes were applied.")
    return 1
  except Exception as e:  
    logger.error("Failed during worker join: %s", e)
    return 1

  # The join is committed from here on. Failures below are start failures.
  if not _ConfirmStartNow(ui):
    _PrintNextSteps(NodeRole.WORKER, static_dir, base_parent_dir, mtt_group)
    return 0
  exit_code = _HandleStart(args, NodeRole.WORKER)
  if exit_code != 0:
    print(
        "\nThe join itself completed and is committed; only the start failed."
        " Fix the problem and re-run the start, not the join.",
        file=sys.stderr,
    )
  return exit_code


def _GetStateManager(
    args: argparse.Namespace, role: NodeRole
) -> NodeStateManager:
  """Helper to construct NodeStateManager from CLI args."""
  base_dir = _ArgsBaseDir(args)
  static_dir = getattr(args, "static_dir", node_init.DEFAULT_STATIC_DIR)
  mtt_cli_path = getattr(args, "cli_path", None)
  kwargs = {"mtt_cli_path": mtt_cli_path} if mtt_cli_path else {}
  return _DefaultStateManagerFactory(
      base_dir=base_dir,
      static_dir=static_dir,
      role=role,
      **kwargs,
  )


@_RequiresMembership
def _HandleStart(args: argparse.Namespace, role: NodeRole) -> int:
  mgr = _GetStateManager(args, role)
  return 0 if mgr.Start() else 1


@_RequiresMembership
def _HandleStop(args: argparse.Namespace, role: NodeRole) -> int:
  mgr = _GetStateManager(args, role)
  drain = getattr(args, "drain", False)
  drain_timeout = getattr(args, "drain_timeout", None)
  success = mgr.Stop(
      drain=drain, timeout_sec=drain_timeout if drain else None
  )
  return 0 if success else 1


@_RequiresMembership
def _HandleRestart(args: argparse.Namespace, role: NodeRole) -> int:
  mgr = _GetStateManager(args, role)
  return 0 if mgr.Restart() else 1


@_RequiresMembership
def _HandleStatus(args: argparse.Namespace, role: NodeRole) -> int:
  """Handler for `mtt node <role> status`.

  Args:
    args: Parsed CLI arguments.
    role: Node role the command was invoked for.

  Returns:
    0 once the observation is made; reporting that a group is down is a
    successful observation. The membership preflight can still return 1
    before any observation happens, since a caller who cannot read the
    directories would otherwise be handed a confidently wrong report.
  """
  mgr = _GetStateManager(args, role)
  status = mgr.GetStatus()
  print(json.dumps(status.ToDict(), indent=2))
  return 0


@_RequiresMembership
def _HandleTunnelUpgrade(args: argparse.Namespace, role: NodeRole) -> int:
  """Handler for `mtt node <role> tunnel upgrade`."""
  mgr = _GetStateManager(args, role)
  return 0 if mgr.UpgradeTunnel() else 1


@_RequiresMembership
def _HandleCoreUpgrade(args: argparse.Namespace, role: NodeRole) -> int:
  """Handler for `mtt node <role> core upgrade`."""
  mgr = _GetStateManager(args, role)
  enable_rollback = getattr(args, "enable_rollback", False)
  drain = getattr(args, "drain", False)
  drain_timeout = getattr(args, "drain_timeout", None)
  image_ref = getattr(args, "image_ref", None)
  success = mgr.UpgradeCore(
      enable_rollback=enable_rollback,
      drain=drain,
      timeout_sec=drain_timeout if drain else None,
      image_ref=image_ref,
  )
  return 0 if success else 1


def AddNodeSubparsers(subparsers: Any) -> None:
  """Registers `mtt node` subparsers.

  Args:
    subparsers: The subparser action returned by `ArgumentParser.
      add_subparsers()`. Typed as Any because `argparse._SubParsersAction` is
      private and not subscriptable at runtime.
  """
  node_parser = subparsers.add_parser(
      "node", help="Manage MTT station nodes (Worker and Controller)."
  )
  node_subparsers = node_parser.add_subparsers(
      title="Node Roles", dest="node_role"
  )

  # =========================================================================
  # Controller Subcommands
  # =========================================================================
  ctrl_parser = node_subparsers.add_parser(
      "controller", help="Manage MTT Controller node."
  )
  ctrl_sub = ctrl_parser.add_subparsers(
      title="Controller Commands", dest="node_command"
  )

  # Controller init (non-interactive)
  ctrl_init = ctrl_sub.add_parser(
      "init",
      parents=[_CreateCommonInitArgParser()],
      help="Initialize controller static configuration.",
  )
  ctrl_init.add_argument(
      "--dcon_acceptor_addr",
      type=str,
      default=None,
      help="DualConduit acceptor Cloud Endpoints address for ESP.",
  )
  _AttachPassthroughSeparator(ctrl_init)
  ctrl_init.set_defaults(func=_HandleControllerInit)

  # Controller lifecycle
  _AddLifecycleCommands(ctrl_sub, NodeRole.CONTROLLER)

  # =========================================================================
  # Worker Subcommands
  # =========================================================================
  worker_parser = node_subparsers.add_parser(
      "worker", help="Manage MTT Worker node."
  )
  worker_sub = worker_parser.add_subparsers(
      title="Worker Commands", dest="node_command"
  )

  # Worker init (non-interactive)
  worker_init = worker_sub.add_parser(
      "init",
      parents=[_CreateLabConfigArgParser(), _CreateCommonInitArgParser()],
      help="Initialize worker static configuration non-interactively.",
  )
  worker_init.add_argument(
      "--dcon_acceptor_target",
      type=str,
      required=True,
      help="DualConduit acceptor websocket target URL.",
  )
  _AttachPassthroughSeparator(worker_init)
  worker_init.set_defaults(func=_HandleWorkerInit)

  # Worker join (interactive)
  worker_join = worker_sub.add_parser(
      "join",
      help="Join worker node to an MTT cluster using GCP Parameter Manager.",
  )
  worker_join.add_argument(
      "--static_dir",
      type=str,
      default=node_init.DEFAULT_STATIC_DIR,
      help="Static configuration directory (default: /etc/mtt).",
  )
  worker_join.add_argument(
      "--base_parent_dir",
      type=str,
      default=_DEFAULT_BASE_PARENT_DIR,
      help=_BASE_PARENT_DIR_HELP,
  )
  # A flag and nothing else: the interactive wizard never prompts for it, so
  # the common case stays a plain `sudo mtt node worker join`.
  worker_join.add_argument(
      "--mtt_group",
      type=str,
      default=node_permissions.DEFAULT_MTT_GROUP,
      help=(
          "Existing host group that owns both directories, so routine"
          " commands run without sudo (default:"
          f" {node_permissions.DEFAULT_MTT_GROUP}). The group is never"
          " created."
      ),
  )
  worker_join.add_argument(
      "--tag",
      type=str,
      default=None,
      help=(
          "Optional node-scope MTT container image tag to override the pool"
          " scope tag."
      ),
  )
  worker_join.add_argument(
      "--android_service_account_key_path",
      type=str,
      default=None,
      help=(
          "Optional path to Android service account JSON key file. Copied to"
          " /etc/mtt/secrets/android-sa-key.json and added to node-scope"
          " mtt_args."
      ),
  )
  worker_join.set_defaults(func=_HandleWorkerJoin)

  # Worker lifecycle
  _AddLifecycleCommands(worker_sub, NodeRole.WORKER)


def _AddLifecycleCommands(subparsers: Any, role: NodeRole) -> None:
  """Adds routine lifecycle subcommands (start, stop, status, upgrades)."""
  # start
  start_p = subparsers.add_parser(
      "start", help=f"Start all {role.value} services and application."
  )
  start_p.add_argument(
      "--base_parent_dir",
      type=str,
      default=_DEFAULT_BASE_PARENT_DIR,
      help=_BASE_PARENT_DIR_HELP,
  )
  start_p.add_argument(
      "--static_dir",
      type=str,
      default=node_init.DEFAULT_STATIC_DIR,
      help="Static directory.",
  )
  start_p.set_defaults(func=lambda args, role=role: _HandleStart(args, role))

  # stop
  stop_p = subparsers.add_parser(
      "stop", help=f"Stop all {role.value} services and application."
  )
  stop_p.add_argument(
      "--base_parent_dir",
      type=str,
      default=_DEFAULT_BASE_PARENT_DIR,
      help=_BASE_PARENT_DIR_HELP,
  )
  stop_p.add_argument(
      "--static_dir",
      type=str,
      default=node_init.DEFAULT_STATIC_DIR,
      help="Static directory.",
  )
  stop_p.add_argument(
      "--drain",
      dest="drain",
      action=argparse.BooleanOptionalAction,
      default=False,
      help="Wait for in-flight tests to finish before stopping. Default is"
      " false.",
  )
  stop_p.add_argument(
      "--drain_timeout",
      type=int,
      default=None,
      help=(
          "Give up and kill 'mtt stop' after this many seconds; only used"
          " with --drain. Unset by default, which lets 'mtt stop' manage its"
          " own budget."
      ),
  )
  stop_p.set_defaults(func=lambda args, role=role: _HandleStop(args, role))

  # restart
  restart_p = subparsers.add_parser(
      "restart", help=f"Restart {role.value} services and application."
  )
  restart_p.add_argument(
      "--base_parent_dir",
      type=str,
      default=_DEFAULT_BASE_PARENT_DIR,
      help=_BASE_PARENT_DIR_HELP,
  )
  restart_p.add_argument(
      "--static_dir",
      type=str,
      default=node_init.DEFAULT_STATIC_DIR,
      help="Static directory.",
  )
  restart_p.set_defaults(
      func=lambda args, role=role: _HandleRestart(args, role)
  )

  # status
  status_p = subparsers.add_parser(
      "status", help=f"Check {role.value} node status."
  )
  status_p.add_argument(
      "--base_parent_dir",
      type=str,
      default=_DEFAULT_BASE_PARENT_DIR,
      help=_BASE_PARENT_DIR_HELP,
  )
  status_p.add_argument(
      "--static_dir",
      type=str,
      default=node_init.DEFAULT_STATIC_DIR,
      help="Static directory.",
  )
  status_p.set_defaults(func=lambda args, role=role: _HandleStatus(args, role))

  # tunnel
  tunnel_p = subparsers.add_parser(
      "tunnel", help=f"Manage {role.value} tunnel sidecars."
  )
  tunnel_sub = tunnel_p.add_subparsers(
      title="Tunnel Commands", dest="tunnel_cmd"
  )
  tunnel_up = tunnel_sub.add_parser("upgrade", help="Upgrade tunnel sidecars.")
  tunnel_up.add_argument(
      "--base_parent_dir",
      type=str,
      default=_DEFAULT_BASE_PARENT_DIR,
      help=_BASE_PARENT_DIR_HELP,
  )
  tunnel_up.add_argument(
      "--static_dir",
      type=str,
      default=node_init.DEFAULT_STATIC_DIR,
      help="Static directory.",
  )
  tunnel_up.set_defaults(
      func=lambda args, role=role: _HandleTunnelUpgrade(args, role)
  )

  # core
  core_p = subparsers.add_parser(
      "core", help=f"Manage {role.value} core application container."
  )
  core_sub = core_p.add_subparsers(title="Core Commands", dest="core_cmd")
  core_up = core_sub.add_parser(
      "upgrade", help="Upgrade core application container."
  )
  core_up.add_argument(
      "--base_parent_dir",
      type=str,
      default=_DEFAULT_BASE_PARENT_DIR,
      help=_BASE_PARENT_DIR_HELP,
  )
  core_up.add_argument(
      "--static_dir",
      type=str,
      default=node_init.DEFAULT_STATIC_DIR,
      help="Static directory.",
  )
  core_up.add_argument(
      "--enable_rollback",
      dest="enable_rollback",
      action=argparse.BooleanOptionalAction,
      default=False,
      help=(
          "Restart the previous active release if the candidate fails health"
          " checks. Default is false; without it a failed candidate leaves the"
          " node stopped."
      ),
  )
  core_up.add_argument(
      "--drain",
      dest="drain",
      action=argparse.BooleanOptionalAction,
      default=False,
      help=(
          "Wait for in-flight tests to finish before stopping the active core."
          " Default is false; recommended for unattended upgrades."
      ),
  )
  core_up.add_argument(
      "--drain_timeout",
      type=int,
      default=None,
      help=(
          "Give up and kill 'mtt stop' after this many seconds; only used"
          " with --drain. Unset by default, which lets 'mtt stop' manage its"
          " own budget."
      ),
  )
  core_up.add_argument(
      "--image_ref",
      type=str,
      default=None,
      help=(
          "Explicit container image reference (for example, repo@sha256:...)"
          " overriding the configured image_name and tag."
      ),
  )
  core_up.set_defaults(
      func=lambda args, role=role: _HandleCoreUpgrade(args, role)
  )
