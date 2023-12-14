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

"""API messages."""

import collections
import logging

from protorpc import message_types
from protorpc import messages
import pytz
from tradefed_cluster import api_messages
from tradefed_cluster.util import ndb_shim as ndb


from google.oauth2 import credentials
from google.oauth2 import service_account

from multitest_transport.plugins import base as plugins
from multitest_transport.models import build
from multitest_transport.models import event_log
from multitest_transport.models import ndb_models
from multitest_transport.models import sql_models
from multitest_transport.util import env
from multitest_transport.util import file_util
from multitest_transport.util import xts_result

_DEFAULT_CLUSTER = 'default'
_OAUTH2_CREDENTIALS_USERNAME = 'User Account'

_convert_func_map = {}


def Converter(from_cls, to_cls):
  """A decorator to register a message converter.

  Args:
    from_cls: a class to convert from.
    to_cls: a class to convert to.
  Returns:
    a decorator function.
  """
  def Decorator(func):
    _convert_func_map[(from_cls, to_cls)] = func
    return func
  return Decorator


def Convert(obj, to_cls, from_cls=None):
  """Converts an object to a given class.

  Args:
    obj: an object.
    to_cls: a class to convert to.
    from_cls: a class to convert from (optional).
  Returns:
    a converted object.
  Raises:
    ValueError: if there's no registered converter function.
  """
  if obj is None:
    return None
  from_cls = from_cls or type(obj)
  func = _convert_func_map.get((from_cls, to_cls))
  if not func:
    raise ValueError('no convert function for %s -> %s' % (from_cls, to_cls))
  return func(obj)


def ConvertList(lst, to_cls, from_cls=None):
  """Converts an object or a list objects to a given class.

  Args:
    lst: a list of objects.
    to_cls: a class to convert to.
    from_cls: a class to convert from (optional).
  Returns:
    a a list of conveted objects.
  """
  if lst is None:
    return None
  return [Convert(obj, to_cls, from_cls) for obj in lst]


def ConvertToKey(model_cls, id_):
  """Convert to a ndb.Key object.

  Args:
    model_cls: a model class.
    id_: an object ID.
  Returns:
    a ndb.Key object.
  """
  try:
    id_ = int(id_)
  except ValueError:
    pass
  return ndb.Key(model_cls, id_)


def ConvertToKeyOrNone(model_cls, id_):
  """Convert to a ndb.Key object or None.

  This returns None if id_ is None.

  Args:
    model_cls: a model class.
    id_: an object ID.
  Returns:
    a ndb.Key object.
  """
  if id_ is None:
    return None
  return ConvertToKey(model_cls, id_)


def ConvertToDeviceSpecs(run_target):
  """Convert a run target to device specs.

  Args:
    run_target: a run target.
  Returns:
    a list of device specs.
  """
  if not run_target:
    return []
  return ['device_serial:%s' % s for s in run_target.split(';')]


def _AddTimezone(datetime, timezone=pytz.UTC):
  """Adds timezone to an NDB datetime (which doesn't store timezone)."""
  if datetime:
    return datetime.replace(tzinfo=timezone)  


class AuthorizationInfo(messages.Message):
  """OAuth2 authorization information.

  Attributes:
    url: an authorization url.
    is_manual: a boolean value which tell us to start automatic or manual
      copy/paste flow
  """
  url = messages.StringField(1, required=True)
  is_manual = messages.BooleanField(2, required=True)


class SimpleMessage(messages.Message):
  """Simple string message."""
  value = messages.StringField(1, required=True)


class NameValuePair(messages.Message):
  """A generic name-value pair to store an option.

  Attributes:
    name: a name.
    value: a value.
  """
  name = messages.StringField(1, required=True)
  value = messages.StringField(2)


class NameMultiValuePair(messages.Message):
  """A generic name-multi value pair to store an option.

  Attributes:
    name: a name.
    values: a value.
  """
  name = messages.StringField(1, required=True)
  values = messages.StringField(2, repeated=True)


def ConvertNameValuePairs(pairs, to_cls):
  """Convert message and NDB model name-value(s) pairs."""
  is_multi = to_cls in (NameMultiValuePair, ndb_models.NameMultiValuePair)
  d = collections.OrderedDict()
  for pair in pairs:
    if pair.name in d:
      logging.warning('Duplicate key %s in %s', pair.name, pairs)
    if is_multi:
      d[pair.name] = to_cls(name=pair.name, values=pair.values)
    else:
      d[pair.name] = to_cls(name=pair.name, value=pair.value)
  return list(d.values())


def ConvertNameValuePairsToDict(pairs):
  """Convert message or NDB model name-value(s) pairs to dict."""
  d = collections.OrderedDict()
  for pair in pairs:
    d[pair.name] = pair.value
  return d


class FileSegment(messages.Message):
  """Partial file content."""
  offset = messages.IntegerField(1)
  length = messages.IntegerField(2)
  lines = messages.StringField(3, repeated=True)


@Converter(file_util.FileSegment, FileSegment)
def _FileSegmentConverter(obj):
  lines = [line.decode() for line in obj.lines]
  return FileSegment(offset=obj.offset, length=obj.length, lines=lines)


class EventLogEntry(messages.Message):
  """An event log entry."""
  create_time = message_types.DateTimeField(1, required=True)
  level = messages.EnumField(ndb_models.EventLogLevel, 2, required=True)
  message = messages.StringField(3, required=True)


@Converter(ndb_models.EventLogEntry, EventLogEntry)
def _EventLogEntryConverter(obj):
  return EventLogEntry(
      create_time=_AddTimezone(obj.create_time),
      level=obj.level,
      message=obj.message)


class TestResourceParameters(messages.Message):
  """Repeated properties of TestResourceObj and TestResourceDef."""
  decompress_files = messages.StringField(1, repeated=True)


@Converter(ndb_models.TestResourceParameters, TestResourceParameters)
def _TestResourceParametersConverter(obj):
  return TestResourceParameters(decompress_files=obj.decompress_files)


@Converter(TestResourceParameters, ndb_models.TestResourceParameters)
def _TestResourceParametersMessageConverter(msg):
  return ndb_models.TestResourceParameters(
      decompress_files=msg.decompress_files)


class TestResourceDef(messages.Message):
  """A test resource definition for a test."""
  name = messages.StringField(1, required=True)
  default_download_url = messages.StringField(2)
  test_resource_type = messages.EnumField(ndb_models.TestResourceType, 3)
  decompress = messages.BooleanField(4)
  decompress_dir = messages.StringField(5)
  mount_zip = messages.BooleanField(6)
  params = messages.MessageField(TestResourceParameters, 7)


@Converter(ndb_models.TestResourceDef, TestResourceDef)
def _TestResourceDefConverter(obj):
  return TestResourceDef(
      name=obj.name,
      default_download_url=obj.default_download_url,
      test_resource_type=obj.test_resource_type,
      decompress=obj.decompress,
      decompress_dir=obj.decompress_dir,
      mount_zip=obj.mount_zip,
      params=Convert(obj.params, TestResourceParameters))


