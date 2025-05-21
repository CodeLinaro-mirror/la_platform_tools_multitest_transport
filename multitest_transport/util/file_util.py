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

"""A util file that stores common function that involve file operation."""
import dataclasses
import datetime
import io
import json
import logging
import mimetypes
import os
import pathlib
import re
import shutil
import socket
import stat
from typing import BinaryIO, Iterator, List, Optional
import urllib.error
import urllib.parse
import urllib.request
import zipfile

import apiclient


from multitest_transport.util import env

DOWNLOAD_BUFFER_SIZE = 16 * 1024 * 1024
UPLOAD_BUFFER_SIZE = 512 * 1024
LOCAL_HOSTNAME = ('localhost', '0.0.0.0', '127.0.0.1', '::', '::1')
HTTP_TIMEOUT_SECONDS = 30
MAX_HTTP_READ_ATTEMPTS = 3
LOCAL_FILE_URL_PREFIX = 'file:///'


@dataclasses.dataclass(frozen=True)
class FileChunk(object):
  """File chunk during download."""
  data: bytes
  offset: int
  total_size: int


@dataclasses.dataclass(frozen=True)
class TestSuiteInfo(object):
  """Test suite information."""
  build_number: str
  target_architecture: str
  name: str
  fullname: str
  version: str


@dataclasses.dataclass(frozen=True)
class TestModuleInfo(object):
  """Test module information."""
  name: str


@dataclasses.dataclass(frozen=True)
class FileInfo(object):
  """File information."""
  url: str  # file URL
  is_file: bool = True  # True for files, False for directories
  total_size: Optional[int] = None  # file total size
  content_type: Optional[str] = None  # file content type
  timestamp: Optional[datetime.datetime] = None  # last modification datetime


@dataclasses.dataclass(frozen=True)
class FileSegment(object):
  """Partial file content."""
  offset: int  # starting offset
  lines: List[bytes]  # lines of content

  @property
  def length(self) -> int:
    return sum([len(line) for line in self.lines])


def _JoinPath(*parts: str) -> str:
  """Join multiple URL parts together with a '/' separator.

  Unlike os.path.join and urllib.urlparse.urljoin, does not treat parts with
  leading slashes (i.e. absolute parts) differently.

  Args:
    *parts: URL parts
  Returns:
    concatenated URL
  """
  return '/'.join(re.sub('(^/|/$)', '', part or '') for part in parts)


def _HttpTimeToDatetime(
    http_time: Optional[str]) -> Optional[datetime.datetime]:
  """Converts a HTTP time string (RFC 2616) to a datetime object."""
  if http_time:
    return datetime.datetime.strptime(http_time, '%a, %d %b %Y %H:%M:%S GMT')


def _SecondsToDatetime(
    epoch_seconds: Optional[float]) -> Optional[datetime.datetime]:
  """Converts a POSIX timestamp (epoch seconds) to a datetime object."""
  if epoch_seconds:
    return datetime.datetime.utcfromtimestamp(epoch_seconds)


def _MillisToDatetime(
    epoch_millis: Optional[float]) -> Optional[datetime.datetime]:
  """Converts epoch milliseconds to a datetime object."""
  if epoch_millis:
    return _SecondsToDatetime(epoch_millis / 1000.)


class BaseReadStream(io.RawIOBase):
  """Abstract seekable read-only file-like object."""

  def __init__(self, handle: 'FileHandle'):
    super(BaseReadStream, self).__init__()
    self.handle = handle
    self.cursor = 0
    self.size = -1

  def ReadBytes(self,
                offset: int = 0,
                length: Optional[int] = None) -> Optional[bytes]:
    """Read bytes.

    Args:
      offset: starting position (defaults to start of file)
      length: number of bytes to read (defaults to rest of file)
    Returns:
      data
    """
    raise NotImplementedError

  def seek(self, offset: int, whence: int = os.SEEK_SET):
    if whence == os.SEEK_SET:
      self.cursor = offset
    elif whence == os.SEEK_CUR:
      self.cursor += offset
    elif whence == os.SEEK_END:
      if self.size < 0:
        file_info = self.handle.Info()
        if not file_info:
          raise ValueError('File %s not found' % self.handle.url)
        self.size = file_info.total_size
      self.cursor = self.size + offset
    else:
      raise ValueError('Unsupported whence %s' % whence)
    return self.cursor

  def tell(self) -> int:
    return self.cursor

  def read(self, size: int = -1) -> bytes:
    data = self.ReadBytes(offset=self.cursor, length=size) or b''
    self.cursor += len(data)
    return data

  def readinto(self, b: bytearray) -> int:
    data = self.read(len(b))
    b[:len(data)] = data
    return len(data)

  def readall(self) -> bytes:
    return self.read()

  def write(self, *args, **kwargs):
    raise io.UnsupportedOperation('write')

  def seekable(self) -> bool:
    return True

  def readable(self) -> bool:
    return True


