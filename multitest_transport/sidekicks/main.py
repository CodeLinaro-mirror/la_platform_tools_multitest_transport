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

"""A main app for sidekick modules."""
import flask


from multitest_transport.test_scheduler import download_util
from multitest_transport.util import analytics

APP = flask.Flask(__name__)
APP.add_url_rule(
    '/sidekicks/heartbeat_sender',
    endpoint='analytics.HeartbeatSender',
    view_func=analytics.HeartbeatSender)
APP.add_url_rule(
    '/sidekicks/test_resource_cache_cleaner',
    endpoint='download_util.TestResourceCacheCleaner',
    view_func=download_util.TestResourceCacheCleaner)
APP.add_url_rule(
    '/sidekicks/test_resource_tracker_cleaner',
    endpoint='download_util.TestResourceTrackerCleaner',
    view_func=download_util.TestResourceTrackerCleaner)
APP.add_url_rule(
    '/sidekicks/test_resource_metadata_cleaner',
    endpoint='download_util.TestResourceMetadataCleaner',
    view_func=download_util.TestResourceMetadataCleaner)

