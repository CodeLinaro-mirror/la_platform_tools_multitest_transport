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

"""MTT config objects and utilities for serializing/deserializing them."""
import json

from protorpc import protojson
from protorpc.messages import Message
from protorpc.messages import MessageField
import yaml


from multitest_transport.models import messages
from multitest_transport.models import ndb_models

NAMESPACE_SEPARATOR = '::'


def Encode(config_set):
  """Serializes MTT configuration.

  Args:
    config_set: MTT configuration set
  Returns:
    Configuration set serialized as a YAML string
  """
  msg = messages.Convert(config_set, _ConfigSetMessage)
  return _JsonToYaml(protojson.encode_message(msg))  # pytype: disable=module-attr


def Decode(string):
  """Deserializes MTT configuration.

  Args:
    string: configuration set in YAML format
  Returns:
    MTT configuration set
  """
  data = yaml.safe_load(string)
  msg = protojson.decode_message(_ConfigSetMessage, json.dumps(data))  # pytype: disable=module-attr

  # If url is provided, add it as a namespace to the id to dedupe objects from
  # different configs with the same id and identify which config set each
  # belongs to.
  info = msg.info
  if info:
    objs = (msg.build_channels + msg.device_actions +
            msg.test_run_actions + msg.tests)
    for obj in objs:
      obj.id = _AddNamespaceToId(info.url, obj.id)
  return messages.Convert(msg, ConfigSet)


def _AddNamespaceToId(namespace, obj_id):
  return NAMESPACE_SEPARATOR.join([namespace, obj_id])


def Load(config_set):
  """Load MTT configuration into the DB.

  Args:
    config_set: MTT configuration set
  """
  if config_set.node_config:
    _Load(config_set.node_config)
  if config_set.file_cleaner:
    _Load(config_set.file_cleaner)

  objs = (
      config_set.build_channels + config_set.device_actions +
      config_set.test_run_actions + config_set.tests)
  for obj in objs:
    _Load(obj)


def _JsonToYaml(string):
  """Converts a JSON string to YAML."""
  obj = json.loads(string)
  return yaml.safe_dump(obj, default_flow_style=False)


def _IsEmptyList(v):
  return isinstance(v, list) and not v


def _Load(obj):
  """Upsert a model instance."""
  existing = obj.key.get(use_cache=False)
  if existing:
    # existing data found, update with new values
    properties = dir(obj.__class__)

    # if the value is not provided or empty list, keep the existing value
    values = dict(
        (k, v)
        for k, v in obj.to_dict().items()
        if v is not None and not _IsEmptyList(v) and k in properties
    )

    existing.populate(**values)
    existing.put()
  else:
    # no existing data, create using new values
    obj.put()


class ConfigSet(object):
  """MTT configuration set object."""

  def __init__(self,
               node_config=None,
               build_channels=None,
               device_actions=None,
               test_run_actions=None,
               tests=None,
               info=None,
               file_cleaner=None):
    self.node_config = node_config
    self.build_channels = build_channels or []
    self.device_actions = device_actions or []
    self.test_run_actions = test_run_actions or []
    self.tests = tests or []
    self.info = info
    self.file_cleaner = file_cleaner
    # TODO: add support for test plans

  def __eq__(self, other):
    return (isinstance(other, ConfigSet) and
            self.node_config == other.node_config and
            self.build_channels == other.build_channels and
            self.device_actions == other.device_actions and
            self.test_run_actions == other.test_run_actions and
            self.tests == other.tests and self.info == other.info and
            self.file_cleaner == other.file_cleaner)

  def __ne__(self, other):
    return not self.__eq__(other)


class _ConfigSetMessage(Message):
  """MTT configuration set message."""
  node_config = MessageField(messages.NodeConfig, 1)
  build_channels = MessageField(messages.BuildChannelConfig, 2, repeated=True)
  device_actions = MessageField(messages.DeviceAction, 3, repeated=True)
  test_run_actions = MessageField(messages.TestRunAction, 4, repeated=True)
  tests = MessageField(messages.Test, 5, repeated=True)
  info = MessageField(messages.ConfigSetInfo, 6)
  file_cleaner = MessageField(messages.FileCleanerSettings, 7)


@messages.Converter(ConfigSet, _ConfigSetMessage)
def _ConfigSetConverter(obj):
  return _ConfigSetMessage(
      node_config=messages.Convert(obj.node_config, messages.NodeConfig),
      build_channels=messages.ConvertList(obj.build_channels,
                                          messages.BuildChannelConfig),
      device_actions=messages.ConvertList(obj.device_actions,
                                          messages.DeviceAction),
      test_run_actions=messages.ConvertList(obj.test_run_actions,
                                            messages.TestRunAction),
      tests=messages.ConvertList(obj.tests, messages.Test),
      info=messages.Convert(obj.info, messages.ConfigSetInfo),
      file_cleaner=messages.Convert(obj.file_cleaner,
                                    messages.FileCleanerSettings))


@messages.Converter(_ConfigSetMessage, ConfigSet)
def _ConfigSetMessageConverter(msg):
  return ConfigSet(
      node_config=messages.Convert(msg.node_config, ndb_models.NodeConfig),
      build_channels=messages.ConvertList(msg.build_channels,
                                          ndb_models.BuildChannelConfig),
      device_actions=messages.ConvertList(msg.device_actions,
                                          ndb_models.DeviceAction),
      test_run_actions=messages.ConvertList(msg.test_run_actions,
                                            ndb_models.TestRunAction),
      tests=messages.ConvertList(msg.tests, ndb_models.Test),
      info=messages.Convert(msg.info, ndb_models.ConfigSetInfo),
      file_cleaner=messages.Convert(msg.file_cleaner,
                                    ndb_models.FileCleanerSettings))
