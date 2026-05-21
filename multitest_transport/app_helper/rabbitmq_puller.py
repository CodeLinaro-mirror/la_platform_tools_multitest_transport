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
"""A message puller for a RabbitMQ.

This pulls messages from RabbitMQ and pushes them to HTTP endpoints
according to queue.yaml configuration. If a HTTP request is unsuccessful,
a push will be retried as configured in queue.yaml.

This app is intended to emulate Cloud Task push in off-cloud environments.
"""

import base64
from concurrent import futures
import datetime
import functools
import json
import logging
import socket
import threading
import time
import urllib.error
import urllib.request

from absl import app
from absl import flags
import pika
import yaml

FLAGS = flags.FLAGS

flags.DEFINE_integer('rabbitmq_node_port', None, 'RabbitMQ node port')
flags.DEFINE_multi_string(
    'target', [], 'A target endpoint URL.'
    'e.g. default=http://localhost:8000/_ah/queue/{queue}')

DEFAULT_EXCHANGE = ''
DELAY_EXCHANGE = 'delay'
DELAY_QUEUE = 'delay-queue'
MIN_BACKOFF_SECONDS = 1
MAX_RETRY_COUNT = 8
DELAY_QUEUE_TTL_SECONDS = 5
RECONNECT_DELAY_SECONDS = 5
DEFAULT_MESSAGE_PULLERS_PER_QUEUE = 1
MAX_MESSAGE_PULLERS_PER_QUEUE = 5
INVOKE_TIMEOUT_SECONDS = 1 * 60 * 60  # Keep this consitent with GAE.


class MessagePuller(threading.Thread):
  """A message puller thread."""

  def __init__(self, conn_params, queue, target_url):
    """Constructor.

    Args:
      conn_params: a pika.ConnectionParameters object.
      queue: a queue name.
      target_url: a target URL.
    """
    super(MessagePuller, self).__init__()
    self.daemon = True
    self._conn_params = conn_params
    self._queue = queue
    if '{queue}' in target_url:
      self._target_url = target_url.format(queue=self._queue)
    else:
      self._target_url = target_url
    self._logger = logging.getLogger(__name__)

  def run(self):
    """A thread main function."""
    self._logger = logging.getLogger(__name__ + '[id=%s]' % self.ident)
    while True:
      try:
        self._logger.info('Connecting to RabbitMQ server...')
        with pika.BlockingConnection(self._conn_params) as connection, \
            futures.ThreadPoolExecutor(max_workers=1) as executor:
          channel = connection.channel()
          channel.queue_declare(queue=self._queue, durable=True)
          channel.queue_purge(queue=self._queue)
          # Handle messages in a worker thread to prevent blocking the puller
          # thread (which could cause a heartbeat timeout)
          on_message_callback = functools.partial(executor.submit,
                                                  self.on_message, connection)
          channel.basic_consume(self._queue, on_message_callback, auto_ack=True)
          self._logger.info('Start consuming from queue %s', self._queue)
          channel.start_consuming()
          self._logger.info('Stopping consuming from queue %s', self._queue)
          channel.stop_consuming()
          break
      except (pika.exceptions.AMQPChannelError,
              pika.exceptions.AMQPConnectionError):
        self._logger.exception('Connection lost, retrying after %s seconds:',
                               RECONNECT_DELAY_SECONDS)
        time.sleep(RECONNECT_DELAY_SECONDS)
      except Exception:  
        self._logger.exception('Unexpected error:')
        break
    self._logger.info('MessagePuller[queue=%s] is stopped.', self._queue)

  def on_message(self, connection, channel, method, properties, body):
    """Parses message and delegates it to the right queue URL.

    Args:
      connection: a pika.Connection
      channel: a pika.Channel
      method: a pika.spec.Basic.Deliver
      properties: a pika.spec.BasicProperties.
      body: a message body (bytes)
    """
    self._logger.debug(
        '[%s] Processing a message %s', self._queue, method.delivery_tag)
    message_headers = properties.headers

    # Check ETA
    now = datetime.datetime.utcnow()
    eta = properties.headers.get('x-eta-millis')
    if eta:
      eta = datetime.datetime.utcfromtimestamp(int(eta) / 1000.)
    if eta and now < eta:
      self.delay_message(connection, channel, properties, body,
                         (eta - now).total_seconds())
      return

    retry_count = message_headers.get('x-retry-count', 0)
    try:
      data = json.loads(body)
      task_name = data['name']
      payload = base64.b64decode(data['payload'])
      url = self._target_url
      headers = {
          'X-AppEngine-TaskName': task_name,
          'X-AppEngine-TaskRetryCount': retry_count
      }
      self._logger.debug(
          'Invoke %s: headers=%s, payload=(%d bytes)',
          url, headers, len(payload))
      req = urllib.request.Request(
          url=url,
          headers=headers,
          data=payload)
      res = urllib.request.urlopen(req, timeout=INVOKE_TIMEOUT_SECONDS)
      self._logger.debug('Response: %s', res.read())
    except (urllib.error.URLError, socket.timeout) as e:
      properties.headers['x-retry-count'] = retry_count + 1
      backoff_seconds = MIN_BACKOFF_SECONDS * (2 ** retry_count)
      if retry_count < MAX_RETRY_COUNT:
        self._logger.error(
            'Failed to process message %s (attempt %d): e=%s',
            method.delivery_tag, retry_count, e)
        self._logger.error(
            'Retrying message %d after %d seconds...',
            method.delivery_tag, backoff_seconds)
        self.delay_message(
            connection, channel, properties, body, backoff_seconds)
      else:
        self._logger.error(
            'Completely failed to process message %s (attempt %d): e=%s',
            method.delivery_tag, retry_count, e)

  def delay_message(self, connection, channel, properties, body, delay_seconds):
    """Delays a message by delay_seconds in the puller thread.

    Args:
      connection: a pika.Connection
      channel: a pika.Channel
      properties: a pika.spec.BasicProperties
      body: a message body (bytes)
      delay_seconds: a delay in seconds
    """
    callback = functools.partial(self._delay_message, channel, properties, body,
                                 delay_seconds)
    connection.add_callback_threadsafe(callback)

  def _delay_message(self, channel, properties, body, delay_seconds):
    """Delays a message by delay_seconds."""
    message_ttl = int(delay_seconds * 1000)
    properties.expiration = str(message_ttl)
    # Since RabbitMQ expiration happen in order, we need to dynamically create
    # a delay queue for each TTL.
    delay_queue = '.'.join([self._queue, properties.expiration])
    channel.queue_declare(
        queue=delay_queue,
        durable=True,
        # RabbmitMQ DLX arguments documentation can be found at the link below:
        # https://www.rabbitmq.com/dlx.html.
        arguments={
            'x-dead-letter-exchange': DEFAULT_EXCHANGE,
            'x-dead-letter-routing-key': self._queue,
            # The messages of expired queues are not dead-lettered, so the queue
            # TTL (reset for each declaration) must be more than the message TTL
            # to ensure the queue is deleted after the last message has expired.
            'x-expires': (DELAY_QUEUE_TTL_SECONDS * 1000) + message_ttl,
        })
    channel.queue_bind(queue=delay_queue, exchange=DELAY_EXCHANGE)
    channel.basic_publish(
        exchange=DELAY_EXCHANGE,
        routing_key=delay_queue,
        body=body,
        properties=properties)


