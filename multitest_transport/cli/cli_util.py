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

"""Utils for cli."""
import argparse
import getpass
import logging
import logging.handlers
import os
import socket
from typing import Callable
import zipfile

import requests
import six


from google.cloud import logging as gcloud_logging
from multitest_transport.cli import command_util
from multitest_transport.cli import gcs_file_util
from multitest_transport.cli import google_auth_util
from multitest_transport.cli import version

logger = logging.getLogger(__name__)
_UNKNOWN = 'unknown'
_VERSION_FILE = 'VERSION'
_DEFAULT_LOCAL_LOG_PATH_FORMAT = '/tmp/%s/mtt_cli.log'
_LOG_FORMAT = '%(asctime)s|%(levelname)s|%(module)s:%(lineno)s|%(message)s'
_SIMPLE_LOG_FORMAT = '%(levelname)s|%(message)s'
_STACKDRIVER_LOG_FORMAT = '%(module)s:%(lineno)s|%(message)s'
_LOG_MAX_BYTES = 50 * 10 ** 6  # 50MB
_LOG_BACKUPS = 5
_PACKAGE_LOGGER_NAME = 'multitest_transport.cli'
_CLI_UPDATE_URL_TEMPLATE = (
    'https://storage.googleapis.com/android-mtt.appspot.com/%s/%s')
_CLI_DOWNLOAD_CHUNK_SIZE_IN_BYTES = 1024 * 1024
_MTT_PROJECT = 'android-mtt'
_STACKDRIVER_CLOUD_PROJECT = 'tradefed-satellite-lab'
_GCLOUD_LOGGING_WRITE_SCOPE = 'https://www.googleapis.com/auth/logging.write'
OUTPUT_RED = '\033[0;31m'
OUTPUT_NOCOLOR = '\033[0m'


def PrintVersion():
  """Print the version of MTT CLI."""
  print('Version: %s' % GetVersion()[0])


def GetVersion():
  """Get the version and build environment of MTT CLI."""
  return version.VERSION, version.BUILD_ENVIRONMENT


def CreateLoggingArgParser():
  """Create argparser for logging."""
  parser = argparse.ArgumentParser(add_help=False)
  parser.add_argument(
      '-v', dest='verbose', action='store_true',
      help='Log logs from multitest_transport.cli package at DEBUG level.')
  parser.add_argument(
      '-vv', dest='very_verbose', action='store_true',
      help='Log all logs from all package at DEBUG level.')
  default_log_file = _DEFAULT_LOCAL_LOG_PATH_FORMAT % getpass.getuser()
  parser.add_argument(
      '--log_file', dest='log_file', type=str, default=default_log_file,
      help='Path to log file.')
  parser.add_argument(
      '--cli_stackdriver_logging_key_path',
      dest='cli_stackdriver_logging_key_path',
      type=str,
      help='Path to service account key file to write cloud logging.')
  return parser