@Converter(TestResourceDef, ndb_models.TestResourceDef)
def _TestResourceDefMessageConverter(msg):
  return ndb_models.TestResourceDef(
      name=msg.name,
      default_download_url=msg.default_download_url,
      test_resource_type=msg.test_resource_type,
      decompress=msg.decompress,
      decompress_dir=msg.decompress_dir,
      mount_zip=msg.mount_zip,
      params=Convert(msg.params, ndb_models.TestResourceParameters))


class TestRunParameter(messages.Message):
  """Test run paramerer."""
  max_retry_on_test_failures = messages.IntegerField(1)
  invocation_timeout_seconds = messages.IntegerField(2)
  output_idle_timeout_seconds = messages.IntegerField(3)


@Converter(ndb_models.TestRunParameter, TestRunParameter)
def _TestRunParameterConverter(obj):
  return TestRunParameter(
      max_retry_on_test_failures=obj.max_retry_on_test_failures,
      output_idle_timeout_seconds=obj.output_idle_timeout_seconds)


@Converter(TestRunParameter, ndb_models.TestRunParameter)
def _TestRunParameterMessageConverter(msg):
  return ndb_models.TestRunParameter(
      max_retry_on_test_failures=msg.max_retry_on_test_failures,
      output_idle_timeout_seconds=msg.output_idle_timeout_seconds)


class Test(messages.Message):
  """A test."""
  id = messages.StringField(1)
  name = messages.StringField(2, required=True)
  description = messages.StringField(3)
  test_resource_defs = messages.MessageField(TestResourceDef, 4, repeated=True)
  command = messages.StringField(5)
  env_vars = messages.MessageField(NameValuePair, 6, repeated=True)
  output_file_patterns = messages.StringField(7, repeated=True)
  result_file = messages.StringField(8)
  setup_scripts = messages.StringField(9, repeated=True)
  jvm_options = messages.StringField(10, repeated=True)
  java_properties = messages.MessageField(NameValuePair, 11, repeated=True)
  context_file_dir = messages.StringField(12)
  context_file_pattern = messages.StringField(13)
  retry_command_line = messages.StringField(14)
  runner_sharding_args = messages.StringField(15)
  default_test_run_parameters = messages.MessageField(TestRunParameter, 16)
  module_config_pattern = messages.StringField(17)
  module_execution_args = messages.StringField(18)


@Converter(ndb_models.Test, Test)
def _TestConverter(obj):
  return Test(
      id=str(obj.key.id()) if obj.key else None,
      name=obj.name,
      description=obj.description,
      test_resource_defs=ConvertList(obj.test_resource_defs, TestResourceDef),
      command=obj.command,
      env_vars=ConvertNameValuePairs(obj.env_vars, NameValuePair),
      output_file_patterns=obj.output_file_patterns,
      result_file=obj.result_file,
      setup_scripts=obj.setup_scripts,
      jvm_options=obj.jvm_options,
      java_properties=ConvertNameValuePairs(obj.java_properties, NameValuePair),
      context_file_dir=obj.context_file_dir,
      context_file_pattern=obj.context_file_pattern,
      retry_command_line=obj.retry_command_line,
      runner_sharding_args=obj.runner_sharding_args,
      default_test_run_parameters=Convert(
          obj.default_test_run_parameters, TestRunParameter),
      module_config_pattern=obj.module_config_pattern,
      module_execution_args=obj.module_execution_args)


@Converter(Test, ndb_models.Test)
def _TestMessageConverter(msg):
  return ndb_models.Test(
      key=ConvertToKeyOrNone(ndb_models.Test, msg.id),
      name=msg.name,
      description=msg.description,
      test_resource_defs=ConvertList(
          msg.test_resource_defs, ndb_models.TestResourceDef),
      command=msg.command,
      env_vars=ConvertNameValuePairs(msg.env_vars, ndb_models.NameValuePair),
      setup_scripts=msg.setup_scripts,
      output_file_patterns=msg.output_file_patterns,
      result_file=msg.result_file,
      jvm_options=msg.jvm_options,
      java_properties=ConvertNameValuePairs(
          msg.java_properties, ndb_models.NameValuePair),
      context_file_dir=msg.context_file_dir,
      context_file_pattern=msg.context_file_pattern,
      retry_command_line=msg.retry_command_line,
      runner_sharding_args=msg.runner_sharding_args,
      default_test_run_parameters=Convert(
          msg.default_test_run_parameters, ndb_models.TestRunParameter),
      module_config_pattern=msg.module_config_pattern,
      module_execution_args=msg.module_execution_args)


class TestList(messages.Message):
  """A list of tests."""
  tests = messages.MessageField(Test, 1, repeated=True)


class CredentialsInfo(messages.Message):
  """Credentials info object."""
  email = messages.StringField(1)


@Converter(credentials.Credentials, CredentialsInfo)
def _OauthCredentialsConverter(_):
  # TODO: Get email from userinfo endpoint
  return CredentialsInfo(
      email=_OAUTH2_CREDENTIALS_USERNAME)


@Converter(service_account.Credentials, CredentialsInfo)
def _ServiceAccountCredentialsConverter(obj):
  return CredentialsInfo(
      email=obj.service_account_email)


class BuildChannelConfig(messages.Message):
  """A build channel configuration."""
  id = messages.StringField(1, required=True)
  name = messages.StringField(2, required=True)
  provider_name = messages.StringField(3, required=True)
  options = messages.MessageField(NameValuePair, 4, repeated=True)


@Converter(ndb_models.BuildChannelConfig, BuildChannelConfig)
def _BuildChannelConfigConverter(obj):
  return BuildChannelConfig(
      id=str(obj.key.id()) if obj.key else None,
      name=obj.name,
      provider_name=obj.provider_name,
      options=ConvertNameValuePairs(obj.options, NameValuePair))


@Converter(BuildChannelConfig, ndb_models.BuildChannelConfig)
def _BuildChannelConfigMessageConverter(msg):
  return ndb_models.BuildChannelConfig(
      key=ConvertToKeyOrNone(ndb_models.BuildChannelConfig, msg.id),
      name=msg.name,
      provider_name=msg.provider_name,
      options=ConvertNameValuePairs(msg.options, ndb_models.NameValuePair))


class BuildChannel(messages.Message):
  """A build channel, which combines channel config and provider properties."""
  id = messages.StringField(1, required=True)
  name = messages.StringField(2, required=True)
  provider_name = messages.StringField(3, required=True)
  auth_state = messages.EnumField(
      ndb_models.AuthorizationState, 4, required=True)
  auth_methods = messages.EnumField(
      ndb_models.AuthorizationMethod, 5, repeated=True)
  credentials = messages.MessageField(CredentialsInfo, 6)
  build_item_path_type = messages.EnumField(
      ndb_models.BuildItemPathType, 7, required=True)


