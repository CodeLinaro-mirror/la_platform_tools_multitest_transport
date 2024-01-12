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
"""An Android Partner Front End client module."""
import json
import urllib.parse

import apiclient
import httplib2
from multitest_transport.util import constant
from multitest_transport.util import file_util
from multitest_transport.util import oauth2_util


class ApfeClient(object):
  """Wrapper class to access APFE service."""

  def __init__(self, api_name, api_key=None, credentials=None):
    self._authorized_http = None
    self._client = None
    self._api_name = api_name
    self._api_key = api_key
    self._credentials = credentials

  def _GetHttp(self):
    """Initializes an authorized http object if necessary."""
    if not self._authorized_http:
      http = httplib2.Http(timeout=constant.HTTP_TIMEOUT_SECONDS)
      self._authorized_http = oauth2_util.AuthorizeHttp(
          http,
          self._credentials,
          scopes=list(constant.ANDROID_PARTNER_OAUTH2_SCOPES),
      )

    return self._authorized_http

  def _GetClient(self):
    """Initializes an APFE client if necessary."""
    if not self._client:
      # Discovery api does not accept credentials
      self._client = apiclient.discovery.build(
          self._api_name,
          constant.ANDROID_PARTNER_API_VERSION,
          # Use raw model as the response of media api is not json
          model=apiclient.model.RawModel(),
          developerKey=self._api_key,
      )

    return self._client

  def UploadReport(self, result_url, company_id):
    """Uploads a zip format report to APFE."""

    result_handle = file_util.FileHandle.Get(result_url)
    result_info = result_handle.Info()
    if not result_info or result_info.content_type != 'application/zip':
      return

    # Start upload session
    raw_response = (
        self._GetClient()
        .compatibility()
        .report()
        .startUploadReport()
        .execute(http=self._GetHttp(), num_retries=constant.NUM_RETRIES)
    )
    resource_name = json.loads(raw_response)['ref']['name']

    # Upload result
    result_media = file_util.FileHandleMediaUpload(
        result_handle, chunksize=constant.UPLOAD_CHUNK_SIZE, resumable=False
    )
    self._GetClient().media().upload(
        resourceName=resource_name, media_body=result_media
    ).execute(http=self._GetHttp(), num_retries=constant.NUM_RETRIES)

    # Create report
    res = (
        self._GetClient()
        .compatibility()
        .report()
        .create(
            body={
                'reportRef': {
                    'name': resource_name,
                },
                'companyId': company_id,
            }
        )
        .execute(http=self._GetHttp(), num_retries=constant.NUM_RETRIES)
    )
    return res

  def GetRequiredReports(self, fingerprint):
    """Gets required reports for a build from APFE."""

    res = (
        self._GetClient()
        .compatibility()
        .device_names()
        .product_names()
        .build_fingerprints()
        .getRequiredreportsinfo(
            name=constant.BUILD_FINGERPRINTS_PATH
            + '/'
            + urllib.parse.quote_plus(fingerprint.strip())
        )
        .execute(http=self._GetHttp(), num_retries=constant.NUM_RETRIES)
    )
    return res
