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

"""Filesystem permission model for the MTT node directories.

`init` and `join` are root-only provisioning steps; every routine operation
must run without `sudo` and must keep working when the on-call operator
changes. That requires both directory trees to be group-owned rather than
user-owned:

| Tree         | Directories | Files  | Owner  | Group     |
| ------------ | ----------- | ------ | ------ | --------- |
| `static_dir` | `2750`      | `0640` | `root` | mtt group |
| `base_dir`   | `2770`      | `0660` | varies | mtt group |

The leading `2` is the setgid bit, so everything created later inside a tree
inherits the group automatically, including per-digest release directories
whose names cannot be known at provisioning time.
"""

import errno
import grp
import logging
import os
import pwd
import shutil
import stat
from typing import Any, Optional

logger = logging.getLogger(__name__)

DEFAULT_MTT_GROUP = "docker"

# Directory modes carry the setgid bit so new entries inherit the group.
STATIC_DIR_MODE = 0o2750
STATIC_FILE_MODE = 0o0640
BASE_DIR_MODE = 0o2770
BASE_FILE_MODE = 0o0660

# Strips o+rwx and keeps g+rw. The inherited shell default of 0022 strips g+w,
# which would leave a file one operator can write and the next cannot.
UMASK = 0o007

_STATIC_PREFIX = "static"
_BASE_PREFIX = "base"

_TYPE_DIR = "dir"
_TYPE_FILE = "file"
_TYPE_SYMLINK = "symlink"


class PermissionPolicyError(Exception):
  """Raised when the permission model cannot be established or satisfied."""


def SetUmask() -> int:
  """Applies the node umask for the current process.

  Called for every command including root-run ones: a single `sudo start`
  under the inherited 0022 would re-create files without g+w and lock the
  next operator out of the tree.

  Returns:
    The previous umask, as returned by os.umask.
  """
  return os.umask(UMASK)


def RequireRoot(command: str) -> None:
  """Fails unless the current process is root.

  Args:
    command: Command name quoted back to the operator.

  Raises:
    PermissionPolicyError: If the effective uid is not 0.
  """
  if os.geteuid() != 0:
    raise PermissionPolicyError(
        f"'{command}' creates the host directories and sets their group"
        " ownership, so it must be run as root. Re-run it with sudo."
    )


def ResolveGroupGid(group_name: str) -> int:
  """Looks up a group by name.

  The CLI never creates the group. Silently running `groupadd` would be a side
  effect the operator cannot predict from the command name, and a typo would
  produce a working but unreachable node.

  Args:
    group_name: Name of an existing host group.

  Returns:
    The numeric group id.

  Raises:
    PermissionPolicyError: If no such group exists on this host.
  """
  try:
    return grp.getgrnam(group_name).gr_gid
  except KeyError:
    raise PermissionPolicyError(
        f"--mtt_group '{group_name}' does not exist on this host. Create it"
        f" with 'sudo groupadd {group_name}', or omit the flag to use the"
        f" default '{DEFAULT_MTT_GROUP}' group."
    ) from None


def DeriveGroupGid(static_dir: str) -> Optional[int]:
  """Reads the owning group back from the provisioned static directory.

  static_dir is the single source of truth, so base_dir cannot drift away from
  it and no later command needs the group named again on the command line.

  Args:
    static_dir: Root static configuration directory.

  Returns:
    The numeric group id, or None when static_dir cannot be stat-ed, which is
    the normal state of a host that was never provisioned.
  """
  try:
    return os.stat(static_dir).st_gid
  except OSError:
    return None


def GroupName(gid: int) -> str:
  """Returns the name for a gid, or the number when it has no entry."""
  try:
    return grp.getgrgid(gid).gr_name
  except KeyError:
    return str(gid)


def _ActiveGids() -> set[int]:
  """Returns the gids this process actually carries.

  Reads process credentials rather than /etc/group on purpose: a user added
  with `usermod -aG` who is still in their old login session would pass a
  file-based check and then fail on the first write anyway.
  """
  gids = set(os.getgroups())
  gids.add(os.getgid())
  gids.add(os.getegid())
  return gids


