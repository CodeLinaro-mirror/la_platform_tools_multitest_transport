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

"""An MTT plugin that integrates google dirve.

  Notice: Google Drive Files are only accessaible through IDs. Thus, it allows
  duplicate names under same directory. It also allows names to have '/' within
  filename.

  To avoid extensive change to MTT user interface, this plugin added certain
  contraints to user:

  1. Plugin throws error if user has duplicated file or folder name under same
  directory
  (it doesn't make sense to have e.g. 10 test_run/ folder under the same
  directory)
  2. Plugin logs the error if user has invalid folder name
  (if file name is e.g. 'sample/file/name.txt', it will log the error to notify
  user to remove slash within file name)
"""
import datetime
import io
import json
import logging
import os

import apiclient


from multitest_transport.plugins import base
from multitest_transport.util import constant
from multitest_transport.util import env
from multitest_transport.util import errors
from multitest_transport.util import file_util
from multitest_transport.util import oauth2_util

# Google Drive Root Directory's id
_DRIVE_ROOT_ID = 'root'
_FOLDER_TYPE = 'application/vnd.google-apps.folder'
_GOOGLE_DRIVE_BUILD_API_NAME = 'drive'
_GOOGLE_DRIVE_BUILD_API_VERSION = 'v3'
_GOOGLE_DRIVE_OAUTH2_SCOPES = ['https://www.googleapis.com/auth/drive.readonly']
_PATH_DELIMITER = '/'
_PAGE_SIZE = 10
# Google Drive file attributes that this plugin needs
_FIELDS = 'mimeType, modifiedTime, name, size'
# A Google Drive query that request a file under a directory
_QUERY_ITEM_FORMAT = "\'%s\' in parents and name = \'%s\' and trashed = false"
# A Google Drive query that request a list of files under a directory
_QUERY_ITEM_LIST_FORMAT = "\'%s\' in parents and trashed = false"
_QUERY_FILE_LIST_FORMAT = (
    _QUERY_ITEM_LIST_FORMAT +
    " and mimeType != 'application/vnd.google-apps.folder'")
_QUERY_FOLDER_LIST_FORMAT = (
    _QUERY_ITEM_LIST_FORMAT +
    " and mimeType = 'application/vnd.google-apps.folder'")
# A prefix for file ID path (e.g. /_id/1YfLO2Se0QoqjjJ9tyULr-6SWvYXeDFbA)
_FILE_ID_PATH_PREFIX = '_id/'

# Error messages
_INVALID_FILE_ID_ERROR = 'File id %s does not exist'
_FILE_NOT_FOUND_ERROR = 'File %s does not exist'
_DUPLICATED_OBJECT_NAME_ERROR = 'Duplicated name found %s under same directory'
_PARAM_NOT_VALID_ERROR = 'Param not valid: %s'
_INVALID_FILE_PATH_ERROR = 'Invalid file path %s'


def _ParseTimeStamp(timestamp):
  """Parse a timestamp into a datetime.datetime object.

  Parse a timestamp from Google Drive API into a datetime.datetime object

  Args:
    timestamp: Google Drive API timestamp (e.g. 2018-07-24T16:38:59.086Z).
  Returns:
    a datetime.datetime object or None (if timestamp is None).
  """
  if timestamp is None:
    return None
  return datetime.datetime.strptime(timestamp, '%Y-%m-%dT%H:%M:%S.%fZ')


