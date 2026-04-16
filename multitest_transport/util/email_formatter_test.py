# Copyright 2026 Google LLC
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

"""Tests for email formatter utility."""

import os
from unittest import mock
from absl.testing import absltest
from multitest_transport.models import ndb_models
from multitest_transport.util import email_formatter
from tradefed_cluster import api_messages


class EmailFormatterTest(absltest.TestCase):

  def test_format_test_run_attempt_event_success(self):
    attempt = api_messages.CommandAttemptMessage(
        attempt_id='attempt_123',
        request_id='request_123',
        state=api_messages.CommandState.COMPLETED,
    )
    with mock.patch.dict(os.environ, {'DEFAULT_VERSION_HOSTNAME': 'test_host'}):
      subject, body = email_formatter.EmailFormatter.FormatTestRunAttemptEvent(
          'test_run_123',
          attempt,
          event_type=ndb_models.NotificationEvent.TEST_RUN_ATTEMPT_FINISHED,
      )

    self.assertEqual(subject, 'Test Run Attempt COMPLETED: N/A_N/A_N/A_N/A')
    self.assertIn('test_run_123', body)
    self.assertIn('request_123', body)
    self.assertIn('COMPLETED', body)
    self.assertIn('http://test_host/test_runs/test_run_123', body)
    self.assertNotIn('Error Reason', body)

  def test_format_test_run_attempt_event_error(self):
    attempt = api_messages.CommandAttemptMessage(
        attempt_id='attempt_123',
        request_id='request_123',
        state=api_messages.CommandState.ERROR,
        error_reason='N/A',
        error='invalid argument',
    )
    with mock.patch.dict(os.environ, {'DEFAULT_VERSION_HOSTNAME': 'test_host'}):
      subject, body = email_formatter.EmailFormatter.FormatTestRunAttemptEvent(
          'test_run_123',
          attempt,
          event_type=ndb_models.NotificationEvent.TEST_RUN_ATTEMPT_FINISHED,
      )

    self.assertEqual(subject, 'Test Run Attempt ERROR: N/A_N/A_N/A_N/A')
    self.assertIn('ERROR', body)
    self.assertIn('Error Reason</b>: N/A', body)
    self.assertIn('Error Detail</b>: invalid argument', body)

  def test_format_test_run_attempt_event_with_test_run(self):
    attempt = api_messages.CommandAttemptMessage(
        attempt_id='attempt_123',
        request_id='request_123',
        state=api_messages.CommandState.COMPLETED,
    )

    mock_test = mock.Mock()
    mock_test.name = 'CTS 16.0 (ARM)'

    mock_config = mock.Mock()
    mock_config.command = 'cts -m CtsUsbTests'

    mock_device = mock.Mock()
    mock_device.build_id = 'bp3a.250905.014'
    mock_device.run_target = 'oriole'

    mock_package_info = mock.Mock()
    mock_package_info.build_number = '14604821'
    mock_package_info.fullname = 'Compatibility Test Suite'
    mock_package_info.version = '16_r4'

    mock_test_run = mock.Mock()
    mock_test_run.test = mock_test
    mock_test_run.test_run_config = mock_config
    mock_test_run.test_devices = [mock_device]
    mock_test_run.test_package_info = mock_package_info

    with mock.patch.dict(os.environ, {'DEFAULT_VERSION_HOSTNAME': 'test_host'}):
      subject, body = email_formatter.EmailFormatter.FormatTestRunAttemptEvent(
          'test_run_123',
          attempt,
          event_type=ndb_models.NotificationEvent.TEST_RUN_ATTEMPT_FINISHED,
          test_run=mock_test_run,
      )

    self.assertEqual(
        subject,
        'Test Run Attempt COMPLETED: CTS 16.0 (ARM)_oriole_bp3a.250905.014_cts'
        ' -m CtsUsbTests',
    )
    self.assertIn('CTS 16.0 (ARM)', body)
    self.assertIn('cts -m CtsUsbTests', body)
    self.assertIn('bp3a.250905.014', body)
    self.assertIn('oriole', body)
    self.assertIn('14604821', body)
    self.assertIn('Compatibility Test Suite', body)
    self.assertIn('16_r4', body)

  def test_format_test_run_finished_event(self):
    attempt = api_messages.CommandAttemptMessage(
        attempt_id='attempt_123',
        request_id='request_123',
        state=api_messages.CommandState.COMPLETED,
    )
    with mock.patch.dict(os.environ, {'DEFAULT_VERSION_HOSTNAME': 'test_host'}):
      subject, body = email_formatter.EmailFormatter.FormatTestRunAttemptEvent(
          'test_run_123',
          attempt,
          event_type=ndb_models.NotificationEvent.TEST_RUN_FINISHED,
      )

    self.assertEqual(subject, 'Test Run COMPLETED: N/A_N/A_N/A_N/A')
    self.assertIn('Test run finished with state', body)
    self.assertNotIn('request_123', body)


if __name__ == '__main__':
  absltest.main()
