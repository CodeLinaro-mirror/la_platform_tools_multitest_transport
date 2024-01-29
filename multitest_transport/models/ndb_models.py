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

"""Datastore model classes."""
import collections
import datetime
import re
from typing import Optional
import uuid

from protorpc import messages
from tradefed_cluster import common
from tradefed_cluster.util import ndb_shim as ndb


from multitest_transport.util import env
from multitest_transport.util import oauth2_util

DEFAULT_CLUSTER = 'default'
NODE_CONFIG_ID = 1
FILE_CLEANER_SETTINGS_ID = 1

# Maps cancellation reasons into human-readable strings.
_TEST_RUN_CANCEL_REASON_MAP = {
    common.CancelReason.QUEUE_TIMEOUT: 'Queue timeout',
    common.CancelReason.REQUEST_API: 'User requested',
    common.CancelReason.COMMAND_ALREADY_CANCELED: 'Command already canceled',
    common.CancelReason.REQUEST_ALREADY_CANCELED: 'Request already canceled',
    common.CancelReason.COMMAND_NOT_EXECUTABLE: 'Invalid command',
    common.CancelReason.INVALID_REQUEST: 'Invalid request',
}


class NameValuePair(ndb.Model):
  """A generic name-value pair to store an option.

  Attributes:
    name: a name.
    value: a value.
  """
  name = ndb.StringProperty(required=True)
  value = ndb.StringProperty()

  @classmethod
  def FromDict(cls, d):
    return [cls(name=k, value=v) for k, v in d.items()]

  @classmethod
  def ToDict(cls, pairs):
    d = collections.OrderedDict()
    for pair in pairs:
      d[pair.name] = pair.value
    return d


class NameMultiValuePair(ndb.Model):
  """A generic name-multi value pair to store an option.

  Attributes:
    name: a name.
    values: a list of values.
  """
  name = ndb.StringProperty(required=True)
  values = ndb.StringProperty(repeated=True)

  @classmethod
  def FromDict(cls, d):
    return [cls(name=k, values=v) for k, v in d.items()]

  @classmethod
  def ToDict(cls, pairs):
    d = collections.OrderedDict()
    for pair in pairs:
      d[pair.name] = pair.values
    return d


class AuthorizationState(messages.Enum):
  """Authorization states."""
  NOT_APPLICABLE = 0  # Does not require authorization
  AUTHORIZED = 1  # Requires authorization and has credentials
  UNAUTHORIZED = 2  # Requires authorization and no credentials found


class AuthorizationMethod(messages.Enum):
  """Authorization methods."""
  OAUTH2_SERVICE_ACCOUNT = 1


class BuildItemPathType(messages.Enum):
  """The path type of build item."""
  DIRECTORY_FILE = 1
  URL = 2


class BuildChannelConfig(ndb.Model):
  """A build channel config."""
  name = ndb.StringProperty(required=True)
  provider_name = ndb.StringProperty(required=True)
  options = ndb.StructuredProperty(NameValuePair, repeated=True)
  credentials = oauth2_util.CredentialsProperty()


class ConfigSetStatus(messages.Enum):
  NOT_IMPORTED = 0
  IMPORTED = 1
  UPDATABLE = 2


class ConfigSetInfo(ndb.Model):
  """Metadata for a config set.

  Attributes:
    url: origin url where this config can be downloaded from
    hash: SHA value of the file, used for comparing two files
    name: name to display to the user
    description: describes the contents of the file
    last_update_time: timestamp when the file was last imported
  """
  url = ndb.StringProperty(required=True)
  hash = ndb.StringProperty()
  name = ndb.StringProperty(required=True)
  description = ndb.StringProperty()
  last_update_time = ndb.StringProperty()


class ConfigSetInfoList(ndb.Model):
  """A list of ConfigSetInfos."""
  config_set_infos = ndb.StructuredProperty(ConfigSetInfo, repeated=True)


class EventLogLevel(messages.Enum):
  """Event log levels."""
  INFO = 1
  WARNING = 2
  ERROR = 3


class EventLogEntry(ndb.Model):
  """Event log entry. The optional parent key defines the related object.

  Attributes:
    create_time: creation timestamp
    level: log level
    message: log message
  """
  create_time = ndb.DateTimeProperty(auto_now_add=True)
  level = ndb.EnumProperty(EventLogLevel, required=True)
  message = ndb.TextProperty(required=True)


class TestResourceType(messages.Enum):
  UNKNOWN = 0
  DEVICE_IMAGE = 1
  TEST_PACKAGE = 2
  SYSTEM_IMAGE = 3


class TestResourceParameters(ndb.Model):
  """Repeated properties of TestResourceObj and TestResourceDef.

  Because the test resources are StructuredProperty of tests, they cannot
  directly contain repeated properties. The test resource models use this class
  to wrap the repeated properties in a LocalStructuredProperty.

  Attributes:
    decompress_files: the files to be decompressed from the downloaded file.
  """
  decompress_files = ndb.StringProperty(repeated=True)

  @classmethod
  def Clone(cls, obj):
    """Copy all properties to a new object if it's not None."""
    return cls(decompress_files=obj.decompress_files) if obj else None


