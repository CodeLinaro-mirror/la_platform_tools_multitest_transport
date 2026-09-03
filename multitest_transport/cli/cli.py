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

"""A package management CLI for MTT.

This tool is supposed to be bootstrapped by 'mtt' script and expects the current
working directory to be the root of MTT package.
"""
import argparse
import hashlib
from importlib import resources
import json
import logging
import os
import os.path
import re
import shlex
import shutil
import socket
import sys
import tempfile
import time
from typing import Optional, Tuple
import urllib.parse
import zipfile


from multitest_transport.cli import cli_util
from multitest_transport.cli import command_util
from multitest_transport.cli import google_auth_util
from multitest_transport.cli import host_util
from multitest_transport.cli import ssh_util
from multitest_transport.util import env
from multitest_transport.util import worker_lab_health_client
from packaging import version
from packaging_legacy import version as legacy_version
import requests
import six
from tradefed_cluster.configs import lab_config_pb2


from com_google_deviceinfra.src.devtools.deviceinfra.host.daemon.proto import health_pb2

_MTT_CONTAINER_NAME = 'mtt'
# The port must be consistent with those in init.sh and serve.sh.
_MTT_CONTROL_SERVER_PORT = 8000
_MTT_SERVER_WAIT_TIME_SECONDS = 300  # 5min
_MTT_SERVER_LOG_PATH = '/data/log/server/current'

_MTT_LIB_DIR = '/var/lib/mtt'
_MTT_LOG_DIR = '/var/log/mtt'
_MTT_LIB_DIR_USER = os.path.expanduser('~/.mtt/lib')
_MTT_LOG_DIR_USER = os.path.expanduser('~/.mtt/log')
_TMP_DIR = '/tmp'
_KEY_FILE = os.path.join(_MTT_LIB_DIR, 'keyfile', 'key.json')
_KEY_FILE_USER = os.path.join(_MTT_LIB_DIR_USER, 'keyfile', 'key.json')
_DOCKER_KEY_FILE = os.path.join(_TMP_DIR, 'keyfile', 'key.json')
# Permanent MTT binary path has to match the one in mttd.service or
# mttd-user.service file.
_MTT_BINARY = os.path.join(_MTT_LIB_DIR, 'mtt')
_HOST_CONFIG = os.path.join(_MTT_LIB_DIR, 'mtt_host_config.yaml')
_MTT_BINARY_USER = os.path.join(_MTT_LIB_DIR_USER, 'mtt')
_HOST_CONFIG_USER = os.path.join(_MTT_LIB_DIR_USER, 'mtt_host_config.yaml')
_ZIPPED_MTTD_FILE = 'multitest_transport/mttd.service'
_ZIPPED_MTTD_FILE_USER = 'multitest_transport/mttd-user.service'
# Location of the MTT systemd daemon script when running as a system service.
_MTTD_FILE = '/etc/systemd/system/mttd.service'
# Location of the MTT systemd daemon script when running as a user service.
_MTTD_FILE_USER = os.path.expanduser('~/.config/systemd/user/mttd-user.service')
_CONFIG_ROOT = 'config'
_VERSION_FILE = 'VERSION'
_UNKNOWN_VERSION = 'unknown'
_DAEMON_UPDATE_INTERVAL_SEC = 600
_ADB_SERVER_PORT = 5037
# Docker networking arguments.
_DOCKER_BRIDGE_NETWORK = 'bridge'
_DOCKER_HOST_NETWORK = 'host'
# The device nodes required by local virtual devices.
_LOCAL_VIRTUAL_DEVICE_NODES = ('/dev/kvm', '/dev/vhost-vsock', '/dev/net/tun',
                               '/dev/vhost-net')
# Docker seccomp profile as a resource.
_SECCOMP_PROFILE_PACKAGE = 'multitest_transport.cli'
_SECCOMP_PROFILE_NAME = 'seccomp.json'
# Docker seccomp profile copied to host file system.
_SECCOMP_PROFILE_PATH = os.path.join(_TMP_DIR, 'mtt_seccomp.json')
# The help message about remote virtual devices.
_REMOTE_VIRTUAL_DEVICES_FORMAT_MSG = '<user>@<IP address>/<number of devices>'

# Tradefed accept TSTP signal as 'quit', which will wait all running tests
# to finish.
_TF_QUIT = 'TSTP'
# Tradefed accept TERM signal as 'kill', which will kill all tests.
_TF_KILL = 'TERM'
# The long wait time for MTT docker container shutdown (graceful shutdown)
_LONG_CONTAINER_SHUTDOWN_TIMEOUT_SEC = 60 * 60
# The short wait time for MTT docker container shutdown (force shutdown)
_SHORT_CONTAINER_SHUTDOWN_TIMEOUT_SEC = 10 * 60
# The waiting interval to check mtt container liveliness
_DETECT_INTERVAL_SEC = 30
# The dict key name of test harness image from host metadata
_TEST_HARNESS_IMAGE_KEY = 'testHarnessImage'
# The dict key name of "allow_to_update" from host metadata
_ALLOW_TO_UPDATE_KEY = 'allowToUpdate'

# Success indicator once tradefed console started, should match to the println
# string in startConsole() method after console.start();
# in tools/tradefederation/core/src/com/android/tradefed/command/Console.java
_TF_CONSOLE_SUCCESS_INDICATOR = 'help all'
# Success indicator once omni lab server started.
_OMNI_LAB_SERVER_SUCCESS_INDICATOR = 'Lab server successfully started'
# command for check log: "docker logs mtt"
_DOCKER_LOGS_MTT_COMMAND = ['logs', 'mtt']
# interval in second for checking out the logs
_LOG_INQUIRE_INTERVAL_SEC = 5

_PRIVATE_KEY_ID_KEY = 'private_key_id'

PACKAGE_LOGGER_NAME = 'multitest_transport.cli'
logger = logging.getLogger(__name__)

_CRASH_REPORT_FILE_PATH = '/data/.crash_report_file'

# Percentage of hosts to rollout ATS2 by default. This is an integer between 0
# and 100.

_DEFAULT_ATS2_ROLLOUT_PERCENTAGE = 10

_ATS2_ROLLOUT_CONFIG_URL = (
    'https://storage.googleapis.com/android-mtt.appspot.com/prod/'
    'rollout_config.json'
)
_PROD_ENVIRONMENT = 'prod'


class ActionableError(Exception):
  """Errors which can be corrected by user actions."""

  def __init__(self, message):
    super().__init__()
    self.message = message


def _WaitForServer(url, timeout):
  """Wait for a server to be ready.

  Args:
    url: a server url.
    timeout: max wait time.
  Returns:
    True if the service is ready. Otherwise False.
  """
  end_time = time.time() + timeout
  while True:
    remaining_time = end_time - time.time()
    if remaining_time <= 0:
      break
    try:
      six.moves.urllib.request.urlopen(url, timeout=remaining_time)
      return True
    except (socket.error, six.moves.urllib.error.URLError):
      time.sleep(0.1)
  return False


def _HasSudoAccess():
  """Check if the current process has sudo access."""
  return os.geteuid() == 0


def _GetDockerImageName(image_name, tag=None):
  """Get a Docker image name to use.

  Args:
    image_name: an image name.
    tag: an image tag (optional).
  Returns:
    a Docker image name.
  """
  if tag:
    image_name = image_name.split(':', 2)[0] + ':' + tag
  return image_name


def _GetMttServerPublicPorts(control_server_port):
  """Get the ports that the container should publish.

  The ports must be consistent with those in init.sh and serve.sh.

  Args:
    control_server_port: the control server port on the host.

  Returns:
    tuple of ports.
  """
  return (
      control_server_port,
      # TODO: Remove legacy FILE_BROWSER_PORT after a few releases.
      control_server_port + 5,  # FILE_BROWSER_PORT (backwards compatibility)
      control_server_port + 6,  # FILE_SERVER_PORT
  )


def _GetAdbVersion():
  """Determine the current adb version."""
  output = os.popen('adb version').read()
  match = re.search('Version (.*)\n', output)
  return match.group(1) if match else 'UNKNOWN'


def _IsDaemonActive(host):
  """Check if the mttd daemon process is active or not.

  Args:
    host: an instance of host_util.Host.

  Returns:
    Bool, True if the daemon is now active, otherwise False.
  """
  status_cmd = (
      ['systemctl', '--user', 'status', 'mttd-user.service']
      if host.config.run_mttd_as_user_service
      else ['systemctl', 'status', 'mttd.service']
  )
  cmd_result = host.context.Run(
      status_cmd,
      raise_on_failure=False,
  )
  return cmd_result.return_code == 0


def _SetupSystemdScript(args, host):
  """Setup the mttd systemd script on host.

  Args:
    args: a parsed argparse.Namespace object.
    host: an instance of host_util.Host.

  Raises:
    zipfile.BadZipfile exception, when the zip file is bad.
    KeyError, when the mttd file does not exist in the zip.
  """
  logger.info('Setting up MTT systemd daemon script on %s', host.name)
  tmp_folder = tempfile.mkdtemp()
  is_user_service = host.config.run_mttd_as_user_service
  try:
    with zipfile.ZipFile(args.cli_path, 'r') as cli_zip:
      mttd_path = cli_zip.extract(
          _ZIPPED_MTTD_FILE_USER if is_user_service else _ZIPPED_MTTD_FILE,
          tmp_folder,
      )
  except zipfile.BadZipfile:
    logger.error('%s is not a zip file.', args.cli_path)
    raise
  except KeyError:
    logger.error(
        'No %s in %s.',
        _ZIPPED_MTTD_FILE_USER if is_user_service else _ZIPPED_MTTD_FILE,
        args.cli_path,
    )
    raise
  else:
    mttd_dest = _MTTD_FILE_USER if is_user_service else _MTTD_FILE
    host.context.CopyFile(mttd_path, mttd_dest)
    daemon_reload_cmd = (
        ['systemctl', '--user', 'daemon-reload']
        if is_user_service
        else ['systemctl', 'daemon-reload']
    )
    host.context.Run(daemon_reload_cmd)
  finally:
    if tmp_folder:
      shutil.rmtree(tmp_folder)
  # Create a log folder for MTT system daemon.
  host.context.Run([
      'mkdir',
      '-p',
      _MTT_LOG_DIR_USER if is_user_service else _MTT_LOG_DIR,
  ])


