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

"""A core service checker.

A module to check availability of the core services.
"""
import logging
import os
import subprocess
import requests


from multitest_transport.models import sql_models
from multitest_transport.util import analytics
from multitest_transport.util import file_util
from tradefed_cluster.util import ndb_shim as ndb


class ServiceChecker(object):
  """A service checker."""
  pass


class DatastoreChecker(ServiceChecker):
  """Cloud Datastore availability checker."""
  name = 'Cloud Datastore'
  label = 'cloud_datastore'

  @classmethod
  def Run(cls):
    """Check Datastore availability."""
    ndb.Key('Kind', 1).get()


class RabbitMQChecker(ServiceChecker):
  """RabbitMQ availability checker."""
  name = 'RabbitMQ'
  label = 'rabbitmq'

  @classmethod
  def Run(cls):
    """Check RabbitMQ service availability using its management plugin."""
    rabbitmq_host = os.environ.get('RABBITMQ_HOST', 'localhost')
    response = requests.get(f'http://{rabbitmq_host}:15672/api/vhosts',
                            auth=requests.auth.HTTPBasicAuth('guest', 'guest'))
    response.raise_for_status()


class FileServerChecker(ServiceChecker):
  """Local file server availability checker."""
  name = 'File Server'
  label = 'file_server'

  @classmethod
  def Run(cls):
    """Check local file server availability."""
    files = file_util.RemoteFileHandle('file:///').ListFiles()
    if files is None:
      raise RuntimeError('File server root directory not found')


class FileCleanerChecker(ServiceChecker):
  """File Cleaner availability checker."""
  name = 'File Cleaner'
  label = 'file_cleaner'

  @classmethod
  def Run(cls):
    """Check file cleaner availability."""
    proc = subprocess.Popen(['ps', '-ef'],
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            text=True)
    out, _ = proc.communicate()
    if 'multitest_transport.file_cleaner' not in out:
      raise RuntimeError('File Cleaner not active')


class SQLDatabaseChecker(ServiceChecker):
  """SQL Database availability checker."""
  name = 'SQL Database'
  label = 'sql_database'

  @classmethod
  def Run(cls):
    """Check sql database availability."""
    if not sql_models.db.engine:
      raise RuntimeError('SQL Database not found')


def Check():
  """Check availability of dependent services."""
  checkers = [DatastoreChecker,
              FileServerChecker,
              FileCleanerChecker,
              RabbitMQChecker,
              SQLDatabaseChecker]

  logging.info('Checking availability of dependent services...')
  for checker in checkers:
    try:
      checker.Run()
      logging.info('\t%s: OK', checker.name)
    except Exception:  
      logging.exception('\t%s: ERROR', checker.name)
      analytics.Log(
          analytics.SYSTEM_CATEGORY,
          analytics.CRASH_ACTION,
          label=checker.label)
