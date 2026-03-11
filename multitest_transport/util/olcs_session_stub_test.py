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
import base64
from concurrent import futures
import os
import queue
import threading
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

  def testGetSharedClient(self):
    client1 = olcs_session_stub._GetSharedClient()
    client2 = olcs_session_stub._GetSharedClient()
    self.assertIs(client1, client2)

  def testNotifySubscribers(self):
    request_id = 'test_request_id'
    request_message = api_messages.RequestMessage(id=request_id)
    callback1 = mock.Mock()
    callback2 = mock.Mock()
    # Mock exception in callback2 to verify it doesn't block other callbacks
    callback2.side_effect = Exception('callback error')
    callback3 = mock.Mock()

    # Manually register subscribers
    sub_id1 = 'sub1'
    sub_id2 = 'sub2'
    sub_id3 = 'sub3'
    olcs_session_stub._active_subscriptions[sub_id1] = request_id
    olcs_session_stub._active_subscriptions[sub_id2] = request_id
    olcs_session_stub._active_subscriptions[sub_id3] = request_id
    olcs_session_stub._subscribers[request_id][sub_id1] = callback1
    olcs_session_stub._subscribers[request_id][sub_id2] = callback2
    olcs_session_stub._subscribers[request_id][sub_id3] = callback3

    try:
      self.session_stub._NotifySubscribers(request_message)

      callback1.assert_called_once_with(request_message)
      callback2.assert_called_once_with(request_message)
      callback3.assert_called_once_with(request_message)
    finally:
      # Clean up global state
      del olcs_session_stub._active_subscriptions[sub_id1]
      del olcs_session_stub._active_subscriptions[sub_id2]
      del olcs_session_stub._active_subscriptions[sub_id3]
      del olcs_session_stub._subscribers[request_id][sub_id1]
      del olcs_session_stub._subscribers[request_id][sub_id2]
      del olcs_session_stub._subscribers[request_id][sub_id3]

  def testCancelRequest(self):
    client_response = session_service_pb2.NotifySessionResponse(successful=True)
    request_id = 'test_request_id'
    application_future = self._executor.submit(
        self.session_stub.CancelRequest, request_id
    )
    _, _, rpc = self._channel.take_unary_unary(
        self._descriptor.methods_by_name['NotifySession']
    )
    rpc.send_initial_metadata(())
    rpc.terminate(
        client_response,
        self._trailing_metadata,
        grpc.StatusCode.OK,
        self._detailed_message,
    )
    actual_response = application_future.result()
    self.assertEqual(True, actual_response)

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

  def testGetTestContext(self):
    with open(
        os.path.join(TEST_DATA_DIR, 'request_detail.textproto')
    ) as text_format_file:
      request_detail = text_format.Parse(
          text_format_file.read(), service_pb2.RequestDetail()
      )
    request_id = request_detail.id
    command_id = list(request_detail.command_details.keys())[0]
    request_detail_str = request_detail.SerializeToString()
    base64_string = base64.b64encode(request_detail_str).decode('utf-8')
    self.mock_request_info = ndb_models.RequestInfo(
        id=request_id,
        request_detail_proto_str=base64_string,
    )
    self.mock_request_info.put()
    actual_test_context = self.session_stub.GetTestContext(
        request_id, command_id
    )

    self.assertEqual(
        actual_test_context.command_line,
        request_detail.test_context.get(command_id).command_line,
    )
    self.assertEqual(
        actual_test_context.env_vars.__len__(),
        5,
    )
    actual_test_resource = actual_test_context.test_resources[0]
    expected_test_resource = request_detail.test_context.get(
        command_id
    ).test_resource[0]
    self.assertEqual(actual_test_resource.url, expected_test_resource.url)
    self.assertEqual(actual_test_resource.name, expected_test_resource.name)

  @mock.patch.object(olcs_session_stub.OlcsSessionStub, '_GetRequestDetail')
  def testGetTestContext_FetchWhenNotInDb(self, mock_get_request_detail):
    request_id = 'test_request_id_fetch'
    command_id = 'test_command_id_fetch'

    expected_request_detail = service_pb2.RequestDetail()
    expected_request_detail.id = request_id
    test_context_proto = expected_request_detail.test_context[command_id]
    test_context_proto.command_line = 'sample command line'
    test_context_proto.env_var['ENV_KEY_1'] = 'ENV_VALUE_1'
    test_context_proto.env_var['ENV_KEY_2'] = 'ENV_VALUE_2'
    resource1 = test_context_proto.test_resource.add()
    resource1.url = 'http://example.com/resource1.zip'
    resource1.name = 'resource1.zip'
    resource1.password = 'password'

    mock_get_request_detail.return_value = expected_request_detail

    actual_test_context = self.session_stub.GetTestContext(
        request_id, command_id
    )

    mock_get_request_detail.assert_called_once_with(request_id)

    self.assertEqual(
        actual_test_context.command_line,
        test_context_proto.command_line,
    )
    expected_env_vars_list = [
        api_messages.KeyValuePair(key='ENV_KEY_1', value='ENV_VALUE_1'),
        api_messages.KeyValuePair(key='ENV_KEY_2', value='ENV_VALUE_2'),
    ]
    self.assertCountEqual(actual_test_context.env_vars, expected_env_vars_list)

    self.assertLen(actual_test_context.test_resources, 1)
    actual_test_resource = actual_test_context.test_resources[0]
    expected_test_resource_proto = test_context_proto.test_resource[0]
    self.assertEqual(actual_test_resource.url, expected_test_resource_proto.url)
    self.assertEqual(
        actual_test_resource.name, expected_test_resource_proto.name
    )
    self.assertEqual(
        actual_test_resource.password, expected_test_resource_proto.password
    )

  @mock.patch.object(olcs_session_stub.OlcsSessionStub, '_GetRequestDetail')
  def testGetTestContext_FetchReturnsNone(self, mock_get_request_detail):
    request_id = 'test_request_id_fetch_none'
    command_id = 'test_command_id_fetch_none'

    mock_get_request_detail.return_value = None

    actual_test_context = self.session_stub.GetTestContext(
        request_id, command_id
    )

    mock_get_request_detail.assert_called_once_with(request_id)

    self.assertEqual(actual_test_context, api_messages.TestContext())

  def testGetRequestWithDatabase(self):
    expected_request_detail = service_pb2.RequestDetail(id='test_request_id')
    request_detail_str = expected_request_detail.SerializeToString()
    base64_string = base64.b64encode(request_detail_str).decode('utf-8')
    self.mock_request_info = ndb_models.RequestInfo(
        id='test_request_id',
        request_detail_proto_str=base64_string,
    )
    self.mock_request_info.put()
    request_message = self.session_stub.GetRequest('test_request_id')
    self.assertEqual(request_message.id, expected_request_detail.id)

  def testGetRequest_commandTimes(self):
    """Test that command start/end times are set from attempts."""
    with open(
        os.path.join(TEST_DATA_DIR, 'request_detail.textproto')
    ) as text_format_file:
      request_detail = text_format.Parse(
          text_format_file.read(), service_pb2.RequestDetail()
      )

    # All attempts are finished, command should have latest end time
    request_message = self.session_stub.GenerateRequestMessage(request_detail)
    self.assertLen(request_message.commands, 1)
    command = request_message.commands[0]
    self.assertEqual(
        command.start_time,
        min(
            c.start_time.ToDatetime()
            for c in request_detail.command_details.values()
        ),
    )
    self.assertEqual(
        command.end_time,
        max(
            c.end_time.ToDatetime()
            for c in request_detail.command_details.values()
        ),
    )

    # Mark one attempt as not finished
    list(request_detail.command_details.values())[
        0
    ].state = service_pb2.CommandState.RUNNING
    request_message = self.session_stub.GenerateRequestMessage(request_detail)
    self.assertIsNone(request_message.commands[0].end_time)

  def GetRequestWrapper(self, request_id):
    """Wrapper for GetRequest, which creates NDB context before the test so the ndb operation can suceed."""
    manager = ndb_test_lib.NdbContextManager()
    manager.__enter__()
    result = self.session_stub.GetRequest(request_id)
    manager.__exit__(None, None, None)
    return result

  def GetLatestFinishedAttemptsWrapper(self, request_id):
    """Wrapper for GetRequest, which creates NDB context before the test so the ndb operation can suceed."""
    manager = ndb_test_lib.NdbContextManager()
    manager.__enter__()
    result = self.session_stub.GetLatestFinishedAttempts(request_id)
    manager.__exit__(None, None, None)
    return result

  @mock.patch('os.path.exists')
  @mock.patch('os.listdir')
  def testGetLatestFinishedAttempts(self, mock_listdir, mock_exists):
    with open(
        os.path.join(TEST_DATA_DIR, 'request_detail.textproto')
    ) as text_format_file:
      request_detail = text_format.Parse(
          text_format_file.read(), service_pb2.RequestDetail()
      )
    request_detail.non_tradefed_log_dir_names.append(
        'MoblyAospTest_test_TEST_ID2'
    )
    mock_exists.return_value = True
    mock_listdir.side_effect = [
        ['inv_1234567890', 'other_dir'],  # Top-level directory
        ['TradefedTest_test_TEST_ID1', 'unmatched_dir'],  # Inside inv_...
    ]
    client_response = session_service_pb2.GetSessionResponse()
    client_response.session_detail.session_output.session_plugin_output[
        olcs_session_stub.SESSION_PLUGIN_LABEL
    ].output.Pack(request_detail)

    application_future = self._executor.submit(
        self.GetLatestFinishedAttemptsWrapper, request_detail.id
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

    command_attempts = application_future.result()
    self.assertLen(command_attempts, 1)
    command_detail = list(request_detail.command_details.values())[0]
    # Verify the command attempt message.
    command_attempt_message = command_attempts[0]
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
    self.assertEqual(
        command_attempt_message.failed_test_run_count,
        command_detail.failed_module_count,
    )
    self.assertCountEqual(
        command_attempt_message.attempt_id,
        command_detail.command_attempt_id,
    )
    self.assertCountEqual(
        command_attempt_message.device_serials,
        command_detail.device_serials,
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
    self.assertEqual(
        command_attempt_message.tf_log_paths[0].key,
        'inv_1234567890',
    )
    self.assertEqual(
        command_attempt_message.tf_log_paths[0].value,
        'logs/inv_1234567890/TradefedTest_test_TEST_ID1',
    )
    self.assertEqual(
        command_attempt_message.non_tradefed_log_dir_names,
        ['MoblyAospTest_test_TEST_ID2'],
    )

  def testGenerateRequestMessage_TestModuleResults(self):
    detail = service_pb2.RequestDetail(id='test')
    res = detail.test_module_results.add()
    res.name = 'm1'
    res.complete = True
    res.duration_ms = 1000
    res.passed_tests = 5
    res.failed_tests = 1
    res.total_tests = 6
    msg = self.session_stub.GenerateRequestMessage(detail)
    self.assertLen(msg.test_module_results, 1)
    self.assertEqual(msg.test_module_results[0].name, 'm1')
    self.assertTrue(msg.test_module_results[0].complete)
    self.assertEqual(msg.test_module_results[0].duration_ms, 1000)
    self.assertEqual(msg.test_module_results[0].passed_tests, 5)
    self.assertEqual(msg.test_module_results[0].failed_tests, 1)
    self.assertEqual(msg.test_module_results[0].total_tests, 6)

  @mock.patch('os.path.exists')
  @mock.patch('os.listdir')
  def testGetRequest(self, mock_listdir, mock_exists):
    with open(
        os.path.join(TEST_DATA_DIR, 'request_detail.textproto')
    ) as text_format_file:
      request_detail = text_format.Parse(
          text_format_file.read(), service_pb2.RequestDetail()
      )
    request_detail.non_tradefed_log_dir_names.append(
        'MoblyAospTest_test_TEST_ID2'
    )
    mock_exists.return_value = True
    mock_listdir.side_effect = [
        ['inv_1234567890', 'other_dir'],  # Top-level directory
        ['TradefedTest_test_TEST_ID1', 'unmatched_dir'],  # Inside inv_...
    ]
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
    self.assertEqual(
        command_attempt_message.failed_test_run_count,
        command_detail.failed_module_count,
    )
    self.assertCountEqual(
        command_attempt_message.attempt_id,
        command_detail.command_attempt_id,
    )
    self.assertCountEqual(
        command_attempt_message.device_serials,
        command_detail.device_serials,
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
    self.assertEqual(
        command_attempt_message.tf_log_paths[0].key,
        'inv_1234567890',
    )
    self.assertEqual(
        command_attempt_message.tf_log_paths[0].value,
        'logs/inv_1234567890/TradefedTest_test_TEST_ID1',
    )
    self.assertEqual(
        command_attempt_message.non_tradefed_log_dir_names,
        ['MoblyAospTest_test_TEST_ID2'],
    )

  def test_generate_request_proto(self):
    with open(
        os.path.join(TEST_DATA_DIR, 'test_new_request_msg.json'), 'rb'
    ) as f:
      new_request_msg = protojson.decode_message(
          api_messages.NewMultiCommandRequestMessage, f.read()
      )
      new_request_msg.test_environment.setup_scripts.append('setup.sh')
      new_request_msg.test_resources[0].password = 'password1'
      new_request_msg.prev_test_context.test_resources[0].password = 'password2'
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
          command_proto.allow_partial_device_match,
          command_msg.allow_partial_device_match,
      )

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
          test_resource_proto1.password, test_resource_msg1.password
      )
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
                      service_pb2.Option(
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
      self.assertEqual(
          request_proto.test_environment.tradefed_options,
          [
              service_pb2.Option(name='online-wait-time', value=['300001']),
              service_pb2.Option(
                  name='bugreport-on-invocation-ended', value=['true']
              ),
          ],
      )

      # Verify previous test context
      self.assertEqual(
          request_proto.prev_test_context.test_resource.__len__(),
          new_request_msg.prev_test_context.test_resources.__len__(),
      )
      self.assertEqual(
          request_proto.prev_test_context.test_resource.__len__(),
          1,
      )
      for test_resource_proto, test_resource_msg in zip(
          request_proto.prev_test_context.test_resource,
          new_request_msg.prev_test_context.test_resources,
      ):
        self.assertEqual(test_resource_proto.url, test_resource_msg.url)
        self.assertEqual(test_resource_proto.name, test_resource_msg.name)
        self.assertEqual(
            test_resource_proto.password, test_resource_msg.password
        )


class MockGrpcError(grpc.RpcError):
  """A mock grpc.RpcError for testing."""

  def __init__(self, code, details='Mock error details'):
    self._code = code
    self._details = details

  def code(self):
    return self._code

  def details(self):
    return self._details

  def __str__(self):
    return self._details


def _create_get_session_response(session_id, finished=False):
  """Helper to create GetSessionResponse."""
  response = session_service_pb2.GetSessionResponse()
  response.session_detail.session_status = (
      session_pb2.SessionStatus.SESSION_FINISHED
      if finished
      else session_pb2.SessionStatus.SESSION_RUNNING
  )
  request_detail = service_pb2.RequestDetail(id=session_id)
  response.session_detail.session_output.session_plugin_output[
      olcs_session_stub.SESSION_PLUGIN_LABEL
  ].output.Pack(request_detail)
  return response


class OlcsSessionStubPollingTest(absltest.TestCase):
  """Tests for OlcsSessionStub polling logic."""

  def setUp(self):
    super().setUp()
    self.mock_sleep = self.enter_context(
        mock.patch('time.sleep', return_value=None)
    )
    self.mock_random = self.enter_context(
        mock.patch('random.random', return_value=0.5)
    )
    self.mock_client = mock.MagicMock(
        spec=olcs_session_client.OlcsSessionClient
    )
    self.stub = olcs_session_stub.OlcsSessionStub(self.mock_client)
    self.request_id = 'sub_req_id_123'
    self.callback_queue = queue.Queue()

  def tearDown(self):
    # Stop any running subscriptions
    for sub_id in list(olcs_session_stub._active_subscriptions.keys()):
      self.stub.StopSubscribeSession(sub_id)
    time.sleep(0.1)  # Give threads time to stop
    super().tearDown()

  def _subscriber_callback(self, response):
    self.callback_queue.put(response)

  def _wait_for_thread_to_finish(self, subscribe_id, timeout=5):
    """Wait until subscribe_id is removed from queues or timeout."""
    start_time = time.time()
    while time.time() - start_time < timeout:
      if subscribe_id not in olcs_session_stub._active_subscriptions:
        return True
      time.sleep(0.01)
    return False

  def test_polling_until_finished(self):
    """Test polling calls get_session until session is finished."""
    self.mock_client.get_session.side_effect = [
        _create_get_session_response(self.request_id, finished=False),
        _create_get_session_response(self.request_id, finished=False),
        _create_get_session_response(self.request_id, finished=True),
    ]

    subscribe_id = self.stub.StartSubscribeSession(
        self.request_id, self._subscriber_callback
    )

    self.assertTrue(
        self._wait_for_thread_to_finish(subscribe_id),
        'Subscription thread did not terminate.',
    )
    # 3 get_session calls -> 3 callbacks
    self.assertEqual(3, self.callback_queue.qsize())
    # 2 sleeps between 3 calls
    polling_sleep_calls = [
        c for c in self.mock_sleep.call_args_list if c[0][0] > 1
    ]
    self.assertLen(polling_sleep_calls, 2)
    self.assertEqual(3, self.mock_client.get_session.call_count)
    self.mock_client.subscribe_session.assert_not_called()

  def test_stop_terminates_polling(self):
    """Test StopSubscribeSession terminates polling."""
    self.mock_client.get_session.return_value = _create_get_session_response(
        self.request_id, finished=False
    )
    # block thread in sleep until we stop it
    block_sleep = threading.Event()
    sleep_called = threading.Event()

    def _sleep_and_block(t):
      if t > 1:
        sleep_called.set()
        block_sleep.wait()

    self.mock_sleep.side_effect = _sleep_and_block

    subscribe_id = self.stub.StartSubscribeSession(
        self.request_id, self._subscriber_callback
    )
    self.assertTrue(sleep_called.wait(5), 'Polling thread did not call sleep.')
    self.stub.StopSubscribeSession(subscribe_id)
    block_sleep.set()

    self.assertTrue(
        self._wait_for_thread_to_finish(subscribe_id),
        'Subscription thread did not terminate.',
    )
    self.assertEqual(1, self.callback_queue.qsize())
    polling_sleep_calls = [
        c for c in self.mock_sleep.call_args_list if c[0][0] > 1
    ]
    self.assertLen(polling_sleep_calls, 1)
    self.mock_client.get_session.assert_called_once()
    self.assertNotIn(subscribe_id, olcs_session_stub._active_subscriptions)

  def test_polling_with_exception(self):
    """Test polling retries after get_session exception."""
    self.mock_client.get_session.side_effect = [
        MockGrpcError(grpc.StatusCode.UNAVAILABLE),
        _create_get_session_response(self.request_id, finished=True),
    ]

    subscribe_id = self.stub.StartSubscribeSession(
        self.request_id, self._subscriber_callback
    )

    self.assertTrue(
        self._wait_for_thread_to_finish(subscribe_id),
        'Subscription thread did not terminate.',
    )
    # 1 exception, 1 success -> 1 callback
    self.assertEqual(1, self.callback_queue.qsize())
    # 1 sleep after exception, 0 sleeps after finished=True
    polling_sleep_calls = [
        c for c in self.mock_sleep.call_args_list if c[0][0] > 1
    ]
    self.assertLen(polling_sleep_calls, 1)
    self.assertEqual(2, self.mock_client.get_session.call_count)
    self.mock_client.subscribe_session.assert_not_called()


if __name__ == '__main__':
  absltest.main()
