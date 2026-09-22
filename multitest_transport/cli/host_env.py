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

"""Host environment classification for MTT Node.

The environment a node runs in decides which Docker Compose overlay applies and
whether GCP-only sidecars are available. Detection is a local probe with no
dependencies, so every caller that needs the environment resolves it here
rather than reimplementing the test.
"""

import enum

_DMI_PRODUCT_NAME_PATH = "/sys/class/dmi/id/product_name"
_GCE_PRODUCT_NAME = "Google Compute Engine"


class HostEnvironment(enum.Enum):
  """Host environment types for Docker Compose overlays."""

  DEFAULT = "default"
  GCE = "gce"
  LAB = "lab"

  def IsGcp(self) -> bool:
    """Returns whether the environment can reach GCP-hosted infrastructure.

    Distinct from the specific environment, which selects a compose overlay.
    Callers gating a GCP-only service (such as the Cloud Endpoints proxy)
    should ask this rather than comparing against a single member, so that
    additional GCP environments stay a one-line change here.
    """
    return self in _GCP_ENVIRONMENTS


_GCP_ENVIRONMENTS = frozenset({HostEnvironment.GCE})


def IsGceInstance(product_name_path: str = _DMI_PRODUCT_NAME_PATH) -> bool:
  """Checks whether the current host is a Google Compute Engine (GCE) instance.

  Args:
    product_name_path: Path to the DMI product_name sysfs file.

  Returns:
    True if running on a GCE instance, False otherwise.
  """
  try:
    with open(product_name_path, "r", encoding="utf-8") as f:
      return _GCE_PRODUCT_NAME in f.read()
  except OSError:
    return False


def Detect() -> HostEnvironment:
  """Resolves the environment of the host this process is running on.

  Returns:
    The detected HostEnvironment, or HostEnvironment.DEFAULT when the host
    matches no known environment.
  """
  if IsGceInstance():
    return HostEnvironment.GCE
  return HostEnvironment.DEFAULT
