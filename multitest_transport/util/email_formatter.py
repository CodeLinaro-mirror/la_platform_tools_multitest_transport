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

"""Email formatter utility."""

import os
from tradefed_cluster import api_messages


class EmailFormatter:
  """Helper class to format email details."""

  @classmethod
  def FormatTestRunAttemptEvent(
      cls, test_run_id: str, attempt: api_messages.CommandAttemptMessage
  ) -> tuple[str, str]:
    """Formats the email subject and body for a test run attempt event.

    Args:
      test_run_id: The ID of the test run.
      attempt: The command attempt message from TFC.

    Returns:
      A tuple containing (subject, body).
    """
    subject = 'Test Run Attempt %s: %s' % (attempt.state, test_run_id)
    hostname = os.environ.get('DEFAULT_VERSION_HOSTNAME', 'localhost')
    results_url = 'http://%s/test_runs/%s' % (hostname, test_run_id)

    error_details = ''
    if getattr(attempt, 'error', None) or getattr(
        attempt, 'error_reason', None
    ):
      error_details = (
          '<b>Error Reason</b>: %s<br><b>Error Detail</b>: %s<br>'
          % (
              attempt.error_reason or 'N/A',
              attempt.error or 'N/A',
          )
      )

    body = (
        'Test run attempt finished.<br><br>'
        '<b>Test Run ID</b>: %s<br>'
        '<b>Attempt ID</b> (ATS Request ID/OLC Session ID): %s<br>'
        '<b>Results</b>: <a href="%s">%s</a><br>'
        '<b>State</b>: %s<br>%s'
    ) % (
        test_run_id,
        attempt.request_id,
        results_url,
        results_url,
        attempt.state,
        error_details,
    )

    return subject, body
