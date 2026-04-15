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
from multitest_transport.models import ndb_models
from tradefed_cluster import api_messages


class EmailFormatter:
  """Helper class to format email details."""

  @classmethod
  def FormatTestRunAttemptEvent(
      cls,
      test_run_id: str,
      attempt: api_messages.CommandAttemptMessage,
      event_type: ndb_models.NotificationEvent,
      test_run=None,
  ) -> tuple[str, str]:
    """Formats the email subject and body for a test run attempt event.

    Args:
      test_run_id: The ID of the test run.
      attempt: The command attempt message from TFC.
      event_type: The notification event type.
      test_run: The TestRun NDB model object.

    Returns:
      A tuple containing (subject, body).
    """
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

    test_name = 'N/A'
    run_command = 'N/A'
    build_id = 'N/A'
    run_target = 'N/A'
    build_number = 'N/A'
    fullname = 'N/A'
    version = 'N/A'

    if test_run:
      if test_run.test:
        test_name = test_run.test.name
      if test_run.test_run_config:
        run_command = test_run.test_run_config.command

      if test_run.test_devices:
        first_device = test_run.test_devices[0]
        build_id = first_device.build_id or 'N/A'
        run_target = first_device.run_target or 'N/A'

      if test_run.test_package_info:
        build_number = test_run.test_package_info.build_number or 'N/A'
        fullname = test_run.test_package_info.fullname or 'N/A'
        version = test_run.test_package_info.version or 'N/A'

    if event_type == ndb_models.NotificationEvent.TEST_RUN_FINISHED:
      subject = 'Test Run %s: %s %s' % (
          attempt.state,
          test_name,
          run_command,
      )
      body_intro = 'Test run finished with state <b>%s</b>.' % attempt.state
    else:
      subject = 'Test Run Attempt %s: %s %s' % (
          attempt.state,
          test_name,
          run_command,
      )
      body_intro = (
          'Test run attempt finished with state <b>%s</b>.' % attempt.state
      )

    run_info = [
        '<h3>Run info</h3>',
        '<b>Test Run ID</b>: %s<br>' % test_run_id,
    ]
    if event_type == ndb_models.NotificationEvent.TEST_RUN_ATTEMPT_FINISHED:
      run_info.append(
          '<b>Attempt ID</b> (ATS Request ID/OLC Session ID): %s<br>'
          % attempt.request_id
      )
    run_info.extend([
        '<b>Results</b>: <a href="%s">%s</a><br>' % (results_url, results_url),
        '<b>State</b>: %s<br>%s' % (attempt.state, error_details),
    ])

    body = (
        '<div style="font-family: Arial, sans-serif; color: #333;">'
        '%s'
        '<hr style="border: 0; height: 1px; background: #ccc; margin: 15px 0;">'
        '<h3>Test Info</h3>'
        '<b>Name</b>: %s<br>'
        '<b>Run Command</b>: <code>%s</code><br>'
        '<hr style="border: 0; height: 1px; background: #ccc; margin: 15px 0;">'
        '<h3>Device Info</h3>'
        '<b>Build ID</b>: %s<br>'
        '<b>Run Target</b>: %s<br>'
        '<hr style="border: 0; height: 1px; background: #ccc; margin: 15px 0;">'
        '<h3>Test Package Info</h3>'
        '<b>Full Name</b>: %s<br>'
        '<b>Version</b>: %s<br>'
        '<b>Build Number</b>: %s<br>'
        '<hr style="border: 0; height: 1px; background: #ccc; margin: 15px 0;">'
        '%s'
        '</div>'
    ) % (
        body_intro,
        test_name,
        run_command,
        build_id,
        run_target,
        fullname,
        version,
        build_number,
        ''.join(run_info),
    )

    return subject, body