@Converter(build.BuildChannel, BuildChannel)
def _BuildChannelConverter(obj):
  return BuildChannel(
      id=str(obj.id),
      name=obj.name,
      provider_name=obj.provider_name,
      auth_state=obj.auth_state,
      auth_methods=obj.auth_methods,
      credentials=Convert(obj.credentials, CredentialsInfo),
      build_item_path_type=obj.build_item_path_type)


class BuildChannelList(messages.Message):
  """A list of build channels."""
  build_channels = messages.MessageField(BuildChannel, 1, repeated=True)


class OptionDef(messages.Message):
  """A plugin option definition."""
  name = messages.StringField(1, required=True)
  value_type = messages.StringField(2, required=True)
  choices = messages.StringField(3, repeated=True)
  default = messages.StringField(4)


@Converter(plugins.OptionDef, OptionDef)
def _OptionDefConverter(obj):
  return OptionDef(
      name=obj.name,
      value_type=obj.value_type.__name__,
      choices=obj.choices or [],
      default=obj.default)


class BuildChannelProvider(messages.Message):
  """Information about a build channel provider."""
  name = messages.StringField(1, required=True)
  option_defs = messages.MessageField(OptionDef, 2, repeated=True)


class BuildChannelProviderList(messages.Message):
  """A list of build channel providers."""
  build_channel_providers = messages.MessageField(
      BuildChannelProvider, 1, repeated=True)


class BuildItem(messages.Message):
  """A build item."""
  name = messages.StringField(1)
  path = messages.StringField(2)
  is_file = messages.BooleanField(3)
  size = messages.IntegerField(4)
  timestamp = message_types.DateTimeField(5)
  description = messages.StringField(6)


@Converter(plugins.BuildItem, BuildItem)
def _BuildItemConverter(obj):
  return BuildItem(
      name=obj.name,
      path=obj.path,
      is_file=obj.is_file,
      size=obj.size,
      timestamp=obj.timestamp,
      description=obj.description)


class BuildItemList(messages.Message):
  """A list of build items."""
  build_items = messages.MessageField(BuildItem, 1, repeated=True)
  next_page_token = messages.StringField(2)


class TradefedConfigObject(messages.Message):
  class_name = messages.StringField(1, required=True)
  option_values = messages.MessageField(NameMultiValuePair, 2, repeated=True)


@Converter(ndb_models.TradefedConfigObject, TradefedConfigObject)
def _TradefedConfigObjectConverter(obj):
  return TradefedConfigObject(
      class_name=obj.class_name,
      option_values=ConvertNameValuePairs(
          obj.option_values, NameMultiValuePair))


@Converter(TradefedConfigObject, ndb_models.TradefedConfigObject)
def _TradefedConfigObjectMessageConverter(msg):
  return ndb_models.TradefedConfigObject(
      class_name=msg.class_name,
      option_values=ConvertNameValuePairs(
          msg.option_values, ndb_models.NameMultiValuePair))


class ConfigSetInfo(messages.Message):
  """Metadata for a config set."""
  url = messages.StringField(1, required=True)
  hash = messages.StringField(2)
  name = messages.StringField(3, required=True)
  description = messages.StringField(4)
  last_update_time = messages.StringField(5)
  status = messages.EnumField(ndb_models.ConfigSetStatus, 6)


@Converter(ndb_models.ConfigSetInfo, ConfigSetInfo)
def _ConfigSetInfoConverter(obj):
  return ConfigSetInfo(
      url=obj.url,
      hash=obj.hash,
      name=obj.name,
      description=obj.description,
      last_update_time=obj.last_update_time,
  )


@Converter(ConfigSetInfo, ndb_models.ConfigSetInfo)
def _ConfigSetInfoMessageConverter(msg):
  return ndb_models.ConfigSetInfo(
      key=ConvertToKeyOrNone(ndb_models.ConfigSetInfo, msg.url),
      url=msg.url,
      hash=msg.hash,
      name=msg.name,
      description=msg.description,
      last_update_time=msg.last_update_time,
  )


class ConfigSetInfoList(messages.Message):
  config_set_infos = messages.MessageField(ConfigSetInfo, 1, repeated=True)


@Converter(ndb_models.ConfigSetInfoList, ConfigSetInfoList)
def _ConfigSetInfoListConverter(obj):
  return ConfigSetInfoList(
      config_set_infos=ConvertList(obj.config_set_infos, ConfigSetInfo))


@Converter(ConfigSetInfoList, ndb_models.ConfigSetInfoList)
def _ConfigSetInfoListMessageConverter(msg):
  return ndb_models.ConfigSetInfoList(
      config_set_infos=ConvertList(
          msg.config_set_infos, ndb_models.ConfigSetInfo))


class DeviceAction(messages.Message):
  """A device action."""
  id = messages.StringField(1)
  name = messages.StringField(2, required=True)
  description = messages.StringField(3)
  test_resource_defs = messages.MessageField(TestResourceDef, 4, repeated=True)
  tradefed_target_preparers = messages.MessageField(
      TradefedConfigObject, 5, repeated=True)
  device_type = messages.StringField(6)
  tradefed_options = messages.MessageField(NameMultiValuePair, 7, repeated=True)
  device_spec = messages.StringField(8)


@Converter(ndb_models.DeviceAction, DeviceAction)
def _DeviceActionConverter(obj):
  return DeviceAction(
      id=str(obj.key.id()) if obj.key else None,
      name=obj.name,
      description=obj.description,
      test_resource_defs=ConvertList(obj.test_resource_defs, TestResourceDef),
      tradefed_target_preparers=ConvertList(
          obj.tradefed_target_preparers, TradefedConfigObject),
      device_type=obj.device_type,
      tradefed_options=ConvertNameValuePairs(
          obj.tradefed_options, NameMultiValuePair),
      device_spec=obj.device_spec)


@Converter(DeviceAction, ndb_models.DeviceAction)
def _DeviceActionMessageConverter(msg):
  return ndb_models.DeviceAction(
      key=ConvertToKeyOrNone(ndb_models.DeviceAction, msg.id),
      name=msg.name,
      description=msg.description,
      test_resource_defs=ConvertList(
          msg.test_resource_defs, ndb_models.TestResourceDef),
      tradefed_target_preparers=ConvertList(
          msg.tradefed_target_preparers, ndb_models.TradefedConfigObject),
      device_type=msg.device_type,
      tradefed_options=ConvertNameValuePairs(
          msg.tradefed_options, ndb_models.NameMultiValuePair),
      device_spec=msg.device_spec)


class DeviceActionList(messages.Message):
  """A list of device actions."""
  device_actions = messages.MessageField(DeviceAction, 1, repeated=True)


