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

"""Docker image pull and digest resolution for MTT Node."""

import enum
import logging
from typing import Optional
from multitest_transport.cli import command_util
from multitest_transport.cli import google_auth_util

logger = logging.getLogger(__name__)

_REPO_DIGEST_FORMAT = "{{index .RepoDigests 0}}"
_IMAGE_ID_FORMAT = "{{.Id}}"
_CONTAINER_STATUS_FORMAT = (
    "{{.State.Running}}:{{if .State.Health}}{{.State.Health.Status}}"
    "{{else}}none{{end}}"
)


class Error(Exception):
  """Raised when a docker image operation fails."""


def _ExtractRegistryServer(image_or_repo: str) -> Optional[str]:
  """Returns the `https://<registry>` URL for a registry-qualified reference.

  Returns None for bare tags (`mtt:latest`) and Docker Hub namespaces whose
  first path segment is not a hostname (`otel/opentelemetry-collector-contrib`).

  Args:
    image_or_repo: Full image reference or repository prefix.
  """
  ref = image_or_repo.strip()
  for prefix in ("https://", "http://"):
    if ref.startswith(prefix):
      ref = ref[len(prefix) :]
  if "/" not in ref:
    return None
  host = ref.split("/", 1)[0]
  if "." in host or ":" in host or host == "localhost":
    return f"https://{host}"
  return None


class ContainerStatus(enum.Enum):
  """Data-plane running and health status of a Docker container."""

  NOT_RUNNING = "not_running"
  UNHEALTHY = "unhealthy"
  HEALTHY = "healthy"

  @property
  def is_running(self) -> bool:
    return self != ContainerStatus.NOT_RUNNING


