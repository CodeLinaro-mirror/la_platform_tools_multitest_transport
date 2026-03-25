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

"""Email notification utility."""

from email.mime import text
import logging
import smtplib

_SMTP_SERVER = 'smtp.gmail.com'
_SMTP_PORT = 587


def SendEmail(
    sender_address,
    sender_password,
    receiver_addresses,
    subject,
    body,
):
  """Sends an email using SMTP.

  Args:
    sender_address: the sender's email address.
    sender_password: the sender's email password.
    receiver_addresses: a list of receiver email addresses.
    subject: the email subject.
    body: the email body.
  """
  if not sender_address or not sender_password or not receiver_addresses:
    return

  msg = text.MIMEText(body, 'html')
  msg['Subject'] = subject
  msg['From'] = sender_address
  msg['To'] = ', '.join(receiver_addresses)

  try:
    with smtplib.SMTP(_SMTP_SERVER, _SMTP_PORT) as server:
      server.starttls()
      server.login(sender_address, sender_password)
      server.send_message(msg)
    logging.info(
        'Email notification successfully sent to %s', receiver_addresses
    )
  except smtplib.SMTPException as e:
    logging.error('Failed to send email notification: %s', e)
