from __future__ import annotations

from sqlalchemy.orm import Session

from app.services.timetable_v2 import build_snapshot_verification_payload
from verifiers.python_snapshot_verifier import verify_snapshot


def run_snapshot_python_verification(db: Session, import_run_id: int) -> dict:
    snapshot = build_snapshot_verification_payload(db, import_run_id)
    result = verify_snapshot(snapshot)
    result["import_run_id"] = int(import_run_id)
    result["generation_run_id"] = int(snapshot["generation_run_id"])
    result["solution_id"] = int(snapshot["solution_id"])
    return result
