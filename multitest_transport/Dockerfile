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

FROM ubuntu:20.04
MAINTAINER Android Test Station <mtt-eng@google.com>

ENV LC_ALL en_US.UTF-8
ENV LANG en_US.UTF-8
ENV LANGUAGE en_US.UTF-8
ENV PATH /tmp/custom_sdk_tools:${PATH}

# Make sure apt-get retries on failures
RUN echo 'Acquire::Retries "3";' > /etc/apt/apt.conf.d/80retries

RUN export DEBIAN_FRONTEND=noninteractive && apt-get update && apt-get install -y \
        apt-utils \
        cec-utils \
        cron \
        daemontools \
        fuse-zip \
        git \
        iputils-ping \
        libc++-dev \
        locales \
        locales-all \
        lsof \
        mariadb-server \
        ndppd \
        netdata \
        socat \
        software-properties-common \
        tini \
        tzdata \
        usbutils \
        unzip \
        wget \
        xz-utils \
        zip

RUN add-apt-repository ppa:deadsnakes/ppa
RUN export DEBIAN_FRONTEND=noninteractive; apt update -qq; apt install -y -qq \
  python python3.8 python3.9 python3-pip \
  python3-distutils python3.9-distutils

# Set minimal Python version that client supports.
RUN update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.9 1000
RUN pip3 install --upgrade setuptools pip
RUN pip3 install \
        absl-py \
        attrs \
        cachetools \
        flask \
        grpcio \
        bcrypt \
        gunicorn==20.1.0
# Install python2 pip.
RUN wget -q --retry-connrefused -O /tmp/get-pip.py https://bootstrap.pypa.io/pip/2.7/get-pip.py && \
    python /tmp/get-pip.py && \
    rm /tmp/get-pip.py

# Install erlang which is used by rabbitmq.
RUN export DEBIAN_FRONTEND=noninteractive && apt-get update && apt-get install -y \
        curl \
        apt-transport-https \
        lsb-release
RUN curl -fsSL https://packages.erlang-solutions.com/ubuntu/erlang_solutions.asc \
        | gpg --dearmor -o /etc/apt/trusted.gpg.d/erlang.gpg
RUN echo "deb https://packages.erlang-solutions.com/ubuntu $(lsb_release -cs) contrib" \
        | tee /etc/apt/sources.list.d/erlang.list
# Install erlang-nox to save container image size (=3.68GB).
# With erlang, container image size could go to 4.78GB.
RUN export DEBIAN_FRONTEND=noninteractive && apt-get update && apt-get install -y \
        erlang-nox

# Install rabbitmq from official channel.
RUN curl -s https://packagecloud.io/install/repositories/rabbitmq/rabbitmq-server/script.deb.sh \
        | bash
RUN export DEBIAN_FRONTEND=noninteractive && apt-get update && apt-get install -y \
        rabbitmq-server

# Enable rabbitmq management plugin for reliability checking
RUN rabbitmq-plugins enable rabbitmq_management

# Installing dependencies for VTS
# Reference: https://android.googlesource.com/platform/test/vts/+/refs/heads/android10-tests-dev/script/setup.sh
# VTS 9.0 depends on libncurses5.
RUN export DEBIAN_FRONTEND=noninteractive && apt-get update && apt-get install -y \
        python-dev \
        python-protobuf \
        protobuf-compiler \
        python-setuptools \
        # python-pip \
        # python3-pip \
        # python-virtualenv \
        build-essential \
        python-tk \
        libjpeg-dev \
        libncurses5 \
        libtiff-dev
# Install the Python3 version of virtualenv for compatibility with newer test
# suites, but pin the version to one with a proven compatibility with VTS.
# VTS 9.0 will require "--python-venv:python-version=2.7".
RUN pip3 install virtualenv==20.19.0

# Install JDK11 from AOSP (https://android.googlesource.com/platform/prebuilts/jdk/jdk11.git/+/4b776e23b6964354047211b1e343dc3ca14ce60a)
RUN mkdir -p /jdk/jdk11 && \
    cd /jdk/jdk11 && \
    git init && \
    git remote add origin https://android.googlesource.com/platform/prebuilts/jdk/jdk11.git && \
    git config core.sparseCheckout true && \
    echo "linux-x86/" >> .git/info/sparse-checkout && \
    git fetch origin 4b776e23b6964354047211b1e343dc3ca14ce60a --depth 1 && \
    git checkout 4b776e23b6964354047211b1e343dc3ca14ce60a && \
    rm -rf .git/ && \
    cd -
