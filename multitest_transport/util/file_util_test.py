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

"""Tests for multitest_transport.util.file_util.py."""
import datetime
import io
import json
import os
import shutil
import socket
import tempfile
from unittest import mock
import urllib.error
import urllib.request

from absl.testing import absltest
from absl.testing import parameterized


from multitest_transport.util import env
from multitest_transport.util import file_util

TEST_DATA_DIR = os.path.join(os.path.dirname(__file__), 'test_data')


class MockFileHandle(file_util.FileHandle):
  """File handle backed by a string."""

  def __init__(self, value):
    super(MockFileHandle, self).__init__(value)
    self.value = value

  def Info(self):
    return file_util.FileInfo(
        url=self.url, total_size=len(self.value), content_type='string')

  def Open(self, mode='r'):
    return MockReadStream(self.value)


class MockReadStream(file_util.BaseReadStream):
  """Read stream backed by a string."""

  def __init__(self, value):
    super(MockReadStream, self).__init__(MockFileHandle(value))
    self.value = value

  def ReadBytes(self, offset=0, length=None):
    end_byte = None if length < 0 else offset + length
    return self.value[offset:end_byte]


class BaseReadStreamTest(absltest.TestCase):
  """Tests BaseReadStream functionality."""

  def testFileSeek(self):
    """Tests that file.seek works with absolute values."""
    stream = MockReadStream(b'test')
    stream.seek(2)
    self.assertEqual(2, stream.tell())
    stream.seek(1, os.SEEK_CUR)
    self.assertEqual(3, stream.tell())
    stream.seek(-3, os.SEEK_END)
    self.assertEqual(1, stream.tell())

  def testFileRead(self):
    """Tests that file.read is implemented."""
    stream = MockReadStream(b'test')
    # Read entire content
    self.assertEqual((b'test', 4), (stream.read(), stream.tell()))
    stream.seek(0)
    # Read partial content
    self.assertEqual((b't', 1), (stream.read(1), stream.tell()))
    self.assertEqual((b'es', 3), (stream.read(2), stream.tell()))
    self.assertEqual((b't', 4), (stream.read(), stream.tell()))

  def testFileReadline(self):
    """Tests that file.readline is implemented."""
    stream = MockReadStream(b'hello\nworld')
    # Read entire lines
    self.assertEqual((b'hello\n', 6), (stream.readline(), stream.tell()))
    self.assertEqual((b'world', 11), (stream.readline(), stream.tell()))
    stream.seek(0)
    # Read partial lines
    self.assertEqual((b'h', 1), (stream.readline(1), stream.tell()))

  def testFileReadlines(self):
    """Tests that file.readlines is implemented."""
    stream = MockReadStream(b'hello\nworld')
    # Read entire content split by lines
    self.assertEqual([b'hello\n', b'world'], stream.readlines())
    self.assertEqual([], stream.readlines())
    stream.seek(0)
    # Read partial content split by lines
    self.assertEqual([b'hello\n'], stream.readlines(5))
    self.assertEqual([b'world'], stream.readlines())

  def testFileIterable(self):
    """Tests that file.__iter__ and file.next are implemented."""
    stream = MockReadStream(b'hello\nworld')
    self.assertEqual([b'hello\n', b'world'], list(stream))


class BaseWriteStreamTest(absltest.TestCase):
  """Tests BaseWriteStream functionality."""

  @mock.patch.object(file_util.BaseWriteStream, 'WriteBytes')
  def testFileWrite(self, mock_write_bytes):
    """Tests that file.write is implemented."""
    with file_util.BaseWriteStream(None) as stream:
      stream.write(b'hello\n')
      stream.write(b'world')
    # Progressively wrote content and finished writing on close
    mock_write_bytes.assert_has_calls([
        mock.call(offset=0, data=b'hello\n', finish=False),
        mock.call(offset=6, data=b'world', finish=False),
        mock.call(offset=11)
    ])

  @mock.patch.object(file_util.BaseWriteStream, 'WriteBytes')
  def testFileWritelines(self, mock_write_bytes):
    """Tests that file.writelines is implemented."""
    with file_util.BaseWriteStream(None) as stream:
      stream.writelines([b'hello\n', b'world'])
    # Progressively wrote content and finished writing on close
    mock_write_bytes.assert_has_calls([
        mock.call(offset=0, data=b'hello\n', finish=False),
        mock.call(offset=6, data=b'world', finish=False),
        mock.call(offset=11)
    ])


