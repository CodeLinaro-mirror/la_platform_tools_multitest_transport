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

"""Tests for analytics_uploader."""
import json
from unittest import mock
import urllib.parse
import urllib.request

from absl.testing import absltest
from tradefed_cluster import testbed_dependent_test


from multitest_transport.models import ndb_models
from multitest_transport.util import analytics_uploader
from multitest_transport.util import env


class AnalyticsUploaderTest(testbed_dependent_test.TestbedDependentTest):

  def setUp(self):
    super(AnalyticsUploaderTest, self).setUp()
    env.VERSION = 'version'
    env.IS_GOOGLE = True
    analytics_uploader._UPLOAD_ERROR_COUNT.value = 0
    analytics_uploader._TRACKING_ID = 'tracking_id'
    private_node_config = ndb_models.GetPrivateNodeConfig()
    private_node_config.server_uuid = 'server'
    private_node_config.metrics_enabled = True
    private_node_config.gms_client_id = 'test_user_tag'
    private_node_config.put()

  def assertValidEvent(self, data, server, category, action):
    """Confirms the base event information is present."""
    self.assertListEqual(['client_id', 'events'], list(data))
    self.assertEqual(server, data['client_id'])
    # Assert event
    self.assertLen(data['events'], 1)
    self.assertListEqual(['name', 'params'], list(data['events'][0]))
    self.assertEqual(action, data['events'][0]['name'])
    expected = {
        'event_category': category,
        'app_version': env.VERSION,
        'is_google': True,
        'user_tag': 'test_user_tag',
    }
    self.assertEqual(
        data['events'][0]['params'], {**data['events'][0]['params'], **expected}
    )

  @mock.patch.object(urllib.request, 'urlopen')
  def testUploadEvent(self, mock_urlopen):
    """Tests that events are sent to GA when metrics are enabled."""
    uploaded = analytics_uploader._UploadEvent('category', 'action')
    self.assertTrue(uploaded)
    request = mock_urlopen.call_args[0][0]
    data = json.loads(request.data.decode())
    self.assertEqual(analytics_uploader._GA_ENDPOINT, request.get_full_url())
    self.assertValidEvent(data, 'server', 'category', 'action')

  @mock.patch.object(urllib.request, 'urlopen')
  def testUploadEvent_disabled(self, mock_urlopen):
    """Tests that events are not sent when metrics are disabled."""
    private_node_config = ndb_models.GetPrivateNodeConfig()
    private_node_config.metrics_enabled = False
    private_node_config.put()
    uploaded = analytics_uploader._UploadEvent('category', 'action')
    self.assertFalse(uploaded)
    mock_urlopen.assert_not_called()

  @mock.patch.object(urllib.request, 'urlopen')
  def testUploadEvent_tooManyErrors(self, mock_urlopen):
    """Tests that events are not sent after too many upload errors."""
    mock_urlopen.side_effect = RuntimeError()
    # Should fail up to the maximum consecutive error count
    for _ in range(analytics_uploader.MAX_CONSECUTIVE_UPLOAD_ERRORS):
      with self.assertRaises(RuntimeError):
        analytics_uploader._UploadEvent('category', 'action')
    # Next calls will be ignored (metrics upload disabled)
    uploaded = analytics_uploader._UploadEvent('category', 'action')
    self.assertFalse(uploaded)

  @mock.patch.object(urllib.request, 'urlopen')
  def testUploadEvent_complex(self, mock_urlopen):
    """Tests complex events are sent to GA correctly."""
    uploaded = analytics_uploader._UploadEvent(
        'category',
        'action',
        test_name='name',
        test_version='version',
        state='COMPLETED',
        is_rerun=True,
        operation_mode='on_premise',
        worker_id='worker_id',
        duration_seconds=0,
        device_count=1,
        attempt_count=2,
        failed_module_count=3,
        test_count=4,
        failed_test_count=5,
        total_disk_size_byte=100000,
        used_disk_size_byte=40000,
        free_disk_size_byte=60000,
        worker_count=2,
        # ignored params
        none=None,
        unknown='unknown',
    )
    self.assertTrue(uploaded)
    request = mock_urlopen.call_args[0][0]
    data = json.loads(request.data.decode())
    self.assertEqual(analytics_uploader._GA_ENDPOINT, request.get_full_url())
    self.assertValidEvent(data, 'server', 'category', 'action')
    self.assertDictEqual(
        {
            'event_category': 'category',
            'app_version': env.VERSION,
            'is_google': True,
            'user_tag': 'test_user_tag',
            'test_name': 'name',
            'test_version': 'version',
            'state': 'COMPLETED',
            'is_rerun': True,
            'operation_mode': 'on_premise',
            'worker_id': 'worker_id',
            'duration_seconds': 0,
            'device_count': 1,
            'attempt_count': 2,
            'failed_module_count': 3,
            'test_count': 4,
            'failed_test_count': 5,
            'total_disk_size_byte': 100000,
            'used_disk_size_byte': 40000,
            'free_disk_size_byte': 60000,
            'worker_count': 2,
        },
        data['events'][0]['params'],
    )

  @mock.patch.object(urllib.request, 'urlopen')
  def testUploadEvent_emptyGmsClientId(self, mock_urlopen):
    """Tests that events are sent to GA without GMS client ID."""
    private_node_config = ndb_models.GetPrivateNodeConfig()
    private_node_config.gms_client_id = None
    private_node_config.put()
    uploaded = analytics_uploader._UploadEvent('category', 'action')
    self.assertTrue(uploaded)
    request = mock_urlopen.call_args[0][0]
    data = json.loads(request.data.decode())

    self.assertNotIn('user_tag', data['events'][0]['params'])


if __name__ == '__main__':
  absltest.main()
