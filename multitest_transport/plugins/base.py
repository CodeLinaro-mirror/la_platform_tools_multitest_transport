# Copyright 2019 Google LLC
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

"""Base classes and utility methods for ATS plugins."""
import collections
import dataclasses
import datetime
import enum
import inspect
import logging
import re
from typing import Dict, Generic, List, Optional, Tuple, Type, TypeVar

from google.auth import credentials as ga_credentials
from tradefed_cluster import api_messages as tfc_messages


from multitest_transport.models import ndb_models
from multitest_transport.plugins.registry import PluginRegistry
from multitest_transport.util import oauth2_util

_PRIVATE_OPTION_PREFIX = '_'

BUILD_PROVIDER_REGISTRY = PluginRegistry()
TEST_RUN_HOOK_REGISTRY = PluginRegistry()

# Re-export commonly used values for convenience.
AuthorizationMethod = ndb_models.AuthorizationMethod
BuildItemPathType = ndb_models.BuildItemPathType

# Supported option value types.
OptionValue = TypeVar('OptionValue', str, int)


@dataclasses.dataclass(frozen=True)
class OptionDef(Generic[OptionValue]):
  """Option definition."""
  name: str
  value_type: Type[OptionValue]
  choices: Optional[List[OptionValue]] = None
  default: Optional[OptionValue] = None


@dataclasses.dataclass(frozen=True)
class BuildItem:
  """File returned by a build provider."""
  name: str
  path: str
  is_file: bool = False
  size: Optional[int] = None
  timestamp: Optional[datetime.datetime] = None
  description: Optional[str] = None


@dataclasses.dataclass(frozen=True)
class UrlPattern:
  """URL pattern that can be handled by a build provider."""
  url: str
  path: str


class BuildItemType(enum.Enum):
  """Build item types."""
  FILE = 1
  DIRECTORY = 2


class BuildProviderOptions:
  """A class to store parsed build provider options."""

  def __init__(self, option_def_map: Dict[str, OptionDef]):
    self._option_def_map = option_def_map
    # Fill default values
    for name, option_def in self._option_def_map.items():
      self.__dict__[name] = option_def.value_type(option_def.default)

  def Update(self, **kwargs):
    """Updates options values.

    Args:
      **kwargs: option name/value pairs to update.

    Raises:
      ValueError: if an option is not defined.
    """
    for name, value in kwargs.items():
      option_def = self._option_def_map.get(name)
      if not option_def:
        logging.warning('Unsupported option name %s; ignoring', name)
        continue
      self.__dict__[name] = option_def.value_type(value)


class BuildProvider(metaclass=BUILD_PROVIDER_REGISTRY.GetMetaclass()):  # pyrefly: ignore[invalid-inheritance]
  """A base class for a build provider."""
  name: str
  auth_methods: List[AuthorizationMethod] = []
  oauth2_config: Optional[oauth2_util.OAuth2Config] = None
  url_patterns: List[UrlPattern] = []
  build_item_path_type: BuildItemPathType

  def __init__(self):
    super().__init__()
    self._option_def_map = collections.OrderedDict()
    self._options = None
    self._credentials = None

  def AddOptionDef(self,
                   name: str,
                   value_type: Type[OptionValue] = str,
                   choices: Optional[List[OptionValue]] = None,
                   default: Optional[OptionValue] = None):
    """Adds a new option definition.

    Option definitions are used to validate user-provided options and render UI.

    Args:
      name: a name.
      value_type: a value type.
      choices: a list of possible values (optional).
      default: a default value (optional).

    Raises:
      ValueError: if an option is already defined.
    """
    if name in self._option_def_map:
      raise ValueError('option %s is already defined' % name)
    self._option_def_map[name] = OptionDef(name, value_type, choices, default)

  def GetOptionDefs(self):
    return self._option_def_map.values()

  def GetOptions(self) -> BuildProviderOptions:
    if not self._options:
      self._options = BuildProviderOptions(self._option_def_map)
    return self._options

  def UpdateOptions(self, **kwargs):
    """Update build provider options.

    Args:
      **kwargs: name value pairs to be updated.
    """
    options = self.GetOptions()
    options.Update(**kwargs)

  def GetCredentials(self) -> Optional[ga_credentials.Credentials]:
    """Returns stored credentials.

    Returns:
      a google.auth.credentials.Credentials object.
    """
    return self._credentials

  def UpdateCredentials(self, credentials: ga_credentials.Credentials):
    """Updates stored credentials for a provider.

    Args:
      credentials: a google.auth.credentials.Credentials object.
    """
    self._credentials = credentials

  def GetOAuth2Config(self) -> Optional[oauth2_util.OAuth2Config]:
    """Returns OAuth2Config object.

    This must be implemented by a child build provider. If it returns None,
    MTT will assume a provider doesn't need OAuth2.

    Returns:
      a OAuth2Config object or None if a provider doesn't need OAuth2.
    """
    return None

  def ListBuildItems(
      self,
      path: Optional[str] = None,
      page_token: Optional[str] = None,
      item_type: Optional[BuildItemType] = None
  ) -> Tuple[List[BuildItem], Optional[str]]:
    """List build items under a given path.

    Args:
      path: a path within a build channel.
      page_token: an optional page token.
      item_type: a type of build items to list. Returns all types if None.

    Returns:
      (a list of BuildItem object, a next page token)
    """
    raise NotImplementedError('ListBuildItems() is not implemented.')

  def GetBuildItem(self, path: str) -> Optional[BuildItem]:
    """Get a build item.

    Args:
      path: a build item path.

    Returns:
      a BuildItem object. None if the build item does not exist.
    """
    raise NotImplementedError('GetBuildItem() is not implemented.')

  def DeleteBuildItem(self, path: str):
    """Delete a build item.

    Args:
      path: a build item path.
    """
    raise NotImplementedError('DeleteBuildItem() is not implemented.')

  def DownloadFile(self, path: str, offset: int = 0):
    """Download a build file.

    Args:
      path: a build file path
      offset: byte offset to read from

    Yields:
      content: chunk of data read
      offset: current position in file
      total_size: total number of bytes in file
    """
    raise NotImplementedError('DownloadFile() is not implemented.')

  def FindBuildItemPath(self, url: str) -> Optional[str]:
    """Find a build item by a URL.

    If a URL matches any known URL patterns, it will return a corresponding
    build item path. If there is no match, it will return None.

    Args:
      url: a URL.

    Returns:
      a build item path if a URL belongs to this build channel. None otherwise.
    """
    for url_pattern in self.url_patterns:
      m = re.match(url_pattern.url, url)
      if not m:
        continue
      return url_pattern.path.format(**m.groupdict())
    return None


