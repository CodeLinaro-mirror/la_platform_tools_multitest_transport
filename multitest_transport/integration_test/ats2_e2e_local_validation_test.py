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
flags.DEFINE_string('xts_file', None, 'XTS file to use')
flags.mark_flag_as_required('xts_file')


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
    if cls.container.FileExists('/data/local_file_store/android-cts.zip'):
      logging.info('android-cts.zip already exists')
    else:
      if not os.path.exists(FLAGS.xts_file):
        raise FileNotFoundError(f'XTS file not found: {FLAGS.xts_file}')
      logging.info(
          'Copying xts file %s to /data/local_file_store', FLAGS.xts_file
      )
      cls.container.CopyFile(
          FLAGS.xts_file, '/data/local_file_store/android-cts.zip'
      )

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

  def testRunCtsAndMctsModules(self):
    """Tests executing a CTS module successfully."""
    test_run_id = self.container.ScheduleTestRun(
        FLAGS.serial_number,
        test_id='android.cts.15_0',
        extra_args=(
            '--include-filter CtsUsbTests --include-filter'
            ' CtsSdkExtensionsTestCases'
        ),
        test_resource_objs=[{
            'name': 'android-cts.zip',
            'url': 'file:///data/local_file_store/android-cts.zip',
            'decompress': True,
            'mount_zip': True,
        }],
        enable_xts_dynamic_download=True,
    )['id']
    self.container.WaitForState(test_run_id, 'COMPLETED', timeout=30 * 60)
    # Verify that the tests were executed (after waiting for result processing).
    time.sleep(10)
    test_run = self.container.GetTestRun(test_run_id)
    self.assertGreater(int(test_run['total_test_count']), 0)
    self.assertEqual(int(test_run['failed_test_count']), 0)
    # Verify that the test output exists
    output_dir = self._GetOutputDir(test_run)
    self._AssertFileExists(output_dir + '*.zip')  # Test results zip file
    test_result_xml_path = output_dir + 'test_result.xml'
    self._AssertFileExists(test_result_xml_path)
    test_result_xml_content = self.container.ReadFile(test_result_xml_path)

    # If the device supports armv7 and armv8, the modules count will be 4.
    # Otherwise, the modules count will be 2.
    self.assertTrue(
        ('modules_done="2" modules_total="2"' in test_result_xml_content)
        or ('modules_done="4" modules_total="4"' in test_result_xml_content),
        'Neither "modules_done="2" modules_total="2"" nor "modules_done="4"'
        ' modules_total="4"" found in test_result.xml',
    )
    self.assertIn('<Module name="CtsUsbTests"', test_result_xml_content)
    self.assertIn(
        '<Module name="CtsSdkExtensionsTestCases"', test_result_xml_content
    )
    self._AssertFileExists(output_dir + 'test_result_failures_suite.html')

  def testWithRetryAttempt(self):
    """Tests executing a test that have multiple attempts because test has failure."""
    test_run_id = self.container.ScheduleTestRun(
        FLAGS.serial_number,
        test_id='android.cts.15_0',
        extra_args='-m CtsNetTestCasesLegacyApi22',
        test_resource_objs=[{
            'name': 'android-cts.zip',
            'url': 'file:///data/local_file_store/android-cts.zip',
            'decompress': True,
            'mount_zip': True,
        }],
        enable_xts_dynamic_download=False,
        max_retry_on_test_failures=1,
    )['id']
    self.container.WaitForState(test_run_id, 'COMPLETED', timeout=30 * 60)
    # Verify that the tests were executed (after waiting for result processing).
    time.sleep(10)
    test_run = self.container.GetTestRun(test_run_id)
    attempts = self.container.GetAttempts(test_run['request_id'])
    self.assertLen(attempts, 2)
    self.assertGreater(int(test_run['total_test_count']), 0)
    self.assertGreater(int(test_run['failed_test_count']), 0)
    # Verify that the test output exists
    output_dir = self._GetOutputDir(test_run)
    self._AssertFileExists(output_dir + '*.zip')  # Test results zip file
    test_result_xml_path = output_dir + 'test_result.xml'
    self._AssertFileExists(test_result_xml_path)
    test_result_xml_content = self.container.ReadFile(test_result_xml_path)
    self.assertIn('<Metric key="cached">true</Metric>', test_result_xml_content)
    self._AssertFileExists(output_dir + 'test_result_failures_suite.html')

  def testRunCtsRerunWithCachedResult(self):
    """Tests that rerunning a CTS test run uses cached results."""
    test_id = 'android.cts.15_0'
    extra_args = '-m CtsNetTestCasesLegacyApi22'
    test_resource_objs = [{
        'name': 'android-cts.zip',
        'url': 'file:///data/local_file_store/android-cts.zip',
        'decompress': True,
        'mount_zip': True,
    }]

    # 1. Run the test with zero retry count.
    test_run_id_1 = self.container.ScheduleTestRun(
        FLAGS.serial_number,
        test_id=test_id,
        extra_args=extra_args,
        test_resource_objs=test_resource_objs,
        enable_xts_dynamic_download=False,
        max_retry_on_test_failures=0,
    )['id']
    self.container.WaitForState(test_run_id_1, 'COMPLETED', timeout=30 * 60)

    # 2. Rerun this first test run using rerun_context.
    test_run_id_2 = self.container.ScheduleTestRun(
        FLAGS.serial_number,
        test_id=test_id,
        extra_args=extra_args,
        test_resource_objs=test_resource_objs,
        enable_xts_dynamic_download=False,
        rerun_context={'test_run_id': test_run_id_1},
    )['id']
    self.container.WaitForState(test_run_id_2, 'COMPLETED', timeout=30 * 60)

    # Verify that the second run used cached results.
    time.sleep(10)
    test_run_2 = self.container.GetTestRun(test_run_id_2)
    output_dir = self._GetOutputDir(test_run_2)
    test_result_xml_path = output_dir + 'test_result.xml'
    self._AssertFileExists(test_result_xml_path)
    test_result_xml_content = self.container.ReadFile(test_result_xml_path)
    self.assertIn('<Metric key="cached">true</Metric>', test_result_xml_content)

  def testRunCtsModuleWithDeviceAction(self):
    """Tests executing a CTS module with a device action."""
    test_run_id = self.container.ScheduleTestRun(
        FLAGS.serial_number,
        test_id='android.cts.15_0',
        extra_args='-m CtsAccelerationTestCases',
        test_resource_objs=[{
            'name': 'android-cts.zip',
            'url': 'file:///data/local_file_store/android-cts.zip',
            'decompress': True,
            'mount_zip': True,
        }],
        enable_xts_dynamic_download=False,
        before_device_action_ids=['connect_wifi'],
    )['id']
    self.container.WaitForState(test_run_id, 'ERROR', timeout=30 * 60)
    # Verify that the tests were executed (after waiting for result processing).
    time.sleep(10)
    test_run = self.container.GetTestRun(test_run_id)
    self.assertEqual(test_run['error_reason'], 'TRADEFED_INVOCATION_ERROR')

  def testRunCtsConcurrentRuns(self):
    """Tests scheduling two concurrent CTS runs.

    They compete for the same device, and one will fail with an allocation
    failure.
    """
    test_run_id_1 = self.container.ScheduleTestRun(
        FLAGS.serial_number,
        test_id='android.cts.15_0',
        extra_args='-m CtsAccelerationTestCases',
        test_resource_objs=[{
            'name': 'android-cts.zip',
            'url': 'file:///data/local_file_store/android-cts.zip',
            'decompress': True,
            'mount_zip': True,
        }],
        enable_xts_dynamic_download=False,
        queue_timeout_seconds=60,  # Allow some time for the first run to start.
    )['id']
    logging.info('Scheduled first test run with ID: %s', test_run_id_1)

    test_run_id_2 = self.container.ScheduleTestRun(
        FLAGS.serial_number,
        test_id='android.cts.15_0',
        extra_args='-m CtsAccelerationTestCases',
        test_resource_objs=[{
            'name': 'android-cts.zip',
            'url': 'file:///data/local_file_store/android-cts.zip',
            'decompress': True,
            'mount_zip': True,
        }],
        enable_xts_dynamic_download=False,
        queue_timeout_seconds=60,  # Allow some time for the first run to start.
    )['id']
    logging.info('Scheduled second test run with ID: %s', test_run_id_2)
    self.container.WaitForFinalState(test_run_id_2, timeout=30 * 60)
    self.container.WaitForFinalState(test_run_id_1, timeout=30 * 60)
    logging.info('Both test runs completed')
    time.sleep(10)  # Wait for result processing.

    test_run_1 = self.container.GetTestRun(test_run_id_1)
    test_run_2 = self.container.GetTestRun(test_run_id_2)

    # Check that one run completed and the other failed with ALLOCATION_TIMEOUT.
    results = [test_run_1, test_run_2]
    completed_runs = [r for r in results if r['state'] == 'COMPLETED']
    error_runs = [r for r in results if r['state'] == 'ERROR']

    self.assertLen(completed_runs, 1, 'Exactly one run should be COMPLETED.')
    self.assertLen(error_runs, 1, 'Exactly one run should be ERROR.')

    completed_run = completed_runs[0]
    error_run = error_runs[0]

    self.assertEqual(error_run['error_reason'], 'OMNILAB_ERROR')
    self.assertStartsWith(
        error_run['error_message'],
        'Test failed to allocate devices. Diagnostic result:'
        ' [MH|CUSTOMER_ISSUE|CLIENT_JR_ALLOC_USER_CONFIG_ERROR|49463]:',
    )

    # Verify the completed test run.
    self.assertGreater(int(completed_run['total_test_count']), 0)
    output_dir = self._GetOutputDir(completed_run)
    self._AssertFileExists(output_dir + '*.zip')
    self._AssertFileExists(output_dir + 'test_result.xml')


if __name__ == '__main__':
  logging.basicConfig(level=logging.DEBUG)
  absltest.main()