class BaseWriteStream(io.RawIOBase):
  """Abstract write-only file-like object."""

  def __init__(self, handle: 'FileHandle'):
    super(BaseWriteStream, self).__init__()
    self.handle = handle
    self.cursor = 0

  def WriteBytes(self,
                 offset: int = 0,
                 data: Optional[bytes] = None,
                 finish: bool = True):
    """Writes bytes.

    Args:
      offset: starting position (defaults to start of file)
      data: bytes to write
      finish: whether to execute any finalization logic
    """
    raise NotImplementedError

  def tell(self) -> int:
    return self.cursor

  def close(self):
    self.WriteBytes(offset=self.cursor)
    super(BaseWriteStream, self).close()

  def read(self, *arg, **kwargs):
    raise io.UnsupportedOperation('read')

  def write(self, data: bytes) -> int:
    self.WriteBytes(offset=self.cursor, data=data, finish=False)
    self.cursor += len(data)
    return len(data)

  def writable(self) -> bool:
    return True


class FileHandle(object):
  """File-like object which wraps a URL and can read file metadata/content."""

  def __init__(self, url: str):
    super(FileHandle, self).__init__()
    self.url = url

  @classmethod
  def Get(cls, url: str) -> 'FileHandle':
    """Factory method which creates the appropriate file handle.

    Args:
      url: file URL
    Returns:
      file handle
    """
    if url.startswith(LOCAL_FILE_URL_PREFIX):
      return LocalFileHandle(url)  # Local file URL
    if url.startswith('file://'):
      return RemoteFileHandle(url)  # Remote file server URL
    return HttpFileHandle(url)  # Any other URL defaults to HTTP handling

  def Info(self) -> Optional[FileInfo]:
    """Get file information.

    Returns:
      FileInfo or None if file not found.
    """
    raise NotImplementedError

  def Open(self, mode: str = 'r') -> BinaryIO:
    """Returns a file-like object for reading or writing.

    Args:
      mode: 'r' for reading or 'w' for writing
    Returns:
      file-like object
    """
    raise NotImplementedError

  def ListFiles(self) -> Optional[List[FileInfo]]:
    """Returns a list of nested files if this handle represents a directory.

    Returns:
      list of FileInfo or None if directory doesn't exist.
    """
    raise NotImplementedError

  def Delete(self):
    """Deletes this file if it exists."""
    raise NotImplementedError

  def DeleteDir(self):
    """Deletes this directory if it exists and all files contained."""
    raise NotImplementedError

  def Archive(self, remove_file: bool = True):
    """Archives this file.

    Args:
      remove_file: if true, remove the file after archiving
    """
    raise NotImplementedError


