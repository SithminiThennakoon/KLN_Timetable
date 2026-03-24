from __future__ import annotations

import csv
from pathlib import Path

from sqlalchemy.orm import Session

from app.models.imports import ImportRun
from app.models.snapshot import SnapshotLecturer
from app.services.snapshot_completion import (
    create_snapshot_lecturer,
    update_snapshot_lecturer,
)


REQUIRED_COLUMNS = {"lecturer_code", "name"}
OPTIONAL_COLUMNS = {"email"}


def _normalize_header(value: str) -> str:
    return (value or "").replace("\ufeff", "").strip()


def _normalize_cell(value: str | None) -> str:
    return (value or "").strip()


def _is_blank_row(values: list[str]) -> bool:
    return not any(_normalize_cell(value) for value in values)


def import_lecturers_csv(db: Session, *, import_run_id: int, csv_path: str) -> dict:
    import_run = db.query(ImportRun).filter(ImportRun.id == import_run_id).first()
    if import_run is None:
        raise ValueError(f"Import run {import_run_id} was not found")

    path = Path(csv_path)
    if not path.exists():
        raise FileNotFoundError(f"Lecturers CSV not found: {path}")

    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle)
        raw_headers = next(reader, None)
        if raw_headers is None:
            raise ValueError("Lecturers CSV is empty")

        headers = [_normalize_header(value) for value in raw_headers]
        duplicate_headers = sorted({header for header in headers if header and headers.count(header) > 1})
        if duplicate_headers:
            raise ValueError(f"Lecturers CSV has duplicate headers: {', '.join(duplicate_headers)}")

        missing_columns = sorted(REQUIRED_COLUMNS - set(headers))
        if missing_columns:
            raise ValueError(
                f"Lecturers CSV is missing required columns: {', '.join(missing_columns)}"
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

        staged_lecturers: list[dict] = []
        seen_codes: set[str] = set()

        for row_number, values in enumerate(reader, start=2):
            if _is_blank_row(values):
                continue

            padded = list(values) + [""] * max(0, len(headers) - len(values))
            row = {headers[index]: _normalize_cell(padded[index]) for index in range(len(headers))}

            lecturer_code = row["lecturer_code"]
            name = row["name"]
            email = row.get("email") or None

            row_errors: list[str] = []
            if not lecturer_code:
                row_errors.append("blank lecturer_code")
            if not name:
                row_errors.append("blank name")
            if lecturer_code in seen_codes:
                row_errors.append(f"duplicate lecturer_code '{lecturer_code}'")

            if row_errors:
                raise ValueError(f"Lecturers CSV row {row_number}: {'; '.join(row_errors)}")

            seen_codes.add(lecturer_code)

            if not email:
                warnings.append(
                    {
                        "row_number": row_number,
                        "message": f"Lecturer '{name}' has no email",
                    }
                )

            staged_lecturers.append(
                {
                    "client_key": lecturer_code,
                    "name": name,
                    "email": email,
                    "notes": "Imported from lecturers.csv",
                }
            )

    existing_lecturers = (
        db.query(SnapshotLecturer)
        .filter(SnapshotLecturer.import_run_id == import_run_id)
        .all()
    )
    by_client_key = {
        (lecturer.client_key or "").strip(): lecturer
        for lecturer in existing_lecturers
        if (lecturer.client_key or "").strip()
    }
    by_name = {
        lecturer.name.strip(): lecturer
        for lecturer in existing_lecturers
        if lecturer.name and lecturer.name.strip()
    }

    created_count = 0
    updated_count = 0
    saved_lecturers: list[dict] = []

    for staged in staged_lecturers:
        matched_lecturer = by_client_key.get(staged["client_key"])
        conflicting_name_lecturer = by_name.get(staged["name"])
        if matched_lecturer is None and conflicting_name_lecturer is not None:
            raise ValueError(
                "Lecturers CSV conflicts with existing lecturer "
                f"'{staged['name']}'. Re-import only updates matching lecturer_code values; "
                "resolve the conflict manually or reuse the original lecturer_code."
            )
        if matched_lecturer is None:
            saved = create_snapshot_lecturer(
                db,
                import_run_id=import_run_id,
                client_key=staged["client_key"],
                name=staged["name"],
                email=staged["email"],
                notes=staged["notes"],
            )
            created_count += 1
        else:
            saved = update_snapshot_lecturer(
                db,
                import_run_id=import_run_id,
                lecturer_id=matched_lecturer.id,
                client_key=staged["client_key"],
                name=staged["name"],
                email=staged["email"],
                notes=staged["notes"],
            )
            updated_count += 1
        saved_lecturers.append(saved)

    return {
        "lecturers": saved_lecturers,
        "created_count": created_count,
        "updated_count": updated_count,
        "warnings": warnings,
    }
