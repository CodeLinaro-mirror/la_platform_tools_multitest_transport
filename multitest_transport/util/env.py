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

"""Service environment variables."""
import enum
import os
import re
from google.appengine.api import full_app_id


class OperationMode(enum.Enum):
  CLOUD = 'cloud'
  ON_PREMISE = 'on_premise'
  STANDALONE = 'standalone'
  UNKNOWN = 'unknown'


@enum.unique
class CredentialType(enum.Enum):
  NO_CREDENTIAL = 'no_credential'
  ALTS = 'alts'
  SSL = 'ssl'
  LOCAL = 'local'


# Constants and default values
UNKNOWN = 'UNKNOWN'
DEFAULT_QUEUE_TIMEOUT_SECONDS = 7200  # two hours
DEFAULT_INVOCATION_TIMEOUT_SECONDS = 0  # no timeout
DEFAULT_OUTPUT_IDLE_TIMEOUT_SECONDS = 3600  # one hour

# General application parameters
PORT = os.environ.get('MTT_PORT')
USER = os.environ.get('MTT_USER', UNKNOWN)
HOSTNAME = os.environ.get('MTT_HOSTNAME', UNKNOWN)
VERSION = os.environ.get('MTT_VERSION', UNKNOWN)
CLI_VERSION = os.environ.get('MTT_CLI_VERSION', UNKNOWN)
ADB_VERSION = os.environ.get('ADB_VERSION', UNKNOWN)
IS_DEV_MODE = os.environ.get('DEV_MODE') == 'true'
IS_LAB_MODE = os.environ.get('LAB_MODE') == 'true'
IS_OMNILAB_BASED = os.environ.get('IS_OMNILAB_BASED') == 'true'
OPERATION_MODE = OperationMode(
    os.environ.get('OPERATION_MODE', OperationMode.UNKNOWN))
IS_GOOGLE = bool(re.search(r'\.google\.com$', HOSTNAME))
SQL_DATABASE_URI = os.environ.get('MTT_SQL_DATABASE_URI')

# Google Cloud Storage parameters
APPLICATION_ID = full_app_id.get()
GCS_BUCKET_NAME = os.environ.get('BUCKET_NAME', 'app_default_bucket')

# File storage parameters
STORAGE_PATH = os.environ.get('MTT_STORAGE_PATH')
FILE_SERVER_ROOT = os.environ.get('MTT_FILE_SERVER_ROOT')
FILE_SERVER_URL = os.environ.get('MTT_FILE_SERVER_URL')
FILE_SERVER_PORT = os.environ.get('MTT_FILE_SERVER_PORT')

# Monitor parameters
NETDATA_URL = os.environ.get('MTT_NETDATA_URL')

# OLCS parameters
OLCS_SERVER_ADDRESS = os.environ.get('OLCS_SERVER_ADDRESS', 'localhost:7030')
OLCS_CREDENTIAL_TYPE = CredentialType(
    os.environ.get('OLCS_CREDENTIAL_TYPE', CredentialType.NO_CREDENTIAL)
)

# Worker lab server parameters
WORKER_LAB_SERVER_ADDRESS = os.environ.get(
    'WORKER_LAB_SERVER_ADDRESS', 'localhost:9994'
)

# Google OAuth2 parameters
GOOGLE_OAUTH2_CLIENT_ID = os.environ.get('MTT_GOOGLE_OAUTH2_CLIENT_ID', UNKNOWN)
GOOGLE_OAUTH2_CLIENT_SECRET = os.environ.get(
    'MTT_GOOGLE_OAUTH2_CLIENT_SECRET', UNKNOWN)

REPORT_GENERATOR_JAR = os.environ.get('MTT_REPORT_GENERATOR_JAR', UNKNOWN)
