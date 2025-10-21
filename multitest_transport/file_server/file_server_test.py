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

"""Android Test Station local file server tests."""
import datetime
import io
import json
import os
import shutil
import tarfile
import tempfile
from unittest import mock

from absl.testing import absltest
from tradefed_cluster.util import ndb_test_lib
import werkzeug

from google3.pyglib import resources


from multitest_transport.file_server import file_server
from multitest_transport.models import ndb_models


class PatchedDateTime(datetime.datetime):
  pass


class FileServerTest(ndb_test_lib.NdbWithContextTest, absltest.TestCase):
  """Tests fetching file information and uploading/downloading files."""

  def setUp(self):
    super(FileServerTest, self).setUp()
    self.app = file_server.flask_app
    self.app.root_path = tempfile.mkdtemp()
    self.app.tmp_upload_dir = tempfile.mkdtemp()
    # Create a text file for testing.
    with open(self.app.root_path + '/test.txt', 'wb') as f:
      f.write(b'hello world')
    self.test_file = resources.GetResourceFilenameInDirectoryTree(
        os.path.join(
            'google3/javatests/com/google/devtools/mobileharness/shared/util/cache/persistent/testdata/',
            'random.out',
        )
    )

  def tearDown(self):
    super(FileServerTest, self).tearDown()
    shutil.rmtree(self.app.root_path)

  def testDownloadFile(self):
    """Tests that files can be downloaded."""
    with self.app.test_client() as client:
      response = client.get('/file/test.txt')
      self.assertEqual(200, response.status_code)
      self.assertEqual(b'hello world', response.data)

  def testDownloadFile_asAttachment(self):
    """Tests that files can be downloaded as attachments."""
    with self.app.test_client() as client:
      response = client.get('/file/test.txt?download=true')
      self.assertEqual(200, response.status_code)
      self.assertEqual(b'hello world', response.data)
      self.assertEqual('attachment; filename=test.txt',
                       response.headers.get('Content-Disposition'))

  def testDownloadFile_withRange(self):
    """Tests that a subset of the file can be downloaded."""
    with self.app.test_client() as client:
      response = client.get('/file/test.txt', headers={'Range': 'bytes=3-7'})
      self.assertEqual(206, response.status_code)
      self.assertEqual(b'lo wo', response.data)
      self.assertEqual('bytes 3-7/11', str(response.content_range))

  def testDownloadFile_notFound(self):
    """Tests that file not found errors are handled."""
    with self.app.test_client() as client:
      response = client.get('/file/unknown.txt')
      self.assertEqual(404, response.status_code)
      data = json.loads(response.data)
      self.assertEqual('File \'unknown.txt\' not found', data['message'])

  def testDownloadFile_wrongType(self):
    """Tests that the path to download must be a file."""
    os.mkdir(self.app.root_path + '/foo')
    with self.app.test_client() as client:
      response = client.get('/file/foo')
      self.assertEqual(404, response.status_code)
      data = json.loads(response.data)
      self.assertEqual('File \'foo\' not found', data['message'])

  def testUploadFile_postMethod(self):
    """Tests that new files can be uploaded by post method."""
    with self.app.test_client() as client:
      file = werkzeug.datastructures.FileStorage(
          stream=io.BytesIO(b'test'),
          filename='/file/upload.txt',
          content_type='text/plain',
      )
      response = client.post(
          '/file/upload.txt',
          data=dict(file=file,),
          follow_redirects=True,
          content_type='multipart/form-data',
      )
      self.assertEqual(201, response.status_code)
      self.assertEqual('test', open(self.app.root_path + '/upload.txt').read())

  def testUploadFile_multipleFiles(self):
    """Tests that uploading fails if request has multiple files."""
    with self.app.test_client() as client:
      file = werkzeug.datastructures.FileStorage(
          stream=io.BytesIO(b'test'),
          filename='/file/upload.txt',
          content_type='text/plain',
      )
      response = client.post(
          '/file/upload.txt',
          data=dict(file1=file, file2=file),
          follow_redirects=True,
          content_type='multipart/form-data',
      )
      self.assertEqual(400, response.status_code)

  def testUploadFile_emptyRequest(self):
    """Tests that uploading files fails when request doesn't have a file."""
    with self.app.test_client() as client:
      response = client.post(
          '/file/test.txt',
          follow_redirects=True,
          content_type='multipart/form-data',
      )
      self.assertEqual(400, response.status_code)

  def testUploadFile_overwriteFile(self):
    """Tests that uploaded files can overwrite existing files."""
    with self.app.test_client() as client:
      file = werkzeug.datastructures.FileStorage(
          stream=io.BytesIO(b'test'),
          filename='/file/test.txt',
          content_type='text/plain',
      )
      response = client.post(
          '/file/test.txt',
          data=dict(file=file,),
          follow_redirects=True,
          content_type='multipart/form-data',
      )
      self.assertEqual(201, response.status_code)
      self.assertEqual('test', open(self.app.root_path + '/test.txt').read())

  def testUploadFile_longFilename(self):
    """Tests that a file can be uploaded to a long destination (b/172595968)."""
    with self.app.test_client() as client:
      filename = os.path.join('a' * 100, 'b' * 100, 'c' * 100, 'upload.txt')
      file = werkzeug.datastructures.FileStorage(
          stream=io.BytesIO(b'test'),
          filename='/file/' + filename,
          content_type='text/plain',
      )
      response = client.post(
          '/file/' + filename,
          data=dict(file=file,),
          follow_redirects=True,
          content_type='multipart/form-data',
      )
      response = client.put('/file/' + filename, data='test')
      self.assertEqual(201, response.status_code)
      self.assertEqual('test', open(self.app.root_path + '/' + filename).read())

  def testUploadFileByChunks_putMethod(self):
    """Tests that new files can be uploaded by chunks by put method."""
    with self.app.test_client() as client:
      response = client.put('/file/upload.txt', data='test')
      self.assertEqual(201, response.status_code)
      self.assertEqual('test', open(self.app.root_path + '/upload.txt').read())

  def testUploadFileByChunks_overwriteFile(self):
    """Tests that uploaded files by chunks can overwrite existing files."""
    with self.app.test_client() as client:
      response = client.put('/file/test.txt', data='test')
      self.assertEqual(201, response.status_code)
      self.assertEqual('test', open(self.app.root_path + '/test.txt').read())

  def testUploadFileByChunks_resumeUpload(self):
    """Tests that files can be uploaded progressively."""
    with self.app.test_client() as client:
      # Upload half of a file's content
      response = client.put(
          '/file/upload.txt',
          data='hello ',
          headers={'Content-Range': 'bytes 0-5/11'})
      self.assertEqual(206, response.status_code)
      # File doesn't exist after incomplete upload
      self.assertFalse(os.path.isfile(self.app.root_path + '/upload.txt'))

      # Send remainder of file content
      response = client.put(
          '/file/upload.txt',
          data='world',
          headers={'Content-Range': 'bytes 6-10/11'})
      self.assertEqual(201, response.status_code)
      # File created with the concatenated content
      self.assertEqual('hello world',
                       open(self.app.root_path + '/upload.txt').read())

  def testUploadFileByChunks_restartUpload(self):
    """Tests that a resumable upload can be restarted."""
    with self.app.test_client() as client:
      # Upload half of a file's content
      response = client.put(
          '/file/upload.txt',
          data='hello ',
          headers={'Content-Range': 'bytes 0-5/11'})
      self.assertEqual(206, response.status_code)
      # File doesn't exist after incomplete upload
      self.assertFalse(os.path.isfile(self.app.root_path + '/upload.txt'))

      # Restart the upload from the first byte
      response = client.put(
          '/file/upload.txt',
          data='test',
          headers={'Content-Range': 'bytes 0-3/4'})
      self.assertEqual(201, response.status_code)
      # File created with the new content
      self.assertEqual('test', open(self.app.root_path + '/upload.txt').read())

  def testUploadFileByChunks_invalidOffset(self):
    """Tests that the starting offset is verified during a resumable upload."""
    with self.app.test_client() as client:
      # Upload half of a file's content
      response = client.put(
          '/file/upload.txt',
          data='hello ',
          headers={'Content-Range': 'bytes 0-5/11'})
      self.assertEqual(206, response.status_code)
      self.assertFalse(os.path.isfile(self.app.root_path + '/upload.txt'))

      # Send wrong starting offset which should return an error
      response = client.put(
          '/file/upload.txt',
          data='world',
          headers={'Content-Range': 'bytes 4-8/11'})
      self.assertEqual(400, response.status_code)
      data = json.loads(response.data)
      self.assertEqual('Invalid offset 4 (expected 6)', data['message'])

  def testUploadFileByChunks_longFilename(self):
    """Tests that a file can be uploaded to a long destination (b/172595968)."""
    with self.app.test_client() as client:
      filename = os.path.join('a' * 100, 'b' * 100, 'c' * 100, 'upload.txt')
      response = client.put('/file/' + filename, data='test')
      self.assertEqual(201, response.status_code)
      self.assertEqual('test', open(self.app.root_path + '/' + filename).read())

  def testUploadFileByChunks_pathNotSafe(self):
    """Tests that the path must be safe."""
    with self.app.test_client() as client:
      filename = '../../../../../../../etc/passwd'
      response = client.put('/file/' + filename, data='test')
      self.assertEqual(400, response.status_code)
      self.assertIn(b'Path is not safe', response.data)

  def testDeleteFile(self):
    """Tests that files can be deleted."""
    with self.app.test_client() as client:
      response = client.delete('/file/test.txt')
      self.assertEqual(204, response.status_code)
      self.assertFalse(os.path.isfile(self.app.root_path + '/test.txt'))

  def testDeleteFile_notFound(self):
    """Tests that missing files are ignored when deleting."""
    with self.app.test_client() as client:
      response = client.delete('/file/unknown.txt')
      self.assertEqual(204, response.status_code)

  def test_CalculateSha256(self):
    """Tests that file hash is encoded in base64."""
    sha256 = file_server._CalculateSha256(self.test_file)
    self.assertEqual('++Oexfed9geAS8cc8YkJEtsdpux9n2dVQaDD/+b/h+I=', sha256)

  def testGetFileHash(self):
    """Tests that file hash can be retrieved."""
    with self.app.test_client() as client:
      response = client.get('/hash/test.txt')
      self.assertEqual(200, response.status_code)
      data = json.loads(response.data)
      self.assertEqual(
          'uU0nuZNNPgilLlLX2n2r+sSE7+N6U4DukIj3rOLvzek=',
          data['sha256'],
      )

  def testGetFileHash_notFound(self):
    """Tests that file not found errors are handled when getting hash."""
    with self.app.test_client() as client:
      response = client.get('/hash/unknown.txt')
      self.assertEqual(404, response.status_code)
      data = json.loads(response.data)
      self.assertEqual("File 'unknown.txt' not found", data['message'])

  @mock.patch.object(file_server.datetime, 'datetime', new=PatchedDateTime)
  @mock.patch.object(file_server, '_CalculateSha256')
  def testFileHash_caching(self, mock_calculate_sha256):
    """Tests that the file hash is cached in NDB."""
    PatchedDateTime.utcnow = mock.MagicMock()
    PatchedDateTime.utcnow.return_value = datetime.datetime(2025, 1, 1, 0, 0, 0)
    mock_calculate_sha256.return_value = 'fake_hash'
    test_file_path = os.path.join(self.app.root_path, 'test.txt')

    with self.app.test_client() as client:
      # First request should trigger a calculation and cache the result.
      response1 = client.get('/hash/test.txt')
      self.assertEqual(200, response1.status_code)
      self.assertEqual('fake_hash', json.loads(response1.data)['sha256'])
      mock_calculate_sha256.assert_called_once_with(test_file_path)

      # Verify the metadata was stored in NDB.
      metadata1 = ndb_models.TestResourceMetadata.get_by_id(test_file_path)
      self.assertIsNotNone(metadata1)
      self.assertEqual('fake_hash', metadata1.sha256)
      time1 = metadata1.metadata_access_time

      # Second request within an hour should be served from cache
      # without updating time.
      now1 = time1 + datetime.timedelta(minutes=30)
      PatchedDateTime.utcnow.return_value = datetime.datetime(
          now1.year,
          now1.month,
          now1.day,
          now1.hour,
          now1.minute,
          now1.second,
          now1.microsecond,
      )
      response2 = client.get('/hash/test.txt')
      self.assertEqual(200, response2.status_code)
      self.assertEqual('fake_hash', json.loads(response2.data)['sha256'])
      # Assert that the calculation was NOT run a second time.
      mock_calculate_sha256.assert_called_once()

      metadata2 = ndb_models.TestResourceMetadata.get_by_id(test_file_path)
      self.assertEqual(metadata2.metadata_access_time, time1)

      # Third request after more than an hour should update access time.
      now2 = time1 + datetime.timedelta(minutes=90)
      PatchedDateTime.utcnow.return_value = datetime.datetime(
          now2.year,
          now2.month,
          now2.day,
          now2.hour,
          now2.minute,
          now2.second,
          now2.microsecond,
      )
      response3 = client.get('/hash/test.txt')
      self.assertEqual(200, response3.status_code)
      self.assertEqual('fake_hash', json.loads(response3.data)['sha256'])
      mock_calculate_sha256.assert_called_once()

      # Verify the access time was updated on the cache hit.
      metadata3 = ndb_models.TestResourceMetadata.get_by_id(test_file_path)
      self.assertIsNotNone(metadata3)
      self.assertGreater(metadata3.metadata_access_time, time1)

  def testListDirectory(self):
    """Tests that directory contents can be listed."""
    os.makedirs(self.app.root_path + '/foo/bar')
    with open(self.app.root_path + '/foo/file.txt', 'wb') as f:
      f.write(b'hello world')

    with self.app.test_client() as client:
      response = client.get('/dir/foo')
      self.assertEqual(200, response.status_code)
      # Two nodes found with name, path, size, type, time information.
      self.assertEqual([{
          'access_time': mock.ANY,
          'name': 'bar',
          'path': 'foo/bar',
          'size': mock.ANY,
          'type': 'DIRECTORY',
          'update_time': mock.ANY,
      }, {
          'access_time': mock.ANY,
          'name': 'file.txt',
          'path': 'foo/file.txt',
          'size': 11,
          'type': 'FILE',
          'update_time': mock.ANY,
      }], json.loads(response.data))

  def testListDirectory_tarArchive(self):
    """Tests that directory contents can be downloaded as a tar archive."""
    os.makedirs(self.app.root_path + '/foo/bar')
    with open(self.app.root_path + '/foo/bar/file.txt', 'wb') as f:
      f.write(b'hello world')

    with self.app.test_client() as client:
      response = client.get('/dir/foo?download=true')
      self.assertEqual(200, response.status_code)
      self.assertEqual('attachment; filename=foo.tar.gz',
                       response.headers.get('Content-Disposition'))
      with tarfile.open(fileobj=io.BytesIO(response.data), mode='r') as archive:
        self.assertLen(archive.getmembers(), 2)
        self.assertTrue(archive.getmember('bar').isdir())
        self.assertTrue(archive.getmember('bar/file.txt').isfile())
        self.assertEqual(b'hello world',
                         archive.extractfile('bar/file.txt').read())

  def testListDirectory_notFound(self):
    """Tests that directory not found errors are handled."""
    with self.app.test_client() as client:
      response = client.get('/dir/unknown')
      self.assertEqual(404, response.status_code)
      data = json.loads(response.data)
      self.assertEqual('Directory \'unknown\' not found', data['message'])

  def testListDirectory_wrongType(self):
    """Tests that the path to list must be a directory."""
    with self.app.test_client() as client:
      response = client.get('/dir/test.txt')
      self.assertEqual(404, response.status_code)
      data = json.loads(response.data)
      self.assertEqual('Directory \'test.txt\' not found', data['message'])


if __name__ == '__main__':
  absltest.main()
