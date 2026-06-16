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

"""A base class for API handlers."""
import functools
import http
import importlib.abc
import importlib.resources
import logging
import sys
import traceback

# Workaround for pyglib.resources on Python 3.10 in MTT container environment.
if sys.version_info < (3, 11):
  sys.modules['importlib.resources.abc'] = importlib.abc
  importlib.resources.abc = importlib.abc

import endpoints  
from tradefed_cluster.util import ndb_shim as ndb


from multitest_transport.api import openapi

DEFAULT_MAX_RESULTS = 25  # The default number of max results per page.

MTT_API = endpoints.api(
    name='mtt',
    version='v1',
    description='Android Test Station API',
    allowed_client_ids=['anonymous', endpoints.API_EXPLORER_CLIENT_ID],
    scopes=[endpoints.EMAIL_SCOPE])


def ApiMethod(request_type, response_type, **kwargs):
  """API method decorator."""
  endpoints_wrapper = endpoints.method(request_type, response_type, **kwargs)
  def _Decorator(method):
    # Wraps execution in an NDB context
    api_method = ndb.with_ndb_context(method)
    # Configures endpoint
    api_method = endpoints_wrapper(api_method)
    # Add method summary and description
    descriptor_wrapper = openapi.ApiMethodDescriptor(
        summary=method.__doc__.splitlines()[0] if method.__doc__ else None,
        description=method.__doc__)
    api_method = descriptor_wrapper(api_method)
    # Handles any uncaught exceptions
    api_method = ConvertExceptions(api_method)
    return api_method
  return _Decorator


def _BuildErrorMessage(**kwargs):
  """Builds an error message with given kwargs."""
  return ','.join('%s=%s' % item for item in kwargs.items())


class ApiError(endpoints.ServiceException):
  """Base class for all API errors."""

  def __init__(self, cause=None, status=None, message=None, **kwargs):
    self.cause = cause
    self.http_status = status or http.HTTPStatus.INTERNAL_SERVER_ERROR.value
    kwargs['message'] = message or http.HTTPStatus(self.http_status).phrase
    kwargs['stacktrace'] = traceback.extract_tb(sys.exc_info()[2])
    super(ApiError, self).__init__(_BuildErrorMessage(**kwargs))


def ConvertExceptions(method):
  """Converts exceptions into ApiErrors, to include error and stacktrace."""
  @functools.wraps(method)
  def _Wrapper(*args, **kwargs):
    try:
      return method(*args, **kwargs)
    except Exception as e:  
      logging.exception('API handler exception:')
      raise ApiError(
          cause=e, status=getattr(e, 'http_status', None), message=str(e))
  return _Wrapper