def _SetupMTTRuntimeIntoLibPath(args, host):
  """Setup the mtt runtime files in a permanent directory on host.

  Args:
    args: a parsed argparse.Namespace object.
    host: an instance of host_util.Host.
  """
  is_user_service = host.config.run_mttd_as_user_service
  host.context.CopyFile(
      args.cli_path,
      _MTT_BINARY_USER if is_user_service else _MTT_BINARY,
  )
  if host.config.service_account_json_key_path:
    key_file_path = _KEY_FILE_USER if is_user_service else _KEY_FILE
    host.context.CopyFile(
        host.config.service_account_json_key_path, key_file_path
    )
    host.config = host.config.SetServiceAccountJsonKeyPath(key_file_path)
  host.config.Save(_HOST_CONFIG_USER if is_user_service else _HOST_CONFIG)


def _GetHostTimezone():
  """Get a host timezone.

  Returns:
    A TZ name of a host timezone.
  """
  try:
    with open('/etc/timezone') as f:
      return f.read().strip()
  except Exception:  
    logger.exception('Failed to get host timezone from /etc/timezone.')
    return 'Etc/UTC'


def _CheckMttNodePrerequisites(args, host):
  """Check whether the host is set up for mtt.

  Args:
    args: a parsed argparse.Namespace object.
    host: an instance of host_util.Host.

  Raises:
    ActionableError: if any prerequisite is not met.
  """
  messages = []
  # Make sure that no adb server is running on the host.
  if not args.use_host_adb:
    try:
      with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as adb_socket:
        adb_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        adb_socket.bind(('127.0.0.1', args.adb_server_port))
    except OSError:
      messages.append('Adb server port %d is not available. If adb is running, '
                      'please run `adb kill-server` and try again.' %
                      args.adb_server_port)
  # Check the device nodes required by local virtual devices.
  if ((args.max_local_virtual_devices or
       host.config.max_local_virtual_devices) and
      not all(os.path.exists(path) for path in _LOCAL_VIRTUAL_DEVICE_NODES)):
    messages.append('Some required device nodes are missing. '
                    'Try `sudo modprobe -a kvm tun vhost_net vhost_vsock`.')
  if messages:
    raise ActionableError('\n'.join(messages))
  # Try connecting to the remote host that runs virtual devices.
  if args.remote_virtual_devices:
    user, host, _ = _ParseRemoteVirtualDevicesArg(args.remote_virtual_devices)
    if not os.path.exists(args.remote_ssh_key):
      raise ActionableError(f'{args.remote_ssh_key} does not exist.')
    ssh_context = ssh_util.Context(
        ssh_util.SshConfig(user=user, hostname=host,
                           ssh_args=('-o PasswordAuthentication=no '
                                     '-o StrictHostKeyChecking=no '
                                     '-o UserKnownHostsFile=/dev/null'),
                           ssh_key=args.remote_ssh_key,
                           use_native_ssh=True))
    # Delete existing virtual devices, runtime files, and shared images.
    # pkill returns 0 if it finds any process; 1 if it finds no process.
    # The device action rvd_setup in config.yaml creates mtt_rvd.
    result = ssh_context.run(f'pkill --uid {user} --exact run_cvd ; '
                             'test $? -le 1 && '
                             'rm -rf acloud_* mtt_rvd')
    if result.return_code != 0:
      logger.warning('The specified --remote_virtual_devices and '
                     '--remote_ssh_key are invalid. Please test the arguments '
                     'with `ssh -i %s %s@%s`',
                     args.remote_ssh_key, user, host)


def _CreateSeccompProfile(host):
  """Create a seccomp profile in temporary directory.

  Args:
    host: an instance of host_util.Host.

  Returns:
    The path to the seccomp profile.
  """
  with resources.path(_SECCOMP_PROFILE_PACKAGE,
                      _SECCOMP_PROFILE_NAME) as resource_path:
    host.context.CopyFile(resource_path, _SECCOMP_PROFILE_PATH)
  return _SECCOMP_PROFILE_PATH


def _CheckDockerImageVersion(docker_helper, container_name):
  """Check a Docker image is compatible with CLI.

  Args:
    docker_helper: a command_util.DockerHelper object.
    container_name: a container name.
  Raises:
    ActionableError: if a Docker image is newer than CLI.
  """
  res = docker_helper.Exec(container_name, ['printenv', 'MTT_VERSION'])
  cli_version, _ = cli_util.GetVersion()
  image_version = res.stdout
  if (not cli_version or '_' not in cli_version or
      not image_version or '_' not in image_version):
    logger.debug(
        'CLI or Docker image version is unrecognizable; '
        'skipping version check: cli_version=%s, image_version=%s',
        cli_version, image_version)
    return
  cli_build_env, cli_version = cli_version.strip().split('_', 1)
  image_build_env, image_version = image_version.strip().split('_', 1)
  if cli_build_env != image_build_env:
    logger.warning(
        'CLI and Docker image are from different release channels; '
        'proceed with cautions (%s != %s)',
        cli_build_env, image_build_env)
    return

  try:
    cli_version_obj = legacy_version.parse(cli_version)
    image_version_obj = legacy_version.parse(image_version)
  except version.InvalidVersion:
    logger.debug(
        'CLI or Docker image version is unrecognizable; '
        'skipping version check: cli_version=%s, image_version=%s', cli_version,
        image_version)
    return

  if cli_version_obj < image_version_obj:
    # Stop a started container.
    docker_helper.Stop([container_name])
    raise ActionableError(
        'CLI is older than Docker image; please update CLI to a newer version'
        '(%s < %s)' % (cli_version, image_version))


def _IsConsoleSuccessfullyStarted(host, is_omnilab_based):
  """Check is the success indicator detected from docker logs.

  Args:
    host: an instance of host_util.Host.
    is_omnilab_based: is omnilab based console or not.

  Returns:
    True if find the success indicator in docker logs.
  Raises:
    RuntimeError: if exceptions detected in docker logs.
  """
  indicator = (
      _OMNI_LAB_SERVER_SUCCESS_INDICATOR
      if is_omnilab_based
      else _TF_CONSOLE_SUCCESS_INDICATOR
  )
  docker_context = command_util.DockerContext(host.context, login=False)
  end_time = time.time() + _MTT_SERVER_WAIT_TIME_SECONDS
  docker_log = ''
  while time.time() <= end_time:
    remaining_time = int(end_time - time.time())
    docker_context.RequestTfConsolePrintOut()
    command_result = docker_context.Run(
        _DOCKER_LOGS_MTT_COMMAND, timeout=remaining_time
    )
    docker_log = command_result.stderr + '\n' + command_result.stdout

    if indicator in command_result.stdout:
      return True
    time.sleep(_LOG_INQUIRE_INTERVAL_SEC)
  # when timeout, check the docker log for exception and raise error if any.
  if 'exception' in docker_log.lower():
    raise RuntimeError('ATS failed to start with exception:\n%s' % (docker_log))
  # Otherwise, raise error indicating the server failed to start.
  else:
    raise RuntimeError(
        'ATS replica failed to start in %ss with docker log:\n%s'
        % (_MTT_SERVER_WAIT_TIME_SECONDS, docker_log)
    )


def _GetTargetNetwork(args, config, docker_env):
  """Get target Docker network based on command-line args and host config."""
  # 1. First check command-line arguments (highest priority).
  if network := getattr(args, 'network', None):
    return network
  config_network = getattr(config, 'network', None)
  if config_network and getattr(config, 'use_host_network', False):
    raise ActionableError(
        'Conflicting host.config: network and use_host_network cannot be '
        'enabled together in the configuration file.'
    )

  if getattr(args, 'use_host_network', False) or getattr(
      config, 'use_host_network', False
  ):
    return _DOCKER_HOST_NETWORK
  if config_network:
    return config_network
  if (
      not getattr(config, 'use_host_network', False)
      and 'MTT_SUPPORT_BRIDGE_NETWORK=true' in docker_env
  ):
    return _DOCKER_BRIDGE_NETWORK
  return _DOCKER_HOST_NETWORK


def _IsContainerNetwork(network):
  """Returns True if the network attaches to a container."""
  return bool(network and str(network).startswith('container:'))


def Start(args, host=None):
  """Execute 'mtt start [OPTION] ...' on local host.

  Args:
    args: a parsed argparse.Namespace object.
    host: an instance of host_util.Host.

  Raises:
    RuntimeError: if a MTT node fails to start.
  """
  host = host or host_util.CreateHost(args)
  if args.enable_auto_update or host.config.enable_autoupdate:
    _StartMttDaemon(args, host)
    return
  if host.config.enable_ui_update:
    host.control_server_client.PatchTestHarnessImageToHostMetadata(
        host.config.hostname, host.config.docker_image)
    _StartMttDaemon(args, host)
    return
  _StartMttNode(args, host)


