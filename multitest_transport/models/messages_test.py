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

"""Unit tests for messages."""

from absl.testing import absltest
from tradefed_cluster import common
from tradefed_cluster import testbed_dependent_test


from multitest_transport.models import messages
from multitest_transport.models import ndb_models


class MessagesTest(testbed_dependent_test.TestbedDependentTest):

  def testConvertNameValuePairs(self):
    models = [ndb_models.NameValuePair(name='foo', value='BAR'),
              ndb_models.NameValuePair(name='bar', value='BAR'),
              ndb_models.NameValuePair(name='foo', value='FOO')]
    # removes duplicate keys
    expected = [messages.NameValuePair(name='foo', value='FOO'),
                messages.NameValuePair(name='bar', value='BAR')]

    actual = messages.ConvertNameValuePairs(models, messages.NameValuePair)
    self.assertEqual(expected, actual)

  def testConvertNameValuePairs_multi(self):
    models = [ndb_models.NameMultiValuePair(name='foo', values=['1', '2']),
              ndb_models.NameMultiValuePair(name='bar', values=['3', '4']),
              ndb_models.NameMultiValuePair(name='bar', values=['5', '6'])]
    # removes duplicate keys
    expected = [messages.NameMultiValuePair(name='foo', values=['1', '2']),
                messages.NameMultiValuePair(name='bar', values=['5', '6'])]

    actual = messages.ConvertNameValuePairs(models, messages.NameMultiValuePair)
    self.assertEqual(expected, actual)

  def assertSameNameValuePair(self, obj, msg):
    self.assertEqual(obj.name, msg.name)
    self.assertEqual(obj.value, msg.value)

  def assertSameTestResourceDef(self, obj, msg):
    self.assertIsInstance(obj, ndb_models.TestResourceDef)
    self.assertIsInstance(msg, messages.TestResourceDef)
    self.assertEqual(obj.name, msg.name)
    self.assertEqual(obj.default_download_url, msg.default_download_url)
    self.assertEqual(obj.decompress, msg.decompress)
    self.assertEqual(obj.decompress_dir, msg.decompress_dir)
    if obj.params and msg.params:
      self.assertEqual(obj.params.decompress_files, msg.params.decompress_files)
    else:
      self.assertIsNone(msg.params)
      self.assertIsNone(obj.params)

  def testConvert_TestResourceDef(self):
    obj = ndb_models.TestResourceDef(
        name='foo', default_download_url='bar', decompress=True,
        decompress_dir='dir',
        params=ndb_models.TestResourceParameters(decompress_files=['file']))
    msg = messages.TestResourceDef(
        name='foo', default_download_url='bar', decompress=True,
        decompress_dir='dir',
        params=messages.TestResourceParameters(decompress_files=['file']))
    self.assertSameTestResourceDef(
        obj, messages.Convert(obj, messages.TestResourceDef))
    self.assertSameTestResourceDef(
        messages.Convert(msg, ndb_models.TestResourceDef), msg)

    obj = ndb_models.TestResourceDef(name='foo')
    msg = messages.TestResourceDef(name='foo')
    self.assertSameTestResourceDef(
        obj, messages.Convert(obj, messages.TestResourceDef))
    self.assertSameTestResourceDef(
        messages.Convert(msg, ndb_models.TestResourceDef), msg)

  def assertSameTestRunParameter(self, obj, msg):
    self.assertEqual(
        obj.max_retry_on_test_failures, msg.max_retry_on_test_failures)
    self.assertEqual(
        obj.invocation_timeout_seconds, msg.invocation_timeout_seconds)
    self.assertEqual(
        obj.output_idle_timeout_seconds, msg.output_idle_timeout_seconds)
    self.assertEqual(
        obj.queue_timeout_seconds, msg.queue_timeout_seconds)

  def testConvert_TestRunParameter(self):
    obj = ndb_models.TestRunParameter(
        max_retry_on_test_failures=1,
        invocation_timeout_seconds=2,
        output_idle_timeout_seconds=3,
        queue_timeout_seconds=4)
    msg = messages.TestRunParameter(
        max_retry_on_test_failures=1,
        invocation_timeout_seconds=2,
        output_idle_timeout_seconds=3,
        queue_timeout_seconds=4)
    self.assertSameTestRunParameter(
        obj, messages.Convert(obj, messages.TestRunParameter))
    self.assertSameTestRunParameter(
        messages.Convert(msg, ndb_models.TestRunParameter), msg)

  def assertSameTest(self, obj, msg):
    self.assertEqual(obj.name, msg.name)
    self.assertEqual(obj.command, msg.command)
    for o, m in zip(obj.test_resource_defs, msg.test_resource_defs):
      self.assertSameTestResourceDef(o, m)
    for o, m in zip(obj.env_vars, msg.env_vars):
      self.assertSameNameValuePair(o, m)
    self.assertEqual(obj.output_file_patterns, msg.output_file_patterns)
    self.assertEqual(obj.setup_scripts, msg.setup_scripts)
    if msg.default_test_run_parameters is None:
      self.assertIsNone(obj.default_test_run_parameters)
    else:
      self.assertIsNotNone(obj.default_test_run_parameters)
      self.assertSameTestRunParameter(
          obj.default_test_run_parameters, msg.default_test_run_parameters)
    for o, m in zip(obj.build_attributes, msg.build_attributes):
      self.assertSameNameValuePair(o, m)

  def testConvert_Test(self):
    obj = ndb_models.Test(
        name='name',
        test_resource_defs=[
            ndb_models.TestResourceDef(name='foo', default_download_url='bar')
        ],
        command='command',
        env_vars=[
            ndb_models.NameValuePair(name='name', value='value'),
        ],
        output_file_patterns=['pattern_1', 'pattern_2'],
        setup_scripts=['script_1', 'script_2', 'script_3'],
        build_attributes=[
            ndb_models.NameValuePair(name='attr', value='value')
        ])
    msg = messages.Convert(obj, messages.Test)
    self.assertIsInstance(msg, messages.Test)
    self.assertSameTest(obj, msg)

    obj.default_test_run_parameters = ndb_models.TestRunParameter(
        max_retry_on_test_failures=1,
        invocation_timeout_seconds=2,
        output_idle_timeout_seconds=3,
        queue_timeout_seconds=4)
    msg = messages.Convert(obj, messages.Test)
    self.assertIsInstance(msg, messages.Test)
    self.assertSameTest(obj, msg)

  def testGetTestRunStateInfo_error(self):
    obj = ndb_models.TestRun(
        state=ndb_models.TestRunState.ERROR,
        error_reason='error')
    self.assertEqual('error', messages._GetTestRunStateInfo(obj))

  def testGetTestRunStateInfo_canceled(self):
    obj = ndb_models.TestRun(
        state=ndb_models.TestRunState.CANCELED,
        cancel_reason=common.CancelReason.INVALID_REQUEST)
    expected = ndb_models._TEST_RUN_CANCEL_REASON_MAP[
        common.CancelReason.INVALID_REQUEST]
    self.assertEqual(expected, messages._GetTestRunStateInfo(obj))

  def testGetTestRunStateInfo_downloading(self):
    obj = ndb_models.TestRun(
        state=ndb_models.TestRunState.PENDING,
        test_resources=[ndb_models.TestResourceObj(name='resource', url='url')])
    # resource tracker found with 50% progress
    tracker = ndb_models.TestResourceTracker(id='url', download_progress=0.5)
    tracker.put()
    expected = 'Downloading resource [50%]'
    self.assertEqual(expected, messages._GetTestRunStateInfo(obj))

  def testGetTestRunStateInfo_notDownloading(self):
    obj = ndb_models.TestRun(
        state=ndb_models.TestRunState.PENDING,
        # resource already has cache URL (already downloaded)
        test_resources=[ndb_models.TestResourceObj(name='resource', url='url',
                                                   cache_url='cache')])
    self.assertIsNone(messages._GetTestRunStateInfo(obj))

  def testConvertNameValuePairsToDict(self):
    pairs = [
        messages.NameValuePair(name='foo', value='FOO'),
        messages.NameValuePair(name='bar', value='BAR')
    ]
    expected = {'foo': 'FOO', 'bar': 'BAR'}

    self.assertEqual(expected, messages.ConvertNameValuePairsToDict(pairs))


if __name__ == '__main__':
  absltest.main()
