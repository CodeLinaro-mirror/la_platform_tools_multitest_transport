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

from google.android.ci.build_v4.services.branch_service import client as branch_client
from google.android.ci.build_v4.services.build_artifact_service import client as build_artifact_client
from google.android.ci.build_v4.services.build_service import client as build_client
from google.android.ci.build_v4.services.target_service import client as target_client
from google.android.ci.build_v4.types import branch_service as branch_types
from google.android.ci.build_v4.types import build_artifact_service as build_artifact_types
from google.android.ci.build_v4.types import build_attempt as build_attempt_types
from google.android.ci.build_v4.types import build_service as build_service_types
from google.android.ci.build_v4.types import build_type as build_type_types
from google.android.ci.build_v4.types import target_service as target_types
from google.api_core import exceptions as google_exceptions
import grpc
from multitest_transport.plugins import base
from multitest_transport.util import constant
from multitest_transport.util import env
from multitest_transport.util import errors
from multitest_transport.util import file_util
from multitest_transport.util import oauth2_util
import requests


OAUTH2_SCOPES = ['https://www.googleapis.com/auth/androidbuild.internal']

MAX_PATH_PARTS = 4
LATEST = 'LATEST'
LATEST_BUILD_ITEM_DESCRIPTION = 'Linked to the latest successful build.'


def _FormatTimestamp(timestamp):
  """Format timestamp to remove timezone."""
  if not timestamp:
    return None
  return timestamp.replace(tzinfo=None)


