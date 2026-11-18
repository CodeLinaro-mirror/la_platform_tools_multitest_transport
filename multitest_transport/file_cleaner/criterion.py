# Copyright 2021 Google LLC
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
# limitations under the License
"""Cleanup criteria.

YAML config example:

  criteria:
  - type: LAST_MODIFIED_TIME  # required
    params:  # optional
    - name: ttl
      value: '7 days'
  - type: NAME_MATCH
    params:
    - name: pattern
      value: 'zip'
"""
import os
import re
import shutil
import time

from pytimeparse import timeparse


from multitest_transport.models import messages
from multitest_transport.models import ndb_models

DISK_SPACE_PATTERN = r'(?i)^(?P<number>\d+)\s*(?P<unit>[KMGT]?B)?$'
DISK_SPACE_UNIT_SHIFTS = {'B': 0, 'KB': 10, 'MB': 20, 'GB': 30, 'TB': 40}

DEFAULT_TTL = '7 days'
DEFAULT_NAME_PATTERN = '.^'  # does not match anything
DEFAULT_SPACE_THRESHOLD = '20GB'


def _DiskSpaceToBytes(space: str) -> int:
  """Convert disk space string to bytes.

  Args:
    space: string. Disk space, eg. 20(B), 20GB, 20 GB

  Returns:
    Integer, bytes.
  """
  match = re.match(DISK_SPACE_PATTERN, space.strip())
  if match is None:
    raise ValueError('Invalid disk space string "%s".' % space)
  number, unit = match.group('number', 'unit')
  shift = 0
  if unit is not None:
    shift = DISK_SPACE_UNIT_SHIFTS[unit.upper()]
  return int(number) << shift


class Criterion(object):
  """Interface for cleanup criteria."""

  def Apply(self, path: str) -> bool:
    """Applies the criterion.

    Args:
      path: file path

    Returns:
      Bool, whether the file meets the criterion.
    """
    raise NotImplementedError


class LastAccessTime(Criterion):
  """Whether the file is expired according to last access time."""

  def __init__(self, ttl: str = DEFAULT_TTL):
    super().__init__()
    self.ttl_seconds = timeparse.timeparse(ttl) or 0

  def Apply(self, path: str) -> bool:
    return time.time() - os.path.getatime(path) > self.ttl_seconds


class LastModifiedTime(Criterion):
  """Whether the file is expired according to last modified time."""

  def __init__(self, ttl: str = DEFAULT_TTL):
    super().__init__()
    self.ttl_seconds = timeparse.timeparse(ttl) or 0

  def Apply(self, path: str) -> bool:
    return time.time() - os.path.getmtime(path) > self.ttl_seconds


class NameMatch(Criterion):
  """Whether the file name matches the given regex pattern."""

  def __init__(self, pattern: str = DEFAULT_NAME_PATTERN):
    super().__init__()
    self.pattern = re.compile(pattern)

  def Apply(self, path: str) -> bool:
    return bool(self.pattern.search(path))


class SystemAvailableSpace(Criterion):
  """Whether the system available space is less than given threshold."""

  def __init__(self, threshold: str = DEFAULT_SPACE_THRESHOLD):
    super().__init__()
    self.threshold_bytes = _DiskSpaceToBytes(threshold)

  def Apply(self, path: str) -> bool:
    return shutil.disk_usage(path).free < self.threshold_bytes


Criteria = {
    ndb_models.FileCleanerCriterionType.LAST_ACCESS_TIME:
        LastAccessTime,
    ndb_models.FileCleanerCriterionType.LAST_MODIFIED_TIME:
        LastModifiedTime,
    ndb_models.FileCleanerCriterionType.NAME_MATCH:
        NameMatch,
    ndb_models.FileCleanerCriterionType.SYSTEM_AVAILABLE_SPACE:
        SystemAvailableSpace
}


def BuildCriterion(config: messages.FileCleanerCriterion) -> 'Criterion':
  """Factory function to build the Criterion according to the config.

  Args:
    config: criterion config.

  Returns:
    Criterion
  """
  return Criteria[config.type](
      **messages.ConvertNameValuePairsToDict(config.params))
