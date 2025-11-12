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

"""Integration tests for MTT CLI."""
import logging
import subprocess

from absl import flags
from absl.testing import absltest
import six

FLAGS = flags.FLAGS
flags.DEFINE_string('mtt_path', None, 'Path of MTT CLI binary.')
flags.mark_flag_as_required('mtt_path')
flags.DEFINE_string('docker_image', None, 'MTT docker image to use.')
flags.mark_flag_as_required('docker_image')
flags.DEFINE_string('mtt_lab_path', None, 'Path of MTT Lab CLI binary.')

RUNNING = 'running'
PROD_DOCKER_IMAGE = 'gcr.io/android-mtt/mtt:prod'


class CommandError(Exception):
  """Exception when fail to run command."""
  pass


def _RunCmd(args, stderr=subprocess.PIPE, stdout=subprocess.PIPE):
  """Run command."""
  logging.info('Running "%s"', ' '.join(args))
  proc = subprocess.Popen(args, stderr=stderr, stdout=stdout)
  outs, errs = proc.communicate()
  logging.info(
      'stdout: %s\n stderr: %s', outs.decode('utf-8'), errs.decode('utf-8'))
  if proc.returncode != 0:
    raise CommandError(six.ensure_text(errs))
  return outs.decode(), errs.decode()


class CliIntegrationTest(absltest.TestCase):
  """Mtt cli integration tests."""

  def setUp(self):
    super(CliIntegrationTest, self).setUp()
    self._Stop()

  def tearDown(self):
    self._Stop()
    super(CliIntegrationTest, self).tearDown()

  def _Start(self, image=None, args=None):
    """Start MTT."""
    cmd = [
        FLAGS.mtt_path,
        '--no_check_update',
        '-v',
        'start',
        '--use_host_network',
        '--image_name',
        image or FLAGS.docker_image,
    ]
    _RunCmd(cmd + (args or []))

  def _Stop(self):
    """Stop MTT if it is 'running'."""
    _RunCmd([FLAGS.mtt_path, '--no_check_update', '-v', 'stop'])

  def _Update(self, image=None, args=None):
    """Update MTT."""
    cmd = [
        FLAGS.mtt_path,
        '--no_check_update',
        '-v',
        'update',
        '--use_host_network',
        '--image_name',
        image or FLAGS.docker_image,
    ]
    _RunCmd(cmd + (args or []))

  def _Inspect(self, args):
    """Inspect the MTT docker container."""
    outs, _ = _RunCmd(['docker', 'inspect', 'mtt'] + args)
    return outs.strip()

  def _GetContainerId(self):
    return self._Inspect(['--format={{.Id}}'])

  def _GetStatus(self):
    return self._Inspect(['--format={{.State.Status}}'])

  def _GetEntryPoint(self):
    return self._Inspect(['--format={{.Path}}'])

  def testVersion(self):
    cmd = [FLAGS.mtt_path, '--no_check_update', 'version']
    outs, _ = _RunCmd(cmd)
    six.assertRegex(self, outs, r'Version: .*')

  def testStart(self):
    self._Start()
    self.assertEqual(RUNNING, self._GetStatus())

  def testStartWithControlServerUrl(self):
    self._Start(args=[
        '--control_server_url=http://localhost:8000'
        ])
    self.assertEqual(RUNNING, self._GetStatus())

  def testStop(self):
    self._Start()
    self.assertEqual(RUNNING, self._GetStatus())
    self._Stop()
    with six.assertRaisesRegex(self, CommandError, r'(?i)No such object: mtt'):
      self._GetStatus()

  def testUpdate(self):
    cmd = ['docker', 'run', '-d', '--entrypoint', 'yes',
           '--name', 'mtt', 'ubuntu']
    _RunCmd(cmd)
    self.assertEqual(RUNNING, self._GetStatus())
    self.assertEqual('yes', self._GetEntryPoint())
    container_id = self._GetContainerId()
    # Update container
    self._Update(image=PROD_DOCKER_IMAGE)
    self.assertEqual(RUNNING, self._GetStatus())
    self.assertNotEqual('yes', self._GetEntryPoint())
    self.assertNotEqual(container_id, self._GetContainerId())

  def testUpdate_sameImage(self):
    self._Start(image=PROD_DOCKER_IMAGE)
    self.assertEqual(RUNNING, self._GetStatus())
    container_id = self._GetContainerId()
    # Update skipped if already running the same version
    self._Update(image=PROD_DOCKER_IMAGE)
    self.assertEqual(RUNNING, self._GetStatus())
    self.assertEqual(container_id, self._GetContainerId())

  def testVersion_labCli(self):
    if not FLAGS.mtt_lab_path:
      logging.debug('No mtt lab cli path setup.')
      return
    cmd = [FLAGS.mtt_lab_path, '--no_check_update', 'version']
    outs, _ = _RunCmd(cmd)
    six.assertRegex(self, outs, r'Version: .*')


if __name__ == '__main__':
  logging.basicConfig(level=logging.DEBUG)
  absltest.main()
