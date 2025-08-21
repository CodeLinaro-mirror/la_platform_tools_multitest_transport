# Copyright 2019 Google LLC
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

"""Tests for cli_util."""
import os
import tempfile
from unittest import mock
import zipfile

from absl.testing import absltest
from absl.testing import parameterized
import six


from multitest_transport.cli import cli_util
from multitest_transport.cli import version  


class CliUtilTest(absltest.TestCase):

  @mock.patch('__main__.version.VERSION', 'aversion')
  @mock.patch('__main__.version.BUILD_ENVIRONMENT', 'test')
  def testGetVersion(self):
    self.assertEqual(('aversion', 'test'), cli_util.GetVersion())

  def testCreateLogger(self):
    try:
      f = tempfile.NamedTemporaryFile()
      arg_parser = cli_util. CreateLoggingArgParser()
      args = arg_parser.parse_args(['-v', '--log_file', f.name])
      logger = cli_util.CreateLogger(args)
      self.assertIsNotNone(logger)
    finally:
      f.close()

  @mock.patch.object(zipfile, 'is_zipfile')
  @mock.patch.object(os, 'access')
  @mock.patch.object(cli_util, '_DownloadToolFromHttp')
  def testCheckAndUpdateTool(self, mock_download, mock_access, mock_is_zip):
    mock_access.return_value = True
    mock_is_zip.return_value = True
    local_path = '/local/path/file.par'
    remote_path = 'http://googlestorage.com/remote/path/file.par'
    mock_download.return_value = local_path
    new_path = cli_util.CheckAndUpdateTool(local_path, remote_path)
    self.assertEqual(local_path, new_path)

    mock_is_zip.assert_called_once_with(local_path)
    mock_access.assert_called_once_with('/local/path', os.W_OK)
    mock_download.assert_called_once_with(remote_path, local_path)

  @mock.patch.object(zipfile, 'is_zipfile')
  @mock.patch.object(os, 'access')
  @mock.patch.object(cli_util, '_DownloadToolFromGCS')
  def testCheckAndUpdateTool_withGCSUrl(
      self, mock_download, mock_access, mock_is_zip):
    mock_access.return_value = True
    mock_is_zip.return_value = True
    local_path = '/local/path/file.par'
    remote_path = 'gs://bucket/remote/path/file.par'
    mock_download.return_value = local_path
    new_path = cli_util.CheckAndUpdateTool(local_path, remote_path)
    self.assertEqual(local_path, new_path)

    mock_is_zip.assert_called_once_with(local_path)
    mock_access.assert_called_once_with('/local/path', os.W_OK)
    mock_download.assert_called_once_with(remote_path, local_path)

  @mock.patch.object(zipfile, 'is_zipfile')
  @mock.patch.object(os, 'access')
  @mock.patch.object(cli_util, '_DownloadToolFromHttp')
  @mock.patch.object(cli_util, 'GetVersion')
  def testCheckAndUpdateTool_remoteNotSet(
      self, mock_get_version, mock_download, mock_access, mock_is_zip):
    local_path = '/local/path/mtt'
    mock_access.return_value = True
    mock_is_zip.return_value = True
    mock_download.return_value = local_path
    mock_get_version.return_value = ('aversion', 'prod')

    new_path = cli_util.CheckAndUpdateTool(local_path)
    self.assertEqual(local_path, new_path)

    mock_get_version.assert_called_once_with()
    mock_is_zip.assert_called_once_with(local_path)
    mock_access.assert_called_once_with('/local/path', os.W_OK)
    mock_download.assert_called_once_with(
        'https://storage.googleapis.com/android-mtt.appspot.com/prod/mtt',
        local_path)

  @mock.patch.object(zipfile, 'is_zipfile')
  @mock.patch.object(cli_util, 'GetVersion')
  def testCheckAndUpdateTool_devEnvironment(
      self, mock_get_version, mock_is_zip):
    mock_is_zip.return_value = True
    mock_get_version.return_value = ('dev', 'dev')

    new_path = cli_util.CheckAndUpdateTool('/local/path/mtt')
    self.assertIsNone(new_path)

    mock_is_zip.assert_called_once_with('/local/path/mtt')
    mock_get_version.assert_called_once_with()

  @mock.patch.object(zipfile, 'is_zipfile')
  def testCheckAndUpdateTool_remoteDifferentName(self, mock_is_zip):
    mock_is_zip.return_value = True
    new_path = cli_util.CheckAndUpdateTool(
        '/local/path/file.par', 'gs://bucket/remote/path/new_file.par')
    self.assertIsNone(new_path)
    mock_is_zip.assert_called_once_with('/local/path/file.par')

  @mock.patch.object(zipfile, 'is_zipfile')
  @mock.patch.object(os, 'access')
  def testCheckAndUpdateTool_noWriteAccess(self, mock_access, mock_is_zip):
    mock_is_zip.return_value = True
    mock_access.return_value = False

    new_path = cli_util.CheckAndUpdateTool(
        '/local/path/file.par', 'gs://bucket/remote/path/file.par')
    self.assertIsNone(new_path)

    mock_is_zip.assert_called_once_with('/local/path/file.par')
    mock_access.assert_called_once_with('/local/path', os.W_OK)

  @mock.patch.object(zipfile, 'is_zipfile')
  def testCheckAndUpdateTool_notZip(self, mock_is_zip):
    mock_is_zip.return_value = False

    new_path = cli_util.CheckAndUpdateTool(
        '/local/path/file.par', 'gs://bucket/remote/path/file.par')
    self.assertIsNone(new_path)

    mock_is_zip.assert_called_once_with('/local/path/file.par')

  @mock.patch.object(os, 'rename')
  @mock.patch.object(os, 'chmod')
  @mock.patch.object(os, 'chown')
  @mock.patch.object(os, 'stat')
  @mock.patch.object(cli_util.gcs_file_util, 'CalculateMd5Hash')
  @mock.patch.object(cli_util.gcs_file_util, 'CreateBackupFilePath')
  @mock.patch.object(cli_util.requests, 'head')
  @mock.patch.object(cli_util.requests, 'get')
  @mock.patch.object(cli_util, '_WriteResponseToFile')
  def testDownloadToolFromHttp(
      self,
      mock_write,
      mock_get,
      mock_head,
      mock_create_backup_path,
      mock_md5hash,
      mock_stat,
      mock_chown,
      mock_chmod,
      mock_rename,
  ):
    mock_head.return_value = mock.MagicMock(
        headers={'x-goog-hash': 'crc32c=crc32chash, md5=md5hash'})
    mock_stat.return_value = mock.MagicMock(
        st_mode=0o775, st_uid=123, st_gid=456
    )
    mock_response = mock.MagicMock()
    mock_get.return_value = mock_response
    mock_create_backup_path.return_value = '/path/to/backup.par'
    mock_md5hash.return_value = six.ensure_text('new_md5hash')

    new_path = cli_util._DownloadToolFromHttp(
        'http://googlestorage.com/remote/path/file.par', '/local/path/file.par')
    self.assertEqual('/local/path/file.par', new_path)

    mock_create_backup_path.assert_called_once_with('/local/path/file.par')
    mock_rename('/local/path/file.par', '/path/to/backup.par')
    mock_write.assert_called_once_with(mock_response, '/local/path/file.par')
    mock_chown.assert_called_once_with('/local/path/file.par', 123, 456)
    mock_chmod.assert_called_once_with('/local/path/file.par', 0o775)

  @mock.patch.object(cli_util.requests, 'head')
  def testDownloadToolFromHttp_remoteNotExist(self, mock_head):
    mock_head.side_effect = cli_util.requests.ConnectionError('File not exist.')
    new_path = cli_util._DownloadToolFromHttp(
        'http://googlestorage.com/remote/path/file.par', '/local/path/file.par')
    self.assertIsNone(new_path)

  @mock.patch.object(cli_util.gcs_file_util, 'CalculateMd5Hash')
  @mock.patch.object(cli_util.requests, 'head')
  def testDownloadToolFromHttp_sameMd5Hash(self, mock_head, mock_md5hash):
    mock_head.return_value = mock.MagicMock(
        headers={'x-goog-hash': 'crc32c=crc32chash, md5=md5hash'})
    mock_md5hash.return_value = six.ensure_text('md5hash')

    new_path = cli_util._DownloadToolFromHttp(
        'http://googlestorage.com/remote/path/file.par', '/local/path/file.par')
    self.assertIsNone(new_path)

  @mock.patch.object(os, 'rename')
  @mock.patch.object(os, 'chmod')
  @mock.patch.object(os, 'chown')
  @mock.patch.object(os, 'stat')
  @mock.patch.object(cli_util.gcs_file_util, 'CreateBackupFilePath')
  @mock.patch.object(cli_util.gcs_file_util, 'CalculateMd5Hash')
  @mock.patch.object(cli_util.gcs_file_util, 'CreateGCSClient')
  @mock.patch.object(cli_util.gcs_file_util, 'GetGCSBlob')
  @mock.patch.object(cli_util.google_auth_util, 'GetGCloudCredential')
  def testDownloadToolFromGCS(
      self, create_cred, mock_get_blob, mock_create_gcs_client, mock_md5hash,
      mock_create_backup_path, mock_stat, mock_chown, mock_chmod, mock_rename):
    cred = mock.MagicMock()
    create_cred.return_value = cred
    mock_client = mock.MagicMock()
    mock_create_gcs_client.return_value = mock_client
    mock_blob = mock.MagicMock(md5_hash='new_md5hash')
    mock_get_blob.return_value = mock_blob
    mock_create_backup_path.return_value = '/path/to/backup.par'
    mock_md5hash.return_value = six.ensure_text('md5hash')
    mock_stat.return_value = mock.MagicMock(
        st_mode=0o711, st_uid=123, st_gid=456
    )

    new_path = cli_util._DownloadToolFromGCS(
        'gs://bucket/remote/path/file.par', '/local/path/file.par')
    self.assertEqual('/local/path/file.par', new_path)

    self.assertTrue(create_cred.called)
    mock_create_gcs_client.assert_called_once_with('android-mtt', cred)
    mock_get_blob.assert_called_once_with(
        mock_client, 'gs://bucket/remote/path/file.par')
    mock_create_backup_path.assert_called_once_with('/local/path/file.par')
    mock_rename('/local/path/file.par', '/path/to/backup.par')
    mock_blob.download_to_filename.assert_called_once_with(
        '/local/path/file.par')
    mock_chmod.assert_called_once_with('/local/path/file.par', 0o771)
    mock_chown.assert_called_once_with('/local/path/file.par', 123, 456)

  @mock.patch.object(cli_util.gcs_file_util, 'CreateGCSClient')
  @mock.patch.object(cli_util.gcs_file_util, 'GetGCSBlob')
  @mock.patch.object(cli_util.google_auth_util, 'GetGCloudCredential')
  def testDownloadToolFromGCS_remoteNotExist(
      self, create_cred, mock_get_blob, mock_create_gcs_client):
    cred = mock.MagicMock()
    create_cred.return_value = cred
    mock_client = mock.MagicMock()
    mock_create_gcs_client.return_value = mock_client
    mock_get_blob.side_effect = cli_util.gcs_file_util.GCSError('No file.par')

    new_path = cli_util._DownloadToolFromGCS(
        'gs://bucket/remote/not/exist/path/file.par', '/local/path/file.par')
    self.assertIsNone(new_path)
    mock_get_blob.assert_called_once_with(
        mock_client, 'gs://bucket/remote/not/exist/path/file.par')

  @mock.patch.object(cli_util.gcs_file_util, 'CalculateMd5Hash')
  @mock.patch.object(cli_util.gcs_file_util, 'CreateGCSClient')
  @mock.patch.object(cli_util.gcs_file_util, 'GetGCSBlob')
  @mock.patch.object(cli_util.google_auth_util, 'GetGCloudCredential')
  def testDownloadToolFromGCS_sameMd5Hash(
      self, create_cred, mock_get_blob, mock_create_gcs_client, mock_md5hash):
    cred = mock.MagicMock()
    create_cred.return_value = cred
    mock_client = mock.MagicMock()
    mock_create_gcs_client.return_value = mock_client
    mock_blob = mock.MagicMock(md5_hash='md5hash')
    mock_get_blob.return_value = mock_blob
    mock_md5hash.return_value = six.ensure_text('md5hash')

    new_path = cli_util._DownloadToolFromGCS(
        'gs://bucket/remote/path/file.par', '/local/path/file.par')
    self.assertIsNone(new_path)
    mock_get_blob.assert_called_once_with(
        mock_client, 'gs://bucket/remote/path/file.par')


class ArgumentParserTest(parameterized.TestCase):

  @parameterized.parameters(
      ([], False),
      (['--parallel'], True),
      (['--parallel', '8'], 8),
      )
  def testParseParallelExecuteOption(self, cmd_args, expected_val):
    arg_parser = cli_util.CreateMultiHostCommandArgParser()
    args = arg_parser.parse_args(cmd_args)
    self.assertEqual(expected_val, args.parallel)


if __name__ == '__main__':
  absltest.main()
