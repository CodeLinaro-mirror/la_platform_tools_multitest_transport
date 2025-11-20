#!/bin/bash

# This script is the central controller for the JuiceFS service stack.
# It handles the complex startup and shutdown procedures that
# Docker Compose alone cannot.

set -e

# Define the compose command with the correct file to make this script robust
COMPOSE_CMD="docker compose -f docker-compose.jfs.yml"

show_usage() {
  cat <<EOUSAGE
Usage: $0 [flags] {up|down|format|destroy}

Manages the JuiceFS service stack (MySQL, SeaweedFS, and Cache Manager).

Commands:
  up        Builds images, starts all services, creates the mount, and formats the filesystem.
  down      Stops services, force-unmounts the host path, destroys the filesystem, and removes all volumes.
  format    (Re)formats the JuiceFS filesystem. (Backend must be running).
  destroy   (Re)destroys the JuiceFS filesystem. (Backend must be running).
  -h, --help  Show this help message.

Flags (these override .env values):
  --jfs-volume-ip <ip>            IP address of the JuiceFS service host.
  --mysql-root-password <pass>    MySQL root password.
  --mysql-user <user>             MySQL user for the JuiceFS metadata database.
  --mysql-password <pass>         MySQL password for the JuiceFS metadata database.
  --mysql-port <port>             Port of the JuiceFS metadata service.
  --seaweedfs-master-port <port>  Port of the SeaweedFS master service.
  --seaweedfs-filer-port <port>   Port of the SeaweedFS filer UI service.
  --seaweedfs-s3-port <port>      Port of the SeaweedFS S3 API service.
  --host-mnt-path <path>          Path for the host mount (e.g., /mnt/jfs).
  --cache-size <GiB>              Cache limit in GiB on the central file server. It should be less than JFS_CAPACITY.
  --jfs-capacity <GiB>            JuiceFS filesystem's total capacity in GiB.
  --cache-manager-image <image>   Cache manager's docker image.

EOUSAGE

  exit 0
}

# --- Configuration ---
# Loads environment variables from .env and exports them.
# Exporting is KEY, as it allows flags to override them.
load_env() {
  if [ -f .env ]; then
    echo "Loading default environment variables from .env..."
    # export all variables from .env
    export $(grep -v '^#' .env | xargs)
  else
    echo "ERROR: .env file not found."
    exit 1
  fi
}

# Checks that all required variables are set (either by .env or flags)
check_env() {
  local required_vars=(
    JFS_VOLUME_IP
    MYSQL_ROOT_PASSWORD MYSQL_USER MYSQL_PASSWORD MYSQL_DATABASE MYSQL_PORT
    SEAWEEDFS_MASTER_PORT SEAWEEDFS_FILER_PORT SEAWEEDFS_S3_PORT
    BUCKET_NAME
    JFS_VOLUME_NAME
    JFS_CAPACITY
    HOST_MNT_PATH
    CACHE_SIZE
    CACHE_MANAGER_IMAGE
  )
  for var in "${required_vars[@]}"; do
    if [ -z "${!var}" ]; then
      echo "ERROR: Environment variable ${var} is not set. Please set it in .env or via a flag."
      exit 1
    fi
  done
}

# --- Reusable Task Functions ---
format_filesystem() {
  $COMPOSE_CMD --profile jfs-tasks --profile jfs-setup run --rm format
}

destroy_filesystem() {
  echo ""
  echo -e "\033[0;31m"
  echo "This will destroy the filesystem on the *backend*. It will not unmount clients."
  read -p "Confirm you have unmounted all clients to this Juicefs filesystem. Press y to confirm: " -n 1 -r
  echo -e "\033[0m" # Reset color
  echo "" # Move to new line after input

  # Check if the reply is 'y' or 'Y'
  if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "User confirmed. Proceeding with filesystem destruction..."
  $COMPOSE_CMD --profile jfs-tasks --profile jfs-setup run --rm destroy
  else
    echo "Destroy operation cancelled by user."
    echo "Skipping filesystem destroy and aborting the 'down' command to prevent an inconsistent state."
    exit 1
  fi
}


# --- Main Orchestration Functions ---

