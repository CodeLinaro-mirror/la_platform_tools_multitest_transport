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

"""Unit tests for build."""

from absl.testing import absltest

from tradefed_cluster import testbed_dependent_test

from google.oauth2 import credentials as authorized_user


from multitest_transport.plugins import base as plugins
from multitest_transport.models import build
from multitest_transport.models import ndb_models
from multitest_transport.util import errors
from multitest_transport.util import oauth2_util


class UrlBuildProvider(plugins.BuildProvider):
  """Build provider with an additional URL pattern."""
  name = 'url_provider'
  url_patterns = [
      build.UrlPattern(r'http://abc.def/xyz/(?P<path>.*)', '{path}')
  ]


class OAuth2BuildProvider(plugins.BuildProvider):
  """Build provider with OAuth2 configuration."""
  name = 'oauth2_provider'
  auth_methods = [
      plugins.AuthorizationMethod.OAUTH2_SERVICE_ACCOUNT
  ]
  oauth2_config = oauth2_util.OAuth2Config('id', 'secret', ['scope'])


class OAuth2BuildWithInvalidOAuth2ConfigProvider(plugins.BuildProvider):
  """Build provider with OAuth2 configuration."""
  name = 'oauth2_provider_with_invalid_oauth2_config'
  auth_methods = [
      plugins.AuthorizationMethod.OAUTH2_SERVICE_ACCOUNT
  ]
  oauth2_config = oauth2_util.OAuth2Config('', '', ['scope'])


class BuildChannelTest(testbed_dependent_test.TestbedDependentTest):
  """Tests BuildChannel functionality."""

  def testInit(self):
    """Tests that build channel can be initialized."""
    config = ndb_models.BuildChannelConfig(
        id='channel_id', provider_name='url_provider')
    # Channel is valid and has instantiated its provider
    channel = build.BuildChannel(config)
    self.assertTrue(channel.is_valid)
    self.assertIsInstance(channel.provider, UrlBuildProvider)
    self.assertEqual(channel.auth_state,
                     ndb_models.AuthorizationState.NOT_APPLICABLE)

  def testInit_unauthorized(self):
    """Tests that build channel can detect its authorization state."""
    config = ndb_models.BuildChannelConfig(
        id='channel_id', provider_name='oauth2_provider')
    # Channel is valid but unauthorized
    channel = build.BuildChannel(config)
    self.assertEqual(channel.id, 'channel_id')
    self.assertTrue(channel.is_valid)
    self.assertIsInstance(channel.provider, OAuth2BuildProvider)
    self.assertEqual(channel.auth_state,
                     ndb_models.AuthorizationState.UNAUTHORIZED)
    self.assertIsNone(channel.provider.GetCredentials())

  def testInit_authorized(self):
    """Tests that build channel can detect its authorization state."""
    credentials = authorized_user.Credentials(None)
    config = ndb_models.BuildChannelConfig(
        id='channel_id',
        provider_name='oauth2_provider',
        credentials=credentials)
    # Channel is valid and authorized
    channel = build.BuildChannel(config)
    self.assertEqual(channel.id, 'channel_id')
    self.assertTrue(channel.is_valid)
    self.assertIsInstance(channel.provider, OAuth2BuildProvider)
    self.assertEqual(channel.auth_state,
                     ndb_models.AuthorizationState.AUTHORIZED)
    self.assertEqual(channel.provider.GetCredentials(), credentials)

  def testInit_invalid(self):
    """Tests that build channel initialization validates the provider."""
    config = ndb_models.BuildChannelConfig(
        id='channel_id', provider_name='unknown_provider')
    channel = build.BuildChannel(config)
    self.assertEqual(channel.id, 'channel_id')
    self.assertFalse(channel.is_valid)
    self.assertEqual(channel.auth_state,
                     ndb_models.AuthorizationState.NOT_APPLICABLE)
    self.assertEqual(channel.build_item_path_type,
                     ndb_models.BuildItemPathType.DIRECTORY_FILE)

  def testInit_withDefaultCredentials(self):
    """Tests that build channels inherits the default auth credentials."""
    credentials = authorized_user.Credentials(None)
    private_node_config = ndb_models.GetPrivateNodeConfig()
    private_node_config.default_credentials = credentials
    private_node_config.put()
    config = ndb_models.BuildChannelConfig(
        id='channel_id', provider_name='oauth2_provider')
    channel = build.BuildChannel(config)
    self.assertEqual(channel.id, 'channel_id')
    self.assertTrue(channel.is_valid)
    self.assertIsInstance(channel.provider, OAuth2BuildProvider)
    self.assertEqual(channel.auth_state,
                     ndb_models.AuthorizationState.AUTHORIZED)
    self.assertIsNotNone(channel.provider.GetCredentials())

  def testAuthMethods(self):
    config = ndb_models.BuildChannelConfig(
        id='channel_id', provider_name='oauth2_provider')
    # Channel is valid but unauthorized
    channel = build.BuildChannel(config)
    self.assertEqual(channel.id, 'channel_id')
    self.assertTrue(channel.is_valid)
    self.assertIsInstance(channel.provider, OAuth2BuildProvider)
    self.assertEqual([
        ndb_models.AuthorizationMethod.OAUTH2_SERVICE_ACCOUNT
    ], channel.auth_methods)
    self.assertEqual(channel.auth_state,
                     ndb_models.AuthorizationState.UNAUTHORIZED)
    self.assertIsNone(channel.provider.GetCredentials())

  def testAuthMethods_withInvalidOAuth2Config(self):
    config = ndb_models.BuildChannelConfig(
        id='channel_id',
        provider_name='oauth2_provider_with_invalid_oauth2_config')
    # Channel is valid but unauthorized
    channel = build.BuildChannel(config)
    self.assertEqual(channel.id, 'channel_id')
    self.assertTrue(channel.is_valid)
    self.assertIsInstance(channel.provider,
                          OAuth2BuildWithInvalidOAuth2ConfigProvider)
    self.assertEqual([ndb_models.AuthorizationMethod.OAUTH2_SERVICE_ACCOUNT],
                     channel.auth_methods)
    self.assertEqual(channel.auth_state,
                     ndb_models.AuthorizationState.UNAUTHORIZED)
    self.assertIsNone(channel.provider.GetCredentials())


