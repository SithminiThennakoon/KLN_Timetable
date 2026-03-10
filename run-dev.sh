#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"
VENV_PYTHON="$ROOT_DIR/.venv/bin/python"
MARIADB_DIR="$BACKEND_DIR/.mariadb"
MARIADB_CONFIG="$MARIADB_DIR/my.cnf"
MARIADB_PID_FILE="$MARIADB_DIR/run/mysqld.pid"

backend_pid=""
frontend_pid=""
mariadb_pid=""

print_line() {
  printf '\n[%s] %s\n' "$1" "$2"
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
else
  print_line "mysql" "Using existing MariaDB listener on 127.0.0.1:3307"
fi

print_line "backend" "Starting FastAPI on http://127.0.0.1:8000"
(
  cd "$BACKEND_DIR"
  exec "$VENV_PYTHON" -m uvicorn app.main:app --host 127.0.0.1 --port 8000
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