# STAGE 1: BRING UP THE STACK
up() {
  echo "--- [UP] Starting JuiceFS Stack ---"

  $COMPOSE_CMD --profile jfs-setup up -d --wait

  format_filesystem

  if [ -z "${HOST_MNT_PATH}" ]; then
    echo "ERROR: HOST_MNT_PATH is not set in .env file."
    exit 1
  fi
  sudo mkdir -p ${HOST_MNT_PATH}

  $COMPOSE_CMD --profile jfs-vol up -d --wait

  echo "---"
  echo "✅ SERVICE STARTUP COMPLETE"
  echo "---"
  echo "Filesystem mounted at: ${HOST_MNT_PATH}"

  cat <<EOM

The service stack is running on ${JFS_VOLUME_IP}.
Clients can now mount the filesystem.

Run this on the client machine (replace <MOUNTPOINT>):

  juicefs mount \\
    --storage s3 \\
    --bucket http://${JFS_VOLUME_IP}:${SEAWEEDFS_S3_PORT}/${BUCKET_NAME} \\
    "mysql://${MYSQL_USER}:${MYSQL_PASSWORD}@(${JFS_VOLUME_IP}:${MYSQL_PORT})/${MYSQL_DATABASE}" \\
    <MOUNTPOINT> -d

EOM
}

# STAGE 2: TEAR DOWN THE STACK
down() {
  echo "--- [DOWN] Tearing Down JuiceFS Stack ---"

  $COMPOSE_CMD --profile jfs-vol down

  destroy_filesystem

  $COMPOSE_CMD --profile jfs-setup down -v

  echo "---"
  echo "✅ SERVICE TEARDOWN COMPLETE"
  echo "---"
}

# --- Script Entrypoint ---
main() {
  # Load configuration first
  load_env

  MAIN_COMMAND=""

  # This loop parses all flags and finds the one main command
  while [ "$#" -gt 0 ]; do
    case "$1" in
      # --- Flags ---
      # Note: We 'export' the variable, which makes it override the .env
      # value for both this script AND for 'docker compose'.
      --jfs-volume-ip)
        export JFS_VOLUME_IP="$2"
        echo "Overriding JFS_VOLUME_IP from flag."
        shift 2
        ;;
      --mysql-root-password)
        export MYSQL_ROOT_PASSWORD="$2"
        echo "Overriding MYSQL_ROOT_PASSWORD from flag."
        shift 2
        ;;
      --mysql-user)
        export MYSQL_USER="$2"
        echo "Overriding MYSQL_USER from flag."
        shift 2
        ;;
      --mysql-password)
        export MYSQL_PASSWORD="$2"
        echo "Overriding MYSQL_PASSWORD from flag."
        shift 2
        ;;
      --mysql-port)
        export MYSQL_PORT="$2"
        echo "Overriding MYSQL_PORT from flag."
        shift 2
        ;;
      --seaweedfs-master-port)
        export SEAWEEDFS_MASTER_PORT="$2"
        echo "Overriding SEAWEEDFS_MASTER_PORT from flag."
        shift 2
        ;;
      --seaweedfs-filer-port)
        export SEAWEEDFS_FILER_PORT="$2"
        echo "Overriding SEAWEEDFS_FILER_PORT from flag."
        shift 2
        ;;
      --seaweedfs-s3-port)
        export SEAWEEDFS_S3_PORT="$2"
        echo "Overriding SEAWEEDFS_S3_PORT from flag."
        shift 2
        ;;
      --host-mnt-path)
        export HOST_MNT_PATH="$2"
        echo "Overriding HOST_MNT_PATH from flag."
        shift 2
        ;;
      --cache-size)
        export CACHE_SIZE="$2"
        echo "Overriding CACHE_SIZE from flag."
        shift 2
        ;;
      --jfs-capacity)
        export JFS_CAPACITY="$2"
        echo "Overriding JFS_CAPACITY from flag."
        shift 2
        ;;
      --cache-manager-image)
        export CACHE_MANAGER_IMAGE="$2"
        echo "Overriding CACHE_MANAGER_IMAGE from flag."
        shift 2
        ;;

      # --- Main Command ---
      up|down|format|destroy)
        if [ -n "$MAIN_COMMAND" ]; then
          echo "Error: Only one command (up, down, format, destroy) can be specified."
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
    format)
      echo "--- Running standalone task: Format Filesystem ---"
      format_filesystem
      ;;
    destroy)
      echo "--- Running standalone task: Destroy Filesystem ---"
      destroy_filesystem
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