def _StartMttNode(args, host):
  """Start MTT node on local hosts.

  Args:
    args: a parsed argparse.Namespace object.
    host: an instance of host_util.Host.

  Raises:
    ActionableError: if a MTT node fails to start due to user errors.
    RuntimeError: if a MTT node fails to start.
  """
  host.control_server_client.SubmitHostUpdateStateChangedEvent(
      host.config.hostname, host_util.HostUpdateState.RESTARTING,
      target_image=host.config.docker_image)
  control_server_url = args.control_server_url or host.config.control_server_url
  control_file_server_url = args.control_file_server_url
  operation_mode = lab_config_pb2.OperationMode.Value(args.operation_mode)
  if operation_mode == lab_config_pb2.OperationMode.UNKNOWN and host.config.operation_mode:
    # Override operation mode if arg value is UNKNOWN and host has config.
    operation_mode = host.config.operation_mode
  image_name = _GetDockerImageName(
      args.image_name or host.config.docker_image, tag=args.tag)
  docker_server = args.docker_server or host.config.docker_server
  logger.info('Using image %s.', image_name)
  docker_context = command_util.DockerContext(
      host.context,
      docker_server=docker_server,
      service_account_json_key_path=host.config.service_account_json_key_path)
  docker_helper = command_util.DockerHelper(docker_context, image_name)

  if docker_helper.IsContainerRunning(args.name):
    logger.error('MTT is already running.')
    return

  _CheckMttNodePrerequisites(args, host)

  if args.force_update or not docker_helper.DoesResourceExist(image_name):
    docker_helper.Pull()

  # Get image build environment and release version
  image_build_env, release = _GetImageVersionInfo(docker_helper, image_name)

  # Determine if we should use ATS 2.0
  is_omnilab_based = _IsOmnilabBased(
      args, host.config, image_build_env, release, image_name
  )

  # Enable FUSE
  docker_helper.AddDeviceNode('/dev/fuse')
  docker_helper.AddCapability('sys_admin')
  docker_helper.AddExtraArgs(['--security-opt', 'apparmor:unconfined'])

  # Set seccomp
  docker_helper.AddExtraArgs(['--security-opt',
                              'seccomp=' + _CreateSeccompProfile(host)])

  docker_env = docker_helper.GetEnv(image_name)
  network = _GetTargetNetwork(args, host.config, docker_env)
  if network != _DOCKER_HOST_NETWORK and not _IsContainerNetwork(network):
    # Containers sharing network namespace cannot configure hostname.
    docker_helper.SetHostname(host.name)
    docker_helper.AddEnv('PARENT_HOSTNAME', host.name)
    docker_helper.AddEnv('LOCAL_HOSTNAME', 'mtt')
  docker_helper.SetNetwork(network)

  docker_helper.AddEnv(
      'OPERATION_MODE',
      lab_config_pb2.OperationMode.Name(operation_mode).lower())
  docker_helper.AddEnv('MTT_CLI_VERSION', cli_util.GetVersion()[0])

  if args.enable_persistent_cache:
    docker_helper.AddEnv('ENABLE_PERSISTENT_CACHE', 'true')
  if args.use_dcon_xds_address:
    docker_helper.AddEnv('USE_DCON_XDS_ADDRESS', 'true')
  if args.bind_jfs_volume:
    docker_helper.AddVolume(args.bind_jfs_volume, '/jfs')
    docker_helper.AddEnv('PERSISTENT_CACHE_DIR', '/jfs/persistent_cache')

  if args.omni_mode_usage or host.config.omni_mode_usage:
    docker_helper.AddEnv(
        'OMNI_MODE_USAGE', args.omni_mode_usage or host.config.omni_mode_usage
    )

  if control_server_url:
    docker_helper.AddEnv('MTT_CONTROL_SERVER_URL', control_server_url)
    u = urllib.parse.urlparse(control_server_url)
    if not control_file_server_url and u.hostname and u.port:
      # Set default value for control file server url
      control_file_server_url = u._replace(netloc=u.hostname + ':' +
                                           str(u.port + 6)).geturl()
    if control_file_server_url:
      docker_helper.AddEnv('MTT_CONTROL_FILE_SERVER_URL',
                           control_file_server_url)
  else:
    logger.info(
        'The control_server_url is not set; starting a standalone node.')
  # TODO: Use config to differentiate worker and controller.
  if (control_server_url and operation_mode
      == lab_config_pb2.OperationMode.ON_PREMISE) or not control_server_url:
    docker_helper.AddEnv('MTT_CONTROL_SERVER_PORT', args.port)
    if network != _DOCKER_HOST_NETWORK and not _IsContainerNetwork(network):
      for port in _GetMttServerPublicPorts(args.port):
        # The server binds to IPv4 addresses only.
        docker_helper.AddPort(f'{args.bind_address}:{port}', port)
      if not control_server_url:
        # Public Netdata port
        netdata_port = args.port + 8
        docker_helper.AddPort(
            f'{args.bind_address}:{netdata_port}', netdata_port
        )
  if host.config.lab_name:
    docker_helper.AddEnv('LAB_NAME', host.config.lab_name)
  if host.config.cluster_name:
    docker_helper.AddEnv('CLUSTER', host.config.cluster_name)
  docker_helper.AddEnv('IMAGE_NAME', image_name)

  if args.enable_config_service:
    docker_helper.AddEnv('MTT_ENABLE_CONFIG_SERVICE', 'true')
    config_service_grpc_port = args.config_service_grpc_port
    if config_service_grpc_port:
      docker_helper.AddEnv(
          'MTT_CONFIG_SERVICE_GRPC_PORT', str(config_service_grpc_port)
      )
      if network != _DOCKER_HOST_NETWORK and not _IsContainerNetwork(network):
        docker_helper.AddPort(
            f'{args.bind_address}:{config_service_grpc_port}',
            config_service_grpc_port,
        )
    if args.config_service_storage_type:
      docker_helper.AddEnv(
          'MTT_CONFIG_SERVICE_STORAGE_TYPE', args.config_service_storage_type
      )
    if args.config_service_local_storage_dir:
      docker_helper.AddEnv(
          'MTT_CONFIG_SERVICE_LOCAL_STORAGE_DIR',
          args.config_service_local_storage_dir,
      )

  if args.connect_labserver_to_config_server:
    docker_helper.AddEnv(
        'MTT_CONNECT_LABSERVER_TO_CONFIG_SERVER',
        'true',
    )

  if host.config.tf_global_config_path:
    docker_helper.AddEnv(
        'TF_GLOBAL_CONFIG_PATH',
        host.config.tf_global_config_path)

  docker_helper.AddEnv('USER', os.environ.get('USER'))
  docker_helper.AddEnv('TZ', _GetHostTimezone())

  # Copy proxy settings if exists.
  http_proxy = docker_helper.CopyEnv('HTTP_PROXY', ['http_proxy'])
  docker_helper.CopyEnv('HTTPS_PROXY', ['https_proxy'])
  docker_helper.CopyEnv('FTP_PROXY', ['ftp_proxy'])
  no_proxy = os.environ.get('NO_PROXY', os.environ.get('no_proxy'))
  if http_proxy or no_proxy:
    # Add localhost to NO_PROXY. This enables in-server API calls.
    no_proxy_list = ['127.0.0.1', '::1', 'localhost', host.name]
    if no_proxy:
      no_proxy_list.append(no_proxy)
    no_proxy = ','.join(no_proxy_list)
    os.environ['NO_PROXY'] = no_proxy
    logger.debug('NO_PROXY=%s', no_proxy)
    docker_helper.AddEnv('NO_PROXY', no_proxy)

  if (
      host.context.IsLocal()
      and args.mount_host_android_dir
      and not host.config.skip_mount_host_android_dir
  ):
    android_sdk_path = os.path.expanduser('~/.android')
    if os.path.exists(android_sdk_path):
      # If running locally, bind ~/.android to access existing adb
      # fingerprints.
      docker_helper.AddBind(android_sdk_path, '/root/.android')

  docker_helper.AddVolume('mtt-data', '/data')
  docker_helper.RemoveVolumes(['mtt-temp'])
  docker_helper.AddVolume('mtt-temp', '/tmp')
  docker_helper.AddBind('/var/run/docker.sock', '/var/run/docker.sock')

  if host.config.service_account_json_key_path:
    docker_helper.AddVolume('mtt-key', os.path.dirname(_DOCKER_KEY_FILE))
    docker_helper.AddFile(
        host.config.service_account_json_key_path, _DOCKER_KEY_FILE)
    docker_helper.AddEnv('JSON_KEY_PATH', _DOCKER_KEY_FILE)
  if getattr(args, 'android_service_account_key_path', None):
    docker_helper.AddVolume('mtt-tf-key', '/tradefed/secrets')
    docker_helper.AddFile(
        args.android_service_account_key_path,
        '/tradefed/secrets/key.json',
    )
  if host.config.enable_stackdriver:
    if host.config.service_account_json_key_path:
      docker_helper.AddEnv('ENABLE_STACKDRIVER_LOGGING', 1)
      docker_helper.AddEnv('ENABLE_STACKDRIVER_MONITORING', 1)
    else:
      logger.error(
          'Set "service_account_json_key_path" in lab config or command-line'
          'args to enable stackdriver.')

  for tmpfs_config in host.config.tmpfs_configs:
    docker_helper.AddTmpfs(
        tmpfs_config.path, size=tmpfs_config.size, mode=tmpfs_config.mode)

  extra_docker_args = (host.config.extra_docker_args +
                       (args.extra_docker_args or []))
  if extra_docker_args:
    # Use shlex.split to properly remove quotes.
    extra_docker_args = shlex.split(' '.join(extra_docker_args))
    logger.debug('Add extra docker args: %s', extra_docker_args)
    docker_helper.AddExtraArgs(extra_docker_args)

  # Create user file store if necessary, and then mount it and any additional
  # paths in the temporary volume. These files and directories will be linked
  # into the local file store.
  user_file_store = os.path.expanduser('~/.ats_storage')
  host.context.Run(['mkdir', '-p', user_file_store])
  mount_paths = [user_file_store]
  mount_paths.extend(
      args.mount_local_path or host.config.mount_local_paths or []
  )
  for mount_path in mount_paths:
    local_path, remote_path = (mount_path.split(':', 1) + [None])[:2]
    if not remote_path:
      remote_path = os.path.basename(local_path)  # pyrefly: ignore[no-matching-overload]
    remote_path = os.path.normpath('/tmp/.mnt/' + remote_path)
    logger.debug('Mounting \'%s\' to \'%s\'', local_path, remote_path)
    docker_helper.AddBind(local_path, remote_path)
  docker_helper.AddEnv('MTT_SERVER_LOG_LEVEL', args.server_log_level)

  enable_ipv6_bridge_network = False
  if network != _DOCKER_HOST_NETWORK and not _IsContainerNetwork(network):
    network_info = docker_helper.GetBridgeNetworkInfo()
    if network_info.IsIPv6Enabled():
      enable_ipv6_bridge_network = True
      ipv6_subnet, _ = network_info.GetIPv6Subnet()
      if not ipv6_subnet:
        raise ActionableError(
            'Cannot get IPv6 subnet of bridge network. '
            'Please check fixed-cidr-v6 in '
            '/etc/docker/daemon.json and restart docker '
            'daemon.'
        )
      docker_helper.AddEnv('IPV6_BRIDGE_NETWORK', ipv6_subnet)

    if args.use_host_adb:
      docker_helper.AddEnv('MTT_USE_HOST_ADB', '1')
      _, host_ip = network_info.GetIPv4Subnet()
      if not host_ip:
        raise ActionableError(
            'Cannot get IPv4 gateway of bridge network. '
            'Please check /etc/docker/daemon.json and '
            'restart docker daemon.'
        )
      logger.info(
          'Using host ADB; please forward %s:5037 to ADB server port (e.g. run'
          ' "socat tcp-listen:5037,bind=%s,reuseaddr,fork'
          ' tcp-connect:127.0.0.1:5037 &")',
          host_ip,
          host_ip,
      )
    else:
      if not _IsContainerNetwork(network):
        docker_helper.AddPort(
            '127.0.0.1:%d' % args.adb_server_port, _ADB_SERVER_PORT
        )

  # Labconsole ports
  labconsole_grpc_port = args.labconsole_grpc_port
  labconsole_rest_port = args.labconsole_rest_port
  lab_console_port = args.lab_console_port
  if args.enable_lab_console_ui:
    docker_helper.AddEnv(
        'MTT_ENABLE_LAB_CONSOLE_UI',
        'true',
    )
    if args.connect_labconsole_to_config_server:
      docker_helper.AddEnv(
          'MTT_CONNECT_LABCONSOLE_TO_CONFIG_SERVER',
          'true',
      )
    docker_helper.AddEnv(
        'LABCONSOLE_SERVER_GRPC_PORT', str(labconsole_grpc_port)
    )
    docker_helper.AddEnv(
        'LABCONSOLE_SERVER_REST_PORT', str(labconsole_rest_port)
    )
    docker_helper.AddEnv('LAB_CONSOLE_PORT', str(lab_console_port))
    logger.debug('labconsole grpc port=%d, rest port=%d, ui port=%d',
                 labconsole_grpc_port, labconsole_rest_port, lab_console_port)
  else:
    docker_helper.AddEnv(
        'MTT_ENABLE_LAB_CONSOLE_UI',
        'false',
    )
    logger.debug('enable_lab_console_ui is false.')

  custom_sdk_dir = None
  if args.custom_adb_path:
    # Create temp directory for custom SDK tools, will be copied over to ensure
    # MTT has access, and will be cleaned up on next start
    custom_sdk_dir = tempfile.mkdtemp()
    docker_helper.AddFile(custom_sdk_dir, '/tmp/custom_sdk_tools')
    # TODO: support GCS files
    shutil.copy(args.custom_adb_path, '%s/adb' % custom_sdk_dir)

  max_local_virtual_devices = args.max_local_virtual_devices
  if max_local_virtual_devices == 0 and host.config.max_local_virtual_devices:
    max_local_virtual_devices = host.config.max_local_virtual_devices
  if max_local_virtual_devices:
    docker_helper.AddEnv('MAX_LOCAL_VIRTUAL_DEVICES',
                         str(max_local_virtual_devices))
    # Add the dependency of crosvm and qemu.
    for device_node in _LOCAL_VIRTUAL_DEVICE_NODES:
      docker_helper.AddDeviceNode(device_node)
    # Allow crosvm to control the tun device.
    docker_helper.AddCapability('net_admin')
    # Enable IPv6 for the virtual network interfaces.
    if enable_ipv6_bridge_network:
      docker_helper.AddSysctl('net.ipv6.conf.all.disable_ipv6', '0')
      docker_helper.AddSysctl('net.ipv6.conf.all.forwarding', '1')

  if args.use_cloud_orchestrator:
    docker_helper.AddEnv(
        'CLOUD_ORCHESTRATOR_URL', args.orchestration_service_url
    )

  if args.remote_virtual_devices and args.remote_ssh_key:
    docker_helper.AddEnv('REMOTE_VIRTUAL_DEVICES', args.remote_virtual_devices)
    # The device action rvd_setup in config.yaml loads /tmp/rvd_id_rsa.
    docker_helper.AddFile(args.remote_ssh_key, '/tmp/rvd_id_rsa')

  if args.extra_ca_cert:
    docker_helper.AddFile(
        args.extra_ca_cert, '/usr/local/share/ca-certificates/')

  if is_omnilab_based:
    docker_helper.AddEnv('IS_OMNILAB_BASED', 'true')
    if (
        network != _DOCKER_HOST_NETWORK
        and not _IsContainerNetwork(network)
        and operation_mode == lab_config_pb2.OperationMode.ON_PREMISE
    ):
      if control_server_url:
        # Public lab server port of the worker
        docker_helper.AddPort(f'{args.bind_address}:9994', 9994)
      else:
        # Public OLC server port of the controller
        docker_helper.AddPort(f'{args.bind_address}:7030', 7030)
        # Public worker grpc port of the controller
        docker_helper.AddPort(f'{args.bind_address}:7031', 7031)

  docker_helper.Run(args.name)

  _CheckDockerImageVersion(docker_helper, args.name)

  # Delete temp tools directory.
  if custom_sdk_dir:
    shutil.rmtree(custom_sdk_dir)

  hostname = host.name
  if host.context.IsLocal():
    # We change hostname to localhost since
    # MTT's build channel authorization only works when accessed with
    # localhost URL.
    hostname = 'localhost'
  if control_server_url:
    if _IsConsoleSuccessfullyStarted(host, is_omnilab_based):
      logger.info('ATS replica is running.')
  else:
    url = 'http://%s:%s' % (hostname, args.port)
    if not _WaitForServer(url, timeout=_MTT_SERVER_WAIT_TIME_SECONDS):
      docker_helper.Logs(args.name)
      docker_helper.Cat(args.name, _MTT_SERVER_LOG_PATH)
      raise RuntimeError(
          'ATS server failed to start in %ss' % _MTT_SERVER_WAIT_TIME_SECONDS)
    logger.info('ATS is serving at %s', url)
  if is_omnilab_based:
    logger.info(
        'Currently running ATS 2.0 (Omnilab based). You can override this by'
        ' setting --force_ats_version 1.'
    )
  else:
    print('\n' + '=' * 80)
    print('INFO: ATS 2.0 is now available!')
    print(
        'Enhance your testing experience with the new Omnilab-based '
        'infrastructure.'
    )
    print(
        "Add '--force_ats_version 2 --force_update' to your start command to"
        ' try it out.'
    )
    print(
        'Learn more at https://source.android.com/docs/core/tests/development/'
        'android-test-station/ats-user-guide'
    )
    print('=' * 80 + '\n')


