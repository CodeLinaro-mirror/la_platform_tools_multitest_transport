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
"""Unit tests for rabbitmq_plugin module."""

import base64
import datetime
import json
from unittest import mock

from absl.testing import absltest
import pika


from multitest_transport.app_helper import rabbitmq_plugin


class TaskSchedulerTest(absltest.TestCase):
  """"RabbitMQ task scheduler tests."""

  def setUp(self):
    super(TaskSchedulerTest, self).setUp()
    self.task_scheduler = rabbitmq_plugin.TaskScheduler()

  def testToEpochMillis(self):
    dt = datetime.datetime(1970, 1, 1)
    self.assertEqual(0, rabbitmq_plugin._ToEpochMillis(dt))
    self.assertEqual(
        86400000,
        rabbitmq_plugin._ToEpochMillis(dt + datetime.timedelta(days=1)))

  def testToEpochMillis_withTimezone(self):
    dt = datetime.datetime(1970, 1, 2).replace(tzinfo=datetime.timezone.utc)
    self.assertEqual(86400000, rabbitmq_plugin._ToEpochMillis(dt))

  def testEncodeTaskPayload(self):
    data = rabbitmq_plugin._EncodeTaskPayload(b'payload')
    payload = base64.b64decode(data)
    self.assertEqual(b'payload', payload)

  @mock.patch.object(pika, 'BlockingConnection')
  def testAddTask(self, mock_conn_ctor):
    mock_conn = mock.MagicMock()
    mock_conn_ctor().__enter__.return_value = mock_conn
    mock_channel = mock.MagicMock()
    mock_conn.channel.return_value = mock_channel

    task = self.task_scheduler.AddTask(
        queue_name='queue_name',
        payload='payload',
        target='target',
        task_name='task_name',
        eta=None)

    mock_channel.basic_publish.assert_called_once_with(
        exchange=rabbitmq_plugin.DEFAULT_EXCHANGE,
        routing_key='queue_name',
        body=json.dumps({
            'name': 'task_name',
            'payload': rabbitmq_plugin._EncodeTaskPayload('payload')
        }),
        properties=pika.BasicProperties(
            content_type='application/json', headers={}))
    self.assertEqual('task_name', task.name)

  @mock.patch.object(pika, 'BlockingConnection')
  def testAddTask_withoutTaskName(self, mock_conn_ctor):
    mock_conn = mock.MagicMock()
    mock_conn_ctor().__enter__.return_value = mock_conn
    mock_channel = mock.MagicMock()
    mock_conn.channel.return_value = mock_channel

    task = self.task_scheduler.AddTask(
        queue_name='queue_name',
        payload='payload',
        target='target',
        task_name=None,
        eta=None)

    self.assertIsNotNone(task.name)
    mock_channel.basic_publish.assert_called_once_with(
        exchange=rabbitmq_plugin.DEFAULT_EXCHANGE,
        routing_key='queue_name',
        body=json.dumps({
            'name': task.name,
            'payload': rabbitmq_plugin._EncodeTaskPayload('payload')
        }),
        properties=pika.BasicProperties(
            content_type='application/json', headers={}))

  @mock.patch.object(pika, 'BlockingConnection', autospec=True)
  def testAddTask_withETA(self, mock_conn_ctor):
    mock_conn = mock.MagicMock(autospec=True)
    mock_conn_ctor().__enter__.return_value = mock_conn
    mock_channel = mock.MagicMock(autospec=True)
    mock_conn.channel.return_value = mock_channel
    eta = datetime.datetime.utcnow() + datetime.timedelta(days=1)
    epoch = datetime.datetime(1970, 1, 1)
    eta_millis = int((eta - epoch).total_seconds() * 1000)

    task = self.task_scheduler.AddTask(
        queue_name='queue_name',
        payload='payload',
        target='target',
        task_name='task_name',
        eta=eta)

    mock_channel.basic_publish.assert_called_once_with(
        exchange=rabbitmq_plugin.DEFAULT_EXCHANGE,
        routing_key='queue_name',
        body=json.dumps({
            'name': 'task_name',
            'payload': rabbitmq_plugin._EncodeTaskPayload('payload')
        }),
        properties=pika.BasicProperties(
            content_type='application/json',
            headers={'x-eta-millis': eta_millis}))
    self.assertEqual('task_name', task.name)


if __name__ == '__main__':
  absltest.main()