class FileHandleTest(absltest.TestCase):
  """Tests FileHandle functionality."""

  def setUp(self):
    super(FileHandleTest, self).setUp()
    env.FILE_SERVER_URL = 'http://file_server:1234/'
    env.STORAGE_PATH = '/root'

  def testGet_local(self):
    """Tests that a local file handle can be created."""
    handle = file_util.FileHandle.Get('file:///root/path')
    self.assertIsInstance(handle, file_util.LocalFileHandle)
    self.assertEqual(handle.path, '/root/path')
    # Accepts paths relative to the storage root
    handle = file_util.FileHandle.Get('file:///path')
    self.assertIsInstance(handle, file_util.LocalFileHandle)
    self.assertEqual(handle.path, '/root/path')

  def testGet_remote(self):
    """Tests that a remote file server handle can be created."""
    handle = file_util.FileHandle.Get('file://host/root/path')
    self.assertIsInstance(handle, file_util.RemoteFileHandle)
    self.assertEqual(handle.file_url, 'http://host:1234/file/path')

  def testGet_http(self):
    """Tests that a HTTP file handle can be created."""
    handle = file_util.FileHandle.Get('https://www.google.com')
    self.assertIsInstance(handle, file_util.HttpFileHandle)
    self.assertEqual(handle.url, 'https://www.google.com')


class LocalFileHandleTest(absltest.TestCase):
  """Tests LocalFileHandle functionality."""

  def setUp(self):
    super(LocalFileHandleTest, self).setUp()
    self.tmp_root = tempfile.mkdtemp()
    for test_file in os.listdir(TEST_DATA_DIR):
      shutil.copy(os.path.join(TEST_DATA_DIR, test_file), self.tmp_root)
    env.STORAGE_PATH = self.tmp_root

  def tearDown(self):
    shutil.rmtree(self.tmp_root)
    super(LocalFileHandleTest, self).tearDown()

  def testInfo(self):
    """Tests that file info can be retrieved."""
    file_info = file_util.LocalFileHandle('file:///FILES').Info()
    self.assertIsNotNone(file_info)
    self.assertEqual(file_info.url, 'file://%s/FILES' % self.tmp_root)
    self.assertTrue(file_info.is_file)
    self.assertEqual(file_info.total_size, 36)

  def testInfo_notFound(self):
    """Tests that file not found errors are handled when getting info."""
    handle = file_util.LocalFileHandle('file:///unknown')
    self.assertIsNone(handle.Info())

  def testOpen(self):
    """Tests that file-like objects can be opened."""
    handle = file_util.LocalFileHandle('file:///dir/file')
    with handle.Open(mode='w') as f:
      f.write(b'hello\nworld')
    with handle.Open() as f:
      self.assertEqual(f.read(), b'hello\nworld')

  def testListFiles(self):
    """Tests that nested files can be listed."""
    files = file_util.LocalFileHandle('file:///').ListFiles()
    self.assertLen(files, 5)
    urls = [f.url for f in files]
    self.assertIn('file://%s/FILES' % self.tmp_root, urls)

  def testListFiles_notFound(self):
    """Tests that file not found errors are handled when listing files."""
    self.assertIsNone(file_util.LocalFileHandle('file:///dir').ListFiles())

  def testDelete(self):
    """Tests that local files can be deleted."""
    self.assertTrue(os.path.exists(os.path.join(self.tmp_root, 'FILES')))
    file_util.LocalFileHandle('file:///FILES').Delete()
    self.assertFalse(os.path.exists(os.path.join(self.tmp_root, 'FILES')))

  def testArchive_file(self):
    """Tests that local files can be archived and removed."""
    file_util.LocalFileHandle('file:///FILES').Archive()

    self.assertFalse(os.path.exists(os.path.join(self.tmp_root, 'FILES')))
    self.assertTrue(os.path.exists(os.path.join(self.tmp_root, 'FILES.zip')))

  def testArchive_file_notRemoved(self):
    """Tests that local files can be archived."""
    file_util.LocalFileHandle('file:///FILES').Archive(remove_file=False)

    self.assertTrue(os.path.exists(os.path.join(self.tmp_root, 'FILES')))
    self.assertTrue(os.path.exists(os.path.join(self.tmp_root, 'FILES.zip')))

  def testArchive_dir(self):
    """Tests that local directories can be archived and removed."""
    os.mkdir(os.path.join(self.tmp_root, 'test_dir'))

    file_util.LocalFileHandle('file:///test_dir').Archive()

    self.assertFalse(os.path.exists(os.path.join(self.tmp_root, 'test_dir')))
    self.assertTrue(os.path.exists(os.path.join(self.tmp_root, 'test_dir.zip')))

  def testArchive_dir_notRemoved(self):
    """Tests that local directories can be archived."""
    os.mkdir(os.path.join(self.tmp_root, 'test_dir'))

    file_util.LocalFileHandle('file:///test_dir').Archive(remove_file=False)

    self.assertTrue(os.path.exists(os.path.join(self.tmp_root, 'test_dir')))
    self.assertTrue(os.path.exists(os.path.join(self.tmp_root, 'test_dir.zip')))


