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

"""Client used to upload Google Analytics events."""
import ctypes
import json
import logging
import multiprocessing
from typing import Iterator, Optional, Tuple
import urllib.parse
import urllib.request

import flask


from multitest_transport.models import ndb_models
from multitest_transport.util import analytics
from multitest_transport.util import env

# Error tracking (uploading disabled after too many consecutive upload errors)
MAX_CONSECUTIVE_UPLOAD_ERRORS = 20
_UPLOAD_ERROR_COUNT = multiprocessing.Value(ctypes.c_int, 0)

# WSGI application
APP = flask.Flask(__name__)

# GA constants
_TRACKING_ID = 'G-DLP3P88DWR'
_API_KEY = 'y10znyAaTom6tlQxY5xYag'
_GA_ENDPOINT = f'https://www.google-analytics.com/mp/collect?measurement_id={_TRACKING_ID}&api_secret={_API_KEY}'

# GA custom metrics definitions
_EVENT_METRIC_KEYS = frozenset([
    # Custom Dimension
    'event_category',
    'event_label',
    'event_value',
    'app_version',
    'test_name',
    'test_version',
    'state',
    'is_rerun',
    'is_google',
    'is_omni_lab',
    'command',
    'failed_test_count_threshold',
    'test_run_command',
    'test_run_retry_command',
    'missing_previous_run',
    'test_id',
    'is_sequence_run',
    'operation_mode',
    'worker_id',
    'user_tag',
    # Custom Metrics
    'duration_seconds',
    'device_count',
    'attempt_count',
    'failed_module_count',
    'test_count',
    'failed_test_count',
    'elapsed_time_seconds',
    'prev_total_test_count',
    'prev_failed_module_count',
    'prev_failed_test_count',
    'total_disk_size_byte',
    'used_disk_size_byte',
    'free_disk_size_byte',
    'worker_count',
])


@APP.route('/_ah/queue/' + analytics.QUEUE_NAME, methods=['POST'])
def UploadEvent() -> flask.Response:
  """Parses event parameters from the request body and uploads to GA."""
  params = flask.request.get_json(force=True)
  category = params.pop('category')
  action = params.pop('action')
  uploaded = _UploadEvent(category, action, **params)
  return flask.Response(status=201 if uploaded else 204)


def _UploadEvent(category: str, action: str, **kwargs) -> bool:
  """Uploads an event to GA if metrics are enabled."""
  private_node_config = ndb_models.GetPrivateNodeConfig()
  if (env.IS_DEV_MODE or not private_node_config.metrics_enabled or
      _UPLOAD_ERROR_COUNT.value >= MAX_CONSECUTIVE_UPLOAD_ERRORS):  # pytype: disable=attribute-error  # re-none
    logging.debug('Metrics disabled - skipping %s:%s', category, action)
    return False
  params = _EventParams(
      category=category, user_tag=private_node_config.gms_client_id, **kwargs
  )
  data = _BuildMeasurementProtocol(
      server_uuid=private_node_config.server_uuid,
      action=action,
      params=params
  )
  request = urllib.request.Request(
      url=_GA_ENDPOINT, data=data, headers={'User-Agent': 'MTT'}
  )
  try:
    urllib.request.urlopen(request)
    _UPLOAD_ERROR_COUNT.value = 0
  except:
    with _UPLOAD_ERROR_COUNT.get_lock():
      _UPLOAD_ERROR_COUNT.value += 1  # pytype: disable=attribute-error  # re-none
    raise
  return True


class _EventParams(object):
  """Holds GA event params."""

  def __init__(
      self,
      category: str,
      label: Optional[str] = None,
      value: Optional[str] = None,
      **kwargs,
  ):
    # Event dimensions
    self.event_category = category
    self.event_label = label
    self.event_value = value

    # Custom dimensions and metrics
    self.app_version = env.VERSION
    self.is_google = env.IS_GOOGLE
    self.is_omni_lab = env.IS_OMNILAB_BASED
    for key, value in kwargs.items():
      if key not in _EVENT_METRIC_KEYS:
        logging.warning('Unknown metric key: %s', key)
        continue
      setattr(self, key, value)

  def __iter__(self) -> Iterator[Tuple[str, str]]:
    for key, value in self.__dict__.items():
      if value is not None:
        yield key, value

  def __eq__(self, other) -> bool:
    return isinstance(other, _EventParams) and dict(self) == dict(other)

  def __ne__(self, other) -> bool:
    return not self.__eq__(other)


def _BuildMeasurementProtocol(
    server_uuid: str, action: str, params: _EventParams
) -> bytes:
  """Builds GA measurement protocol JSON post body."""
  mp = {
      'client_id': server_uuid,
      'events': [{'name': action, 'params': dict(params)}],
  }
  return json.dumps(mp).encode()
