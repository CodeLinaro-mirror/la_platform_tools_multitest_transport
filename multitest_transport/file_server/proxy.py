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

"""Android Test Station local file server proxy."""
import http
import logging
import urllib.error
import urllib.parse
import urllib.request

import flask
import flask.views


from multitest_transport.util import env

APP = flask.Flask(__name__)


HOP_BY_HOP_HEADERS = {
    'connection',
    'keep-alive',
    'proxy-authenticate',
    'proxy-authorization',
    'te',
    'trailers',
    'transfer-encoding',
    'upgrade',
}


def _SanitizeHeaders(headers):
  return {
      k: v
      for k, v in dict(headers).items()
      if k.lower() not in HOP_BY_HOP_HEADERS
  }


class FileServerProxy(flask.views.MethodView):
  """Proxies requests to the local file server."""

  def get(self, path):
    return self._ProxyRequest('GET', path)

  def post(self, path):
    return self._ProxyRequest('POST', path)

  def put(self, path):
    return self._ProxyRequest('PUT', path)

  def delete(self, path):
    return self._ProxyRequest('DELETE', path)

  def _ProxyRequest(self, method, path):
    # Combine target host and request URL
    target_host = env.FILE_SERVER_URL
    (scheme, host, _, _, _) = urllib.parse.urlsplit(target_host)
    hostname = flask.request.args.get('hostname')
    if hostname:
      host = hostname + ':' + str(urllib.parse.urlparse(target_host).port)
    (_, _, _, query, fragment) = urllib.parse.urlsplit(flask.request.url)
    url = urllib.parse.urlunsplit((scheme, host, path, query, fragment))  

    try:
      # Create and send request with body and header
      data = flask.request.get_data()
      headers = {}
      for key, value in flask.request.headers.items():
        headers[str(key)] = str(value)
      request = urllib.request.Request(url=url, data=data, headers=headers)
      request.get_method = lambda: method
      response = urllib.request.urlopen(request)
    except urllib.error.HTTPError as e:
      # Relay HTTP errors back to caller
      r = flask.Response(e.read(), headers=_SanitizeHeaders(e.headers))
      r.status = e.reason
      r.status_code = int(e.code)
      return r
    except urllib.error.URLError:
      logging.exception('Error during proxy request %s', url)
      return flask.Response(status=http.HTTPStatus.INTERNAL_SERVER_ERROR.value)

    def _GenerateChunks(resp):
      try:
        while True:
          chunk = resp.read(65536)
          if not chunk:
            break
          yield chunk
      finally:
        resp.close()

    r = flask.Response(
        _GenerateChunks(response), headers=_SanitizeHeaders(response.headers)
    )
    r.status = getattr(response, 'msg', None)
    r.status_code = int(response.code)
    return r


APP.add_url_rule(
    '/fs_proxy/<path:path>', view_func=FileServerProxy.as_view('fs_proxy'))
