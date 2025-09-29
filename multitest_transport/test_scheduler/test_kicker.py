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

"""A test kicker module."""
import collections
import json
import logging
import os
import re
import string
import uuid

import flask
from googleapiclient.errors import HttpError
from protorpc import messages
from tradefed_cluster import api_messages
from tradefed_cluster import common
from tradefed_cluster.services import task_scheduler
from tradefed_cluster.util import ndb_shim as ndb


from multitest_transport.models import build
from multitest_transport.models import event_log
from multitest_transport.models import ndb_models
from multitest_transport.models import test_run_hook
from multitest_transport.test_scheduler import download_util
from multitest_transport.test_scheduler import test_run_manager
from multitest_transport.test_scheduler import sharding_strategies
from multitest_transport.util import analytics
from multitest_transport.util import env
from multitest_transport.util import errors
from multitest_transport.util import file_util
from multitest_transport.util import tfc_client

TEST_KICKER_QUEUE = 'test-kicker-queue'
TEST_RUN_OUTPUT_PATH_FORMAT = '/%s/test_runs/%%s/output/' % env.GCS_BUCKET_NAME
MAX_RETRY_COUNT = 7
METADATA_FILE = 'mtt.json'
METADATA_API_FORMAT = 'http://%s/_ah/api/mtt/v1/test_runs/%s/metadata'
EXTRA_COMMAND_ARGS = ['--invocation-data', 'mtt=1']
DEFAULT_TF_CONFIG_OBJECTS = [
    # Turns a screen off after an invocation.
    api_messages.TradefedConfigObject(
        type=api_messages.TradefedConfigObjectType.TARGET_PREPARER,
        class_name='com.android.tradefed.targetprep.DeviceCleaner',
        option_values=[
            api_messages.KeyMultiValuePair(
                key='post-cleanup', values=['SCREEN_OFF']
            )
        ],
    )
]
DYNAMIC_DOWNLOAD_MCTS_TF_CONFIG = [
    # Dynamic Download MCTS based on the device preloaded Mainline Modules.
    api_messages.TradefedConfigObject(
        type=api_messages.TradefedConfigObjectType.TARGET_PREPARER,
        class_name=(
            'com.android.tradefed.targetprep.RunHostCommandTargetPreparer'
        ),
        option_values=[
            api_messages.KeyMultiValuePair(
                key='host-cmd-timeout', values=['90m']
            ),
            api_messages.KeyMultiValuePair(
                key='host-setup-command',
                values=[
                    'chmod u+x ./MctsDynamicDownloadPlugin_deploy.jar',
                    'chmod u+x ./dynamic_download.sh',
                    (
                        './dynamic_download.sh $SERIAL ${TF_WORK_DIR}'
                        ' ${MTT_STORAGE_PATH}'
                    ),
                ],
            ),
            api_messages.KeyMultiValuePair(
                key='work-dir', values=['${TF_WORK_DIR}']
            ),
        ],
    )
]
TF_DEVICE_COUNT_ENV_VAR = '${TF_DEVICE_COUNT}'
# This is the list of the tradefed options that are allowed to be specified in
# multiple device actions. The options in the list should be repeatable and
# unordered. The other options are disallowed because it is difficult to predict
# the effect of the concatenated options.
REPEATABLE_TF_OPTIONS = ('gce-driver-file-param',)
MAX_COMMANDS = 500
TRADEFED_OPTIONS_CLASS_NAME = 'tradefed_options'

APP = flask.Flask(__name__)


class TestKickerError(errors.BaseError):
  """A base error for test kick errors."""
  pass


