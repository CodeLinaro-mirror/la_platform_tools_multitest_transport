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

import logging
from typing import List, Optional

from multitest_transport.models import ndb_models
from multitest_transport.util import olcs_session_client
from protorpc import protojson
from tradefed_cluster import api_messages
from tradefed_cluster import common

from google3.google.protobuf import duration_pb2
from com_google_deviceinfra.src.devtools.mobileharness.infra.ats.server.proto import service_pb2
from com_google_deviceinfra.src.devtools.mobileharness.infra.client.longrunningservice.proto import session_service_pb2


SESSION_PLUGIN_CLASS_NAME = "com.google.devtools.mobileharness.infra.ats.server.sessionplugin.AtsServerSessionPlugin"
SESSION_MODULE_CLASS_NAME = "com.google.devtools.mobileharness.infra.ats.server.sessionplugin.AtsServerSessionPluginModule"
SESSION_PLUGIN_LABEL = "AtsServerSessionPlugin"
NANOS_PER_MILLISECOND = 1000000
MILLIS_PER_SECOND = 1000


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
    service_pb2.CancelReason.COMMAND_NOT_EXECUTABLE: (
        common.CancelReason.COMMAND_NOT_EXECUTABLE
    ),
    service_pb2.CancelReason.INVALID_REQUEST: (
        common.CancelReason.INVALID_REQUEST
    ),
    # No corresponding id for invalid resource error, need to add.
    service_pb2.CancelReason.INVALID_RESOURCE: (
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
    request = self.GetRequest(request_id)
    attempt_map = {}
    for attempt in request.command_attempts:
      if not common.IsFinalCommandState(attempt.state):
        continue
      attempt_map[attempt.command_id] = attempt
    return list(attempt_map.values())

  # TODO: To be implemented
  def GetTestContext(
      self, request_id: str, command_id: str
  ) -> api_messages.TestContext:
    del request_id, command_id  # TODO: To be completed.
    test_context = api_messages.TestContext()
    return test_context

  def _FetchRequest(self, request_id: str) -> api_messages.RequestMessage:
    """Fetch request from OLCS and convert to TFC request message.

    Args:
      request_id: The request id of the request.

    Returns:
      The request message defined by TFC.
    """
    request = session_service_pb2.GetSessionRequest()
    request.session_id.id = request_id
    response = self._client.get_session(request)
    request_detail = service_pb2.RequestDetail()
    response.session_detail.session_output.session_plugin_output[
        SESSION_PLUGIN_LABEL
    ].output.Unpack(request_detail)
    logging.info(
        "Fetched request detail proto from OLCS: %s", request_detail.__str__()
    )

    request_message = api_messages.RequestMessage()
    request_message.id = request_id
    request_message.user = request_detail.user
    request_message.command_infos = list(
        map(self._ConvertProtoToCommandInfo, request_detail.command_infos)
    )
    request_message.priority = request_detail.priority
    request_message.queue_timeout_seconds = request_detail.queue_timeout.seconds
    request_message.cancel_reason = _TEST_RUN_CANCEL_REASON_MAP.get(
        request_detail.cancel_reason, common.CancelReason.UNKNOWN
    )
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

    request_message.commands = list(
        map(
            self._ConvertCommandDetail,
            request_detail.command_details.values(),
        )
    )
    request_message.command_attempts = list(
        map(
            self._ConvertCommandAttemptDetail,
            request_detail.command_attempt_details,
        )
    )
    return request_message

  def GetRequest(self, request_id):
    """Get request from OLCS or from Database.

    Args:
      request_id: The request id of the request.

    Returns:
      The request message defined by TFC.
    """
    test_request = ndb_models.RequestInfo.get_by_id(request_id)
    if test_request:
      request_json = test_request.request_json_str
      # pytype: disable=module-attr
      return protojson.decode_message(api_messages.RequestMessage, request_json)
      # pytype: enable=module-attr
    test_request = self._FetchRequest(request_id)
    if test_request:
      if (
          test_request.state == common.RequestState.COMPLETED
          or test_request.state == common.RequestState.ERROR
      ):
        request_info = ndb_models.RequestInfo(
            id=request_id,
            request_json_str=protojson.encode_message(test_request),  # pytype: disable=module-attr
        )
        request_info.put()
      return test_request
    return None

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

  def _ConvertProtoToCommandInfo(
      self, proto: service_pb2.CommandInfo
  ) -> api_messages.CommandInfo:
    command_info_message = api_messages.CommandInfo()
    command_info_message.name = proto.name
    command_info_message.command_line = proto.command_line
    # TODO: add cluster
    command_info_message.run_count = proto.run_count
    command_info_message.shard_count = proto.shard_count
    return command_info_message

  def _ConvertCommandDetail(
      self, command_detail: service_pb2.CommandDetail
  ) -> api_messages.CommandMessage:
    """Convert Command Detail from Request Detail proto to TFC CommandMessage.

    Args:
      command_detail: Command Detail from Request Detail proto.

    Returns:
      The CommandMessage defined by TFC.
    """
    command_message = api_messages.CommandMessage()
    command_message.id = command_detail.id
    command_message.request_id = command_detail.request_id
    command_message.command_line = command_detail.command_line

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
    return command_message

  def _ConvertCommandAttemptDetail(
      self, command_attempt_detail: service_pb2.CommandAttemptDetail
  ) -> api_messages.CommandAttemptMessage:
    """Convert Command Attempt Detail from Request Detail proto to TFC CommandAttemptMessage.

    Args:
      command_attempt_detail: Command Attempt Detail from Request Detail proto.

    Returns:
      The CommandAttemptMessage defined by TFC.
    """
    command_attempt_message = api_messages.CommandAttemptMessage()
    command_attempt_message.request_id = command_attempt_detail.request_id
    command_attempt_message.attempt_id = command_attempt_detail.id
    command_attempt_message.command_id = command_attempt_detail.command_id
    command_attempt_message.task_id = "0"  # TODO: what is this
    command_attempt_message.state = _COMMAND_STATE_MAP.get(
        command_attempt_detail.state, common.CommandState.UNKNOWN
    )
    command_attempt_message.device_serials = list(
        command_attempt_detail.device_serials
    )
    command_attempt_message.start_time = (
        command_attempt_detail.start_time.ToDatetime()
    )
    command_attempt_message.end_time = (
        command_attempt_detail.end_time.ToDatetime()
    )
    command_attempt_message.create_time = (
        command_attempt_detail.create_time.ToDatetime()
    )
    command_attempt_message.update_time = (
        command_attempt_detail.update_time.ToDatetime()
    )
    command_attempt_message.passed_test_count = (
        command_attempt_detail.passed_test_count
    )
    command_attempt_message.failed_test_count = (
        command_attempt_detail.failed_test_count
    )
    command_attempt_message.total_test_count = (
        command_attempt_detail.total_test_count
    )
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
      for group in command_info.test_bench.host.groups:
        device_attribute = group.run_targets[0].device_attributes[0]
        device_attribute_requirement = service_pb2.CommandInfo.DeviceDimension(
            name=device_attribute.name, value=device_attribute.value
        )
        command_info_proto.device_dimensions.append(
            device_attribute_requirement
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

    if request.test_environment:
      if request.test_environment.env_vars:
        for env_var in request.test_environment.env_vars:
          request_proto.test_environment.env_vars[env_var.key] = env_var.value
      if request.test_environment.setup_scripts:
        request_proto.test_environment.setup_scripts = (
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
            service_pb2.DeviceActionConfigObject.Option(
                name=kv.key, value=kv.values
            )
            for kv in obj.option_values
        ],
    )


def _MillisecToDuration(millis: int) -> duration_pb2.Duration:
  return duration_pb2.Duration(
      seconds=int(millis / MILLIS_PER_SECOND),
      nanos=int(millis % MILLIS_PER_SECOND * NANOS_PER_MILLISECOND),
  )
