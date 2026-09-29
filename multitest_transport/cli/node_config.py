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

"""Declarative configuration management layer for MTT Node.

Resolves multi-scope GCP Parameter Manager hierarchies (Tenant -> Pool -> Node)
from manifest.yaml and compiles them into concrete runtime configuration files
(lab_config.yaml, docker-compose.env, and mtt_flags.yaml).
"""

import dataclasses
import enum
import logging
import os
import re
import socket
from typing import Any, Iterator, Optional, Sequence, Union
from google.protobuf import json_format
import jinja2
from multitest_transport.cli import command_util
from multitest_transport.cli import gcp_param_manager
from multitest_transport.cli import host_env
from multitest_transport.cli import node_permissions
import strictyaml as syaml
from tradefed_cluster.configs import lab_config
from tradefed_cluster.configs import lab_config_pb2
import yaml

# Re-export client for convenience.
GcpParamManagerClient = gcp_param_manager.GcpParamManagerClient

DEFAULT_PARTNER_IMAGE_NAME = (
    "asia-docker.pkg.dev/omnilab-ats-repo/omnilab-ats-partner/omnilab-ats"
)
DEFAULT_PARTNER_TAG = "partner_latest"

logger = logging.getLogger(__name__)


class ConfigValidationError(Exception):
  """Raised when materialized configuration violates MTT node invariants."""


class NodeRole(enum.Enum):
  """Operational roles for MTT Node."""

  WORKER = "worker"
  CONTROLLER = "controller"


class _ConfigScope(enum.Enum):
  """Hierarchical configuration scopes."""

  TENANT = "tenant"
  POOL = "pool"
  NODE = "node"


class _ResetList(list):
  """A list subclass indicating that higher scopes reset inherited list items."""

  pass


def _ResetConstructor(loader: yaml.SafeLoader, node: yaml.Node) -> _ResetList:
  return _ResetList(loader.construct_sequence(node))


# Register custom '!reset' constructor in SafeLoader.
yaml.SafeLoader.add_constructor("!reset", _ResetConstructor)


def _ResolveBoolArgs(flags: Sequence[str]) -> list[str]:
  """Resolves conflicting boolean flags, keeping the last one specified.

  For example, ['enable-cache', 'no-enable-cache'] resolves to
  ['no-enable-cache'].

  Args:
    flags: Sequence of flag strings (e.g. ['foo', 'no-foo']).

  Returns:
    List of resolved flag strings.
  """
  resolved: list[str] = []
  for flag in flags:
    counterpart = flag[3:] if flag.startswith("no-") else f"no-{flag}"
    if counterpart in resolved:
      resolved.remove(counterpart)
    if flag in resolved:
      resolved.remove(flag)
    resolved.append(flag)
  return resolved


def _ApplyBoolFlagsToMessage(msg: Any, bool_flags: Sequence[str]) -> None:
  """Applies resolved boolean flags to protobuf message fields."""
  resolved = _ResolveBoolArgs(bool_flags)
  for flag in resolved:
    val = False if flag.startswith("no-") else True
    name = flag[3:] if flag.startswith("no-") else flag
    if hasattr(msg, name):
      setattr(msg, name, val)


def _CoerceBool(value: Any) -> bool:
  """Coerces a YAML scalar into a boolean.

  `bool("false")` evaluates to True in Python, so string values must be parsed
  explicitly. Any string not recognized as truthy is treated as False.

  Args:
    value: Scalar value parsed from configuration.

  Returns:
    The coerced boolean value.
  """
  if isinstance(value, str):
    return value.strip().lower() in ("true", "1", "yes", "y")
  return bool(value)


def _ApplyDictToMessage(
    msg: Any, data: dict[str, Any], skip_fields: Sequence[str] = ()
) -> None:
  """Applies key-value dictionary to scalar protobuf message fields."""
  for k, v in data.items():
    if k in skip_fields:
      continue
    if hasattr(msg, k):
      field_desc = msg.DESCRIPTOR.fields_by_name.get(k)
      if not field_desc:
        continue
      if field_desc.label == field_desc.LABEL_REPEATED:
        logger.warning(
            "Skipping unhandled repeated field '%s' on %s message.",
            k,
            msg.DESCRIPTOR.name,
        )
        continue

      if field_desc.type == field_desc.TYPE_ENUM:
        if isinstance(v, str):
          enum_val = field_desc.enum_type.values_by_name.get(v.upper())
          if enum_val is not None:
            setattr(msg, k, enum_val.number)
          elif v.isdigit():
            setattr(msg, k, int(v))
          else:
            raise ValueError(
                f"Invalid enum value '{v}' for field '{k}' in"
                f" {msg.DESCRIPTOR.name}"
            )
        else:
          setattr(msg, k, int(v))
      elif field_desc.type in (
          field_desc.TYPE_INT32,
          field_desc.TYPE_UINT32,
          field_desc.TYPE_INT64,
          field_desc.TYPE_UINT64,
      ):
        setattr(msg, k, int(v))
      elif field_desc.type in (
          field_desc.TYPE_DOUBLE,
          field_desc.TYPE_FLOAT,
      ):
        setattr(msg, k, float(v))
      elif field_desc.type == field_desc.TYPE_BOOL:
        setattr(msg, k, _CoerceBool(v))
      elif field_desc.type == field_desc.TYPE_STRING:
        setattr(msg, k, str(v))
      else:
        setattr(msg, k, v)


def _ConvertJavaOptsDictToOptsList(opts: dict[str, Any]) -> list[str]:
  """Converts a dictionary of Java server options into a list of flags.

  Boolean flags are formatted as --key=true or --key=false.

  Args:
    opts: Dictionary of option name to value.

  Returns:
    List of option flag strings (e.g. ['--key=val', '--enable_xds=true']).
  """
  opts_list: list[str] = []
  for k, v in opts.items():
    if isinstance(v, bool):
      opts_list.append(f"--{k}={'true' if v else 'false'}")
    else:
      opts_list.append(f"--{k}={v}")
  return opts_list


