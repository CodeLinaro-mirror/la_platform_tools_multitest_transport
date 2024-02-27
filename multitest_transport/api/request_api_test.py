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

from unittest import mock
from multitest_transport.api import api_test_util
from multitest_transport.api import request_api
from multitest_transport.util import olcs_session_stub
from protorpc import protojson
from tradefed_cluster import api_messages
from google3.testing.pybase import googletest


class RequestApiTest(api_test_util.TestCase):

  class RequestApiForTest(request_api.TestRequestApi):

    def __init__(self):
      self._olcs_session_stub = mock.create_autospec(
          olcs_session_stub.OlcsSessionStub, spec_set=True
      )
      self._olcs_session_stub.GetRequest = mock.MagicMock()
      response = api_messages.RequestMessage()
      response.id = "request_id"

      self._olcs_session_stub.GetRequest.return_value = response

  def setUp(self):
    super(RequestApiTest, self).setUp(RequestApiTest.RequestApiForTest)

  def testGetRequest(self):
    res = self.app.get("/_ah/api/mtt/v1/requests/%s" % "request_id")
    res_msg = protojson.decode_message(api_messages.RequestMessage, res.body)
    self.assertEqual(res_msg.id, "request_id")


if __name__ == "__main__":
  googletest.main()
