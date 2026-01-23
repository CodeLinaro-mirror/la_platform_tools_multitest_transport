#!/bin/bash
set -e

# This script is intended to be run via
#`iblaze run //third_party/py/multitest_transport/ui2:sync_ui_to_docker --define dev_mode=true`
# which will build the UI in dev mode and copy it to the running docker container.
# And it will also do the incremental build if you change any source file,
# and then it will copy the new UI to the docker container.

# The generated files are available in the runfiles directory.
# The path to this script is in $0.
RUNFILES_DIR=$(dirname "$0")
readonly SCRIPT_PATH="$(realpath "${0}")"
readonly SOURCE_DIR="$(dirname "${SCRIPT_PATH}")"
echo "RUNFILES_DIR: ${RUNFILES_DIR}"
echo "SOURCE_DIR: ${SOURCE_DIR}"

# The path inside the container
DEST_PATH="/mtt/google3/third_party/py/multitest_transport/ui2"
# A temporary directory on the host to stage files before copying to Docker
TMP_DIR=$(mktemp -d)
echo "TMP_DIR: ${TMP_DIR}"
# Ensure cleanup on exit
trap 'rm -rf -- "$TMP_DIR"' EXIT

echo "Staging UI files in ${TMP_DIR}..."

# index.html is a source file, so we copy it from the source directory.
cp -L "${SOURCE_DIR}/index.html" "${TMP_DIR}/index.html"
# static files and JS are generated files from the runfiles.
cp -rL "${RUNFILES_DIR}/static" "${TMP_DIR}/static"

# Make the temporary directory writable, so we can delete it on exit.
find "${TMP_DIR}" -type d -exec chmod u+w {} +

# The server in the pre-built Docker image expects 'app.js'.
# In dev mode, we build 'dev_sources.concat.js', so we rename it.
if [ -f "${RUNFILES_DIR}/dev_sources.concat.js" ]; then
  echo "Staging dev_sources.concat.js as app.js"
  cp -L "${RUNFILES_DIR}/dev_sources.concat.js" "${TMP_DIR}/app.js"
else
  echo "Staging app.js"
  cp -L "${RUNFILES_DIR}/app.js" "${TMP_DIR}/app.js"
fi

echo "Syncing staged UI files to Docker container 'mtt'..."

# The '.' at the end of the source path copies the *contents* of the directory
MAX_RETRIES=999
RETRY_COUNT=0
until docker cp "${TMP_DIR}/." "mtt:${DEST_PATH}/"
do
  RETRY_COUNT=$((RETRY_COUNT+1))
  if [ "$RETRY_COUNT" -ge "$MAX_RETRIES" ]; then
    echo "Error: Could not copy files to container 'mtt' after $MAX_RETRIES attempts." >&2
    exit 1
  fi
  echo "Failed to copy files to container (Attempt ${RETRY_COUNT}/${MAX_RETRIES}). Retrying in 10s..."
  sleep 10
done

echo "Sync complete. Refresh your browser to see the changes!!!!!!"
