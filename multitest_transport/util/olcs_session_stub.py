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

from multitest_transport.util import olcs_session_client
from tradefed_cluster import api_messages

from google3.google.protobuf import duration_pb2
from com_google_deviceinfra.src.devtools.mobileharness.infra.ats.server.proto import service_pb2
from com_google_deviceinfra.src.devtools.mobileharness.infra.client.longrunningservice.proto import session_service_pb2

SESSION_PLUGIN_CLASS_NAME = "com.google.devtools.mobileharness.infra.ats.server.sessionplugin.AtsServerSessionPlugin"
SESSION_PLUGIN_LABEL = "AtsServerSessionPlugin"
NANOS_PER_MILLISECOND = 1000000
MILLIS_PER_SECOND = 1000


class OlcsSessionStub:
  """The OLCS session service stub to send ats server specific request to OLCS."""

  def __init__(self, client: None):
    if client is None:
      self._client = olcs_session_client.OlcsSessionClient.create()
    else:
      self._client = client

  def create_new_request(
      self, request: api_messages.NewMultiCommandRequestMessage
  ) -> str:
    response = self._client.create_session(
        OlcsSessionStub.generate_request_proto(request)
    )
    return response.session_id.id

  def get_request(self, request_id: str) -> api_messages.RequestMessage:
    request = session_service_pb2.GetSessionRequest()
    request.session_id = request_id
    response = self._client.get_session(request)
    request_detail = service_pb2.RequestDetail
    response.session_detail.session_output.session_plugin_output[
        SESSION_PLUGIN_CLASS_NAME
    ].output.Unpack(request_detail)
    # TODO: decoding from request detail proto to be implemented.
    return api_messages.RequestMessage(id=request_detail.id)

  @staticmethod
  def generate_request_proto(
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
      # TODO: add device dimension
    if request.max_retry_on_test_failures:
      request_proto.max_retry_on_test_failures = (
          request.max_retry_on_test_failures
      )
    if request.max_concurrent_tasks:
      request_proto.max_concurrent_tasks = request.max_concurrent_tasks

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
            _millisec_to_duration(
                request.test_environment.invocation_timeout_millis
            )
        )
      if request.test_environment.output_idle_timeout_millis:
        request_proto.test_environment.output_idle_timeout.CopyFrom(
            _millisec_to_duration(
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

    end_request = session_service_pb2.CreateSessionRequest()
    session_plugin_config = (
        end_request.session_config.session_plugin_configs.session_plugin_config.add()
    )
    session_plugin_config.execution_config.config.Pack(request_proto)
    session_plugin_config.loading_config.plugin_class_name = (
        SESSION_PLUGIN_CLASS_NAME
    )
    session_plugin_config.explicit_label.label = SESSION_PLUGIN_LABEL
    return end_request


def _millisec_to_duration(millis: int) -> duration_pb2.Duration:
  return duration_pb2.Duration(
      seconds=int(millis / MILLIS_PER_SECOND),
      nanos=int(millis % MILLIS_PER_SECOND * NANOS_PER_MILLISECOND),
  )
