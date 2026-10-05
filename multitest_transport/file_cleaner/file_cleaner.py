# Copyright 2021 Google LLC
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
# limitations under the License
"""File cleaner.

YAML example:

  file_cleaner:
    policies:
    - name: Archive directories not modified
      target: DIRECTORY
      operation:
        type: ARCHIVE
      criteria:
        type: LAST_MODIFIED_TIME
        params:
        - name: ttl
          value: 7 days
    - ...

    configs:
    - name: name  # required
      description: '...'  # optional
      directories: # required
      - '/data/app_default_bucket/test_runs'
      - '/.../...'
      policy_names:
      - Archive directories not modified
      - ...
"""
import logging
import time
from absl import app
from absl import flags
from protorpc import protojson
import requests


from multitest_transport.file_cleaner import policy
from multitest_transport.models import messages

FLAGS = flags.FLAGS
flags.DEFINE_string('control_server_url', 'http://localhost:8000',
                    'Control server url for workers in ON_PREMISE mode.')

FILE_CLEANER_SETTINGS_API_FORMAT = '{}/_ah/api/mtt/v1/file_cleaner/settings'
FILE_CLEANER_INTERVAL = 60 * 60  # 1 hour


def LoadSettings() -> messages.FileCleanerSettings:
  """Loads file cleaner settings from control server.

  Returns:
    messages.FileCleanerSettings
  """
  url = FILE_CLEANER_SETTINGS_API_FORMAT.format(FLAGS.control_server_url)
  response = requests.get(url)
  return protojson.decode_message(
      messages.FileCleanerSettings, response.content)


def CleanUp():
  """Applies policies to directories."""
  settings = LoadSettings()

  policies = {}
  for obj in settings.policies:
    policies[obj.name] = policy.Policy(obj)

  for config in settings.configs:
    try:
      for directory in config.directories:
        for policy_name in config.policy_names:
          logging.info('[File Cleaner] Applying %s to %s', policy_name,
                       directory)
          policies[policy_name].Apply(directory)
    except Exception:  
      logging.exception('[File Cleaner] Config %s failed:', config.name)


def main(_):
  while True:
    try:
      CleanUp()
    except Exception:  
      logging.exception('[File Cleaner] Failed when cleaning up:')
    time.sleep(FILE_CLEANER_INTERVAL)


if __name__ == '__main__':
  logging.getLogger().setLevel(logging.INFO)
  app.run(main)
