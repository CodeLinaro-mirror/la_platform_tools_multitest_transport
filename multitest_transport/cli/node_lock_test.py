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

"""Unit tests for node_lock."""

import errno
import fcntl
import json
import os
import stat
from unittest import mock
from absl.testing import absltest
from multitest_transport.cli import node_lock
from multitest_transport.cli import node_permissions


class NodeLockTest(absltest.TestCase):

  def setUp(self):
    super().setUp()
    self.base_dir = self.create_tempdir().full_path
    self.lock_file = os.path.join(self.base_dir, node_lock.LOCK_FILENAME)

  def _HoldLock(self) -> int:
    """Holds the lock from a separate open file description, like another process."""
    fd = os.open(self.lock_file, os.O_CREAT | os.O_RDWR, 0o660)
    self.addCleanup(os.close, fd)
    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    return fd

  def _PatchContendedFlock(self, busy_attempts: int) -> list[int]:
    """Makes the first exclusive attempts fail as if another process held it.

    Only `LOCK_EX | LOCK_NB` calls are counted and failed; everything else
    (including the unlock in Release) goes to the real `flock`.

    Args:
      busy_attempts: Number of exclusive attempts that fail with EAGAIN.

    Returns:
      A list that records every exclusive attempt, for assertions.
    """
    real_flock = fcntl.flock
    attempts: list[int] = []

    def ContendedFlock(fd, operation):
      if operation == fcntl.LOCK_EX | fcntl.LOCK_NB:
        attempts.append(operation)
        if len(attempts) <= busy_attempts:
          raise OSError(errno.EAGAIN, "Resource temporarily unavailable")
      return real_flock(fd, operation)

    self.enterContext(
        mock.patch.object(node_lock.fcntl, "flock", side_effect=ContendedFlock)
    )
    return attempts

  def testAcquire_isNonInheritableWithPolicyModeAndReleasable(self):
    fd = node_lock.Acquire(self.base_dir)

    self.assertIsNotNone(fd)
    assert fd is not None
    try:
      # Child processes such as `mtt -vv start` must not keep the lock.
      self.assertFalse(os.get_inheritable(fd))
      self.assertEqual(
          stat.S_IMODE(os.fstat(fd).st_mode), node_permissions.BASE_FILE_MODE
      )
      self.assertTrue(node_lock.IsHeld(self.base_dir))
    finally:
      node_lock.Release(fd)
    self.assertFalse(node_lock.IsHeld(self.base_dir))

  def testAcquire_createsMissingBaseDir(self):
    base_dir = os.path.join(self.base_dir, "missing", "mttnode")

    fd = node_lock.Acquire(base_dir)

    self.assertIsNotNone(fd)
    assert fd is not None
    node_lock.Release(fd)
    self.assertTrue(os.path.isdir(base_dir))

  def testAcquire_outlastsAStatusProbe(self):
    # A `status` probe holds the lock for microseconds. Two contended attempts
    # stand in for it; the clock does not advance, so the grace period cannot
    # run out however slowly the test machine schedules us.
    attempts = self._PatchContendedFlock(busy_attempts=2)
    mock_sleep = self.enterContext(mock.patch.object(node_lock.time, "sleep"))
    self.enterContext(
        mock.patch.object(node_lock.time, "monotonic", return_value=0.0)
    )

    fd = node_lock.Acquire(self.base_dir)

    self.assertIsNotNone(fd)
    assert fd is not None
    node_lock.Release(fd)
    self.assertLen(attempts, 3)
    self.assertEqual(
        mock_sleep.call_args_list,
        [mock.call(node_lock._LOCK_RETRY_SEC)] * 2,  
    )

  def testAcquire_givesUpAfterGracePeriod(self):
    # A real command holds the lock for seconds: every attempt is contended,
    # and the third clock reading is past the deadline.
    attempts = self._PatchContendedFlock(busy_attempts=100)
    mock_sleep = self.enterContext(mock.patch.object(node_lock.time, "sleep"))
    self.enterContext(
        mock.patch.object(
            node_lock.time, "monotonic", side_effect=[0.0, 0.0, 0.0, 1.0]
        )
    )

    self.assertIsNone(node_lock.Acquire(self.base_dir))
    self.assertLen(attempts, 3)
    self.assertEqual(mock_sleep.call_count, 2)

  def testAcquire_heldByAnotherOpenFileIsReported(self):
    self._HoldLock()

    self.assertIsNone(node_lock.Acquire(self.base_dir))

  def testIsHeld_createsNothingWhenThereIsNoLockFile(self):
    self.assertFalse(node_lock.IsHeld(self.base_dir))
    self.assertFalse(os.path.exists(self.lock_file))

  def testIsHeld_reportsAHeldLock(self):
    self._HoldLock()

    self.assertTrue(node_lock.IsHeld(self.base_dir))

  def testHolderCommand(self):
    self.assertEqual(node_lock.HolderCommand(self.base_dir), "unknown")

    with open(
        os.path.join(self.base_dir, node_lock.JOURNAL_FILENAME),
        "w",
        encoding="utf-8",
    ) as f:
      json.dump({"command": "UpgradeCore", "started_at": "t0"}, f)

    self.assertEqual(node_lock.HolderCommand(self.base_dir), "UpgradeCore")


if __name__ == "__main__":
  absltest.main()