def _FormatJavaServerOpts(opts: dict[str, Any]) -> str:
  """Converts a dictionary of Java server options into a space-separated flag string."""
  return " ".join(_ConvertJavaOptsDictToOptsList(opts))


@dataclasses.dataclass
class ConfigDTO:
  """Strongly-typed data transfer object flattening LabConfig proto & compose env.

  Attributes:
    docker_compose_env: Environment variables used by Docker Compose services.
    mtt_docker_env: Environment variables injected into the MTT Docker container
      (formatted as -e in HostConfig.extra_docker_args).
    lab_server_opts: Dedicated dict of lab server options (merged across scopes,
      formatted into LAB_SERVER_OPTS, and added to mtt_docker_env).
    olc_server_opts: Dedicated dict of OLC server options (merged across scopes,
      formatted into OLC_SERVER_OPTS, and added to mtt_docker_env).
    lab_config_args: Key-value fields for LabConfig proto.
    lab_config_bool_args: Boolean flag names for LabConfig proto.
    cluster_config_args: Key-value fields for ClusterConfig proto.
    cluster_config_bool_args: Boolean flag names for ClusterConfig proto.
    host_config_args: Key-value fields for HostConfig proto.
    host_config_bool_args: Boolean flag names for HostConfig proto.
    host_config_mount_local_path: Host filesystem paths mounted into container.
    mtt_args: Extra key-value CLI arguments not covered by lab_config.proto.
      Must not contain image_name or tag; see __post_init__.
    mtt_bool_args: Extra boolean CLI arguments not covered by lab_config.proto.
    image_name: Target Docker repository/image name.
    tag: Target Docker image tag for registry pull (e.g. latest, prod, v1.2.3).
  """

  docker_compose_env: dict[str, str] = dataclasses.field(default_factory=dict)
  mtt_docker_env: dict[str, str] = dataclasses.field(default_factory=dict)
  lab_server_opts: dict[str, Any] = dataclasses.field(default_factory=dict)
  olc_server_opts: dict[str, Any] = dataclasses.field(default_factory=dict)
  lab_config_args: dict[str, Any] = dataclasses.field(default_factory=dict)
  lab_config_bool_args: list[str] = dataclasses.field(default_factory=list)
  cluster_config_args: dict[str, Any] = dataclasses.field(default_factory=dict)
  cluster_config_bool_args: list[str] = dataclasses.field(default_factory=list)
  host_config_args: dict[str, Any] = dataclasses.field(default_factory=dict)
  host_config_bool_args: list[str] = dataclasses.field(default_factory=list)
  host_config_mount_local_path: list[str] = dataclasses.field(
      default_factory=list
  )
  mtt_args: dict[str, Any] = dataclasses.field(default_factory=dict)
  mtt_bool_args: list[str] = dataclasses.field(default_factory=list)
  image_name: Optional[str] = None
  tag: Optional[str] = None

  def __post_init__(self):
    """Rejects image identity passed through mtt_args.

    Raises:
      ConfigValidationError: If mtt_args carries image_name or tag.
    """
    violations = [k for k in ("image_name", "tag") if k in self.mtt_args]
    if not violations:
      return

    raise ConfigValidationError(
        f"mtt_args must not contain {violations}. Image identity belongs to"
        " the dedicated top-level 'image_name' and 'tag' fields. mtt_args is"
        " appended to the mtt command line after the node's own --image_name,"
        " so these would override the pinned image reference."
    )

  @property
  def pull_image_ref(self) -> str:
    """Returns registry pull reference (<image_name>:<tag>)."""
    if not self.image_name:
      return ""
    tag = self.tag or "latest"
    return f"{self.image_name}:{tag}"

  def ToDict(self) -> dict[str, Any]:
    """Converts DTO to a dictionary representation."""
    d: dict[str, Any] = {}
    if self.docker_compose_env:
      d["docker_compose_env"] = self.docker_compose_env
    if self.mtt_docker_env:
      d["mtt_docker_env"] = self.mtt_docker_env
    if self.lab_server_opts:
      d["lab_server_opts"] = self.lab_server_opts
    if self.olc_server_opts:
      d["olc_server_opts"] = self.olc_server_opts
    if self.lab_config_args:
      d["lab_config_args"] = self.lab_config_args
    if self.lab_config_bool_args:
      d["lab_config_bool_args"] = self.lab_config_bool_args
    if self.cluster_config_args:
      d["cluster_config_args"] = self.cluster_config_args
    if self.cluster_config_bool_args:
      d["cluster_config_bool_args"] = self.cluster_config_bool_args
    if self.host_config_args:
      d["host_config_args"] = self.host_config_args
    if self.host_config_bool_args:
      d["host_config_bool_args"] = self.host_config_bool_args
    if self.host_config_mount_local_path:
      d["host_config_mount_local_path"] = self.host_config_mount_local_path
    if self.mtt_args:
      d["mtt_args"] = self.mtt_args
    if self.mtt_bool_args:
      d["mtt_bool_args"] = self.mtt_bool_args
    if self.image_name:
      d["image_name"] = self.image_name
    if self.tag:
      d["tag"] = self.tag
    return d

  @classmethod
  def FromDict(cls, data: dict[str, Any]) -> "ConfigDTO":
    """Creates a ConfigDTO from a dictionary with strict field naming."""
    image_name = data.get("image_name")
    tag = data.get("tag")
    if not image_name and "image" in data and data["image"]:
      raw_image = str(data["image"])
      if ":" in raw_image:
        image_name, tag = raw_image.split(":", 1)
      else:
        image_name = raw_image

    return cls(
        docker_compose_env=dict(data.get("docker_compose_env", {})),
        mtt_docker_env=dict(data.get("mtt_docker_env", {})),
        lab_server_opts=dict(data.get("lab_server_opts", {})),
        olc_server_opts=dict(data.get("olc_server_opts", {})),
        lab_config_args=dict(data.get("lab_config_args", {})),
        lab_config_bool_args=list(data.get("lab_config_bool_args", [])),
        cluster_config_args=dict(data.get("cluster_config_args", {})),
        cluster_config_bool_args=list(data.get("cluster_config_bool_args", [])),
        host_config_args=dict(data.get("host_config_args", {})),
        host_config_bool_args=list(data.get("host_config_bool_args", [])),
        host_config_mount_local_path=list(
            data.get("host_config_mount_local_path", [])
        ),
        mtt_args=dict(data.get("mtt_args", {})),
        mtt_bool_args=list(data.get("mtt_bool_args", [])),
        image_name=image_name,
        tag=tag,
    )

  def ToDockerComposeEnvVars(self) -> dict[str, str]:
    """Returns environment variables dictionary for Docker Compose."""
    return dict(self.docker_compose_env)

  def ToMttFlags(self) -> list[str]:
    """Assembles extra CLI flags not in lab_config.proto."""
    flags: list[str] = []
    for k, v in self.mtt_args.items():
      if v is None or (isinstance(v, str) and not v):
        flags.append(f"--{k}=")
      else:
        flags.append(f"--{k}={v}")

    resolved_bools = _ResolveBoolArgs(self.mtt_bool_args)
    for bflag in resolved_bools:
      flags.append(f"--{bflag}")

    return flags

  def ToLabConfigProto(self) -> lab_config_pb2.LabConfig:
    """Converts flattened ConfigDTO into structured LabConfig proto message."""
    # 1. Prepare extra_docker_args from mtt_docker_env + server opts
    merged_docker_env = dict(self.mtt_docker_env)

    if self.lab_server_opts and "LAB_SERVER_OPTS" not in merged_docker_env:
      merged_docker_env["LAB_SERVER_OPTS"] = _FormatJavaServerOpts(
          self.lab_server_opts
      )

    if self.olc_server_opts and "OLC_SERVER_OPTS" not in merged_docker_env:
      merged_docker_env["OLC_SERVER_OPTS"] = _FormatJavaServerOpts(
          self.olc_server_opts
      )

    formatted_docker_args: list[str] = []
    if merged_docker_env:
      for opts_key in ["LAB_SERVER_OPTS", "OLC_SERVER_OPTS"]:
        if opts_key in merged_docker_env:
          formatted_docker_args.append(
              f'-e {opts_key}="{merged_docker_env[opts_key]}"'
          )
      for k, v in merged_docker_env.items():
        if k not in ["LAB_SERVER_OPTS", "OLC_SERVER_OPTS"]:
          formatted_docker_args.append(f'-e {k}="{v}"')

    # 2. Build HostConfig proto
    host_config_pb = lab_config_pb2.HostConfig()
    _ApplyDictToMessage(
        host_config_pb,
        self.host_config_args,
        skip_fields=("extra_docker_args", "mount_local_paths"),
    )
    _ApplyBoolFlagsToMessage(host_config_pb, self.host_config_bool_args)

    if self.host_config_mount_local_path:
      host_config_pb.mount_local_paths.extend(self.host_config_mount_local_path)

    existing_docker_args = self.host_config_args.get("extra_docker_args", [])
    if isinstance(existing_docker_args, (list, tuple)):
      formatted_docker_args.extend(existing_docker_args)
    if formatted_docker_args:
      host_config_pb.extra_docker_args.extend(formatted_docker_args)

    # 3. Build ClusterConfig proto
    cluster_config_pb = lab_config_pb2.ClusterConfig()
    _ApplyDictToMessage(
        cluster_config_pb,
        self.cluster_config_args,
        skip_fields=("host_configs", "mount_local_paths", "extra_docker_args"),
    )
    _ApplyBoolFlagsToMessage(cluster_config_pb, self.cluster_config_bool_args)
    # An all-default submessage serializes to an empty mapping, which the
    # strictyaml lab config schema rejects. Omit empty levels instead: a
    # controller legitimately has no host config, and a node config may carry
    # only docker_compose_env or mtt_args.
    if host_config_pb.ListFields():
      cluster_config_pb.host_configs.append(host_config_pb)

    # 4. Build LabConfig proto
    lab_config_pb = lab_config_pb2.LabConfig()
    _ApplyDictToMessage(
        lab_config_pb,
        self.lab_config_args,
        skip_fields=("cluster_configs",),
    )
    _ApplyBoolFlagsToMessage(lab_config_pb, self.lab_config_bool_args)
    if cluster_config_pb.ListFields():
      lab_config_pb.cluster_configs.append(cluster_config_pb)

    return lab_config_pb


