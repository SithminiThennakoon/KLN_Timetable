#!/usr/bin/env python3

from __future__ import annotations

import os
import queue
import shutil
import signal
import socket
import subprocess
import tempfile
import threading
import time
from urllib.parse import urlparse
from dataclasses import dataclass
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, scrolledtext, ttk


ROOT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = ROOT_DIR / "backend"
FRONTEND_DIR = ROOT_DIR / "frontend"
VENV_PYTHON = ROOT_DIR / ".venv" / "bin" / "python"
MARIADB_DIR = BACKEND_DIR / ".mariadb"
MARIADB_RUN_DIR = MARIADB_DIR / "run"
MARIADB_LOG_DIR = MARIADB_DIR / "log"
MARIADB_CONFIG = MARIADB_DIR / "my.cnf"
MARIADB_SOCKET = MARIADB_RUN_DIR / "mysqld.sock"
MARIADB_PID_FILE = MARIADB_RUN_DIR / "mysqld.pid"
MARIADB_DATA_DIR = MARIADB_DIR / "data"
BACKEND_ENV_FILE = BACKEND_DIR / ".env"

HOST = "127.0.0.1"


@dataclass
class ServiceConfig:
    key: str
    label: str
    port: int
    command: list[str]
    cwd: Path
    log_key: str


SERVICES = {
    "mysql": ServiceConfig(
        key="mysql",
        label="MariaDB",
        port=3307,
        command=["mariadbd", "--defaults-file=my.cnf"],
        cwd=MARIADB_DIR,
        log_key="events",
    ),
    "backend": ServiceConfig(
        key="backend",
        label="Backend",
        port=8000,
        command=[
            str(VENV_PYTHON),
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            HOST,
            "--port",
            "8000",
            "--reload",
        ],
        cwd=BACKEND_DIR,
        log_key="backend",
    ),
    "frontend": ServiceConfig(
        key="frontend",
        label="Frontend",
        port=5173,
        command=["npm", "run", "dev", "--", "--host", HOST, "--strictPort"],
        cwd=FRONTEND_DIR,
        log_key="frontend",
    ),
}


