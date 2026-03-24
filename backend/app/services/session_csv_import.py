from __future__ import annotations

import csv
from pathlib import Path

from sqlalchemy.orm import Session

from app.models.academic import CurriculumModule
from app.models.imports import ImportRun
from app.models.snapshot import SnapshotRoom, SnapshotSharedSession
from app.services.snapshot_completion import build_import_workspace
from app.services.snapshot_completion import (
    create_snapshot_shared_session,
    update_snapshot_shared_session,
)


REQUIRED_COLUMNS = {
    "session_code",
    "module_code",
    "session_name",
    "session_type",
    "duration_minutes",
    "occurrences_per_week",
    "required_room_type",
}
OPTIONAL_COLUMNS = {
    "required_lab_type",
    "specific_room_code",
    "max_students_per_group",
    "allow_parallel_rooms",
    "notes",
}
SUPPORTED_SESSION_TYPES = {"lecture", "tutorial", "seminar", "lab", "practical", "laboratory"}
SUPPORTED_ROOM_TYPES = {"lecture", "lab", "seminar"}
TRUE_VALUES = {"true", "1", "yes", "y"}
FALSE_VALUES = {"false", "0", "no", "n", ""}


def _normalize_header(value: str) -> str:
    return (value or "").replace("\ufeff", "").strip()


def _normalize_cell(value: str | None) -> str:
    return (value or "").strip()


def _is_blank_row(values: list[str]) -> bool:
    return not any(_normalize_cell(value) for value in values)


def _parse_bool(value: str) -> bool | None:
    normalized = value.strip().lower()
    if normalized in TRUE_VALUES:
        return True
    if normalized in FALSE_VALUES:
        return False
    return None


