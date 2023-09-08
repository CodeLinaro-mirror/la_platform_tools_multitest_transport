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

"""Handles storing test result information."""
import logging
import os
import shutil
import subprocess
import threading
import time

from typing import Optional
from tradefed_cluster.services import task_scheduler
from tradefed_cluster.util import ndb_shim as ndb


from multitest_transport.models import ndb_models
from multitest_transport.models import sql_models
from multitest_transport.util import env
from multitest_transport.util import file_util
from multitest_transport.util import tfc_client
from multitest_transport.util import xts_result

write_report_lock = threading.Lock()


def StoreTestResults(test_run_id, attempt_id, test_results_url):
  """Parses and stores test results for a test run and attempt."""
  start_time = time.time()
  try:
    with file_util.OpenFile(test_results_url) as test_results_stream:
      test_results = xts_result.TestResults(test_results_stream)

      # Store test results in DB
      sql_models.InsertTestResults(test_run_id, attempt_id, test_results)
      logging.info('Stored test results from %s (took %.1fs)',
                   attempt_id, time.time() - start_time)
  except FileNotFoundError:
    logging.warning('Test result file not found: %s', test_results_url)
  task_scheduler.AddCallableTask(UpdateTestRunSummary, test_run_id)
  test_run = ndb_models.TestRun.get_by_id(test_run_id)
  # If the test run is canceled and finalized earlier which may not merge the
  # result from this attempt, so do the merging again.
  # In most of cases, the test run is not finalized at the moment and the merge
  # will be delegated to the request handler
  if test_run.is_finalized:
    task_scheduler.AddCallableTask(MergeReports, test_run_id)


@ndb.transactional()
def UpdateTestRunSummary(test_run_id):
  """Update test run numbers."""
  logging.info('Updating summary for test run %s', test_run_id)
  test_run = ndb_models.TestRun.get_by_id(test_run_id)
  test_run.total_test_count = 0
  test_run.failed_test_count = 0
  test_run.failed_test_run_count = 0
  attempts = tfc_client.GetLatestFinishedAttempts(test_run.request_id)
  modules = sql_models.GetTestModuleResults(
      [attempt.attempt_id for attempt in attempts])
  for module in modules:
    test_run.total_test_count += module.total_tests
    test_run.failed_test_count += module.failed_tests
    if module.error_message:
      test_run.failed_test_run_count += 1
  test_run.put()


@ndb.transactional()
def MergeReports(test_run_id):
  """Merges reports from latest finished attempts."""
  logging.info('Merging reports for test run %s', test_run_id)

  report_generator_jar = env.REPORT_GENERATOR_JAR
  if not os.path.isfile(report_generator_jar):
    logging.info(
        (
            'The given report_generator_jar [%s] is not a valid file, skip'
            ' merging reports'
        ),
        report_generator_jar,
    )
    return

  test_run = ndb_models.TestRun.get_by_id(test_run_id)
  if test_run.test_run_config.sharding_mode != ndb_models.ShardingMode.MODULE:
    logging.info(
        'Test run %s is not running with MODULE sharding mode, skip merging'
        ' report.', test_run_id
    )
    return
  if not test_run.is_finalized:
    logging.info(
        'Test run %s is not finalized yet, skip merging reports', test_run_id
    )
    return
  attempts = tfc_client.GetLatestFinishedAttempts(test_run.request_id)

  result_urls = []
  test_record_urls = []
  for attempt in attempts:
    result_url = file_util.GetResultUrl(test_run, attempt)
    local_result_url = _GetLocalFilePath(result_url) if result_url else None
    if local_result_url:
      local_result_url = local_result_url.strip()
      local_test_record_url = '/'.join(
          [os.path.dirname(local_result_url), 'test-record.pb']
      )
      result_urls.append(local_result_url)
      test_record_urls.append(local_test_record_url)

  if len(result_urls) < 2:
    logging.info(
        'Test run %s has less than two valid result URLs, skip merging reports',
        test_run_id
    )
    return

  with write_report_lock:
    logging.info('Acquired the lock to merge reports...')
    xml_report_files = ','.join(result_urls)
    test_record_proto_files = ','.join(test_record_urls)
    merged_report_dir = os.path.join(
        _GetLocalFilePath(file_util.GetAppStorageUrl([test_run.output_path])),
        'merged_report',
    )
    if os.path.isdir(merged_report_dir):
      shutil.rmtree(merged_report_dir, ignore_errors=True)
    merge_reports_cmd = [
        'java',
        '-jar',
        report_generator_jar,
        '--xml_report_files',
        xml_report_files,
        '--test_record_proto_files',
        test_record_proto_files,
        '--output_dir',
        merged_report_dir,
    ]
    logging.info('Executing cmd to merge reports: %s', merge_reports_cmd)
    proc = subprocess.Popen(
        merge_reports_cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    try:
      while proc.poll() is None:
        line = proc.stdout.readline() if proc.stdout else None
        if line:
          logging.info(line.decode('utf-8').strip())
        else:
          break
      merged_report_zip_file_url = _GetMergedReportZipFile(test_run)
      if merged_report_zip_file_url:
        test_resources = test_run.next_test_context.test_resources
        if test_resources:
          new_test_resource_name = os.path.basename(merged_report_zip_file_url)
          old_test_resource_name = test_resources[0].name
          idx = old_test_resource_name.rfind('/')
          if idx >= 0:
            new_test_resource_name = (
                old_test_resource_name[:idx] + '/' + new_test_resource_name
            )
          test_run.next_test_context.test_resources = [
              ndb_models.TestResourceObj(
                  name=new_test_resource_name,
                  url=merged_report_zip_file_url,
              )
          ]
          logging.info(
              'Updates test resources for test run %s next_test_context: %s',
              test_run_id,
              test_run.next_test_context.test_resources,
          )
          test_run.put()
    finally:
      (unexpected_out, _) = proc.communicate()
      for line in unexpected_out.splitlines():
        logging.warning(line)


def _GetLocalFilePath(result_url: str) -> Optional[str]:
  if not result_url.startswith('file:///'):
    logging.warning('Invalid local file URL %s', result_url)
    return None
  return result_url[7:]


def _GetMergedReportZipFile(test_run) -> Optional[str]:
  """Gets merged report zip file URL."""
  merged_report_dir = file_util.GetMergedReportFileUrl(test_run)
  merged_report_dir_handle = file_util.FileHandle.Get(merged_report_dir)
  merged_report_files = merged_report_dir_handle.ListFiles()
  merged_report_zip_file_url = None
  if merged_report_files:
    merged_report_file_urls = [
        f.url for f in merged_report_files if f.is_file
    ]
    merged_report_zip_file_url = next(
        (f for f in merged_report_file_urls if f.endswith('.zip')),
        None,
    )
  return merged_report_zip_file_url
