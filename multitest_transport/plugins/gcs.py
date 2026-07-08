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

"""MTT plugins for Google Cloud Storage."""
import datetime
import io
import logging

import apiclient


from multitest_transport.models import event_log
from multitest_transport.plugins import base
from multitest_transport.plugins import file_upload_hook
from multitest_transport.util import constant
from multitest_transport.util import env
from multitest_transport.util import errors
from multitest_transport.util import file_util
from multitest_transport.util import oauth2_util

_PATH_DELIMITER = '/'
_EMPTY_FOLDER_CONTENT_TYPE = 'application/x-www-form-urlencoded;charset=UTF-8'
_GCS_API_NAME = 'storage'
_GCS_API_VERSION = 'v1'
_PAGE_SIZE = 10

RO_SCOPES = ['https://www.googleapis.com/auth/devstorage.read_only']
RW_SCOPES = ['https://www.googleapis.com/auth/devstorage.read_write']


def GetClient(credentials, scopes):
  """Constructs a client to access the Google Cloud Storage API."""
  http = apiclient.http.build_http()
  http.timeout = constant.HTTP_TIMEOUT_SECONDS
  http = oauth2_util.AuthorizeHttp(http, credentials, scopes=scopes)
  return apiclient.discovery.build(
      _GCS_API_NAME, _GCS_API_VERSION, http=http, static_discovery=False)


def _ParsePath(path):
  """Parses a path into a bucket name and an object name."""
  if not path:
    return '', ''
  parts = path.split(_PATH_DELIMITER, 1)
  bucket = parts[0] if parts[0] else None
  object_name = parts[1] if 1 < len(parts) else None
  return bucket, object_name


def _ParseTimeStamp(timestamp):
  """Parse a timestamp into a datetime.datetime object.

  Parse a timestamp from Cloud Storage JSON API into a datetime.datetime object

  Args:
    timestamp: Cloud Storage JSON API timestamp.
  Returns:
    a datetime.datetime object or None (if timestamp is None).
  """
  if timestamp is None:
    return None
  return datetime.datetime.strptime(timestamp, '%Y-%m-%dT%H:%M:%S.%fZ')


def _ParseFileName(path):
  """Parses the file name from an object path."""
  if path.endswith(_PATH_DELIMITER):
    return path[:-1].split(_PATH_DELIMITER)[-1] + _PATH_DELIMITER
  else:
    return path.split(_PATH_DELIMITER)[-1]


class GCSBucketNotFoundError(errors.FileNotFoundError):
  """A Google Cloud Storage Error indicating that bucket is not supplied."""


