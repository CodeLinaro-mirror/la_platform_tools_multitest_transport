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

"""A utility for running local/remote commands."""
import collections
import getpass
import ipaddress
import json
import logging
import os
import pty
import re
import shlex
import socket
import subprocess
import time

import six


from multitest_transport.cli import common
from multitest_transport.cli import google_auth_util
from multitest_transport.cli import ssh_util

logger = logging.getLogger(__name__)


try:
  import invoke  
except ImportError:
  invoke = None
  logging.warning('Failed to import invoke')

try:
  # Test importing paramiko.
  # Importing fabric can error out in uncatchable ways if paramiko errors out.
  import paramiko  
  import fabric  
except ImportError:
  fabric = None
  paramiko = None
  logging.warning('Failed to import fabric or paramiko')

DEFAULT_DOCKER_SERVER = 'https://gcr.io'

_GCLOUD_PATHS = ['gcloud', '/google/data/ro/teams/cloud-sdk/gcloud']
_REMOTE_IMAGE_DIGEST_FORMAT = '{{index .RepoDigests 0}}'
_IMAGE_ID_FORMAT = '{{.Image}}'
_IMAGE_ENV_FORMAT = '{{json .Config.Env}}'
_CONTAINER_STATUS_FORMAT = '{{.State.Status}}'
_CONTAINER_PID_FORMAT = '{{.State.Pid}}'
_CONTAINER_RUNNING_STATUS = 'running'
_NO_SUCH_OBJECT_ERROR = 'no such object'
_DEFAULT_TMPFS_SIZE_IN_BYTES = 10 * 2 ** 30  # 10G
_DOCKER_STOP_CMD_TIMEOUT_SEC = 60 * 60
_DOCKER_KILL_CMD_TIMEOUT_SEC = 60
_DOCKER_WAIT_CMD_TIMEOUT_SEC = 2 * 60 * 60
_DOCKER_LIVELINESS_CHECKING_MESSAGE = 'Checking container liveliness.'
_DOCKER_LIVELINESS_CHECKING_TIMEOUT_SEC = 2 * 60
_DEFAULT_TF_CONSOLE_CMD_TIMEOUT_SEC = 2
# docker command for attaching TF console: "docker attach mtt"
_DOCKER_ATTACH_COMMAND = ['docker', 'attach', 'mtt']
# dockerized TF command for checking TF version
_TF_VERSION_COMMAND = b'\nhelp\n'

# To exec command on a dead container, docker will output:
# OCI runtime exec failed: exec failed: cannot exec a container that has
# stopped: unknown
# to the stdout.
_DOCKER_CONTAINER_NOT_ALIVE_PATTERN = re.compile(
    '.*cannot exec a container that has stopped.*')


CommandRunConfig = collections.namedtuple(
    'CommandRunConfig', ['sudo', 'env', 'raise_on_failure', 'timeout'])


class CommandContextClosedError(Exception):
  """Error for running command on a closed context."""


class CommandTimeoutError(Exception):
  """A command failed to complete in a given timeout."""


class DockerError(Exception):
  """Docker-related error."""


class DockerNotFoundError(DockerError):
  """Docker is not found on a host."""


class DockerVersionTooOldError(DockerError):
  """Docker version is too old."""


class DockerVersionNotFoundError(DockerError):
  """Docker version is not found."""


class GCloudError(Exception):
  """GCloud-related error."""


class GCloudNotFoundError(GCloudError):
  """GCloud is not found on a host."""


class FabricNotFoundError(Exception):
  """Fabric is not found on a host."""


class AuthenticationError(Exception):
  """Fail to auth a user on a host."""


class HostCommandOutStream(object):
  """Customized file object like output stream.

  This is not thread safe.
  This is used to distinguish output from different hosts.
  """

  def __init__(self, host, tag='', log_level=logging.DEBUG):
    self.log_level = log_level
    prefixs = []
    if host:
      prefixs.append(host)
    if tag:
      prefixs.append(tag)
    self._prefix = ' '.join(prefixs)
    if self._prefix:
      self._prefix += ': '
    self._last_incomplete_line = ''

  def write(self, b):  
    """Write a string to the stream."""
    decoded_stream = six.ensure_text(b, errors='ignore')
    lines = decoded_stream.split('\n')
    if not lines:
      return
    lines[0] = self._last_incomplete_line + lines[0]
    self._last_incomplete_line = lines.pop()
    for line in lines:
      self._Print(self._prefix + line)

  def flush(self):  
    pass

  def _Print(self, line):
    """Print a line, expose for testing."""
    logger.log(self.log_level, line)


