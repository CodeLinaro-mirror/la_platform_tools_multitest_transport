# Copyright 2021 Google LLC
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

"""Test results APIs."""
import os
import typing

# Non-standard docstrings are used to generate the API documentation.

import endpoints
from protorpc import message_types
from protorpc import messages
from protorpc import remote


from multitest_transport.api import base
from multitest_transport.models import messages as mtt_messages
from multitest_transport.models import ndb_models
from multitest_transport.models import sql_models
from multitest_transport.util import olcs_session_stub
from multitest_transport.util import tfc_client
from multitest_transport.util import xts_result
from tradefed_cluster import common


@base.MTT_API.api_class(resource_name='test_result', path='test_results')
class TestResultApi(remote.Service):
  """Test results API handler."""

  @base.ApiMethod(
      endpoints.ResourceContainer(
          message_types.VoidMessage,
          attempt_id=messages.StringField(1),
          test_run_id=messages.StringField(2)),
      mtt_messages.TestModuleResultList,
      path='modules', http_method='GET', name='list_modules')
  def ListTestModuleResults(self, request):
    """Fetches a page of test module results.

    Incomplete modules are returned first, and results are then sorted by
    descending failure count.

    Parameters:
      attempt_id: Test run attempt ID
      test_run_id: Test run ID (used if attempt_id not provided)
    """
    if request.attempt_id:
      # Use attempt_id directly if provided
      return mtt_messages.TestModuleResultList(
          results=self._GetTestModuleResults(request.attempt_id))

    if not request.test_run_id:
      # Invalid request (test_run_id and attempt_id not provided)
      raise endpoints.BadRequestException('Test run ID or attempt ID required')

    # Determine attempt_id from test_run_id (latest finished attempt)
    test_run_id = request.test_run_id
    test_run = ndb_models.TestRun.get_by_id(test_run_id)
    if not test_run:
      raise endpoints.NotFoundException('Test run %s not found' % test_run_id)

    if not test_run.request_id:
      return mtt_messages.TestModuleResultList(
          extra_info='Test run %s not started' % test_run_id)

    # For ATS 2.0 (OmniLab based), return the currently running attempt's
    # results if present.
    if os.environ.get('IS_OMNILAB_BASED') == 'true':
      stub = olcs_session_stub.GetSharedStub()
      request_message = stub.GetRequest(test_run.request_id)
      if request_message:
        attempts = request_message.command_attempts or []
        running_attempt = next(
            (a for a in attempts if a.state == common.CommandState.RUNNING),
            None,
        )
        if running_attempt:
          results = [
              mtt_messages.TestModuleResult(
                  name=r.name,
                  complete=r.complete,
                  duration_ms=r.duration_ms,
                  passed_tests=r.passed_tests,
                  failed_tests=r.failed_tests,
                  total_tests=r.total_tests,
              )
              for r in request_message.test_module_results
          ]
          results.sort(key=lambda r: r.complete)
          return mtt_messages.TestModuleResultList(results=results)

    attempts = tfc_client.GetLatestFinishedAttempts(test_run.request_id)
    result_list = mtt_messages.TestModuleResultList()
    for attempt in attempts:
      result_list.results.extend(self._GetTestModuleResults(attempt.attempt_id))
    if not result_list.results:
      # No results found for latest attempt, try fetching legacy results instead
      return self._GetLegacyTestModuleResults(str(test_run.request_id))
    return result_list

  def _GetTestModuleResults(
      self, attempt_id: str) -> typing.List[mtt_messages.TestModuleResult]:
    """Fetch test module results from the DB."""
    with sql_models.db.Session() as session:
      query = session.query(sql_models.TestModuleResult)  # pyrefly: ignore[missing-attribute]
      query = query.order_by(sql_models.TestModuleResult.complete,
                             sql_models.TestModuleResult.failed_tests.desc(),
                             sql_models.TestModuleResult.id)
      query = query.filter_by(attempt_id=attempt_id)
      modules = query.all()
    return mtt_messages.ConvertList(modules, mtt_messages.TestModuleResult)

  def _GetLegacyTestModuleResults(
      self, request_id: str
  ) -> mtt_messages.TestModuleResultList:
    """Fetch legacy test module results from TFC."""
    invocation_status = tfc_client.GetRequestInvocationStatus(request_id)
    test_group_statuses = sorted(
        invocation_status.test_group_statuses or [],
        key=lambda s: (s.is_complete, -s.failed_test_count))
    results = mtt_messages.ConvertList(test_group_statuses,
                                       mtt_messages.TestModuleResult)
    return mtt_messages.TestModuleResultList(
        results=results,
        extra_info='Legacy test results from request %s' % request_id)

  @base.ApiMethod(
      endpoints.ResourceContainer(
          message_types.VoidMessage,
          module_id=messages.StringField(1, required=True),
          max_results=messages.IntegerField(
              2, default=base.DEFAULT_MAX_RESULTS),
          page_token=messages.StringField(3),
          status=messages.EnumField(xts_result.TestStatus, 4, repeated=True),
          name=messages.StringField(5)),
      mtt_messages.TestCaseResultList,
      path='modules/{module_id}/test_cases',
      http_method='GET', name='list_test_cases')
  def ListTestCaseResults(self, request):
    """Fetches a page of test case results.

    Parameters:
      module_id: Test module ID
      max_results: Maximum number of test results to return
      page_token: Token for pagination
      status: Set of statuses to include
      name: Partial name filter (case-insensitive)
    """
    with sql_models.db.Session() as session:
      # Find parent module
      module = session.query(sql_models.TestModuleResult).get(request.module_id)  # pyrefly: ignore[missing-attribute]
      if not module:
        raise endpoints.NotFoundException(
            'Module %s not found' % request.module_id)
      # Initialize query (ordered by insertion order)
      query = session.query(sql_models.TestCaseResult)  # pyrefly: ignore[missing-attribute]
      query = query.order_by(sql_models.TestCaseResult.id).with_parent(module)
      # Apply page token (<last id>)
      if request.page_token:
        query = query.filter(
            sql_models.TestCaseResult.id > int(request.page_token))
      # Apply filters
      if request.status:
        query = query.filter(
            sql_models.TestCaseResult.status.in_(request.status))
      if request.name:
        query = query.filter(
            sql_models.TestCaseResult.name.contains(request.name))
      # Fetch at most N + 1 results
      if request.max_results and request.max_results > 0:
        query = query.limit(request.max_results + 1)
      test_cases = query.all()

    # Generate next page token and response
    next_page_token = None
    if request.max_results and 0 < request.max_results < len(test_cases):
      test_cases = test_cases[:-1]
      next_page_token = str(test_cases[-1].id)
    results = mtt_messages.ConvertList(test_cases, mtt_messages.TestCaseResult)
    return mtt_messages.TestCaseResultList(
        results=results, next_page_token=next_page_token)