def ValidateDeviceActions(device_actions):
  """Validate a list of device actions for a test run.

  Args:
    device_actions: a list of ndb_models.DeviceAction objects.

  Raises:
    ValueError: if any two device actions contain different device specs or
      identical TradeFed option names.
  """
  action_with_device_spec = None
  options = dict()
  for index, action in enumerate(device_actions):
    if action.device_spec:
      if not action_with_device_spec:
        action_with_device_spec = action
      elif action_with_device_spec.device_spec != action.device_spec:
        raise ValueError(
            'The selected device actions contain different device specs. '
            'Please remove one of %s and %s.' %
            (action_with_device_spec.name, action.name))

    for opt in action.tradefed_options:
      if (opt.name not in REPEATABLE_TF_OPTIONS and
          options.setdefault(opt.name, index) != index):
        raise ValueError(
            'The selected device actions contain identical TradeFed option %s. '
            'Please remove one of %s and %s.' %
            (opt.name, device_actions[options[opt.name]].name, action.name))


def _ConvertToTestResourceMap(test_resource_defs):
  """Convert TestResourceDef objects to a dict of TestResourceObj objects.

  Args:
    test_resource_defs: a collection of ndb_models.TestResourceDef objects.

  Returns:
    a dict that maps names to ndb_models.TestResourceObj objects.

  Raises:
    ValueError: if any two test resources have identical name but different
      attributes.
  """
  test_resource_map = {}
  for d in test_resource_defs:
    obj = d.ToTestResourceObj()
    if not obj.params:
      obj.params = ndb_models.TestResourceParameters()
    obj.params.decompress_files = [f for f in obj.params.decompress_files if f]

    existing_obj = test_resource_map.get(obj.name)
    if not existing_obj:
      test_resource_map[obj.name] = obj
      continue
    if (existing_obj.decompress != obj.decompress or
        existing_obj.decompress_dir != obj.decompress_dir or
        existing_obj.test_resource_type != obj.test_resource_type):
      raise ValueError('The test run has multiple test resources named %s and '
                       'having different attributes.' % obj.name)
    if obj.decompress:
      # Union decompress_files. An empty list means to decompress all files.
      if existing_obj.params.decompress_files and obj.params.decompress_files:
        existing_obj.params.decompress_files.extend(
            obj.params.decompress_files)
      else:
        existing_obj.params.decompress_files.clear()

  for obj in test_resource_map.values():
    obj.params.decompress_files = sorted(set(obj.params.decompress_files))
  return test_resource_map


