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

"""A module to process TFC events."""
import datetime
import hashlib
import json
import logging
import os
import threading
import traceback
from typing import Union
import zlib

import flask
from protorpc import messages
from protorpc import protojson
from tradefed_cluster import api_messages
from tradefed_cluster import common
from tradefed_cluster.services import task_scheduler
from tradefed_cluster.util import ndb_shim as ndb


from multitest_transport.models import event_log
from multitest_transport.models import ndb_models
from multitest_transport.models import test_run_hook
from multitest_transport.models import sql_models
from multitest_transport.test_scheduler import test_result_handler
from multitest_transport.test_scheduler import test_scheduler
from multitest_transport.util import analytics
from multitest_transport.util import file_util
from multitest_transport.util import tfc_client
from multitest_transport.util import olcs_session_stub
from multitest_transport.util import lru_cache

IsFinalRequestState = common.IsFinalRequestState
TEST_RUN_STATE_MAP = {
    api_messages.RequestState.UNKNOWN: ndb_models.TestRunState.UNKNOWN,
    api_messages.RequestState.QUEUED: ndb_models.TestRunState.QUEUED,
    api_messages.RequestState.RUNNING: ndb_models.TestRunState.RUNNING,
    api_messages.RequestState.CANCELED: ndb_models.TestRunState.CANCELED,
    api_messages.RequestState.COMPLETED: ndb_models.TestRunState.COMPLETED,
    api_messages.RequestState.ERROR: ndb_models.TestRunState.ERROR,
}

FAILED_TEST_COUNT_THRESHOLDS = [1, 10, 50, 100, 200, 500, 1000]
LOCAL_ID_TAG = 'custom'
APP = flask.Flask(__name__)

_TEST_RUN_HOOK_QUEUE = 'test-run-hook-queue'

_tls = threading.local()
_lock = threading.Lock()
_subscriptions = {}
_request_cache = lru_cache.LRUCache(1000)


def _GenerateHashOfProtorpcObject(message):
  """Generates a hash of a protorpc object.

  Args:
    message: The protorpc object to hash.

  Returns:
    The hexadecimal representation of the hash.
  """
  if not isinstance(message, messages.Message):
    return None
  serialized_message = protojson.encode_message(message)  # pytype: disable=module-attr
  hash_object = hashlib.sha256()
  hash_object.update(serialized_message.encode('utf-8'))
  hex_digest = hash_object.hexdigest()
  return hex_digest


def _ProcessSubscribedSessionResponse(
    test_request: api_messages.RequestMessage,
):
  """Session response subscriber."""
  try:
    if not test_request:
      logging.warning(
          'Skipping processing subscribed session response: request is None'
      )
      return
    request_id = test_request.id
    request_event = api_messages.RequestEventMessage(
        type=common.ObjectEventType.REQUEST_STATE_CHANGED,
        request_id=request_id,
        new_state=test_request.state,
        request=test_request,
        event_time=datetime.datetime.now(),
    )
    logging.info('Calling stack:\n%s', traceback.format_stack())
    logging.info(
        'Subscribed session event: request_id=%s, state=%s, update_time=%s',
        request_event.request_id,
        request_event.new_state,
        request_event.request.update_time,
    )
    ProcessRequestEvent(request_event)
  except Exception as e:  
    logging.exception(
        'Exception %s when processing subscribed session response', e
    )