class LocalFileHandle(FileHandle):
  """Reads file metadata and content from the file system."""

  def __init__(self, url: str):
    super(LocalFileHandle, self).__init__(url)
    local_file_path = GetLocalFilePath(url)
    if not local_file_path:
      raise ValueError('Invalid local file URL %s' % url)
    self.path = local_file_path
    if not self.path.startswith(env.STORAGE_PATH):
      self.path = _JoinPath('/', env.STORAGE_PATH, self.path)

  def _GetFileInfo(self, path: str) -> FileInfo:
    stat_info = os.stat(path)
    content_type, _ = mimetypes.guess_type(path)
    return FileInfo(
        url='file://' + path,
        is_file=not stat.S_ISDIR(stat_info.st_mode),
        total_size=stat_info.st_size,
        content_type=content_type,
        timestamp=_SecondsToDatetime(stat_info.st_mtime))

  def Info(self) -> Optional[FileInfo]:
    if not os.path.exists(self.path):
      return None
    return self._GetFileInfo(self.path)

  def Open(self, mode: str = 'r') -> BinaryIO:
    if mode == 'r':
      return open(self.path, mode='rb')
    if mode == 'w':
      dir_path = os.path.dirname(self.path)
      if not os.path.exists(dir_path):
        os.makedirs(dir_path)
      return open(self.path, mode='wb')
    raise ValueError('Unsupported mode %s' % mode)

  def ListFiles(self) -> Optional[List[FileInfo]]:
    if not os.path.isdir(self.path):
      return None
    files = []
    for filename in os.listdir(self.path):
      child_path = os.path.join(self.path, filename)
      files.append(self._GetFileInfo(child_path))
    return files

  def Delete(self):
    if os.path.isfile(self.path):
      os.remove(self.path)

  def DeleteDir(self):
    if os.path.isdir(self.path):
      shutil.rmtree(self.path)

  def Archive(self, remove_file: bool = True):
    if os.path.isdir(self.path):
      shutil.make_archive(self.path, 'zip', self.path)
      if remove_file:
        shutil.rmtree(self.path)
    else:
      with zipfile.ZipFile(self.path + '.zip', 'w') as f:
        f.write(self.path)
      if remove_file:
        os.remove(self.path)


class HttpReadStream(BaseReadStream):
  """Read-only file-like object accessible using HTTP requests."""

  def __init__(self,
               handle: FileHandle,
               url: str,
               urlopen=urllib.request.urlopen):
    super(HttpReadStream, self).__init__(handle)
    self.url = url
    self.urlopen = urlopen

  def ReadBytes(self,
                offset: int = 0,
                length: Optional[int] = None) -> Optional[bytes]:
    if length is None or length < 0:
      headers = {'Range': 'bytes=%s-' % offset}
    else:
      headers = {'Range': 'bytes=%s-%s' % (offset, offset + length - 1)}
    attempt = 1
    while attempt <= MAX_HTTP_READ_ATTEMPTS:
      try:
        request = urllib.request.Request(self.url, headers=headers)
        return self.urlopen(request, timeout=HTTP_TIMEOUT_SECONDS).read()
      except urllib.error.HTTPError as e:
        if e.code == 404 or e.code == 416:
          # Ignore file not found or unsatisfied range errors, which occur if
          # requesting content from after EOF
          return None
        raise
      except socket.timeout:
        if MAX_HTTP_READ_ATTEMPTS <= attempt:
          raise
        logging.info(
            'Read failed due to socket timeout; retrying... (attempt %d of %d)',
            attempt, MAX_HTTP_READ_ATTEMPTS)
      attempt += 1


class HttpWriteStream(BaseWriteStream):
  """Write-only file-like object which uses HTTP requests."""

  def __init__(self,
               handle: FileHandle,
               url: str,
               urlopen=urllib.request.urlopen):
    super(HttpWriteStream, self).__init__(handle)
    self.url = url
    self.urlopen = urlopen

  def WriteBytes(self,
                 offset: int = 0,
                 data: Optional[bytes] = None,
                 finish: bool = True):
    end_byte = offset + len(data) - 1 if data else offset
    # Upload is complete when end_byte + 1 == total_size
    total_size = end_byte + 1 if finish else '*'
    headers = {'Content-Range': 'bytes %s-%s/%s' %
                                (offset, end_byte, total_size)}
    request = urllib.request.Request(url=self.url, data=data, headers=headers)
    request.get_method = lambda: 'PUT'
    self.urlopen(request, timeout=HTTP_TIMEOUT_SECONDS).read()


class HttpFileHandle(FileHandle):
  """Reads file metadata and content via HTTP requests."""

  def __init__(self,
               url: str,
               info_url: Optional[str] = None,
               read_url: Optional[str] = None,
               url_opener: Optional[urllib.request.OpenerDirector] = None):
    super(HttpFileHandle, self).__init__(url)
    self.info_url = info_url or url
    self.read_url = read_url or url
    self.urlopen = url_opener.open if url_opener else urllib.request.urlopen

  def Info(self) -> Optional[FileInfo]:
    try:
      request = urllib.request.Request(self.info_url)
      request.get_method = lambda: 'HEAD'
      response = self.urlopen(request, timeout=HTTP_TIMEOUT_SECONDS)
    except urllib.error.HTTPError as e:
      if e.code == 404:
        return None
      raise
    # Parse file info from response headers
    return FileInfo(
        url=self.url,
        is_file=True,
        total_size=int(response.info().get('content-length', 0)),
        content_type=response.info().get('content-type'),
        timestamp=_HttpTimeToDatetime(response.info().get('last-modified')))

  def Open(self, mode: str = 'r') -> BinaryIO:
    if mode == 'r':
      return io.BufferedReader(
          HttpReadStream(self, self.read_url, self.urlopen))
    raise ValueError('Unsupported mode %s' % mode)


