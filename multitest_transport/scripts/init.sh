#!/bin/bash
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

set -e

# LINT.IfChange

# TODO Better differentiate different running mode
IS_CONTROLLER="false"
if [[ -z "${MTT_CONTROL_SERVER_URL}" ]]; then
  IS_CONTROLLER="true"
fi

# --- Environment Variables from MTT CLI ---
# Enables persistent caching if set to 'true'.
ENABLE_PERSISTENT_CACHE="${ENABLE_PERSISTENT_CACHE:-}"
# Proxy settings for FTP.
FTP_PROXY="${FTP_PROXY:-}"
# Proxy settings for HTTP.
HTTP_PROXY="${HTTP_PROXY:-}"
# Proxy settings for HTTPS.
HTTPS_PROXY="${HTTPS_PROXY:-}"
# Flag to indicate if the node is based on OmniLab.
IS_OMNILAB_BASED="${IS_OMNILAB_BASED:-}"
# gRPC port for the Labconsole server.
LABCONSOLE_SERVER_GRPC_PORT="${LABCONSOLE_SERVER_GRPC_PORT:-8080}"
# REST port for the Labconsole server.
LABCONSOLE_SERVER_REST_PORT="${LABCONSOLE_SERVER_REST_PORT:-9000}"
# Port for the Lab Console UI.
LAB_CONSOLE_PORT="${LAB_CONSOLE_PORT:-4200}"
# Maximum number of local virtual devices to allocate.
MAX_LOCAL_VIRTUAL_DEVICES="${MAX_LOCAL_VIRTUAL_DEVICES:-0}"
# Maximum number of orchestration-managed virtual devices to allocate.
MAX_ORCHESTRATION_VIRTUAL_DEVICES="${MAX_ORCHESTRATION_VIRTUAL_DEVICES:-0}"
# The version of the MTT CLI.
MTT_CLI_VERSION="${MTT_CLI_VERSION:-}"
# gRPC port for the Config Service.
MTT_CONFIG_SERVICE_GRPC_PORT="${MTT_CONFIG_SERVICE_GRPC_PORT:-8081}"
# Local storage directory for the Config Service.
MTT_CONFIG_SERVICE_LOCAL_STORAGE_DIR="${MTT_CONFIG_SERVICE_LOCAL_STORAGE_DIR:-/data/config_service}"
# Storage type for the Config Service (e.g., LOCAL_FILE).
MTT_CONFIG_SERVICE_STORAGE_TYPE="${MTT_CONFIG_SERVICE_STORAGE_TYPE:-LOCAL_FILE}"
# Flag to indicate if the lab server should connect to the config server.
MTT_CONNECT_LABSERVER_TO_CONFIG_SERVER="${MTT_CONNECT_LABSERVER_TO_CONFIG_SERVER:-false}"
# URL of the file server on the control server.
MTT_CONTROL_FILE_SERVER_URL="${MTT_CONTROL_FILE_SERVER_URL:-}"
# Port bound by the MTT control server.
MTT_CONTROL_SERVER_PORT="${MTT_CONTROL_SERVER_PORT:-8000}"
# URL of the MTT control server.
MTT_CONTROL_SERVER_URL="${MTT_CONTROL_SERVER_URL:-}"
# Flag to indicate if the Config Service is enabled.
MTT_ENABLE_CONFIG_SERVICE="${MTT_ENABLE_CONFIG_SERVICE:-}"
# Flag to enable the Lab Console UI.
MTT_ENABLE_LAB_CONSOLE_UI="${MTT_ENABLE_LAB_CONSOLE_UI:-true}"
# Proxy settings for no_proxy.
NO_PROXY="${NO_PROXY:-}"
# Port for the OLC server.
OLC_SERVER_PORT="${OLC_SERVER_PORT:-7030}"
# Usage metrics flag for Omni mode.
OMNI_MODE_USAGE="${OMNI_MODE_USAGE:-}"
# Operation mode of the node (e.g., standalone, on_premise).
OPERATION_MODE="${OPERATION_MODE:-}"
# Directory for persistent cache inside the container.
PERSISTENT_CACHE_DIR="${PERSISTENT_CACHE_DIR:-}"
# List of remote virtual devices.
REMOTE_VIRTUAL_DEVICES="${REMOTE_VIRTUAL_DEVICES:-}"
# Path to TradeFed global config. Some how it is used all over the place.
TF_GLOBAL_CONFIG_PATH="${TF_GLOBAL_CONFIG_PATH:-}"
# Flag to use DCon XDS address.
USE_DCON_XDS_ADDRESS="${USE_DCON_XDS_ADDRESS:-}"