def _CreateFabricContext(ssh_config):
  """Create a fabric context."""
  # fabric has problems to understand complex ssh config.
  # Point to a user config
  fab_config = fabric.Config(system_ssh_path='~/.ssh/config')
  connect_kwargs = {
      'config': fab_config
  }
  if ssh_config.ssh_key or ssh_config.password:
    connect_kwargs['connect_kwargs'] = {}
  if ssh_config.ssh_key:
    logger.debug(
        'Use ssh key %s ssh %s@%s.', ssh_config.ssh_key,
        ssh_config.user, ssh_config.hostname)
    connect_kwargs['connect_kwargs']['key_filename'] = ssh_config.ssh_key
  if ssh_config.password:
    logger.debug('Use password to ssh %s@%s.',
                 ssh_config.user, ssh_config.hostname)
    connect_kwargs['connect_kwargs']['password'] = ssh_config.password
  connect_kwargs['user'] = ssh_config.user
  try:
    wrapped_context = fabric.Connection(
        host=ssh_config.hostname, **connect_kwargs)
    wrapped_context.open()
    return wrapped_context
  except (paramiko.AuthenticationException, paramiko.SSHException) as e:
    logger.debug(e)
    raise AuthenticationError(e)


class CommandContext(object):
  """Wrap around invoke.Context."""

  def __init__(self, host=None, user=None,
               ssh_config=None, sudo_ssh_config=None,
               wrapped_context=None, sudo_wrapped_context=None):
    """Create context that will be used to run command with.

    Args:
      host: a host name.
      user: username of the host.
      ssh_config: ssh_util.SshConfig for login to the host.
      sudo_ssh_config: ssh_util.SshConfig for login to the host as sudo.
      wrapped_context: invoke context, used for test.
      sudo_wrapped_context: invoke context, used for sudo test.
    Raises:
      FabricNotFoundError: fabric is not installed.
    """
    self._host = host or socket.gethostname()
    self._user = user or getpass.getuser()
    self._is_local = False
    self._tried_gcloud = False
    self._gcloud = None
    if socket.gethostname() == self._host or socket.getfqdn() == self._host:
      self._is_local = True

    self._ssh_config = ssh_config or ssh_util.SshConfig(
        user=user, hostname=host)
    self._sudo_ssh_config = sudo_ssh_config
    self._closed = False
    # TODO: We should make the subprocess's output configurable by
    # parent process.
    self._out_stream = HostCommandOutStream(
        None if self._is_local else host, 'stdout')
    # We also output stderr to DEBUG level, if the command failed and
    # raise on failure, the raised exception will have the information.
    self._err_stream = HostCommandOutStream(
        None if self._is_local else host, 'stderr')

    self._wrapped_context = wrapped_context
    self._sudo_wrapped_context = sudo_wrapped_context
    if self._wrapped_context:
      return
    if self._is_local:
      # Use _RunDirectly.
      return
    if self._ssh_config.use_native_ssh or not fabric:
      if not self._ssh_config.use_native_ssh and not fabric:
        logger.debug('No fabric package installed, using native ssh.')
      self._CreateNativeSshContexts()
      return
    self._CreateFabricContexts()

  def _CreateNativeSshContexts(self):
    """Create a native SSH context for a remote host.

    This function creates two fabric connections, one for sudo commands, another
    for regular commands.
    """
    self._wrapped_context = ssh_util.Context(self._ssh_config)
    if self._sudo_wrapped_context:
      return
    if not self._sudo_ssh_config:
      return
    self._sudo_wrapped_context = ssh_util.Context(self._sudo_ssh_config)
    self._TestSudoAccess()

  def _CreateFabricContexts(self):
    """Create wrapped context for a remote host.

    This function creates two fabric connections, one for sudo commands, another
    for regular commands.

    Raises:
      AuthenticationError: failed to auth
    """
    self._wrapped_context = _CreateFabricContext(self._ssh_config)
    if self._sudo_wrapped_context:
      return
    if not self._sudo_ssh_config:
      return
    self._sudo_wrapped_context = _CreateFabricContext(self._sudo_ssh_config)
    self._TestSudoAccess()

  def _TestSudoAccess(self):
    """Test sudo access on a host."""
    logger.debug('Testing sudo access.')
    try:
      self._sudo_wrapped_context.sudo(
          'echo "Testing sudo access..."',
          hide=True,
          password=self._sudo_ssh_config.password)
    except invoke.exceptions.AuthFailure as e:
      logger.debug('Sudo access failed: %s', e)
      raise AuthenticationError(e)

  @property
  def host(self):
    return self._host

  @property
  def user(self):
    return self._user

  @property
  def gcloud(self):
    return self._FindGCloud()

  def _FindGCloud(self):
    """Find a gcloud binary path if available.

    Returns:
      A gcloud binary path. None if not available.
    """
    if not self._tried_gcloud:
      self._tried_gcloud = True
      for path in _GCLOUD_PATHS:
        try:
          res = self.Run(['which', path], raise_on_failure=False)
          if res.return_code == 0:
            self._gcloud = path
            break
        except OSError as e:
          logger.debug('Failed to find %s: %s', path, e)
    return self._gcloud

  def IsLocal(self):
    return self._is_local

  def CopyFile(self, local_file_path, remote_file_path):
    """Copy a local file to the command context's host.

    Args:
      local_file_path: a local file path.
      remote_file_path: the remote file path.
    Raises:
      IOError: if the local file doesn't exist
    """
    if not os.path.exists(local_file_path):
      raise IOError('%s doesn\'t exist.' % local_file_path)
    self.Run(['mkdir', '-p', os.path.dirname(remote_file_path)])
    if not self.IsLocal():
      self._wrapped_context.put(local_file_path, remote_file_path)
      return
    if local_file_path != remote_file_path:
      self.Run(['cp', '-rf', local_file_path, remote_file_path])

  def Close(self):
    """Close the context so no more command can run."""
    logger.debug('Close connection to %s.', self.host)
    if self._closed:
      logger.debug('Connection to %s already closed.', self.host)
      return
    self._closed = True
    if not self.IsLocal() and self._wrapped_context:
      # Local wrapped context doesn't support close.
      # And also there is no need to close a local context.
      self._wrapped_context.close()
    self._wrapped_context = None

  def Run(self,
          command,
          sudo=False,
          raise_on_failure=True,
          env=None,
          timeout=None):
    """Run a command in context.

    Args:
        command: the command to run, a list of string args.
        sudo: run as sudo
        raise_on_failure: raise Exception on failure or not.
        env: additional environment variables.
        timeout: int, the timeout to run the command, in seconds.
    Returns:
        a common.CommandResult
    Raises:
        CommandContextClosedError: run command on a closed context.
    """
    if self._closed:
      raise CommandContextClosedError('%s is already closed' % self.host)
    run_config = CommandRunConfig(
        sudo=sudo, raise_on_failure=raise_on_failure, env=env, timeout=timeout)
    if self._wrapped_context:
      return self._RunOnWrappedContext(command, run_config)
    return self._RunDirectly(command, run_config)

  def _RunOnWrappedContext(self, command, run_config):
    """Run the command on a wrapped invoke.context.

    Args:
      command: a list of string.
      run_config: CommandRunConfig that config how to run the command.
    Returns:
      a common.CommandResult
    Raises:
      RuntimeError: failed to run command and raise_on_failure is true.
    """
    run_kwargs = {}
    # Instead of raise by fabric, we should raise by ourself.
    # Raise by fabric the output is hard to control.
    run_kwargs['warn'] = True
    if run_config.env:
      run_kwargs['env'] = run_config.env
    if isinstance(run_config.timeout, int):
      run_kwargs['timeout'] = run_config.timeout
    if self._out_stream:
      run_kwargs['out_stream'] = self._out_stream
      run_kwargs['err_stream'] = self._out_stream
    if self._err_stream:
      run_kwargs['err_stream'] = self._err_stream
    command_str = u' '.join([shlex.quote(token) for token in command])
    res = None
    try:
      if run_config.sudo:
        res = self._sudo_wrapped_context.sudo(
            command_str, password=self._sudo_ssh_config.password, **run_kwargs)
      else:
        res = self._wrapped_context.run(command_str, **run_kwargs)
    except invoke.exceptions.CommandTimedOut as err:
      msg = 'command %s with run config %s timed out after %s seconds' % (
          command, run_config, run_config.timeout)
      if run_config.raise_on_failure:
        raise CommandTimeoutError(msg)
      logger.warning(msg)
      return common.CommandResult(
          return_code=err.result.exited, stdout='', stderr=str(err))

    if run_config.raise_on_failure and res.return_code != 0:
      raise RuntimeError(
          'command returned %s: stdout=%s, stderr=%s' % (
              res.return_code, res.stdout, res.stderr))
    return common.CommandResult(
        return_code=res.return_code,
        stdout=res.stdout,
        stderr=res.stderr)

  def _RunDirectly(self, command, run_config):
    """Run the command on a wrapped invoke.context.

    Args:
      command: a list of string.
      run_config: CommandRunConfig that config how to run the command.
    Returns:
      a common.CommandResult.
    Raises:
      RuntimeError: failed to run command and raise_on_failure=True
    """
    if run_config.sudo:
      command = ['sudo'] + command
    logger.debug('Running command: %s', command)
    kwargs = {}
    if run_config.env:
      kwargs['env'] = dict(os.environ, **run_config.env)
    start_time = time.time()
    proc = subprocess.Popen(
        command, universal_newlines=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        **kwargs)
    try:
      stdout, stderr = proc.communicate(timeout=run_config.timeout)
    except subprocess.TimeoutExpired as e:
      if run_config.raise_on_failure:
        raise CommandTimeoutError(
            'command %s with run config %s timed out after %s seconds' % (
                command, run_config, run_config.timeout))
      return common.CommandResult(return_code=None, stdout=None, stderr=str(e))
    stdout = six.ensure_str(stdout or '')
    stderr = six.ensure_str(stderr or '')
    if stdout:
      for line in stdout.split('\n'):
        logger.debug('stdout: %s', line)
    if stderr:
      for line in stderr.split('\n'):
        logger.debug('stderr: %s', line)
    logger.debug(
        'Finished running command (took %.1fs): result=%s',
        time.time() - start_time, proc.returncode)
    if proc.returncode and run_config.raise_on_failure:
      raise RuntimeError(
          'command returned %s: stdout=%s, stderr=%s' % (
              proc.returncode, stdout, stderr))
    return common.CommandResult(
        return_code=proc.returncode, stdout=stdout, stderr=stderr)