class TestModuleResult(messages.Message):
  """Test module result."""
  id = messages.StringField(1)  # Legacy test results will not have an ID
  name = messages.StringField(2, required=True)
  complete = messages.BooleanField(3, required=True)
  duration_ms = messages.IntegerField(4, required=True)
  passed_tests = messages.IntegerField(5, required=True)
  failed_tests = messages.IntegerField(6, required=True)
  total_tests = messages.IntegerField(7, required=True)
  error_message = messages.StringField(8)


@Converter(sql_models.TestModuleResult, TestModuleResult)
def _TestModuleResultConverter(obj):
  return TestModuleResult(
      id=obj.id,
      name=obj.name,
      complete=obj.complete,
      duration_ms=obj.duration_ms,
      passed_tests=obj.passed_tests,
      failed_tests=obj.failed_tests,
      total_tests=obj.total_tests,
      error_message=obj.error_message,
  )


@Converter(api_messages.TestGroupStatus, TestModuleResult)
def _LegacyTestModuleResultConverter(obj):
  return TestModuleResult(
      name=obj.name,
      complete=obj.is_complete,
      duration_ms=obj.elapsed_time,
      passed_tests=obj.passed_test_count,
      failed_tests=obj.failed_test_count,
      total_tests=obj.total_test_count,
      error_message=obj.failure_message,
  )


class TestModuleResultList(messages.Message):
  """List of test module results."""
  results = messages.MessageField(TestModuleResult, 1, repeated=True)
  extra_info = messages.StringField(2)


class TestCaseResult(messages.Message):
  """Test case result."""
  id = messages.IntegerField(1, required=True)
  module_id = messages.StringField(2, required=True)
  name = messages.StringField(3, required=True)
  status = messages.EnumField(xts_result.TestStatus, 4, required=True)
  error_message = messages.StringField(5)
  stack_trace = messages.StringField(6)


@Converter(sql_models.TestCaseResult, TestCaseResult)
def _TestCaseResultConverter(obj):
  return TestCaseResult(
      id=obj.id,
      module_id=obj.module_id,
      name=obj.name,
      status=obj.status,
      error_message=obj.error_message,
      stack_trace=obj.stack_trace,
  )


class TestCaseResultList(messages.Message):
  """List of test case results with pagination."""
  results = messages.MessageField(TestCaseResult, 1, repeated=True)
  next_page_token = messages.StringField(2)


class TestRunAction(messages.Message):
  """A test run action."""
  id = messages.StringField(1)
  name = messages.StringField(2, required=True)
  description = messages.StringField(3)
  hook_class_name = messages.StringField(4, required=True)
  phases = messages.EnumField(ndb_models.TestRunPhase, 5, repeated=True)
  options = messages.MessageField(NameValuePair, 6, repeated=True)
  tradefed_result_reporters = messages.MessageField(
      TradefedConfigObject, 7, repeated=True)
  authorization_state = messages.EnumField(ndb_models.AuthorizationState, 8)
  credentials = messages.MessageField(CredentialsInfo, 9)


@Converter(ndb_models.TestRunAction, TestRunAction)
def _TestRunActionConverter(obj):
  return TestRunAction(
      id=str(obj.key.id()) if obj.key else None,
      name=obj.name,
      description=obj.description,
      hook_class_name=obj.hook_class_name,
      phases=obj.phases,
      options=ConvertNameValuePairs(obj.options, NameValuePair),
      tradefed_result_reporters=ConvertList(
          obj.tradefed_result_reporters, TradefedConfigObject),
      credentials=Convert(obj.credentials, CredentialsInfo))


@Converter(TestRunAction, ndb_models.TestRunAction)
def _TestRunActionMessageConverter(msg):
  return ndb_models.TestRunAction(
      key=ConvertToKeyOrNone(ndb_models.TestRunAction, msg.id),
      name=msg.name,
      description=msg.description,
      hook_class_name=msg.hook_class_name,
      phases=msg.phases,
      options=ConvertNameValuePairs(msg.options, ndb_models.NameValuePair),
      tradefed_result_reporters=ConvertList(
          msg.tradefed_result_reporters, ndb_models.TradefedConfigObject))


class TestRunActionList(messages.Message):
  """A list of test run actions."""
  actions = messages.MessageField(TestRunAction, 1, repeated=True)


class TestRunActionRef(messages.Message):
  """A test run action reference."""
  action_id = messages.StringField(1)
  options = messages.MessageField(NameValuePair, 2, repeated=True)


@Converter(ndb_models.TestRunActionRef, TestRunActionRef)
def _TestRunActionRefConverter(obj):
  return TestRunActionRef(
      action_id=str(obj.action_key.id()) if obj.action_key else None,
      options=ConvertNameValuePairs(obj.options, NameValuePair))


@Converter(TestRunActionRef, ndb_models.TestRunActionRef)
def _TestRunActionRefMessageConverter(msg):
  return ndb_models.TestRunActionRef(
      action_key=ConvertToKeyOrNone(ndb_models.TestRunAction, msg.action_id),
      options=ConvertNameValuePairs(msg.options, ndb_models.NameValuePair))


class TestRunActionRefList(messages.Message):
  """A list of test run action references."""
  refs = messages.MessageField(TestRunActionRef, 1, repeated=True)


class TestRunHook(messages.Message):
  """Information about a test run hook."""
  name = messages.StringField(1, required=True)
  option_defs = messages.MessageField(OptionDef, 2, repeated=True)


class TestRunHookList(messages.Message):
  """A list of test run hook."""
  test_run_hooks = messages.MessageField(TestRunHook, 1, repeated=True)


class TestResourceObj(messages.Message):
  """A test resource object for a test."""
  name = messages.StringField(1)
  url = messages.StringField(2)
  cache_url = messages.StringField(3)
  test_resource_type = messages.EnumField(ndb_models.TestResourceType, 4)
  decompress = messages.BooleanField(5)
  decompress_dir = messages.StringField(6)
  mount_zip = messages.BooleanField(7)
  params = messages.MessageField(TestResourceParameters, 8)


@Converter(ndb_models.TestResourceObj, TestResourceObj)
def _TestResourceObjConverter(obj):
  return TestResourceObj(
      name=obj.name,
      url=obj.url,
      cache_url=obj.cache_url,
      test_resource_type=obj.test_resource_type,
      decompress=obj.decompress,
      decompress_dir=obj.decompress_dir,
      mount_zip=obj.mount_zip,
      params=Convert(obj.params, TestResourceParameters))


@Converter(TestResourceObj, ndb_models.TestResourceObj)
def _TestResourceObjMessageConverter(msg):
  return ndb_models.TestResourceObj(
      name=msg.name,
      url=msg.url,
      cache_url=msg.cache_url,
      test_resource_type=msg.test_resource_type,
      decompress=msg.decompress,
      decompress_dir=msg.decompress_dir,
      mount_zip=msg.mount_zip,
      params=Convert(msg.params, ndb_models.TestResourceParameters))


