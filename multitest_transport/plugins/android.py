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

"""A MTT plugin for the Android Build system."""
import datetime
import io

import apiclient
import httplib2


from multitest_transport.plugins import base
from multitest_transport.util import constant
from multitest_transport.util import env
from multitest_transport.util import errors
from multitest_transport.util import file_util
from multitest_transport.util import oauth2_util

OAUTH2_SCOPES = ['https://www.googleapis.com/auth/androidbuild.internal']

ANDROID_BUILD_API_NAME = 'androidbuildinternal'
ANDROID_BUILD_API_VERSION = 'v2beta1'

MAX_PATH_PARTS = 4
LATEST = 'LATEST'
LATEST_BUILD_ITEM_DESCRIPTION = ('Linked to the latest successful build.')


def _ParseTimestamp(ts):
  """Parse a timestamp from Android Build API into a datetime.datetime object.

  Args:
    ts: Android Build API timestamp.
  Returns:
    a datetime.datetime object or None (if ts is None).
  """
  if not ts:
    return None
  return datetime.datetime.utcfromtimestamp(int(ts) / 1000.0)


class AndroidBuildProvider(base.BuildProvider):
  """A build provider for the Android Build system."""
  name = 'Android'
  auth_methods = [
      base.AuthorizationMethod.OAUTH2_SERVICE_ACCOUNT
  ]
  oauth2_config = oauth2_util.OAuth2Config(
      client_id=env.GOOGLE_OAUTH2_CLIENT_ID,
      client_secret=env.GOOGLE_OAUTH2_CLIENT_SECRET,
      scopes=OAUTH2_SCOPES)
  build_item_path_type = base.BuildItemPathType.DIRECTORY_FILE

  def __init__(self):
    super(AndroidBuildProvider, self).__init__()
    self._client = None

  def _GetClient(self):
    """Returns a non-thread safe API client."""
    if self._client:
      return self._client
    http = httplib2.Http(timeout=constant.HTTP_TIMEOUT_SECONDS)
    http = oauth2_util.AuthorizeHttp(
        http, self.GetCredentials(), scopes=OAUTH2_SCOPES)
    self._client = apiclient.discovery.build(
        ANDROID_BUILD_API_NAME,
        ANDROID_BUILD_API_VERSION,
        http=http,
        static_discovery=False)
    return self._client

  def ListBuildItems(self, path=None, page_token=None, item_type=None):
    """List build items under a given path.

    Args:
      path: a build item path (e.g. /git_master/taimen-userdebug).
      page_token: an optional page token.
      item_type: a type of build items to list. Returns all types if None.
    Returns:
      (a list of base.BuildItem objects, the next page token)
    Raises:
      ValueError: if a path is invalid.
    """
    try:
      parts = path.split('/', MAX_PATH_PARTS - 1) if path else []
      if not parts:
        if item_type == base.BuildItemType.FILE:
          return [], None
        return self._ListBranches(page_token)
      elif len(parts) == 1:
        if item_type == base.BuildItemType.FILE:
          return [], None
        return self._ListTargets(branch=parts[0], page_token=page_token)
      elif len(parts) == 2:
        if item_type == base.BuildItemType.FILE:
          return [], None
        return self._ListBuilds(
            branch=parts[0], target=parts[1], page_token=page_token)
      elif len(parts) == 3:
        if item_type == base.BuildItemType.DIRECTORY:
          return [], None
        return self._ListBuildArtifacts(
            branch=parts[0], target=parts[1], build_id=parts[2],
            page_token=page_token)
      raise ValueError('invalid path: %s' % path)
    except apiclient.errors.HttpError as e:
      if e.resp.status == 404:
        raise errors.FileNotFoundError('File %s not found' % path)
      raise

  def GetBuildItem(self, path=None):
    """Returns a build item.

    Args:
      path: a build item path.
    Returns:
      a base.BuildItem object.
    """
    try:
      parts = path.split('/', MAX_PATH_PARTS - 1) if path else []
      if len(parts) == 1:
        return self._GetBranch(name=parts[0])
      elif len(parts) == 2:
        return self._GetTarget(branch=parts[0], name=parts[1])
      elif len(parts) == 3:
        return self._GetBuild(
            branch=parts[0], target=parts[1], build_id=parts[2])
      elif len(parts) == 4:
        return self._GetBuildArtifact(
            branch=parts[0], target=parts[1], build_id=parts[2], name=parts[3])
      raise ValueError('invalid path: %s' % path)
    except apiclient.errors.HttpError as e:
      if e.resp.status == 404:
        return None
      raise

  def _ListBranches(self, page_token):
    """List branches as build items."""
    client = self._GetClient()
    req = client.branch().list(
        fields='branches/name,nextPageToken', pageToken=page_token)
    res = req.execute(num_retries=constant.NUM_RETRIES)
    build_items = [
        base.BuildItem(
            name=b['name'], path=b['name'], is_file=False, size=None,
            timestamp=None)
        for b in res.get('branches', [])
    ]
    next_page_token = res.get('nextPageToken')
    return (build_items, next_page_token)

  def _GetBranch(self, name):
    """Returns a branch as a build item."""
    client = self._GetClient()
    req = client.branch().get(resourceId=name, fields=['name'])
    res = req.execute(num_retries=constant.NUM_RETRIES)
    return base.BuildItem(
        name=res['name'], path=res['name'], is_file=False, size=None,
        timestamp=None)

  def _ListTargets(self, branch, page_token):
    """List build targets as build items."""
    client = self._GetClient()
    req = client.target().list(
        branch=branch, fields='targets/name,nextPageToken',
        pageToken=page_token)
    res = req.execute(num_retries=constant.NUM_RETRIES)
    build_items = [
        base.BuildItem(
            name=t['name'], path='%s/%s' % (branch, t['name']), is_file=False,
            size=None, timestamp=None)
        for t in res.get('targets', [])
    ]
    next_page_token = res.get('nextPageToken')
    return (build_items, next_page_token)

  def _GetTarget(self, branch, name):
    """Returns a build target as a build item."""
    client = self._GetClient()
    req = client.target().get(branch=branch, resourceId=name)
    res = req.execute(num_retries=constant.NUM_RETRIES)
    return base.BuildItem(
        name=res['name'], path='%s/%s' % (branch, res['name']), is_file=False,
        size=None, timestamp=None)

  def _ListBuilds(self, branch, target, page_token):
    """List builds as build items."""
    client = self._GetClient()
    req = client.build().list(
        buildType='submitted',
        buildAttemptStatus='complete',
        branch=branch,
        target=target,
        pageToken=page_token)
    res = req.execute(num_retries=constant.NUM_RETRIES)
    build_items = [
        base.BuildItem(
            name=b['buildId'],
            path='%s/%s/%s' % (branch, target, b['buildId']),
            is_file=False,
            size=None,
            timestamp=_ParseTimestamp(b.get('creationTimestamp')))
        for b in res.get('builds', [])
    ]
    # Add a latest folder to the first page
    if not page_token and build_items:
      latest_buid_item = base.BuildItem(
          name=LATEST,
          path='%s/%s/%s' % (branch, target, LATEST),
          is_file=False,
          size=None,
          timestamp=None,
          description=LATEST_BUILD_ITEM_DESCRIPTION)
      build_items.insert(0, latest_buid_item)

    next_page_token = res.get('nextPageToken')
    return (build_items, next_page_token)

  def _GetBuild(self, branch, target, build_id):
    """Returns a build as a build item."""
    if build_id == LATEST:
      res = self._GetLatestBuild(branch=branch, target=target)
    else:
      client = self._GetClient()
      req = client.build().get(target=target, buildId=build_id)
      res = req.execute(num_retries=constant.NUM_RETRIES)
    return base.BuildItem(
        name=res['buildId'],
        path='%s/%s/%s' % (branch, target, res['buildId']),
        is_file=False,
        size=None,
        timestamp=_ParseTimestamp(res.get('creationTimestamp')))

  def _GetLatestBuild(self, branch, target):
    """Returns the latest successful build for a given branch/target."""
    client = self._GetClient()
    req = client.build().list(
        buildType='submitted',
        buildAttemptStatus='complete',
        branch=branch,
        successful=True,
        target=target,
        maxResults=1)
    res = req.execute(num_retries=constant.NUM_RETRIES)
    builds = res.get('builds', [])
    if not builds:
      raise ValueError('latest build does not exist')
    return builds[0]

  def _ListBuildArtifacts(self, branch, target, build_id, page_token):
    """Lists build artifacts as build items."""
    client = self._GetClient()
    is_latest_build = build_id == LATEST

    # If selected folder is latest folder, make api call to get the build_id
    # for latest folder
    if is_latest_build:
      build_id = self._GetLatestBuild(branch=branch, target=target)['buildId']

    req = client.buildartifact().list(
        target=target,
        buildId=build_id,
        attemptId='latest',
        pageToken=page_token)
    res = req.execute(num_retries=constant.NUM_RETRIES)
    artifacts = res.get('artifacts', [])

    # if in latest folder, change its path to contain latest
    if is_latest_build:
      build_id = LATEST

    build_items = [
        base.BuildItem(
            name=a['name'],
            path='%s/%s/%s/%s' % (branch, target, build_id, a['name']),
            is_file=True,
            size=int(a['size']),
            timestamp=_ParseTimestamp(a.get('lastModifiedTime')))
        for a in artifacts if 'name' in a
    ]
    next_page_token = res.get('nextPageToken')
    return (build_items, next_page_token)

  def _GetBuildArtifact(self, branch, target, build_id, name):
    """Returns a build artifact as a build item."""
    # if build_id is 'latest', make sure find the latest resource
    if build_id == LATEST:
      build_id = self._GetLatestBuild(branch=branch, target=target)['buildId']

    client = self._GetClient()
    req = client.buildartifact().get(
        target=target, buildId=build_id, attemptId='latest', resourceId=name)
    res = req.execute(num_retries=constant.NUM_RETRIES)
    return base.BuildItem(
        name=res['name'],
        path='%s/%s/%s/%s' % (branch, target, build_id, res['name']),
        is_file=True,
        size=int(res['size']),
        timestamp=_ParseTimestamp(res.get('lastModifiedTime')))

  def DownloadFile(self, path, offset=0):
    """Download a build file.

    Args:
      path: a build file path
      offset: byte offset to read from
    Yields:
      FileChunks (data read, current position, total file size)
    Raises:
      ValueError: if the build does not contain a file.
    """
    parts = path.split('/', MAX_PATH_PARTS - 1)
    target = parts[1]
    build_id = parts[2]
    name = parts[3]
    client = self._GetClient()
    req = client.buildartifact().get(
        buildId=build_id,
        target=target,
        attemptId='latest',
        resourceId=name)
    res = req.execute(num_retries=constant.NUM_RETRIES)
    if not res:
      raise ValueError('build file %s does not exist' % path)

    dl_req = client.buildartifact().get_media(
        buildId=build_id,
        target=target,
        attemptId='latest',
        resourceId=name)

    buffer_ = io.BytesIO()
    downloader = apiclient.http.MediaIoBaseDownload(
        buffer_, dl_req, chunksize=constant.DEFAULT_CHUNK_SIZE)
    downloader._progress = offset  
    done = False
    while not done:
      status, done = downloader.next_chunk(num_retries=constant.NUM_RETRIES)
      yield file_util.FileChunk(
          data=buffer_.getvalue(),
          offset=status.resumable_progress,
          total_size=status.total_size)
      buffer_.seek(0)
      buffer_.truncate()
