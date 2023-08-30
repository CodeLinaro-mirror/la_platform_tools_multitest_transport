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

"""Utilities for downloading test resources."""
from concurrent import futures
import datetime
import hashlib
import logging
import time

from tradefed_cluster import common
from tradefed_cluster.util import ndb_shim as ndb


from multitest_transport.models import build
from multitest_transport.models import event_log
from multitest_transport.models import ndb_models
from multitest_transport.util import file_util

# Directory in which test resources are cached
TEST_RESOURCE_CACHE_DIR = 'test_resources'
# Max number of workers used when downloading resources
MAX_WORKERS = 12
# Max idle time for test resource downloads (will be cancelled if exceeded)
MAX_DOWNLOAD_IDLE_TIME = datetime.timedelta(minutes=10)
# Max test resource cache access time (will be deleted if exceeded)
MAX_CACHE_ACCESS_TIME = datetime.timedelta(days=7)


def GetCacheUrl(url: str = '') -> str:
  """Get the cache URL for a remote resource.

  Args:
    url: a resource URL.
  Returns:
    a cache URL.
  """
  if url:
    encoded_url = hashlib.sha256(url.encode()).hexdigest()
  else:
    encoded_url = ''
  return file_util.GetAppStorageUrl([TEST_RESOURCE_CACHE_DIR, encoded_url])


def DownloadResources(urls, test_run=None):
  """Downloads multiple resources to the cache in parallel.

  Waits for all downloads to complete (regardless of success or failure) before
  returning. If an error occurs, the first encountered exception will be raised.

  Args:
    urls: list of resource URLs
    test_run: optional related test run
  Returns:
    dict of resource URL to cache URL
  """
  with futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
    future_url_map = {}
    for url in urls:
      future = executor.submit(
          _DownloadResourceInWorker, url, test_run=test_run)
      future_url_map[future] = url
    # Process cache URLs as the tasks complete
    cache_url_dict = {}
    # TODO: Refactor (i.e. add timeout) after Python 3 migration
    for future in futures.as_completed(future_url_map):
      url = future_url_map[future]
      cache_url = future.result()
      cache_url_dict[url] = cache_url
    return cache_url_dict


def _DownloadResourceInWorker(url, test_run=None):
  """Download resource in a worker thread after wrapping in an NDB context."""
  return ndb.with_ndb_context(DownloadResource)(url, test_run=test_run)


def DownloadResource(url, test_run=None):
  """Download resource to the cache.

  If a url starts with mtt://, this function tries to download a file from
  one of registered build channel via a corresponding build provider. Otherwise,
  it will try to use a file_util.FileHandle to download the file.

  Args:
    url: resource URL.
    test_run: optional related test run
  Returns:
    a cache URL.
  """
  if url.startswith('file://'):
    return url  # Skip downloading local files

  logging.info('Downloading resource %s', url)
  downloader = TestResourceDownloader(url)
  # Check if resource already cached
  if downloader.IsCached():
    logging.info('Resource already cached: %s', downloader.cache_url)
    return downloader.cache_url
  # Download resource
  downloader.Download()

  if test_run:
    event_log.Info(test_run, 'Downloaded resource %s' % url)
  return downloader.cache_url


