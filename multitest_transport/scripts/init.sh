#!/bin/bash
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

set -e

# The custom script that is executed after basic environment is set up and before any services are started .
readonly PRERUN_SCRIPT_PATH="/mtt/scripts/init_pre_run.sh"

function start_ndppd {
  # This function generates a configuration file and starts ndppd. The arguments
  # are the networks to which the neighbor solocitations are forwarded.
  # For example, "2001:db8::/64".
  DEFAULT_INTERFACE="$(ip -6 route show default | awk '/default/ {print $5}')"
  CONFIG_PATH=/tmp/ndppd.conf
  echo "proxy ${DEFAULT_INTERFACE} {" > "${CONFIG_PATH}"
  for SUBNET in "$@"
  do
    echo "  rule ${SUBNET} {" >> "${CONFIG_PATH}"
    echo "    auto" >> "${CONFIG_PATH}"
    echo "  }" >> "${CONFIG_PATH}"
  done
  echo "}" >> "${CONFIG_PATH}"
  ndppd -d -c "${CONFIG_PATH}"
}

function set_java_proxy {
  HOST=$(echo ${2} | sed "s,^\(https\?://\)\?\([^:/]\+\)\(:\([0-9]\+\)\)\?\+.*$,\2,g")
  PORT=$(echo ${2} | sed "s,^\(https\?://\)\?\([^:/]\+\)\(:\([0-9]\+\)\)\?\+.*$,\4,g")
  export JAVA_TOOL_OPTIONS="${JAVA_TOOL_OPTIONS} -D${1}.proxyHost=${HOST} -D${1}.proxyPort=${PORT}"
}

function set_java_non_proxy {
  # Convert ${no_proxy} to java property. For example, "127.0.0.1,::1" => "127.0.0.1|[::1]".
  HOSTS=$(echo -n "${1}" | awk 'BEGIN {RS=","} NR > 1 {printf "|"} {printf ($0 ~ /:/ ? "[%s]" : "%s"), $0}')
  export JAVA_TOOL_OPTIONS="${JAVA_TOOL_OPTIONS} -Dhttp.nonProxyHosts=${HOSTS}"
}

MAX_LOCAL_VIRTUAL_DEVICES="${MAX_LOCAL_VIRTUAL_DEVICES:-0}"

