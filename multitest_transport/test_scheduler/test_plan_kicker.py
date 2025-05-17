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

"""A module to kick test plans."""
import datetime
import functools
import json
import logging

import croniter
import flask
import pytz
from retry import api as retry


from multitest_transport.models import messages
from multitest_transport.models import ndb_models
from multitest_transport.test_scheduler import test_kicker
from multitest_transport.test_scheduler import test_run_manager
from tradefed_cluster import common
from tradefed_cluster.services import task_scheduler

TEST_PLAN_KICKER_QUEUE = 'test-plan-kicker-queue'
MAX_NEXT_RUN_DELAY_SECONDS = 5 * 60

# Retry parameters and wrapper function
MAX_RETRY_COUNT = 3
retry_wrapper = functools.partial(
    retry.retry_call, tries=MAX_RETRY_COUNT, delay=1, backoff=2, logger=logging)

APP = flask.Flask(__name__)


def _GetCurrentTime():
  """Return naive current UTC time, visible for testing."""
  return datetime.datetime.utcnow()


def _GetTestPlanAndStatus(test_plan_id):
  """Fetch a test plan and its status."""
  test_plan = messages.ConvertToKey(ndb_models.TestPlan, test_plan_id).get()
  if not test_plan:
    logging.warning('Test plan %s not found', test_plan_id)
    return None, None
  status = ndb_models.TestPlanStatus.query(ancestor=test_plan.key).get()
  return test_plan, status or ndb_models.TestPlanStatus(parent=test_plan.key)


def _ParseTimezone(timezone):
  """Try to parse a timezone string (e.g. 'America/Los_Angeles')."""
  try:
    return pytz.timezone(timezone)
  except pytz.exceptions.UnknownTimeZoneError:
    return None


def _ClearNextRun(test_plan_status):
  """Clear the next run information in a test plan's status."""
  test_plan_status.next_run_time = None
  test_plan_status.next_run_task_name = None
  test_plan_status.put()


def _GetNextRunTime(cron_expression, timezone):
  """Calculate the next run time for a cron expression and timezone."""
  utc_time = _GetCurrentTime().replace(tzinfo=datetime.timezone.utc)
  # Determine next run time relative to the requested timezone
  relative_time = utc_time.astimezone(timezone)
  cron = croniter.croniter(cron_expression, relative_time)
  relative_next_run = cron.get_next(datetime.datetime)
  # Convert back to a naive UTC datetime as NDB doesn't support timezones
  utc_next_run = relative_next_run.astimezone(datetime.timezone.utc)
  return utc_next_run.replace(tzinfo=None)


def ScheduleCronKick(test_plan_id, next_run_time=None):
  """Schedule a next cron kick for a test plan.

  Args:
    test_plan_id: a test plan ID.
    next_run_time: next run time, calculated based on cron_exp if not given.
  """
  test_plan, test_plan_status = _GetTestPlanAndStatus(test_plan_id)
  if not test_plan or not test_plan_status:
    return

  if not test_plan.cron_exp:
    logging.warning(
        'Cannot schedule next kick for test plan %s: cron_exp is None.',
        test_plan_id)
    _ClearNextRun(test_plan_status)
    return

  timezone = _ParseTimezone(test_plan.cron_exp_timezone)
  if not timezone:
    logging.warning(
        'Cannot schedule next kick for test plan %s: unknown timezone %s.',
        test_plan_id, test_plan.cron_exp_timezone)
    _ClearNextRun(test_plan_status)
    return

  if not next_run_time:
    next_run_time = _GetNextRunTime(test_plan.cron_exp, timezone)
  test_plan_status.next_run_time = next_run_time
  payload = json.dumps({'test_plan_id': test_plan_id})
  task = task_scheduler.AddTask(
      queue_name=TEST_PLAN_KICKER_QUEUE,
      payload=payload,
      eta=test_plan_status.next_run_time.replace(tzinfo=datetime.timezone.utc),
  )
  test_plan_status.next_run_task_name = task.name
  test_plan_status.put()
  logging.info('Scheduled the next kick task %s (eta=%s)', task.name, task.eta)


def KickTestPlan(test_plan_id, task_name=None):
  """Kicks a test plan.

  Args:
    test_plan_id: a test plan ID.
    task_name: a task name.
  Returns:
    True if the test plan was kicked, False if skipped
  Raises:
    NoBuildError: if any of build channels doesn't return any builds.
  """
  logging.info('Kicking test plan %s', test_plan_id)
  test_plan, test_plan_status = _GetTestPlanAndStatus(test_plan_id)
  if not test_plan or not test_plan_status:
    return False

  if task_name:
    if test_plan_status.next_run_task_name != task_name:
      logging.warning('Unexpected cron task name: %s != %s; ignoring',
                      task_name, test_plan_status.next_run_task_name)
      return False
    test_plan_status.next_run_task_name = None

  # Schedule all test runs
  test_runs = []
  error = None
  try:
    for sequence in test_plan.test_run_sequences:
      test_run = retry_wrapper(
          test_kicker.CreateTestRun,
          fkwargs=dict(
              labels=test_plan.labels,
              test_plan_key=test_plan.key,
              test_run_config=sequence.test_run_configs[0],
              rerun_configs=sequence.test_run_configs[1:]))
      test_runs.append(test_run)
  except Exception as e:  
    # Record exception info and cancel all scheduled runs
    error = e
    for test_run in test_runs:
      test_run_manager.SetTestRunState(
          test_run_id=test_run.key.id(), state=ndb_models.TestRunState.CANCELED)

  # Update last run info
  test_plan_status.last_run_time = _GetCurrentTime()
  test_plan_status.last_run_keys = [test_run.key for test_run in test_runs]
  test_plan_status.last_run_error = str(error) if error else None
  test_plan_status.put()

  # Re-raise any caught exception
  if error:
    raise error
  return True


def CheckTestPlanNextRuns():
  """Check next runs of test plans to reschedule non-executed ones."""
  now = _GetCurrentTime()
  cutoff_time = now - datetime.timedelta(seconds=MAX_NEXT_RUN_DELAY_SECONDS)
  query = ndb_models.TestPlanStatus.query(
      ndb_models.TestPlanStatus.next_run_time < cutoff_time)
  for status in query:
    if not status.next_run_time:
      continue
    test_plan_id = status.key.parent().id()
    logging.info(
        'Test plan %s did not run until %s (next_run_time=%s); rescheduling',
        test_plan_id, now, status.next_run_time)
    ScheduleCronKick(test_plan_id, next_run_time=now)


@APP.route('/', methods=['POST'])
# This matchs all path start with '/'.
@APP.route('/<path:fake>', methods=['POST'])
def TaskHandler(fake):
  """A web request handler to handle tasks from the test kicker queue."""
  del fake
  payload = json.loads(flask.request.get_data())
  test_plan_id = payload['test_plan_id']
  task_name = flask.request.headers.get('X-AppEngine-TaskName')
  # Kick off the test plan
  reschedule = True
  try:
    reschedule = KickTestPlan(test_plan_id, task_name=task_name)
  except Exception:  
    logging.exception('Failed to start test plan %s; skipping cron kick',
                      test_plan_id)
  # Reschedule if the kick was successful or if an error occurred
  if reschedule:
    ScheduleCronKick(test_plan_id)
  return common.HTTP_OK