def CreateTestRun(labels,
                  test_run_config,
                  test_plan_key=None,
                  rerun_context=None,
                  rerun_configs=None,
                  sequence_id=None):
  """Creates a test run.

  Args:
    labels: labels for the test run
    test_run_config: a ndb_models.TestRunConfig object.
    test_plan_key: a ndb_models.TestPlan key.
    rerun_context: rerun parameters containing parent ID or context filename.
    rerun_configs: a list of configs to use for reruns
    sequence_id: id of the sequence the run should belong to
  Returns:
    a ndb_models.TestRun object.
  Raises:
    ValueError: some of given parameters are invalid.
    errors.TestResourceError: if some of test resources don't have URLs.
  """
  # Set defaults for null test_run_config fields for backward compatibility.
  if test_run_config.use_parallel_setup is None:
    test_run_config.use_parallel_setup = True
  if test_run_config.allow_partial_device_match is None:
    test_run_config.allow_partial_device_match = False

  test = test_run_config.test_key.get()
  if not test:
    raise ValueError('cannot find test %s' % test_run_config.test_key)

  if (not env.IS_OMNILAB_BASED
      and test_run_config.sharding_mode == ndb_models.ShardingMode.MODULE):
    if (not test.module_config_pattern or not test.module_execution_args):
      raise ValueError(
          'test "%s" does not support module sharding: '
          'module_config_pattern or module_exeuction_args not defined' % (
              test.name))
    test_package_urls = [
        r.cache_url
        for r in test_run_config.test_resource_objs
        if r.test_resource_type == ndb_models.TestResourceType.TEST_PACKAGE]
    if not test_package_urls:
      raise ValueError(
          'cannot use module sharding: '
          'no test package is found in test resources')

  node_config = ndb_models.GetNodeConfig()
  test.env_vars.extend(node_config.env_vars)

  # Store snapshot of test run's actions
  before_device_actions = ndb.get_multi(
      test_run_config.before_device_action_keys)

  if not all(before_device_actions):
    raise ValueError(
        'Cannot find some device actions: %s -> %s' % (
            test_run_config.before_device_action_keys, before_device_actions))
  ValidateDeviceActions(before_device_actions)

  test_run_actions = [
      ref.ToAction() for ref in test_run_config.test_run_action_refs
  ]

  test_resource_defs = test.test_resource_defs[:]
  for device_action in before_device_actions:
    test_resource_defs += device_action.test_resource_defs
  test_resource_map = _ConvertToTestResourceMap(test_resource_defs)
  # Override test resource URLs based on
  # node_config.test_resource_default_download_urls.
  for pair in node_config.test_resource_default_download_urls:
    if pair.name not in test_resource_map:
      continue
    test_resource_map[pair.name].url = pair.value
  test_resources = build.FindTestResources(test_run_config.test_resource_objs)
  for r in test_resources:
    if r.name not in test_resource_map:
      logging.warning(
          'Test resource %s is not needed for this test run; ignoring', r)
      continue
    test_resource_map[r.name].url = r.url
    test_resource_map[r.name].cache_url = r.cache_url
  # Check every test resource has a valid URL.
  for test_resource in test_resource_map.values():
    if not test_resource.url:
      raise errors.TestResourceError(
          'No URL for test resource %s' % test_resource.name)

  # Determine previous test context from previous test run
  prev_test_run_key, prev_test_context = _GetRerunInfo(test, rerun_context)

  if rerun_configs:
    if sequence_id:
      raise ValueError(
          'Cannot create test run with both sequence id %s and rerun configs %s'
          % (sequence_id, rerun_configs))
    rerun_configs.insert(0, test_run_config)
    sequence_id = str(uuid.uuid4())
    test_run_sequence = ndb_models.TestRunSequence(
        state=ndb_models.TestRunSequenceState.RUNNING,
        test_run_configs=rerun_configs,
        finished_test_run_ids=[])
    test_run_sequence.key = ndb.Key(ndb_models.TestRunSequence, sequence_id)
    test_run_sequence.put()

  # Create and enqueue test run
  test_run = ndb_models.TestRun(
      id=str(uuid.uuid4()),
      prev_test_run_key=prev_test_run_key,
      labels=labels,
      test_plan_key=test_plan_key,
      test=test,
      test_run_config=test_run_config,
      test_resources=list(test_resource_map.values()),
      prev_test_context=prev_test_context,
      state=ndb_models.TestRunState.PENDING,
      before_device_actions=before_device_actions,
      test_run_actions=test_run_actions,
      sequence_id=sequence_id)
  test_run.put()
  test_run_id = test_run.key.id()
  logging.info('Test run %s created', test_run_id)
  event_log.Info(test_run, 'Test run created')
  EnqueueTestRun(test_run_id)
  return test_run


def _GetRerunInfo(test, rerun_context):
  """Determine parent run key and test context for reruns.

  Args:
    test: ndb_models.Test that will be executed.
    rerun_context: rerun parameters containing parent ID or context filename.
  Returns:
    previous test run key and previous test context to use during rerun
  """
  if rerun_context and rerun_context.test_run_id:
    # local rerun - fetch key and test context from DB
    logging.info('Rerunning local test run %s', rerun_context.test_run_id)
    prev_test_run_key = ndb.Key(ndb_models.TestRun, rerun_context.test_run_id)
    # disable cache to ensure we get the updated test context
    prev_test_run = prev_test_run_key.get(use_cache=False, use_memcache=False)
    if not prev_test_run:
      raise ValueError(
          'Previous test run %s not found' % prev_test_run_key.id())
    return prev_test_run_key, prev_test_run.next_test_context

  if (rerun_context and rerun_context.context_filename
      and rerun_context.context_file_url):
    # remote rerun - construct test context from locally uploaded file
    logging.info('Rerunning test run from %s', rerun_context.context_filename)
    resource_name = rerun_context.context_filename
    if test.context_file_dir:
      resource_name = os.path.join(test.context_file_dir, resource_name)
    remote_test_context = ndb_models.TestContextObj(test_resources=[
        ndb_models.TestResourceObj(
            name=resource_name,
            url=rerun_context.context_file_url)
    ])
    return None, remote_test_context

  # no rerun information
  return None, None


