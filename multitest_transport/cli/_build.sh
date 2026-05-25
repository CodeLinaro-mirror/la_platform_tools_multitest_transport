#!/bin/bash
# Copyright 2021 Google LLC
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

# This file builds CLIs with CLIs' source folder.
# It is used by local build and kokoro build.
set -eux

# Parse command line arguments
while [[ $# -gt 0 ]]; do
  case "$1" in
    --cli_dir) CLI_DIR="$2";;
    --version) VERSION="$2";;
    --release) RELEASE="$2";;
    --environment) ENVIRONMENT="$2";;
    *) echo "Unknown argument $1"; exit 1; # fail-fast on unknown key
  esac
  shift # skip key
  shift # skip value
done

CLI_DIR=$(readlink -f "${CLI_DIR}")
pushd "${CLI_DIR}"
# Move MTT source code under src directory
mkdir src
mv -t src multitest_transport tradefed_cluster setup.py

# Some device-infra source code files are needed by the MTT CLI.
# When running in Kokoro, these files are pre-populated in $KOKORO_ARTIFACTS_DIR
# (configured by
# http://google3/devtools/kokoro/config/data/git_on_borg_resource_acl.gcl;l=18131-18142;rcl=808571504).
# When running locally (outside of Kokoro), $KOKORO_ARTIFACTS_DIR is not set.
# To support local development/builds, we download these files from the public
# google/device-infra GitHub repository if they are not available locally.
#
# This helper function handles preparing these files by either moving them from
# Kokoro artifacts or downloading them from GitHub.
prepare_file() {
  local repo_path="$1"
  local target_path="$2"

  local target_dir
  target_dir=$(dirname "${target_path}")
  mkdir -p "${target_dir}"

  if [[ -n "${KOKORO_ARTIFACTS_DIR:-}" ]]; then
    # Kokoro environment: move the file from the pre-populated artifacts directory.
    local source_path="${KOKORO_ARTIFACTS_DIR}/git/device-infra/${repo_path}"
    if [[ -f "${source_path}" ]]; then
      mv "${source_path}" "${target_path}"
    else
      echo "Error: Source file not found in Kokoro artifacts: ${source_path}"
      exit 1
    fi
  else
    # Local environment: download the file from the public GitHub repository.
    echo "KOKORO_ARTIFACTS_DIR not set. Downloading ${repo_path} from GitHub..."
    if ! command -v curl &> /dev/null; then
      echo "Error: curl is required to download files but is not installed."
      exit 1
    fi
    local url="https://raw.githubusercontent.com/google/device-infra/master/${repo_path}"
    if ! curl -sSfL "${url}" -o "${target_path}"; then
      echo "Error: Failed to download ${url} to ${target_path}"
      exit 1
    fi
  fi
}

# Prepare device-infra's files that go to src/google3/third_party/deviceinfra/
for file in \
  "src/devtools/common/metrics/stability/util/grpc_error_util.py" \
  "src/devtools/deviceinfra/host/daemon/proto/health.proto"; do
  prepare_file "${file}" "src/google3/third_party/deviceinfra/${file}"
done

# Prepare device-infra's files that go to src/
for file in \
  "src/devtools/common/metrics/stability/model/proto/exception.proto" \
  "src/devtools/common/metrics/stability/model/proto/error_id.proto" \
  "src/devtools/common/metrics/stability/model/proto/error_type.proto" \
  "src/devtools/common/metrics/stability/model/proto/namespace.proto" \
  "src/devtools/common/metrics/stability/rpc/proto/rpc_error_payload.proto" \
  "src/devtools/common/metrics/stability/rpc/proto/rpc_error.proto"; do
  prepare_file "${file}" "src/${file}"
done

# Adding __init__.py in all subdirectories so Python can import modules in them
# correctly.
find src/google3 src/src src/multitest_transport \
-type d -exec touch {}/__init__.py \;

cat << EOF > src/VERSION
[version]
VERSION=${VERSION}
BUILD_ENVIRONMENT=${ENVIRONMENT}
EOF

chmod +w src/multitest_transport/cli/version.py
cat << EOF > src/multitest_transport/cli/version.py
VERSION = "${VERSION}"
BUILD_ENVIRONMENT = "${ENVIRONMENT}"
EOF

chmod +w src/setup.py
# setup.py's version must obey pep-440.
sed -i "s/VERSION =.*/VERSION = \"${RELEASE}\"/" src/setup.py

cat << EOF > Dockerfile
FROM ubuntu:24.04
ENV LANG=C.UTF-8

RUN export DEBIAN_FRONTEND=noninteractive; apt update -qq; apt install -y -qq \
  unzip wget zip software-properties-common build-essential;
