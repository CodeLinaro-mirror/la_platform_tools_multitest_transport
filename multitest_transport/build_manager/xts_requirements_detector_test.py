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

"""Unit tests for xts requirements detector module."""
import json
from unittest import mock

from absl.testing import absltest
from google.oauth2 import credentials as authorized_user
from tradefed_cluster import testbed_dependent_test
from tradefed_cluster.services import task_scheduler


from multitest_transport.build_manager import xts_requirements_detector
from multitest_transport.models import messages
from multitest_transport.models import ndb_models
from multitest_transport.util import apfe_client


class XtsRequirementsDetectorTest(testbed_dependent_test.TestbedDependentTest):

  def setUp(self):
    super(XtsRequirementsDetectorTest, self).setUp()
    self.mock_test_run_action = ndb_models.TestRunAction(
        name='Report Upload Action',
        hook_class_name=xts_requirements_detector.REPORT_UPLOAD_HOOK_CLASS_NAME,
        credentials=authorized_user.Credentials(None),
    )
    self.mock_test_run_action.put()
    self.mock_test = ndb_models.Test(
        id=xts_requirements_detector.XTS_REQUIREMENTS_DETECTION_TEST_KEY,
        name='test',
        command='command',
        result_file='result_file',
    )
    self.mock_test.put()
    self.mock_test_run = ndb_models.TestRun(
        test_run_config=ndb_models.TestRunConfig(
            test_key=self.mock_test.key,
            run_target='run_target',
            cluster='cluster',
            command='mock test run command',
            retry_command='mock test run retry command',
        ),
        test=self.mock_test,
        request_id='request_id',
        state=ndb_models.TestRunState.COMPLETED,
        is_finalized=True,
    )
    self.mock_test_run.put()
    self.mock_build = ndb_models.Build(
        name='build',
        fingerprint='fingerprint',
        file_url='file:///root/file/path',
        size=123456,
        labels=['label1', 'label2'],
        detection_status=ndb_models.XtsRequirementsDetectionStatus.SIGNALS_COLLECTING,
        detection_test_run_key=self.mock_test_run.key,
    )
    self.mock_build.put()
    self.mock_apfe_report = ndb_models.ApfeReport(
        parent=self.mock_test_run.key,
        name='apfe_report',
        type=ndb_models.ReportType.GTS,
        company_id=1,
        company_name='company_name',
        device_name='device_name',
        product_name='product_name',
        model_name='model_name',
        build_fingerprint=self.mock_build.fingerprint,
    )
    self.mock_apfe_report.put()
    self.attempt_count = 2
    self.device_spec = 'device_serial:2A151FDH20066K'
    self.test_resource_objs = [
        messages.TestResourceObj(
            name='android-gts.zip', url='file:///android/gts/zip/path'
        )
    ]

  @mock.patch.object(apfe_client, 'ApfeClient')
  def testSyncApfeBuild(self, mock_client_factory):
    mock_client = mock.MagicMock()
    mock_client_factory.return_value = mock_client
    mock_client.GetLatestApfeBuild.return_value = apfe_client.ApfeBuild(
        name='apfe build',
    )
    xts_requirements_detector.SyncApfeBuild(self.mock_build.key.id())
    apfe_build = ndb_models.ApfeBuild.query(ancestor=self.mock_build.key).get()
    self.mock_build = self.mock_build.key.get()

    self.assertEqual(
        apfe_build.name,
        'apfe build',
    )

  @mock.patch.object(task_scheduler, 'AddTask')
  @mock.patch.object(apfe_client, 'ApfeClient')
  def testKickDetection(self, mock_client_factory, mock_add_task):
    self.mock_build.detection_status = (
        ndb_models.XtsRequirementsDetectionStatus.NOT_STARTED
    )
    self.mock_build.detection_test_run_key = None
    self.mock_build.put()
    mock_client = mock.MagicMock()
    mock_client_factory.return_value = mock_client
    mock_client.GetLatestApfeBuild.return_value = apfe_client.ApfeBuild(
        name='apfe build',
    )
    mock_client.GetLatestBtsReport.return_value = apfe_client.ApfeReport(
        processState=apfe_client.ProcessState.COMPLETE,
    )
    xts_requirements_detector.KickDetection(
        self.device_spec, self.test_resource_objs, str(self.mock_build.key.id())
    )
    self.mock_build = self.mock_build.key.get()

    self.assertEqual(
        ndb_models.XtsRequirementsDetectionStatus.SIGNALS_COLLECTING,
        self.mock_build.detection_status,
    )
    self.assertIsNotNone(self.mock_build.detection_start_time)
    self.assertIsNotNone(self.mock_build.detection_test_run_key)

    _, task_args = mock_add_task.call_args
    self.assertEqual(
        task_args['queue_name'],
        xts_requirements_detector.XTS_REQUIREMENTS_DETECTION_EVENT_QUEUE,
    )
    self.assertEqual(
        json.loads(task_args['payload']),
        {
            'build_id': str(self.mock_build.key.id()),
            'attempt_count': 1,
        },
    )
    self.assertEqual(
        task_args['target'],
        'default',
    )

  @mock.patch.object(apfe_client, 'ApfeClient')
  def testKickDetection_btsReportMissing(self, mock_client_factory):
    self.mock_build.detection_status = (
        ndb_models.XtsRequirementsDetectionStatus.NOT_STARTED
    )
    self.mock_build.detection_test_run_key = None
    self.mock_build.put()
    mock_client = mock.MagicMock()
    mock_client_factory.return_value = mock_client
    mock_client.GetLatestApfeBuild.return_value = apfe_client.ApfeBuild(
        name='apfe build',
    )
    mock_client.GetLatestBtsReport.return_value = None
    xts_requirements_detector.KickDetection(
        self.device_spec, self.test_resource_objs, str(self.mock_build.key.id())
    )
    self.mock_build = self.mock_build.key.get()

    self.assertEqual(
        ndb_models.XtsRequirementsDetectionStatus.ERROR,
        self.mock_build.detection_status,
    )
    self.assertEqual(
        self.mock_build.detection_error_reason,
        'BTS report not ready. Please upload the software build to Android'
        ' Firmware Analysis portal in advance.',
    )
    self.assertIsNone(self.mock_build.detection_start_time)
    self.assertIsNone(self.mock_build.detection_test_run_key)

  @mock.patch.object(task_scheduler, 'AddTask')
  @mock.patch.object(apfe_client, 'ApfeClient')
  def testProcessDetectionEvent_signalsCollecting(
      self, mock_client_factory, mock_add_task
  ):
    xts_requirements_detector.ProcessDetectionEvent(
        str(self.mock_build.key.id()), self.attempt_count
    )
    self.mock_build = self.mock_build.key.get()

    self.assertEqual(
        self.mock_build.detection_status,
        ndb_models.XtsRequirementsDetectionStatus.ANALYSIS_RUNNING,
    )
    _, task_args = mock_add_task.call_args
    self.assertEqual(
        task_args['queue_name'],
        xts_requirements_detector.XTS_REQUIREMENTS_DETECTION_EVENT_QUEUE,
    )
    self.assertEqual(
        json.loads(task_args['payload']),
        {
            'build_id': str(self.mock_build.key.id()),
            'attempt_count': 1,
        },
    )
    self.assertEqual(
        task_args['target'],
        'default',
    )
    mock_client_factory.assert_not_called()

  @mock.patch.object(task_scheduler, 'AddTask')
  @mock.patch.object(apfe_client, 'ApfeClient')
  def testProcessDetectionEvent_signalsCollecting_runningStateTestRun(
      self, mock_client_factory, mock_add_task
  ):
    self.mock_test_run.state = ndb_models.TestRunState.RUNNING
    self.mock_test_run.put()
    xts_requirements_detector.ProcessDetectionEvent(
        str(self.mock_build.key.id()), self.attempt_count
    )
    self.mock_build = self.mock_build.key.get()

    self.assertEqual(
        self.mock_build.detection_status,
        ndb_models.XtsRequirementsDetectionStatus.SIGNALS_COLLECTING,
    )
    _, task_args = mock_add_task.call_args
    self.assertEqual(
        task_args['queue_name'],
        xts_requirements_detector.XTS_REQUIREMENTS_DETECTION_EVENT_QUEUE,
    )
    self.assertEqual(
        json.loads(task_args['payload']),
        {
            'build_id': str(self.mock_build.key.id()),
            'attempt_count': self.attempt_count,
        },
    )
    self.assertEqual(
        task_args['target'],
        'default',
    )
    mock_client_factory.assert_not_called()

  @mock.patch.object(task_scheduler, 'AddTask')
  @mock.patch.object(apfe_client, 'ApfeClient')
  def testProcessDetectionEvent_signalsCollecting_apfeReportMissing(
      self, mock_client_factory, mock_add_task
  ):
    self.mock_apfe_report.key.delete()
    xts_requirements_detector.ProcessDetectionEvent(
        str(self.mock_build.key.id()), self.attempt_count
    )
    self.mock_build = self.mock_build.key.get()

    self.assertEqual(
        self.mock_build.detection_status,
        ndb_models.XtsRequirementsDetectionStatus.SIGNALS_COLLECTING,
    )
    _, task_args = mock_add_task.call_args
    self.assertEqual(
        task_args['queue_name'],
        xts_requirements_detector.XTS_REQUIREMENTS_DETECTION_EVENT_QUEUE,
    )
    self.assertEqual(
        json.loads(task_args['payload']),
        {
            'build_id': str(self.mock_build.key.id()),
            'attempt_count': self.attempt_count + 1,
        },
    )
    self.assertEqual(
        task_args['target'],
        'default',
    )
    mock_client_factory.assert_not_called()

  @mock.patch.object(apfe_client, 'ApfeClient')
  def testProcessDetectionEvent_signalsCollecting_buildFingerprintMismatch(
      self, mock_client_factory
  ):
    self.mock_apfe_report.build_fingerprint = 'other_fingerprint'
    self.mock_apfe_report.put()
    xts_requirements_detector.ProcessDetectionEvent(
        str(self.mock_build.key.id()), self.attempt_count
    )
    self.mock_build = self.mock_build.key.get()

    self.assertEqual(
        self.mock_build.detection_status,
        ndb_models.XtsRequirementsDetectionStatus.ERROR,
    )
    self.assertEqual(
        self.mock_build.detection_error_reason,
        "The provided fingerprint %s doesn't match the one %s collected from"
        ' devices.'
        % (
            self.mock_build.fingerprint,
            self.mock_apfe_report.build_fingerprint,
        ),
    )
    mock_client_factory.assert_not_called()

  @mock.patch.object(task_scheduler, 'AddTask')
  @mock.patch.object(apfe_client, 'ApfeClient')
  def testProcessDetectionEvent_signalsCollecting_maxAttemptCountReached(
      self, mock_client_factory, mock_add_task
  ):
    self.mock_apfe_report.key.delete()
    xts_requirements_detector.ProcessDetectionEvent(
        str(self.mock_build.key.id()),
        xts_requirements_detector.MAX_ATTEMPT_COUNT,
    )
    self.mock_build = self.mock_build.key.get()

    self.assertEqual(
        self.mock_build.detection_status,
        ndb_models.XtsRequirementsDetectionStatus.ERROR,
    )
    self.assertEqual(
        self.mock_build.detection_error_reason,
        'Signals collection times out. Please click the Invocation Run link'
        ' and navigate to Progress tab to get more details.',
    )
    mock_client_factory.assert_not_called()
    mock_add_task.assert_not_called()

  @mock.patch.object(task_scheduler, 'AddTask')
  @mock.patch.object(apfe_client, 'ApfeClient')
  def testProcessDetectionEvent_analysisRunning(
      self, mock_client_factory, mock_add_task
  ):
    self.mock_build.detection_status = (
        ndb_models.XtsRequirementsDetectionStatus.ANALYSIS_RUNNING
    )
    self.mock_build.put()
    mock_client = mock.MagicMock()
    mock_client_factory.return_value = mock_client
    mock_client.GetLatestApfeReport.return_value = apfe_client.ApfeReport(
        processState=apfe_client.ProcessState.COMPLETE,
    )
    mock_client.GetRequiredReports.return_value = (
        apfe_client.RequiredReportInfo(
            requiredReports=[
                apfe_client.RequiredReport(
                    type=ndb_models.ReportType.CTS,
                ),
                apfe_client.RequiredReport(
                    type=ndb_models.ReportType.GTS,
                    testPlans=['gts-interactive'],
                ),
                apfe_client.RequiredReport(
                    type=ndb_models.ReportType.VTS, available=True
                ),
            ]
        )
    )

    xts_requirements_detector.ProcessDetectionEvent(
        str(self.mock_build.key.id()), self.attempt_count
    )
    self.mock_build = self.mock_build.key.get()

    self.assertEqual(
        self.mock_build.detection_status,
        ndb_models.XtsRequirementsDetectionStatus.COMPLETED,
    )
    required_reports = list(
        ndb_models.RequiredReport.query(
            ndb_models.RequiredReport.build_key == self.mock_build.key
        ).order(ndb_models.RequiredReport.type)
    )
    # Reset key to verify other fields.
    for required_report in required_reports:
      required_report.key = None
    self.assertEqual(
        required_reports,
        [
            ndb_models.RequiredReport(
                build_key=self.mock_build.key,
                type=ndb_models.ReportType.CTS,
            ),
            ndb_models.RequiredReport(
                build_key=self.mock_build.key,
                type=ndb_models.ReportType.GTS,
                test_plans=['gts-interactive'],
            ),
            ndb_models.RequiredReport(
                build_key=self.mock_build.key,
                type=ndb_models.ReportType.VTS,
                available=True,
            ),
        ],
    )
    mock_add_task.assert_not_called()

  @mock.patch.object(task_scheduler, 'AddTask')
  @mock.patch.object(apfe_client, 'ApfeClient')
  def testProcessDetectionEvent_analysisRunning_apfeReportInProgress(
      self, mock_client_factory, mock_add_task
  ):
    self.mock_build.detection_status = (
        ndb_models.XtsRequirementsDetectionStatus.ANALYSIS_RUNNING
    )
    self.mock_build.put()
    mock_client = mock.MagicMock()
    mock_client_factory.return_value = mock_client
    mock_client.GetLatestApfeReport.return_value = apfe_client.ApfeReport(
        processState=apfe_client.ProcessState.IN_PROGRESS,
    )

    xts_requirements_detector.ProcessDetectionEvent(
        str(self.mock_build.key.id()), self.attempt_count
    )
    self.mock_build = self.mock_build.key.get()

    self.assertEqual(
        self.mock_build.detection_status,
        ndb_models.XtsRequirementsDetectionStatus.ANALYSIS_RUNNING,
    )
    _, task_args = mock_add_task.call_args
    self.assertEqual(
        task_args['queue_name'],
        xts_requirements_detector.XTS_REQUIREMENTS_DETECTION_EVENT_QUEUE,
    )
    self.assertEqual(
        json.loads(task_args['payload']),
        {
            'build_id': str(self.mock_build.key.id()),
            'attempt_count': self.attempt_count + 1,
        },
    )
    self.assertEqual(
        task_args['target'],
        'default',
    )

  @mock.patch.object(task_scheduler, 'AddTask')
  @mock.patch.object(apfe_client, 'ApfeClient')
  def testProcessDetectionEvent_analysisRunning_maxAttemptCountReached(
      self, mock_client_factory, mock_add_task
  ):
    self.mock_build.detection_status = (
        ndb_models.XtsRequirementsDetectionStatus.ANALYSIS_RUNNING
    )
    self.mock_build.put()
    mock_client = mock.MagicMock()
    mock_client_factory.return_value = mock_client
    mock_client.GetLatestApfeReport.return_value = apfe_client.ApfeReport(
        processState=apfe_client.ProcessState.IN_PROGRESS,
    )

    xts_requirements_detector.ProcessDetectionEvent(
        str(self.mock_build.key.id()),
        xts_requirements_detector.MAX_ATTEMPT_COUNT,
    )
    self.mock_build = self.mock_build.key.get()

    self.assertEqual(
        self.mock_build.detection_status,
        ndb_models.XtsRequirementsDetectionStatus.ERROR,
    )
    self.assertEqual(
        self.mock_build.detection_error_reason,
        'Build analysis times out.',
    )
    mock_add_task.assert_not_called()


if __name__ == '__main__':
  absltest.main()
