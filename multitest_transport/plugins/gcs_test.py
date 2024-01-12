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

"""Unit tests for gcs."""
import datetime
from unittest import mock

from absl.testing import absltest
import apiclient


from multitest_transport.models import event_log
from multitest_transport.plugins import base
from multitest_transport.plugins import gcs
from multitest_transport.util import constant
from multitest_transport.util import errors
from multitest_transport.util import file_util


class GCSBuildProviderTest(absltest.TestCase):

  def setUp(self):
    super().setUp()
    self.provider = gcs.GCSBuildProvider()
    self.api_client = self.provider._client = mock.MagicMock()

  def testGetBuildItem_withPathToFile(self):
    """Tests that files can be fetched from GCS."""
    self.api_client.objects().get().execute.return_value = {
        'name': 'dir/file',
        'size': '123',
        'updated': '2018-07-07T23:52:40.332Z',
    }

    build_item = self.provider.GetBuildItem('bucket/dir/file')
    self.assertEqual(
        build_item,
        base.BuildItem(
            name='file',
            path='bucket/dir/file',
            is_file=True,
            size=123,
            timestamp=datetime.datetime(2018, 7, 7, 23, 52, 40, 332000)))

  def testGetBuildItem_withPathToDirectory(self):
    """Tests that directories can be fetched from GCS."""
    self.api_client.objects().get().execute.return_value = {
        'name': 'dir/',
        'size': '0',
        'updated': '2018-07-07T23:52:33.535Z',
    }

    build_item = self.provider.GetBuildItem('bucket/dir/')
    self.assertEqual(
        build_item,
        base.BuildItem(
            name='dir/',
            path='bucket/dir/',
            is_file=False,
            size=0,
            timestamp=datetime.datetime(2018, 7, 7, 23, 52, 33, 535000)))

  def testGetBuildItem_withPathToDirectory_withoutObject(self):
    """Tests that directories without objects can be fetched from GCS."""
    side_effect = apiclient.http.HttpError(mock.Mock(status=404), 'not found')
    self.api_client.objects().get().execute.side_effect = side_effect
    self.api_client.objects().get().execute.return_value = {
        'items': [{
            'bucket': 'bucket',
            'contentType': 'text/plain',
            'name': 'dir/nested_dir/file',
            'size': '456',
            'updated': '2018-07-06T23:29:21.410Z',
        }],
    }

    build_item = self.provider.GetBuildItem('bucket/dir/')
    self.assertEqual(
        build_item,
        base.BuildItem(name='dir/', path='bucket/dir/', is_file=False),
    )

  def testGetBuildItem_fileNotFound(self):
    """Tests that None is returned if the file is not found."""
    side_effect = apiclient.http.HttpError(mock.Mock(status=404), 'not found')
    self.api_client.objects().get().execute.side_effect = side_effect
    self.api_client.objects().list().execute.return_value = {'items': []}

    build_item = self.provider.GetBuildItem('bucket/dir/file')
    self.assertIsNone(build_item)
    self.api_client.objects().get.assert_has_calls([
        mock.call(bucket='bucket', object='dir/file'),
        mock.ANY,  # Execute request.
    ])
    # Automatically retries with a trailing slash to check for directories.
    self.api_client.objects().list.assert_has_calls([
        mock.call(
            bucket='bucket',
            delimiter=mock.ANY,
            maxResults=mock.ANY,
            prefix='dir/file/',
            pageToken=None,
        ),
        mock.ANY,  # Execute request.
    ])

  def testGetBuildItem_rootDirectory(self):
    """Tests that the root dir is returned if no object name is provided."""
    build_item = self.provider.GetBuildItem('bucket')
    self.assertEqual(build_item,
                     base.BuildItem(name='', path='bucket', is_file=False))

  def testListBuildItems(self):
    """Tests that GCS files and directories can be listed."""
    response = {
        'items': [{
            'bucket': 'bucket',
            'contentType': 'text/plain',
            'name': 'dir/file',
            'size': '456',
            'updated': '2018-07-06T23:29:21.410Z'
        }],
        'nextPageToken': 'nextPageToken',
        'prefixes': ['dir/nested_dir/'],
    }
    self.api_client.objects().list().execute.return_value = response

    build_items, next_page_token = self.provider.ListBuildItems(
        path='bucket/dir', page_token=None)
    self.assertEqual(next_page_token, 'nextPageToken')
    self.assertEqual(build_items, [
        base.BuildItem(
            name='nested_dir/',
            path='bucket/dir/nested_dir/',
            is_file=False),
        base.BuildItem(
            name='file',
            path='bucket/dir/file',
            is_file=True,
            size=456,
            timestamp=datetime.datetime(2018, 7, 6, 23, 29, 21, 410000)),
    ])

  def testListBuildItems_withEmptyFolder(self):
    """Tests that empty folders are ignored when listing GCS objects."""
    self.api_client.objects().list().execute.return_value = {
        'items': [{
            'bucket': 'bucket',
            'contentType': 'text/plain',
            'name': 'dir/',  # Name is empty (just folder prefix).
            'size': '0',
            'updated': '2018-07-06T23:29:21.410Z'
        }, {
            'bucket': 'bucket',
            'contentType': 'application/x-www-form-urlencoded;charset=UTF-8',
            'name': 'dir/empty_folder',  # Content type identifies empty folder.
            'size': '0',
            'updated': '2018-07-06T23:29:21.410Z'
        }],
        'nextPageToken': 'nextPageToken',
    }

    build_items, next_page_token = self.provider.ListBuildItems(
        path='bucket/dir', page_token=None)
    self.assertEqual(next_page_token, 'nextPageToken')
    self.assertEmpty(build_items)

  def testListBuildItems_bucketNotFound(self):
    """Tests that an error is raised if the bucket is not found."""
    side_effect = apiclient.http.HttpError(mock.Mock(status=404), 'not found')
    self.api_client.objects().list().execute.side_effect = side_effect
    with self.assertRaisesRegex(gcs.GCSBucketNotFoundError,
                                'bucket invalid_bucket does not exist'):
      self.provider.ListBuildItems(path='invalid_bucket/', page_token=None)

  @mock.patch.object(gcs.GCSBuildProvider, 'GetBuildItem')
  def testDownloadFile_withInvalidFile(self, mock_get_build_item):
    """Tests that an error is raised when attempting to download a directory."""
    mock_get_build_item.return_value = base.BuildItem(
        name='path/', path='bucket/fake/path/', is_file=False)
    with self.assertRaisesRegex(errors.FileNotFoundError,
                                'Build item bucket/fake/path/ does not exist'):
      list(self.provider.DownloadFile('bucket/fake/path/'))

  @mock.patch.object(gcs.GCSBuildProvider, 'GetBuildItem')
  def testDownloadFile_withNoneValue(self, mock_get_build_item):
    """Try to download a file that does not exist."""
    mock_get_build_item.return_value = None
    with self.assertRaisesRegex(errors.FileNotFoundError,
                                'Build item bucket/fake/path/ does not exist'):
      list(self.provider.DownloadFile('bucket/fake/path/'))

  @mock.patch.object(gcs.GCSBuildProvider, 'GetBuildItem')
  @mock.patch.object(
      apiclient.http.MediaIoBaseDownload, 'next_chunk', autospec=True)
  def testDownloadFile(self, mock_next_chunk, mock_get_build_item):
    """Test downloading a file with multiple chunks."""
    path = 'bucket/fake/path/kitten.png'
    mock_get_build_item.return_value = base.BuildItem(
        name='kitten.png',
        path='bucket/fake/path/kitten.png',
        is_file=True,
        size=0,
        timestamp=None)

    # Mock downloader that processes two chunks of data
    mock_progress = iter([
        (b'hello', mock.MagicMock(resumable_progress=5, total_size=10), False),
        (b'world', mock.MagicMock(resumable_progress=10, total_size=10), True),
    ])
    def _next_chunk(self, **_):
      value, status, done = next(mock_progress)
      self._fd.write(value)
      return status, done
    mock_next_chunk.side_effect = _next_chunk

    result = list(self.provider.DownloadFile(path))
    self.api_client.objects().get_media.assert_called_with(
        bucket='bucket', object='fake/path/kitten.png')
    expected = [
        file_util.FileChunk(data=b'hello', offset=5, total_size=10),
        file_util.FileChunk(data=b'world', offset=10, total_size=10)
    ]
    self.assertEqual(expected, result)


