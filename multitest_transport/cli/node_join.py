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

"""Interactive onboarding join workflow for GCP-managed MTT Worker nodes."""

import hashlib
import json
import logging
import os
import socket
import sys
from typing import Any, Callable, Optional, Sequence
from multitest_transport.cli import gcp_endpoints_client
from multitest_transport.cli import gcp_param_manager
from multitest_transport.cli import node_config
from multitest_transport.cli import node_permissions
import yaml

logger = logging.getLogger(__name__)

DEFAULT_BASE_DIR = "/var/lib/mttnode"
DEFAULT_STATIC_DIR = "/etc/mtt"
DEFAULT_VAR_CONFIG_DIR = os.path.join(DEFAULT_BASE_DIR, "config")
DEFAULT_OTEL_ENDPOINT = "http://otel-collector:4317"
SUPPORTED_USAGES: Sequence[str] = (
    "dda",
    "public_testing",
    "internal_testing",
    "private_usage",
    "cts_testing",
)
_NODE_PARAM_SUFFIX = "_node_config"
# GCP Parameter Manager rejects resource IDs longer than 63 characters; see
# cloud/security/parametermanager/shared/util/resourcepath/resourcepath.go
_PARAM_ID_MAX_LEN = 63
# 48 bits of SHA-256. Collision probability is roughly 2e-7 across a fleet of
# 10,000 hosts, and this is the only thing keeping two hosts apart.
_PARAM_DIGEST_LEN = 12
# Whatever is left for the human-readable prefix, after the digest and the
# hyphen separating it.
_PARAM_PREFIX_MAX_LEN = (
    _PARAM_ID_MAX_LEN - len(_NODE_PARAM_SUFFIX) - _PARAM_DIGEST_LEN - 1
)
_SA_KEY_FILENAME = "sa-key.json"
_ANDROID_SA_KEY_FILENAME = "android-sa-key.json"
# Path of the service account key as seen from inside the dialer container,
# which mounts ${SECRETS_DIR:-/etc/mtt/secrets} at /etc/secrets.
_CONTAINER_SA_KEY_PATH = f"/etc/secrets/{_SA_KEY_FILENAME}"
# Unformatted YAML parameter, maintained by Google OmniLab, holding a flat map
# from Cloud Endpoints service name (exactly as returned by ListServiceNames,
# without "wss://") to the ATS Web UI URL of the controller behind it, e.g.
#   testing-dev.endpoints.<project>.cloud.goog: "https://<ui>.omnilab-ats.dev/"
# The UI domain cannot be derived from the endpoint name, hence the manual map.
ATS_UI_CONFIG_PARAM = "ats_ui_config"
_CONTACT_OMNILAB = "Contact Google OmniLab for the URL."


class UserAbortError(Exception):
  """Raised when the user aborts the interactive join workflow."""


def HostnameToNodeParamName(hostname: str) -> str:
  """Derives a unique GCP Parameter Manager parameter ID from a hostname.

  The ID is `<prefix>-<digest>_node_config`. The digest, a truncated SHA-256 of
  the canonical hostname, is what makes the ID unique; the prefix is a lossy
  rendering of the hostname that exists only so an operator can recognize the
  host when browsing parameters. Two hosts therefore never share an ID even if
  their prefixes are identical.

  The hostname is canonicalized before hashing (surrounding whitespace and any
  trailing root dot removed, then lowercased) because DNS names are
  case-insensitive and `host.corp` and `host.corp.` name the same machine: each
  must derive the same ID however it is spelled.

  The prefix keeps the head of the name and drops the tail, since hosts in one
  tenant typically differ in their leading labels and share the trailing
  domain.

  The result always satisfies the Parameter Manager ID constraint
  `^[a-zA-Z0-9_][a-zA-Z0-9_-]{0,62}$`, whatever the hostname contains.

  Args:
    hostname: The hostname to convert.

  Returns:
    A valid GCP Parameter Manager parameter ID ending with `_node_config`.

  Raises:
    ValueError: If hostname is empty or contains consecutive dots.
  """
  canonical = hostname.strip().rstrip(".").lower()
  if not canonical:
    raise ValueError("Hostname cannot be empty.")
  if ".." in canonical:
    raise ValueError(
        f"Hostname {hostname!r} contains consecutive dots, which is not a"
        " valid DNS name."
    )
  digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
  prefix = "".join(
      c if c.isascii() and (c.isalnum() or c == "-") else "-" for c in canonical
  )
  # Trailing hyphens are stripped after truncation so a cut that lands on a
  # label boundary does not leave a dangling separator before the digest.
  prefix = prefix[:_PARAM_PREFIX_MAX_LEN].strip("-") or "host"
  return f"{prefix}-{digest[:_PARAM_DIGEST_LEN]}{_NODE_PARAM_SUFFIX}"


