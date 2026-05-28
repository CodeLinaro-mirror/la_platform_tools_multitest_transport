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

"""A plugin for RabbitMQ."""
import base64
import datetime
import json
import logging
import os
from typing import Union
import uuid

import pika


from tradefed_cluster.plugins import base

DEFAULT_EXCHANGE = ''


def _ToEpochMillis(dt):
  """Converts a datetime.datetime object to epoch millis.

  Args:
    dt: a datetime.datetime object.

  Returns:
    Epoch millis.
  """
  if dt.tzinfo:
    # Convert dt to be timezone-naive.
    dt = dt.astimezone(datetime.timezone.utc).replace(tzinfo=None)
  return int((dt - datetime.datetime(1970, 1, 1)).total_seconds() * 1000)


def _EncodeTaskPayload(payload: Union[bytes, str]) -> str:
  """Encodes a task payload.

  Args:
    payload: a payload string.
  Returns:
    a base64 encoded payload string.
  """
  payload = payload if isinstance(payload, bytes) else payload.encode()
  return base64.b64encode(payload).decode()


class TaskScheduler(base.TaskScheduler):
  """A RabbitMQ task scheduler."""

  def AddTask(self, queue_name, payload, target, task_name, eta):
    """Add a task to RabbitMQ.

    Args:
      queue_name: a queue name.
      payload: a task payload.
      target: a target module name.
      task_name: a task name.
      eta: a ETA for task execution.
    Returns:
      A base.Task object.
    """
    logging.getLogger('pika').setLevel(logging.WARNING)
    rabbitmq_host = os.environ.get('RABBITMQ_HOST', 'localhost')
    parameters = pika.ConnectionParameters(host=rabbitmq_host)
    with pika.BlockingConnection(parameters) as conn:
      channel = conn.channel()
      headers = {}
      if eta:
        headers['x-eta-millis'] = _ToEpochMillis(eta)
      if not task_name:
        task_name = str(uuid.uuid4())
      body = {'name': task_name, 'payload': _EncodeTaskPayload(payload)}
      # TODO: check task name conflicts.
      channel.basic_publish(
          exchange=DEFAULT_EXCHANGE,
          routing_key=queue_name,
          body=json.dumps(body),
          properties=pika.BasicProperties(
              content_type='application/json', headers=headers))
      return base.Task(name=task_name, payload=payload, eta=eta)

  def DeleteTask(self, queue_name, task_name):
    logging.warning(
        'DeleteTask is not supported by RabbitMQ; ignoring: '
        'queue_name=%s, task_name=%s', queue_name, task_name)