class RemoteFileHandle(HttpFileHandle):
  """Reads file metadata and content from a remote file server."""

  def __init__(self, url: str):
    # Hostname is optional for backwards compatibility (uses local file server)
    match = re.search('^file://([^/]+)?(/.*)', url)
    if not match:
      raise ValueError('Invalid file URL %s' % url)
    self.hostname, self.path = match.groups()
    # Remove storage path prefix (file server expect relative paths)
    if self.path and self.path.startswith(env.STORAGE_PATH):
      self.path = self.path[len(env.STORAGE_PATH):]
    # Use remote file server if hostname is provided
    fs_url = env.FILE_SERVER_URL
    if self.hostname is not None:
      parsed_fs_url = urllib.parse.urlparse(fs_url)
      fs_url = parsed_fs_url._replace(
          netloc='{}:{}'.format(self.hostname, parsed_fs_url.port)).geturl()
    # Generate URLs
    self.file_url = _JoinPath(fs_url, 'file', self.path)
    self.dir_url = _JoinPath(fs_url, 'dir', self.path)
    super(RemoteFileHandle, self).__init__(url, info_url=self.file_url)

  def Open(self, mode: str = 'r') -> BinaryIO:
    if mode == 'r':
      return io.BufferedReader(
          HttpReadStream(self, self.file_url, self.urlopen))
    if mode == 'w':
      return io.BufferedWriter(
          HttpWriteStream(self, self.file_url, self.urlopen))
    raise ValueError('Unsupported mode %s' % mode)

  def ListFiles(self) -> Optional[List[FileInfo]]:
    try:
      response = urllib.request.urlopen(self.dir_url)
    except urllib.error.HTTPError as e:
      if e.code == 404:
        return None
      raise
    # Parse file information from JSON response
    files = []
    for node in json.load(response):
      files.append(
          FileInfo(
              url=_JoinPath(self.url, node.get('name')),
              is_file=node.get('type') != 'DIRECTORY',
              total_size=node.get('size'),
              timestamp=_MillisToDatetime(node.get('update_time'))))
    return files

  def Delete(self):
    request = urllib.request.Request(url=self.file_url)
    request.get_method = lambda: 'DELETE'
    urllib.request.urlopen(request)


def GetLocalFilePath(file_url: str) -> Optional[str]:
  """Get the local file path.

  Args:
    file_url: file URL.

  Returns:
    local file path
  """
  if not file_url.startswith(LOCAL_FILE_URL_PREFIX):
    logging.warning('Invalid local file URL %s', file_url)
    return None
  return file_url[7:]


def GetAppStorageUrl(parts: List[str], hostname: Optional[str] = None) -> str:
  """Get the application storage URL for a file.

  Args:
    parts: a list of file path parts
    hostname: optional hostname of a file

  Returns:
    application storage URL
  """
  # TODO: Support GCS storage in cloud mode
  if hostname:
    return _JoinPath(*(['file://', hostname, env.STORAGE_PATH] + parts))
  return _JoinPath(*(['file:///', env.STORAGE_PATH] + parts))


def GetWorkFileUrl(attempt, file_path: str = '') -> str:
  """Get URL for a command attempt's work directory.

  Args:
    attempt: command attempt
    file_path: optional file path
  Returns:
    attempt's work directory URL
  """
  if os.environ.get('IS_OMNILAB_BASED') == 'true':
    # TODO: add remote mode
    url = GetAppStorageUrl([
        file_path,
    ])
    return url
  if env.OPERATION_MODE == env.OperationMode.ON_PREMISE:
    return GetAppStorageUrl(['tmp', attempt.attempt_id, file_path],
                            attempt.hostname)
  return GetAppStorageUrl(['tmp', attempt.attempt_id, file_path])