class Prompter:
  """Terminal prompt primitives with validation and abort guards."""

  def __init__(
      self,
      input_fn: Callable[[str], str] = input,
      output_fn: Callable[[str], None] = print,
      isatty_check: bool = True,
  ):
    self._input_fn = input_fn
    self._output_fn = output_fn
    self._isatty_check = isatty_check

  def CheckTty(self) -> None:
    """Verifies that the process is running in an interactive terminal."""
    if self._isatty_check and not sys.stdin.isatty():
      raise RuntimeError(
          "Interactive terminal (TTY) required for join. For"
          " non-interactive automated provisioning, use 'mtt node worker init'."
      )

  def Info(self, message: str) -> None:
    """Shows a message to the operator without waiting for input."""
    self._output_fn(message)

  def Text(
      self,
      message: str,
      validator: Optional[Callable[[str], bool]] = None,
      error_message: str = "Invalid input, please try again.",
      max_retries: int = 3,
  ) -> str:
    """Prompts for text input with optional validation and bounded retries."""
    for _ in range(max_retries):
      try:
        val = self._input_fn(message).strip()
      except (KeyboardInterrupt, EOFError) as e:
        self._output_fn("\nJoin cancelled by user.")
        raise UserAbortError("Join cancelled by user.") from e

      if validator is None or validator(val):
        return val
      self._output_fn(f"Error: {error_message}")
    raise RuntimeError(
        f"Maximum retry limit exceeded ({max_retries}) for input."
    )

  def Confirm(
      self,
      message: str,
      default: bool = True,
      max_retries: int = 3,
      abort_message: str = "Join cancelled by user.",
  ) -> bool:
    """Prompts for boolean confirmation ([Y/n] or [y/N]) with bounded retries.

    Args:
      message: Question to show, without the [Y/n] suffix.
      default: Value returned when the operator just presses enter.
      max_retries: How many unparseable answers to tolerate.
      abort_message: Text shown and raised when the operator interrupts.
        Callers that confirm something after the join has already been
        committed must override this, otherwise an interrupt claims the join
        was cancelled when it was not.

    Returns:
      The operator's answer.

    Raises:
      UserAbortError: If the operator interrupts the prompt.
      RuntimeError: If the retry limit is exhausted.
    """
    prompt_suffix = " [Y/n]: " if default else " [y/N]: "
    for _ in range(max_retries):
      try:
        raw = self._input_fn(message + prompt_suffix).strip().lower()
      except (KeyboardInterrupt, EOFError) as e:
        self._output_fn(f"\n{abort_message}")
        raise UserAbortError(abort_message) from e

      if not raw:
        return default
      if raw in ("y", "yes"):
        return True
      if raw in ("n", "no"):
        return False
      self._output_fn("Please enter 'y' for yes or 'n' for no.")
    raise RuntimeError(
        f"Maximum retry limit exceeded ({max_retries}) for confirmation."
    )

  def Choice(
      self,
      message: str,
      options: Sequence[str],
      display_fn: Optional[Callable[[str], str]] = None,
      max_retries: int = 3,
  ) -> str:
    """Presents a numbered choice menu and prompts for selection."""
    if not options:
      raise ValueError("Cannot prompt for choice with empty options.")

    self._output_fn(message)
    for idx, opt in enumerate(options, 1):
      display_text = display_fn(opt) if display_fn else opt
      self._output_fn(f"  [{idx}] {display_text}")

    prompt_msg = f"Select an option [1-{len(options)}]: "
    for _ in range(max_retries):
      try:
        raw = self._input_fn(prompt_msg).strip()
      except (KeyboardInterrupt, EOFError) as e:
        self._output_fn("\nJoin cancelled by user.")
        raise UserAbortError("Join cancelled by user.") from e

      if raw.isdigit():
        choice_idx = int(raw) - 1
        if 0 <= choice_idx < len(options):
          return options[choice_idx]
      self._output_fn(
          f"Invalid selection '{raw}'. Please enter a number between 1 and"
          f" {len(options)}."
      )
    raise RuntimeError(
        f"Maximum retry limit exceeded ({max_retries}) for option selection."
    )


