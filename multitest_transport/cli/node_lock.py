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

"""Host-wide lock that serializes `mtt node` commands on one node directory.

Every command that changes a node takes an exclusive `flock` on
`<baseDir>/.lock`: the lifecycle pipelines in `node_state`, and `init` / `join`
while they reset the node directory in `node_provision`. Keeping the primitive
here gives both one implementation, without either depending on the other.

The lock is kernel-managed: it is released when the holding process exits or
crashes, so there is no stale lock to clean up. The descriptor is opened
non-inheritable, so child processes such as `mtt -vv start` do not keep it.
The holding command is not stored in the lock; it is read from `journal.json`,
which the holder writes after taking the lock.
"""

import errno
import fcntl
import json
import os
import stat
import time
from typing import Optional
from multitest_transport.cli import node_permissions

LOCK_FILENAME = ".lock"
# The journal of the most recent pipeline run. Its `command` names the holder
# of the lock while that run is in progress.
JOURNAL_FILENAME = "journal.json"

# How long an acquisition keeps retrying the non-blocking lock before reporting
# it held, and the pause between attempts. Long enough to outlast a `status`
# probe, which takes and releases the lock in microseconds; far shorter than
# any real command, which holds it for seconds to minutes.
_LOCK_GRACE_SEC = 0.05
_LOCK_RETRY_SEC = 0.01


def Acquire(base_dir: str) -> Optional[int]:
  """Acquires the exclusive lock of a node directory, or reports it held.

  The non-blocking attempt is retried for _LOCK_GRACE_SEC so that a
  concurrent `status` probe cannot make a command fail as busy, while a real
  command holding the lock is still reported promptly.

  Args:
    base_dir: Node directory; created if missing.

  Returns:
    The locked file descriptor, or None if another process holds the lock.
  """
  os.makedirs(base_dir, exist_ok=True)
  fd = os.open(
      os.path.join(base_dir, LOCK_FILENAME),
      os.O_CREAT | os.O_RDWR,
      node_permissions.BASE_FILE_MODE,
  )
  deadline = time.monotonic() + _LOCK_GRACE_SEC
  while True:
    try:
      fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
      break
    except OSError as e:
      if e.errno not in (errno.EACCES, errno.EAGAIN):
        os.close(fd)
        raise
      if time.monotonic() >= deadline:
        os.close(fd)
        return None
      time.sleep(_LOCK_RETRY_SEC)
  try:
    st = os.fstat(fd)
    if stat.S_IMODE(st.st_mode) != node_permissions.BASE_FILE_MODE:
      os.fchmod(fd, node_permissions.BASE_FILE_MODE)
  except PermissionError:
    pass
  return fd


def Release(fd: int) -> None:
  """Releases and closes a descriptor returned by Acquire."""
  try:
    fcntl.flock(fd, fcntl.LOCK_UN)
  finally:
    os.close(fd)


def IsHeld(base_dir: str) -> bool:
  """Tests whether another process holds the lock, creating nothing.

  The test takes the lock without blocking and releases it at once; Acquire's
  grace period is what keeps this from making a concurrent command fail.

  Args:
    base_dir: Node directory.

  Returns:
    True if the lock file exists and is held.
  """
  lock_file = os.path.join(base_dir, LOCK_FILENAME)
  if not os.path.exists(lock_file):
    return False
  try:
    fd = os.open(lock_file, os.O_RDWR)
  except PermissionError:
    try:
      fd = os.open(lock_file, os.O_RDONLY)
    except OSError:
      return False
  except OSError:
    return False
  try:
    try:
      fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError as e:
      return e.errno in (errno.EACCES, errno.EAGAIN)
    fcntl.flock(fd, fcntl.LOCK_UN)
    return False
  finally:
    os.close(fd)


def HolderCommand(base_dir: str) -> str:
  """Names the command that holds the lock, from `journal.json`.

  Only meaningful while the lock is held: the holder writes the journal after
  taking the lock, so a held lock with no readable journal is reported as
  `unknown`.

  Args:
    base_dir: Node directory.

  Returns:
    The journal's `command`, or "unknown".
  """
  try:
    with open(
        os.path.join(base_dir, JOURNAL_FILENAME), "r", encoding="utf-8"
    ) as f:
      data = json.load(f)
  except (OSError, ValueError):
    return "unknown"
  if not isinstance(data, dict):
    return "unknown"
  return str(data.get("command") or "unknown")