class TestResourceDef(ndb.Model):
  """A test resource definition.

  Attributes:
    name: a test resource name.
    default_download_url: a default download URL.
    test_resource_type: a test resource type.
    decompress: whether the host should decompress the downloaded file.
    decompress_dir: the directory where the host decompresses the file.
    mount_zip: whether to mount zip file.
    params: test resource parameters.
  """
  name = ndb.StringProperty(required=True)
  default_download_url = ndb.StringProperty()
  test_resource_type = ndb.EnumProperty(TestResourceType)
  decompress = ndb.BooleanProperty()
  decompress_dir = ndb.StringProperty()
  mount_zip = ndb.BooleanProperty()
  params = ndb.LocalStructuredProperty(TestResourceParameters)

  def ToTestResourceObj(self):
    """Create a TestResourceObj from this definition."""
    return TestResourceObj(
        name=self.name,
        url=self.default_download_url,
        test_resource_type=self.test_resource_type,
        decompress=self.decompress or False,
        decompress_dir=self.decompress_dir or '',
        mount_zip=self.mount_zip or False,
        params=TestResourceParameters.Clone(self.params))


class TestRunParameter(ndb.Model):
  """Test run parameter.

  Attributes:
    max_retry_on_test_failures: the max number of retry on test failure.
    invocation_timeout_seconds: the maximum time for each invocation to run. If
        an invocation(attempt) runs longer than a given timeout, it would be
        force stopped.
    output_idle_timeout_seconds: how long a test run's output can be idle before
        attempting recovery
  """
  max_retry_on_test_failures = ndb.IntegerProperty()
  invocation_timeout_seconds = ndb.IntegerProperty()
  output_idle_timeout_seconds = ndb.IntegerProperty()


class VisibilityType(messages.Enum):
  PUBLIC = 0  # Test is visible to any user.
  HIDDEN = 1  # Test is not visible to any user.


class Test(ndb.Model):
  """A test.

  Attributes:
    name: a test name.
    description: user-friendly string that describes the test suite.
    test_resource_defs: a list of test resource definitions.
    command: a TF command line.
    env_vars: a dict of environment variables to set before running a test.
    output_file_patterns: a list of file patterns to collect after a test run.
    result_file: XML result file path.
    setup_scripts: a list of scripts to run before running a test.
    jvm_options: a list of JVM options to be passed to TF.
    java_properties: a dict of Java properties to be passed to TF.
    context_file_dir: directory where the context file which needs to be passed
      across attempts is located.
    context_file_pattern: a regex pattern for the filename of the context file
      which needs to be passed across attempts.
    retry_command_line: a command line to use in retry invocations. attempts.
    runner_sharding_args: extra args to enable runner sharding. It can contain a
      reference to a desired shard count (e.g. ${TF_SHARD_COUNT})
    default_test_run_parameters: default test run parameters.
    module_config_pattern: a regex pattern for module config files.
    module_execution_args: extra args to run a specific module.
    visibility_type: the visibility of a test.
  """
  name = ndb.StringProperty(required=True)
  description = ndb.StringProperty()
  test_resource_defs = ndb.StructuredProperty(TestResourceDef, repeated=True)
  command = ndb.TextProperty(required=True)
  env_vars = ndb.StructuredProperty(NameValuePair, repeated=True)
  output_file_patterns = ndb.StringProperty(repeated=True)
  result_file = ndb.StringProperty()
  setup_scripts = ndb.StringProperty(repeated=True)
  jvm_options = ndb.StringProperty(repeated=True)
  java_properties = ndb.StructuredProperty(NameValuePair, repeated=True)
  context_file_dir = ndb.StringProperty()
  context_file_pattern = ndb.StringProperty()
  retry_command_line = ndb.TextProperty()
  runner_sharding_args = ndb.StringProperty()
  default_test_run_parameters = ndb.LocalStructuredProperty(TestRunParameter)
  module_config_pattern = ndb.StringProperty()
  module_execution_args = ndb.StringProperty()
  visibility_type = ndb.EnumProperty(
      VisibilityType, default=VisibilityType.PUBLIC
  )


class ShardingMode(messages.Enum):
  RUNNER = 0  # Let a test runner to take care of sharding.
  MODULE = 1  # Schedule each module as a separate command


class TradefedConfigObject(ndb.Model):
  """A Tradefed object and its options.

  Attributes:
    class_name: a Tradefed config class name.
    option_values: a list of option name and value pairs.
  """
  class_name = ndb.StringProperty(required=True)
  option_values = ndb.LocalStructuredProperty(NameMultiValuePair, repeated=True)


