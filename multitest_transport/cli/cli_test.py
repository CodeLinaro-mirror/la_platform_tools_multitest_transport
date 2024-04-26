# Copyright 2019 Google LLC
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

"""Unit tests for cli."""
import os
import shutil
import tempfile
import time
from unittest import mock

from absl.testing import absltest
from absl.testing import parameterized
from tradefed_cluster.configs import lab_config


from multitest_transport.cli import command_util
from multitest_transport.cli import common
from multitest_transport.cli import cli
from multitest_transport.cli import cli_util
from multitest_transport.cli import google_auth_util
from multitest_transport.cli import unittest_util

_DOCKER_VERSION_STRING = 'Docker version 18.06.1-ce'
_DEFAULT_CREATE_ARGS = (
    '-v', '/dev/bus/usb:/dev/bus/usb',
    '--device-cgroup-rule', 'c 189:* rwm',
    '--cap-add', 'syslog',
    '--log-opt', 'max-size=200m', '--log-opt', 'max-file=5',
)


class CliTest(parameterized.TestCase):
  """Unit tests for cli."""

  def setUp(self):
    super(CliTest, self).setUp()
    self.mock_context = mock.MagicMock()
    self.context_patcher = mock.patch(
        '__main__.cli.command_util.CommandContext',
        return_value=self.mock_context)
    self.mock_create_context = self.context_patcher.start()
    self.enable_ipv6 = False
    self.mock_context.Run.side_effect = self._MockRun
    self.mock_context.IsLocal.return_value = True

    self.mock_socket = mock.MagicMock()
    self.mock_socket.__enter__.return_value = self.mock_socket
    self.socket_patcher = mock.patch(
        '__main__.cli.socket.socket',
        return_value=self.mock_socket)
    self.socket_patcher.start()
    self.mock_auth_patcher = mock.patch(
        '__main__.cli.command_util.google_auth_util'
        '.CreateCredentialFromServiceAccount')
    self.mock_auth_patcher.start()
    self.expanduser_patcher = mock.patch('__main__.os.path.expanduser')
    self.mock_expanduser = self.expanduser_patcher.start()
    self.mock_expanduser.side_effect = lambda s: s.replace('~', '/local')
    self.file_exists_patcher = mock.patch(
        '__main__.os.path.exists',
        side_effect=lambda p: p in self.mock_exist_files)
    self.file_exists_patcher.start()
    self.mock_exist_files = ['/dev/kvm', '/dev/vhost-vsock', '/dev/net/tun',
                             '/dev/vhost-net', '/local/.android',
                             '/mock/id_rsa']
    self.old_user = os.environ.get('USER')
    os.environ['USER'] = 'user'
    self.mock_timezone_patcher = mock.patch(
        '__main__.cli._GetHostTimezone', return_value='Etc/UTC')
    self.mock_timezone_patcher.start()
    self.mock_waiter_patcher = mock.patch('__main__.cli._WaitForServer')
    self.mock_waiter_patcher.start()
    self.tmp_root = tempfile.mkdtemp()
    self.get_version_patcher = mock.patch.object(
        cli_util, 'GetVersion',
        return_value=('dev_version', 'dev'))
    self.get_version_patcher.start()

    self.arg_parser = cli.CreateParser()
    self.arg_parser.add_argument('--cli_path', default='cli_path')

    self.mock_control_server_client = mock.MagicMock()
    self.submit_host_update_event_patcher = mock.patch.object(
        cli.host_util.control_server_util, 'ControlServerClient',
        return_value=self.mock_control_server_client)
    self.submit_host_update_event_patcher.start()
    self.mock_tf_console_started_patcher = mock.patch.object(
        cli, '_IsConsoleSuccessfullyStarted', return_value=True
    )
    self.mock_tf_console_started_patcher.start()
    self.mock_tf_console_print_out_patcher = mock.patch.object(
        command_util.DockerContext, 'RequestTfConsolePrintOut',
        return_value=None)
    self.mock_tf_console_print_out_patcher.start()

  def tearDown(self):
    self.get_version_patcher.stop()
    os.environ['USER'] = self.old_user
    self.expanduser_patcher.stop()
    self.file_exists_patcher.stop()
    self.mock_auth_patcher.stop()
    self.socket_patcher.stop()
    self.context_patcher.stop()
    self.submit_host_update_event_patcher.stop()
    try:
      self.mock_tf_console_started_patcher.stop()
    except RuntimeError:
      # ignore if mock_tf_console_started_patcher already stoped in the test
      pass
    shutil.rmtree(self.tmp_root)
    super(CliTest, self).tearDown()

  def testGetDockerImageName(self):
    self.assertEqual(
        'image:xxx',
        cli._GetDockerImageName('image:xxx'))
    self.assertEqual(
        'image:yyy',
        cli._GetDockerImageName('image:xxx', tag='yyy'))

  def _MockRun(self, command, **_kwargs):
    """Mock CommandContext.Run."""
    res = mock.MagicMock(return_code=0)
    if command == ['docker', '-v']:
      res.stdout = _DOCKER_VERSION_STRING
    if (command[:2] == ['docker', 'inspect'] and
        command[3:] == ['--format', '{{json .Config.Env}}']):
      res.stdout = '["MTT_SUPPORT_BRIDGE_NETWORK=true"]'
    if command[:4] == ['docker', 'network', 'inspect', 'bridge']:
      res.stdout = ('{"EnableIPv6":%s,"IPAM":{"Config":['
                    '{"Subnet":"2001:db8::/56"},'
                    '{"Subnet":"192.168.9.0/24","Gateway":"192.168.9.1"}'
                    ']}}' % ('true' if self.enable_ipv6 else 'false'))
    return res

  def _CreateHost(self,
                  hostname='mock-host',
                  cluster_name=None,
                  login_name=None,
                  tmpfs_configs=None,
                  docker_image='gcr.io/android-mtt/mtt:prod',
                  graceful_shutdown=False,
                  shutdown_timeout_sec=0,
                  enable_stackdriver=False,
                  lab_name=None,
                  enable_autoupdate=None,
                  service_account_json_key_path=None,
                  extra_docker_args=(),
                  control_server_url='url',
                  enable_ui_update=False,
                  operation_mode=None,
                  max_local_virtual_devices=None,
                  secret_project_id=None,
                  service_account_key_secret_id=None,
                  max_concurrent_update_percentage=None,
                  ):

    host = cli.host_util.Host(
        lab_config.CreateHostConfig(
            hostname=hostname,
            lab_name=lab_name,
            cluster_name=cluster_name,
            host_login_name=login_name,
            tmpfs_configs=tmpfs_configs,
            docker_image=docker_image,
            control_server_url=control_server_url,
            graceful_shutdown=graceful_shutdown,
            shutdown_timeout_sec=shutdown_timeout_sec,
            enable_stackdriver=enable_stackdriver,
            enable_autoupdate=enable_autoupdate,
            enable_ui_update=enable_ui_update,
            service_account_json_key_path=service_account_json_key_path,
            extra_docker_args=list(extra_docker_args),
            operation_mode=operation_mode,
            max_local_virtual_devices=max_local_virtual_devices,
            secret_project_id=secret_project_id,
            service_account_key_secret_id=service_account_key_secret_id,
            max_concurrent_update_percentage=max_concurrent_update_percentage))
    host.context = self.mock_context
    return host

  @mock.patch.object(cli_util, 'GetVersion')
  def testCheckDockerImageVersion(self, mock_get_version):
    docker_helper = mock.MagicMock()
    container_name = 'container_name'
    mock_get_version.return_value = ('prod_R9.202009.001', 'prod')
    docker_helper.Exec.return_value = mock.MagicMock(
        stdout='prod_R9.202009.001')

    cli._CheckDockerImageVersion(docker_helper, container_name)

  @mock.patch.object(cli_util, 'GetVersion')
  def testCheckDockerImageVersion_withNewerImage(self, mock_get_version):
    docker_helper = mock.MagicMock()
    container_name = 'container_name'
    mock_get_version.return_value = ('prod_R9.202009.001', 'prod')
    docker_helper.Exec.return_value = mock.MagicMock(
        stdout='prod_R10.202010.001')

    with self.assertRaises(cli.ActionableError):
      cli._CheckDockerImageVersion(docker_helper, container_name)

  @mock.patch.object(cli_util, 'GetVersion')
  def testCheckDockerImageVersion_withOlderImage(self, mock_get_version):
    docker_helper = mock.MagicMock()
    container_name = 'container_name'
    mock_get_version.return_value = ('prod_R9.202009.001', 'prod')
    docker_helper.Exec.return_value = mock.MagicMock(
        stdout='prod_R8.202008.001')

    cli._CheckDockerImageVersion(docker_helper, container_name)

  @mock.patch.object(cli_util, 'GetVersion')
  def testCheckDockerImageVersion_multipleUnderScore(self, mock_get_version):
    docker_helper = mock.MagicMock()
    container_name = 'container_name'
    mock_get_version.return_value = ('prod_R9_202009_001', 'prod')
    docker_helper.Exec.return_value = mock.MagicMock(
        stdout='prod_R9_202009_001')

    cli._CheckDockerImageVersion(docker_helper, container_name)

  @mock.patch.object(cli_util, 'GetVersion')
  def testCheckDockerImageVersion_invalidVersion(self, mock_get_version):
    docker_helper = mock.MagicMock()
    container_name = 'container_name'
    mock_get_version.return_value = ('presubmit_227550af-6c61', 'presubmit')
    docker_helper.Exec.return_value = mock.MagicMock(
        stdout='prod_R8.202008.001')

    cli._CheckDockerImageVersion(docker_helper, container_name)

  @mock.patch.object(command_util.DockerContext, 'Run')
  def testCheckConsoleSuccessfullyStarted_withSuccessIndicator(
      self, mock_command_result):
    self.mock_tf_console_started_patcher.stop()
    mock_command_result.return_value = common.CommandResult(
        return_code=0, stdout=cli._TF_CONSOLE_SUCCESS_INDICATOR, stderr='')
    self.assertTrue(
        cli._IsConsoleSuccessfullyStarted(self._CreateHost(), False)
    )

  @mock.patch.object(command_util.DockerContext, 'Run')
  def testCheckConsoleSuccessfullyStarted_withOmniBasedSuccessIndicator(
      self, mock_command_result
  ):
    self.mock_tf_console_started_patcher.stop()
    mock_command_result.return_value = common.CommandResult(
        return_code=0, stdout=cli._OMNI_LAB_SERVER_SUCCESS_INDICATOR, stderr=''
    )
    self.assertTrue(
        cli._IsConsoleSuccessfullyStarted(self._CreateHost(), True)
    )

  @mock.patch.object(command_util.DockerContext, 'Run')
  def testCheckConsoleSuccessfullyStarted_withException(
      self, mock_command_result):
    self.mock_tf_console_started_patcher.stop()
    stderr = 'com.android.tradefed.config.ConfigurationException'
    mock_command_result.return_value = common.CommandResult(
        return_code=0, stdout='', stderr=stderr)
    with self.assertRaisesRegex(
        RuntimeError, r'.*ATS failed to start with exception:*'):
      cli._IsConsoleSuccessfullyStarted(self._CreateHost(), False)

  @mock.patch.object(time, 'time')
  @mock.patch.object(command_util.DockerContext, 'Run')
  def testCheckConsoleSuccessfullyStarted_withTimeout(
      self, mock_command_result, mock_time):
    self.mock_tf_console_started_patcher.stop()
    mock_command_result.return_value = common.CommandResult(
        return_code=0, stdout='', stderr='')
    mock_time.side_effect = iter([0, cli._MTT_SERVER_WAIT_TIME_SECONDS + 1])
    with self.assertRaisesRegex(
        RuntimeError, r'.*ATS replica failed to start in*'):
      cli._IsConsoleSuccessfullyStarted(self._CreateHost(), False)

  def testStart(self):
    """Test start without service account."""
    args = self.arg_parser.parse_args(['start'])
    cli.Start(
        args,
        self._CreateHost(
            cluster_name='acluster',
            lab_name='alab'))

    self.mock_context.Run.assert_has_calls([
        mock.call([
            'docker', 'create',
            '--name', 'mtt', '-it',
            *_DEFAULT_CREATE_ARGS,
            '--hostname', 'mock-host',
            '--network', 'bridge',
            '-e', 'OPERATION_MODE=unknown',
            '-e', 'MTT_CLI_VERSION=dev_version',
            '-e', 'MTT_CONTROL_SERVER_URL=url',
            '-e', 'LAB_NAME=alab',
            '-e', 'CLUSTER=acluster',
            '-e', 'IMAGE_NAME=gcr.io/android-mtt/mtt:prod',
            '-e', 'USER=user',
            '-e', 'TZ=Etc/UTC',
            '-e', 'MTT_SERVER_LOG_LEVEL=info',
            '--mount', 'type=volume,src=mtt-data,dst=/data',
            '--mount', 'type=volume,src=mtt-temp,dst=/tmp',
            '--mount', 'type=bind,src=/local/.android,dst=/root/.android',
            '--mount', ('type=bind,src=/var/run/docker.sock,'
                        'dst=/var/run/docker.sock'),
            '--mount', ('type=bind,src=/local/.ats_storage,'
                        'dst=/tmp/.mnt/.ats_storage'),
            '-p', '127.0.0.1:5037:5037',
            '--cap-add', 'sys_admin',
            '--device', '/dev/fuse',
            '--security-opt', 'apparmor:unconfined',
            '--security-opt', 'seccomp=/tmp/mtt_seccomp.json',
            'gcr.io/android-mtt/mtt:prod']),
        mock.call(['docker', 'start', 'mtt']),
        mock.call(
            ['docker', 'exec', 'mtt', 'printenv', 'MTT_VERSION'],
            raise_on_failure=False),
    ])

  @mock.patch.dict(
      os.environ, {
          'http_proxy': 'http_proxy',
          'https_proxy': 'https_proxy',
          'ftp_proxy': 'ftp_proxy',
          'no_proxy': 'no_proxy'
      })
  def testStart_withProxySettings(self):
    """Test start with local proxy settings."""
    args = self.arg_parser.parse_args(['start'])
    cli.Start(
        args,
        self._CreateHost(hostname='ahost', cluster_name='acluster'))

    self.mock_context.Run.assert_has_calls([
        mock.call([
            'docker', 'create',
            '--name', 'mtt', '-it',
            *_DEFAULT_CREATE_ARGS,
            '--hostname', 'ahost',
            '--network', 'bridge',
            '-e', 'OPERATION_MODE=unknown',
            '-e', 'MTT_CLI_VERSION=dev_version',
            '-e', 'MTT_CONTROL_SERVER_URL=url',
            '-e', 'CLUSTER=acluster',
            '-e', 'IMAGE_NAME=gcr.io/android-mtt/mtt:prod',
            '-e', 'USER=user',
            '-e', 'TZ=Etc/UTC',
            '-e', 'HTTP_PROXY=http_proxy',
            '-e', 'HTTPS_PROXY=https_proxy',
            '-e', 'FTP_PROXY=ftp_proxy',
            '-e', 'NO_PROXY=127.0.0.1,::1,localhost,ahost,no_proxy',
            '-e', 'MTT_SERVER_LOG_LEVEL=info',
            '--mount', 'type=volume,src=mtt-data,dst=/data',
            '--mount', 'type=volume,src=mtt-temp,dst=/tmp',
            '--mount', 'type=bind,src=/local/.android,dst=/root/.android',
            '--mount', ('type=bind,src=/var/run/docker.sock,'
                        'dst=/var/run/docker.sock'),
            '--mount', ('type=bind,src=/local/.ats_storage,'
                        'dst=/tmp/.mnt/.ats_storage'),
            '-p', '127.0.0.1:5037:5037',
            '--cap-add', 'sys_admin',
            '--device', '/dev/fuse',
            '--security-opt', 'apparmor:unconfined',
            '--security-opt', 'seccomp=/tmp/mtt_seccomp.json',
            'gcr.io/android-mtt/mtt:prod']),
        mock.call(['docker', 'start', 'mtt']),
        mock.call(
            ['docker', 'exec', 'mtt', 'printenv', 'MTT_VERSION'],
            raise_on_failure=False),
    ])

  @mock.patch.object(cli.command_util.DockerHelper, 'IsContainerRunning')
  def testStart_alreadyRunning(self, mock_is_running):
    """Test start with MTT already running."""
    mock_is_running.return_value = True

    args = self.arg_parser.parse_args(['start'])
    cli.Start(args, self._CreateHost(cluster_name='acluster'))

    # exited early after checking docker and authentication
    self.mock_context.IsLocal.assert_not_called()
    self.mock_context.CopyFile.assert_not_called()
    self.assertEqual(2, self.mock_context.Run.call_count)

  def testStart_localNoAndroid(self):
    """Test start local but no ~/.android."""
    self.mock_exist_files = []
    args = self.arg_parser.parse_args(['start'])
    cli.Start(
        args,
        self._CreateHost(cluster_name='acluster'))

    self.mock_context.Run.assert_has_calls([
        mock.call([
            'docker', 'create',
            '--name', 'mtt', '-it',
            *_DEFAULT_CREATE_ARGS,
            '--hostname', 'mock-host',
            '--network', 'bridge',
            '-e', 'OPERATION_MODE=unknown',
            '-e', 'MTT_CLI_VERSION=dev_version',
            '-e', 'MTT_CONTROL_SERVER_URL=url',
            '-e', 'CLUSTER=acluster',
            '-e', 'IMAGE_NAME=gcr.io/android-mtt/mtt:prod',
            '-e', 'USER=user',
            '-e', 'TZ=Etc/UTC',
            '-e', 'MTT_SERVER_LOG_LEVEL=info',
            '--mount', 'type=volume,src=mtt-data,dst=/data',
            '--mount', 'type=volume,src=mtt-temp,dst=/tmp',
            '--mount', ('type=bind,src=/var/run/docker.sock,'
                        'dst=/var/run/docker.sock'),
            '--mount', ('type=bind,src=/local/.ats_storage,'
                        'dst=/tmp/.mnt/.ats_storage'),
            '-p', '127.0.0.1:5037:5037',
            '--cap-add', 'sys_admin',
            '--device', '/dev/fuse',
            '--security-opt', 'apparmor:unconfined',
            '--security-opt', 'seccomp=/tmp/mtt_seccomp.json',
            'gcr.io/android-mtt/mtt:prod']),
        mock.call(['docker', 'start', 'mtt']),
        mock.call(
            ['docker', 'exec', 'mtt', 'printenv', 'MTT_VERSION'],
            raise_on_failure=False),
    ])

  def testStart_withServiceAccount(self):
    """Test Start function."""
    args = self.arg_parser.parse_args([
        'start', '--service_account_json_key_path', '/path/to/key.json'])
    cli.Start(
        args,
        self._CreateHost(
            cluster_name='acluster',
            service_account_json_key_path='/path/to/key.json'))

    self.mock_context.Run.assert_has_calls([
        mock.call(['docker', 'inspect', 'gcr.io/android-mtt/mtt:prod',
                   '--format', '{{json .Config.Env}}'],
                  raise_on_failure=False),
        mock.call(
            ['docker', 'volume', 'rm', 'mtt-temp'], raise_on_failure=False),
        mock.call(['mkdir', '-p', '/local/.ats_storage']),
        mock.call(['docker', 'network', 'inspect', 'bridge',
                   '--format={{json .}}'],
                  raise_on_failure=False),
        mock.call(['docker', 'container', 'rm', 'mtt'],
                  raise_on_failure=False),
        mock.call([
            'docker', 'create',
            '--name', 'mtt', '-it',
            *_DEFAULT_CREATE_ARGS,
            '--hostname', 'mock-host',
            '--network', 'bridge',
            '-e', 'OPERATION_MODE=unknown',
            '-e', 'MTT_CLI_VERSION=dev_version',
            '-e', 'MTT_CONTROL_SERVER_URL=url',
            '-e', 'CLUSTER=acluster',
            '-e', 'IMAGE_NAME=gcr.io/android-mtt/mtt:prod',
            '-e', 'USER=user',
            '-e', 'TZ=Etc/UTC',
            '-e', 'JSON_KEY_PATH=/tmp/keyfile/key.json',
            '-e', 'MTT_SERVER_LOG_LEVEL=info',
            '--mount', 'type=volume,src=mtt-data,dst=/data',
            '--mount', 'type=volume,src=mtt-temp,dst=/tmp',
            '--mount', 'type=volume,src=mtt-key,dst=/tmp/keyfile',
            '--mount', 'type=bind,src=/local/.android,dst=/root/.android',
            '--mount', ('type=bind,src=/var/run/docker.sock,'
                        'dst=/var/run/docker.sock'),
            '--mount', ('type=bind,src=/local/.ats_storage,'
                        'dst=/tmp/.mnt/.ats_storage'),
            '-p', '127.0.0.1:5037:5037',
            '--cap-add', 'sys_admin',
            '--device', '/dev/fuse',
            '--security-opt', 'apparmor:unconfined',
            '--security-opt', 'seccomp=/tmp/mtt_seccomp.json',
            'gcr.io/android-mtt/mtt:prod']),
        mock.call([
            'docker', 'cp', '-L',
            '/path/to/key.json', 'mtt:/tmp/keyfile/key.json']),
        mock.call(['docker', 'start', 'mtt']),
        mock.call(
            ['docker', 'exec', 'mtt', 'printenv', 'MTT_VERSION'],
            raise_on_failure=False),
    ])

  def testStart_onPremise(self):
    args = self.arg_parser.parse_args([
        'start', '--port', '8100', '--adb_server_port', '5137',
        '--operation_mode', 'ON_PREMISE'
    ])
    cli.Start(args, self._CreateHost())

    self.mock_context.Run.assert_has_calls([
        mock.call([
            'docker', 'create',
            '--name', 'mtt', '-it',
            *_DEFAULT_CREATE_ARGS,
            '--hostname', 'mock-host',
            '--network', 'bridge',
            '-e', 'OPERATION_MODE=on_premise',
            '-e', 'MTT_CLI_VERSION=dev_version',
            '-e', 'MTT_CONTROL_SERVER_URL=url',
            '-e', 'MTT_CONTROL_SERVER_PORT=8100',
            '-e', 'IMAGE_NAME=gcr.io/android-mtt/mtt:prod',
            '-e', 'USER=user',
            '-e', 'TZ=Etc/UTC',
            '-e', 'MTT_SERVER_LOG_LEVEL=info',
            '--mount', 'type=volume,src=mtt-data,dst=/data',
            '--mount', 'type=volume,src=mtt-temp,dst=/tmp',
            '--mount', 'type=bind,src=/local/.android,dst=/root/.android',
            '--mount', ('type=bind,src=/var/run/docker.sock,'
                        'dst=/var/run/docker.sock'),
            '--mount', ('type=bind,src=/local/.ats_storage,'
                        'dst=/tmp/.mnt/.ats_storage'),
            '-p', '0.0.0.0:8100:8100',
            '-p', '0.0.0.0:8105:8105',
            '-p', '0.0.0.0:8106:8106',
            '-p', '127.0.0.1:5137:5037',
            '--cap-add', 'sys_admin',
            '--device', '/dev/fuse',
            '--security-opt', 'apparmor:unconfined',
            '--security-opt', 'seccomp=/tmp/mtt_seccomp.json',
            'gcr.io/android-mtt/mtt:prod']),
        mock.call(['docker', 'start', 'mtt']),
        mock.call(
            ['docker', 'exec', 'mtt', 'printenv', 'MTT_VERSION'],
            raise_on_failure=False),
    ])

  def testStart_withHostConfig_onPremise(self):
    args = self.arg_parser.parse_args([
        'start', '--port', '8100', '--adb_server_port', '5137'
    ])
    cli.Start(args, self._CreateHost(operation_mode='ON_PREMISE'))

    self.mock_context.Run.assert_has_calls([
        mock.call([
            'docker', 'create',
            '--name', 'mtt', '-it',
            *_DEFAULT_CREATE_ARGS,
            '--hostname', 'mock-host',
            '--network', 'bridge',
            '-e', 'OPERATION_MODE=on_premise',
            '-e', 'MTT_CLI_VERSION=dev_version',
            '-e', 'MTT_CONTROL_SERVER_URL=url',
            '-e', 'MTT_CONTROL_SERVER_PORT=8100',
            '-e', 'IMAGE_NAME=gcr.io/android-mtt/mtt:prod',
            '-e', 'USER=user',
            '-e', 'TZ=Etc/UTC',
            '-e', 'MTT_SERVER_LOG_LEVEL=info',
            '--mount', 'type=volume,src=mtt-data,dst=/data',
            '--mount', 'type=volume,src=mtt-temp,dst=/tmp',
            '--mount', 'type=bind,src=/local/.android,dst=/root/.android',
            '--mount', ('type=bind,src=/var/run/docker.sock,'
                        'dst=/var/run/docker.sock'),
            '--mount', ('type=bind,src=/local/.ats_storage,'
                        'dst=/tmp/.mnt/.ats_storage'),
            '-p', '0.0.0.0:8100:8100',
            '-p', '0.0.0.0:8105:8105',
            '-p', '0.0.0.0:8106:8106',
            '-p', '127.0.0.1:5137:5037',
            '--cap-add', 'sys_admin',
            '--device', '/dev/fuse',
            '--security-opt', 'apparmor:unconfined',
            '--security-opt', 'seccomp=/tmp/mtt_seccomp.json',
            'gcr.io/android-mtt/mtt:prod']),
        mock.call(['docker', 'start', 'mtt']),
        mock.call(
            ['docker', 'exec', 'mtt', 'printenv', 'MTT_VERSION'],
            raise_on_failure=False),
    ])

  @mock.patch.object(cli, '_WaitForServer')
  def testStart_standalone(self, wait_for_server):
    wait_for_server.return_value = True

    args = self.arg_parser.parse_args([
        'start', '--port', '8100', '--adb_server_port', '5137'])
    cli.Start(args, self._CreateHost(control_server_url=None))

    self.mock_context.Run.assert_has_calls([
        mock.call([
            'docker', 'create',
            '--name', 'mtt', '-it',
            *_DEFAULT_CREATE_ARGS,
            '--hostname', 'mock-host',
            '--network', 'bridge',
            '-e', 'OPERATION_MODE=unknown',
            '-e', 'MTT_CLI_VERSION=dev_version',
            '-e', 'MTT_CONTROL_SERVER_PORT=8100',
            '-e', 'IMAGE_NAME=gcr.io/android-mtt/mtt:prod',
            '-e', 'USER=user',
            '-e', 'TZ=Etc/UTC',
            '-e', 'MTT_SERVER_LOG_LEVEL=info',
            '--mount', 'type=volume,src=mtt-data,dst=/data',
            '--mount', 'type=volume,src=mtt-temp,dst=/tmp',
            '--mount', 'type=bind,src=/local/.android,dst=/root/.android',
            '--mount', ('type=bind,src=/var/run/docker.sock,'
                        'dst=/var/run/docker.sock'),
            '--mount', ('type=bind,src=/local/.ats_storage,'
                        'dst=/tmp/.mnt/.ats_storage'),
            '-p', '0.0.0.0:8100:8100',
            '-p', '0.0.0.0:8105:8105',
            '-p', '0.0.0.0:8106:8106',
            '-p', '0.0.0.0:8108:8108',
            '-p', '127.0.0.1:5137:5037',
            '--cap-add', 'sys_admin',
            '--device', '/dev/fuse',
            '--security-opt', 'apparmor:unconfined',
            '--security-opt', 'seccomp=/tmp/mtt_seccomp.json',
            'gcr.io/android-mtt/mtt:prod']),
        mock.call(['docker', 'start', 'mtt']),
        mock.call(
            ['docker', 'exec', 'mtt', 'printenv', 'MTT_VERSION'],
            raise_on_failure=False),
    ])

  @mock.patch('__main__.cli.command_util.DockerHelper.IsContainerRunning')
  @mock.patch.object(cli, '_WaitForServer')
  def testStart_standaloneFailContainerRunning(
      self, wait_for_server, is_container_running):
    wait_for_server.return_value = False
    is_container_running.side_effect = [False, True]

    args = self.arg_parser.parse_args(['start'])
    with self.assertRaisesRegex(
        RuntimeError, r'.*ATS server failed to start.*'):
      cli.Start(args, self._CreateHost(control_server_url=None))

    self.mock_context.Run.assert_has_calls([
        mock.call(['docker', 'start', 'mtt']),
        mock.call(
            ['docker', 'exec', 'mtt', 'printenv', 'MTT_VERSION'],
            raise_on_failure=False),
        mock.call(
            ['docker', 'logs', 'mtt'], raise_on_failure=False),
        mock.call(
            ['docker', 'exec', 'mtt', 'cat', '/data/log/server/current'],
            raise_on_failure=False)
    ])

  @mock.patch('__main__.cli.command_util.DockerHelper.IsContainerRunning')
  @mock.patch.object(cli, '_WaitForServer')
  def testStart_standaloneFailContainerDead(
      self, wait_for_server, is_container_running):
    wait_for_server.return_value = False
    is_container_running.side_effect = [False, False]

    args = self.arg_parser.parse_args(['start'])
    with self.assertRaisesRegex(
        RuntimeError, r'.*ATS server failed to start.*'):
      cli.Start(args, self._CreateHost(control_server_url=None))

    self.mock_context.Run.assert_has_calls([
        mock.call(['docker', 'start', 'mtt']),
        mock.call(
            ['docker', 'exec', 'mtt', 'printenv', 'MTT_VERSION'],
            raise_on_failure=False),
        mock.call(
            ['docker', 'logs', 'mtt'], raise_on_failure=False),
        mock.call(
            ['docker', 'run', '--rm', '--entrypoint', 'cat',
             '--mount', 'type=volume,src=mtt-data,dst=/data',
             '--mount', 'type=volume,src=mtt-temp,dst=/tmp',
             'gcr.io/android-mtt/mtt:prod', '/data/log/server/current'],
            raise_on_failure=False)
    ])

  def testStart_argsWithContainerNameAndImageName(self):
    """Test Start function."""
    args = self.arg_parser.parse_args(
        ['start', '--name', 'acontainer', '--image_name', 'animage',
         '--tag', 'atag'])
    cli.Start(
        args,
        self._CreateHost(cluster_name='acluster'))

    self.mock_context.Run.assert_has_calls([
        mock.call(['docker', 'inspect', 'animage:atag',
                   '--format', '{{json .Config.Env}}'],
                  raise_on_failure=False),
        mock.call(
            ['docker', 'volume', 'rm', 'mtt-temp'], raise_on_failure=False),
        mock.call(['mkdir', '-p', '/local/.ats_storage']),
        mock.call(['docker', 'network', 'inspect', 'bridge',
                   '--format={{json .}}'],
                  raise_on_failure=False),
        mock.call(['docker', 'container', 'rm', 'acontainer'],
                  raise_on_failure=False),
        mock.call([
            'docker', 'create',
            '--name', 'acontainer', '-it',
            *_DEFAULT_CREATE_ARGS,
            '--hostname', 'mock-host',
            '--network', 'bridge',
            '-e', 'OPERATION_MODE=unknown',
            '-e', 'MTT_CLI_VERSION=dev_version',
            '-e', 'MTT_CONTROL_SERVER_URL=url',
            '-e', 'CLUSTER=acluster',
            '-e', 'IMAGE_NAME=animage:atag',
            '-e', 'USER=user',
            '-e', 'TZ=Etc/UTC',
            '-e', 'MTT_SERVER_LOG_LEVEL=info',
            '--mount', 'type=volume,src=mtt-data,dst=/data',
            '--mount', 'type=volume,src=mtt-temp,dst=/tmp',
            '--mount', 'type=bind,src=/local/.android,dst=/root/.android',
            '--mount', ('type=bind,src=/var/run/docker.sock,'
                        'dst=/var/run/docker.sock'),
            '--mount', ('type=bind,src=/local/.ats_storage,'
                        'dst=/tmp/.mnt/.ats_storage'),
            '-p', '127.0.0.1:5037:5037',
            '--cap-add', 'sys_admin',
            '--device', '/dev/fuse',
            '--security-opt', 'apparmor:unconfined',
            '--security-opt', 'seccomp=/tmp/mtt_seccomp.json',
            'animage:atag']),
        mock.call(['docker', 'start', 'acontainer']),
        mock.call(
            ['docker', 'exec', 'acontainer', 'printenv', 'MTT_VERSION'],
            raise_on_failure=False),
    ])

  @mock.patch.object(shutil, 'rmtree')
  @mock.patch.object(shutil, 'copy')
  @mock.patch.object(tempfile, 'mkdtemp')
  def testStart_adb(self, mock_temp_dir, mock_copy_file, mock_rm_dir):
    """Test starting with a custom ADB tool."""
    mock_temp_dir.return_value = '/tmp/dir'
    args = self.arg_parser.parse_args(
        ['start', '--custom_adb_path', '/local/adb'])
    cli.Start(
        args,
        self._CreateHost(cluster_name='acluster'))

    # file copied over to temp directory and ultimately cleaned up
    mock_copy_file.assert_called_with('/local/adb', '/tmp/dir/adb')
    mock_rm_dir.assert_called_with('/tmp/dir')

    self.mock_context.Run.assert_has_calls([
        mock.call([
            'docker', 'create',
            '--name', 'mtt', '-it',
            *_DEFAULT_CREATE_ARGS,
            '--hostname', 'mock-host',
            '--network', 'bridge',
            '-e', 'OPERATION_MODE=unknown',
            '-e', 'MTT_CLI_VERSION=dev_version',
            '-e', 'MTT_CONTROL_SERVER_URL=url',
            '-e', 'CLUSTER=acluster',
            '-e', 'IMAGE_NAME=gcr.io/android-mtt/mtt:prod',
            '-e', 'USER=user',
            '-e', 'TZ=Etc/UTC',
            '-e', 'MTT_SERVER_LOG_LEVEL=info',
            '--mount', 'type=volume,src=mtt-data,dst=/data',
            '--mount', 'type=volume,src=mtt-temp,dst=/tmp',
            '--mount', 'type=bind,src=/local/.android,dst=/root/.android',
            '--mount', ('type=bind,src=/var/run/docker.sock,'
                        'dst=/var/run/docker.sock'),
            '--mount', ('type=bind,src=/local/.ats_storage,'
                        'dst=/tmp/.mnt/.ats_storage'),
            '-p', '127.0.0.1:5037:5037',
            '--cap-add', 'sys_admin',
            '--device', '/dev/fuse',
            '--security-opt', 'apparmor:unconfined',
            '--security-opt', 'seccomp=/tmp/mtt_seccomp.json',
            'gcr.io/android-mtt/mtt:prod']),
        mock.call([  # temp directory copied over to container
            'docker',
            'cp', '-L', '/tmp/dir', 'mtt:/tmp/custom_sdk_tools']),
        mock.call(['docker', 'start', 'mtt']),
        mock.call(
            ['docker', 'exec', 'mtt', 'printenv', 'MTT_VERSION'],
            raise_on_failure=False),
    ])

  def testStart_withStackdriver(self):
    """Test Start with stackdriver logging enabled."""
    args = self.arg_parser.parse_args([
        'start', '--service_account_json_key_path', '/path/to/key.json'])
    cli.Start(
        args,
        self._CreateHost(
            cluster_name='acluster',
            enable_stackdriver=True,
            service_account_json_key_path='/path/to/key.json'))

    self.mock_context.Run.assert_has_calls([
        mock.call(['docker', 'inspect', 'gcr.io/android-mtt/mtt:prod',
                   '--format', '{{json .Config.Env}}'],
                  raise_on_failure=False),
        mock.call(
            ['docker', 'volume', 'rm', 'mtt-temp'], raise_on_failure=False),
        mock.call(['mkdir', '-p', '/local/.ats_storage']),
        mock.call(['docker', 'network', 'inspect', 'bridge',
                   '--format={{json .}}'],
                  raise_on_failure=False),
        mock.call(['docker', 'container', 'rm', 'mtt'],
                  raise_on_failure=False),
        mock.call([
            'docker', 'create',
            '--name', 'mtt', '-it',
            *_DEFAULT_CREATE_ARGS,
            '--hostname', 'mock-host',
            '--network', 'bridge',
            '-e', 'OPERATION_MODE=unknown',
            '-e', 'MTT_CLI_VERSION=dev_version',
            '-e', 'MTT_CONTROL_SERVER_URL=url',
            '-e', 'CLUSTER=acluster',
            '-e', 'IMAGE_NAME=gcr.io/android-mtt/mtt:prod',
            '-e', 'USER=user',
            '-e', 'TZ=Etc/UTC',
            '-e', 'JSON_KEY_PATH=/tmp/keyfile/key.json',
            '-e', 'ENABLE_STACKDRIVER_LOGGING=1',
            '-e', 'ENABLE_STACKDRIVER_MONITORING=1',
            '-e', 'MTT_SERVER_LOG_LEVEL=info',
            '--mount', 'type=volume,src=mtt-data,dst=/data',
            '--mount', 'type=volume,src=mtt-temp,dst=/tmp',
            '--mount', 'type=volume,src=mtt-key,dst=/tmp/keyfile',
            '--mount', 'type=bind,src=/local/.android,dst=/root/.android',
            '--mount', ('type=bind,src=/var/run/docker.sock,'
                        'dst=/var/run/docker.sock'),
            '--mount', ('type=bind,src=/local/.ats_storage,'
                        'dst=/tmp/.mnt/.ats_storage'),
            '-p', '127.0.0.1:5037:5037',
            '--cap-add', 'sys_admin',
            '--device', '/dev/fuse',
            '--security-opt', 'apparmor:unconfined',
            '--security-opt', 'seccomp=/tmp/mtt_seccomp.json',
            'gcr.io/android-mtt/mtt:prod']),
        mock.call([
            'docker', 'cp', '-L',
            '/path/to/key.json', 'mtt:/tmp/keyfile/key.json']),
        mock.call(['docker', 'start', 'mtt']),
        mock.call(
            ['docker', 'exec', 'mtt', 'printenv', 'MTT_VERSION'],
            raise_on_failure=False),
    ])

  def testStart_withTmpfs(self):
    """Test Start with tmpfs."""
    args = self.arg_parser.parse_args(['start'])
    cli.Start(
        args,
        self._CreateHost(
            cluster_name='acluster',
            tmpfs_configs=[
                lab_config.CreateTmpfsConfig('/atmpfs', 1000, '750')]))

    self.mock_context.Run.assert_has_calls([
        mock.call(['docker', 'inspect', 'gcr.io/android-mtt/mtt:prod',
                   '--format', '{{json .Config.Env}}'],
                  raise_on_failure=False),
        mock.call(
            ['docker', 'volume', 'rm', 'mtt-temp'], raise_on_failure=False),
        mock.call(['mkdir', '-p', '/local/.ats_storage']),
        mock.call(['docker', 'network', 'inspect', 'bridge',
                   '--format={{json .}}'],
                  raise_on_failure=False),
        mock.call(['docker', 'container', 'rm', 'mtt'],
                  raise_on_failure=False),
        mock.call([
            'docker', 'create',
            '--name', 'mtt', '-it',
            *_DEFAULT_CREATE_ARGS,
            '--hostname', 'mock-host',
            '--network', 'bridge',
            '-e', 'OPERATION_MODE=unknown',
            '-e', 'MTT_CLI_VERSION=dev_version',
            '-e', 'MTT_CONTROL_SERVER_URL=url',
            '-e', 'CLUSTER=acluster',
            '-e', 'IMAGE_NAME=gcr.io/android-mtt/mtt:prod',
            '-e', 'USER=user',
            '-e', 'TZ=Etc/UTC',
            '-e', 'MTT_SERVER_LOG_LEVEL=info',
            '--mount', 'type=volume,src=mtt-data,dst=/data',
            '--mount', 'type=volume,src=mtt-temp,dst=/tmp',
            '--mount', 'type=bind,src=/local/.android,dst=/root/.android',
            '--mount', ('type=bind,src=/var/run/docker.sock,'
                        'dst=/var/run/docker.sock'),
            '--mount', ('type=bind,src=/local/.ats_storage,'
                        'dst=/tmp/.mnt/.ats_storage'),
            '--mount', 'type=tmpfs,dst=/atmpfs,tmpfs-size=1000,tmpfs-mode=750',
            '-p', '127.0.0.1:5037:5037',
            '--cap-add', 'sys_admin',
            '--device', '/dev/fuse',
            '--security-opt', 'apparmor:unconfined',
            '--security-opt', 'seccomp=/tmp/mtt_seccomp.json',
            'gcr.io/android-mtt/mtt:prod']),
        mock.call(['docker', 'start', 'mtt']),
        mock.call(
            ['docker', 'exec', 'mtt', 'printenv', 'MTT_VERSION'],
            raise_on_failure=False),
    ])

  def testStart_imageNameAndControlServerUrlInHost(self):
    """Test start with image name and primary url in host."""
    args = self.arg_parser.parse_args(['start'])
    cli.Start(
        args,
        self._CreateHost(
            cluster_name='acluster',
            control_server_url='tfc',
            docker_image='a_docker_image'))

    self.mock_context.Run.assert_has_calls([
        mock.call([
            'docker', 'create',
            '--name', 'mtt', '-it',
            *_DEFAULT_CREATE_ARGS,
            '--hostname', 'mock-host',
            '--network', 'bridge',
            '-e', 'OPERATION_MODE=unknown',
            '-e', 'MTT_CLI_VERSION=dev_version',
            '-e', 'MTT_CONTROL_SERVER_URL=tfc',
            '-e', 'CLUSTER=acluster',
            '-e', 'IMAGE_NAME=a_docker_image',
            '-e', 'USER=user',
            '-e', 'TZ=Etc/UTC',
            '-e', 'MTT_SERVER_LOG_LEVEL=info',
            '--mount', 'type=volume,src=mtt-data,dst=/data',
            '--mount', 'type=volume,src=mtt-temp,dst=/tmp',
            '--mount', 'type=bind,src=/local/.android,dst=/root/.android',
            '--mount', ('type=bind,src=/var/run/docker.sock,'
                        'dst=/var/run/docker.sock'),
            '--mount', ('type=bind,src=/local/.ats_storage,'
                        'dst=/tmp/.mnt/.ats_storage'),
            '-p', '127.0.0.1:5037:5037',
            '--cap-add', 'sys_admin',
            '--device', '/dev/fuse',
            '--security-opt', 'apparmor:unconfined',
            '--security-opt', 'seccomp=/tmp/mtt_seccomp.json',
            'a_docker_image']),
        mock.call(['docker', 'start', 'mtt']),
        mock.call(
            ['docker', 'exec', 'mtt', 'printenv', 'MTT_VERSION'],
            raise_on_failure=False),
    ])

  @mock.patch.object(cli, '_StartMttNode')
  @mock.patch.object(cli, '_StartMttDaemon')
  def testStart_EnableAutoupdate_DaemonAlreadyActive(
      self, start_mttd, start_mtt):
    args = self.arg_parser.parse_args(['start'])
    host = self._CreateHost(
        cluster_name='acluster', hostname='ahost', enable_autoupdate=True)

    cli.Start(args, host)

    start_mtt.assert_not_called()
    start_mttd.assert_called_once_with(args, host)

  @mock.patch.object(cli, '_StartMttNode')
  @mock.patch.object(cli, '_StartMttDaemon')
  def testStart_EnableUiUpdate(
      self, start_mttd, start_mtt):
    args = self.arg_parser.parse_args(['start'])
    host = self._CreateHost(enable_ui_update=True)
    cli.Start(args, host)
    start_mttd.assert_called_once_with(args, host)
    start_mtt.assert_not_called()
    (self.mock_control_server_client.PatchTestHarnessImageToHostMetadata
     .assert_called_with(host.config.hostname, host.config.docker_image))

  def testStart_withLocalVirtualDevice(self):
    """Test start with virtual device enabled."""
    args = self.arg_parser.parse_args(
        ['start', '--max_local_virtual_devices', '1'])
    cli.Start(args, self._CreateHost())

    self.mock_context.Run.assert_has_calls([
        mock.call([
            'docker', 'create',
            '--name', 'mtt', '-it',
            *_DEFAULT_CREATE_ARGS,
            '--hostname', 'mock-host',
            '--network', 'bridge',
            '-e', 'OPERATION_MODE=unknown',
            '-e', 'MTT_CLI_VERSION=dev_version',
            '-e', 'MTT_CONTROL_SERVER_URL=url',
            '-e', 'IMAGE_NAME=gcr.io/android-mtt/mtt:prod',
            '-e', 'USER=user',
            '-e', 'TZ=Etc/UTC',
            '-e', 'MTT_SERVER_LOG_LEVEL=info',
            '-e', 'MAX_LOCAL_VIRTUAL_DEVICES=1',
            '--mount', 'type=volume,src=mtt-data,dst=/data',
            '--mount', 'type=volume,src=mtt-temp,dst=/tmp',
            '--mount', 'type=bind,src=/local/.android,dst=/root/.android',
            '--mount', ('type=bind,src=/var/run/docker.sock,'
                        'dst=/var/run/docker.sock'),
            '--mount', ('type=bind,src=/local/.ats_storage,'
                        'dst=/tmp/.mnt/.ats_storage'),
            '-p', '127.0.0.1:5037:5037',
            '--cap-add', 'sys_admin',
            '--cap-add', 'net_admin',
            '--device', '/dev/fuse',
            '--device', '/dev/kvm',
            '--device', '/dev/vhost-vsock',
            '--device', '/dev/net/tun',
            '--device', '/dev/vhost-net',
            '--security-opt', 'apparmor:unconfined',
            '--security-opt', 'seccomp=/tmp/mtt_seccomp.json',
            'gcr.io/android-mtt/mtt:prod']),
        mock.call(['docker', 'start', 'mtt']),
        mock.call(
            ['docker', 'exec', 'mtt', 'printenv', 'MTT_VERSION'],
            raise_on_failure=False),
    ])

  def testStart_withLocalVirtualDeviceInHostConfig(self):
    """Test start with virtual device configured in host config."""
    args = self.arg_parser.parse_args(['start'])
    cli.Start(args, self._CreateHost(max_local_virtual_devices=5))

    self.mock_context.Run.assert_has_calls([
        mock.call([
            'docker', 'create',
            '--name', 'mtt', '-it',
            *_DEFAULT_CREATE_ARGS,
            '--hostname', 'mock-host',
            '--network', 'bridge',
            '-e', 'OPERATION_MODE=unknown',
            '-e', 'MTT_CLI_VERSION=dev_version',
            '-e', 'MTT_CONTROL_SERVER_URL=url',
            '-e', 'IMAGE_NAME=gcr.io/android-mtt/mtt:prod',
            '-e', 'USER=user',
            '-e', 'TZ=Etc/UTC',
            '-e', 'MTT_SERVER_LOG_LEVEL=info',
            '-e', 'MAX_LOCAL_VIRTUAL_DEVICES=5',
            '--mount', 'type=volume,src=mtt-data,dst=/data',
            '--mount', 'type=volume,src=mtt-temp,dst=/tmp',
            '--mount', 'type=bind,src=/local/.android,dst=/root/.android',
            '--mount', ('type=bind,src=/var/run/docker.sock,'
                        'dst=/var/run/docker.sock'),
            '--mount', ('type=bind,src=/local/.ats_storage,'
                        'dst=/tmp/.mnt/.ats_storage'),
            '-p', '127.0.0.1:5037:5037',
            '--cap-add', 'sys_admin',
            '--cap-add', 'net_admin',
            '--device', '/dev/fuse',
            '--device', '/dev/kvm',
            '--device', '/dev/vhost-vsock',
            '--device', '/dev/net/tun',
            '--device', '/dev/vhost-net',
            '--security-opt', 'apparmor:unconfined',
            '--security-opt', 'seccomp=/tmp/mtt_seccomp.json',
            'gcr.io/android-mtt/mtt:prod']),
        mock.call(['docker', 'start', 'mtt']),
        mock.call(
            ['docker', 'exec', 'mtt', 'printenv', 'MTT_VERSION'],
            raise_on_failure=False),
    ])

  def testStart_withExtraDockerArgs(self):
    """Test start with extra docker args."""
    args = self.arg_parser.parse_args([
        'start',
        '--extra_docker_args', '"--arg1" value1',
        '--extra_docker_args', '"--arg2"',
        '--extra_docker_args', 'value2',
    ])
    cli.Start(
        args,
        self._CreateHost(
            hostname='ahost', cluster_name='acluster',
            extra_docker_args=['--arg3', 'value3']))

    self.mock_context.Run.assert_has_calls([
        mock.call([
            'docker', 'create',
            '--name', 'mtt', '-it',
            *_DEFAULT_CREATE_ARGS,
            '--hostname', 'ahost',
            '--network', 'bridge',
            '-e', 'OPERATION_MODE=unknown',
            '-e', 'MTT_CLI_VERSION=dev_version',
            '-e', 'MTT_CONTROL_SERVER_URL=url',
            '-e', 'CLUSTER=acluster',
            '-e', 'IMAGE_NAME=gcr.io/android-mtt/mtt:prod',
            '-e', 'USER=user',
            '-e', 'TZ=Etc/UTC',
            '-e', 'MTT_SERVER_LOG_LEVEL=info',
            '--mount', 'type=volume,src=mtt-data,dst=/data',
            '--mount', 'type=volume,src=mtt-temp,dst=/tmp',
            '--mount', 'type=bind,src=/local/.android,dst=/root/.android',
            '--mount', ('type=bind,src=/var/run/docker.sock,'
                        'dst=/var/run/docker.sock'),
            '--mount', ('type=bind,src=/local/.ats_storage,'
                        'dst=/tmp/.mnt/.ats_storage'),
            '-p', '127.0.0.1:5037:5037',
            '--cap-add', 'sys_admin',
            '--device', '/dev/fuse',
            '--security-opt', 'apparmor:unconfined',
            '--security-opt', 'seccomp=/tmp/mtt_seccomp.json',
            '--arg3', 'value3', '--arg1', 'value1', '--arg2', 'value2',
            'gcr.io/android-mtt/mtt:prod']),
        mock.call(['docker', 'start', 'mtt']),
        mock.call(
            ['docker', 'exec', 'mtt', 'printenv', 'MTT_VERSION'],
            raise_on_failure=False),
    ])

  def testStart_withUseHostNetwork(self):
    """Test start with --use_host_network."""
    args = self.arg_parser.parse_args(['start', '--use_host_network'])
    cli.Start(args, self._CreateHost())

    self.mock_context.Run.assert_has_calls([
        mock.call([
            'docker', 'create',
            '--name', 'mtt', '-it',
            *_DEFAULT_CREATE_ARGS,
            '--network', 'host',
            '-e', 'OPERATION_MODE=unknown',
            '-e', 'MTT_CLI_VERSION=dev_version',
            '-e', 'MTT_CONTROL_SERVER_URL=url',
            '-e', 'IMAGE_NAME=gcr.io/android-mtt/mtt:prod',
            '-e', 'USER=user',
            '-e', 'TZ=Etc/UTC',
            '-e', 'MTT_SERVER_LOG_LEVEL=info',
            '--mount', 'type=volume,src=mtt-data,dst=/data',
            '--mount', 'type=volume,src=mtt-temp,dst=/tmp',
            '--mount', 'type=bind,src=/local/.android,dst=/root/.android',
            '--mount', ('type=bind,src=/var/run/docker.sock,'
                        'dst=/var/run/docker.sock'),
            '--mount', ('type=bind,src=/local/.ats_storage,'
                        'dst=/tmp/.mnt/.ats_storage'),
            '--cap-add', 'sys_admin',
            '--device', '/dev/fuse',
            '--security-opt', 'apparmor:unconfined',
            '--security-opt', 'seccomp=/tmp/mtt_seccomp.json',
            'gcr.io/android-mtt/mtt:prod']),
        mock.call(['docker', 'start', 'mtt']),
    ])

  def testStart_withLocalMounts(self):
    """Test start with additional paths mounted in local file store."""
    args = self.arg_parser.parse_args([
        'start',
        '--mount_local_path', '/path/to/dir',
        '--mount_local_path', '/path/to/dir:remote',
        '--mount_local_path', '/path/to/dir:/absolute',
    ])
    cli.Start(args, self._CreateHost())

    self.mock_context.Run.assert_has_calls([
        mock.call([
            'docker', 'create',
            '--name', 'mtt', '-it',
            *_DEFAULT_CREATE_ARGS,
            '--hostname', 'mock-host',
            '--network', 'bridge',
            '-e', 'OPERATION_MODE=unknown',
            '-e', 'MTT_CLI_VERSION=dev_version',
            '-e', 'MTT_CONTROL_SERVER_URL=url',
            '-e', 'IMAGE_NAME=gcr.io/android-mtt/mtt:prod',
            '-e', 'USER=user',
            '-e', 'TZ=Etc/UTC',
            '-e', 'MTT_SERVER_LOG_LEVEL=info',
            '--mount', 'type=volume,src=mtt-data,dst=/data',
            '--mount', 'type=volume,src=mtt-temp,dst=/tmp',
            '--mount', 'type=bind,src=/local/.android,dst=/root/.android',
            '--mount', ('type=bind,src=/var/run/docker.sock,'
                        'dst=/var/run/docker.sock'),
            '--mount', ('type=bind,src=/local/.ats_storage,'
                        'dst=/tmp/.mnt/.ats_storage'),
            '--mount', 'type=bind,src=/path/to/dir,dst=/tmp/.mnt/dir',
            '--mount', 'type=bind,src=/path/to/dir,dst=/tmp/.mnt/remote',
            '--mount', 'type=bind,src=/path/to/dir,dst=/tmp/.mnt/absolute',
            '-p', '127.0.0.1:5037:5037',
            '--cap-add', 'sys_admin',
            '--device', '/dev/fuse',
            '--security-opt', 'apparmor:unconfined',
            '--security-opt', 'seccomp=/tmp/mtt_seccomp.json',
            'gcr.io/android-mtt/mtt:prod']),
        mock.call(['docker', 'start', 'mtt']),
        mock.call(
            ['docker', 'exec', 'mtt', 'printenv', 'MTT_VERSION'],
            raise_on_failure=False),
    ])

  def testStart_failAdbPortInUse(self):
    """Test start with the adb server port in use."""
    self.mock_socket.bind.side_effect = OSError('unit test')
    args = self.arg_parser.parse_args(['start'])
    with self.assertRaises(cli.ActionableError):
      cli.Start(args, self._CreateHost())

  def testStart_withVirtualDevicesArgs_failDeviceNodesNotExisting(self):
    """Test start without the device nodes required by local virtual devices."""
    self.mock_exist_files = []
    args = self.arg_parser.parse_args(
        ['start', '--max_local_virtual_devices', '1'])
    with self.assertRaises(cli.ActionableError):
      cli.Start(args, self._CreateHost())

  def testStart_withVirtualDevicesConfig_failDeviceNodesNotExisting(self):
    """Test start without the device nodes required by local virtual devices."""
    self.mock_exist_files = []
    args = self.arg_parser.parse_args(['start'])
    with self.assertRaises(cli.ActionableError):
      cli.Start(args, self._CreateHost(max_local_virtual_devices=1))

  @mock.patch.object(shutil, 'which')
  def testStart_withUseHostADB(self, mock_which):
    """Test start with additional paths mounted in local file store."""
    with tempfile.NamedTemporaryFile() as mock_adb:
      args = self.arg_parser.parse_args(['start', '--use_host_adb'])
      mock_which.return_value = mock_adb.name

      cli.Start(args, self._CreateHost())

      self.mock_context.Run.assert_has_calls([
          mock.call([
              'docker', 'create',
              '--name', 'mtt', '-it',
              *_DEFAULT_CREATE_ARGS,
              '--hostname', 'mock-host',
              '--network', 'bridge',
              '-e', 'OPERATION_MODE=unknown',
              '-e', 'MTT_CLI_VERSION=dev_version',
              '-e', 'MTT_CONTROL_SERVER_URL=url',
              '-e', 'IMAGE_NAME=gcr.io/android-mtt/mtt:prod',
              '-e', 'USER=user',
              '-e', 'TZ=Etc/UTC',
              '-e', 'MTT_SERVER_LOG_LEVEL=info',
              '-e', 'MTT_USE_HOST_ADB=1',
              '--mount', 'type=volume,src=mtt-data,dst=/data',
              '--mount', 'type=volume,src=mtt-temp,dst=/tmp',
              '--mount', 'type=bind,src=/local/.android,dst=/root/.android',
              '--mount', ('type=bind,src=/var/run/docker.sock,'
                          'dst=/var/run/docker.sock'),
              '--mount', ('type=bind,src=/local/.ats_storage,'
                          'dst=/tmp/.mnt/.ats_storage'),
              '--cap-add', 'sys_admin',
              '--device', '/dev/fuse',
              '--security-opt', 'apparmor:unconfined',
              '--security-opt', 'seccomp=/tmp/mtt_seccomp.json',
              'gcr.io/android-mtt/mtt:prod']),
          mock.call(['docker', 'start', 'mtt']),
          mock.call(
              ['docker', 'exec', 'mtt', 'printenv', 'MTT_VERSION'],
              raise_on_failure=False),
      ])

  def testStart_WithLocalVirtualDeviceIPv6(self):
    """Test start with virtual device and IPv6 enabled."""
    self.enable_ipv6 = True
    args = self.arg_parser.parse_args(
        ['start', '--max_local_virtual_devices', '1'])
    cli.Start(args, self._CreateHost())

    self.mock_context.Run.assert_has_calls([
        mock.call(['docker', 'network', 'inspect', 'bridge',
                   '--format={{json .}}'],
                  raise_on_failure=False),
        mock.call(['docker', 'container', 'rm', 'mtt'],
                  raise_on_failure=False),
        mock.call([
            'docker', 'create',
            '--name', 'mtt', '-it',
            *_DEFAULT_CREATE_ARGS,
            '--hostname', 'mock-host',
            '--network', 'bridge',
            '-e', 'OPERATION_MODE=unknown',
            '-e', 'MTT_CLI_VERSION=dev_version',
            '-e', 'MTT_CONTROL_SERVER_URL=url',
            '-e', 'IMAGE_NAME=gcr.io/android-mtt/mtt:prod',
            '-e', 'USER=user',
            '-e', 'TZ=Etc/UTC',
            '-e', 'MTT_SERVER_LOG_LEVEL=info',
            '-e', 'IPV6_BRIDGE_NETWORK=2001:db8::/56',
            '-e', 'MAX_LOCAL_VIRTUAL_DEVICES=1',
            '--mount', 'type=volume,src=mtt-data,dst=/data',
            '--mount', 'type=volume,src=mtt-temp,dst=/tmp',
            '--mount', 'type=bind,src=/local/.android,dst=/root/.android',
            '--mount', ('type=bind,src=/var/run/docker.sock,'
                        'dst=/var/run/docker.sock'),
            '--mount', ('type=bind,src=/local/.ats_storage,'
                        'dst=/tmp/.mnt/.ats_storage'),
            '-p', '127.0.0.1:5037:5037',
            '--cap-add', 'sys_admin',
            '--cap-add', 'net_admin',
            '--device', '/dev/fuse',
            '--device', '/dev/kvm',
            '--device', '/dev/vhost-vsock',
            '--device', '/dev/net/tun',
            '--device', '/dev/vhost-net',
            '--sysctl', 'net.ipv6.conf.all.disable_ipv6=0',
            '--sysctl', 'net.ipv6.conf.all.forwarding=1',
            '--security-opt', 'apparmor:unconfined',
            '--security-opt', 'seccomp=/tmp/mtt_seccomp.json',
            'gcr.io/android-mtt/mtt:prod']),
        mock.call(['docker', 'start', 'mtt']),
        mock.call(
            ['docker', 'exec', 'mtt', 'printenv', 'MTT_VERSION'],
            raise_on_failure=False),
    ])

  def testStart_withControlServerUrl(self):
    """Test start with control_server_url."""
    args = self.arg_parser.parse_args(
        ['start', '--control_server_url', 'new_url'])
    cli.Start(args, self._CreateHost(cluster_name='acluster', lab_name='alab'))

    self.mock_context.Run.assert_has_calls([
        mock.call([
            'docker', 'create', '--name', 'mtt', '-it',
            *_DEFAULT_CREATE_ARGS,
            '--hostname', 'mock-host', '--network',
            'bridge', '-e', 'OPERATION_MODE=unknown', '-e',
            'MTT_CLI_VERSION=dev_version', '-e',
            'MTT_CONTROL_SERVER_URL=new_url', '-e', 'LAB_NAME=alab', '-e',
            'CLUSTER=acluster', '-e', 'IMAGE_NAME=gcr.io/android-mtt/mtt:prod',
            '-e', 'USER=user', '-e', 'TZ=Etc/UTC', '-e',
            'MTT_SERVER_LOG_LEVEL=info', '--mount',
            'type=volume,src=mtt-data,dst=/data', '--mount',
            'type=volume,src=mtt-temp,dst=/tmp', '--mount',
            'type=bind,src=/local/.android,dst=/root/.android', '--mount',
            ('type=bind,src=/var/run/docker.sock,'
             'dst=/var/run/docker.sock'), '--mount',
            ('type=bind,src=/local/.ats_storage,'
             'dst=/tmp/.mnt/.ats_storage'), '-p', '127.0.0.1:5037:5037',
            '--cap-add', 'sys_admin',
            '--device', '/dev/fuse',
            '--security-opt', 'apparmor:unconfined',
            '--security-opt', 'seccomp=/tmp/mtt_seccomp.json',
            'gcr.io/android-mtt/mtt:prod'
        ]),
        mock.call(['docker', 'start', 'mtt']),
        mock.call(['docker', 'exec', 'mtt', 'printenv', 'MTT_VERSION'],
                  raise_on_failure=False),
    ])

  def testStart_withControlFileServerUrlUnset(self):
    """Test start with control_file_server_url unset."""
    args = self.arg_parser.parse_args(
        ['start', '--control_server_url', 'http://localhost:9000'])
    cli.Start(args, self._CreateHost(cluster_name='acluster', lab_name='alab'))

    self.mock_context.Run.assert_has_calls([
        mock.call([
            'docker', 'create', '--name', 'mtt', '-it',
            *_DEFAULT_CREATE_ARGS,
            '--hostname', 'mock-host', '--network',
            'bridge', '-e', 'OPERATION_MODE=unknown', '-e',
            'MTT_CLI_VERSION=dev_version', '-e',
            'MTT_CONTROL_SERVER_URL=http://localhost:9000', '-e',
            'MTT_CONTROL_FILE_SERVER_URL=http://localhost:9006', '-e',
            'LAB_NAME=alab', '-e',
            'CLUSTER=acluster', '-e', 'IMAGE_NAME=gcr.io/android-mtt/mtt:prod',
            '-e', 'USER=user', '-e', 'TZ=Etc/UTC', '-e',
            'MTT_SERVER_LOG_LEVEL=info', '--mount',
            'type=volume,src=mtt-data,dst=/data', '--mount',
            'type=volume,src=mtt-temp,dst=/tmp', '--mount',
            'type=bind,src=/local/.android,dst=/root/.android', '--mount',
            ('type=bind,src=/var/run/docker.sock,'
             'dst=/var/run/docker.sock'), '--mount',
            ('type=bind,src=/local/.ats_storage,'
             'dst=/tmp/.mnt/.ats_storage'), '-p', '127.0.0.1:5037:5037',
            '--cap-add', 'sys_admin',
            '--device', '/dev/fuse',
            '--security-opt', 'apparmor:unconfined',
            '--security-opt', 'seccomp=/tmp/mtt_seccomp.json',
            'gcr.io/android-mtt/mtt:prod'
        ]),
        mock.call(['docker', 'start', 'mtt']),
        mock.call(['docker', 'exec', 'mtt', 'printenv', 'MTT_VERSION'],
                  raise_on_failure=False),
    ])

  def testStart_withControlFileServerUrl(self):
    """Test start with control_file_server_url."""
    args = self.arg_parser.parse_args(
        ['start', '--control_server_url', 'http://localhost:9000',
         '--control_file_server_url', 'http://localhost:9500'])
    cli.Start(args, self._CreateHost(cluster_name='acluster', lab_name='alab'))

    self.mock_context.Run.assert_has_calls([
        mock.call([
            'docker', 'create', '--name', 'mtt', '-it',
            *_DEFAULT_CREATE_ARGS,
            '--hostname', 'mock-host', '--network',
            'bridge', '-e', 'OPERATION_MODE=unknown', '-e',
            'MTT_CLI_VERSION=dev_version', '-e',
            'MTT_CONTROL_SERVER_URL=http://localhost:9000', '-e',
            'MTT_CONTROL_FILE_SERVER_URL=http://localhost:9500', '-e',
            'LAB_NAME=alab', '-e',
            'CLUSTER=acluster', '-e', 'IMAGE_NAME=gcr.io/android-mtt/mtt:prod',
            '-e', 'USER=user', '-e', 'TZ=Etc/UTC', '-e',
            'MTT_SERVER_LOG_LEVEL=info', '--mount',
            'type=volume,src=mtt-data,dst=/data', '--mount',
            'type=volume,src=mtt-temp,dst=/tmp', '--mount',
            'type=bind,src=/local/.android,dst=/root/.android', '--mount',
            ('type=bind,src=/var/run/docker.sock,'
             'dst=/var/run/docker.sock'), '--mount',
            ('type=bind,src=/local/.ats_storage,'
             'dst=/tmp/.mnt/.ats_storage'), '-p', '127.0.0.1:5037:5037',
            '--cap-add', 'sys_admin',
            '--device', '/dev/fuse',
            '--security-opt', 'apparmor:unconfined',
            '--security-opt', 'seccomp=/tmp/mtt_seccomp.json',
            'gcr.io/android-mtt/mtt:prod'
        ]),
        mock.call(['docker', 'start', 'mtt']),
        mock.call(['docker', 'exec', 'mtt', 'printenv', 'MTT_VERSION'],
                  raise_on_failure=False),
    ])

  @mock.patch('__main__.cli.ssh_util')
  def testStart_withRemoteVirtualDevices(self, mock_ssh_util):
    """Test start with remote_virtual_devices."""
    args = self.arg_parser.parse_args(
        ['start', '--remote_virtual_devices', 'user1@192.0.2.3/2',
         '--remote_ssh_key', '/mock/id_rsa'])
    mock_ssh_context = mock.Mock()
    mock_ssh_util.Context.return_value = mock_ssh_context
    cli.Start(args, self._CreateHost())

    self.mock_context.Run.assert_has_calls([
        mock.call([
            'docker', 'create',
            '--name', 'mtt', '-it',
            *_DEFAULT_CREATE_ARGS,
            '--hostname', 'mock-host',
            '--network', 'bridge',
            '-e', 'OPERATION_MODE=unknown',
            '-e', 'MTT_CLI_VERSION=dev_version',
            '-e', 'MTT_CONTROL_SERVER_URL=url',
            '-e', 'IMAGE_NAME=gcr.io/android-mtt/mtt:prod',
            '-e', 'USER=user',
            '-e', 'TZ=Etc/UTC',
            '-e', 'MTT_SERVER_LOG_LEVEL=info',
            '-e', 'REMOTE_VIRTUAL_DEVICES=user1@192.0.2.3/2',
            '--mount', 'type=volume,src=mtt-data,dst=/data',
            '--mount', 'type=volume,src=mtt-temp,dst=/tmp',
            '--mount', 'type=bind,src=/local/.android,dst=/root/.android',
            '--mount', ('type=bind,src=/var/run/docker.sock,'
                        'dst=/var/run/docker.sock'),
            '--mount', ('type=bind,src=/local/.ats_storage,'
                        'dst=/tmp/.mnt/.ats_storage'),
            '-p', '127.0.0.1:5037:5037',
            '--cap-add', 'sys_admin',
            '--device', '/dev/fuse',
            '--security-opt', 'apparmor:unconfined',
            '--security-opt', 'seccomp=/tmp/mtt_seccomp.json',
            'gcr.io/android-mtt/mtt:prod']),
        mock.call(
            ['docker', 'cp', '-L', '/mock/id_rsa', 'mtt:/tmp/rvd_id_rsa']),
        mock.call(['docker', 'start', 'mtt']),
        mock.call(
            ['docker', 'exec', 'mtt', 'printenv', 'MTT_VERSION'],
            raise_on_failure=False),
    ])
    mock_ssh_util.SshConfig.assert_called_once_with(
        user='user1',
        hostname='192.0.2.3',
        ssh_args=(
            '-o PasswordAuthentication=no '
            '-o StrictHostKeyChecking=no '
            '-o UserKnownHostsFile=/dev/null'
        ),
        ssh_key='/mock/id_rsa',
        use_native_ssh=True,
    )
    mock_ssh_context.run.assert_called_once()

  @mock.patch.object(cli, '_IsDaemonActive')
  @mock.patch.object(cli, '_SetupSystemdScript')
  @mock.patch.object(cli, '_SetupMTTRuntimeIntoLibPath')
  def testStartMttDaemon_AlreadyActive(
      self, setup_permanent_bin, setup_mttd, is_active):
    args = mock.create_autospec(cli.argparse.Namespace)
    host = self._CreateHost(
        cluster_name='acluster', hostname='ahost', enable_autoupdate=True)
    is_active.return_value = True

    cli._StartMttDaemon(args, host)
    setup_mttd.assert_not_called()
    setup_permanent_bin.assert_not_called()

  @mock.patch.object(cli, '_HasSudoAccess')
  @mock.patch.object(cli, '_IsDaemonActive')
  @mock.patch.object(cli, '_SetupSystemdScript')
  @mock.patch.object(cli, '_SetupMTTRuntimeIntoLibPath')
  def testStartMttDaemon_NotYetActive(
      self, setup_permanent_bin, setup_mttd, is_active, has_sudo):
    args = mock.create_autospec(cli.argparse.Namespace)
    host = self._CreateHost(
        cluster_name='acluster', hostname='ahost', enable_autoupdate=True)
    is_active.return_value = False
    has_sudo.return_value = True

    cli._StartMttDaemon(args, host)
    setup_mttd.assert_called_with(args, host)
    setup_permanent_bin.assert_called_with(args, host)
    self.mock_context.Run.assert_has_calls([
        mock.call(['systemctl', 'enable', 'mttd.service']),
        mock.call(['systemctl', 'start', 'mttd.service']),
    ])

  @mock.patch.object(cli, '_HasSudoAccess')
  @mock.patch.object(cli, '_IsDaemonActive')
  def testStartMttDaemon_NoSudo(self, is_active, has_sudo):
    args = mock.create_autospec(cli.argparse.Namespace)
    host = self._CreateHost(
        cluster_name='acluster', hostname='ahost', enable_autoupdate=True)
    is_active.return_value = False
    has_sudo.return_value = False

    with self.assertRaises(cli.ActionableError):
      cli._StartMttDaemon(args, host)

  @mock.patch.object(cli, '_IsDaemonActive')
  @mock.patch('__main__.cli.command_util.DockerHelper.IsContainerRunning')
  @mock.patch('__main__.cli.os.geteuid')
  def testStop(self, euid, is_running, daemon_active):
    euid.return_value = 123
    is_running.return_value = True
    daemon_active.return_value = False
    self.mock_context.host = 'ahost'
    args = self.arg_parser.parse_args(['stop'])
    host = self._CreateHost()
    cli.Stop(args, host)

    self.mock_context.Run.assert_has_calls([
        mock.call(['docker', 'kill', '-s', 'TERM', 'mtt'],
                  timeout=command_util._DOCKER_KILL_CMD_TIMEOUT_SEC),
        mock.call(['docker', 'container', 'wait', 'mtt'],
                  timeout=cli._SHORT_CONTAINER_SHUTDOWN_TIMEOUT_SEC),
        mock.call(['docker', 'inspect', 'mtt'], raise_on_failure=False),
        mock.call(['docker', 'container', 'rm', 'mtt'],
                  raise_on_failure=False),
    ])
    is_running.assert_called_once_with('mtt')

  @mock.patch.object(cli, '_IsDaemonActive')
  @mock.patch('__main__.cli.command_util.DockerHelper.IsContainerRunning')
  def testStop_notRunning(self, is_running, daemon_active):
    is_running.return_value = False
    daemon_active.return_value = False
    self.mock_context.host = 'ahost'
    args = self.arg_parser.parse_args(['stop'])
    cli.Stop(args, self._CreateHost())

    self.mock_context.Run.assert_has_calls([
        mock.call(['docker', 'inspect', 'mtt'], raise_on_failure=False),
        mock.call(['docker', 'container', 'rm', 'mtt'],
                  raise_on_failure=False),
    ])
    is_running.assert_called_once_with('mtt')

  @mock.patch.object(cli, '_IsDaemonActive')
  @mock.patch('__main__.cli.command_util.DockerHelper.IsContainerRunning')
  @mock.patch('__main__.cli.os.geteuid')
  def testStop_gracefulShutdownWithWaitFlag(
      self, euid, is_running, daemon_active):
    """Test Stop with wait flag set."""
    euid.return_value = 123
    is_running.return_value = True
    daemon_active.return_value = False
    self.mock_context.host = 'ahost'
    args = self.arg_parser.parse_args(['stop', '--wait'])
    cli.Stop(args, self._CreateHost())

    self.mock_context.Run.assert_has_calls([
        mock.call(['docker', 'kill', '-s', 'TSTP', 'mtt'],
                  timeout=command_util._DOCKER_KILL_CMD_TIMEOUT_SEC),
        mock.call(['docker', 'container', 'wait', 'mtt'],
                  timeout=cli._LONG_CONTAINER_SHUTDOWN_TIMEOUT_SEC),
        mock.call(['docker', 'inspect', 'mtt'], raise_on_failure=False),
        mock.call(['docker', 'container', 'rm', 'mtt'],
                  raise_on_failure=False),
    ])
    is_running.assert_called_once_with('mtt')

  @mock.patch.object(cli, '_IsDaemonActive')
  @mock.patch('__main__.cli.command_util.DockerHelper.IsContainerRunning')
  @mock.patch('__main__.cli.os.geteuid')
  def testStop_gracefulShutdownWithConfig(
      self, euid, is_running, daemon_active):
    euid.return_value = 123
    is_running.return_value = True
    daemon_active.return_value = False
    daemon_active.return_value = False
    self.mock_context.host = 'ahost'
    args = self.arg_parser.parse_args(['stop'])
    cli.Stop(args, self._CreateHost(graceful_shutdown=True))

    self.mock_context.Run.assert_has_calls([
        mock.call(['docker', 'kill', '-s', 'TSTP', 'mtt'],
                  timeout=command_util._DOCKER_KILL_CMD_TIMEOUT_SEC),
        mock.call(['docker', 'container', 'wait', 'mtt'],
                  timeout=cli._LONG_CONTAINER_SHUTDOWN_TIMEOUT_SEC),
        mock.call(['docker', 'inspect', 'mtt'], raise_on_failure=False),
        mock.call(['docker', 'container', 'rm', 'mtt'],
                  raise_on_failure=False),
    ])
    is_running.assert_called_once_with('mtt')

  @mock.patch.object(cli, '_IsDaemonActive')
  @mock.patch('__main__.cli.command_util.DockerHelper.IsContainerRunning')
  @mock.patch('__main__.cli.os.geteuid')
  def testStop_withShutdownTimeoutConfig(self, euid, is_running, daemon_active):
    """Test Stop with kill mtt with control_server_url in host config."""
    euid.return_value = 123
    is_running.return_value = True
    daemon_active.return_value = False
    self.mock_context.host = 'ahost'
    args = self.arg_parser.parse_args(['stop'])
    host = self._CreateHost(shutdown_timeout_sec=60)
    cli.Stop(args, host)

    self.mock_context.Run.assert_has_calls([
        mock.call(['docker', 'kill', '-s', 'TERM', 'mtt'],
                  timeout=command_util._DOCKER_KILL_CMD_TIMEOUT_SEC),
        mock.call(['docker', 'container', 'wait', 'mtt'],
                  timeout=60),
        mock.call(['docker', 'inspect', 'mtt'], raise_on_failure=False),
        mock.call(['docker', 'container', 'rm', 'mtt'],
                  raise_on_failure=False),
    ])
    is_running.assert_called_once_with('mtt')

  @mock.patch.object(cli, '_HasSudoAccess')
  @mock.patch.object(cli, '_StopMttNode')
  @mock.patch.object(cli, '_IsDaemonActive')
  def testStop_DaemonIsClosedIfActive(self, is_active, stop_mtt, has_sudo):
    is_active.return_value = True
    has_sudo.return_value = True
    args = self.arg_parser.parse_args(['stop'])
    host = self._CreateHost(hostname='ahost')

    cli.Stop(args, host)

    stop_mtt.assert_called_with(args, host)
    self.mock_context.Run.assert_has_calls([
        mock.call(['systemctl', 'stop', 'mttd.service']),
        mock.call(['systemctl', 'disable', 'mttd.service']),
    ])

  @mock.patch.object(cli, '_HasSudoAccess')
  @mock.patch.object(cli, '_IsDaemonActive')
  def testStop_DaemonFailedIfActiveAndNoSudo(
      self, is_active, has_sudo):
    is_active.return_value = True
    has_sudo.return_value = False
    args = self.arg_parser.parse_args(['stop'])
    host = self._CreateHost(hostname='ahost')

    with self.assertRaises(cli.ActionableError):
      cli.Stop(args, host)

  @mock.patch('__main__.cli.os.geteuid')
  @mock.patch('__main__.cli.command_util.DockerHelper.IsContainerRunning')
  @mock.patch.object(cli, '_DetectAndKillDeadContainer')
  def testStop_ForceKillInSudoMode(self, detect_and_kill, is_running, euid):
    euid.return_value = 0
    is_running.return_value = True
    self.mock_context.host = 'ahost'
    args = self.arg_parser.parse_args(['stop'])

    cli.Stop(args, self._CreateHost())

    self.mock_context.Run.assert_has_calls([
        mock.call(['docker', 'kill', '-s', 'TERM', 'mtt'],
                  timeout=command_util._DOCKER_KILL_CMD_TIMEOUT_SEC),
        mock.call(['docker', 'inspect', 'mtt'], raise_on_failure=False),
        mock.call(['docker', 'container', 'rm', 'mtt'],
                  raise_on_failure=False),
    ])
    detect_and_kill.assert_called_once()

  @mock.patch.object(cli, '_StartMttNode')
  @mock.patch.object(cli, '_StopMttNode')
  @mock.patch.object(cli, '_StartMttDaemon')
  @mock.patch.object(cli, '_StopMttDaemon')
  def testRestart(self, stop_mttd, start_mttd, stop_mtt, start_mtt):
    """Test Restart."""
    args = self.arg_parser.parse_args(['restart'])
    host = self._CreateHost()
    cli.Restart(args, host)
    stop_mttd.assert_called_with(host)
    stop_mtt.assert_called_once_with(args, host)
    start_mttd.assert_not_called()
    start_mtt.assert_called_once_with(args, host)

  @mock.patch.object(cli, '_StartMttNode')
  @mock.patch.object(cli, '_StopMttNode')
  @mock.patch.object(cli, '_StartMttDaemon')
  @mock.patch.object(cli, '_StopMttDaemon')
  def testRestart_EnableAutoupdate(
      self, stop_mttd, start_mttd, stop_mtt, start_mtt):
    """Test Restart."""
    args = self.arg_parser.parse_args(['restart'])
    host = self._CreateHost(enable_autoupdate=True)
    cli.Restart(args, host)
    stop_mttd.assert_called_with(host)
    stop_mtt.assert_called_once_with(args, host)
    start_mtt.assert_not_called()
    start_mttd.assert_called_once_with(args, host)

  @mock.patch.object(cli, '_StartMttNode')
  @mock.patch.object(cli, '_StopMttNode')
  @mock.patch.object(cli, '_StartMttDaemon')
  @mock.patch.object(cli, '_StopMttDaemon')
  def testRestart_EnableUiUpdate(
      self, stop_mttd, start_mttd, stop_mtt, start_mtt):
    args = self.arg_parser.parse_args(['restart'])
    host = self._CreateHost(enable_ui_update=True)
    cli.Restart(args, host)
    stop_mttd.assert_called_with(host)
    stop_mtt.assert_called_once_with(args, host)
    start_mtt.assert_not_called()
    start_mttd.assert_called_once_with(args, host)
    (self.mock_control_server_client.PatchTestHarnessImageToHostMetadata
     .assert_called_with(host.config.hostname, host.config.docker_image))

  @mock.patch.object(cli, '_StopMttDaemon')
  @mock.patch.object(cli, '_StartMttNode')
  @mock.patch.object(cli, '_StopMttNode')
  @mock.patch.object(cli, '_PullUpdate')
  def testUpdate(self, pull_update, stop_mtt, start_mtt, stop_mttd):
    """Test Update."""
    pull_update.return_value = True
    args = self.arg_parser.parse_args(['update'])
    host = self._CreateHost()

    cli.Update(args, host)

    stop_mttd.assert_called()
    stop_mtt.assert_called_once_with(args, host)
    start_mtt.assert_called_once_with(args, host)

  @mock.patch.object(cli, '_StopMttDaemon')
  @mock.patch.object(cli, '_StartMttNode')
  @mock.patch.object(cli, '_StopMttNode')
  @mock.patch.object(cli, '_PullUpdate')
  def testUpdate_notUpdate(self, pull_update, stop_mtt, start_mtt, stop_mttd):
    """Test Update but skip."""
    pull_update.return_value = False
    args = self.arg_parser.parse_args(['update'])
    host = self._CreateHost()

    cli.Update(args, host)

    stop_mttd.assert_called()
    self.assertFalse(stop_mtt.called)
    self.assertFalse(start_mtt.called)

  @mock.patch.object(cli, '_UpdateMttNode')
  @mock.patch.object(cli, '_StartMttDaemon')
  @mock.patch.object(cli, '_StopMttDaemon')
  def testUpdate_EnableAutoupdate(self, stop_mttd, start_mttd, update_mtt):
    args = self.arg_parser.parse_args(['update'])
    host = self._CreateHost(enable_autoupdate=True)
    cli.Update(args, host)
    stop_mttd.assert_called_once()
    start_mttd.assert_called_once()
    update_mtt.assert_not_called()

  @mock.patch.object(cli, '_UpdateMttNode')
  @mock.patch.object(cli, '_StopMttDaemon')
  def testUpdate_DisableAutoupdate(self, stop_mttd, update_mtt):
    args = self.arg_parser.parse_args(['update'])
    host = self._CreateHost(enable_autoupdate=False)
    cli.Update(args, host)
    stop_mttd.assert_called_once()
    update_mtt.assert_called_once()

  @mock.patch.object(cli, '_UpdateMttNode')
  @mock.patch.object(cli, '_StartMttDaemon')
  @mock.patch.object(cli, '_StopMttDaemon')
  def testUpdate_EnableUiUpdate(
      self, stop_mttd, start_mttd, update_mtt):
    args = self.arg_parser.parse_args(['update'])
    host = self._CreateHost(enable_ui_update=True)
    cli.Update(args, host)
    stop_mttd.assert_called_once()
    start_mttd.assert_called_once()
    update_mtt.assert_not_called()
    (self.mock_control_server_client.PatchTestHarnessImageToHostMetadata
     .assert_called_with(host.config.hostname, host.config.docker_image))

  def testPullUpdate_forceUpdate(self):
    """Test PullUpdate with force_update."""
    args = self.arg_parser.parse_args(['update', '--force_update'])
    host = self._CreateHost()
    self.assertTrue(cli._PullUpdate(args, host))

  @mock.patch('__main__.cli.command_util.DockerHelper.IsContainerRunning')
  def testPullUpdate_notRunning(self, is_running):
    """Test PullUpdate when container is not running."""
    is_running.return_value = False
    args = self.arg_parser.parse_args(['update'])
    host = self._CreateHost()
    self.assertTrue(cli._PullUpdate(args, host))
    is_running.assert_called_once_with('mtt')

  @mock.patch('__main__.cli.command_util.DockerHelper.IsContainerRunning')
  @mock.patch('__main__.cli.command_util.DockerHelper.GetImageIdForContainer')
  @mock.patch('__main__.cli.command_util.DockerHelper.GetRemoteImageDigest')
  def testPullUpdate_allowedByClusterConcurrencyLimit(
      self, get_remote_image_digest, get_image_id, is_running):
    """Test PullUpdate when container is running, and concurrency allows."""
    is_running.return_value = True
    get_image_id.return_value = 'image_id'
    get_remote_image_digest.side_effect = ['container_image', 'remote_image']
    args = self.arg_parser.parse_args(['update'])
    host = self._CreateHost(
        enable_autoupdate=True, max_concurrent_update_percentage=10)
    host.metadata = {
        cli._TEST_HARNESS_IMAGE_KEY: 'repo/image_1:tag_1',
        cli._ALLOW_TO_UPDATE_KEY: True,
    }
    self.assertTrue(cli._PullUpdate(args, host))
    is_running.assert_called_once_with('mtt')

  @mock.patch('__main__.cli.command_util.DockerHelper.IsContainerRunning')
  @mock.patch('__main__.cli.command_util.DockerHelper.GetImageIdForContainer')
  @mock.patch('__main__.cli.command_util.DockerHelper.GetRemoteImageDigest')
  def testPullUpdate_blockedByClusterConcurrencyLimitContainerRunning(
      self, get_remote_image_digest, get_image_id, is_running):
    """Test PullUpdate when container is running, but concurrency blocks."""
    is_running.return_value = True
    get_image_id.return_value = 'image_id'
    get_remote_image_digest.side_effect = ['container_image', 'remote_image']
    args = self.arg_parser.parse_args(['update'])
    host = self._CreateHost(
        enable_ui_update=True, max_concurrent_update_percentage=10)
    host.metadata = {
        cli._TEST_HARNESS_IMAGE_KEY: 'repo/image_1:tag_1',
        cli._ALLOW_TO_UPDATE_KEY: False,
    }
    self.assertFalse(cli._PullUpdate(args, host))
    is_running.assert_called_once_with('mtt')

  @mock.patch('__main__.cli.command_util.DockerHelper.IsContainerRunning')
  @mock.patch('__main__.cli.command_util.DockerHelper.GetImageIdForContainer')
  @mock.patch('__main__.cli.command_util.DockerHelper.GetRemoteImageDigest')
  def testPullUpdate_differetImage(
      self, get_remote_image_digest, get_image_id, is_running):
    """Test PullUpdate with different remote image."""
    is_running.return_value = True
    get_image_id.return_value = 'image_id'
    get_remote_image_digest.side_effect = ['container_image', 'remote_image']
    args = self.arg_parser.parse_args(['update'])
    host = self._CreateHost(docker_image='gcr.io/android-mtt/mtt:prod')
    self.assertTrue(cli._PullUpdate(args, host))

    is_running.assert_called_once_with('mtt')
    get_image_id.assert_called_once_with('mtt')
    self.mock_context.Run.assert_has_calls([
        mock.call(['docker', 'pull', 'gcr.io/android-mtt/mtt:prod'])])
    get_remote_image_digest.assert_has_calls([
        mock.call('image_id'),
        mock.call('gcr.io/android-mtt/mtt:prod'),
    ])

  @mock.patch('__main__.cli.command_util.DockerHelper.IsContainerRunning')
  @mock.patch('__main__.cli.command_util.DockerHelper.GetImageIdForContainer')
  @mock.patch('__main__.cli.command_util.DockerHelper.GetRemoteImageDigest')
  def testPullUpdate_sameImage(
      self, get_remote_image_digest, get_image_id, is_running):
    """Test PullUpdate with the same remote image."""
    is_running.return_value = 'running'
    get_image_id.return_value = 'image_id'
    get_remote_image_digest.return_value = 'remote_image'
    args = self.arg_parser.parse_args(['update'])
    host = self._CreateHost(docker_image='gcr.io/android-mtt/mtt:prod')
    self.assertFalse(cli._PullUpdate(args, host))

    is_running.assert_called_once_with('mtt')
    get_image_id.assert_called_once_with('mtt')
    self.mock_context.Run.assert_has_calls([
        mock.call(['docker', 'pull', 'gcr.io/android-mtt/mtt:prod'])])
    get_remote_image_digest.assert_has_calls([
        mock.call('image_id'),
        mock.call('gcr.io/android-mtt/mtt:prod'),
    ])

  @mock.patch.object(tempfile, 'mkdtemp')
  def testSetupSystemdScript(self, mock_create_temp):
    tmp_folder = os.path.join(self.tmp_root, 'mtt_extracted')
    os.mkdir(tmp_folder)
    mock_create_temp.return_value = tmp_folder
    mtt_path = os.path.join(self.tmp_root, 'mtt')
    unittest_util.CreateZipFile(
        mtt_path,
        [unittest_util.File(
            filename='multitest_transport/mttd.service',
            content='this is a fake mttd systemd script')])

    args = mock.create_autospec(cli.argparse.Namespace)
    args.cli_path = mtt_path
    host = mock.create_autospec(cli.host_util.Host)
    host.name = 'host1'
    cli._SetupSystemdScript(args, host)
    host.context.CopyFile.assert_called_once_with(
        os.path.join(tmp_folder, cli._ZIPPED_MTTD_FILE),
        cli._MTTD_FILE)
    host.context.Run.assert_has_calls([
        mock.call(['systemctl', 'daemon-reload'])])

  @mock.patch.object(lab_config.HostConfig, 'Save')
  def testSetupMTTRuntimeIntoPermanentPath(self, mock_save):
    mtt_path = os.path.join(self.tmp_root, 'mtt')
    key_path = os.path.join(self.tmp_root, 'keyfile', 'key.json')
    args = mock.create_autospec(cli.argparse.Namespace)
    args.cli_path = mtt_path
    host = mock.create_autospec(cli.host_util.Host)
    host.config = lab_config.CreateHostConfig(
        service_account_json_key_path=key_path)
    cli._SetupMTTRuntimeIntoLibPath(args, host)
    host.context.assert_has_calls([
        mock.call.CopyFile(mtt_path, cli._MTT_BINARY),
        mock.call.CopyFile(key_path, cli._KEY_FILE),
    ])
    mock_save.assert_called_once_with(cli._HOST_CONFIG)

  @parameterized.named_parameters(
      ('Daemon is active', True, 0, '**/nActive: active (running)\n**', ''),
      ('Daemon is inactive', False, 3, '**/nActive: inactive (dead)\n**', ''),
      ('Daemon is not registered', False, 4, '', '**could not be found.\n'))
  def testIsDaemonActive(self, expect_active, return_code, stdout, stderr):
    host = self._CreateHost()
    host.context.Run.side_effect = [
        common.CommandResult(
            return_code=return_code, stdout=stdout, stderr=stderr)
    ]
    self.assertEqual(expect_active, cli._IsDaemonActive(host))

  def testForceKillMttNode_withoutContainerRunning(self):
    host = self._CreateHost()
    docker_helper = mock.create_autospec(cli.command_util.DockerHelper)
    docker_helper.IsContainerRunning.return_value = False
    cli._ForceKillMttNode(host, docker_helper, 'a_container_name')
    host.context.Run.assert_not_called()
    docker_helper.IsContainerRunning.assert_called_with('a_container_name')

  def testForceKillMttNode_withContainerRunning(self):
    host = self._CreateHost()
    docker_helper = mock.create_autospec(cli.command_util.DockerHelper)
    docker_helper.IsContainerRunning.side_effect = [
        True,
        True,
        False,
    ]
    docker_helper.GetProcessIdForContainer.return_value = 'acontainer_pid'
    host.context.Run.side_effect = [
        common.CommandResult(0, 'a_parent_pid\n', None),
        common.CommandResult(0, None, None),
    ]

    cli._ForceKillMttNode(host, docker_helper, 'a_container_name')

    docker_helper.GetProcessIdForContainer.assert_called_with(
        'a_container_name')
    docker_helper.IsContainerRunning.assert_called_with('a_container_name')
    docker_helper.Wait.assert_called_with(['a_container_name'])
    host.context.Run.assert_has_calls([
        mock.call(['ps', '-o', 'ppid=', '-p', 'acontainer_pid'],
                  raise_on_failure=True),
        mock.call(['kill', '-9', 'a_parent_pid'], raise_on_failure=True),
    ])

  @mock.patch.object(cli, '_ForceKillMttNode')
  @mock.patch('__main__.cli.time')
  def testDetectAndKillDeadContainer_detectedAndKilled(self, mock_time,
                                                       mock_kill):
    docker_helper = mock.create_autospec(cli.command_util.DockerHelper)
    docker_helper.IsContainerDead.side_effect = [False, False, True]
    docker_helper.IsContainerRunning.return_value = True
    mock_time.time.side_effect = [0, 0, 30, 60, 90]
    host = self._CreateHost()
    container_name = 'container_1'

    cli._DetectAndKillDeadContainer(host, docker_helper, container_name, 90)

    mock_kill.assert_called_with(host, docker_helper, container_name)
    self.assertLen(mock_time.sleep.call_args_list, 2)

  @mock.patch.object(cli, '_ForceKillMttNode')
  @mock.patch('__main__.cli.time')
  def testDetectAndKillDeadContainer_timedOut(self, mock_time, mock_kill):
    docker_helper = mock.create_autospec(cli.command_util.DockerHelper)
    docker_helper.IsContainerDead.return_value = False
    docker_helper.IsContainerRunning.return_value = True
    mock_time.time.side_effect = [0, 0, 30, 60, 90]
    host = self._CreateHost()
    container_name = 'container_1'

    cli._DetectAndKillDeadContainer(host, docker_helper, container_name, 90)

    mock_kill.assert_called_with(host, docker_helper, container_name)
    self.assertLen(mock_time.sleep.call_args_list, 3)

  @mock.patch.object(cli, '_ForceKillMttNode')
  @mock.patch('__main__.cli.time')
  def testDetectAndKillDeadContainer_NoLongerRunning(self, mock_time,
                                                     mock_kill):
    docker_helper = mock.create_autospec(cli.command_util.DockerHelper)
    docker_helper.IsContainerDead.side_effect = [False, False, True]
    docker_helper.IsContainerRunning.side_effect = [True, True, False]
    mock_time.time.side_effect = [0, 0, 30, 60, 90]
    host = self._CreateHost()
    container_name = 'container_1'

    cli._DetectAndKillDeadContainer(host, docker_helper, container_name, 90)

    mock_kill.assert_not_called()
    self.assertLen(mock_time.sleep.call_args_list, 2)

  @mock.patch.object(cli, '_UpdateMttNode')
  def testRunDaemonIteration_autoUpdate(self, mtt_update):
    args = self.arg_parser.parse_args(['daemon'])
    host = self._CreateHost(enable_autoupdate=True)
    cli._RunDaemonIteration(args, host)
    mtt_update.assert_called_with(args, host)

  @mock.patch.object(cli, '_UpdateMttNode')
  def testRunDaemonIteration_uiUpdate(self, mtt_update):
    args = self.arg_parser.parse_args(['daemon'])
    host = self._CreateHost(enable_ui_update=True)
    self.mock_control_server_client.GetHostMetadata.return_value = {
        'hostname': host.config.hostname,
        'testHarnessImage': 'gcr.io/android-mtt/mtt:123',
    }
    cli._RunDaemonIteration(args, host)
    mtt_update.assert_called_with(args, host)
    self.assertEqual('gcr.io/android-mtt/mtt:123', host.config.docker_image)

  @mock.patch.object(cli, '_UpdateMttNode')
  def testRunDaemonIteration_uiUpdateNoMetadata(self, mtt_update):
    args = self.arg_parser.parse_args(['daemon'])
    host = self._CreateHost(enable_ui_update=True)
    self.mock_control_server_client.GetHostMetadata.return_value = {
        'hostname': host.config.hostname,
    }
    cli._RunDaemonIteration(args, host)
    mtt_update.assert_called_with(args, host)
    self.assertEqual('gcr.io/android-mtt/mtt:prod', host.config.docker_image)

  @mock.patch.object(cli, '_UpdateMttNode')
  def testRunDaemonIteration_runNothing(self, mtt_update):
    args = self.arg_parser.parse_args(['daemon'])
    host = self._CreateHost()
    cli._RunDaemonIteration(args, host)
    mtt_update.assert_not_called()

  @mock.patch.object(cli, '_UpdateMttNode')
  @mock.patch.object(google_auth_util, 'CreateCredentialFromServiceAccount')
  @mock.patch.object(google_auth_util, 'GetSecret')
  def testRunDaemonIteration_withServiceAccountSecret(
      self, get_secret, create_credential, mtt_update):
    mock_cred = mock.MagicMock()
    create_credential.return_value = mock_cred
    get_secret.return_value = b'{"private_key_id": "id2"}'
    local_key_path = os.path.join(self.tmp_root, 'key.json')
    with open(local_key_path, 'w') as f:
      f.write('{"private_key_id": "id1"}')

    args = self.arg_parser.parse_args(['daemon'])
    host = self._CreateHost(
        secret_project_id='aproject',
        service_account_key_secret_id='asecret',
        service_account_json_key_path=local_key_path)
    cli._RunDaemonIteration(args, host)
    mtt_update.assert_not_called()
    create_credential.assert_called_once_with(
        local_key_path, [google_auth_util.AUTH_SCOPE])
    get_secret.assert_called_once_with(
        'aproject', 'asecret', credentials=mock_cred)
    with open(local_key_path) as f:
      new_key = f.read()
    self.assertEqual('{"private_key_id": "id2"}', new_key)

  @mock.patch.object(google_auth_util, 'CreateCredentialFromServiceAccount')
  @mock.patch.object(google_auth_util, 'GetSecret')
  def testUpdateServiceAccountKeyFile(self, get_secret, create_credential):
    mock_cred = mock.MagicMock()
    create_credential.return_value = mock_cred
    get_secret.return_value = b'{"private_key_id": "id2"}'
    local_key_path = os.path.join(self.tmp_root, 'key.json')
    with open(local_key_path, 'w') as f:
      f.write('{"private_key_id": "id1"}')

    cli._UpdateServiceAccountKeyFile('aproject', 'asecret', local_key_path)
    create_credential.assert_called_once_with(
        local_key_path, [google_auth_util.AUTH_SCOPE])
    get_secret.assert_called_once_with(
        'aproject', 'asecret', credentials=mock_cred)
    with open(local_key_path) as f:
      new_key = f.read()
    self.assertEqual('{"private_key_id": "id2"}', new_key)

  @mock.patch.object(google_auth_util, 'CreateCredentialFromServiceAccount')
  @mock.patch.object(google_auth_util, 'GetSecret')
  def testUpdateServiceAccountKeyFile_localSameAsRemote(
      self, get_secret, create_credential):
    mock_cred = mock.MagicMock()
    create_credential.return_value = mock_cred
    get_secret.return_value = b'{"private_key_id": "id1"}'
    local_key_path = os.path.join(self.tmp_root, 'key.json')
    with open(local_key_path, 'w') as f:
      f.write('{"private_key_id": "id1"}')

    cli._UpdateServiceAccountKeyFile('aproject', 'asecret', local_key_path)
    create_credential.assert_called_once_with(
        local_key_path, [google_auth_util.AUTH_SCOPE])
    get_secret.assert_called_once_with(
        'aproject', 'asecret', credentials=mock_cred)
    with open(local_key_path) as f:
      new_key = f.read()
    self.assertEqual('{"private_key_id": "id1"}', new_key)

  @mock.patch.object(google_auth_util, 'CreateCredentialFromServiceAccount')
  @mock.patch.object(google_auth_util, 'GetSecret')
  def testUpdateServiceAccountKeyFile_exception(
      self, get_secret, create_credential):
    mock_cred = mock.MagicMock()
    create_credential.return_value = mock_cred
    get_secret.side_effect = [Exception('fail to get secret')]
    local_key_path = os.path.join(self.tmp_root, 'key.json')
    with open(local_key_path, 'w') as f:
      f.write('{"private_key_id": "id1"}')

    cli._UpdateServiceAccountKeyFile('aproject', 'asecret', local_key_path)
    create_credential.assert_called_once_with(
        local_key_path, [google_auth_util.AUTH_SCOPE])
    get_secret.assert_called_once_with(
        'aproject', 'asecret', credentials=mock_cred)
    with open(local_key_path) as f:
      new_key = f.read()
    self.assertEqual('{"private_key_id": "id1"}', new_key)