# --- Environment Variables from Dockerfile ---
# Path to Google application credentials.
GOOGLE_APPLICATION_CREDENTIALS="${GOOGLE_APPLICATION_CREDENTIALS:-/tmp/keyfile/key.json}"
# Path to TradeFed host config file.
MTT_CUSTOM_TF_CONFIG_FILE="${MTT_CUSTOM_TF_CONFIG_FILE:-/data/host-config.xml}"
# Google OAuth2 client ID.
MTT_GOOGLE_OAUTH2_CLIENT_ID="${MTT_GOOGLE_OAUTH2_CLIENT_ID:-}"
# Google OAuth2 client secret.
MTT_GOOGLE_OAUTH2_CLIENT_SECRET="${MTT_GOOGLE_OAUTH2_CLIENT_SECRET:-}"
# Directory for MTT logs.
MTT_LOG_DIR="${MTT_LOG_DIR:-/data/log}"
# Directory for MTT work files.
MTT_MH_WORK_DIR="${MTT_MH_WORK_DIR:-/data/mh}"
# Path to report generator jar.
MTT_REPORT_GENERATOR_JAR="${MTT_REPORT_GENERATOR_JAR:-/merge_report_generator/report_generator_deploy.jar}"
# Log level for MTT server.
MTT_SERVER_LOG_LEVEL="${MTT_SERVER_LOG_LEVEL:-info}"
# Base storage path for MTT data.
MTT_STORAGE_PATH="${MTT_STORAGE_PATH:-/data}"
# Directory for temporary test files.
MTT_TEST_WORK_DIR="${MTT_TEST_WORK_DIR:-/data/tmp}"
# Flag to use host adb.
MTT_USE_HOST_ADB="${MTT_USE_HOST_ADB:-}"
# Version of MTT.
MTT_VERSION="${MTT_VERSION:-dev}"

# --- Local Variables ---
# ATS lab server type.
ATS_LAB_SERVER_TYPE="on-prem"

# ATS worker gRPC port.
ATS_WORKER_GRPC_PORT="${ATS_WORKER_GRPC_PORT:-7031}"

# Bind to IPv4 only because endpoints service cannot convert IPv6 addresses to
# URLs correctly.
BIND_ADDRESS="0.0.0.0"

# Enable controller and worker features by default.
ENABLE_CONTROLLER_FEATURES="true"
ENABLE_WORKER_FEATURES="true"

# Default to file service only mode.
FILE_SERVICE_ONLY="true"

# Directory for MTT control server logs.
MTT_CONTROL_SERVER_LOG_DIR="${MTT_LOG_DIR}/server"

# Directory for Config Service logs.
MTT_CONFIG_SERVICE_LOG_DIR="${MTT_LOG_DIR}/config_service"

# Credential type for the OLC server.
OLCS_CREDENTIAL_TYPE="no_credential"

# SQL database URI.
SQL_DATABASE_URI=""

# The custom script that is executed after basic environment is set up and
# before any services are started.
readonly PRERUN_SCRIPT_PATH="/mtt/scripts/init_pre_run.sh"

# The custom script that is executed only before the lab server or TF are
# started, and after all other services are started.
# TODO Move the post-run script to run after lab server startup.
readonly POSTRUN_SCRIPT_PATH="/mtt/scripts/init_post_run.sh"

readonly MYSQL_SCRIPT_PATH="/mtt/scripts/mysql.sh"

# --- Helper Functions ---