class GCSBuildProvider(base.BuildProvider):
  """A build channel.

  A Google Cloud Storage plugin that allows user to download Android builds and
  listing builds with pagination.
  """
  name = 'Google Cloud Storage'
  url_patterns = [
      base.UrlPattern(
          r'gs://(?P<bucket>.*)/(?P<path>.*)',
          '{bucket}/{path}'),
  ]
  auth_methods = [
      base.AuthorizationMethod.OAUTH2_SERVICE_ACCOUNT
  ]
  oauth2_config = oauth2_util.OAuth2Config(
      client_id=env.GOOGLE_OAUTH2_CLIENT_ID,
      client_secret=env.GOOGLE_OAUTH2_CLIENT_SECRET,
      scopes=RO_SCOPES)
  build_item_path_type = base.BuildItemPathType.DIRECTORY_FILE

  def __init__(self):
    super(GCSBuildProvider, self).__init__()
    self._client = None

  def _GetClient(self):
    """Initializes a GCS client if one was not already initialized."""
    if not self._client:
      self._client = GetClient(self.GetCredentials(), RO_SCOPES)
    return self._client

  def GetOAuth2Config(self):
    """Provide base with params needed for OAuth2 authentication."""
    if not env.GOOGLE_OAUTH2_CLIENT_ID or not env.GOOGLE_OAUTH2_CLIENT_SECRET:
      return None
    return oauth2_util.OAuth2Config(
        client_id=env.GOOGLE_OAUTH2_CLIENT_ID,
        client_secret=env.GOOGLE_OAUTH2_CLIENT_SECRET,
        scopes=RO_SCOPES)

  def _GetGCSObject(self, bucket, object_name):
    """Get a Google Cloud Storage object from path.

    Args:
      bucket: a bucket name.
      object_name: an object name (e.g. path/to/object.zip).
    Returns:
      (a response object that contains attributes for the object requested)
    """
    client = self._GetClient()
    try:
      request = client.objects().get(bucket=bucket, object=object_name)
      return request.execute(num_retries=constant.NUM_RETRIES)
    except apiclient.errors.HttpError as e:
      if e.resp.status == 403:
        raise errors.FilePermissionError(
            'no permission to access file %s in GCS bucket %s'
            % (object_name, bucket))
      if e.resp.status == 404:
        logging.info(e)
        return None
      raise

  def GetBuildItem(self, path=None):
    """Get a build item.

    Args:
      path: a path to file or directory, (e.g. path/to/file/kitten.png -> file
      path1/path2/ -> directory)

    Returns:
      a base.BuildItem object if response is valid, otherwise, return None
    """
    bucket, object_name = _ParsePath(path)
    # If an object name is not given, return a root directory.
    if not object_name:
      return base.BuildItem(name='', is_file=False, path=path)  # pyrefly: ignore[bad-argument-type]
    response = self._GetGCSObject(bucket, object_name)
    if response:
      return base.BuildItem(
          name=_ParseFileName(response['name']),
          path=_PATH_DELIMITER.join([bucket, response['name']]),
          is_file=(not response['name'].endswith(_PATH_DELIMITER)),
          size=int(response['size']),
          timestamp=_ParseTimeStamp(response['updated']),
      )
    # There is no GCS object for the item. Try the list api to check if it's a
    # directory.
    if not object_name.endswith(_PATH_DELIMITER):
      object_name += _PATH_DELIMITER
    try:
      response = self._ListGCSObjects(bucket, object_name)
    except GCSBucketNotFoundError:
      return None
    if response and response.get('items'):
      return base.BuildItem(
          name=_ParseFileName(object_name),
          path=path,  # pyrefly: ignore[bad-argument-type]
          is_file=False,
      )
    return None

  def _ListGCSObjects(self, bucket, prefix, page_token=None):
    """List Google Storage Objects from given path.

    Args:
      bucket: a bucket name.
      prefix: an object name prefix.
      page_token: an optional page token.
    Returns:
      (a response object containing information about the list of objects)
    Raises:
      GCSBucketNotFoundError
    """
    client = self._GetClient()
    try:
      return client.objects().list(
          bucket=bucket,
          delimiter=_PATH_DELIMITER,
          maxResults=_PAGE_SIZE,
          prefix=prefix,
          pageToken=page_token).execute(num_retries=constant.NUM_RETRIES)
    except apiclient.errors.HttpError as e:
      if e.resp.status == 403:
        raise errors.FilePermissionError('no permission to access GCS bucket %s'
                                         % bucket)
      if e.resp.status == 404:
        raise GCSBucketNotFoundError('bucket %s does not exist' % bucket) from e
      raise

  def ListBuildItems(self, path=None, page_token=None, item_type=None):
    """List build items under a given path.

    Args:
      path: a build item path (e.g. bucket/git_master/taimen-userdebug).
      page_token: an optional page token.
      item_type: a type of build items to list. Returns all types if None.
    Returns:
      (a list of base.BuildItem objects, the next page token)
    """
    if path and not path.endswith(_PATH_DELIMITER):
      path = path + _PATH_DELIMITER
    bucket, object_name = _ParsePath(path)
    response = self._ListGCSObjects(bucket, object_name, page_token)
    build_items = []
    directory_prefixes = response.get('prefixes', [])
    items = response.get('items', [])
    prefix_len = len(object_name) if object_name else 0

    if not item_type or item_type == base.BuildItemType.DIRECTORY:
      for directory_prefix in directory_prefixes:
        build_items.append(
            base.BuildItem(
                name=directory_prefix[prefix_len:],
                path=_PATH_DELIMITER.join([bucket, directory_prefix]),
                is_file=False,
                size=None,
                timestamp=None))
    if not item_type or item_type == base.BuildItemType.FILE:
      for item in items:
        if item['contentType'] == _EMPTY_FOLDER_CONTENT_TYPE:
          continue
        item_name = item['name'][prefix_len:]
        if not item_name:
          continue
        build_items.append(
            base.BuildItem(
                name=item_name,
                path=_PATH_DELIMITER.join([bucket, item['name']]),
                is_file=True,
                size=int(item['size']),
                timestamp=_ParseTimeStamp(item['updated'])))
    next_page_token = response.get('nextPageToken')
    return (build_items, next_page_token)

  def _CreateMediaDownloader(self, bucket, object_name, fh, chunk_size, offset):
    """Create a media downloader."""
    client = self._GetClient()
    request = client.objects().get_media(bucket=bucket, object=object_name)
    downloader = apiclient.http.MediaIoBaseDownload(
        fh, request, chunksize=chunk_size)
    downloader._progress = offset  
    return downloader

  def DownloadFile(self, path, offset=0):
    """Download file from remote GCS.

    Args:
      path: a build item path (e.g. aa5/abc/bla/kitten.png)
      offset: byte offset to read from
    Yields:
      FileChunks (data read, current position, total file size)
    Raises:
      errors.FileNotFoundError: if a path is invalid
    """
    build_item = self.GetBuildItem(path)
    if (build_item is None) or (not build_item.is_file):
      raise errors.FileNotFoundError('Build item %s does not exist' % path)

    bucket, object_name = _ParsePath(path)
    buffer_ = io.BytesIO()
    downloader = self._CreateMediaDownloader(
        bucket, object_name, buffer_, constant.DEFAULT_CHUNK_SIZE, offset)
    done = False
    while not done:
      status, done = downloader.next_chunk(num_retries=constant.NUM_RETRIES)
      yield file_util.FileChunk(
          data=buffer_.getvalue(),
          offset=status.resumable_progress,
          total_size=status.total_size)
      buffer_.seek(0)
      buffer_.truncate()


