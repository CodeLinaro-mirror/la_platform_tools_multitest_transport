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
          'test_run_123', attempt
      )

    self.assertEqual(subject, 'Test Run Attempt COMPLETED: test_run_123')
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
          'test_run_123', attempt
      )

    self.assertEqual(subject, 'Test Run Attempt ERROR: test_run_123')
    self.assertIn('ERROR', body)
    self.assertIn('Error Reason</b>: N/A', body)
    self.assertIn('Error Detail</b>: invalid argument', body)


if __name__ == '__main__':
  absltest.main()
