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

"""A module that defines build channel classes."""
import fnmatch
import logging
import os
import re
import urllib.parse
import uuid


from multitest_transport.plugins import base as plugins
from multitest_transport.models import ndb_models
from multitest_transport.util import analytics
from multitest_transport.util import errors

BuildItem = plugins.BuildItem  
BuildItemType = plugins.BuildItemType  
UrlPattern = plugins.UrlPattern  

WILDCARD_CHARS = '*?'


class BuildLocator(object):
  """A utility class which parses an encoded url."""

  def __init__(self, build_channel_id, directory, filename, path):
    self._build_channel_id = build_channel_id
    self._directory = directory
    self._filename = filename
    self._path = path

  @classmethod
  def ParseUrl(cls, url):
    """Parse an encoded url.

    Args:
      url: an encoded url.

    Returns:
      A BuildLocator or None if url not start with mtt:///
    """
    if not url:
      return None
    m = re.match(r'mtt:///([^/]*)/(.*)', url)
    if not m:
      return None

    directory = None
    filename = None
    build_channel_id = m.group(1)
    path = m.group(2)

    idx = path.rfind('/')
    if idx == -1:
      # Only filename remain
      filename = urllib.parse.unquote(path)
      path = filename
    else:
      directory = path[:idx]
      filename = urllib.parse.unquote(path[idx + 1:])
      path = os.path.join(directory, filename)
    return BuildLocator(build_channel_id, directory, filename, path)

  @property
  def build_channel_id(self):
    return self._build_channel_id

  @property
  def directory(self):
    """Get the directory within an MTT url.

    e.g. mtt:///local_file_store/a/b/c.txt, directory will be a/b
    e.g. mtt:///local_file_store/c.txt, directory will be None
    Returns:
      directory: an mtt url directory
    """
    return self._directory

  @property
  def filename(self):
    """Filename will be decoded filename.

    Returns:
      filename: a filename
    """
    return self._filename

  @property
  def path(self):
    """Get the concatenation of directory and filename.

    e.g. mtt:///local_file_store/a/b/c.txt, path will be a/b/c.txt
    e.g. mtt:///local_file_store/a.txt, path will be a.txt
    Returns:
      path: an mtt url path
    """
    return self._path


def GetBuildProviderClass(name):
  """Returns a build provider class.

  Args:
    name: a build provider name.
  Returns:
    a plugins.BuildProvider class.
  """
  return plugins.GetBuildProviderClass(name)


def ListBuildProviderNames():
  """Returns a list of names of registered build providers.

  Returns:
    a list of build provider names.
  """
  return plugins.ListBuildProviderNames()


