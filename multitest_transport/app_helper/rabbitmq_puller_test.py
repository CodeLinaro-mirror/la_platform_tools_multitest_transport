# Copyright 2020 Google LLC
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

"""Unit tests for rabbitmq_puller."""
import base64
import datetime
import json
from unittest import mock
import urllib.error
import urllib.request

from absl.testing import absltest
import pika


from multitest_transport.app_helper import rabbitmq_puller


class MessagePullerTest(absltest.TestCase):
  """"Tests MessagePuller class."""

  def setUp(self):
    super(MessagePullerTest, self).setUp()
    patcher = mock.patch.object(pika, 'BlockingConnection')
    self.conn_params = pika.ConnectionParameters()
    self.mock_conn_ctor = patcher.start()
    self.addCleanup(patcher.stop)
    self.mock_conn = mock.MagicMock()
    self.mock_conn_ctor().__enter__.return_value = self.mock_conn
    self.mock_channel = mock.MagicMock()
    self.mock_conn.channel.return_value = self.mock_channel

  def testRun(self):
    message_puller = rabbitmq_puller.MessagePuller(
        self.conn_params, 'queue', 'target_url')

    message_puller.run()

    self.mock_conn_ctor.assert_called_with(self.conn_params)
    self.mock_channel.assert_has_calls([
        mock.call.queue_declare(queue='queue', durable=True),
        mock.call.queue_purge(queue='queue'),
        mock.call.basic_consume('queue', mock.ANY, auto_ack=True),
        mock.call.start_consuming(),
        mock.call.stop_consuming(),
    ])

  @mock.patch.object(urllib.request, 'urlopen', autospec=True)
  @mock.patch.object(urllib.request, 'Request', autospec=True)
  def testOnMessage(self, mock_request_ctor, mock_urlopen):
    message_puller = rabbitmq_puller.MessagePuller(
        self.conn_params, 'queue', 'target_url')
    method = mock.MagicMock(pika.spec.Basic.Deliver, autospec=True)
    method.delivery_tag = 1234
    properties = pika.spec.BasicProperties(headers={})
    body = json.dumps({
        'name': 'name',
        'payload': base64.b64encode('payload'.encode('ascii')).decode('ascii')
    })

    message_puller.on_message(self.mock_conn, self.mock_channel, method,
                              properties, body)

    mock_request_ctor.assert_called_with(
        url='target_url',
        headers={
            'X-AppEngine-TaskName': 'name',
            'X-AppEngine-TaskRetryCount': 0
        },
        data='payload'.encode('ascii'))
    mock_urlopen.assert_called_with(
        mock_request_ctor.return_value,
        timeout=rabbitmq_puller.INVOKE_TIMEOUT_SECONDS)

  @mock.patch.object(urllib.request, 'urlopen', autospec=True)
  @mock.patch.object(urllib.request, 'Request', autospec=True)
  def testOnMessage_withDynamicTargetUrl(self, mock_request_ctor, mock_urlopen):
    message_puller = rabbitmq_puller.MessagePuller(
        self.conn_params, 'queue', 'target_url/{queue}')
    method = mock.MagicMock(pika.spec.Basic.Deliver, autospec=True)
    method.delivery_tag = 1234
    properties = pika.spec.BasicProperties(headers={})
    body = json.dumps({
        'name': 'name',
        'payload': base64.b64encode('payload'.encode('ascii')).decode('ascii')
    })

    message_puller.on_message(self.mock_conn, self.mock_channel, method,
                              properties, body)

    mock_request_ctor.assert_called_with(
        url='target_url/queue',
        headers={
            'X-AppEngine-TaskName': 'name',
            'X-AppEngine-TaskRetryCount': 0
        },
        data='payload'.encode('ascii'))
    mock_urlopen.assert_called_with(
        mock_request_ctor.return_value,
        timeout=rabbitmq_puller.INVOKE_TIMEOUT_SECONDS)

  @mock.patch.object(urllib.request, 'urlopen', autospec=True)
  @mock.patch.object(urllib.request, 'Request', autospec=True)
  @mock.patch.object(rabbitmq_puller.MessagePuller, 'delay_message')
  @mock.patch.object(datetime, 'datetime', wraps=datetime.datetime)
  def testOnMessage_messageWithETA(self, mock_datetime, mock_delay_message,
                                   mock_request_ctor, mock_urlopen):
    epoch = datetime.datetime(1970, 1, 1)
    now = datetime.datetime(2020, 9, 1)
    mock_datetime.utcnow = mock.MagicMock(return_value=now)
    eta = now + datetime.timedelta(seconds=1234)
    message_puller = rabbitmq_puller.MessagePuller(
        self.conn_params, 'queue', 'target_url')
    method = mock.MagicMock(pika.spec.Basic.Deliver, autospec=True)
    method.delivery_tag = 4321
    properties = pika.spec.BasicProperties(
        headers={
            # ETA in epoch millis
            'x-eta-millis': str(int((eta - epoch).total_seconds() * 1000))
        })
    body = json.dumps({
        'name': 'name',
        'payload': base64.b64encode('payload'.encode('ascii')).decode('ascii')
    })

    message_puller.on_message(self.mock_conn, self.mock_channel, method,
                              properties, body)

    mock_delay_message.assert_called_with(self.mock_conn, self.mock_channel,
                                          properties, body, 1234)
    mock_request_ctor.assert_not_called()
    mock_urlopen.assert_not_called()

  @mock.patch.object(rabbitmq_puller.MessagePuller, 'delay_message')
  @mock.patch.object(urllib.request, 'urlopen', autospec=True)
  @mock.patch.object(urllib.request, 'Request', autospec=True)
  def testOnMessage_onError(self, mock_request_ctor, mock_urlopen,
                            mock_delay_message):
    message_puller = rabbitmq_puller.MessagePuller(
        self.conn_params, 'queue', 'target_url')
    method = mock.MagicMock(pika.spec.Basic.Deliver, autospec=True)
    method.delivery_tag = 1234
    properties = pika.spec.BasicProperties(headers={})
    body = json.dumps({
        'name': 'name',
        'payload': base64.b64encode('payload'.encode('ascii')).decode('ascii')
    })
    mock_urlopen.side_effect = urllib.error.URLError('reason')

    message_puller.on_message(self.mock_conn, self.mock_channel, method,
                              properties, body)

    mock_request_ctor.assert_called_with(
        url='target_url',
        headers={
            'X-AppEngine-TaskName': 'name',
            'X-AppEngine-TaskRetryCount': 0
        },
        data='payload'.encode('ascii'))
    mock_urlopen.assert_called_with(
        mock_request_ctor.return_value,
        timeout=rabbitmq_puller.INVOKE_TIMEOUT_SECONDS)
    mock_delay_message.assert_called_with(self.mock_conn, self.mock_channel,
                                          properties, body,
                                          rabbitmq_puller.MIN_BACKOFF_SECONDS)

  def testDelayMessage(self):
    message_puller = rabbitmq_puller.MessagePuller(
        self.conn_params, 'queue', 'target_url')
    properties = pika.spec.BasicProperties(headers={})
    body = json.dumps({
        'name': 'name',
        'payload': base64.b64encode('payload'.encode('ascii')).decode('ascii')
    })

    message_puller._delay_message(self.mock_channel, properties, body, 1234)

    self.mock_channel.queue_declare.assert_called_with(
        queue='queue.1234000',
        durable=True,
        arguments={
            'x-dead-letter-exchange': rabbitmq_puller.DEFAULT_EXCHANGE,
            'x-dead-letter-routing-key': 'queue',
            'x-expires': (
                1234000 + rabbitmq_puller.DELAY_QUEUE_TTL_SECONDS * 1000),
        })
    self.mock_channel.queue_bind.assert_called_with(
        queue='queue.1234000', exchange=rabbitmq_puller.DELAY_EXCHANGE)
    self.mock_channel.basic_publish.assert_called_with(
        exchange=rabbitmq_puller.DELAY_EXCHANGE,
        routing_key='queue.1234000',
        body=body,
        properties=properties)


if __name__ == '__main__':
  absltest.main()