class HttpFileHandleTest(absltest.TestCase):
  """Tests HttpFileHandle functionality."""

  MOCK_URL = 'http://url'

  @mock.patch.object(urllib.request, 'urlopen')
  def testInfo(self, mock_urlopen):
    """Tests that file info can be fetched and parsed."""
    mock_file = mock.MagicMock()
    mock_file.info.return_value = {
        'content-length': '123',
        'content-type': 'type',
        'last-modified': 'Fri, 01 Jan 1990 00:00:00 GMT'
    }
    mock_urlopen.return_value = mock_file

    file_info = file_util.HttpFileHandle(self.MOCK_URL).Info()
    self.assertEqual(file_info.total_size, 123)
    self.assertEqual(file_info.content_type, 'type')
    self.assertEqual(file_info.timestamp, datetime.datetime(1990, 1, 1))

  @mock.patch.object(urllib.request, 'urlopen')
  def testInfo_notFound(self, mock_urlopen):
    """Tests that file not found errors are handled when getting info."""
    mock_urlopen.side_effect = urllib.error.HTTPError(None, 404, None, None,
                                                      None)
    self.assertIsNone(file_util.HttpFileHandle(self.MOCK_URL).Info())

  @mock.patch.object(urllib.request, 'urlopen')
  def testReadBytes(self, mock_urlopen):
    """Tests that bytes can be read using HTTP requests."""
    handle = file_util.HttpFileHandle(self.MOCK_URL)
    stream = handle.Open().detach()  # Detach to test underlying stream
    # Fetches full file content
    stream.ReadBytes()
    full_request = mock_urlopen.call_args_list[0][0][0]
    self.assertEqual(self.MOCK_URL, full_request.get_full_url())
    self.assertEqual('bytes=0-', full_request.get_header('Range'))
    # Fetches partial file content
    stream.ReadBytes(offset=123, length=456)
    partial_request = mock_urlopen.call_args_list[1][0][0]
    self.assertEqual(self.MOCK_URL, partial_request.get_full_url())
    self.assertEqual('bytes=123-578', partial_request.get_header('Range'))

  @mock.patch.object(urllib.request, 'urlopen')
  def testReadBytes_notFound(self, mock_urlopen):
    """Tests that file not found errors are handled when reading content."""
    mock_urlopen.side_effect = urllib.error.HTTPError(None, 404, None, None,
                                                      None)
    handle = file_util.HttpFileHandle(self.MOCK_URL)
    stream = handle.Open().detach()  # Detach to test underlying stream
    self.assertIsNone(stream.ReadBytes())

  @mock.patch.object(urllib.request, 'urlopen')
  def testReadBytes_rangeError(self, mock_urlopen):
    """Tests that range errors are handled when reading content."""
    mock_urlopen.side_effect = urllib.error.HTTPError(None, 416, None, None,
                                                      None)
    handle = file_util.HttpFileHandle(self.MOCK_URL)
    stream = handle.Open().detach()  # Detach to test underlying stream
    self.assertIsNone(stream.ReadBytes())

  @mock.patch.object(urllib.request, 'urlopen')
  def testReadBytes_socketTimeout(self, mock_urlopen):
    """Tests that range errors are handled when reading content."""
    mock_response = mock.MagicMock()
    mock_response.read.return_value = b'foo'
    mock_urlopen.side_effect = [socket.timeout(), mock_response]
    handle = file_util.HttpFileHandle(self.MOCK_URL)
    stream = handle.Open().detach()  # Detach to test underlying stream

    # Fetches partial file content
    data = stream.ReadBytes(offset=123, length=456)

    self.assertEqual(b'foo', data)
    partial_request = mock_urlopen.call_args_list[0][0][0]
    self.assertEqual(self.MOCK_URL, partial_request.get_full_url())
    self.assertEqual('bytes=123-578', partial_request.get_header('Range'))
    partial_request = mock_urlopen.call_args_list[1][0][0]
    self.assertEqual(self.MOCK_URL, partial_request.get_full_url())
    self.assertEqual('bytes=123-578', partial_request.get_header('Range'))

  @mock.patch.object(urllib.request, 'urlopen')
  def testReadBytes_repeatedSocketTimeouts(self, mock_urlopen):
    """Tests that range errors are handled when reading content."""
    mock_urlopen.side_effect = socket.timeout()
    handle = file_util.HttpFileHandle(self.MOCK_URL)
    stream = handle.Open().detach()  # Detach to test underlying stream

    # Fetches partial file content
    with self.assertRaises(socket.timeout):
      stream.ReadBytes(offset=123, length=456)

    for call_args in mock_urlopen.call_args_list:
      partial_request = call_args[0][0]
      self.assertEqual(self.MOCK_URL, partial_request.get_full_url())
      self.assertEqual('bytes=123-578', partial_request.get_header('Range'))