class DeviceAction(ndb.Model):
  """A device action.

  Attributes:
    name: a device action name.
    description: a description.
    test_resource_defs: a list of test resource definitions.
    tradefed_target_preparers: a list of Tradefed target preparers.
    device_type: (obsolete) the type of the devices that require the device
      action.
    tradefed_options: key-value pairs to be added to Tradefed configuration.
    device_spec: the regular expression of the device specs that require the
      device action.
  """
  name = ndb.StringProperty(required=True)
  description = ndb.StringProperty()
  test_resource_defs = ndb.LocalStructuredProperty(
      TestResourceDef, repeated=True)
  tradefed_target_preparers = ndb.LocalStructuredProperty(
      TradefedConfigObject, repeated=True)
  device_type = ndb.StringProperty()
  tradefed_options = ndb.LocalStructuredProperty(
      NameMultiValuePair, repeated=True)
  device_spec = ndb.StringProperty()


class TestRunPhase(messages.Enum):
  """Test run phases."""
  UNKNOWN = 0  # Invalid phase
  BEFORE_RUN = 1  # Before run is started (but is created)
  BEFORE_ATTEMPT = 2  # Before an attempt is created (task not sent to runner)
  AFTER_ATTEMPT = 3  # After an attempt is completed (successfully or not)
  AFTER_RUN = 4  # After run is completed (successfully or not)
  ON_SUCCESS = 5  # After run is completed successfully (may have test failures)
  ON_ERROR = 6  # After run fails to complete due to errors
  MANUAL = 7  # Phase triggered manually


class TestRunAction(ndb.Model):
  """Test run action, describes a specific hook execution.

  Attributes:
    name: action name.
    description: action description.
    hook_class_name: run hook class identifier.
    phases: phases during which hook should be triggered.
    options: key-value pairs to use when configuring the hook.
    tradefed_result_reporters: list of TF result reporters.
    credentials: stored OAuth2 credentials.
  """
  name = ndb.StringProperty(required=True)
  description = ndb.StringProperty()
  hook_class_name = ndb.StringProperty(required=True)
  phases = ndb.EnumProperty(TestRunPhase, repeated=True)
  options = ndb.LocalStructuredProperty(NameValuePair, repeated=True)
  tradefed_result_reporters = ndb.LocalStructuredProperty(
      TradefedConfigObject, repeated=True)
  credentials = oauth2_util.CredentialsProperty()


class TestRunActionRef(ndb.Model):
  """Test run action reference, with additional overridden options.

  Attributes:
    action_key: test run action to execute.
    options: additional key-value pairs to use when configuring the hook.
  """
  action_key = ndb.KeyProperty(TestRunAction, required=True)
  options = ndb.LocalStructuredProperty(NameValuePair, repeated=True)

  def ToAction(self):
    """Converts this ref into a test run action."""
    action = self.action_key.get()
    if not action:
      raise ValueError('Test run action %s not found' % self.action_key)
    options = NameValuePair.ToDict(action.options or [])
    options.update(NameValuePair.ToDict(self.options or []))
    action.options = NameValuePair.FromDict(options)
    return action


class TestResourceObj(ndb.Model):
  """A test resource object.

  The "Obj" suffix was added to avoid name collistion with TFC TestResource.

  Attributes:
    name: a test resource name.
    url: a URL.
    cache_url: a URL for a cached copy.
    test_resource_type: a test resource type.
    decompress: whether the host should decompress the downloaded file.
    decompress_dir: the directory where the host decompresses the file.
    mount_zip: whether to mount a zip file.
    params: test resource parameters.
  """
  name = ndb.StringProperty(required=True)
  url = ndb.StringProperty()
  cache_url = ndb.StringProperty()
  test_resource_type = ndb.EnumProperty(TestResourceType)
  decompress = ndb.BooleanProperty()
  decompress_dir = ndb.StringProperty()
  mount_zip = ndb.BooleanProperty()
  params = ndb.LocalStructuredProperty(TestResourceParameters)


class TestRunConfig(ndb.Model):
  """A test run config.

  Attributes:
    test_key: a Test key.
    cluster: a cluster to run a test in.
    command: the command to run the test suite
    retry_command: the command to retry this test run
    device_specs: device requirements expressed in space-separated list of
        key-value pairs (e.g. "product:bramble sim_state:LOADED").
    run_target: (deprecated) a run target. Only used when device_specs is empty.
    run_count: a run count.
    shard_count: a shard count.
    sharding_mode: a sharding mode.
    extra_args: a string containing extra arguments.
    retry_extra_args: extra arguments used when retrying.
    max_retry_on_test_failures: the max number of retry on test failure.
    queue_timeout_seconds: how long a test run can stay in QUEUED state before
        being cancelled
    invocation_timeout_seconds: the maximum time for each invocation to run. If
        an invocation(attempt) runs longer than a given timeout, it would be
        force stopped.
    output_idle_timeout_seconds: how long a test run's output can be idle before
        attempting recovery
    before_device_action_keys: device actions to execute before running a test.
    test_run_action_refs: test run actions to execute during a test.
    test_resource_objs: path to the files to use for test resources.
    use_parallel_setup: a flag on whether to setup devices in parallel.
    allow_partial_device_match: a flag on whether to allow partial device match
        or not
  """
  test_key = ndb.KeyProperty(kind=Test, required=True)
  cluster = ndb.StringProperty(required=True, default=DEFAULT_CLUSTER)
  command = ndb.TextProperty(required=True, default='')
  retry_command = ndb.TextProperty(required=True, default='')
  device_specs = ndb.StringProperty(repeated=True)
  run_target = ndb.StringProperty()
  run_count = ndb.IntegerProperty(required=True, default=1)
  shard_count = ndb.IntegerProperty(required=True, default=1)
  sharding_mode = ndb.EnumProperty(
      ShardingMode, default=ShardingMode.RUNNER)
  extra_args = ndb.StringProperty()   # TODO: Deprecated
  retry_extra_args = ndb.StringProperty()  # TODO: Deprecated
  max_retry_on_test_failures = ndb.IntegerProperty()
  queue_timeout_seconds = ndb.IntegerProperty(
      required=True, default=env.DEFAULT_QUEUE_TIMEOUT_SECONDS)
  invocation_timeout_seconds = ndb.IntegerProperty(
      default=env.DEFAULT_INVOCATION_TIMEOUT_SECONDS)
  output_idle_timeout_seconds = ndb.IntegerProperty(
      default=env.DEFAULT_OUTPUT_IDLE_TIMEOUT_SECONDS)
  before_device_action_keys = ndb.KeyProperty(DeviceAction, repeated=True)
  test_run_action_refs = ndb.LocalStructuredProperty(
      TestRunActionRef, repeated=True)
  test_resource_objs = ndb.LocalStructuredProperty(
      TestResourceObj, repeated=True)
  use_parallel_setup = ndb.BooleanProperty(default=True)
  allow_partial_device_match = ndb.BooleanProperty(default=False)