@ndb.transactional()
def _AfterTestRunHandler(test_run_id, test_context=None):
  """Performs after test run tasks.

  After a test run is in one of the final states, MTT needs to do the following:
    Save the final test context.
    Invoke after run hooks.
    Schedule a job to upload test output files.
    Record test run metrics.

  Args:
    test_run_id: id for the test run.
    test_context: optional pre-fetched test context.
  """
  test_run = ndb_models.TestRun.get_by_id(test_run_id)
  if not test_run:
    return

  test_run.is_finalized = True  # Mark post-run handlers as completed

  # Query and store next test context if not already provided
  if not test_context and test_run.request_id:
    test_context = _GetTestContext(test_run.request_id)

  if test_context:
    test_run.next_test_context = ndb_models.TestContextObj(
        command_line=test_context.command_line,
        env_vars=[
            ndb_models.NameValuePair(name=p.key, value=p.value)
            for p in test_context.env_vars
        ],
        test_resources=[
            _ConvertToTestResourceObj(r) for r in test_context.test_resources
        ],
    )
    logging.debug(
        'Setting the next_test_context = %s', test_run.next_test_context
    )
  test_run.put()

  # Schedule the report merging, it happens before plugin execution as some
  # plugins like apfe, ants may need to access the merged report.
  task_scheduler.AddCallableTask(
      test_result_handler.MergeReports, test_run_id, _transactional=True
  )

  # Invoke after run hooks
  if test_run.state == ndb_models.TestRunState.COMPLETED:
    task_scheduler.AddCallableTask(test_run_hook.ExecuteHooks,
                                   test_run.key.id(),
                                   ndb_models.TestRunPhase.ON_SUCCESS,
                                   _queue=_TEST_RUN_HOOK_QUEUE,
                                   _transactional=True)
  elif test_run.state == ndb_models.TestRunState.ERROR:
    task_scheduler.AddCallableTask(test_run_hook.ExecuteHooks,
                                   test_run.key.id(),
                                   ndb_models.TestRunPhase.ON_ERROR,
                                   _queue=_TEST_RUN_HOOK_QUEUE,
                                   _transactional=True)
  task_scheduler.AddCallableTask(test_run_hook.ExecuteHooks, test_run.key.id(),
                                 ndb_models.TestRunPhase.AFTER_RUN,
                                 _queue=_TEST_RUN_HOOK_QUEUE,
                                 _transactional=True)

  # Record metrics
  task_scheduler.AddCallableTask(_TrackTestRun, test_run.key.id(),
                                 _transactional=True)

  # Log final state
  task_scheduler.AddCallableTask(event_log.Info, test_run.key,
                                 'Test run reached final state',
                                 _transactional=True)

  # Schedule next run in sequence
  if test_run.sequence_id:
    task_scheduler.AddCallableTask(test_scheduler.ScheduleNextTestRun,
                                   test_run.sequence_id, test_run.key)


def _StartSubscribeSession(test_run_id, request_id):
  """Starts a session subscription for a request."""
  if request_id in _subscriptions:
    return
  logging.info(
      'StartSubscribeSession session: %s, test run: %s',
      request_id,
      test_run_id,
  )
  subscription_id = olcs_session_stub.GetSharedStub().StartSubscribeSession(
      request_id,
      ndb.with_ndb_context(_ProcessSubscribedSessionResponse),
  )
  _subscriptions[request_id] = subscription_id


def _StopSubscribeSession(test_run_id, request_id):
  """Stops a session subscription for a request."""
  if request_id not in _subscriptions:
    return
  logging.info(
      'StopSubscribeSession session: %s, test run: %s',
      request_id,
      test_run_id,
  )
  olcs_session_stub.GetSharedStub().StopSubscribeSession(
      _subscriptions[request_id]
  )
  del _subscriptions[request_id]


