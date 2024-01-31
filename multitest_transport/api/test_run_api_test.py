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

"""Tests for test_run_api."""
import tempfile
from unittest import mock
import uuid
import zipfile

from absl.testing import absltest
from protorpc import protojson
from tradefed_cluster import api_messages
from tradefed_cluster.api_messages import CommandState


from multitest_transport.api import api_test_util
from multitest_transport.api import test_run_api
from multitest_transport.models import messages
from multitest_transport.models import ndb_models
from multitest_transport.models import sql_models
from multitest_transport.test_scheduler import test_kicker
from multitest_transport.test_scheduler import test_run_manager
from multitest_transport.util import analytics
from multitest_transport.util import env
from multitest_transport.util import file_util
from multitest_transport.util import tfc_client


class TestRunApiTest(api_test_util.TestCase):

  def setUp(self):
    super(TestRunApiTest, self).setUp(test_run_api.TestRunApi)

  def _createMockTest(self, name='test', command='command'):
    """Create a mock ndb_models.Test object."""
    test = ndb_models.Test(name=name, command=command)
    test.put()
    return test

  def _createMockBuild(self):
    """Create a mock ndb_models.Build object."""
    build = ndb_models.Build(
        name='build',
        fingerprint='fingerprint',
        file_url='file:///root/file/path',
        size=123456,
        labels=['label1', 'label2'],
    )
    build.put()
    return build

  def _createMockRequiredReport(self, build_key):
    """Create a mock ndb_models.RequiredReport object."""
    required_report = ndb_models.RequiredReport(
        build_key=build_key, type=ndb_models.ReportType.CTS
    )
    required_report.put()
    return required_report

  def _createMockTestRuns(
      self,
      test=None,
      labels=None,
      cluster='cluster',
      device_specs=None,
      run_count=1,
      shard_count=1,
      test_devices=None,
      test_package_info=None,
      test_resources=None,
      state=None,
      output_path=None,
      count=1,
      prev_test_run_key=None):
    """Create a mock ndb_models.TestRun object."""
    device_specs = device_specs or ['device_spec']
    test_runs = []
    for _ in range(count):
      test_run = ndb_models.TestRun(
          id=str(uuid.uuid4()),
          prev_test_run_key=prev_test_run_key,
          test=test,
          labels=labels or [],
          test_run_config=ndb_models.TestRunConfig(
              test_key=test.key if test is not None else None,
              cluster=cluster,
              device_specs=device_specs,
              run_count=run_count,
              shard_count=shard_count),
          test_devices=test_devices or [],
          test_package_info=test_package_info,
          test_resources=test_resources or [],
          state=state,
          output_path=output_path)
      test_run.put()
      test_runs.append(test_run)
    return test_runs

  def _createMockTestRunSummaries(self, **kwargs):
    test_runs = self._createMockTestRuns(**kwargs)
    return [test_run.ToSummary() for test_run in test_runs]

  def _createAttempt(self, state=None):
    """Creates a fake command attempt."""
    return api_messages.CommandAttemptMessage(
        request_id='id', command_id='id', attempt_id='id', task_id='id',
        state=state or CommandState.UNKNOWN)

  def testListSummaries(self):
    test = self._createMockTest()
    for i in range(1, 10):
      self._createMockTestRuns(test, device_specs=[str(i)], count=1)

    # fetch first page (5 results, run count 9 to 5, has more)
    res = self.app.get('/_ah/api/mtt/v1/test_runs?max_results=5')
    self.assertEqual('200 OK', res.status)
    first_page = protojson.decode_message(messages.TestRunSummaryList, res.body)
    self.assertLen(first_page.test_runs, 5)
    self.assertIsNone(first_page.prev_page_token)  # no previous runs
    self.assertIsNotNone(first_page.next_page_token)  # has following runs
    self.assertEqual(first_page.test_runs[0].device_specs, ['9'])
    self.assertEqual(first_page.test_runs[4].device_specs, ['5'])

    # fetch next page (4 results, run count 4 to 1, last page)
    res = self.app.get(
        '/_ah/api/mtt/v1/test_runs?max_results=5&page_token=%s' %
        first_page.next_page_token)
    self.assertEqual('200 OK', res.status)
    next_page = protojson.decode_message(messages.TestRunSummaryList, res.body)
    self.assertLen(next_page.test_runs, 4)
    self.assertIsNotNone(next_page.prev_page_token)  # has previous runs
    self.assertIsNone(next_page.next_page_token)  # no following runs
    self.assertEqual(next_page.test_runs[0].device_specs, ['4'])
    self.assertEqual(next_page.test_runs[3].device_specs, ['1'])

    # fetch previous page (same as first page)
    res = self.app.get(
        '/_ah/api/mtt/v1/test_runs?max_results=5&page_token=%s&backwards=true' %
        next_page.prev_page_token)
    self.assertEqual('200 OK', res.status)
    prev_page = protojson.decode_message(messages.TestRunSummaryList, res.body)
    self.assertEqual(first_page, prev_page)

  def testListSummaries_filterReruns(self):
    test = self._createMockTest()
    test_run = self._createMockTestRunSummaries(test=test)[0]

    res = self.app.get('/_ah/api/mtt/v1/test_runs?prev_test_run_id=%s' %
                       test_run.key.id())
    self.assertEqual('200 OK', res.status)
    test_run_msg = protojson.decode_message(messages.TestRunSummaryList,
                                            res.body).test_runs
    self.assertEqual(test_run_msg, [])

    test_run_key = messages.ConvertToKey(ndb_models.TestRun, test_run.key.id())
    retry_run = self._createMockTestRunSummaries(
        test=test, prev_test_run_key=test_run_key)[0]
    retry_run_msg = messages.Convert(retry_run, messages.TestRunSummary)
    separate_retry = self._createMockTestRunSummaries(
        test=test, prev_test_run_key=test_run_key)[0]
    separate_retry_msg = messages.Convert(separate_retry,
                                          messages.TestRunSummary)

    res = self.app.get('/_ah/api/mtt/v1/test_runs?prev_test_run_id=%s' %
                       test_run.key.id())
    test_run_msg = protojson.decode_message(messages.TestRunSummaryList,
                                            res.body).test_runs
    self.assertEqual(test_run_msg[0].id, separate_retry_msg.id)
    self.assertEqual(test_run_msg[1].id, retry_run_msg.id)

  def testListSummaries_filter(self):
    # Helper to fetch filtered test runs and verify/parse response.
    def FetchTestRuns(*args):
      filters = '&'.join(['filter_query=' + query for query in args])
      res = self.app.get('/_ah/api/mtt/v1/test_runs?' + filters)
      self.assertEqual('200 OK', res.status)
      return protojson.decode_message(messages.TestRunSummaryList,
                                      res.body).test_runs

    # Create placeholder test runs with a variety of property values
    runs1 = self._createMockTestRunSummaries(
        test=self._createMockTest(name='foo'),
        labels=['bar'],
        device_specs=['baz'])
    msg1 = messages.Convert(runs1[0], messages.TestRunSummary)
    runs2 = self._createMockTestRunSummaries(
        test=self._createMockTest(),
        labels=['common'],
        test_devices=[
            ndb_models.TestDeviceInfo(build_id='qux', product='spam')
        ])
    msg2 = messages.Convert(runs2[0], messages.TestRunSummary)
    runs3 = self._createMockTestRunSummaries(
        test=self._createMockTest(name='common'),
        test_package_info=ndb_models.TestPackageInfo(
            name='ham', version='eggs'))
    msg3 = messages.Convert(runs3[0], messages.TestRunSummary)

    # Can search using individual properties
    self.assertEqual([], FetchTestRuns('unknown'))
    self.assertEqual([msg1], FetchTestRuns('foo'))  # test name
    self.assertEqual([msg1], FetchTestRuns('bar'))  # label
    self.assertEqual([msg1], FetchTestRuns('baz'))  # run target
    self.assertEqual([msg2], FetchTestRuns('qux'))  # device build ID
    self.assertEqual([msg2], FetchTestRuns('spam'))  # device product
    self.assertEqual([msg3], FetchTestRuns('ham'))  # test package name
    self.assertEqual([msg3], FetchTestRuns('eggs'))  # test package version
    self.assertEqual([msg3, msg2], FetchTestRuns('common'))

    # Can search for union of multiple values
    self.assertEqual([msg1], FetchTestRuns('foo', 'bar', 'baz'))
    self.assertEqual([msg2], FetchTestRuns('common', 'qux', 'spam'))
    self.assertEqual([msg3], FetchTestRuns('common', 'ham', 'eggs'))
    self.assertEqual([], FetchTestRuns('foo', 'common'))

  def testListSummaries_stateFilter(self):
    # Helper to fetch test runs filtered by state
    def FetchTestRuns(*args):
      state_filters = '&'.join(['state=' + str(state) for state in args])
      res = self.app.get('/_ah/api/mtt/v1/test_runs?' + state_filters)
      self.assertEqual('200 OK', res.status)
      return protojson.decode_message(messages.TestRunSummaryList,
                                      res.body).test_runs

    test = self._createMockTest(name='foo')
    pending_run = self._createMockTestRunSummaries(
        test=test, state=ndb_models.TestRunState.PENDING)
    pending_msg = messages.Convert(pending_run[0], messages.TestRunSummary)
    completed_run_1 = self._createMockTestRunSummaries(
        test=test, state=ndb_models.TestRunState.COMPLETED)
    completed_msg_1 = messages.Convert(completed_run_1[0],
                                       messages.TestRunSummary)
    completed_run_2 = self._createMockTestRunSummaries(
        test=test, state=ndb_models.TestRunState.COMPLETED)
    completed_msg_2 = messages.Convert(completed_run_2[0],
                                       messages.TestRunSummary)

    # Can search for multiple states
    self.assertEqual([completed_msg_2, completed_msg_1, pending_msg],
                     FetchTestRuns(ndb_models.TestRunState.PENDING,
                                   ndb_models.TestRunState.COMPLETED))

    # Can search for a single state
    self.assertEqual([pending_msg],
                     FetchTestRuns(ndb_models.TestRunState.PENDING))
    self.assertEqual([completed_msg_2, completed_msg_1],
                     FetchTestRuns(ndb_models.TestRunState.COMPLETED))

    # Can search for a state with no runs
    self.assertEqual([], FetchTestRuns(ndb_models.TestRunState.ERROR))

  def testGet(self):
    test = self._createMockTest()
    test_run = self._createMockTestRuns(
        test, ['label'], cluster='cluster',
        device_specs=['device_spec'], run_count=10,
        shard_count=100)[0]

    res = self.app.get('/_ah/api/mtt/v1/test_runs/%s' % test_run.key.id())

    self.assertEqual('200 OK', res.status)
    test_run_msg = protojson.decode_message(messages.TestRun, res.body)
    self.assertEqual(str(test.key.id()), test_run_msg.test.id)
    self.assertEqual(test.name, test_run_msg.test.name)
    self.assertEqual(str(test.key.id()), test_run_msg.test_run_config.test_id)
    self.assertEqual(['label'], test_run_msg.labels)
    self.assertEqual('cluster', test_run_msg.test_run_config.cluster)
    self.assertEqual(['device_spec'], test_run_msg.test_run_config.device_specs)
    self.assertEqual(10, test_run_msg.test_run_config.run_count)
    self.assertEqual(100, test_run_msg.test_run_config.shard_count)

  @mock.patch.object(test_kicker, 'CreateTestRun', autospec=True)
  def testNew(self, mock_run_test):
    test = self._createMockTest()
    request = {
        'labels': ['label'],
        'test_run_config': {
            'test_id': str(test.key.id()),
            'cluster': 'cluster',
            'device_specs': ['device_serial:foo', 'device_serial:bar'],
            'run_count': 10,
            'shard_count': 100,
            'max_retry_on_test_failures': 1000,
            'test_resource_objs': [
                {
                    'name': 'bar',
                    'url': 'bar_url'
                },
                {
                    'name': 'zzz',
                    'url': 'zzz_url'
                },
            ],
        },
    }
    test_run = ndb_models.TestRun(
        test=test,
        labels=['label'],
        test_run_config=ndb_models.TestRunConfig(
            test_key=test.key,
            cluster='cluster',
            device_specs=['device_serial:foo', 'device_serial:bar'],
            run_count=10,
            shard_count=100,
            max_retry_on_test_failures=1000))
    test_run.put()
    mock_run_test.return_value = test_run

    res = self.app.post_json('/_ah/api/mtt/v1/test_runs', request)

    mock_run_test.assert_called_with(
        labels=['label'],
        test_run_config=ndb_models.TestRunConfig(
            test_key=test.key,
            cluster='cluster',
            device_specs=['device_serial:foo', 'device_serial:bar'],
            run_count=10,
            shard_count=100,
            max_retry_on_test_failures=1000,
            test_resource_objs=[
                ndb_models.TestResourceObj(name='bar', url='bar_url'),
                ndb_models.TestResourceObj(name='zzz', url='zzz_url'),
            ]),
        rerun_context=None,
        rerun_configs=[]
        )
    self.assertEqual('200 OK', res.status)
    test_run_msg = protojson.decode_message(messages.TestRun, res.body)
    self.assertEqual(
        messages.Convert(test_run, messages.TestRun), test_run_msg)

  @mock.patch.object(test_kicker, 'CreateTestRun', autospec=True)
  def testNew_withRunTarget(self, mock_run_test):
    test = self._createMockTest()
    request = {
        'labels': ['label'],
        'test_run_config': {
            'test_id': str(test.key.id()),
            'cluster': 'cluster',
            'device_specs': ['foo', 'bar'],
            'run_count': 10,
            'shard_count': 100,
            'max_retry_on_test_failures': 1000,
            'test_resource_objs': [
                {
                    'name': 'bar',
                    'url': 'bar_url'
                },
                {
                    'name': 'zzz',
                    'url': 'zzz_url'
                },
            ],
        },
    }
    test_run = ndb_models.TestRun(
        test=test,
        labels=['label'],
        test_run_config=ndb_models.TestRunConfig(
            test_key=test.key,
            cluster='cluster',
            device_specs=['foo', 'bar'],
            run_count=10,
            shard_count=100,
            max_retry_on_test_failures=1000))
    test_run.put()
    mock_run_test.return_value = test_run

    res = self.app.post_json('/_ah/api/mtt/v1/test_runs', request)

    mock_run_test.assert_called_with(
        labels=['label'],
        test_run_config=ndb_models.TestRunConfig(
            test_key=test.key,
            cluster='cluster',
            device_specs=['foo', 'bar'],
            run_count=10,
            shard_count=100,
            max_retry_on_test_failures=1000,
            test_resource_objs=[
                ndb_models.TestResourceObj(name='bar', url='bar_url'),
                ndb_models.TestResourceObj(name='zzz', url='zzz_url'),
            ],
        ),
        rerun_context=None,
        rerun_configs=[],
    )
    self.assertEqual('200 OK', res.status)
    test_run_msg = protojson.decode_message(messages.TestRun, res.body)
    self.assertEqual(messages.Convert(test_run, messages.TestRun), test_run_msg)

  @mock.patch.object(analytics, 'Log')
  @mock.patch.object(test_kicker, 'CreateTestRun', autospec=True)
  def testNew_withRequiredReportId(self, mock_run_test, mock_log):
    test = self._createMockTest()
    build = self._createMockBuild()
    required_report = self._createMockRequiredReport(build.key)
    request = {
        'labels': ['label'],
        'test_run_config': {
            'test_id': str(test.key.id()),
            'cluster': 'cluster',
            'device_specs': ['foo', 'bar'],
            'run_count': 10,
            'shard_count': 100,
            'max_retry_on_test_failures': 1000,
            'test_resource_objs': [
                {'name': 'bar', 'url': 'bar_url'},
                {'name': 'zzz', 'url': 'zzz_url'},
            ],
        },
        'required_report_id': str(required_report.key.id()),
    }
    test_run = ndb_models.TestRun(
        test=test,
        labels=['label'],
        test_run_config=ndb_models.TestRunConfig(
            test_key=test.key,
            cluster='cluster',
            device_specs=['foo', 'bar'],
            run_count=10,
            shard_count=100,
            max_retry_on_test_failures=1000,
        ),
    )
    test_run.put()
    mock_run_test.return_value = test_run

    res = self.app.post_json('/_ah/api/mtt/v1/test_runs', request)

    mock_run_test.assert_called_with(
        labels=['label'],
        test_run_config=ndb_models.TestRunConfig(
            test_key=test.key,
            cluster='cluster',
            device_specs=['foo', 'bar'],
            run_count=10,
            shard_count=100,
            max_retry_on_test_failures=1000,
            test_resource_objs=[
                ndb_models.TestResourceObj(name='bar', url='bar_url'),
                ndb_models.TestResourceObj(name='zzz', url='zzz_url'),
            ]),
        rerun_context=None,
        rerun_configs=[]
        )
    self.assertEqual('200 OK', res.status)
    test_run_msg = protojson.decode_message(messages.TestRun, res.body)
    self.assertEqual(
        messages.Convert(test_run, messages.TestRun), test_run_msg)
    required_report = required_report.key.get()
    self.assertEqual(required_report.test_run_key, test_run.key)
    mock_log.assert_called_with(
        analytics.BUILD_CATEGORY,
        analytics.RUN_TEST_ACTION,
        label=str(required_report.type),
    )

  @mock.patch.object(test_run_manager, 'SetTestRunState', autospec=True)
  def testCancel(self, mock_set_test_run_state):
    test = self._createMockTest()
    test_run = self._createMockTestRuns(test)[0]

    res = self.app.post_json(
        '/_ah/api/mtt/v1/test_runs/%s/cancel' % test_run.key.id())

    mock_set_test_run_state.assert_called_with(
        test_run_id=test_run.key.id(),
        state=ndb_models.TestRunState.CANCELED)
    self.assertEqual('204 No Content', res.status)

  @mock.patch.object(file_util.FileHandle, 'Get')
  @mock.patch.object(sql_models.db, 'Session')
  @mock.patch.object(env, 'STORAGE_PATH', '/root')
  def testDeleteMulti(self, _, mock_handle_factory):
    """Tests that test runs can be deleted."""
    mock_output_dir = mock.MagicMock()
    mock_output_zip = mock.MagicMock()
    mock_handle_factory.side_effect = [mock_output_dir, mock_output_zip]

    test = self._createMockTest()
    test_run = self._createMockTestRuns(
        test,
        state=ndb_models.TestRunState.COMPLETED,
        output_path='/test_runs/test_run_id/output/')[0]

    self.app.delete(
        '/_ah/api/mtt/v1/test_runs',
        params={'test_run_ids': [test_run.key.id()]})
    self.assertIsNone(test_run.key.get())
    mock_handle_factory.assert_has_calls(
        [mock.call('file:///root/test_runs/test_run_id'),
         mock.call('file:///root/test_runs/test_run_id.zip')])
    mock_output_dir.DeleteDir.assert_called_once()
    mock_output_zip.Delete.assert_called_once()

  @mock.patch.object(sql_models.db, 'Session')
  def testDeleteMulti_multiple(self, _):
    """Tests that multiple runs can be deleted and failed ones are skipped."""
    test = self._createMockTest()
    canceled_run = self._createMockTestRuns(
        test, state=ndb_models.TestRunState.CANCELED)[0]
    queued_run = self._createMockTestRuns(
        test, state=ndb_models.TestRunState.QUEUED)[0]
    running_run = self._createMockTestRuns(
        test, state=ndb_models.TestRunState.RUNNING)[0]

    # CANCELED run is deleted, but active and unknown runs are skipped.
    res = self.app.delete(
        '/_ah/api/mtt/v1/test_runs',
        params={'test_run_ids': [canceled_run.key.id(),
                                 queued_run.key.id(),
                                 running_run.key.id(),
                                 'fake_id']}, expect_errors=True)
    self.assertIsNone(canceled_run.key.get())
    self.assertIsNotNone(queued_run.key.get())
    self.assertIsNotNone(running_run.key.get())
    self.assertEqual('400 Bad Request', res.status)

  def testTailOutputFile_runNotFound(self):
    # unknown test run ID
    res = self.app.get(
        '/_ah/api/mtt/v1/test_runs/%s/output' % 666,
        params={'attempt_id': 'attempt', 'path': 'path'},
        expect_errors=True)
    # throws if test run not found
    self.assertEqual('404 Not Found', res.status)

  @mock.patch.object(tfc_client, 'GetAttempt')
  def testTailOutputFile_attemptNotFound(self, mock_attempt):
    # fails to find latest command attempt
    mock_attempt.return_value = None

    test = self._createMockTest()
    test_run = self._createMockTestRuns(test)[0]
    res = self.app.get(
        '/_ah/api/mtt/v1/test_runs/%s/output' % test_run.key.id(),
        params={'attempt_id': 'attempt', 'path': 'path'},
        expect_errors=True)
    # throws if attempt not found
    self.assertEqual('404 Not Found', res.status)

  @mock.patch.object(file_util, 'TailFile')
  @mock.patch.object(tfc_client, 'GetAttempt')
  def testTailOutputFile_fileNotFound(self, mock_attempt, mock_tail):
    # latest attempt is RUNNING, but file not found
    mock_attempt.return_value = self._createAttempt(CommandState.RUNNING)
    mock_tail.return_value = None

    test = self._createMockTest()
    test_run = self._createMockTestRuns(test)[0]
    res = self.app.get(
        '/_ah/api/mtt/v1/test_runs/%s/output' % test_run.key.id(),
        params={'attempt_id': 'attempt', 'path': 'path'},
        expect_errors=True)
    # throws if file not found
    self.assertEqual('404 Not Found', res.status)

  @mock.patch.object(file_util, 'ReadFile')
  @mock.patch.object(file_util, 'TailFile')
  @mock.patch.object(tfc_client, 'GetAttempt')
  def testTailOutputFile_noOffset(self, mock_attempt, mock_tail, mock_read):
    # latest attempt is RUNNING and end of file returned
    mock_attempt.return_value = self._createAttempt(CommandState.RUNNING)
    mock_tail.return_value = file_util.FileSegment(123, [b'hello', b'world'])

    test = self._createMockTest()
    test_run = self._createMockTestRuns(test)[0]
    res = self.app.get(
        '/_ah/api/mtt/v1/test_runs/%s/output' % test_run.key.id(),
        params={'attempt_id': 'attempt', 'path': 'path'})

    # will tail file if called without offset
    mock_read.assert_not_called()
    mock_tail.assert_called()

    # file segment is sent back
    file_segment = protojson.decode_message(messages.FileSegment, res.body)
    expected = messages.FileSegment(offset=123, length=10,
                                    lines=['hello', 'world'])
    self.assertEqual(expected, file_segment)

  @mock.patch.object(file_util, 'ReadFile')
  @mock.patch.object(file_util, 'TailFile')
  @mock.patch.object(tfc_client, 'GetAttempt')
  def testTailOutputFile_withOffset(self, mock_attempt, mock_tail, mock_read):
    # latest attempt is RUNNING and file read
    mock_attempt.return_value = self._createAttempt(CommandState.RUNNING)
    mock_read.return_value = file_util.FileSegment(123, [b'hello', b'world'])

    test = self._createMockTest()
    test_run = self._createMockTestRuns(test)[0]
    res = self.app.get(
        '/_ah/api/mtt/v1/test_runs/%s/output' % test_run.key.id(),
        params={'attempt_id': 'attempt', 'path': 'path', 'offset': 123})

    # will read file if called with offset
    mock_read.assert_called_with(mock.ANY, offset=123, length=mock.ANY)
    mock_tail.assert_not_called()

    # file segment is sent back
    file_segment = protojson.decode_message(messages.FileSegment, res.body)
    expected = messages.FileSegment(offset=123, length=10,
                                    lines=['hello', 'world'])
    self.assertEqual(expected, file_segment)

  @mock.patch.object(tfc_client, 'GetRequest')
  def testGetMetadata(self, mock_get_request):
    # request w/o attempts
    mock_get_request.return_value = mock.MagicMock()

    test = self._createMockTest()
    test_run = self._createMockTestRuns(test=test)[0]
    test_run.request_id = 'request'
    test_run.put()
    res = self.app.get(
        '/_ah/api/mtt/v1/test_runs/%s/metadata' % test_run.key.id())

    # metadata is sent back w/o attempts
    metadata = protojson.decode_message(messages.TestRunMetadataList, res.body)
    expected = messages.TestRunMetadataList(
        test_runs=[
            messages.TestRunMetadata(
                test_run=messages.Convert(test_run, messages.TestRun))
        ],
        server_version=env.VERSION)
    self.assertEqual(expected, metadata)

  def testGetMetadata_runNotFound(self):
    # unknown test run ID
    res = self.app.get('/_ah/api/mtt/v1/test_runs/%s/metadata' % 666,
                       expect_errors=True)
    # throws if test run not found
    self.assertEqual('404 Not Found', res.status)

  @mock.patch.object(tfc_client, 'GetRequest')
  def testGetMetadata_returnsCompletedAttempts(self, mock_get_request):
    # request w/ RUNNING and COMPLETED attempts
    mock_request = mock.MagicMock()
    mock_get_request.return_value = mock_request
    running_attempt = self._createAttempt(CommandState.RUNNING)
    completed_attempt = self._createAttempt(CommandState.COMPLETED)
    mock_request.command_attempts = [running_attempt, completed_attempt]

    test = self._createMockTest()
    test_run = self._createMockTestRuns(test=test)[0]
    test_run.request_id = 'request'
    test_run.put()
    res = self.app.get(
        '/_ah/api/mtt/v1/test_runs/%s/metadata' % test_run.key.id())

    # metadata is sent back w/ only COMPLETED attempts
    metadata = protojson.decode_message(messages.TestRunMetadataList, res.body)
    expected = messages.TestRunMetadataList(
        test_runs=[
            messages.TestRunMetadata(
                test_run=messages.Convert(test_run, messages.TestRun),
                command_attempts=[completed_attempt])
        ],
        server_version=env.VERSION)
    self.assertEqual(expected, metadata)

  @mock.patch.object(tfc_client, 'GetRequest')
  def testGetMetadata_ancestry(self, mock_get_request):
    mock_get_request.return_value = mock.MagicMock()
    test = self._createMockTest()

    # create hierarchy of test_runs
    child, parent, grandparent = self._createMockTestRuns(test=test, count=3)  
    child.prev_test_run_key = parent.key
    child.prev_test_context = ndb_models.TestContextObj()
    child.put()
    parent.prev_test_run_key = grandparent.key
    parent.prev_test_context = ndb_models.TestContextObj()
    parent.put()

    res = self.app.get('/_ah/api/mtt/v1/test_runs/%s/metadata' % child.key.id())

    # metadata is sent back w/ ordered ancestry information
    metadata = protojson.decode_message(messages.TestRunMetadataList, res.body)
    expected = messages.TestRunMetadataList(
        test_runs=[
            messages.TestRunMetadata(
                test_run=messages.Convert(child, messages.TestRun)),
            messages.TestRunMetadata(
                test_run=messages.Convert(parent, messages.TestRun)),
            messages.TestRunMetadata(
                test_run=messages.Convert(grandparent, messages.TestRun))
        ],
        server_version=env.VERSION)
    self.assertEqual(expected, metadata)

  @mock.patch.object(file_util, 'OpenFile')
  def testGetMetadata_remoteAncestry(self, mock_open_file):
    # create hierarchy of test_runs
    test = self._createMockTest()
    child, parent = self._createMockTestRuns(test=test, count=2)  

    with tempfile.NamedTemporaryFile(suffix='.zip') as tmp_stream:
      # write parent metadata to a temporary zip file
      with zipfile.ZipFile(tmp_stream, 'w') as context_file:
        res = self.app.get('/_ah/api/mtt/v1/test_runs/%s/metadata' %
                           parent.key.id())
        context_file.writestr('mtt.json', res.body)
      tmp_stream.seek(0)
      mock_open_file.return_value = tmp_stream

      # mark child as a remote return
      child.prev_test_context = ndb_models.TestContextObj(test_resources=[
          ndb_models.TestResourceObj(name='mtt.json', url='url')
      ])
      child.put()

      res = self.app.get('/_ah/api/mtt/v1/test_runs/%s/metadata' %
                         child.key.id())

      # metadata is sent back w/ ordered ancestry information
      metadata = protojson.decode_message(messages.TestRunMetadataList,
                                          res.body)
      expected = messages.TestRunMetadataList(
          test_runs=[
              messages.TestRunMetadata(
                  test_run=messages.Convert(child, messages.TestRun)),
              messages.TestRunMetadata(
                  test_run=messages.Convert(parent, messages.TestRun))
          ],
          server_version=env.VERSION)
      self.assertEqual(expected, metadata)


if __name__ == '__main__':
  absltest.main()
