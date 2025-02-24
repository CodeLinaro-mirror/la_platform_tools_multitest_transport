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
from protorpc import messages
from protorpc import protojson
from tradefed_cluster.util import ndb_shim as ndb


from multitest_transport.models import ndb_models
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
    apfe_report = protojson.decode_message(ApfeReport, res)  # pytype: disable=module-attr
    return apfe_report

  def GetLatestApfeBuild(self, fingerprint):
    """Gets the latest build from APFE."""

    res = (
        self._GetClient()
        .compatibility()
        .device_names()
        .product_names()
        .build_fingerprints()
        .get(
            name=constant.BUILD_FINGERPRINTS_PATH
            + '/'
            + urllib.parse.quote_plus(fingerprint.strip())
        )
        .execute(http=self._GetHttp(), num_retries=constant.NUM_RETRIES)
    )
    apfe_build = protojson.decode_message(ApfeBuild, res)  # pytype: disable=module-attr
    return apfe_build

  def GetLatestApfeReport(self, report_name):
    """Gets the latest report from APFE."""

    res = (
        self._GetClient()
        .compatibility()
        .devices()
        .products()
        .builds()
        .reports()
        .get(name=report_name)
        .execute(http=self._GetHttp(), num_retries=constant.NUM_RETRIES)
    )
    apfe_report = protojson.decode_message(ApfeReport, res)  # pytype: disable=module-attr
    return apfe_report

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
    required_report_info = protojson.decode_message(RequiredReportInfo, res)  # pytype: disable=module-attr
    return required_report_info


class ApfeBuild(messages.Message):
  """an APFE build."""

  name = messages.StringField(1)
  approvalStatus = messages.EnumField(ndb_models.BuildApprovalStatus, 2)  


def ConvertApfeBuild(msg, build_key):
  if not isinstance(msg, ApfeBuild):
    return None
  # Syncs data to existing APFE build if any, otherwise creates a new one.
  saved_apfe_build = ndb_models.ApfeBuild.query(ancestor=build_key).get()
  key_id = saved_apfe_build.key.id() if saved_apfe_build else None
  return ndb_models.ApfeBuild(
      key=ndb.Key(ndb_models.ApfeBuild, key_id, parent=build_key),
      name=msg.name,
      approval_status=msg.approvalStatus,
  )


class ApfeReport(messages.Message):
  """an APFE report."""

  name = messages.StringField(1)
  type = messages.EnumField(ndb_models.ReportType, 2)
  companyId = messages.IntegerField(3)  
  companyName = messages.StringField(4)  
  deviceName = messages.StringField(5)  
  productName = messages.StringField(6)  
  modelName = messages.StringField(7)  
  buildFingerprint = messages.StringField(8)  
  processState = messages.EnumField(ndb_models.ReportProcessState, 9)  


def ConvertApfeReport(msg, test_run_key):
  if not isinstance(msg, ApfeReport):
    return None
  # Syncs data to existing APFE report if any, otherwise creates a new one.
  saved_apfe_report = ndb_models.ApfeReport.query(ancestor=test_run_key).get()
  key_id = saved_apfe_report.key.id() if saved_apfe_report else None
  return ndb_models.ApfeReport(
      key=ndb.Key(ndb_models.ApfeReport, key_id, parent=test_run_key),
      name=msg.name,
      type=msg.type,
      company_id=msg.companyId,
      company_name=msg.companyName,
      device_name=msg.deviceName,
      product_name=msg.productName,
      model_name=msg.modelName,
      build_fingerprint=msg.buildFingerprint,
      process_state=msg.processState,
  )


class RequiredReport(messages.Message):
  """A required report."""

  type = messages.EnumField(ndb_models.ReportType, 1)
  testPlans = messages.StringField(2, repeated=True)  
  available = messages.BooleanField(3)


def ConvertRequiredReport(msg, build_key):
  if not isinstance(msg, RequiredReport):
    return None
  test_plans = [
      test_plan.strip() for test_plan in msg.testPlans if test_plan.strip()
  ]
  return ndb_models.RequiredReport(
      build_key=build_key,
      type=msg.type,
      test_plans=test_plans,
      available=msg.available,
  )


class RequiredReportInfo(messages.Message):
  """Required reports to get approval for a build."""

  requiredReports = messages.MessageField(RequiredReport, 1, repeated=True)  