def GetBuildProviderClass(name: str) -> Optional[Type[BuildProvider]]:
  """Retrieves a registered build provider class by its name."""
  return BUILD_PROVIDER_REGISTRY.GetPluginClass(name)


def ListBuildProviderNames() -> List[str]:
  """Lists all registered build provider names."""
  return BUILD_PROVIDER_REGISTRY.ListPluginNames()


@dataclasses.dataclass(frozen=True)
class TestRunHookContext:
  """Test run hook execution context.

  Attributes:
    test_run: test run being executed
    phase: current execution phase
    latest_attempt: optional latest finished attempt
    next_task: optional next task to be executed
  """
  test_run: ndb_models.TestRun
  phase: ndb_models.TestRunPhase
  latest_attempt: Optional[tfc_messages.CommandAttemptMessage] = None
  next_task: Optional['TestRunTask'] = None


@dataclasses.dataclass()
class TestRunTask:
  """Mutable test run attempt not yet sent to the runner.

  Attributes:
    task_id: task ID
    command_line: command line to execute
    extra_options: dict of extra options to pass to runner
  """
  task_id: str
  command_line: str
  extra_options: Dict[str, List[str]]


class TestRunHook(metaclass=TEST_RUN_HOOK_REGISTRY.GetMetaclass()):  # pyrefly: ignore[invalid-inheritance]
  """Base class for all test run hooks."""
  name: str
  oauth2_config: Optional[oauth2_util.OAuth2Config]

  def __init__(self, **_):
    super().__init__()

  def Execute(self, context: TestRunHookContext):
    """Execute the hook.

    Args:
      context: test run hook execution context.
    """
    raise NotImplementedError()

  @classmethod
  def GetPublicOptionDefs(cls):
    """Retrieves a list of public option definitions."""
    option_def_map = collections.OrderedDict()
    signature = inspect.signature(cls)
    for (name, param) in signature.parameters.items():
      if name.startswith(_PRIVATE_OPTION_PREFIX):
        continue
      # Param type is always str. Convert the default value to str
      if param.default == inspect.Parameter.empty or param.default is None:
        default = ''
      else:
        default = str(param.default)
      option_def_map[name] = OptionDef(name, str, [], default)
    return option_def_map.values()


def GetTestRunHookClass(name: str) -> Optional[Type[TestRunHook]]:
  """Retrieves a run hook class by its name."""
  return TEST_RUN_HOOK_REGISTRY.GetPluginClass(name)


def ListTestRunHookNames() -> List[str]:
  """Lists all registered test run hook names."""
  return TEST_RUN_HOOK_REGISTRY.ListPluginNames()
