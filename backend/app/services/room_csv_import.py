from __future__ import annotations

import csv
from pathlib import Path

from sqlalchemy.orm import Session

from app.models.imports import ImportRun
from app.models.snapshot import SnapshotRoom
from app.services.snapshot_completion import create_snapshot_room, update_snapshot_room


REQUIRED_COLUMNS = {"room_code", "room_name", "capacity", "room_type"}
OPTIONAL_COLUMNS = {"lab_type", "location", "year_restriction"}
SUPPORTED_ROOM_TYPES = {"lecture", "lab", "seminar"}


def _normalize_header(value: str) -> str:
    return (value or "").replace("\ufeff", "").strip()


def _normalize_cell(value: str | None) -> str:
    return (value or "").strip()


def _is_blank_row(values: list[str]) -> bool:
    return not any(_normalize_cell(value) for value in values)


def import_rooms_csv(db: Session, *, import_run_id: int, csv_path: str) -> dict:
    import_run = db.query(ImportRun).filter(ImportRun.id == import_run_id).first()
    if import_run is None:
        raise ValueError(f"Import run {import_run_id} was not found")

    path = Path(csv_path)
    if not path.exists():
        raise FileNotFoundError(f"Rooms CSV not found: {path}")

    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle)
        raw_headers = next(reader, None)
        if raw_headers is None:
            raise ValueError("Rooms CSV is empty")

        headers = [_normalize_header(value) for value in raw_headers]
        duplicate_headers = sorted({header for header in headers if header and headers.count(header) > 1})
        if duplicate_headers:
            raise ValueError(f"Rooms CSV has duplicate headers: {', '.join(duplicate_headers)}")

        missing_columns = sorted(REQUIRED_COLUMNS - set(headers))
        if missing_columns:
            raise ValueError(
                f"Rooms CSV is missing required columns: {', '.join(missing_columns)}"
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

        staged_rooms: list[dict] = []
        seen_room_codes: set[str] = set()

        for row_number, values in enumerate(reader, start=2):
            if _is_blank_row(values):
                continue

            padded = list(values) + [""] * max(0, len(headers) - len(values))
            row = {headers[index]: _normalize_cell(padded[index]) for index in range(len(headers))}

            room_code = row["room_code"]
            room_name = row["room_name"]
            capacity_raw = row["capacity"]
            room_type = row["room_type"].lower()
            lab_type = row.get("lab_type") or None
            location = row.get("location", "")
            year_restriction_raw = row.get("year_restriction", "")

            row_errors: list[str] = []
            if not room_code:
                row_errors.append("blank room_code")
            if not room_name:
                row_errors.append("blank room_name")
            if room_code in seen_room_codes:
                row_errors.append(f"duplicate room_code '{room_code}'")
            if room_type not in SUPPORTED_ROOM_TYPES:
                row_errors.append(
                    f"unsupported room_type '{row.get('room_type', '')}' (expected one of: lecture, lab, seminar)"
                )

            try:
                capacity = int(capacity_raw)
                if capacity <= 0:
                    row_errors.append("capacity must be a positive integer")
            except ValueError:
                capacity = None
                row_errors.append("capacity must be a positive integer")

            year_restriction = None
            if year_restriction_raw:
                try:
                    year_restriction = int(year_restriction_raw)
                    if year_restriction < 1 or year_restriction > 6:
                        row_errors.append("year_restriction must be between 1 and 6")
                except ValueError:
                    row_errors.append("year_restriction must be an integer between 1 and 6")

            if row_errors:
                raise ValueError(f"Rooms CSV row {row_number}: {'; '.join(row_errors)}")

            seen_room_codes.add(room_code)

            if capacity is not None and capacity < 10:
                warnings.append(
                    {
                        "row_number": row_number,
                        "message": f"Room '{room_name}' has a very small capacity ({capacity})",
                    }
                )
            if capacity is not None and capacity > 2000:
                warnings.append(
                    {
                        "row_number": row_number,
                        "message": f"Room '{room_name}' has a very large capacity ({capacity})",
                    }
                )
            if room_type == "lab" and not lab_type:
                warnings.append(
                    {
                        "row_number": row_number,
                        "message": f"Lab room '{room_name}' has no lab_type",
                    }
                )
            if room_type != "lab" and lab_type:
                warnings.append(
                    {
                        "row_number": row_number,
                        "message": f"Non-lab room '{room_name}' includes lab_type '{lab_type}'",
                    }
                )

            staged_rooms.append(
                {
                    "client_key": room_code,
                    "name": room_name,
                    "capacity": capacity,
                    "room_type": room_type,
                    "lab_type": lab_type,
                    "location": location,
                    "year_restriction": year_restriction,
                    "notes": "Imported from rooms.csv",
                }
            )

    existing_rooms = (
        db.query(SnapshotRoom).filter(SnapshotRoom.import_run_id == import_run_id).all()
    )
    by_client_key = {
        (room.client_key or "").strip(): room
        for room in existing_rooms
        if (room.client_key or "").strip()
    }
    by_name = {room.name.strip(): room for room in existing_rooms if room.name and room.name.strip()}

    created_count = 0
    updated_count = 0
    saved_rooms: list[dict] = []

    for staged in staged_rooms:
        matched_room = by_client_key.get(staged["client_key"])
        conflicting_name_room = by_name.get(staged["name"])
        if matched_room is None and conflicting_name_room is not None:
            raise ValueError(
                "Rooms CSV conflicts with existing room "
                f"'{staged['name']}'. Re-import only updates matching room_code values; "
                "resolve the conflict manually or reuse the original room_code."
            )
        if matched_room is None:
            saved = create_snapshot_room(
                db,
                import_run_id=import_run_id,
                client_key=staged["client_key"],
                name=staged["name"],
                capacity=staged["capacity"],
                room_type=staged["room_type"],
                lab_type=staged["lab_type"],
                location=staged["location"],
                year_restriction=staged["year_restriction"],
                notes=staged["notes"],
            )
            created_count += 1
        else:
            saved = update_snapshot_room(
                db,
                import_run_id=import_run_id,
                room_id=matched_room.id,
                client_key=staged["client_key"],
                name=staged["name"],
                capacity=staged["capacity"],
                room_type=staged["room_type"],
                lab_type=staged["lab_type"],
                location=staged["location"],
                year_restriction=staged["year_restriction"],
                notes=staged["notes"],
            )
            updated_count += 1
        saved_rooms.append(saved)

    return {
        "rooms": saved_rooms,
        "created_count": created_count,
        "updated_count": updated_count,
        "warnings": warnings,
    }
