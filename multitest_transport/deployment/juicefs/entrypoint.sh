#!/bin/sh
set -e

# Define a cleanup function
cleanup() {
    echo "Shutting down... Unmounting /mnt"
    juicefs umount /mnt
    echo "Unmount complete. Waiting for process to exit."
    wait "$CMD_PID" # Wait for the command process to die
    echo "Shutdown complete."
}

# Trap SIGTERM (the default for 'docker compose down')
# and SIGINT
trap 'cleanup' TERM INT

# Run the command passed from docker-compose in the background
"$@" &

# Store the process ID
CMD_PID=$!

# Wait for the command process to exit
wait "$CMD_PID"