class _ConfigLoader:
  """Orchestrates Jinja2 rendering with explicit scope parameters.

  Attributes:
    manifest_dir: Base directory containing manifest files.
    service_account_key_path: Path to service account key file specified in
      manifest.
    configs: Dictionary mapping scope name ('tenant', 'pool', 'node') to parsed
      configuration dictionary.
  """

  def __init__(
      self,
      manifest_dir: str,
      param_manager_client: Optional[
          gcp_param_manager.GcpParamManagerClient
      ] = None,
      service_account_key_path: Optional[str] = None,
  ):
    self.manifest_dir = manifest_dir
    self._param_manager_client = param_manager_client
    self.service_account_key_path = service_account_key_path
    self.configs: dict[str, dict[str, Any]] = {}

  @classmethod
  def FromManifest(
      cls,
      manifest_path: str,
  ) -> "_ConfigLoader":
    """Instantiates _ConfigLoader from manifest.yaml, validating service_account_key_path."""
    abs_manifest_path = os.path.abspath(manifest_path)
    if not os.path.exists(abs_manifest_path):
      raise FileNotFoundError(f"Manifest file not found: {abs_manifest_path}")

    with open(abs_manifest_path, "r", encoding="utf-8") as f:
      content = f.read()

    manifest_dir = os.path.dirname(abs_manifest_path)
    uses_param_manager = (
        "param_manager(" in content or "param_manager " in content
    )

    param_manager_client = None
    key_path = None
    if uses_param_manager:
      match = re.search(
          r"^\s*service_account_key_path:\s*['\"]?(.*?)['\"]?\s*$",
          content,
          re.MULTILINE,
      )
      key_path = match.group(1).strip() if match else None
      if not key_path:
        raise ValueError(
            "Manifest uses param_manager() but service_account_key_path is"
            f" missing in {abs_manifest_path}."
        )
      if not os.path.isabs(key_path):
        key_path = os.path.normpath(os.path.join(manifest_dir, key_path))
      if not os.path.exists(key_path):
        raise FileNotFoundError(
            "Service account key file specified in manifest not found:"
            f" {key_path}"
        )
      param_manager_client = (
          gcp_param_manager.GcpParamManagerClient.FromServiceAccountKeyFile(
              key_path
          )
      )

    return cls(
        manifest_dir=manifest_dir,
        param_manager_client=param_manager_client,
        service_account_key_path=key_path,
    )

  @classmethod
  def FromServiceAccountKeyFile(
      cls,
      manifest_dir: str,
      service_account_key_path: str,
  ) -> "_ConfigLoader":
    """Instantiates _ConfigLoader with GCP Parameter Manager client from service account key."""
    client = gcp_param_manager.GcpParamManagerClient.FromServiceAccountKeyFile(
        service_account_key_path
    )
    return cls(manifest_dir, client)

  @classmethod
  def Default(
      cls,
      manifest_dir: str,
  ) -> "_ConfigLoader":
    """Instantiates _ConfigLoader with default ADC GCP Parameter Manager client."""
    client = gcp_param_manager.GcpParamManagerClient.FromCredentials()
    return cls(manifest_dir, client)

  @jinja2.pass_context
  def ParamManager(
      self,
      context: jinja2.runtime.Context,
      param_version_path: str,
      scope: Union[_ConfigScope, str],
  ) -> dict[str, Any]:
    """Jinja2 helper to fetch, render, and register a GCP Parameter Manager configuration.

    Args:
      context: Active Jinja2 execution context.
      param_version_path: Parameter version resource name path.
      scope: Explicit scope (_ConfigScope enum or 'tenant', 'pool', 'node').

    Returns:
      Parsed dictionary.

    Raises:
      RuntimeError: If GcpParamManagerClient is not configured.
    """
    if self._param_manager_client is None:
      raise RuntimeError(
          "GcpParamManagerClient is not configured. A valid service account key"
          " file must be specified in manifest.yaml to use param_manager()."
      )

    scope_name = (
        _ConfigScope(scope).value if isinstance(scope, str) else scope.value
    )
    payload_str = self._param_manager_client.FetchUnformatted(
        param_version_path
    )

    raw_data: dict[str, Any] = {}
    try:
      raw_data = yaml.safe_load(payload_str) or {}
    except Exception:  
      pass

    temp_context = context.get_all()
    if raw_data:
      temp_context[scope_name] = raw_data

    template = context.environment.from_string(payload_str)
    rendered = template.render(temp_context)
    data = yaml.safe_load(rendered) or {}

    self.configs[scope_name] = data
    context.environment.globals[scope_name] = data
    return data


