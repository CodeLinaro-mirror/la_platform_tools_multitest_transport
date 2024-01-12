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
from multitest_transport.util import apfe_client
from multitest_transport.util import constant
from multitest_transport.util import file_util


class ApfeClientTest(absltest.TestCase):

  def setUp(self):
    super(ApfeClientTest, self).setUp()
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
    resource_name = 'resource_name'
    self.client.compatibility().report().startUploadReport().execute.return_value = json.dumps(
        {'ref': {'name': resource_name}}
    )
    company_id = 'company_id'

    self.apfe_client.UploadReport('result_url', company_id)

    mock_media_upload_ctor.assert_called_with(
        mock_handle, chunksize=constant.UPLOAD_CHUNK_SIZE, resumable=False
    )
    self.client.compatibility().report().startUploadReport.assert_called()
    self.client.media().upload.assert_called_once_with(
        resourceName=resource_name, media_body=mock.ANY
    )
    self.client.compatibility().report().create.assert_called_once_with(
        body={
            'reportRef': {
                'name': resource_name,
            },
            'companyId': company_id,
        }
    )

  def testGetRequiredReports(self):
    """Tests required reports can be retrieved."""
    build_fingerprint = (
        'google/sunfish/sunfish:13/TQ1A.221205.006/9206830:user/release-keys'
    )

    self.apfe_client.GetRequiredReports(build_fingerprint)

    self.client.compatibility().device_names().product_names().build_fingerprints().getRequiredreportsinfo.assert_called_once_with(
        name='device_names/*/product_names/*/build_fingerprints/google%2Fsunfish%2Fsunfish%3A13%2FTQ1A.221205.006%2F9206830%3Auser%2Frelease-keys'
    )


if __name__ == '__main__':
  absltest.main()
