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

"""Re-provisioning support for `init` and `join`.

`init` and `join` define what a host is, so they start its runtime state from
nothing. This module owns the part of that which does not depend on the role
being provisioned:

  * `InspectNode` reports what a previous `mtt node` setup still runs on the
    host, whatever role it ran as.
  * `Reprovisioning` holds the node lock, refuses a node that is still running
    or in use, and hands back the reset of the node runtime directory
    (`base_dir`, which is `<base_parent_dir>/mttnode`).

Role-dependent host preparation belongs after the reset and after the new
config is written, inside the same `Reprovisioning` hold (for example freeing
the adb server port a worker needs). The node lifecycle after provisioning is
`node_state`'s, and this module does not depend on it beyond the names the
node runs its services under.
"""

import contextlib
import dataclasses
import logging
import os
import shutil
from typing import Callable, Iterator, Optional
from multitest_transport.cli import docker_image
from multitest_transport.cli import node_lock
from multitest_transport.cli import node_permissions
from multitest_transport.cli import node_state

logger = logging.getLogger(__name__)


class ReprovisionError(Exception):
  """Raised when `init` or `join` cannot safely reset the node."""


@dataclasses.dataclass(frozen=True)
class NodeFootprint:
  """What a previous `mtt node` setup still runs on the host."""

  core_running: bool = False
  tunnel_containers: tuple[str, ...] = ()

  @property
  def running(self) -> bool:
    return self.core_running or bool(self.tunnel_containers)

  def Describe(self) -> str:
    """Names what is running, for an operator-facing message."""
    parts = []
    if self.core_running:
      parts.append(f"core container '{node_state.CORE_CONTAINER_NAME}'")
    if self.tunnel_containers:
      parts.append(f"tunnel ({', '.join(self.tunnel_containers)})")
    return "; ".join(parts) or "nothing"


def InspectNode(
    image_executor: Optional[docker_image.DockerImageExecutor] = None,
) -> NodeFootprint:
  """Reports what a previous `mtt node` setup still runs on the host.

  Independent of any role: the core is found by container name, and the tunnel
  by any running container of its compose project, whatever profiles it was
  started with and whatever its health. An unhealthy or restarting tunnel is
  still up.

  Args:
    image_executor: Docker executor, injectable for tests.

  Returns:
    The running core and tunnel containers.
  """
  executor = image_executor or docker_image.DockerImageExecutor()
  return NodeFootprint(
      core_running=executor.GetContainerStatus(
          node_state.CORE_CONTAINER_NAME
      ).is_running,
      tunnel_containers=tuple(
          executor.ListRunningComposeContainers(node_state.TUNNEL_PROJECT_NAME)
      ),
  )


def CheckBaseDirPaths(static_dir: str, base_dir: str) -> None:
  """Refuses a node runtime directory that a reset could not empty safely.

  The CLI only ever passes a directory named `mttnode`, so a mistyped flag
  cannot point the reset at unrelated data. What remains is a symlink, whose
  target the reset would empty, something other than a directory, and an
  overlap with the static tree that provisioning writes.

  Args:
    static_dir: Root static configuration directory.
    base_dir: Node runtime directory that is about to be reset.

  Raises:
    ReprovisionError: If base_dir is a symlink or not a directory, or either
      directory contains the other.
  """
  if os.path.islink(base_dir):
    raise ReprovisionError(
        f"{base_dir} is a symlink; refusing to reset it, because that would"
        " empty the directory it points to."
    )
  if os.path.lexists(base_dir) and not os.path.isdir(base_dir):
    raise ReprovisionError(f"{base_dir} exists and is not a directory.")
  static_real = os.path.realpath(static_dir)
  base_real = os.path.realpath(base_dir)
  if os.path.commonpath([static_real, base_real]) in (static_real, base_real):
    raise ReprovisionError(
        f"{static_dir} and {base_dir} overlap; the static configuration and"
        " the node runtime directory must be separate trees."
    )


def ResetBaseDir(static_dir: str, base_dir: str) -> None:
  """Empties the node runtime directory and re-applies the permission policy.

  Everything inside goes, including `core/active` and the release it points to:
  the previous release cannot be rolled back to after re-provisioning, and the
  first `start` re-pulls the configured image. Only `.lock` stays, so the
  lock the caller holds keeps guarding the same file throughout; the directory
  is created if it did not exist. The group is read back from static_dir,
  which provisioning has already committed.

  Args:
    static_dir: Root static configuration directory.
    base_dir: Node runtime directory.

  Raises:
    ReprovisionError: If the paths are unsafe to reset.
  """
  CheckBaseDirPaths(static_dir, base_dir)
  os.makedirs(base_dir, exist_ok=True)
  for entry in os.scandir(base_dir):
    if entry.name == node_lock.LOCK_FILENAME:
      continue
    if entry.is_dir(follow_symlinks=False):
      # rmtree removes symlinks inside the tree (core/active) without
      # following them.
      shutil.rmtree(entry.path)
    else:
      os.unlink(entry.path)
  gid = node_permissions.DeriveGroupGid(static_dir)
  if gid is not None:
    node_permissions.ApplyPolicy(gid, base_dir=base_dir)
  logger.info("Reset node runtime directory %s", base_dir)


@contextlib.contextmanager
def Reprovisioning(
    static_dir: str,
    base_dir: str,
    image_executor: Optional[docker_image.DockerImageExecutor] = None,
) -> Iterator[Callable[[], None]]:
  """Holds the node for `init`/`join` and yields the reset of base_dir.

  Re-provisioning is only allowed on a node that is stopped and that no other
  command is using. A held `.lock` is an operator mistake, reported rather than
  waited for; a running node is reported with what is running, and the
  operator stops it with the role it was started as.

  An existing base_dir is locked before anything else and stays locked until
  the context exits: the reset keeps `.lock`, so nothing can take the node in
  between. A missing base_dir is not created by the precheck, so a refused or
  aborted re-provisioning leaves the host as it was; there is nothing to guard
  until the reset creates the directory, which then takes the lock.

  Args:
    static_dir: Root static configuration directory.
    base_dir: Node runtime directory.
    image_executor: Docker executor, injectable for tests.

  Yields:
    A function that resets base_dir. Callers invoke it after the static tree
    is committed; role-dependent host preparation follows it in the same hold.

  Raises:
    ReprovisionError: If the paths are unsafe, another command holds the lock,
      or the core or tunnel is running.
  """
  CheckBaseDirPaths(static_dir, base_dir)
  lock_fds: list[int] = []

  def _Lock() -> None:
    fd = node_lock.Acquire(base_dir)
    if fd is None:
      raise ReprovisionError(
          f"Another node command ({node_lock.HolderCommand(base_dir)}) is"
          f" running in {base_dir}. Wait for it to finish or stop it, then"
          " re-run."
      )
    lock_fds.append(fd)

  def _Reset() -> None:
    ResetBaseDir(static_dir, base_dir)
    if not lock_fds:
      _Lock()

  if os.path.isdir(base_dir):
    _Lock()
  try:
    footprint = InspectNode(image_executor)
    if footprint.running:
      raise ReprovisionError(
          f"The node is running: {footprint.Describe()}. Stop it with the role"
          " it was started as, 'mtt node worker stop' or 'mtt node controller"
          " stop', then re-run."
      )
    yield _Reset
  finally:
    for fd in lock_fds:
      node_lock.Release(fd)
