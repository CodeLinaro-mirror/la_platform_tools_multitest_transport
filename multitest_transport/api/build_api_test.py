# Copyright 2023 Google LLC
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

"""Tests for build_api."""

import json
from unittest import mock
import uuid

from absl.testing import absltest
from google.oauth2 import credentials as authorized_user
from multitest_transport.api import api_test_util
from multitest_transport.api import build_api
from multitest_transport.models import messages
from multitest_transport.models import ndb_models
from multitest_transport.test_scheduler import test_kicker
from multitest_transport.util import analytics
from protorpc import protojson

FILE_URL = 'file:///root/file/path/build.zip'
DEVICE_SPEC = 'device_serial:2A151FDH20066K'
GTS_ZIP_NAME = 'android-gts.zip'
GTS_ZIP_URL = 'file:///android/gts/zip/path'
DETECTION_REQUEST = {
    'device_spec': DEVICE_SPEC,
    'test_resource_objs': [{
        'name': GTS_ZIP_NAME,
        'url': GTS_ZIP_URL,
    }],
}
FINGERPRINT = 'brand/product/device:plaform_version/build_id:user/release-keys'


class BuildApiTest(api_test_util.TestCase):
  """Unit tests for build APIs."""

  def setUp(self):
    super(BuildApiTest, self).setUp(build_api.BuildApi)

  def _CreateBuildToRequest(self):
    build_to_request = {
        'name': 'Foo',
        'fingerprint': FINGERPRINT,
        'file_url': FILE_URL,
        'size': '123123123',
        'labels': [
            'UDC',
            'MR',
        ],
    }
    return build_to_request

  def _CreateMockBuild(self):
    build = ndb_models.Build(
        id=str(uuid.uuid4()),
        name='Foo',
        fingerprint=FINGERPRINT,
        file_url=FILE_URL,
        size=123123123,
        labels=[
            'MR',
            'UDC',
        ],
    )
    build.put()
    return build

  def _createMockTest(self, name='test', command='command'):
    """Create a mock ndb_models.Test object."""
    test = ndb_models.Test(
        id=build_api.XTS_REQUIREMENTS_DETECTION_TEST_KEY,
        name=name,
        command=command,
    )
    test.put()
    return test

  def _CreateTestRunAction(self, **kwargs):
    """Convenience method to create a test run action."""
    action = ndb_models.TestRunAction(**kwargs)
    action.put()
    return action

  def _createMockTestRun(self, test, test_run_action_refs=None, labels=None):
    """Create a mock ndb_models.TestRun object."""
    test_run = ndb_models.TestRun(
        test=test,
        labels=labels or [],
        test_run_config=ndb_models.TestRunConfig(
            test_key=test.key,
            cluster='cluster',
            command=test.command,
            device_specs=[DEVICE_SPEC],
            test_run_action_refs=test_run_action_refs or [],
            test_resource_objs=[
                ndb_models.TestResourceObj(name=GTS_ZIP_NAME, url=GTS_ZIP_URL),
            ],
        ),
        state=ndb_models.TestRunState.RUNNING,
    )
    test_run.put()
    return test_run

  def _createMockRequiredReport(self, build_key, test_run_key):
    """Create a mock ndb_models.RequiredReport object."""
    required_report = ndb_models.RequiredReport(
        build_key=build_key,
        type=ndb_models.ReportType.CTS,
        test_run_key=test_run_key,
    )
    required_report.put()
    return required_report

  def testList(self):
    """Tests builds.list API."""
    res = self.app.get('/_ah/api/mtt/v1/builds')
    self.assertIsNotNone(res)

  @mock.patch.object(analytics, 'Log')
  def testCreate(self, mock_log):
    """Tests builds.create API."""
    data = self._CreateBuildToRequest()

    res = self.app.post_json('/_ah/api/mtt/v1/builds', data)

    obj = json.loads(res.body)
    build = ndb_models.Build.get_by_id(obj['id'])
    self.assertEqual(data['name'], build.name)
    self.assertEqual(data['fingerprint'], build.fingerprint)
    self.assertEqual(data['file_url'], build.file_url)
    self.assertEqual(data['size'], str(build.size))
    self.assertEqual(data['labels'], build.labels)
    mock_log.assert_called_with(
        analytics.BUILD_CATEGORY, analytics.CREATE_ACTION
    )

  def testCreate_unsetName(self):
    """Tests builds.create API with unset name."""
    data = self._CreateBuildToRequest()
    data.pop('name')

    res = self.app.post_json('/_ah/api/mtt/v1/builds', data, expect_errors=True)

    self.assertEqual('400 Bad Request', res.status)
    self.assertIn(
        'Name in the request is unset.',
        str(res.body),
    )

  def testCreate_fingerprintName(self):
    """Tests builds.create API with unset fingerprint."""
    data = self._CreateBuildToRequest()
    data.pop('fingerprint')

    res = self.app.post_json('/_ah/api/mtt/v1/builds', data, expect_errors=True)

    self.assertEqual('400 Bad Request', res.status)
    self.assertIn(
        'Fingerprint in the request is unset.',
        str(res.body),
    )

  def testCreate_unsetFileUrl(self):
    """Tests builds.create API with unset file url."""
    data = self._CreateBuildToRequest()
    data.pop('file_url')

    res = self.app.post_json('/_ah/api/mtt/v1/builds', data, expect_errors=True)

    self.assertEqual('400 Bad Request', res.status)
    self.assertIn(
        'File url in the request is unset.',
        str(res.body),
    )

  def testCreate_remoteFileUrl(self):
    """Tests builds.create API with remote file url."""
    data = self._CreateBuildToRequest()
    data['file_url'] = 'file://remote/file/path'

    res = self.app.post_json('/_ah/api/mtt/v1/builds', data, expect_errors=True)

    self.assertEqual('400 Bad Request', res.status)
    self.assertIn(
        'Invalid local file URL %s.' % data['file_url'],
        str(res.body),
    )

  def testCreate_unsupportedFileFormat(self):
    """Tests builds.create API with unsupported file format."""
    data = self._CreateBuildToRequest()
    data['file_url'] = 'file:///root/file/path/build.rar.gz'

    res = self.app.post_json('/_ah/api/mtt/v1/builds', data, expect_errors=True)

    self.assertEqual('400 Bad Request', res.status)
    self.assertIn(
        'The file format for %s has not been supported.' % data['file_url'],
        str(res.body),
    )

  def testGet(self):
    """Tests builds.get API."""
    build = self._CreateMockBuild()
    test = self._createMockTest()
    test_run = self._createMockTestRun(test)
    self._createMockRequiredReport(build.key, test_run.key)

    res = self.app.get('/_ah/api/mtt/v1/builds/%s' % build.key.id())
    msg = protojson.decode_message(messages.Build, res.body)
    self.assertEqual(messages.Convert(build, messages.Build), msg)

  def testGet_notFound(self):
    """Tests builds.get with unknown ID."""
    res = self.app.get('/_ah/api/mtt/v1/builds/%s' % 123456, expect_errors=True)
    self.assertEqual('404 Not Found', res.status)

  @mock.patch.object(analytics, 'Log')
  def testUpdate(self, mock_log):
    """Tests builds.update API."""
    build = self._CreateMockBuild()
    build_msg = messages.Convert(build, messages.Build)
    build_msg.name = 'Bar'
    build_msg.labels = ['IR', 'TM']
    data = protojson.encode_message(build_msg)

    res = self.app.put('/_ah/api/mtt/v1/builds/%s' % build.key.id(), data)

    updated_build_msg = protojson.decode_message(messages.Build, res.body)
    # Verify that the update_time field is updated automatically.
    self.assertGreater(updated_build_msg.update_time, build_msg.update_time)
    # Reset update_time to verify other fields.
    updated_build_msg.update_time = None
    build_msg.update_time = None
    self.assertEqual(build_msg, updated_build_msg)
    mock_log.assert_called_with(
        analytics.BUILD_CATEGORY, analytics.UPDATE_ACTION
    )

  def testUpdate_skipChangesToReadOnlyFields(self):
    """Tests builds.update API with changes to read only fields."""
    build = self._CreateMockBuild()
    build_msg = messages.Convert(build, messages.Build)
    build_msg.name = 'Bar'
    build_msg.fingerprint = 'new_fingerprint'
    build_msg.file_url = 'file:///root/file/new_path'
    data = protojson.encode_message(build_msg)

    res = self.app.put('/_ah/api/mtt/v1/builds/%s' % build.key.id(), data)

    updated_build_msg = protojson.decode_message(messages.Build, res.body)
    # Verify that the name field is updated.
    self.assertEqual(updated_build_msg.name, 'Bar')
    # Verify that the fingerprint is updated.
    self.assertEqual(updated_build_msg.fingerprint, 'new_fingerprint')
    # Verify that the file_url field remains the same as before.
    self.assertEqual(updated_build_msg.file_url, FILE_URL)

  @mock.patch.object(analytics, 'Log')
  def testDelete(self, mock_log):
    """Tests builds.delete API."""
    build = self._CreateMockBuild()
    self.assertIsNotNone(build.key.get())
    self.app.delete(
        '/_ah/api/mtt/v1/builds', params={'build_ids': [build.key.id()]}
    )
    self.assertIsNone(build.key.get())
    mock_log.assert_called_with(
        analytics.BUILD_CATEGORY, analytics.DELETE_ACTION
    )

  def testDelete_skipFailedBuilds(self):
    """Tests builds.delete API with unknown ID."""
    build = self._CreateMockBuild()
    self.assertIsNotNone(build.key.get())
    res = self.app.delete(
        '/_ah/api/mtt/v1/builds',
        params={'build_ids': [build.key.id(), 'unknown_id']},
        expect_errors=True,
    )
    self.assertIsNone(build.key.get())
    self.assertEqual('400 Bad Request', res.status)

  @mock.patch.object(analytics, 'Log')
  @mock.patch.object(test_kicker, 'CreateTestRun', autospec=True)
  def testDetect(self, mock_run_test, mock_log):
    """Tests builds.detect API."""
    test = self._createMockTest()
    action = self._CreateTestRunAction(
        name='Report Upload Action',
        hook_class_name=build_api.REPORT_UPLOAD_HOOK_CLASS_NAME,
        credentials=authorized_user.Credentials(None),
    )
    test_run = self._createMockTestRun(
        test,
        [ndb_models.TestRunActionRef(action_key=action.key)],
        ['xts_requirements_detection'],
    )
    mock_run_test.return_value = test_run
    build = self._CreateMockBuild()
    build_msg = messages.Convert(build, messages.Build)
    self.assertEqual(
        build_msg.detection_status,
        ndb_models.XtsRequirementsDetectionStatus.NOT_STARTED,
    )
    self.assertIsNone(build_msg.detection_test_run_id)

    res = self.app.post_json(
        '/_ah/api/mtt/v1/builds/%s/detect' % build.key.id(),
        DETECTION_REQUEST,
    )
    mock_run_test.assert_called_with(
        labels=['xts_requirements_detection', build.key.id()],
        test_run_config=ndb_models.TestRunConfig(
            test_key=test.key,
            command=test.command,
            device_specs=[DEVICE_SPEC],
            test_run_action_refs=[
                ndb_models.TestRunActionRef(action_key=action.key)
            ],
            test_resource_objs=[
                ndb_models.TestResourceObj(name=GTS_ZIP_NAME, url=GTS_ZIP_URL),
            ],
        ),
    )
    updated_build_msg = protojson.decode_message(messages.Build, res.body)
    self.assertEqual(
        updated_build_msg.detection_status,
        ndb_models.XtsRequirementsDetectionStatus.SIGNALS_COLLECTING,
    )
    self.assertEqual(
        updated_build_msg.detection_test_run_id,
        str(test_run.key.id()),
    )
    mock_log.assert_called_with(
        analytics.BUILD_CATEGORY, analytics.DETECT_ACTION
    )

  def testDetect_testNotFound(self):
    """Tests builds.detect with test not added."""
    build = self._CreateMockBuild()
    res = self.app.post_json(
        '/_ah/api/mtt/v1/builds/%s/detect' % build.key.id(),
        DETECTION_REQUEST,
        expect_errors=True,
    )
    self.assertEqual('404 Not Found', res.status)
    self.assertIn(
        'Test %s not found' % build_api.XTS_REQUIREMENTS_DETECTION_TEST_KEY,
        str(res.body),
    )

  def testDetect_reportUploadActionNotFound(self):
    """Tests builds.detect with report upload action not added."""
    self._createMockTest()
    build = self._CreateMockBuild()
    res = self.app.post_json(
        '/_ah/api/mtt/v1/builds/%s/detect' % build.key.id(),
        DETECTION_REQUEST,
        expect_errors=True,
    )
    self.assertEqual('404 Not Found', res.status)
    self.assertIn(
        'Report upload test action with configed credentials and options %s not'
        ' found'
        % build_api.REPORT_UPLOAD_HOOK_CLASS_NAME,
        str(res.body),
    )

  def testDetect_reportUploadActionNotFound_noCredentials(self):
    """Tests builds.detect with credentials in report upload action unset."""
    self._createMockTest()
    self._CreateTestRunAction(
        name='Report Upload Action',
        hook_class_name=build_api.REPORT_UPLOAD_HOOK_CLASS_NAME,
    )
    build = self._CreateMockBuild()
    res = self.app.post_json(
        '/_ah/api/mtt/v1/builds/%s/detect' % build.key.id(),
        DETECTION_REQUEST,
        expect_errors=True,
    )
    self.assertEqual('404 Not Found', res.status)
    self.assertIn(
        'Report upload test action with configed credentials and options %s not'
        ' found'
        % build_api.REPORT_UPLOAD_HOOK_CLASS_NAME,
        str(res.body),
    )

  def testDetect_reportUploadActionNotFound_noOptionValues(self):
    """Tests builds.detect with option values in report upload action unset."""
    self._createMockTest()
    self._CreateTestRunAction(
        name='Report Upload Action',
        hook_class_name=build_api.REPORT_UPLOAD_HOOK_CLASS_NAME,
        credentials=authorized_user.Credentials(None),
        options=[{'name': 'option_name'}],
    )
    build = self._CreateMockBuild()
    res = self.app.post_json(
        '/_ah/api/mtt/v1/builds/%s/detect' % build.key.id(),
        DETECTION_REQUEST,
        expect_errors=True,
    )
    self.assertEqual('404 Not Found', res.status)
    self.assertIn(
        'Report upload test action with configed credentials and options %s not'
        ' found'
        % build_api.REPORT_UPLOAD_HOOK_CLASS_NAME,
        str(res.body),
    )


if __name__ == '__main__':
  absltest.main()
