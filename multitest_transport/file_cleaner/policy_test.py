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
"""Tests for multitest_transport.file_cleaner.policy.py."""
import os
from unittest import mock

from absl.testing import absltest
from multitest_transport.file_cleaner import policy
from multitest_transport.models import messages
from multitest_transport.models import ndb_models
from multitest_transport.util import env
from multitest_transport.util import file_util
from pyfakefs import fake_filesystem_unittest


class PolicyTest(fake_filesystem_unittest.TestCase, absltest.TestCase):
  """Tests Policy functionality."""

  def setUp(self):
    super(PolicyTest, self).setUp()
    self.setUpPyfakefs()

    # After Python 3.12, we cannot mock shutil.os to use MockGFile because
    # shutil's methods assert that operations are performed with the base os
    # module.
    self.enter_context(
        mock.patch.object(
            file_util.shutil,
            'rmtree',
            side_effect=self.fs.remove_object,
        )
    )
    env.STORAGE_PATH = '/test'

  def testPolicy_file(self):
    """Tests policy for files."""
    self.fs.create_dir('/test/path/dir')
    self.fs.create_file('/test/path/dir/file1.zip')
    self.fs.create_file('/test/path/dir/file2')
    self.fs.create_file('/test/path/dir/output.zip')
    self.fs.create_file('/test/path/file.zip')

    policy.Policy(
        messages.FileCleanerPolicy(
            name='name',
            target=ndb_models.FileCleanerTargetType.FILE,
            operation=messages.FileCleanerOperation(
                type=ndb_models.FileCleanerOperationType.DELETE),
            criteria=[
                messages.FileCleanerCriterion(
                    type=ndb_models.FileCleanerCriterionType.NAME_MATCH,
                    params=[
                        messages.NameValuePair(name='pattern', value='zip')
                    ]),
                messages.FileCleanerCriterion(
                    type=ndb_models.FileCleanerCriterionType.NAME_MATCH,
                    params=[
                        messages.NameValuePair(name='pattern', value='file')
                    ])
            ])).Apply('/test/path')

    self.assertTrue(os.path.exists('/test/path/dir'))
    self.assertFalse(os.path.exists('/test/path/dir/file1.zip'))
    self.assertTrue(os.path.exists('/test/path/dir/file2'))
    self.assertTrue(os.path.exists('/test/path/dir/output.zip'))
    self.assertFalse(os.path.exists('/test/path/file.zip'))

  def testPolicy_dir(self):
    """Tests policy for directories."""
    self.fs.create_dir('/test/path/dir_match_1')
    self.fs.create_dir('/test/path/dir_match_1/subdir')
    self.fs.create_dir('/test/path/dir_2')
    self.fs.create_dir('/test/path/dir_2/subdir_match')
    self.fs.create_file('/test/path/file_match')

    policy.Policy(
        messages.FileCleanerPolicy(
            name='name',
            target=ndb_models.FileCleanerTargetType.DIRECTORY,
            operation=messages.FileCleanerOperation(
                type=ndb_models.FileCleanerOperationType.ARCHIVE),
            criteria=[
                messages.FileCleanerCriterion(
                    type=ndb_models.FileCleanerCriterionType.NAME_MATCH,
                    params=[
                        messages.NameValuePair(name='pattern', value='match')
                    ])
            ])).Apply('/test/path')

    self.assertFalse(os.path.exists('/test/path/dir_match_1'))
    self.assertFalse(os.path.exists('/test/path/dir_match_1/subdir'))
    self.assertTrue(os.path.exists('/test/path/dir_match_1.zip'))
    self.assertTrue(os.path.exists('/test/path/dir_2'))
    self.assertTrue(os.path.exists('/test/path/dir_2/subdir_match'))
    self.assertTrue(os.path.exists('/test/path/file_match'))

  def testPolicy_noCriteria(self):
    """Tests policy without criteria."""
    self.fs.create_dir('/test/path/dir')
    self.fs.create_file('/test/path/dir/file1.zip')
    self.fs.create_file('/test/path/dir/file2')
    self.fs.create_file('/test/path/dir/output.zip')
    self.fs.create_file('/test/path/file.zip')

    policy.Policy(
        messages.FileCleanerPolicy(
            name='name',
            target=ndb_models.FileCleanerTargetType.FILE,
            operation=messages.FileCleanerOperation(
                type=ndb_models.FileCleanerOperationType.DELETE))).Apply(
                    '/test/path')

    self.assertFalse(os.path.exists('/test/path/dir/file1.zip'))
    self.assertFalse(os.path.exists('/test/path/dir/file2'))
    self.assertFalse(os.path.exists('/test/path/dir/output.zip'))
    self.assertFalse(os.path.exists('/test/path/file.zip'))


if __name__ == '__main__':
  absltest.main()
