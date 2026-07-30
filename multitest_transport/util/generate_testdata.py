# Copyright 2026 Google LLC
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

"""Script to generate golden pickle files for oauth2_util_test."""

import os
import pickle
from absl import app
from absl import flags
from google.oauth2 import service_account

FLAGS = flags.FLAGS
flags.DEFINE_string(
    'output_dir',
    None,
    'Directory to output the golden pickle file. Defaults to testdata in source'
    ' tree.',
)


def main(argv):
  del argv
  output_dir = FLAGS.output_dir
  if not output_dir:
    build_dir = os.environ.get('BUILD_WORKING_DIRECTORY')
    if build_dir:
      output_dir = os.path.join(
          build_dir, 'third_party/py/multitest_transport/util/testdata'
      )
    else:
      output_dir = os.path.join(os.path.dirname(__file__), 'testdata')
  os.makedirs(output_dir, exist_ok=True)

  # Create a service account Credentials instance
  creds = service_account.Credentials(
      signer=None,
      service_account_email='legacy-sa@example.com',
      token_uri='https://oauth2.googleapis.com/token',
      project_id='legacy-project',
  )

  output_file = os.path.join(
      output_dir, 'legacy_service_account_credentials.pickle'
  )
  with open(output_file, 'wb') as f:
    pickle.dump(creds, f, protocol=2)

  print(f'Successfully generated golden pickle file at: {output_file}')


if __name__ == '__main__':
  app.run(main)
