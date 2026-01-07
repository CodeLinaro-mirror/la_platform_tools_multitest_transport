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

"""Tests for test_plan_api."""
from unittest import mock
import uuid

from absl.testing import absltest
from protorpc import protojson


from multitest_transport.api import api_test_util
from multitest_transport.api import test_plan_api
from multitest_transport.models import build
from multitest_transport.models import messages
from multitest_transport.models import ndb_models
from multitest_transport.plugins import base
from multitest_transport.test_scheduler import test_plan_kicker
from multitest_transport.test_scheduler import test_scheduler

HTTP_STATUS_400 = '400 Bad Request'
HTTP_STATUS_404 = '404 Not Found'


def _CreateMockTestPlan(name, cron_exp='0 * * * *', test_run_sequences=None):
  """Creates a mock test plan."""
  test_plan = ndb_models.TestPlan(name=name, cron_exp=cron_exp,
                                  test_run_sequences=test_run_sequences or [])
  test_plan.put()
  return test_plan


class TestPlanApiTest(api_test_util.TestCase):

  def _VerifyTestPlan(self, data, test_plan):
    """Verifies whether a test plan is same as the given data object."""
    self.assertEqual(data['name'], test_plan.name)
    self.assertEqual(
        len(data['test_run_sequences']), len(test_plan.test_run_sequences))

  def setUp(self):
    super(TestPlanApiTest, self).setUp(test_plan_api.TestPlanApi)
    self.mock_test = ndb_models.Test(name='mock_test', command='command')
    self.mock_test.put()
    self.mock_test_id = str(self.mock_test.key.id())
    self.mock_build_channel = ndb_models.BuildChannelConfig(
        id=str(uuid.uuid4()), name='mock_build_channel',
        provider_name='mock_build_provider')
    self.mock_build_channel.put()
    self.mock_build_channel_id = self.mock_build_channel.key.id()
    self.mock_device_action = ndb_models.DeviceAction(name='mock_device_action')
    self.mock_device_action.put()
    self.mock_device_action_id = str(self.mock_device_action.key.id())

    build_item = base.BuildItem(name='zz', path='/foo/bar/zz', is_file=True)
    self.mock_test_resource_url = build.BuildUrl(self.mock_build_channel_id,
                                                 build_item)

  def testList(self):
    """Tests test_plans.list API."""
    res = self.app.get('/_ah/api/mtt/v1/test_plans')
    self.assertIsNotNone(res)

  @mock.patch.object(test_scheduler, 'ScheduleTestPlanCronJob', autospec=True)
  def testCreate(self, mock_schedule_test_plan_cron_job):
    """Tests test_plans.create API."""
    config = {
        'test_id': self.mock_test_id,
        'cluster': 'cluster',
        'run_target': 'run_target',
        'test_resource_objs': [
            {
                'name': 'bar',
                'url': self.mock_test_resource_url,
            }
        ],
        'before_device_action_ids': [
            self.mock_device_action_id,
        ]
    }
    data = {
        'name': 'foo',
        'cron_exp': '0 * * * *',
        'test_run_sequences': [{'test_run_configs': [config]}],
    }

    res = self.app.post_json('/_ah/api/mtt/v1/test_plans', data)

    msg = protojson.decode_message(messages.TestPlan, res.body)
    test_plan_id = int(msg.id)
    test_plan = ndb_models.TestPlan.get_by_id(test_plan_id)
    self._VerifyTestPlan(data, test_plan)
    mock_schedule_test_plan_cron_job.assert_called_with(test_plan_id)

  def testCreate_invalidData(self):
    """Tests test_plans.create API with invalid data."""
    data = {
        'name': 'foo',
        'test_run_sequences': [],
    }
    test_data = dict(data)
    test_data['cron_exp'] = 'invalid'
    res = self.app.post_json(
        '/_ah/api/mtt/v1/test_plans', test_data, expect_errors=True)
    self.assertEqual(HTTP_STATUS_400, res.status)

    test_data = dict(data)
    test_data['test_run_sequences'].append({
        'test_run_configs': [{'test_id': 'invalid'}],
    })
    res = self.app.post_json(
        '/_ah/api/mtt/v1/test_plans', test_data, expect_errors=True)
    self.assertEqual(HTTP_STATUS_400, res.status)

  def testGet(self):
    """Tests test_plans.get API."""
    test_plan = _CreateMockTestPlan('foo')

    res = self.app.get('/_ah/api/mtt/v1/test_plans/%s' % test_plan.key.id())
    msg = protojson.decode_message(messages.TestPlan, res.body)
    self.assertEqual(messages.Convert(test_plan, messages.TestPlan), msg)

  def testGet_default(self):
    """Tests test_plans.get with default test plan ID."""
    res = self.app.get('/_ah/api/mtt/v1/test_plans/%s' % 0)
    msg = protojson.decode_message(messages.TestPlan, res.body)
    self.assertIsNotNone(msg)

  def testGet_notFound(self):
    """Tests test_plans.get with unknown ID."""
    res = self.app.get('/_ah/api/mtt/v1/test_plans/%s' % 666,
                       expect_errors=True)
    self.assertEqual(HTTP_STATUS_404, res.status)

  @mock.patch.object(test_scheduler, 'ScheduleTestPlanCronJob', autospec=True)
  def testBatchUpdate(self, mock_schedule_test_plan_cron_job):
    """Tests test_plans.batch_update API."""
    test_plan1 = _CreateMockTestPlan('foo')
    test_plan2 = _CreateMockTestPlan('bar')
    test_plan1_id = test_plan1.key.id()
    test_plan2_id = test_plan2.key.id()

    data = {
        'test_plans': [
            {'id': str(test_plan1_id), 'name': 'foo_updated'},
            {'id': str(test_plan2_id), 'name': 'bar_updated'},
        ]
    }

    res = self.app.post_json('/_ah/api/mtt/v1/test_plans/batch_update', data)

    msg = protojson.decode_message(messages.TestPlanList, res.body)
    self.assertLen(msg.test_plans, 2)
    self.assertEqual(msg.test_plans[0].name, 'foo_updated')
    self.assertEqual(msg.test_plans[1].name, 'bar_updated')

    updated_test_plan1 = ndb_models.TestPlan.get_by_id(test_plan1_id)
    updated_test_plan2 = ndb_models.TestPlan.get_by_id(test_plan2_id)
    self.assertEqual(updated_test_plan1.name, 'foo_updated')
    self.assertEqual(updated_test_plan2.name, 'bar_updated')

    mock_schedule_test_plan_cron_job.assert_has_calls([
        mock.call(test_plan1_id),
        mock.call(test_plan2_id),
    ], any_order=True)

  @mock.patch.object(test_scheduler, 'ScheduleTestPlanCronJob', autospec=True)
  def testUpdate(self, mock_schedule_test_plan_cron_job):
    """Tests test_plans.update API with invalid data."""
    test_plan = _CreateMockTestPlan('foo')
    test_plan_id = test_plan.key.id()
    config = {
        'test_id': self.mock_test_id,
        'cluster': 'cluster',
        'run_target': 'run_target',
        'test_resource_objs': [
            {
                'name': 'bar',
                'url': self.mock_test_resource_url,
            }
        ],
        'before_device_action_ids': [
            self.mock_device_action_id,
        ]
    }
    data = {
        'name': 'bar',
        'test_run_sequences': [{'test_run_configs': [config]}],
    }

    res = self.app.put_json(
        '/_ah/api/mtt/v1/test_plans/%s' % test_plan_id, data)

    msg = protojson.decode_message(messages.TestPlan, res.body)
    self.assertEqual(test_plan_id, int(msg.id))
    test_plan = ndb_models.TestPlan.get_by_id(test_plan_id)
    self.assertIsNotNone(test_plan)
    self._VerifyTestPlan(data, test_plan)
    mock_schedule_test_plan_cron_job.assert_called_with(test_plan_id)

  def testUpdate_invalidData(self):
    """Tests test_plans.update API with invalid data."""
    test_plan = _CreateMockTestPlan('foo')
    test_plan_id = test_plan.key.id()
    path = '/_ah/api/mtt/v1/test_plans/%s' % test_plan_id
    data = {
        'name': 'foo',
        'test_run_sequences': [],
    }
    test_data = dict(data)
    test_data['cron_exp'] = 'invalid'
    res = self.app.put_json(path, test_data, expect_errors=True)
    self.assertEqual(HTTP_STATUS_400, res.status)

    test_data = dict(data)
    test_data['test_run_sequences'].append({
        'test_run_configs': [{'test_id': 'invalid'}],
    })
    res = self.app.put_json(path, test_data, expect_errors=True)
    self.assertEqual(HTTP_STATUS_400, res.status)

  def testDelete(self):
    """Tests test_plans.delete API."""
    test_plan = _CreateMockTestPlan('foo')
    test_plan_id = test_plan.key.id()
    ndb_models.TestPlanStatus(parent=test_plan.key).put()
    # Test plan and status exist initially
    self.assertIsNotNone(ndb_models.TestPlan.get_by_id(test_plan_id))
    self.assertIsNotNone(
        ndb_models.TestPlanStatus.query(ancestor=test_plan.key).get())

    self.app.delete('/_ah/api/mtt/v1/test_plans/%s' % test_plan_id)
    # Test plan and status were both deleted
    self.assertIsNone(ndb_models.TestPlan.get_by_id(test_plan_id))
    self.assertIsNone(
        ndb_models.TestPlanStatus.query(ancestor=test_plan.key).get())

  @mock.patch.object(test_plan_kicker, 'KickTestPlan')
  def testRun(self, mock_test_plan_runner):
    """Tests test_plans.run API."""
    test_run_config = ndb_models.TestRunConfig(
        cluster='cluster',
        test_key=messages.ConvertToKey(ndb_models.Test, 'test'),
        run_target='target')
    test_run_sequence = ndb_models.TestRunConfigList(
        test_run_configs=[test_run_config])
    test_plan = _CreateMockTestPlan('foo',
                                    test_run_sequences=[test_run_sequence])

    self.app.post('/_ah/api/mtt/v1/test_plans/%s/run' % test_plan.key.id())
    mock_test_plan_runner.assert_called_with(test_plan.key.id())

  def testRun_withoutConfigs(self):
    """Tests test_plans.run API without run configs."""
    test_plan = _CreateMockTestPlan('foo')
    res = self.app.post(
        '/_ah/api/mtt/v1/test_plans/%s/run' % test_plan.key.id(),
        expect_errors=True)
    self.assertEqual(HTTP_STATUS_400, res.status)

  def testRun_notFound(self):
    """Tests test_plans.run API with unknown ID."""
    res = self.app.post(
        '/_ah/api/mtt/v1/test_plans/%s/run' % 666, expect_errors=True)
    self.assertEqual(HTTP_STATUS_404, res.status)


if __name__ == '__main__':
  absltest.main()
