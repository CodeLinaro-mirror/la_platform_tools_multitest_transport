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

"""Android Test Station local file server proxy tests."""
import http
from unittest import mock
import urllib.error
import urllib.request

from absl.testing import absltest
import webtest


from multitest_transport.file_server import proxy
from multitest_transport.util import env


class MockProxyResponse(object):
  """Fake response to return from the proxy's urllib request."""

  def __init__(self, status=200, data=b'', headers=None):
    self.code = status
    self.msg = http.HTTPStatus(status).phrase
    self.headers = headers or {}
    self.data = data

  def read(self, amt=None):  
    if amt is None:
      res, self.data = self.data, b''
      return res
    res, self.data = self.data[:amt], self.data[amt:]
    return res

  def close(self):  
    pass


class MockProxyError(urllib.error.HTTPError, MockProxyResponse):
  """Fake error response to return from the proxy's urllib request."""

  def __init__(self, status=500, **kwargs):
    urllib.error.HTTPError.__init__(self, None, status, None, None, None)
    MockProxyResponse.__init__(self, status=status, **kwargs)


class FileServerProxyTest(absltest.TestCase):

  def setUp(self):
    super(FileServerProxyTest, self).setUp()
    env.FILE_SERVER_URL = 'http://localhost:8006/'
    self.patcher = mock.patch.object(urllib.request, 'urlopen')
    self.mock_urlopen = self.patcher.start()
    self.testapp = webtest.TestApp(proxy.APP)

  def tearDown(self):
    super(FileServerProxyTest, self).tearDown()
    self.patcher.stop()

  def SendMockRequest(self, url, method='GET', data=b'', headers=None,
                      expect_errors=False):
    """Send a request to the proxy handler and return the response."""
    request = webtest.TestRequest.blank(url, method=method, body=data)
    for key, value in (headers or {}).items():
      request.headers[key] = value
    return self.testapp.do_request(request, expect_errors=expect_errors)

  def GetProxyRequest(self):
    """Fetch the request that was sent by the proxy."""
    return self.mock_urlopen.call_args[0][0]

  def AssertRequest(
      self, request, url='', method='GET', data=b'', headers=None):
    """Verifies the URL, method, data, and headers of a request."""
    self.assertEqual(url, request.get_full_url())
    self.assertEqual(method, request.get_method())
    self.assertEqual(data, request.data)
    for key, value in (headers or {}).items():
      self.assertEqual(value, request.headers[key])

  def AssertResponse(self, response, status=500, data=b'', headers=None):
    """Verifies the status, data, and headers of a response."""
    self.assertEqual(status, response.status_int)
    self.assertEqual(data, response.body)
    for key, value in (headers or {}).items():
      self.assertEqual(value, response.headers[key])

  def testProxyRequest_get(self):
    """Tests that a GET request can be sent."""
    self.mock_urlopen.return_value = MockProxyResponse()
    response = self.SendMockRequest('/fs_proxy/path/to/file')
    self.AssertResponse(response, status=200)
    proxy_request = self.GetProxyRequest()
    self.AssertRequest(proxy_request, url='http://localhost:8006/path/to/file')

  def testProxyRequest_getWithCustomHostnameParam(self):
    """Tests that a custom hostname can be provided."""
    self.mock_urlopen.return_value = MockProxyResponse()
    response = self.SendMockRequest('/fs_proxy/path/to/file?hostname=hostname')
    self.AssertResponse(response, status=200)
    proxy_request = self.GetProxyRequest()
    self.AssertRequest(
        proxy_request,
        url='http://hostname:8006/path/to/file?hostname=hostname')

  def testProxyRequest_post(self):
    """Tests that a POST request can be sent."""
    self.mock_urlopen.return_value = MockProxyResponse()
    self.SendMockRequest('/fs_proxy/path', method='POST')
    proxy_request = self.GetProxyRequest()
    self.AssertRequest(proxy_request, method='POST', url=mock.ANY)

  def testProxyRequest_put(self):
    """Tests that a PUT request can be sent."""
    self.mock_urlopen.return_value = MockProxyResponse()
    self.SendMockRequest('/fs_proxy/path', method='PUT')
    proxy_request = self.GetProxyRequest()
    self.AssertRequest(proxy_request, method='PUT', url=mock.ANY)

  def testProxyRequest_delete(self):
    """Tests that a DELETE request can be sent."""
    self.mock_urlopen.return_value = MockProxyResponse()
    self.SendMockRequest('/fs_proxy/path', method='DELETE')
    proxy_request = self.GetProxyRequest()
    self.AssertRequest(proxy_request, method='DELETE', url=mock.ANY)

  def testProxyRequest_requestData(self):
    """Tests that data is passed to the proxy request."""
    self.mock_urlopen.return_value = MockProxyResponse()
    self.SendMockRequest('/fs_proxy/path', data=b'test')
    proxy_request = self.GetProxyRequest()
    self.AssertRequest(proxy_request, data=b'test', url=mock.ANY)

  def testProxyRequest_requestHeader(self):
    """Tests that headers are passed to the proxy request."""
    self.mock_urlopen.return_value = MockProxyResponse()
    self.SendMockRequest('/fs_proxy/path', headers={'Key': 'value'})
    proxy_request = self.GetProxyRequest()
    self.AssertRequest(proxy_request, headers={'Key': 'value'}, url=mock.ANY)

  def testProxyRequest_responseStatus(self):
    """Tests that the proxy response status is returned."""
    self.mock_urlopen.return_value = MockProxyResponse(status=303)
    response = self.SendMockRequest('/fs_proxy/path')
    self.AssertResponse(response, status=303)

  def testProxyRequest_responseData(self):
    """Tests that the proxy response data is returned."""
    self.mock_urlopen.return_value = MockProxyResponse(data=b'test')
    response = self.SendMockRequest('/fs_proxy/path')
    self.AssertResponse(response, status=200, data=b'test')

  def testProxyRequest_responseHeader(self):
    """Tests that the proxy response headers are returned."""
    self.mock_urlopen.return_value = MockProxyResponse(headers={'Key': 'value'})
    response = self.SendMockRequest('/fs_proxy/path')
    self.AssertResponse(response, status=200, headers={'Key': 'value'})

  def testProxyRequest_errorResponse(self):
    """Tests that an error response can be returned."""
    self.mock_urlopen.side_effect = MockProxyError(
        status=400, data=b'error', headers={'Key': 'value'})
    response = self.SendMockRequest('/fs_proxy/path', expect_errors=True)
    self.AssertResponse(
        response, status=400, data=b'error', headers={'Key': 'value'})

  def testProxyRequest_proxyError(self):
    """Tests that an error can be handled."""
    self.mock_urlopen.side_effect = urllib.error.URLError('error')
    response = self.SendMockRequest('/fs_proxy/path', expect_errors=True)
    self.AssertResponse(response, status=500)

  def testProxyRequest_streamingChunkedResponse(self):
    """Tests that proxy response streams in chunks and excludes hop-by-hop headers."""
    mock_resp = MockProxyResponse(
        data=b'a' * 150000,
        headers={
            'Content-Type': 'application/zip',
            'Transfer-Encoding': 'chunked',
            'CONNECTION': 'keep-alive',
        },
    )
    mock_resp.read = mock.MagicMock(side_effect=mock_resp.read)
    mock_resp.close = mock.MagicMock()
    self.mock_urlopen.return_value = mock_resp

    response = self.SendMockRequest('/fs_proxy/path/large.zip')

    self.AssertResponse(response, status=200, data=b'a' * 150000)
    self.assertIn('Content-Type', response.headers)
    self.assertNotIn('Transfer-Encoding', response.headers)
    self.assertNotIn('Connection', response.headers)
    self.assertGreater(mock_resp.read.call_count, 1)
    mock_resp.close.assert_called_once()


if __name__ == '__main__':
  absltest.main()