class TestRunConfig(messages.Message):
  """A test run config."""
  test_id = messages.StringField(1, required=True)
  cluster = messages.StringField(2, required=True, default=_DEFAULT_CLUSTER)
  command = messages.StringField(3, required=True, default='')
  retry_command = messages.StringField(4, required=True, default='')
  device_specs = messages.StringField(5, repeated=True)
  run_target = messages.StringField(6)  # Deprecated
  run_count = messages.IntegerField(7, required=True, default=1)
  shard_count = messages.IntegerField(8, required=True, default=1)
  sharding_mode = messages.EnumField(
      ndb_models.ShardingMode, 9, default=ndb_models.ShardingMode.RUNNER)
  extra_args = messages.StringField(10)  # TODO: Deprecated
  retry_extra_args = messages.StringField(11)  # TODO: Deprecated
  max_retry_on_test_failures = messages.IntegerField(12)
  queue_timeout_seconds = messages.IntegerField(
      13, required=True, default=env.DEFAULT_QUEUE_TIMEOUT_SECONDS)
  invocation_timeout_seconds = messages.IntegerField(
      14, required=True, default=env.DEFAULT_INVOCATION_TIMEOUT_SECONDS)
  output_idle_timeout_seconds = messages.IntegerField(
      15, default=env.DEFAULT_OUTPUT_IDLE_TIMEOUT_SECONDS)
  before_device_action_ids = messages.StringField(16, repeated=True)
  test_run_action_refs = messages.MessageField(
      TestRunActionRef, 17, repeated=True)
  test_resource_objs = messages.MessageField(
      TestResourceObj, 18, repeated=True)
  use_parallel_setup = messages.BooleanField(19, default=True)
  allow_partial_device_match = messages.BooleanField(20, default=False)


@Converter(ndb_models.TestRunConfig, TestRunConfig)
def _TestRunConfigConverter(obj):
  """Converts test run configs."""
  if (not obj.command or not obj.retry_command) and obj.test_key:
    test = obj.test_key.get()
    if not obj.command and test:
      obj.command = test.command
      if obj.extra_args:
        obj.command += ' %s' % obj.extra_args
    if not obj.retry_command and test:
      obj.retry_command = test.retry_command_line
      if obj.retry_extra_args:
        obj.retry_command += ' %s' % obj.retry_extra_args
  return TestRunConfig(
      test_id=str(obj.test_key.id()) if obj.test_key else None,
      cluster=obj.cluster,
      command=obj.command,
      retry_command=obj.retry_command,
      device_specs=obj.device_specs or ConvertToDeviceSpecs(obj.run_target),
      run_target=obj.run_target,
      run_count=obj.run_count,
      shard_count=obj.shard_count,
      sharding_mode=obj.sharding_mode,
      max_retry_on_test_failures=obj.max_retry_on_test_failures,
      queue_timeout_seconds=obj.queue_timeout_seconds,
      invocation_timeout_seconds=obj.invocation_timeout_seconds,
      output_idle_timeout_seconds=obj.output_idle_timeout_seconds,
      before_device_action_ids=[
          str(key.id()) for key in obj.before_device_action_keys
      ],
      test_run_action_refs=ConvertList(
          obj.test_run_action_refs, TestRunActionRef),
      test_resource_objs=ConvertList(obj.test_resource_objs, TestResourceObj),
      use_parallel_setup=obj.use_parallel_setup,
      allow_partial_device_match=obj.allow_partial_device_match)


@Converter(TestRunConfig, ndb_models.TestRunConfig)
def _TestRunConfigMessageConverter(msg):
  return ndb_models.TestRunConfig(
      test_key=ConvertToKeyOrNone(ndb_models.Test, msg.test_id),
      cluster=msg.cluster,
      command=msg.command,
      retry_command=msg.retry_command,
      device_specs=msg.device_specs,
      run_target=msg.run_target,
      run_count=msg.run_count,
      shard_count=msg.shard_count,
      sharding_mode=msg.sharding_mode,
      extra_args=msg.extra_args,  # TODO: Deprecated
      retry_extra_args=msg.retry_extra_args,  # TODO: Deprecated
      max_retry_on_test_failures=msg.max_retry_on_test_failures,
      queue_timeout_seconds=msg.queue_timeout_seconds,
      invocation_timeout_seconds=msg.invocation_timeout_seconds,
      output_idle_timeout_seconds=msg.output_idle_timeout_seconds,
      before_device_action_keys=[
          ConvertToKeyOrNone(ndb_models.DeviceAction, device_action_id)
          for device_action_id in msg.before_device_action_ids
      ],
      test_run_action_refs=ConvertList(
          msg.test_run_action_refs, ndb_models.TestRunActionRef),
      test_resource_objs=ConvertList(
          msg.test_resource_objs, ndb_models.TestResourceObj),
      use_parallel_setup=msg.use_parallel_setup,
      allow_partial_device_match=msg.allow_partial_device_match)


class TestRunConfigList(messages.Message):
  """A list of test run configs."""
  test_run_configs = messages.MessageField(TestRunConfig, 1, repeated=True)


@Converter(ndb_models.TestRunConfigList, TestRunConfigList)
def _TestRunConfigListConverter(obj):
  return TestRunConfigList(
      test_run_configs=ConvertList(obj.test_run_configs, TestRunConfig),)


@Converter(TestRunConfigList, ndb_models.TestRunConfigList)
def _TestRunConfigListMessageConverter(msg):
  return ndb_models.TestRunConfigList(
      test_run_configs=ConvertList(msg.test_run_configs,
                                   ndb_models.TestRunConfig))


# TODO: Deprecate TestResourcePipe
class TestResourcePipe(messages.Message):
  """A test resource pipe for a test plan."""
  name = messages.StringField(1, required=True)
  url = messages.StringField(2)
  test_resource_type = messages.EnumField(ndb_models.TestResourceType, 3)


@Converter(ndb_models.TestResourcePipe, TestResourcePipe)
def _TestResourcePipeConverter(obj):
  return TestResourcePipe(
      name=obj.name,
      url=obj.url,
      test_resource_type=obj.test_resource_type)


@Converter(TestResourcePipe, ndb_models.TestResourcePipe)
def _TestResourcePipeMessageConverter(msg):
  return ndb_models.TestResourcePipe(
      name=msg.name,
      url=msg.url,
      test_resource_type=msg.test_resource_type)


class TestRunSequence(messages.Message):
  """A list of test run configs to run as retries."""
  id = messages.StringField(1)
  state = messages.EnumField(ndb_models.TestRunSequenceState, 2)
  test_run_configs = messages.MessageField(TestRunConfig, 3, repeated=True)
  finished_test_run_ids = messages.StringField(4, repeated=True)


@Converter(ndb_models.TestRunSequence, TestRunSequence)
def _TestRunSequenceConverter(obj):
  return TestRunSequence(
      id=str(obj.key.id()),
      state=obj.state,
      test_run_configs=ConvertList(obj.test_run_configs, TestRunConfig),
      finished_test_run_ids=obj.finished_test_run_ids)