def GetOutputFileUrl(test_run, attempt, file_path: str = '') -> str:
  """Get URL for a command attempt's output file.

  Args:
    test_run: test run
    attempt: command attempt
    file_path: optional file path
  Returns:
    attempt's output URL
  """
  if os.environ.get('IS_OMNILAB_BASED') == 'true':
    return GetAppStorageUrl([
        test_run.output_path,
        attempt.request_id,
        attempt.command_id,
        file_path,
    ])
  return GetAppStorageUrl(
      [test_run.output_path, attempt.command_id, attempt.attempt_id, file_path])


def GetMergedReportFileUrl(test_run, file_path: str = '') -> str:
  """Get URL for the test run's merged report directory.

  Only test run triggered with sharding mode MODULE will have merged report.

  Args:
    test_run: test run
    file_path: optional file path

  Returns:
    test run's merged report directory/file URL
  """
  return GetAppStorageUrl([test_run.output_path, 'merged_report', file_path])


def GetOutputFilenames(test_run, attempt) -> List[str]:
  """Get a list of output filenames for a completed attempt.

  Args:
    test_run: test run
    attempt: command attempt
  Returns:
    list of output filenames
  """
  summary_url = GetOutputFileUrl(test_run, attempt, 'FILES')
  with OpenFile(summary_url) as stream:
    return [line.strip().decode() for line in stream.readlines()]


def GetResultUrl(test_run, attempt) -> Optional[str]:
  """Get URL for a command attempt's result file."""
  result_file = test_run.test.result_file
  if not result_file:
    return None
  if os.environ.get('IS_OMNILAB_BASED') == 'true':
    return GetAppStorageUrl([
        test_run.output_path,
        attempt.request_id,
        attempt.command_id,
        test_run.test.result_file,
    ])
  return GetOutputFileUrl(test_run, attempt, result_file)


def GetWorkerAccessibleUrl(url: str) -> str:
  """Get URL for worker based on operation mode.

  Args:
    url: URL

  Returns:
    URL for worker to access.
  """
  if env.OPERATION_MODE != env.OperationMode.ON_PREMISE:
    return url
  if env.IS_OMNILAB_BASED:
    return url
  u = urllib.parse.urlparse(url)
  # If the URL is under file server root directory, translate it to http.
  # Otherwise, it refers to a local file on worker.
  if u.scheme == 'file' and (u.hostname or u.path.startswith(env.STORAGE_PATH)):
    u = urllib.parse.urlparse(RemoteFileHandle(url).file_url)
  # IN ON_PREMISE mode, return templated url for worker,
  # and tradefed will populate it with accessible url
  if (u.scheme == 'http' or u.scheme == 'https') and u.hostname in (
      LOCAL_HOSTNAME + (env.HOSTNAME.lower(),)
  ):
    url_format = f'{u.scheme}://{u.netloc}'
    modified_url = u.geturl()
    if str(u.port) == env.PORT:
      modified_url = modified_url.replace(url_format,
                                          '${MTT_CONTROL_SERVER_URL}', 1)
    if str(u.port) == env.FILE_SERVER_PORT:
      modified_url = modified_url.replace(url_format,
                                          '${MTT_CONTROL_FILE_SERVER_URL}', 1)
    return modified_url
  return u.geturl()


def OpenFile(url: str, mode: str = 'r') -> BinaryIO:
  """Convenience method to get a file handle and open it for reading or writing.

  Args:
    url: file URL
    mode: 'r' for reading or 'w' for writing
  Returns:
    file-like object for reading or writing
  """
  return FileHandle.Get(url).Open(mode=mode)


def ReadFile(file_url: str,
             offset: int = 0,
             length: int = -1) -> Optional[FileSegment]:
  """Read file segment.

  Args:
    file_url: file URL
    offset: starting position (defaults to start of file)
    length: number of bytes to read (defaults to rest of file)
  Returns:
    file segment containing lines of content and metadata
  """
  with OpenFile(file_url) as stream:
    stream.seek(offset)
    data = stream.read(length)
    return FileSegment(offset, data.splitlines(True)) if data else None


