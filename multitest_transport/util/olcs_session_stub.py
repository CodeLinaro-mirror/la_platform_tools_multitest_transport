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

"""A OLCS session service stub that is providing similar functionality as tfc_client."""
import base64
from concurrent import futures
import logging
import os
import queue
import re
import threading
import time
import traceback
from typing import Callable, Iterator, List, Optional
import uuid

import grpc
from multitest_transport.models import ndb_models
from multitest_transport.util import file_util
from multitest_transport.util import olcs_session_client
from tradefed_cluster import api_messages
from tradefed_cluster import common

from google3.google.protobuf import duration_pb2
from com_google_deviceinfra.src.devtools.mobileharness.infra.ats.common.proto import xts_common_pb2
from com_google_deviceinfra.src.devtools.mobileharness.infra.ats.server.proto import service_pb2
from com_google_deviceinfra.src.devtools.mobileharness.infra.client.longrunningservice.proto import session_pb2
from com_google_deviceinfra.src.devtools.mobileharness.infra.client.longrunningservice.proto import session_service_pb2

SESSION_PLUGIN_CLASS_NAME = "com.google.devtools.mobileharness.infra.ats.server.sessionplugin.AtsServerSessionPlugin"
SESSION_MODULE_CLASS_NAME = "com.google.devtools.mobileharness.infra.ats.server.sessionplugin.AtsServerSessionPluginModule"
SESSION_PLUGIN_LABEL = "AtsServerSessionPlugin"
NANOS_PER_MILLISECOND = 1000000
MILLIS_PER_SECOND = 1000

# TODO: The database operation should not be single threaded.
# Remove this lock after finding better solution to address database data race
# issue. Potential solution is to use sql database.
_lock = threading.Lock()

_REQUEST_STATE_MAP = {
    service_pb2.RequestDetail.RequestState.UNKNOWN: common.RequestState.UNKNOWN,
    service_pb2.RequestDetail.RequestState.QUEUED: common.RequestState.QUEUED,
    service_pb2.RequestDetail.RequestState.RUNNING: common.RequestState.RUNNING,
    service_pb2.RequestDetail.RequestState.CANCELED: (
        common.RequestState.CANCELED
    ),
    service_pb2.RequestDetail.RequestState.COMPLETED: (
        common.RequestState.COMPLETED
    ),
    service_pb2.RequestDetail.RequestState.ERROR: common.RequestState.ERROR,
}

_COMMAND_STATE_MAP = {
    service_pb2.CommandState.UNKNOWN_STATE: common.CommandState.UNKNOWN,
    service_pb2.CommandState.QUEUED: common.CommandState.QUEUED,
    service_pb2.CommandState.RUNNING: common.CommandState.RUNNING,
    service_pb2.CommandState.CANCELED: common.CommandState.CANCELED,
    service_pb2.CommandState.COMPLETED: common.CommandState.COMPLETED,
    service_pb2.CommandState.ERROR: common.CommandState.ERROR,
}

_TEST_RUN_CANCEL_REASON_MAP = {
    service_pb2.CancelReason.UNKNOWN_CANCEL_REASON: common.CancelReason.UNKNOWN,
    service_pb2.CancelReason.REQUEST_API: common.CancelReason.REQUEST_API,
    service_pb2.CancelReason.QUEUE_TIMEOUT: common.CancelReason.QUEUE_TIMEOUT,
    service_pb2.CancelReason.COMMAND_ALREADY_CANCELED: (
        common.CancelReason.COMMAND_ALREADY_CANCELED
    ),
    service_pb2.CancelReason.REQUEST_ALREADY_CANCELED: (
        common.CancelReason.REQUEST_ALREADY_CANCELED
    ),
    service_pb2.ErrorReason.COMMAND_NOT_EXECUTABLE: (
        common.CancelReason.COMMAND_NOT_EXECUTABLE
    ),
    service_pb2.ErrorReason.INVALID_REQUEST: (
        common.CancelReason.INVALID_REQUEST
    ),
    # No corresponding id for invalid resource error, need to add.
    service_pb2.ErrorReason.INVALID_RESOURCE: (
        common.CancelReason.INVALID_REQUEST
    ),
}