class LauncherGUI:
    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title("KLN Timetable Launcher")
        self.root.geometry("1280x840")
        self.root.minsize(1120, 760)

        self.state_var = tk.StringVar(value="Idle")
        self.detail_var = tk.StringVar(value="Ready.")

        self.status_vars = {
            key: tk.StringVar(value="Stopped") for key in SERVICES
        }
        self.log_widgets: dict[str, scrolledtext.ScrolledText] = {}
        self.log_queue: queue.Queue[tuple[str, str]] = queue.Queue()
        self.processes: dict[str, subprocess.Popen[str]] = {}
        self.managed_service_keys: set[str] = set()
        self.busy = False

        self._build_ui()
        self.root.protocol("WM_DELETE_WINDOW", self.handle_close)
        self.root.after(100, self._pump_logs)
        self.root.after(1000, self._poll_processes)

    def _build_ui(self) -> None:
        style = ttk.Style()
        if "clam" in style.theme_names():
            style.theme_use("clam")

        shell = ttk.Frame(self.root, padding=16)
        shell.pack(fill="both", expand=True)

        header = ttk.Frame(shell)
        header.pack(fill="x")
        ttk.Label(header, text="KLN Timetable Launcher", font=("TkDefaultFont", 18, "bold")).pack(
            side="left"
        )

        controls = ttk.Frame(header)
        controls.pack(side="right")
        self.start_btn = ttk.Button(controls, text="Start App", command=self.start_app)
        self.start_btn.pack(side="left", padx=(0, 8))
        self.stop_btn = ttk.Button(controls, text="Stop App", command=self.stop_app)
        self.stop_btn.pack(side="left", padx=(0, 8))
        self.restart_btn = ttk.Button(controls, text="Restart App", command=self.restart_app)
        self.restart_btn.pack(side="left")

        info = ttk.Frame(shell, padding=(0, 12, 0, 8))
        info.pack(fill="x")
        ttk.Label(info, textvariable=self.state_var, font=("TkDefaultFont", 11, "bold")).pack(anchor="w")
        ttk.Label(info, textvariable=self.detail_var, wraplength=1150).pack(anchor="w", pady=(4, 0))
        ttk.Label(
            info,
            text="Frontend: http://127.0.0.1:5173    Backend: http://127.0.0.1:8000    MariaDB: 127.0.0.1:3307",
        ).pack(anchor="w", pady=(8, 0))

        status_frame = ttk.LabelFrame(shell, text="Service Status", padding=12)
        status_frame.pack(fill="x", pady=(0, 12))
        for index, key in enumerate(("mysql", "backend", "frontend")):
            ttk.Label(status_frame, text=SERVICES[key].label, width=12).grid(row=index, column=0, sticky="w", pady=2)
            ttk.Label(status_frame, textvariable=self.status_vars[key]).grid(row=index, column=1, sticky="w", pady=2)

        logs = ttk.Frame(shell)
        logs.pack(fill="both", expand=True)
        logs.columnconfigure(0, weight=1)
        logs.columnconfigure(1, weight=1)
        logs.rowconfigure(0, weight=1)
        logs.rowconfigure(1, weight=1)

        self._build_log_panel(logs, 0, 0, "backend", "Backend Logs")
        self._build_log_panel(logs, 0, 1, "frontend", "Frontend Logs")
        self._build_log_panel(logs, 1, 0, "events", "Launcher Events", span=2)

        self._set_buttons()

    def _build_log_panel(
        self, parent: ttk.Frame, row: int, column: int, key: str, title: str, span: int = 1
    ) -> None:
        frame = ttk.LabelFrame(parent, text=title, padding=8)
        frame.grid(
            row=row,
            column=column,
            columnspan=span,
            sticky="nsew",
            padx=(0, 12 if column == 0 and span == 1 else 0),
            pady=(0, 12),
        )

        button_row = ttk.Frame(frame)
        button_row.pack(fill="x", pady=(0, 8))
        if key in {"backend", "frontend", "events"}:
            ttk.Button(
                button_row,
                text=f"Copy {title}",
                command=lambda target=key: self.copy_logs(target),
            ).pack(side="right")

        text = scrolledtext.ScrolledText(frame, wrap="word", height=10, state="disabled")
        text.pack(fill="both", expand=True)
        self.log_widgets[key] = text

    def _set_buttons(self) -> None:
        running = any(self._is_process_running(key) for key in ("backend", "frontend"))
        self.start_btn.configure(state="disabled" if self.busy or running else "normal")
        self.stop_btn.configure(state="disabled" if self.busy or not running else "normal")
        self.restart_btn.configure(state="disabled" if self.busy else "normal")

    def log(self, key: str, message: str) -> None:
        self.log_queue.put((key, message.rstrip("\n")))

    def _pump_logs(self) -> None:
        try:
            while True:
                key, message = self.log_queue.get_nowait()
                widget = self.log_widgets[key]
                widget.configure(state="normal")
                widget.insert("end", f"{message}\n")
                widget.see("end")
                widget.configure(state="disabled")
        except queue.Empty:
            pass
        self.root.after(100, self._pump_logs)

    def copy_logs(self, key: str) -> None:
        content = self.log_widgets[key].get("1.0", "end-1c")
        self.root.clipboard_clear()
        self.root.clipboard_append(content)
        self.root.update()
        if key in SERVICES:
            label = SERVICES[key].label.lower()
        else:
            label = "launcher event"
        self.detail_var.set(f"Copied {label} logs to clipboard.")

    def _append_reader(self, service_key: str, process: subprocess.Popen[str]) -> None:
        def _reader() -> None:
            assert process.stdout is not None
            for line in process.stdout:
                self.log(SERVICES[service_key].log_key, f"[{service_key}] {line.rstrip()}")

        thread = threading.Thread(target=_reader, daemon=True)
        thread.start()

    def _is_process_running(self, key: str) -> bool:
        process = self.processes.get(key)
        return process is not None and process.poll() is None

    def _update_service_status(self, key: str, value: str) -> None:
        self.root.after(0, lambda: self.status_vars[key].set(value))

    def _set_state(self, state: str, detail: str) -> None:
        self.root.after(0, lambda: self.state_var.set(state))
        self.root.after(0, lambda: self.detail_var.set(detail))

    def _mark_busy(self, busy: bool) -> None:
        self.busy = busy
        self.root.after(0, self._set_buttons)

    def _port_open(self, port: int) -> bool:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.5)
            return sock.connect_ex((HOST, port)) == 0

    def _listener_details(self, port: int) -> list[tuple[int, str, str]]:
        result = subprocess.run(
            ["lsof", "-nP", f"-iTCP:{port}", "-sTCP:LISTEN", "-t"],
            capture_output=True,
            text=True,
            check=False,
        )
        pids = [int(line.strip()) for line in result.stdout.splitlines() if line.strip().isdigit()]
        details: list[tuple[int, str, str]] = []
        for pid in pids:
            ps = subprocess.run(
                ["ps", "-p", str(pid), "-o", "args="],
                capture_output=True,
                text=True,
                check=False,
            )
            cwd = ""
            try:
                cwd = os.path.realpath(f"/proc/{pid}/cwd")
            except OSError:
                cwd = ""
            details.append((pid, ps.stdout.strip() or "<unknown>", cwd))
        return details

    def _matches_repo_service(self, key: str, cmdline: str, cwd: str) -> bool:
        if key == "mysql":
            return "mariadbd" in cmdline and cwd.startswith(str(MARIADB_DIR))
        if key == "backend":
            return "uvicorn" in cmdline and cwd.startswith(str(BACKEND_DIR))
        if key == "frontend":
            return (("vite" in cmdline) or ("npm" in cmdline)) and cwd.startswith(
                str(FRONTEND_DIR)
            )
        return False

    def _terminate_pid(self, pid: int, label: str) -> None:
        try:
            pgid = os.getpgid(pid)
        except ProcessLookupError:
            return

        try:
            os.killpg(pgid, signal.SIGTERM)
        except OSError:
            try:
                os.kill(pid, signal.SIGTERM)
            except ProcessLookupError:
                return

        deadline = time.time() + 10
        while time.time() < deadline:
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                return
            time.sleep(0.2)

        try:
            os.killpg(pgid, signal.SIGKILL)
        except OSError:
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                return
        self.log("events", f"[cleanup] Forced {label} process {pid} to stop.")

    def _clean_stale_mysql_state(self) -> None:
        if self._port_open(SERVICES["mysql"].port):
            return
        for path in (MARIADB_PID_FILE, MARIADB_SOCKET):
            if path.exists():
                path.unlink()
                self.log("events", f"[cleanup] Removed stale MariaDB state: {path.name}")

    def _safe_cleanup(self) -> None:
        self.log("events", "[cleanup] Starting safe cleanup.")
        for key in ("frontend", "backend", "mysql"):
            process = self.processes.get(key)
            if process and process.poll() is None:
                self.log("events", f"[cleanup] Stopping managed {SERVICES[key].label}.")
                self._stop_process(key)

        for key in ("frontend", "backend", "mysql"):
            for pid, cmdline, cwd in self._listener_details(SERVICES[key].port):
                if self._matches_repo_service(key, cmdline, cwd):
                    self.log(
                        "events",
                        f"[cleanup] Stopping stale repo-local {SERVICES[key].label} process {pid}.",
                    )
                    self._terminate_pid(pid, SERVICES[key].label)

        for key in ("frontend", "backend", "mysql"):
            if not self._wait_for_port_free(SERVICES[key].port):
                self.log(
                    "events",
                    f"[cleanup] Port {SERVICES[key].port} is still busy after cleanup.",
                )

        self._clean_stale_mysql_state()
        self.log("events", "[cleanup] Safe cleanup complete.")

    def _check_prerequisites(self) -> list[str]:
        missing = []
        if not VENV_PYTHON.exists():
            missing.append("Missing repo virtualenv Python at .venv/bin/python")
        if shutil.which("npm") is None:
            missing.append("npm is not available in PATH")
        if shutil.which("mariadbd") is None:
            missing.append("mariadbd is not available in PATH")
        if not MARIADB_CONFIG.exists():
            missing.append("Missing backend/.mariadb/my.cnf")
        if not (BACKEND_DIR / ".env").exists():
            missing.append("Missing backend/.env")
        return missing

    def _find_conflicts(self) -> list[str]:
        conflicts: list[str] = []
        for key in ("frontend", "backend", "mysql"):
            for pid, cmdline, cwd in self._listener_details(SERVICES[key].port):
                if not self._matches_repo_service(key, cmdline, cwd):
                    conflicts.append(
                        f"Port {SERVICES[key].port} is occupied by external process {pid}: {cmdline}"
                    )
        return conflicts

    def _wait_for_port(self, port: int, timeout: int = 30) -> bool:
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self._port_open(port):
                return True
            time.sleep(0.5)
        return False

    def _mysql_system_tables_present(self) -> bool:
        mysql_dir = MARIADB_DATA_DIR / "mysql"
        if not mysql_dir.is_dir():
            return False
        return any(mysql_dir.glob("db.*"))

    def _load_backend_env(self) -> dict[str, str]:
        values: dict[str, str] = {}
        if not BACKEND_ENV_FILE.exists():
            return values
        for raw_line in BACKEND_ENV_FILE.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip()
        return values

    def _wait_for_mysql_ready(self, timeout: int = 30) -> bool:
        env_values = self._load_backend_env()
        database_url = env_values.get("DATABASE_URL", "").strip()
        if not database_url.startswith("mysql"):
            return True

        parsed = urlparse(database_url)
        script = (
            "import os\n"
            "import pymysql\n"
            "conn = pymysql.connect("
            "host=os.environ['DB_HOST'],"
            "port=int(os.environ['DB_PORT']),"
            "user=os.environ['DB_USER'],"
            "password=os.environ['DB_PASSWORD'],"
            "database=os.environ['DB_NAME'],"
            "connect_timeout=1,"
            "read_timeout=1,"
            "write_timeout=1)\n"
            "cur = conn.cursor()\n"
            "cur.execute('SELECT 1')\n"
            "conn.close()\n"
        )
        child_env = os.environ.copy()
        child_env.update(
            {
                "DB_HOST": parsed.hostname or "127.0.0.1",
                "DB_PORT": str(parsed.port or 3306),
                "DB_USER": parsed.username or "",
                "DB_PASSWORD": parsed.password or "",
                "DB_NAME": (parsed.path or "/").lstrip("/"),
            }
        )

        deadline = time.time() + timeout
        while time.time() < deadline:
            result = subprocess.run(
                [str(VENV_PYTHON), "-c", script],
                env=child_env,
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode == 0:
                return True
            time.sleep(1)
        return False

    def _ensure_mysql_app_access(self) -> None:
        env_values = self._load_backend_env()
        database_url = env_values.get("DATABASE_URL", "").strip()
        if not database_url.startswith("mysql"):
            return

        parsed = urlparse(database_url)
        script = (
            "import os\n"
            "import pymysql\n"
            "conn = pymysql.connect("
            "unix_socket=os.environ['DB_SOCKET'],"
            "user='root',"
            "password='',"
            "connect_timeout=1,"
            "read_timeout=1,"
            "write_timeout=1,"
            "autocommit=True)\n"
            "cur = conn.cursor()\n"
            "cur.execute(f\"CREATE DATABASE IF NOT EXISTS `{os.environ['DB_NAME']}`\")\n"
            "for host in {os.environ['DB_HOST'], 'localhost'}:\n"
            "    cur.execute(f\"CREATE USER IF NOT EXISTS '{os.environ['DB_USER']}'@'{host}' IDENTIFIED BY %s\", (os.environ['DB_PASSWORD'],))\n"
            "    cur.execute(f\"ALTER USER '{os.environ['DB_USER']}'@'{host}' IDENTIFIED BY %s\", (os.environ['DB_PASSWORD'],))\n"
            "    cur.execute(f\"GRANT ALL PRIVILEGES ON `{os.environ['DB_NAME']}`.* TO '{os.environ['DB_USER']}'@'{host}'\")\n"
            "cur.execute('FLUSH PRIVILEGES')\n"
            "conn.close()\n"
        )
        child_env = os.environ.copy()
        child_env.update(
            {
                "DB_SOCKET": str(MARIADB_SOCKET),
                "DB_HOST": parsed.hostname or "127.0.0.1",
                "DB_USER": parsed.username or "",
                "DB_PASSWORD": parsed.password or "",
                "DB_NAME": (parsed.path or "/").lstrip("/") or "kln_timetable",
            }
        )
        result = subprocess.run(
            [str(VENV_PYTHON), "-c", script],
            env=child_env,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            output = (result.stderr or result.stdout or "").strip()
            raise RuntimeError(f"MariaDB app user setup failed: {output or 'unknown error'}")

    def _bootstrap_mysql_datadir(self) -> None:
        env_values = self._load_backend_env()
        database_url = env_values.get("DATABASE_URL", "").strip()
        if not database_url.startswith("mysql"):
            return

        MARIADB_DATA_DIR.mkdir(parents=True, exist_ok=True)
        MARIADB_RUN_DIR.mkdir(parents=True, exist_ok=True)
        MARIADB_LOG_DIR.mkdir(parents=True, exist_ok=True)

        if any(MARIADB_DATA_DIR.iterdir()) and not self._mysql_system_tables_present():
            backup_dir = MARIADB_DATA_DIR.with_name(
                f"{MARIADB_DATA_DIR.name}.incomplete.{time.strftime('%Y%m%d-%H%M%S')}"
            )
            MARIADB_DATA_DIR.rename(backup_dir)
            MARIADB_DATA_DIR.mkdir(parents=True, exist_ok=True)
            self.log("events", f"[mysql] Moved incomplete MariaDB data dir to {backup_dir.name}.")

        parsed = urlparse(database_url)
        database = (parsed.path or "/kln_timetable").lstrip("/") or "kln_timetable"
        user = parsed.username or "kln_user"
        password = (parsed.password or "").replace("\\", "\\\\").replace("'", "\\'")
        host = parsed.hostname or "127.0.0.1"

        extra_sql = (
            f"CREATE DATABASE IF NOT EXISTS `{database}`;\n"
            f"CREATE USER IF NOT EXISTS '{user}'@'{host}' IDENTIFIED BY '{password}';\n"
            f"GRANT ALL PRIVILEGES ON `{database}`.* TO '{user}'@'{host}';\n"
            "FLUSH PRIVILEGES;\n"
        )

        self.log("events", "[mysql] Initializing repo-local MariaDB system tables.")
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as handle:
            handle.write(extra_sql)
            extra_file = handle.name

        try:
            result = subprocess.run(
                [
                    "mariadb-install-db",
                    "--defaults-file=my.cnf",
                    f"--datadir={MARIADB_DATA_DIR}",
                    "--auth-root-authentication-method=normal",
                    "--skip-test-db",
                    "--skip-name-resolve",
                    f"--extra-file={extra_file}",
                ],
                cwd=MARIADB_DIR,
                capture_output=True,
                text=True,
                check=False,
            )
        finally:
            Path(extra_file).unlink(missing_ok=True)

        if result.returncode != 0:
            output = (result.stdout or "").strip()
            error = (result.stderr or "").strip()
            detail = error or output or "unknown initialization failure"
            raise RuntimeError(f"Failed to initialize repo-local MariaDB data dir: {detail}")

    def _wait_for_port_free(self, port: int, timeout: int = 15) -> bool:
        deadline = time.time() + timeout
        while time.time() < deadline:
            if not self._port_open(port):
                return True
            time.sleep(0.3)
        return False

    def _start_process(self, key: str) -> subprocess.Popen[str]:
        config = SERVICES[key]
        process = subprocess.Popen(
            config.command,
            cwd=config.cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            start_new_session=True,
        )
        self.processes[key] = process
        self.managed_service_keys.add(key)
        self._append_reader(key, process)
        self._update_service_status(key, "Starting...")
        return process

    def _stop_process(self, key: str) -> None:
        process = self.processes.get(key)
        if not process or process.poll() is not None:
            self._update_service_status(key, "Stopped")
            return

        self._update_service_status(key, "Stopping...")
        try:
            pgid = os.getpgid(process.pid)
        except ProcessLookupError:
            self._update_service_status(key, "Stopped")
            return
        try:
            os.killpg(pgid, signal.SIGTERM)
        except OSError:
            process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(pgid, signal.SIGKILL)
            except OSError:
                process.kill()
            process.wait(timeout=5)
        self._update_service_status(key, "Stopped")

    def start_app(self) -> None:
        if self.busy:
            return
        threading.Thread(target=self._start_sequence, daemon=True).start()

    def _start_sequence(self) -> None:
        self._mark_busy(True)
        self._set_state("Starting", "Preparing services...")
        try:
            self._safe_cleanup()
            missing = self._check_prerequisites()
            if missing:
                raise RuntimeError("\n".join(missing))

            conflicts = self._find_conflicts()
            if conflicts:
                raise RuntimeError("\n".join(conflicts))

            if not self._port_open(SERVICES["mysql"].port):
                if not self._mysql_system_tables_present():
                    self._bootstrap_mysql_datadir()
                self.log("events", "[mysql] Starting repo-local MariaDB.")
                self._start_process("mysql")
                if not self._wait_for_port(SERVICES["mysql"].port, timeout=30):
                    raise RuntimeError("MariaDB did not become ready on port 3307.")
                self._ensure_mysql_app_access()
                if not self._wait_for_mysql_ready(timeout=30):
                    raise RuntimeError("MariaDB opened port 3307 but did not become query-ready.")
            else:
                self._update_service_status("mysql", "Running (external)")
                self._ensure_mysql_app_access()
                if not self._wait_for_mysql_ready(timeout=10):
                    raise RuntimeError("Existing MariaDB listener is not accepting queries.")

            self.log("events", "[backend] Starting FastAPI backend.")
            self._start_process("backend")
            if not self._wait_for_port(SERVICES["backend"].port, timeout=30):
                raise RuntimeError("Backend did not become ready on port 8000.")

            self.log("events", "[frontend] Starting Vite frontend.")
            self._start_process("frontend")
            if not self._wait_for_port(SERVICES["frontend"].port, timeout=30):
                raise RuntimeError("Frontend did not become ready on port 5173.")

            self._update_service_status("mysql", "Running")
            self._update_service_status("backend", "Running")
            self._update_service_status("frontend", "Running")
            self._set_state("Running", "All services are running.")
        except Exception as exc:
            self.log("events", f"[error] {exc}")
            self._set_state("Error", str(exc))
            self._safe_cleanup()
        finally:
            self._mark_busy(False)

    def stop_app(self) -> None:
        if self.busy:
            return
        threading.Thread(target=self._stop_sequence, daemon=True).start()

    def _stop_sequence(self) -> None:
        self._mark_busy(True)
        self._set_state("Stopping", "Stopping services...")
        try:
            self._stop_process("frontend")
            self._stop_process("backend")
            if "mysql" in self.managed_service_keys:
                self._stop_process("mysql")
            self._clean_stale_mysql_state()
            self._set_state("Idle", "All managed services stopped.")
        finally:
            self._mark_busy(False)

    def restart_app(self) -> None:
        if self.busy:
            return

        def _restart() -> None:
            self._stop_sequence()
            self._start_sequence()

        threading.Thread(target=_restart, daemon=True).start()

    def _poll_processes(self) -> None:
        for key in ("mysql", "backend", "frontend"):
            process = self.processes.get(key)
            if process and process.poll() is not None:
                self._update_service_status(key, f"Exited ({process.returncode})")
        self._set_buttons()
        self.root.after(1000, self._poll_processes)

    def handle_close(self) -> None:
        if self.busy:
            self.root.after(500, self.handle_close)
            return
        self._stop_sequence()
        self.root.destroy()

    def run(self) -> None:
        self.root.mainloop()


if __name__ == "__main__":
    app = LauncherGUI()
    app.run()