_ALL_START_OPTIONS = (
    ('force_update', True),
    ('name', 'container'),
    ('image_name', 'image'),
    ('tag', 'tag'),
    ('service_account_json_key_path', 'key.json'),
    ('port', 8001),
    ('max_local_virtual_devices', 1),
    ('remote_virtual_devices', 'user1@192.0.2.3/2'),
    ('server_log_level', 'info'),
    ('operation_mode', 'UNKNOWN'),
)
_ALL_STOP_OPTIONS = (
    ('name', 'container'),
    ('wait', True),
)
_ALL_RESTART_OPTIONS = tuple(
    _ALL_START_OPTIONS + _ALL_STOP_OPTIONS)
_ALL_UPDATE_OPTIONS = tuple(
    _ALL_START_OPTIONS + _ALL_STOP_OPTIONS)


class CliParserTest(parameterized.TestCase):
  """Unit tests for cli."""

  def setUp(self):
    super().setUp()
    self.arg_parser = cli.CreateParser()

  def _CreateCommandLine(self, prefix_args, options, suffix_args):
    cmd = prefix_args[:]
    for key, value in options:
      cmd.append('--%s' % key)
      if not isinstance(value, bool):
        cmd.append(value.__str__())
    cmd.extend(suffix_args)
    return cmd

  @parameterized.named_parameters(
      ('start', 'start', cli.Start),
      ('stop', 'stop', cli.Stop),
      ('restart', 'restart', cli.Restart),
      ('update', 'update', cli.Update))
  def testParseArg_defaultOptions(self, cmd, f):
    """Test arg parsing for default options."""
    args = self.arg_parser.parse_args([cmd])
    self.assertEqual(f, args.func)

  @parameterized.named_parameters(
      ('start', 'start', cli.Start, _ALL_START_OPTIONS),
      ('stop', 'stop', cli.Stop, _ALL_STOP_OPTIONS),
      ('restart', 'restart', cli.Restart, _ALL_RESTART_OPTIONS),
      ('update', 'update', cli.Update, _ALL_UPDATE_OPTIONS))
  def testParseArg_AllOptions(self, cmd, f, options):
    """Test arg parsing for default options."""
    cmd = self._CreateCommandLine([cmd], options, ['lab_config.yaml'])
    args = self.arg_parser.parse_args(cmd)
    self.assertEqual(f, args.func)
    for key, value in options:
      self.assertEqual(value, getattr(args, key))
    self.assertEqual('lab_config.yaml', args.lab_config_path)
    self.assertEqual(f, args.func)


if __name__ == '__main__':
  absltest.main()
