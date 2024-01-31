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

"""Utilities for tracking Google Analytics events."""
import collections
import json
import shutil
import uuid

from tradefed_cluster import common
from tradefed_cluster.services import task_scheduler


from multitest_transport.util import env
from multitest_transport.util import tfc_client

# Analytics uploading task queue
QUEUE_NAME = 'analytics-queue'

# GA categories
BUILD_CATEGORY = 'build'
BUILD_CHANNEL_CATEGORY = 'build_channel'
DEVICE_ACTION_CATEGORY = 'device_action'
SYSTEM_CATEGORY = 'system'
TEST_RUN_ACTION_CATEGORY = 'test_run_action'
TEST_RUN_CATEGORY = 'test_run'
INVOCATION_CATEGORY = 'invocation'
DISK_USAGE_CATEGORY = 'disk_usage'
DEVICE_COUNT_PER_WORKER_CATEGORY = 'device_count_per_worker'
WORKER_COUNT_CATEGORY = 'worker_count'

# GA actions
CRASH_ACTION = 'crash'
CREATE_ACTION = 'create'
DELETE_ACTION = 'delete'
DETECT_ACTION = 'detect'
DOWNLOAD_ACTION = 'download'
END_ACTION = 'end'
EXECUTE_ACTION = 'execute'
HEARTBEAT_ACTION = 'heartbeat'
RUN_TEST_ACTION = 'run_test'
START_ACTION = 'start'
TARGET_PREPARER_ACTION = 'target_preparer'
UPDATE_ACTION = 'update'


def Log(category: str, action: str, **kwargs):
  """Schedules a task to upload an event to GA."""
  payload = json.dumps(dict(category=category, action=action, **kwargs))
  task_scheduler.AddTask(queue_name=QUEUE_NAME, payload=payload)


def HeartbeatSender():
  """Request handler which periodically logs that this instance is up."""
  Log(SYSTEM_CATEGORY, HEARTBEAT_ACTION)
  _LogDiskUsage()
  _LogWorkerAndDeviceCount()
  return common.HTTP_OK


def _LogDiskUsage():
  """Uploads the disk usage to GA."""
  total, used, free = shutil.disk_usage('/')
  Log(DISK_USAGE_CATEGORY,
      HEARTBEAT_ACTION,
      total_disk_size_byte=total,
      used_disk_size_byte=used,
      free_disk_size_byte=free)


def _LogWorkerAndDeviceCount():
  """Uploads number of workers and device counts for each worker."""
  worker_count = 0
  device_collection = tfc_client.ListDevices()
  if device_collection:
    worker_device_map = collections.defaultdict(int)
    for device_info in device_collection.device_infos:
      worker_id = uuid.uuid3(uuid.NAMESPACE_DNS, device_info.hostname)
      worker_device_map[worker_id] += 1
    for worker_id, device_count in worker_device_map.items():
      Log(DEVICE_COUNT_PER_WORKER_CATEGORY,
          HEARTBEAT_ACTION,
          worker_id=str(worker_id),
          device_count=device_count)
    worker_count = len(worker_device_map)
  operation_mode = env.OPERATION_MODE.value
  Log(WORKER_COUNT_CATEGORY,
      HEARTBEAT_ACTION,
      operation_mode=operation_mode,
      worker_count=worker_count)
