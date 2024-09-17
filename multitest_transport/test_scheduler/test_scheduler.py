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

"""A test scheduler module."""

import datetime
import logging

import flask
from multitest_transport.models import messages as mtt_messages
from multitest_transport.models import ndb_models
from multitest_transport.test_scheduler import test_kicker
from multitest_transport.test_scheduler import test_plan_kicker
from multitest_transport.test_scheduler import test_run_manager
from tradefed_cluster import common
from tradefed_cluster.util import ndb_shim as ndb

_PENDING_TEST_RUN_TTL = 60 * 60 * 24
_QUEUED_TEST_RUN_TTL = 60 * 60 * 24 * 7
_RUNNING_TEST_RUN_TTL = 60 * 60 * 24 * 7

APP = flask.Flask(__name__)


def CheckUnfinishedTestRuns():
  """Check test runs to decide if requeue/cancel according timeout parameter."""
  unfinished_test_runs = (
      ndb_models.TestRun.query()
      .order(-ndb_models.TestRun.create_time, ndb_models.TestRun.key)
      .filter(
          ndb_models.TestRun.state.IN([
              ndb_models.TestRunState.PENDING,
              ndb_models.TestRunState.QUEUED,
              ndb_models.TestRunState.RUNNING,
          ])
      )
  )
  for test_run in unfinished_test_runs:
    if test_run.state == ndb_models.TestRunState.QUEUED:
      test_run_ttl = _QUEUED_TEST_RUN_TTL
    elif test_run.state == ndb_models.TestRunState.RUNNING:
      test_run_ttl = _RUNNING_TEST_RUN_TTL
    else:
      test_run_ttl = _PENDING_TEST_RUN_TTL
    test_expire_time = test_run.create_time + datetime.timedelta(
        seconds=test_run_ttl
    )
    if datetime.datetime.utcnow() > test_expire_time:
      test_run_manager.SetTestRunState(
          test_run_id=test_run.key.id(), state=ndb_models.TestRunState.CANCELED
      )
      continue
    logging.info('requeue the test run %s', test_run.key.id())
    test_kicker.EnqueueTestRun(test_run.key.id())


def ScheduleTestPlanCronJob(test_plan_id):
  """Schedules a cron job for a test plan.

  If the test plan is not for cron, no cron job will be scheduled.

  Args:
    test_plan_id: a test plan ID.
  """
  test_plan_kicker.ScheduleCronKick(test_plan_id)


@ndb.transactional()
def _GetNextTestRunConfig(sequence_id, previous_test_run):
  """Gets the next config from a sequence and updates it."""
  sequence_key = ndb.Key(ndb_models.TestRunSequence, sequence_id)
  sequence = sequence_key.get()

  if not sequence:
    logging.warning('Cannot find test run sequence %s', sequence_id)
    return None

  previous_test_run_id = previous_test_run.key.id()
  if previous_test_run_id in sequence.finished_test_run_ids:
    logging.warning('Rerun already scheduled for run %s in sequence %s.',
                    sequence_id, previous_test_run_id)
    return None

  sequence.finished_test_run_ids.append(previous_test_run_id)
  sequence.put()

  if previous_test_run.state == ndb_models.TestRunState.ERROR:
    sequence.state = ndb_models.TestRunSequenceState.ERROR
    sequence.put()
    logging.info('Test run %s errored out. Test run sequence %s stopped.',
                 previous_test_run_id, sequence_id)
    return None

  if previous_test_run.state == ndb_models.TestRunState.CANCELED:
    sequence.state = ndb_models.TestRunSequenceState.CANCELED
    sequence.put()
    logging.info('Test run %s canceled. Test run sequence %s stopped.',
                 previous_test_run_id, sequence_id)
    return None

  if len(sequence.test_run_configs) <= len(sequence.finished_test_run_ids):
    sequence.state = ndb_models.TestRunSequenceState.COMPLETED
    sequence.put()
    logging.info('Test run sequence %s completed.', sequence_id)
    return None

  return sequence.test_run_configs[len(sequence.finished_test_run_ids)]


def ScheduleNextTestRun(sequence_id, previous_test_run_key):
  """Schedules the next run in sequence."""
  previous_test_run = previous_test_run_key.get()

  next_run_config = _GetNextTestRunConfig(sequence_id, previous_test_run)
  if not next_run_config:
    return

  next_run_config.prev_test_run_key = previous_test_run_key
  rerun_context = mtt_messages.RerunContext()
  rerun_context.test_run_id = previous_test_run_key.id()

  logging.info('Scheduling rerun for sequence %s', sequence_id)
  test_kicker.CreateTestRun(
      # TODO: Move labels to TestRunConfig
      labels=previous_test_run.labels,
      test_run_config=next_run_config,
      rerun_context=rerun_context,
      rerun_configs=[],
      sequence_id=sequence_id)


@APP.route('/test_scheduler/cron')
def CronHandler():
  """A cron handler for periodic schedule checks."""
  test_plan_kicker.CheckTestPlanNextRuns()
  return common.HTTP_OK