class _NodeConfigManager:
  """Manager for resolving, merging, and materializing node configurations.

  Attributes:
    loader: _ConfigLoader instance used for template resolution.
  """

  def __init__(self, loader: Optional[_ConfigLoader] = None):
    self.loader = loader

  def MergeScopes(self, configs: dict[str, dict[str, Any]]) -> ConfigDTO:
    """Merges configurations across Tenant -> Pool -> Node scopes.

    Precedence order (later overrides earlier):
      Tenant -> Pool -> Node

    Args:
      configs: Dictionary mapping scope name ('tenant', 'pool', 'node') to
        parsed configuration dict.

    Returns:
      Merged ConfigDTO.
    """
    scope_order = [
        _ConfigScope.TENANT.value,
        _ConfigScope.POOL.value,
        _ConfigScope.NODE.value,
    ]

    scope_dicts = [
        configs[s]
        for s in scope_order
        if s in configs and isinstance(configs[s], dict)
    ]

    merged_docker_compose_env: dict[str, str] = {}
    merged_mtt_docker_env: dict[str, str] = {}
    merged_lab_opts: dict[str, Any] = {}
    merged_olc_opts: dict[str, Any] = {}
    merged_lab_config_args: dict[str, Any] = {}
    merged_lab_config_bool_args: list[str] = []
    merged_cluster_config_args: dict[str, Any] = {}
    merged_cluster_config_bool_args: list[str] = []
    merged_host_config_args: dict[str, Any] = {}
    merged_host_config_bool_args: list[str] = []
    merged_mount_paths: list[str] = []
    merged_mtt_args: dict[str, Any] = {}
    merged_mtt_bool_args: list[str] = []
    image_name: Optional[str] = None
    tag: Optional[str] = None

    for d in scope_dicts:
      if "docker_compose_env" in d and isinstance(
          d["docker_compose_env"], dict
      ):
        merged_docker_compose_env.update(d["docker_compose_env"])

    for d in scope_dicts:
      if "mtt_docker_env" in d and isinstance(d["mtt_docker_env"], dict):
        merged_mtt_docker_env.update(d["mtt_docker_env"])

      # Dedicated lab_server_opts & olc_server_opts dicts
      if "lab_server_opts" in d and isinstance(d["lab_server_opts"], dict):
        merged_lab_opts.update(d["lab_server_opts"])
      if "olc_server_opts" in d and isinstance(d["olc_server_opts"], dict):
        merged_olc_opts.update(d["olc_server_opts"])

      # LabConfig args & bool args
      if "lab_config_args" in d and isinstance(d["lab_config_args"], dict):
        merged_lab_config_args.update(d["lab_config_args"])
      if "lab_config_bool_args" in d:
        bflags = d["lab_config_bool_args"]
        if isinstance(bflags, _ResetList):
          merged_lab_config_bool_args = list(bflags)
        elif isinstance(bflags, (list, tuple)):
          merged_lab_config_bool_args.extend(bflags)

      # ClusterConfig args & bool args
      if "cluster_config_args" in d and isinstance(
          d["cluster_config_args"], dict
      ):
        merged_cluster_config_args.update(d["cluster_config_args"])
      if "cluster_config_bool_args" in d:
        bflags = d["cluster_config_bool_args"]
        if isinstance(bflags, _ResetList):
          merged_cluster_config_bool_args = list(bflags)
        elif isinstance(bflags, (list, tuple)):
          merged_cluster_config_bool_args.extend(bflags)

      # HostConfig args & bool args
      if "host_config_args" in d and isinstance(d["host_config_args"], dict):
        merged_host_config_args.update(d["host_config_args"])
      if "host_config_bool_args" in d:
        bflags = d["host_config_bool_args"]
        if isinstance(bflags, _ResetList):
          merged_host_config_bool_args = list(bflags)
        elif isinstance(bflags, (list, tuple)):
          merged_host_config_bool_args.extend(bflags)

      # Mount local paths
      if "host_config_mount_local_path" in d:
        paths = d["host_config_mount_local_path"]
        if isinstance(paths, _ResetList):
          merged_mount_paths = list(paths)
        elif isinstance(paths, (list, tuple)):
          merged_mount_paths.extend(paths)

      # Extra passthrough mtt_args and mtt_bool_args
      if "mtt_args" in d and isinstance(d["mtt_args"], dict):
        merged_mtt_args.update(d["mtt_args"])
      if "mtt_bool_args" in d:
        extra_bools = d["mtt_bool_args"]
        if isinstance(extra_bools, _ResetList):
          merged_mtt_bool_args = list(extra_bools)
        elif isinstance(extra_bools, (list, tuple)):
          merged_mtt_bool_args.extend(extra_bools)

      if "image_name" in d and d["image_name"]:
        image_name = str(d["image_name"])
      if "tag" in d and d["tag"]:
        tag = str(d["tag"])
      if "image" in d and d["image"]:
        raw_image = str(d["image"])
        if ":" in raw_image:
          image_name, tag = raw_image.split(":", 1)
        else:
          image_name = raw_image

    if not image_name:
      image_name = DEFAULT_PARTNER_IMAGE_NAME
    if not tag:
      tag = DEFAULT_PARTNER_TAG

    return ConfigDTO(
        docker_compose_env=merged_docker_compose_env,
        mtt_docker_env=merged_mtt_docker_env,
        lab_server_opts=merged_lab_opts,
        olc_server_opts=merged_olc_opts,
        lab_config_args=merged_lab_config_args,
        lab_config_bool_args=_ResolveBoolArgs(merged_lab_config_bool_args),
        cluster_config_args=merged_cluster_config_args,
        cluster_config_bool_args=_ResolveBoolArgs(
            merged_cluster_config_bool_args
        ),
        host_config_args=merged_host_config_args,
        host_config_bool_args=_ResolveBoolArgs(merged_host_config_bool_args),
        host_config_mount_local_path=merged_mount_paths,
        mtt_args=merged_mtt_args,
        mtt_bool_args=_ResolveBoolArgs(merged_mtt_bool_args),
        image_name=image_name,
        tag=tag,
    )

  def ResolveFromManifest(
      self,
      manifest_path: str,
  ) -> ConfigDTO:
    """Renders entrypoint manifest and returns merged ConfigDTO.

    Args:
      manifest_path: Path to the entrypoint manifest file.

    Returns:
      Resolved ConfigDTO.

    Raises:
      FileNotFoundError: If the manifest file cannot be found.
    """
    abs_manifest_path = os.path.abspath(manifest_path)
    if not os.path.exists(abs_manifest_path):
      raise FileNotFoundError(f"Manifest file not found: {abs_manifest_path}")

    manifest_dir = os.path.dirname(abs_manifest_path)
    manifest_name = os.path.basename(abs_manifest_path)

    loader = _ConfigLoader.FromManifest(abs_manifest_path)

    env = jinja2.Environment(loader=jinja2.FileSystemLoader(manifest_dir))
    env.globals["param_manager"] = loader.ParamManager
    env.globals["hostname"] = socket.gethostname()

    template = env.get_template(manifest_name)
    _ = template.render()

    dto = self.MergeScopes(loader.configs)
    if (
        loader.service_account_key_path
        and "service_account_json_key_path" not in dto.mtt_args
    ):
      dto.mtt_args["service_account_json_key_path"] = (
          loader.service_account_key_path
      )
    return dto

  @staticmethod
  def MaterializeLabConfig(config_dto: ConfigDTO, target_path: str) -> None:
    """Materializes resolved ConfigDTO into a valid lab_config.yaml.

    lab_config.yaml is optional downstream (only workers consume it), so a DTO
    carrying no lab, cluster or host settings produces no file. Any stale file
    at target_path is removed so that a setting deleted upstream cannot
    survive in the runtime directory.

    Args:
      config_dto: Resolved configuration DTO.
      target_path: Destination path for lab_config.yaml.
    """
    lab_config_pb = config_dto.ToLabConfigProto()
    os.makedirs(os.path.dirname(os.path.abspath(target_path)), exist_ok=True)
    lab_config_dict = json_format.MessageToDict(
        lab_config_pb, preserving_proto_field_name=True
    )
    if not lab_config_dict:
      logger.info(
          "No lab, cluster or host settings resolved; skipping %s.",
          target_path,
      )
      if os.path.lexists(target_path):
        os.remove(target_path)
      return
    
    schema = lab_config._YAML_SCHEMA
    
    yaml_doc = syaml.as_document(lab_config_dict, schema=schema)
    with open(target_path, "w", encoding="utf-8") as f:
      f.write(yaml_doc.as_yaml())

  @staticmethod
  def MaterializeDockerComposeEnv(
      config_dto: ConfigDTO, target_path: str
  ) -> None:
    """Materializes environment variables into docker-compose.env.

    Args:
      config_dto: Resolved configuration DTO.
      target_path: Destination path for docker-compose.env.
    """
    os.makedirs(os.path.dirname(os.path.abspath(target_path)), exist_ok=True)
    with open(target_path, "w", encoding="utf-8") as f:
      for k, v in sorted(config_dto.ToDockerComposeEnvVars().items()):
        f.write(f'{k}="{v}"\n')

  @staticmethod
  def MaterializeMttFlags(config_dto: ConfigDTO, target_path: str) -> None:
    """Materializes target image_name, tag, and extra MTT flags into mtt_flags.yaml.

    Args:
      config_dto: Resolved configuration DTO.
      target_path: Destination path for mtt_flags.yaml.
    """
    flags_data = {
        "image_name": config_dto.image_name or "",
        "tag": config_dto.tag or "",
        "flags": config_dto.ToMttFlags(),
    }
    os.makedirs(os.path.dirname(os.path.abspath(target_path)), exist_ok=True)
    with open(target_path, "w", encoding="utf-8") as f:
      yaml.dump(flags_data, f, default_flow_style=False, sort_keys=False)

  @staticmethod
  def StoreNodeConfig(
      param_version_path: str,
      config_dto: ConfigDTO,
      client: gcp_param_manager.GcpParamManagerClient,
  ) -> str:
    """Serializes a ConfigDTO to YAML and stores it in GCP Parameter Manager.

    Args:
      param_version_path: Target parameter or version resource path.
      config_dto: ConfigDTO instance to store.
      client: GCP Parameter Manager client.

    Returns:
      Resource name of the created parameter version.
    """
    yaml_content = yaml.dump(
        config_dto.ToDict(), default_flow_style=False, sort_keys=False
    )
    return client.StoreUnformatted(param_version_path, yaml_content)


