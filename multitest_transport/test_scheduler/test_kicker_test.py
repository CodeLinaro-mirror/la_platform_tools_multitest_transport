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

"""Unit tests for test_kicker module."""
import json
import os
from unittest import mock
import uuid

from absl.testing import absltest
from tradefed_cluster import api_messages
from tradefed_cluster import common
from tradefed_cluster import testbed_dependent_test
from tradefed_cluster.util import ndb_shim as ndb
import webtest


from multitest_transport.models import build
from multitest_transport.models import messages
from multitest_transport.models import ndb_models
from multitest_transport.models import test_run_hook
from multitest_transport.test_scheduler import download_util
from multitest_transport.test_scheduler import test_kicker
from multitest_transport.util import analytics
from multitest_transport.util import file_util
from multitest_transport.util import tfc_client
from multitest_transport.util import env

GAE_CONFIGS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), 'gae_configs')


class TestKickerTest(testbed_dependent_test.TestbedDependentTest):

  def _CreateMockTest(self, name='test', command='command'):
    """Create a mock ndb_models.Test object."""
    test = ndb_models.Test(name=name, command=command)
    test.put()
    return test

  def _CreateMockTestRunConfig(self, test, run_target='run_target'):
    """Create a mock ndb_models.TestRunConfig object."""
    return ndb_models.TestRunConfig(
        test_key=test.key,
        run_target=run_target,
        cluster='cluster',
        )

  def _CreateMockTestRun(
      self,
      test_name='test',
      command='command',
      retry_command_line=None,
      runner_sharding_args=None,
      cluster='cluster',
      device_specs=None,
      shard_count=1,
      sharding_mode=ndb_models.ShardingMode.RUNNER,
      edited_command='command',
      module_config_pattern=None,
      module_execution_args=None,
      extra_test_resources=None,
      allow_partial_device_match=False):
    test = ndb_models.Test(
        name=test_name,
        command=command,
        retry_command_line=retry_command_line,
        runner_sharding_args=runner_sharding_args,
        module_config_pattern=module_config_pattern,
        module_execution_args=module_execution_args)
    test.put()
    test_run_config = ndb_models.TestRunConfig(
        test_key=test.key, cluster=cluster, device_specs=device_specs or [],
        shard_count=shard_count, sharding_mode=sharding_mode,
        command=edited_command,
        allow_partial_device_match=allow_partial_device_match)
    test_resources = [
        ndb_models.TestResourceObj(name='foo', url='http://foo_origin_url'),
        ndb_models.TestResourceObj(name='bar', url='https://bar_origin_url'),
    ] + (extra_test_resources or [])
    test_run = ndb_models.TestRun(
        id=str(uuid.uuid4()),
        test=test, labels=['label'], test_run_config=test_run_config,
        test_resources=test_resources, state=ndb_models.TestRunState.PENDING)
    test_run.put()
    return test_run

  def assertModelEqual(self, first, second):
    self.assertEqual(first.to_dict(), second.to_dict())

  def assertModelListEqual(self, first, second):
    self.assertEqual([f.to_dict() for f in first],
                     [s.to_dict() for s in second])

  def assertModelSetEqual(self, first, second):
    self.assertCountEqual([f.to_dict() for f in first],
                          [s.to_dict() for s in second])

  def setUp(self):
    super(TestKickerTest, self).setUp()
    self.testapp = webtest.TestApp(test_kicker.APP)
    self.hostname = 'localhost:8000'
    env.STORAGE_PATH = '/data'
    env.HOSTNAME = 'test.hostname.com'
    env.FILE_SERVER_URL = 'http://localhost:8006/'
    os.environ['DEFAULT_VERSION_HOSTNAME'] = self.hostname

  def testValidateDeviceActions(self):
    action = ndb_models.DeviceAction(
        device_spec='spec1',
        tradefed_options=[
            ndb_models.NameMultiValuePair(
                name='gce-driver-param', values=['--boot-timeout']),
            ndb_models.NameMultiValuePair(
                name='gce-driver-param', values=['600']),
            ndb_models.NameMultiValuePair(
                name='gce-driver-file-param', values=['file=url'])
        ])

    with self.assertRaises(ValueError):
      test_kicker.ValidateDeviceActions(
          [action, ndb_models.DeviceAction(device_spec='spec2')])

    with self.assertRaises(ValueError):
      test_kicker.ValidateDeviceActions([action, action])

    test_kicker.ValidateDeviceActions([
        action,
        ndb_models.DeviceAction(
            device_type='LOCAL_VIRTUAL',
            tradefed_options=[
                ndb_models.NameMultiValuePair(
                    name='gce-driver-path', values=['/bin/acloud_prebuilt']),
                ndb_models.NameMultiValuePair(
                    name='gce-driver-file-param', values=['file2=url2'])
            ])
    ])

  def testDeviceSpecsToTFCTestBench(self):
    self.assertEqual(
        test_kicker._DeviceSpecsToTFCTestBench('cluster', ['product:taimen']),
        api_messages.TestBenchRequirement(
            cluster='cluster',
            host=api_messages.HostRequirement(
                groups=[
                    api_messages.GroupRequirement(
                        run_targets=[
                            api_messages.RunTargetRequirement(
                                name='*',
                                device_attributes=[
                                    api_messages.DeviceAttributeRequirement(
                                        name='product', value='taimen')
                                ])
                        ])
                ])))
    self.assertEqual(
        test_kicker._DeviceSpecsToTFCTestBench(
            'cluster', ['device_serial:A', 'device_serial:B']),
        api_messages.TestBenchRequirement(
            cluster='cluster',
            host=api_messages.HostRequirement(
                groups=[
                    api_messages.GroupRequirement(
                        run_targets=[
                            api_messages.RunTargetRequirement(
                                name='*',
                                device_attributes=[
                                    api_messages.DeviceAttributeRequirement(
                                        name='device_serial', value='A')
                                ])
                        ]),
                    api_messages.GroupRequirement(
                        run_targets=[
                            api_messages.RunTargetRequirement(
                                name='*',
                                device_attributes=[
                                    api_messages.DeviceAttributeRequirement(
                                        name='device_serial', value='B')
                                ])
                        ])
                ])))
    self.assertEqual(
        test_kicker._DeviceSpecsToTFCTestBench(
            'cluster', ['device_serial:A device_serial:B']),
        api_messages.TestBenchRequirement(
            cluster='cluster',
            host=api_messages.HostRequirement(
                groups=[
                    api_messages.GroupRequirement(
                        run_targets=[
                            api_messages.RunTargetRequirement(
                                name='*',
                                device_attributes=[
                                    api_messages.DeviceAttributeRequirement(
                                        name='device_serial',
                                        value='A,B',
                                        operator='IN')
                                ])
                        ]),
                ])))

  @mock.patch.object(build, 'FindTestResources', autospec=True)
  def testCreateTestRun(self, mock_find_resources):
    test = ndb_models.Test(
        name='test',
        command='command',
        test_resource_defs=[
            ndb_models.TestResourceDef(
                name='foo',
                default_download_url='default_download_url',
                password='password',
            ),
            ndb_models.TestResourceDef(
                name='bar',
                default_download_url='default_download_url',
                decompress=True,
                decompress_dir='dir',
            ),
        ],
    )
    test.put()
    overwritten_obj = ndb_models.TestResourceObj(
                name='foo', url='origin_url', cache_url='cache_url')
    test_run_config = ndb_models.TestRunConfig(
        test_key=test.key,
        cluster='cluster',
        device_specs=['device_serial:serial'],
        test_resource_objs=[overwritten_obj],
    )
    mock_find_resources.return_value = [overwritten_obj]

    test_run = test_kicker.CreateTestRun(['label'], test_run_config)

    test_run = ndb_models.TestRun.get_by_id(test_run.key.id())
    self.assertModelEqual(test, test_run.test)
    self.assertEqual(['label'], test_run.labels)
    self.assertModelEqual(test_run_config, test_run.test_run_config)
    self.assertModelSetEqual(
        [
            ndb_models.TestResourceObj(
                name='bar',
                url='default_download_url',
                decompress=True,
                decompress_dir='dir',
                mount_zip=False,
                password='',
                params=ndb_models.TestResourceParameters(),
            ),
            ndb_models.TestResourceObj(
                name='foo',
                url='origin_url',
                cache_url='cache_url',
                password='password',
                decompress=False,
                decompress_dir='',
                mount_zip=False,
                params=ndb_models.TestResourceParameters(),
            ),
        ],
        test_run.test_resources,
    )
    self.assertEqual(ndb_models.TestRunState.PENDING, test_run.state)
    tasks = self.mock_task_scheduler.GetTasks(
        queue_names=[test_kicker.TEST_KICKER_QUEUE])
    self.assertLen(tasks, 1)
    task = tasks[0]
    data = json.loads(task.payload)
    self.assertEqual(test_run.key.id(), data['test_run_id'])
    self.assertIsNone(test_run.sequence_id)

  @mock.patch.object(build, 'FindTestResources', autospec=True)
  def testCreateTestRun_withNodeConfig(self, mock_find_resources):
    test = ndb_models.Test(
        name='test', command='command', test_resource_defs=[
            ndb_models.TestResourceDef(
                name='abc', default_download_url='default_download_url'),
            ndb_models.TestResourceDef(
                name='def', default_download_url='default_download_url'),
            ndb_models.TestResourceDef(
                name='xyz', default_download_url='default_download_url'),
        ])
    test.put()
    node_config = ndb_models.GetNodeConfig()
    node_config.env_vars.append(
        ndb_models.NameValuePair(name='foo', value='bar'))
    node_config.test_resource_default_download_urls = [
        ndb_models.NameValuePair(name='def', value='default_download_url2'),
        ndb_models.NameValuePair(name='xyz', value='default_download_url2'),
    ]
    node_config.put()
    overwritten_obj = ndb_models.TestResourceObj(
                name='xyz', url='origin_url', cache_url='cache_url')
    test_run_config = ndb_models.TestRunConfig(
        test_key=test.key,
        cluster='cluster',
        device_specs=['device_serial:serial'],
        test_resource_objs=[overwritten_obj])
    mock_find_resources.return_value = [overwritten_obj]

    test_run = test_kicker.CreateTestRun(
        ['label'], test_run_config)

    test_run = ndb_models.TestRun.get_by_id(test_run.key.id())
    self.assertEqual(test.command, test_run.test.command)
    self.assertModelListEqual(node_config.env_vars, test_run.test.env_vars)
    self.assertEqual(['label'], test_run.labels)
    self.assertModelEqual(test_run_config, test_run.test_run_config)
    self.assertModelSetEqual(
        [
            ndb_models.TestResourceObj(
                name='abc',
                url='default_download_url',
                decompress=False,
                decompress_dir='',
                mount_zip=False,
                password='',
                params=ndb_models.TestResourceParameters(),
            ),
            ndb_models.TestResourceObj(
                name='def',
                url='default_download_url2',
                decompress=False,
                decompress_dir='',
                mount_zip=False,
                password='',
                params=ndb_models.TestResourceParameters(),
            ),
            ndb_models.TestResourceObj(
                name='xyz',
                url='origin_url',
                cache_url='cache_url',
                decompress=False,
                decompress_dir='',
                mount_zip=False,
                password='',
                params=ndb_models.TestResourceParameters(),
            ),
        ],
        test_run.test_resources,
    )
    self.assertEqual(ndb_models.TestRunState.PENDING, test_run.state)
    tasks = self.mock_task_scheduler.GetTasks(
        queue_names=[test_kicker.TEST_KICKER_QUEUE])
    self.assertEqual(1, len(tasks))
    task = tasks[0]
    data = json.loads(task.payload)
    self.assertEqual(test_run.key.id(), data['test_run_id'])

  def testCreateTestRun_withTestRunActions(self):
    """Tests that test run can be created with test run actions."""
    test = ndb_models.Test(name='test', command='command')
    test.put()
    # Create a placeholder action with two default options
    action = ndb_models.TestRunAction(
        name='Foo',
        hook_class_name='foo',
        options=[
            ndb_models.NameValuePair(name='key1', value='default'),
            ndb_models.NameValuePair(name='key2', value='default'),
        ])
    action.put()
    # Create action ref with overridden and added options
    test_run_config = ndb_models.TestRunConfig(
        test_key=test.key,
        cluster='cluster',
        test_run_action_refs=[
            ndb_models.TestRunActionRef(
                action_key=action.key,
                options=[
                    ndb_models.NameValuePair(name='key2', value='updated'),
                    ndb_models.NameValuePair(name='key3', value='added'),
                ],
            )
        ])

    # Test run created with the right test run action
    test_run = test_kicker.CreateTestRun([], test_run_config)
    self.assertModelEqual(test_run_config, test_run.test_run_config)
    self.assertModelListEqual(test_run.test_run_actions, [
        ndb_models.TestRunAction(
            name='Foo',
            hook_class_name='foo',
            options=[
                ndb_models.NameValuePair(name='key1', value='default'),
                ndb_models.NameValuePair(name='key2', value='updated'),
                ndb_models.NameValuePair(name='key3', value='added'),
            ])
    ])

  def testCreateTestRun_withRerunConfigs(self):
    test = self._CreateMockTest()
    config1 = self._CreateMockTestRunConfig(test)
    config2 = self._CreateMockTestRunConfig(test, 'rt1;rt2')
    config3 = self._CreateMockTestRunConfig(test, 't1;t2;t3')

    test_run = test_kicker.CreateTestRun(
        ['label'], config1, rerun_configs=[config2, config3])

    sequence_id = test_run.sequence_id
    sequence = ndb.Key(ndb_models.TestRunSequence, sequence_id).get()

    self.assertEqual(len(sequence.test_run_configs), 3)
    self.assertModelEqual(sequence.test_run_configs[0], config1)
    self.assertModelEqual(sequence.test_run_configs[1], config2)
    self.assertModelEqual(sequence.test_run_configs[2], config3)

  def testConvertToTestResourceMap_unionDecompressFiles(self):
    test_resource_defs = [
        ndb_models.TestResourceDef(
            name='foo',
            decompress=True,
            decompress_dir='dir',
            params=ndb_models.TestResourceParameters(
                decompress_files=['a', 'b'])),
        ndb_models.TestResourceDef(
            name='foo',
            decompress=True,
            decompress_dir='dir',
            params=ndb_models.TestResourceParameters(
                decompress_files=['', 'b', 'c'])),
        ndb_models.TestResourceDef(name='bar', decompress=True),
        ndb_models.TestResourceDef(
            name='bar', decompress=True,
            params=ndb_models.TestResourceParameters(
                decompress_files=['bar'])),
    ]
    objs = test_kicker._ConvertToTestResourceMap(test_resource_defs)
    self.assertDictEqual(
        objs,
        {
            'foo': ndb_models.TestResourceObj(
                name='foo',
                decompress=True,
                decompress_dir='dir',
                mount_zip=False,
                password='',
                params=ndb_models.TestResourceParameters(
                    decompress_files=['a', 'b', 'c']
                ),
            ),
            'bar': ndb_models.TestResourceObj(
                name='bar',
                decompress=True,
                decompress_dir='',
                mount_zip=False,
                password='',
                params=ndb_models.TestResourceParameters(decompress_files=[]),
            ),
        },
    )

    # Assert that the input objects are unchanged.
    self.assertEqual(test_resource_defs[0].params.decompress_files, ['a', 'b'])
    self.assertEqual(test_resource_defs[1].params.decompress_files,
                     ['', 'b', 'c'])
    self.assertIsNone(test_resource_defs[2].params)
    self.assertEqual(test_resource_defs[3].params.decompress_files, ['bar'])

  def testConvertToTestResourceMap_invalidArguments(self):
    # Test test_resource_type field.
    with self.assertRaises(ValueError):
      test_kicker._ConvertToTestResourceMap([
          ndb_models.TestResourceDef(
              name='bar',
              test_resource_type=ndb_models.TestResourceType.UNKNOWN),
          ndb_models.TestResourceDef(
              name='bar',
              test_resource_type=ndb_models.TestResourceType.DEVICE_IMAGE),
      ])

    # Test decompress field.
    with self.assertRaises(ValueError):
      test_kicker._ConvertToTestResourceMap([
          ndb_models.TestResourceDef(name='bar', decompress=True),
          ndb_models.TestResourceDef(name='bar', decompress=False),
      ])

    # Test decompress_dir field.
    with self.assertRaises(ValueError):
      test_kicker._ConvertToTestResourceMap([
          ndb_models.TestResourceDef(name='bar', decompress=True),
          ndb_models.TestResourceDef(
              name='bar', decompress=True, decompress_dir='dir'
          ),
      ])

    # Test password field.
    with self.assertRaises(ValueError):
      test_kicker._ConvertToTestResourceMap([
          ndb_models.TestResourceDef(name='bar', password='password'),
          ndb_models.TestResourceDef(name='bar', password='password2'),
      ])

  def testGetRerunInfo_empty(self):
    # no rerun info without context
    self.assertEqual((None, None), test_kicker._GetRerunInfo(None, None))
    # no rerun info for empty context
    self.assertEqual((None, None),
                     test_kicker._GetRerunInfo(None, messages.RerunContext()))

  def testGetRerunInfo_local(self):
    # create local test run to rerun
    prev_test_run = self._CreateMockTestRun()
    prev_test_run.next_test_context = ndb_models.TestContextObj(
        test_resources=[ndb_models.TestResourceObj(name='bar', url='zzz')])
    prev_test_run.put()

    # determine rerun info using parent ID
    prev_run_key, prev_test_context = test_kicker._GetRerunInfo(
        None, messages.RerunContext(test_run_id=prev_test_run.key.id()))

    # test run key found and next_test_context used
    self.assertEqual(prev_test_run.key, prev_run_key)
    self.assertEqual(prev_test_run.next_test_context, prev_test_context)

  def testGetRerunInfo_remote(self):
    test = ndb_models.Test(context_file_dir='context/')

    # determine rerun info using parent ID
    prev_run_key, prev_test_context = test_kicker._GetRerunInfo(
        test, messages.RerunContext(context_filename='file',
                                    context_file_url='file_url'))

    # no test run key and test context contains provided file
    expected_context = ndb_models.TestContextObj(test_resources=[
        ndb_models.TestResourceObj(
            name='context/file', url='file_url')])
    self.assertIsNone(prev_run_key)
    self.assertEqual(expected_context, prev_test_context)

  def _CheckNewRequestMessage(
      self,
      msg,
      test_run,
      output_url,
      test_resource_urls,
      original_urls,
      command_lines,
      retry_command_line=None,
      test_bench=None,
      shard_count=None,
      max_concurrent_tasks=None,
  ):
    """Compare a new request message to its associated test run."""
    test = test_run.test
    test_run_config = test_run.test_run_config
    # compare general options
    self.assertEqual(api_messages.RequestType.MANAGED, msg.type)
    expected_shard_count = shard_count or test_run_config.shard_count
    for command_line, info in zip(command_lines, msg.command_infos):
      self.assertEqual(command_line, info.command_line)
      self.assertEqual(test_bench, info.test_bench)
      self.assertEqual(test_run_config.run_count, info.run_count)
      self.assertEqual(expected_shard_count, info.shard_count)
    self.assertEqual(
        retry_command_line, msg.test_environment.retry_command_line)
    self.assertEqual(
        test_run_config.max_retry_on_test_failures,
        msg.max_retry_on_test_failures)
    self.assertEqual(max_concurrent_tasks, msg.max_concurrent_tasks)
    # compare test environment
    self.assertTrue(msg.test_environment.use_subprocess_reporting)
    self.assertEqual(output_url, msg.test_environment.output_file_upload_url)
    self.assertEqual(test.context_file_pattern,
                     msg.test_environment.context_file_pattern)
    self.assertEqual([test_kicker.METADATA_FILE],
                     msg.test_environment.extra_context_files)
    self.assertEqual(common.LogLevel.INFO, msg.test_environment.log_level)
    self.assertEqual(
        test_run_config.use_parallel_setup,
        msg.test_environment.use_parallel_setup)
    # compare test resources, including additional metadata file
    test_resources = [
        api_messages.TestResource(
            name=r.name,
            url=test_resource_urls[r.name],
            original_download_url=original_urls[r.name],
        )
        for r in test_run.test_resources
    ]
    metadata_url = test_resource_urls['mtt.json']
    test_resources.append(api_messages.TestResource(
        name=test_kicker.METADATA_FILE, url=metadata_url))
    self.assertEqual(test_resources, msg.test_resources)
    # compare previous test context
    if test_run.prev_test_context:
      self.assertIsNotNone(msg.prev_test_context)
      self.assertEqual([
          api_messages.KeyValuePair(key=p.name, value=p.value)
          for p in test_run.prev_test_context.env_vars
      ], msg.prev_test_context.env_vars)
      self.assertEqual([
          api_messages.TestResource(
              name=r.name, url=file_util.GetWorkerAccessibleUrl(r.url))
          for r in test_run.prev_test_context.test_resources
      ], msg.prev_test_context.test_resources)

  @mock.patch.object(test_kicker, '_TrackTestRun')
  @mock.patch.object(tfc_client, 'NewRequest', autospec=True)
  @mock.patch.object(download_util, 'DownloadResources', autospec=True)
  def testKickTestRun(
      self, mock_download_resources, mock_new_request, mock_track_test_run):
    test_run_id = self._CreateMockTestRun().key.id()
    test_run = ndb_models.TestRun.get_by_id(test_run_id)
    test_run.test_run_config.use_parallel_setup = True
    test_run.test_run_config.allow_partial_device_match = True
    test_run.put()
    mock_download_resources.return_value = {
        r.url: 'cache_url' for r in test_run.test_resources
    }
    mock_request = api_messages.RequestMessage(id='request_id')
    mock_new_request.return_value = mock_request

    test_kicker.KickTestRun(test_run_id)

    mock_download_resources.assert_called_once_with(
        [r.url for r in test_run.test_resources], test_run=test_run)
    mock_new_request.assert_called()
    msg = mock_new_request.call_args[0][0]
    self._CheckNewRequestMessage(
        msg=msg,
        test_run=test_run,
        output_url=(
            'file:///data/app_default_bucket/test_runs/{}/output'.format(
                test_run_id
            )
        ),
        test_resource_urls={
            'foo': 'cache_url',
            'bar': 'cache_url',
            'mtt.json': (
                'http://localhost:8000/_ah/api/mtt/v1/test_runs/{}/metadata'
                .format(test_run_id)
            ),
        },
        original_urls={
            'foo': 'http://foo_origin_url',
            'bar': 'https://bar_origin_url',
        },
        command_lines=['command --invocation-data mtt=1'],
        test_bench=api_messages.TestBenchRequirement(
            cluster='cluster', host=api_messages.HostRequirement()
        ),
    )
    test_run = ndb_models.TestRun.get_by_id(test_run_id)
    self.assertEqual(mock_request.id, test_run.request_id)
    self.assertEqual(ndb_models.TestRunState.QUEUED, test_run.state)
    self.assertTrue(test_run.test_run_config.allow_partial_device_match)

    # metrics tracked
    mock_track_test_run.assert_called_once()

  @mock.patch.object(tfc_client, 'NewRequest', autospec=True)
  @mock.patch.object(download_util, 'DownloadResources', autospec=True)
  def testKickTestRun_runnerSharding(
      self, mock_download_resources, mock_new_request):
    test_run_id = self._CreateMockTestRun(
        command='command',
        runner_sharding_args='--shard-count ${TF_SHARD_COUNT}',
        device_specs=['name:value'],
        shard_count=2,
        sharding_mode=ndb_models.ShardingMode.RUNNER).key.id()
    test_run = ndb_models.TestRun.get_by_id(test_run_id)
    mock_download_resources.return_value = {
        r.url: 'cache_url' for r in test_run.test_resources
    }
    mock_request = api_messages.RequestMessage(id='request_id')
    mock_new_request.return_value = mock_request

    test_kicker.KickTestRun(test_run_id)

    mock_download_resources.assert_called_once_with(
        [r.url for r in test_run.test_resources], test_run=test_run)
    mock_new_request.assert_called()
    msg = mock_new_request.call_args[0][0]
    self._CheckNewRequestMessage(
        msg=msg,
        test_run=test_run,
        output_url=(
            'file:///data/app_default_bucket/test_runs/{}/output'.format(
                test_run_id
            )
        ),
        test_resource_urls={
            'foo': 'cache_url',
            'bar': 'cache_url',
            'mtt.json': (
                'http://localhost:8000/_ah/api/mtt/v1/test_runs/{}/metadata'
                .format(test_run_id)
            ),
        },
        original_urls={
            'foo': 'http://foo_origin_url',
            'bar': 'https://bar_origin_url',
        },
        command_lines=['command --shard-count 2 --invocation-data mtt=1'],
        test_bench=test_kicker._DeviceSpecsToTFCTestBench(
            test_run.test_run_config.cluster,
            test_run.test_run_config.device_specs,
        ),
        shard_count=1,
    )
    test_run = ndb_models.TestRun.get_by_id(test_run_id)
    self.assertEqual(mock_request.id, test_run.request_id)
    self.assertEqual(ndb_models.TestRunState.QUEUED, test_run.state)

  @mock.patch.object(tfc_client, 'NewRequest', autospec=True)
  @mock.patch.object(file_util, 'GetTestModuleInfos', autospec=True)
  @mock.patch.object(file_util, 'OpenFile', autospec=True)
  @mock.patch.object(download_util, 'DownloadResources', autospec=True)
  def testKickTestRun_moduleSharding(
      self,
      mock_download_resources,
      mock_open_file,
      mock_get_test_module_infos,
      mock_new_request):
    test_run = self._CreateMockTestRun(
        command='command',
        cluster='cluster',
        device_specs=['name:value1', 'name:value2'],
        shard_count=6,
        sharding_mode=ndb_models.ShardingMode.MODULE,
        module_config_pattern='path/to/.*\\.config',
        module_execution_args='-m ${MODULE_NAME}',
        extra_test_resources=[
            ndb_models.TestResourceObj(
                name='test_package',
                url='test_package_url',
                test_resource_type=ndb_models.TestResourceType.TEST_PACKAGE)
        ])
    test_run_id = test_run.key.id()
    test_run = ndb_models.TestRun.get_by_id(test_run_id)
    mock_download_resources.return_value = {
        r.url: '%s_cache_url' % r.name for r in test_run.test_resources
    }
    mock_get_test_module_infos.return_value = [
        file_util.TestModuleInfo(name='CtsFooTestCases'),
        file_util.TestModuleInfo(name='CtsDeqpTestCases'),
        file_util.TestModuleInfo(name='CtsBarTestCases'),
    ]
    mock_request = api_messages.RequestMessage(id='request_id')
    mock_new_request.return_value = mock_request

    test_kicker.KickTestRun(test_run_id)

    mock_download_resources.assert_called_once_with(
        [r.url for r in test_run.test_resources], test_run=test_run)
    mock_open_file.assert_called_with('test_package_cache_url')
    mock_get_test_module_infos.assert_called_once_with(
        mock_open_file.return_value, 'path/to/.*\\.config')
    mock_new_request.assert_called()
    msg = mock_new_request.call_args[0][0]
    self._CheckNewRequestMessage(
        msg=msg,
        test_run=test_run,
        output_url=(
            'file:///data/app_default_bucket/test_runs/{}/output'.format(
                test_run_id
            )
        ),
        test_resource_urls={
            'foo': 'foo_cache_url',
            'bar': 'bar_cache_url',
            'test_package': 'test_package_cache_url',
            'mtt.json': (
                'http://localhost:8000/_ah/api/mtt/v1/test_runs/{}/metadata'
                .format(test_run_id)
            ),
        },
        original_urls={
            'foo': 'http://foo_origin_url',
            'bar': 'https://bar_origin_url',
            'test_package': 'test_package_url',
        },
        command_lines=[
            (
                'command -m CtsDeqpTestCases --shard-count 6 --shard-index 0'
                ' --invocation-data mtt=1'
            ),
            (
                'command -m CtsDeqpTestCases --shard-count 6 --shard-index 1'
                ' --invocation-data mtt=1'
            ),
            (
                'command -m CtsDeqpTestCases --shard-count 6 --shard-index 2'
                ' --invocation-data mtt=1'
            ),
            (
                'command -m CtsDeqpTestCases --shard-count 6 --shard-index 3'
                ' --invocation-data mtt=1'
            ),
            (
                'command -m CtsDeqpTestCases --shard-count 6 --shard-index 4'
                ' --invocation-data mtt=1'
            ),
            (
                'command -m CtsDeqpTestCases --shard-count 6 --shard-index 5'
                ' --invocation-data mtt=1'
            ),
            'command -m CtsBarTestCases --invocation-data mtt=1',
            'command -m CtsFooTestCases --invocation-data mtt=1',
        ],
        test_bench=test_kicker._DeviceSpecsToTFCTestBench(
            test_run.test_run_config.cluster, ['name:value1 name:value2']
        ),
        shard_count=1,
        max_concurrent_tasks=6,
    )
    test_run = ndb_models.TestRun.get_by_id(test_run_id)
    self.assertEqual(mock_request.id, test_run.request_id)
    self.assertEqual(ndb_models.TestRunState.QUEUED, test_run.state)

  @mock.patch.object(tfc_client, 'NewRequest', autospec=True)
  @mock.patch.object(download_util, 'DownloadResources', autospec=True)
  def testKickTestRun_AllowPartialDeviceMatch(
      self, mock_download_resources, mock_new_request):
    test_run_id = self._CreateMockTestRun(
        command='command',
        runner_sharding_args='--shard-count ${TF_SHARD_COUNT}',
        cluster='cluster',
        device_specs=['name:value'],
        shard_count=2,
        sharding_mode=ndb_models.ShardingMode.RUNNER,
        allow_partial_device_match=True).key.id()
    test_run = ndb_models.TestRun.get_by_id(test_run_id)
    mock_download_resources.return_value = {
        r.url: 'cache_url' for r in test_run.test_resources
    }
    mock_request = api_messages.RequestMessage(id='request_id')
    mock_new_request.return_value = mock_request

    test_kicker.KickTestRun(test_run_id)

    mock_download_resources.assert_called_once_with(
        [r.url for r in test_run.test_resources], test_run=test_run)
    mock_new_request.assert_called()
    msg = mock_new_request.call_args[0][0]
    self._CheckNewRequestMessage(
        msg=msg,
        test_run=test_run,
        output_url=(
            'file:///data/app_default_bucket/test_runs/{}/output'.format(
                test_run_id
            )
        ),
        test_resource_urls={
            'foo': 'cache_url',
            'bar': 'cache_url',
            'mtt.json': (
                'http://localhost:8000/_ah/api/mtt/v1/test_runs/{}/metadata'
                .format(test_run_id)
            ),
        },
        original_urls={
            'foo': 'http://foo_origin_url',
            'bar': 'https://bar_origin_url',
        },
        command_lines=[
            'command --shard-count ${TF_DEVICE_COUNT} --invocation-data mtt=1'
        ],
        test_bench=test_kicker._DeviceSpecsToTFCTestBench(
            test_run.test_run_config.cluster,
            test_run.test_run_config.device_specs,
        ),
        shard_count=1,
    )
    test_run = ndb_models.TestRun.get_by_id(test_run_id)
    self.assertEqual(mock_request.id, test_run.request_id)
    self.assertEqual(ndb_models.TestRunState.QUEUED, test_run.state)

  @mock.patch.object(tfc_client, 'NewRequest', autospec=True)
  @mock.patch.object(download_util, 'DownloadResources', autospec=True)
  def testKickTestRun_editedCommand(
      self, mock_download_resources, mock_new_request):
    test_run_id = self._CreateMockTestRun(
        edited_command='edited command').key.id()
    test_run = ndb_models.TestRun.get_by_id(test_run_id)
    mock_download_resources.return_value = {
        r.url: 'cache_url' for r in test_run.test_resources
    }
    mock_request = api_messages.RequestMessage(id='request_id')
    mock_new_request.return_value = mock_request

    test_kicker.KickTestRun(test_run_id)

    mock_download_resources.assert_called_once_with(
        [r.url for r in test_run.test_resources], test_run=test_run)
    mock_new_request.assert_called()
    msg = mock_new_request.call_args[0][0]
    self._CheckNewRequestMessage(
        msg=msg,
        test_run=test_run,
        output_url=(
            'file:///data/app_default_bucket/test_runs/{}/output'.format(
                test_run_id
            )
        ),
        test_resource_urls={
            'foo': 'cache_url',
            'bar': 'cache_url',
            'mtt.json': (
                'http://localhost:8000/_ah/api/mtt/v1/test_runs/{}/metadata'
                .format(test_run_id)
            ),
        },
        original_urls={
            'foo': 'http://foo_origin_url',
            'bar': 'https://bar_origin_url',
        },
        command_lines=['edited command --invocation-data mtt=1'],
        test_bench=test_kicker._DeviceSpecsToTFCTestBench(
            test_run.test_run_config.cluster,
            test_run.test_run_config.device_specs,
        ),
        shard_count=1,
    )
    test_run = ndb_models.TestRun.get_by_id(test_run_id)
    self.assertEqual(mock_request.id, test_run.request_id)
    self.assertEqual(ndb_models.TestRunState.QUEUED, test_run.state)

  @mock.patch.object(tfc_client, 'NewRequest', autospec=True)
  @mock.patch.object(download_util, 'DownloadResources', autospec=True)
  def testKickTestRun_withPrevTestContext(
      self, mock_download_resources, mock_new_request):
    test_run = self._CreateMockTestRun(
        command='command',
        retry_command_line='retry_command_line',
        runner_sharding_args='--shard-count ${TF_SHARD_COUNT}',
        shard_count=6)
    test_run.prev_test_context = ndb_models.TestContextObj(
        command_line='prev_command_line',
        env_vars=[],
        test_resources=[ndb_models.TestResourceObj(name='bar', url='zzz')])
    test_run.put()
    test_run_id = test_run.key.id()
    test_run = ndb_models.TestRun.get_by_id(test_run_id)
    mock_download_resources.return_value = {
        r.url: 'cache_url' for r in test_run.test_resources
    }
    mock_request = api_messages.RequestMessage(id='request_id')
    mock_new_request.return_value = mock_request

    test_kicker.KickTestRun(test_run_id)

    mock_download_resources.assert_called_once_with(
        [r.url for r in test_run.test_resources], test_run=test_run)
    mock_new_request.assert_called()
    msg = mock_new_request.call_args[0][0]
    self._CheckNewRequestMessage(
        msg=msg,
        test_run=test_run,
        output_url=(
            'file:///data/app_default_bucket/test_runs/{}/output'.format(
                test_run_id
            )
        ),
        test_resource_urls={
            'foo': 'cache_url',
            'bar': 'cache_url',
            'mtt.json': (
                'http://localhost:8000/_ah/api/mtt/v1/test_runs/{}/metadata'
                .format(test_run_id)
            ),
        },
        original_urls={
            'foo': 'http://foo_origin_url',
            'bar': 'https://bar_origin_url',
        },
        command_lines=['command --shard-count 6 --invocation-data mtt=1'],
        retry_command_line=(
            'retry_command_line --shard-count 6 --invocation-data mtt=1'
        ),
        test_bench=test_kicker._DeviceSpecsToTFCTestBench(
            test_run.test_run_config.cluster,
            test_run.test_run_config.device_specs,
        ),
        shard_count=1,
    )
    # prev_test_context's command_line should be replaced.
    self.assertEqual(
        'retry_command_line --shard-count 6 --invocation-data mtt=1',
        msg.prev_test_context.command_line)
    test_run = ndb_models.TestRun.get_by_id(test_run_id)
    self.assertEqual(mock_request.id, test_run.request_id)
    self.assertEqual(ndb_models.TestRunState.QUEUED, test_run.state)

  @mock.patch.object(tfc_client, 'NewRequest', autospec=True)
  @mock.patch.object(test_run_hook, 'ExecuteHooks', autospec=True)
  @mock.patch.object(download_util, 'DownloadResources', autospec=True)
  def testKickTestRun_withTestRunActions(
      self, mock_download_resources, mock_execute_hooks, mock_new_request):
    # Create test run action with two TF result reporters
    test_run_action = ndb_models.TestRunAction(
        name='Foo',
        hook_class_name='foo',
        tradefed_result_reporters=[
            ndb_models.TradefedConfigObject(
                class_name='com.android.foo',
                option_values=[ndb_models.NameMultiValuePair(
                    name='test-run-id', values=['${MTT_TEST_RUN_ID}'])]
            ),
            ndb_models.TradefedConfigObject(class_name='com.android.bar'),
        ])
    before_device_action = ndb_models.DeviceAction(
        name='Before Device Action',
        tradefed_target_preparers=[
            ndb_models.TradefedConfigObject(
                class_name='com.android.before_device_action',
            )
        ],
        tradefed_options=[
            ndb_models.NameMultiValuePair(
                name='bugreport-on-invocation-ended', values=['true']
            )
        ],
    )
    test_run_action.put()
    before_device_action.put()
    # Create test run with test run action
    test_run = self._CreateMockTestRun(command='command')
    test_run.test_run_actions = [test_run_action]
    test_run.before_device_actions = [before_device_action]
    test_run.put()
    test_run_id = test_run.key.id()
    test_run = ndb_models.TestRun.get_by_id(test_run_id)
    # Mock responses
    mock_download_resources.return_value = {
        r.url: 'cache_url' for r in test_run.test_resources
    }
    mock_request = api_messages.RequestMessage(id='request_id')
    mock_new_request.return_value = mock_request

    test_kicker.KickTestRun(test_run_id)

    # Resources downloaded, hooks executed, and new TFC request created
    mock_download_resources.assert_called_once_with(
        [r.url for r in test_run.test_resources], test_run=test_run)
    mock_execute_hooks.assert_called_with(
        test_run_id, ndb_models.TestRunPhase.BEFORE_RUN)
    mock_new_request.assert_called()
    msg = mock_new_request.call_args[0][0]
    self._CheckNewRequestMessage(
        msg=msg,
        test_run=test_run,
        output_url=(
            'file:///data/app_default_bucket/test_runs/{}/output'.format(
                test_run_id
            )
        ),
        test_resource_urls={
            'foo': 'cache_url',
            'bar': 'cache_url',
            'mtt.json': (
                'http://localhost:8000/_ah/api/mtt/v1/test_runs/{}/metadata'
                .format(test_run_id)
            ),
        },
        original_urls={
            'foo': 'http://foo_origin_url',
            'bar': 'https://bar_origin_url',
        },
        command_lines=['command --invocation-data mtt=1'],
        test_bench=test_kicker._DeviceSpecsToTFCTestBench(
            test_run.test_run_config.cluster,
            test_run.test_run_config.device_specs,
        ),
    )

    # TFC request has two TF result reporters with right class names and options
    tradefed_config_objects = msg.test_environment.tradefed_config_objects
    self.assertEqual(
        [tradefed_config_objects.pop(0)], test_kicker.DEFAULT_TF_CONFIG_OBJECTS)
    self.assertLen(tradefed_config_objects, 3)
    self.assertEqual(
        api_messages.TradefedConfigObjectType.TARGET_PREPARER,
        tradefed_config_objects[0].type,
    )
    self.assertEqual(
        'com.android.before_device_action',
        tradefed_config_objects[0].class_name,
    )
    self.assertEqual(
        api_messages.TradefedConfigObjectType.RESULT_REPORTER,
        tradefed_config_objects[1].type,
    )
    self.assertEqual('com.android.foo', tradefed_config_objects[1].class_name)
    self.assertEqual(
        'test-run-id', tradefed_config_objects[1].option_values[0].key
    )
    self.assertEqual(
        [str(test_run_id)], tradefed_config_objects[1].option_values[0].values
    )
    self.assertEqual(
        api_messages.TradefedConfigObjectType.RESULT_REPORTER,
        tradefed_config_objects[2].type,
    )
    self.assertEqual('com.android.bar', tradefed_config_objects[2].class_name)
    self.assertEmpty(tradefed_config_objects[2].option_values)

    self.assertEqual(
        api_messages.KeyMultiValuePair(
            key='bugreport-on-invocation-ended', values=['true']
        ),
        msg.test_environment.tradefed_options[0],
    )

    # Test run now queued
    test_run = ndb_models.TestRun.get_by_id(test_run_id)
    self.assertEqual(mock_request.id, test_run.request_id)
    self.assertEqual(ndb_models.TestRunState.QUEUED, test_run.state)

  @mock.patch('multitest_transport.util.env.PORT',
              '8000')
  @mock.patch('multitest_transport.util.env.FILE_SERVER_PORT',
              '8006')
  @mock.patch('multitest_transport.util.env.OPERATION_MODE',
              env.OperationMode.ON_PREMISE)
  @mock.patch.object(tfc_client, 'NewRequest', autospec=True)
  @mock.patch.object(download_util, 'DownloadResources', autospec=True)
  def testKickTestRun_onPremiseMode(self, mock_download_resources,
                                    mock_new_request):
    test_run = self._CreateMockTestRun()
    # test_run = ndb_models.TestRun.get_by_id(test_run_id)
    test_run.prev_test_context = ndb_models.TestContextObj(
        command_line='prev_command_line',
        env_vars=[],
        test_resources=[
            ndb_models.TestResourceObj(name='bar', url='file:///data/root/path')
        ])
    test_run.put()
    test_run_id = test_run.key.id()
    test_run = ndb_models.TestRun.get_by_id(test_run_id)
    mock_download_resources.return_value = {
        r.url: 'file:///data/cache_url' for r in test_run.test_resources
    }
    mock_request = api_messages.RequestMessage(id='request_id')
    mock_new_request.return_value = mock_request

    test_kicker.KickTestRun(test_run_id)

    mock_download_resources.assert_called_once_with(
        [r.url for r in test_run.test_resources], test_run=test_run)
    mock_new_request.assert_called()
    msg = mock_new_request.call_args[0][0]
    self._CheckNewRequestMessage(
        msg=msg,
        test_run=test_run,
        output_url=f'${{MTT_CONTROL_FILE_SERVER_URL}}/file/app_default_bucket/test_runs/{test_run_id}/output',
        test_resource_urls={
            'foo': '${MTT_CONTROL_FILE_SERVER_URL}/file/cache_url',
            'bar': '${MTT_CONTROL_FILE_SERVER_URL}/file/cache_url',
            'mtt.json': (
                f'${{MTT_CONTROL_SERVER_URL}}/_ah/api/mtt/v1/test_runs/{test_run_id}/metadata'
            ),
        },
        original_urls={
            'foo': 'http://foo_origin_url',
            'bar': 'https://bar_origin_url',
        },
        command_lines=['command --invocation-data mtt=1'],
        test_bench=test_kicker._DeviceSpecsToTFCTestBench(
            test_run.test_run_config.cluster,
            test_run.test_run_config.device_specs))
    self.assertEqual([
        api_messages.TestResource(
            name='bar', url='${MTT_CONTROL_FILE_SERVER_URL}/file/root/path')
    ], msg.prev_test_context.test_resources)

  @mock.patch.object(tfc_client, 'ResumeRequest', autospec=True)
  def testKickTestRun_resumeRequest(self, mock_resume_request):
    test_run = self._CreateMockTestRun()
    test_run.state = ndb_models.TestRunState.RUNNING
    test_run.put()
    test_run_id = test_run.key.id()
    test_run = ndb_models.TestRun.get_by_id(test_run_id)

    test_kicker.KickTestRun(test_run_id)

    mock_resume_request.assert_called_once_with(test_run.request_id)

  @mock.patch.object(test_kicker, 'KickTestRun')
  def testEnqueueTestRun(self, mock_kick_test_run):
    test_run_id = 1000
    test_kicker.EnqueueTestRun(test_run_id)
    tasks = self.mock_task_scheduler.GetTasks(
        queue_names=test_kicker.TEST_KICKER_QUEUE)
    self.assertLen(tasks, 1)
    response = self.testapp.post(
        '/_ah/queue/%s' % test_kicker.TEST_KICKER_QUEUE, tasks[0].payload)
    self.assertEqual('200 OK', response.status)
    mock_kick_test_run.assert_called_with(test_run_id)

  @mock.patch.object(download_util, 'DownloadResources', autospec=True)
  @mock.patch.object(file_util, 'GetTestSuiteInfo')
  @mock.patch.object(file_util, 'OpenFile')
  def testPrepareTestResources(
      self, mock_open_file, mock_get_suite_info, mock_download_resources):
    test_run = self._CreateMockTestRun(
        command='command')
    test_run.test_resources = [
        ndb_models.TestResourceObj(
            name='foo',
            url='http://foo_origin_url',
            test_resource_type=ndb_models.TestResourceType.TEST_PACKAGE)
    ]
    test_run.put()
    test_run_id = test_run.key.id()
    test_run = ndb_models.TestRun.get_by_id(test_run_id)
    mock_download_resources.return_value = {
        r.url: 'cache_url' for r in test_run.test_resources
    }
    mock_open_file.return_value = mock.MagicMock()
    test_suite_info = file_util.TestSuiteInfo(
        'build_number', 'architecture', 'name', 'fullname', 'version')
    mock_get_suite_info.return_value = test_suite_info

    test_kicker._PrepareTestResources(test_run_id)
    updated_test_run = ndb_models.TestRun.get_by_id(test_run.key.id())

    # Resource downloaded and cached
    mock_download_resources.assert_called_with(
        ['http://foo_origin_url'], test_run=test_run)
    self.assertEqual(updated_test_run.test_resources[0].cache_url, 'cache_url')
    mock_open_file.assert_called_with('cache_url')
    # Test package info was updated
    test_package_info = updated_test_run.test_package_info
    self.assertEqual(test_package_info.build_number, 'build_number')
    self.assertEqual(test_package_info.target_architecture, 'architecture')
    self.assertEqual(test_package_info.name, 'name')
    self.assertEqual(test_package_info.fullname, 'fullname')
    self.assertEqual(test_package_info.version, 'version')

  @mock.patch.object(analytics, 'Log')
  def testTrackTestRun(self, mock_log):
    # configure test run
    test_run = self._CreateMockTestRun()
    test_run.test_package_info = ndb_models.TestPackageInfo(
        name='name', version='version')

    # check that right data was logged
    test_kicker._TrackTestRun(test_run)
    mock_log.assert_called_with(analytics.TEST_RUN_CATEGORY,
                                analytics.START_ACTION,
                                test_name='name',
                                test_version='version',
                                is_rerun=False)

  @mock.patch.object(env, 'IS_OMNILAB_BASED', True)
  @mock.patch.object(tfc_client, 'NewRequest', autospec=True)
  @mock.patch.object(download_util, 'DownloadResources', autospec=True)
  def testKickTestRun_AllowPartialDeviceMatch_omniLab(
      self, mock_download_resources, mock_new_request):
    test_run_id = self._CreateMockTestRun(
        command='command',
        runner_sharding_args='--shard-count ${TF_SHARD_COUNT}',
        cluster='cluster',
        device_specs=['name:value'],
        shard_count=2,
        sharding_mode=ndb_models.ShardingMode.RUNNER,
        allow_partial_device_match=True).key.id()
    test_run = ndb_models.TestRun.get_by_id(test_run_id)
    mock_download_resources.return_value = {
        r.url: 'cache_url' for r in test_run.test_resources
    }
    mock_request = api_messages.RequestMessage(id='request_id')
    mock_new_request.return_value = mock_request

    test_kicker.KickTestRun(test_run_id)

    mock_download_resources.assert_called_once_with(
        [r.url for r in test_run.test_resources], test_run=test_run)
    mock_new_request.assert_called()
    msg = mock_new_request.call_args[0][0]
    self._CheckNewRequestMessage(
        msg=msg,
        test_run=test_run,
        output_url=(
            'file:///data/app_default_bucket/test_runs/{}/output'.format(
                test_run_id
            )
        ),
        test_resource_urls={
            'foo': 'cache_url',
            'bar': 'cache_url',
            'mtt.json': (
                'http://localhost:8000/_ah/api/mtt/v1/test_runs/{}/metadata'
                .format(test_run_id)
            ),
        },
        original_urls={
            'foo': 'http://foo_origin_url',
            'bar': 'https://bar_origin_url',
        },
        command_lines=[
            'command --shard-count 2 --invocation-data mtt=1'
        ],
        test_bench=test_kicker._DeviceSpecsToTFCTestBench(
            test_run.test_run_config.cluster,
            test_run.test_run_config.device_specs,
        ),
        shard_count=1,
    )
    test_run = ndb_models.TestRun.get_by_id(test_run_id)
    self.assertEqual(mock_request.id, test_run.request_id)
    self.assertEqual(ndb_models.TestRunState.QUEUED, test_run.state)

if __name__ == '__main__':
  absltest.main()
