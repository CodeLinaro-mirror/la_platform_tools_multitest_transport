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

"""Release directory management data plane for MTT Node.

Manages template configs, tunnel compose environment files, versioned release
directories under <baseDir>/core/releases/<image_ref>-<config_hash>/, atomic
symlink transitions between staging and active releases, path getters, and
release pruning.
"""

import hashlib
import json
import logging
import os
import re
import shutil
from typing import Any, Optional
import uuid
from multitest_transport.cli import node_permissions
import yaml

logger = logging.getLogger(__name__)

_LAB_CONFIG_FILENAME = "lab_config.yaml"
_UNPINNED_FLAGS_FILENAME = "mtt_flags.yaml"
_PINNED_FLAGS_FILENAME = "pinned_mtt_flags.yaml"
_COMPOSE_ENV_FILENAME = "docker-compose.env"
_CONFIG_VERSIONS_FILENAME = "config_versions.json"
_REVISION_FILENAME = "revision.json"
_CONFIG_HASH_LEN = 12


def _SanitizeImageRef(image_ref: str) -> str:
  """Sanitizes an image reference into a filesystem-safe directory name."""
  sanitized = re.sub(r"[^a-zA-Z0-9._-]", "_", image_ref)
  return sanitized.strip("_")


def _HashConfigInputs(lab_config_path: str, flags: list[str]) -> str:
  """Computes a short deterministic SHA-256 hash of lab_config and flags."""
  hasher = hashlib.sha256()
  if os.path.exists(lab_config_path):
    hasher.update(b"lab_config:present\n")
    with open(lab_config_path, "rb") as f:
      hasher.update(f.read())
  else:
    hasher.update(b"lab_config:absent\n")
  hasher.update(b"\nflags:")
  hasher.update(
      json.dumps([str(f) for f in flags], separators=(",", ":")).encode("utf-8")
  )
  return hasher.hexdigest()[:_CONFIG_HASH_LEN]


def _BuildRevisionDict(image_ref: str, src_dir: str) -> dict[str, str]:
  """Builds the revision.json payload from image_ref and config_versions.json."""
  revision: dict[str, str] = {"build": image_ref}
  versions_path = os.path.join(src_dir, _CONFIG_VERSIONS_FILENAME)
  if os.path.exists(versions_path):
    try:
      with open(versions_path, "r", encoding="utf-8") as f:
        versions_data = json.load(f)
      if isinstance(versions_data, dict):
        for key in ("tenant_config_version", "pool_config_version"):
          val = versions_data.get(key)
          if val:
            revision[key] = str(val)
    except (OSError, ValueError):
      logger.warning(
          "Could not read %s; writing build-only revision.", versions_path
      )
  return revision


def _WriteJsonWithMode(path: str, data: dict[str, Any], mode: int) -> None:
  """Atomically writes a JSON file with explicit file mode."""
  parent = os.path.dirname(path)
  temp_path = os.path.join(parent, f".tmp_{uuid.uuid4().hex[:8]}.json")
  try:
    with open(temp_path, "w", encoding="utf-8") as f:
      json.dump(data, f, indent=2)
    os.chmod(temp_path, mode)
    os.replace(temp_path, path)
  finally:
    if os.path.exists(temp_path):
      try:
        os.remove(temp_path)
      except OSError:
        pass


