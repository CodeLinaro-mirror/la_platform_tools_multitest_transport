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
import uuid

from absl.testing import absltest
from multitest_transport.api import api_test_util
from multitest_transport.api import build_api
from multitest_transport.models import messages
from multitest_transport.models import ndb_models
from protorpc import protojson


class BuildApiTest(api_test_util.TestCase):
  """Unit tests for build APIs."""

  FILE_URL = 'file:///root/file/path'

  def setUp(self):
    super(BuildApiTest, self).setUp(build_api.BuildApi)

  def _CreateMockBuild(self):
    build = ndb_models.Build(
        id=str(uuid.uuid4()),
        name='Foo',
        file_url=self.FILE_URL,
        size=123123123,
        labels=[
            'MR',
            'UDC',
        ],
    )
    build.put()
    return build

  def testList(self):
    """Tests builds.list API."""
    res = self.app.get('/_ah/api/mtt/v1/builds')
    self.assertIsNotNone(res)

  def testCreate(self):
    """Tests builds.create API."""
    data = {
        'name': 'Foo',
        'file_url': self.FILE_URL,
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
    self.assertEqual(updated_build_msg.file_url, self.FILE_URL)

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


if __name__ == '__main__':
  absltest.main()