class RemoteFileHandleTest(absltest.TestCase):
  """Tests RemoteFileHandle functionality."""

  def setUp(self):
    super(RemoteFileHandleTest, self).setUp()
    env.FILE_SERVER_URL = 'http://file_server:8006/'
    env.STORAGE_PATH = '/root'

  def testUrlWithHostname(self):
    """Tests that bytes can be written using HTTP requests."""
    handle = file_util.RemoteFileHandle('file://test.hostname/root/path')
    self.assertEqual('/path', handle.path)
    self.assertEqual('http://test.hostname:8006/file/path', handle.file_url)
    self.assertEqual('http://test.hostname:8006/dir/path', handle.dir_url)

  @mock.patch.object(urllib.request, 'urlopen')
  def testWriteBytes(self, mock_urlopen):
    """Tests that bytes can be written using HTTP requests."""
    handle = file_util.RemoteFileHandle('file:///root/path')
    stream = handle.Open(mode='w').detach()  # Detach to test underlying stream
    stream.WriteBytes(data='hello\nworld')
    request = mock_urlopen.call_args[0][0]
    self.assertEqual('http://file_server:8006/file/path',
                     request.get_full_url())
    self.assertEqual('hello\nworld', request.data)
    self.assertEqual('bytes 0-10/11', request.get_header('Content-range'))

  @mock.patch.object(urllib.request, 'urlopen')
  def testWriteBytes_partial(self, mock_urlopen):
    """Tests that partial content can be written using HTTP requests."""
    handle = file_util.RemoteFileHandle('file:///root/path')
    stream = handle.Open(mode='w').detach()  # Detach to test underlying stream
    stream.WriteBytes(offset=5, data='hello\nworld', finish=False)
    request = mock_urlopen.call_args[0][0]
    self.assertEqual('http://file_server:8006/file/path',
                     request.get_full_url())
    self.assertEqual('hello\nworld', request.data)
    self.assertEqual('bytes 5-15/*', request.get_header('Content-range'))

  @mock.patch.object(urllib.request, 'urlopen')
  def testListFiles(self, mock_urlopen):
    """Tests that nested files can be listed."""
    data = json.dumps([
        {
            'name': 'foo',
            'path': 'path/foo',
            'size': 4096,
            'type': 'DIRECTORY',
            'update_time': 631152000000
        },
        {
            'name': 'bar',
            'path': 'path/bar',
            'size': 123456,
            'type': 'FILE',
            'update_time': 946684800000
        },
    ])
    mock_urlopen.return_value = io.BytesIO(data.encode())

    files = file_util.RemoteFileHandle('file:///root/path').ListFiles()
    mock_urlopen.assert_called_with('http://file_server:8006/dir/path')
    self.assertEqual(files, [
        file_util.FileInfo(
            url='file:///root/path/foo',
            is_file=False,
            total_size=4096,
            timestamp=datetime.datetime(1990, 1, 1)),
        file_util.FileInfo(
            url='file:///root/path/bar',
            is_file=True,
            total_size=123456,
            timestamp=datetime.datetime(2000, 1, 1))
    ])

  @mock.patch.object(urllib.request, 'urlopen')
  def testListFiles_notFound(self, mock_urlopen):
    """Tests that file not found errors are handled when listing files."""
    mock_urlopen.side_effect = urllib.error.HTTPError(None, 404, None, None,
                                                      None)
    files = file_util.RemoteFileHandle('file:///root/path').ListFiles()
    self.assertIsNone(files)

  @mock.patch.object(urllib.request, 'urlopen')
  def testDelete(self, mock_urlopen):
    """Tests that local files can be deleted."""
    file_util.RemoteFileHandle('file:///root/path').Delete()
    request = mock_urlopen.call_args[0][0]
    self.assertEqual('DELETE', request.get_method())
    self.assertEqual('http://file_server:8006/file/path',
                     request.get_full_url())


