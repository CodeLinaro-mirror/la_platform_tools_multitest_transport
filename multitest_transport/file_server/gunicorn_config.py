"""Gunicorn configuration and entrypoint for the production server.

See Also:
  https://docs.gunicorn.org/en/stable/settings.html#server-hooks
"""
import os
import shutil
import threading
import time

# Name of the temporary upload directory to create and manage
UPLOAD_DIR_NAME = '.file_server'
# Maximum temporary file idle time
UPLOAD_TIMEOUT = 60 * 60  # 1 hour
# Interval at which to check for stale temporary upload files
CLEAN_INTERVAL = 5 * 60  # 5 minutes

# Server logger instance
logger = None
# File server's base path, must be provided as $STORAGE_PATH
storage_path = None
# Temporary upload directory, created on start and deleted on exit
tmp_upload_dir = None


def on_starting(server):
  """Verify the storage path before starting the server."""
  global logger
  logger = server.log
  global storage_path
  storage_path = os.getenv('STORAGE_PATH')
  if not storage_path:
    raise ValueError('Storage path is required')
  if not os.path.isdir(storage_path):
    raise ValueError('Storage path must be an existing directory')

  # Check for DATASTORE_EMULATOR_HOST
  emulator_host = os.getenv('DATASTORE_EMULATOR_HOST')
  if not emulator_host:
    logger.error('DATASTORE_EMULATOR_HOST environment variable is not set.')
    raise ValueError('DATASTORE_EMULATOR_HOST is required')
  logger.info('DATASTORE_EMULATOR_HOST is set to: %s', emulator_host)


def when_ready(_):
  """Create the upload directory after starting."""
  global tmp_upload_dir
  tmp_upload_dir = os.path.join(storage_path, UPLOAD_DIR_NAME)
  logger.info('Using temporary upload directory \'%s\'', tmp_upload_dir)
  os.makedirs(tmp_upload_dir, exist_ok=True)
  threading.Thread(target=_clean_tmp_directory, daemon=True).start()


def post_worker_init(worker):
  """Pass directory information to worker."""
  worker.wsgi.logger = logger
  worker.wsgi.root_path = storage_path
  worker.wsgi.tmp_upload_dir = tmp_upload_dir


def on_exit(_):
  """Delete the upload directory before exiting."""
  shutil.rmtree(tmp_upload_dir, ignore_errors=True)


def _clean_tmp_directory():
  """Periodically delete stale temporary upload files."""
  while True:
    min_modification_time = time.time() - UPLOAD_TIMEOUT
    with os.scandir(tmp_upload_dir) as it:
      for entry in it:
        if entry.is_file() and entry.stat().st_mtime < min_modification_time:
          logger.info('Deleting expired upload \'%s\'', entry.name)
          os.remove(entry.path)
    time.sleep(CLEAN_INTERVAL)
