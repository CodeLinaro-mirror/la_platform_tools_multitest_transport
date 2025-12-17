#!/bin/bash

# This script is for client machines to mount a remote JuiceFS volume.
# It mounts the filesystem directly onto the host, which can then be
# used to back a Docker named volume.

set -e

show_usage() {
  cat <<EOUSAGE
Usage: $0 [flags] {up|down}

Manages a client-side mount for a remote JuiceFS volume.

Commands:
  up        Mounts the remote JuiceFS volume to the host path specified by --host-mnt-path.
  down      Unmounts the JuiceFS volume from the host path.
  -h, --help  Show this help message.

Flags (these override .env values):
  --jfs-volume-ip <ip>           IP address of the JuiceFS service host.
  --mysql-user <user>            MySQL user for the JuiceFS metadata database.
  --mysql-password <pass>        MySQL password for the JuiceFS metadata database.
  --mysql-port <port>            Port of the JuiceFS metadata service.
  --seaweedfs-s3-port <port>     Port of the SeaweedFS S3 API service.
  --host-mnt-path <path>         Path on this client machine to mount the volume.

EOUSAGE

  exit 0
}

# --- Configuration ---
# Loads environment variables from .env and exports them.
load_env() {
  if [ -f .env ]; then
    echo "Loading environment variables from .env..."
    export $(grep -v '^#' .env | xargs)
  else
    # This is not a fatal error for the client, as all vars can be passed via flags.
    echo "INFO: .env file not found. All required variables must be provided via flags."
  fi
}

# Checks that all required variables are set (either by .env or flags)
check_env() {
  local required_vars=(
    JFS_VOLUME_IP
    MYSQL_USER MYSQL_PASSWORD MYSQL_DATABASE MYSQL_PORT
    SEAWEEDFS_S3_PORT
    BUCKET_NAME
    HOST_MNT_PATH
  )
  for var in "${required_vars[@]}"; do
    if [ -z "${!var}" ]; then
      echo "ERROR: Environment variable ${var} is not set. Please set it in .env or via a flag."
      show_usage
      exit 1
    fi
  done
}

# --- Core Functions ---

# Installs the JuiceFS client if it is not already installed
install_juicefs() {
  echo "--> Checking for JuiceFS client..."
  if ! command -v juicefs &> /dev/null; then
    echo "JuiceFS client not found. Attempting to install it..."
    # Install the latest JuiceFS client using the official script
    curl -sSL https://d.juicefs.com/install | sudo sh -
    echo "JuiceFS client installed successfully."
  else
    echo "JuiceFS client already installed."
  fi
}

# Checks if the remote JuiceFS volume is ready
check_juicefs_volume_status() {
  echo "--> Checking remote JuiceFS volume status..."
  if ! juicefs status "mysql://${MYSQL_USER}:${MYSQL_PASSWORD}@tcp(${JFS_VOLUME_IP}:${MYSQL_PORT})/${MYSQL_DATABASE}" &> /dev/null; then
    echo "ERROR: JuiceFS volume at ${JFS_VOLUME_IP} is not ready or accessible."
    echo "Please ensure the JuiceFS service is running on the server and the volume is formatted."
    exit 1
  fi
  echo "JuiceFS volume is ready."
}

