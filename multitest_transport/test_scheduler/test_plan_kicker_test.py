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

"""Unit tests for test_plan_kicker module."""
import datetime
import json
import os.path
from unittest import mock

from absl.testing import absltest
from tradefed_cluster import testbed_dependent_test


from multitest_transport.models import ndb_models
from multitest_transport.test_scheduler import test_kicker
from multitest_transport.test_scheduler import test_plan_kicker
from multitest_transport.test_scheduler import test_run_manager

GAE_CONFIGS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), 'gae_configs')


class TestPlanKickerTest(testbed_dependent_test.TestbedDependentTest):

  @mock.patch.object(test_plan_kicker, '_GetCurrentTime', autospec=True)
  def testScheduleCronKick(self, get_current_time):
    """Tests that test plans can be scheduled."""
    # Create test plan that runs every day at midnight
    test_plan = ndb_models.TestPlan(name='test_plan', cron_exp='0 0 * * *')
    test_plan.put()
    test_plan_id = test_plan.key.id()
    # Current time is 12:30 AM UTC and next run time is the following midnight
    get_current_time.return_value = datetime.datetime(1970, 1, 1, 0, 30, 0)
    next_run_time = datetime.datetime(1970, 1, 2, 0, 0, 0).replace(
        tzinfo=datetime.timezone.utc
    )

    test_plan_kicker.ScheduleCronKick(test_plan_id)

    tasks = self.mock_task_scheduler.GetTasks(
        queue_names=[test_plan_kicker.TEST_PLAN_KICKER_QUEUE])
    self.assertLen(tasks, 1)
    self.assertEqual(next_run_time, tasks[0].eta)
    data = json.loads(tasks[0].payload)
    self.assertEqual(test_plan_id, data['test_plan_id'])

  @mock.patch.object(test_plan_kicker, '_GetCurrentTime', autospec=True)
  def testScheduleCronKick_withTimezone(self, get_current_time):
    """Tests that test plans can be scheduled relative to a timezone."""
    # Create test plan that runs every day at midnight in PT
    test_plan = ndb_models.TestPlan(
        name='test_plan',
        cron_exp='0 0 * * *',
        cron_exp_timezone='America/Los_Angeles')
    test_plan.put()
    # Current time is 12:30 AM UTC and next run time is midnight PT (8 AM UTC)
    get_current_time.return_value = datetime.datetime(1970, 1, 1, 0, 30, 0)
    next_run_time = datetime.datetime(1970, 1, 1, 8, 0, 0).replace(
        tzinfo=datetime.timezone.utc
    )

    test_plan_kicker.ScheduleCronKick(test_plan.key.id())

    tasks = self.mock_task_scheduler.GetTasks(
        queue_names=[test_plan_kicker.TEST_PLAN_KICKER_QUEUE])
    self.assertLen(tasks, 1)
    self.assertEqual(next_run_time, tasks[0].eta)

  def testScheduleCronKick_noCronExpression(self):
    """Tests that test plan without cron expressions do not get scheduled."""
    test_plan = ndb_models.TestPlan(name='test_plan')
    test_plan.put()
    test_plan_kicker.ScheduleCronKick(test_plan.key.id())
    # No tasks scheduled
    tasks = self.mock_task_scheduler.GetTasks(
        queue_names=[test_plan_kicker.TEST_PLAN_KICKER_QUEUE])
    self.assertEmpty(tasks)

  def testScheduleCronKick_invalidTimezone(self):
    """Tests that test plan with invalid timezones do not get scheduled."""
    test_plan = ndb_models.TestPlan(
        name='test_plan', cron_exp='0 0 * * *', cron_exp_timezone='INVALID')
    test_plan.put()
    test_plan_kicker.ScheduleCronKick(test_plan.key.id())
    # No tasks scheduled
    tasks = self.mock_task_scheduler.GetTasks(
        queue_names=[test_plan_kicker.TEST_PLAN_KICKER_QUEUE])
    self.assertEmpty(tasks)

  @mock.patch.object(test_kicker, 'CreateTestRun', autospec=True)
  def testKickTestPlan(self, create_test_run):
    """Tests that a test plan can be kicked off."""
    test = ndb_models.Test(id='test_id')
    test_device_action = ndb_models.DeviceAction(id='test_device_action')
    test_run_action = ndb_models.TestRunAction(id='test_run_action')
    config1 = ndb_models.TestRunConfig(
        test_key=test.key,
        cluster='cluster',
        run_target='run_target',
        before_device_action_keys=[test_device_action.key],
        test_run_action_refs=[
            ndb_models.TestRunActionRef(action_key=test_run_action.key),
        ],
        test_resource_objs=[
            ndb_models.TestResourceObj(name='res_1', url='url_1')])

    config2 = ndb_models.TestRunConfig(
        test_key=test.key,
        cluster='cluster2',
        run_target='run_target2',
        before_device_action_keys=[test_device_action.key],
        test_run_action_refs=[
            ndb_models.TestRunActionRef(action_key=test_run_action.key),
        ],
        test_resource_objs=[
            ndb_models.TestResourceObj(name='res_2', url='url_2')])

    config_list = ndb_models.TestRunConfigList(
        test_run_configs=[config1, config2])
    # Create a test plan with multiple resources and actions
    test_plan = ndb_models.TestPlan(
        name='test_plan',
        labels=['label'],
        cron_exp='0 0 * * *',
        test_run_sequences=[config_list]
        )
    test_plan.put()
    # Test run will be created successfully
    test_run = ndb_models.TestRun(id='test_run_id')
    create_test_run.return_value = test_run

    executed = test_plan_kicker.KickTestPlan(test_plan.key.id())
    self.assertTrue(executed)

    # Test run is created with the right test and test plan components
    create_test_run.assert_called_with(
        labels=['label'],
        test_plan_key=test_plan.key,
        test_run_config=config1,
        rerun_configs=[config2],
        )
    # Test run key is stored in the test plan status
    status = ndb_models.TestPlanStatus.query(ancestor=test_plan.key).get()
    self.assertEqual(status.last_run_keys, [test_run.key])

  @mock.patch.object(test_run_manager, 'SetTestRunState', autospec=True)
  @mock.patch.object(test_kicker, 'CreateTestRun', autospec=True)
  def testKickTestPlan_withError(self, create_test_run, set_test_run_state):
    """Tests that errors are handled when kicking off a test plan."""
    test = ndb_models.Test(id='test_id')
    test_run_config = ndb_models.TestRunConfig(
        test_key=test.key, cluster='cluster', run_target='run_target')
    config_list = ndb_models.TestRunConfigList(
        test_run_configs=[test_run_config])
    test_plan = ndb_models.TestPlan(
        name='test_plan', test_run_sequences=[config_list, config_list])
    test_plan.put()
    # First test run created successfully, but second fails even with retries
    test_run = ndb_models.TestRun(id='test_run_id')
    create_test_run.side_effect = (
        [test_run] +
        test_plan_kicker.MAX_RETRY_COUNT * [RuntimeError('Test error')])

    # Retries a few times before canceling test run and raising exception
    with self.assertRaisesRegex(RuntimeError, 'Test error'):
      test_plan_kicker.KickTestPlan(test_plan.key.id())
    self.assertEqual(create_test_run.call_count,
                     1 + test_plan_kicker.MAX_RETRY_COUNT)
    set_test_run_state.assert_called_once_with('test_run_id',
                                               ndb_models.TestRunState.CANCELED)
    # Stores the canceled test run key and the error message
    status = ndb_models.TestPlanStatus.query(ancestor=test_plan.key).get()
    self.assertEqual(status.last_run_keys, [test_run.key])
    self.assertEqual(status.last_run_error, 'Test error')

  @mock.patch.object(test_kicker, 'CreateTestRun', autospec=True)
  def testKickTestPlan_withRetry(self, create_test_run):
    """Tests that a test plan kick operations can be retried."""
    test = ndb_models.Test(id='test_id')
    test_run_config = ndb_models.TestRunConfig(
        test_key=test.key, cluster='cluster', run_target='run_target')
    config_list = ndb_models.TestRunConfigList(
        test_run_configs=[test_run_config])
    test_plan = ndb_models.TestPlan(
        name='test_plan', test_run_sequences=[config_list])
    test_plan.put()
    # First test run creation fails, but second attempt succeeds
    test_run = ndb_models.TestRun(id='test_run_id')
    create_test_run.side_effect = [RuntimeError('test_run_error'), test_run]

    executed = test_plan_kicker.KickTestPlan(test_plan.key.id())
    self.assertTrue(executed)

    # Create test run operation retried until successful
    self.assertEqual(create_test_run.call_count, 2)
    status = ndb_models.TestPlanStatus.query(ancestor=test_plan.key).get()
    # Test run key stored and error message is empty
    self.assertEqual(status.last_run_keys, [test_run.key])
    self.assertIsNone(status.last_run_error)

  def testKickTestPlan_notFound(self):
    """Tests that a test plan kick is skipped if the plan is not found."""
    test_plan = ndb_models.TestPlan(id='unknown')
    executed = test_plan_kicker.KickTestPlan(test_plan.key.id())
    self.assertFalse(executed)

  def testKickTestPlan_invalidTask(self):
    """Tests that a test plan kick is skipped if the task is invalid."""
    test_plan = ndb_models.TestPlan(name='test_plan')
    test_plan.put()
    ndb_models.TestPlanStatus(
        parent=test_plan.key, next_run_task_name='task_name').put()

    executed = test_plan_kicker.KickTestPlan(
        test_plan.key.id(), task_name='invalid_task_name')
    self.assertFalse(executed)

  @mock.patch.object(test_plan_kicker, 'ScheduleCronKick', autospec=True)
  @mock.patch.object(test_plan_kicker, '_GetCurrentTime', autospec=True)
  def testCheckTestPlanNextRuns(self, get_current_time, schedule_cron_kick):
    now = datetime.datetime(1970, 1, 1, 0, 30, 0)
    get_current_time.return_value = now
    test_plan = ndb_models.TestPlan(name='foo', cron_exp='0 0 * * *')
    test_plan.put()
    test_plan_status = ndb_models.TestPlanStatus(
        parent=test_plan.key,
        next_run_time=datetime.datetime(1970, 1, 1, 0, 0, 0))
    test_plan_status.put()

    test_plan_kicker.CheckTestPlanNextRuns()

    schedule_cron_kick.assert_called_with(test_plan.key.id(), next_run_time=now)


if __name__ == '__main__':
  absltest.main()