def EnqueueTestRun(test_run_id):
  """Push the exist test run to the task queue.

  Args:
    test_run_id: a test run ID.
  """
  task_name = str(test_run_id)
  payload = json.dumps({
      'test_run_id': test_run_id
  })
  task_scheduler.AddTask(
      queue_name=TEST_KICKER_QUEUE,
      name=task_name,
      payload=payload,
      target='default')


def KickTestRun(test_run_id):
  """Kick off a test run.

  Args:
    test_run_id: a test run ID.
  """
  test_run = ndb_models.TestRun.get_by_id(test_run_id)
  if test_run.state == ndb_models.TestRunState.PENDING:
    _PrepareTestResources(test_run_id)
    test_run_hook.ExecuteHooks(test_run_id, ndb_models.TestRunPhase.BEFORE_RUN)
    _CreateTFCRequest(test_run_id)
  elif test_run.state in [
      ndb_models.TestRunState.QUEUED,
      ndb_models.TestRunState.RUNNING,
  ]:
    logging.info('Resume test run %s at state %s.', test_run_id, test_run.state)
    tfc_client.ResumeRequest(test_run.request_id)
  elif test_run.state == ndb_models.TestRunState.CANCELED:
    logging.info('Test run %s is CANCELED. Do nothing.', test_run_id)


def _PrepareTestResources(test_run_id):
  """Prepare test resources.

  Args:
    test_run_id: a test run ID.
  """
  test_run = ndb_models.TestRun.get_by_id(test_run_id)
  if test_run.state != ndb_models.TestRunState.PENDING:
    logging.info(
        'Test run %s is %s; aborting _PrepareTestResources()',
        test_run_id,
        test_run.state,
    )
    return

  logging.info(
      'Preparing test resources for test run %s: test_resources=%s',
      test_run_id,
      test_run.test_resources,
  )
  resource_urls = [r.url for r in test_run.test_resources]
  # Download all resources in parallel. If the resource is already downloaded
  # and still up-to-date, this will simply return its cache URL.
  cache_urls = download_util.DownloadResources(resource_urls, test_run=test_run)
  # Update all the test resource URLs and the test package information
  test_package_info = None
  for r in test_run.test_resources:
    if r.test_resource_type == ndb_models.TestResourceType.TEST_PACKAGE:
      test_package_info = _GetTestPackageInfo(cache_urls[r.url])
      break
  _UpdateTestResources(test_run_id, cache_urls, test_package_info)
  logging.info('Done preparing test resources for test run %s', test_run_id)


def _GetTestPackageInfo(cache_url):
  """Retrieve the test package information at a specified resource URL."""
  stream = file_util.OpenFile(cache_url)
  test_suite_info = file_util.GetTestSuiteInfo(stream)
  if test_suite_info:
    return ndb_models.TestPackageInfo(
        build_number=test_suite_info.build_number,
        target_architecture=test_suite_info.target_architecture,
        name=test_suite_info.name,
        fullname=test_suite_info.fullname,
        version=test_suite_info.version,
    )


@ndb.transactional()
def _UpdateTestResources(test_run_id, cache_urls, test_package_info):
  """Update test resource cache URLs and test package info."""
  test_run = ndb_models.TestRun.get_by_id(test_run_id)
  if not test_run or test_run.state != ndb_models.TestRunState.PENDING:
    return
  for r in test_run.test_resources:
    r.cache_url = cache_urls[r.url]
  if test_package_info:
    test_run.test_package_info = test_package_info
  test_run.put()


