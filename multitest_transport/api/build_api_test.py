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
from protorpc import protojson

FILE_URL = 'file:///root/file/path'
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


class BuildApiTest(api_test_util.TestCase):
  """Unit tests for build APIs."""

  def setUp(self):
    super(BuildApiTest, self).setUp(build_api.BuildApi)

  def _CreateMockBuild(self):
    build = ndb_models.Build(
        id=str(uuid.uuid4()),
        name='Foo',
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

  def testList(self):
    """Tests builds.list API."""
    res = self.app.get('/_ah/api/mtt/v1/builds')
    self.assertIsNotNone(res)

  def testCreate(self):
    """Tests builds.create API."""
    data = {
        'name': 'Foo',
        'file_url': FILE_URL,
        'size': '123123123',
        'labels': [
            'UDC',
            'MR',
        ],
    }

    res = self.app.post_json('/_ah/api/mtt/v1/builds', data)

    obj = json.loads(res.body)
    build = ndb_models.Build.get_by_id(obj['id'])
    self.assertEqual(data['name'], build.name)
    self.assertEqual(data['file_url'], build.file_url)
    self.assertEqual(data['size'], str(build.size))
    self.assertEqual(data['labels'], build.labels)

  def testGet(self):
    """Tests builds.get API."""
    build = self._CreateMockBuild()

    res = self.app.get('/_ah/api/mtt/v1/builds/%s' % build.key.id())
    msg = protojson.decode_message(messages.Build, res.body)
    self.assertEqual(messages.Convert(build, messages.Build), msg)

  def testGet_notFound(self):
    """Tests builds.get with unknown ID."""
    res = self.app.get('/_ah/api/mtt/v1/builds/%s' % 123456, expect_errors=True)
    self.assertEqual('404 Not Found', res.status)

  def testUpdate(self):
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

  def testUpdate_skipChangesToReadOnlyFields(self):
    """Tests builds.update API with changes to read only fields."""
    build = self._CreateMockBuild()
    build_msg = messages.Convert(build, messages.Build)
    build_msg.name = 'Bar'
    build_msg.file_url = 'file:///root/file/new_path'
    data = protojson.encode_message(build_msg)

    res = self.app.put('/_ah/api/mtt/v1/builds/%s' % build.key.id(), data)

    updated_build_msg = protojson.decode_message(messages.Build, res.body)
    # Verify that the name field is updated.
    self.assertEqual(updated_build_msg.name, 'Bar')
    # Verify that the file_url field remains the same as before.
    self.assertEqual(updated_build_msg.file_url, FILE_URL)

  def testDelete(self):
    """Tests builds.delete API."""
    build = self._CreateMockBuild()
    self.assertIsNotNone(build.key.get())
    self.app.delete(
        '/_ah/api/mtt/v1/builds', params={'build_ids': [build.key.id()]}
    )
    self.assertIsNone(build.key.get())

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

  @mock.patch.object(test_kicker, 'CreateTestRun', autospec=True)
  def testDetect(self, mock_run_test):
    """Tests builds.detect API."""
    test = self._createMockTest()
    action = self._CreateTestRunAction(
        name='Report Upload Action',
        hook_class_name=build_api.REPORT_UPLOAD_HOOK_CLASS_NAME,
        credentials=authorized_user.Credentials(None),
    )
    test_run = ndb_models.TestRun(
        test=test,
        labels=['xts_requirements_detection'],
        test_run_config=ndb_models.TestRunConfig(
            test_key=test.key,
            cluster='cluster',
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
    test_run.put()
    mock_run_test.return_value = test_run
    build = self._CreateMockBuild()
    build_msg = messages.Convert(build, messages.Build)
    self.assertEqual(
        build_msg.xts_requirements.detection_status,
        ndb_models.XtsRequirementsDetectionStatus.NOT_STARTED,
    )
    self.assertIsNone(build_msg.xts_requirements.detection_test_run_id)

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
        updated_build_msg.xts_requirements.detection_status,
        ndb_models.XtsRequirementsDetectionStatus.SIGNALS_COLLECTING,
    )
    self.assertEqual(
        updated_build_msg.xts_requirements.detection_test_run_id,
        str(test_run.key.id()),
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
