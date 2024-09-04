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

"""Unit tests for config_encoder."""
from absl.testing import absltest
from tradefed_cluster import testbed_dependent_test
from tradefed_cluster.util import ndb_shim as ndb


from multitest_transport.models import config_encoder
from multitest_transport.models import ndb_models


class ConfigTest(testbed_dependent_test.TestbedDependentTest):

  def CreateNodeConfig(self, env_vars=None):
    return ndb_models.NodeConfig(
        id=ndb_models.NODE_CONFIG_ID,
        env_vars=ndb_models.NameValuePair.FromDict(env_vars or {}))

  def CreateBuildChannel(self, key=None, name=None, options=None):
    return ndb_models.BuildChannelConfig(
        id=key, name=name, provider_name=name,
        options=ndb_models.NameValuePair.FromDict(options or {}))

  def CreateTestRunAction(
      self,
      key=None,
      name=None,
      description=None,
      phases=None,
      hook_class_name=None,
      options=None,
  ):
    return ndb_models.TestRunAction(
        id=key,
        name=name,
        description=description,
        phases=phases or [],
        hook_class_name=hook_class_name,
        options=ndb_models.NameValuePair.FromDict(options or {}),
    )

  def testEncode_nodeConfig(self):
    """Tests serializing a node config (single object)."""
    node_config = self.CreateNodeConfig(env_vars={'variable': 'value'})

    expected =\
"""node_config:
  env_vars:
  - name: variable
    value: value
"""
    actual = config_encoder.Encode(
        config_encoder.ConfigSet(node_config=node_config))
    self.assertEqual(expected, actual)

  def testDecode_nodeConfig(self):
    """Tests deserializing a node config (single object)."""
    node_config = self.CreateNodeConfig(env_vars={'hello': 'world'})
    expected = config_encoder.ConfigSet(node_config=node_config)

    string =\
"""node_config:
  env_vars:
  - name: hello
    value: world
"""
    actual = config_encoder.Decode(string)
    self.assertEqual(expected, actual)

  def testEncode_buildChannels(self):
    """Tests serializing build channels (list of objects)."""
    foo = self.CreateBuildChannel(key='foo', name='Foo')
    bar = self.CreateBuildChannel(key='bar', name='Bar',
                                  options={'option': 'value'})

    expected =\
"""build_channels:
- id: foo
  name: Foo
  provider_name: Foo
- id: bar
  name: Bar
  options:
  - name: option
    value: value
  provider_name: Bar
"""
    actual = config_encoder.Encode(
        config_encoder.ConfigSet(build_channels=[foo, bar]))
    self.assertEqual(expected, actual)

  def testDecode_buildChannels(self):
    """Tests deserializing build channels (list of objects)."""
    foo = self.CreateBuildChannel(key='foo', name='Foo')
    bar = self.CreateBuildChannel(key='bar', name='Bar',
                                  options={'option': 'value'})
    expected = config_encoder.ConfigSet(build_channels=[foo, bar])

    string = \
"""build_channels:
- id: foo
  name: Foo
  provider_name: Foo
- id: bar
  name: Bar
  options:
  - name: option
    value: value
  provider_name: Bar
"""
    actual = config_encoder.Decode(string)
    self.assertEqual(expected, actual)

  def testEncode_multipleObjects(self):
    """Tests serializing multiple objects."""
    build_channel = self.CreateBuildChannel(key='foo', name='Foo',
                                            options={'option': 'value'})
    test_run_action = self.CreateTestRunAction(
        key='bar', name='Bar', hook_class_name='Web',
        options={'url': 'www.google.com'})
    expected = \
"""build_channels:
- id: foo
  name: Foo
  options:
  - name: option
    value: value
  provider_name: Foo
test_run_actions:
- hook_class_name: Web
  id: bar
  name: Bar
  options:
  - name: url
    value: www.google.com
"""

    config_set = config_encoder.ConfigSet(
        build_channels=[build_channel], test_run_actions=[test_run_action])
    actual = config_encoder.Encode(config_set)
    self.assertEqual(expected, actual)

  def testLoad(self):
    # add an existing build channel
    self.CreateBuildChannel(key='foo', name='Foo').put()
    # add an existing test run action
    self.CreateTestRunAction(
        key='foo',
        name='Foo',
        description='description',
        phases=[ndb_models.TestRunPhase.BEFORE_RUN],
        hook_class_name='hook',
    ).put()

    # load configuration
    build_channel = self.CreateBuildChannel(
        key='foo', options={'option': 'value'}
    )
    test_run_action = self.CreateTestRunAction(key='foo', description='')
    config_set = config_encoder.ConfigSet(
        build_channels=[build_channel], test_run_actions=[test_run_action]
    )
    config_encoder.Load(config_set)

    # updated existing build channel
    stored_build_channel = ndb.Key(ndb_models.BuildChannelConfig, 'foo').get()
    self.assertIsNotNone(stored_build_channel)
    self.assertEqual('Foo', stored_build_channel.name)  # preserved
    self.assertEqual('option', stored_build_channel.options[0].name)
    self.assertEqual('value', stored_build_channel.options[0].value)
    # updated existing test run action
    stored_test_run_action = ndb.Key(ndb_models.TestRunAction, 'foo').get()
    self.assertIsNotNone(stored_test_run_action)
    self.assertEqual('Foo', stored_test_run_action.name)  # preserved
    self.assertEqual('', stored_test_run_action.description)  # overridden
    self.assertEqual(
        [ndb_models.TestRunPhase.BEFORE_RUN], stored_test_run_action.phases
    )  # preserved repeated field
    self.assertEqual(
        'hook', stored_test_run_action.hook_class_name
    )  # preserved

  def testLoad_nodeConfig(self):
    """Tests updating a node config."""
    self.CreateNodeConfig(env_vars={'hello': 'world'}).put()

    # load configuration
    node_config = self.CreateNodeConfig()
    config_set = config_encoder.ConfigSet(node_config=node_config)
    config_encoder.Load(config_set)

    # updated existing node config
    stored_node_config = ndb.Key(ndb_models.NodeConfig, 1).get()
    self.assertIsNotNone(stored_node_config)
    self.assertLen(stored_node_config.env_vars, 1)  # preserved repeated fields


if __name__ == '__main__':
  absltest.main()