def _ConvertToTFCTestResource(obj, url, set_original_download_url=False):
  """Convert ndb_models.TestResourceObj to TFC api_messages.TestResource."""
  params = None
  if obj.params:
    params = api_messages.TestResourceParameters(
        decompress_files=obj.params.decompress_files
    )
  return api_messages.TestResource(
      name=obj.name,
      url=file_util.GetWorkerAccessibleUrl(url),
      decompress=obj.decompress,
      decompress_dir=obj.decompress_dir,
      mount_zip=obj.mount_zip,
      params=params,
      original_download_url=obj.url if set_original_download_url else None,
  )


def _CreateTFCRequest(test_run_id):
  """Creates a TFC request.

  Args:
    test_run_id: a test run ID.
  """
  test_run = ndb_models.TestRun.get_by_id(test_run_id, use_cache=False)
  if test_run.state != ndb_models.TestRunState.PENDING:
    logging.info(
        'Test run %s is %s; aborting _CreateTFCRequest()',
        test_run_id,
        test_run.state,
    )
    return

  logging.info(
      'Creating a TFC request: test=%s, test_run_config=%s',
      test_run.test, test_run.test_run_config)
  output_path = TEST_RUN_OUTPUT_PATH_FORMAT % test_run_id
  output_url = file_util.GetAppStorageUrl([output_path])

  # Construct command
  if test_run.test_run_config.command:
    command_line = test_run.test_run_config.command
  else:  # TODO: Deprecate extra_args
    command_line = test_run.test.command
    if test_run.test_run_config.extra_args:
      command_line = ' '.join([command_line,
                               test_run.test_run_config.extra_args])
    logging.warning(
        'Test run %s missing command, using test.command and extra_args: %s',
        test_run_id, command_line)

  # Construct retry command
  if test_run.test_run_config.retry_command:
    retry_command_line = test_run.test_run_config.retry_command
  else:  # TODO: Deprecate extra_args
    retry_command_line = test_run.test.retry_command_line
    if retry_command_line and test_run.test_run_config.retry_extra_args:
      retry_command_line = ' '.join([retry_command_line,
                                     test_run.test_run_config.retry_extra_args])
    logging.warning(
        ('Test run %s missing retry command, using test.retry_command and '
         'retry_extra_args: %s'),
        test_run_id, retry_command_line)

  # Buid command infos
  command_infos = []
  max_concurrent_tasks = None
  enable_xts_dynamic_download = (
      test_run.test_run_config.enable_xts_dynamic_download
  )
  sharding_mode = ndb_models.ShardingMode(
      test_run.test_run_config.sharding_mode or ndb_models.ShardingMode.RUNNER)
  if sharding_mode == ndb_models.ShardingMode.RUNNER:
    test_bench = _DeviceSpecsToTFCTestBench(
        test_run.test_run_config.cluster, test_run.test_run_config.device_specs)
    if (test_run.test_run_config.shard_count > 1 and
        test_run.test.runner_sharding_args):
      tmpl = string.Template(test_run.test.runner_sharding_args)
      # Whether to use ATS 1.0's TFC dynamic sharding. ATS 2.0 uses Omnilab
      # scheduler and don't need to replace shard count with environment
      # variable.
      use_tfc_dynamic_sharding = (
          test_run.test_run_config.allow_partial_device_match and
          not env.IS_OMNILAB_BASED)
      if use_tfc_dynamic_sharding:
        logging.warning(
            'Allow partial device matching require shard_count to be dynamic; '
            'ignoring shard count')
      shard_count = (
          TF_DEVICE_COUNT_ENV_VAR if use_tfc_dynamic_sharding
          else str(test_run.test_run_config.shard_count))
      sharding_args = tmpl.safe_substitute(
          {'TF_SHARD_COUNT': shard_count})
      command_line = ' '.join([command_line, sharding_args])
      if retry_command_line:
        retry_command_line = ' '.join([retry_command_line, sharding_args])
    command_infos.append(
        api_messages.CommandInfo(
            command_line=command_line,
            test_bench=test_bench,
            run_count=test_run.test_run_config.run_count,
            shard_count=1,
            allow_partial_device_match=(
                test_run.test_run_config.allow_partial_device_match
            ),
            sharding_mode=sharding_mode.name,
            enable_xts_dynamic_download=enable_xts_dynamic_download,
        )
    )
  elif env.IS_OMNILAB_BASED and sharding_mode == ndb_models.ShardingMode.MODULE:
    test_bench = _DeviceSpecsToTFCTestBench(
        test_run.test_run_config.cluster, test_run.test_run_config.device_specs)
    command_infos.append(
        api_messages.CommandInfo(
            command_line=command_line,
            test_bench=test_bench,
            run_count=test_run.test_run_config.run_count,
            allow_partial_device_match=True,
            sharding_mode=sharding_mode.name,
            enable_xts_dynamic_download=enable_xts_dynamic_download,
        )
    )
  elif sharding_mode == ndb_models.ShardingMode.MODULE:
    # Each command in MODULE sharding mode should target one device.
    # Combine if there are multiple device specs e.g.
    # ['device_serial:A', 'device_serial:B']
    #     -> ['device_serial:A device_serial:B']
    device_specs = [' '.join(test_run.test_run_config.device_specs)]
    test_bench = _DeviceSpecsToTFCTestBench(
        test_run.test_run_config.cluster, device_specs)
    command_infos = sharding_strategies.ShardModules(
        test_run, command_line, test_bench, MAX_COMMANDS
    )
    max_concurrent_tasks = test_run.test_run_config.shard_count

  # Append extra command args to flag as a MTT run.
  for info in command_infos:
    info.command_line = ' '.join([info.command_line] + EXTRA_COMMAND_ARGS)
  if retry_command_line:
    retry_command_line = ' '.join([retry_command_line] + EXTRA_COMMAND_ARGS)

  tradefed_config_objects = _GetTradefedConfigObjects(test_run)

  prev_test_context = None
  if test_run.prev_test_context:
    prev_test_context = api_messages.TestContext(
        env_vars=[
            api_messages.KeyValuePair(key=p.name, value=p.value)
            for p in test_run.prev_test_context.env_vars
        ],
        test_resources=[
            _ConvertToTFCTestResource(r, r.url)
            for r in test_run.prev_test_context.test_resources
        ])
    # TODO: consider removing command_line from TestContext.
    if not prev_test_context.test_resources:
      prev_test_context.command_line = command_line
    else:
      prev_test_context.command_line = retry_command_line

  test_resources = [
      _ConvertToTFCTestResource(r, r.cache_url, True)
      for r in test_run.test_resources
  ]

  # add metadata URL to the test resources
  hostname = os.environ['DEFAULT_VERSION_HOSTNAME']
  metadata_url = METADATA_API_FORMAT % (hostname, test_run.key.id())
  metadata_url = file_util.GetWorkerAccessibleUrl(metadata_url)

  test_resources.append(
      api_messages.TestResource(name=METADATA_FILE, url=metadata_url))

  logging.info('List all test resources: %s', test_resources)

  # determine context file pattern
  context_file_pattern = test_run.test.context_file_pattern
  if test_run.test.context_file_dir and test_run.test.context_file_pattern:
    context_file_pattern = os.path.join(
        test_run.test.context_file_dir, test_run.test.context_file_pattern)

  # Record metrics
  _TrackTestRun(test_run)

  new_request_msg = api_messages.NewMultiCommandRequestMessage(
      type=api_messages.RequestType.MANAGED,
      user='test_kicker',
      command_infos=command_infos,
      max_retry_on_test_failures=(
          test_run.test_run_config.max_retry_on_test_failures),
      queue_timeout_seconds=test_run.test_run_config.queue_timeout_seconds,
      test_environment=api_messages.TestEnvironment(
          env_vars=[
              api_messages.KeyValuePair(key=p.name, value=p.value)
              for p in test_run.test.env_vars
          ],
          setup_scripts=test_run.test.setup_scripts,
          output_file_upload_url=file_util.GetWorkerAccessibleUrl(output_url),
          output_file_patterns=test_run.test.output_file_patterns,
          use_subprocess_reporting=True,
          invocation_timeout_millis=(
              test_run.test_run_config.invocation_timeout_seconds * 1000),
          output_idle_timeout_millis=(
              test_run.test_run_config.output_idle_timeout_seconds * 1000),
          jvm_options=test_run.test.jvm_options,
          java_properties=[
              api_messages.KeyValuePair(key=p.name, value=p.value)
              for p in test_run.test.java_properties
          ],
          context_file_pattern=context_file_pattern,
          extra_context_files=[METADATA_FILE],  # append metadata to context
          retry_command_line=retry_command_line,
          log_level=common.LogLevel.INFO,
          tradefed_config_objects=tradefed_config_objects,
          use_parallel_setup=test_run.test_run_config.use_parallel_setup,
          build_attributes=[
              api_messages.KeyValuePair(key=p.name, value=p.value)
              for p in test_run.test.build_attributes
          ],
          tradefed_options=_GetTradefedOptions(test_run),
      ),
      test_resources=test_resources,
      prev_test_context=prev_test_context,
      max_concurrent_tasks=max_concurrent_tasks,
      affinity_tag=str(test_run.key.id()))
  logging.debug('new_request_msg=%s', new_request_msg)
  request = tfc_client.NewRequest(new_request_msg)
  logging.info('TFC request %s is created', request.id)
  # Update test run to QUEUED and store TFC request ID.
  def _Txn():
    txn_test_run = ndb_models.TestRun.get_by_id(test_run_id)
    if (
        not txn_test_run
        or txn_test_run.state != ndb_models.TestRunState.PENDING
    ):
      # If the test run is not pending, it means the test run is proceeded to
      # the next step. Cancel the created request as well.
      tfc_client.CancelRequest(request.id)
      return
    txn_test_run.output_path = output_path
    txn_test_run.output_url = output_url
    txn_test_run.request_id = request.id
    txn_test_run.state = ndb_models.TestRunState.QUEUED
    txn_test_run.put()
  ndb.transaction(_Txn)


