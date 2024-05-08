# Copyright 2023 Google LLC
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

"""A module to provide build APIs."""
# Non-standard docstrings are used to generate the API documentation.

import os
import uuid

import endpoints
from protorpc import message_types
from protorpc import messages
from protorpc import remote
from tradefed_cluster.services import task_scheduler


from multitest_transport.api import base
from multitest_transport.build_manager import xts_requirements_detector
from multitest_transport.models import messages as mtt_messages
from multitest_transport.models import ndb_models
from multitest_transport.util import analytics
from multitest_transport.util import file_util

_ALLOWED_SOURCE_EXT = ['.zip', '.rar', '.tgz']


@base.MTT_API.api_class(resource_name='build', path='builds')
class BuildApi(remote.Service):
  """A handler for Build API."""

  @base.ApiMethod(
      endpoints.ResourceContainer(message_types.VoidMessage),
      mtt_messages.BuildList,
      path='/builds',
      http_method='GET',
      name='list',
  )
  def List(self, request):
    """Lists builds."""
    builds = list(ndb_models.Build.query().order(-ndb_models.Build.create_time))
    build_msgs = mtt_messages.ConvertList(builds, mtt_messages.Build)
    return mtt_messages.BuildList(builds=build_msgs)

  @base.ApiMethod(
      endpoints.ResourceContainer(mtt_messages.Build),
      mtt_messages.Build, path='/builds', http_method='POST',
      name='create')
  def Create(self, request):
    """Creates a build.

    Body:
      Build data
    """
    analytics.Log(analytics.BUILD_CATEGORY, analytics.CREATE_ACTION)
    build = ndb_models.Build(
        id=str(uuid.uuid4()),
        name=self._strip(request.name),
        fingerprint=self._strip(request.fingerprint),
        file_url=request.file_url,
        size=request.size,
        labels=request.labels,
    )
    self._ValidateBuild(build)
    build.put()
    task_scheduler.AddCallableTask(
        xts_requirements_detector.SyncApfeBuild, build.key.id()
    )
    return mtt_messages.Convert(build, mtt_messages.Build)

  @base.ApiMethod(
      endpoints.ResourceContainer(
          message_types.VoidMessage,
          build_id=messages.StringField(1, required=True),
      ),
      mtt_messages.Build,
      path='{build_id}',
      http_method='GET',
      name='get',
  )
  def Get(self, request):
    """Fetches a build.

    Parameters:
      build_id: Build ID
    """
    _, build = self._getBuild(request.build_id)
    return mtt_messages.Convert(build, mtt_messages.Build)

  @base.ApiMethod(
      endpoints.ResourceContainer(
          mtt_messages.Build, build_id=messages.StringField(1, required=True)
      ),
      mtt_messages.Build,
      path='{build_id}',
      http_method='PUT',
      name='update',
  )
  def Update(self, request):
    """Updates a build.

    Only name, fingerprint, labels, file_url and size fields are updatable.

    Body:
      Build data
    Parameters:
      build_id: Build ID
    """
    analytics.Log(analytics.BUILD_CATEGORY, analytics.UPDATE_ACTION)
    _, existing_build = self._getBuild(request.build_id)
    existing_fingerprint = existing_build.fingerprint
    existing_build.name = self._strip(request.name)
    existing_build.fingerprint = self._strip(request.fingerprint)
    existing_build.labels = request.labels
    existing_build.file_url = request.file_url
    existing_build.size = request.size
    self._ValidateBuild(existing_build)
    existing_build.put()
    if existing_fingerprint != existing_build.fingerprint:
      task_scheduler.AddCallableTask(
          xts_requirements_detector.SyncApfeBuild, request.build_id
      )
    return mtt_messages.Convert(existing_build, mtt_messages.Build)

  @base.ApiMethod(
      endpoints.ResourceContainer(
          message_types.VoidMessage,
          build_ids=messages.StringField(1, repeated=True),
      ),
      message_types.VoidMessage,
      path='/builds',
      http_method='DELETE',
      name='delete',
  )
  def Delete(self, request):
    """Deletes multiple builds.

    If any deletion fails, it will continue with remaining and raise an
    exception at the end.
    """
    analytics.Log(analytics.BUILD_CATEGORY, analytics.DELETE_ACTION)
    failed_ids = []
    for build_id in request.build_ids:
      try:
        self._Delete(build_id)
      except (endpoints.NotFoundException, endpoints.BadRequestException):
        failed_ids.append(build_id)
    if failed_ids:
      raise endpoints.BadRequestException(
          'Failed to delete builds: %s' % failed_ids
      )
    return message_types.VoidMessage()

  @base.ApiMethod(
      endpoints.ResourceContainer(
          mtt_messages.XtsRequirementsDetectionRequest,
          build_id=messages.StringField(1, required=True),
      ),
      mtt_messages.Build,
      path='{build_id}/detect',
      http_method='POST',
      name='detect',
  )
  def Detect(self, request):
    """Detects xTS requirements for a build.

    Body:
      Request to run xTS requirements detection
    Parameters:
      build_id: Build ID
    """
    updated_build = xts_requirements_detector.KickDetection(
        request.device_spec, request.test_resource_objs, request.build_id
    )
    return mtt_messages.Convert(updated_build, mtt_messages.Build)

  def _Delete(self, build_id):
    """Deletes a build."""
    build_key, _ = self._getBuild(build_id)
    build_key.delete()

  def _getBuild(self, build_id):
    """Gets a build."""
    build_key = mtt_messages.ConvertToKey(ndb_models.Build, build_id)
    build = build_key.get()
    if not build:
      raise endpoints.NotFoundException('Build %s not found' % build_id)
    return build_key, build

  def _strip(self, build_property):
    """Strips build property."""
    if not build_property:
      return None
    return build_property.strip()

  def _ValidateBuild(self, build):
    """Check validity of a given build.

    Args:
      build: a ndb_models.Build object.
    """
    if not build.name:
      raise endpoints.BadRequestException('Name in the request is unset.')
    if not build.fingerprint:
      raise endpoints.BadRequestException(
          'Fingerprint in the request is unset.'
      )
    if build.file_url:
      local_file_path = file_util.GetLocalFilePath(build.file_url)
      if not local_file_path:
        raise endpoints.BadRequestException(
            'Invalid local file URL %s.' % build.file_url
        )
      _, ext = os.path.splitext(local_file_path)
      if ext not in _ALLOWED_SOURCE_EXT:
        raise endpoints.BadRequestException(
            (
                'The file format for %s has not been supported. For information'
                ' on supported formats, see'
                ' https://docs.partner.android.com/partners/guides/afap/builds#prepare-build.'
            )
            % build.file_url
        )