def ProcessRequestEvent(message: api_messages.RequestEventMessage):
  """Process a TFC request state change event message."""
  requets_hash = _GenerateHashOfProtorpcObject(message.request)
  with _lock:
    if _request_cache.get(requets_hash) is not None:
      logging.info(
          'Skipping processing request event request_id=%s, update_time=%s,'
          ' state=%s, already processed.',
          message.request.id,
          message.request.update_time,
          message.request.state,
      )
      return
    _request_cache.put(requets_hash, '')
  logging.info('Calling stack:\n%s', traceback.format_stack())
  logging.info('ProcessRequestEvent: %s', message)
  test_run = _GetTestRunToUpdate(message)
  if not test_run:
    return
  _ProcessRequestEvent(test_run.key.id(), message)
  test_run = test_run.key.get()
  if test_run.IsFinal():
    with _lock:
      _StopSubscribeSession(test_run.key.id(), message.request_id)
    if test_run.test.result_file:
      # Retrieve the latest finished attempt from the request.
      attempts = None
      if os.environ.get('IS_OMNILAB_BASED') == 'true' and message.request:
        attempts = _GetLatestFinishedAttemptFromRequest(message.request)
      try:
        test_result_handler.UpdateTestRunSummary(
            test_run.key.id(), latest_finished_attempts=attempts)
      except Exception:  
        logging.exception('Summary update failed for %s', test_run.key.id())
    if not test_run.is_finalized:
      # PRE-FETCH: Call _GetTestContext OUTSIDE the transaction.
      # This performs the RPCs and stub database updates non-transactionally.
      test_context = None
      if test_run.request_id:
        test_context = _GetTestContext(test_run.request_id)

      # Pass the context into the transactional handler
      _AfterTestRunHandler(test_run.key.id(), test_context=test_context)
  elif (
      os.environ.get('IS_OMNILAB_BASED') == 'true'
      and test_run.request_id
      and message.request_id
      and test_run.request_id != message.request_id
  ):
    # Subscribe to retry request's status update.
    with _lock:
      _StartSubscribeSession(test_run.key.id(), test_run.request_id)
      _StopSubscribeSession(test_run.key.id(), message.request_id)


@ndb.transactional()
def _ProcessRequestEvent(test_run_id, message):
  """Process a TFC request state change event message."""
  test_run = ndb_models.TestRun.get_by_id(test_run_id)
  if not test_run:
    return

  # Update test run information
  test_run.request_event_time = message.event_time
  test_run.update_time = message.event_time
  if os.environ.get('IS_OMNILAB_BASED') == 'true':
    _UpdateTestRunDevices(test_run, message.request)

  # Process command attempt result if the request session is finished.
  if (
      os.environ.get('IS_OMNILAB_BASED') == 'true'
      and message.request.state
      and IsFinalRequestState(message.request.state)
  ):
    try:
      _ProcessCommandAttemptResult(test_run_id, test_run, message.request)
    except Exception as e:  
      logging.exception(
          'Exception %s when processing command attempt result for test'
          ' run: %s',
          test_run_id,
          e,
      )

  # Check if the request is being retried. If yes, wait for the retry request
  # to be finished.
  if (
      os.environ.get('IS_OMNILAB_BASED') == 'true'
      and message.request.next_attempt_session_id
  ):
    test_run.request_id = message.request.next_attempt_session_id
    test_run.put()
    return

  if not test_run.IsFinal():
    test_run.state = TEST_RUN_STATE_MAP.get(
        message.new_state, ndb_models.TestRunState.UNKNOWN
    )
  if not test_run.test.result_file:
    # No test results file to parse, use partial test counts
    if (message.failed_test_count is not None and
        message.passed_test_count is not None):
      test_run.total_test_count = (message.failed_test_count +
                                   message.passed_test_count)
    if message.failed_test_count is not None:
      test_run.failed_test_count = message.failed_test_count
    if message.failed_test_run_count is not None:
      test_run.failed_test_run_count = message.failed_test_run_count
  test_run.cancel_reason = (
      message.request.cancel_reason if message.request else None)
  if (
      os.environ.get('IS_OMNILAB_BASED') == 'true'
  ):
    test_run.error_reason = (
        message.request.error_reason if message.request else None)
    test_run.error_message = (
        message.request.error_message if message.request else None)
  test_run.put()


def _UpdateTestRunDevices(test_run, request):
  """Update test run devices."""
  for attempt in request.command_attempts:
    device_serials = {device.device_serial for device in test_run.test_devices}
    logging.info(
        'request %s, attempt %s device_serials: %s',
        attempt.request_id,
        attempt.attempt_id,
        attempt.device_serials,
    )
    test_run.test_devices.extend(
        _GetTestDeviceInfos(set(attempt.device_serials) - device_serials)
    )
    logging.info('test_run.test_devices: %s', test_run.test_devices)