class GoogleDriveBuildProvider(base.BuildProvider):
  """A build channel.

  A MTT plugin that allows user to download Android builds from Google Drive and
  listing builds with pagination.
  """
  name = 'Google Drive'
  auth_methods = [
      base.AuthorizationMethod.OAUTH2_SERVICE_ACCOUNT
  ]
  oauth2_config = oauth2_util.OAuth2Config(
      client_id=env.GOOGLE_OAUTH2_CLIENT_ID,
      client_secret=env.GOOGLE_OAUTH2_CLIENT_SECRET,
      scopes=_GOOGLE_DRIVE_OAUTH2_SCOPES)
  url_patterns = [
      base.UrlPattern(
          r'https://drive.google.com/file/d/(?P<id>.*)/view.*',
          _FILE_ID_PATH_PREFIX + '{id}'),
      base.UrlPattern(
          r'https://drive.google.com/open\?id=(?P<id>.*)',
          _FILE_ID_PATH_PREFIX + '{id}'),
  ]
  build_item_path_type = base.BuildItemPathType.DIRECTORY_FILE

  def __init__(self):
    super(GoogleDriveBuildProvider, self).__init__()
    self._client = None
    self._file_id_map = {}

  def _GetClient(self):
    """Initialize client.

    Returns:
      a client which is a Google Api Client Resource object with methods
    for interacting with the service. Returns None if client has already been
    initialized
    """
    if self._client:
      return self._client
    http = apiclient.http.build_http()
    http.timeout = constant.HTTP_TIMEOUT_SECONDS
    http = oauth2_util.AuthorizeHttp(
        http, self.GetCredentials(), scopes=_GOOGLE_DRIVE_OAUTH2_SCOPES)
    self._client = apiclient.discovery.build(
        _GOOGLE_DRIVE_BUILD_API_NAME,
        _GOOGLE_DRIVE_BUILD_API_VERSION,
        http=http,
        static_discovery=False)
    return self._client

  def _GetFileIds(self, param):
    """Get List of file ids.

    Args:
      param: A dictionary of parameters

    Returns:
      child_ids: a list of google drive file ids
      next_page_token: return None if not available
    """
    logging.debug('Getting file IDs with param: %s', param)
    client = self._GetClient()
    try:
      files = client.files().list(
          supportsAllDrives=True,
          includeItemsFromAllDrives=True,
          **param).execute(num_retries=constant.NUM_RETRIES)
      logging.debug('response = %s', files)
      next_page_token = files.get('nextPageToken', None)
      file_ids = [file_item['id'] for file_item in files.get('files', [])]
      return file_ids, next_page_token
    except apiclient.errors.HttpError as e:
      if e.resp.status == constant.HTTP_NOT_FOUND_ERROR_CODE:
        raise errors.PluginError(_PARAM_NOT_VALID_ERROR % json.dumps(param))
      raise

  def _GetFileItem(self, file_id):
    """Get a file item from file id.

    Args:
      file_id: a google drive file id

    Returns:
      file_item: represents an actuall google drive file

    Raises:
      errors.FileNotFoundError: if file id does not exist.
    """
    # get a file item by file id
    client = self._GetClient()
    try:
      file_item = client.files().get(
          supportsAllDrives=True,
          fileId=file_id,
          fields=_FIELDS).execute(num_retries=constant.NUM_RETRIES)
      return file_item
    except apiclient.errors.HttpError as e:
      if e.resp.status == constant.HTTP_NOT_FOUND_ERROR_CODE:
        raise errors.FileNotFoundError(_INVALID_FILE_ID_ERROR % file_id)
      raise

  def _ConvertFileToBuildItem(self, file_item, path):
    """Convert a file_item to a build_item.

    Args:
      file_item: a google drive file object
      path: path to the file (e.g folderB/folderA/, folderB/cat.img)

    Returns:
      base.BuildItem
    """
    is_file = file_item['mimeType'] != _FOLDER_TYPE
    name = file_item['name']
    if is_file:
      timestamp = _ParseTimeStamp(file_item['modifiedTime'])
    else:
      name = name + _PATH_DELIMITER
      timestamp = None
    return base.BuildItem(
        name=name,
        path=path,
        is_file=is_file,
        size=int(file_item.get('size', 0)),
        timestamp=timestamp)

  def _GetFileIdHelper(
      self, parent_folder_id, name):
    """Get id by query with parent folder's id and wanted file or folder's name.

    E.g. If path is b/c, and we pass in b's id and c's name. We will return
    c'id.

    Args:
      parent_folder_id: (e.g. root, some_hash_value).
      name: a file or folder's name (e.g. folderA, cat.img)
    Returns:
      subfolder's id: (e.g. some_hash_value)
    Raises:
      errors.PluginError: if the filename is not unique.
      errors.FileNotFoundError: if no file matched the subfolder's name
        or no matching file id was found.
    """
    param = {}
    param['q'] = (_QUERY_ITEM_FORMAT % (parent_folder_id, name))
    child_ids, _ = self._GetFileIds(param)

    if len(child_ids) >= 2:
      raise errors.PluginError(_DUPLICATED_OBJECT_NAME_ERROR % name)
    if not child_ids:
      raise errors.FileNotFoundError(_FILE_NOT_FOUND_ERROR % name)
    return child_ids[0]

  def _GetFileId(self, path=None):
    """Returns an object id for a given path.

    A path can be in one of two types: an absolute path and a relative path.

    An absolute path starts with a "_id/" prefix which is followed by an object
    ID. The object ID can point to either a file or a folder. If the ID points
    to a folder, the path may include a path part
    (e.g. _id/(file_id)/foo/bar.txt) which is resolved relative to the folder
    denoted by the ID.

    A path which doesn't have a "_id" is considered as a relative path. A
    relative path is resolved from a user's root folder (e.g. My Drive).


    Args:
      path: an absolute/relative path.
    Returns:
      An object ID.
    """
    if path in self._file_id_map:
      return self._file_id_map[path]

    file_id = _DRIVE_ROOT_ID
    if not path:
      return file_id
    if path.startswith(_FILE_ID_PATH_PREFIX):
      tokens = path[len(_FILE_ID_PATH_PREFIX):].split(_PATH_DELIMITER)
      file_id = tokens.pop(0)
    else:
      tokens = path.split(_PATH_DELIMITER)
    for token in tokens:
      if not token:  # needed due to trailing '/'
        continue
      file_id = self._GetFileIdHelper(file_id, token)

    self._file_id_map[path] = file_id
    return file_id

  def GetBuildItem(self, path=None):
    """Get a build item.

    Args:
      path: a path to file or directory, (e.g. path/to/file/kitten.png -> file
      path1/path2/ -> directory)

    Returns:
      a base.BuildItem object if response is valid, otherwise, return None
    """
    file_id = self._GetFileId(path)
    file_item = self._GetFileItem(file_id)
    return self._ConvertFileToBuildItem(file_item, path)

  def ListBuildItems(self, path='', page_token=None, item_type=None):
    """List build items under a given path.

    Args:
      path: a build item path (e.g. '', folderA/, folderA/folderB/).
      page_token: an optional page token.
      item_type: a type of build items to list. Returns all types if None.
    Returns:
      (a list of base.BuildItem objects, the next page token)
    """
    path = path.rstrip('/')
    folder_id = self._GetFileId(path)

    param = {}
    if page_token:
      param['pageToken'] = page_token
    param['pageSize'] = _PAGE_SIZE
    if item_type == base.BuildItemType.FILE:
      query_format = _QUERY_FILE_LIST_FORMAT
    elif item_type == base.BuildItemType.DIRECTORY:
      query_format = _QUERY_FOLDER_LIST_FORMAT
    else:
      query_format = _QUERY_ITEM_LIST_FORMAT
    param['q'] = query_format % folder_id

    child_ids, next_page_token = self._GetFileIds(param)

    build_items = []
    for child_id in child_ids:
      file_item = self._GetFileItem(child_id)
      name = file_item['name']
      if _PATH_DELIMITER in name:
        logging.info(
            "File %s contains invalid character '/', please remove", name)
        continue
      build_item_path = os.path.join(path, name)
      build_item = self._ConvertFileToBuildItem(
          file_item, build_item_path)
      build_items.append(build_item)
    return (build_items, next_page_token)

  def _CreateMediaDownloader(self, path, file_handle, chunk_size, offset):
    """Create a media downloader.

    Args:
      path: a build item path (e.g. folderA/folderB/cts.zip).
      file_handle: a file handle.
      chunk_size: int, File will be downloaded in chunks of this many bytes.
      offset: starting offset
    Returns:
      A Media Downloader
    """
    client = self._GetClient()
    file_id = self._GetFileId(path)
    request = client.files().get_media(supportsAllDrives=True, fileId=file_id)
    downloader = apiclient.http.MediaIoBaseDownload(
        file_handle, request, chunksize=chunk_size)
    downloader._progress = offset  
    return downloader

  def DownloadFile(self, path, offset=0):
    """Download file from Google Drive.

    Args:
      path: a build item path (e.g. folderA/folderB/cts.zip)
      offset: byte offset to read from
    Yields:
      FileChunks (data read, current position, total file size)
    Raises:
      errors.FileNotFoundError: if a path is invalid
    """
    build_item = self.GetBuildItem(path)
    if (build_item is None) or (not build_item.is_file):
      raise errors.FileNotFoundError(_FILE_NOT_FOUND_ERROR % path)

    buffer_ = io.BytesIO()
    downloader = self._CreateMediaDownloader(path, buffer_,
                                             constant.DEFAULT_CHUNK_SIZE,
                                             offset)
    done = False
    while not done:
      status, done = downloader.next_chunk(num_retries=constant.NUM_RETRIES)
      yield file_util.FileChunk(
          data=buffer_.getvalue(),
          offset=status.resumable_progress,
          total_size=status.total_size)
      buffer_.seek(0)
      buffer_.truncate()