def CheckMembership(static_dir: str) -> None:
  """Verifies the caller can use the provisioned directories.

  Applied to every non-provisioning command, `status` included. `status` is
  not exempt because `ObserveTunnel` gates on `os.path.exists`, which swallows
  EACCES and returns False: without this check a non-member is told a healthy
  tunnel is DOWN instead of being told they lack access.

  Args:
    static_dir: Root static configuration directory.

  Raises:
    PermissionPolicyError: If the caller is not an active member of the group
      owning static_dir.
  """
  # Root is not in the group, and `sudo restart` is a legitimate recovery path
  # on a host whose permissions have been damaged.
  if os.geteuid() == 0:
    return
  gid = DeriveGroupGid(static_dir)
  # Nothing is provisioned yet, so there is no group to belong to. Let the
  # command report "no configuration found" rather than a confusing group
  # error for a directory that does not exist.
  if gid is None:
    return
  if gid in _ActiveGids():
    return
  group_name = GroupName(gid)
  raise PermissionPolicyError(
      "Permission check failed: you are not an active member of group"
      f" '{group_name}', which owns {static_dir}.\n"
      f"If you have not joined: sudo usermod -aG {group_name} $USER\n"
      f"If you were just added: run 'newgrp {group_name}', or log out and log"
      " back in."
  )


def CopyFileWithMode(src: str, dst: str, mode: int) -> None:
  """Copies file content and sets the destination mode from its own tree.

  shutil.copy2 copies mode bits, so a 0640 file in static_dir would land as
  0640 in base_dir instead of 0660 and register as permanent drift.
  shutil.copyfile preserves the mode of an existing destination, which has the
  same effect on a re-materialized node, so the mode is always set explicitly.

  Args:
    src: Source file path.
    dst: Destination file path, replaced when it already exists.
    mode: Destination mode, from the destination tree's policy.
  """
  if os.path.lexists(dst):
    os.remove(dst)
  shutil.copyfile(src, dst)
  os.chmod(dst, mode)


def _ChownGroup(path: str, gid: int, is_link: bool = False) -> None:
  """Sets the group of one entry, leaving the owning user alone.

  The uid is deliberately untouched (-1). base_dir ownership is legitimately
  mixed: `sudo init` lays the skeleton down as root and sudoless operations
  create files as the operator who ran them. Group and mode are the invariant.

  Args:
    path: Entry to change.
    gid: Numeric group id to set.
    is_link: True when path is a symlink, so the link itself is changed rather
      than its target.
  """
  if is_link:
    os.lchown(path, -1, gid)
  else:
    os.chown(path, -1, gid)


def _ApplyToEntry(path: str, gid: int, mode: Optional[int]) -> None:
  """Applies group and mode to one entry, tolerating a concurrent unlink."""
  try:
    is_link = os.path.islink(path)
    _ChownGroup(path, gid, is_link=is_link)
    # os.chmod follows symlinks on Linux, so chmod-ing core/active would chmod
    # the release directory behind it. follow_symlinks=False raises
    # NotImplementedError here, and a symlink's own mode is meaningless.
    if mode is not None and not is_link:
      os.chmod(path, mode)
  except OSError as e:
    if e.errno in (errno.ENOENT, errno.ESTALE):
      logger.debug("Skipping vanished path while applying policy: %s", path)
      return
    raise


def _ApplyTree(root: str, gid: int, dir_mode: int, file_mode: int) -> None:
  """Applies the policy to one tree, without following symlinks out of it."""
  _ApplyToEntry(root, gid, dir_mode)
  for dirpath, dirnames, filenames in os.walk(
      root, topdown=True, followlinks=False
  ):
    # os.walk still lists symlinked directories in dirnames even with
    # followlinks=False. The real directory is reached through its own path,
    # so descending here would touch the same inodes twice.
    kept_dirs = []
    for name in dirnames:
      path = os.path.join(dirpath, name)
      if os.path.islink(path):
        _ApplyToEntry(path, gid, None)
      else:
        _ApplyToEntry(path, gid, dir_mode)
        kept_dirs.append(name)
    dirnames[:] = kept_dirs
    for name in filenames:
      path = os.path.join(dirpath, name)
      if os.path.islink(path):
        _ApplyToEntry(path, gid, None)
      else:
        _ApplyToEntry(path, gid, file_mode)