def _StartMttDaemon(args, host):
  """Start MTT daemon on local host.

  Args:
    args: a parsed argparse.Namespace object.
    host: an instance of host_util.Host.

  Raises:
    RuntimeError: when failing to run command on host.
    ActionableError: when root privileges are not granted.
  """
  is_user_service = host.config.run_mttd_as_user_service
  logger.info(
      'Starting MTT daemon on %s as a %s service.',
      host.name,
      'user' if is_user_service else 'system',
  )
  if _IsDaemonActive(host):
    logger.warning('MTT daemon is already running on %s.', host.name)
    return
  if not is_user_service and not _HasSudoAccess():
    raise ActionableError(
        'The root privileges are required to start MTT daemon as a system'
        ' service. Please consider run MTT CLI with sudo access. If you are'
        ' running MTT Lab CLI, please consider adding flags --sudo_user and/or'
        ' --ask_sudo_password.'
    )
  _SetupMTTRuntimeIntoLibPath(args, host)
  _SetupSystemdScript(args, host)
  # Enable the daemon service, to make sure it can "start" on system reboot.
  # Note: this command will not start the service immediately.
  enable_cmd = (
      ['systemctl', '--user', 'enable', 'mttd-user.service']
      if is_user_service
      else ['systemctl', 'enable', 'mttd.service']
  )
  host.context.Run(enable_cmd)
  # Start the daemon service immediately.
  start_cmd = (
      ['systemctl', '--user', 'start', 'mttd-user.service']
      if is_user_service
      else ['systemctl', 'start', 'mttd.service']
  )
  host.context.Run(start_cmd)
  # Enable automatic start-up of systemd user instance
  # (https://wiki.archlinux.org/title/Systemd/User)
  if is_user_service:
    host.context.Run(['loginctl', 'enable-linger'])
  logger.info(('MTT daemon started on %s. '
               'It keeps MTT container up and running on the latest version.'),
              host.name)


