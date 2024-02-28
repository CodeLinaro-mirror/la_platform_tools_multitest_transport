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

"""Tests for build_channel_api."""
import datetime
from unittest import mock
import urllib.parse

from absl.testing import absltest
from google.oauth2 import credentials as authorized_user
from google.oauth2 import service_account
from protorpc import protojson


from multitest_transport.api import api_test_util
from multitest_transport.api import build_channel_api
from multitest_transport.models import build
from multitest_transport.models import messages
from multitest_transport.models import ndb_models
from multitest_transport.plugins import base as plugins
from multitest_transport.util import file_util


class AndroidBuildProvider(plugins.BuildProvider):
  """Dummy build provider for testing."""
  name = 'Android'
  mock = mock.MagicMock()
  build_item_path_type = plugins.BuildItemPathType.DIRECTORY_FILE

  def __init__(self):
    super(AndroidBuildProvider, self).__init__()
    self.AddOptionDef('mock_option')

  def GetBuildItem(self, path):
    return self.mock.GetBuildItem(path)


class GoogleDriveBuildProvider(plugins.BuildProvider):
  """Dummy build provider for testing."""
  name = 'Google Drive'
  build_item_path_type = plugins.BuildItemPathType.DIRECTORY_FILE


class BuildChannelApiTest(api_test_util.TestCase):

  def setUp(self):
    super(BuildChannelApiTest, self).setUp(build_channel_api.BuildChannelApi)

  def _CreateMockBuildChannel(self, name='android', provider='Android'):
    return build.AddBuildChannel(None, name, provider, {})

  def testList(self):
    self._CreateMockBuildChannel(name='android', provider='Android')
    self._CreateMockBuildChannel(name='drive', provider='Google Drive')

    res = self.app.get('/_ah/api/mtt/v1/build_channels')
    build_channel_list = protojson.decode_message(
        messages.BuildChannelList, res.body)

    # verify that the right channels are returned
    build_channels = build_channel_list.build_channels
    self.assertEqual(2, len(build_channels))
    self.assertItemsEqual(['android', 'drive'], [
        channel.name for channel in build_channels])
    self.assertItemsEqual(['Android', 'Google Drive'], [
        channel.provider_name for channel in build_channels])

  def testGet(self):
    config = self._CreateMockBuildChannel()

    res = self.app.get('/_ah/api/mtt/v1/build_channels/%s' % config.key.id())
    build_channel_config = protojson.decode_message(messages.BuildChannelConfig,
                                                    res.body)

    # verify that the right channel is returned
    self.assertEqual(config.key.id(), build_channel_config.id)
    self.assertEqual('android', build_channel_config.name)

  def testGet_notFound(self):
    # unknown build channel ID
    res = self.app.get('/_ah/api/mtt/v1/build_channels/%s' % 666,
                       expect_errors=True)
    # throws if channel not found
    self.assertEqual('404 Not Found', res.status)

  @mock.patch.object(build.BuildChannel, 'ListBuildItems')
  def testListBuildItems(self, mock_channel):
    # create placeholders build items to return from channel
    build_items = [
        plugins.BuildItem(name='item1', path=u'path1', is_file=True),
        plugins.BuildItem(name='item2', path=u'path2', is_file=True)
    ]
    mock_channel.return_value = build_items, 'next_page_token'
    config = self._CreateMockBuildChannel()

    res = self.app.get(
        '/_ah/api/mtt/v1/build_channels/%s/build_items' % config.key.id())
    build_item_list = protojson.decode_message(messages.BuildItemList, res.body)

    # verify same build items are returned
    self.assertEqual('next_page_token', build_item_list.next_page_token)
    self.assertItemsEqual(['item1', 'item2'], [
        item.name for item in build_item_list.build_items])

  def testListBuildItems_notFound(self):
    # unknown build channel ID
    res = self.app.get('/_ah/api/mtt/v1/build_channels/%s/build_items' % 666,
                       expect_errors=True)
    # throws if channel not found
    self.assertEqual('404 Not Found', res.status)

  def testLookupBuildItem(self):
    config = self._CreateMockBuildChannel(name='android', provider='Android')
    url = 'mtt:///%s/path/to/file.ext' % config.key.id()
    build_item = plugins.BuildItem(
        name='foo',
        path='zzz/bar/foo',
        is_file=True,
        size=1234,
        timestamp=datetime.datetime.utcnow())
    AndroidBuildProvider.mock.GetBuildItem.return_value = build_item

    res = self.app.get(
        '/_ah/api/mtt/v1/build_channels/build_item_lookup?url=%s' % (
            urllib.parse.quote(url)))
    build_item_msg = protojson.decode_message(messages.BuildItem, res.body)

    AndroidBuildProvider.mock.GetBuildItem.assert_called_once_with(
        'path/to/file.ext')
    self.assertEqual(
        messages.Convert(build_item, messages.BuildItem), build_item_msg)

  @mock.patch.object(file_util.FileHandle, 'Get')
  def testLookupBuildItem_withHttpUrl(self, mock_find_handle_get):
    url = 'http://foo.com/bar/zzz/file.ext?foo=bar'
    mock_file_handle = mock.MagicMock()
    mock_find_handle_get.return_value = mock_file_handle
    mock_file_info = file_util.FileInfo(
        url=url,
        is_file=True,
        total_size=1234,
        timestamp=datetime.datetime.utcnow())
    mock_file_handle.Info.return_value = mock_file_info

    res = self.app.get(
        '/_ah/api/mtt/v1/build_channels/build_item_lookup?url=%s' % (
            urllib.parse.quote(url)))
    build_item_msg = protojson.decode_message(messages.BuildItem, res.body)

    mock_find_handle_get.assert_called_once_with(url)
    mock_file_handle.Info.assert_called_once()
    self.assertEqual('file.ext', build_item_msg.name)
    self.assertEqual(mock_file_info.is_file, build_item_msg.is_file)
    self.assertEqual(mock_file_info.total_size, build_item_msg.size)
    self.assertEqual(mock_file_info.timestamp, build_item_msg.timestamp)

  def testDelete(self):
    # create build channel and confirm it exists
    config = self._CreateMockBuildChannel()
    self.assertIsNotNone(config.key.get())

    # delete channel and verify that it no longer exists
    self.app.delete('/_ah/api/mtt/v1/build_channels/%s' % config.key.id())
    self.assertIsNone(config.key.get())

  def testCreate(self):
    data = {
        'name': 'testName',
        'id': '',
        'provider_name': 'Android',
        'options': [{
            'name': 'mock_option',
            'value': '123123123'
        }]
    }
    res = self.app.post_json('/_ah/api/mtt/v1/build_channels', data)
    msg = protojson.decode_message(messages.BuildChannelConfig, res.body)
    build_channel_config = messages.ConvertToKey(ndb_models.BuildChannelConfig,
                                                 msg.id).get()
    self.assertIsNotNone(build_channel_config)
    self.assertEqual(data['name'], build_channel_config.name)
    self.assertEqual(data['provider_name'], build_channel_config.provider_name)
    self.assertEqual(data['options'][0]['name'],
                     build_channel_config.options[0].name)

  def testUpdate(self):
    build_channel_config = self._CreateMockBuildChannel()
    build_channel_config_id = str(build_channel_config.key.id())
    data = {
        'id': build_channel_config_id,
        'name': 'bar',
        'provider_name': 'Android'
    }
    res = self.app.put_json(
        '/_ah/api/mtt/v1/build_channels/%s' % build_channel_config_id, data)

    build_channel_config = build_channel_config.key.get()
    msg = protojson.decode_message(messages.BuildChannelConfig, res.body)
    self.assertEqual(
        messages.Convert(build_channel_config, messages.BuildChannelConfig),
        msg)
    self.assertEqual(data['name'], build_channel_config.name)

  @mock.patch.object(service_account.Credentials, 'from_service_account_info')
  def testAuthorizeConfigWithServiceAccount(self, mock_parse_key):
    """Tests that a build channel can be authorized with a service account."""
    config = self._CreateMockBuildChannel(name='android', provider='Android')
    # Mock parsing service account JSON key
    mock_parse_key.return_value = service_account.Credentials(None, None, None)
    # Verify that credentials were obtained and stored
    self.app.put_json(
        '/_ah/api/mtt/v1/build_channels/%s/auth' % config.key.id(),
        {'value': '{}'})
    config = ndb_models.BuildChannelConfig.get_by_id(config.key.id())
    self.assertIsNotNone(config.credentials)

  def testAuthorizeWithServiceAccount_notFound(self):
    """Tests that an error occurs when a build channel is not found."""
    response = self.app.put_json(
        '/_ah/api/mtt/v1/build_channels/%s/auth' % 'unknown', {'value': '{}'},
        expect_errors=True)
    self.assertEqual('404 Not Found', response.status)

  def testUnauthorize(self):
    """Tests that a build channel can be unauthorized."""
    config = self._CreateMockBuildChannel(name='android', provider='Android')
    config.credentials = authorized_user.Credentials(None)
    config.put()
    # Verify that credentials were removed
    self.app.delete('/_ah/api/mtt/v1/build_channels/%s/auth' % config.key.id())
    config = ndb_models.BuildChannelConfig.get_by_id(config.key.id())
    self.assertIsNone(config.credentials)

  def testUnauthorize_notFound(self):
    """Tests that an error occurs when a build channel is not found."""
    response = self.app.delete(
        '/_ah/api/mtt/v1/build_channels/%s/auth' % 'unknown',
        expect_errors=True)
    self.assertEqual('404 Not Found', response.status)


if __name__ == '__main__':
  absltest.main()