def _ResolveAndMaterializeFromManifest(
    manifest_path: str,
    var_config_dir: str,
) -> ConfigDTO:
  """Resolves multi-scope GCP configs from manifest and materializes them into var_config_dir."""
  manager = _NodeConfigManager()
  config_dto = manager.ResolveFromManifest(manifest_path)
  os.makedirs(var_config_dir, exist_ok=True)
  _NodeConfigManager.MaterializeLabConfig(
      config_dto, os.path.join(var_config_dir, "lab_config.yaml")
  )
  _NodeConfigManager.MaterializeDockerComposeEnv(
      config_dto, os.path.join(var_config_dir, "docker-compose.env")
  )
  _NodeConfigManager.MaterializeMttFlags(
      config_dto, os.path.join(var_config_dir, "mtt_flags.yaml")
  )
  return config_dto


def _CopyMaterializedConfig(
    static_config_dir: str, var_config_dir: str
) -> None:
  """Copies materialized configuration files from static source to runtime directory.

  Any destination file with the same name is replaced by the static version.
  The destination is unlinked first so that the copy also succeeds when the
  previous file was written with read-only permissions.

  Args:
    static_config_dir: Source directory holding materialized static configs.
    var_config_dir: Destination runtime configuration directory.
  """
  os.makedirs(var_config_dir, exist_ok=True)
  for filename in ("lab_config.yaml", "docker-compose.env", "mtt_flags.yaml"):
    src_file = os.path.join(static_config_dir, filename)
    dst_file = os.path.join(var_config_dir, filename)
    if not os.path.exists(src_file):
      if os.path.lexists(dst_file):
        os.remove(dst_file)
      continue
    node_permissions.CopyFileWithMode(
        src_file, dst_file, node_permissions.BASE_FILE_MODE
    )


