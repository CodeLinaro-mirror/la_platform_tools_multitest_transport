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

"""A module to handle app lifecycle events."""
import logging
import os
import pathlib

import flask


from multitest_transport.core import config_loader
from multitest_transport.core import cron_kicker
from multitest_transport.core import ndb_upgrader
from multitest_transport.core import service_checker
from multitest_transport.models import sql_models
from multitest_transport.test_scheduler import download_util
from multitest_transport.test_scheduler import test_scheduler
from multitest_transport.util import analytics
from multitest_transport.util import env
from multitest_transport.util import tfc_client
from tradefed_cluster import common

APP = flask.Flask(__name__)

_CRASH_REPORT_FILE = '.crash_report_file'


def CheckPreviousCrash():
  """The crash file should be deleted during a normal shutdown, so its presence on startup indicates a crash."""
  filepath = os.path.join(env.STORAGE_PATH, _CRASH_REPORT_FILE)  # pyrefly: ignore[no-matching-overload]
  crash_report_file = pathlib.Path(filepath)
  if crash_report_file.is_file():
    logging.info('Uploading ATS crash status to Google Analytics')
    analytics.Log(
        analytics.SYSTEM_CATEGORY,
        analytics.CRASH_ACTION,
        label='ats_container')
  else:
    # On ATS start, create a file to track ATS crashing status
    crash_report_file.touch()


@APP.route('/init')
def AppStartHandler():
  """App start event handler."""
  logging.info(
      'Server is starting... (%s, cli_version=%s)',
      env.VERSION, env.CLI_VERSION)
  logging.info('os.environ=%s', os.environ)

  # Service Checks
  CheckPreviousCrash()
  service_checker.Check()

  config_loader.Load()
  cron_kicker.Init()

  # Update datastore and database if necessary
  ndb_upgrader.UpgradeNdb()
  sql_models.db.CreateTables()

  # Release any remaining test resource download trackers.
  download_util.ReleaseDownloadLocks()

  # Requeue non-final requests, commands and command attempts for monitoring.
  tfc_client.BackfillRequestSyncs()
  tfc_client.BackfillCommands()
  tfc_client.BackfillCommandAttempts()

  # Requeue or Cancel the pending test runs.
  test_scheduler.CheckUnfinishedTestRuns()
  return common.HTTP_OK