class _AtsWebUiLookupError(Exception):
  """Raised when the ATS Web UI URL cannot be determined.

  The message is shown to the operator verbatim and says whom to contact.
  """


def _LookUpAtsWebUiUrl(
    pm_client: Any,
    project_id: str,
    endpoint: str,
    all_parameters: Sequence[str],
) -> str:
  """Returns the ATS Web UI URL of an acceptor endpoint from ats_ui_config.

  Args:
    pm_client: Parameter Manager client for the project.
    project_id: GCP project ID.
    endpoint: Cloud Endpoints service name the operator selected.
    all_parameters: Parameter IDs already listed by the join. Used to report a
      missing parameter without another API call.

  Returns:
    The URL, with surrounding whitespace removed.

  Raises:
    _AtsWebUiLookupError: If the URL cannot be determined.
  """
  param = ATS_UI_CONFIG_PARAM
  if param not in all_parameters:
    raise _AtsWebUiLookupError(
        f"parameter '{param}' does not exist in project '{project_id}'."
        f" {_CONTACT_OMNILAB}"
    )

  version_path = (
      f"projects/{project_id}/locations/global/parameters/{param}"
      "/versions/latest"
  )
  try:
    payload = pm_client.FetchUnformatted(version_path)
  except (RuntimeError, ValueError) as e:
    # RuntimeError: the API call failed. ValueError: empty or non-UTF-8
    # payload.
    raise _AtsWebUiLookupError(
        f"could not read parameter '{param}': {e}. {_CONTACT_OMNILAB}"
    ) from e

  try:
    url_by_endpoint = yaml.safe_load(payload)
  except yaml.YAMLError as e:
    raise _AtsWebUiLookupError(
        f"parameter '{param}' is not valid YAML. {_CONTACT_OMNILAB}"
    ) from e
  if not isinstance(url_by_endpoint, dict):
    # Most likely cause: `endpoint:"url"` without a space after the colon,
    # which YAML reads as one plain string.
    raise _AtsWebUiLookupError(
        f"parameter '{param}' must be a YAML map of endpoint to URL"
        " ('<endpoint>: <url>', with a space after the colon)."
        f" {_CONTACT_OMNILAB}"
    )
  if endpoint not in url_by_endpoint:
    raise _AtsWebUiLookupError(
        f"parameter '{param}' has no entry for '{endpoint}'. {_CONTACT_OMNILAB}"
    )
  url = url_by_endpoint[endpoint]
  if not isinstance(url, str) or not url.strip().startswith(
      ("https://", "http://")
  ):
    raise _AtsWebUiLookupError(
        f"the '{param}' entry for '{endpoint}' must be an http(s) URL string,"
        f" got {url!r}. {_CONTACT_OMNILAB}"
    )
  return url.strip()


def _ShowAtsWebUiUrl(
    ui: Prompter,
    pm_client: Any,
    project_id: str,
    endpoint: str,
    all_parameters: Sequence[str],
) -> None:
  """Shows the ATS Web UI URL of the selected controller, or a warning.

  Runs after the join is committed and never raises: the URL only informs the
  operator, so failing to find it must neither roll back the join nor change
  its exit code.

  Args:
    ui: Prompter used to show the result.
    pm_client: Parameter Manager client for the project.
    project_id: GCP project ID.
    endpoint: Cloud Endpoints service name the operator selected.
    all_parameters: Parameter IDs already listed by the join.
  """
  warning_prefix = (
      "\nWARNING: The join succeeded, but the ATS Web UI URL for"
      f" '{endpoint}' is unavailable:"
  )
  try:
    url = _LookUpAtsWebUiUrl(pm_client, project_id, endpoint, all_parameters)
  except _AtsWebUiLookupError as e:
    ui.Info(f"{warning_prefix} {e}")
    return
  except Exception as e:  
    logger.debug("ATS Web UI URL lookup failed", exc_info=True)
    ui.Info(f"{warning_prefix} unexpected error: {e}. {_CONTACT_OMNILAB}")
    return
  ui.Info(f"\nATS Web UI for controller '{endpoint}': {url}")