# Name of the secrets subdirectory under static_dir, bind-mounted into the
# tunnel containers at /etc/secrets.
_SECRETS_DIR_NAME = "secrets"

# Env vars that describe *this host* rather than the pool, so they cannot come
# from the shared Parameter Manager payload and must be injected locally.
_HOST_SPECIFIC_ENV_KEYS = (
    "SECRETS_DIR",
    "MTT_GID",
    "OTEL_RESOURCE_ATTRIBUTES",
)


def _InjectHostSpecificEnv(static_dir: str, var_config_dir: str) -> None:
  """Appends host-specific variables to the materialized docker-compose.env.

  Both values follow --static_dir, so neither can be baked in at `init`:

    - SECRETS_DIR is the *host* side of the bind mount the compose files
      declare as `${SECRETS_DIR:-/etc/mtt/secrets}`. Nothing wrote it before,
      so a node provisioned with a non-default --static_dir mounted a
      directory Docker silently created empty, and the containers found no
      service account key.
    - MTT_GID is the group that owns those secrets, passed to `group_add` so
      that non-root container users (the otel collector runs as uid 10001)
      can read a group-readable key.
    - OTEL_RESOURCE_ATTRIBUTES sets `host.name=<hostname>` on non-GCP (lab)
      hosts so the OTel Collector maps the resource to `generic_node` with
      `resource.labels.node_id` equal to the hostname. On GCE it is omitted
      so the collector's `gcp` resource detector provides the GCE metadata.

  Args:
    static_dir: Static host configuration root.
    var_config_dir: Destination runtime configuration directory.
  """
  target_path = os.path.join(var_config_dir, "docker-compose.env")
  values = {"SECRETS_DIR": os.path.join(static_dir, _SECRETS_DIR_NAME)}
  gid = node_permissions.DeriveGroupGid(static_dir)
  if gid is not None:
    values["MTT_GID"] = str(gid)
  if not host_env.IsGceInstance():
    values["OTEL_RESOURCE_ATTRIBUTES"] = f"host.name={socket.gethostname()}"

  lines: list[str] = []
  if os.path.exists(target_path):
    with open(target_path, "r", encoding="utf-8") as f:
      # Drop any inherited copy so a re-materialization does not accumulate
      # stale duplicates; the last assignment would win, but the file would
      # grow on every run and mislead anyone reading it.
      lines = [
          line
          for line in f.read().splitlines()
          if line.split("=", 1)[0].strip() not in _HOST_SPECIFIC_ENV_KEYS
      ]

  for key, value in values.items():
    lines.append(f'{key}="{value}"')
  with open(target_path, "w", encoding="utf-8") as f:
    f.write("\n".join(lines) + "\n")


# Docker named volume created by the JuiceFS deployment (see
# deployment/juicefs/jfs_client.sh). Its presence is the whole signal that a
# persistent cache is available on this host.
_JFS_CACHE_VOLUME = "mtt-jfs"

