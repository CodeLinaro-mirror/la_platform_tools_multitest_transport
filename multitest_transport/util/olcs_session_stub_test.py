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
"""Tests for multitest_transport.util.olcs_session_stub."""
from concurrent import futures
import os
import time
from unittest import mock

from absl.testing import absltest
from google.protobuf import text_format
import grpc
import grpc_testing
from multitest_transport.models import ndb_models
from multitest_transport.util import olcs_session_client
from multitest_transport.util import olcs_session_stub
from protorpc import protojson
from tradefed_cluster import api_messages
from tradefed_cluster import testbed_dependent_test
from tradefed_cluster.util import ndb_test_lib

from com_google_deviceinfra.src.devtools.mobileharness.infra.ats.server.proto import service_pb2
from com_google_deviceinfra.src.devtools.mobileharness.infra.client.longrunningservice.proto import session_pb2
from com_google_deviceinfra.src.devtools.mobileharness.infra.client.longrunningservice.proto import session_service_pb2

TEST_DATA_DIR = os.path.join(os.path.dirname(__file__), 'test_data')


class OlcsSessionStubTest(testbed_dependent_test.TestbedDependentTest):

  def setUp(self):
    super().setUp()
    self._executor = futures.ThreadPoolExecutor(max_workers=10)
    self._time = grpc_testing.strict_real_time()
    self._descriptor = session_service_pb2.DESCRIPTOR.services_by_name[
        'SessionService'
    ]
    self._channel = grpc_testing.channel(
        self._descriptor,
        grpc_testing.strict_real_time(),
    )
    self._stubby_client = olcs_session_client.OlcsSessionClient(self._channel)
    self._trailing_metadata = ()
    self._detailed_message = ''
    self.session_stub = olcs_session_stub.OlcsSessionStub(self._stubby_client)

  def tearDown(self):
    self._executor.shutdown(wait=True)
    super().tearDown()

  def testCreateNewRequest(self):
    client_response = session_service_pb2.CreateSessionResponse()
    client_response.session_id.id = 'test_session_id'

    # Create input to the session service stub.
    request_message = api_messages.NewMultiCommandRequestMessage(
        user='test_user'
    )

    # Create the expected request proto sent to session service.
    request_proto = session_service_pb2.CreateSessionRequest()
    session_request_proto = service_pb2.SessionRequest()
    session_request_proto.new_multi_command_request.user_id = 'test_user'
    request_proto.session_config.session_plugin_configs.session_plugin_config.add().execution_config.config.Pack(
        session_request_proto
    )
    request_proto.session_config.session_plugin_configs.session_plugin_config[
        0
    ].explicit_label.label = olcs_session_stub.SESSION_PLUGIN_LABEL
    request_proto.session_config.session_plugin_configs.session_plugin_config[
        0
    ].loading_config.plugin_class_name = (
        olcs_session_stub.SESSION_PLUGIN_CLASS_NAME
    )
    request_proto.session_config.session_plugin_configs.session_plugin_config[
        0
    ].loading_config.plugin_module_class_name = (
        olcs_session_stub.SESSION_MODULE_CLASS_NAME
    )

    application_future = self._executor.submit(
        self.session_stub.CreateNewRequest, request_message
    )
    _, _, rpc = self._channel.take_unary_unary(
        self._descriptor.methods_by_name['CreateSession']
    )
    rpc.send_initial_metadata(())
    rpc.terminate(
        client_response,
        self._trailing_metadata,
        grpc.StatusCode.OK,
        self._detailed_message,
    )

    stub_response = application_future.result()
    # Assert service response.
    self.assertEqual(stub_response, client_response.session_id.id)

  def testGetRequestWithDatabase(self):
    expected_request_message = api_messages.RequestMessage(id='test_request_id')
    self.mock_request_info = ndb_models.RequestInfo(
        id='test_request_id',
        request_json_str=protojson.encode_message(expected_request_message),  # pytype: disable=module-attr
    )
    self.mock_request_info.put()
    request_message = self.session_stub.GetRequest('test_request_id')
    self.assertEqual(request_message, expected_request_message)

  def GetRequestWrapper(self, request_id):
    """Wrapper for GetRequest, which creates NDB context before the test so the ndb operation can suceed."""
    manager = ndb_test_lib.NdbContextManager()
    manager.__enter__()
    result = self.session_stub.GetRequest(request_id)
    manager.__exit__(None, None, None)
    return result

  def testGetRequest(self):
    with open(
        os.path.join(TEST_DATA_DIR, 'request_detail.textproto')
    ) as text_format_file:
      request_detail = text_format.Parse(
          text_format_file.read(), service_pb2.RequestDetail()
      )
    client_response = session_service_pb2.GetSessionResponse()
    client_response.session_detail.session_output.session_plugin_output[
        olcs_session_stub.SESSION_PLUGIN_LABEL
    ].output.Pack(request_detail)

    application_future = self._executor.submit(
        self.GetRequestWrapper, request_detail.id
    )
    _, _, rpc = self._channel.take_unary_unary(
        self._descriptor.methods_by_name['GetSession']
    )
    rpc.send_initial_metadata(())
    rpc.terminate(
        client_response,
        self._trailing_metadata,
        grpc.StatusCode.OK,
        self._detailed_message,
    )

    request_message = application_future.result()

    self.assertEqual(request_message.id, request_detail.id)
    self.assertEqual(request_message.state, api_messages.RequestState.COMPLETED)
    self.assertEqual(
        request_message.command_infos[0].command_line,
        request_detail.command_infos[0].command_line,
    )

    # Verify the command message.
    command_message = request_message.commands[0]
    command_detail = list(request_detail.command_details.values())[0]
    self.assertEqual(command_message.command_line, command_detail.command_line)
    self.assertEqual(command_message.state, api_messages.CommandState.COMPLETED)
    self.assertEqual(
        command_message.run_count,
        command_detail.original_command_info.run_count,
    )
    self.assertEqual(
        command_message.shard_count,
        command_detail.original_command_info.shard_count,
    )
    self.assertEqual(
        command_message.passed_test_count, command_detail.passed_test_count
    )
    self.assertEqual(
        command_message.failed_test_count, command_detail.failed_test_count
    )
    self.assertEqual(
        command_message.total_test_count, command_detail.total_test_count
    )

    # Verify the command attempt message.
    command_attempt_message = request_message.command_attempts[0]
    self.assertEqual(
        command_attempt_message.request_id, command_detail.request_id
    )
    self.assertEqual(command_attempt_message.command_id, command_detail.id)
    self.assertEqual(
        command_attempt_message.state, api_messages.CommandState.COMPLETED
    )
    self.assertEqual(
        command_attempt_message.passed_test_count,
        command_detail.passed_test_count,
    )
    self.assertEqual(
        command_attempt_message.failed_test_count,
        command_detail.failed_test_count,
    )
    self.assertEqual(
        command_attempt_message.total_test_count,
        command_detail.total_test_count,
    )
    self.assertCountEqual(
        command_attempt_message.device_serials,
        request_detail.command_attempt_details[0].device_serials,
    )
    self.assertEqual(
        command_attempt_message.start_time,
        command_detail.start_time.ToDatetime(),
    )
    self.assertEqual(
        command_attempt_message.end_time,
        command_detail.end_time.ToDatetime(),
    )
    self.assertEqual(
        command_attempt_message.create_time,
        command_detail.create_time.ToDatetime(),
    )
    self.assertEqual(
        command_attempt_message.update_time,
        command_detail.update_time.ToDatetime(),
    )

  def test_generate_request_proto(self):
    with open(
        os.path.join(TEST_DATA_DIR, 'test_new_request_msg.json'), 'rb'
    ) as f:
      new_request_msg = protojson.decode_message(
          api_messages.NewMultiCommandRequestMessage, f.read()
      )
      create_session_request = (
          olcs_session_stub.OlcsSessionStub.GenerateRequestProto(
              new_request_msg
          )
      )
      session_request_proto = service_pb2.SessionRequest()
      create_session_request.session_config.session_plugin_configs.session_plugin_config[
          0
      ].execution_config.config.Unpack(
          session_request_proto
      )
      request_proto = session_request_proto.new_multi_command_request

      self.assertEqual(request_proto.user_id, new_request_msg.user)
      self.assertEqual(request_proto.user_id, 'test_kicker')
      self.assertEqual(
          request_proto.commands.__len__(),
          new_request_msg.command_infos.__len__(),
      )

      # Verify commands.
      command_proto = request_proto.commands[0]
      command_msg = new_request_msg.command_infos[0]
      self.assertEqual(command_proto.command_line, command_msg.command_line)
      self.assertEqual(command_proto.run_count, command_msg.run_count)
      self.assertEqual(command_proto.shard_count, command_msg.shard_count)

      self.assertEqual(
          request_proto.max_retry_on_test_failures,
          new_request_msg.max_retry_on_test_failures,
      )
      self.assertEqual(
          request_proto.queue_timeout.seconds,
          new_request_msg.queue_timeout_seconds,
      )

      # Verify test resources
      self.assertEqual(
          len(request_proto.test_resources), len(new_request_msg.test_resources)
      )
      test_resource_proto1 = request_proto.test_resources[0]
      test_resource_msg1 = new_request_msg.test_resources[0]
      self.assertEqual(test_resource_proto1.url, test_resource_msg1.url)
      self.assertEqual(test_resource_proto1.name, test_resource_msg1.name)
      self.assertEqual(
          test_resource_proto1.decompress, test_resource_msg1.decompress
      )
      self.assertEqual(
          test_resource_proto1.decompress_dir, test_resource_msg1.decompress_dir
      )
      self.assertEqual(
          test_resource_proto1.mount_zip, test_resource_msg1.mount_zip
      )
      self.assertEqual(
          len(test_resource_proto1.params.decompress_files),
          len(test_resource_msg1.params.decompress_files),
      )

      test_resource_proto2 = request_proto.test_resources[1]
      test_resource_msg2 = new_request_msg.test_resources[1]
      self.assertEqual(test_resource_proto2.url, test_resource_msg2.url)
      self.assertEqual(test_resource_proto2.name, test_resource_msg2.name)

      # Verify test environment
      self.assertEqual(
          request_proto.test_environment.env_vars.__len__(),
          new_request_msg.test_environment.env_vars.__len__(),
      )
      for pair in new_request_msg.test_environment.env_vars:
        self.assertEqual(
            request_proto.test_environment.env_vars[pair.key], pair.value
        )
      self.assertEqual(
          request_proto.test_environment.setup_scripts,
          new_request_msg.test_environment.setup_scripts,
      )
      self.assertEqual(
          request_proto.test_environment.output_file_patterns,
          new_request_msg.test_environment.output_file_patterns,
      )
      self.assertEqual(
          request_proto.test_environment.output_file_upload_url,
          new_request_msg.test_environment.output_file_upload_url,
      )
      self.assertEqual(
          request_proto.test_environment.use_subprocess_reporting,
          new_request_msg.test_environment.use_subprocess_reporting,
      )
      self.assertEqual(
          int(
              request_proto.test_environment.invocation_timeout.seconds * 1000
              + request_proto.test_environment.invocation_timeout.nanos
              / 1000000
          ),
          new_request_msg.test_environment.invocation_timeout_millis,
      )
      self.assertEqual(
          int(
              request_proto.test_environment.output_idle_timeout.seconds * 1000
              + request_proto.test_environment.output_idle_timeout.nanos
              / 1000000
          ),
          new_request_msg.test_environment.output_idle_timeout_millis,
      )
      self.assertEqual(
          request_proto.test_environment.jvm_options,
          new_request_msg.test_environment.jvm_options,
      )
      self.assertEqual(
          request_proto.test_environment.java_properties.__len__(),
          new_request_msg.test_environment.java_properties.__len__(),
      )
      for pair in new_request_msg.test_environment.java_properties:
        self.assertEqual(
            request_proto.test_environment.java_properties[pair.key], pair.value
        )
      self.assertEqual(
          request_proto.test_environment.context_file_pattern,
          new_request_msg.test_environment.context_file_pattern,
      )
      self.assertEqual(
          request_proto.test_environment.extra_context_files,
          new_request_msg.test_environment.extra_context_files,
      )
      self.assertEqual(
          request_proto.test_environment.retry_command_line,
          new_request_msg.test_environment.retry_command_line,
      )
      self.assertEqual(
          request_proto.test_environment.use_parallel_setup,
          new_request_msg.test_environment.use_parallel_setup,
      )
      self.assertEqual(
          request_proto.test_environment.device_action_config_objects,
          [
              service_pb2.DeviceActionConfigObject(
                  type=service_pb2.DeviceActionConfigObject.DeviceActionConfigObjectType.TARGET_PREPARER,
                  class_name='com.android.tradefed.targetprep.DeviceCleaner',
                  option_values=[
                      service_pb2.DeviceActionConfigObject.Option(
                          name='post-cleanup', value=['SCREEN_OFF']
                      )
                  ],
              ),
              service_pb2.DeviceActionConfigObject(
                  type=service_pb2.DeviceActionConfigObject.DeviceActionConfigObjectType.RESULT_REPORTER,
                  class_name='com.google.android.tradefed.result.teststorage.ResultReporter',
              ),
          ],
      )

  def testSubscribeSession(self):
    subscribe_session_request = session_service_pb2.SubscribeSessionRequest()
    subscribe_session_request.get_session_request.session_id.id = (
        'test_session_id'
    )
    subscribe_session_response_1 = (
        session_service_pb2.SubscribeSessionResponse()
    )
    subscribe_session_response_1.get_session_response.session_detail.session_id.id = (
        'test_session_id'
    )
    subscribe_session_response_1.get_session_response.session_detail.session_status = (
        session_pb2.SessionStatus.SESSION_RUNNING
    )
    subscribe_session_response_2 = (
        session_service_pb2.SubscribeSessionResponse()
    )
    subscribe_session_response_2.get_session_response.session_detail.session_id.id = (
        'test_session_id'
    )
    subscribe_session_response_2.get_session_response.session_detail.session_status = (
        session_pb2.SessionStatus.SESSION_FINISHED
    )

    mock_method = mock.Mock()

    future = self._executor.submit(
        self.session_stub.StartSubscribeSession,
        'test_session_id',
        mock_method,
    )
    subscribe_id = future.result()
    _, rpc = self._channel.take_stream_stream(
        self._descriptor.methods_by_name['SubscribeSession']
    )
    rpc.send_initial_metadata(())
    rpc.take_request()
    rpc.send_response(subscribe_session_response_1)
    rpc.send_response(subscribe_session_response_2)
    time.sleep(5)
    self.session_stub.StopSubscribeSession(subscribe_id)
    rpc.requests_closed()
    rpc.terminate(
        self._trailing_metadata,
        grpc.StatusCode.OK,
        self._detailed_message,
    )
    mock_method.assert_any_call(subscribe_session_response_1)
    mock_method.assert_any_call(subscribe_session_response_2)


if __name__ == '__main__':
  absltest.main()