def ApplyPolicy(
    gid: int,
    static_dir: Optional[str] = None,
    base_dir: Optional[str] = None,
) -> None:
  """Applies the permission policy to the trees that exist.

  Idempotent, so re-running `sudo mtt node <role> init` is the documented
  repair for a host provisioned before this policy existed.

  Args:
    gid: Numeric group id both trees are owned by. Passed in rather than
      derived so tests can apply a group the test process already owns.
    static_dir: Root static configuration directory, when it should be
      covered.
    base_dir: Runtime base directory, when it should be covered.
  """
  if static_dir and os.path.isdir(static_dir):
    _ApplyTree(static_dir, gid, STATIC_DIR_MODE, STATIC_FILE_MODE)
  if base_dir and os.path.isdir(base_dir):
    _ApplyTree(base_dir, gid, BASE_DIR_MODE, BASE_FILE_MODE)


def CreateAndApplyPolicy(gid: int, static_dir: str, base_dir: str) -> None:
  """Creates both trees if absent, then applies the policy to them."""
  os.makedirs(static_dir, exist_ok=True)
  os.makedirs(base_dir, exist_ok=True)
  ApplyPolicy(gid, static_dir=static_dir, base_dir=base_dir)


def _FormatMode(st_mode: int) -> str:
  return f"{stat.S_IMODE(st_mode):04o}"


def _FormatOwner(st_uid: int, st_gid: int) -> str:
  try:
    user = pwd.getpwuid(st_uid).pw_name
  except KeyError:
    user = str(st_uid)
  return f"{user}:{GroupName(st_gid)}"


def _EntryPath(root: str, path: str, prefix: str) -> str:
  rel = os.path.relpath(path, root)
  if rel == os.curdir:
    return f"{prefix}:/"
  return f"{prefix}:/{rel}"


def _SnapshotEntry(
    root: str, path: str, prefix: str
) -> Optional[dict[str, Any]]:
  """Describes one entry, or None when it vanished mid-walk."""
  try:
    st = os.lstat(path)
  except OSError:
    return None
  if stat.S_ISLNK(st.st_mode):
    # A symlink's own mode is always 0777 and carries no information.
    return {
        "path": _EntryPath(root, path, prefix),
        "type": _TYPE_SYMLINK,
        "owner": _FormatOwner(st.st_uid, st.st_gid),
    }
  return {
      "path": _EntryPath(root, path, prefix),
      "type": _TYPE_DIR if stat.S_ISDIR(st.st_mode) else _TYPE_FILE,
      "owner": _FormatOwner(st.st_uid, st.st_gid),
      "mode": _FormatMode(st.st_mode),
  }


def SnapshotTree(root: str, prefix: str) -> list[dict[str, Any]]:
  """Walks one tree and reports metadata only: path, type, owner and mode.

  Never records file contents or sizes.

  Args:
    root: Directory to walk.
    prefix: Namespace for the recorded paths, `static` or `base`, so one
      baseline file can cover both trees.

  Returns:
    Entries sorted by path, so two snapshots of the same tree compare equal.
  """
  if not os.path.isdir(root):
    return []
  entries = []
  root_entry = _SnapshotEntry(root, root, prefix)
  if root_entry:
    entries.append(root_entry)
  for dirpath, dirnames, filenames in os.walk(
      root, topdown=True, followlinks=False
  ):
    kept_dirs = []
    for name in dirnames:
      path = os.path.join(dirpath, name)
      entry = _SnapshotEntry(root, path, prefix)
      if entry:
        entries.append(entry)
      if not os.path.islink(path):
        kept_dirs.append(name)
    dirnames[:] = kept_dirs
    for name in filenames:
      entry = _SnapshotEntry(root, os.path.join(dirpath, name), prefix)
      if entry:
        entries.append(entry)
  entries.sort(key=lambda e: e["path"])
  return entries