def _DeviceSpecsToTFCTestBench(
    cluster, device_specs) -> api_messages.TestBenchRequirement:
  """Convert device specs to TFC test bench."""
  run_targets = []
  for spec in device_specs:
    attr_map = collections.defaultdict(list)
    for match in re.finditer(r'([^\s:]+):(\S+)', spec):
      key = match.group(1)
      value = match.group(2)
      attr_map[key].append(value)
    attrs = []
    for name, values in attr_map.items():
      if len(values) == 1:
        attr = api_messages.DeviceAttributeRequirement(
            name=name, value=values[0])
      else:
        attr = api_messages.DeviceAttributeRequirement(
            name=name, value=','.join(values), operator='IN')
      attrs.append(attr)
    run_targets.append(
        api_messages.RunTargetRequirement(name='*', device_attributes=attrs))
  groups = [
      api_messages.GroupRequirement(run_targets=[run_target])
      for run_target in run_targets
  ]
  return api_messages.TestBenchRequirement(
      cluster=cluster, host=api_messages.HostRequirement(groups=groups))


def _GetTradefedOptions(test_run):
  """Return a list of Tradefed options for a test run."""
  tradefed_options = []
  for action in test_run.before_device_actions:
    option_values = [
        api_messages.KeyMultiValuePair(key=o.name, values=o.values)
        for o in action.tradefed_options
    ]
    tradefed_options.extend(option_values)
  return tradefed_options