# Mounts the remote JuiceFS filesystem to the host
mount_fs() {
  check_juicefs_volume_status

  if mountpoint -q "${HOST_MNT_PATH}"; then
    MOUNT_TYPE=$(df -Th "${HOST_MNT_PATH}" | awk 'NR==2 {print $2}')
    if [ "$MOUNT_TYPE" == "fuse.juicefs" ]; then
      echo "INFO: ${HOST_MNT_PATH} is already mounted as a JuiceFS volume. Skipping mount."
      return
    else
      echo "ERROR: ${HOST_MNT_PATH} is already mounted, but not as fuse.juicefs (type: $MOUNT_TYPE)."
      echo "Please unmount it or choose a different --host-mnt-path."
      exit 1
    fi
  fi

  echo "--> Creating mount point directory: ${HOST_MNT_PATH}"
  sudo mkdir -p "${HOST_MNT_PATH}"

  echo "--> Mounting JuiceFS volume..."
  # The command is run with sudo and placed in the background (-d)
  sudo juicefs mount \
    --storage s3 \
    --bucket "http://${JFS_VOLUME_IP}:${SEAWEEDFS_S3_PORT}/${BUCKET_NAME}" \
    "mysql://${MYSQL_USER}:${MYSQL_PASSWORD}@tcp(${JFS_VOLUME_IP}:${MYSQL_PORT})/${MYSQL_DATABASE}" \
    "${HOST_MNT_PATH}" -d

  echo "✅ JuiceFS volume successfully mounted at ${HOST_MNT_PATH}"
}

# Creates a Docker volume backed by the host mount path
create_vol() {
    echo "--> Creating Docker volume 'mtt-jfs'..."
    if docker volume inspect mtt-jfs &> /dev/null; then
        echo "Docker volume 'mtt-jfs' already exists. Skipping creation."
    else
        docker volume create \
          --driver local \
          --opt type=none \
          --opt o=bind \
          --opt device=${HOST_MNT_PATH} \
          mtt-jfs
        echo "✅ Docker volume 'mtt-jfs' created."
    fi
}

# Unmounts the JuiceFS filesystem from the host
unmount_fs() {
  echo "--> Unmounting JuiceFS volume from ${HOST_MNT_PATH}..."
  # Check if the path is actually a mount point before trying to unmount
  if mountpoint -q "${HOST_MNT_PATH}"; then
    sudo juicefs umount "${HOST_MNT_PATH}"
    echo "✅ Unmount complete."
  else
    echo "INFO: ${HOST_MNT_PATH} is not a mount point. Skipping unmount."
  fi
}

# Removes the Docker volume
destroy_vol() {
    echo "--> Removing Docker volume 'mtt-jfs'..."
    if docker volume inspect mtt-jfs &> /dev/null; then
        docker volume rm mtt-jfs
        echo "✅ Docker volume 'mtt-jfs' removed."
    else
        echo "INFO: Docker volume 'mtt-jfs' not found. Skipping removal."
    fi
}

# --- Orchestration Functions ---

# Brings up the entire client-side setup
up() {
  install_juicefs
  mount_fs
  create_vol
}

# Tears down the entire client-side setup
down() {
  destroy_vol
  unmount_fs
}


# --- Script Entrypoint ---
main() {
  load_env

  MAIN_COMMAND=""

  while [ "$#" -gt 0 ]; do
    case "$1" in
      # --- Flags ---
      --jfs-volume-ip)
        export JFS_VOLUME_IP="$2"
        shift 2
        ;;
      --mysql-user)
        export MYSQL_USER="$2"
        shift 2
        ;;
      --mysql-password)
        export MYSQL_PASSWORD="$2"
        shift 2
        ;;
      --mysql-port)
        export MYSQL_PORT="$2"
        shift 2
        ;;
      --seaweedfs-s3-port)
        export SEAWEEDFS_S3_PORT="$2"
        shift 2
        ;;
      --host-mnt-path)
        export HOST_MNT_PATH="$2"
        shift 2
        ;;

      # --- Main Command ---
      up|down)
        if [ -n "$MAIN_COMMAND" ]; then
          echo "Error: Only one command (up, down) can be specified."
          show_usage
          exit 1
        fi
        MAIN_COMMAND="$1"
        shift 1
        ;;

      # --- Help Command ---
      -h|--help)
        show_usage
        exit 0
        ;;

      # --- Unknown ---
      *)
        echo "Error: Unknown argument: $1"
        show_usage
        exit 1
        ;;
    esac
  done

  check_env

  case "$MAIN_COMMAND" in
    up)
      up
      ;;
    down)
      down
      ;;
    "")
      echo "Error: No command specified."
      show_usage
      exit 1
      ;;
  esac
}

# Run the main function
main "$@"