def Stop(args, host=None):
  """Execute 'mtt stop [OPTION] ...' on local host.

  Args:
    args: a parsed argparse.Namespace object.
    host: an instance of host_util.Host.
  """
  host = host or host_util.CreateHost(args)
  _StopMttDaemon(host)
  _StopMttNode(args, host)


def _StopMttNode(args, host):
  """Stop MTT node on a local host.

  Args:
    args: a parsed argparse.Namespace object.
    host: an instance of host_util.Host.
  """
  host.control_server_client.SubmitHostUpdateStateChangedEvent(
      host.config.hostname, host_util.HostUpdateState.SHUTTING_DOWN,
      target_image=host.config.docker_image)
  docker_context = command_util.DockerContext(host.context, login=False)
  docker_helper = command_util.DockerHelper(docker_context)

  # TODO: The kill logic should be more general and works for both
  # mtt and dockerized tf.
  if docker_helper.IsContainerRunning(args.name):
    if args.drain or host.config.drain:
      logger.info('Draining container %s before stopping it.', args.name)
      _DrainMttNode(args.name, docker_helper)

    logger.info('Stopping running container %s.', args.name)

    # Remove crash report file to indicate that the docker container was
    # stopped properly (used to track reliability).
    docker_helper.Exec(args.name, ['rm', '-f', _CRASH_REPORT_FILE_PATH])

    timeout = None
    if host.config.graceful_shutdown or args.wait:
      logger.info('Wait all tests to finish.')
      docker_helper.Kill([args.name], _TF_QUIT)
      # Send shutdown signal to mariadb to gracefully shut down the database.
      docker_helper.Exec(args.name, ['bash', '-c', 'mysqladmin shutdown'])
      timeout = _LONG_CONTAINER_SHUTDOWN_TIMEOUT_SEC
    else:
      # This send "TERM" to TF inside the container.
      logger.info('Send TERM signal to TF. This will stop all running tests.')
      docker_helper.Kill([args.name], _TF_KILL)
      timeout = _SHORT_CONTAINER_SHUTDOWN_TIMEOUT_SEC
    if host.config.shutdown_timeout_sec:
      timeout = host.config.shutdown_timeout_sec
    if _HasSudoAccess():
      _DetectAndKillDeadContainer(host, docker_helper, args.name, timeout)
    else:
      try:
        docker_helper.Wait([args.name], timeout=timeout)
      except command_util.CommandTimeoutError:
        logger.warning(
            'Container is still running after %s seconds; killing...',
            timeout)
        docker_helper.Stop([args.name])
        docker_helper.Wait([args.name])
  logger.info('Container %s stopped.', args.name)
  res_inspect = docker_helper.Inspect(args.name)
  if res_inspect.return_code != 0:
    logger.info('No container %s.', args.name)
    return
  logger.info('Remove container %s.', args.name)
  docker_helper.RemoveContainers([args.name], raise_on_failure=False)


def _DrainMttNode(name, docker_helper):
  """Drain the existing traffic of MTT node on a local host.

  Only applicable when the server is Omnilab based while starting MTT.

  Args:
    name: string, the name of docker container to drain.
    docker_helper: an instance of command_util.DockerHelper.
  """
  worker_lab_grpc_server_address = _GetWorkerLabGprcServerAddress(
      name, docker_helper
  )
  try:
    health_client = worker_lab_health_client.WorkerLabHealthClient.create(
        worker_lab_grpc_server_address
    )
    health_client.drain(health_pb2.DrainServerRequest())
    while True:
      status_response = health_client.check(health_pb2.CheckStatusRequest())
      if status_response.status == health_pb2.ServingStatus.DRAINED:
        break
      logger.info(
          'Waiting for drain to complete. Current status: %s',
          health_pb2.ServingStatus.Name(status_response.status),
      )
      time.sleep(30)
    logger.info('Drain complete.')
  except worker_lab_health_client.WorkerLabHealthRpcError as e:
    logger.error('Failed to drain lab: %s', e)


def _GetWorkerLabGprcServerAddress(name, docker_helper):
  """Get the worker lab server address used to call its gRPC services.

  Args:
    name: string, the name of docker container to drain.
    docker_helper: an instance of command_util.DockerHelper.

  Returns:
    The worker lab gRPC server address. The default address is returned if the
    gRPC port wasn't overridden when starting the MTT container.
  """
  # We try to parse out the --grpc_port parameter value (if set when bringing up
  # the MTT container) from the Docker container's LAB_SERVER_OPTS environment
  # variable.
  # Example: "LAB_SERVER_OPTS=--no_op_device_num=5 --grpc_port=50001"
  grpc_port_param = env.WORKER_LAB_SERVER_PORT

  docker_env = docker_helper.GetEnv(name)
  for env_var in docker_env:
    if not env_var.startswith('LAB_SERVER_OPTS='):
      continue
    # 1. Remove "LAB_SERVER_OPTS=" prefix
    lab_server_opts = env_var.replace('LAB_SERVER_OPTS=', '', 1)
    # 2. Split into individual key-value pairs.
    params = [param for param in lab_server_opts.split(' ')]
    # 3. Iterate through individual parameters to find the target
    for param in params:
      if param.startswith('--grpc_port='):
        grpc_port_param = param.split('=', 1)[1]

  server_address = f'localhost:{grpc_port_param}'
  logger.debug('Will use worker lab gRPC server address: %s', server_address)
  return server_address


def _DetectAndKillDeadContainer(host, docker_helper, container_name, timeout):
  """Detect a dead MTT container, force kill it when detected or timed out.

  Args:
    host: an instance of host_util.Host.
    docker_helper: an instance of command_util.DockerHelper.
    container_name: string, the name of docker container to kill.
    timeout: seconds to wait before killing a container. Can be
        overridden by host config.
  """
  total_wait_sec = timeout
  logging.debug(
      'Waiting %d sec for docker container shutdown.', total_wait_sec)
  wait_end_sec = time.time() + total_wait_sec
  while time.time() < wait_end_sec:
    if not docker_helper.IsContainerRunning(container_name):
      logging.debug('The docker container %s has shut down already.',
                    container_name)
      return
    if docker_helper.IsContainerDead(container_name):
      logging.debug('The docker container %s is not alive.', container_name)
      _ForceKillMttNode(host, docker_helper, container_name)
      return
    logging.debug('Waiting for docker container <%s> on host <%s> shutdown.',
                  container_name, host.name)
    time.sleep(_DETECT_INTERVAL_SEC)
  logging.info(
      'The container <%s> failed to shutdown within given %ss on host <%s>.',
      container_name, total_wait_sec, host.name)
  _ForceKillMttNode(host, docker_helper, container_name)


def _ForceKillMttNode(host, docker_helper, container_name):
  """Force kill MTT container and its parent process.

  This method guarantees to kill a docker container, and it should be used only
  when "docker kill/stop" does not work, or times out.

  Args:
    host: an instance of host_util.Host.
    docker_helper: an instance of command_util.DockerHelper.
    container_name: string, the name of docker container to kill.
  """
  logger.info('Force killing MTT node on host %s', host.name)
  if not docker_helper.IsContainerRunning(container_name):
    logger.info('The container process does not exist, skipping killing.')
    return
  # Step 1: Find process ID of MTT container.
  mtt_pid = docker_helper.GetProcessIdForContainer(container_name)
  # Step 2: Get the parent process ID of MTT(containerd-shim process ID).
  res = host.context.Run(
      ['ps', '-o', 'ppid=', '-p', mtt_pid], raise_on_failure=False
  )
  if res.return_code == 0:
    containerd_pid = res.stdout.strip()
    # Step 3: Kill the parent process of MTT and wait until it exists.
    host.context.Run(['kill', '-9', containerd_pid], raise_on_failure=True)
  else:
    logger.warning(
        'Failed to find parent process ID for PID %s (maybe running in a'
        ' container?). Falling back to docker kill.',
        mtt_pid,
    )
    docker_helper.Kill([container_name])
  docker_helper.Wait([container_name])


def _StopMttDaemon(host):
  """Restart MTT daemon on a local host.

  Args:
    host: an instance of host_util.Host.

  Raises:
    ActionableError: when root privileges are not granted.
  """
  is_user_service = host.config.run_mttd_as_user_service
  if not _IsDaemonActive(host):
    logger.debug('MTT daemon is not active on %s. Skip daemon stop.', host.name)
    return
  if not is_user_service and not _HasSudoAccess():
    raise ActionableError(
        'The root privileges are required to stop MTT daemon run as a system'
        ' service. Please consider run MTT CLI with sudo access. If you are'
        ' running MTT Lab CLI, please consider adding flags --sudo_user and/or'
        ' --ask_sudo_password.'
    )
  logger.info('Stopping MTT daemon on %s.', host.name)
  # Stop the daemon service immediately.
  stop_cmd = (
      ['systemctl', '--user', 'stop', 'mttd-user.service']
      if is_user_service
      else ['systemctl', 'stop', 'mttd.service']
  )
  host.context.Run(stop_cmd)
  # Unregister the daemon service, so that it does not start on system reboot.
  disable_cmd = (
      ['systemctl', '--user', 'disable', 'mttd-user.service']
      if is_user_service
      else ['systemctl', 'disable', 'mttd.service']
  )
  host.context.Run(disable_cmd)


