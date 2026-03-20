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

"""Tests for test_result_api."""
import os
from unittest import mock

from absl.testing import absltest
from protorpc import protojson
from tradefed_cluster import api_messages
from tradefed_cluster.api_messages import CommandState


from multitest_transport.api import api_test_util
from multitest_transport.api import test_result_api
from multitest_transport.models import messages
from multitest_transport.models import ndb_models
from multitest_transport.models import sql_models
from multitest_transport.util import tfc_client
from multitest_transport.util import xts_result


class TestResultApiTest(api_test_util.TestCase):

  def setUp(self):
    super(TestResultApiTest, self).setUp(test_result_api.TestResultApi)
    sql_models.db.uri = 'sqlite:///:memory:'
    sql_models.db.CreateTables()
    # Create three modules (2nd is incomplete, 3rd has failures)
    with sql_models.db.Session() as session:
      session.add_all([
          sql_models.TestModuleResult(
              id='module_1', test_run_id='test_run_id', attempt_id='attempt_id',
              name='module_1', complete=True, duration_ms=123,
              passed_tests=0, failed_tests=0, total_tests=0),
          sql_models.TestModuleResult(
              id='module_2', test_run_id='test_run_id', attempt_id='attempt_id',
              name='module_2', complete=False, duration_ms=456,
              passed_tests=0, failed_tests=0, total_tests=0),
          sql_models.TestModuleResult(
              id='module_3', test_run_id='test_run_id', attempt_id='attempt_id',
              name='module_3', complete=True, duration_ms=789,
              passed_tests=1, failed_tests=1, total_tests=3,
              test_cases=[
                  sql_models.TestCaseResult(
                      name='test_1', status=xts_result.TestStatus.PASS),
                  sql_models.TestCaseResult(
                      name='test_2', status=xts_result.TestStatus.FAIL),
                  sql_models.TestCaseResult(
                      name='test_3', status=xts_result.TestStatus.IGNORED),
              ]),
      ])

  def tearDown(self):
    sql_models.db.DropTables()
    super(TestResultApiTest, self).tearDown()

  def testListTestModuleResults(self):
    """Tests that module results can be fetched."""
    path = 'modules?attempt_id=attempt_id'
    response = self.app.get('/_ah/api/mtt/v1/test_results/' + path)
    self.assertEqual('200 OK', response.status)
    result_list = protojson.decode_message(
        messages.TestModuleResultList, response.body)
    # All modules returned, ordered by incomplete first, then by failures
    expected_results = [
        messages.TestModuleResult(
            id='module_2', name='module_2', complete=False, duration_ms=456,
            passed_tests=0, failed_tests=0, total_tests=0),
        messages.TestModuleResult(
            id='module_3', name='module_3', complete=True, duration_ms=789,
            passed_tests=1, failed_tests=1, total_tests=3),
        messages.TestModuleResult(
            id='module_1', name='module_1', complete=True, duration_ms=123,
            passed_tests=0, failed_tests=0, total_tests=0),
    ]
    self.assertEqual(result_list.results, expected_results)

  @mock.patch.object(tfc_client, 'GetRequest')
  def testListTestModuleResults_testRunId(self, mock_request):
    """Tests that module results can be fetched using a test run ID."""
    # Create test run with three attempts (latest is still RUNNING)
    ndb_models.TestRun(id='test_run_id', request_id='request_id').put()
    first_attempt = mock.MagicMock(
        attempt_id='INVALID', state=CommandState.COMPLETED)
    second_attempt = mock.MagicMock(
        attempt_id='attempt_id', state=CommandState.COMPLETED)
    third_attempt = mock.MagicMock(
        attempt_id='INVALID', state=CommandState.RUNNING)
    mock_request.return_value = mock.MagicMock(
        command_attempts=[first_attempt, second_attempt, third_attempt])

    # Results are fetched for the latest completed attempt
    path = 'modules?test_run_id=test_run_id'
    response = self.app.get('/_ah/api/mtt/v1/test_results/' + path)
    self.assertEqual('200 OK', response.status)
    result_list = protojson.decode_message(
        messages.TestModuleResultList, response.body)
    self.assertLen(result_list.results, 3)
    module_ids = [r.id for r in result_list.results]
    self.assertEqual(['module_2', 'module_3', 'module_1'], module_ids)

  def testListTestModuleResults_testRunNotFound(self):
    """Tests that an error is returned if the test run is not found."""
    path = 'modules?test_run_id=UNKNOWN'
    response = self.app.get('/_ah/api/mtt/v1/test_results/' + path,
                            expect_errors=True)
    self.assertEqual('404 Not Found', response.status)

  def testListTestModuleResults_missingAttemptId(self):
    """Tests that an error is returned if no attempt ID provided."""
    response = self.app.get('/_ah/api/mtt/v1/test_results/modules',
                            expect_errors=True)
    self.assertEqual('400 Bad Request', response.status)

  @mock.patch.object(test_result_api.TestResultApi,
                     '_GetLegacyTestModuleResults')
  @mock.patch.object(tfc_client, 'GetRequest')
  def testListTestModuleResults_noCompletedAttempts(self, mock_request,
                                                    mock_legacy_results):
    """Tests that legacy results are returned if no completed attempts found."""
    ndb_models.TestRun(id='test_run_id', request_id='request_id').put()
    mock_request.return_value = mock.MagicMock(command_attempts=[])
    mock_result_list = messages.TestModuleResultList(extra_info='Mock results')
    mock_legacy_results.return_value = mock_result_list

    path = 'modules?test_run_id=test_run_id'
    response = self.app.get('/_ah/api/mtt/v1/test_results/' + path)
    self.assertEqual('200 OK', response.status)
    result_list = protojson.decode_message(messages.TestModuleResultList,
                                           response.body)
    self.assertEqual(result_list, mock_result_list)

  @mock.patch.object(tfc_client, 'GetRequestInvocationStatus')
  @mock.patch.object(tfc_client, 'GetRequest')
  def testListTestModuleResults_legacy(self, mock_request,
                                       mock_invocation_status):
    """Tests that legacy module results are fetched if not found in DB."""
    # Create test run with a COMPLETED legacy attempts
    ndb_models.TestRun(id='test_run_id', request_id='123').put()
    attempt = mock.MagicMock(attempt_id='LEGACY', state=CommandState.COMPLETED)
    mock_request.return_value = mock.MagicMock(command_attempts=[attempt])
    # Return three test group statuses (2nd is incomplete, 3rd has failures)
    mock_invocation_status.return_value = api_messages.InvocationStatus(
        test_group_statuses=[
            api_messages.TestGroupStatus(
                name='legacy_module_1', is_complete=True, elapsed_time=123,
                total_test_count=0, passed_test_count=0, failed_test_count=0),
            api_messages.TestGroupStatus(
                name='legacy_module_2', is_complete=False, elapsed_time=456,
                total_test_count=0, passed_test_count=0, failed_test_count=0),
            api_messages.TestGroupStatus(
                name='legacy_module_3', is_complete=True, elapsed_time=789,
                total_test_count=3, passed_test_count=1, failed_test_count=1),
        ])

    # Legacy results are returned, ordered by incomplete first, then by failures
    path = 'modules?test_run_id=test_run_id'
    response = self.app.get('/_ah/api/mtt/v1/test_results/' + path)
    self.assertEqual('200 OK', response.status)
    result_list = protojson.decode_message(messages.TestModuleResultList,
                                           response.body)
    expected_results = [
        messages.TestModuleResult(
            id=None, name='legacy_module_2', complete=False, duration_ms=456,
            passed_tests=0, failed_tests=0, total_tests=0),
        messages.TestModuleResult(
            id=None, name='legacy_module_3', complete=True, duration_ms=789,
            passed_tests=1, failed_tests=1, total_tests=3),
        messages.TestModuleResult(
            id=None, name='legacy_module_1', complete=True, duration_ms=123,
            passed_tests=0, failed_tests=0, total_tests=0),
    ]
    self.assertEqual(result_list.results, expected_results)

  @mock.patch.dict(os.environ, {'IS_OMNILAB_BASED': 'true'})
  @mock.patch.object(test_result_api.olcs_session_stub, 'GetSharedStub')
  def testListTestModuleResults_omnilab(self, mock_get_stub):
    """Tests that module results can be fetched from OmniLab."""
    ndb_models.TestRun(id='test_run_id', request_id='request_id').put()
    mock_stub = mock_get_stub.return_value
    module_result = mock.MagicMock()
    module_result.name = 'module_1'
    module_result.complete = True
    module_result.duration_ms = 123
    module_result.passed_tests = 1
    module_result.failed_tests = 0
    module_result.total_tests = 1

    mock_request_message = mock.MagicMock()
    mock_request_message.test_module_results = [module_result]
    mock_request_message.command_attempts = [
        mock.MagicMock(state=api_messages.CommandState.RUNNING)
    ]
    mock_stub.GetRequest.return_value = mock_request_message

    path = 'modules?test_run_id=test_run_id'
    response = self.app.get('/_ah/api/mtt/v1/test_results/' + path)
    self.assertEqual('200 OK', response.status)
    result_list = protojson.decode_message(
        messages.TestModuleResultList, response.body
    )
    expected_results = [
        messages.TestModuleResult(
            name='module_1',
            complete=True,
            duration_ms=123,
            passed_tests=1,
            failed_tests=0,
            total_tests=1,
        ),
    ]
    self.assertEqual(result_list.results, expected_results)
    mock_stub.GetRequest.assert_called_with('request_id')

  @mock.patch.dict(os.environ, {'IS_OMNILAB_BASED': 'true'})
  @mock.patch.object(test_result_api.olcs_session_stub, 'GetSharedStub')
  def testListTestModuleResults_omnilab_sorting(self, mock_get_stub):
    """Tests that OmniLab module results are sorted by complete status."""
    ndb_models.TestRun(id='test_run_id', request_id='request_id').put()
    mock_stub = mock_get_stub.return_value

    m1 = mock.MagicMock(
        complete=True,
        duration_ms=0,
        passed_tests=0,
        failed_tests=0,
        total_tests=0,
    )
    m1.name = 'm1'
    m2 = mock.MagicMock(
        complete=False,
        duration_ms=0,
        passed_tests=0,
        failed_tests=0,
        total_tests=0,
    )
    m2.name = 'm2'

    mock_request_message = mock.MagicMock()
    mock_request_message.test_module_results = [m1, m2]
    mock_request_message.command_attempts = [
        mock.MagicMock(state=api_messages.CommandState.RUNNING)
    ]
    mock_stub.GetRequest.return_value = mock_request_message

    path = 'modules?test_run_id=test_run_id'
    response = self.app.get('/_ah/api/mtt/v1/test_results/' + path)
    result_list = protojson.decode_message(
        messages.TestModuleResultList, response.body
    )
    # m2 (False) should be first
    self.assertEqual(['m2', 'm1'], [r.name for r in result_list.results])

  @mock.patch.dict(os.environ, {'IS_OMNILAB_BASED': 'true'})
  @mock.patch.object(test_result_api.olcs_session_stub, 'GetSharedStub')
  @mock.patch.object(tfc_client, 'GetLatestFinishedAttempts')
  def testListTestModuleResults_omnilabNoRunningAttempt(
      self, mock_get_finished, mock_get_stub
  ):
    """Tests that it falls back if no running attempt found in OmniLab."""
    ndb_models.TestRun(id='test_run_id', request_id='request_id').put()
    mock_stub = mock_get_stub.return_value
    mock_stub.GetRequest.return_value = mock.MagicMock(command_attempts=[])
    mock_get_finished.return_value = [mock.MagicMock(attempt_id='attempt_id')]

    path = 'modules?test_run_id=test_run_id'
    response = self.app.get('/_ah/api/mtt/v1/test_results/' + path)
    self.assertEqual('200 OK', response.status)
    # Should fall back to DB results for 'attempt_id'
    result_list = protojson.decode_message(
        messages.TestModuleResultList, response.body
    )
    self.assertLen(result_list.results, 3)

  def testListTestCaseResults(self):
    """Tests that test case results can be fetched."""
    path = 'modules/module_3/test_cases'
    response = self.app.get('/_ah/api/mtt/v1/test_results/' + path)
    self.assertEqual('200 OK', response.status)
    result_list = protojson.decode_message(
        messages.TestCaseResultList, response.body)
    # All test cases returned, ordered by ID, with no next page
    self.assertLen(result_list.results, 3)
    test_case_names = [r.name for r in result_list.results]
    self.assertEqual(['test_1', 'test_2', 'test_3'], test_case_names)
    self.assertIsNone(result_list.next_page_token)

  def testListTestCaseResults_pagination(self):
    """Tests that test case results can be fetched with pagination."""
    path = 'modules/module_3/test_cases?max_results=2'
    response = self.app.get('/_ah/api/mtt/v1/test_results/' + path)
    self.assertEqual('200 OK', response.status)
    first_page = protojson.decode_message(
        messages.TestCaseResultList, response.body)
    # First page has two results and a page token
    self.assertLen(first_page.results, 2)
    test_case_names = [r.name for r in first_page.results]
    self.assertEqual(['test_1', 'test_2'], test_case_names)
    self.assertIsNotNone(first_page.next_page_token)

    path = ('modules/module_3/test_cases?max_results=2&page_token=%s' %
            first_page.next_page_token)
    response = self.app.get('/_ah/api/mtt/v1/test_results/' + path)
    self.assertEqual('200 OK', response.status)
    second_page = protojson.decode_message(
        messages.TestCaseResultList, response.body)
    # Second page has one result and no page token
    self.assertLen(second_page.results, 1)
    self.assertEqual('test_3', second_page.results[0].name)
    self.assertIsNone(second_page.next_page_token)

  def testListTestCaseResults_moduleNotFound(self):
    """Tests that an error is returned if the module is not found."""
    path = 'modules/UNKNOWN/test_cases'
    response = self.app.get('/_ah/api/mtt/v1/test_results/' + path,
                            expect_errors=True)
    self.assertEqual('404 Not Found', response.status)

  def testListTestCaseResults_nameFilter(self):
    """Tests that test case results can be filtered by name."""
    path = 'modules/module_3/test_cases?name=sT_2'
    response = self.app.get('/_ah/api/mtt/v1/test_results/' + path)
    result_list = protojson.decode_message(
        messages.TestCaseResultList, response.body)
    self.assertLen(result_list.results, 1)
    self.assertEqual('test_2', result_list.results[0].name)

  def testListTestCaseResults_statusFilter(self):
    """Tests that test case results can be filtered by status."""
    path = 'modules/module_3/test_cases?status=PASS&status=IGNORED'
    response = self.app.get('/_ah/api/mtt/v1/test_results/' + path)
    result_list = protojson.decode_message(
        messages.TestCaseResultList, response.body)
    self.assertLen(result_list.results, 2)
    test_case_names = [r.name for r in result_list.results]
    self.assertEqual(['test_1', 'test_3'], test_case_names)


if __name__ == '__main__':
  absltest.main()
