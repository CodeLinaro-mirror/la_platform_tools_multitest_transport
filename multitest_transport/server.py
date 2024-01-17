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

"""WSGI application dispatchers."""
from tradefed_cluster.server import RegexDispatcher
from tradefed_cluster.services import task_scheduler


from multitest_transport.api import server as api
from multitest_transport.build_manager import xts_requirements_detector
from multitest_transport.core import app as core
from multitest_transport.core import cron_kicker
from multitest_transport.file_server import proxy as file_server_proxy
from multitest_transport.sidekicks import main as sidekicks
from multitest_transport.test_scheduler import test_kicker
from multitest_transport.test_scheduler import test_plan_kicker
from multitest_transport.test_scheduler import test_scheduler
from multitest_transport.test_scheduler import tfc_event_handler
from multitest_transport.tools.webaoa import server as webaoa
from multitest_transport.ui2 import main as ui
from multitest_transport.util import analytics_uploader


CORE = RegexDispatcher([
    # Cron handlers
    (r'/_ah/queue/cron-kicker-queue', cron_kicker.APP),
    # Initialization
    (r'/.*', core.APP),
])

APP = RegexDispatcher([
    # REST API
    (r'/_ah/api_docs(/.*)?', api.DOCS_APP),
    (r'/_ah/api(/.*)?', api.APP),
    # Task handlers
    (r'/_ah/queue/analytics-queue', analytics_uploader.APP),
    (r'/_ah/queue/default', task_scheduler.APP),
    (
        r'/_ah/queue/xts-requirements-detection-event-queue',
        xts_requirements_detector.APP,
    ),
    (r'/_ah/queue/test-kicker-queue', test_kicker.APP),
    (r'/_ah/queue/test-plan-kicker-queue', test_plan_kicker.APP),
    (r'/_ah/queue/tfc-event-queue', tfc_event_handler.APP),
    # Cron handlers
    (r'/sidekicks(/.*)?', sidekicks.APP),
    (r'/test_scheduler(/.*)?', test_scheduler.APP),
    # Local file server proxy
    (r'/fs_proxy(/.*)?', file_server_proxy.APP),
    # Additional tools
    (r'/webaoa(/.*)?', webaoa.APP),
    # User interface (ignore /_ah/start to speed up start up)
    (r'^/(?!_ah/start).*', ui.APP),
])