class GCSFileUploadHook(file_upload_hook.AbstractFileUploadHook):
  """Hook which uploads files to Google Cloud Storage."""
  name = 'Google Cloud Storage File Upload'
  oauth2_config = oauth2_util.OAuth2Config(
      client_id=env.GOOGLE_OAUTH2_CLIENT_ID,
      client_secret=env.GOOGLE_OAUTH2_CLIENT_SECRET,
      scopes=RW_SCOPES)

  def __init__(self,
               _credentials=None,
               file_pattern=None,
               upload_prefix=None,
               **_):  
    super(GCSFileUploadHook, self).__init__(
        file_pattern=file_pattern, upload_prefix=upload_prefix)
    self._client = None
    self._credentials = _credentials

  def _GetClient(self):
    """Initializes a GCS client if one was not already initialized."""
    if not self._client:
      self._client = GetClient(self._credentials, RW_SCOPES)
    return self._client

  def UploadFile(self, test_run, source_url, dest_file_path):
    """Uploads a file to GCS."""
    client = self._GetClient()
    file_handle = file_util.FileHandle.Get(source_url)
    media = file_util.FileHandleMediaUpload(
        file_handle, chunksize=constant.UPLOAD_CHUNK_SIZE, resumable=True)

    bucket, object_name = _ParsePath(dest_file_path)
    request = client.objects().insert(
        bucket=bucket, name=object_name, media_body=media)
    done = False
    while not done:
      _, done = request.next_chunk(num_retries=constant.NUM_RETRIES)
    event_log.Info(test_run,
                   '[GCS] Uploaded %s to %s.' % (source_url, dest_file_path))
