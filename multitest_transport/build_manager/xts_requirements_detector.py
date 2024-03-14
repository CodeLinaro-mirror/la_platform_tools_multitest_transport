# Copyright 2024 Google LLC
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

"""A module to process xTS requirements detection requests."""
import datetime
import json
import logging

import flask
import pytz



from multitest_transport.models import messages as mtt_messages
from multitest_transport.models import ndb_models
from multitest_transport.util import apfe_client
from multitest_transport.util import constant
from tradefed_cluster import common
from tradefed_cluster.services import task_scheduler
from tradefed_cluster.util import ndb_shim as ndb

MAX_ATTEMPT_COUNT = 10
MAX_RETRY_COUNT = 5

XTS_REQUIREMENTS_DETECTION_EVENT_QUEUE = (
    'xts-requirements-detection-event-queue'
)


APP = flask.Flask(__name__)


def _GetCurrentTime():
  """Returns naive current UTC time."""
  return datetime.datetime.utcnow()


def _GetNextSyncTime(delta_minutes=1):
  """Calculate the next sync UTC time for required reports."""
  now = _GetCurrentTime()
  next_sync_time = now + datetime.timedelta(minutes=delta_minutes)
  return next_sync_time


def SyncRequiredReports(build_id, attempt_count):
  """Retrieves and stores the required reports for a build.

  Args:
    build_id: a build ID.
    attempt_count: attempt count of required reports syncing.
  """
  build = mtt_messages.ConvertToKey(ndb_models.Build, build_id).get()
  if not build:
    return
  if (
      build.detection_status
      != ndb_models.XtsRequirementsDetectionStatus.ANALYSIS_RUNNING
  ):
    if not build.IsFinalDetectionStatus():
      SetDetectionStatus(
          build_id,
          ndb_models.XtsRequirementsDetectionStatus.ERROR,
          detection_error_reason='Invalid detection request.',
      )
    return
  apfe_report = ndb_models.ApfeReport.query(
      ancestor=build.detection_test_run_key
  ).get()
  if not apfe_report:
    SetDetectionStatus(
        build_id,
        ndb_models.XtsRequirementsDetectionStatus.ERROR,
        detection_error_reason=(
            'Failed to upload GTS reports to APFE. Please click the invocation'
            ' run and navigate to Progress tab to get more details.'
        ),
    )
    return
  if build.fingerprint != apfe_report.build_fingerprint:
    SetDetectionStatus(
        build_id,
        ndb_models.XtsRequirementsDetectionStatus.ERROR,
        detection_error_reason=(
            "The provided fingerprint %s doesn't match the one %s collected "
            'from devices.'
        )
        % (build.fingerprint, apfe_report.build_fingerprint),
    )
    return
  # Uses the default credentials to sync required reports from APFE.
  private_node_config = ndb_models.GetPrivateNodeConfig()
  client = apfe_client.ApfeClient(
      constant.ANDROID_PARTNER_API_NAME,
      credentials=private_node_config.default_credentials,
  )
  required_report_info = client.GetRequiredReports(build.fingerprint)

  if required_report_info.requiredReports:
    # Updates detection status to COMPLETED and store required reports.
    def _Txn():
      build = mtt_messages.ConvertToKey(ndb_models.Build, build_id).get()
      if not build:
        return
      required_reports = [
          apfe_client.ConvertRequiredReport(required_report, build.key)
          for required_report in required_report_info.requiredReports
      ]
      ndb.put_multi(required_reports)
      build.detection_status = (
          ndb_models.XtsRequirementsDetectionStatus.COMPLETED
      )
      build.put()

    ndb.transaction(_Txn)
  elif attempt_count < MAX_ATTEMPT_COUNT:
    # Schedules a next sync task.
    payload = json.dumps(
        {'build_id': build_id, 'attempt_count': attempt_count + 1}
    )
    next_sync_time = _GetNextSyncTime()
    task_scheduler.AddTask(
        queue_name=XTS_REQUIREMENTS_DETECTION_EVENT_QUEUE,
        payload=payload,
        target='default',
        eta=pytz.UTC.localize(next_sync_time),
    )
  else:
    # Updates detection status to ERROR.
    SetDetectionStatus(
        build_id,
        ndb_models.XtsRequirementsDetectionStatus.ERROR,
        detection_error_reason='Build analysis times out.',
    )


def HandleFinalizedTestRun(test_run_key):
  """Handles a finalized test run.

  Args:
    test_run_key: a test run key.
  """
  test_run = test_run_key.get(use_cache=False)
  if not test_run or not test_run.is_finalized:
    return

  build = ndb_models.Build.query(
      ndb_models.Build.detection_test_run_key == test_run_key
  ).get()
  if not build:
    return

  build_id = build.key.id()
  SetDetectionStatus(
      build_id, ndb_models.XtsRequirementsDetectionStatus.ANALYSIS_RUNNING
  )

  payload = json.dumps({'build_id': build_id, 'attempt_count': 1})
  # Holds for 5 minutes to allow for analysis to complete.
  next_sync_time = _GetNextSyncTime(delta_minutes=5)
  task_scheduler.AddTask(
      queue_name=XTS_REQUIREMENTS_DETECTION_EVENT_QUEUE,
      payload=payload,
      target='default',
      eta=pytz.UTC.localize(next_sync_time),
  )


@ndb.transactional()
def SetDetectionStatus(build_id, detection_status, detection_error_reason=None):
  """Updates a build's detection status.

  Args:
    build_id: build ID.
    detection_status: new detection status.
    detection_error_reason: detection error reason, only used for ERROR
      detection status.
  """
  build = mtt_messages.ConvertToKey(ndb_models.Build, build_id).get()
  if not build:
    return

  build.detection_status = detection_status
  if detection_status == ndb_models.XtsRequirementsDetectionStatus.ERROR:
    build.detection_error_reason = detection_error_reason
  build.put()


@APP.route('/', methods=['POST'])
# This matchs all path start with '/'.
@APP.route('/<path:fake>', methods=['POST'])
def TaskHandler(fake):
  """Handle tasks from the xTS requirements detection event queue."""
  del fake
  retry_count = int(
      flask.request.headers.get('X-AppEngine-TaskRetryCount', MAX_RETRY_COUNT)
  )
  payload = json.loads(flask.request.get_data())
  build_id = payload['build_id']
  attempt_count = payload['attempt_count']
  try:
    SyncRequiredReports(build_id, attempt_count)
  except Exception as e:  
    if retry_count < MAX_RETRY_COUNT:
      logging.exception(
          'Failed to fetch required reports for build %s, retry_count = %d',
          build_id,
          retry_count + 1,
      )
      raise
    else:
      logging.exception(
          'Failed to fetch required reports for build %s after %d retries',
          build_id,
          MAX_RETRY_COUNT,
      )
      SetDetectionStatus(
          build_id,
          ndb_models.XtsRequirementsDetectionStatus.ERROR,
          detection_error_reason=str(e),
      )
  return common.HTTP_OK