class TestRunConfigList(ndb.Model):
  """A list of test run configs.

  Attributes:
    test_run_configs: the list of configs
  """
  test_run_configs = ndb.LocalStructuredProperty(TestRunConfig, repeated=True)


class TestResourcePipe(ndb.Model):
  """A pipe which defines where to get test resources from.

  Attributes:
    name: a test resource name.
    url: a url.
    test_resource_type: a test resource type.
  """
  name = ndb.StringProperty(required=True)
  url = ndb.StringProperty()
  test_resource_type = ndb.EnumProperty(TestResourceType)


class TestRunSequenceState(messages.Enum):
  """Completion state for a TestRunSequence."""
  RUNNING = 0
  CANCELED = 1
  COMPLETED = 2
  ERROR = 3


class TestRunSequence(ndb.Model):
  """A list of test run configs to be scheduled as retries.

  Attributes:
    state: completion state for this sequence
    test_run_configs: remaining retries to schedule
    finished_test_run_ids: list of completed runs scheduled for this sequence
  """
  state = ndb.EnumProperty(TestRunSequenceState, required=True)
  test_run_configs = ndb.LocalStructuredProperty(TestRunConfig, repeated=True)
  finished_test_run_ids = ndb.StringProperty(repeated=True)


class TestPlan(ndb.Model):
  """A test plan.

  Attributes:
    name: a test resource name.
    labels: list of strings users can use to categorize test runs and plans.
    cron_exp: a CRON expression.
    cron_exp_timezone: timezone to use when processing cron expression.
    test_run_configs: a list of test run configs.
    test_run_sequences: a list of test run sequences triggered when running.
  """
  name = ndb.StringProperty(required=True)
  labels = ndb.StringProperty(repeated=True)
  cron_exp = ndb.StringProperty()
  cron_exp_timezone = ndb.StringProperty(default='UTC')
  test_run_configs = ndb.LocalStructuredProperty(TestRunConfig, repeated=True)
  test_run_sequences = ndb.LocalStructuredProperty(
      TestRunConfigList, repeated=True)

  @classmethod
  def _post_delete_hook(cls, key, future):
    status = TestPlanStatus.query(ancestor=key).get()
    if status:
      status.key.delete()


class TestPlanStatus(ndb.Model):
  """A test plan status."""
  last_run_time = ndb.DateTimeProperty()
  last_run_keys = ndb.KeyProperty(kind='TestRun', repeated=True)
  last_run_error = ndb.StringProperty()
  next_run_time = ndb.DateTimeProperty()
  next_run_task_name = ndb.StringProperty()


class TestRunState(messages.Enum):
  """Test run state values."""
  UNKNOWN = 0  # this is an invalid state
  PENDING = 1  # A test run is waiting to be kicked-off.
  QUEUED = 2  # A test run is queued by a runner.
  RUNNING = 3  # A test run is running by a runner.
  COMPLETED = 4  # A test run is completed.
  CANCELED = 5  # A test run is canceled.
  ERROR = 6  # A test run is finished with an error.

FINAL_TEST_RUN_STATES = {
    TestRunState.COMPLETED,
    TestRunState.CANCELED,
    TestRunState.ERROR
}


class TestContextObj(ndb.Model):
  """A test context object.

  The "Obj" suffix was added to avoid name collision with TFC TestContext.

  Attributes:
    command_line: a command line.
    env_vars: environment variables.
    test_resources: a list of TestResourceObj objects.
  """
  command_line = ndb.TextProperty()
  env_vars = ndb.LocalStructuredProperty(NameValuePair, repeated=True)
  test_resources = ndb.LocalStructuredProperty(TestResourceObj, repeated=True)


