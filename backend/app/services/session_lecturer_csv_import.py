from __future__ import annotations

import csv
from pathlib import Path

from sqlalchemy.orm import Session

from app.models.imports import ImportRun
from app.models.snapshot import SnapshotLecturer, SnapshotSharedSession
from app.services.snapshot_completion import update_snapshot_shared_session


REQUIRED_COLUMNS = {"session_code", "lecturer_code"}


def _normalize_header(value: str) -> str:
    return (value or "").replace("\ufeff", "").strip()


def _normalize_cell(value: str | None) -> str:
    return (value or "").strip()


def _is_blank_row(values: list[str]) -> bool:
    return not any(_normalize_cell(value) for value in values)


def import_session_lecturers_csv(db: Session, *, import_run_id: int, csv_path: str) -> dict:
    import_run = db.query(ImportRun).filter(ImportRun.id == import_run_id).first()
    if import_run is None:
        raise ValueError(f"Import run {import_run_id} was not found")

    path = Path(csv_path)
    if not path.exists():
        raise FileNotFoundError(f"Session lecturers CSV not found: {path}")

    sessions = (
        db.query(SnapshotSharedSession)
        .filter(SnapshotSharedSession.import_run_id == import_run_id)
        .all()
    )
    lecturers = (
        db.query(SnapshotLecturer)
        .filter(SnapshotLecturer.import_run_id == import_run_id)
        .all()
    )
    session_by_code = {
        (session.client_key or "").strip(): session
        for session in sessions
        if (session.client_key or "").strip()
    }
    lecturer_by_code = {
        (lecturer.client_key or "").strip(): lecturer
        for lecturer in lecturers
        if (lecturer.client_key or "").strip()
    }

    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle)
        raw_headers = next(reader, None)
        if raw_headers is None:
            raise ValueError("Session lecturers CSV is empty")

        headers = [_normalize_header(value) for value in raw_headers]
        duplicate_headers = sorted({header for header in headers if header and headers.count(header) > 1})
        if duplicate_headers:
            raise ValueError(
                f"Session lecturers CSV has duplicate headers: {', '.join(duplicate_headers)}"
            )

        missing_columns = sorted(REQUIRED_COLUMNS - set(headers))
        if missing_columns:
            raise ValueError(
                f"Session lecturers CSV is missing required columns: {', '.join(missing_columns)}"
            )

        unknown_columns = sorted(set(headers) - REQUIRED_COLUMNS)
        warnings: list[dict] = []
        if unknown_columns:
            warnings.append(
                {
                    "row_number": None,
                    "message": f"Ignoring unknown columns: {', '.join(unknown_columns)}",
                }
            )

        lecturer_ids_by_session_id: dict[int, set[int]] = {}
        seen_pairs: set[tuple[str, str]] = set()

        for row_number, values in enumerate(reader, start=2):
            if _is_blank_row(values):
                continue

            padded = list(values) + [""] * max(0, len(headers) - len(values))
            row = {headers[index]: _normalize_cell(padded[index]) for index in range(len(headers))}

            session_code = row["session_code"]
            lecturer_code = row["lecturer_code"]
            row_errors: list[str] = []

            if not session_code:
                row_errors.append("blank session_code")
            if not lecturer_code:
                row_errors.append("blank lecturer_code")

            pair = (session_code, lecturer_code)
            if pair in seen_pairs:
                row_errors.append(
                    f"duplicate session/lecturer pair '{session_code}' + '{lecturer_code}'"
                )

            session = session_by_code.get(session_code)
            if session is None:
                row_errors.append(
                    f"session_code '{session_code}' does not resolve to an imported session"
                )

            lecturer = lecturer_by_code.get(lecturer_code)
            if lecturer is None:
                row_errors.append(
                    f"lecturer_code '{lecturer_code}' does not resolve to an imported lecturer"
                )

            if row_errors:
                raise ValueError(
                    f"Session lecturers CSV row {row_number}: {'; '.join(row_errors)}"
                )

            seen_pairs.add(pair)
            lecturer_ids_by_session_id.setdefault(int(session.id), set()).add(int(lecturer.id))

    updated_sessions: list[dict] = []
    updated_count = 0
    for session in sessions:
        extra_ids = lecturer_ids_by_session_id.get(int(session.id))
        if not extra_ids:
            continue
        combined_ids = sorted({int(lecturer.id) for lecturer in session.lecturers} | set(extra_ids))
        updated = update_snapshot_shared_session(
            db,
            import_run_id=import_run_id,
            shared_session_id=int(session.id),
            client_key=session.client_key,
            name=session.name,
            session_type=session.session_type,
            duration_minutes=session.duration_minutes,
            occurrences_per_week=session.occurrences_per_week,
            required_room_type=session.required_room_type,
            required_lab_type=session.required_lab_type,
            specific_room_id=session.specific_room_id,
            max_students_per_group=session.max_students_per_group,
            allow_parallel_rooms=session.allow_parallel_rooms,
            notes=session.notes,
            lecturer_ids=combined_ids,
            curriculum_module_ids=[int(module.id) for module in session.curriculum_modules],
            attendance_group_ids=[int(group.id) for group in session.attendance_groups],
        )
        updated_sessions.append(updated)
        updated_count += 1

    return {
        "shared_sessions": updated_sessions,
        "created_count": 0,
        "updated_count": updated_count,
        "warnings": warnings,
    }
