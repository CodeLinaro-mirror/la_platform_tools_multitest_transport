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

from absl.testing import absltest


from multitest_transport.api import api_test_util
from multitest_transport.api import build_api
from multitest_transport.models import ndb_models


class BuildApiTest(api_test_util.TestCase):

  def setUp(self):
    super(BuildApiTest, self).setUp(build_api.BuildApi)

  def testCreate(self):
    data = {
        'name': 'Foo',
        'file_url': 'file:///root/file/path',
        'size': '123123123',
        'labels': [
            'UDC',
            'MR',
        ],
    }

    res = self.app.post_json('/_ah/api/mtt/v1/builds', data)

    obj = json.loads(res.body)
    build = ndb_models.Build.get_by_id(int(obj['id']))
    self.assertEqual(data['name'], build.name)
    self.assertEqual(data['file_url'], build.file_url)
    self.assertEqual(data['size'], str(build.size))
    self.assertEqual(data['labels'], build.labels)

if __name__ == '__main__':
  absltest.main()
