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

"""Unit tests for oauth2_util."""
import json
import os
import pickle

from absl.testing import absltest
from google.oauth2 import credentials as authorized_user
from google.oauth2 import service_account
from tradefed_cluster import testbed_dependent_test
from tradefed_cluster.util import ndb_shim as ndb


from multitest_transport.util import oauth2_util


class TestModel(ndb.Model):
  """Dummy model to test storing credentials."""
  credentials = oauth2_util.CredentialsProperty()


class CredentialsPropertyTest(testbed_dependent_test.TestbedDependentTest):
  """Tests for oauth2_util.CredentialsProperty."""

  def testStore(self):
    """Tests that credentials can be stored and retrieved."""
    credentials = authorized_user.Credentials.from_authorized_user_info({
        'client_id': 'client_id',
        'client_secret': 'client_secret',
        'refresh_token': 'refresh_token',
    })
    entity = TestModel(id='foo', credentials=credentials)
    entity.put()
    retrieved = TestModel.get_by_id('foo')
    self.assertIsNotNone(retrieved.credentials)
    self.assertEqual('client_id', retrieved.credentials.client_id)
    self.assertEqual('client_secret', retrieved.credentials.client_secret)
    self.assertEqual('refresh_token', retrieved.credentials.refresh_token)

  def testValidate(self):
    """Tests that the credentials type is validated."""
    prop = oauth2_util.CredentialsProperty()
    # None is allowed
    prop._validate(None)
    # User authorization and service accounts are allowed
    prop._validate(authorized_user.Credentials(None))
    prop._validate(service_account.Credentials(None, None, None))
    # Anything else is forbidden
    with self.assertRaises(TypeError):
      prop._validate({})

  def testParseLegacy(self):
    """Tests that legacy JSON blobs can be parsed."""
    prop = oauth2_util.CredentialsProperty()
    data = {
        'client_id': 'client_id',
        'client_secret': 'client_secret',
        'refresh_token': 'refresh_token',
    }
    value = json.dumps(data).encode()
    credentials = prop._from_base_type(value)
    self.assertIsNotNone(credentials)
    self.assertEqual('client_id', credentials.client_id)
    self.assertEqual('client_secret', credentials.client_secret)
    self.assertEqual('refresh_token', credentials.refresh_token)

  def testPatchMissingFields(self):
    """Tests that missing fields like _cred_file_path are patched on unpickled credentials."""
    credentials = service_account.Credentials(None, None, None)
    delattr(credentials, '_cred_file_path')
    data = pickle.dumps(credentials, protocol=2)
    unpickled = oauth2_util.CredentialsProperty()._from_base_type(data)
    self.assertIsNotNone(unpickled)
    self.assertTrue(hasattr(unpickled, '_cred_file_path'))
    self.assertIsNone(unpickled._cred_file_path)
    # Verify with_scopes doesn't raise AttributeError
    scoped = unpickled.with_scopes(
        ['https://www.googleapis.com/auth/cloud-platform']
    )
    self.assertIsNotNone(scoped)

  def testGoldenPickleCredentials(self):
    """Tests deserializing a golden legacy pickled Credentials object."""
    golden_path = os.path.join(
        os.path.dirname(__file__),
        'testdata/legacy_service_account_credentials.pickle',
    )
    self.assertTrue(
        os.path.exists(golden_path),
        f'Golden pickle file missing at {golden_path}. Run:'
        ' blaze run'
        ' //third_party/py/multitest_transport/util:generate_testdata',
    )
    with open(golden_path, 'rb') as f:
      golden_bytes = f.read()

    try:
      unpickled = oauth2_util.CredentialsProperty()._from_base_type(
          golden_bytes
      )
      self.assertIsNotNone(unpickled, 'Failed to unpickle golden credentials.')
      # Test with_scopes to verify _make_copy() works without AttributeError
      scoped = unpickled.with_scopes(
          ['https://www.googleapis.com/auth/cloud-platform']
      )
      self.assertIsNotNone(scoped)
    except AttributeError as e:
      missing_attr = getattr(e, 'name', str(e))
      agent_hint = (
          '\n======================================================================\n'
          'GOLDEN PICKLE COMPATIBILITY TEST FAILED DUE TO ATTRIBUTE ERROR:'
          f' {e}\n'
          '----------------------------------------------------------------------\n'
          '[JETSKI / AGENT INSTRUCTIONS TO FIX THIS ISSUE]:\n'
          f'1. Root Cause: A new field ({missing_attr}) was added to'
          ' `google.auth` or\n'
          '   `google.oauth2.service_account.Credentials` that is missing on'
          ' legacy\n'
          '   pickled objects stored in Datastore.\n\n'
          '2. Fix in'
          ' `third_party/py/multitest_transport/util/oauth2_util.py`:\n'
          '   Inside `CredentialsProperty._from_base_type()`, add a patch'
          ' check:\n'
          f'     if not hasattr(credentials, "{missing_attr}"):\n'
          f'       setattr(credentials, "{missing_attr}", None)\n\n'
          '3. Regeneration (if intentional breaking change):\n'
          '   If older golden files are no longer supported, regenerate'
          ' using:\n'
          '     blaze run'
          ' //third_party/py/multitest_transport/util:generate_testdata\n'
          '======================================================================\n'
      )
      self.fail(agent_hint)


if __name__ == '__main__':
  absltest.main()