def _GetTradefedConfigObjects(test_run):
  """Return a list of Tradefed config objects for a test run.

  Args:
    test_run: a ndb_models.TestRun object.
  Returns:
    a list of api_messages.TradefedConfigObjects.
  """
  objs = []
  # Adding default TF config objects.
  objs.extend(DEFAULT_TF_CONFIG_OBJECTS)
  if (
      test_run.test_run_config.enable_xts_dynamic_download
      and not env.IS_OMNILAB_BASED
  ):
    test_run.test_run_config.use_parallel_setup = False
    objs.extend(DYNAMIC_DOWNLOAD_MCTS_TF_CONFIG)
  for action in test_run.before_device_actions:
    for target_preparer in action.tradefed_target_preparers:
      obj = api_messages.TradefedConfigObject(
          type=api_messages.TradefedConfigObjectType.TARGET_PREPARER,
          class_name=target_preparer.class_name,
          option_values=[
              api_messages.KeyMultiValuePair(key=o.name, values=o.values)
              for o in target_preparer.option_values
          ])
      objs.append(obj)
  for action in test_run.test_run_actions:
    for result_reporter in action.tradefed_result_reporters:
      obj = api_messages.TradefedConfigObject(
          type=api_messages.TradefedConfigObjectType.RESULT_REPORTER,
          class_name=result_reporter.class_name,
          option_values=[
              api_messages.KeyMultiValuePair(key=o.name, values=o.values)
              for o in result_reporter.option_values
          ])
      objs.append(obj)

  ctx = test_run.GetContext()
  for obj in objs:
    for pair in obj.option_values:
      pair.values = [
          string.Template(v).safe_substitute(ctx)
          for v in pair.values
      ]
  return objs