class DockerContext(object):
  """Docker command context."""

  def __init__(
      self,
      command_context,
      login=True,
      docker_server=None,
      service_account_json_key_path=None):
    self._context = command_context
    self._docker_client_version = None
    self._CheckDocker()
    self._docker_server = docker_server or DEFAULT_DOCKER_SERVER
    self._service_account_json_key_path = service_account_json_key_path
    if login:
      self._DockerLogin()

  def _DockerLogin(self):
    """Login docker server."""
    if self._service_account_json_key_path:
      credential = google_auth_util.CreateCredentialFromServiceAccount(
          service_account_json_key_path=self._service_account_json_key_path,
          scopes=[google_auth_util.GCS_READ_SCOPE])
      self._context.Run(
          ['docker',
           'login',
           '-u', 'oauth2accesstoken',
           '-p', credential.token,
           self._docker_server],
          raise_on_failure=False)
      return
    if self._context.gcloud:
      self._context.Run(
          [self._context.gcloud, 'auth', 'configure-docker', '--quiet'],
          raise_on_failure=False)
      logger.info('gcloud auth configure-docker')
      return
    logger.warning(
        'No gcloud or service account json key file, can not login to %s.',
        self._docker_server)

  def _CheckDocker(self):
    """Check if docker is installed."""
    try:
      res = self._context.Run(['docker', '-v'], raise_on_failure=False)
    except OSError as e:
      logger.info('Failed to execute docker: %r', e)
      res = None
    if not res or res.return_code:
      raise DockerNotFoundError('Failed to run docker: res=%s' % str(res))

  def Run(self, command, **kwargs):
    """Run docker command. It's a wrap for context.run.

    Args:
      command: a str
      **kwargs: key value args
    Returns:
      invoke.runners.Result
    """
    args = ['docker']
    return self._context.Run(args + command, **kwargs)

  def RequestTfConsolePrintOut(
      self, timeout=_DEFAULT_TF_CONSOLE_CMD_TIMEOUT_SEC):
    """Attach to the dockerized TF console and print out the TF version."""
    main_file_descriptor, child_file_descriptor = pty.openpty()
    process = subprocess.Popen(
        _DOCKER_ATTACH_COMMAND, stdin=child_file_descriptor,
        stdout=child_file_descriptor, stderr=child_file_descriptor)
    os.write(main_file_descriptor, _TF_VERSION_COMMAND)
    try:
      process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
      # Timeout is expected, we communicate just to send the input
      # to TF console.
      process.kill()