def _ProcessCommandAttemptResult(test_run_id, test_run, request):
  """Process command attempt result.

  Args:
    test_run_id: the id of the test run.
    test_run: the test run entity.
    request: the test run's request.
  """
  for attempt in request.command_attempts:
    results = sql_models.GetTestModuleResults([attempt.attempt_id])

    # Skip loading test results if they already exist in DB.
    if not results and common.IsFinalCommandState(attempt.state):
      _StoreTestResults(test_run_id, test_run, attempt)
      _InvokeAttemptHandler(test_run_id, test_run, attempt)


def _StoreTestResults(test_run_id, test_run, attempt):
  """Store test results to database and invoke after attempt hooks."""
  result_url = file_util.GetResultUrl(test_run, attempt)
  if result_url:
    task_scheduler.AddCallableTask(
        test_result_handler.StoreTestResults,
        test_run_id,
        attempt.attempt_id,
        result_url,
        _transactional=True,
    )
  else:
    logging.warning(
        'No result file for test run %s, skip processing', test_run_id
    )


def _InvokeAttemptHandler(test_run_id, test_run, attempt):
  if not test_run.is_finalized:
    task_scheduler.AddCallableTask(
        test_run_hook.ExecuteHooks,
        test_run_id,
        ndb_models.TestRunPhase.AFTER_ATTEMPT,
        attempt_id=attempt.attempt_id,
        _queue=_TEST_RUN_HOOK_QUEUE,
        _transactional=True,
    )


def ProcessCommandAttemptEvent(
    message: api_messages.CommandAttemptEventMessage):
  """Process a TFC attempt state change event message."""
  test_run = _GetTestRunToUpdate(message)
  if test_run:
    _ProcessCommandAttemptEvent(test_run.key.id(), message)


@ndb.transactional()
def _ProcessCommandAttemptEvent(test_run_id, message):
  """Process a TFC attempt state change event message."""
  test_run = ndb_models.TestRun.get_by_id(test_run_id)
  if not test_run:
    return

  # Update test run information
  attempt = message.attempt
  test_run.attempt_event_time = message.event_time
  test_run.update_time = message.event_time
  device_serials = {device.device_serial for device in test_run.test_devices}
  test_run.test_devices.extend(
      _GetTestDeviceInfos(set(attempt.device_serials) - device_serials)
  )
  test_run.put()

  # Store attempt test results and invoke after attempt hooks
  if common.IsFinalCommandState(attempt.state):
    _StoreTestResults(test_run_id, test_run, attempt)
    _InvokeAttemptHandler(test_run_id, test_run, attempt)


def _GetLatestFinishedAttemptFromRequest(request):
  """Gets the latest finished command attempt from a request.

  Args:
    request: The api_messages.RequestMessage object.

  Returns:
    A list containing the latest finished attempt, or None if no finished
    attempts are found.
  """
  finished_attempts = [
      a for a in request.command_attempts
      if a.state and common.IsFinalCommandState(a.state)
  ]
  if finished_attempts:
    return [
        max(
            finished_attempts,
            key=lambda attempt: attempt.start_time or datetime.datetime.min,
        )
    ]
  return None


def _GetTestContext(request_id):
  """Retrieve the TFC test context for a request."""
  request = tfc_client.GetRequest(request_id)
  # TODO: merge test contexts if there is more than one.
  if request.commands:
    return tfc_client.GetTestContext(request.id, request.commands[0].id)
  return None


def _ConvertToTestResourceObj(msg):
  """Convert TFC api_messages.TestResource to ndb_models.TestResourceObj."""
  return ndb_models.TestResourceObj(
      name=msg.name,
      url=msg.url,
      decompress=msg.decompress,
      decompress_dir=msg.decompress_dir,
      password=msg.password,
      params=ndb_models.TestResourceParameters(
          decompress_files=msg.params.decompress_files) if msg.params else None)