_ERROR_REASON_MAP = {
    service_pb2.ErrorReason.UNKNOWN_REASON: common.ErrorReason.UNKNOWN,
    service_pb2.ErrorReason.TOO_MANY_LOST_DEVICES: (
        common.ErrorReason.TOO_MANY_LOST_DEVICES
    ),
}

_DEVICE_ACTION_TYPE_MAP = {
    api_messages.TradefedConfigObjectType.UNKNOWN: (
        service_pb2.DeviceActionConfigObject.DeviceActionConfigObjectType.UNKNOWN_DEVICE_ACTION_CONFIG_OBJECT_TYPE
    ),
    api_messages.TradefedConfigObjectType.TARGET_PREPARER: (
        service_pb2.DeviceActionConfigObject.DeviceActionConfigObjectType.TARGET_PREPARER
    ),
    api_messages.TradefedConfigObjectType.RESULT_REPORTER: (
        service_pb2.DeviceActionConfigObject.DeviceActionConfigObjectType.RESULT_REPORTER
    ),
}


class OlcsSessionStub:
  """The OLCS session service stub to send ats server specific request to OLCS."""

  def __init__(self, client: None):
    if client is None:
      self._client = olcs_session_client.OlcsSessionClient.create()
    else:
      self._client = client
    self._subscribe_session_queues = {}
    self._executor = futures.ThreadPoolExecutor(max_workers=10)

  def CancelRequest(self, request_id: str):
    """Cancel a request.

    Args:
      request_id: The request id of the request.

    Returns:
      True if the request is cancelled successfully.
    """
    session_notification = session_pb2.SessionNotification(
        plugin_label=session_pb2.SessionPluginLabel(label=SESSION_PLUGIN_LABEL)
    )
    session_notification.notification.Pack(
        service_pb2.AtsServerSessionNotification(
            cancel_session=service_pb2.CancelSession()
        )
    )
    response = self._client.notify_session(
        session_service_pb2.NotifySessionRequest(
            session_id=session_pb2.SessionId(id=request_id),
            session_notification=session_notification,
        )
    )
    logging.info("Cancel request response:%s", response)
    return response and response.successful

  def CreateNewRequest(
      self, request: api_messages.NewMultiCommandRequestMessage
  ) -> str:
    response = self._client.create_session(
        OlcsSessionStub.GenerateRequestProto(request)
    )
    return response.session_id.id

  def GetLatestFinishedAttempts(
      self, request_id: str
  ) -> List[api_messages.CommandAttemptMessage]:
    """Get latest finished attempts from OLCS.

    Args:
      request_id: The request id of the request.

    Returns:
      A list of latest finished attempts of the request.
    """
    request = self.GetRequest(request_id)
    if not request:
      return []
    attempt_map = {}
    attempt_list = request.command_attempts or []
    attempt_list.sort(key=lambda attempt: attempt.start_time)
    for attempt in attempt_list:
      if not common.IsFinalCommandState(attempt.state):
        continue
      attempt_map[attempt.command_id] = attempt
    return list(attempt_map.values())

  def GetTestContext(
      self, request_id: str, command_id: str
  ) -> api_messages.TestContext:
    """Get test context from OLCS.

    Args:
      request_id: The request id of the request.
      command_id: The command id of the command.

    Returns:
      The test context of the command.
    """
    request_detail = self._GetRequestDetail(request_id)
    if request_detail:
      test_context_proto = request_detail.test_context.get(command_id)
      if test_context_proto:
        test_context = api_messages.TestContext()
        test_context.command_line = test_context_proto.command_line
        for key, value in test_context_proto.env_var.items():
          test_context.env_vars.append(
              api_messages.KeyValuePair(key=key, value=value)
          )
        for test_resource in test_context_proto.test_resource:
          test_context.test_resources.append(
              api_messages.TestResource(
                  url=test_resource.url, name=test_resource.name
              )
          )
        return test_context
    return api_messages.TestContext()

  def _FetchRequestDetail(
      self, request_id: str
  ) -> tuple[bool, service_pb2.RequestDetail]:
    """Fetch request from OLCS and convert to TFC request message.

    Args:
      request_id: The request id of the request.

    Returns:
      A tuple of (request_finished, request_detail).
      request_finished is a boolean value indicating whether the request is
      finished or not.
      request_detail is the request message defined by TFC.
    """
    request = session_service_pb2.GetSessionRequest()
    request.session_id.id = request_id
    response = self._client.get_session(request)
    request_detail = service_pb2.RequestDetail()
    response.session_detail.session_output.session_plugin_output[
        SESSION_PLUGIN_LABEL
    ].output.Unpack(request_detail)
    logging.info("Calling stack:\n%s", traceback.format_stack())
    logging.info(
        "Fetched %s status request detail proto from OLCS: %s",
        response.session_detail.session_status,
        request_detail.__str__(),
    )
    # In case the test request hasn't started and proto is empty, fill in the
    # request id manually.
    if not request_detail.id:
      request_detail.id = request_id
    return (
        response.session_detail.session_status == session_pb2.SESSION_FINISHED,
        request_detail,
    )

  def _GenerateRequestMessage(
      self, request_detail: service_pb2.RequestDetail
  ) -> api_messages.RequestMessage:
    """Generate request message from request detail proto.

    Args:
      request_detail: Request detail proto.

    Returns:
      The request message defined by TFC.
    """
    request_id = request_detail.id

    request_message = api_messages.RequestMessage()
    request_message.id = request_id
    request_message.user = request_detail.user
    request_message.command_infos = list(
        map(self._ConvertProtoToCommandInfo, request_detail.command_infos)
    )
    request_message.priority = request_detail.priority
    request_message.queue_timeout_seconds = request_detail.queue_timeout.seconds
    if request_detail.state == service_pb2.RequestDetail.RequestState.CANCELED:
      request_message.cancel_reason = _TEST_RUN_CANCEL_REASON_MAP.get(
          request_detail.cancel_reason, common.CancelReason.UNKNOWN
      )
    elif request_detail.state == service_pb2.RequestDetail.RequestState.ERROR:
      request_message.error_reason = service_pb2.ErrorReason.Name(
          request_detail.error_reason
      )
    request_message.error_message = request_detail.error_message
    request_message.max_retry_on_test_failures = (
        request_detail.max_retry_on_test_failures
    )
    # TODO: add (prev_test_context)
    request_message.max_concurrent_tasks = request_detail.max_concurrent_tasks
    # TODO: add (affinity_tag)

    request_message.state = _REQUEST_STATE_MAP.get(
        request_detail.state, common.RequestState.UNKNOWN
    )
    request_message.start_time = request_detail.start_time.ToDatetime()
    request_message.end_time = request_detail.end_time.ToDatetime()

    request_message.create_time = request_detail.create_time.ToDatetime()
    request_message.update_time = request_detail.update_time.ToDatetime()
    # TODO: cancel message is deprecated.

    # Only one command and one command attempt exists for each OLCS session
    # request.
    if request_detail.command_details:
      single_command_detail = next(
          iter(request_detail.command_details.values())
      )
      if len(request_detail.command_details) > 1:
        logging.warning(
            "More than one command detail found in request %s, only the first"
            " one will be processed.",
            request_id,
        )
      request_message.commands = [
          self._ConvertCommandDetail(single_command_detail, request_detail)
      ]
      command_attempt_message = self._GenerateCommandAttemptFromCommand(
          single_command_detail, request_detail
      )
      command_attempt_message.attempt_id = (
          single_command_detail.command_attempt_id
      )
      command_attempt_message.device_serials = list(
          single_command_detail.device_serials
      )
      request_message.command_attempts.append(command_attempt_message)

    request_message.next_attempt_session_id = (
        request_detail.next_attempt_session_id
    )

    # add all previous attempts from previous sessions
    last_attempt_session_id = (
        request_detail.original_request.retry_previous_session_id
    )
    if last_attempt_session_id:
      last_attempt_request_message = self.GetRequest(last_attempt_session_id)
      if last_attempt_request_message:
        request_message.command_attempts.extend(
            last_attempt_request_message.command_attempts
        )
    request_message.command_attempts.sort(
        key=lambda attempt: attempt.start_time
    )

    # Consolidate the MTT request message's command duration. It needs to sum up
    # from the current attempt and previous attempts.
    if request_message.commands:
      single_command = request_message.commands[0]
      if request_message.command_attempts:
        single_command.start_time = request_message.command_attempts[
            0
        ].start_time

        all_finished = all(
            common.IsFinalCommandState(attempt.state)
            for attempt in request_message.command_attempts
        )
        if all_finished:
          # The command is finished, use the latest attempt's end time.
          latest_end_time = request_message.command_attempts[-1].end_time
          single_command.end_time = latest_end_time
        else:
          single_command.end_time = None
      request_message.commands = [single_command]

    return request_message

  def _GetRequestDetail(
      self, request_id: str
  ) -> Optional[service_pb2.RequestDetail]:
    """Get request detail from DB or fetch from OLCS."""
    # First, try to load from the database
    request_detail = self._LoadRequestDetailFromDatabase(request_id)
    if request_detail:
      return request_detail

    # If not in the database, fetch from the OLCS server
    request_finished, request_detail = self._FetchRequestDetail(request_id)

    # If the request is finished, save the details to the database for caching
    if request_detail and request_finished:
      self._SaveRequestDetailToDatabase(request_id, request_detail)

    return request_detail

  def GetRequest(
      self, request_id: str
  ) -> Optional[api_messages.RequestMessage]:
    """Get request from OLCS or from Database.

    Args:
      request_id: The request id of the request.

    Returns:
      The request message defined by TFC.
    """
    request_detail = self._GetRequestDetail(request_id)
    if request_detail:
      return self._GenerateRequestMessage(request_detail)
    return None

  def _LoadRequestDetailFromDatabase(
      self, request_id: str
  ) -> Optional[service_pb2.RequestDetail]:
    """Load request detail from database."""
    with _lock:
      test_request = ndb_models.RequestInfo.get_by_id(request_id, retries=5)
      if test_request:
        request_detail = service_pb2.RequestDetail()
        decoded_bytes = base64.b64decode(test_request.request_detail_proto_str)
        request_detail.ParseFromString(decoded_bytes)
        return request_detail
      return None

  def _SaveRequestDetailToDatabase(
      self, request_id: str, request_detail: service_pb2.RequestDetail
  ) -> None:
    """Save request detail to database."""
    with _lock:
      request_detail_str = request_detail.SerializeToString()
      base64_string = base64.b64encode(request_detail_str).decode("utf-8")
      request_info = ndb_models.RequestInfo(
          id=request_id,
          request_detail_proto_str=base64_string,
      )
      request_info.put()

  def GetAttempt(
      self, request_id: str, attempt_id: str
  ) -> Optional[api_messages.CommandAttemptMessage]:
    """Find a OLC command attempt.

    Args:
      request_id: request ID.
      attempt_id: attempt ID.

    Returns:
      TFC command attempt, or None if not found
    """
    request = self.GetRequest(request_id)
    if not request:
      return None
    attempts = request.command_attempts or []
    return next((a for a in attempts if a.attempt_id == attempt_id), None)

  def GetRequestInvocationStatus(
      self,
      request_id: str,
  ) -> api_messages.InvocationStatus:
    """Get invocation status from OLCS.

    Args:
      request_id: The request id of the request.

    Returns:
      The invocation status of the request.
    """
    del request_id  # TODO: To be completed.
    return api_messages.InvocationStatus()

  def StartSubscribeSession(
      self,
      request_id: str,
      session_response_subscriber: Callable[
          [session_service_pb2.SubscribeSessionResponse], None
      ],
  ):
    """Start to subscribe session to OLCS.

    Args:
      request_id: The request id of the request.
      session_response_subscriber: The callback method to be called when there's
        subscribed response.

    Returns:
      The subscribe id.
    """
    subscribe_id = str(uuid.uuid4())
    subscribe_session_request = session_service_pb2.SubscribeSessionRequest()
    subscribe_session_request.get_session_request.session_id.id = request_id
    subscribe_session_queue = queue.SimpleQueue()
    self._subscribe_session_queues[subscribe_id] = subscribe_session_queue
    subscribe_session_queue.put(subscribe_session_request)
    subscribe_session_responses = self._client.subscribe_session(
        iter(subscribe_session_queue.get, None)
    )
    self._executor.submit(
        self._ProcessSubscribeSessionResponses,
        subscribe_id,
        request_id,
        session_response_subscriber,
        subscribe_session_responses,
    )
    return subscribe_id

  def _ProcessSubscribeSessionResponses(
      self,
      subscribe_id: str,
      request_id: str,
      session_response_subscriber: Callable[
          [session_service_pb2.SubscribeSessionResponse], None
      ],
      subscribe_session_responses: Iterator[
          session_service_pb2.SubscribeSessionResponse
      ],
  ):
    """Process subscribe session responses.

    Args:
      subscribe_id: The id of the subscribe.
      request_id: The id of the request it subscribes to.
      session_response_subscriber: The callback method to be called when there's
        subscribed response.
      subscribe_session_responses: The subscribe session responses.
    """
    try:
      for subscribe_session_response in subscribe_session_responses:
        logging.info(
            "subscribe_session_response: %s", subscribe_session_response
        )
        logging.info("Calling stack:\n%s", traceback.format_stack())
        session_response_subscriber(subscribe_session_response)
    except grpc.RpcError as e:  
      logging.exception(
          "Failed to process subscribe session %s responses", request_id
      )
      if e.code() == grpc.StatusCode.UNAVAILABLE:  # pytype: disable=attribute-error
        # Sleep 60 seconds to wait for the server to be back.
        time.sleep(60)
        self.StartSubscribeSession(request_id, session_response_subscriber)
    except Exception:  
      logging.exception(
          "Failed to process subscribe session %s responses", request_id
      )
    finally:
      self._subscribe_session_queues.pop(subscribe_id)

  def StopSubscribeSession(self, subscribe_id: str):
    """Stop subscribing session to OLCS.

    Args:
      subscribe_id: The request id of the subscribe.
    """
    subscribe_session_queue = self._subscribe_session_queues.get(subscribe_id)
    if subscribe_session_queue:
      subscribe_session_queue.put(None)

  def _ConvertProtoToCommandInfo(
      self, proto: service_pb2.CommandInfo
  ) -> api_messages.CommandInfo:
    """Convert Command Info proto to TFC CommandInfo.

    Args:
      proto: Command Info proto.

    Returns:
      The CommandInfo defined by TFC.
    """
    command_info_message = api_messages.CommandInfo()
    command_info_message.name = proto.name
    command_info_message.command_line = proto.command_line
    # TODO: add cluster
    command_info_message.run_count = proto.run_count
    command_info_message.shard_count = proto.shard_count
    command_info_message.enable_xts_dynamic_download = (
        proto.enable_xts_dynamic_download
    )
    command_info_message.allow_partial_device_match = (
        proto.allow_partial_device_match
    )
    return command_info_message

  def _ConvertCommandDetail(
      self,
      command_detail: service_pb2.CommandDetail,
      request_detail: service_pb2.RequestDetail,
  ) -> api_messages.CommandMessage:
    """Convert Command Detail from Request Detail proto to TFC CommandMessage.

    Args:
      command_detail: Command Detail from Request Detail proto.
      request_detail: Request Detail proto.

    Returns:
      The CommandMessage defined by TFC.
    """
    command_message = api_messages.CommandMessage()
    command_message.id = command_detail.id
    command_message.request_id = command_detail.request_id
    command_message.command_line = command_detail.command_line
    if (
        request_detail.original_request.prev_test_context
        and request_detail.original_request.prev_test_context.command_line
    ):
      command_message.command_line = (
          request_detail.original_request.prev_test_context.command_line
      )

    # TODO: fill run target and cluster
    command_message.state = _COMMAND_STATE_MAP.get(
        command_detail.state, common.CommandState.UNKNOWN
    )
    command_message.cancel_reason = _TEST_RUN_CANCEL_REASON_MAP.get(
        command_detail.cancel_reason, common.CancelReason.UNKNOWN
    )
    command_message.error_reason = _ERROR_REASON_MAP.get(
        command_detail.error_reason, common.ErrorReason.UNKNOWN
    )
    command_message.run_count = command_detail.original_command_info.run_count
    command_message.shard_count = (
        command_detail.original_command_info.shard_count
    )
    command_message.total_test_count = command_detail.total_test_count
    command_message.passed_test_count = command_detail.passed_test_count
    command_message.failed_test_count = command_detail.failed_test_count

    command_message.start_time = command_detail.start_time.ToDatetime()
    if command_detail.end_time:
      command_message.end_time = command_detail.end_time.ToDatetime()
    command_message.create_time = command_detail.create_time.ToDatetime()
    command_message.update_time = command_detail.update_time.ToDatetime()
    return command_message

  def _GenerateCommandAttemptFromCommand(
      self,
      command_detail: service_pb2.CommandDetail,
      request_detail: service_pb2.RequestDetail,
  ) -> api_messages.CommandAttemptMessage:
    """Generate command attempt from command detail.

    A command attempt is defined as one attempt to run a command line under
    one session. Therefore command_attempt_detail can be generate from command
    detail directly. Note that the RequestDetail proto's command attempt
    represent a job or test in OLCS, which is not useful to end users.

    Args:
      command_detail: Command Detail from Request Detail proto.
      request_detail: Request Detail proto.

    Returns:
      The CommandAttemptMessage defined by TFC.
    """
    # need to add device serial info.
    command_attempt_message = api_messages.CommandAttemptMessage()
    command_attempt_message.request_id = command_detail.request_id
    command_attempt_message.command_id = command_detail.id
    command_attempt_message.attempt_id = (
        command_detail.request_id + "_" + command_detail.id
    )
    command_attempt_message.task_id = "0"
    command_attempt_message.state = _COMMAND_STATE_MAP.get(
        command_detail.state, common.CommandState.UNKNOWN
    )
    command_attempt_message.error = command_detail.error_message
    command_attempt_message.start_time = command_detail.start_time.ToDatetime()
    command_attempt_message.end_time = command_detail.end_time.ToDatetime()
    command_attempt_message.create_time = (
        command_detail.create_time.ToDatetime()
    )
    command_attempt_message.update_time = (
        command_detail.update_time.ToDatetime()
    )
    command_attempt_message.passed_test_count = command_detail.passed_test_count
    command_attempt_message.failed_test_count = command_detail.failed_test_count
    command_attempt_message.total_test_count = command_detail.total_test_count
    command_attempt_message.failed_test_run_count = (
        command_detail.failed_module_count
    )
    command_attempt_message.working_job_id = request_detail.working_job_id
    command_attempt_message.working_test_id = request_detail.working_test_id
    command_attempt_message.hostname = command_detail.host_ip
    command_attempt_message.non_tradefed_log_dir_names = list(
        request_detail.non_tradefed_log_dir_names
    )

    log_dir_path = os.path.join(
        file_util.GetLocalFilePath(
            request_detail.original_request.test_environment.output_file_upload_url
        ),
        command_attempt_message.request_id,
        command_attempt_message.command_id,
        "logs",
    )
    if os.path.exists(log_dir_path):
      for dir_name in os.listdir(log_dir_path):
        if re.match(r"inv_[a-z0-9-]+", dir_name):
          tf_path_with_inv_id = os.path.join(log_dir_path, dir_name)
          for tf_dir_name in os.listdir(tf_path_with_inv_id):
            if re.match(r"XtsTradefedTest_test_.*", tf_dir_name):
              command_attempt_message.tf_log_paths.append(
                  api_messages.KeyValuePair(
                      key=dir_name,
                      value=os.path.join("logs", dir_name, tf_dir_name),
                  )
              )
              break
    return command_attempt_message

  @staticmethod
  def GenerateRequestProto(
      request: api_messages.NewMultiCommandRequestMessage,
  ) -> session_service_pb2.CreateSessionRequest:
    """Generate request message sent to OLCS client.

    Convert TFC client defined new test request message to ATS OLC defined new
    test request proto.

    Args:
      request: TFC client defined new test request message

    Returns:
      ATS OLCS defined new test request protobuf
    """
    request_proto = service_pb2.NewMultiCommandRequest()
    request_proto.user_id = request.user
    for command_info in request.command_infos:
      command_info_proto = request_proto.commands.add()
      command_info_proto.command_line = command_info.command_line
      command_info_proto.run_count = command_info.run_count
      command_info_proto.shard_count = command_info.shard_count
      command_info_proto.allow_partial_device_match = (
          command_info.allow_partial_device_match
      )
      for group in command_info.test_bench.host.groups:
        device_attribute = group.run_targets[0].device_attributes[0]
        device_attribute_requirement = service_pb2.CommandInfo.DeviceDimension(
            name=device_attribute.name, value=device_attribute.value
        )
        command_info_proto.device_dimensions.append(
            device_attribute_requirement
        )
        command_info_proto.sharding_mode = xts_common_pb2.ShardingMode.Value(
            command_info.sharding_mode
        )
        command_info_proto.enable_xts_dynamic_download = (
            command_info.enable_xts_dynamic_download
        )
      # TODO: add device dimension
    if request.max_retry_on_test_failures:
      request_proto.max_retry_on_test_failures = (
          request.max_retry_on_test_failures
      )
    if request.max_concurrent_tasks:
      request_proto.max_concurrent_tasks = request.max_concurrent_tasks
    if request.queue_timeout_seconds:
      request_proto.queue_timeout.seconds = request.queue_timeout_seconds

    for test_resource in request.test_resources:
      test_resource_proto = request_proto.test_resources.add()
      test_resource_proto.url = test_resource.url
      test_resource_proto.name = test_resource.name
      if test_resource.path:
        test_resource_proto.path = test_resource.path
      if test_resource.decompress:
        test_resource_proto.decompress = test_resource.decompress
      if test_resource.decompress_dir:
        test_resource_proto.decompress_dir = test_resource.decompress_dir
      if test_resource.mount_zip:
        test_resource_proto.mount_zip = test_resource.mount_zip
      if test_resource.params and test_resource.params.decompress_files:
        for decompress_file in test_resource.params.decompress_files:
          test_resource_proto.params.decompress_files.append(decompress_file)
      if test_resource.original_download_url:
        test_resource_proto.original_download_url = (
            test_resource.original_download_url
        )

    if request.prev_test_context:
      for test_resource in request.prev_test_context.test_resources:
        test_resource_proto = (
            request_proto.prev_test_context.test_resource.add()
        )
        test_resource_proto.url = test_resource.url
        test_resource_proto.name = test_resource.name

    if request.test_environment:
      if request.test_environment.env_vars:
        for env_var in request.test_environment.env_vars:
          request_proto.test_environment.env_vars[env_var.key] = env_var.value
      if request.test_environment.setup_scripts:
        request_proto.test_environment.setup_scripts.extend(
            request.test_environment.setup_scripts
        )
      if request.test_environment.output_file_patterns:
        request_proto.test_environment.output_file_patterns.extend(
            request.test_environment.output_file_patterns
        )
      if request.test_environment.output_file_upload_url:
        request_proto.test_environment.output_file_upload_url = (
            request.test_environment.output_file_upload_url
        )
      if request.test_environment.use_subprocess_reporting:
        request_proto.test_environment.use_subprocess_reporting = (
            request.test_environment.use_subprocess_reporting
        )
      if request.test_environment.invocation_timeout_millis:
        request_proto.test_environment.invocation_timeout.CopyFrom(
            _MillisecToDuration(
                request.test_environment.invocation_timeout_millis
            )
        )
      if request.test_environment.output_idle_timeout_millis:
        request_proto.test_environment.output_idle_timeout.CopyFrom(
            _MillisecToDuration(
                request.test_environment.output_idle_timeout_millis
            )
        )
      if request.test_environment.jvm_options:
        request_proto.test_environment.jvm_options.extend(
            request.test_environment.jvm_options
        )
      if request.test_environment.java_properties:
        for java_property in request.test_environment.java_properties:
          request_proto.test_environment.java_properties[java_property.key] = (
              java_property.value
          )
      if request.test_environment.context_file_pattern:
        request_proto.test_environment.context_file_pattern = (
            request.test_environment.context_file_pattern
        )
      if request.test_environment.extra_context_files:
        request_proto.test_environment.extra_context_files.extend(
            request.test_environment.extra_context_files
        )
      if request.test_environment.retry_command_line:
        request_proto.test_environment.retry_command_line = (
            request.test_environment.retry_command_line
        )
      if request.test_environment.use_parallel_setup:
        request_proto.test_environment.use_parallel_setup = (
            request.test_environment.use_parallel_setup
        )
      if request.test_environment.tradefed_config_objects:
        request_proto.test_environment.device_action_config_objects.extend([
            OlcsSessionStub._ConvertToDeviceActionConfigObject(obj)
            for obj in request.test_environment.tradefed_config_objects
        ])
      if request.test_environment.tradefed_options:
        request_proto.test_environment.tradefed_options.extend([
            service_pb2.Option(name=o.key, value=o.values)
            for o in request.test_environment.tradefed_options
        ])

    end_request = session_service_pb2.CreateSessionRequest()
    session_plugin_config = (
        end_request.session_config.session_plugin_configs.session_plugin_config.add()
    )
    session_request = service_pb2.SessionRequest()
    session_request.new_multi_command_request.CopyFrom(request_proto)
    session_plugin_config.execution_config.config.Pack(session_request)
    session_plugin_config.loading_config.plugin_class_name = (
        SESSION_PLUGIN_CLASS_NAME
    )
    session_plugin_config.loading_config.plugin_module_class_name = (
        SESSION_MODULE_CLASS_NAME
    )
    session_plugin_config.explicit_label.label = SESSION_PLUGIN_LABEL
    return end_request

  @staticmethod
  def _ConvertToDeviceActionConfigObject(
      obj: api_messages.TradefedConfigObject,
  ) -> service_pb2.DeviceActionConfigObject:
    return service_pb2.DeviceActionConfigObject(
        type=_DEVICE_ACTION_TYPE_MAP.get(
            obj.type,
            service_pb2.DeviceActionConfigObject.UNKNOWN_DEVICE_ACTION_CONFIG_OBJECT_TYPE,
        ),
        class_name=obj.class_name,
        option_values=[
            service_pb2.Option(name=kv.key, value=kv.values)
            for kv in obj.option_values
        ],
    )


def _MillisecToDuration(millis: int) -> duration_pb2.Duration:
  return duration_pb2.Duration(
      seconds=int(millis / MILLIS_PER_SECOND),
      nanos=int(millis % MILLIS_PER_SECOND * NANOS_PER_MILLISECOND),
  )