def _TrackTestRun(test_run):
  """Generate and send test run analytics information before start."""
  package = test_run.test_package_info
  analytics.Log(
      analytics.TEST_RUN_CATEGORY,
      analytics.START_ACTION,
      test_name=package.name if package else None,
      test_version=package.version if package else None,
      is_rerun=test_run.prev_test_run_key is not None)
  for device_action in test_run.before_device_actions:
    for target_preparer in device_action.tradefed_target_preparers:
      analytics.Log(
          analytics.DEVICE_ACTION_CATEGORY,
          analytics.TARGET_PREPARER_ACTION,
          label=target_preparer.class_name)


@APP.route('/', methods=['POST'])
# This matchs all path start with '/'.
@APP.route('/<path:fake>', methods=['POST'])
def HandleTask(fake=None):
  """Handle tasks from the test kicker queue."""
  del fake
  retry_count = int(
      flask.request.headers.get('X-AppEngine-TaskRetryCount', MAX_RETRY_COUNT))
  payload = json.loads(flask.request.get_data())
  test_run_id = payload['test_run_id']
  try:
    KickTestRun(test_run_id)
  except Exception as e:  
    if isinstance(e, errors.BaseError) and not e.retriable:
      logging.exception('Non retriable error %s, no retry needed', e)
    elif isinstance(e, messages.ValidationError):
      logging.exception('Non retriable error %s, no retry needed', e)
    elif isinstance(e, HttpError) and e.resp.status == 400:
      logging.exception('Non retriable error %s, no retry needed', e)
    elif retry_count < MAX_RETRY_COUNT:
      logging.exception(
          'Fail to kick test run %s, retry_count = %d',
          test_run_id, retry_count + 1)
      raise
    else:
      logging.exception(
          'Fail to kick test run %s after %d retries', test_run_id,
          MAX_RETRY_COUNT)
    test_run_manager.SetTestRunState(
        test_run_id=test_run_id,
        state=ndb_models.TestRunState.ERROR,
        error_reason=str(e))
  return common.HTTP_OK