class AndroidBuildProvider(base.BuildProvider):
  """A build provider for the Android Build system."""

  name = 'Android'
  auth_methods = [base.AuthorizationMethod.OAUTH2_SERVICE_ACCOUNT]
  oauth2_config = oauth2_util.OAuth2Config(
      client_id=env.GOOGLE_OAUTH2_CLIENT_ID,
      client_secret=env.GOOGLE_OAUTH2_CLIENT_SECRET,
      scopes=OAUTH2_SCOPES,
  )
  build_item_path_type = base.BuildItemPathType.DIRECTORY_FILE

  def __init__(self):
    super(AndroidBuildProvider, self).__init__()
    self._branch_client_val = None
    self._target_client_val = None
    self._build_client_val = None
    self._build_artifact_client_val = None

  @property
  def branch_client(self):
    if not self._branch_client_val:
      self._branch_client_val = branch_client.BranchServiceClient(
          credentials=self.GetCredentials()
      )
    return self._branch_client_val

  @property
  def target_client(self):
    if not self._target_client_val:
      self._target_client_val = target_client.TargetServiceClient(
          credentials=self.GetCredentials()
      )
    return self._target_client_val

  @property
  def build_client(self):
    if not self._build_client_val:
      self._build_client_val = build_client.BuildServiceClient(
          credentials=self.GetCredentials()
      )
    return self._build_client_val

  @property
  def build_artifact_client(self):
    if not self._build_artifact_client_val:
      self._build_artifact_client_val = (
          build_artifact_client.BuildArtifactServiceClient(
              credentials=self.GetCredentials()
          )
      )
    return self._build_artifact_client_val

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
            branch=parts[0], target=parts[1], page_token=page_token
        )
      elif len(parts) == 3:
        if item_type == base.BuildItemType.DIRECTORY:
          return [], None
        return self._ListBuildArtifacts(
            branch=parts[0],
            target=parts[1],
            build_id=parts[2],
            page_token=page_token,
        )
      raise ValueError('invalid path: %s' % path)
    except google_exceptions.NotFound as e:
      raise errors.FileNotFoundError('File %s not found' % path) from e
    except grpc.RpcError as e:
      if hasattr(e, 'code') and e.code() == grpc.StatusCode.NOT_FOUND:
        raise errors.FileNotFoundError('File %s not found' % path) from e
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
            branch=parts[0], target=parts[1], build_id=parts[2]
        )
      elif len(parts) == 4:
        return self._GetBuildArtifact(
            branch=parts[0], target=parts[1], build_id=parts[2], name=parts[3]
        )
      raise ValueError('invalid path: %s' % path)
    except google_exceptions.NotFound:
      return None
    except grpc.RpcError as e:
      if hasattr(e, 'code') and e.code() == grpc.StatusCode.NOT_FOUND:
        return None
      raise

  def _ListBranches(self, page_token):
    """List branches as build items."""
    request = branch_types.ListBranchesRequest(page_token=page_token)
    response = self.branch_client.list(request=request)

    build_items = [
        base.BuildItem(
            name=b.name, path=b.name, is_file=False, size=None, timestamp=None
        )
        for b in response.branches
    ]
    return (build_items, response.next_page_token)

  def _GetBranch(self, name):
    """Returns a branch as a build item."""
    request = branch_types.GetBranchRequest(name=name)
    response = self.branch_client.get(request=request)
    return base.BuildItem(
        name=response.branch.name,
        path=response.branch.name,
        is_file=False,
        size=None,
        timestamp=None,
    )

  def _ListTargets(self, branch, page_token):
    """List build targets as build items."""
    request = target_types.ListTargetsRequest(
        branch=branch, page_token=page_token
    )
    response = self.target_client.list(request=request)

    build_items = [
        base.BuildItem(
            name=t.name,
            path='%s/%s' % (branch, t.name),
            is_file=False,
            size=None,
            timestamp=None,
        )
        for t in response.targets
    ]
    return (build_items, response.next_page_token)

  def _GetTarget(self, branch, name):
    """Returns a build target as a build item."""
    request = target_types.GetTargetRequest(branch=branch, target=name)
    response = self.target_client.get(request=request)
    return base.BuildItem(
        name=response.target.name,
        path='%s/%s' % (branch, response.target.name),
        is_file=False,
        size=None,
        timestamp=None,
    )

  def _ListBuilds(self, branch, target, page_token):
    """List builds as build items."""
    request = build_service_types.ListBuildsRequest(
        build_type=build_type_types.BuildType.SUBMITTED,
        build_attempt_status=build_attempt_types.BuildAttempt.BuildStatus.COMPLETE,
        branches=[branch],
        targets=[target],
        page_token=page_token,
    )
    response = self.build_client.list(request=request)

    build_items = [
        base.BuildItem(
            name=b.build_id,
            path='%s/%s/%s' % (branch, target, b.build_id),
            is_file=False,
            size=None,
            timestamp=_FormatTimestamp(b.creation_timestamp),
        )
        for b in response.builds
    ]
    # Add a latest folder to the first page
    if not page_token and build_items:
      latest_buid_item = base.BuildItem(
          name=LATEST,
          path='%s/%s/%s' % (branch, target, LATEST),
          is_file=False,
          size=None,
          timestamp=None,
          description=LATEST_BUILD_ITEM_DESCRIPTION,
      )
      build_items.insert(0, latest_buid_item)

    return (build_items, response.next_page_token)

  def _GetBuild(self, branch, target, build_id):
    """Returns a build as a build item."""
    if build_id == LATEST:
      response = self._GetLatestBuild(branch=branch, target=target)
      build = response
    else:
      request = build_service_types.GetBuildRequest(
          target=target, build_id=build_id
      )
      response = self.build_client.get(request=request)
      build = response.build
    return base.BuildItem(
        name=build.build_id,
        path='%s/%s/%s' % (branch, target, build.build_id),
        is_file=False,
        size=None,
        timestamp=_FormatTimestamp(build.creation_timestamp),
    )

  def _GetLatestBuild(self, branch, target):
    """Returns the latest successful build for a given branch/target."""
    request = build_service_types.ListBuildsRequest(
        build_type=build_type_types.BuildType.SUBMITTED,
        build_attempt_status=build_attempt_types.BuildAttempt.BuildStatus.COMPLETE,
        branches=[branch],
        successful=True,
        targets=[target],
        page_size=1,
    )
    response = self.build_client.list(request=request)

    if not response.builds:
      raise ValueError('latest build does not exist')
    return response.builds[0]

  def _ListBuildArtifacts(self, branch, target, build_id, page_token):
    """Lists build artifacts as build items."""
    is_latest_build = build_id == LATEST
    # If selected folder is latest folder, make api call to get the build_id
    # for latest folder
    if is_latest_build:
      build_id = self._GetLatestBuild(branch=branch, target=target).build_id

    request = build_artifact_types.ListBuildArtifactsRequest(
        target=target,
        build_id=build_id,
        build_attempt_id='latest',
        page_token=page_token,
    )
    response = self.build_artifact_client.list(request=request)

    # if in latest folder, change its path to contain latest
    if is_latest_build:
      build_id = LATEST

    build_items = [
        base.BuildItem(
            name=a.name,
            path='%s/%s/%s/%s' % (branch, target, build_id, a.name),
            is_file=True,
            size=int(a.size),
            timestamp=_FormatTimestamp(a.last_modified_time),
        )
        for a in response.artifacts
        if a.name
    ]
    return (build_items, response.next_page_token)

  def _GetBuildArtifact(self, branch, target, build_id, name):
    """Returns a build artifact as a build item."""
    # if build_id is 'latest', make sure find the latest responseource
    if build_id == LATEST:
      build_id = self._GetLatestBuild(branch=branch, target=target).build_id

    request = build_artifact_types.GetBuildArtifactRequest(
        target=target,
        build_id=build_id,
        build_attempt_id='latest',
        build_artifact_name=name,
    )
    response = self.build_artifact_client.get(request=request)
    a = response.build_artifact_metadata
    return base.BuildItem(
        name=a.name,
        path='%s/%s/%s/%s' % (branch, target, build_id, a.name),
        is_file=True,
        size=int(a.size),
        timestamp=_FormatTimestamp(a.last_modified_time),
    )

  def DownloadFile(self, path, offset=0):
    """Download a build file."""
    parts = path.split('/', MAX_PATH_PARTS - 1)
    target = parts[1]
    build_id = parts[2]
    name = parts[3]
    if build_id == LATEST:
      build_id = self._GetLatestBuild(branch=parts[0], target=target).build_id

    request = build_artifact_types.GetDownloadUrlRequest(
        build_id=build_id,
        target=target,
        build_attempt_id='latest',
        build_artifact_name=name,
    )
    response = self.build_artifact_client.get_download_url(request=request)

    headers = {}
    if offset:
      headers['Range'] = 'bytes=%d-' % offset
    try:
      resp = requests.get(
          response.signed_url,
          headers=headers,
          stream=True,
          timeout=constant.HTTP_TIMEOUT_SECONDS,
      )
      # Raise HTTPError for bad responses (4xx or 5xx)
      resp.raise_for_status()
    except requests.exceptions.RequestException as e:
      raise ValueError('failed to download file: %s' % path) from e

    if offset and resp.status_code != 206:
      raise ValueError(
          'Range request ignored, cannot resume download from offset %d'
          % offset
      )

    content_range = resp.headers.get('content-range')
    if content_range:
      total_size = int(content_range.split('/')[-1])
    else:
      total_size = int(resp.headers.get('content-length', 0))

    current_offset = offset
    for chunk in resp.iter_content(chunk_size=constant.DEFAULT_CHUNK_SIZE):
      if not chunk:
        continue
      current_offset += len(chunk)
      yield file_util.FileChunk(
          data=chunk, offset=current_offset, total_size=total_size
      )