class TestResourceDownloader(object):
  """Wrapper around a test resource download."""

  def __init__(self, url):
    """Constructs a download context for a given resource URL."""
    self.url = url
    self.cache_url = GetCacheUrl(url)
    build_channel, build_item_path = build.FindBuildChannel(url)
    if not build_channel:
      # URL does not match any build channel, use default download context
      self.source_url = url
      self.download_fn = file_util.DownloadFile
      self.source_info = file_util.FileHandle.Get(url).Info()
      return
    # Corresponding build channel found, use its download context
    self.source_url = build_item_path
    self.download_fn = build_channel.DownloadFile
    build_item = build_channel.GetBuildItem(build_item_path)
    if build_item:
      self.source_info = file_util.FileInfo(
          url=self.url,
          total_size=build_item.size,
          timestamp=build_item.timestamp)

  def IsCached(self):
    """Checks whether the resource was already downloaded and cached."""
    if (not self.source_info or not self.source_info.timestamp or
        not self.source_info.total_size):
      return False  # Source file not found or missing metadata
    cache_info = file_util.FileHandle.Get(self.cache_url).Info()
    if not cache_info or not cache_info.timestamp or not cache_info.total_size:
      return False  # Cached file not found or missing metadata
    return (cache_info.timestamp >= self.source_info.timestamp and
            cache_info.total_size == self.source_info.total_size)

  def Download(self):
    """Download file or wait for another thread to download it."""
    if self._TryAcquireDownloadLock():
      self._PerformDownload()
    else:
      self._WaitForDownload()

  @ndb.transactional()
  def _TryAcquireDownloadLock(self):
    """Attempt to acquire a download lock.

    Either fetch an existing download tracker (lock not acquired and current
    thread should wait for download to complete), or create a new download
    tracker (lock acquired and current thread should perform the download).

    Returns:
      True if lock was acquired
    """
    tracker = ndb_models.TestResourceTracker.get_by_id(self.url)
    if tracker and not tracker.error:
      return False
    tracker = ndb_models.TestResourceTracker(id=self.url)
    tracker.put()
    return True

  def _WaitForDownload(self, poll_interval=10):
    """Wait for a download to complete."""
    logging.info('Waiting for download of %s to complete', self.url)
    while not self._IsDownloadComplete():
      time.sleep(poll_interval)

  def _IsDownloadComplete(self):
    """Check whether a download has completed."""
    return self._GetTracker().completed

  def _PerformDownload(self):
    """Executes the download and updates the download progress."""
    try:
      logging.info('Starting download of %s', self.url)
      with file_util.FileHandle.Get(self.cache_url).Open(mode='w') as dest:
        for chunk in self.download_fn(self.source_url):
          dest.write(chunk.data)
          progress = float(chunk.offset) / float(chunk.total_size)
          self._UpdateTracker(progress)
      logging.info('Downloading %s completed', self.url)
      # Mark download as completed
      self._UpdateTracker(1.0, completed=True)
    except Exception as e:  
      logging.error('Failed to download %s: %s', self.url, e)
      self._UpdateTracker(0.0, error=str(e))
      raise

  @ndb.transactional()
  def _UpdateTracker(self, download_progress, completed=False, error=None):
    """Update an existing download tracker."""
    tracker = self._GetTracker()
    tracker.download_progress = download_progress
    tracker.completed = completed
    tracker.error = error
    tracker.put()

  def _GetTracker(self):
    """Locate a download tracker and check its validity."""
    tracker = ndb_models.TestResourceTracker.get_by_id(self.url)
    if tracker is None:
      # Download tracker unexpectedly not found
      raise RuntimeError('Test resource tracker %s not found' % self.url)
    if tracker.error:
      # Error was encountered during download
      raise RuntimeError(tracker.error)
    return tracker


def ReleaseDownloadLocks(min_update_time=None):
  """Deletes resource trackers to release the download locks.

  Args:
    min_update_time: latest update timestamp to delete, or None to delete all
  """
  if min_update_time is None:
    min_update_time = datetime.datetime.utcnow()
  logging.info('Cleaning up resource trackers not updated since %s (UTC)',
               min_update_time)
  keys_to_delete = ndb_models.TestResourceTracker.query(
      ndb_models.TestResourceTracker.update_time < min_update_time).fetch(
          keys_only=True)
  ndb.delete_multi(keys_to_delete)


def TestResourceTrackerCleaner():
  """Request handler which periodically releases idle resource trackers."""
  min_update_time = datetime.datetime.utcnow() - MAX_DOWNLOAD_IDLE_TIME
  ReleaseDownloadLocks(min_update_time=min_update_time)
  return common.HTTP_OK


def CleanTestResourceCache(min_access_time=None):
  """Delete files from the test resource cache.

  Args:
    min_access_time: latest test run timestamp, or None to delete all
  """
  if min_access_time is None:
    min_access_time = datetime.datetime.utcnow()
  logging.info('Cleaning up test resources not used since %s (UTC)',
               min_access_time)
  # Find recently used test resources
  query = ndb_models.TestRun.query(
      ndb_models.TestRun.create_time >= min_access_time)
  recently_used_resources = []
  for test_run in query:
    recently_used_resources.extend(test_run.test_resources)
  files_to_keep = set([GetCacheUrl(r.url) for r in recently_used_resources])
  # Iterate over files in the test resource cache, deleting those that have not
  # been updated or used recently
  cache_root = GetCacheUrl()
  cache_files = file_util.FileHandle.Get(cache_root).ListFiles() or []
  for cache_file in cache_files:
    if not cache_file.is_file:
      continue  # skip directories
    if cache_file.timestamp > min_access_time:
      continue  # skip recently updated files
    if cache_file.url in files_to_keep:
      continue  # skip recently used files
    logging.debug('Deleting %s', cache_file.url)
    file_util.FileHandle.Get(cache_file.url).Delete()


def TestResourceCacheCleaner():
  """Request handler which periodically deletes unused cached test resources."""
  min_access_time = datetime.datetime.utcnow() - MAX_CACHE_ACCESS_TIME
  CleanTestResourceCache(min_access_time=min_access_time)
  return common.HTTP_OK
