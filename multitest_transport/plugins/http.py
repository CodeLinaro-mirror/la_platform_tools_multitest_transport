# Copyright 2022 Google LLC
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
"""HTTP plugins."""
import urllib.request


from multitest_transport.plugins import base
from multitest_transport.util import errors
from multitest_transport.util import file_util


class BasicAuthHttpProvider(base.BuildProvider):
  """A build provider for HTTP Basic Auth protected urls."""
  name = 'HTTP (Basic Auth)'
  build_item_path_type = base.BuildItemPathType.URL

  def __init__(self):
    super(BasicAuthHttpProvider, self).__init__()
    self.AddOptionDef(name='user')
    self.AddOptionDef(name='password')

  def _GetOpener(self, path):
    password_mgr = urllib.request.HTTPPasswordMgrWithDefaultRealm()
    options = self.GetOptions()
    password_mgr.add_password(None, path, options.user, options.password)  # pyrefly: ignore[missing-attribute]
    handler = urllib.request.HTTPBasicAuthHandler(password_mgr)
    return urllib.request.build_opener(handler)

  def GetBuildItem(self, path):
    """Returns a build item.

    Args:
      path: a build item path.

    Returns:
      a base.BuildItem object.

    Raises:
      errors.FileNotFoundError: if build item does not exist
    """
    handler = file_util.HttpFileHandle(path, url_opener=self._GetOpener(path))
    info = handler.Info()
    if not info:
      raise errors.FileNotFoundError(f'Build item {path} does not exist')
    return base.BuildItem(
        name=path,
        path='',
        is_file=info.is_file,
        size=info.total_size,
        timestamp=info.timestamp)

  def DownloadFile(self, path, offset=0):
    """Downloads a build file.

    Args:
      path: a build file path
      offset: byte offset to read from

    Returns:
      FileChunk iterator
    """
    return file_util.DownloadFile(path, url_opener=self._GetOpener(path))
