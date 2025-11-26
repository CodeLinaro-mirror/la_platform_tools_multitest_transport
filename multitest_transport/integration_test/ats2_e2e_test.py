# Copyright 2025 Google LLC
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

"""MTT end-to-end tests."""
import logging
import os
import socket
import time

from absl import flags
from absl.testing import absltest


from multitest_transport.integration_test import integration_util

TEST_DATA_DIR = os.path.join(os.path.dirname(__file__), 'test_data')

FLAGS = flags.FLAGS
flags.DEFINE_string('serial_number', None, 'Device serial number')
flags.mark_flag_as_required('serial_number')
flags.DEFINE_string('architecture', 'arm', 'Device architecture (arm or x86)')


# TODO: Replace /url with ?alt=media when it works
_ARTIFACTS_DOWNLOAD_URL = (
    'https://www.googleapis.com/android/internal/build/'
    'v3/builds/%s/%s/attempts/latest/artifacts/%s/url'
)
_BUILD_ID = '13281750'
_BUILD_TARGET = 'aosp_cf_x86_64_phone-trunk_staging-userdebug'
_CVD_HOST_PACKAGE_URL = _ARTIFACTS_DOWNLOAD_URL % (
    _BUILD_ID,
    _BUILD_TARGET,
    'cvd-host_package.tar.gz',
)
_IMG_ZIP_URL = _ARTIFACTS_DOWNLOAD_URL % (
    _BUILD_ID,
    _BUILD_TARGET,
    f'aosp_cf_x86_64_phone-img-{_BUILD_ID}.zip',
)
_ACLOUD_PREBUILT_URL = _ARTIFACTS_DOWNLOAD_URL % (
    _BUILD_ID,
    _BUILD_TARGET,
    'acloud_prebuilt',
)
_CTS_FILE_NAME = (
    'android-cts-git_24Q3-release-test_suites_x86_64-11835886-trimmed.zip'
)


class E2eIntegrationTest(integration_util.DockerContainerTest):
  """Tests that TF is running and can handle test run information from MTT."""

  @classmethod
  def GetContainer(cls, container_id=None):
    """Factory method to construct a container that supports virtualization."""
    return integration_util.MttContainer(
        max_local_virtual_devices=1, ats2=True, container_id=container_id
    )

  @classmethod
  def setUpClass(cls):
    super(E2eIntegrationTest, cls).setUpClass()
    # Import additional configurations for end-to-end testing.
    config_file = os.path.join(TEST_DATA_DIR, 'e2e_test_config.yaml')
    with open(config_file) as f:
      cls.container.ImportConfig(f.read())
    cls.container.Exec(
        'wget', '--retry-connrefused', '-O', '/data/img.zip', _IMG_ZIP_URL
    )
    cls.container.Exec(
        'wget',
        '--retry-connrefused',
        '-O',
        '/data/cvd.tar.gz',
        _CVD_HOST_PACKAGE_URL,
    )
    cts_file = os.path.join(
        TEST_DATA_DIR,
        _CTS_FILE_NAME,
    )
    cls.container.CopyFile(cts_file, '/data/android-cts.zip')

  def _GetOutputDir(self, test_run):
    """Returns the path to a test run's output directory."""
    attempt = self.container.GetAttempts(test_run['request_id'])[-1]
    return '/data/app_default_bucket/test_runs/%s/output/%s/%s/' % (
        test_run['id'],
        attempt['request_id'],
        attempt['command_id'],
    )

  def _AssertFileExists(self, path):
    """Checks if a path (optionally with wildcards) matches any files."""
    # ls will return a non-zero exit code if no matching file(s) found
    self.container.Exec('bash', '-c', 'ls ' + path)

  def _GetLocalDeviceSerial(self, serial):
    if ':' in serial:
      return serial.split(':', 2)[1]
    return serial

  @staticmethod
  def _GetGlobalDeviceSerial(serial):
    """Combines the host name and the device serial."""
    return socket.gethostname() + ':' + serial

  def testCtsSingleModule_withLocalVirtualDevice(self):
    """Tests executing a test on a local virtual device."""
    test_run_id = self.container.ScheduleTestRun(
        self._GetGlobalDeviceSerial('local-virtual-device-0'),
        test_id='android.cts.10_0.arm',
        before_device_action_ids=['lvd_setup', 'cts_virtual_device_setup'],
        extra_args='-m CtsUsbTests',  # arbitrary small module
        test_resource_objs=[
            {
                'name': 'device',
                'url': 'file:///data/img.zip',
                'decompress': True,
                'decompress_dir': 'lvd-images',
            },
            {
                'name': 'cvd-host_package.tar.gz',
                'url': 'file:///data/cvd.tar.gz',
                'decompress': True,
                'decompress_dir': 'lvd-tools',
            },
            {
                'name': 'acloud',
                'url': 'file:///bin/acloud_prebuilt',
            },
            {
                'name': 'android-cts.zip',
                'url': 'file:///data/android-cts.zip',
            },
        ],
    )['id']
    self.container.WaitForState(test_run_id, 'COMPLETED', timeout=20 * 60)
    # Verify that the tests were executed (after waiting for result processing).
    time.sleep(10)
    test_run = self.container.GetTestRun(test_run_id)
    self.assertGreater(int(test_run['total_test_count']), 0)
    self.assertEqual(int(test_run['failed_test_count']), 0)
    self.container.DumpLogs()
    output_dir = self._GetOutputDir(test_run)
    self._AssertFileExists(output_dir + 'FILES')
    self._AssertFileExists(output_dir + 'test_result.xml')
    self._AssertFileExists(output_dir + 'test_result.pb')

  # TODO: Add tests for other test types after upgrading the
  # virtual device launched by kokoro to a newer version that is compatible
  # with CTS 15.


if __name__ == '__main__':
  logging.basicConfig(level=logging.DEBUG)
  absltest.main()