def ToTimestamp(dt):
  return int((dt - datetime.datetime(1970, 1, 1)).total_seconds())


class TestPackageInfo(ndb.Model):
  """A test package info.

  Attributes
    build_number: test package build number.
    target_architecture: test package arch.
    name: A short name of test package.
    full_name: A full name of test package.
    version: test package version
  """
  build_number = ndb.StringProperty()
  target_architecture = ndb.StringProperty()
  name = ndb.StringProperty()
  fullname = ndb.StringProperty()
  version = ndb.StringProperty()


class TestDeviceInfo(ndb.Model):
  """A test package info.

  Attributes
    device_serial: Serial identifying the device. It should be unique.
    hostname: The name of the host this device is connected to.
    run_target: Run target for the device.
    build_id: Current build ID in the device.
    product: Device product (Eg.: flounder).
    sdk_version: SDK version of the device's build.
  """
  device_serial = ndb.StringProperty()
  hostname = ndb.StringProperty()
  run_target = ndb.StringProperty()
  build_id = ndb.StringProperty()
  product = ndb.StringProperty()
  sdk_version = ndb.StringProperty()


class TestRun(ndb.Model):
  """A test run.

  Attributes:
    prev_test_run_key: previous (parent) test run key.
    user: a user who scheduled a test run.
    labels: list of strings users can use to categorize test runs.
    test_plan_key: a test plan key.
    test: a Test object copy made at the test run schedule time.
    test_run_config: a TestRunConfig object.
    test_resources: a list of TestResourceObj objects.
    state: a test run state.
    is_finalized: True if post-run handlers were executed.
    output_path: a path to store test outputs to.
    output_url: a test output URL.
    prev_test_context: a previous test context object.
    next_test_context: a test context object from this test run.
    test_package_info: a test package information
    test_devices: a list of TestDeviceInfo of DUTs
    request_id: a TFC request ID.
    sequence_id: a TestRunSequence ID.
    total_test_count: the number of total test cases.
    failed_test_count: the number of failed test cases.
    failed_test_run_count: the number of test modules that failed to execute.
    create_time: time a test run is created.
    update_time: time a test run is last updated.
    request_event_time: last received TFC request event time.
    attempt_event_time: last received TFC attempt event time.
    before_device_actions: device actions used during the run.
    test_run_actions: test run actions executed during the run.
    hook_data: additional data used by hooks
    cancel_reason: cancellation reason
    error_reason: error reason
  """
  prev_test_run_key = ndb.KeyProperty(kind='TestRun')
  user = ndb.StringProperty()
  labels = ndb.StringProperty(repeated=True)
  test_plan_key = ndb.KeyProperty(TestPlan)
  test = ndb.LocalStructuredProperty(Test)
  test_run_config = ndb.LocalStructuredProperty(TestRunConfig)
  test_resources = ndb.StructuredProperty(TestResourceObj, repeated=True)
  state = ndb.EnumProperty(TestRunState, default=TestRunState.UNKNOWN)
  is_finalized = ndb.BooleanProperty()
  output_path = ndb.StringProperty()
  output_url = ndb.StringProperty()
  prev_test_context = ndb.LocalStructuredProperty(TestContextObj)
  next_test_context = ndb.LocalStructuredProperty(TestContextObj)
  test_package_info = ndb.StructuredProperty(TestPackageInfo)
  test_devices = ndb.StructuredProperty(TestDeviceInfo, repeated=True)
  request_id = ndb.StringProperty()
  sequence_id = ndb.StringProperty()
  total_test_count = ndb.IntegerProperty()
  failed_test_count = ndb.IntegerProperty()
  failed_test_run_count = ndb.IntegerProperty()

  create_time = ndb.DateTimeProperty(auto_now_add=True)
  update_time = ndb.DateTimeProperty(auto_now_add=True)
  request_event_time = ndb.DateTimeProperty()
  attempt_event_time = ndb.DateTimeProperty()

  # Snapshot of the actions executed by the run
  before_device_actions = ndb.LocalStructuredProperty(
      DeviceAction, repeated=True)
  test_run_actions = ndb.LocalStructuredProperty(TestRunAction, repeated=True)
  hook_data = ndb.JsonProperty(default={})

  cancel_reason = ndb.EnumProperty(common.CancelReason)
  error_reason = ndb.TextProperty()

  @classmethod
  def get_by_id(cls, id_, **kwargs):
    try:
      # support numeric (legacy) and uuid identifiers
      id_ = int(id_)
    except ValueError:
      pass
    return TestRun._get_by_id(id_, **kwargs)

  def _post_put_hook(self, future):
    self.ToSummary().put()

  @classmethod
  def _post_delete_hook(cls, key, future):
    ndb.delete_multi(ndb.Query(ancestor=key).iter(keys_only=True))

  def ToSummary(self):
    return TestRunSummary(
        parent=self.key,
        id=self.key.id(),
        prev_test_run_key=self.prev_test_run_key,
        labels=self.labels,
        test_name=self.test.name if self.test else None,
        device_specs=(
            self.test_run_config.device_specs if self.test_run_config else []),
        run_target=(
            self.test_run_config.run_target if self.test_run_config else None),
        state=self.state,
        test_package_info=self.test_package_info,
        test_devices=self.test_devices,
        total_test_count=self.total_test_count,
        failed_test_count=self.failed_test_count,
        failed_test_run_count=self.failed_test_run_count,
        create_time=self.create_time,
        update_time=self.update_time)

  def IsFinal(self):
    """Returns whether a test run is in a final state.

    Returns:
      True if a test run is in a final state. Otherwise false.
    """
    return self.state in FINAL_TEST_RUN_STATES

  def IsRerun(self):
    """Checks whether this is a rerun of another test run."""
    return self.prev_test_context is not None

  def IsLocalRerun(self):
    """Checks whether this is a rerun using a local test run ID."""
    return self.prev_test_run_key is not None

  def IsRemoteRerun(self):
    """Checks whether this is a rerun using an uploaded context file."""
    return self.IsRerun() and not self.IsLocalRerun()

  def GetRerunContextFile(self):
    """Fetches the rerun context file if it exists."""
    if not self.prev_test_context or not self.prev_test_context.test_resources:
      return None
    return self.prev_test_context.test_resources[0]

  def GetContext(self):
    """Returns a test run context dictionary."""
    ctx = {
        'MTT_USER': env.USER,
        'MTT_HOSTNAME': env.HOSTNAME,
        'MTT_VERSION': env.VERSION,
        'MTT_TEST_RUN_ID': self.key.id(),
        'MTT_TEST_ID': self.test_run_config.test_key.id(),
        'MTT_TEST_NAME': self.test.name,
        'MTT_TEST_PLAN_NAME': (
            self.test_plan_key.get().name if self.test_plan_key else ''),
        'MTT_TEST_RUN_CREATE_TIMESTAMP': ToTimestamp(self.create_time),
        'MTT_TEST_RUN_CREATE_TIMESTAMP_MILLIS':
            ToTimestamp(self.create_time) * 1000,
    }

    test_resource_map = {}
    for r in self.test_resources:
      m = re.match(r'mtt:///android_ci/(\S+)/(\S+)/(\S+)/.*', r.url)
      if m:
        test_resource_map[r.test_resource_type] = [
            r.url, m.group(1), m.group(2), m.group(3)
        ]
      else:
        test_resource_map[r.test_resource_type] = [r.url, None, None, None]
    for t in TestResourceType:
      if t == TestResourceType.UNKNOWN:
        continue
      url, branch, target, build_id = test_resource_map.get(
          t, [None, None, None, None])
      ctx['MTT_%s_URL' % t.name] = url or ''
      ctx['MTT_%s_BRANCH' % t.name] = branch or ''
      ctx['MTT_%s_BUILD_ID' % t.name] = build_id or ''
      ctx['MTT_%s_TARGET' % t.name] = target or ''
    return ctx

  def GetErrorInfo(self) -> Optional[str]:
    """Returns additional information if run was cancelled or errored out."""
    if self.state == TestRunState.ERROR:
      return self.error_reason
    if self.state == TestRunState.CANCELED:
      return _TEST_RUN_CANCEL_REASON_MAP.get(self.cancel_reason)


