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

# Path to the docker compose file
COMPOSE_FILE="docker-compose.yml"

# --- Environment Variables for MTT ---
# You can override these by setting them in your shell before running the script.
export OPERATION_MODE="${OPERATION_MODE:-on_premise}"
# export MTT_CONTROL_SERVER_URL="${MTT_CONTROL_SERVER_URL:-http://localhost:8000}"
export MTT_CONTROL_SERVER_URL="${MTT_CONTROL_SERVER_URL:-}"
# export MTT_CONTROL_FILE_SERVER_URL="${MTT_CONTROL_FILE_SERVER_URL:-http://localhost:8006}"
export MTT_CONTROL_FILE_SERVER_URL="${MTT_CONTROL_FILE_SERVER_URL:-}"
# export MTT_CONTROL_SERVER_PORT="${MTT_CONTROL_SERVER_PORT:-8000}"
export MTT_CONTROL_SERVER_PORT="${MTT_CONTROL_SERVER_PORT:-}"
export LAB_NAME="${LAB_NAME:-mtt-lab}"
# export CLUSTER="${CLUSTER:-mtt-cluster}"
export MTT_ENABLE_CONFIG_SERVICE="${MTT_ENABLE_CONFIG_SERVICE:-false}"
export MTT_CONFIG_SERVICE_GRPC_PORT="${MTT_CONFIG_SERVICE_GRPC_PORT:-8081}"
export TF_GLOBAL_CONFIG_PATH="${TF_GLOBAL_CONFIG_PATH:-}"
export MTT_SERVER_LOG_LEVEL="${MTT_SERVER_LOG_LEVEL:-info}"
export MTT_ENABLE_LAB_CONSOLE_UI="${MTT_ENABLE_LAB_CONSOLE_UI:-true}"
export LABCONSOLE_SERVER_GRPC_PORT="${LABCONSOLE_SERVER_GRPC_PORT:-8080}"
export LABCONSOLE_SERVER_REST_PORT="${LABCONSOLE_SERVER_REST_PORT:-9000}"
export LAB_CONSOLE_PORT="${LAB_CONSOLE_PORT:-4200}"
export IS_OMNILAB_BASED="${IS_OMNILAB_BASED:-true}"

show_usage() {
  echo "Usage: $0 {up|down|logs|restart}"
  echo "Commands:"
  echo "  up       Start services in the background"
  echo "  down     Stop and remove containers, networks, and volumes"
  echo "  logs     View real-time logs from all containers"
  echo "  restart  Restart the containers"
  exit 1
}

COMMAND=$1

case $COMMAND in
  up)
    echo "Starting MTT services according to ${COMPOSE_FILE}..."
    # -d runs the containers in the background
    docker compose -f "${COMPOSE_FILE}" up -d
    echo "Services started successfully."
    echo "Run '$0 logs' to view logs."
    ;;
  down)
    echo "Stopping MTT services gracefully..."
    # down stops containers and removes them, along with networks and volumes
    docker compose -f "${COMPOSE_FILE}" down
    echo "Services stopped and cleaned up."
    ;;
  logs)
    docker compose -f "${COMPOSE_FILE}" logs -f
    ;;
  restart)
    echo "Restarting MTT services..."
    docker compose -f "${COMPOSE_FILE}" restart
    echo "Services restarted."
    ;;
  *)
    show_usage
    ;;
esac
