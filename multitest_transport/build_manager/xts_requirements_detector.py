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
from multitest_transport.test_scheduler import test_kicker
from multitest_transport.util import analytics
from multitest_transport.util import apfe_client
from multitest_transport.util import constant
from tradefed_cluster import common
from tradefed_cluster.services import task_scheduler
from tradefed_cluster.util import ndb_shim as ndb

MAX_ATTEMPT_COUNT = 15
MAX_RETRY_COUNT = 5

XTS_REQUIREMENTS_DETECTION_EVENT_QUEUE = (
    'xts-requirements-detection-event-queue'
)

# LINT.IfChange(xts_requirements_detection_test_key)
XTS_REQUIREMENTS_DETECTION_TEST_KEY = 'gs://android-test-catalog/prod/gms.yaml::android.gts.latest_release.xts_requirements_detection'
# LINT.ThenChange(
#     //depot/google3/third_party/py/multitest_transport/ui2/app/services/mtt_models.ts:xts_requirements_detection_test_id,
# )

# LINT.IfChange(report_upload_hook_class_name)
REPORT_UPLOAD_HOOK_CLASS_NAME = 'APFEReportUploadHook'
# LINT.ThenChange(//depot/google3/third_party/py/multitest_transport/plugins/apfe.py:report_upload_hook_name)


APP = flask.Flask(__name__)


def _GetCurrentTime():
  """Returns naive current UTC time."""
  return datetime.datetime.utcnow()


def _GetNextProcessTime(delta_minutes):
  """Calculate the next process UTC time for xTS requirement detections."""
  now = _GetCurrentTime()
  next_process_time = now + datetime.timedelta(minutes=delta_minutes)
  return next_process_time


def _ScheduleNextProcessTask(build_id, attempt_count, delta_minutes=1):
  """Calculate the next process UTC time for xTS requirement detections."""
  payload = json.dumps({'build_id': build_id, 'attempt_count': attempt_count})
  next_process_time = _GetNextProcessTime(delta_minutes)
  task_scheduler.AddTask(
      queue_name=XTS_REQUIREMENTS_DETECTION_EVENT_QUEUE,
      payload=payload,
      target='default',
      eta=pytz.UTC.localize(next_process_time),
  )


def _GetXtsRequirementsDetectionTest():
  """Gets the default test for xts requirements detection."""
  test_key = mtt_messages.ConvertToKey(
      ndb_models.Test, XTS_REQUIREMENTS_DETECTION_TEST_KEY
  )
  test = test_key.get()
  if not test:
    raise ValueError('Test %s not found' % XTS_REQUIREMENTS_DETECTION_TEST_KEY)
  return test_key, test


def _GetReportUploadAction():
  """Gets the report upload test action."""
  actions = list(
      ndb_models.TestRunAction.query(
          ndb_models.TestRunAction.hook_class_name
          == REPORT_UPLOAD_HOOK_CLASS_NAME
      )
  )
  report_upload_action = None
  for action in actions:
    if action.credentials and all(opt.value for opt in action.options):
      report_upload_action = action
      break
  if not report_upload_action:
    raise ValueError(
        'Report upload test action with configed credentials and options %s'
        ' not found' % REPORT_UPLOAD_HOOK_CLASS_NAME
    )
  return report_upload_action.key, report_upload_action


