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

"""Compose directory management data plane for MTT Node.

Manages the extraction of bundled Docker Compose specifications from package
resources to <baseDir>/compose/ and exposes paths to compose files.
"""

import importlib.resources
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

_COMPOSE_RESOURCE_PACKAGE = "multitest_transport.cli"
_COMPOSE_RESOURCE_DIR = "compose"


class ComposeDirectoryManager:
  """Manages Docker Compose specification files extracted from package data."""

  def __init__(self, base_dir: str = "."):
    self._base_dir = os.path.abspath(base_dir)
    self._compose_dir = os.path.join(self._base_dir, "compose")

  @property
  def base_dir(self) -> str:
    """Returns the base station directory."""
    return self._base_dir

  @property
  def compose_dir(self) -> str:
    """Returns the absolute path to <baseDir>/compose/."""
    return self._compose_dir

  @property
  def has_compose_files(self) -> bool:
    """Returns True if the compose directory exists and contains files."""
    return os.path.isdir(self._compose_dir) and bool(
        os.listdir(self._compose_dir)
    )

  def GetComposeFilePath(self, relative_path: str) -> str:
    """Returns the absolute path for a compose file relative to compose_dir."""
    return os.path.join(self._compose_dir, relative_path)

  def ExtractComposeFiles(self) -> None:
    """Recursively extracts bundled compose definitions into <baseDir>/compose/."""
    os.makedirs(self._compose_dir, exist_ok=True)
    try:
      resource_traversable = importlib.resources.files(
          _COMPOSE_RESOURCE_PACKAGE
      ).joinpath(_COMPOSE_RESOURCE_DIR)
    except (
        TypeError,
        FileNotFoundError,
        ModuleNotFoundError,
        AttributeError,
    ) as e:
      logger.warning("Could not locate bundled compose resources: %s", e)
      return

    self._ExtractRecursive(resource_traversable, self._compose_dir)

  def _ExtractRecursive(self, traversable: Any, target_dir: str) -> None:
    """Recursively traverses a resource Traversable and writes files to target_dir."""
    os.makedirs(target_dir, exist_ok=True)
    if not hasattr(traversable, "iterdir"):
      return

    for item in traversable.iterdir():
      # Defensive only: traversal is rooted at compose/, which holds YAML and
      # nothing else, so this never matches today. Guards against a stray
      # __init__.py or helper script later being copied onto a user's machine.
      if item.name == "__pycache__" or item.name.endswith((".py", ".pyc")):
        continue
      target_path = os.path.join(target_dir, item.name)
      if item.is_dir():
        self._ExtractRecursive(item, target_path)
      elif item.is_file():
        try:
          content = item.read_bytes()
          with open(target_path, "wb") as f:
            f.write(content)
        except (OSError, IOError) as e:
          logger.warning(
              "Failed to extract compose file %s: %s", target_path, e
          )