class BuildTest(testbed_dependent_test.TestbedDependentTest):
  """Tests build channel utility methods."""

  def setUp(self):
    super(BuildTest, self).setUp()
    # Create two build channel configurations (one valid and one invalid)
    ndb_models.BuildChannelConfig(
        id='channel_id', name='valid', provider_name='url_provider').put()
    ndb_models.BuildChannelConfig(
        id='invalid_id', name='invalid',
        provider_name='unknown_provider').put()

  def testGetBuildProviderClass(self):
    """Tests that build provider classes can be retrieved by name."""
    self.assertEqual(UrlBuildProvider,
                     build.GetBuildProviderClass('url_provider'))
    self.assertEqual(OAuth2BuildProvider,
                     build.GetBuildProviderClass('oauth2_provider'))
    self.assertIsNone(build.GetBuildProviderClass('unknown_provider'))

  def testListBuildProviderNames(self):
    """Tests that all registered build provider names can be listed."""
    names = build.ListBuildProviderNames()
    self.assertIn('url_provider', names)
    self.assertIn('oauth2_provider', names)

  def testAddBuildChannel(self):
    """Tests that new build channel configurations can be created."""
    config = build.AddBuildChannel(None, 'test', 'url_provider', {})
    config_id = config.key.id()
    self.assertEqual(config.name, 'test')
    self.assertEqual(config.provider_name, 'url_provider')
    self.assertIsNotNone(ndb_models.BuildChannelConfig.get_by_id(config_id))

  def testAddBuildChannel_invalid(self):
    """Tests that the provider is validated when creating a configuration."""
    with self.assertRaises(errors.PluginError):
      build.AddBuildChannel(None, 'test', 'unknown_provider', {})

  def testGetBuildChannel(self):
    """Tests that build channels can be retrieved by ID."""
    self.assertIsNotNone(build.GetBuildChannel('channel_id'))
    self.assertIsNotNone(build.GetBuildChannel('invalid_id'))
    self.assertIsNone(build.GetBuildChannel('unknown'))

  def testListBuildChannels(self):
    """Tests that build channels can be listed (including invalid ones)."""
    channels = build.ListBuildChannels()
    self.assertLen(channels, 2)
    channel_ids = [channel.id for channel in channels]
    self.assertCountEqual(['channel_id', 'invalid_id'], channel_ids)

  def testFindBuildChannel(self):
    """Tests that a build channel can be found using an mtt:// URL."""
    channel, path = build.FindBuildChannel('mtt:///channel_id/path/to/file')
    self.assertEqual('channel_id', channel.id)
    self.assertEqual('path/to/file', path)

  def testFindBuildChannel_missingChannel(self):
    """Tests that a build channel referenced by ID must exist."""
    with self.assertRaises(errors.PluginError):
      build.FindBuildChannel('mtt:///unknown/path/to/file')

  def testFindBuildChannel_urlPattern(self):
    """Tests that a build channel can be found with its URL pattern."""
    channel, path = build.FindBuildChannel('http://abc.def/xyz/path/to/file')
    self.assertEqual('channel_id', channel.id)
    self.assertEqual('path/to/file', path)

  def testFindBuildChannel_noMatch(self):
    """Tests that URLs with no matching build channels are handled."""
    build_channel, path = build.FindBuildChannel('http://www.google.com')
    self.assertIsNone(build_channel)
    self.assertIsNone(path)

  def testBuildUrl(self):
    """Tests that build channel URLs can be generated."""
    item = plugins.BuildItem(
        name='z z z.txt', path='a/b/c/z z z.txt', is_file=True)
    encoded_url = build.BuildUrl('local_file_store', item)
    self.assertEqual(encoded_url, 'mtt:///local_file_store/a/b/c/z%20z%20z.txt')
    item = plugins.BuildItem(name='d/e.txt', path='a/b/c/d/e.txt', is_file=True)
    encoded_url = build.BuildUrl('local_file_store', item)
    self.assertEqual(encoded_url, 'mtt:///local_file_store/a/b/c/d%2Fe.txt')


