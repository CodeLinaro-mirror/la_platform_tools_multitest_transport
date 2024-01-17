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
import json
import logging

import flask
from protorpc import messages
from protorpc import protojson



from multitest_transport.models import messages as mtt_messages
from multitest_transport.models import ndb_models
from multitest_transport.util import apfe_client
from multitest_transport.util import constant
from tradefed_cluster import common
from tradefed_cluster.services import task_scheduler
from tradefed_cluster.util import ndb_shim as ndb

MAX_RETRY_COUNT = 5

XTS_REQUIREMENTS_DETECTION_EVENT_QUEUE = (
    'xts-requirements-detection-event-queue'
)


APP = flask.Flask(__name__)


def FetchRequiredReports(build_id):
  """Retrieves and stores the required reports for a build.

  Args:
    build_id: a build ID.
  """
  build = mtt_messages.ConvertToKey(ndb_models.Build, build_id).get()
  if not build:
    return
  if (
      build.xts_requirements.detection_status
      != ndb_models.XtsRequirementsDetectionStatus.ANALYSIS_RUNNING
  ):
    return
  # TODO: Gets build fingerprint.
  fingerprint = ''
  # Uses the default credentials to fetch required reports from APFE.
  private_node_config = ndb_models.GetPrivateNodeConfig()
  client = apfe_client.ApfeClient(
      constant.ANDROID_PARTNER_API_NAME,
      credentials=private_node_config.default_credentials,
  )
  response = client.GetRequiredReports(fingerprint)
  required_report_info = protojson.decode_message(_RequiredReportInfo, response)  # pytype: disable=module-attr
  required_reports = [
      _RequiredReportConverter(required_report)
      for required_report in required_report_info.requiredReports
  ]

  # Update detection status to COMPLETED and store required reports.
  def _Txn():
    build.xts_requirements.required_reports = required_reports
    build.xts_requirements.detection_status = (
        ndb_models.XtsRequirementsDetectionStatus.COMPLETED
    )
    build.put()

  ndb.transaction(_Txn)


def HandleFinalizedTestRun(test_run_key):
  """Handles a finalized test run.

  Args:
    test_run_key: a test run key.
  """
  test_run = test_run_key.get()
  if not test_run or not test_run.is_finalized:
    return

  build = ndb_models.Build.query(
      ndb_models.Build.xts_requirements.detection_test_run_key == test_run_key
  ).get()
  if not build:
    return

  build_id = build.key.id()
  SetDetectionStatus(
      build_id, ndb_models.XtsRequirementsDetectionStatus.ANALYSIS_RUNNING
  )

  task_name = str(build_id)
  payload = json.dumps({'build_id': build_id})
  task_scheduler.AddTask(
      queue_name=XTS_REQUIREMENTS_DETECTION_EVENT_QUEUE,
      name=task_name,
      payload=payload,
      target='default',
  )


def SetDetectionStatus(build_id, detection_status):
  """Updates a build's detection status.

  Args:
    build_id: build ID.
    detection_status: new detection status.
  """
  build = mtt_messages.ConvertToKey(ndb_models.Build, build_id).get()
  if not build:
    return

  build.xts_requirements.detection_status = detection_status
  build.put()


class _RequiredReport(messages.Message):
  """A required report."""

  type = messages.EnumField(ndb_models.ReportType, 1)
  testPlan = messages.StringField(2)  
  available = messages.BooleanField(3)


@mtt_messages.Converter(_RequiredReport, ndb_models.RequiredReport)
def _RequiredReportConverter(msg):
  return ndb_models.RequiredReport(
      type=msg.type, test_plan=msg.testPlan, available=msg.available
  )


class _RequiredReportInfo(messages.Message):
  """Required reports to get approval for a build."""

  requiredReports = messages.MessageField(_RequiredReport, 1, repeated=True)  


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
  try:
    FetchRequiredReports(build_id)
  except Exception:  
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
          build_id, ndb_models.XtsRequirementsDetectionStatus.ERROR
      )
  return common.HTTP_OK