class GCSFileUploadHookTest(absltest.TestCase):

  @mock.patch.object(event_log, 'Info')
  @mock.patch.object(file_util, 'FileHandleMediaUpload')
  @mock.patch.object(file_util.FileHandle, 'Get')
  def testUploadFile(self, mock_handle_factory, mock_media_upload_ctor,
                     mock_log):
    """Tests uploading a file to GCS."""
    hook = gcs.GCSFileUploadHook(file_pattern='.*')

    # Configure mock file handle
    mock_handle = mock.MagicMock()
    mock_handle_factory.return_value = mock_handle
    # Configure mock media uploader
    mock_media_upload = mock.MagicMock()
    mock_media_upload_ctor.return_value = mock_media_upload
    # Configure mock client and response (upload will be done)
    hook._client = mock.MagicMock()
    hook._client.objects().insert().next_chunk.return_value = None, True

    # Upload file and verify that client and uploader used properly
    hook.UploadFile(mock.MagicMock(), 'file_url', 'bucket/test_run/file.txt')
    mock_media_upload_ctor.assert_called_with(
        mock_handle, chunksize=constant.UPLOAD_CHUNK_SIZE, resumable=True)
    hook._client.objects().insert.assert_called_with(
        bucket='bucket',
        name='test_run/file.txt',
        media_body=mock_media_upload)
    mock_log.assert_called_with(
        mock.ANY, '[GCS] Uploaded file_url to bucket/test_run/file.txt.')


if __name__ == '__main__':
  absltest.main()