def _PullUpdate(args, host):
  """Pull the latest version of the image.

  Args:
    args: a parsed argparse.Namespace object.
    host: an instance of host_util.Host.
  Returns:
    True if container need to be restarted.
    False otherwise.
  """
  if args.force_update:
    logger.info('force_update==True, updating.')
    return True
  if args.image_name:
    host.config = host.config.SetDockerImage(args.image_name)
  image_name = _GetDockerImageName(host.config.docker_image)
  docker_server = args.docker_server or host.config.docker_server
  logger.debug('Using image %s.', image_name)
  docker_context = command_util.DockerContext(
      host.context,
      docker_server=docker_server,
      service_account_json_key_path=host.config.service_account_json_key_path)
  docker_helper = command_util.DockerHelper(docker_context, image_name)
  # docker doesn't provide a command to inspect remote image directly.
  # And to use docker repository http API:
  # https://docs.docker.com/registry/spec/api/, the authenticating will
  # be difficult, especially we have 2 different authentication ways.
  # Here we are checking the remote image is the same as the running container's
  # image or not. Logically the following 2 ways are the same:
  # 1. pull the image, compare the remote image with running container,
  #    update if they are not the same.
  # 2. compare the remote image with runnint container, pull and update
  #    if they are not the same.
  # Here we do 1, since it's much simpler. Pull will be slow when the images
  # are different, but it will be cheap if the images are the same, so there
  # should be no performance concerns.
  docker_helper.Pull()
  if not docker_helper.IsContainerRunning(args.name):
    logger.info('%s is not running, will start %s with %s.',
                args.name, args.name, image_name)
    return True
  logger.info('%s is running.', args.name)
  container_image_id = docker_helper.GetImageIdForContainer(args.name)
  container_image_remote_digest = (
      docker_helper.GetRemoteImageDigest(container_image_id))
  image_remote_digest = docker_helper.GetRemoteImageDigest(image_name)
  if container_image_remote_digest == image_remote_digest:
    logger.info('%s is already using the same image as remote, skip.',
                args.name)
    return False
  if (
      host.config.enable_ui_update
      or args.enable_auto_update
      or host.config.enable_autoupdate
  ):
    if (host.config.max_concurrent_update_percentage and
        not host.metadata.get(_ALLOW_TO_UPDATE_KEY, False)):
      logger.info(
          'Pending to kick-off the update of currently running container '
          'until getting sign-off from control server, '
          'because max_concurrent_update_percentage was '
          'limited to %d%% in the physical cluster.',
          host.config.max_concurrent_update_percentage)
      return False
  host.control_server_client.SubmitHostUpdateStateChangedEvent(
      host.config.hostname, host_util.HostUpdateState.SYNCING,
      target_image=host.config.docker_image)
  docker_helper.CleanupUnusedImages()
  logger.info(
      '%s != %s, should restart.',
      container_image_remote_digest, image_remote_digest)
  return True


def Update(args, host=None):
  """Execute 'mtt update [OPTION] ...' on the local host.

  Args:
    args: a parsed argparse.Namespace object.
    host: an instance of host_util.Host.
  """
  host = host or host_util.CreateHost(args)
  _StopMttDaemon(host)
  if args.enable_auto_update or host.config.enable_autoupdate:
    _StartMttDaemon(args, host)
    return
  if host.config.enable_ui_update:
    host.control_server_client.PatchTestHarnessImageToHostMetadata(
        host.config.hostname, host.config.docker_image)
    _StartMttDaemon(args, host)
    return
  _UpdateMttNode(args, host)


def _UpdateMttNode(args, host):
  """Update mtt node on the local host.

  Args:
    args: a parsed argparse.Namespace object.
    host: an instance of host_util.Host.
  """
  if not _PullUpdate(args, host):
    return

  if host.config.update_delay_sec:
    logger.info(
        'Delaying for %d seconds based on config update_delay_sec before'
        ' restarting %s.',
        host.config.update_delay_sec,
        args.name,
    )
    time.sleep(host.config.update_delay_sec)

  logger.info('Restarting %s.', args.name)
  try:
    _StopMttNode(args, host)
    _StartMttNode(args, host)
  except Exception as e:  
    host.control_server_client.SubmitHostUpdateStateChangedEvent(
        host.config.hostname,
        host_util.HostUpdateState.ERRORED,
        display_message=str(e),
        target_image=host.config.docker_image)
    raise e
  host.control_server_client.SubmitHostUpdateStateChangedEvent(
      host.config.hostname, host_util.HostUpdateState.SUCCEEDED,
      target_image=host.config.docker_image)


def Restart(args, host=None):
  """Execute 'mtt restart [OPTION] ...' on the local host.

  Args:
    args: a parsed argparse.Namespace object.
    host: an instance of host_util.Host.
  """
  host = host or host_util.CreateHost(args)
  _StopMttDaemon(host)
  _StopMttNode(args, host)
  if args.enable_auto_update or host.config.enable_autoupdate:
    _StartMttDaemon(args, host)
    return
  if host.config.enable_ui_update:
    host.control_server_client.PatchTestHarnessImageToHostMetadata(
        host.config.hostname, host.config.docker_image)
    _StartMttDaemon(args, host)
    return
  _StartMttNode(args, host)


def RunDaemon(args, host=None):
  """Run MTT daemon on the local host.

  Args:
    args: a parsed argparse.Namespace object.
    host: an instance of host_util.Host.
  """
  while True:
    _RunDaemonIteration(args, host=host)
    time.sleep(_DAEMON_UPDATE_INTERVAL_SEC)


def _RunDaemonIteration(args, host=None):
  """Run one iteration of daemon task.

  Args:
    args: a parsed argparse.Namespace object.
    host: an instance of host_util.Host.
  """
  if not args.no_check_update:
    try:
      new_path = cli_util.CheckAndUpdateTool(
          args.cli_path,
          cli_update_url=args.cli_update_url)
      if new_path:
        logger.debug('CLI is updated.')
        os.execv(new_path, [new_path] + sys.argv[1:])
    except Exception as e:  
      logger.warning('Failed to check/update tool: %s', e)
  host = host or host_util.CreateHost(args)
  if (host.config.secret_project_id and
      host.config.service_account_key_secret_id and
      host.config.service_account_json_key_path):
    _UpdateServiceAccountKeyFile(
        host.config.secret_project_id,
        host.config.service_account_key_secret_id,
        host.config.service_account_json_key_path)
  if args.enable_auto_update or host.config.enable_autoupdate:
    logger.debug('Auto-update enabled.')
    _UpdateMttNode(args, host)
    return
  if host.config.enable_ui_update:
    logger.debug('Update from UI enabled.')
    host.metadata = host.control_server_client.GetHostMetadata(
        host.config.hostname)
    test_harness_image = host.metadata.get(_TEST_HARNESS_IMAGE_KEY)
    logger.debug('Refreshed host metadata: %s.', host.metadata)
    if test_harness_image:
      logger.debug('Pinned to image: %s.', test_harness_image)
      host.config = host.config.SetDockerImage(test_harness_image)
    else:
      logger.warning(
          'No test_harness_image is found in HostMetadata, updating with '
          'image from lab config file.')
    _UpdateMttNode(args, host)


def _ParseRemoteVirtualDevicesArg(arg):
  """Parse --remote_virtual_devices."""
  user_host, _, cnt = arg.partition('/')
  user, _, host = user_host.partition('@')
  if not (user and host and cnt):
    raise ValueError(f'Expect {_REMOTE_VIRTUAL_DEVICES_FORMAT_MSG}')
  return user, host, int(cnt)


def _RemoteVirtualDevicesArg(arg):
  """Validate --remote_virtual_devices."""
  _ParseRemoteVirtualDevicesArg(arg)
  return arg


def _CreateImageArgParser():
  """Create argparser for docker image relate operations."""
  parser = argparse.ArgumentParser(add_help=False)
  parser.add_argument('--image_name', help='The docker image to use.')
  parser.add_argument('--tag', help='A tag for a new image.')
  return parser


def _CreateContainerArgParser():
  """Create argparser for docker container relate operations."""
  parser = argparse.ArgumentParser(add_help=False)
  parser.add_argument('--name', default=_MTT_CONTAINER_NAME,
                      help='Docker container name.')
  return parser