def Join(
    static_dir: str = DEFAULT_STATIC_DIR,
    var_config_dir: str = DEFAULT_VAR_CONFIG_DIR,
    base_dir: str = DEFAULT_BASE_DIR,
    mtt_group: str = node_permissions.DEFAULT_MTT_GROUP,
    tag: Optional[str] = None,
    android_service_account_key_path: Optional[str] = None,
    prompter: Optional[Prompter] = None,
    endpoints_client_factory: Optional[Callable[[str], Any]] = None,
    param_manager_client_factory: Optional[Callable[[str], Any]] = None,
) -> None:
  """Executes the interactive onboarding wizard for MTT worker nodes.

  After the join is committed, shows the ATS Web UI URL of the selected
  controller from the `ats_ui_config` parameter, or a warning if it cannot be
  determined. That lookup never raises.

  Args:
    static_dir: Root static directory (default /etc/mtt).
    var_config_dir: Destination runtime directory (default
      /var/lib/mttnode/config).
    base_dir: Runtime base directory (default /var/lib/mttnode).
    mtt_group: Existing host group that owns both directories. A flag only; the
      wizard never prompts for it.
    tag: Optional node-scope MTT image tag override stored in Parameter Manager.
    android_service_account_key_path: Optional path to Android service account
      JSON key file. Copied to <static_dir>/secrets/android-sa-key.json and
      referenced in node-scope mtt_args.
    prompter: Optional Prompter instance for dependency injection.
    endpoints_client_factory: Factory for GcpEndpointsClient (for testing).
    param_manager_client_factory: Factory for GcpParamManagerClient (for
      testing).

  Raises:
    UserAbortError: If the operator interrupts a prompt. Nothing has been
      written to the host or to Parameter Manager when this propagates.
    RuntimeError: If GCP resources are missing, auth is invalid, the terminal
      is non-interactive, or a prompt exhausts its retry budget.
    FileNotFoundError: If android_service_account_key_path does not exist.
    node_permissions.PermissionPolicyError: If mtt_group does not exist.
  """
  ui = prompter or Prompter()
  ui.CheckTty()

  # Resolved before the first prompt: a bad group name must not surface after
  # the operator has answered everything and a parameter version has already
  # been written to GCP.
  gid = node_permissions.ResolveGroupGid(mtt_group)

  android_sa_key_content: Optional[str] = None
  if android_service_account_key_path:
    if not os.path.isfile(android_service_account_key_path):
      raise FileNotFoundError(
          "Android service account key file not found:"
          f" {android_service_account_key_path}"
      )
    with open(android_service_account_key_path, "r", encoding="utf-8") as f:
      android_sa_key_content = f.read()

  # =========================================================================
  # Phase 1: In-Memory Collection (Zero Local/Remote Side Effects)
  # =========================================================================

  # Step 1: Service Account Key Path & Project ID
  def _ValidateSaPath(path: str) -> bool:
    if not os.path.isfile(path):
      return False
    try:
      with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
      return "project_id" in data
    except Exception:  
      return False

  sa_key_source_path = ui.Text(
      "Enter path to GCP Service Account JSON key: ",
      validator=_ValidateSaPath,
      error_message=(
          "File does not exist or is not a valid service account JSON key with"
          " 'project_id'."
      ),
  )

  with open(sa_key_source_path, "r", encoding="utf-8") as f:
    sa_key_json_data = json.load(f)
  project_id = sa_key_json_data["project_id"]

  # Initialize GCP clients
  if endpoints_client_factory:
    ep_client = endpoints_client_factory(sa_key_source_path)
  else:
    ep_factory = (
        gcp_endpoints_client.GcpEndpointsClient.FromServiceAccountKeyFile
    )
    ep_client = ep_factory(sa_key_source_path)

  if param_manager_client_factory:
    pm_client = param_manager_client_factory(sa_key_source_path)
  else:
    pm_factory = (
        gcp_param_manager.GcpParamManagerClient.FromServiceAccountKeyFile
    )
    pm_client = pm_factory(sa_key_source_path)

  # Step 2: DCON Acceptor Discovery (Cloud Endpoints)
  discovered_endpoints = ep_client.ListServiceNames(project_id)
  if not discovered_endpoints:
    raise RuntimeError(
        f"No Cloud Endpoints services found in project '{project_id}'."
    )

  chosen_endpoint = ui.Choice(
      "Select DCON Acceptor Endpoint:", options=discovered_endpoints
  )
  dcon_acceptor_target = f"wss://{chosen_endpoint}"

  # Step 3: Omni Mode Usage & Pool Config Resolution
  all_parameters = pm_client.ListParameters(project_id)
  if "tenant_config" not in all_parameters:
    raise RuntimeError(
        f"'tenant_config' parameter not found in project '{project_id}'"
        " Parameter Manager."
    )

  available_usages = [
      u for u in SUPPORTED_USAGES if f"{u}_pool_config" in all_parameters
  ]
  if not available_usages:
    raise RuntimeError(
        "No matching pool configs (*_pool_config) found in project"
        f" '{project_id}'. Supported usages are: {', '.join(SUPPORTED_USAGES)}"
    )

  chosen_usage = ui.Choice(
      "Select Omni Mode Usage:",
      options=available_usages,
      display_fn=lambda u: f"{u} ({u}_pool_config)",
  )
  chosen_pool_param = f"{chosen_usage}_pool_config"

  # Step 4: WiFi Configuration (Mandatory)
  wifi_ssid = ui.Text(
      "Enter WiFi SSID: ",
      validator=lambda s: bool(s.strip()),
      error_message="WiFi SSID cannot be empty.",
  )
  wifi_psk = ui.Text(
      "Enter WiFi Password (PSK): ",
      validator=lambda s: bool(s.strip()),
      error_message="WiFi Password cannot be empty.",
  )

  # =========================================================================
  # Phase 2: Idempotent Remote GCP Push
  # =========================================================================
  hostname = socket.gethostname()
  node_param_name = HostnameToNodeParamName(hostname)
  wifi_host_path = os.path.join(static_dir, "config", "wifi.yaml")
  android_sa_key_dest = os.path.join(
      static_dir, "secrets", _ANDROID_SA_KEY_FILENAME
  )
  mtt_args = (
      {"android_service_account_key_path": android_sa_key_dest}
      if android_service_account_key_path
      else {}
  )

  node_dto = node_config.ConfigDTO(
      docker_compose_env={
          "ACCEPTOR_TARGET": dcon_acceptor_target,
          "USE_SA_TOKEN": "true",
          "SA_KEY_FILE": _CONTAINER_SA_KEY_PATH,
          "OTEL_EXPORTER_OTLP_ENDPOINT": DEFAULT_OTEL_ENDPOINT,
      },
      cluster_config_args={
          "omni_mode_usage": chosen_usage,
      },
      host_config_args={
          "hostname": hostname,
      },
      host_config_mount_local_path=[
          f"{wifi_host_path}:/lab_config_values.yaml"
      ],
      mtt_args=mtt_args,
      tag=tag,
  )

  # Check existence first, create only if missing
  if not pm_client.ParameterExists(project_id, node_param_name):
    pm_client.CreateParameter(project_id, node_param_name)

  node_param_path = (
      f"projects/{project_id}/locations/global/parameters/{node_param_name}"
  )
  node_yaml_payload = yaml.dump(
      node_dto.ToDict(), default_flow_style=False, sort_keys=False
  )
  pm_client.StoreUnformatted(node_param_path, node_yaml_payload)

  # =========================================================================
  # Phase 3: Atomic Local Commit & Materialization
  # =========================================================================
  node_permissions.CreateAndApplyPolicy(gid, static_dir, base_dir)
  config_dir = os.path.join(static_dir, "config")
  secrets_dir = os.path.join(static_dir, "secrets")
  os.makedirs(config_dir, exist_ok=True)
  os.makedirs(secrets_dir, exist_ok=True)

  created_files: list[str] = []
  backups: list[tuple[str, str]] = []

  def _TrackWrite(path: str) -> None:
    """Registers a destination path for rollback before it is written.

    Any file already at the destination is moved aside so that a failed join
    restores the previous provisioning instead of destroying it. This matters
    when re-joining a host that was previously set up by `mtt node worker
    init`, whose secrets would otherwise be truncated and then deleted.

    Args:
      path: Destination path that is about to be created or overwritten.
    """
    if os.path.lexists(path):
      backup_path = f"{path}.join_bak"
      os.replace(path, backup_path)
      backups.append((path, backup_path))
    created_files.append(path)

  try:
    # 1. Copy Service Account Key(s)
    # The path is tracked before the file is opened so that a failure while
    # serializing the payload still leaves the partial file eligible for
    # cleanup below.
    sa_key_dest = os.path.join(secrets_dir, _SA_KEY_FILENAME)
    _TrackWrite(sa_key_dest)
    fd = os.open(
        sa_key_dest,
        os.O_WRONLY | os.O_CREAT | os.O_TRUNC,
        node_permissions.STATIC_FILE_MODE,
    )
    with open(fd, "w", encoding="utf-8") as f:
      json.dump(sa_key_json_data, f, indent=2)

    if android_sa_key_content is not None:
      _TrackWrite(android_sa_key_dest)
      fd = os.open(
          android_sa_key_dest,
          os.O_WRONLY | os.O_CREAT | os.O_TRUNC,
          node_permissions.STATIC_FILE_MODE,
      )
      with open(fd, "w", encoding="utf-8") as f:
        f.write(android_sa_key_content)

    # 2. Write WiFi Configuration
    wifi_data = {
        "WIFI_SSID": wifi_ssid,
        "WIFI_PSK": wifi_psk,
    }
    _TrackWrite(wifi_host_path)
    fd = os.open(
        wifi_host_path,
        os.O_WRONLY | os.O_CREAT | os.O_TRUNC,
        node_permissions.STATIC_FILE_MODE,
    )
    with open(fd, "w", encoding="utf-8") as f:
      yaml.safe_dump(wifi_data, f, default_flow_style=False, sort_keys=False)

    # 3. Write Manifest
    manifest_dest = os.path.join(static_dir, "manifest.yaml")
    t_path = (
        f"projects/{project_id}/locations/global/parameters/"
        "tenant_config/versions/latest"
    )
    p_path = (
        f"projects/{project_id}/locations/global/parameters/"
        f"{chosen_pool_param}/versions/latest"
    )
    n_path = (
        f"projects/{project_id}/locations/global/parameters/"
        f"{node_param_name}/versions/latest"
    )
    manifest_content = (
        f"service_account_key_path: {sa_key_dest}\n"
        f"{{% set tenant = param_manager('{t_path}', 'tenant') %}}\n"
        f"{{% set pool = param_manager('{p_path}', 'pool') %}}\n"
        f"{{% set node = param_manager('{n_path}', 'node') %}}\n"
    )
    _TrackWrite(manifest_dest)
    with open(manifest_dest, "w", encoding="utf-8") as f:
      f.write(manifest_content)

    # 4. Materialize Node Configuration
    node_config.MaterializeNodeConfig(
        static_dir=static_dir,
        var_config_dir=var_config_dir,
        role=node_config.NodeRole.WORKER,
    )
    logger.info(
        "Worker node '%s' joined and materialized successfully.", hostname
    )
  except Exception as e:
    # Roll back: drop everything this join wrote, then restore whatever it
    # displaced so the host is left exactly as it was found.
    for path in created_files:
      if os.path.lexists(path):
        try:
          os.remove(path)
        except OSError:
          logger.warning("Failed to remove partial file %s", path)
    for path, backup_path in backups:
      try:
        os.replace(backup_path, path)
      except OSError:
        logger.warning(
            "Failed to restore %s from backup %s; the previous file is still"
            " available at the backup path.",
            path,
            backup_path,
        )
    raise RuntimeError(
        f"Failed to finalize worker node provisioning: {e}"
    ) from e
  else:
    # The join is committed; the displaced files are no longer needed.
    for _, backup_path in backups:
      try:
        os.remove(backup_path)
      except OSError:
        logger.warning("Failed to remove backup file %s", backup_path)
    # Re-applied after the backups are gone, so the policy covers the
    # committed tree without touching transient .join_bak files.
    node_permissions.FinalizeProvisioning(gid, static_dir, base_dir)

  # Outside the transaction above: the join is committed by now, and this
  # lookup only informs the operator.
  _ShowAtsWebUiUrl(ui, pm_client, project_id, chosen_endpoint, all_parameters)
