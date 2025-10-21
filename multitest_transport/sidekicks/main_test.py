"""Tests for sidekicks."""
from unittest import mock

from absl.testing import absltest
import webtest


from multitest_transport.sidekicks import main
from multitest_transport.test_scheduler import download_util
from multitest_transport.util import analytics
from multitest_transport.util import tfc_client
from tradefed_cluster import api_messages


class MainTest(absltest.TestCase):
  """Unit test for main."""

  def setUp(self):
    super(MainTest, self).setUp()
    self.testapp = webtest.TestApp(main.APP)

  @mock.patch.object(tfc_client, 'ListDevices')
  @mock.patch.object(analytics, 'Log')
  def testHeartbeatSenderWithNoDevices(self, mock_log, mock_list_devices):
    mock_list_devices.return_value = None
    response = self.testapp.get('/sidekicks/heartbeat_sender')
    self.assertEqual('200 OK', response.status)
    self.assertEqual(mock_log.call_count, 3)

  @mock.patch.object(tfc_client, 'ListDevices')
  @mock.patch.object(analytics, 'Log')
  def testHeartbeatSenderWithMultipleWorkers(self, mock_log, mock_list_devices):
    device_1 = api_messages.DeviceInfo(hostname='worker_1.com')
    device_2 = api_messages.DeviceInfo(hostname='worker_2.com')
    device_infos = [device_1, device_2]
    mock_list_devices.return_value = api_messages.DeviceInfoCollection(
        device_infos=device_infos)
    response = self.testapp.get('/sidekicks/heartbeat_sender')
    self.assertEqual('200 OK', response.status)
    self.assertEqual(mock_log.call_count, 5)

  @mock.patch.object(download_util, 'CleanTestResourceCache')
  def testTestResourceCacheCleaner(self, mock_clean_test_resource_cache):
    response = self.testapp.get('/sidekicks/test_resource_cache_cleaner')
    self.assertEqual('200 OK', response.status)
    self.assertTrue(mock_clean_test_resource_cache.called)

  @mock.patch.object(download_util, 'ReleaseDownloadLocks')
  def testTestResourceTrackerCleaner(self, mock_release_download_locks):
    response = self.testapp.get('/sidekicks/test_resource_tracker_cleaner')
    self.assertEqual('200 OK', response.status)
    self.assertTrue(mock_release_download_locks.called)

  @mock.patch('multitest_transport.models.ndb_models.ndb.delete_multi')
  @mock.patch(
      'multitest_transport.models.ndb_models.TestResourceMetadata.query'
  )
  def testTestResourceMetadataCleaner(self, mock_query, mock_delete_multi):
    response = self.testapp.get('/sidekicks/test_resource_metadata_cleaner')
    self.assertEqual('200 OK', response.status)
    self.assertTrue(mock_query.called)
    self.assertTrue(mock_delete_multi.called)


if __name__ == '__main__':
  absltest.main()