def _CreateStartArgParser():
  """Create argparser for Start."""
  parser = argparse.ArgumentParser(add_help=False)
  parser.add_argument('--force_update', action='store_true')
  parser.add_argument('--port', type=int, default=_MTT_CONTROL_SERVER_PORT)
  parser.add_argument(
      '--bind_address',
      help='Address to bind to when publishing container ports in bridge mode, '
      'or when starting server in host mode.',
      default='0.0.0.0')
  parser.add_argument(
      '--labconsole_grpc_port',
      type=int,
      default=8080,
      help='Labconsole gRPC port exposed by the container',
  )
  parser.add_argument(
      '--labconsole_rest_port',
      type=int,
      default=9000,
      help='Labconsole REST port exposed by the container',
  )
  parser.add_argument(
      '--lab_console_port',
      type=int,
      default=4200,
      help='Lab console UI port exposed by the container',
  )
  parser.add_argument(
      '--enable_lab_console_ui',
      dest='enable_lab_console_ui',
      action=argparse.BooleanOptionalAction,
      default=True,
      help='Enable Lab Console UI and backend services. Default is true.',
  )
  parser.add_argument(
      '--connect_labconsole_to_config_server',
      dest='connect_labconsole_to_config_server',
      action=argparse.BooleanOptionalAction,
      default=False,
      help=(
          'Whether the OSS FE server should connect to the config server. '
          'Default is false. Note: this is only applicable when '
          '--enable_lab_console_ui is set.'
      ),
  )
  parser.add_argument(
      '--use_dcon_xds_address',
      dest='use_dcon_xds_address',
      action=argparse.BooleanOptionalAction,
      default=False,
      help=(
          'Whether to use xDS addresses exposed by Dual Conduit. Default is'
          ' false.'
      ),
  )
  parser.add_argument(
      '--server_log_level',
      help='Server Log level',
      default='info',
      choices=['debug', 'info', 'warn', 'error', 'critical'])
  parser.add_argument(
      '--docker_server',
      help='Docker server to login when using a service account.')

  # Set env GOOGLE_APPLICATION_CREDENTIALS to the service account json key path.
  parser.add_argument(
      '--service_account_json_key_path', help='Service account json key path.')
  parser.add_argument(
      '--android_service_account_key_path',
      help=(
          'Android service account json key path (provided by Android for'
          ' access to resources like Android builds, AnTS). Do not set this'
          ' unless you are within Google or a partner of Android.'
      ),
  )
  parser.add_argument('--custom_adb_path', help='Path to custom ADB tool')
  parser.add_argument(
      '--adb_server_port', type=int,
      help='Adb server port exposed by the container',
      default=_ADB_SERVER_PORT)
  parser.add_argument(
      '--max_local_virtual_devices', type=int, default=0,
      help='Maximum number of virtual devices on local host (experimental).')
  parser.add_argument(
      '--use_cloud_orchestrator',
      action='store_true',
      help='Use JIT Emulator with Cloud Orchestrator (experimental).',
  )
  parser.add_argument(
      '--orchestration_service_url',
      default='http://localhost:8080',
      help='URL of the Cloud Orchestration service.',
  )
  parser.add_argument(
      '--remote_virtual_devices',
      type=_RemoteVirtualDevicesArg,
      help=('The remote host that runs virtual devices (experimental). Format: '
            f'{_REMOTE_VIRTUAL_DEVICES_FORMAT_MSG}'))
  parser.add_argument(
      '--remote_ssh_key',
      default=os.path.expanduser('~/.ssh/id_rsa'),
      help=('The path to the ssh key used to login the remote hosts that runs '
            'virtual devices (experimental). Default value: ~/.ssh/id_rsa'))
  parser.add_argument(
      '--extra_docker_args', action='append',
      help='Extra docker args passing to container.')
  parser.add_argument('--extra_ca_cert', help='Extra CA cert file for SSL.')
  parser.add_argument('--mount_local_path', action='append',
                      help='Additional path to mount in the local file store.')
  net_group = parser.add_mutually_exclusive_group()
  net_group.add_argument(
      '--use_host_network',
      help='Use host networking for the container.',
      action='store_true',
  )
  net_group.add_argument(
      '--network',
      help='Use a specific existing Docker network for the container.',
      default=None,
  )
  parser.add_argument(
      '--use_host_adb',
      help=(
          'Use host ADB server. This is useful when accessing virtual devices '
          'running outside Docker container.'),
      action='store_true')
  parser.add_argument(
      '--operation_mode',
      default=lab_config_pb2.OperationMode.Name(
          lab_config_pb2.OperationMode.UNKNOWN),
      choices=lab_config_pb2.OperationMode.keys(),
      help='Run ATS in a certain operation mode.')
  parser.add_argument(
      '--control_server_url',
      default=None,
      help=('Control server url is required for workers in ON_PREMISE mode.'
            'This field can also be set by yaml config.'))
  parser.add_argument(
      '--control_file_server_url',
      default=None,
      help=(
          'Set in ON_PREMISE mode if file server URL cannot be inferred '
          'from the control server URL.'
      ))
  parser.add_argument(
      '--is_omnilab_based',
      default=False,
      help=(
          'Use OmniLab based servers. This flag is deprecated. Please use'
          ' force_ats_version flag instead.'
      ),
  )
  parser.add_argument(
      '--enable_auto_update',
      default=False,
      action='store_true',
      help=(
          'Whether to enable auto update through systemd daemon service.'
          ' Default is false.'
      ),
  )
  parser.add_argument(
      '--force_ats_version',
      type=int,
      choices=[1, 2],
      help='Force to use ATS version 1 or 2. Allowed input is 1 or 2.',
  )
  parser.add_argument(
      '--mount_host_android_dir',
      dest='mount_host_android_dir',
      action=argparse.BooleanOptionalAction,
      default=True,
      help=(
          'Mount the ~/.android directory from the host, which contains'
          ' existing adb keys. Default is true.'
      ),
  )
  parser.add_argument(
      '--omni_mode_usage',
      help='Usage of the lab under Omni mode.',
      dest='omni_mode_usage',
      type=str,
  )
  parser.add_argument(
      '--enable_config_service',
      dest='enable_config_service',
      action=argparse.BooleanOptionalAction,
      default=False,
      help='Enable device config service. Default is false.',
  )
  parser.add_argument(
      '--config_service_grpc_port',
      type=int,
      default=8081,
      help='Device config service gRPC port exposed by the container',
  )
  parser.add_argument(
      '--config_service_storage_type',
      help='Device config service storage type',
      default='LOCAL_FILE',
      choices=['LOCAL_FILE', 'JDBC_CONNECTOR'],
  )
  parser.add_argument(
      '--config_service_local_storage_dir',
      help='Device config service local storage directory',
      default='/data/config_service',
  )
  parser.add_argument(
      '--connect_labserver_to_config_server',
      dest='connect_labserver_to_config_server',
      action=argparse.BooleanOptionalAction,
      default=False,
      help=(
          'Whether the OSS lab server should connect to the config server. '
          'Default is false.'
      ),
  )
  parser.add_argument(
      '--enable_persistent_cache',
      help='Enable persistent cache for the lab.',
      action='store_true',
      default=False,
  )
  parser.add_argument(
      '--bind_jfs_volume',
      help='Name of the docker volume to bind to /jfs in the container.',
      type=str,
  )

  parser.set_defaults(func=Start)
  return parser


def _GetImageVersionInfo(
    docker_helper, image_name
) -> Tuple[str, Optional[int]]:
  """Extracts the build environment and release version integer from the image.

  This parses the `MTT_VERSION` environment variable from the Docker image's
  internal metadata to safely identify build types and release numbers.

  Supported Version String Formats (MTT_VERSION):
    - Dev / Local builds: 'dev' or missing MTT_VERSION. Returns ('dev', None).
    - Legacy Prod releases: 'prod_R52.202601.001'. Returns ('prod', 52).
    - Modern Prod releases: 'prod_1.52.003'. Returns ('prod', 52).
    - Custom / Release Candidates: 'latest_20260511.000'. Returns ('latest',
    None).

  To prevent false-positive substring matches (e.g. parsing a release integer
  from the middle of a date timestamp like '202601' inside R51), we use strict
  re.match anchored at the start of the version string.

  Args:
    docker_helper: an instance of command_util.DockerHelper for inspecting.
    image_name: absolute Docker image name with tag.

  Returns:
    A tuple containing:
      - build_env (str): Environment name ('prod', 'dev', etc.).
      - release (int|None): The release number (e.g., 52 for r52/1.52 builds),
        or None if the environment is dev or has an unparseable version format.
  """
  try:
    env_vars = docker_helper.GetEnv(image_name)
  except Exception as e:  
    logger.warning('Failed to inspect image env: %s. Assuming dev.', e)
    return 'dev', None

  mtt_version = None
  for env_var in env_vars:
    if env_var.startswith('MTT_VERSION='):
      mtt_version = env_var.split('=', 1)[1]
      break

  if not mtt_version:
    logger.debug('MTT_VERSION not found in image env. Assuming dev.')
    return 'dev', None

  if mtt_version == 'dev':
    return 'dev', None

  build_env = 'dev'
  version_str = mtt_version
  if '_' in mtt_version:
    # Extract environment prefix (e.g. 'prod') and version suffix
    # (e.g. '1.52.003')
    build_env, version_str = mtt_version.strip().split('_', 1)

  release = None
  # Check modern version format: '1.XX.YYY'
  new_format_match = re.match(r'1\.(\d+)', version_str)
  if new_format_match:
    release = int(new_format_match.group(1))
  else:
    # Check legacy release format: 'RXX...' or 'rXX...'
    old_format_match = re.match(r'R(\d+)', version_str, re.IGNORECASE)
    if old_format_match:
      release = int(old_format_match.group(1))

  return build_env, release


def _GetATS2RolloutPercentage() -> int:
  """Fetches the dynamic rollout percentage from GCS with fallback."""
  try:
    response = requests.get(_ATS2_ROLLOUT_CONFIG_URL, timeout=2)
    if response.status_code == 200:
      config = response.json()
      percentage = config.get(
          'ats2_rollout_percentage', _DEFAULT_ATS2_ROLLOUT_PERCENTAGE
      )
      return int(percentage)
  except Exception as e:  
    logger.debug(
        'Failed to fetch dynamic rollout config: %s. Falling back to %d%%.',
        e,
        _DEFAULT_ATS2_ROLLOUT_PERCENTAGE,
    )
  return _DEFAULT_ATS2_ROLLOUT_PERCENTAGE


