#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"
VENV_PYTHON="$ROOT_DIR/.venv/bin/python"
MARIADB_DIR="$BACKEND_DIR/.mariadb"
MARIADB_CONFIG="$MARIADB_DIR/my.cnf"
MARIADB_PID_FILE="$MARIADB_DIR/run/mysqld.pid"
BACKEND_ENV_FILE="$BACKEND_DIR/.env"
MARIADB_DATA_DIR="$MARIADB_DIR/data"
MARIADB_LOG_DIR="$MARIADB_DIR/log"

backend_pid=""
frontend_pid=""
mariadb_pid=""

print_line() {
  printf '\n[%s] %s\n' "$1" "$2"
}

wait_for_mysql_ready() {
  if [[ ! -f "$BACKEND_ENV_FILE" ]]; then
    print_line "error" "Missing backend/.env for MariaDB readiness check."
    return 1
  fi

  set -a
  # shellcheck disable=SC1090
  source "$BACKEND_ENV_FILE"
  set +a

  for _ in {1..60}; do
    if DATABASE_URL="${DATABASE_URL:-}" "$VENV_PYTHON" - <<'PY' >/dev/null 2>&1
import os
from urllib.parse import urlparse

import pymysql

database_url = os.environ.get("DATABASE_URL", "").strip()
if not database_url:
    raise SystemExit(1)

parsed = urlparse(database_url)
connection = pymysql.connect(
    host=parsed.hostname or "127.0.0.1",
    port=parsed.port or 3306,
    user=parsed.username or "",
    password=parsed.password or "",
    database=(parsed.path or "/").lstrip("/"),
    connect_timeout=1,
    read_timeout=1,
    write_timeout=1,
)
with connection.cursor() as cursor:
    cursor.execute("SELECT 1")
connection.close()
PY
    then
      return 0
    fi
    sleep 1
  done

  return 1
}

