from __future__ import annotations

import csv
import shutil
import sys
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_DIR.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.services.enrollment_inference import (  # noqa: E402
    DEFAULT_ENROLLMENT_CSV,
    build_realistic_demo_dataset_from_enrollment_csv,
)
from app.services.import_fixtures import (  # noqa: E402
    FIXTURE_ROOT,
    PRODUCTION_LIKE_FILES,
    PRODUCTION_LIKE_PACK_NAME,
)


def _write_csv(path: Path, headers: list[str], rows: list[list[str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(headers)
        writer.writerows(rows)


def _bool_string(value: bool) -> str:
    return "true" if value else "false"


def build_rows() -> dict[str, list[list[str]]]:
    dataset = build_realistic_demo_dataset_from_enrollment_csv(str(DEFAULT_ENROLLMENT_CSV))

    module_code_by_client_key = {
        str(module["client_key"]): str(module["code"])
        for module in dataset["modules"]
    }

    room_code_by_client_key = {
        str(room["client_key"]): str(room["client_key"])
        for room in dataset["rooms"]
    }

    rooms_rows = [
        [
            str(room["client_key"]),
            str(room["name"]),
            str(room["capacity"]),
            str(room["room_type"]),
            "" if room.get("lab_type") is None else str(room["lab_type"]),
            "" if room.get("location") is None else str(room["location"]),
            "" if room.get("year_restriction") is None else str(room["year_restriction"]),
        ]
        for room in sorted(dataset["rooms"], key=lambda item: str(item["client_key"]))
    ]

    lecturers_rows = [
        [
            str(lecturer["client_key"]),
            str(lecturer["name"]),
            "" if lecturer.get("email") is None else str(lecturer["email"]),
        ]
        for lecturer in sorted(dataset["lecturers"], key=lambda item: str(item["client_key"]))
    ]

    modules_rows = [
        [
            str(module["code"]),
            str(module["name"]),
            "" if module.get("subject_name") is None else str(module["subject_name"]),
            str(module["year"]),
            str(module["semester"]),
            _bool_string(bool(module.get("is_full_year"))),
        ]
        for module in sorted(dataset["modules"], key=lambda item: str(item["code"]))
    ]

    sessions_rows: list[list[str]] = []
    session_lecturers_rows: list[list[str]] = []
    for session in sorted(dataset["sessions"], key=lambda item: str(item["client_key"])):
        module_client_key = session.get("module_client_key")
        if not module_client_key and session.get("linked_module_client_keys"):
            module_client_key = session["linked_module_client_keys"][0]
        module_code = module_code_by_client_key.get(str(module_client_key or ""), "")
        if not module_code:
            raise ValueError(
                f"Session '{session['client_key']}' could not be mapped to a module_code."
            )

        specific_room_code = ""
        if session.get("specific_room_client_key"):
            specific_room_code = room_code_by_client_key.get(
                str(session["specific_room_client_key"]),
                "",
            )

        sessions_rows.append(
            [
                str(session["client_key"]),
                module_code,
                "|".join(
                    str(module_code_by_client_key[str(key)])
                    for key in session.get("linked_module_client_keys", [])
                    if str(key) in module_code_by_client_key
                ),
                str(session["name"]),
                str(session["session_type"]),
                str(session["duration_minutes"]),
                str(session["occurrences_per_week"]),
                str(session["required_room_type"]),
                "" if session.get("required_lab_type") is None else str(session["required_lab_type"]),
                specific_room_code,
                ""
                if session.get("max_students_per_group") is None
                else str(session["max_students_per_group"]),
                _bool_string(bool(session.get("allow_parallel_rooms"))),
                "" if session.get("notes") is None else str(session["notes"]),
            ]
        )
        for lecturer_code in sorted(str(value) for value in session.get("lecturer_client_keys", [])):
            session_lecturers_rows.append([str(session["client_key"]), lecturer_code])

    return {
        "rooms.csv": rooms_rows,
        "lecturers.csv": lecturers_rows,
        "modules.csv": modules_rows,
        "sessions.csv": sessions_rows,
        "session_lecturers.csv": session_lecturers_rows,
    }


def main() -> None:
    destination = FIXTURE_ROOT / PRODUCTION_LIKE_PACK_NAME
    destination.mkdir(parents=True, exist_ok=True)

    shutil.copyfile(DEFAULT_ENROLLMENT_CSV, destination / "student_enrollments.csv")
    rows_by_file = build_rows()

    _write_csv(
        destination / "rooms.csv",
        ["room_code", "room_name", "capacity", "room_type", "lab_type", "location", "year_restriction"],
        rows_by_file["rooms.csv"],
    )
    _write_csv(
        destination / "lecturers.csv",
        ["lecturer_code", "name", "email"],
        rows_by_file["lecturers.csv"],
    )
    _write_csv(
        destination / "modules.csv",
        ["module_code", "module_name", "subject_name", "nominal_year", "semester_bucket", "is_full_year"],
        rows_by_file["modules.csv"],
    )
    _write_csv(
        destination / "sessions.csv",
        [
            "session_code",
            "module_code",
            "module_codes",
            "session_name",
            "session_type",
            "duration_minutes",
            "occurrences_per_week",
            "required_room_type",
            "required_lab_type",
            "specific_room_code",
            "max_students_per_group",
            "allow_parallel_rooms",
            "notes",
        ],
        rows_by_file["sessions.csv"],
    )
    _write_csv(
        destination / "session_lecturers.csv",
        ["session_code", "lecturer_code"],
        rows_by_file["session_lecturers.csv"],
    )

    missing = [filename for filename in PRODUCTION_LIKE_FILES if not (destination / filename).exists()]
    if missing:
        raise RuntimeError(f"Fixture generation failed; missing files: {', '.join(missing)}")

    print(f"Wrote fixture pack to {destination}")


if __name__ == "__main__":
    main()