def main(argv):
  target_to_url_map = {}
  for s in FLAGS.target:
    name, url = s.split('=', 2)
    target_to_url_map[name] = url

  queue_yaml = argv[1]
  with open(queue_yaml) as f:
    queues = yaml.safe_load(f)['queue']

  # Check RabbitMQ availability
  kwargs = {}
  if FLAGS.rabbitmq_node_port:
    kwargs['port'] = FLAGS.rabbitmq_node_port
  conn_params = pika.ConnectionParameters(**kwargs)

  try:
    pika.BlockingConnection(conn_params).close()
  except pika.exceptions.AMQPConnectionError:
    logging.error('RabbitMQ server is not available')
    exit(-1)

  with pika.BlockingConnection(conn_params) as conn:
    channel = conn.channel()
    # Create a delay exchange.
    channel.exchange_declare(exchange=DELAY_EXCHANGE, exchange_type='direct')
    workers = []
    for queue_info in queues:
      target_name = queue_info.get('target', 'default')
      url = target_to_url_map[target_name]
      worker_count = min(
          queue_info.get(
              'max_concurrent_requests', DEFAULT_MESSAGE_PULLERS_PER_QUEUE),
          MAX_MESSAGE_PULLERS_PER_QUEUE)
      for _ in range(worker_count):
        worker = MessagePuller(conn_params, queue_info['name'], url)
        workers.append(worker)
        worker.start()
    for worker in workers:
      worker.join()


if __name__ == '__main__':
  logging.getLogger().setLevel(logging.DEBUG)
  # Set pika logging level to WARNING
  logging.getLogger('pika').setLevel(logging.WARNING)
  app.run(main)
