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

"""Unit tests for test_scheduler module."""
import datetime
from unittest import mock
import uuid

from absl.testing import absltest
from tradefed_cluster import testbed_dependent_test
from tradefed_cluster.util import ndb_shim as ndb


from multitest_transport.models import messages as mtt_messages
from multitest_transport.models import ndb_models
from multitest_transport.test_scheduler import test_kicker
from multitest_transport.test_scheduler import test_scheduler


class TestSchedulerTest(testbed_dependent_test.TestbedDependentTest):
  """Unit tests for test_scheduler module."""

  def _CreateMockTestRun(self, config, state=None, create_time=None):
    """Creates a test run.

    Args:
      config: a test run config
      state: a test run state.
      create_time: a test run create time.
    Returns:
      a ndb_models.TestRun object.
    """
    test = ndb_models.Test(name='test', command='command')
    test.put()
    test_run_config = ndb_models.TestRunConfig(
        test_key=test.key, cluster='cluster', run_target='run_target')
    test_resources = [
        ndb_models.TestResourceObj(name='foo', url='http://foo_origin_url'),
        ndb_models.TestResourceObj(name='bar', url='https://bar_origin_url'),
    ]
    test_run = ndb_models.TestRun(
        labels=['label'],
        test=test,
        test_run_config=test_run_config,
        test_resources=test_resources,
        state=state or ndb_models.TestRunState.PENDING,
        create_time=create_time)
    test_run.key = ndb.Key(ndb_models.TestRun, str(uuid.uuid4()))
    test_run.put()
    return test_run

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

  def _CreateMockTestRunSequence(self,
                                 sequence_id='sequence_id',
                                 configs=None,
                                 state=ndb_models.TestRunSequenceState.RUNNING):
    """Create a mock ndb_models.TestRunSequence object."""
    sequence = ndb_models.TestRunSequence(
        state=state,
        test_run_configs=configs or [],
        finished_test_run_ids=[],
        )
    sequence.key = ndb.Key(ndb_models.TestRunSequence, sequence_id)
    sequence.put()
    return sequence

  @mock.patch.object(test_kicker, 'EnqueueTestRun')
  def testCheckPendingTestRuns_less_than_24hr(self, mock_enqueue_test_run):
    test = self._CreateMockTest()
    test_run = self._CreateMockTestRun(
        config=self._CreateMockTestRunConfig(test),
        state=ndb_models.TestRunState.PENDING,
        create_time=datetime.datetime.utcnow())
    test_scheduler.CheckUnfinishedTestRuns()
    mock_enqueue_test_run.assert_called_with(test_run.key.id())

  def testCheckPendingTestRuns_more_than_24hr(self):
    test = self._CreateMockTest()
    create_time = datetime.datetime.utcnow() - datetime.timedelta(
        seconds=(test_scheduler._PENDING_TEST_RUN_TTL + 1))
    test_run_id = self._CreateMockTestRun(
        config=self._CreateMockTestRunConfig(test),
        state=ndb_models.TestRunState.PENDING,
        create_time=create_time).key.id()
    test_scheduler.CheckUnfinishedTestRuns()
    test_run = ndb_models.TestRun.get_by_id(test_run_id)
    self.assertEqual(ndb_models.TestRunState.CANCELED, test_run.state)

  @mock.patch.object(test_kicker, 'EnqueueTestRun')
  def testCheckRunningTestRuns_less_than_7days(self, mock_enqueue_test_run):
    test = self._CreateMockTest()
    test_run = self._CreateMockTestRun(
        config=self._CreateMockTestRunConfig(test),
        state=ndb_models.TestRunState.RUNNING,
        create_time=datetime.datetime.utcnow())
    test_scheduler.CheckUnfinishedTestRuns()
    mock_enqueue_test_run.assert_called_with(test_run.key.id())

  def testCheckRunningTestRuns_more_than_7days(self):
    test = self._CreateMockTest()
    create_time = datetime.datetime.utcnow() - datetime.timedelta(
        seconds=(test_scheduler._RUNNING_TEST_RUN_TTL + 1))
    test_run_id = self._CreateMockTestRun(
        config=self._CreateMockTestRunConfig(test),
        state=ndb_models.TestRunState.RUNNING,
        create_time=create_time).key.id()
    test_scheduler.CheckUnfinishedTestRuns()
    test_run = ndb_models.TestRun.get_by_id(test_run_id)
    self.assertEqual(ndb_models.TestRunState.CANCELED, test_run.state)

  @mock.patch.object(test_kicker, 'CreateTestRun')
  def testScheduleNextTestRun(self, mock_create_test_run):
    test = self._CreateMockTest()
    config1 = self._CreateMockTestRunConfig(test, 'rt1')
    config2 = self._CreateMockTestRunConfig(test, 'rt2;rt3')
    run1 = self._CreateMockTestRun(config1)
    sequence = self._CreateMockTestRunSequence(
        'sequence_id', [config1, config2])
    sequence_id = sequence.key.id()

    run1_id = str(run1.key.id())
    config2.prev_test_run_key = run1.key
    rerun_context = mtt_messages.RerunContext()
    rerun_context.test_run_id = run1_id

    # Schedules next run successfully
    test_scheduler.ScheduleNextTestRun(sequence_id, run1.key)
    mock_create_test_run.assert_called_with(
        labels=['label'],
        test_run_config=config2,
        rerun_context=rerun_context,
        rerun_configs=[],
        sequence_id=sequence_id)

    updated_sequence = sequence.key.get()
    self.assertEqual(updated_sequence.finished_test_run_ids, [run1_id])
    self.assertEqual(updated_sequence.state,
                     ndb_models.TestRunSequenceState.RUNNING)

    # Ignores a call with a duplicate previous run id
    test_scheduler.ScheduleNextTestRun(sequence_id, run1.key)
    mock_create_test_run.assert_called_once()  # Only called the first time

    updated_sequence = sequence.key.get()
    self.assertEqual(updated_sequence.finished_test_run_ids, [run1_id])
    self.assertEqual(updated_sequence.state,
                     ndb_models.TestRunSequenceState.RUNNING)

    # Does not schedule another run when no more configs left
    run2 = self._CreateMockTestRun(config2)
    run2_id = str(run2.key.id())
    test_scheduler.ScheduleNextTestRun(sequence_id, run2.key)

    mock_create_test_run.assert_called_once()  # Only called the first time
    updated_sequence2 = sequence.key.get()
    self.assertEqual(updated_sequence2.finished_test_run_ids,
                     [run1_id, run2_id])
    self.assertEqual(updated_sequence2.state,
                     ndb_models.TestRunSequenceState.COMPLETED)

  @mock.patch.object(test_kicker, 'CreateTestRun')
  def testScheduleNextTestRun_error(self, mock_create_test_run):
    test = self._CreateMockTest()
    config1 = self._CreateMockTestRunConfig(test, 'rt1')
    config2 = self._CreateMockTestRunConfig(test, 'rt2;rt3')
    run1 = self._CreateMockTestRun(config1, ndb_models.TestRunState.ERROR)
    sequence = self._CreateMockTestRunSequence(
        'sequence_id', [config1, config2])
    sequence_id = sequence.key.id()

    # Schedules next run successfully
    test_scheduler.ScheduleNextTestRun(sequence_id, run1.key)
    mock_create_test_run.assert_not_called()

    updated_sequence = sequence.key.get()
    self.assertEqual(updated_sequence.finished_test_run_ids, [run1.key.id()])
    self.assertEqual(updated_sequence.state,
                     ndb_models.TestRunSequenceState.ERROR)

  @mock.patch.object(test_kicker, 'CreateTestRun')
  def testScheduleNextTestRun_canceled(self, mock_create_test_run):
    test = self._CreateMockTest()
    config1 = self._CreateMockTestRunConfig(test, 'rt1')
    config2 = self._CreateMockTestRunConfig(test, 'rt2;rt3')
    run1 = self._CreateMockTestRun(config1, ndb_models.TestRunState.CANCELED)
    sequence = self._CreateMockTestRunSequence(
        'sequence_id', [config1, config2])
    sequence_id = sequence.key.id()

    # Schedules next run successfully
    test_scheduler.ScheduleNextTestRun(sequence_id, run1.key)
    mock_create_test_run.assert_not_called()

    updated_sequence = sequence.key.get()
    self.assertEqual(updated_sequence.finished_test_run_ids, [run1.key.id()])
    self.assertEqual(updated_sequence.state,
                     ndb_models.TestRunSequenceState.CANCELED)

if __name__ == '__main__':
  absltest.main()
