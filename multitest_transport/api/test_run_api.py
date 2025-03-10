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

"""A module to provide test run APIs."""
# Non-standard docstrings are used to generate the API documentation.

import logging
import os
from typing import Optional
import zipfile

import endpoints
from protorpc import message_types
from protorpc import messages
from protorpc import protojson
from protorpc import remote
from tradefed_cluster import datastore_util
from tradefed_cluster.common import IsFinalCommandState
from tradefed_cluster.util import ndb_shim as ndb


from multitest_transport.api import base
from multitest_transport.models import messages as mtt_messages
from multitest_transport.models import ndb_models
from multitest_transport.models import sql_models
from multitest_transport.test_scheduler import test_kicker
from multitest_transport.test_scheduler import test_run_manager
from multitest_transport.util import analytics
from multitest_transport.util import env
from multitest_transport.util import file_util
from multitest_transport.util import tfc_client
from multitest_transport.util import olcs_session_stub


@base.MTT_API.api_class(resource_name='test_run', path='test_runs')
class TestRunApi(remote.Service):
  """A handler for Test Run API."""

  def __init__(
      self,
      olcs_client: Optional[olcs_session_stub.OlcsSessionStub] = None,
  ):
    if olcs_client:
      self._olcs_session_stub = olcs_client
    else:
      self._olcs_session_stub = olcs_session_stub.OlcsSessionStub(None)

  @base.ApiMethod(
      endpoints.ResourceContainer(
          message_types.VoidMessage,
          max_results=messages.IntegerField(
              1, default=base.DEFAULT_MAX_RESULTS
          ),
          page_token=messages.StringField(2),
          backwards=messages.BooleanField(3),
          labels=messages.StringField(4, repeated=True),
          test=messages.StringField(5),
          device_specs=messages.StringField(6, repeated=True),
          state=messages.EnumField(ndb_models.TestRunState, 7, repeated=True),
          device_build_id=messages.StringField(8),
          test_package_info=messages.StringField(9),
          prev_test_run_id=messages.StringField(10),
          filter_query=messages.StringField(11, repeated=True),
      ),
      mtt_messages.TestRunSummaryList,
      path='/test_runs',
      http_method='GET',
      name='list',
  )
  def ListSummaries(self, request):
    """Fetches a page of test run summaries.

    Parameters:
      max_results: Maximum number of test runs to return
      page_token: Token for pagination
      backwards: True to fetch previous page of results
      labels: Labels to look for
      test: Test name to look for
      device_spec: A device spec to look for
      state: List of test run states to include
      device_build_id: Build ID to look for
      test_package_info: Test package to look for
      prev_test_run_id: Previous test run ID
      filter_query: Additional filters to apply (applied to test name, run
        target, labels, test package name and version, device build ID and
        product)
    """
    query = ndb_models.TestRunSummary.query().order(
        -ndb_models.TestRunSummary.create_time, ndb_models.TestRunSummary.key
    )
    query = self._ApplyQueryFilters(query, request)
    result_filter = self._BuildTestRunFilterFunction(request)
    test_runs, prev_cursor, next_cursor = datastore_util.FetchPage(
        query,
        request.max_results,
        page_cursor=request.page_token,
        backwards=request.backwards,
        result_filter=result_filter,
    )
    return mtt_messages.TestRunSummaryList(
        test_runs=mtt_messages.ConvertList(
            test_runs, mtt_messages.TestRunSummary
        ),
        prev_page_token=prev_cursor,
        next_page_token=next_cursor,
    )

  def _ApplyQueryFilters(self, query, request):
    """Applies simple predicates (equality, AND) to a test run query."""
    if request.labels:
      for label in request.labels:
        query = query.filter(ndb_models.TestRunSummary.labels == label)

    if request.test:
      query = query.filter(ndb_models.TestRunSummary.test_name == request.test)

    if request.device_specs:
      query = query.filter(
          ndb_models.TestRunSummary.device_specs == request.device_specs
      )

    if request.test_package_info:
      filter_data = request.test_package_info.split()
      query = query.filter(
          ndb_models.TestRunSummary.test_package_info.name == filter_data[0]
          and ndb_models.TestRunSummary.test_package_info.version
          == filter_data[1]
      )

    if request.prev_test_run_id:
      prev_key = mtt_messages.ConvertToKey(
          ndb_models.TestRun, request.prev_test_run_id
      )
      query = query.filter(
          ndb_models.TestRunSummary.prev_test_run_key == prev_key
      )

    return query

  def _BuildTestRunFilterFunction(self, request):
    """Construct a test run filter for complex predicates (OR, IN)."""
    build_ids = []
    if request.device_build_id:
      build_ids = request.device_build_id.split(';')

    def _Filter(test_run):
      package = test_run.test_package_info
      devices = test_run.test_devices

      if request.state and test_run.state not in request.state:
        return False

      if build_ids and not next(
          (d for d in devices if d.build_id in build_ids), None
      ):
        return False

      for value in request.filter_query:
        if not value:
          continue
        if not (
            value == test_run.test_name
            or value in test_run.device_specs
            or value in test_run.labels
            or (package and (package.name == value or package.version == value))
            or next(
                (
                    d
                    for d in devices
                    if d.build_id == value or d.product == value
                ),
                None,
            )
        ):
          return False
      return True

    return _Filter

  @base.ApiMethod(
      endpoints.ResourceContainer(
          message_types.VoidMessage,
          test_run_id=messages.StringField(1, required=True),
      ),
      mtt_messages.TestRun,
      path='{test_run_id}',
      http_method='GET',
      name='get',
  )
  def Get(self, request):
    """Fetches a test run.

    Parameters:
      test_run_id: Test run ID
    """
    test_run = ndb_models.TestRun.get_by_id(request.test_run_id)
    if not test_run:
      raise endpoints.NotFoundException(
          'no test run found for ID %s' % request.test_run_id
      )
    return mtt_messages.Convert(test_run, mtt_messages.TestRun)

  @base.ApiMethod(
      endpoints.ResourceContainer(mtt_messages.NewTestRunRequest),
      mtt_messages.TestRun,
      path='/test_runs',
      http_method='POST',
      name='new',
  )
  def New(self, request):
    """Creates a new test run.

    Body:
      Test run request data
    """
    logging.info('New test run request: %s', protojson.encode_message(request))  # pytype: disable=module-attr
    labels = request.labels
    test_run_config = mtt_messages.Convert(
        request.test_run_config, ndb_models.TestRunConfig
    )
    if not test_run_config.device_specs:
      if not test_run_config.run_target:
        raise endpoints.BadRequestException(
            'test_run_config.(device_specs or run_target) must be set'
        )
      # For old run targets are one or more device serials. Convert them to
      # device specs for backward compatibility
      test_run_config.device_specs = mtt_messages.ConvertToDeviceSpecs(
          test_run_config.run_target
      )
      test_run_config.run_target = None
    # start test run
    test_run = test_kicker.CreateTestRun(
        labels=labels,
        test_run_config=test_run_config,
        rerun_context=request.rerun_context,
        rerun_configs=mtt_messages.ConvertList(
            request.rerun_configs, ndb_models.TestRunConfig
        ),
    )

    if request.required_report_id:

      def _Txn():
        required_report = mtt_messages.ConvertToKey(
            ndb_models.RequiredReport, request.required_report_id
        ).get()
        if not required_report:
          return
        required_report.test_run_key = test_run.key
        required_report.put()
        return required_report

      required_report = ndb.transaction(_Txn)
      report_type = required_report.type if required_report else 'unknown'
      analytics.Log(
          analytics.BUILD_CATEGORY,
          analytics.RUN_TEST_ACTION,
          label=str(report_type),
      )
    return mtt_messages.Convert(test_run, mtt_messages.TestRun)

  @base.ApiMethod(
      endpoints.ResourceContainer(
          message_types.VoidMessage,
          test_run_id=messages.StringField(1, required=True),
      ),
      message_types.VoidMessage,
      path='{test_run_id}/cancel',
      http_method='POST',
      name='cancel',
  )
  def Cancel(self, request):
    """Cancels a test run.

    Parameters:
      test_run_id: Test run ID
    """
    try:
      test_run_manager.SetTestRunState(
          test_run_id=request.test_run_id,
          state=ndb_models.TestRunState.CANCELED,
      )
    except test_run_manager.TestRunNotFoundError:
      raise endpoints.NotFoundException(
          'No test run found for ID %s' % request.test_run_id
      )
    return message_types.VoidMessage()

  def _Delete(self, test_run_id):
    """Deletes a test run and all related files if it is in a final state."""
    test_run_key = mtt_messages.ConvertToKey(ndb_models.TestRun, test_run_id)
    test_run = test_run_key.get()

    if not test_run:
      raise endpoints.NotFoundException('Test run %s not found' % test_run_id)

    if not test_run.IsFinal():
      raise endpoints.BadRequestException(
          'Cannot delete non-final test run %s' % test_run_id
      )

    # Remove output files (i.e. test_runs/<ID>/ and test_runs/<ID>.zip).
    if test_run.output_path:
      output_dir = os.path.normpath(os.path.join(test_run.output_path, '..'))
      output_dir_url = file_util.GetAppStorageUrl([output_dir])
      file_util.FileHandle.Get(output_dir_url).DeleteDir()
      output_zip_url = file_util.GetAppStorageUrl([output_dir + '.zip'])
      file_util.FileHandle.Get(output_zip_url).Delete()

    # Delete test results database
    with sql_models.db.Session() as session:
      session.query(sql_models.TestModuleResult).filter_by(
          test_run_id=test_run_id
      ).delete()

    test_run_key.delete()

  @base.ApiMethod(
      endpoints.ResourceContainer(
          message_types.VoidMessage,
          test_run_ids=messages.StringField(1, repeated=True),
      ),
      message_types.VoidMessage,
      path='/test_runs',
      http_method='DELETE',
      name='delete',
  )
  def DeleteMulti(self, request):
    """Deletes multiple test runs.

    If any deletion fails, it will continue with remaining and raise an
    exception at the end.
    """
    failed_ids = []
    for test_run_id in request.test_run_ids:
      try:
        self._Delete(test_run_id)
      except (endpoints.NotFoundException, endpoints.BadRequestException):
        failed_ids.append(test_run_id)
    if failed_ids:
      raise endpoints.BadRequestException(
          'Failed to delete test runs: %s' % failed_ids
      )
    return message_types.VoidMessage()

  @base.ApiMethod(
      endpoints.ResourceContainer(
          message_types.VoidMessage,
          test_run_id=messages.StringField(1, required=True),
          attempt_id=messages.StringField(2, required=True),
          path=messages.StringField(3, required=True),
          offset=messages.IntegerField(4),
          length=messages.IntegerField(5, default=25 * 1024),
      ),
      mtt_messages.FileSegment,
      path='{test_run_id}/output',
      http_method='GET',
      name='output',
  )
  def TailOutputFile(self, request):
    """Reads from the end of a test run output file.

    Parameters:
      test_run_id: Test run ID
      attempt_id: Attempt ID
      path: Relative file path
      offset: Position to read from
      length: Number of bytes to read
    """
    # find test run
    test_run = ndb_models.TestRun.get_by_id(request.test_run_id)
    if not test_run:
      raise endpoints.NotFoundException(
          'Test run %s not found' % request.test_run_id
      )

    # get attempt and check whether it is active
    attempt = tfc_client.GetAttempt(test_run.request_id, request.attempt_id)
    if attempt is None:
      raise endpoints.NotFoundException(
          'Command attempt %s not found' % request.attempt_id
      )

    # determine file URL
    if IsFinalCommandState(attempt.state):
      file_url = file_util.GetOutputFileUrl(test_run, attempt, request.path)
    else:
      file_url = file_util.GetWorkFileUrl(attempt, request.path)

    # read file contents
    if request.offset is None:
      # no offset given, fetch from end of file up to length limit
      file_segment = file_util.TailFile(file_url, length=request.length)
    else:
      # offset provided, fetch bytes from offset up to length limit
      file_segment = file_util.ReadFile(
          file_url, offset=request.offset, length=request.length
      )
    if file_segment is None:
      raise endpoints.NotFoundException('File %s not found' % request.path)
    return mtt_messages.Convert(file_segment, mtt_messages.FileSegment)

  @base.ApiMethod(
      endpoints.ResourceContainer(
          message_types.VoidMessage,
          test_run_id=messages.StringField(1, required=True),
      ),
      mtt_messages.TestRunMetadataList,
      path='{test_run_id}/metadata',
      http_method='GET',
      name='metadata',
  )
  def GetMetadata(self, request):
    """Returns a test run's metadata.

    Parameters:
      test_run_id: Test run ID
    """
    test_run = ndb_models.TestRun.get_by_id(request.test_run_id)
    if not test_run:
      raise endpoints.NotFoundException(
          'No test run found for ID %s' % request.test_run_id
      )
    return mtt_messages.TestRunMetadataList(
        test_runs=self._GetMetadataList(test_run), server_version=env.VERSION
    )

  def _GetMetadataList(self, test_run):
    """Return a list containing a test run and all of its ancestors."""
    test_runs = []
    while test_run:
      test_runs.append(self._GetMetadata(test_run))
      if not test_run.IsRerun():
        break  # no more test runs to append
      if test_run.IsRemoteRerun():
        # remaining test run metadata is in the previous context
        context_file = test_run.GetRerunContextFile()
        if context_file:
          test_runs.extend(self._LoadMetadataFromContextFile(context_file.url))
        break
      test_run = test_run.prev_test_run_key.get()
    return test_runs

  def _GetMetadata(self, test_run):
    """Get the metadata for a test run."""
    completed_attempts = []
    if test_run.request_id:
      request = tfc_client.GetRequest(test_run.request_id)
      attempts = request.command_attempts or []
      completed_attempts = [
          attempt for attempt in attempts if IsFinalCommandState(attempt.state)
      ]

    return mtt_messages.TestRunMetadata(
        test_run=mtt_messages.Convert(test_run, mtt_messages.TestRun),
        command_attempts=completed_attempts,
    )

  def _LoadMetadataFromContextFile(self, context_file_url):
    """Parse metadata from a context file."""
    try:
      with file_util.OpenFile(context_file_url) as context_stream:
        zf = zipfile.ZipFile(context_stream)
        metadata_file = zf.NameToInfo.get(test_kicker.METADATA_FILE)
        if not metadata_file:
          logging.warning('Metadata file not found')
          return []  # ignore file not found
        metadata_list = protojson.decode_message(  # pytype: disable=module-attr
            mtt_messages.TestRunMetadataList, zf.read(metadata_file)
        )
        # TODO: last command attempt is missing
        return metadata_list.test_runs
    except Exception:  
      logging.exception('Failed to read remote metadata')
      return []