@Converter(TestRunSequence, ndb_models.TestRunSequence)
def _TestRunSequenceMessageConverter(msg):
  return ndb_models.TestRunSequence(
      state=msg.state,
      test_run_configs=ConvertList(msg.test_run_configs,
                                   ndb_models.TestRunConfig),
      finished_test_run_ids=msg.finished_test_run_ids)


class TestPlan(messages.Message):
  """A test plan."""
  id = messages.StringField(1)
  name = messages.StringField(2, required=True)
  labels = messages.StringField(3, repeated=True)
  cron_exp = messages.StringField(4)
  cron_exp_timezone = messages.StringField(5, default='UTC')
  test_run_configs = messages.MessageField(TestRunConfig, 6, repeated=True)
  test_run_sequences = messages.MessageField(
      TestRunConfigList, 7, repeated=True)
  last_run_time = message_types.DateTimeField(8)
  last_run_ids = messages.StringField(9, repeated=True)
  last_run_error = messages.StringField(10)
  next_run_time = message_types.DateTimeField(11)


@Converter(ndb_models.TestPlan, TestPlan)
def _TestPlanConverter(obj):
  status = None
  if obj.key.id():
    status = ndb_models.TestPlanStatus.query(ancestor=obj.key).get()
  return TestPlan(
      id=str(obj.key.id()),
      name=obj.name,
      labels=obj.labels,
      cron_exp=obj.cron_exp,
      cron_exp_timezone=obj.cron_exp_timezone,
      test_run_configs=ConvertList(obj.test_run_configs, TestRunConfig),
      test_run_sequences=ConvertList(obj.test_run_sequences, TestRunConfigList),
      last_run_time=_AddTimezone(status.last_run_time) if status else None,
      last_run_ids=([str(key.id()) for key in status.last_run_keys]
                    if status else []),
      last_run_error=status.last_run_error if status else None,
      next_run_time=_AddTimezone(status.next_run_time) if status else None,
  )


@Converter(TestPlan, ndb_models.TestPlan)
def _TestPlanMessageConverter(msg):
  return ndb_models.TestPlan(
      key=ConvertToKeyOrNone(ndb_models.TestPlan, getattr(msg, 'id')),
      name=msg.name,
      labels=msg.labels,
      cron_exp=msg.cron_exp,
      cron_exp_timezone=msg.cron_exp_timezone,
      test_run_configs=ConvertList(
          msg.test_run_configs, ndb_models.TestRunConfig),
      test_run_sequences=ConvertList(
          msg.test_run_sequences, ndb_models.TestRunConfigList))


class TestPlanList(messages.Message):
  """A list of test plans."""
  test_plans = messages.MessageField(TestPlan, 1, repeated=True)


class TestContextObj(messages.Message):
  """A test context object."""
  command_line = messages.StringField(1)
  env_vars = messages.MessageField(NameValuePair, 2, repeated=True)
  test_resources = messages.MessageField(TestResourceObj, 3, repeated=True)


@Converter(ndb_models.TestContextObj, TestContextObj)
def _TestContextObjConverter(obj):
  return TestContextObj(
      command_line=obj.command_line,
      env_vars=ConvertNameValuePairs(obj.env_vars, NameValuePair),
      test_resources=ConvertList(obj.test_resources, TestResourceObj))


class TestPackageInfo(messages.Message):
  """A test package info."""
  build_number = messages.StringField(1)
  target_architecture = messages.StringField(2)
  name = messages.StringField(3)
  fullname = messages.StringField(4)
  version = messages.StringField(5)


@Converter(ndb_models.TestPackageInfo, TestPackageInfo)
def _TestPackageInfoConverter(obj):
  return TestPackageInfo(
      build_number=obj.build_number,
      target_architecture=obj.target_architecture,
      name=obj.name,
      fullname=obj.fullname,
      version=obj.version)


class TestDeviceInfo(messages.Message):
  """A test device info."""
  device_serial = messages.StringField(1)
  hostname = messages.StringField(2)
  run_target = messages.StringField(3)
  build_id = messages.StringField(4)
  product = messages.StringField(5)
  sdk_version = messages.StringField(7)


@Converter(ndb_models.TestDeviceInfo, TestDeviceInfo)
def _TestDeviceInfoConverter(obj):
  return TestDeviceInfo(
      device_serial=obj.device_serial,
      hostname=obj.hostname,
      run_target=obj.run_target,
      build_id=obj.build_id,
      product=obj.product,
      sdk_version=obj.sdk_version)


class TestRun(messages.Message):
  """A test run."""
  id = messages.StringField(1)
  prev_test_run_id = messages.StringField(2)
  user = messages.StringField(3)
  labels = messages.StringField(4, repeated=True)
  test_plan = messages.MessageField(TestPlan, 5)
  test = messages.MessageField(Test, 6)
  test_run_config = messages.MessageField(TestRunConfig, 7)
  test_resources = messages.MessageField(TestResourceObj, 8, repeated=True)
  state = messages.EnumField(ndb_models.TestRunState, 9)
  state_info = messages.StringField(10)
  output_url = messages.StringField(11)
  prev_test_context = messages.MessageField(TestContextObj, 12)
  next_test_context = messages.MessageField(TestContextObj, 13)

  request_id = messages.StringField(14)
  sequence_id = messages.StringField(15)
  total_test_count = messages.IntegerField(16)
  failed_test_count = messages.IntegerField(17)
  failed_test_run_count = messages.IntegerField(18)

  create_time = message_types.DateTimeField(19)
  update_time = message_types.DateTimeField(20)

  before_device_actions = messages.MessageField(DeviceAction, 21, repeated=True)
  test_run_actions = messages.MessageField(TestRunAction, 22, repeated=True)

  test_devices = messages.MessageField(TestDeviceInfo, 23, repeated=True)
  test_package_info = messages.MessageField(TestPackageInfo, 24)
  log_entries = messages.MessageField(EventLogEntry, 25, repeated=True)