def TailFile(file_url: str, length: int) -> Optional[FileSegment]:
  """Read file segment from end of file.

  Args:
    file_url: file URL
    length: number of bytes to read
  Returns:
    file segment containing lines of content and metadata
  """
  handle = FileHandle.Get(file_url)
  info = handle.Info()
  if info is None:
    return None
  total_size = info.total_size

  offset = max(0, total_size - length)
  with handle.Open() as stream:
    stream.seek(offset)
    data = stream.read()
    return FileSegment(offset, data.splitlines(True)) if data else None


def DownloadFile(
    file_url: str,
    offset: int = 0,
    url_opener: Optional[urllib.request.OpenerDirector] = None
) -> Iterator[FileChunk]:
  """Download a file.

  Args:
    file_url: file URL
    offset: byte offset to read from
    url_opener: optional, open director with handlers to open the url

  Yields:
    file chunk (chunk of data read, current position, total size in bytes)
  Raises:
    RuntimeError: if file not found
  """
  if url_opener:
    # Only HttpFileHandle support url opener
    handle = HttpFileHandle(file_url, url_opener=url_opener)
  else:
    handle = FileHandle.Get(file_url)
  info = handle.Info()
  if not info:
    raise RuntimeError('File %s not found' % file_url)
  total_size = info.total_size

  size = DOWNLOAD_BUFFER_SIZE
  with handle.Open() as stream:
    stream.seek(offset)
    while DOWNLOAD_BUFFER_SIZE <= size:
      # Read/write until EOF (downloaded size smaller than requested size)
      logging.debug('Downloading %s-%s', offset,
                    offset + DOWNLOAD_BUFFER_SIZE - 1)
      data = stream.read(DOWNLOAD_BUFFER_SIZE)
      size = len(data)
      offset += size
      yield FileChunk(data=data, offset=offset, total_size=total_size)


def GetTestSuiteInfo(file_obj: BinaryIO) -> Optional[TestSuiteInfo]:
  """Get the test package information.

  Args:
    file_obj: XTS zip file-like object.
  Returns:
    package_info dictionary
  """
  try:
    zf = zipfile.ZipFile(file_obj)
    for file_name in zf.namelist():
      # Find a tradefed jar file inside the test package zip.
      if file_name.endswith('-tradefed.jar'):
        jar = zipfile.ZipFile(io.BytesIO(zf.read(file_name)))
        jar_info = jar.NameToInfo.get('test-suite-info.properties')
        if not jar_info:
          continue  # Test suite information not found, skip.
        # Parse test suite information.
        suite_info = {}
        for line in jar.open(jar_info):
          line = line.decode()
          if not line or line.startswith('#') or '=' not in line:
            continue
          key, value = line.split('=', 1)
          suite_info[key.strip()] = value.strip()
        return TestSuiteInfo(build_number=suite_info.get('build_number'),
                             target_architecture=suite_info.get('target_arch'),
                             name=suite_info.get('name'),
                             fullname=suite_info.get('fullname'),
                             version=suite_info.get('version'))
  except Exception:  
    logging.exception('Failed to get test suite info')
  return None


def GetTestModuleInfos(
    file_obj: BinaryIO, module_config_pattern: str) -> List[TestModuleInfo]:
  """Finds test module infos from a test package zip.

  Args:
    file_obj: a file object for a test package zip.
    module_config_pattern: a pattern for module config files.
  Returns:
    A list of test module infos.
  """
  infos = []
  zf = zipfile.ZipFile(file_obj)
  r = re.compile(module_config_pattern)
  for file_name in zf.namelist():
    if not r.match(file_name):
      continue
    name = pathlib.Path(file_name).stem
    infos.append(TestModuleInfo(name=name))
  return infos


class FileHandleMediaUpload(apiclient.http.MediaIoBaseUpload):
  """MediaUpload which uploads a file handle without streaming."""

  def __init__(self,
               handle: FileHandle,
               chunksize: int = UPLOAD_BUFFER_SIZE,
               resumable: bool = False):
    info = handle.Info()
    mimetype = info.content_type if info else None
    super(FileHandleMediaUpload, self).__init__(
        fd=handle.Open(),
        mimetype=mimetype or 'application/octet-stream',
        chunksize=chunksize,
        resumable=resumable)

  def has_stream(self):
    # Disable streaming to issue a single request per chunk.
    return False
