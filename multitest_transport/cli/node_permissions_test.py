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

"""Unit tests for the filesystem permission model.

The chown and chmod syscalls run for real against a temporary tree. Forge
shards are not root, so every test targets the process's own gid: a chown to a
foreign group would be EPERM and would only ever exercise the error path.
"""

import grp
import os
import stat
from unittest import mock

from absl.testing import absltest

from multitest_transport.cli import node_permissions


def _Mode(path: str) -> int:
  return stat.S_IMODE(os.lstat(path).st_mode)


def _Gid(path: str) -> int:
  return os.lstat(path).st_gid


class NodePermissionsTest(absltest.TestCase):

  def setUp(self):
    super().setUp()
    root = self.create_tempdir().full_path
    self.static_dir = os.path.join(root, "etc_mtt")
    self.base_dir = os.path.join(root, "var_lib_mttnode")
    os.makedirs(self.static_dir)
    os.makedirs(self.base_dir)
    self.gid = os.getgid()

  def _BuildTrees(self):
    """Lays down a representative tree in both roots, including a symlink."""
    os.makedirs(os.path.join(self.static_dir, "config"))
    os.makedirs(os.path.join(self.static_dir, "secrets"))
    self.create_tempfile(
        os.path.join(self.static_dir, "secrets", "sa-key.json"), content="{}"
    )
    self.create_tempfile(
        os.path.join(self.static_dir, "config", "mtt_flags.yaml"),
        content="a: 1",
    )
    release_dir = os.path.join(self.base_dir, "core", "releases", "sha256_abc")
    os.makedirs(release_dir)
    self.create_tempfile(
        os.path.join(release_dir, "pinned_mtt_flags.yaml"), content="a: 1"
    )
    self.create_tempfile(
        os.path.join(self.base_dir, "journal.json"), content="{}"
    )
    self.active_link = os.path.join(self.base_dir, "core", "active")
    os.symlink(release_dir, self.active_link)
    return release_dir

  # ==========================================================================
  # ResolveGroupGid / DeriveGroupGid / GroupName
  # ==========================================================================

  def testResolveGroupGid(self):
    name = grp.getgrgid(self.gid).gr_name
    self.assertEqual(node_permissions.ResolveGroupGid(name), self.gid)

  def testResolveGroupGid_missingGroup(self):
    with self.assertRaises(node_permissions.PermissionPolicyError) as ctx:
      node_permissions.ResolveGroupGid("no_such_mtt_group")
    message = str(ctx.exception)
    self.assertIn("does not exist on this host", message)
    self.assertIn("groupadd no_such_mtt_group", message)

  def testDeriveGroupGid(self):
    self.assertEqual(
        node_permissions.DeriveGroupGid(self.static_dir), _Gid(self.static_dir)
    )

  def testDeriveGroupGid_absentDir(self):
    self.assertIsNone(
        node_permissions.DeriveGroupGid(
            os.path.join(self.static_dir, "nowhere")
        )
    )

  def testGroupName_unknownGid(self):
    # Well above any real gid, so it cannot resolve to a name.
    self.assertEqual(node_permissions.GroupName(4294967000), "4294967000")

  # ==========================================================================
  # RequireRoot
  # ==========================================================================

  @mock.patch.object(os, "geteuid", return_value=0)
  def testRequireRoot_asRoot(self, unused_geteuid):
    node_permissions.RequireRoot("mtt node worker init")

  @mock.patch.object(os, "geteuid", return_value=1000)
  def testRequireRoot_asUser(self, unused_geteuid):
    with self.assertRaises(node_permissions.PermissionPolicyError) as ctx:
      node_permissions.RequireRoot("mtt node worker init")
    self.assertIn("must be run as root", str(ctx.exception))

  # ==========================================================================
  # CheckMembership
  # ==========================================================================

  @mock.patch.object(os, "geteuid", return_value=0)
  def testCheckMembership_rootBypasses(self, unused_geteuid):
    # Root is not in the mtt group, and `sudo restart` is a valid recovery
    # path on a host whose permissions are damaged.
    with mock.patch.object(os, "getgroups", return_value=[]):
      node_permissions.CheckMembership(self.static_dir)

  @mock.patch.object(os, "geteuid", return_value=1000)
  def testCheckMembership_member(self, unused_geteuid):
    node_permissions.CheckMembership(self.static_dir)

  @mock.patch.object(os, "geteuid", return_value=1000)
  def testCheckMembership_nonMember(self, unused_geteuid):
    foreign_gid = self.gid + 4242
    with mock.patch.object(
        node_permissions, "DeriveGroupGid", return_value=foreign_gid
    ):
      with self.assertRaises(node_permissions.PermissionPolicyError) as ctx:
        node_permissions.CheckMembership(self.static_dir)
    message = str(ctx.exception)
    self.assertIn("not an active member of group", message)
    self.assertIn("usermod -aG", message)
    self.assertIn("newgrp", message)

  @mock.patch.object(os, "geteuid", return_value=1000)
  def testCheckMembership_unprovisionedHost(self, unused_geteuid):
    # Nothing is provisioned, so there is no group to belong to: the command
    # must reach its own "no configuration found" error instead.
    node_permissions.CheckMembership(os.path.join(self.static_dir, "nowhere"))

  def testCheckMembership_primaryGidCounts(self):
    # POSIX does not require the primary gid to appear in getgroups(), so a
    # member whose mtt group is their primary group must still pass.
    with mock.patch.object(os, "geteuid", return_value=1000), mock.patch.object(
        os, "getgroups", return_value=[]
    ):
      node_permissions.CheckMembership(self.static_dir)

  # ==========================================================================
  # os.path.exists behaviour the preflight exists to prevent
  # ==========================================================================

  def testOsPathExists_masksEaccesAsFalse(self):
    if os.geteuid() == 0:
      self.skipTest("root bypasses directory mode checks")
    tunnel_dir = os.path.join(self.base_dir, "tunnel")
    os.makedirs(tunnel_dir)
    env_path = os.path.join(tunnel_dir, "docker-compose.env")
    self.create_tempfile(env_path, content="A=1")
    os.chmod(tunnel_dir, 0o000)
    try:
      # Not an exception: a silent False. This is why `status` is gated on
      # membership rather than left to report DOWN.
      self.assertFalse(os.path.exists(env_path))
    finally:
      os.chmod(tunnel_dir, 0o700)

  # ==========================================================================
  # CopyFileWithMode
  # ==========================================================================

  def testCopyFileWithMode(self):
    src = self.create_tempfile("src.yaml", content="a: 1").full_path
    os.chmod(src, 0o640)
    dst = os.path.join(self.base_dir, "dst.yaml")
    node_permissions.CopyFileWithMode(
        src, dst, node_permissions.BASE_FILE_MODE
    )
    self.assertEqual(_Mode(dst), node_permissions.BASE_FILE_MODE)
    with open(dst, "r", encoding="utf-8") as f:
      self.assertEqual(f.read(), "a: 1")

  def testCopyFileWithMode_replacesExistingMode(self):
    # shutil.copyfile keeps the *destination's* mode, so an existing file left
    # at 0600 by an older run would silently stay unreadable to the group.
    src = self.create_tempfile("src.yaml", content="a: 1").full_path
    dst = os.path.join(self.base_dir, "dst.yaml")
    self.create_tempfile(dst, content="old")
    os.chmod(dst, 0o600)
    node_permissions.CopyFileWithMode(
        src, dst, node_permissions.BASE_FILE_MODE
    )
    self.assertEqual(_Mode(dst), node_permissions.BASE_FILE_MODE)

  # ==========================================================================
  # ApplyPolicy
  # ==========================================================================

  def testApplyPolicy_modes(self):
    self._BuildTrees()
    node_permissions.ApplyPolicy(
        self.gid, static_dir=self.static_dir, base_dir=self.base_dir
    )
    self.assertEqual(_Mode(self.static_dir), node_permissions.STATIC_DIR_MODE)
    self.assertEqual(
        _Mode(os.path.join(self.static_dir, "secrets")),
        node_permissions.STATIC_DIR_MODE,
    )
    self.assertEqual(
        _Mode(os.path.join(self.static_dir, "secrets", "sa-key.json")),
        node_permissions.STATIC_FILE_MODE,
    )
    self.assertEqual(_Mode(self.base_dir), node_permissions.BASE_DIR_MODE)
    self.assertEqual(
        _Mode(os.path.join(self.base_dir, "core", "releases")),
        node_permissions.BASE_DIR_MODE,
    )
    self.assertEqual(
        _Mode(os.path.join(self.base_dir, "journal.json")),
        node_permissions.BASE_FILE_MODE,
    )

  def testApplyPolicy_group(self):
    self._BuildTrees()
    node_permissions.ApplyPolicy(
        self.gid, static_dir=self.static_dir, base_dir=self.base_dir
    )
    for path in (
        self.static_dir,
        os.path.join(self.static_dir, "secrets", "sa-key.json"),
        self.base_dir,
        os.path.join(self.base_dir, "journal.json"),
    ):
      self.assertEqual(_Gid(path), self.gid, msg=path)

  def testApplyPolicy_symlinkNeverChmoded(self):
    release_dir = self._BuildTrees()
    os.chmod(release_dir, 0o700)
    node_permissions.ApplyPolicy(self.gid, base_dir=self.base_dir)
    # os.chmod follows symlinks on Linux, so chmod-ing core/active would have
    # been applied to the release directory behind it. Confirm the target was
    # reached through its own path, and that the link itself kept the 0777
    # every Linux symlink carries.
    self.assertEqual(_Mode(release_dir), node_permissions.BASE_DIR_MODE)
    self.assertEqual(_Mode(self.active_link), 0o777)
    self.assertTrue(os.path.islink(self.active_link))

  def testApplyPolicy_idempotent(self):
    self._BuildTrees()
    node_permissions.ApplyPolicy(
        self.gid, static_dir=self.static_dir, base_dir=self.base_dir
    )
    first = node_permissions.SnapshotTree(self.base_dir, "base")
    node_permissions.ApplyPolicy(
        self.gid, static_dir=self.static_dir, base_dir=self.base_dir
    )
    self.assertEqual(
        first, node_permissions.SnapshotTree(self.base_dir, "base")
    )

  def testApplyPolicy_repairsLegacyTree(self):
    self._BuildTrees()
    os.chmod(self.static_dir, 0o755)
    os.chmod(os.path.join(self.static_dir, "secrets"), 0o700)
    os.chmod(
        os.path.join(self.static_dir, "secrets", "sa-key.json"), 0o600
    )
    node_permissions.ApplyPolicy(self.gid, static_dir=self.static_dir)
    self.assertEqual(_Mode(self.static_dir), node_permissions.STATIC_DIR_MODE)
    self.assertEqual(
        _Mode(os.path.join(self.static_dir, "secrets")),
        node_permissions.STATIC_DIR_MODE,
    )
    self.assertEqual(
        _Mode(os.path.join(self.static_dir, "secrets", "sa-key.json")),
        node_permissions.STATIC_FILE_MODE,
    )

  def testApplyPolicy_absentTreesAreSkipped(self):
    node_permissions.ApplyPolicy(
        self.gid,
        static_dir=os.path.join(self.static_dir, "nowhere"),
        base_dir=os.path.join(self.base_dir, "nowhere"),
    )

  def testApplyPolicy_setgidInheritance(self):
    supplementary = [
        g for g in os.getgroups() if g != os.getgid() and g != 0
    ]
    if not supplementary:
      self.skipTest("no supplementary group to distinguish inheritance from")
    other_gid = supplementary[0]
    node_permissions.ApplyPolicy(other_gid, base_dir=self.base_dir)
    child = os.path.join(self.base_dir, "created_after")
    os.makedirs(child)
    self.assertEqual(_Gid(child), other_gid)

  def testCreateAndApplyPolicy_createsMissingTrees(self):
    static_dir = os.path.join(self.static_dir, "fresh_static")
    base_dir = os.path.join(self.base_dir, "fresh_base")
    node_permissions.CreateAndApplyPolicy(self.gid, static_dir, base_dir)
    self.assertEqual(_Mode(static_dir), node_permissions.STATIC_DIR_MODE)
    self.assertEqual(_Mode(base_dir), node_permissions.BASE_DIR_MODE)

  # ==========================================================================
  # Snapshot and drift detection
  # ==========================================================================

  def testSnapshotTree_symlinkCarriesNoMode(self):
    self._BuildTrees()
    node_permissions.ApplyPolicy(self.gid, base_dir=self.base_dir)
    entries = node_permissions.SnapshotTree(self.base_dir, "base")
    entry = next(e for e in entries if e["path"] == "base:/core/active")
    self.assertEqual(entry["type"], "symlink")
    self.assertNotIn("mode", entry)

  def testDetectDrift_clean(self):
    self._BuildTrees()
    node_permissions.FinalizeProvisioning(
        self.gid, self.static_dir, self.base_dir
    )
    self.assertEmpty(
        node_permissions.DetectDrift(self.static_dir, self.base_dir)
    )

  def testDetectDrift_modeChanged(self):
    self._BuildTrees()
    node_permissions.FinalizeProvisioning(
        self.gid, self.static_dir, self.base_dir
    )
    os.chmod(os.path.join(self.base_dir, "journal.json"), 0o644)
    drift = node_permissions.DetectDrift(self.static_dir, self.base_dir)
    self.assertLen(drift, 1)
    self.assertEqual(drift[0]["path"], "base:/journal.json")
    self.assertIn("0660", drift[0]["expected"])
    self.assertIn("0644", drift[0]["actual"])

  def testDetectDrift_pathsCreatedAfterProvisioningAreClean(self):
    # base_dir is nearly empty at provisioning time; `start` creates almost
    # everything in it later. Checking the live tree against the policy ensures
    # runtime-created paths with valid group and mode are not reported as drift.
    self._BuildTrees()
    node_permissions.FinalizeProvisioning(
        self.gid, self.static_dir, self.base_dir
    )
    new_release = os.path.join(self.base_dir, "core", "releases", "sha256_new")
    os.makedirs(new_release)
    os.chmod(new_release, node_permissions.BASE_DIR_MODE)
    new_file = os.path.join(new_release, "pinned_mtt_flags.yaml")
    with open(new_file, "w", encoding="utf-8") as f:
      f.write("a: 1")
    os.chmod(new_file, node_permissions.BASE_FILE_MODE)

    self.assertEmpty(
        node_permissions.DetectDrift(self.static_dir, self.base_dir)
    )

  def testDetectDrift_pathCreatedAfterProvisioningIsStillChecked(self):
    self._BuildTrees()
    node_permissions.FinalizeProvisioning(
        self.gid, self.static_dir, self.base_dir
    )
    stray = os.path.join(self.base_dir, "stray.txt")
    with open(stray, "w", encoding="utf-8") as f:
      f.write("x")
    os.chmod(stray, 0o600)

    drift = node_permissions.DetectDrift(self.static_dir, self.base_dir)
    self.assertLen(drift, 1)
    self.assertEqual(drift[0]["path"], "base:/stray.txt")
    self.assertIn("0600", drift[0]["actual"])

  def testDetectDrift_symlinkModeIsNotChecked(self):
    # A symlink's own mode is always 0777, so checking it against the file
    # mode would report core/active as drift on every single failure.
    self._BuildTrees()
    node_permissions.FinalizeProvisioning(
        self.gid, self.static_dir, self.base_dir
    )
    paths = [
        d["path"]
        for d in node_permissions.DetectDrift(self.static_dir, self.base_dir)
    ]
    self.assertNotIn("base:/core/active", paths)

  def testDetectDrift_unprovisionedStaticDir(self):
    drift = node_permissions.DetectDrift(
        os.path.join(self.static_dir, "nonexistent"), self.base_dir
    )
    # There is no owning group to check against, so one entry saying so beats
    # reporting every path in base_dir against a guess.
    self.assertLen(drift, 1)
    self.assertEqual(drift[0]["actual"], "missing or unreadable")

  def testFormatDrift(self):
    text = node_permissions.FormatDrift(
        [{"path": "base:/", "expected": "docker 2770", "actual": "root 0755"}],
        "worker",
    )
    self.assertIn("base:/", text)
    self.assertIn("docker 2770", text)
    self.assertIn("sudo mtt node worker init", text)

  # ==========================================================================
  # SetUmask
  # ==========================================================================

  def testSetUmask(self):
    previous = node_permissions.SetUmask()
    try:
      self.assertEqual(os.umask(node_permissions.UMASK), node_permissions.UMASK)
    finally:
      os.umask(previous)


if __name__ == "__main__":
  absltest.main()