class BuildLocatorTest(testbed_dependent_test.TestbedDependentTest):
  """Tests BuildLocator functionality."""

  def testBuildLocator(self):
    build_locator = build.BuildLocator.ParseUrl(
        'mtt:///local_file_store/file.txt')
    self.assertEqual(build_locator.build_channel_id, 'local_file_store')
    self.assertEqual(build_locator.directory, None)
    self.assertEqual(build_locator.filename, 'file.txt')
    self.assertEqual(build_locator.path, 'file.txt')

    build_locator = build.BuildLocator.ParseUrl(
        'mtt:///local_file_store/a/b/c/file.txt')
    self.assertEqual(build_locator.build_channel_id, 'local_file_store')
    self.assertEqual(build_locator.directory, 'a/b/c')
    self.assertEqual(build_locator.filename, 'file.txt')
    self.assertEqual(build_locator.path, 'a/b/c/file.txt')

    build_locator = build.BuildLocator.ParseUrl('http://file.img')
    self.assertEqual(build_locator, None)

    build_locator = build.BuildLocator.ParseUrl(
        'mtt:///drive/a/b/c/file%201.txt')
    self.assertEqual(build_locator.build_channel_id, 'drive')
    self.assertEqual(build_locator.directory, 'a/b/c')
    self.assertEqual(build_locator.filename, 'file 1.txt')
    self.assertEqual(build_locator.path, 'a/b/c/file 1.txt')

    build_locator = build.BuildLocator.ParseUrl(
        'mtt:///drive/a/b/c/signed%2Fbuild.img')
    self.assertEqual(build_locator.build_channel_id, 'drive')
    self.assertEqual(build_locator.directory, 'a/b/c')
    self.assertEqual(build_locator.filename, 'signed/build.img')
    self.assertEqual(build_locator.path, 'a/b/c/signed/build.img')

    build_locator = build.BuildLocator.ParseUrl(
        'mtt:///basic_auth_http/http%3A%2F%2Ffile.img')
    self.assertEqual(build_locator.build_channel_id, 'basic_auth_http')
    self.assertIsNone(build_locator.directory)
    self.assertEqual(build_locator.filename, 'http://file.img')
    self.assertEqual(build_locator.path, 'http://file.img')


if __name__ == '__main__':
  absltest.main()
