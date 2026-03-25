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

import smtplib
from unittest import mock

from absl.testing import absltest
from multitest_transport.util import mailer


class MailerTest(absltest.TestCase):

  @mock.patch.object(smtplib, 'SMTP')
  def testSendEmail(self, mock_smtp):
    mock_server = mock.MagicMock()
    mock_smtp.return_value.__enter__.return_value = mock_server

    mailer.SendEmail(
        'sender@test.com',
        'pwd',
        ['recv1@test.com', 'recv2@test.com'],
        'Subject',
        'Body',
    )

    mock_smtp.assert_called_once_with('smtp.gmail.com', 587)
    mock_server.starttls.assert_called_once()
    mock_server.login.assert_called_once_with('sender@test.com', 'pwd')
    mock_server.send_message.assert_called_once()

    # Verify message contents
    msg = mock_server.send_message.call_args[0][0]
    self.assertEqual(msg['Subject'], 'Subject')
    self.assertEqual(msg['From'], 'sender@test.com')
    self.assertEqual(msg['To'], 'recv1@test.com, recv2@test.com')
    self.assertEqual(msg.get_payload(), 'Body')

  @mock.patch.object(smtplib, 'SMTP')
  def testSendEmail_html(self, mock_smtp):
    mock_server = mock.MagicMock()
    mock_smtp.return_value.__enter__.return_value = mock_server

    mailer.SendEmail(
        'sender@test.com',
        'pwd',
        ['recv1@test.com'],
        'Subject',
        '<b>Body</b>',
    )

    mock_server.send_message.assert_called_once()
    msg = mock_server.send_message.call_args[0][0]
    self.assertEqual(msg.get_content_type(), 'text/html')
    self.assertEqual(msg.get_payload(), '<b>Body</b>')

  @mock.patch.object(smtplib, 'SMTP')
  def testSendEmail_missingConfig(self, mock_smtp):
    mailer.SendEmail('', 'pwd', ['recv@test.com'], 'Subject', 'Body')
    mailer.SendEmail(
        'sender@test.com', '', ['recv@test.com'], 'Subject', 'Body'
    )
    mailer.SendEmail('sender@test.com', 'pwd', [], 'Subject', 'Body')

    mock_smtp.assert_not_called()

  @mock.patch.object(smtplib, 'SMTP')
  def testSendEmail_exception(self, mock_smtp):
    mock_server = mock.MagicMock()
    mock_smtp.return_value.__enter__.return_value = mock_server
    mock_server.send_message.side_effect = smtplib.SMTPException('SMTP Error')

    # Should catch the exception and log instead of crashing
    mailer.SendEmail(
        'sender@test.com',
        'password',
        ['recv@test.com'],
        'Test Subject',
        'Test Body',
    )
    mock_server.send_message.assert_called_once()


if __name__ == '__main__':
  absltest.main()