def _TrackTestRun(test_run_id):
  """Generate and send test run analytics information after completion."""
  test_run = ndb_models.TestRun.get_by_id(test_run_id)
  if not test_run:
    return
  package = test_run.test_package_info
  duration = _GetCurrentTime() - test_run.create_time

  device_count = None
  attempt_count = None
  if test_run.request_id:
    request = tfc_client.GetRequest(test_run.request_id)
    attempts = request.command_attempts
    if attempts:
      device_count = max(len(a.device_serials or []) for a in attempts)
      attempt_count = len(attempts)
      _TrackTestInvocations(request, test_run)

  analytics.Log(analytics.TEST_RUN_CATEGORY, analytics.END_ACTION,
                test_name=package.name if package else None,
                test_version=package.version if package else None,
                state=test_run.state.name,
                duration_seconds=int(duration.total_seconds()),
                device_count=device_count,
                attempt_count=attempt_count,
                is_rerun=test_run.prev_test_run_key is not None,
                failed_module_count=test_run.failed_test_run_count,
                test_count=test_run.total_test_count,
                failed_test_count=test_run.failed_test_count)


def _TrackTestInvocations(request, test_run):
  """Generate and send analytics for each command attempt in a request."""
  if not request.command_attempts:
    return
  attempts = request.command_attempts

  test_run_config = test_run.test_run_config
  test_run_command = test_run_config.command if test_run_config else ''
  test_run_retry_command = (
      test_run_config.retry_command if test_run_config else '')
  test_id = test_run_config.test_key.id()
  if test_id and ndb_models.IsLocalId(test_id):
    test_id = LOCAL_ID_TAG
  package = test_run.test_package_info
  original_start_time = test_run.create_time
  prev_total_test_count = None
  prev_failed_module_count = None
  prev_failed_test_count = None
  missing_previous_run = bool(test_run.prev_test_context and
                              not test_run.prev_test_run_key)

  # If the test run is a rerun, get data from the previous run
  if test_run.prev_test_run_key:
    prev_test_run = ndb_models.TestRun.get_by_id(
        test_run.prev_test_run_key.id())
    if prev_test_run:
      original_start_time = prev_test_run.create_time
      prev_total_test_count = prev_test_run.total_test_count
      prev_failed_module_count = prev_test_run.failed_test_run_count
      prev_failed_test_count = prev_test_run.failed_test_count

      # Trace retries to get the create time of the first run
      while prev_test_run.prev_test_run_key:
        prev_test_run = ndb_models.TestRun.get_by_id(
            prev_test_run.prev_test_run_key.id())
        if not prev_test_run:
          break
        original_start_time = prev_test_run.create_time

      # Check if first run was a rerun of a non-local run
      if not prev_test_run or prev_test_run.prev_test_context:
        missing_previous_run = True

  # Log data for each attempt
  for attempt in attempts:
    # Cancelled attempts could still be running and might not have an end time,
    # in that case the request cancellation time is used
    attempt_end_time = attempt.end_time or request.update_time
    # Attempts can also be cancelled before starting, this ensures duration >= 0
    attempt_start_time = attempt.start_time or attempt_end_time
    duration = max(attempt_end_time - attempt_start_time, datetime.timedelta(0))
    elapsed_time = attempt_end_time - original_start_time
    failed_test_count_threshold = _FindFailedTestCountThreshold(
        attempt.failed_test_count, prev_failed_test_count)
    if failed_test_count_threshold:
      failed_test_count_threshold = str(failed_test_count_threshold)
    analytics.Log(analytics.INVOCATION_CATEGORY, analytics.END_ACTION,
                  command=request.command_line,
                  test_run_command=test_run_command,
                  test_run_retry_command=test_run_retry_command,
                  test_id=test_id,
                  test_name=package.name if package else None,
                  test_version=package.version if package else None,
                  state=attempt.state.name,
                  failed_test_count_threshold=failed_test_count_threshold,
                  duration_seconds=int(duration.total_seconds()),
                  elapsed_time_seconds=int(elapsed_time.total_seconds()),
                  device_count=len(attempt.device_serials or []),
                  test_count=attempt.total_test_count,
                  failed_module_count=attempt.failed_test_run_count,
                  failed_test_count=attempt.failed_test_count,
                  prev_total_test_count=prev_total_test_count,
                  prev_failed_module_count=prev_failed_module_count,
                  prev_failed_test_count=prev_failed_test_count,
                  missing_previous_run=missing_previous_run,
                  is_sequence_run=test_run.sequence_id is not None)
    prev_total_test_count = attempt.total_test_count
    prev_failed_module_count = attempt.failed_test_run_count
    prev_failed_test_count = attempt.failed_test_count