ensure_mysql_app_access() {
  set -a
  # shellcheck disable=SC1090
  source "$BACKEND_ENV_FILE"
  set +a

  DATABASE_URL="${DATABASE_URL:-}" MARIADB_SOCKET="$MARIADB_DIR/run/mysqld.sock" "$VENV_PYTHON" - <<'PY' >/dev/null 2>&1
import os
from urllib.parse import urlparse

import pymysql

database_url = os.environ.get("DATABASE_URL", "").strip()
socket_path = os.environ.get("MARIADB_SOCKET", "").strip()
if not database_url or not socket_path:
    raise SystemExit(1)

parsed = urlparse(database_url)
database = (parsed.path or "/kln_timetable").lstrip("/") or "kln_timetable"
user = parsed.username or "kln_user"
password = parsed.password or ""
host = parsed.hostname or "127.0.0.1"

connection = pymysql.connect(
    unix_socket=socket_path,
    user="root",
    password="",
    connect_timeout=1,
    read_timeout=1,
    write_timeout=1,
    autocommit=True,
)
with connection.cursor() as cursor:
    cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{database}`")
    for grant_host in {host, "localhost"}:
        cursor.execute(
            f"CREATE USER IF NOT EXISTS '{user}'@'{grant_host}' IDENTIFIED BY %s",
            (password,),
        )
        cursor.execute(
            f"ALTER USER '{user}'@'{grant_host}' IDENTIFIED BY %s",
            (password,),
        )
        cursor.execute(
            f"GRANT ALL PRIVILEGES ON `{database}`.* TO '{user}'@'{grant_host}'",
        )
    cursor.execute("FLUSH PRIVILEGES")
connection.close()
PY
}

mysql_system_tables_present() {
  [[ -d "$MARIADB_DATA_DIR/mysql" ]] && compgen -G "$MARIADB_DATA_DIR/mysql/db.*" >/dev/null
}

bootstrap_mysql_datadir() {
  print_line "mysql" "Initializing repo-local MariaDB system tables..."

  mkdir -p "$MARIADB_DATA_DIR" "$MARIADB_DIR/run" "$MARIADB_LOG_DIR"

  if [[ -d "$MARIADB_DATA_DIR" ]] && [[ -n "$(ls -A "$MARIADB_DATA_DIR" 2>/dev/null)" ]] && ! mysql_system_tables_present; then
    local backup_dir
    backup_dir="${MARIADB_DATA_DIR}.incomplete.$(date +%Y%m%d-%H%M%S)"
    mv "$MARIADB_DATA_DIR" "$backup_dir"
    mkdir -p "$MARIADB_DATA_DIR"
    print_line "mysql" "Moved incomplete MariaDB data dir to $(basename "$backup_dir")."
  fi

  set -a
  # shellcheck disable=SC1090
  source "$BACKEND_ENV_FILE"
  set +a

  local extra_sql
  extra_sql="$(mktemp)"
  DATABASE_URL="${DATABASE_URL:-}" "$VENV_PYTHON" - <<'PY' > "$extra_sql"
import os
from urllib.parse import urlparse

database_url = os.environ.get("DATABASE_URL", "").strip()
parsed = urlparse(database_url)
database = (parsed.path or "/kln_timetable").lstrip("/") or "kln_timetable"
user = parsed.username or "kln_user"
password = (parsed.password or "").replace("\\", "\\\\").replace("'", "\\'")
host = parsed.hostname or "127.0.0.1"

print(f"CREATE DATABASE IF NOT EXISTS `{database}`;")
print(f"CREATE USER IF NOT EXISTS '{user}'@'{host}' IDENTIFIED BY '{password}';")
print(f"GRANT ALL PRIVILEGES ON `{database}`.* TO '{user}'@'{host}';")
print("FLUSH PRIVILEGES;")
PY

  if ! (
    cd "$MARIADB_DIR"
    mariadb-install-db \
      --defaults-file=my.cnf \
      --datadir="$MARIADB_DATA_DIR" \
      --auth-root-authentication-method=normal \
      --skip-test-db \
      --skip-name-resolve \
      --extra-file="$extra_sql"
  ) >/dev/null 2>&1; then
    rm -f "$extra_sql"
    print_line "error" "Failed to initialize repo-local MariaDB data directory."
    return 1
  fi

  rm -f "$extra_sql"
}

cleanup() {
  print_line "dev" "Shutting down services..."
  if [[ -n "$frontend_pid" ]] && kill -0 "$frontend_pid" 2>/dev/null; then
    kill "$frontend_pid" 2>/dev/null || true
    wait "$frontend_pid" 2>/dev/null || true
  fi
  if [[ -n "$backend_pid" ]] && kill -0 "$backend_pid" 2>/dev/null; then
    kill "$backend_pid" 2>/dev/null || true
    wait "$backend_pid" 2>/dev/null || true
  fi
  if [[ -n "$mariadb_pid" ]] && kill -0 "$mariadb_pid" 2>/dev/null; then
    kill "$mariadb_pid" 2>/dev/null || true
    wait "$mariadb_pid" 2>/dev/null || true
  fi
}

trap cleanup EXIT INT TERM

if [[ ! -x "$VENV_PYTHON" ]]; then
  print_line "error" "Missing repo venv at .venv. Create it before running this launcher."
  exit 1
fi

if ! command -v npm >/dev/null 2>&1; then
  print_line "error" "npm is required but not available in PATH."
  exit 1
fi

if ! command -v mariadbd >/dev/null 2>&1; then
  print_line "error" "mariadbd is required for the local MySQL-compatible dev database."
  exit 1
fi

if ! lsof -iTCP:3307 -sTCP:LISTEN -n -P >/dev/null 2>&1; then
  if ! mysql_system_tables_present; then
    bootstrap_mysql_datadir || exit 1
  fi

  print_line "mysql" "Starting repo-local MariaDB on 127.0.0.1:3307"
  (
    cd "$MARIADB_DIR"
    exec mariadbd --defaults-file=my.cnf
  ) > >(stdbuf -oL sed 's/^/[mysql] /') 2> >(stdbuf -oL sed 's/^/[mysql] /' >&2) &
  mariadb_pid=$!

  for _ in {1..30}; do
    if lsof -iTCP:3307 -sTCP:LISTEN -n -P >/dev/null 2>&1; then
      break
    fi
    sleep 1
  done

  if ! lsof -iTCP:3307 -sTCP:LISTEN -n -P >/dev/null 2>&1; then
    print_line "error" "MariaDB did not start successfully."
    exit 1
  fi

  if ! ensure_mysql_app_access; then
    print_line "error" "MariaDB started, but app user/database setup failed."
    exit 1
  fi

  if ! wait_for_mysql_ready; then
    print_line "error" "MariaDB listener opened, but the database did not become query-ready."
    exit 1
  fi
else
  print_line "mysql" "Using existing MariaDB listener on 127.0.0.1:3307"
  if ! ensure_mysql_app_access; then
    print_line "error" "Existing MariaDB listener is up, but app user/database setup failed."
    exit 1
  fi
  if ! wait_for_mysql_ready; then
    print_line "error" "Existing MariaDB listener is not accepting database connections."
    exit 1
  fi
fi

print_line "backend" "Starting FastAPI on http://127.0.0.1:8000"
(
  cd "$BACKEND_DIR"
  exec "$VENV_PYTHON" -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
) > >(stdbuf -oL sed 's/^/[backend] /') 2> >(stdbuf -oL sed 's/^/[backend] /' >&2) &
backend_pid=$!

print_line "frontend" "Starting Vite on http://127.0.0.1:5173"
(
  cd "$FRONTEND_DIR"
  exec npm run dev -- --host 127.0.0.1
) > >(stdbuf -oL sed 's/^/[frontend] /') 2> >(stdbuf -oL sed 's/^/[frontend] /' >&2) &
frontend_pid=$!

print_line "dev" "Frontend: http://127.0.0.1:5173"
print_line "dev" "Backend:  http://127.0.0.1:8000"
print_line "dev" "Press Ctrl+C to stop all services."

wait -n "$backend_pid" "$frontend_pid"