class BridgeNetworkInfo(object):
  """Wrapper of the json object returned by "docker network inspect"."""

  def __init__(self, json_obj):
    self._json_obj = json_obj

  def IsIPv6Enabled(self):
    """Return whether IPv6 is enabled."""
    return self._json_obj.get('EnableIPv6', False)

  def _GetSubnet(self, ip_version):
    """Find the subnet config that matches the IP version.

    If IPv6 is enabled, the network info contains both IPv4 and IPv6 subnets.
    The IPv6 gateway can be empty when no container is running.

    Args:
      ip_version: 4 or 6, the version of the IP subnet.

    Returns:
      The subnet and the gateway as a pair of strings. Either of them can be
      None if it is not found in this object.
    """
    for config in self._json_obj['IPAM']['Config']:
      subnet = config.get('Subnet')
      try:
        if subnet and ipaddress.ip_network(subnet).version == ip_version:
          return subnet, config.get('Gateway')
      except ValueError:
        logger.warning('Cannot parse "%s" in bridge network info.', subnet)
    return None, None

  def GetIPv4Subnet(self):
    """Return IPv4 subnet and gateway as a pair of strings."""
    return self._GetSubnet(4)

  def GetIPv6Subnet(self):
    """Return IPv6 subnet and gateway as a pair of strings."""
    return self._GetSubnet(6)


