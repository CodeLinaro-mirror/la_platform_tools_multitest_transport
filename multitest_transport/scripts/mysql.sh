#!/bin/bash

function start_mysql_database {
  # Skip starting DB if URI already set
  if [[ -n "${SQL_DATABASE_URI}" ]]; then return; fi

  echo "Starting MySQL database..."
  DB_NAME="ats_db"
  local datadir="$1/${DB_NAME}"
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
}