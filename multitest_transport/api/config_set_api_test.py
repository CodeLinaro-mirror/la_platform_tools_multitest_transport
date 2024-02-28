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

"""Tests for config_set_api."""
from unittest import mock

from absl.testing import absltest
from protorpc import protojson
from tradefed_cluster.util import ndb_shim as ndb


from multitest_transport.api import api_test_util
from multitest_transport.api import config_set_api
from multitest_transport.models import build
from multitest_transport.models import config_set_helper
from multitest_transport.models import messages
from multitest_transport.models import ndb_models
from multitest_transport.plugins import base as plugins


class GCSBuildProvider(plugins.BuildProvider):
  """Dummy build provider for testing."""
  name = 'Google Cloud Storage'
  build_item_path_type = plugins.BuildItemPathType.DIRECTORY_FILE


class ConfigSetApiTest(api_test_util.TestCase):
  """Unit tests for config set APIs."""

  MOCK_FILE = 'info:\n- name: test_name\n  url: url/test.yaml'

  def setUp(self):
    super(ConfigSetApiTest, self).setUp(config_set_api.ConfigSetApi)

  def _CreateMockBuildChannel(self, name='google_cloud_storage',
                              provider='Google Cloud Storage'):
    return build.AddBuildChannel(None, name, provider, {})

  def _CreateConfigSetInfo(self, name='Test Config',
                           url='some.url/some.bucket', hash_value='123'):
    return ndb_models.ConfigSetInfo(
        key=ndb.Key(ndb_models.ConfigSetInfo, url),
        name=name, url=url, hash=hash_value)

  def _CreateConfigSetInfoMessage(self, info, status):
    message = messages.Convert(info, messages.ConfigSetInfo)
    message.status = status
    return message

  def _CreateImportedConfig(self):
    imported_config = self._CreateConfigSetInfo(name='Imported Config',
                                                url='import/config.yaml',
                                                hash_value='12345')
    imported_config.put()
    return imported_config

  def _CreateNonImportedConfig(self):
    return self._CreateConfigSetInfo(name='Non-Imported Config',
                                     url='dont/import/config.yaml',
                                     hash_value='67890')

  def _CreateUpdatableConfig(self):
    name = 'Updatable Config'
    url = 'updatable/config.yaml'
    old_config = self._CreateConfigSetInfo(name=name, url=url,
                                           hash_value='34567')
    old_config.put()
    new_config = self._CreateConfigSetInfo(name=name, url=url,
                                           hash_value='98765')
    return old_config, new_config

  @mock.patch.object(build, 'GetBuildChannel')
  def testListBuildChannels(self, mock_get_build_channel):

    config = ndb_models.BuildChannelConfig(id='google_cloud_storage',
                                           name='GCS',
                                           provider_name='Google Cloud Storage')
    channel = build.BuildChannel(config)
    mock_get_build_channel.return_value = channel

    res = self.app.get('/_ah/api/mtt/v1/config_sets/build_channels')
    res_msg = protojson.decode_message(messages.BuildChannelList, res.body)
    self.assertEqual(len(res_msg.build_channels), 1)
    self.assertEqual(res_msg.build_channels[0].id, 'google_cloud_storage')
    self.assertEqual(res_msg.build_channels[0].name, 'GCS')

  def testList(self):
    imported_config = self._CreateImportedConfig()
    updatable_config_old, _ = self._CreateUpdatableConfig()

    imported_message = self._CreateConfigSetInfoMessage(
        imported_config, ndb_models.ConfigSetStatus.IMPORTED)
    # Not using include-remote, so should not detect the update
    updatable_message = self._CreateConfigSetInfoMessage(
        updatable_config_old, ndb_models.ConfigSetStatus.IMPORTED)

    res = self.app.get('/_ah/api/mtt/v1/config_sets')
    res_msg = protojson.decode_message(messages.ConfigSetInfoList, res.body)
    self.assertEqual(len(res_msg.config_set_infos), 2)
    self.assertEqual(imported_message, res_msg.config_set_infos[0])
    self.assertEqual(updatable_message, res_msg.config_set_infos[1])

  @mock.patch.object(config_set_helper, 'GetRemoteConfigSetInfos')
  def testList_includeRemote(self, mock_get_remote_config_set_infos):
    imported_config = self._CreateImportedConfig()
    nonimported_config = self._CreateNonImportedConfig()
    updatable_config_old, updatable_config_new = self._CreateUpdatableConfig()

    imported_message = self._CreateConfigSetInfoMessage(
        imported_config, ndb_models.ConfigSetStatus.IMPORTED)
    nonimported_message = self._CreateConfigSetInfoMessage(
        nonimported_config, ndb_models.ConfigSetStatus.NOT_IMPORTED)
    updatable_message_old = self._CreateConfigSetInfoMessage(
        updatable_config_old, ndb_models.ConfigSetStatus.UPDATABLE)
    updatable_message_new = self._CreateConfigSetInfoMessage(
        updatable_config_new, ndb_models.ConfigSetStatus.UPDATABLE)

    mock_get_remote_config_set_infos.return_value = [imported_message,
                                                     nonimported_message,
                                                     updatable_message_new]

    res = self.app.get('/_ah/api/mtt/v1/config_sets?include_remote=true')
    res_msg = protojson.decode_message(messages.ConfigSetInfoList, res.body)
    self.assertEqual(len(res_msg.config_set_infos), 3)
    self.assertEqual(nonimported_message, res_msg.config_set_infos[0])
    self.assertEqual(imported_message, res_msg.config_set_infos[1])
    self.assertEqual(updatable_message_old, res_msg.config_set_infos[2])

  @mock.patch.object(config_set_helper, 'GetRemoteConfigSetInfos')
  def testList_filter(self, mock_get_remote_config_set_infos):
    imported_config = self._CreateImportedConfig()
    nonimported_config = self._CreateNonImportedConfig()
    updatable_config_old, updatable_config_new = self._CreateUpdatableConfig()

    imported_message = self._CreateConfigSetInfoMessage(
        imported_config, ndb_models.ConfigSetStatus.IMPORTED)
    nonimported_message = self._CreateConfigSetInfoMessage(
        nonimported_config, ndb_models.ConfigSetStatus.NOT_IMPORTED)
    updatable_message_old = self._CreateConfigSetInfoMessage(
        updatable_config_old, ndb_models.ConfigSetStatus.UPDATABLE)
    updatable_message_new = self._CreateConfigSetInfoMessage(
        updatable_config_new, ndb_models.ConfigSetStatus.UPDATABLE)

    mock_get_remote_config_set_infos.return_value = [imported_message,
                                                     nonimported_message,
                                                     updatable_message_new]

    args = 'include_remote=true&statuses=IMPORTED&statuses=UPDATABLE'
    res = self.app.get('/_ah/api/mtt/v1/config_sets?%s' % args)
    res_msg = protojson.decode_message(messages.ConfigSetInfoList, res.body)
    self.assertEqual(len(res_msg.config_set_infos), 2)
    self.assertEqual(imported_message, res_msg.config_set_infos[0])
    self.assertEqual(updatable_message_old, res_msg.config_set_infos[1])

    args = 'include_remote=true&statuses=NOT_IMPORTED'
    res = self.app.get('/_ah/api/mtt/v1/config_sets?%s' % args)
    res_msg = protojson.decode_message(messages.ConfigSetInfoList, res.body)
    self.assertEqual(len(res_msg.config_set_infos), 1)
    self.assertEqual(nonimported_message, res_msg.config_set_infos[0])

  def testImport_local(self):
    data = {
        'content': self.MOCK_FILE,
    }
    res = self.app.post_json(
        '/_ah/api/mtt/v1/config_sets/import/local', data)
    msg = protojson.decode_message(messages.ConfigSetInfo, res.body)
    self.assertEqual(msg.name, 'test_name')
    self.assertEqual(msg.url, 'url/test.yaml')

  def testDelete(self):
    config_set = self._CreateImportedConfig()
    self.app.delete_json('/_ah/api/mtt/v1/config_sets/import%252Fconfig.yaml')

    config_set = config_set.key.get()
    self.assertIsNone(config_set)


if __name__ == '__main__':
  absltest.main()
