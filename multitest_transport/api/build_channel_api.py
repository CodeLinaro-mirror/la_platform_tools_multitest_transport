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

"""A module to provide build channel APIs."""
# Non-standard docstrings are used to generate the API documentation.

import collections
import json
import os
import urllib.parse

import endpoints
from protorpc import message_types
from protorpc import messages
from protorpc import remote

from google.oauth2 import service_account


from multitest_transport.api import base
from multitest_transport.models import build
from multitest_transport.models import messages as mtt_messages
from multitest_transport.models import ndb_models
from multitest_transport.util import file_util


@base.MTT_API.api_class(resource_name='build_channel', path='build_channels')
class BuildChannelApi(remote.Service):
  """A handler for Build Channel API."""

  def _GetBuildChannel(self, build_channel_id):
    """Fetch a build channel by its ID or throw if not found."""
    build_channel = build.GetBuildChannel(build_channel_id)
    if not build_channel:
      raise endpoints.NotFoundException(
          'Build channel %s not found' % build_channel_id)
    return build_channel

  @base.ApiMethod(
      message_types.VoidMessage, mtt_messages.BuildChannelList,
      path='/build_channels', http_method='GET', name='list')
  def List(self, request):
    """Lists registered build channels."""
    objs = build.ListBuildChannels()
    build_channels = mtt_messages.ConvertList(objs, mtt_messages.BuildChannel)
    return mtt_messages.BuildChannelList(build_channels=build_channels)

  @base.ApiMethod(
      endpoints.ResourceContainer(
          message_types.VoidMessage,
          build_channel_id=messages.StringField(1, required=True)),
      mtt_messages.BuildChannelConfig,
      path='{build_channel_id}',
      http_method='GET',
      name='get')
  def Get(self, request):
    """Fetches a build channel.

    Parameters:
      build_channel_id: Build channel ID
    """
    build_channel = self._GetBuildChannel(request.build_channel_id)
    return mtt_messages.Convert(build_channel.config,
                                mtt_messages.BuildChannelConfig)

  @base.ApiMethod(
      endpoints.ResourceContainer(
          message_types.VoidMessage,
          build_channel_id=messages.StringField(1, required=True),
          path=messages.StringField(2),
          page_token=messages.StringField(3)),
      mtt_messages.BuildItemList, path='{build_channel_id}/build_items',
      http_method='GET', name='build_item.list')
  def ListBuildItems(self, request):
    """Fetches a list of build items.

    Parameters:
      build_channel_id: Build channel ID
      path: Build item path
      page_token: Token for pagination
    """
    build_channel = self._GetBuildChannel(request.build_channel_id)
    build_items, next_page_token = build_channel.ListBuildItems(
        path=request.path, page_token=request.page_token)
    return mtt_messages.BuildItemList(
        build_items=mtt_messages.ConvertList(
            build_items, mtt_messages.BuildItem),
        next_page_token=next_page_token)

  @base.ApiMethod(
      endpoints.ResourceContainer(
          message_types.VoidMessage,
          build_channel_id=messages.StringField(1, required=True),
          path=messages.StringField(2)),
      message_types.VoidMessage, path='{build_channel_id}/build_items',
      http_method='DELETE', name='build_item.delete')
  def DeleteBuildItem(self, request):
    """Deletes a build item.

    Parameters:
      build_channel_id: Build channel ID
      path: Build item path
    """
    build_channel = self._GetBuildChannel(request.build_channel_id)
    build_channel.DeleteBuildItem(request.path)
    return message_types.VoidMessage()

  @base.ApiMethod(
      endpoints.ResourceContainer(
          message_types.VoidMessage,
          url=messages.StringField(1, required=True)),
      mtt_messages.BuildItem, path='build_item_lookup',
      http_method='GET', name='build_item.lookup')
  def LookupBuildItem(self, request):
    """Get a build item info for a given URL.

    Parameters:
      url: a build item (file) URL.
    """
    build_channel, path = build.FindBuildChannel(request.url)
    if build_channel:
      build_item = build_channel.GetBuildItem(path)
      if not build_item:
        raise endpoints.NotFoundException('Cannot find %s' % request.url)
      return mtt_messages.Convert(build_item, mtt_messages.BuildItem)
    name = os.path.basename(urllib.parse.urlparse(request.url).path)
    info = file_util.FileHandle.Get(request.url).Info()
    if not info:
      raise endpoints.NotFoundException('Cannot find %s' % request.url)
    return mtt_messages.BuildItem(
        name=name,
        is_file=info.is_file,
        size=info.total_size,
        timestamp=info.timestamp)

  @base.ApiMethod(
      endpoints.ResourceContainer(mtt_messages.BuildChannelConfig),
      mtt_messages.BuildChannelConfig,
      path='/build_channels',
      http_method='POST',
      name='create')
  def Create(self, request):
    """Creates a build channel.

    Body:
      Build channel data
    """
    options = collections.OrderedDict()
    name_value_pair_list = request.options
    for pair in name_value_pair_list:
      if not pair.name:
        continue
      options[pair.name] = pair.value
    build_channel_config = build.AddBuildChannel(
        build_channel_id=request.id, name=request.name, provider_name=request.provider_name, options=options)
    return mtt_messages.Convert(build_channel_config,
                                mtt_messages.BuildChannelConfig)

  @base.ApiMethod(
      endpoints.ResourceContainer(
          mtt_messages.BuildChannelConfig,
          build_channel_id=messages.StringField(1, required=True)),
      mtt_messages.BuildChannelConfig,
      path='{build_channel_id}',
      http_method='PUT',
      name='update')
  def Update(self, request):
    """Updates an existing build channel.

    Body:
      Build channel data
    Parameters:
      build_channel_id: Build channel ID
    """
    options = collections.OrderedDict()
    name_value_pair_list = request.options
    for pair in name_value_pair_list:
      if not pair.name:
        continue
      options[pair.name] = pair.value
    build_channel = self._GetBuildChannel(request.build_channel_id)
    build_channel_config = build_channel.Update(
        name=request.name, provider_name=request.provider_name, options=options)
    return mtt_messages.Convert(build_channel_config,
                                mtt_messages.BuildChannelConfig)

  @base.ApiMethod(
      endpoints.ResourceContainer(
          message_types.VoidMessage,
          build_channel_id=messages.StringField(1, required=True)),
      message_types.VoidMessage,
      path='{build_channel_id}',
      http_method='DELETE',
      name='delete')
  def Delete(self, request):
    """Deletes a build channel.

    Parameters:
      build_channel_id: Build channel ID
    """
    build_channel_key = mtt_messages.ConvertToKey(
        ndb_models.BuildChannelConfig, request.build_channel_id)
    build_channel_key.delete()
    return message_types.VoidMessage()

  @base.ApiMethod(
      endpoints.ResourceContainer(
          mtt_messages.SimpleMessage,
          build_channel_id=messages.StringField(1, required=True)),
      message_types.VoidMessage,
      path='{build_channel_id}/auth',
      http_method='PUT',
      name='authorize_with_service_account')
  def AuthorizeConfigWithServiceAccount(self, request):
    """Authorizes a build channel configuration with a service account key.

    Body:
      Service account JSON key file data
    Parameters:
      build_channel_id: Build channel ID
    """
    build_channel = self._GetBuildChannel(request.build_channel_id)
    data = json.loads(request.value)
    credentials = service_account.Credentials.from_service_account_info(data)
    build_channel.config.credentials = credentials
    build_channel.config.put()
    return message_types.VoidMessage()

  @base.ApiMethod(
      endpoints.ResourceContainer(
          message_types.VoidMessage,
          build_channel_id=messages.StringField(1, required=True)),
      message_types.VoidMessage,
      path='{build_channel_id}/auth',
      http_method='DELETE',
      name='unauthorize')
  def UnauthorizeConfig(self, request):
    """Revokes a build channel configuration's authorization.

    Parameters:
      build_channel_id: Build channel ID
    """
    build_channel = self._GetBuildChannel(request.build_channel_id)
    build_channel.config.credentials = None
    build_channel.config.put()
    return message_types.VoidMessage()
