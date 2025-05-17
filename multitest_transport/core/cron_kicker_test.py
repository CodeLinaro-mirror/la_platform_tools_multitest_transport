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

"""Unit tests for cron_kicker."""
import datetime
import os
from unittest import mock
import urllib.request

from absl.testing import absltest
from tradefed_cluster import testbed_dependent_test
from tradefed_cluster.plugins import base as tfc_plugins
import webtest


from multitest_transport.core import cron_kicker

GAE_CONFIGS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), 'gae_configs')


class CronKickerTest(testbed_dependent_test.TestbedDependentTest):

  @mock.patch.object(urllib.request, 'urlopen')
  def testKick(self, mock_urlopen):
    now = datetime.datetime.utcnow()
    cron_job = cron_kicker.CronJob(
        url='/foo', schedule='schedule', target='target', next_run_time=now)
    self.mock_app_manager.GetInfo.return_value = tfc_plugins.AppInfo(
        name='target', hostname='localhost')

    cron_kicker.Kick(cron_job)

    self.mock_app_manager.GetInfo.assert_called_with('target')
    mock_urlopen.assert_called_with('http://localhost/foo')
    self.assertIsNone(cron_job.next_run_time)

  @mock.patch.object(cron_kicker, '_GetCurrentTime')
  def testScheduleNextKick(self, mock_get_current_time):
    next_run_time = datetime.datetime(2000, 1, 1, 1, 0, 0)
    mock_get_current_time.return_value = next_run_time - datetime.timedelta(
        hours=1)
    cron_job = cron_kicker.CronJob(
        url='/foo', schedule='every 1 hours', target='target',
        next_run_time=None)

    cron_kicker.ScheduleNextKick(cron_job)

    tasks = self.mock_task_scheduler.GetTasks(
        queue_names=[cron_kicker.CRON_KICKER_QUEUE])
    self.assertLen(tasks, 1)
    task = tasks[0]
    self.assertEqual(
        next_run_time.replace(tzinfo=datetime.timezone.utc), task.eta
    )
    new_cron_job = cron_kicker.CronJob.FromJson(task.payload)
    self.assertEqual(cron_job.url, new_cron_job.url)
    self.assertEqual(cron_job.schedule, new_cron_job.schedule)
    self.assertEqual(cron_job.target, new_cron_job.target)
    self.assertEqual(next_run_time, new_cron_job.next_run_time)


class TaskHandlerTest(absltest.TestCase):

  def setUp(self):
    super(TaskHandlerTest, self).setUp()
    self.app = webtest.TestApp(cron_kicker.APP)

  @mock.patch.object(cron_kicker, 'ScheduleNextKick')
  @mock.patch.object(cron_kicker, 'Kick')
  def testTaskHandler(self, mock_kick, mock_schedule_next_kick):
    cron_job = cron_kicker.CronJob(
        url='/foo', schedule='every 1 hours', target='target',
        next_run_time=None)

    self.app.post(
        '/_ah/queue/%s' % cron_kicker.CRON_KICKER_QUEUE, cron_job.ToJson())

    mock_kick.assert_called_with(cron_job)
    mock_schedule_next_kick.assert_called_with(cron_job)

if __name__ == '__main__':
  absltest.main()