class DockerHelper(object):
  """Helper to operate docker."""

  def __init__(self, docker_context, image_name=None):
    self._docker_context = docker_context
    self._image_name = image_name
    self._hostname = None
    self._network = None
    self._env = []
    self._binds = []
    self._volumes = []
    self._tmpfss = []
    self._ports = []
    self._capabilities = []
    self._device_nodes = []
    self._files = []
    self._sysctls = []
    self._extra_args = []

  def Build(self, path, build_args=None):
    """Build the docker image from given path.

    Args:
      path: the path which include DockerFile to build.
      build_args: build args to pass to Docker build command.
    """
    args = ['build', '-t', self._image_name]
    for build_arg in build_args or []:
      args.extend(['--build-arg', build_arg])
    args.append(path)
    self._docker_context.Run(args)

  def Push(self):
    """Push the docker image to remote repository."""
    self._docker_context.Run(['push', self._image_name])

  def Pull(self):
    """Pull the docker image from remote repository."""
    logger.info('Pulling %s from remote repository.',
                self._image_name)
    self._docker_context.Run(['pull', self._image_name])

  def SetHostname(self, hostname):
    """Set the hostname of the container.

    Args:
      hostname: the hostname.
    """
    self._hostname = hostname

  def SetNetwork(self, network):
    """Set the network that the container connects to.

    Args:
      network: the network name.
    """
    self._network = network

  def AddEnv(self, key, value):
    """Add environment to inject into the docker container.

    Args:
      key: environement variable's key
      value: environement variable's value
    """
    self._env.append((key, value))

  def CopyEnv(self, key, alt_keys=None):
    """Copy an environment variable from the current environment if exists.

    Args:
      key: an environment variable name.
      alt_keys: alternative variable names to lookup if the key doesn't exist.
    Returns:
      a value if a variable exists. Otherwise None.
    """
    keys = [key] + (alt_keys or [])
    for k in keys:
      value = os.environ.get(k)
      if value is not None:
        self.AddEnv(key, value)
        return value
    return None

  def AddVolume(self, volume_name, dst):
    """Create a volume to mount to docker container.

    Args:
      volume_name: volume name
      dst: the path to mount inside docker container.
    """
    self._volumes.append((volume_name, dst))

  def AddTmpfs(self, path, size=_DEFAULT_TMPFS_SIZE_IN_BYTES, mode=None):
    """Mount a tmpfs in the container.

    The mode is the linux file mode, for example 750 is for owner can read,
    write and execute, group can read and execute but no write and other has
    no access.

    Args:
      path: the destination path in container.
      size: the size of the tmpfs size in bytes.
      mode: the linux file mode of the tmpfs.
    """
    self._tmpfss.append((path, size, mode))

  def AddBind(self, src, dst):
    """Mount file/dir on the local host to the docker container.

    Args:
      src: local file path
      dst: the path to mount inside docker container.
    """
    self._binds.append((src, dst))

  def AddPort(self, local_host_port, docker_port):
    """Map local port to docker port.

    Args:
      local_host_port: local port or local host:port.
      docker_port: the docker port that the local port map to.
    """
    self._ports.append((local_host_port, docker_port))

  def AddCapability(self, cap):
    """Grant a capability to the docker container.

    Args:
      cap: the capability name.
    """
    self._capabilities.append(cap)

  def AddDeviceNode(self, path):
    """Allow the docker container to access a device node.

    Args:
      path: the device node path.
    """
    self._device_nodes.append(path)

  def AddSysctl(self, variable, value):
    """Set namespaced kernel parameters.

    Args:
      variable: the name of the variable.
      value: the value of the variable.
    """
    self._sysctls.append((variable, value))

  def AddExtraArgs(self, args):
    """Add extra args to docker container.

    Args:
      args: a list of string
    """
    self._extra_args.extend(args)

  def AddFile(self, local_path, docker_path):
    """Copy a file to the docker container.

    Args:
      local_path: local file path
      docker_path: docker file path to copy to
    """
    self._files.append((local_path, docker_path))

  def Run(self, container_name):
    """Start a container with the docker images.

    Args:
      container_name: the container name to use when start the container.
    Returns:
      common.CommandResult
    """
    # Remove existing container if necessary
    self._docker_context.Run(['container', 'rm', container_name],
                             raise_on_failure=False)

    # Create new container
    args = [
        'create',
        '--name', container_name,
        '-it',
        '-v', '/dev/bus/usb:/dev/bus/usb',  # Mount USB devices
        '--device-cgroup-rule', 'c 189:* rwm',  # Grant access to USB devices
        '--cap-add', 'syslog',  # Enables host system logs (e.g. dmesg) access
        '--log-opt', 'max-size=200m', '--log-opt', 'max-file=5'  # Set log size
    ]
    if self._hostname:
      args.extend(['--hostname', self._hostname])
    if self._network:
      args.extend(['--network', self._network])
    for key, value in self._env:
      args.extend(['-e', '%s=%s' % (key, value)])
    for volume_name, dst in self._volumes:
      args.extend(['--mount', 'type=volume,src=%s,dst=%s' % (volume_name, dst)])
    for src, dst in self._binds:
      args.extend(['--mount', 'type=bind,src=%s,dst=%s' % (src, dst)])
    for path, size, mode in self._tmpfss:
      tmpfs_arg = 'type=tmpfs,dst=%s' % path
      if size:
        tmpfs_arg += ',tmpfs-size=%s' % size
      if mode:
        tmpfs_arg += ',tmpfs-mode=%s' % mode
      args.extend(['--mount', tmpfs_arg])
    for local_host_port, docker_port in self._ports:
      args.extend(['-p', '%s:%s' % (local_host_port, docker_port)])
    for cap in self._capabilities:
      args.extend(['--cap-add', cap])
    for path in self._device_nodes:
      args.extend(['--device', path])
    for sysctl in self._sysctls:
      args.extend(['--sysctl', '%s=%s' % sysctl])
    args.extend(self._extra_args)
    args.append(self._image_name)
    self._docker_context.Run(args)

    # Copy additional files
    for local_path, docker_path in self._files:
      self._docker_context.Run(['cp', '-L', local_path,
                                '%s:%s' % (container_name, docker_path)])

    # Start container
    return self._docker_context.Run(['start', container_name])

  def Exec(self, container_name, args):
    """Executes a command in a container.

    Args:
      container_name: a Docker container name.
      args: command line args.
    Returns:
      common.CommandResult
    """
    return self._docker_context.Run(
        ['exec', container_name, *args], raise_on_failure=False)

  def Stop(self, container_names, stop_timeout=None):
    """Stop the given containers.

    Args:
      container_names: a list of container_names to stop
      stop_timeout: seconds to wait for stop before killing it.
    Returns:
      the common.CommandResult
    """
    cmds = ['stop']
    if stop_timeout is not None:
      cmds.extend(['-t', stop_timeout])
    cmds.extend(container_names)
    return self._docker_context.Run(cmds, timeout=_DOCKER_STOP_CMD_TIMEOUT_SEC)

  def Kill(self, container_names, signal=None):
    """Send a signal to container with kill command.

    Args:
      container_names: a list of container_names to stop
      signal: the signal send to the container.
    Returns:
      the common.CommandResult
    """
    cmds = ['kill']
    if signal is not None:
      cmds.extend(['-s', signal])
    cmds.extend(container_names)
    return self._docker_context.Run(cmds, timeout=_DOCKER_KILL_CMD_TIMEOUT_SEC)

  def Wait(self, container_names, timeout=_DOCKER_WAIT_CMD_TIMEOUT_SEC):
    """Wait the containers to stop.

    Args:
      container_names: a list of container_names to stop
      timeout: int, max timeout to wait, in sec.
    Returns:
      the common.CommandResult
    """
    return self._docker_context.Run(
        ['container', 'wait'] + container_names, timeout=timeout)

  def Inspect(self, resource_name, output_format=None, raise_on_failure=False):
    """Inspect the given resource (image or container).

    Args:
      resource_name: the name of resource to inspect.
      output_format: --format value of inspect command.
      raise_on_failure: raise on failure or not.
    Returns:
      common.CommandResult
    """
    cmd = ['inspect', resource_name]
    if output_format:
      cmd.extend(['--format', output_format])
    return self._docker_context.Run(cmd, raise_on_failure=raise_on_failure)

  def DoesResourceExist(self, resource_name):
    """Return whether the resource (image, container, network, etc.) exists."""
    res = self.Inspect(
        resource_name,
        output_format='OK',
        raise_on_failure=False)
    if res.return_code != 0:
      if res.stderr and _NO_SUCH_OBJECT_ERROR in res.stderr.lower():
        return False
      raise DockerError(
          'Failed to inpect %s:\nstderr:%s\nstdout:%s.' % (
              resource_name, res.stderr, res.stdout))
    return True

  def GetEnv(self, image_id_or_name):
    """Get image's environment variables.

    Args:
      image_id_or_name: the image to inspect.

    Returns:
      A list of strings in the format of 'NAME=VALUE'.

    Raises:
      DockerError: failed to inspect the image.
    """
    res = self.Inspect(
        image_id_or_name,
        output_format=_IMAGE_ENV_FORMAT,
        raise_on_failure=False)
    if res.return_code != 0:
      raise DockerError('Failed to inpect %s:\nstderr: %s\nstdout: %s.' %
                        (image_id_or_name, res.stderr, res.stdout))
    return json.loads(res.stdout)

  def GetRemoteImageDigest(self, image_id_or_name):
    """Get image's remote image digest."""
    res = self.Inspect(
        image_id_or_name, output_format=_REMOTE_IMAGE_DIGEST_FORMAT,
        raise_on_failure=True)
    return res.stdout.strip()

  def GetImageIdForContainer(self, container_name):
    """Get container's image id."""
    res = self.Inspect(
        container_name, output_format=_IMAGE_ID_FORMAT,
        raise_on_failure=True)
    return res.stdout.strip()

  def GetProcessIdForContainer(self, container_name):
    """Get container's process id."""
    res = self.Inspect(
        container_name,
        output_format=_CONTAINER_PID_FORMAT,
        raise_on_failure=True)
    return res.stdout.strip()

  def CleanupUnusedImages(self):
    """Clean up unused docker images.

    Returns:
      An instance of common.CommandResult.
    """
    logging.info('Cleaning up unused docker images...')
    return self._docker_context.Run(
        ['image', 'prune', '-a', '-f', '--filter', 'until=240h'],
        raise_on_failure=False)

  def IsContainerRunning(self, container_name):
    """Check if container is running or not."""
    res = self.Inspect(container_name, output_format=_CONTAINER_STATUS_FORMAT)
    if res.return_code != 0:
      if res.stderr and _NO_SUCH_OBJECT_ERROR in res.stderr.lower():
        logger.debug('No container %s.', container_name)
        return False
      raise DockerError(
          'Failed to inpect %s:\nstderr:%s\nstdout:%s.' % (
              container_name, res.stderr, res.stdout))
    return res.stdout.strip() == _CONTAINER_RUNNING_STATUS

  def IsContainerDead(self, container_name):
    """Check if container is dead.

    The result from "docker inspect" could show container is running, but it
    is already dead in fact. This function helps to check whether the container
    is realy alive when it is shown as running.

    Dead means container is neither running nor removed.

    Args:
      container_name: text, the docker container name.

    Returns:
      A bool, True if the container is dead, otherwise False.
    """
    res = self._docker_context.Run(
        ['exec', container_name, 'echo', _DOCKER_LIVELINESS_CHECKING_MESSAGE],
        raise_on_failure=False,
        timeout=_DOCKER_LIVELINESS_CHECKING_TIMEOUT_SEC)
    # The return code will be 126 when container is dead.
    if res.return_code:
      logger.info(
          'Std-Out output when checking container liveliness: %s', res.stdout)
      return bool(_DOCKER_CONTAINER_NOT_ALIVE_PATTERN.match(res.stdout))
    return False

  def RemoveContainers(self, container_names, raise_on_failure=True):
    """Remove given containers.

    Args:
        container_names: a list of container names to remove.
        raise_on_failure: raise an exception if an operation fails.
    Returns:
      the common.CommandResult
    """
    return self._docker_context.Run(
        ['container', 'rm'] + container_names,
        raise_on_failure=raise_on_failure)

  def RemoveVolumes(self, volume_names, raise_on_failure=False):
    """Remove given volumes.

    Args:
        volume_names: a list of volume names to remove.
        raise_on_failure: raise an exception if an operation fails.
    Returns:
      the common.CommandResult
    """
    return self._docker_context.Run(
        ['volume', 'rm'] + volume_names, raise_on_failure=raise_on_failure)

  def Logs(self, container_name, raise_on_failure=False):
    """Get logs from container's PID 1.

    Args:
      container_name: text, the docker container name.
      raise_on_failure: raise error on failure or not.
    Returns:
      common.CommandResult
    """
    logger.debug('Get container %s logs.', container_name)
    # If log is set to verbose, the subprocess prints to stdout as well.
    # The res.stdout will also have the subprocess's stdout.
    res = self._docker_context.Run(
        ['logs', container_name], raise_on_failure=raise_on_failure)
    return res.stdout

  def Cat(self, container_name, file_name, raise_on_failure=False):
    """Get content of file in the container.

    Get file content in the container. Right now
    only support files in self._volumes

    Args:
      container_name: name of the container.
      file_name: the file's name to content from.
      raise_on_failure: raise error on failure or not.
    Returns:
      the content of the file.
    """
    logger.debug('Cat %s:%s.', container_name, file_name)
    if self.IsContainerRunning(container_name):
      res = self._docker_context.Run(
          ['exec', container_name, 'cat', file_name],
          raise_on_failure=raise_on_failure)
      return res.stdout
    # If the container is stopped, we need to create a temporary container.
    logger.debug('Container %s is stopped.', container_name)
    args = [
        'run',
        '--rm',
        '--entrypoint', 'cat']
    for volume_name, dst in self._volumes:
      args.extend(['--mount', 'type=volume,src=%s,dst=%s' % (volume_name, dst)])
    args.append(self._image_name)
    args.append(file_name)
    # If log is set to verbose, the subprocess prints to stdout as well.
    # The res.stdout will also have the subprocess's stdout.
    res = self._docker_context.Run(args, raise_on_failure=raise_on_failure)
    return res.stdout

  def GetBridgeNetworkInfo(self):
    """Get info on the Docker network.

    Inspects the network specified in `self._network`, or the default 'bridge'
    network if `self._network` is not set.

    Returns:
      a BridgeNetworkInfo object.

    Raises:
      DockerError: if a Docker command fails.
    """
    args = [
        'network',
        'inspect',
        self._network or 'bridge',
        '--format={{json .}}',
    ]
    res = self._docker_context.Run(args, raise_on_failure=False)
    if res.return_code:
      raise DockerError('Command "%s" failed: %s' % (args, res))
    return BridgeNetworkInfo(json.loads(res.stdout.strip()))