class BuildChannel(object):
  """A class representing a build channel."""

  def __init__(self, config):
    self.id = config.key.id()
    self.config = config
    # Find and instantiate provider
    provider_class = GetBuildProviderClass(config.provider_name)
    if not provider_class:
      self.auth_state = ndb_models.AuthorizationState.NOT_APPLICABLE
      return
    self._provider = provider_class()
    self._provider.UpdateOptions(
        **ndb_models.NameValuePair.ToDict(self.config.options))
    # Load credentials and set authorization state
    self.auth_state = ndb_models.AuthorizationState.UNAUTHORIZED
    private_node_config = ndb_models.GetPrivateNodeConfig()
    if not self._provider.auth_methods:
      self.auth_state = ndb_models.AuthorizationState.NOT_APPLICABLE
    elif config.credentials or private_node_config.default_credentials:
      self.auth_state = ndb_models.AuthorizationState.AUTHORIZED
      self._provider.UpdateCredentials(
          config.credentials or private_node_config.default_credentials)

  @property
  def is_valid(self):
    return hasattr(self, '_provider')

  @property
  def provider(self):
    if self.is_valid:
      return getattr(self, '_provider')
    raise errors.PluginError('Unknown provider %s' % self.config.provider_name)

  @property
  def name(self):
    return self.config.name

  @property
  def provider_name(self):
    return self.config.provider_name

  @property
  def options(self):
    return self.config.options

  @property
  def credentials(self):
    return self.config.credentials

  @property
  def auth_methods(self):
    """Supported authorization methods."""
    if not self.is_valid:
      return []
    return self._provider.auth_methods

  @property
  def oauth2_config(self):
    if not self.is_valid:
      return []
    return self._provider.oauth2_config

  @property
  def url_patterns(self):
    """File URL patterns."""
    if not self.is_valid:
      return []
    return self._provider.url_patterns

  @property
  def build_item_path_type(self):
    if not self.is_valid:
      return ndb_models.BuildItemPathType.DIRECTORY_FILE
    return self._provider.build_item_path_type

  def ListBuildItems(self, path=None, page_token=None, item_type=None):
    """List build items.

    Args:
      path: a path within a build channel.
      page_token: an optional token for paging.
      item_type: a type of build items to list. Returns all types if None.
    Returns:
      (a list of plugins.BuildItem objects, a next page token)
    """
    return self.provider.ListBuildItems(
        path=path, page_token=page_token, item_type=item_type)

  def GetBuildItem(self, path):
    """Get a build item.

    Args:
      path: a build item path.
    Returns:
      a plugins.BuildItem object.
    """
    return self.provider.GetBuildItem(path)

  def DeleteBuildItem(self, path):
    """Delete a build item.

    Args:
      path: a build item path.
    """
    self.provider.DeleteBuildItem(path)

  def DownloadFile(self, path, offset=0):
    """Download a build file.

    Args:
      path: a build file path
      offset: byte offset to read from
    Returns:
      FileChunk generator (yields data, current position, total file size)
    """
    analytics.Log(
        analytics.BUILD_CHANNEL_CATEGORY,
        analytics.DOWNLOAD_ACTION,
        label=self.provider_name)
    return self.provider.DownloadFile(path, offset=offset)

  def Update(self, name, provider_name, options):
    """Updates a build channel.

    Args:
      name: a build channel name.
      provider_name: a build provider name.
      options: a option dict.
    Returns:
      an updated ndb_models.BuildChannelConfig object.
    """
    provider_class = GetBuildProviderClass(provider_name)
    if not provider_class:
      raise errors.PluginError(
          'Unknown provider %s' % provider_name, http_status=400)
    provider = provider_class()
    provider.UpdateOptions(**options)
    self.config.name = name
    self.config.provider_name = provider_name
    self.config.options = ndb_models.NameValuePair.FromDict(options)
    self.config.put()
    self._provider = provider
    return self.config

  def FindBuildItemPath(self, url):
    return self.provider.FindBuildItemPath(url)


def AddBuildChannel(build_channel_id, name, provider_name, options):
  """Adds a new build channel.

  Args:
    build_channel_id: ID for build channel.
    name: a build channel name.
    provider_name: a build provider name.
    options: a option dict.
  Returns:
    a newly created ndb_models.BuildChannelConfig object.
  """
  provider_class = GetBuildProviderClass(provider_name)
  if not provider_class:
    raise errors.PluginError(
        'Unknown provider %s' % provider_name, http_status=400)
  provider = provider_class()
  # Validate options.
  provider.UpdateOptions(**options)
  new_config = ndb_models.BuildChannelConfig(
      id=build_channel_id or str(uuid.uuid4()),
      name=name,
      provider_name=provider_name,
      options=ndb_models.NameValuePair.FromDict(options))
  new_config.put()
  return new_config


def GetBuildChannel(build_channel_id):
  """Returns a build channel.

  Args:
    build_channel_id: a build channel id.
  Returns:
    BuildChannel or None if not found.
  """
  config = ndb_models.BuildChannelConfig.get_by_id(build_channel_id)
  if config is None:
    return None
  return BuildChannel(config)


def ListBuildChannels():
  """Lists all build channels.

  Returns:
    a list of ndb_models.BuildChannelConfig objects.
  """
  return [
      BuildChannel(config)
      for config in ndb_models.BuildChannelConfig.query().fetch()
  ]


def FindBuildChannel(url):
  """Find a build channel for a given URL.

  Args:
    url: a URL.
  Returns:
    (a build channel, a build item path)
  Raises:
    errors.PluginError: if a build channel ID is not found.
  """
  # Try to handle a build channel specific URL (mtt:///<build_channel_id>/...)
  build_locator = BuildLocator.ParseUrl(url)
  if build_locator:
    config = ndb_models.BuildChannelConfig.get_by_id(
        build_locator.build_channel_id)
    if not config:
      raise errors.PluginError(
          'Cannot find build channel %s' % build_locator.build_channel_id,
          http_status=404)
    return BuildChannel(config), build_locator.path

  # Iterate over all build channels to find one that supports this URL
  for config in ndb_models.BuildChannelConfig.query().fetch():
    build_channel = BuildChannel(config)
    if not build_channel.is_valid:
      continue  # skip invalid channels
    path = build_channel.FindBuildItemPath(url)
    if path:
      return build_channel, path

  # No matching build channel found
  return None, None