# The only token MTT node owns. It is derived from the live host on every
# materialization, so an inherited copy is always dropped first. Any other
# `--bind_jfs_volume` token is the user's and is passed through untouched.
_JFS_BIND_FLAG = f"--bind_jfs_volume={_JFS_CACHE_VOLUME}"
_BIND_JFS_VOLUME_FLAG_NAME = "bind_jfs_volume"
_ENABLE_PERSISTENT_CACHE_FLAG_NAME = "enable_persistent_cache"


def _HasCacheVolume() -> bool:
  """Reports whether the JuiceFS cache volume exists on this host."""
  try:
    context = command_util.DockerContext(
        command_util.CommandContext(), login=False
    )
    res = context.Run(
        ["volume", "inspect", _JFS_CACHE_VOLUME],
        raise_on_failure=False,
        timeout=30,
    )
  except Exception:  
    # An unavailable Docker daemon must never be the reason a node fails to
    # materialize. The node runs without a cache instead.
    logger.warning(
        "Could not probe for the %s volume; assuming no persistent cache.",
        _JFS_CACHE_VOLUME,
        exc_info=True,
    )
    return False
  return res.return_code == 0


def _InjectHostSpecificFlags(var_config_dir: str, role: NodeRole) -> None:
  """Adds the persistent cache flags derived from this host's Docker volumes.

  The cache is backed by the `mtt-jfs` Docker volume, which the JuiceFS
  deployment creates and removes independently of MTT node. That makes the
  bind host state, not pool state, so it is resolved here rather than recorded
  at `init`/`join`: a bind frozen at provisioning time would outlive the
  volume, and Docker silently auto-creates a missing named volume, leaving the
  node running against an empty local directory that only looks like the
  shared cache.

  MTT node stays transparent to user-authored flags. It only removes the exact
  `--bind_jfs_volume=mtt-jfs` token it owns, and only adds flags when the user
  has not expressed a choice:

  - Both roles: `--bind_jfs_volume=mtt-jfs` is added if the volume exists and
    the user has not bound another volume.
  - Worker: `--enable_persistent_cache` is added alongside that bind, unless it
    is already present.
  - Controller: `--enable_persistent_cache` controls OLC behavior, not local
    caching, so it is never added or removed here.

  Args:
    var_config_dir: Destination runtime configuration directory.
    role: Role of the node being materialized.
  """
  target_path = os.path.join(var_config_dir, "mtt_flags.yaml")
  if not os.path.exists(target_path):
    return
  with open(target_path, "r", encoding="utf-8") as f:
    flags_data = yaml.safe_load(f) or {}
  if not isinstance(flags_data, dict):
    return

  flags = [
      str(flag)
      for flag in flags_data.get("flags") or []
      if str(flag).strip() != _JFS_BIND_FLAG
  ]
  flag_names = {_ParseFlagName(flag) for flag in flags}
  if _BIND_JFS_VOLUME_FLAG_NAME in flag_names:
    logger.info(
        "mtt_flags.yaml already binds a volume; not binding %s.",
        _JFS_CACHE_VOLUME,
    )
  elif _HasCacheVolume():
    logger.info("Found Docker volume %s; binding it.", _JFS_CACHE_VOLUME)
    flags.append(_JFS_BIND_FLAG)
    if (
        role == NodeRole.WORKER
        and _ENABLE_PERSISTENT_CACHE_FLAG_NAME not in flag_names
    ):
      flags.append(f"--{_ENABLE_PERSISTENT_CACHE_FLAG_NAME}")

  flags_data["flags"] = flags
  with open(target_path, "w", encoding="utf-8") as f:
    yaml.dump(flags_data, f, default_flow_style=False, sort_keys=False)


# lab_config.proto fields that hand control of the container version to the
# legacy MTT daemon. They are valid proto fields at the lab, cluster and host
# levels, so they can be introduced from any configuration scope.
_FORBIDDEN_LAB_CONFIG_FIELDS = ("enable_autoupdate", "enable_ui_update")

# Flag names that must never reach the `flags:` list of mtt_flags.yaml, mapped
# to the reason reported to the operator.
_FORBIDDEN_MTT_FLAGS = {
    "enable_auto_update": (
        "the legacy MTT daemon replaces the running container behind the"
        " node's back, which invalidates the pinned digest"
    ),
    "enable_ui_update": (
        "the legacy MTT daemon replaces the running container behind the"
        " node's back, which invalidates the pinned digest"
    ),
    "force_update": (
        "a forced pull cannot change a digest-pinned version, it only makes"
        " every start depend on the registry, and it fails outright for"
        " locally built images"
    ),
    "tag": (
        "image identity is owned by the top-level 'image_name' and 'tag' keys"
        " of mtt_flags.yaml and must not be passed as an extra flag"
    ),
    "image_name": (
        "image identity is owned by the top-level 'image_name' and 'tag' keys"
        " of mtt_flags.yaml and must not be passed as an extra flag"
    ),
}


def _IterLabConfigScopes(
    lab_config_data: Any,
) -> Iterator[tuple[str, dict[str, Any]]]:
  """Yields (scope_name, mapping) for every level of a lab config document."""
  if not isinstance(lab_config_data, dict):
    return
  yield "lab", lab_config_data
  for cluster in lab_config_data.get("cluster_configs") or []:
    if not isinstance(cluster, dict):
      continue
    yield "cluster", cluster
    for host in cluster.get("host_configs") or []:
      if isinstance(host, dict):
        yield "host", host


def _FindForbiddenLabConfigFields(lab_config_path: str) -> list[str]:
  """Returns descriptions of legacy autoupdate fields enabled in a lab config.

  Args:
    lab_config_path: Path to a materialized lab_config.yaml.

  Returns:
    Human readable descriptions of each enabled forbidden field, empty if none.
  """
  if not os.path.exists(lab_config_path):
    return []
  with open(lab_config_path, "r", encoding="utf-8") as f:
    lab_config_data = yaml.safe_load(f)

  violations: list[str] = []
  for scope, mapping in _IterLabConfigScopes(lab_config_data):
    for field in _FORBIDDEN_LAB_CONFIG_FIELDS:
      if field in mapping and _CoerceBool(mapping[field]):
        violations.append(f"{field} (enabled at {scope} level)")
  return violations


