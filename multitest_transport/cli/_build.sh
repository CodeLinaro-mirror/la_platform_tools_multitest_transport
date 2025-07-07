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

# Also move device-infra source code needed by MTT CLI to the src directory:
# Moving device-infra's grpc_error_util.py
mkdir -p src/google3/third_party/deviceinfra/src/devtools/common/metrics/stability/util/
mv $KOKORO_ARTIFACTS_DIR/git/device-infra/src/devtools/common/metrics/stability/util/grpc_error_util.py src/google3/third_party/deviceinfra/src/devtools/common/metrics/stability/util/grpc_error_util.py

# Moving device-infra's exception.proto
mkdir -p src/com_google_deviceinfra/src/devtools/common/metrics/stability/model/proto/
mkdir -p src/src/devtools/common/metrics/stability/model/proto/
# Note the com_google_deviceinfra path is how it's referenced in Python source
# code: https://github.com/google/device-infra/blob/fc4e20e65e69700422cab4c0d7378745d82fb659/src/devtools/common/metrics/stability/util/grpc_error_util.py#L22
# (It's processed by Copybara: http://google3/third_party/deviceinfra/copy.bara.sky;l=571-575;rcl=755968683)
mv $KOKORO_ARTIFACTS_DIR/git/device-infra/src/devtools/common/metrics/stability/model/proto/exception.proto src/com_google_deviceinfra/src/devtools/common/metrics/stability/model/proto/exception.proto
mv $KOKORO_ARTIFACTS_DIR/git/device-infra/src/devtools/common/metrics/stability/model/proto/error_id.proto src/src/devtools/common/metrics/stability/model/proto/error_id.proto
mv $KOKORO_ARTIFACTS_DIR/git/device-infra/src/devtools/common/metrics/stability/model/proto/error_type.proto src/src/devtools/common/metrics/stability/model/proto/error_type.proto
mv $KOKORO_ARTIFACTS_DIR/git/device-infra/src/devtools/common/metrics/stability/model/proto/namespace.proto src/src/devtools/common/metrics/stability/model/proto/namespace.proto

# Moving device-infra's rpc_error_payload.proto
mkdir -p src/com_google_deviceinfra/src/devtools/common/metrics/stability/rpc/proto/
mkdir -p src/src/devtools/common/metrics/stability/rpc/proto/
mv $KOKORO_ARTIFACTS_DIR/git/device-infra/src/devtools/common/metrics/stability/rpc/proto/rpc_error_payload.proto src/com_google_deviceinfra/src/devtools/common/metrics/stability/rpc/proto/rpc_error_payload.proto
mv $KOKORO_ARTIFACTS_DIR/git/device-infra/src/devtools/common/metrics/stability/rpc/proto/rpc_error.proto src/src/devtools/common/metrics/stability/rpc/proto/rpc_error.proto

# Moving device-infra's health.proto
mkdir -p src/google3/third_party/deviceinfra/src/devtools/deviceinfra/host/daemon/proto/
mv $KOKORO_ARTIFACTS_DIR/git/device-infra/src/devtools/deviceinfra/host/daemon/proto/health.proto src/google3/third_party/deviceinfra/src/devtools/deviceinfra/host/daemon/proto/health.proto

# Adding __init__.py in all subdirectories so Python can import modules in them
# correctly.
find src/google3 src/com_google_deviceinfra src/src src/multitest_transport \
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
FROM ubuntu:20.04
ENV LANG=C.UTF-8

RUN export DEBIAN_FRONTEND=noninteractive; apt update -qq; apt install -y -qq \
  unzip wget zip software-properties-common build-essential;
# Add deadsnakes for different versions of python and distutils
RUN add-apt-repository -y ppa:deadsnakes/ppa
RUN export DEBIAN_FRONTEND=noninteractive; apt update -qq; apt install -y -qq \
  python3.9 python3.10 python3.11 python3.12 python3.13 \
  python3.9-distutils python3.10-distutils python3.11-distutils \
  python3.10-dev python3.10-venv python3.11-venv python3.12-venv python3.13-venv