class ReleaseDirectoryManager:
  """Manages staging and active release directories and atomic symlink transitions."""

  def __init__(self, base_dir: str = "."):
    self._base_dir = os.path.abspath(base_dir)
    self._config_dir = os.path.join(self._base_dir, "config")
    self._tunnel_dir = os.path.join(self._base_dir, "tunnel")
    self._core_dir = os.path.join(self._base_dir, "core")
    self._releases_dir = os.path.join(self._core_dir, "releases")
    self._staging_symlink = os.path.join(self._core_dir, "staging")
    self._active_symlink = os.path.join(self._core_dir, "active")

    os.makedirs(self._config_dir, exist_ok=True)
    os.makedirs(self._tunnel_dir, exist_ok=True)
    os.makedirs(self._releases_dir, exist_ok=True)

  @property
  def config_dir(self) -> str:
    return self._config_dir

  @property
  def tunnel_dir(self) -> str:
    return self._tunnel_dir

  @property
  def core_dir(self) -> str:
    return self._core_dir

  @property
  def config_lab_config_path(self) -> str:
    """Returns the path to lab_config.yaml in the config directory."""
    return os.path.join(self._config_dir, _LAB_CONFIG_FILENAME)

  @property
  def config_flags_path(self) -> str:
    """Returns the path to mtt_flags.yaml in the config directory."""
    return os.path.join(self._config_dir, _UNPINNED_FLAGS_FILENAME)

  @property
  def config_compose_env_path(self) -> str:
    """Returns desired compose env path in config/ (materialized from PM/static)."""
    return os.path.join(self._config_dir, _COMPOSE_ENV_FILENAME)

  @property
  def config_versions_path(self) -> str:
    """Returns the path to config_versions.json in the config directory."""
    return os.path.join(self._config_dir, _CONFIG_VERSIONS_FILENAME)

  @property
  def tunnel_compose_env_path(self) -> str:
    """Returns applied compose env path in tunnel/ (snapshot read by compose)."""
    return os.path.join(self._tunnel_dir, _COMPOSE_ENV_FILENAME)

  @property
  def active_config_path(self) -> str:
    """Returns the path to lab_config.yaml in the active release."""
    return os.path.join(self._active_symlink, _LAB_CONFIG_FILENAME)

  @property
  def active_flags_path(self) -> str:
    """Returns the path to pinned_mtt_flags.yaml in the active release."""
    return os.path.join(self._active_symlink, _PINNED_FLAGS_FILENAME)

  @property
  def active_revision_path(self) -> str:
    """Returns the path to revision.json in the active release."""
    return os.path.join(self._active_symlink, _REVISION_FILENAME)

  @property
  def staging_config_path(self) -> str:
    """Returns the path to lab_config.yaml in the staging release."""
    return os.path.join(self._staging_symlink, _LAB_CONFIG_FILENAME)

  @property
  def staging_flags_path(self) -> str:
    """Returns the path to pinned_mtt_flags.yaml in the staging release."""
    return os.path.join(self._staging_symlink, _PINNED_FLAGS_FILENAME)

  @property
  def staging_revision_path(self) -> str:
    """Returns the path to revision.json in the staging release."""
    return os.path.join(self._staging_symlink, _REVISION_FILENAME)

  @property
  def has_active_release(self) -> bool:
    """Returns True if the active symlink points to a valid release."""
    return os.path.islink(self._active_symlink) and os.path.exists(
        self._active_symlink
    )

  @property
  def has_staging_release(self) -> bool:
    """Returns True if the staging symlink points to a valid release."""
    return os.path.islink(self._staging_symlink) and os.path.exists(
        self._staging_symlink
    )

  @property
  def _active_release_dir(self) -> Optional[str]:
    """Returns the target directory of the active symlink, or None."""
    if os.path.islink(self._active_symlink):
      return os.path.realpath(self._active_symlink)
    return None

  @property
  def _staging_release_dir(self) -> Optional[str]:
    """Returns the target directory of the staging symlink, or None."""
    if os.path.islink(self._staging_symlink):
      return os.path.realpath(self._staging_symlink)
    return None

  def _AtomicSymlink(self, target: str, link_path: str) -> None:
    """Atomically points link_path to target using a temporary symlink and os.replace."""
    temp_link = os.path.join(self._core_dir, f".link_{uuid.uuid4().hex}")
    try:
      os.symlink(target, temp_link)
      os.replace(temp_link, link_path)
    finally:
      if os.path.islink(temp_link) or os.path.exists(temp_link):
        try:
          os.unlink(temp_link)
        except OSError:
          pass

  def StageTunnelEnv(self, source_dir: Optional[str] = None) -> str:
    """Copies docker-compose.env from source_dir (defaults to config_dir) to tunnel/."""
    src_dir = os.path.abspath(source_dir) if source_dir else self._config_dir
    src_env = os.path.join(src_dir, _COMPOSE_ENV_FILENAME)

    if not os.path.exists(src_env):
      raise FileNotFoundError(
          f"Source docker-compose.env not found at: {src_env}"
      )

    dst_env = self.tunnel_compose_env_path
    node_permissions.CopyFileWithMode(
        src_env, dst_env, node_permissions.BASE_FILE_MODE
    )
    logger.info("Staged tunnel docker-compose.env at %s", dst_env)
    return dst_env

  def ComputeConfigHash(self, source_dir: Optional[str] = None) -> str:
    """Computes the deterministic config hash for source_dir (or config_dir)."""
    src_dir = os.path.abspath(source_dir) if source_dir else self._config_dir
    src_lab_config = os.path.join(src_dir, _LAB_CONFIG_FILENAME)
    src_flags_config = os.path.join(src_dir, _UNPINNED_FLAGS_FILENAME)
    if not os.path.exists(src_flags_config):
      raise FileNotFoundError(
          f"Source mtt_flags.yaml not found at: {src_flags_config}"
      )
    with open(src_flags_config, "r", encoding="utf-8") as f:
      src_flags_data = yaml.safe_load(f) or {}
    flags = (
        [str(x) for x in (src_flags_data.get("flags") or [])]
        if isinstance(src_flags_data, dict)
        else []
    )
    return _HashConfigInputs(src_lab_config, flags)

  def GetActiveImageRef(self) -> Optional[str]:
    """Returns the image_ref recorded in core/active, or None if unavailable."""
    if not self.has_active_release or not os.path.exists(
        self.active_flags_path
    ):
      return None
    try:
      with open(self.active_flags_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    except (OSError, yaml.YAMLError):
      return None
    if not isinstance(data, dict):
      return None
    ref = str(data.get("image_ref") or "").strip()
    return ref or None

  def GetActiveConfigHash(self) -> Optional[str]:
    """Computes the config hash of the active release, or None if absent."""
    if not self.has_active_release or not os.path.exists(
        self.active_flags_path
    ):
      return None
    try:
      with open(self.active_flags_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    except (OSError, yaml.YAMLError):
      return None
    if not isinstance(data, dict):
      return None
    flags = [str(x) for x in (data.get("flags") or [])]
    return _HashConfigInputs(self.active_config_path, flags)

  def DoesActiveMatchConfig(self, source_dir: Optional[str] = None) -> bool:
    """Returns True if core/active has the same config hash as source_dir."""
    active_hash = self.GetActiveConfigHash()
    if active_hash is None:
      return False
    try:
      desired_hash = self.ComputeConfigHash(source_dir)
    except (OSError, yaml.YAMLError):
      return False
    return active_hash == desired_hash

  def GetActiveRevision(self) -> dict[str, str]:
    """Reads core/active/revision.json, returning {} if absent or unreadable."""
    if not self.has_active_release or not os.path.exists(
        self.active_revision_path
    ):
      return {}
    try:
      with open(self.active_revision_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    except (OSError, ValueError):
      return {}
    if not isinstance(data, dict):
      return {}
    return {str(k): str(v) for k, v in data.items() if v}

  def WriteActiveRevisionFromConfig(
      self, image_ref: str, source_dir: Optional[str] = None
  ) -> None:
    """Refreshes core/active/revision.json when an upgrade is a config no-op."""
    if not self.has_active_release:
      return
    active_dir = self._active_release_dir
    if not active_dir or not os.path.isdir(active_dir):
      return
    src_dir = os.path.abspath(source_dir) if source_dir else self._config_dir
    revision = _BuildRevisionDict(image_ref, src_dir)
    _WriteJsonWithMode(
        os.path.join(active_dir, _REVISION_FILENAME),
        revision,
        node_permissions.BASE_FILE_MODE,
    )

  def StageRelease(
      self,
      image_ref: str,
      source_dir: Optional[str] = None,
  ) -> str:
    """Stages a release in releases/<image_ref>-<hash>/ from source_dir.

    Args:
      image_ref: Complete immutable image reference as returned by
        DockerImageExecutor.PullAndResolveImageRef. Persisted verbatim under the
        `image_ref` key of pinned_mtt_flags.yaml, so it must be directly usable
        as `mtt --image_name`.
      source_dir: Directory holding the unpinned config, defaults to config_dir.

    The release directory is named from both the sanitized image reference and a
    deterministic hash of the staged lab_config.yaml and flags list, so a
    config-only change stages into a distinct directory without overwriting the
    active release needed for rollback.

    Returns:
      Absolute path of the staged release directory.

    Raises:
      ValueError: If image_ref sanitizes to an empty directory name.
      FileNotFoundError: If the source mtt_flags.yaml is missing.
    """
    sanitized_ref = _SanitizeImageRef(image_ref)
    if not sanitized_ref:
      raise ValueError(f"Invalid image reference: {image_ref!r}")

    src_dir = os.path.abspath(source_dir) if source_dir else self._config_dir
    src_lab_config = os.path.join(src_dir, _LAB_CONFIG_FILENAME)
    src_flags_config = os.path.join(src_dir, _UNPINNED_FLAGS_FILENAME)

    if not os.path.exists(src_flags_config):
      raise FileNotFoundError(
          f"Source mtt_flags.yaml not found at: {src_flags_config}"
      )

    with open(src_flags_config, "r", encoding="utf-8") as f:
      src_flags_data = yaml.safe_load(f) or {}
    flags_list = (
        [str(x) for x in (src_flags_data.get("flags") or [])]
        if isinstance(src_flags_data, dict)
        else []
    )

    config_hash = _HashConfigInputs(src_lab_config, flags_list)
    release_name = f"{sanitized_ref}-{config_hash}"

    release_dir = os.path.join(self._releases_dir, release_name)
    os.makedirs(release_dir, exist_ok=True)

    dst_lab_config = os.path.join(release_dir, _LAB_CONFIG_FILENAME)
    if os.path.exists(src_lab_config):
      node_permissions.CopyFileWithMode(
          src_lab_config, dst_lab_config, node_permissions.BASE_FILE_MODE
      )
    elif os.path.exists(dst_lab_config):
      os.remove(dst_lab_config)

    dst_flags = os.path.join(release_dir, _PINNED_FLAGS_FILENAME)

    # image_name and tag are deliberately dropped here: image_ref already
    # identifies the exact image, and re-emitting the mutable tag would invite
    # callers to reconstruct a reference instead of using the pinned one.
    flags_data = {
        "image_ref": image_ref,
        "flags": flags_list,
    }
    with open(dst_flags, "w", encoding="utf-8") as f:
      yaml.dump(flags_data, f, default_flow_style=False, sort_keys=False)
    os.chmod(dst_flags, node_permissions.BASE_FILE_MODE)

    revision = _BuildRevisionDict(image_ref, src_dir)
    _WriteJsonWithMode(
        os.path.join(release_dir, _REVISION_FILENAME),
        revision,
        node_permissions.BASE_FILE_MODE,
    )

    self._AtomicSymlink(target=release_dir, link_path=self._staging_symlink)
    logger.info("Staged release for %s at %s", image_ref, release_dir)
    return release_dir

  def PromoteStagingToActive(self) -> None:
    """Atomically promotes staging -> active, removes staging, and prunes."""
    if not self.has_staging_release:
      raise ValueError("No staging release available to promote.")

    staging_target = self._staging_release_dir
    if not staging_target or not os.path.exists(staging_target):
      raise FileNotFoundError(
          f"Staging target {staging_target} does not exist on disk."
      )

    self._AtomicSymlink(target=staging_target, link_path=self._active_symlink)

    try:
      os.unlink(self._staging_symlink)
    except OSError:
      pass

    self._PruneReleases()
    logger.info("Promoted staging release to active: %s", staging_target)

  def DiscardStaging(self) -> None:
    """Removes staging symlink and deletes the unverified candidate directory."""
    if not self.has_staging_release:
      return

    staging_target = self._staging_release_dir
    try:
      os.unlink(self._staging_symlink)
    except OSError:
      pass

    active_target = self._active_release_dir
    if staging_target and staging_target != active_target:
      if (
          os.path.commonpath([self._releases_dir, staging_target])
          == self._releases_dir
      ):
        shutil.rmtree(staging_target, ignore_errors=True)
        logger.info(
            "Discarded and removed staging release directory: %s",
            staging_target,
        )

  def _PruneReleases(self) -> list[str]:
    """Removes release directories not referenced by active or staging."""
    active_target = self._active_release_dir
    staging_target = self._staging_release_dir

    pruned: list[str] = []

    if not os.path.exists(self._releases_dir):
      return pruned

    for entry in os.listdir(self._releases_dir):
      entry_path = os.path.join(self._releases_dir, entry)
      if not os.path.isdir(entry_path):
        continue

      real_path = os.path.realpath(entry_path)
      if real_path == active_target or real_path == staging_target:
        continue

      shutil.rmtree(entry_path, ignore_errors=True)
      pruned.append(entry)
      logger.info("Pruned unreferenced release directory: %s", entry_path)

    return pruned