def _FindFailedTestCountThreshold(failed_test_count, prev_failed_test_count):
  """Returns the minimum threshold between two counts."""
  if failed_test_count is None:
    return None
  if prev_failed_test_count is None:
    prev_failed_test_count = float('inf')
  for threshold in FAILED_TEST_COUNT_THRESHOLDS:
    if failed_test_count < threshold <= prev_failed_test_count:
      return threshold
  return None


def _GetCurrentTime():
  """Return current time, visible for testing."""
  return datetime.datetime.now()


def _GetTestRunToUpdate(
    message: Union[api_messages.RequestEventMessage,
                   api_messages.CommandAttemptEventMessage]):
  """Retrieve the associated test run if it exists and should be updated."""
  request_event = isinstance(message, api_messages.RequestEventMessage)
  request_id = (message.request_id if request_event
                else message.attempt.request_id)
  query = ndb_models.TestRun.query(ndb_models.TestRun.request_id == request_id)
  test_run_key = query.get(keys_only=True)
  if not test_run_key:
    logging.warning('Cannot find test run for request %s', request_id)
    return None

  test_run = test_run_key.get(use_cache=False, use_memcache=False)
  last_event_time = (test_run.request_event_time if request_event
                     else test_run.attempt_event_time)
  if last_event_time and message.event_time < last_event_time:
    logging.warning('Event timestamp too old (%s < %s); skipping message: %s',
                    message.event_time, last_event_time, message)
    return None
  return test_run


def _GetTestDeviceInfos(device_serials):
  """Retrieve information about the test devices."""
  device_infos = []
  for serial in device_serials:
    device = tfc_client.GetDeviceInfo(serial)
    if device:
      device_info = ndb_models.TestDeviceInfo(
          device_serial=device.device_serial,
          hostname=device.hostname,
          run_target=device.run_target,
          build_id=device.build_id,
          product=device.product,
          sdk_version=device.sdk_version)
      device_infos.append(device_info)
    else:
      logging.error('Device %s not found', serial)
  return device_infos


# Event message classes and handlers
_EVENT_HANDLERS = {
    common.ObjectEventType.COMMAND_ATTEMPT_STATE_CHANGED: (
        api_messages.CommandAttemptEventMessage, ProcessCommandAttemptEvent),
    common.ObjectEventType.REQUEST_STATE_CHANGED: (
        api_messages.RequestEventMessage, ProcessRequestEvent)
}


# Sets the callback method for the request event.
tfc_client.SetRequestEventMessageHandler(ProcessRequestEvent)


@APP.route('/', methods=['POST'])
@APP.route('/<path:fake>', methods=['POST'])
def HandleTask(fake=None):
  """Handle tasks from the TFC event queue."""
  del fake
  body = flask.request.get_data()
  try:
    body = zlib.decompress(body)
  except zlib.error:
    logging.warning(
        'payload may not be compressed: %s', body, exc_info=True)
  message_type = json.loads(body).get('type')
  message_cls, handler = _EVENT_HANDLERS[message_type]
  if not message_cls or not handler:
    raise ValueError('Unknown TFC event type %s' % message_type)
  message = protojson.decode_message(message_cls, body)  # pytype: disable=module-attr
  handler(message)
  return common.HTTP_OK