def _HandleSignalsCollectingStatus(build_id, attempt_count):
  """Handles a detection event for a build with SIGNALS_COLLECTING status.

  Args:
    build_id: a build ID.
    attempt_count: attempt count to process signals collecting status.
  """
  build = mtt_messages.ConvertToKey(ndb_models.Build, build_id).get()
  if not build:
    return
  test_run = build.detection_test_run_key.get()
  # Checks if the test run was deleted.
  if not test_run:
    SetDetectionStatus(
        build_id,
        ndb_models.XtsRequirementsDetectionStatus.ERROR,
        detection_error_reason='Invocation run %s not found.'
        % build.detection_test_run_key,
    )
    return
  apfe_report = ndb_models.ApfeReport.query(
      ancestor=build.detection_test_run_key
  ).get()
  if test_run.is_finalized and apfe_report is not None:
    # Crosses check the build fingerprint.
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
    else:
      SetDetectionStatus(
          build_id, ndb_models.XtsRequirementsDetectionStatus.ANALYSIS_RUNNING
      )
      # Resets the attempt acount and holds for 5 minutes for build analysis.
      _ScheduleNextProcessTask(build_id, attempt_count=1, delta_minutes=5)
  elif attempt_count < MAX_ATTEMPT_COUNT:
    # Schedules a next process task.
    _ScheduleNextProcessTask(build_id, attempt_count=attempt_count + 1)
  else:
    SetDetectionStatus(
        build_id,
        ndb_models.XtsRequirementsDetectionStatus.ERROR,
        detection_error_reason=(
            'Signals collection times out. Please click the Invocation Run link'
            ' and navigate to Progress tab to get more details.'
        ),
    )


def _HandleAnalysisRunningStatus(build_id, attempt_count):
  """Handles a detection event for a build with ANALYSIS_RUNNING status.

  Args:
    build_id: a build ID.
    attempt_count: attempt count to process signals collecting status.
  """
  build = mtt_messages.ConvertToKey(ndb_models.Build, build_id).get()
  if not build:
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
    # Schedules a next process task.
    _ScheduleNextProcessTask(build_id, attempt_count=attempt_count + 1)
  else:
    # Updates detection status to ERROR.
    SetDetectionStatus(
        build_id,
        ndb_models.XtsRequirementsDetectionStatus.ERROR,
        detection_error_reason='Build analysis times out.',
    )


def KickDetection(device_spec, test_resource_objs, build_id):
  """Kick off an xTS requirements detection for a build.

  Args:
    device_spec: device spec.
    test_resource_objs: path to the files to use for test resources.
    build_id: a build ID.

  Returns:
    a latest ndb_models.Build object.
  """
  analytics.Log(
      analytics.BUILD_CATEGORY,
      analytics.DETECT_ACTION,
  )
  test_key, test = _GetXtsRequirementsDetectionTest()
  report_upload_action_key, _ = _GetReportUploadAction()

  test_run_config = ndb_models.TestRunConfig(
      test_key=test_key,
      command=test.command,
      device_specs=[device_spec],
      test_run_action_refs=[
          ndb_models.TestRunActionRef(action_key=report_upload_action_key)
      ],
      test_resource_objs=mtt_messages.ConvertList(
          test_resource_objs, ndb_models.TestResourceObj
      ),
  )
  test_run = test_kicker.CreateTestRun(
      labels=['xts_requirements_detection', build_id],
      test_run_config=test_run_config,
  )

  # Update detection status to SIGNALS_COLLECTING and store test run key.
  def _Txn():
    build = mtt_messages.ConvertToKey(ndb_models.Build, build_id).get()
    if not build:
      return
    build.detection_status = (
        ndb_models.XtsRequirementsDetectionStatus.SIGNALS_COLLECTING
    )
    # Reset detection_error_reason.
    build.detection_error_reason = None
    build.detection_test_run_key = test_run.key
    build.put()
    return build

  updated_build = ndb.transaction(_Txn)
  # Holds for 12 minutes to collect signals from devices.
  _ScheduleNextProcessTask(build_id, attempt_count=1, delta_minutes=12)
  return updated_build


def ProcessDetectionEvent(build_id, attempt_count):
  """Processes an xTS requirements detection event for a build.

  Args:
    build_id: a build ID.
    attempt_count: attempt count to process an xTS requirements detection for a
      build.
  """
  build = mtt_messages.ConvertToKey(ndb_models.Build, build_id).get()
  if not build:
    return
  if (
      build.detection_status
      == ndb_models.XtsRequirementsDetectionStatus.SIGNALS_COLLECTING
  ):
    _HandleSignalsCollectingStatus(build_id, attempt_count)
  elif (
      build.detection_status
      == ndb_models.XtsRequirementsDetectionStatus.ANALYSIS_RUNNING
  ):
    _HandleAnalysisRunningStatus(build_id, attempt_count)


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
    ProcessDetectionEvent(build_id, attempt_count)
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