def CreateLogger(args, service_account_key_path=None):
  """Create logger.

  All sub package should use logger.getLogger(__name__) to get module logger,
  instead of using logging directly.

  Args:
    args: parsed args for logging.
    service_account_key_path: service account key path to use.
  Returns:
    a logging.Logger
  """
  if args.very_verbose:
    new_logger = logging.getLogger()
  else:
    new_logger = logging.getLogger(_PACKAGE_LOGGER_NAME)
    # Avoid to logging through root.
    if new_logger.root:
      for handler in new_logger.root.handlers[:] or []:
        new_logger.root.removeHandler(handler)
      new_logger.root.addHandler(logging.NullHandler())
  # Remove existing handler, we will add customized handlers.
  for handler in new_logger.handlers[:] or []:
    new_logger.removeHandler(handler)

  logger_level = (logging.DEBUG if args.verbose or args.very_verbose
                  else logging.INFO)
  new_logger.setLevel(logger_level)
  log_format = (_LOG_FORMAT if args.verbose or args.very_verbose
                else _SIMPLE_LOG_FORMAT)

  if args.log_file:
    log_dir = os.path.dirname(args.log_file)
    os.makedirs(log_dir, exist_ok=True)
    handler = logging.handlers.RotatingFileHandler(
        filename=args.log_file,
        maxBytes=_LOG_MAX_BYTES,
        backupCount=_LOG_BACKUPS)
    log_formatter = logging.Formatter(log_format)
    handler.setFormatter(log_formatter)
    new_logger.addHandler(handler)

  service_account_key_path = (service_account_key_path or
                              args.cli_stackdriver_logging_key_path)
  if service_account_key_path:
    cloud_logging_client = gcloud_logging.Client(
        project=_STACKDRIVER_CLOUD_PROJECT,
        credentials=google_auth_util.CreateCredentialFromServiceAccount(
            service_account_key_path,
            scopes=[_GCLOUD_LOGGING_WRITE_SCOPE]))
    handler = cloud_logging_client.get_default_handler()
    cloud_log_format = socket.getfqdn() + '|' + _STACKDRIVER_LOG_FORMAT
    cloud_log_formatter = logging.Formatter(cloud_log_format)
    handler.setFormatter(cloud_log_formatter)
    new_logger.addHandler(handler)

  handler = logging.StreamHandler()
  log_formatter = logging.Formatter(log_format)
  handler.setFormatter(log_formatter)
  new_logger.addHandler(handler)

  return new_logger


def CreateMultiHostCommandArgParser():
  """Create argparser for executing on multiple hosts."""
  parser = argparse.ArgumentParser(add_help=False)
  parser.add_argument(
      '--parallel',
      dest='parallel',
      default=False,
      const=True,
      nargs='?',
      type=int)
  parser.add_argument(
      '--exit_on_error', action='store_true')
  return parser


def CreateSSHArgParser():
  """Create argparser for ssh to remote host."""
  parser = argparse.ArgumentParser(add_help=False)
  parser.add_argument(
      '--ssh_key', help='Use ssh key file.')
  parser.add_argument(
      '-p', '--ask_login_password', default=False,
      dest='ask_login_password',
      action='store_true', help='Ask password to ssh to the host.')
  parser.add_argument(
      '--ask_sudo_password', default=False,
      action='store_true', dest='ask_sudo_password',
      help='Ask sudo password on the host.')
  parser.add_argument(
      '--sudo_user', dest='sudo_user',
      help='Sudo user to use on the host.')
  parser.add_argument(
      '--use_native_ssh', default=True,
      action='store_true', dest='use_native_ssh',
      help='Use native ssh instead of fabric.')
  parser.add_argument(
      '--no_use_native_ssh', default=False,
      action='store_true', dest='no_use_native_ssh',
      help='Use fabric instead of native ssh.')
  parser.add_argument(
      '--ssh_arg', help='ssh arg passed to native ssh and rsync.')
  return parser


def CreateCliUpdateArgParser():
  """Create argparser for cli update."""
  parser = argparse.ArgumentParser(add_help=False)
  parser.add_argument(
      '--cli_update_url', type=str,
      help='Remote url to download the latest version command line.')
  parser.add_argument(
      '--no_check_update', action='store_true',
      help='Enable command line auto update or not.')
  return parser


def CheckAndUpdateTool(local_path, cli_update_url=None):
  """Check the remote version, if it's different, update the local CLI."""
  local_filename = os.path.basename(local_path)
  if not zipfile.is_zipfile(local_path):
    return None
  if not cli_update_url or not cli_update_url.strip():
    _, build_environment = GetVersion()
    if build_environment == 'dev':
      logger.debug('CLI from dev and no "cli_update_url" set, not update CLI.')
      return None
    cli_update_url = _CLI_UPDATE_URL_TEMPLATE % (
        build_environment, local_filename)
    logger.debug('Command auto update enabled, '
                 'but there is no cli_update_url set. '
                 'Using the default: %s.', cli_update_url)
  cli_update_url = cli_update_url.strip()
  remote_filename = os.path.basename(cli_update_url)
  if local_filename != remote_filename:
    logger.debug(
        '%s is not %s, skip updating.', local_filename, remote_filename)
    return None
  if not os.access(os.path.dirname(local_path), os.W_OK):
    logger.warning('No write access to %s, skip updating.',
                   os.path.dirname(local_path))
    return None

  if cli_update_url.startswith('gs://'):
    return _DownloadToolFromGCS(cli_update_url, local_path)
  return _DownloadToolFromHttp(cli_update_url, local_path)


