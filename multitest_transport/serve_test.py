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
"""Exercises serve.sh via BASH_SOURCE function sourcing and CLI execution."""
import os
import stat
import subprocess
import textwrap
from absl.testing import absltest
from absl.testing import parameterized

_SERVE_SH = os.path.join(os.path.dirname(__file__), 'serve.sh')


class ServeShTest(parameterized.TestCase):

  @parameterized.named_parameters(
      dict(
          testcase_name='host_and_port_without_scheme',
          control_server_url='dialer:8000',
          expected_host='dialer',
          expected_port=8008,
      ),
      dict(
          testcase_name='http_scheme_with_port',
          control_server_url='http://dialer:8000',
          expected_host='dialer',
          expected_port=8008,
      ),
      dict(
          testcase_name='https_scheme_with_port_and_path',
          control_server_url='https://ctrl.example.com:8443/api',
          expected_host='ctrl.example.com',
          expected_port=8451,
      ),
      dict(
          testcase_name='url_with_glob_metacharacters',
          control_server_url='http://ctrl.example.com:8000/api?a=1&b=*',
          expected_host='ctrl.example.com',
          expected_port=8008,
      ),
      dict(
          testcase_name='http_scheme_without_port',
          control_server_url='http://ctrl.example.com',
          expected_host='ctrl.example.com',
          expected_port=88,
      ),
      dict(
          testcase_name='host_only_without_scheme_or_port',
          control_server_url='ctrl.example.com',
          expected_host='ctrl.example.com',
          expected_port=88,
      ),
  )
  def test_start_netdata_headless_collector_writes_stream_conf(
      self, control_server_url: str, expected_host: str, expected_port: int
  ):
    storage_dir = self.create_tempdir()
    netdata_dir = os.path.join(storage_dir.full_path, 'netdata')
    os.makedirs(netdata_dir, exist_ok=True)
    netdata_args_file = os.path.join(storage_dir.full_path, 'netdata_args.txt')

    script = f"""
      set -euo pipefail
      source "{_SERVE_SH}"
      function netdata {{
        printf '%s\\n' "$@" > "{netdata_args_file}"
      }}
      STORAGE_PATH="{storage_dir.full_path}"
      MTT_CONTROL_SERVER_URL='{control_server_url}'
      start_netdata_headless_collector
      wait
    """
    result = subprocess.run(
        ['bash', '-c', script],
        capture_output=True,
        text=True,
        check=False,
    )

    self.assertEqual(result.returncode, 0, msg=result.stderr)
    stream_conf_path = os.path.join(netdata_dir, 'stream.conf')
    with open(stream_conf_path, 'r', encoding='utf-8') as f:
      stream_conf = f.read()
    expected_conf = (
        '[stream]\n'
        '  enabled = yes\n'
        f'  destination = {expected_host}\n'
        '  api key = 2ba5b231-875d-4d39-82b0-adafd4c977d9\n'
        f'  default port = {expected_port}\n'
    )
    self.assertEqual(stream_conf, expected_conf)
    self.assertTrue(os.path.exists(netdata_args_file))

  def test_setup_runtime_parses_args_and_derives_ports(self):
    work_dir = self.create_tempdir()
    storage_path = os.path.join(work_dir.full_path, 'storage')
    state_file = os.path.join(work_dir.full_path, 'state.txt')

    script = textwrap.dedent(f"""\
        set -e
        source "{_SERVE_SH}"
        function adb {{
          echo "Android Debug Bridge version 1.0.41"
          echo "Version 34.0.5"
        }}
        setup_runtime \\
          --port 8100 \\
          --storage_path "{storage_path}" \\
          --working_dir "{work_dir.full_path}" \\
          --control_server_url "dialer:8100"
        cat <<EOF > "{state_file}"
        ADB_VERSION=${{ADB_VERSION}}
        MTT_PORT=${{MTT_PORT}}
        MTT_CORE_PORT=${{MTT_CORE_PORT}}
        MTT_TFC_PORT=${{MTT_TFC_PORT}}
        FILE_SERVER_PORT=${{FILE_SERVER_PORT}}
        DATASTORE_EMULATOR_PORT=${{DATASTORE_EMULATOR_PORT}}
        NETDATA_PORT=${{NETDATA_PORT}}
        MTT_CONTROL_SERVER_URL=${{MTT_CONTROL_SERVER_URL}}
        EXIT_TRAP=$(trap -p EXIT)
        EOF
    """)
    result = subprocess.run(
        ['bash', '-c', script],
        capture_output=True,
        text=True,
        check=False,
    )

    self.assertEqual(result.returncode, 0, msg=result.stderr)
    with open(state_file, 'r', encoding='utf-8') as f:
      state = dict(
          line.rstrip('\n').split('=', 1) for line in f if '=' in line
      )
    self.assertDictEqual(
        state,
        {
            'ADB_VERSION': '34.0.5',
            'MTT_PORT': '8100',
            'MTT_CORE_PORT': '8101',
            'MTT_TFC_PORT': '8102',
            'FILE_SERVER_PORT': '8106',
            'DATASTORE_EMULATOR_PORT': '8107',
            'NETDATA_PORT': '8108',
            'MTT_CONTROL_SERVER_URL': 'dialer:8100',
            'EXIT_TRAP': '',
        },
    )
    self.assertTrue(os.path.isdir(os.path.join(storage_path, 'netdata', 'log')))

  def test_main_entrypoint_forwards_args_and_rejects_unknown_flag(self):
    bin_dir = self.create_tempdir()
    adb_stub = os.path.join(bin_dir.full_path, 'adb')
    with open(adb_stub, 'w', encoding='utf-8') as f:
      f.write('#!/bin/bash\necho "Version 34.0.5"\n')
    os.chmod(adb_stub, stat.S_IRWXU)
    pkill_stub = os.path.join(bin_dir.full_path, 'pkill')
    with open(pkill_stub, 'w', encoding='utf-8') as f:
      f.write('#!/bin/bash\nexit 0\n')
    os.chmod(pkill_stub, stat.S_IRWXU)

    env = os.environ.copy()
    env['PATH'] = f"{bin_dir.full_path}:{env.get('PATH', '')}"
    result = subprocess.run(
        [_SERVE_SH, '--unknown_flag', 'value'],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    self.assertEqual(result.returncode, 1, msg=result.stderr)
    self.assertIn('Unknown argument --unknown_flag', result.stdout)
    self.assertIn('Cleaning up...', result.stdout)


if __name__ == '__main__':
  absltest.main()