def BuildUrl(build_channel_id, build_item):
  """Build a encoded url.

  (e.g. if channel id is local_file_store, has a build item a/b c.txt,
  it will convert it to mtt:///local_file_store/a%2Fb%20c.txt)

  Args:
    build_channel_id: a build channel id
    build_item: a build item

  Returns:
    An encode url
  """
  path = build_item.path[:-len(build_item.name)]
  filename = build_item.name
  if not filename:
    return 'mtt:///%s/%s' % (build_channel_id, path)
  encoded_filename = urllib.parse.quote(filename.encode('utf-8'), safe='')
  if not path:
    return 'mtt:///%s/%s' % (build_channel_id, encoded_filename)
  else:
    return 'mtt:///%s/%s' % (build_channel_id,
                             os.path.join(path, encoded_filename))


def FindTestResources(test_resource_objs):
  """Parses test resource obj urls (may include wildcards).

  Args:
    test_resource_objs: a list of TestResourceObjs

  Returns:
    parsed_objs: a list of TestResourceObj with urls parsed
  Raises:
    FileNotFoundError: if no file matching the test resource obj url is found
    TestResourceError: if a test resource obj url is missing
  """
  test_resource_map = {}
  for obj in test_resource_objs:
    build_locator = BuildLocator.ParseUrl(obj.url)
    if build_locator:
      build_item = FindFile(build_locator.build_channel_id,
                            build_locator.directory, build_locator.filename)
      if not build_item:
        raise errors.FileNotFoundError('Cannot find file from %s' % obj.url)
      # Build a encoded url
      url = BuildUrl(build_locator.build_channel_id, build_item)
    else:
      url = obj.url
    test_resource_map[obj.name] = ndb_models.TestResourceObj(
        name=obj.name,
        url=url,
        test_resource_type=obj.test_resource_type,
        decompress=obj.decompress,
        decompress_dir=obj.decompress_dir,
        params=ndb_models.TestResourceParameters.Clone(obj.params))
  parsed_objs = sorted(test_resource_map.values(), key=lambda x: x.name)
  for r in parsed_objs:
    logging.info('\t%s: %s', r.name, r.cache_url)
    if not r.url:
      raise errors.TestResourceError('No URL for test resource %s' % r.name)
  return parsed_objs


def FindFile(build_channel_id, path, filename=None):
  """Finds a file build item under a given path recursively.

  Args:
    build_channel_id: a build channel ID.
    path: a build item path.
    filename: a filename. Can containd wildcard characters (*?).

  Returns:
    a plugins.BuildItem object.
  """
  build_channel = GetBuildChannel(build_channel_id)
  if not build_channel:
    raise ValueError('Build channel [%s] does not exist' % build_channel_id)
  if path:
    build_item = build_channel.GetBuildItem(path)
  else:
    # Path can be none when file are at first level into the build channel
    # e.g. mtt:///google_drive/file.txt, in this case google_drive in the
    # id, and file.txt is filename, but path is none.
    build_item = plugins.BuildItem(name='', path='', is_file=False)
  if not filename:
    return build_item

  # If a given path is for a director and a filename is given, recursively
  # search the first file that matches.
  while build_item and not build_item.is_file:
    next_build_item = None
    # If filename has wildcard characters
    if any([c in filename for c in WILDCARD_CHARS]):
      for child_item in _BuildItemIterator(
          build_channel, build_item.path, item_type=BuildItemType.FILE):
        if child_item.is_file and fnmatch.fnmatch(child_item.name, filename):
          next_build_item = child_item
          break
    else:
      child_item = build_channel.GetBuildItem(
          os.path.join(build_item.path or '', filename))
      if child_item and child_item.is_file:
        next_build_item = child_item
    if not next_build_item:
      # We assume the first build item returned is the latest one.
      for child_item in _BuildItemIterator(
          build_channel,
          build_item.path,
          item_type=BuildItemType.DIRECTORY):
        next_build_item = child_item
        break
    build_item = next_build_item
  return build_item


def _BuildItemIterator(build_channel, path, item_type=None):
  """An iterator to list all build items under a given path.

  Args:
    build_channel: a build.BuildChannel object.
    path: a build item path.
    item_type: a build item type.
  Yields:
    plugins.BuildItem objects.
  """
  page_token = None
  while True:
    items, page_token = build_channel.ListBuildItems(
        path, page_token=page_token, item_type=item_type)
    for item in items:
      if (item_type and
          (item.is_file and item_type != BuildItemType.FILE) or
          (not item.is_file and item_type == BuildItemType.FILE)):
        logging.warning(
            'An item does not match an item type filter: item=%s, item_type=%s',
            item, item_type)
        continue
      yield item
    if not page_token:
      break