def _IsOmnilabBased(
    args,
    host_config,
    image_build_env='dev',
    release=None,
    image_name=None,
) -> bool:
  """Determines if the CLI orchestration session should use ATS 2.0 (Omnilab).

  The decision is made according to the following priority:
    1. Manual command-line force override via `--force_ats_version <1|2>`.
    2. Deprecated `--is_omnilab_based` flag (always forces ATS 2.0).
    3. Host-specific config file override via `force_ats_version`.
    4. Operation Mode check: ON_PREMISE nodes are excluded from ATS 2.0.
    5. Image build environment evaluation:
       - Non-prod (e.g. 'dev', 'latest', local builds) bypass rollout checks and
         default directly to ATS 2.0.
       - Prod ('prod') images are subject to percentage-based dynamic rollout.

  After selecting ATS 2.0, a version safety floor compatibility check is
  enforced
  for production images. If the image release version is less than 52:
    - If ATS 2.0 was explicitly forced via `--force_ats_version 2`, an
      ActionableError is raised.
    - Otherwise, the system logs a warning and falls back gracefully to ATS 1.0.

  Args:
    args: Command-line parsed arguments.
    host_config: Current host's configuration structure.
    image_build_env: The target image build environment ('prod', 'dev', etc.)
      parsed from the container metadata.
    release: Optional integer release version of the image.
    image_name: Optional string name of the Docker image for error reporting.

  Returns:
    bool: True if ATS 2.0 (Omnilab) should be enabled; False for ATS 1.0.

  Raises:
    ActionableError: If ATS 2.0 is forced on an incompatible image.
  """
  if args.force_ats_version:
    return args.force_ats_version == 2

  if args.is_omnilab_based:
    logging.info(
        '"--is_omnilab_based" flag is deprecated. Please use'
        ' "--force_ats_version" flag instead.'
    )
    return True

  if host_config.force_ats_version != 0:
    if host_config.force_ats_version not in (1, 2):
      raise ValueError(
          'Host config has force_ats_version set to an invalid value:'
          f' {host_config.force_ats_version}.'
      )
    return host_config.force_ats_version == 2

  operation_mode = lab_config_pb2.OperationMode.Value(args.operation_mode)
  if (
      operation_mode == lab_config_pb2.OperationMode.UNKNOWN
      and host_config.operation_mode
  ):
    operation_mode = host_config.operation_mode

  # On Premise mode does not have percentage rollout to ATS 2.0.
  if operation_mode == lab_config_pb2.OperationMode.ON_PREMISE:
    return False

  # Non-prod build environments (like local 'dev' and 'latest' tags) default
  # to ATS 2.0 directly.
  if image_build_env != _PROD_ENVIRONMENT:
    return True

  # Production images ('prod_...') use host-deterministic SHA-256 hashing
  # for percentage-based rollouts.
  hostname = socket.gethostname()
  hash_value = int(hashlib.sha256(hostname.encode('utf-8')).hexdigest(), 16)
  rollout_number = (hash_value % 100) + 1
  logger.debug(
      'Random number for ATS 2.0 rollout: %s, hostname: %s, hash value: %s',
      rollout_number,
      hostname,
      hash_value,
  )
  is_ats2 = rollout_number <= _GetATS2RolloutPercentage()
  if is_ats2:
    # Enforce safety floor compatibility check only for automatic rollouts.
    if release is None or release < 52:
      display_image_name = image_name or 'The target image'
      logger.warning(
          'Image %s does not support ATS 2.0. Falling back to ATS 1.0.',
          display_image_name,
      )
      return False

  return is_ats2


def _CreateStopArgParser():
  """Create argparser for Stop."""
  parser = argparse.ArgumentParser(add_help=False)
  parser.add_argument(
      '--wait', action=argparse.BooleanOptionalAction, default=True
  )
  parser.add_argument(
      '--drain',
      action='store_true',
      help=(
          'Whether to drain the existing traffic of the lab. Default is false.'
          ' Only applicable when the server is Omnilab based'
          ' (--is_omnilab_based set to true while starting MTT).'
      ),
  )
  parser.set_defaults(func=Stop)
  return parser


def _CreateRestartArgParser():
  """Create argparser for Restart."""
  parser = argparse.ArgumentParser(
      add_help=False, parents=[_CreateStartArgParser(), _CreateStopArgParser()])
  parser.set_defaults(func=Restart)
  return parser


def _CreateUpdateArgParser():
  """Create argparser for Update."""
  parser = argparse.ArgumentParser(
      add_help=False, parents=[_CreateStartArgParser(), _CreateStopArgParser()])
  parser.set_defaults(func=Update)
  return parser


def _CreateDaemonCommandArgParser():
  parser = argparse.ArgumentParser(
      add_help=False, parents=[_CreateUpdateArgParser()])
  parser.set_defaults(func=RunDaemon)
  return parser


def _CreateLabConfigArgParser():
  """Create argparser for lab config path arg."""
  parser = argparse.ArgumentParser(add_help=False)
  parser.add_argument(
      'lab_config_path', metavar='lab_config_path', type=str, nargs='?',
      help='Lab config path to use.')
  return parser


def _UpdateServiceAccountKeyFile(
    secret_project_id, secret_id, local_service_account_key_path):
  """Update local service account key path."""
  try:
    with open(local_service_account_key_path) as f:
      local_service_account_key = f.read()
    local_sa_key_dict = json.loads(local_service_account_key)
    # Only read secret when local is old.
    credentials = google_auth_util.CreateCredentialFromServiceAccount(
        local_service_account_key_path, [google_auth_util.AUTH_SCOPE])
    service_account_key = google_auth_util.GetSecret(
        secret_project_id, secret_id, credentials=credentials)
    sa_key_dict = json.loads(service_account_key)
    if (local_sa_key_dict.get(_PRIVATE_KEY_ID_KEY) ==
        sa_key_dict.get(_PRIVATE_KEY_ID_KEY)):
      logger.debug('Local service account key is the same as remote.')
      return False
    logger.debug(
        'Local service account key %s is different from remote %s. Updating %s',
        local_sa_key_dict.get(_PRIVATE_KEY_ID_KEY),
        sa_key_dict.get(_PRIVATE_KEY_ID_KEY),
        local_service_account_key_path)
    with open(local_service_account_key_path, 'w') as f:
      f.write(service_account_key.decode())
    return True
  except Exception:  
    logger.exception(
        'Fail to update service account key %s.',
        local_service_account_key_path)
    return False


def CreateParser():
  """Creates an argument parser.

  Returns:
    an argparse.ArgumentParser object.
  """
  parser = argparse.ArgumentParser(
      parents=[cli_util.CreateLoggingArgParser(),
               cli_util.CreateCliUpdateArgParser()])
  subparsers = parser.add_subparsers(title='Actions', dest='action')

  # Commands for users
  subparsers.add_parser(
      'start', help='Start a MTT instance on the local host.',
      parents=[_CreateLabConfigArgParser(), _CreateImageArgParser(),
               _CreateContainerArgParser(), _CreateStartArgParser()])
  subparsers.add_parser(
      'stop', help='Stop a MTT instance on the local host.',
      parents=[_CreateLabConfigArgParser(), _CreateContainerArgParser(),
               _CreateStopArgParser()])
  subparsers.add_parser(
      'restart', help='Restart a MTT instance on the local host.',
      parents=[
          _CreateLabConfigArgParser(), _CreateImageArgParser(),
          _CreateContainerArgParser(), _CreateRestartArgParser()])
  subparsers.add_parser(
      'update', help='Update a MTT instance on the local host.',
      parents=[
          _CreateLabConfigArgParser(), _CreateImageArgParser(),
          _CreateContainerArgParser(), _CreateUpdateArgParser()])
  subparsers.add_parser(
      'daemon', help='Run MTT daemon process.',
      parents=[
          _CreateLabConfigArgParser(), _CreateImageArgParser(),
          _CreateContainerArgParser(), _CreateDaemonCommandArgParser()])

  subparser = subparsers.add_parser(
      'version', help='Print the version of MTT CLI.')
  subparser.set_defaults(func=cli_util.PrintVersion)
  return parser


def Main():
  """The entry point function for CLI."""
  parser = CreateParser()
  args = parser.parse_args()
  args.cli_path = os.environ.get('PEX', os.path.realpath(sys.argv[0]))
  global logger
  logger = cli_util.CreateLogger(args)
  if not args.no_check_update:
    try:
      new_path = cli_util.CheckAndUpdateTool(
          args.cli_path,
          cli_update_url=args.cli_update_url)
      if new_path:
        logger.debug('CLI is updated.')
        os.execv(new_path, [new_path] + sys.argv[1:])
    except Exception as e:  
      logger.warning('Failed to check/update tool: %s', e)
  try:
    if args.action == 'version':
      cli_util.PrintVersion()
    elif hasattr(args, 'func'):
      args.func(args)
    else:
      parser.print_usage()
  except command_util.DockerNotFoundError:
    logger.error(
        'Docker is not installed on the host. Please install Docker Engine'
        '(http://www.docker.com/) and try again.')
    sys.exit(-1)
  except command_util.FabricNotFoundError:
    logger.error(
        'Running remote commands requires Fabric. Please install Fabric'
        '(http://www.fabfile.org/) and try again.')
    sys.exit(-1)
  except command_util.GCloudNotFoundError:
    logger.error(
        'gcloud is not found on the host. Please install Google Cloud SDK'
        '(https://cloud.google.com/sdk/downloads) and try again.')
    sys.exit(-1)
  except host_util.ExecutionError:
    # The information should already be printed.
    sys.exit(-1)
  except ActionableError as e:
    logger.error(e.message)
    sys.exit(-1)


if __name__ == '__main__':
  Main()