def _DownloadToolFromHttp(url, local_path):
  """Update local cli to remote cli with http."""
  try:
    r = requests.head(url)
  except requests.ConnectionError as e:
    logger.warning('Can not access %s, skip updating: %s',
                   url, str(e))
    return None
  # x-goog-hash is a head for GCS links which includes md5 hash.
  hashes = r.headers.get('x-goog-hash')
  if not hashes or 'md5=' not in hashes:
    logger.warning(
        'No md5 hash from %s, skip updating.', url)
    return None
  remote_md5hash = None
  for hash_str in hashes.split(','):
    hash_str = hash_str.strip()
    hash_type, hash_value = hash_str.split('=', 1)
    if hash_type == 'md5':
      remote_md5hash = six.ensure_text(hash_value)
  local_md5hash = gcs_file_util.CalculateMd5Hash(local_path)
  if remote_md5hash == local_md5hash:
    logger.debug('Local is the same as remote, skip updating.')
    return None
  logger.info(
      'There is a newer version %s on %s, updating.',
      os.path.basename(local_path), url)

  def _DownloadFromHttp(local_path: str) -> None:
    r = requests.get(url, stream=True)
    _WriteResponseToFile(r, local_path)

  return _UpdateLocalFile(local_path, _DownloadFromHttp)


def _UpdateLocalFile(
    local_path: str, write_new_file: Callable[[str], None]
) -> str:
  """Update local file with contents from write_new_file function.

  The updated permission is the or operation of the original permission and
  0o770. The owner and group are preserved.

  Args:
    local_path: The local path of the file to update. The path should not be a
      symlink.
    write_new_file: A function that writes the new file contents to the
      specified local path.

  Returns:
    The local path of the updated file.
  """
  # The local_path is always the final binary path, not symlink, so we can use
  # os.stat to get the original permission and owner of the file.
  original_st = os.stat(local_path)
  os.rename(
      local_path,
      gcs_file_util.CreateBackupFilePath(local_path))
  write_new_file(local_path)
  # Restore the original permission and owner of the file.
  os.chmod(local_path, original_st.st_mode | 0o770)
  os.chown(local_path, original_st.st_uid, original_st.st_gid)
  return local_path


def _WriteResponseToFile(response, local_path):
  """Write http response to file, used for test."""
  with open(local_path, 'wb') as fd:
    for chunk in response.iter_content(
        chunk_size=_CLI_DOWNLOAD_CHUNK_SIZE_IN_BYTES):
      fd.write(chunk)


def _DownloadToolFromGCS(gcs_url, local_path):
  """Update local cli to remote cli with gcs."""
  try:
    cred = google_auth_util.GetGCloudCredential(command_util.CommandContext())
    gcs_client = gcs_file_util.CreateGCSClient(_MTT_PROJECT, cred)
    blob = gcs_file_util.GetGCSBlob(gcs_client, gcs_url)
  except gcs_file_util.GCSError as e:
    logger.warning(e)
    return None
  local_md5hash = gcs_file_util.CalculateMd5Hash(local_path)
  if six.ensure_text(blob.md5_hash) == local_md5hash:
    logger.debug('Local is the same as remote, skip updating.')
    return None
  logger.info(
      'There is a newer version %s on %s, updating.',
      os.path.basename(local_path), gcs_url)

  def _DownloadFromGCS(local_path: str):
    blob.download_to_filename(local_path)

  return _UpdateLocalFile(local_path, _DownloadFromGCS)