# Set Python version to 3.10 since 3.9 will be deprecated on 2025-10.
RUN update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.10 1000

COPY ./requirements.txt /tmp
COPY ./constraints.txt /tmp
RUN python3 -m ensurepip --upgrade
RUN pip3 install --upgrade setuptools pip
RUN pip3 install pex
RUN pip3 install -r /tmp/requirements.txt -c /tmp/constraints.txt
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

cat << EOF > inside_docker_build.sh
# Build python file from proto
/protoc/bin/protoc --python_out=/workspace/src/tradefed_cluster/configs/ \
  --proto_path /workspace/src/tradefed_cluster/configs/ \
  /workspace/src/tradefed_cluster/configs/lab_config.proto

/protoc/bin/protoc --python_out=/workspace/src/ \
--proto_path /workspace/src/ \
/workspace/src/com_google_deviceinfra/src/devtools/common/metrics/stability/model/proto/exception.proto

/protoc/bin/protoc --python_out=/workspace/src/ \
--proto_path /workspace/src/ \
/workspace/src/src/devtools/common/metrics/stability/model/proto/error_id.proto

/protoc/bin/protoc --python_out=/workspace/src/ \
--proto_path /workspace/src/ \
/workspace/src/src/devtools/common/metrics/stability/model/proto/error_type.proto

/protoc/bin/protoc --python_out=/workspace/src/ \
--proto_path /workspace/src/ \
/workspace/src/src/devtools/common/metrics/stability/model/proto/namespace.proto

/protoc/bin/protoc --python_out=/workspace/src/ \
--proto_path /workspace/src/ \
/workspace/src/com_google_deviceinfra/src/devtools/common/metrics/stability/rpc/proto/rpc_error_payload.proto

/protoc/bin/protoc --python_out=/workspace/src/ \
--proto_path /workspace/src/ \
/workspace/src/src/devtools/common/metrics/stability/rpc/proto/rpc_error.proto

/protoc/bin/protoc --python_out=/workspace/src/ \
--proto_path /workspace/src/ \
/workspace/src/google3/third_party/deviceinfra/src/devtools/deviceinfra/host/daemon/proto/health.proto

# Generate gRPC server and client code for health.proto.
python3 -m grpc_tools.protoc \
  --proto_path /workspace/src/ \
  --grpc_python_out=/workspace/src/ \
  /workspace/src/google3/third_party/deviceinfra/src/devtools/deviceinfra/host/daemon/proto/health.proto

cd /workspace
# Build mtt pex package.
pex --python="python3.13" --python="python3.12" --python="python3.11" \
  --python="python3.10" --python="python3.9" \
  --python-shebang="/usr/bin/env python3" \
  --pip-version latest-compatible \
  -D src \
  -r requirements.txt \
  --constraints constraints.txt \
  -m multitest_transport.cli.cli \
  -o mtt

# Build zip file include all mtt source.
cd src/
zip -r /workspace/mtt.zip *
cd ..

# Build mtt_lab pex package.
cp mtt src/mtt_binary
pex --python="python3.13" --python="python3.12" --python="python3.11" \
  --python="python3.10" --python="python3.9" \
  --python-shebang="/usr/bin/env python3" \
  --pip-version latest-compatible \
  -D src \
  -r requirements.txt \
  --constraints constraints.txt \
  -m multitest_transport.cli.lab_cli \
  -o mtt_lab
EOF
chmod +x inside_docker_build.sh
echo "Starting build inside Docker at: $(date)"
docker run --rm --mount type=bind,source="$CLI_DIR",target=/workspace docker_pex sh -c /workspace/inside_docker_build.sh
echo "Build inside Docker finished at: $(date)"
cd -

popd
