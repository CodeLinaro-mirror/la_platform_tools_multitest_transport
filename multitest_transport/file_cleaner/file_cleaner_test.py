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
"""Tests for multitest_transport.file_cleaner.file_cleaner.py."""
import os
from absl.testing import absltest
from absl.testing import flagsaver
from pyfakefs import fake_filesystem_unittest
import requests
import requests_mock


from multitest_transport.file_cleaner import file_cleaner
from multitest_transport.util import env


class FileCleanerTest(fake_filesystem_unittest.TestCase):
  """Tests FileCleaner functionality."""

  def setUp(self):
    super(FileCleanerTest, self).setUp()
    self.setUpPyfakefs()
    env.STORAGE_PATH = '/test'

  @requests_mock.mock()
  def testCleanUp_loadSettingsFromControlServer(self, mock_requests):
    """Tests file cleaner can get policies and configs and clean up dirs."""
    self.fs.create_dir('/test/dir1')
    self.fs.create_dir('/test/dir2')
    self.fs.create_file('/test/dir1/file')
    self.fs.create_file('/test/dir2/file')
    config = b"""{
        "policies": [{
            "name": "policy name",
            "target": "FILE",
            "operation": {
                "type": "DELETE"
            }
        }],
        "configs": [{
            "name": "config name",
            "directories": ["/test/dir1", "/test/dir2"],
            "policy_names": ["policy name"]
        }]
    }
    """
    mock_requests.get(
        'http://localhost:8000/_ah/api/mtt/v1/file_cleaner/settings',
        content=config)

    file_cleaner.CleanUp()

    self.assertTrue(os.path.exists('/test/dir1'))
    self.assertTrue(os.path.exists('/test/dir2'))
    self.assertFalse(os.path.exists('/test/dir1/file'))
    self.assertFalse(os.path.exists('/test/dir2/file'))

  @flagsaver.flagsaver(control_server_url='dialer:8000')
  @requests_mock.mock()
  def testCleanUp_withoutSchemeInControlServerUrl(self, mock_requests):
    self.fs.create_dir('/test/dir1')
    self.fs.create_file('/test/dir1/file')
    config = b"""{
        "policies": [{
            "name": "policy name",
            "target": "FILE",
            "operation": {
                "type": "DELETE"
            }
        }],
        "configs": [{
            "name": "config name",
            "directories": ["/test/dir1"],
            "policy_names": ["policy name"]
        }]
    }
    """
    mock_requests.get(
        'http://dialer:8000/_ah/api/mtt/v1/file_cleaner/settings',
        content=config,
    )

    file_cleaner.CleanUp()

    self.assertTrue(os.path.exists('/test/dir1'))
    self.assertFalse(os.path.exists('/test/dir1/file'))

  @flagsaver.flagsaver(control_server_url='')
  def testLoadSettings_emptyControlServerUrl(self):
    with self.assertRaisesRegex(
        requests.exceptions.MissingSchema,
        '/_ah/api/mtt/v1/file_cleaner/settings',
    ):
      file_cleaner.LoadSettings()


if __name__ == '__main__':
  absltest.main()