def import_sessions_csv(db: Session, *, import_run_id: int, csv_path: str) -> dict:
    import_run = db.query(ImportRun).filter(ImportRun.id == import_run_id).first()
    if import_run is None:
        raise ValueError(f"Import run {import_run_id} was not found")

    path = Path(csv_path)
    if not path.exists():
        raise FileNotFoundError(f"Sessions CSV not found: {path}")

    module_rows = db.query(CurriculumModule).order_by(CurriculumModule.id.asc()).all()
    modules_by_code: dict[str, list[CurriculumModule]] = {}
    for module in module_rows:
        modules_by_code.setdefault((module.code or "").strip(), []).append(module)
    workspace = build_import_workspace(db, import_run_id)
    attendance_group_ids_by_module_id = {
        int(module["id"]): [int(group_id) for group_id in module.get("attendance_group_ids", [])]
        for module in workspace.get("curriculum_modules", [])
    }

    rooms = db.query(SnapshotRoom).filter(SnapshotRoom.import_run_id == import_run_id).all()
    room_by_code = {
        (room.client_key or "").strip(): room for room in rooms if (room.client_key or "").strip()
    }

    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle)
        raw_headers = next(reader, None)
        if raw_headers is None:
            raise ValueError("Sessions CSV is empty")

        headers = [_normalize_header(value) for value in raw_headers]
        duplicate_headers = sorted({header for header in headers if header and headers.count(header) > 1})
        if duplicate_headers:
            raise ValueError(f"Sessions CSV has duplicate headers: {', '.join(duplicate_headers)}")

        missing_columns = sorted(REQUIRED_COLUMNS - set(headers))
        if missing_columns:
            raise ValueError(
                f"Sessions CSV is missing required columns: {', '.join(missing_columns)}"
            )

        unknown_columns = sorted(set(headers) - REQUIRED_COLUMNS - OPTIONAL_COLUMNS)
        warnings: list[dict] = []
        if unknown_columns:
            warnings.append(
                {
                    "row_number": None,
                    "message": f"Ignoring unknown columns: {', '.join(unknown_columns)}",
                }
            )

        staged_sessions: list[dict] = []
        seen_codes: set[str] = set()

        for row_number, values in enumerate(reader, start=2):
            if _is_blank_row(values):
                continue

            padded = list(values) + [""] * max(0, len(headers) - len(values))
            row = {headers[index]: _normalize_cell(padded[index]) for index in range(len(headers))}

            session_code = row["session_code"]
            module_code = row["module_code"]
            session_name = row["session_name"]
            session_type = row["session_type"].lower()
            required_room_type = row["required_room_type"].lower()
            required_lab_type = row.get("required_lab_type") or None
            specific_room_code = row.get("specific_room_code", "")
            notes = row.get("notes") or None

            row_errors: list[str] = []
            if not session_code:
                row_errors.append("blank session_code")
            if not module_code:
                row_errors.append("blank module_code")
            if not session_name:
                row_errors.append("blank session_name")
            if session_code in seen_codes:
                row_errors.append(f"duplicate session_code '{session_code}'")
            if session_type not in SUPPORTED_SESSION_TYPES:
                row_errors.append(f"unsupported session_type '{row.get('session_type', '')}'")
            if required_room_type not in SUPPORTED_ROOM_TYPES:
                row_errors.append(f"unsupported required_room_type '{row.get('required_room_type', '')}'")

            try:
                duration_minutes = int(row["duration_minutes"])
                if duration_minutes <= 0:
                    row_errors.append("duration_minutes must be a positive integer")
            except ValueError:
                duration_minutes = None
                row_errors.append("duration_minutes must be a positive integer")

            try:
                occurrences_per_week = int(row["occurrences_per_week"])
                if occurrences_per_week <= 0:
                    row_errors.append("occurrences_per_week must be a positive integer")
            except ValueError:
                occurrences_per_week = None
                row_errors.append("occurrences_per_week must be a positive integer")

            max_students_raw = row.get("max_students_per_group", "")
            max_students_per_group = None
            if max_students_raw:
                try:
                    max_students_per_group = int(max_students_raw)
                    if max_students_per_group <= 0:
                        row_errors.append("max_students_per_group must be a positive integer")
                except ValueError:
                    row_errors.append("max_students_per_group must be a positive integer")

            allow_parallel_rooms = _parse_bool(row.get("allow_parallel_rooms", ""))
            if allow_parallel_rooms is None:
                row_errors.append("allow_parallel_rooms must be a boolean value")

            matching_modules = modules_by_code.get(module_code, [])
            if not matching_modules:
                row_errors.append(f"module_code '{module_code}' does not resolve to accepted module data")

            specific_room = None
            if specific_room_code:
                specific_room = room_by_code.get(specific_room_code)
                if specific_room is None:
                    row_errors.append(
                        f"specific_room_code '{specific_room_code}' does not resolve to an imported room"
                    )

            if row_errors:
                raise ValueError(f"Sessions CSV row {row_number}: {'; '.join(row_errors)}")

            seen_codes.add(session_code)

            if session_type in {"lab", "practical", "laboratory"} and duration_minutes != 180:
                warnings.append(
                    {
                        "row_number": row_number,
                        "message": f"Lab-like session '{session_name}' is not 180 minutes",
                    }
                )
            if required_room_type != "lab" and required_lab_type:
                warnings.append(
                    {
                        "row_number": row_number,
                        "message": f"Non-lab session '{session_name}' includes required_lab_type '{required_lab_type}'",
                    }
                )
            if max_students_per_group and not allow_parallel_rooms:
                warnings.append(
                    {
                        "row_number": row_number,
                        "message": f"Session '{session_name}' has max_students_per_group but parallel rooms are disabled",
                    }
                )

            curriculum_module_ids = sorted(int(module.id) for module in matching_modules)
            attendance_group_ids = sorted(
                {
                    int(group_id)
                    for module in matching_modules
                    for group_id in attendance_group_ids_by_module_id.get(int(module.id), [])
                }
            )

            staged_sessions.append(
                {
                    "client_key": session_code,
                    "name": session_name,
                    "session_type": session_type,
                    "duration_minutes": duration_minutes,
                    "occurrences_per_week": occurrences_per_week,
                    "required_room_type": required_room_type,
                    "required_lab_type": required_lab_type,
                    "specific_room_id": int(specific_room.id) if specific_room else None,
                    "max_students_per_group": max_students_per_group,
                    "allow_parallel_rooms": bool(allow_parallel_rooms),
                    "notes": notes or "Imported from sessions.csv",
                    "lecturer_ids": [],
                    "curriculum_module_ids": curriculum_module_ids,
                    "attendance_group_ids": attendance_group_ids,
                }
            )

    existing_sessions = (
        db.query(SnapshotSharedSession)
        .filter(SnapshotSharedSession.import_run_id == import_run_id)
        .all()
    )
    by_client_key = {
        (session.client_key or "").strip(): session
        for session in existing_sessions
        if (session.client_key or "").strip()
    }
    by_name_type = {
        ((session.name or "").strip(), (session.session_type or "").strip().lower()): session
        for session in existing_sessions
        if session.name and session.session_type
    }

    created_count = 0
    updated_count = 0
    saved_sessions: list[dict] = []

    for staged in staged_sessions:
        matched_session = by_client_key.get(staged["client_key"])
        conflicting_name_type_session = by_name_type.get((staged["name"], staged["session_type"]))
        if matched_session is None and conflicting_name_type_session is not None:
            raise ValueError(
                "Sessions CSV conflicts with existing session "
                f"'{staged['name']}' ({staged['session_type']}). Re-import only updates matching session_code values; "
                "resolve the conflict manually or reuse the original session_code."
            )
        if matched_session is None:
            saved = create_snapshot_shared_session(
                db,
                import_run_id=import_run_id,
                client_key=staged["client_key"],
                name=staged["name"],
                session_type=staged["session_type"],
                duration_minutes=staged["duration_minutes"],
                occurrences_per_week=staged["occurrences_per_week"],
                required_room_type=staged["required_room_type"],
                required_lab_type=staged["required_lab_type"],
                specific_room_id=staged["specific_room_id"],
                max_students_per_group=staged["max_students_per_group"],
                allow_parallel_rooms=staged["allow_parallel_rooms"],
                notes=staged["notes"],
                lecturer_ids=staged["lecturer_ids"],
                curriculum_module_ids=staged["curriculum_module_ids"],
                attendance_group_ids=staged["attendance_group_ids"],
            )
            created_count += 1
        else:
            saved = update_snapshot_shared_session(
                db,
                import_run_id=import_run_id,
                shared_session_id=matched_session.id,
                client_key=staged["client_key"],
                name=staged["name"],
                session_type=staged["session_type"],
                duration_minutes=staged["duration_minutes"],
                occurrences_per_week=staged["occurrences_per_week"],
                required_room_type=staged["required_room_type"],
                required_lab_type=staged["required_lab_type"],
                specific_room_id=staged["specific_room_id"],
                max_students_per_group=staged["max_students_per_group"],
                allow_parallel_rooms=staged["allow_parallel_rooms"],
                notes=staged["notes"],
                lecturer_ids=staged["lecturer_ids"],
                curriculum_module_ids=staged["curriculum_module_ids"],
                attendance_group_ids=staged["attendance_group_ids"],
            )
            created_count += 0
            updated_count += 1
        saved_sessions.append(saved)

    return {
        "shared_sessions": saved_sessions,
        "created_count": created_count,
        "updated_count": updated_count,
        "warnings": warnings,
    }