function configure_operation_mode {
  # Standalone mode: mtt start
  # Worker mode: mtt start --mtt_control_server_url=... --operation_mode=on_premise
  # Controller mode: mtt start --operation_mode=on_premise
  # If the controller URL is set, we are in worker mode.
  if [[ ! -z "${MTT_CONTROL_SERVER_URL}" ]]; then
    # Disable controller features in worker mode.
    ENABLE_CONTROLLER_FEATURES="false"

    # Only initialize the ATS file server if the controller URL is set.
    OLC_SERVER_GRPC_TARGET="$(echo ${MTT_CONTROL_SERVER_URL} | sed 's,^\([^:/]\+://\)\?\([^:/]\+\)\(:\([0-9]\{1\,5\}\)\)\?\+.*$,\2,g'):${ATS_WORKER_GRPC_PORT}"
    local remotes_control_server_port="$(echo ${MTT_CONTROL_SERVER_URL} | sed 's,^\([^:/]\+://\)\?\([^:/]\+:\)\(\([0-9]\{1\,5\}\)\)\?\+.*$,\3,g')"
    local ats_file_server_port="$((${remotes_control_server_port}+6))"
    ATS_FILE_SERVER="$(echo ${MTT_CONTROL_SERVER_URL} | sed 's,^\(\([^:/]\+://\)\?\([^:/]\+\)\)\(:\([0-9]\{1\,5\}\)\)\?\+.*$,\1,g'):${ats_file_server_port}"
  fi

  # If we are in on-premise mode but the controller URL is not set, we are in
  # controller mode.
  if [[ -z "${MTT_CONTROL_SERVER_URL}" ]] && [[ "${OPERATION_MODE}" == "on_premise" ]]; then
    # Disable worker features in controller mode.
    ENABLE_WORKER_FEATURES="false"
  fi
}

