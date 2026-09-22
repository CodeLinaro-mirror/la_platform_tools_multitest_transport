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

"""Non-interactive static host provisioning for MTT Controller and Worker."""

import logging
import os
import shutil
from typing import Optional, Sequence
from multitest_transport.cli import host_env
from multitest_transport.cli import node_permissions
import yaml

logger = logging.getLogger(__name__)

DEFAULT_IMAGE_NAME = "gcr.io/android-mtt/mtt"
DEFAULT_TAG = "latest"
DEFAULT_STATIC_DIR = "/etc/mtt"
DEFAULT_BASE_DIR = "/var/lib/mttnode"
DEFAULT_OTEL_ENDPOINT = "http://otel-collector:4317"
DEFAULT_SECRETS_DIR_NAME = "secrets"
DEFAULT_CONFIG_DIR_NAME = "config"
DEFAULT_SA_KEY_FILENAME = "sa-key.json"


def _ProvisionDirectories(static_dir: str, base_dir: str, group: str) -> int:
  """Creates both trees and hands them to the mtt group.

  Called before anything is written so that files land inside setgid
  directories and inherit the group without a second pass, and called again
  afterwards so that anything created by an intervening step is covered.

  Args:
    static_dir: Root static directory.
    base_dir: Runtime base directory.
    group: Name of an existing host group.

  Returns:
    The numeric group id the trees are owned by.

  Raises:
    node_permissions.PermissionPolicyError: If the group does not exist.
  """
  gid = node_permissions.ResolveGroupGid(group)
  node_permissions.CreateAndApplyPolicy(gid, static_dir, base_dir)
  return gid


def InitController(
    static_dir: str = DEFAULT_STATIC_DIR,
    base_dir: str = DEFAULT_BASE_DIR,
    mtt_group: str = node_permissions.DEFAULT_MTT_GROUP,
    image_name: str = DEFAULT_IMAGE_NAME,
    tag: str = DEFAULT_TAG,
    dcon_acceptor_addr: Optional[str] = None,
    otel: bool = False,
    service_account_json_key_path: Optional[str] = None,
    unrecognized_flags: Sequence[str] = (),
    host_environment: Optional[host_env.HostEnvironment] = None,
) -> None:
  """Initializes controller configuration non-interactively.

  Args:
    static_dir: Root static directory (e.g. /etc/mtt).
    base_dir: Runtime base directory (e.g. /var/lib/mttnode).
    mtt_group: Existing host group that owns both directories.
    image_name: MTT container image name.
    tag: MTT container image tag.
    dcon_acceptor_addr: Cloud Endpoints address for ESP. Required on GCP, and
      rejected elsewhere.
    otel: Whether to enable OpenTelemetry exporter.
    service_account_json_key_path: Path to local service account JSON key file.
    unrecognized_flags: Extra flags to forward to MTT container.
    host_environment: Environment this host runs in. Detected when omitted.

  Raises:
    FileNotFoundError: If service_account_json_key_path does not exist.
    ValueError: If dcon_acceptor_addr does not agree with the host
      environment.
    node_permissions.PermissionPolicyError: If mtt_group does not exist.
  """
  if host_environment is None:
    host_environment = host_env.Detect()

  # The Cloud Endpoints proxy that serves the acceptor is GCP-only. Requiring
  # the pair to agree here keeps the two broken shapes out of the config
  # entirely: a GCP controller with nothing for ESP to proxy, and a lab
  # controller carrying an address that will never be read.
  if host_environment.IsGcp() and not dcon_acceptor_addr:
    raise ValueError(
        "--dcon_acceptor_addr is required for a controller on"
        f" {host_environment.value}: the DualConduit acceptor is served"
        " through the Cloud Endpoints proxy, which needs the service name."
    )
  if dcon_acceptor_addr and not host_environment.IsGcp():
    raise ValueError(
        "--dcon_acceptor_addr was given but this host is"
        f" {host_environment.value}, not GCP. The Cloud Endpoints proxy will"
        " not be started here, so the address would have no effect."
    )

  # Resolved before anything is written so a typo in the group name fails
  # while the host is still untouched.
  gid = _ProvisionDirectories(static_dir, base_dir, mtt_group)

  config_dir = os.path.join(static_dir, DEFAULT_CONFIG_DIR_NAME)
  secrets_dir = os.path.join(static_dir, DEFAULT_SECRETS_DIR_NAME)
  os.makedirs(config_dir, exist_ok=True)
  os.makedirs(secrets_dir, exist_ok=True)

  dest_lab_config = os.path.join(config_dir, "lab_config.yaml")
  if os.path.lexists(dest_lab_config):
    os.remove(dest_lab_config)

  compose_env_vars: dict[str, str] = {}
  mtt_flags: list[str] = []

  if service_account_json_key_path:
    if not os.path.isfile(service_account_json_key_path):
      raise FileNotFoundError(
          f"Service account key file not found: {service_account_json_key_path}"
      )
    dest_sa_key_path = os.path.join(secrets_dir, DEFAULT_SA_KEY_FILENAME)
    shutil.copyfile(service_account_json_key_path, dest_sa_key_path)
    compose_env_vars["SA_KEY_FILE"] = f"/etc/secrets/{DEFAULT_SA_KEY_FILENAME}"
    mtt_flags.append(f"--service_account_json_key_path={dest_sa_key_path}")

  if dcon_acceptor_addr:
    compose_env_vars["DCON_ACCEPTOR_ADDR"] = dcon_acceptor_addr

  if otel:
    compose_env_vars["OTEL_EXPORTER_OTLP_ENDPOINT"] = DEFAULT_OTEL_ENDPOINT

  # Write docker-compose.env
  compose_env_file = os.path.join(config_dir, "docker-compose.env")
  with open(compose_env_file, "w", encoding="utf-8") as f:
    for k, v in compose_env_vars.items():
      f.write(f"{k}={v}\n")

  # Write mtt_flags.yaml
  extra_flags = list(unrecognized_flags)
  if extra_flags and extra_flags[0] == "--":
    extra_flags = extra_flags[1:]
  mtt_flags.extend(extra_flags)
  flags_data = {
      "image_name": image_name,
      "tag": tag,
      "flags": mtt_flags,
  }
  flags_file = os.path.join(config_dir, "mtt_flags.yaml")
  with open(flags_file, "w", encoding="utf-8") as f:
    yaml.dump(flags_data, f, default_flow_style=False)

  node_permissions.FinalizeProvisioning(gid, static_dir, base_dir)
  logger.info("Controller initialized successfully in %s", static_dir)