ENV JAVA_HOME /jdk/jdk11/linux-x86
ENV PATH ${JAVA_HOME}/bin:${PATH}

# Install SDK tools (aapt, adb, fastboot, mke2fs)
RUN mkdir -p /sdk_tools/lib64
# Use wget for more reliable retries
RUN wget -q --retry-connrefused -O build-tools.zip https://dl.google.com/android/repository/build-tools_r33.0.2-linux.zip \
    && unzip -jq build-tools.zip -d /sdk_tools android-13/aapt \
    && unzip -jq build-tools.zip -d /sdk_tools android-13/aapt2 \
    && unzip -jq build-tools.zip -d /sdk_tools/lib64 android-13/lib64/* \
    && rm build-tools.zip
RUN wget -q --retry-connrefused -O platform-tools.zip https://dl.google.com/android/repository/platform-tools_r33.0.3-linux.zip \
    && unzip -jq platform-tools.zip -d /sdk_tools \
        platform-tools/adb \
        platform-tools/fastboot \
        platform-tools/mke2fs \
    && rm platform-tools.zip
ENV PATH /tmp/custom_sdk_tools:/sdk_tools:${PATH}
ENV LD_LIBRARY_PATH /sdk_tools/lib64:${LD_LIBRARY_PATH}

# Install Google Cloud SDK
# Reference: https://github.com/GoogleCloudPlatform/cloud-sdk-docker/blob/master/Dockerfile
ENV CLOUD_SDK_VERSION=363.0.0
ENV CLOUD_SDK_ROOT=/usr/lib/google-cloud-sdk
RUN apt-get -qqy update && apt-get install -qqy \
        curl \
        gcc \
        python3-dev \
        python3-pip \
        apt-transport-https \
        openssh-client \
        git \
        make \
        gnupg && \
    pip3 install -U crcmod && \
    export CLOUD_SDK_REPO="cloud-sdk" && \
    echo "deb https://packages.cloud.google.com/apt $CLOUD_SDK_REPO main" > /etc/apt/sources.list.d/google-cloud-sdk.list && \
    curl https://packages.cloud.google.com/apt/doc/apt-key.gpg | apt-key add - && \
    apt-get update && \
    apt-get install -y --allow-unauthenticated \
        google-cloud-sdk=${CLOUD_SDK_VERSION}-0 \
        google-cloud-sdk-datastore-emulator=${CLOUD_SDK_VERSION}-0

# Installing dependencies for TVTS
RUN export DEBIAN_FRONTEND=noninteractive && \
        curl -sL https://deb.nodesource.com/setup_18.x -o nodesource_setup.sh && \
        bash nodesource_setup.sh && \
        apt-get install -y nodejs && \
        rm nodesource_setup.sh

# Install TVTS prerequisites
# The perfetto package is only supported by python 3.9
RUN pip install perfetto
RUN pip install matplotlib

# Install cuttlefish-common and add MTT user (root) to the groups
# debuild -d skips checking the dependency of debhelper-compat 12.
# Reference: https://android.googlesource.com/device/google/cuttlefish/+/refs/heads/android13-dev/README.md
ARG CUTTLEFISH_COMMON_COMMIT=09546cf4a618563071beb42508fc7b4a5336ad29
RUN git clone https://github.com/google/android-cuttlefish --no-checkout --single-branch /tmp/cuttlefish-common/src && \
    cd /tmp/cuttlefish-common/src && \
    git checkout ${CUTTLEFISH_COMMON_COMMIT} && \
    apt-get install -y devscripts config-package-dev debhelper-compat && \
    debuild -i -us -uc -b -d && \
    apt-get install -y ../cuttlefish-common_*_amd64.deb iproute2 rsyslog && \
    cd - && \
    rm -rf /tmp/cuttlefish-common/src && \
    groupadd --force kvm && \
    groupadd --force cvdnetwork && \
    groupadd --force render && \
    usermod -aG kvm,cvdnetwork,render root

# Ubuntu has a weird bug which is not allowing us to boot linux kernel when
# kernel and u-boot modes are different (for example u-boot is 32 bit and
# linux is 64 bit): https://bugs.launchpad.net/ubuntu/+source/grub2/+bug/1876737
# Fixing this by downloading the latest debian grub-efi-ie32-bin deb package
# instead.
#
# Update: No need to update this along with OS since that's just a static
# binaries that are used to boot OtherOS and OpenWRT. In case link will become
# invalid, just use another latest debian grub-efi-ia32-bin
#
# Test: To verify it works fine need to check OpenWRT succesfully booted by
# verifying we have kernel log inside <cvd-instance>/crosvm_openwrt_boot.log
# and virtual wifi works fine inside guest.
RUN echo "deb [trusted=yes] http://ftp.debian.org/debian sid main" > /etc/apt/sources.list.d/debian.list && \
    apt-get update && \
    apt-get install -y grub-efi-ia32-bin

# TODO: Remove this flag after a couple of releases.
ENV MTT_SUPPORT_BRIDGE_NETWORK true

# Install acloud
# TODO: Replace /url with ?alt=media when it works
ARG ACLOUD_DOWNLOAD_URL='https://www.googleapis.com/android/internal/build/v3/builds/10988168/aosp_cf_x86_64_phone-trunk_staging-userdebug/attempts/latest/artifacts/acloud_prebuilt/url'
ENV ACLOUD_PREBUILT_PATH=/bin/acloud_prebuilt
RUN wget -q --retry-connrefused -O ${ACLOUD_PREBUILT_PATH} ${ACLOUD_DOWNLOAD_URL} \
    && chmod +x ${ACLOUD_PREBUILT_PATH}

# Install libusb-1.0 with udev disabled, as it doesn't work without --net=host
ARG LIBUSB_VERSION=libusb-1.0.24
RUN wget -q --retry-connrefused -O ${LIBUSB_VERSION}.tar.bz2 http://downloads.sourceforge.net/project/libusb/libusb-1.0/${LIBUSB_VERSION}/${LIBUSB_VERSION}.tar.bz2 \
    && tar -xf ${LIBUSB_VERSION}.tar.bz2 \
    && cd ${LIBUSB_VERSION} \
    && ./configure --disable-udev \
    && make install \
    && ldconfig \
    && cd - \
    && rm -rf ${LIBUSB_VERSION}.tar.bz2 ${LIBUSB_VERSION}

# Install ffmpeg
ARG FFMPEG_VERSION=ffmpeg-release-amd64-static
RUN wget -q --retry-connrefused https://johnvansickle.com/ffmpeg/releases/${FFMPEG_VERSION}.tar.xz \
  && tar -xf ${FFMPEG_VERSION}.tar.xz \
  && cd ffmpeg-*-amd64-static \
  && mv ffmpeg ffprobe /usr/local/bin/ \
  && cd - \
  && rm -rf ffmpeg-*-amd64-static*

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
ENV MTT_REPORT_GENERATOR_JAR ${MTT_REPORT_GENERATOR_JAR_PATH}
ENV MTT_TEST_OUTPUT_DIR ${MTT_STORAGE_PATH}/app_default_bucket/test_runs
ENV MTT_TEST_WORK_DIR ${MTT_STORAGE_PATH}/tmp
ENV MTT_USE_HOST_ADB ""

# Authenticate on GCE (ignored if running locally or file not provided)
ENV GOOGLE_APPLICATION_CREDENTIALS /tmp/keyfile/key.json

# In case there are libraries in context folder
COPY /usr/ /usr/

COPY /mtt/ /mtt/
# Compile and remove all python source files.
RUN python3 -m compileall -bq /mtt/google3 \
    && find /mtt/google3 -type f -iname "*.py" ! -iname "gunicorn_config.py" -exec rm -rf {} \;
# Unzip the selected prebuilt TF runner
RUN unzip -q /mtt/prebuilts/tradefed/${MTT_TRADEFED_PREBUILT} -d /tradefed
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
