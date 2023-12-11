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

import os
from unittest import mock

from absl.testing import absltest
from multitest_transport.util import olcs_session_client
from multitest_transport.util import olcs_session_stub
from protorpc import protojson
from tradefed_cluster import api_messages

from com_google_deviceinfra.src.devtools.mobileharness.infra.ats.server.proto import service_pb2
from com_google_deviceinfra.src.devtools.mobileharness.infra.client.longrunningservice.proto import session_service_pb2

TEST_DATA_DIR = os.path.join(os.path.dirname(__file__), 'test_data')


class OlcsSessionStubTest(absltest.TestCase):

  def setUp(self):
    super().setUp()
    mock_stub = mock.create_autospec(session_service_pb2.SessionServiceStub)
    self.stubby_client = olcs_session_client.OlcsSessionClient(mock_stub)
    self.session_stub = olcs_session_stub.OlcsSessionStub(self.stubby_client)

  def testCreateNewRequest(self):
    client_response = session_service_pb2.CreateSessionResponse()
    client_response.session_id.id = 'test_session_id'
    self.stubby_client._stub.CreateSession.return_value = client_response

    # Create input to the session service stub.
    request_message = api_messages.NewMultiCommandRequestMessage()
    request_message.user = 'test_user'

    # Create the expected request proto sent to session service.
    request_proto = session_service_pb2.CreateSessionRequest()
    request_proto.session_config.session_plugin_configs.session_plugin_config.add().execution_config.config.Pack(
        service_pb2.NewMultiCommandRequest(user_id=request_message.user)
    )
    request_proto.session_config.session_plugin_configs.session_plugin_config[
        0
    ].explicit_label.label = olcs_session_stub.SESSION_PLUGIN_LABEL
    request_proto.session_config.session_plugin_configs.session_plugin_config[
        0
    ].loading_config.plugin_class_name = (
        olcs_session_stub.SESSION_PLUGIN_CLASS_NAME
    )

    stub_response = self.session_stub.create_new_request(request_message)

    # Assert session service received the expected request proto.
    self.stubby_client._stub.CreateSession.assert_called_once_with(
        request_proto
    )
    # Assert service response.
    self.assertEqual(stub_response, client_response.session_id.id)

  def test_generate_request_proto(self):
    with open(
        os.path.join(TEST_DATA_DIR, 'test_new_request_msg.json'), 'rb'
    ) as f:
      new_request_msg = protojson.decode_message(
          api_messages.NewMultiCommandRequestMessage, f.read()
      )
      create_session_request = (
          olcs_session_stub.OlcsSessionStub.generate_request_proto(
              new_request_msg
          )
      )
      request_proto = service_pb2.NewMultiCommandRequest()
      create_session_request.session_config.session_plugin_configs.session_plugin_config[
          0
      ].execution_config.config.Unpack(
          request_proto
      )
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


if __name__ == '__main__':
  absltest.main()
