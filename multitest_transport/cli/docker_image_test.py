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

"""Unit tests for DockerImageExecutor."""

from unittest import mock
from absl.testing import absltest
from multitest_transport.cli import command_util
from multitest_transport.cli import common
from multitest_transport.cli import docker_image

Error = docker_image.Error
DockerImageExecutor = docker_image.DockerImageExecutor


class DockerImageTest(absltest.TestCase):

  def setUp(self):
    super().setUp()
    self.mock_context = mock.create_autospec(
        command_util.DockerContext, instance=True
    )
    self.executor = DockerImageExecutor(self.mock_context)

  def testPullAndResolveImageRef(self):
    image_ref = "asia-docker.pkg.dev/ats-dev-418504/ats/ats:latest"
    expected_digest = (
        "asia-docker.pkg.dev/ats-dev-418504/ats/ats@sha256:7f9a2b3c4d5e6f"
    )

    self.mock_context.Run.side_effect = [
        common.CommandResult(0, "Pulling from ats...", ""),
        common.CommandResult(0, f"{expected_digest}\n", ""),
    ]

    result = self.executor.PullAndResolveImageRef(image_ref)

    self.assertEqual(result, expected_digest)
    self.assertEqual(self.mock_context.Run.call_count, 2)
    self.mock_context.Run.assert_any_call(
        ["pull", image_ref],
        raise_on_failure=False,
        timeout=600,
    )
    self.mock_context.Run.assert_any_call(
        ["inspect", "--format={{index .RepoDigests 0}}", image_ref],
        raise_on_failure=False,
        timeout=30,
    )

  def testPullAndResolveImageRef_fallbackToImageId(self):
    # A locally built image has no RepoDigests. The bare image ID is a valid
    # locally resolvable reference; prefixing it with the repository name
    # would produce an unresolvable repo@sha256:<id>.
    image_ref = "local-image:test"
    image_id = "sha256:1234567890abcdef"

    self.mock_context.Run.side_effect = [
        common.CommandResult(0, "Image is up to date", ""),
        common.CommandResult(0, "<no value>\n", ""),
        common.CommandResult(0, f"{image_id}\n", ""),
    ]

    result = self.executor.PullAndResolveImageRef(image_ref)

    self.assertEqual(result, image_id)
    self.assertEqual(self.mock_context.Run.call_count, 3)

  def testPullAndResolveImageRef_pullFailureRaisesError(self):
    image_ref = "invalid-registry.com/image:latest"

    self.mock_context.Run.return_value = common.CommandResult(
        1, "", "Error response from daemon: repository not found"
    )

    with self.assertRaisesRegex(Error, "repository not found"):
      self.executor.PullAndResolveImageRef(image_ref)

  def testPullAndResolveImageRef_emptyImageRaisesValueError(self):
    with self.assertRaises(ValueError):
      self.executor.PullAndResolveImageRef("")
    with self.assertRaises(ValueError):
      self.executor.PullAndResolveImageRef("   ")

  def testPullAndResolveImageRef_fallbackKeepsAlreadyPinnedRef(self):
    # The input is already an immutable reference, so it is returned as-is
    # rather than collapsed to the local image ID, and the .Id inspect is
    # skipped entirely.
    image_ref = "localhost:5000/my-org/mtt@sha256:abcd1234"
    self.mock_context.Run.side_effect = [
        common.CommandResult(0, "Status: Image is up to date", ""),
        common.CommandResult(0, "<no value>", ""),
    ]

    resolved = self.executor.PullAndResolveImageRef(image_ref)
    self.assertEqual(resolved, image_ref)
    self.assertEqual(self.mock_context.Run.call_count, 2)

  def testPullAndResolveImageRef_unresolvableTagRaisesError(self):
    # Both inspects fail (e.g. daemon flakiness or the 30s timeout) on a
    # mutable tag. Returning the tag would silently stage an unpinned release.
    image_ref = "gcr.io/proj/mtt:latest"
    self.mock_context.Run.side_effect = [
        common.CommandResult(0, "Status: Downloaded newer image", ""),
        common.CommandResult(None, None, "timed out after 30 seconds"),
        common.CommandResult(None, None, "timed out after 30 seconds"),
    ]

    with self.assertRaisesRegex(Error, "Failed to resolve an immutable"):
      self.executor.PullAndResolveImageRef(image_ref)

  def testPullAndResolveImageRef_emptyImageIdRaisesError(self):
    # Inspect succeeds but reports nothing usable; same hazard as failing.
    image_ref = "gcr.io/proj/mtt:latest"
    self.mock_context.Run.side_effect = [
        common.CommandResult(0, "Status: Image is up to date", ""),
        common.CommandResult(0, "<no value>\n", ""),
        common.CommandResult(0, "  \n", ""),
    ]

    with self.assertRaisesRegex(Error, "Failed to resolve an immutable"):
      self.executor.PullAndResolveImageRef(image_ref)

  def testGetContainerStatus_notRunning(self):
    self.mock_context.Run.return_value = common.CommandResult(
        0, "false:none\n", ""
    )
    status = self.executor.GetContainerStatus("mtt")
    self.assertEqual(status, docker_image.ContainerStatus.NOT_RUNNING)
    self.assertFalse(status.is_running)

  def testGetContainerStatus_errorIsNotRunning(self):
    self.mock_context.Run.return_value = common.CommandResult(
        1, "", "no such container"
    )
    status = self.executor.GetContainerStatus("mtt")
    self.assertEqual(status, docker_image.ContainerStatus.NOT_RUNNING)
    self.assertFalse(status.is_running)

  def testGetContainerStatus_runningNoHealthcheckIsHealthy(self):
    self.mock_context.Run.return_value = common.CommandResult(
        0, "true:none\n", ""
    )
    status = self.executor.GetContainerStatus("mtt")
    self.assertEqual(status, docker_image.ContainerStatus.HEALTHY)
    self.assertTrue(status.is_running)

  def testGetContainerStatus_runningHealthy(self):
    self.mock_context.Run.return_value = common.CommandResult(
        0, "true:healthy\n", ""
    )
    status = self.executor.GetContainerStatus("mtt")
    self.assertEqual(status, docker_image.ContainerStatus.HEALTHY)
    self.assertTrue(status.is_running)

  def testGetContainerStatus_runningUnhealthy(self):
    self.mock_context.Run.return_value = common.CommandResult(
        0, "true:unhealthy\n", ""
    )
    status = self.executor.GetContainerStatus("mtt")
    self.assertEqual(status, docker_image.ContainerStatus.UNHEALTHY)
    self.assertTrue(status.is_running)

  def testDoesContainerMatchImage_exactConfigImageMatch(self):
    self.mock_context.Run.return_value = common.CommandResult(
        0, "gcr.io/mtt/image@sha256:manifest1234\n", ""
    )
    self.assertTrue(
        self.executor.DoesContainerMatchImage(
            "mtt", "gcr.io/mtt/image@sha256:manifest1234"
        )
    )

  def testDoesContainerMatchImage_tagMatchesRepoDigestViaImageId(self):
    self.mock_context.Run.side_effect = [
        # GetContainerImage ({{.Config.Image}}) -> tag
        common.CommandResult(0, "gcr.io/mtt/image:prod\n", ""),
        # Container {{.Image}} -> config hash
        common.CommandResult(0, "sha256:config_hash_a\n", ""),
        # Expected image {{.Id}} -> same config hash
        common.CommandResult(0, "sha256:config_hash_a\n", ""),
    ]
    self.assertTrue(
        self.executor.DoesContainerMatchImage(
            "mtt", "gcr.io/mtt/image@sha256:manifest_hash_a"
        )
    )

  def testDoesContainerMatchImage_untaggedContainerDifferentDigestReturnsFalse(
      self,
  ):
    self.mock_context.Run.side_effect = [
        # GetContainerImage ({{.Config.Image}}) -> untagged repo name
        common.CommandResult(0, "gcr.io/mtt/image\n", ""),
        # Container {{.Image}} -> old config hash
        common.CommandResult(0, "sha256:config_hash_old\n", ""),
        # Expected image {{.Id}} -> new config hash
        common.CommandResult(0, "sha256:config_hash_new\n", ""),
    ]
    self.assertFalse(
        self.executor.DoesContainerMatchImage(
            "mtt", "gcr.io/mtt/image@sha256:manifest_hash_new"
        )
    )

  @mock.patch.object(
      docker_image.google_auth_util, "CreateCredentialFromServiceAccount"
  )
  def testPullAndResolveImageRef_withServiceAccountLogsInBeforePull(
      self, mock_create_cred
  ):
    image_ref = "asia-docker.pkg.dev/ats-dev-418504/ats-dev/ats:partner_latest"
    expected_digest = (
        "asia-docker.pkg.dev/ats-dev-418504/ats-dev/ats@sha256:abcdef123456"
    )
    mock_cred = mock.MagicMock()
    mock_cred.token = "sa-oauth-token-123"
    mock_create_cred.return_value = mock_cred

    self.mock_context.Run.side_effect = [
        common.CommandResult(0, "Login Succeeded", ""),
        common.CommandResult(0, "Pulling from ats...", ""),
        common.CommandResult(0, f"{expected_digest}\n", ""),
    ]

    result = self.executor.PullAndResolveImageRef(
        image_ref,
        service_account_json_key_path="/etc/mtt/secrets/sa-key.json",
    )

    self.assertEqual(result, expected_digest)
    mock_create_cred.assert_called_once_with(
        service_account_json_key_path="/etc/mtt/secrets/sa-key.json",
        scopes=[
            docker_image.google_auth_util.GCS_READ_SCOPE,
            docker_image.google_auth_util.AUTH_SCOPE,
        ],
    )
    self.assertEqual(
        self.mock_context.Run.call_args_list[0],
        mock.call(
            [
                "login",
                "-u",
                "oauth2accesstoken",
                "-p",
                "sa-oauth-token-123",
                "https://asia-docker.pkg.dev",
            ],
            raise_on_failure=False,
            timeout=30,
        ),
    )

  @mock.patch.object(
      docker_image.google_auth_util, "CreateCredentialFromServiceAccount"
  )
  def testLoginWithServiceAccount_skipsBareAndDockerHubNames(
      self, mock_create_cred
  ):
    self.executor.LoginWithServiceAccount(
        "/etc/mtt/secrets/sa-key.json", "mtt:latest"
    )
    self.executor.LoginWithServiceAccount(
        "/etc/mtt/secrets/sa-key.json",
        "otel/opentelemetry-collector-contrib:0.157.0",
    )
    mock_create_cred.assert_not_called()
    self.mock_context.Run.assert_not_called()

  @mock.patch.object(
      docker_image.google_auth_util, "CreateCredentialFromServiceAccount"
  )
  def testLoginWithServiceAccount_loginFailureRaisesError(
      self, mock_create_cred
  ):
    mock_cred = mock.MagicMock()
    mock_cred.token = "bad-token"
    mock_create_cred.return_value = mock_cred
    self.mock_context.Run.return_value = common.CommandResult(
        1, "", "unauthorized: authentication required"
    )

    with self.assertRaisesRegex(Error, "Failed to authenticate Docker"):
      self.executor.LoginWithServiceAccount(
          "/etc/mtt/secrets/sa-key.json",
          "asia-docker.pkg.dev/ats-dev-418504/ats-dev/ats:partner_latest",
      )

  @mock.patch.object(
      docker_image.google_auth_util, "CreateCredentialFromServiceAccount"
  )
  def testLoginWithServiceAccount_redactsTokenInTimeoutError(
      self, mock_create_cred
  ):
    mock_cred = mock.MagicMock()
    mock_cred.token = "secret-sa-oauth-token-999"
    mock_create_cred.return_value = mock_cred
    self.mock_context.Run.return_value = common.CommandResult(
        None,
        None,
        "Command '['docker', 'login', '-u', 'oauth2accesstoken', '-p',"
        " 'secret-sa-oauth-token-999', 'https://asia-docker.pkg.dev']' timed"
        " out after 30 seconds",
    )

    with self.assertRaises(Error) as ctx:
      self.executor.LoginWithServiceAccount(
          "/etc/mtt/secrets/sa-key.json",
          "asia-docker.pkg.dev/ats-dev-418504/ats-dev/ats:partner_latest",
      )
    self.assertNotIn("secret-sa-oauth-token-999", str(ctx.exception))
    self.assertIn("<redacted>", str(ctx.exception))

  @mock.patch.object(
      docker_image.google_auth_util, "CreateCredentialFromServiceAccount"
  )
  def testLoginWithServiceAccount_emptyTokenRaisesError(self, mock_create_cred):
    mock_cred = mock.MagicMock()
    mock_cred.token = ""
    mock_create_cred.return_value = mock_cred

    with self.assertRaisesRegex(Error, "empty OAuth token"):
      self.executor.LoginWithServiceAccount(
          "/etc/mtt/secrets/sa-key.json",
          "asia-docker.pkg.dev/ats-dev-418504/ats-dev/ats:partner_latest",
      )


if __name__ == "__main__":
  absltest.main()