# Add deadsnakes for different versions of python and distutils
RUN add-apt-repository -y ppa:deadsnakes/ppa
RUN export DEBIAN_FRONTEND=noninteractive; apt update -qq; apt install -y -qq \
  python3.10 python3.11 python3.12 python3.13 \
  python3.10-distutils python3.11-distutils \
  python3.10-dev python3.10-venv python3.11-venv python3.12-venv python3.13-venv

# Set Python version to 3.10.
RUN update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.10 1000

COPY ./requirements.txt /tmp
RUN python3 -m ensurepip --upgrade
RUN pip3 install --upgrade setuptools pip
RUN pip3 install pex
RUN pip3 install -r /tmp/requirements.txt
RUN pip3 install --upgrade keyrings.alt

# Upgrade to the latest verified version of protoc which supports python3.13.
RUN mkdir -p /protoc && \
  wget --no-verbose -O /protoc/protoc-31.1-linux-x86_64.zip \
  https://github.com/protocolbuffers/protobuf/releases/download/v31.1/protoc-31.1-linux-x86_64.zip && \
  unzip -q -o /protoc/protoc-31.1-linux-x86_64.zip -d /protoc
EOF

echo "Starting Docker pull cache image at: $(date)"
docker pull gcr.io/android-mtt/pex:latest
echo "Starting Docker build at: $(date)"
docker build -t docker_pex . --cache-from gcr.io/android-mtt/pex:latest
echo "Docker build finished at: $(date)"

cat << 'EOF' > inside_docker_build.sh
# Build python file from proto
/protoc/bin/protoc --python_out=/workspace/src/tradefed_cluster/configs/ \
  --proto_path /workspace/src/tradefed_cluster/configs/ \
  /workspace/src/tradefed_cluster/configs/lab_config.proto

# Compile stability model and RPC error protos
for proto in \
  "src/devtools/common/metrics/stability/model/proto/exception.proto" \
  "src/devtools/common/metrics/stability/model/proto/error_id.proto" \
  "src/devtools/common/metrics/stability/model/proto/error_type.proto" \
  "src/devtools/common/metrics/stability/model/proto/namespace.proto" \
  "src/devtools/common/metrics/stability/rpc/proto/rpc_error_payload.proto" \
  "src/devtools/common/metrics/stability/rpc/proto/rpc_error.proto"; do
  /protoc/bin/protoc --python_out=/workspace/src/ \
    --proto_path /workspace/src/ \
    "/workspace/src/${proto}"
done

# Generate both python proto and gRPC code for health.proto
python3 -m grpc_tools.protoc \
  --proto_path /workspace/src/ \
  --python_out=/workspace/src/ \
  --grpc_python_out=/workspace/src/ \
  /workspace/src/google3/third_party/deviceinfra/src/devtools/deviceinfra/host/daemon/proto/health.proto

# Clean up raw proto files to avoid packaging them into PEX/ZIP
rm -f /workspace/src/google3/third_party/deviceinfra/src/devtools/deviceinfra/host/daemon/proto/health.proto
for proto in \
  "src/devtools/common/metrics/stability/model/proto/exception.proto" \
  "src/devtools/common/metrics/stability/model/proto/error_id.proto" \
  "src/devtools/common/metrics/stability/model/proto/error_type.proto" \
  "src/devtools/common/metrics/stability/model/proto/namespace.proto" \
  "src/devtools/common/metrics/stability/rpc/proto/rpc_error_payload.proto" \
  "src/devtools/common/metrics/stability/rpc/proto/rpc_error.proto"; do
  rm -f "/workspace/src/${proto}"
done

cd /workspace
# Build mtt pex package.
pex --python="python3.13" --python="python3.12" \
  --python="python3.11" --python="python3.10" \
  --python-shebang="/usr/bin/env python3" \
  --pip-version latest-compatible \
  -D src \
  -r requirements.txt \
  -m multitest_transport.cli.cli \
  -o mtt

# Build zip file include all mtt source.
cd src/
zip -r /workspace/mtt.zip *
cd ..

# Build mtt_lab pex package.
cp mtt src/mtt_binary
pex --python="python3.13" --python="python3.12" \
  --python="python3.11" --python="python3.10" \
  --python-shebang="/usr/bin/env python3" \
  --pip-version latest-compatible \
  -D src \
  -r requirements.txt \
  -m multitest_transport.cli.lab_cli \
  -o mtt_lab
EOF
chmod +x inside_docker_build.sh
echo "Starting build inside Docker at: $(date)"
docker run --rm --mount type=bind,source="$CLI_DIR",target=/workspace docker_pex sh -c /workspace/inside_docker_build.sh
echo "Build inside Docker finished at: $(date)"
cd -

popd
