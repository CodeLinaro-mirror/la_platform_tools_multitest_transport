# Copyright 2021 Google LLC
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

"""Tests for xts_result."""
import os

from absl.testing import absltest

from multitest_transport.util import xts_result

TEST_DATA_DIR = os.path.join(os.path.dirname(__file__), 'test_data')


class XtsResultTest(absltest.TestCase):

  def testSummary(self):
    with open(os.path.join(TEST_DATA_DIR, 'test_result.xml'), 'rb') as stream:
      test_results = xts_result.TestResults(stream)
      self.assertEqual(
          test_results.summary,
          xts_result.Summary(
              passed=12, failed=34, modules_done=56, modules_total=78))

  def testModules(self):
    with open(os.path.join(TEST_DATA_DIR, 'test_result.xml'), 'rb') as stream:
      modules = list(xts_result.TestResults(stream))
      self.assertEqual(
          modules[0],
          xts_result.Module(
              name='abi SimpleModule',
              complete=True,
              duration_ms=123,
              test_cases=[
                  xts_result.TestCase(
                      name='Passing#test',
                      status=xts_result.TestStatus.PASS,
                  )
              ],
          ))
      self.assertEqual(
          modules[1],
          xts_result.Module(
              name='abi ComplexModule',
              complete=True,
              duration_ms=456,
              test_cases=[
                  xts_result.TestCase(
                      name='Failing#test',
                      status=xts_result.TestStatus.FAIL,
                      error_message='Failure message',
                      stack_trace='Failure stacktrace'),
                  xts_result.TestCase(
                      name='Skipped#ignored',
                      status=xts_result.TestStatus.IGNORED,
                  ),
                  xts_result.TestCase(
                      name='Skipped#assumption',
                      status=xts_result.TestStatus.ASSUMPTION_FAILURE,
                      error_message='Assumption failure message',
                      stack_trace='Assumption failure stacktrace'),
              ],
          ))
      self.assertEqual(
          modules[2],
          xts_result.Module(
              name='abi IncompleteModule',
              complete=False,
              duration_ms=789,
              test_cases=[],
              error_message='Incomplete module message',
          ))

  def testModules_missingRuntime(self):
    with open(
        os.path.join(TEST_DATA_DIR, 'test_result_missing_runtime.xml'), 'rb'
    ) as stream:
      modules = list(xts_result.TestResults(stream))
      self.assertEqual(
          modules[0],
          xts_result.Module(
              name='arm64-v8a CtsUsbTests',
              complete=False,
              duration_ms=0,
              test_cases=[],
          ),
      )
      self.assertEqual(
          modules[1],
          xts_result.Module(
              name='arm64-v8a CtsSdkExtensionsTestCases',
              complete=True,
              duration_ms=389,
              test_cases=[
                  xts_result.TestCase(
                      name=(
                          'com.android.os.ext.SdkExtensionsTest#testZeroValues'
                      ),
                      status=xts_result.TestStatus.PASS,
                  ),
                  xts_result.TestCase(
                      name=(
                          'com.android.os.ext.SdkExtensionsTest#testExtensionAdServices'
                      ),
                      status=xts_result.TestStatus.PASS,
                  ),
                  xts_result.TestCase(
                      name=(
                          'com.android.os.ext.SdkExtensionsTest#testBadArgument'
                      ),
                      status=xts_result.TestStatus.PASS,
                  ),
                  xts_result.TestCase(
                      name=(
                          'com.android.os.ext.SdkExtensionsTest#testGetAllExtensionVersionsKeys'
                      ),
                      status=xts_result.TestStatus.PASS,
                  ),
                  xts_result.TestCase(
                      name=(
                          'com.android.os.ext.SdkExtensionsTest#testExtensionR'
                      ),
                      status=xts_result.TestStatus.PASS,
                  ),
                  xts_result.TestCase(
                      name=(
                          'com.android.os.ext.SdkExtensionsTest#testExtensionS'
                      ),
                      status=xts_result.TestStatus.PASS,
                  ),
                  xts_result.TestCase(
                      name=(
                          'com.android.os.ext.SdkExtensionsTest#testExtensionT'
                      ),
                      status=xts_result.TestStatus.PASS,
                  ),
                  xts_result.TestCase(
                      name=(
                          'com.android.os.ext.SdkExtensionsTest#testExtensionU'
                      ),
                      status=xts_result.TestStatus.PASS,
                  ),
                  xts_result.TestCase(
                      name=(
                          'com.android.os.ext.SdkExtensionsTest#testExtensionV'
                      ),
                      status=xts_result.TestStatus.PASS,
                  ),
              ],
          ),
      )


if __name__ == '__main__':
  absltest.main()
