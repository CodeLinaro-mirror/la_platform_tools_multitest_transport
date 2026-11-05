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

"""Unit tests for node_provision."""

import fcntl
import json
import os
import stat
from unittest import mock
from absl.testing import absltest
from multitest_transport.cli import docker_image
from multitest_transport.cli import node_lock
from multitest_transport.cli import node_permissions
from multitest_transport.cli import node_provision


class NodeProvisionTest(absltest.TestCase):

  def setUp(self):
    super().setUp()
    previous_umask = os.umask(0o022)
    os.umask(previous_umask)
    self.addCleanup(os.umask, previous_umask)
    self.static_dir = self.create_tempdir().full_path
    self.base_dir = os.path.join(self.create_tempdir().full_path, "mttnode")
    os.makedirs(os.path.join(self.base_dir, "core", "releases", "old"))
    self.mock_image_executor = mock.create_autospec(
        docker_image.DockerImageExecutor, instance=True, spec_set=True
    )
    self.mock_image_executor.GetContainerStatus.return_value = (
        docker_image.ContainerStatus.NOT_RUNNING
    )
    self.mock_image_executor.ListRunningComposeContainers.return_value = []

  def _Reprovisioning(self):
    return node_provision.Reprovisioning(
        self.static_dir, self.base_dir, self.mock_image_executor
    )

  def _WriteJournal(self, command: str) -> None:
    with open(
        os.path.join(self.base_dir, node_lock.JOURNAL_FILENAME),
        "w",
        encoding="utf-8",
    ) as f:
      json.dump({"command": command, "started_at": "t0"}, f)

  def testReprovisioning_resetEmptiesBaseDirButKeepsTheLock(self):
    self._WriteJournal("Start")
    active = os.path.join(self.base_dir, "core", "active")
    os.symlink(os.path.join(self.base_dir, "core", "releases", "old"), active)
    lock_inode = None

    with self._Reprovisioning() as reset:
      lock_inode = os.stat(
          os.path.join(self.base_dir, node_lock.LOCK_FILENAME)
      ).st_ino
      reset()
      # Still held after the reset, on the very file it was taken on: a
      # command started now finds the node busy.
      self.assertTrue(node_lock.IsHeld(self.base_dir))
      self.assertEqual(
          os.stat(os.path.join(self.base_dir, node_lock.LOCK_FILENAME)).st_ino,
          lock_inode,
      )

    # Everything else is gone, releases and journal included, so the next
    # `start` is a first start; the directory is back under the policy.
    self.assertEqual(os.listdir(self.base_dir), [node_lock.LOCK_FILENAME])
    self.assertEqual(
        stat.S_IMODE(os.stat(self.base_dir).st_mode),
        node_permissions.BASE_DIR_MODE,
    )
    self.assertFalse(node_lock.IsHeld(self.base_dir))

  def testReprovisioning_withoutResetLeavesBaseDirAlone(self):
    with self._Reprovisioning():
      pass

    self.assertTrue(
        os.path.isdir(os.path.join(self.base_dir, "core", "releases", "old"))
    )
    self.assertFalse(node_lock.IsHeld(self.base_dir))

  def testReprovisioning_missingBaseDirIsNotCreatedByThePrecheck(self):
    base_dir = os.path.join(self.create_tempdir().full_path, "mttnode")

    with node_provision.Reprovisioning(
        self.static_dir, base_dir, self.mock_image_executor
    ):
      # A refused or aborted re-provisioning must leave the host as it was.
      self.assertFalse(os.path.exists(base_dir))

    self.assertFalse(os.path.exists(base_dir))

  def testReprovisioning_resetCreatesAndLocksAMissingBaseDir(self):
    base_dir = os.path.join(self.create_tempdir().full_path, "mttnode")

    with node_provision.Reprovisioning(
        self.static_dir, base_dir, self.mock_image_executor
    ) as reset:
      reset()
      self.assertTrue(node_lock.IsHeld(base_dir))

    self.assertEqual(os.listdir(base_dir), [node_lock.LOCK_FILENAME])
    self.assertEqual(
        stat.S_IMODE(os.stat(base_dir).st_mode),
        node_permissions.BASE_DIR_MODE,
    )
    self.assertFalse(node_lock.IsHeld(base_dir))

  def testReprovisioning_runningCoreIsRefused(self):
    # An unhealthy container is still running and still has to be stopped.
    for status in (
        docker_image.ContainerStatus.HEALTHY,
        docker_image.ContainerStatus.UNHEALTHY,
    ):
      self.mock_image_executor.GetContainerStatus.return_value = status

      with self.assertRaisesRegex(
          node_provision.ReprovisionError, "core container 'mtt'"
      ) as cm:
        with self._Reprovisioning():
          self.fail("A running node must not be re-provisioned.")

      # The role being provisioned may not be the role the node runs as, so
      # the operator is given both stop commands rather than a guess.
      self.assertIn("mtt node worker stop", str(cm.exception))
      self.assertIn("mtt node controller stop", str(cm.exception))
      self.assertTrue(os.path.isdir(os.path.join(self.base_dir, "core")))
      self.assertFalse(node_lock.IsHeld(self.base_dir))

  def testReprovisioning_runningTunnelIsRefusedWhateverItsRoleOrHealth(self):
    self.mock_image_executor.ListRunningComposeContainers.return_value = [
        "tunnel-acceptor-1",
        "tunnel-esp-1",
    ]

    with self.assertRaisesRegex(
        node_provision.ReprovisionError, "tunnel-acceptor-1, tunnel-esp-1"
    ):
      with self._Reprovisioning():
        self.fail("A running tunnel must not be reset underneath.")

    # Found by compose project label, so profiles and health play no part.
    self.mock_image_executor.ListRunningComposeContainers.assert_called_once_with(
        "tunnel"
    )

  def testReprovisioning_heldLockIsReportedNotWaitedFor(self):
    lock_fd = os.open(
        os.path.join(self.base_dir, node_lock.LOCK_FILENAME),
        os.O_CREAT | os.O_RDWR,
        0o660,
    )
    self.addCleanup(os.close, lock_fd)
    fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    self._WriteJournal("UpgradeCore")

    with self.assertRaisesRegex(node_provision.ReprovisionError, "UpgradeCore"):
      with self._Reprovisioning():
        self.fail("Another command holds the node.")

    self.assertTrue(os.path.isdir(os.path.join(self.base_dir, "core")))
    self.mock_image_executor.GetContainerStatus.assert_not_called()

  def testReprovisioning_symlinkedBaseDirIsRefusedBeforeTouchingIt(self):
    target = self.create_tempdir().full_path
    link = os.path.join(self.create_tempdir().full_path, "mttnode")
    os.symlink(target, link)

    with self.assertRaisesRegex(node_provision.ReprovisionError, "symlink"):
      with node_provision.Reprovisioning(
          self.static_dir, link, self.mock_image_executor
      ):
        self.fail("A symlinked node runtime directory must not be reset.")

    # Not even the lock file is created through the link.
    self.assertEqual(os.listdir(target), [])

  def testCheckBaseDirPaths_refusesUnsafePaths(self):
    with self.assertRaisesRegex(node_provision.ReprovisionError, "overlap"):
      node_provision.CheckBaseDirPaths(
          self.static_dir, os.path.join(self.static_dir, "mttnode")
      )
    with self.assertRaisesRegex(node_provision.ReprovisionError, "overlap"):
      node_provision.CheckBaseDirPaths(
          os.path.join(self.base_dir, "etc"), self.base_dir
      )
    not_a_dir = os.path.join(self.create_tempdir().full_path, "mttnode")
    with open(not_a_dir, "w", encoding="utf-8") as f:
      f.write("")
    with self.assertRaisesRegex(
        node_provision.ReprovisionError, "not a directory"
    ):
      node_provision.CheckBaseDirPaths(self.static_dir, not_a_dir)

    # Separate trees are fine.
    node_provision.CheckBaseDirPaths(self.static_dir, self.base_dir)

  def testInspectNode_describesWhatIsRunning(self):
    self.assertFalse(
        node_provision.InspectNode(self.mock_image_executor).running
    )

    self.mock_image_executor.GetContainerStatus.return_value = (
        docker_image.ContainerStatus.HEALTHY
    )
    self.mock_image_executor.ListRunningComposeContainers.return_value = [
        "tunnel-dialer-1"
    ]
    footprint = node_provision.InspectNode(self.mock_image_executor)

    self.assertTrue(footprint.running)
    self.assertEqual(
        footprint.Describe(), "core container 'mtt'; tunnel (tunnel-dialer-1)"
    )


if __name__ == "__main__":
  absltest.main()