class DockerImageExecutor:
  """Executes Docker image pulls and inspects immutable RepoDigests."""

  def __init__(
      self,
      docker_context: Optional[command_util.DockerContext] = None,
  ):
    self._docker_context = docker_context or command_util.DockerContext(
        command_util.CommandContext(), login=False
    )

  def LoginWithServiceAccount(
      self,
      service_account_json_key_path: str,
      image_or_repo: str,
  ) -> None:
    """Authenticates Docker to the registry in `image_or_repo` using a GCP SA key.

    Args:
      service_account_json_key_path: Path to the GCP service account JSON key.
      image_or_repo: Image reference or repository prefix whose registry host
        should be logged into.

    Raises:
      Error: If minting the OAuth token or running `docker login` fails.
    """
    server = _ExtractRegistryServer(image_or_repo)
    if not server:
      return
    try:
      credential = google_auth_util.CreateCredentialFromServiceAccount(
          service_account_json_key_path=service_account_json_key_path,
          scopes=[
              google_auth_util.GCS_READ_SCOPE,
              google_auth_util.AUTH_SCOPE,
          ],
      )
    except Exception as e:  
      raise Error(
          "Failed to mint OAuth token from service account key"
          f" {service_account_json_key_path!r} for {server}: {e}"
      ) from e

    if not credential.token:
      raise Error(
          "Service account credential produced an empty OAuth token for"
          f" {server} from {service_account_json_key_path!r}"
      )

    logger.info("Logging into Docker registry %s with service account", server)
    login_res = self._docker_context.Run(
        ["login", "-u", "oauth2accesstoken", "-p", credential.token, server],
        raise_on_failure=False,
        timeout=30,
    )
    if login_res.return_code != 0:
      err_msg = (login_res.stderr or login_res.stdout or "").strip()
      err_msg = err_msg.replace(credential.token, "<redacted>")
      raise Error(
          f"Failed to authenticate Docker to {server} with service account key"
          f" {service_account_json_key_path!r}: {err_msg}"
      )

  def PullAndResolveImageRef(
      self,
      image_ref: str,
      timeout_sec: int = 600,
      service_account_json_key_path: Optional[str] = None,
  ) -> str:
    """Pulls a Docker image and resolves it to a complete, immutable reference.

    Args:
      image_ref: Docker image reference (repo/image:tag or repo/image@sha256:).
      timeout_sec: Timeout for pull in seconds.
      service_account_json_key_path: Optional GCP service account JSON key path
        used to authenticate to the target registry before pulling.

    Returns:
      A complete, immutable image reference suitable for passing verbatim to
      `mtt --image_name`. Either a registry digest reference
      (`repo/image@sha256:7f9a2b...`), the input itself when it is already
      digest-pinned, or, for an image with no RepoDigests such as a locally
      built one, the bare local image ID (`sha256:...`). Never a bare digest
      that a caller must recombine with a repository name, and never a mutable
      tag.

    Raises:
      ValueError: If image_ref is empty.
      Error: If docker login/pull fails, or if no immutable reference can be
        resolved for a tagged image. Failing is deliberate: returning the tag
        would record an unpinned reference in pinned_mtt_flags.yaml and
        silently defeat version pinning.
    """
    if not image_ref or not image_ref.strip():
      raise ValueError("Image reference cannot be empty.")

    image_ref = image_ref.strip()

    if service_account_json_key_path:
      self.LoginWithServiceAccount(service_account_json_key_path, image_ref)

    logger.info("Pulling docker image: %s", image_ref)
    pull_res = self._docker_context.Run(
        ["pull", image_ref],
        raise_on_failure=False,
        timeout=timeout_sec,
    )
    if pull_res.return_code != 0:
      err_msg = pull_res.stderr or pull_res.stdout
      raise Error(f"Failed to pull docker image {image_ref!r}: {err_msg}")

    logger.info("Inspecting docker image digest for: %s", image_ref)
    inspect_res = self._docker_context.Run(
        ["inspect", f"--format={_REPO_DIGEST_FORMAT}", image_ref],
        raise_on_failure=False,
        timeout=30,
    )
    if inspect_res.return_code == 0:
      digest = inspect_res.stdout.strip()
      if digest and digest != "<no value>":
        logger.info("Resolved immutable digest: %s", digest)
        return digest

    # An input that is already digest-pinned is its own immutable reference.
    # Prefer it over the local image ID so the registry form is preserved.
    if "@sha256:" in image_ref:
      return image_ref

    # Fallback to .Id for images with no RepoDigests (e.g. locally built).
    # The bare image ID is itself a valid immutable reference that `docker
    # inspect` and `docker run` resolve locally. It must NOT be combined with
    # the repository name: `repo@sha256:<id>` resolves against RepoDigests,
    # which is exactly what is empty here, so that form is unresolvable.
    id_res = self._docker_context.Run(
        ["inspect", f"--format={_IMAGE_ID_FORMAT}", image_ref],
        raise_on_failure=False,
        timeout=30,
    )
    if id_res.return_code == 0:
      image_id = id_res.stdout.strip()
      if image_id:
        logger.info("Resolved local image ID: %s", image_id)
        return image_id

    # Neither inspection yielded a reference and the input is a mutable tag.
    # Returning it would write an unpinned reference into
    # pinned_mtt_flags.yaml, defeating the version pinning the node exists to
    # enforce, and would do so silently. Fail instead.
    raise Error(
        f"Failed to resolve an immutable reference for {image_ref!r}: the"
        " image pulled but neither its RepoDigests nor its image ID could be"
        " inspected. Refusing to stage a release pinned to a mutable tag."
    )

  def GetContainerStatus(
      self, container_name: str = "mtt"
  ) -> ContainerStatus:
    """Returns the running and health status of the specified container."""
    res = self._docker_context.Run(
        ["inspect", f"--format={_CONTAINER_STATUS_FORMAT}", container_name],
        raise_on_failure=False,
        timeout=15,
    )
    if res.return_code != 0:
      return ContainerStatus.NOT_RUNNING
    running_str, _, health_str = res.stdout.strip().lower().partition(":")
    if running_str != "true":
      return ContainerStatus.NOT_RUNNING
    if health_str == "unhealthy":
      return ContainerStatus.UNHEALTHY
    # TODO: Once the mtt container image defines a HEALTHCHECK,
    # require health_str == "healthy" instead of treating "none" as HEALTHY.
    return ContainerStatus.HEALTHY

  def GetContainerImage(self, container_name: str = "mtt") -> Optional[str]:
    """Returns the image name/ref of the container, or None if not found."""
    res = self._docker_context.Run(
        ["inspect", "--format={{.Config.Image}}", container_name],
        raise_on_failure=False,
        timeout=15,
    )
    if res.return_code == 0 and res.stdout.strip():
      return res.stdout.strip()
    return None

  def DoesContainerMatchImage(
      self, container_name: str, expected_image: str
  ) -> bool:
    """Checks if a container's image or image ID matches the expected image/digest."""
    if not expected_image:
      return False
    # Fast path: exact Config.Image match (e.g. container started with the
    # exact pinned image_ref).
    running_image = self.GetContainerImage(container_name)
    if running_image == expected_image:
      return True

    # Compare the container's Image ID ({{.Image}}) against the expected
    # image's ID ({{.Id}}). Docker's RepoDigest (@sha256:<manifest_hash>)
    # differs from Image ID (sha256:<config_hash>), so both sides must be
    # resolved to their Image ID.
    container_res = self._docker_context.Run(
        ["inspect", "--format={{.Image}}", container_name],
        raise_on_failure=False,
        timeout=15,
    )
    if container_res.return_code != 0 or not container_res.stdout.strip():
      return False
    container_image_id = container_res.stdout.strip()
    if container_image_id == expected_image:
      return True

    expected_res = self._docker_context.Run(
        ["inspect", "--format={{.Id}}", expected_image],
        raise_on_failure=False,
        timeout=15,
    )
    if expected_res.return_code != 0 or not expected_res.stdout.strip():
      return False
    return container_image_id == expected_res.stdout.strip()