function import_ca_certificates {
  # Add extra CA certificates.
  local file
  for file in /usr/local/share/ca-certificates/*
  do
    [[ -f "${file}" ]] || continue
    chmod 644 "${file}"
    echo yes | keytool -importcert\
        -cacerts\
        -trustcacerts\
        -file "${file}"\
        -alias $(basename -- "${file}")\
        -storepass "changeit"
  done
  update-ca-certificates
}

function set_java_proxy {
  local host=$(echo ${2} | sed "s,^\(https\?://\)\?\([^:/]\+\)\(:\([0-9]\+\)\)\?\+.*$,\2,g")
  local port=$(echo ${2} | sed "s,^\(https\?://\)\?\([^:/]\+\)\(:\([0-9]\+\)\)\?\+.*$,\4,g")
  export JAVA_TOOL_OPTIONS="${JAVA_TOOL_OPTIONS} -D${1}.proxyHost=${host} -D${1}.proxyPort=${port}"
}

function set_java_non_proxy {
  # Convert ${no_proxy} to java property. For example, "127.0.0.1,::1" => "127.0.0.1|[::1]".
  local hosts=$(echo -n "${1}" | awk 'BEGIN {RS=","} NR > 1 {printf "|"} {printf ($0 ~ /:/ ? "[%s]" : "%s"), $0}')
  export JAVA_TOOL_OPTIONS="${JAVA_TOOL_OPTIONS} -Dhttp.nonProxyHosts=${hosts}"
}

function configure_proxies {
  # Configure proxy settings for tools.
  [[ ! -z "${HTTP_PROXY}" ]] && set_java_proxy http ${HTTP_PROXY}
  [[ ! -z "${HTTPS_PROXY}" ]] && set_java_proxy https ${HTTPS_PROXY}
  [[ ! -z "${NO_PROXY}" ]] && set_java_non_proxy ${NO_PROXY}
  export HTTPLIB2_CA_CERTS=/etc/ssl/certs/ca-certificates.crt
}

function link_temporary_mounts {
  # Link temporarily mounted files/directories into the local file store
  mkdir -p "${MTT_STORAGE_PATH}/local_file_store"
  find "${MTT_STORAGE_PATH}/local_file_store" -xtype l -delete
  [[ -d /tmp/.mnt ]] && find /tmp/.mnt -mindepth 1 -maxdepth 1 \
    -exec ln -sf {} "${MTT_STORAGE_PATH}/local_file_store" \;
}

function run_prerun_hook {
  cd /mtt

  if [[ -f "${PRERUN_SCRIPT_PATH}" ]]; then
    source ${PRERUN_SCRIPT_PATH}
  fi

  if [[ -f "${MYSQL_SCRIPT_PATH}" ]]; then
    source ${MYSQL_SCRIPT_PATH}
  fi
}

function init_omnilab_workdir {
  # Initialize MTT work directory for OmniLab based setups.
  if [[ ! -z "${IS_OMNILAB_BASED}" ]]
  then
    rm -rf "${MTT_MH_WORK_DIR}"
    mkdir -p "${MTT_MH_WORK_DIR}"
  fi
}

function start_config_service {
  echo "Starting Config Service on port ${MTT_CONFIG_SERVICE_GRPC_PORT}..."
  local -a config_service_args=(
    --config_service_grpc_port="${MTT_CONFIG_SERVICE_GRPC_PORT}"
    --config_service_storage_type="${MTT_CONFIG_SERVICE_STORAGE_TYPE}"
  )
  if [[ "${MTT_CONFIG_SERVICE_STORAGE_TYPE}" == "LOCAL_FILE" ]]; then
    mkdir -p "${MTT_CONFIG_SERVICE_LOCAL_STORAGE_DIR}"
    config_service_args+=(--config_service_local_storage_dir="${MTT_CONFIG_SERVICE_LOCAL_STORAGE_DIR}")
  fi
  # TODO: add flag for sql config service storage type.

  mkdir -p "${MTT_CONFIG_SERVICE_LOG_DIR}"
  java -XX:+HeapDumpOnOutOfMemoryError \
      -jar /deviceinfra/device_config_server_deploy.jar \
      "${config_service_args[@]}" \
      &> "${MTT_CONFIG_SERVICE_LOG_DIR}/log.txt" &
  echo "Config Service started."
}

function start_olc_server {
  echo "Starting OLC server on port ${OLC_SERVER_PORT}..."

  # Setup OLC server default options
  local -a olc_server_default_opts=(
    "--ats_worker_grpc_port=${ATS_WORKER_GRPC_PORT}"
    "--connect_to_lab_server_using_ip=true"
    "--connect_to_lab_server_using_master_detected_ip=true"
    "--enable_ats_mode=true"
    "--enable_client_experiment_manager=false"
    "--enable_client_file_transfer=false"
    "--enable_grpc_lab_server=true"
    "--enable_simple_scheduler_shuffle=true"
    "--olc_database_jdbc_property=socketFactory=org.newsclub.net.mysql.AFUNIXDatabaseSocketFactory,junixsocket.file=/data/ats_db/mysqld.sock"
    "--olc_database_jdbc_url=jdbc:mysql:///ats_db"
    "--olc_server_port=${OLC_SERVER_PORT}"
    "--public_dir=${MTT_LOG_DIR}"
    "--resource_dir_name=olc_server_res_files"
    "--tmp_dir_root=${MTT_MH_WORK_DIR}"
    "--use_tf_retry=false"
  )

  if [[ "${ENABLE_PERSISTENT_CACHE}" == "true" ]]
  then
    olc_server_default_opts+=("--enable_persistent_cache=true")
  fi

  local -a java_loader_args
  if [[ "${USE_DCON_XDS_ADDRESS}" == "true" ]]
  then
    olc_server_default_opts+=("--use_dcon_xds_address=true")
    java_loader_args=(-cp "/deviceinfra/ats_olc_server_deploy.jar:/deviceinfra/grpc_xds_plugin_deploy.jar" "com.google.devtools.mobileharness.infra.client.longrunningservice.OlcServer")
  else
    java_loader_args=(-jar "/deviceinfra/ats_olc_server_deploy.jar")
  fi

  # Start OLC server on the controller
  java -XX:+HeapDumpOnOutOfMemoryError \
    "${java_loader_args[@]}" \
    "${olc_server_default_opts[@]}" \
    ${OLC_SERVER_OPTS} &> /dev/null &
  echo "OLC server started."
}

function start_controller_features {
  # Start RabbitMQ server
  local rabbitmq_pid_dir="/var/run/rabbitmq"
  local rabbitmq_user="rabbitmq"
  if [ ! -d ${rabbitmq_pid_dir} ] ; then
    mkdir -p ${rabbitmq_pid_dir}
    chown -R ${rabbitmq_user}:${rabbitmq_user} ${rabbitmq_pid_dir}
    chmod 755 ${rabbitmq_pid_dir}
  fi
  export RABBITMQ_PID_FILE="${rabbitmq_pid_dir}/pid"
  export RABBITMQ_SERVER_ADDITIONAL_ERL_ARGS="-rabbitmq_server deprecated_features_permit_transient_nonexcl_queues true"
  rabbitmq-server >/var/log/rabbitmq/startup_log 2>&1 &
  time rabbitmqctl wait --timeout 600 "${RABBITMQ_PID_FILE}" || \
  (cat /var/log/rabbitmq/startup_*; false)

  MTT_CONTROL_SERVER_URL="http://localhost:${MTT_CONTROL_SERVER_PORT}"
  OLC_SERVER_GRPC_TARGET="$(echo ${MTT_CONTROL_SERVER_URL} | sed 's,^\([^:/]\+://\)\?\([^:/]\+\)\(:\([0-9]\{1\,5\}\)\)\?\+.*$,\2,g'):${ATS_WORKER_GRPC_PORT}"
  FILE_SERVICE_ONLY="false"

  # Start OMNILAB specific controller features.
  if [[ ! -z "${IS_OMNILAB_BASED}" ]]
  then
    local ats_file_server_port="$((${MTT_CONTROL_SERVER_PORT}+6))"
    ATS_FILE_SERVER="localhost:${ats_file_server_port}"

    # Start MySQL server and wait for it to be ready.
    start_mysql_database "${MTT_STORAGE_PATH}" "false"

    if [[ "${MTT_ENABLE_CONFIG_SERVICE}" == "true" ]]; then
      start_config_service
    fi

    start_olc_server
  fi

  # Set the credential type for the OLC server.
  if [[ "${OLC_SERVER_OPTS}" == *"--use_alts=true"* ]]; then
    OLCS_CREDENTIAL_TYPE="alts"
  fi
}

function start_common_services {
  # Regardless of the operational mode, we always launch the serve.sh
  # orchestrator. Depending on the configuration, it will either orchestrate the
  # full deployment (launching the main ATS server, local datastores, and
  # supporting sidecars) or initiate only the required sidecar services for
  # worker nodes.
  mkdir -p "${MTT_CONTROL_SERVER_LOG_DIR}"
  /mtt/serve.sh \
      --storage_path "${MTT_STORAGE_PATH}" \
      --bind_address "${BIND_ADDRESS}" \
      --port "${MTT_CONTROL_SERVER_PORT}" \
      --labconsole_grpc_port "${LABCONSOLE_SERVER_GRPC_PORT}" \
      --labconsole_rest_port "${LABCONSOLE_SERVER_REST_PORT}" \
      --olc_server_port "${OLC_SERVER_PORT}" \
      --lab_console_port "${LAB_CONSOLE_PORT}" \
      --log_level "${MTT_SERVER_LOG_LEVEL}" \
      --file_service_only "${FILE_SERVICE_ONLY}" \
      --sql_database_uri "${SQL_DATABASE_URI}" \
      --control_server_url "${MTT_CONTROL_SERVER_URL}" \
      --olcs_server_address "localhost:${OLC_SERVER_PORT}" \
      --olcs_credential_type "${OLCS_CREDENTIAL_TYPE}" \
      --report_generator_jar "${MTT_REPORT_GENERATOR_JAR}" \
      --is_omnilab_based "${IS_OMNILAB_BASED}" \
      --enable_lab_console_ui "${MTT_ENABLE_LAB_CONSOLE_UI}" \
      2>&1 | multilog s10485760 n10 "${MTT_CONTROL_SERVER_LOG_DIR}" &
}

function configure_tradefed {
  # Construct TF global config
  TF_CONFIG_FILE=/tradefed/configs/host-config.xml
  local ab_config_file=/tradefed/configs/ab.xml
  cp scripts/host-config.xml "${TF_CONFIG_FILE}"
  cp scripts/ab.xml "${ab_config_file}"
  if [[ -f "${MTT_CUSTOM_TF_CONFIG_FILE}" ]]
  then
    cp "${MTT_CUSTOM_TF_CONFIG_FILE}" "${TF_CONFIG_FILE}"
  fi

  chmod -R a+rX /tradefed/configs /tradefed/secrets

  local ab_include="empty"
  TF_EXTRA_OPTS="--tradefed_host_config=${TF_CONFIG_FILE}"
  if [[ -f /tradefed/secrets/key.json ]]; then
    ab_include="${ab_config_file}"
    TF_EXTRA_OPTS+=" --tradefed_service_account_key_file=/tradefed/secrets/key.json"
  fi

  # Convert REMOTE_VIRTUAL_DEVICES to PRECONFIGURED_VIRTUAL_DEVICE_POOL.
  # Each input element is "${RVD_USER}@${RVD_HOST}/{RVD_COUNT}".
  local preconfigured_virtual_device_pool=""
  local rvd rvd_user_host i
  for rvd in ${REMOTE_VIRTUAL_DEVICES}
  do
    rvd_user_host=$(cut -f 1 -d / <<< "${rvd}")
    RVD_COUNT=$(cut -f 2 -d / <<< "${rvd}")
    RVD_USER=$(cut -f 1 -d @ <<< "${rvd_user_host}")
    RVD_HOST=$(cut -f 2 -d @ <<< "${rvd_user_host}")
    for i in $(seq "${RVD_COUNT}")
    do
      preconfigured_virtual_device_pool+="\\n<option name=\"host_options:preconfigured-virtual-device-pool\" value=\"${RVD_HOST}:${RVD_USER}\" \\/>"
    done
  done

  # Use comma as delimiter because MTT_CONTROL_SERVER_URL has forward slashes.
  sed -e s,\${MTT_CONTROL_SERVER_URL},"${MTT_CONTROL_SERVER_URL}",g \
      -e s/\${MAX_LOCAL_VIRTUAL_DEVICES}/"${MAX_LOCAL_VIRTUAL_DEVICES}"/g \
      -e s/\${PRECONFIGURED_VIRTUAL_DEVICE_POOL}/"${preconfigured_virtual_device_pool}"/g \
      -e s,\${AB_INCLUDE},"${ab_include}",g \
      -i "${TF_CONFIG_FILE}"
}

function start_adb {
  if [[ -z "${MTT_USE_HOST_ADB}" ]]
  then
    # Start ADB and load keys
    [[ -e /root/.android && ! -d /root/.android ]] && rm -f /root/.android
    mkdir -p /root/.android
    export ADB_VENDOR_KEYS="$(ls -1 /root/.android/*.adb_key 2>/dev/null | paste -sd ":" - || echo "")"
    adb start-server || echo "adb start-server returned non-zero code."
    # If IPv6 is enabled, the hostname command prints IPv6 and IPv4 addresses
    # separated by spaces. The following command finds the IPv4 address.
    local container_ipv4_address="$(hostname -i | grep -Eo '(^|\s)[0-9]+(\.[0-9]+){3}($|\s)' | xargs)"
    # Because the adb server listens to 127.0.0.1:5037, this script forwards only
    # IPv4 packets to the server. The container exposes port 5037 to the host-side
    # adb commands. The docker proxy forwards the commands to
    # ${container_ipv4_address}:5037 in the container. Then the socat process
    # forwards them to 127.0.0.1:5037.
    socat -lf /tmp/socat.log \
          tcp-listen:5037,bind="${container_ipv4_address}",reuseaddr,fork \
          tcp-connect:127.0.0.1:5037 &
  else
    # Forward 5037 port to the host.
    local host_ipv4_address=$(/sbin/ip -4 route | awk '/default/ { print $3 }')
    socat -lf /tmp/socat.log \
          tcp-listen:5037,bind=127.0.0.1,reuseaddr,fork \
          tcp-connect:"${host_ipv4_address}":5037 &
  fi
}

function start_ndppd {
  # This function generates a configuration file and starts ndppd. The arguments
  # are the networks to which the neighbor solocitations are forwarded.
  # For example, "2001:db8::/64".
  local default_interface="$(ip -6 route show default | awk '/default/ {print $5}')"
  local config_path=/tmp/ndppd.conf
  local subnet
  echo "proxy ${default_interface} {" > "${config_path}"
  for subnet in "$@"
  do
    echo "  rule ${subnet} {" >> "${config_path}"
    echo "    auto" >> "${config_path}"
    echo "  }" >> "${config_path}"
  done
  echo "}" >> "${config_path}"
  ndppd -d -c "${config_path}"
}

function start_cuttlefish {
  if [[ "${MAX_LOCAL_VIRTUAL_DEVICES}" -ne 0 ]]
  then
    # Start rsyslog which is a dependency of crosvm.
    # It starts slowly if open file limit is high.
    # Reference: https://github.com/rsyslog/rsyslog/issues/5158
    local open_file_limit="$(ulimit -Sn)"
    if [[ "${open_file_limit}" -gt 32768 ]] || [[ "${open_file_limit}" == unlimited ]]; then
      ulimit -Sn 32768
    fi
    rsyslogd -iNONE
    ulimit -Sn "${open_file_limit}"
    # Start cuttlefish service.
    if [[ -n "${IPV6_BRIDGE_NETWORK}" ]]
    then
      local ipv6_subnets="$(/mtt/scripts/gen_subnets.py "${IPV6_BRIDGE_NETWORK}" 64 2 $(hostname -I))"
      local wifi_ipv6_prefix ethernet_ipv6_prefix
      read wifi_ipv6_prefix ethernet_ipv6_prefix <<< "${ipv6_subnets}"
      echo "WIFI_IPV6_PREFIX=${wifi_ipv6_prefix}"
      echo "ETHERNET_IPV6_PREFIX=${ethernet_ipv6_prefix}"
      # Reference: https://github.com/google/android-cuttlefish/blob/main/debian/cuttlefish-common.default
      num_cvd_accounts="${MAX_LOCAL_VIRTUAL_DEVICES}" \
        wifi_ipv6_prefix="${wifi_ipv6_prefix}" \
        wifi_ipv6_prefix_length=64 \
        ethernet_ipv6_prefix="${ethernet_ipv6_prefix}" \
        ethernet_ipv6_prefix_length=64 \
        /etc/init.d/cuttlefish-common start
      start_ndppd "${wifi_ipv6_prefix}/64" "${ethernet_ipv6_prefix}/64"
    else
      num_cvd_accounts="${MAX_LOCAL_VIRTUAL_DEVICES}" \
        /etc/init.d/cuttlefish-common start
    fi
  fi
}

# TODO Move the post-run script to run after lab server startup.
function run_postrun_hook {
  if [[ -f "${POSTRUN_SCRIPT_PATH}" ]]; then
    source ${POSTRUN_SCRIPT_PATH}
  fi
}

function start_test_runner {
  rm -rf "${MTT_TEST_WORK_DIR}"
  mkdir -p "${MTT_TEST_WORK_DIR}"
  local max_heap_mb="$(expr `free -m | awk '/^Mem:/{print $2}'` / 4)"
  max_heap_mb=$(( max_heap_mb < 6000 ? 6000 : max_heap_mb ))
  if [[ -z "${IS_OMNILAB_BASED}" ]]
  then
    # Start TF with the modified global config and at least 6GB of heap space (can
    # be adjusted by setting the -Xmx flag in the TRADEFED_OPTS variable).
    local mtt_tradefed_opts="-Djava.io.tmpdir=${MTT_TEST_WORK_DIR} -Xmx${max_heap_mb}m"
    TF_GLOBAL_CONFIG="${TF_CONFIG_FILE}"\
      MTT_CONTROL_SERVER_URL="${MTT_CONTROL_SERVER_URL}"\
      MTT_CONTROL_FILE_SERVER_URL="${MTT_CONTROL_FILE_SERVER_URL}"\
      TRADEFED_OPTS="${mtt_tradefed_opts} ${TRADEFED_OPTS}"\
      exec tradefed.sh
  else
    # Start OSS lab server
    local lab_server_args=""
    if [[ "${MAX_ORCHESTRATION_VIRTUAL_DEVICES}" -gt 0 ]]; then
      CLOUD_ORCHESTRATOR_URL="${CLOUD_ORCHESTRATOR_URL:-http://localhost:8080}"
      lab_server_args+="--android_jit_emulator_num=${MAX_ORCHESTRATION_VIRTUAL_DEVICES} "
      lab_server_args+="--cloud_orchestrator_service_url=${CLOUD_ORCHESTRATOR_URL} "
      lab_server_args+="--noop_jit_emulator=false "
    elif [[ "${MAX_LOCAL_VIRTUAL_DEVICES}" -gt 0 ]]; then
      lab_server_args+="--android_jit_emulator_num=${MAX_LOCAL_VIRTUAL_DEVICES} "
      if [[ -n "${CLOUD_ORCHESTRATOR_URL}" ]]; then
        lab_server_args+="--cloud_orchestrator_service_url=${CLOUD_ORCHESTRATOR_URL} "
        lab_server_args+="--noop_jit_emulator=false "
      else
        lab_server_args+="--noop_jit_emulator=true "
      fi
    fi
    if [[ "${RVD_COUNT}" -gt 0 ]]; then
      lab_server_args+="--remote_android_jit_emulator_num=${RVD_COUNT} "
      lab_server_args+="--noop_jit_emulator=true "
      lab_server_args+="--virtual_device_server_ip=${RVD_HOST} "
      lab_server_args+="--virtual_device_server_username=${RVD_USER} "
    fi

    # Only start cache manager in worker mode.
    if [[ "${ENABLE_CONTROLLER_FEATURES}" != "true" ]]; then
      local is_cache_local="false"
      if [[ -z "${PERSISTENT_CACHE_DIR}" ]]; then
        is_cache_local="true"
        PERSISTENT_CACHE_DIR="${MTT_STORAGE_PATH}/local_file_store/persistent_cache"
      fi
      if [ ! -d "${PERSISTENT_CACHE_DIR}" ]; then
        mkdir -p "${PERSISTENT_CACHE_DIR}"
      fi

      if [[ "${ENABLE_PERSISTENT_CACHE}" == "true" ]]
      then
        # Move this logic to local docker volume setup outside of the mtt container when we migrate to docker compose deployment.
        if [[ "${is_cache_local}" == "true" ]]; then
          PERSISTENT_CACHE_OPTS+=" --persistent_cache_dir=${PERSISTENT_CACHE_DIR} --public_dir=${MTT_LOG_DIR}"
          echo "Start persistent cache manager with opts: ${PERSISTENT_CACHE_OPTS} for local cache."
          java -XX:+HeapDumpOnOutOfMemoryError \
            -jar /deviceinfra/cache_manager_server_deploy.jar \
            ${PERSISTENT_CACHE_OPTS} &> /dev/null &
        fi
        lab_server_args+=" --persistent_cache_dir=${PERSISTENT_CACHE_DIR} --enable_persistent_cache=true"
      fi
    fi

    if [[ "${MTT_CONNECT_LABSERVER_TO_CONFIG_SERVER}" == "true" ]]; then
      lab_server_args+=" --enable_external_config_service=true"
      lab_server_args+=" --config_service_grpc_target=localhost:${MTT_CONFIG_SERVICE_GRPC_PORT}"
    else
      lab_server_args+=" --api_config=/deviceinfra/lab_server_api_config.textproto"
    fi

    java \
      "-Xmx${max_heap_mb}m" \
      -XX:+HeapDumpOnOutOfMemoryError \
      -Dcom.google.mobileharness.ats.lab_server_type="${ATS_LAB_SERVER_TYPE}" \
      -jar /deviceinfra/lab_server_oss_deploy.jar \
      --ats_file_server="${ATS_FILE_SERVER}" \
      --ats_xts_work_dir="${MTT_MH_WORK_DIR}" \
      --master_grpc_target="${OLC_SERVER_GRPC_TARGET}" \
      --public_dir="${MTT_LOG_DIR}" \
      --tf_fallback_java_binary="${JAVA21_HOME}/bin/java" \
      --tmp_dir_root="${MTT_MH_WORK_DIR}" \
      ${LAB_SERVER_OPTS} \
        ${lab_server_args} \
        ${TF_EXTRA_OPTS}
  fi
}

# --- Main Execution Flow ---

configure_operation_mode
import_ca_certificates
configure_proxies
link_temporary_mounts
run_prerun_hook
init_omnilab_workdir

# Start controller features first.
if [[ "${ENABLE_CONTROLLER_FEATURES}" == "true" ]]
then
  start_controller_features
fi

start_common_services

# Start worker features if enabled.
if [[ "${ENABLE_WORKER_FEATURES}" == "true" ]]
then
  configure_tradefed
  start_adb
  start_cuttlefish
  run_postrun_hook
  start_test_runner
else
  # Keep the container alive when worker features are disabled (e.g., in controller mode).
  echo "Worker features disabled. Keeping container alive for controller services..."
  tail -f /dev/null
fi

# LINT.ThenChange(init_script_workflow.md, init_script_workflow.mermaid)