@Converter(ndb_models.TestRun, TestRun)
def _TestRunConverter(obj):
  """Converts a ndb_models.TestRun object to a message."""
  # TestRun.test stores a snapshot copy of a test at test run creation time.
  test_msg = Convert(obj.test, Test)
  test_run_config_msg = Convert(obj.test_run_config, TestRunConfig)
  # Grab a valid test id from test_run_config since a snapshot copy is missing
  # a key.
  if test_msg and test_run_config_msg:
    test_msg.id = test_run_config_msg.test_id

  return TestRun(
      id=str(obj.key.id()),
      prev_test_run_id=(str(obj.prev_test_run_key.id())
                        if obj.prev_test_run_key else None),
      user=obj.user,
      labels=obj.labels,
      test_plan=(
          Convert(obj.test_plan_key.get(), TestPlan)
          if obj.test_plan_key else None),
      test=test_msg,
      test_run_config=test_run_config_msg,
      test_resources=ConvertList(obj.test_resources, TestResourceObj),
      state=obj.state,
      state_info=_GetTestRunStateInfo(obj),
      output_url=(file_util.GetAppStorageUrl([obj.output_path])
                  if obj.output_path else None),
      prev_test_context=Convert(obj.prev_test_context, TestContextObj),
      next_test_context=Convert(obj.next_test_context, TestContextObj),
      request_id=obj.request_id,
      sequence_id=obj.sequence_id,
      total_test_count=obj.total_test_count,
      failed_test_count=obj.failed_test_count,
      failed_test_run_count=obj.failed_test_run_count,
      create_time=_AddTimezone(obj.create_time),
      update_time=_AddTimezone(obj.update_time),
      before_device_actions=ConvertList(
          obj.before_device_actions, DeviceAction),
      test_run_actions=ConvertList(obj.test_run_actions, TestRunAction),
      test_devices=ConvertList(obj.test_devices, TestDeviceInfo),
      test_package_info=Convert(obj.test_package_info, TestPackageInfo),
      log_entries=ConvertList(event_log.GetEntries(obj), EventLogEntry),
  )


def _GetTestRunStateInfo(test_run: ndb_models.TestRun):
  """Determine an ndb_models.TestRun's relevant state information."""
  error_info = test_run.GetErrorInfo()
  if error_info:
    return error_info
  if test_run.state == ndb_models.TestRunState.PENDING:
    # TODO: consider adding a download progress endpoint instead
    for resource in test_run.test_resources:
      if resource.cache_url:
        continue  # already downloaded
      tracker = ndb_models.TestResourceTracker.get_by_id(resource.url)
      if tracker is None or tracker.completed:
        continue  # download either not started or already completed
      return 'Downloading %s [%d%%]' % (resource.name,
                                        100 * tracker.download_progress)
  return None


class TestRunSummary(messages.Message):
  """A test run."""
  id = messages.StringField(1)
  prev_test_run_id = messages.StringField(2)
  labels = messages.StringField(3, repeated=True)
  test_name = messages.StringField(4)
  device_specs = messages.StringField(5, repeated=True)
  state = messages.EnumField(ndb_models.TestRunState, 6)
  test_package_info = messages.MessageField(TestPackageInfo, 7)
  test_devices = messages.MessageField(TestDeviceInfo, 8, repeated=True)
  total_test_count = messages.IntegerField(9)
  failed_test_count = messages.IntegerField(10)
  failed_test_run_count = messages.IntegerField(11)
  create_time = message_types.DateTimeField(12)
  update_time = message_types.DateTimeField(13)


@Converter(ndb_models.TestRunSummary, TestRunSummary)
def _TestRunSummaryConverter(obj):
  """Converts a ndb_models.TestRunSummary object to a message."""
  return TestRunSummary(
      id=str(obj.key.id()),
      prev_test_run_id=(str(obj.prev_test_run_key.id())
                        if obj.prev_test_run_key else None),
      labels=obj.labels,
      test_name=obj.test_name,
      device_specs=obj.device_specs or ConvertToDeviceSpecs(obj.run_target),
      state=obj.state,
      test_package_info=Convert(obj.test_package_info, TestPackageInfo),
      test_devices=ConvertList(obj.test_devices, TestDeviceInfo),
      total_test_count=obj.total_test_count,
      failed_test_count=obj.failed_test_count,
      failed_test_run_count=obj.failed_test_run_count,
      create_time=_AddTimezone(obj.create_time),
      update_time=_AddTimezone(obj.update_time))


class TestRunSummaryList(messages.Message):
  """A list of test run summaries."""
  test_runs = messages.MessageField(TestRunSummary, 1, repeated=True)
  prev_page_token = messages.StringField(2)
  next_page_token = messages.StringField(3)


class TestRunMetadata(messages.Message):
  """Combination of a test run and its command attempts."""
  test_run = messages.MessageField(TestRun, 1, required=True)
  command_attempts = messages.MessageField(
      api_messages.CommandAttemptMessage, 2, repeated=True)


class TestRunMetadataList(messages.Message):
  """List of test run metadata.

  Attributes:
    test_runs: a list of test run metadata.
    server_version: a server version.
  """
  test_runs = messages.MessageField(TestRunMetadata, 1, repeated=True)
  server_version = messages.StringField(2)


class RerunContext(messages.Message):
  """Previous test run context used for rerun.

  Represents either a local test run (ID provided) or a remote test run (context
  file already uploaded to local file storage and filename provided).
  """
  test_run_id = messages.StringField(1)
  context_filename = messages.StringField(2)
  context_file_url = messages.StringField(3)


class NewTestRunRequest(messages.Message):
  """A request object for test_runs.new API."""
  labels = messages.StringField(1, repeated=True)
  test_run_config = messages.MessageField(TestRunConfig, 2)
  rerun_context = messages.MessageField(RerunContext, 3)
  rerun_configs = messages.MessageField(TestRunConfig, 4, repeated=True)


class NodeConfig(messages.Message):
  """Node config."""
  env_vars = messages.MessageField(NameValuePair, 1, repeated=True)
  test_resource_default_download_urls = messages.MessageField(
      NameValuePair, 2, repeated=True)


@Converter(ndb_models.NodeConfig, NodeConfig)
def _NodeConfigConverter(obj):
  return NodeConfig(
      env_vars=ConvertNameValuePairs(obj.env_vars, NameValuePair),
      test_resource_default_download_urls=ConvertNameValuePairs(
          obj.test_resource_default_download_urls, NameValuePair))


@Converter(NodeConfig, ndb_models.NodeConfig)
def _NodeConfigMessageConverter(msg):
  """Converts a NodeConfig message into an object."""
  return ndb_models.NodeConfig(
      id=ndb_models.NODE_CONFIG_ID,
      env_vars=ConvertNameValuePairs(msg.env_vars, ndb_models.NameValuePair),
      test_resource_default_download_urls=ConvertNameValuePairs(
          msg.test_resource_default_download_urls, ndb_models.NameValuePair))


class PrivateNodeConfig(messages.Message):
  """User-specific settings."""
  ndb_version = messages.IntegerField(1)
  metrics_enabled = messages.BooleanField(2)
  gms_client_id = messages.StringField(3)
  setup_wizard_completed = messages.BooleanField(4)
  default_credentials = messages.MessageField(CredentialsInfo, 5)


@Converter(ndb_models.PrivateNodeConfig, PrivateNodeConfig)
def _PrivateNodeConfigConverter(obj):
  return PrivateNodeConfig(
      ndb_version=obj.ndb_version,
      metrics_enabled=obj.metrics_enabled,
      gms_client_id=obj.gms_client_id,
      setup_wizard_completed=obj.setup_wizard_completed,
      default_credentials=Convert(obj.default_credentials, CredentialsInfo))


