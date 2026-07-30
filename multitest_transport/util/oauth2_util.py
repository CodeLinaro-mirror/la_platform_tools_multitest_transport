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

"""OAuth2 utilities."""
import dataclasses
import json
import logging
import pickle
from typing import List, Optional

from google.auth import credentials as ga_credentials
from google.oauth2 import credentials as authorized_user
import google_auth_httplib2
import httplib2
from tradefed_cluster.util import ndb_shim as ndb

GOOGLE_AUTH_URI = 'https://accounts.google.com/o/oauth2/auth'
GOOGLE_TOKEN_URI = 'https://accounts.google.com/o/oauth2/token'


class CredentialsProperty(ndb.BlobProperty):
  """Stores authorized user or service account credentials."""

  def _validate(self, value: bytes):
    if value is not None and not isinstance(value, ga_credentials.Credentials):
      raise TypeError('Value %s is not a Credentials instance.' % value)

  def _to_base_type(self, value: bytes):
    # Using protocol 2 to ensure compatibility with Python 2.
    return pickle.dumps(value, protocol=2)

  def _from_base_type(self,  # pytype: disable=signature-mismatch  # overriding-return-type-checks
                      value: bytes) -> Optional[ga_credentials.Credentials]:
    try:
      # Use UTF-8 encoding for backwards compatibility with Python 2
      credentials = pickle.loads(value, encoding='utf-8')
      # Patch missing fields from older credentials objects
      # (b/176850961, b/540280985)
      if not hasattr(credentials, '_quota_project_id'):
        setattr(credentials, '_quota_project_id', None)
      if not hasattr(credentials, '_always_use_jwt_access'):
        setattr(credentials, '_always_use_jwt_access', None)
      if not hasattr(credentials, '_cred_file_path'):
        setattr(credentials, '_cred_file_path', None)
      return credentials
    except (KeyError, pickle.PickleError, UnicodeDecodeError):
      logging.warning('Unpickling credentials failed, reverting to JSON')
    # Try to parse JSON blob for backwards compatibility with oauth2client
    try:
      data = json.loads(value)
      return authorized_user.Credentials.from_authorized_user_info(data)
    except ValueError:
      return None


@dataclasses.dataclass(frozen=True)
class OAuth2Config(object):
  """OAuth2 configuration."""
  client_id: str
  client_secret: str
  scopes: List[str]
  auth_uri: str = GOOGLE_AUTH_URI
  token_uri: str = GOOGLE_TOKEN_URI

  @property
  def is_valid(self) -> bool:
    return all([self.client_id, self.client_secret, self.scopes])


def AuthorizeHttp(http: httplib2.Http,
                  credentials: Optional[ga_credentials.Credentials],
                  scopes: Optional[List[str]] = None):
  """Helper function to apply credentials to an HTTP client."""
  if not credentials:
    return http  # TODO: try to use default credentials
  if scopes:
    credentials = ga_credentials.with_scopes_if_required(credentials, scopes)
  return google_auth_httplib2.AuthorizedHttp(credentials, http)
