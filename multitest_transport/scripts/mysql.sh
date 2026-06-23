#!/bin/bash

function start_mysql_database {
  # Skip starting DB if URI already set
  if [[ -n "${SQL_DATABASE_URI}" ]]; then return; fi

  echo "Starting MySQL database..."
  DB_NAME="ats_db"
  local datadir="$1/${DB_NAME}"
  local skip_wait="${2:-true}"

  if [[ "${skip_wait}" != "true" && "${skip_wait}" != "false" ]]; then
    echo "Error: skip_wait must be 'true' or 'false', got '${skip_wait}'"
    return 1
  fi
  MYSQL_SOCKET="${datadir}/mysqld.sock"
  local pidfile="${datadir}/mysqld.pid"
  # Ensure DB directory is created and initialized
  mkdir -p "${datadir}"
  chown -R mysql:mysql "${datadir}"
  # Start DB with specific socket/pid to prevent clashes. Does not check access
  # (system/grant tables don't need to exist), but network access is disabled.
  mysqld_safe \
    --socket="${MYSQL_SOCKET}" \
    --pid-file="${pidfile}" \
    --skip-grant-tables \
    --skip-networking \
    --datadir="${datadir}" \
    --log-error="${datadir}/error.log" \
    &
  SQL_DATABASE_URI="mysql+pymysql://root@/${DB_NAME}?unix_socket=${MYSQL_SOCKET}"

  if [[ "${skip_wait}" == "true" ]]; then
    echo "Skipping MySQL wait and initialization."
    return
  fi

  echo "Waiting for MySQL ready..."
  for i in $(seq 30)
  do
    if mysqladmin -S "$MYSQL_SOCKET" ping > /dev/null 2>&1; then
      echo "MySQL is started. Start initializing MySQL database..."
      mysql -S "${MYSQL_SOCKET}" -e "CREATE DATABASE IF NOT EXISTS ${DB_NAME}"
      mysql -S "${MYSQL_SOCKET}" -D "${DB_NAME}" < /deviceinfra/test_allocations.sql
      mysql -S "${MYSQL_SOCKET}" -D "${DB_NAME}" < /deviceinfra/unfinished_sessions.sql
      if [[ "${MTT_ENABLE_CONFIG_SERVICE}" == "true" ]]; then
        mysql -S "${MYSQL_SOCKET}" -D "${DB_NAME}" < /deviceinfra/device_config_table.sql
        mysql -S "${MYSQL_SOCKET}" -D "${DB_NAME}" < /deviceinfra/lab_config_table.sql
      fi
      echo "MySQL initialized"
      break
    else
      echo "MySQL is not started. Retrying in 1 second..."
      sleep 1
    fi
  done
}