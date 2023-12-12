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

import endpoints
from protorpc import remote


from multitest_transport.api import base
from multitest_transport.models import messages as mtt_messages
from multitest_transport.models import ndb_models


@base.MTT_API.api_class(resource_name='build', path='builds')
class BuildApi(remote.Service):
  """A handler for Build API."""

  @base.ApiMethod(
      endpoints.ResourceContainer(mtt_messages.Build),
      mtt_messages.Build, path='/builds', http_method='POST',
      name='create')
  def Create(self, request):
    """Creates a build.

    Body:
      Build data
    """
    build = mtt_messages.Convert(
        request, ndb_models.Build, from_cls=mtt_messages.Build)
    build.put()
    return mtt_messages.Convert(build, mtt_messages.Build)