def FinalizeProvisioning(gid: int, static_dir: str, base_dir: str) -> None:
  """Closes out a provisioning run.

  The policy is applied a second time because provisioning writes files after
  the trees are created, and re-applying is cheaper than reasoning about which
  steps produced which paths.

  Args:
    gid: Numeric group id both trees are owned by.
    static_dir: Root static configuration directory.
    base_dir: Runtime base directory.
  """
  ApplyPolicy(gid, static_dir=static_dir, base_dir=base_dir)


def _Comparable(entry: dict[str, Any]) -> str:
  """Renders the compared fields: group and mode only.

  The owning user is displayed but never compared. base_dir owners
  legitimately vary per operator, and journal.json in particular is rewritten
  atomically so every run creates a new inode owned by whoever ran it.
  Comparing owners would fill the report with noise at exactly the moment
  someone is debugging.

  Args:
    entry: One snapshot entry.

  Returns:
    The entry's group and mode, or just the group for a symlink, which has no
    meaningful mode of its own.
  """
  group = entry.get("owner", ":").split(":")[-1]
  mode = entry.get("mode")
  return f"{group} {mode}" if mode else group


def _PolicyDrift(
    root: str, prefix: str, gid: int, dir_mode: int, file_mode: int
) -> list[dict[str, Any]]:
  """Reports entries in one tree whose group or mode violates the policy.

  Args:
    root: Directory to walk.
    prefix: Namespace for the reported paths, `static` or `base`.
    gid: Numeric group id both trees must be owned by.
    dir_mode: Mode every directory in this tree must carry.
    file_mode: Mode every file in this tree must carry.

  Returns:
    One entry per violation, empty when the tree satisfies the policy.
  """
  group = GroupName(gid)
  drift: list[dict[str, Any]] = []
  for entry in SnapshotTree(root, prefix):
    if entry["type"] == _TYPE_SYMLINK:
      # A symlink's own mode is always 0777, so only its group is checked.
      expected = group
    else:
      mode = dir_mode if entry["type"] == _TYPE_DIR else file_mode
      expected = f"{group} {mode:04o}"
    actual = _Comparable(entry)
    if actual != expected:
      drift.append(
          {"path": entry["path"], "expected": expected, "actual": actual}
      )
  return drift


def DetectDrift(static_dir: str, base_dir: str) -> list[dict[str, Any]]:
  """Reports paths whose group or mode violates the policy.

  Read-only, and only ever called after an operation has already failed: a
  recursive walk of both trees buys nothing when the operation succeeded.
  Walks the live trees directly against the policy (`2750`/`0640` for
  `static_dir`, `2770`/`0660` for `base_dir`) so paths created at runtime after
  provisioning (`compose/`, `core/releases/<digest>/`, `journal.json`,
  `tunnel/`) are covered without false positives.

  Args:
    static_dir: Root static configuration directory.
    base_dir: Runtime base directory.

  Returns:
    One entry per violation, each naming the expected and actual group and
    mode. Empty when both trees satisfy the policy.
  """
  gid = DeriveGroupGid(static_dir)
  if gid is None:
    # Without static_dir there is no owning group to check against. The
    # command has already failed for a more basic reason than permissions.
    return [{
        "path": static_dir,
        "expected": "a provisioned static directory",
        "actual": "missing or unreadable",
    }]
  return _PolicyDrift(
      static_dir, _STATIC_PREFIX, gid, STATIC_DIR_MODE, STATIC_FILE_MODE
  ) + _PolicyDrift(base_dir, _BASE_PREFIX, gid, BASE_DIR_MODE, BASE_FILE_MODE)


def FormatDrift(drift: list[dict[str, Any]], role: str) -> str:
  """Renders a drift table for stderr."""
  lines = ["Filesystem permission differences detected:"]
  for item in drift:
    lines.append(
        f"  {item['path']}  expected {item['expected']}, actual"
        f" {item['actual']}"
    )
  lines.append(f"Repair with: sudo mtt node {role} init")
  return "\n".join(lines)