class TestRunSummary(ndb.Model):
  """Partial test run information.

  Attributes:
    prev_test_run_key: ID of the previous (parent) test run.
    labels: list of strings users can use to categorize test runs.
    test_name: name of the Test to run.
    device_specs: device specs.
    run_target: run target.
    state: a test run state.
    test_package_info: a test package information
    test_devices: a list of TestDeviceInfo of DUTs
    total_test_count: the number of total test cases.
    failed_test_count: the number of failed test cases.
    failed_test_run_count: the number of test modules that failed to execute.
    create_time: time a test run is created.
    update_time: time a test run is last updated.
  """
  prev_test_run_key = ndb.KeyProperty(kind='TestRun')
  labels = ndb.StringProperty(repeated=True)
  test_name = ndb.StringProperty()
  device_specs = ndb.StringProperty(repeated=True)
  run_target = ndb.StringProperty()
  state = ndb.EnumProperty(TestRunState, default=TestRunState.UNKNOWN)
  test_package_info = ndb.StructuredProperty(TestPackageInfo)
  test_devices = ndb.StructuredProperty(TestDeviceInfo, repeated=True)
  total_test_count = ndb.IntegerProperty()
  failed_test_count = ndb.IntegerProperty()
  failed_test_run_count = ndb.IntegerProperty()
  create_time = ndb.DateTimeProperty()
  update_time = ndb.DateTimeProperty()


class NodeConfig(ndb.Model):
  """A MTT node configuration.

  Attributes:
    env_vars: default environment vars.
    test_resource_default_download_urls: default download URLs for test
        resources.
  """
  env_vars = ndb.LocalStructuredProperty(NameValuePair, repeated=True)
  test_resource_default_download_urls = ndb.LocalStructuredProperty(
      NameValuePair, repeated=True)