# Add extra CA certificates.
for FILE in /usr/local/share/ca-certificates/*
do
  [[ -f "${FILE}" ]] || continue
  chmod 644 "${FILE}"
  echo yes | keytool -importcert\
      -cacerts\
      -trustcacerts\
      -file "${FILE}"\
      -alias $(basename -- "${FILE}")\
      -storepass "changeit"
done
update-ca-certificates

# Configure proxy settings for tools.
[[ ! -z "${HTTP_PROXY}" ]] && set_java_proxy http ${HTTP_PROXY}
[[ ! -z "${HTTPS_PROXY}" ]] && set_java_proxy https ${HTTPS_PROXY}
[[ ! -z "${NO_PROXY}" ]] && set_java_non_proxy ${NO_PROXY}
export HTTPLIB2_CA_CERTS=/etc/ssl/certs/ca-certificates.crt

# Link temporarily mounted files/directories into the local file store
mkdir -p "${MTT_STORAGE_PATH}/local_file_store"
find "${MTT_STORAGE_PATH}/local_file_store" -xtype l -delete
[[ -d /tmp/.mnt ]] && find /tmp/.mnt -mindepth 1 -maxdepth 1 \
  -exec ln -sf {} "${MTT_STORAGE_PATH}/local_file_store" \;

cd /mtt

if [[ -f "${PRERUN_SCRIPT_PATH}" ]]; then
  source ${PRERUN_SCRIPT_PATH}
fi

if [[ -z "${MTT_CONTROL_SERVER_URL}" ]] || [[ "${OPERATION_MODE}"=="on_premise" ]]
then
  # Start RabbitMQ server
  time service rabbitmq-server start || (cat /var/log/rabbitmq/startup_*; false)

  MTT_CONTROL_SERVER_PORT="${MTT_CONTROL_SERVER_PORT:-8000}"
  MTT_CONTROL_SERVER_LOG_DIR="${MTT_LOG_DIR}/server"
  mkdir -p "${MTT_CONTROL_SERVER_LOG_DIR}"

  if [[ -z "${MTT_CONTROL_SERVER_URL}" ]]
  then
    MTT_CONTROL_SERVER_URL="http://localhost:${MTT_CONTROL_SERVER_PORT}"
    FILE_SERVICE_ONLY="false"
  # TODO: Use config to differentiate worker and controller.
  elif [[ "${OPERATION_MODE}"=="on_premise" ]]
  then
    # Only launch worker's file server in on_premise mode.
    FILE_SERVICE_ONLY="true"
  fi

  if [[ ! -z "${IS_OMNILAB_BASED}" ]]
  then
    OLC_SERVER_PORT="${OLC_SERVER_PORT:-7030}"
    ATS_WORKER_GRPC_PORT="${ATS_WORKER_GRPC_PORT:-7031}"
    OLC_SERVER_GRPC_TARGET="$(echo ${MTT_CONTROL_SERVER_URL} | sed 's,^\([^:/]\+://\)\?\([^:/]\+\)\(:\([0-9]\{1\,5\}\)\)\?\+.*$,\2,g'):${ATS_WORKER_GRPC_PORT}"
    ATS_FILE_SERVER_PORT="$((${MTT_CONTROL_SERVER_PORT}+6))"
    ATS_FILE_SERVER="localhost:${ATS_FILE_SERVER_PORT}"

    rm -rf "${MTT_MH_WORK_DIR}"
    mkdir -p "${MTT_MH_WORK_DIR}"
    if [[ "${FILE_SERVICE_ONLY}" == "false" ]]
    then
      # Start OLC server on the controller
      java -XX:+HeapDumpOnOutOfMemoryError \
        -jar /deviceinfra/ats_olc_server_deploy.jar \
        --connect_to_lab_server_using_ip=true \
        --connect_to_lab_server_using_master_detected_ip=true \
        --enable_ats_mode=true \
        --enable_client_experiment_manager=false \
        --enable_client_file_transfer=false \
        --enable_grpc_lab_server=true \
        --enable_simple_scheduler_shuffle=true \
        --olc_server_port="${OLC_SERVER_PORT}" \
        --ats_worker_grpc_port="${ATS_WORKER_GRPC_PORT}" \
        --public_dir="${MTT_LOG_DIR}" \
        --resource_dir_name="olc_server_res_files" \
        --tmp_dir_root="${MTT_MH_WORK_DIR}" \
        --use_tf_retry=false \
        ${OLC_SERVER_OPTS} &> /dev/null &
    else
      REMOTES_CONTROL_SERVER_PORT="$(echo ${MTT_CONTROL_SERVER_URL} | sed 's,^\([^:/]\+://\)\?\([^:/]\+:\)\(\([0-9]\{1\,5\}\)\)\?\+.*$,\3,g')"
      ATS_FILE_SERVER_PORT="$((${REMOTES_CONTROL_SERVER_PORT}+6))"
      ATS_FILE_SERVER="$(echo ${MTT_CONTROL_SERVER_URL} | sed 's,^\(\([^:/]\+://\)\?\([^:/]\+\)\)\(:\([0-9]\{1\,5\}\)\)\?\+.*$,\1,g'):${ATS_FILE_SERVER_PORT}"
    fi
  fi

  # Bind to IPv4 only because endpoints service cannot convert IPv6 addresses to
  # URLs correctly.
  BIND_ADDRESS="0.0.0.0"

  # Set the credential type for the OLC server.
  if [[ "${OLC_SERVER_OPTS}" == *"--use_alts=true"* ]]; then
    OLCS_CREDENTIAL_TYPE="alts"
  else
    OLCS_CREDENTIAL_TYPE="no_credential"
  fi

  # Start the ATS server and pass empty sql_database_uri to launch DB server.
  /mtt/serve.sh \
      --storage_path "${MTT_STORAGE_PATH}" \
      --bind_address "${BIND_ADDRESS}" \
      --port "${MTT_CONTROL_SERVER_PORT}" \
      --log_level "${MTT_SERVER_LOG_LEVEL}" \
      --file_service_only "${FILE_SERVICE_ONLY}" \
      --sql_database_uri "" \
      --control_server_url "${MTT_CONTROL_SERVER_URL}" \
      --olcs_server_address "localhost:${OLC_SERVER_PORT}" \
      --olcs_credential_type "${OLCS_CREDENTIAL_TYPE}" \
      --report_generator_jar "${MTT_REPORT_GENERATOR_JAR}" \
      --is_omnilab_based "${IS_OMNILAB_BASED}" \
      2>&1 | multilog s10485760 n10 "${MTT_CONTROL_SERVER_LOG_DIR}" &
fi

# Construct TF global config
TF_CONFIG_FILE=scripts/host-config.xml
if [[ -f "${MTT_CUSTOM_TF_CONFIG_FILE}" ]]
then
  cp "${MTT_CUSTOM_TF_CONFIG_FILE}" "${TF_CONFIG_FILE}"
fi

# Convert REMOTE_VIRTUAL_DEVICES to PRECONFIGURED_VIRTUAL_DEVICE_POOL.
# Each input element is "${RVD_USER}@${RVD_HOST}/{RVD_COUNT}".
for RVD in "${REMOTE_VIRTUAL_DEVICES}"
do
  RVD_USER_HOST=$(cut -f 1 -d / <<< "${RVD}")
  RVD_COUNT=$(cut -f 2 -d / <<< "${RVD}")
  RVD_USER=$(cut -f 1 -d @ <<< "${RVD_USER_HOST}")
  RVD_HOST=$(cut -f 2 -d @ <<< "${RVD_USER_HOST}")
  for I in $(seq "${RVD_COUNT}")
  do
    PRECONFIGURED_VIRTUAL_DEVICE_POOL+="\\n<option name=\"host_options:preconfigured-virtual-device-pool\" value=\"${RVD_HOST}:${RVD_USER}\" \\/>"
  done
done

# Use comma as delimiter because MTT_CONTROL_SERVER_URL has forward slashes.
sed -e s,\${MTT_CONTROL_SERVER_URL},"${MTT_CONTROL_SERVER_URL}",g \
    -e s/\${MAX_LOCAL_VIRTUAL_DEVICES}/"${MAX_LOCAL_VIRTUAL_DEVICES}"/g \
    -e s/\${PRECONFIGURED_VIRTUAL_DEVICE_POOL}/"${PRECONFIGURED_VIRTUAL_DEVICE_POOL}"/g \
    -i "${TF_CONFIG_FILE}"

if [[ -z "${MTT_USE_HOST_ADB}" ]]
then
  # Start ADB and load keys
  export ADB_VENDOR_KEYS=$(ls -1 /root/.android/*.adb_key | paste -sd ":" -)
  adb start-server
  # If IPv6 is enabled, the hostname command prints IPv6 and IPv4 addresses
  # separated by spaces. The following command finds the IPv4 address.
  CONTAINER_IPV4_ADDRESS="$(hostname -i | grep -Eo '(^|\s)[0-9]+(\.[0-9]+){3}($|\s)' | xargs)"
  # Because the adb server listens to 127.0.0.1:5037, this script forwards only
  # IPv4 packets to the server. The container exposes port 5037 to the host-side
  # adb commands. The docker proxy forwards the commands to
  # ${CONTAINER_IPV4_ADDRESS}:5037 in the container. Then the socat process
  # forwards them to 127.0.0.1:5037.
  socat -lf /tmp/socat.log \
        tcp-listen:5037,bind="${CONTAINER_IPV4_ADDRESS}",reuseaddr,fork \
        tcp-connect:127.0.0.1:5037 &
else
  # Forward 5037 port to the host.
  HOST_IPV4_ADDRESS=$(/sbin/ip -4 route | awk '/default/ { print $3 }')
  socat -lf /tmp/socat.log \
        tcp-listen:5037,bind=127.0.0.1,reuseaddr,fork \
        tcp-connect:"${HOST_IPV4_ADDRESS}":5037 &
fi


if [[ "${MAX_LOCAL_VIRTUAL_DEVICES}" -ne 0 ]]
then
  # Start rsyslog which is a dependency of crosvm.
  rsyslogd -iNONE
  # Start cuttlefish service.
  if [[ -n "${IPV6_BRIDGE_NETWORK}" ]]
  then
    IPV6_SUBNETS="$(/mtt/scripts/gen_subnets.py "${IPV6_BRIDGE_NETWORK}" 64 2 $(hostname -I))"
    read WIFI_IPV6_PREFIX ETHERNET_IPV6_PREFIX <<< "${IPV6_SUBNETS}"
    echo "WIFI_IPV6_PREFIX=${WIFI_IPV6_PREFIX}"
    echo "ETHERNET_IPV6_PREFIX=${ETHERNET_IPV6_PREFIX}"
    # Reference: https://github.com/google/android-cuttlefish/blob/main/debian/cuttlefish-common.default
    num_cvd_accounts="${MAX_LOCAL_VIRTUAL_DEVICES}" \
      wifi_ipv6_prefix="${WIFI_IPV6_PREFIX}" \
      wifi_ipv6_prefix_length=64 \
      ethernet_ipv6_prefix="${ETHERNET_IPV6_PREFIX}" \
      ethernet_ipv6_prefix_length=64 \
      /etc/init.d/cuttlefish-common start
    start_ndppd "${WIFI_IPV6_PREFIX}/64" "${ETHERNET_IPV6_PREFIX}/64"
  else
    num_cvd_accounts="${MAX_LOCAL_VIRTUAL_DEVICES}" \
      /etc/init.d/cuttlefish-common start
  fi
fi

rm -rf "${MTT_TEST_WORK_DIR}"
mkdir -p "${MTT_TEST_WORK_DIR}"
MAX_HEAP_MB="$(expr `free -m | awk '/^Mem:/{print $2}'` / 4)"
MAX_HEAP_MB=$(( MAX_HEAP_MB < 6000 ? 6000 : MAX_HEAP_MB ))
if [[ -z "${IS_OMNILAB_BASED}" ]]
then
  # Start TF with the modified global config and at least 6GB of heap space (can
  # be adjusted by setting the -Xmx flag in the TRADEFED_OPTS variable).
  MTT_TRADEFED_OPTS="-Djava.io.tmpdir=${MTT_TEST_WORK_DIR} -Xmx${MAX_HEAP_MB}m"
  TF_GLOBAL_CONFIG="${TF_CONFIG_FILE}"\
    MTT_CONTROL_SERVER_URL="${MTT_CONTROL_SERVER_URL}"\
    MTT_CONTROL_FILE_SERVER_URL="${MTT_CONTROL_FILE_SERVER_URL}"\
    TRADEFED_OPTS="${MTT_TRADEFED_OPTS} ${TRADEFED_OPTS}"\
    exec tradefed.sh
else
  # Start OSS lab server
  java "-Xmx${MAX_HEAP_MB}m" -XX:+HeapDumpOnOutOfMemoryError \
    -jar /deviceinfra/lab_server_oss_deploy.jar \
    --adb_dont_kill_server=true \
    --adb_max_no_device_detection_rounds=1200 \
    --android_device_daemon=false \
    --api_config=/deviceinfra/lab_server_api_config.textproto \
    --ats_file_server="${ATS_FILE_SERVER}" \
    --check_device_interval=1h \
    --clear_android_device_multi_users=false \
    --disable_calling=false \
    --disable_device_reboot_for_ro_properties=true \
    --disable_wifi_util_func=true \
    --enable_android_device_ready_check=false \
    --enable_ats_file_server_uploader=true \
    --enable_device_state_change_recover=false \
    --enable_device_system_settings_change=false \
    --enable_external_master_server=true \
    --enable_xts_dynamic_downloader=true \
    --master_grpc_target="${OLC_SERVER_GRPC_TARGET}" \
    --mute_android=false \
    --public_dir="${MTT_LOG_DIR}" \
    --resource_dir_name="lab_server_res_files" \
    --serv_via_cloud_rpc=false \
    --set_test_harness_property=false \
    --tmp_dir_root="${MTT_MH_WORK_DIR}" \
    ${LAB_SERVER_OPTS}
fi