def InitWorker(
    dcon_acceptor_target: str,
    static_dir: str = DEFAULT_STATIC_DIR,
    base_dir: str = DEFAULT_BASE_DIR,
    mtt_group: str = node_permissions.DEFAULT_MTT_GROUP,
    image_name: str = DEFAULT_IMAGE_NAME,
    tag: str = DEFAULT_TAG,
    otel: bool = False,
    service_account_json_key_path: Optional[str] = None,
    lab_config_path: Optional[str] = None,
    unrecognized_flags: Sequence[str] = (),
) -> None:
  """Initializes worker configuration non-interactively.

  Args:
    dcon_acceptor_target: DualConduit acceptor websocket target URL.
    static_dir: Root static directory (e.g. /etc/mtt).
    base_dir: Runtime base directory (e.g. /var/lib/mttnode).
    mtt_group: Existing host group that owns both directories.
    image_name: MTT container image name.
    tag: MTT container image tag.
    otel: Whether to enable OpenTelemetry exporter.
    service_account_json_key_path: Path to local service account JSON key file.
    lab_config_path: Path to local lab_config.yaml file.
    unrecognized_flags: Extra flags to forward to MTT container.

  Raises:
    ValueError: If dcon_acceptor_target is empty.
    FileNotFoundError: If key file or lab_config file does not exist.
    node_permissions.PermissionPolicyError: If mtt_group does not exist.
  """
  if not dcon_acceptor_target:
    raise ValueError("--dcon_acceptor_target is required for worker init")

  # Resolved before anything is written so a typo in the group name fails
  # while the host is still untouched.
  gid = _ProvisionDirectories(static_dir, base_dir, mtt_group)

  config_dir = os.path.join(static_dir, DEFAULT_CONFIG_DIR_NAME)
  secrets_dir = os.path.join(static_dir, DEFAULT_SECRETS_DIR_NAME)
  os.makedirs(config_dir, exist_ok=True)
  os.makedirs(secrets_dir, exist_ok=True)

  dest_lab_config = os.path.join(config_dir, "lab_config.yaml")
  if lab_config_path:
    if not os.path.isfile(lab_config_path):
      raise FileNotFoundError(f"Lab config file not found: {lab_config_path}")
    shutil.copyfile(lab_config_path, dest_lab_config)
  elif os.path.lexists(dest_lab_config):
    os.remove(dest_lab_config)

  compose_env_vars: dict[str, str] = {
      "ACCEPTOR_TARGET": dcon_acceptor_target,
  }
  mtt_flags: list[str] = []

  if service_account_json_key_path:
    if not os.path.isfile(service_account_json_key_path):
      raise FileNotFoundError(
          f"Service account key file not found: {service_account_json_key_path}"
      )
    dest_sa_key_path = os.path.join(secrets_dir, DEFAULT_SA_KEY_FILENAME)
    shutil.copyfile(service_account_json_key_path, dest_sa_key_path)
    compose_env_vars["USE_SA_TOKEN"] = "true"
    compose_env_vars["SA_KEY_FILE"] = f"/etc/secrets/{DEFAULT_SA_KEY_FILENAME}"
    mtt_flags.append(f"--service_account_json_key_path={dest_sa_key_path}")

  if otel:
    compose_env_vars["OTEL_EXPORTER_OTLP_ENDPOINT"] = DEFAULT_OTEL_ENDPOINT

  # Write docker-compose.env
  compose_env_file = os.path.join(config_dir, "docker-compose.env")
  with open(compose_env_file, "w", encoding="utf-8") as f:
    for k, v in compose_env_vars.items():
      f.write(f"{k}={v}\n")

  # Write mtt_flags.yaml
  extra_flags = list(unrecognized_flags)
  if extra_flags and extra_flags[0] == "--":
    extra_flags = extra_flags[1:]
  mtt_flags.extend(extra_flags)
  flags_data = {
      "image_name": image_name,
      "tag": tag,
      "flags": mtt_flags,
  }
  flags_file = os.path.join(config_dir, "mtt_flags.yaml")
  with open(flags_file, "w", encoding="utf-8") as f:
    yaml.dump(flags_data, f, default_flow_style=False)

  node_permissions.FinalizeProvisioning(gid, static_dir, base_dir)
  logger.info("Worker initialized successfully in %s", static_dir)