class FileUtilTest(parameterized.TestCase):
  """Test for file_util functions."""

  def setUp(self):
    super(FileUtilTest, self).setUp()
    env.STORAGE_PATH = '/root'
    env.FILE_SERVER_URL = 'http://localhost:8006/'
    env.HOSTNAME = 'test.hostname.com'

  def testGetLocalFilePath(self):
    self.assertEqual(
        '/local/file/path/',
        file_util.GetLocalFilePath('file:///local/file/path/'),
    )
    self.assertIsNone(
        file_util.GetLocalFilePath('file://invalid/local/file/path/')
    )

  def testGetGetAppStorageUrl(self):
    self.assertEqual('file:///root/file/path',
                     file_util.GetAppStorageUrl(['file', 'path']))
    self.assertEqual(
        'file://hostname.com/root/file/path',
        file_util.GetAppStorageUrl(['file', 'path'], 'hostname.com'))

  @mock.patch('multitest_transport.util.env.OPERATION_MODE',
              env.OperationMode.STANDALONE)
  def testGetWorkFileUrl_standaloneMode(self):
    attempt = mock.MagicMock(attempt_id='attempt')

    self.assertEqual('file:///root/tmp/attempt/',
                     file_util.GetWorkFileUrl(attempt))
    self.assertEqual('file:///root/tmp/attempt/file',
                     file_util.GetWorkFileUrl(attempt, 'file'))

  @mock.patch('multitest_transport.util.env.OPERATION_MODE',
              env.OperationMode.ON_PREMISE)
  def testGetWorkFileUrl_onPremiseMode(self):
    attempt = mock.MagicMock(
        hostname='test.hostname.com',
        command_id='command',
        attempt_id='attempt')

    self.assertEqual('file://test.hostname.com/root/tmp/attempt/',
                     file_util.GetWorkFileUrl(attempt))
    self.assertEqual('file://test.hostname.com/root/tmp/attempt/file/path',
                     file_util.GetWorkFileUrl(attempt, 'file/path'))

  def testGetOutputFileUrl(self):
    attempt = mock.MagicMock(command_id='command', attempt_id='attempt')
    test_run = mock.MagicMock(output_path='/base/')

    self.assertEqual('file:///root/base/command/attempt/',
                     file_util.GetOutputFileUrl(test_run, attempt))
    self.assertEqual('file:///root/base/command/attempt/file',
                     file_util.GetOutputFileUrl(test_run, attempt, 'file'))

  @mock.patch.dict(os.environ, {'IS_OMNILAB_BASED': 'true'}, clear=True)
  def testGetOutputFileUrlWithOmnilabEnabled(self):
    attempt = mock.MagicMock(
        command_id='command', attempt_id='attempt', request_id='request'
    )
    test_run = mock.MagicMock(output_path='/base/')

    self.assertEqual(
        'file:///root/base/request/command/tradefed_logs/XtsTradefedTest_test_attempt/',
        file_util.GetOutputFileUrl(test_run, attempt),
    )
    self.assertEqual(
        'file:///root/base/request/command/tradefed_logs/XtsTradefedTest_test_attempt/file',
        file_util.GetOutputFileUrl(test_run, attempt, 'file'),
    )

  @mock.patch.dict(os.environ, {'IS_OMNILAB_BASED': 'true'}, clear=True)
  def testResultUrlWithOmnilabEnabled(self):
    test = mock.MagicMock(result_file='test_result.xml')
    attempt = mock.MagicMock(
        command_id='command', attempt_id='attempt', request_id='request'
    )
    test_run = mock.MagicMock(output_path='/base/', test=test)

    self.assertEqual(
        'file:///root/base/request/command/tradefed_results/XtsTradefedTest_test_attempt/test_result.xml',
        file_util.GetResultUrl(test_run, attempt),
    )

  @mock.patch.object(file_util.FileHandle, 'Get')
  @mock.patch.object(file_util, 'GetOutputFileUrl')
  def testGetOutputFilenames(self, mock_get_output_url, mock_handle_factory):
    """Tests that an attempt's output filenames can retrieved."""
    test_run = mock.MagicMock()
    attempt = mock.MagicMock()
    with open(os.path.join(TEST_DATA_DIR, 'FILES'), 'rb') as f:
      mock_handle_factory.return_value.Open.return_value = f
      # List of filenames read from 'FILES' summary file
      filenames = file_util.GetOutputFilenames(test_run, attempt)
      self.assertEqual(['test_result.xml', 'tool-logs/stdout.txt'], filenames)
      mock_get_output_url.assert_called_once_with(test_run, attempt, 'FILES')

  @parameterized.parameters(
      (env.OperationMode.STANDALONE, 'http://localhost:8000/path',
       'http://localhost:8000/path'),
      (env.OperationMode.STANDALONE, 'file:///root/path', 'file:///root/path'),
      (env.OperationMode.ON_PREMISE, 'http://localhost:8000/xx',
       '${MTT_CONTROL_SERVER_URL}/xx'),
      (env.OperationMode.ON_PREMISE, 'http://0.0.0.0:8000/xx',
       '${MTT_CONTROL_SERVER_URL}/xx'),
      (env.OperationMode.ON_PREMISE, 'http://127.0.0.1:8000/xx',
       '${MTT_CONTROL_SERVER_URL}/xx'),
      (env.OperationMode.ON_PREMISE, 'http://[::]:8000/xx',
       '${MTT_CONTROL_SERVER_URL}/xx'),
      (env.OperationMode.ON_PREMISE, 'http://[::1]:8000/xx',
       '${MTT_CONTROL_SERVER_URL}/xx'),
      (env.OperationMode.ON_PREMISE, 'http://other.hostname.com:8000/xx',
       'http://other.hostname.com:8000/xx'),
      (env.OperationMode.ON_PREMISE, 'file:///root/path',
       '${MTT_CONTROL_FILE_SERVER_URL}/file/path'),
      (env.OperationMode.ON_PREMISE, 'http://localhost:8006/xx',
       '${MTT_CONTROL_FILE_SERVER_URL}/xx'),
      (env.OperationMode.ON_PREMISE, 'file:///xx', 'file:///xx'),
      (env.OperationMode.ON_PREMISE, 'http://TEST.hostname.com:8000/xx',
       '${MTT_CONTROL_SERVER_URL}/xx'))
  def testGetWorkerAccessibleUrl(self, operation_mode, original_url,
                                 expected_url):
    env.OPERATION_MODE = operation_mode
    env.PORT = '8000'
    env.FILE_SERVER_PORT = '8006'
    env.HOSTNAME = 'TEST.hostname.com'
    url = file_util.GetWorkerAccessibleUrl(original_url)
    self.assertEqual(url, expected_url)

  @mock.patch.object(file_util.FileHandle, 'Get')
  def testReadFile(self, mock_handle_factory):
    """Tests that file segments can be read."""
    mock_handle_factory.return_value.Open.side_effect = [
        MockReadStream('hello\nworld'),
        MockReadStream('hello\nworld'),
    ]
    self.assertEqual(
        file_util.ReadFile('url'),
        file_util.FileSegment(0, ['hello\n', 'world']))
    self.assertEqual(
        file_util.ReadFile('url', offset=2, length=7),
        file_util.FileSegment(2, ['llo\n', 'wor']))

  @mock.patch.object(file_util.FileHandle, 'Get')
  def testTailFile(self, mock_handle_factory):
    """Tests that file segments can be read from end of file."""
    test_handle = MockFileHandle('hello\nworld')
    mock_handle_factory.return_value = test_handle
    self.assertEqual(
        file_util.TailFile('url', 3), file_util.FileSegment(8, ['rld']))
    self.assertEqual(
        file_util.TailFile('url', 8),
        file_util.FileSegment(3, ['lo\n', 'world']))
    # Out of bounds returns entire file
    self.assertEqual(
        file_util.TailFile('url', 999),
        file_util.FileSegment(0, ['hello\n', 'world']))

  @mock.patch.object(file_util.FileHandle, 'Get')
  def testDownloadFile(self, mock_handle_factory):
    """Tests that a file can be downloaded in multiple chunks."""
    file_util.DOWNLOAD_BUFFER_SIZE = 4
    test_handle = MockFileHandle('hello\nworld')
    mock_handle_factory.return_value = test_handle

    result = list(file_util.DownloadFile('url'))
    expected_result = [
        file_util.FileChunk(data='hell', offset=4, total_size=11),
        file_util.FileChunk(data='o\nwo', offset=8, total_size=11),
        file_util.FileChunk(data='rld', offset=11, total_size=11)
    ]
    self.assertEqual(expected_result, result)

  @mock.patch.object(file_util.FileHandle, 'Get')
  def testDownloadFile_notFound(self, mock_handle_factory):
    mock_handle = mock.MagicMock()
    mock_handle_factory.return_value = mock_handle
    mock_handle.Info.return_value = None

    with self.assertRaises(RuntimeError):
      list(file_util.DownloadFile('url'))

  def testGetTestSuiteInfo(self):
    # Test package contains a tradefed jar file with test suite information.
    with open(os.path.join(TEST_DATA_DIR, 'test_package.zip'), 'rb') as f:
      suite_info = file_util.GetTestSuiteInfo(f)
      self.assertEqual('1234567', suite_info.build_number)
      self.assertEqual('x86_64', suite_info.target_architecture)
      self.assertEqual('DTS', suite_info.name)
      self.assertEqual('Dummy Test Suite', suite_info.fullname)
      self.assertEqual('1.0', suite_info.version)

  def testGetTestSuiteInfo_empty(self):
    # Test package does not contain a tradefed jar file.
    with open(os.path.join(TEST_DATA_DIR, 'test_package-empty.zip'), 'rb') as f:
      self.assertIsNone(file_util.GetTestSuiteInfo(f))

  def testGetTestSuiteInfo_invalid(self):
    # Test package contains a tradefed jar file without test suite information.
    with open(
        os.path.join(TEST_DATA_DIR, 'test_package-invalid.zip'), 'rb') as f:
      self.assertIsNone(file_util.GetTestSuiteInfo(f))

  def testFileHandleMediaUpload(self):
    """Tests that media upload can process a file handle."""
    test_handle = MockFileHandle('hello\nworld')
    media_upload = file_util.FileHandleMediaUpload(test_handle)
    self.assertEqual(11, media_upload.size())
    self.assertEqual('ello', media_upload.getbytes(1, 4))
    self.assertEqual('string', media_upload.mimetype())
    self.assertFalse(media_upload.has_stream())


if __name__ == '__main__':
  absltest.main()
