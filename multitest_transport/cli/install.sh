#!/bin/bash
set -e -u

# Parse command line arguments
while [[ $# -gt 0 ]]; do
  case "$1" in
    --environment | -e) ENVIRONMENT="$2";;
    *) echo "Unknown argument $1"; exit 1; # fail-fast on unknown key
  esac
  shift # skip key
  shift # skip value
done

ENVIRONMENT="${ENVIRONMENT:-prod}"

if [[ ! ${ENVIRONMENT} =~ ^(prod|dogfood|latest)$ ]]; then
  echo "--environment must prod, dogfood or latest."
  exit 1
fi

MTT_BASE_URL="https://storage.googleapis.com/android-mtt.appspot.com/${ENVIRONMENT}"
MTT_ZIP_URL="${MTT_BASE_URL}/mtt.zip"
OLD_HOME_BIN_DIR="$HOME/bin"
HOME_BIN_DIR="$HOME/.local/bin"
PYTHON3_MINIMAL_MINOR_VERSION="10"
DOCKER_MINIMAL_API_VERSION="42"

function install_docker {
  docker_version=$(docker --version 2> /dev/null || echo "")

  if [ ! -z "$docker_version" ]
  then
    docker_api_version=$(docker version --format '{{.Server.APIVersion}}' 2> /dev/null | awk -F\. '{print $2}')
  fi

  if [ -z "$docker_version" ] || [ "$docker_api_version" -lt "$DOCKER_MINIMAL_API_VERSION" ]
  then
    echo "Install Docker Engine..."
    # Follow https://docs.docker.com/install/linux/docker-ce/ubuntu/
    # to install docker.
    sudo apt-get update
    sudo apt-get install -y \
      apt-transport-https \
      ca-certificates \
      curl \
      gnupg-agent \
      software-properties-common
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo apt-key add -
    sudo add-apt-repository \
      "deb [arch=amd64] https://download.docker.com/linux/ubuntu \
      $(lsb_release -cs) \
      stable"
    sudo apt-get update
    sudo apt-get install -y docker-ce docker-ce-cli containerd.io
  else
    echo "\"$docker_version\" is installed. Skip installing."
  fi
}

function setup_sudoless_docker {
  if ! groups $USER | grep -q '\bdocker\b'
  then
    echo "Add $USER to 'docker' group."
    sudo usermod -a -G docker $USER
    newgrp docker
  else
    echo "$USER is already in 'docker' group."
  fi
}

function install_mtt {
  # Clean up existing mtt.
  echo "Removing old mtt binary."
  rm -f ${OLD_HOME_BIN_DIR}/mtt

  echo "Install MTT CLI with pip."
  python3 -m pip install wheel
  python3 -m pip install $MTT_ZIP_URL
  which_mtt=$(which mtt 2> /dev/null || echo "")
  if [ -z "$which_mtt" ]
  then
    echo PATH=${HOME_BIN_DIR}:\$PATH >> $HOME/.bashrc
    export PATH=${HOME_BIN_DIR}:$PATH
    mtt version
  fi
}

function check_python {
  python3_version=$(python3 --version 2> /dev/null)
  if [ -z "$python3_version" ]
  then
    echo "Python 3 is not installed. Please install Python 3 first."
    exit 1
  fi

  python3_minor_version=$(python3 --version 2> /dev/null | awk -F\. '{print $2}')
  if [ "$python3_minor_version" -lt "$PYTHON3_MINIMAL_MINOR_VERSION" ]
  then
    echo "Python 3 version should be the greater than 3.9. Please upgrade Python first."
    exit 1
  fi
}

check_python
install_docker
install_mtt
# setup_sudoless_docker have to be the last line since it will start a
# new bash to login as docker group.
setup_sudoless_docker
