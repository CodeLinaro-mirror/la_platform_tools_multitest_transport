# Copyright 2024 Google LLC
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

"""Constant."""

# Integer, number of times to retry an api call
NUM_RETRIES = 3
# Socket level timeout
HTTP_TIMEOUT_SECONDS = 60
# int, File will be downloaded in chunks of this many bytes.
DEFAULT_CHUNK_SIZE = 16 * 1024 * 1024
# Upload chunk size in bytes.
UPLOAD_CHUNK_SIZE = 1 * 1024 * 1024  # 1MB
HTTP_NOT_FOUND_ERROR_CODE = 404

ANDROID_PARTNER_OAUTH2_SCOPES = (
    'https://www.googleapis.com/auth/androidPartner',
)
ANDROID_PARTNER_API_NAME = 'androidpartner'

ANDROID_PARTNER_API_VERSION = 'v1'
BUILD_FINGERPRINTS_PATH = 'device_names/*/product_names/*/build_fingerprints'
