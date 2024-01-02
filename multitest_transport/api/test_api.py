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

"""A module to provide test APIs."""
# Non-standard docstrings are used to generate the API documentation.

import endpoints
from protorpc import message_types
from protorpc import messages
from protorpc import remote


from multitest_transport.api import base
from multitest_transport.models import messages as mtt_messages
from multitest_transport.models import ndb_models


@base.MTT_API.api_class(resource_name='test', path='tests')
class TestApi(remote.Service):
  """A handler for Test API."""

  @base.ApiMethod(
      endpoints.ResourceContainer(message_types.VoidMessage),
      mtt_messages.TestList, path='/tests', http_method='GET',
      name='list')
  def List(self, request):
    """Lists test suites."""
    tests = list(ndb_models.Test.query().order(ndb_models.Test.name))
    tests = [
        test
        for test in tests
        if test.visibility_type is None
        or test.visibility_type == ndb_models.VisibilityType.PUBLIC
    ]
    test_msgs = mtt_messages.ConvertList(tests, mtt_messages.Test)
    return mtt_messages.TestList(tests=test_msgs)

  @base.ApiMethod(
      endpoints.ResourceContainer(mtt_messages.Test),
      mtt_messages.Test, path='/tests', http_method='POST',
      name='create')
  def Create(self, request):
    """Creates a test suite.

    Body:
      Test suite data
    """
    test = mtt_messages.Convert(
        request, ndb_models.Test, from_cls=mtt_messages.Test)
    test.put()
    return mtt_messages.Convert(test, mtt_messages.Test)

  @base.ApiMethod(
      endpoints.ResourceContainer(
          message_types.VoidMessage,
          test_id=messages.StringField(1, required=True)),
      mtt_messages.Test, path='{test_id}', http_method='GET',
      name='get')
  def Get(self, request):
    """Fetches a test suite.

    Parameters:
      test_id: Test ID, or zero for an empty test suite
    """
    if request.test_id == '0':
      # For ID 0, return an empty test object to use as a template in UI.
      test = ndb_models.Test(name='')
    else:
      test = mtt_messages.ConvertToKey(ndb_models.Test, request.test_id).get()
    if not test:
      raise endpoints.NotFoundException(
          'no test found for ID %s' % request.test_id)
    return mtt_messages.Convert(test, mtt_messages.Test)

  @base.ApiMethod(
      endpoints.ResourceContainer(
          mtt_messages.Test, test_id=messages.StringField(1, required=True)),
      mtt_messages.Test, path='{test_id}', http_method='PUT',
      name='update')
  def Update(self, request):
    """Updates a test suite.

    Body:
      Test suite data
    Parameters:
      test_id: Test ID
    """
    test = mtt_messages.ConvertToKey(ndb_models.Test, request.test_id).get()
    if not test:
      raise endpoints.NotFoundException(
          'no test found for ID %s' % request.test_id)
    request.id = request.test_id
    test = mtt_messages.Convert(request, ndb_models.Test, mtt_messages.Test)
    test.put()
    return mtt_messages.Convert(test, mtt_messages.Test)

  @base.ApiMethod(
      endpoints.ResourceContainer(
          message_types.VoidMessage,
          test_id=messages.StringField(1, required=True)),
      message_types.VoidMessage, path='{test_id}', http_method='DELETE',
      name='delete')
  def Delete(self, request):
    """Deletes a test suite.

    Parameters:
      test_id: Test ID
    """
    test_key = mtt_messages.ConvertToKey(ndb_models.Test, request.test_id)
    test_key.delete()
    return message_types.VoidMessage()