def _ParseFlagName(flag: str) -> str:
  """Extracts the bare flag name from a `--name[=value]` token."""
  token = flag.strip()
  if not token.startswith("--"):
    return ""
  return token[2:].split("=", 1)[0].strip()


def _FindForbiddenMttFlags(mtt_flags_path: str) -> list[str]:
  """Returns descriptions of forbidden entries in an mtt_flags.yaml flag list.

  Args:
    mtt_flags_path: Path to a materialized mtt_flags.yaml.

  Returns:
    Human readable descriptions of each forbidden flag, empty if none.
  """
  if not os.path.exists(mtt_flags_path):
    return []
  with open(mtt_flags_path, "r", encoding="utf-8") as f:
    flags_data = yaml.safe_load(f) or {}
  if not isinstance(flags_data, dict):
    return []

  violations: list[str] = []
  for flag in flags_data.get("flags") or []:
    reason = _FORBIDDEN_MTT_FLAGS.get(_ParseFlagName(str(flag)))
    if reason:
      violations.append(f"--{_ParseFlagName(str(flag))} ({reason})")
  return violations


def _ValidateMaterializedConfig(var_config_dir: str) -> None:
  """Rejects materialized configuration that would defeat digest pinning.

  Runs against the generated files rather than the in-memory ConfigDTO so that
  the GCP-resolved and self-managed static paths are both covered: the static
  path copies operator-authored files verbatim and never builds a DTO.

  Args:
    var_config_dir: Runtime configuration directory holding the generated
      lab_config.yaml and mtt_flags.yaml.

  Raises:
    ConfigValidationError: If any forbidden field or flag is present.
  """
  violations = _FindForbiddenLabConfigFields(
      os.path.join(var_config_dir, "lab_config.yaml")
  )
  violations += _FindForbiddenMttFlags(
      os.path.join(var_config_dir, "mtt_flags.yaml")
  )
  if not violations:
    return

  raise ConfigValidationError(
      f"Materialized configuration in {var_config_dir} contains settings that"
      " MTT node does not support:\n"
      + "\n".join(f"  - {v}" for v in violations)
      + "\nRemove these from the node configuration source and retry."
  )


def MaterializeNodeConfig(
    static_dir: str = "/etc/mtt",
    var_config_dir: str = "/var/lib/mttnode/config",
    *,
    role: NodeRole,
) -> None:
  """Materializes node configuration into var_config_dir from static_dir.

  Contract:
    - Root static dir: <static_dir> (e.g. /etc/mtt).
    - GCP-Managed: <static_dir>/manifest.yaml. If present, GCP configuration
      always takes precedence by design, resolving multi-scope parameters from
      GCP Parameter Manager.
    - Non-GCP/Static: <static_dir>/config/. Requires mtt_flags.yaml for both
      roles; lab_config.yaml is optional and only consumed by workers.
    - Destination: <var_config_dir> (e.g. /var/lib/mttnode/config/).
    - Both branches validate the materialized files before returning, so a
      configuration that would hand container version control to the legacy
      MTT daemon fails here rather than at container start.

  Args:
    static_dir: Static host configuration root (e.g. /etc/mtt).
    var_config_dir: Destination runtime directory (e.g.
      /var/lib/mttnode/config).
    role: Role of the node being materialized. It decides whether the
      persistent cache flag follows the `mtt-jfs` bind (worker) or is left to
      the user (controller).

  Raises:
    FileNotFoundError: If neither manifest.yaml nor a static config directory
      is found, or if the static config directory lacks mtt_flags.yaml.
    ConfigValidationError: If the materialized configuration contains settings
      MTT node does not support.
  """
  manifest_path = os.path.join(static_dir, "manifest.yaml")
  static_config_dir = os.path.join(static_dir, "config")

  # 1. GCP Manifest Check (GCP configuration always takes precedence).
  if os.path.exists(manifest_path):
    logger.info(
        "Found manifest at %s; resolving remote parameters from GCP Parameter"
        " Manager (GCP takes precedence).",
        manifest_path,
    )
    config_dto = _ResolveAndMaterializeFromManifest(
        manifest_path, var_config_dir
    )
    logger.info(
        "Resolved GCP configuration: image=%s, tag=%s, lab_name=%s",
        config_dto.image_name,
        config_dto.tag,
        config_dto.lab_config_args.get("lab_name"),
    )
    _InjectHostSpecificEnv(static_dir, var_config_dir)
    _InjectHostSpecificFlags(var_config_dir, role)
    _ValidateMaterializedConfig(var_config_dir)
    return

  # 2. Non-GCP Static Config Check
  if os.path.exists(static_config_dir):
    mtt_flags_file = os.path.join(static_config_dir, "mtt_flags.yaml")
    if not os.path.exists(mtt_flags_file):
      raise FileNotFoundError(
          "Static config directory is incomplete. mtt_flags.yaml is required"
          " for both controller and worker nodes, but was not found in:"
          f" {static_config_dir}"
      )
    logger.info(
        "No manifest found; copying static configuration files from %s to %s.",
        static_config_dir,
        var_config_dir,
    )
    _CopyMaterializedConfig(static_config_dir, var_config_dir)
    _InjectHostSpecificEnv(static_dir, var_config_dir)
    _InjectHostSpecificFlags(var_config_dir, role)
    _ValidateMaterializedConfig(var_config_dir)
    return

  # 3. Neither Found
  raise FileNotFoundError(
      f"No configuration source found in {static_dir}. Expected either"
      f" manifest file ({manifest_path}) or static config directory"
      f" ({static_config_dir})."
  )


__all__ = [
    "ConfigDTO",
    "ConfigValidationError",
    "MaterializeNodeConfig",
    "NodeRole",
]
