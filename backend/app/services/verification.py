from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

from sqlalchemy.orm import Session

from app.services.timetable_v2 import build_snapshot_verification_payload
from verifiers.python_snapshot_verifier import verify_snapshot


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _which_with_windows_fallback(command: str, fallback_paths: list[Path]) -> str | None:
    resolved = shutil.which(command)
    if resolved:
        return resolved
    if os.name != "nt":
        return None
    for path in fallback_paths:
        if path.exists():
            return str(path)
    return None


def _windows_msvc_env(base_env: dict[str, str]) -> dict[str, str]:
    vswhere = Path("C:/Program Files (x86)/Microsoft Visual Studio/Installer/vswhere.exe")
    if not vswhere.exists():
        return base_env

    discovery = subprocess.run(
        [
            str(vswhere),
            "-latest",
            "-products",
            "*",
            "-requires",
            "Microsoft.VisualStudio.Component.VC.Tools.x86.x64",
            "-property",
            "installationPath",
        ],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    installation_path = (discovery.stdout or "").strip()
    if not installation_path:
        return base_env

    vcvars64 = Path(installation_path) / "VC" / "Auxiliary" / "Build" / "vcvars64.bat"
    if not vcvars64.exists():
        return base_env

    env_dump = subprocess.run(
        ["cmd.exe", "/d", "/c", f"call \"{vcvars64}\" >nul && set"],
        capture_output=True,
        text=True,
        env=base_env,
        timeout=60,
        check=False,
    )
    if env_dump.returncode != 0:
        return base_env

    merged = dict(base_env)
    for line in env_dump.stdout.splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key:
            merged[key] = value
    return merged


def _attach_snapshot_identity(result: dict, snapshot: dict, import_run_id: int) -> dict:
    result["import_run_id"] = int(import_run_id)
    result["generation_run_id"] = int(snapshot["generation_run_id"])
    result["solution_id"] = int(snapshot["solution_id"])
    return result


def _run_rust_snapshot_verification(snapshot: dict) -> dict:
    cargo = _which_with_windows_fallback(
        "cargo",
        [Path.home() / ".cargo" / "bin" / "cargo.exe"],
    )
    if not cargo:
        raise RuntimeError("Cargo is not installed.")

    manifest_path = _repo_root() / "verifiers" / "rust_snapshot_verifier" / "Cargo.toml"
    if not manifest_path.exists():
        raise RuntimeError("Rust verifier manifest is missing.")

    env = os.environ.copy()
    env["CARGO_NET_OFFLINE"] = "false"
    if os.name == "nt":
        env["CARGO_HTTP_CHECK_REVOKE"] = "false"
        env = _windows_msvc_env(env)
        process = subprocess.run(
            [
                cargo,
                "run",
                "--quiet",
                "--manifest-path",
                str(manifest_path),
                "--",
                "-",
            ],
            input=json.dumps(snapshot),
            capture_output=True,
            text=True,
            cwd=_repo_root(),
            env=env,
            timeout=180,
            check=False,
        )
    else:
        process = subprocess.run(
            [
                cargo,
                "run",
                "--quiet",
                "--manifest-path",
                str(manifest_path),
                "--",
                "-",
            ],
            input=json.dumps(snapshot),
            capture_output=True,
            text=True,
            cwd=_repo_root(),
            env=env,
            timeout=120,
            check=False,
        )
    if process.returncode not in {0, 1}:
        stderr = process.stderr.strip() or process.stdout.strip() or "Rust verifier failed."
        raise RuntimeError(stderr)
    return json.loads(process.stdout)


def _run_elixir_snapshot_verification(snapshot: dict) -> dict:
    verifier_dir = _repo_root() / "verifiers" / "elixir_snapshot_verifier"
    escript_path = verifier_dir / "elixir_snapshot_verifier"
    if not verifier_dir.exists():
        raise RuntimeError("Elixir verifier project is missing.")

    if escript_path.exists():
        if os.name == "nt":
            escript = _which_with_windows_fallback(
                "escript",
                [
                    Path("C:/Program Files/Erlang OTP/bin/escript.exe"),
                    Path("C:/Program Files/Erlang OTP/erts-16.3/bin/escript.exe"),
                ],
            )
            if not escript:
                raise RuntimeError("Erlang escript runtime is not installed.")
            process = subprocess.run(
                [escript, str(escript_path), "-"],
                input=json.dumps(snapshot),
                capture_output=True,
                text=True,
                cwd=verifier_dir,
                timeout=120,
                check=False,
            )
        else:
            process = subprocess.run(
                [str(escript_path), "-"],
                input=json.dumps(snapshot),
                capture_output=True,
                text=True,
                cwd=verifier_dir,
                timeout=120,
                check=False,
            )
        if process.returncode not in {0, 1}:
            stderr = process.stderr.strip() or process.stdout.strip() or "Elixir verifier failed."
            raise RuntimeError(stderr)
        return json.loads(process.stdout)

    mix = _which_with_windows_fallback(
        "mix",
        [],
    )
    if not mix:
        raise RuntimeError("Mix is not installed.")

    if not escript_path.exists():
        build = subprocess.run(
            [mix, "escript.build"],
            capture_output=True,
            text=True,
            cwd=verifier_dir,
            timeout=120,
            check=False,
        )
        if build.returncode != 0:
            stderr = build.stderr.strip() or build.stdout.strip() or "Elixir verifier build failed."
            raise RuntimeError(stderr)

    process = subprocess.run(
        [str(escript_path), "-"],
        input=json.dumps(snapshot),
        capture_output=True,
        text=True,
        cwd=verifier_dir,
        timeout=120,
        check=False,
    )
    if process.returncode not in {0, 1}:
        stderr = process.stderr.strip() or process.stdout.strip() or "Elixir verifier failed."
        raise RuntimeError(stderr)
    return json.loads(process.stdout)


def run_snapshot_python_verification(db: Session, import_run_id: int) -> dict:
    snapshot = build_snapshot_verification_payload(db, import_run_id)
    result = verify_snapshot(snapshot)
    return _attach_snapshot_identity(result, snapshot, import_run_id)


def run_snapshot_verification_suite(db: Session, import_run_id: int) -> dict:
    snapshot = build_snapshot_verification_payload(db, import_run_id)
    results: dict[str, dict] = {}
    errors: dict[str, str] = {}

    results["python"] = _attach_snapshot_identity(
        verify_snapshot(snapshot), snapshot, import_run_id
    )

    try:
        results["rust"] = _attach_snapshot_identity(
            _run_rust_snapshot_verification(snapshot), snapshot, import_run_id
        )
    except Exception as exc:  # pragma: no cover - runtime integration path
        errors["rust"] = str(exc)

    try:
        results["elixir"] = _attach_snapshot_identity(
            _run_elixir_snapshot_verification(snapshot), snapshot, import_run_id
        )
    except Exception as exc:  # pragma: no cover - runtime integration path
        errors["elixir"] = str(exc)

    required_verifiers = ["python", "rust", "elixir"]
    hard_valid_all = (
        all(item in results for item in required_verifiers)
        and all(item.get("hard_valid") for item in results.values())
    )

    return {
        "import_run_id": int(import_run_id),
        "generation_run_id": int(snapshot["generation_run_id"]),
        "solution_id": int(snapshot["solution_id"]),
        "required_verifiers": required_verifiers,
        "completed_verifiers": sorted(results.keys()),
        "missing_verifiers": [item for item in required_verifiers if item not in results],
        "hard_valid_all": hard_valid_all,
        "results": results,
        "errors": errors,
    }
