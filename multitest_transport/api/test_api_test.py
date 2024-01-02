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

"""Tests for test_api."""

import json

from absl.testing import absltest
from protorpc import protojson


from multitest_transport.api import api_test_util
from multitest_transport.api import test_api
from multitest_transport.models import ndb_models
from multitest_transport.models import messages


class TestApiTest(api_test_util.TestCase):

  def setUp(self):
    super(TestApiTest, self).setUp(test_api.TestApi)

  def _CreateMockTest(
      self,
      visibility_type=None,
  ):
    test = ndb_models.Test(
        name='Foo',
        test_resource_defs=[
            ndb_models.TestResourceDef(
                name='test_resource_name',
                default_download_url='test_resource_url',
            ),
        ],
        command='command',
        env_vars=[
            ndb_models.NameValuePair(name='env_var_name', value='env_var_value')
        ],
        output_file_patterns=['output_file_pattern'],
        setup_scripts=['setup_script'],
        jvm_options=['jvm_option'],
        java_properties=[
            ndb_models.NameValuePair(
                name='java_property_name', value='java_property_value'
            )
        ],
        visibility_type=visibility_type,
    )
    test.put()
    return test

  def testList(self):
    for _ in range(1, 6):
      self._CreateMockTest()
    res = self.app.get('/_ah/api/mtt/v1/tests')
    test_list = protojson.decode_message(messages.TestList, res.body)
    self.assertLen(test_list.tests, 5)

  def testList_filterOutHiddenTests(self):
    for _ in range(1, 6):
      self._CreateMockTest()
      self._CreateMockTest(visibility_type=ndb_models.VisibilityType.HIDDEN)
    res = self.app.get('/_ah/api/mtt/v1/tests')
    test_list = protojson.decode_message(messages.TestList, res.body)
    self.assertLen(test_list.tests, 5)

  def testCreate(self):
    data = {
        'name': 'Foo',
        'test_resource_defs': [{
            'name': 'test_resource_1',
            'default_download_url': 'test_resource_1_url',
        }],
        'command': 'command',
        'env_vars': [
            {'name': 'env_var_1', 'value': 'env_var_1_value'}
        ],
        'output_file_patterns': [
            'output_file_pattern_1',
        ],
        'setup_scripts': [
            'setup_script_1',
        ],
        'jvm_options': ['jvm_option'],
        'java_properties': [
            {'name': 'java_property_1', 'value': 'java_property_1_value'}
        ],
    }

    res = self.app.post_json('/_ah/api/mtt/v1/tests', data)

    obj = json.loads(res.body)
    test = ndb_models.Test.get_by_id(int(obj['id']))
    self.assertEqual(data['name'], test.name)
    # TODO: need to assert equality of all fields.

  def testGet(self):
    test = self._CreateMockTest()

    res = self.app.get('/_ah/api/mtt/v1/tests/%s' % test.key.id())

    obj = json.loads(res.body)
    self.assertEqual(str(test.key.id()), obj['id'])
    self.assertEqual(test.name, obj['name'])
    # TODO: need to assert equality of all fields.

  def testGet_stubTest(self):
    """This checks whether test.get API returns a stub Test object for ID=0."""
    res = self.app.get('/_ah/api/mtt/v1/tests/0')

    obj = json.loads(res.body)
    self.assertTrue('id' not in obj)
    self.assertEqual('', obj['name'])

  def testUpdate(self):
    test = self._CreateMockTest()
    test_msg = messages.Convert(test, messages.Test)
    test_msg.name = 'bar'
    test_msg.test_resource_defs[0].params = messages.TestResourceParameters(
        decompress_files=['foo'])
    data = protojson.encode_message(test_msg)

    res = self.app.put('/_ah/api/mtt/v1/tests/%s' % test.key.id(), data)

    obj = json.loads(res.body)
    self.assertEqual(str(test.key.id()), obj['id'])
    self.assertEqual(test_msg.name, obj['name'])
    self.assertEqual(test_msg.test_resource_defs[0].params.decompress_files,
                     obj['test_resource_defs'][0]['params']['decompress_files'])
    # TODO: need to assert equality of all fields.

  def testDelete(self):
    test = self._CreateMockTest()
    self.assertIsNotNone(test.key.get())

    self.app.delete('/_ah/api/mtt/v1/tests/%s' % test.key.id())

    self.assertIsNone(test.key.get())


if __name__ == '__main__':
  absltest.main()