def GetNodeConfig():
  """Returns a node config object.

  Returns:
    a NodeConfig object.
  """
  obj = ndb.Key(NodeConfig, NODE_CONFIG_ID).get()
  if not obj:
    obj = NodeConfig(id=NODE_CONFIG_ID)
    obj.put()
  return obj


class PrivateNodeConfig(ndb.Model):
  """Non-shareable node configs.

  Attributes:
    ndb_version: Latest version the database has been updated to
    default_credentials: default service account credentials
    metrics_enabled: True to collect usage metrics.
    gms_client_id: Optional user-provided label to identify their company
    setup_wizard_completed: If false, trigger the setup wizard on startup
    server_uuid: node's unique identifier.
  """
  ndb_version = ndb.IntegerProperty()
  default_credentials = oauth2_util.CredentialsProperty()
  metrics_enabled = ndb.BooleanProperty()
  gms_client_id = ndb.StringProperty()
  setup_wizard_completed = ndb.BooleanProperty()
  server_uuid = ndb.StringProperty(required=True, default=str(uuid.uuid4()))


def GetPrivateNodeConfig():
  """Returns a private node config object.

  Returns:
    a PrivateNodeConfig object.
  """
  obj = PrivateNodeConfig.query().get()
  if obj is None:
    obj = PrivateNodeConfig()
    obj.put()
  return obj


class TestResourceTracker(ndb.Model):
  """Test resource download tracker.

  Serves as a lock to determine the thread that should perform the download, and
  holds the download metadata.

  Attributes
    update_time: Latest update timestamp.
    download_progress: Download progress (between 0 and 1).
    completed: True if download is finished.
    error: Optional error encountered during download.
  """
  _use_cache = False
  _use_memcache = False
  update_time = ndb.DateTimeProperty(auto_now=True)
  download_progress = ndb.FloatProperty(required=True, default=0.0)
  completed = ndb.BooleanProperty()
  error = ndb.StringProperty()


def IsLocalId(model_id):
  """Returns true if the given id is a local id, false otherwise."""
  try:
    int(model_id)
  except ValueError:
    return False
  return True


class FileCleanerOperationType(messages.Enum):
  ARCHIVE = 0
  DELETE = 1


class FileCleanerCriterionType(messages.Enum):
  LAST_ACCESS_TIME = 0
  LAST_MODIFIED_TIME = 1
  NAME_MATCH = 2
  SYSTEM_AVAILABLE_SPACE = 3


class FileCleanerTargetType(messages.Enum):
  FILE = 0
  DIRECTORY = 1


class FileCleanerOperation(ndb.Model):
  """File cleaner operation.

  Attributes:
    type: operation type.
    params: operation parameters.
  """
  type = ndb.EnumProperty(FileCleanerOperationType, required=True)
  params = ndb.LocalStructuredProperty(NameValuePair, repeated=True)


class FileCleanerCriterion(ndb.Model):
  """File cleaner criterion.

  Attributes:
    type: criterion type.
    params: criterion parameters.
  """
  type = ndb.EnumProperty(FileCleanerCriterionType, required=True)
  params = ndb.LocalStructuredProperty(NameValuePair, repeated=True)


class FileCleanerPolicy(ndb.Model):
  """File cleaner policy, which combines one operation and several criteria.

  Attributes:
    name: policy name, should be unique.
    target: policy target.
    operation: the operation to apply to targets.
    criteria: a list of criteria to select targets.
  """
  name = ndb.StringProperty(required=True)
  target = ndb.EnumProperty(FileCleanerTargetType)
  operation = ndb.LocalStructuredProperty(FileCleanerOperation, required=True)
  criteria = ndb.LocalStructuredProperty(FileCleanerCriterion, repeated=True)


class FileCleanerConfig(ndb.Model):
  """File cleaner config.

  Attributes:
    name: config name.
    description: describes the config.
    directories: directories to apply the policies to.
    policy_names: name of policies to be used.
  """
  name = ndb.StringProperty(required=True)
  description = ndb.StringProperty()
  directories = ndb.StringProperty(repeated=True)
  policy_names = ndb.StringProperty(repeated=True)


class FileCleanerSettings(ndb.Model):
  """File cleaner settings, with combines policies and configs.

  Attributes:
    policies: file cleaner policies.
    configs: file cleaner configs.
  """
  policies = ndb.LocalStructuredProperty(FileCleanerPolicy, repeated=True)
  configs = ndb.LocalStructuredProperty(FileCleanerConfig, repeated=True)


