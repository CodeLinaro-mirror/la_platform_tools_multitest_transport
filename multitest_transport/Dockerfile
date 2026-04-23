# Copyright 2025 Google LLC
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

# Keep loading this internal base image until we have external compilation ready
FROM us.gcr.io/android-mtt/mtt:base_candidate
MAINTAINER Android Test Station <mtt-eng@google.com>

# Docker builds image by layers. If a layer changes, all the following layers
# will need to be rebuilt. So less frequent changes, e.g. install packages, will
# be built in the base layers. And frequent changes, e.g. set env, will be in
# later layers.
ARG MTT_GOOGLE_OAUTH2_CLIENT_ID=
ARG MTT_GOOGLE_OAUTH2_CLIENT_SECRET=
ARG MTT_REPORT_GENERATOR_JAR_DIR=/merge_report_generator
ARG MTT_REPORT_GENERATOR_JAR_PATH=${MTT_REPORT_GENERATOR_JAR_DIR}/report_generator_deploy.jar
ARG MTT_TRADEFED_PREBUILT=tradefed.zip
ARG MTT_VERSION=dev

ENV MTT_GOOGLE_OAUTH2_CLIENT_ID ${MTT_GOOGLE_OAUTH2_CLIENT_ID}
ENV MTT_GOOGLE_OAUTH2_CLIENT_SECRET ${MTT_GOOGLE_OAUTH2_CLIENT_SECRET}
ENV MTT_VERSION ${MTT_VERSION}
ENV MTT_STORAGE_PATH /data
ENV MTT_SERVER_LOG_LEVEL info

ENV MTT_CUSTOM_TF_CONFIG_FILE ${MTT_STORAGE_PATH}/host-config.xml
ENV MTT_LOG_DIR ${MTT_STORAGE_PATH}/log
ENV MTT_MH_WORK_DIR ${MTT_STORAGE_PATH}/mh
ENV MTT_REPORT_GENERATOR_JAR ${MTT_REPORT_GENERATOR_JAR_PATH}
ENV MTT_TEST_OUTPUT_DIR ${MTT_STORAGE_PATH}/app_default_bucket/test_runs
ENV MTT_TEST_WORK_DIR ${MTT_STORAGE_PATH}/tmp
ENV MTT_USE_HOST_ADB ""

# Authenticate on GCE (ignored if running locally or file not provided)
ENV GOOGLE_APPLICATION_CREDENTIALS /tmp/keyfile/key.json

# In case there are libraries in context folder
COPY /usr/ /usr/

COPY /mtt/ /mtt/

RUN mkdir -p /etc/envoy \
    && mv /mtt/envoy/envoy.yaml /etc/envoy/envoy.yaml \
    && mv /mtt/envoy/api_descriptor.pb /etc/envoy/api_descriptor.pb \
    && mv /mtt/envoy/envoy /usr/bin/envoy \
    && rm -rf /mtt/envoy

RUN python3 -m pip install /mtt/prebuilts/build_v4/ci-build-v4-py.tar.gz --no-deps
# Note that since Python 3.12, dist-packages is no longer used.
RUN cp -r /usr/local/lib/python3.10/dist-packages/google/android /mtt/google3/third_party/py/google
# Compile and remove all python source files. Explicitly don't compile
# absl/colour/flask/scipy/sqlalchemy_utils/sqlalchemy/numpy because google3's
# source code is only compatible with python 3.12+ and MTT still uses python
# 3.9. Need newer cryptography/OpenSSL to support Android Build V4 APIs.
# They are installed via pip.
RUN python3 -m compileall -bq \
    -x "/mtt/google3/third_party/py/(absl|colour|flask|scipy|sqlalchemy_utils|sqlalchemy|numpy|cryptography|OpenSSL)" /mtt/google3 \
    && find /mtt/google3 -type f -iname "*.py" ! -iname "gunicorn_config.py" -exec rm -rf {} \;
# Unzip the selected prebuilt TF runner
RUN unzip -q /mtt/prebuilts/tradefed/${MTT_TRADEFED_PREBUILT} -d /tradefed
# Unzip the device infra servers
RUN unzip -q /mtt/prebuilts/deviceinfra/deviceinfra.zip -d /deviceinfra
# Prepare the report generator jar used for merging reports
RUN unzip -q /mtt/prebuilts/tools/report_generator.zip -d ${MTT_REPORT_GENERATOR_JAR_DIR}

RUN rm -rf /mtt/prebuilts
ENV PATH /tradefed:${PATH}

# Setup scripts
RUN chmod 755 \
        /mtt/scripts/init.sh \
        /mtt/scripts/gen_subnets.py

VOLUME /data

# tini will forward signals to all child processes and wait for them to finish.
ENTRYPOINT ["tini", "-g", "-v", "--"]
CMD ["/mtt/scripts/init.sh"]
