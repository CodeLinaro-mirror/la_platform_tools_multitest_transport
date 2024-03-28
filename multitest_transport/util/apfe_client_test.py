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
"""Unit tests for apfe_client."""

import json
from unittest import mock

from absl.testing import absltest
from multitest_transport.models import ndb_models
from multitest_transport.util import apfe_client
from multitest_transport.util import constant
from multitest_transport.util import file_util


class ApfeClientTest(absltest.TestCase):

  def setUp(self):
    super(ApfeClientTest, self).setUp()
    self.mock_company_id = 1
    self.mock_report_name = 'report_name'
    self.mock_company_name = 'company_name'
    self.mock_device_name = 'device_name'
    self.mock_product_name = 'product_name'
    self.mock_model_name = 'model_name'
    self.mock_build_fingerprint = 'build_fingerprint'
    self.mock_resource_name = 'resource_name'
    self.mock_test_plan = 'gts-interactive'
    self.client = mock.MagicMock()
    self.apfe_client = apfe_client.ApfeClient('api_name')
    self.apfe_client._client = self.client
    self.apfe_client._authorized_http = mock.MagicMock()

  @mock.patch.object(file_util, 'FileHandleMediaUpload')
  @mock.patch.object(file_util.FileHandle, 'Get')
  def testUploadReport(self, mock_handle_factory, mock_media_upload_ctor):
    """Tests report can be uploaded."""
    mock_handle = mock.MagicMock()
    mock_handle_factory.return_value = mock_handle
    mock_handle.Info.return_value = file_util.FileInfo(
        url='report.zip', content_type='application/zip'
    )
    self.client.compatibility().report().startUploadReport().execute.return_value = json.dumps(
        {'ref': {'name': self.mock_resource_name}}
    )
    self.client.compatibility().report().create().execute.return_value = (
        json.dumps({
            'name': self.mock_report_name,
            'type': 'GTS',
            'companyId': self.mock_company_id,
            'companyName': self.mock_company_name,
            'deviceName': self.mock_device_name,
            'productName': self.mock_product_name,
            'modelName': self.mock_model_name,
            'buildFingerprint': self.mock_build_fingerprint,
            'processState': 'IN_PROGRESS',
        })
    )

    apfe_report = self.apfe_client.UploadReport(
        'result_url', self.mock_company_id
    )

    mock_media_upload_ctor.assert_called_with(
        mock_handle, chunksize=constant.UPLOAD_CHUNK_SIZE, resumable=False
    )
    self.client.compatibility().report().startUploadReport.assert_called()
    self.client.media().upload.assert_called_once_with(
        resourceName=self.mock_resource_name, media_body=mock.ANY
    )
    self.assertEqual(
        apfe_report,
        apfe_client.ApfeReport(
            name=self.mock_report_name,
            type=ndb_models.ReportType.GTS,
            companyId=self.mock_company_id,
            companyName=self.mock_company_name,
            deviceName=self.mock_device_name,
            productName=self.mock_product_name,
            modelName=self.mock_model_name,
            buildFingerprint=self.mock_build_fingerprint,
            processState=apfe_client.ProcessState.IN_PROGRESS,
        ),
    )
    request = (
        self.client.compatibility().report().create.call_args_list[1][1]['body']
    )
    self.assertEqual(
        request,
        {
            'reportRef': {
                'name': self.mock_resource_name,
            },
            'companyId': self.mock_company_id,
        },
    )

  def testGetLatestApfeReport(self):
    """Tests latest APFE report can be retrieved."""
    self.client.compatibility().devices().products().builds().reports().get().execute.return_value = json.dumps({
        'name': self.mock_report_name,
        'type': 'GTS',
        'companyId': self.mock_company_id,
        'companyName': self.mock_company_name,
        'deviceName': self.mock_device_name,
        'productName': self.mock_product_name,
        'modelName': self.mock_model_name,
        'buildFingerprint': self.mock_build_fingerprint,
        'processState': 'COMPLETE',
    })

    latest_apfe_report = self.apfe_client.GetLatestApfeReport(
        self.mock_report_name
    )
    self.assertEqual(
        latest_apfe_report,
        apfe_client.ApfeReport(
            name=self.mock_report_name,
            type=ndb_models.ReportType.GTS,
            companyId=self.mock_company_id,
            companyName=self.mock_company_name,
            deviceName=self.mock_device_name,
            productName=self.mock_product_name,
            modelName=self.mock_model_name,
            buildFingerprint=self.mock_build_fingerprint,
            processState=apfe_client.ProcessState.COMPLETE,
        ),
    )
    request = (
        self.client.compatibility()
        .devices()
        .products()
        .builds()
        .reports()
        .get.call_args_list[1][1]
    )
    self.assertEqual(
        request,
        {'name': self.mock_report_name},
    )

  def testGetRequiredReports(self):
    """Tests required reports can be retrieved."""
    self.client.compatibility().device_names().product_names().build_fingerprints().getRequiredreportsinfo().execute.return_value = json.dumps({
        'requiredReports': [
            {'type': 'CTS'},
            {'type': 'GTS', 'testPlans': [self.mock_test_plan]},
            {'type': 'VTS', 'available': True},
        ]
    })

    build_fingerprint = (
        'google/sunfish/sunfish:13/TQ1A.221205.006/9206830:user/release-keys'
    )

    required_reports = self.apfe_client.GetRequiredReports(build_fingerprint)
    self.assertEqual(
        required_reports,
        apfe_client.RequiredReportInfo(
            requiredReports=[
                apfe_client.RequiredReport(
                    type=ndb_models.ReportType.CTS,
                ),
                apfe_client.RequiredReport(
                    type=ndb_models.ReportType.GTS,
                    testPlans=[self.mock_test_plan],
                ),
                apfe_client.RequiredReport(
                    type=ndb_models.ReportType.VTS, available=True
                ),
            ]
        ),
    )
    request = (
        self.client.compatibility()
        .device_names()
        .product_names()
        .build_fingerprints()
        .getRequiredreportsinfo.call_args_list[1][1]
    )
    self.assertEqual(
        request,
        {
            'name': 'device_names/*/product_names/*/build_fingerprints/google%2Fsunfish%2Fsunfish%3A13%2FTQ1A.221205.006%2F9206830%3Auser%2Frelease-keys'
        },
    )


if __name__ == '__main__':
  absltest.main()