DEFAULT_FILE_CLEANER_SETTINGS = FileCleanerSettings(
    policies=[
        FileCleanerPolicy(
            name='Archive directories not modified',
            target=FileCleanerTargetType.DIRECTORY,
            operation=FileCleanerOperation(
                type=FileCleanerOperationType.ARCHIVE),
            criteria=[
                FileCleanerCriterion(
                    type=FileCleanerCriterionType.LAST_MODIFIED_TIME,
                    params=[NameValuePair(name='ttl', value='7 days')])
            ]),
        FileCleanerPolicy(
            name='Delete directories not modified and accessed',
            target=FileCleanerTargetType.DIRECTORY,
            operation=FileCleanerOperation(
                type=FileCleanerOperationType.DELETE),
            criteria=[
                FileCleanerCriterion(
                    type=FileCleanerCriterionType.LAST_MODIFIED_TIME,
                    params=[NameValuePair(name='ttl', value='7 days')]),
                FileCleanerCriterion(
                    type=FileCleanerCriterionType.LAST_ACCESS_TIME,
                    params=[NameValuePair(name='ttl', value='7 days')])
            ])
    ],
    configs=[
        FileCleanerConfig(
            name='Clean up test results',
            description='Clean up test results',
            directories=[
                '{}/{}/test_runs'.format(env.STORAGE_PATH, env.GCS_BUCKET_NAME)
            ],
            policy_names=['Archive directories not modified']),
        FileCleanerConfig(
            name='Clean up test work files',
            description='Clean up test work files',
            directories=['{}/tmp'.format(env.STORAGE_PATH)],
            policy_names=['Delete directories not modified and accessed'])
    ])


def GetFileCleanerSettings():
  """Returns a file cleaner settings object.

  Returns:
    a FileCleanerSettings object.
  """
  obj = ndb.Key(FileCleanerSettings, FILE_CLEANER_SETTINGS_ID).get()
  return obj or DEFAULT_FILE_CLEANER_SETTINGS


class ReportType(messages.Enum):
  """Type of a report."""

  REPORT_TYPE_UNKNOWN = 0  # Unknown test report.
  CTS = 1  # Android Compatibility Test Suite.
  CTS_VERIFIER = 2  # Android Compatibility Test Suite Verifier.
  GTS = 3  # GMS Core Test Suite.
  CAT = 4  # CTS Auto Test Suite.
  WTS = 5  # Wearable Test Suite.
  WTS_VERIFIER = 6  # Wearable Test Suite Verifier.
  TVTS = 7  # TV Test Suite.
  CRT = 8  # Cast Ready Test.
  PCTS = 9  # Automotive Projected Test Suite.
  VTS = 10  # Vendor Test Suite (Treble).
  ATS = 11  # Automotive Test Suite.
  ATS_VERIFIER = 12  # Automotive Test Suite Verifier.
  GOATS = 13  # Android Go Test Suite.
  STS = 14  # Security Test Suite.
  CTS_INSTANT = 15  # Instant App mode of CTS.
  BTS_V2 = 17  # Athena Report (BTS v2).
  ENTS = 18  # Exposure Notification Test Suite.
  CTS_ON_GSI = 19  # Compatibility Test Suite on GSI (go/android-gsi).
  CATBOX = 20  # CATBox Test Suite.
  APTS = 21  # Android Performance Test Suite.
  DTS = 22  # Driveable Test Suite.
  GTS_VERIFIER = 23  # GMS Core Manual Test Suite.
  WTS_CHECKLIST = 25  # Wear Test Suite Checklist.
  GCATBOX = 26  # GAS CATBox Test Suite.
  WPTS = 27  # Wear Performance Test Suite.


class XtsRequirementsDetectionStatus(messages.Enum):
  NOT_STARTED = 0  # Xts requirements detection is not yet started.
  SIGNALS_COLLECTING = 1  # A task is collecting build integrity signals.
  ANALYSIS_RUNNING = 2  # A build analysis on APA side is running.
  COMPLETED = 3  # Xts requirements detection is completed.
  CANCELED = 4  # Xts requirements detection is canceled.
  ERROR = 5  # Xts requirements detection is aborted with an error.


class Build(ndb.Model):
  """A build.

  Attributes:
    name: a build name
    file_url: file URL of a build.
    size: size of a build.
    labels: list of strings users can use to categorize builds.
    create_time: time a build is created.
    update_time: time a build is last updated.
    detection_status: status of xts requirements detection for a build.
    detection_test_run_key: test run key of xts requirements detection for a
      build.
  """
  name = ndb.StringProperty()
  file_url = ndb.StringProperty()
  size = ndb.IntegerProperty()
  labels = ndb.StringProperty(repeated=True)
  create_time = ndb.DateTimeProperty(auto_now_add=True)
  update_time = ndb.DateTimeProperty(auto_now=True)
  detection_status = ndb.EnumProperty(
      XtsRequirementsDetectionStatus,
      default=XtsRequirementsDetectionStatus.NOT_STARTED,
  )
  detection_test_run_key = ndb.KeyProperty(TestRun)

  @classmethod
  def _post_delete_hook(cls, key, future):
    keys_to_delete = RequiredReport.query(
        RequiredReport.build_key == key
    ).fetch(keys_only=True)
    ndb.delete_multi(keys_to_delete)


class RequiredReport(ndb.Model):
  """A required report for a build.

  Attributes:
    build_key: the build key.
    type: the type of a report.
    test_plans: the qualified test plans of a report.
    available: whether the report is available on APFE.
    test_run_key: the test run key a required report is associated with.
  """

  build_key = ndb.KeyProperty(Build, required=True)
  type = ndb.EnumProperty(ReportType, required=True)
  test_plans = ndb.StringProperty(repeated=True)
  available = ndb.BooleanProperty()
  test_run_key = ndb.KeyProperty(TestRun)