@Converter(PrivateNodeConfig, ndb_models.PrivateNodeConfig)
def _PrivateNodeConfigMessageConverter(msg):
  """Converts a PrivateNodeConfig message into an object."""
  private_node_config = ndb_models.GetPrivateNodeConfig()
  private_node_config.ndb_version = msg.ndb_version
  private_node_config.metrics_enabled = msg.metrics_enabled
  private_node_config.gms_client_id = msg.gms_client_id
  private_node_config.setup_wizard_completed = msg.setup_wizard_completed
  return private_node_config


class FileCleanerOperation(messages.Message):
  """File cleaner operation."""
  type = messages.EnumField(
      ndb_models.FileCleanerOperationType, 1, required=True)
  params = messages.MessageField(NameValuePair, 2, repeated=True)


@Converter(ndb_models.FileCleanerOperation, FileCleanerOperation)
def _FileCleanerOperationConverter(obj):
  return FileCleanerOperation(
      type=obj.type, params=ConvertNameValuePairs(obj.params, NameValuePair))


@Converter(FileCleanerOperation, ndb_models.FileCleanerOperation)
def _FileCleanerOperationMessageConverter(msg):
  """Converts a FileCleanerOperation message into an object."""
  return ndb_models.FileCleanerOperation(
      type=msg.type,
      params=ConvertNameValuePairs(msg.params, ndb_models.NameValuePair))


class FileCleanerCriterion(messages.Message):
  """File cleaner criterion."""
  type = messages.EnumField(
      ndb_models.FileCleanerCriterionType, 1, required=True)
  params = messages.MessageField(NameValuePair, 2, repeated=True)


@Converter(ndb_models.FileCleanerCriterion, FileCleanerCriterion)
def _FileCleanerCriterionConverter(obj):
  return FileCleanerCriterion(
      type=obj.type, params=ConvertNameValuePairs(obj.params, NameValuePair))


@Converter(FileCleanerCriterion, ndb_models.FileCleanerCriterion)
def _FileCleanerCriterionMessageConverter(msg):
  """Converts a FileCleanerCriterion message into an object."""
  return ndb_models.FileCleanerCriterion(
      type=msg.type,
      params=ConvertNameValuePairs(msg.params, ndb_models.NameValuePair))


class FileCleanerPolicy(messages.Message):
  """File cleaner policy."""
  name = messages.StringField(1, required=True)
  target = messages.EnumField(ndb_models.FileCleanerTargetType, 2)
  operation = messages.MessageField(FileCleanerOperation, 3, required=True)
  criteria = messages.MessageField(FileCleanerCriterion, 4, repeated=True)


@Converter(ndb_models.FileCleanerPolicy, FileCleanerPolicy)
def _FileCleanerPolicyConverter(obj):
  return FileCleanerPolicy(
      name=obj.name,
      target=obj.target,
      operation=Convert(obj.operation, FileCleanerOperation),
      criteria=ConvertList(obj.criteria, FileCleanerCriterion))


@Converter(FileCleanerPolicy, ndb_models.FileCleanerPolicy)
def _FileCleanerPolicyMessageConverter(msg):
  """Converts a FileCleanerPolicy message into an object."""
  return ndb_models.FileCleanerPolicy(
      name=msg.name,
      target=msg.target,
      operation=Convert(msg.operation, ndb_models.FileCleanerOperation),
      criteria=ConvertList(msg.criteria, ndb_models.FileCleanerCriterion))


class FileCleanerConfig(messages.Message):
  """File cleaner config."""
  name = messages.StringField(1, required=True)
  description = messages.StringField(2)
  directories = messages.StringField(3, repeated=True)
  policy_names = messages.StringField(4, repeated=True)


@Converter(ndb_models.FileCleanerConfig, FileCleanerConfig)
def _FileCleanerConfigConverter(obj):
  return FileCleanerConfig(
      name=obj.name,
      description=obj.description,
      directories=obj.directories,
      policy_names=obj.policy_names)


@Converter(FileCleanerConfig, ndb_models.FileCleanerConfig)
def _FileCleanerConfigMessageConverter(msg):
  """Converts a FileCleanerConfig message into an object."""
  return ndb_models.FileCleanerConfig(
      name=msg.name,
      description=msg.description,
      directories=msg.directories,
      policy_names=msg.policy_names)


class FileCleanerSettings(messages.Message):
  """File cleaner settings, which combine cleanup policies and configs."""
  policies = messages.MessageField(FileCleanerPolicy, 1, repeated=True)
  configs = messages.MessageField(FileCleanerConfig, 2, repeated=True)


@Converter(ndb_models.FileCleanerSettings, FileCleanerSettings)
def _FileCleanerSettingsConverter(obj):
  return FileCleanerSettings(
      policies=ConvertList(obj.policies, FileCleanerPolicy),
      configs=ConvertList(obj.configs, FileCleanerConfig))


@Converter(FileCleanerSettings, ndb_models.FileCleanerSettings)
def _FileCleanerSettingsMessageConverter(msg):
  """Converts a FileCleanerSettings message into an object."""
  return ndb_models.FileCleanerSettings(
      id=ndb_models.FILE_CLEANER_SETTINGS_ID,
      policies=ConvertList(msg.policies, ndb_models.FileCleanerPolicy),
      configs=ConvertList(msg.configs, ndb_models.FileCleanerConfig))


class NetdataAlarmStatus(messages.Enum):
  REMOVED = 0
  UNINITIALIZED = 1
  UNDEFINED = 2
  CLEAR = 3
  WARNING = 4
  CRITICAL = 5


class NetdataAlarm(messages.Message):
  hostname = messages.StringField(1, required=True)
  id = messages.IntegerField(2, required=True)
  name = messages.StringField(3, required=True)
  value = messages.StringField(4, required=True)
  status = messages.EnumField(NetdataAlarmStatus, 5, required=True)


class NetdataAlarmList(messages.Message):
  alarms = messages.MessageField(NetdataAlarm, 1, repeated=True)


class Build(messages.Message):
  """A build."""
  id = messages.StringField(1)
  name = messages.StringField(2)
  file_url = messages.StringField(3)
  size = messages.IntegerField(4)
  labels = messages.StringField(5, repeated=True)
  create_time = message_types.DateTimeField(6)
  update_time = message_types.DateTimeField(7)


@Converter(ndb_models.Build, Build)
def _BuildConverter(obj):
  return Build(
      id=str(obj.key.id()) if obj.key else None,
      name=obj.name,
      file_url=obj.file_url,
      size=obj.size,
      labels=obj.labels,
      create_time=_AddTimezone(obj.create_time),
      update_time=_AddTimezone(obj.update_time),
  )


@Converter(Build, ndb_models.Build)
def _BuildMessageConverter(msg):
  return ndb_models.Build(
      key=ConvertToKeyOrNone(ndb_models.Build, msg.id),
      name=msg.name,
      file_url=msg.file_url,
      size=msg.size,
      labels=msg.labels)


class BuildList(messages.Message):
  """A list of builds."""

  builds = messages.MessageField(Build, 1, repeated=True)
