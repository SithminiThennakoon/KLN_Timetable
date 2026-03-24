from __future__ import annotations

import io
import zipfile
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[2]
FIXTURE_ROOT = BACKEND_DIR / "testdata" / "import_fixtures"

PRODUCTION_LIKE_PACK_NAME = "production_like"
PRODUCTION_LIKE_FILES = (
    "student_enrollments.csv",
    "rooms.csv",
    "lecturers.csv",
    "modules.csv",
    "sessions.csv",
    "session_lecturers.csv",
)

FIXTURE_PACKS: dict[str, dict] = {
    PRODUCTION_LIKE_PACK_NAME: {
        "label": "Production-Like Fixture Pack",
        "description": (
            "A realistic CSV bundle derived from the canonical enrollment sample and "
            "realistic teaching-data seeding logic."
        ),
        "zip_filename": "production_like_import_fixture_pack.zip",
        "files": PRODUCTION_LIKE_FILES,
    }
}


def _pack_directory(pack_name: str) -> Path:
    return FIXTURE_ROOT / pack_name


def get_import_fixture_pack(pack_name: str) -> dict | None:
    pack = FIXTURE_PACKS.get(pack_name)
    if pack is None:
        return None

    directory = _pack_directory(pack_name)
    available = directory.exists() and all((directory / filename).exists() for filename in pack["files"])
    return {
        "name": pack_name,
        "label": pack["label"],
        "description": pack["description"],
        "zip_filename": pack["zip_filename"],
        "files": list(pack["files"]),
        "available": available,
    }


def list_import_fixture_packs() -> list[dict]:
    return [pack for name in FIXTURE_PACKS if (pack := get_import_fixture_pack(name)) is not None]


def read_import_fixture_file(pack_name: str, filename: str) -> tuple[str, bytes] | None:
    pack = get_import_fixture_pack(pack_name)
    if pack is None or not pack["available"]:
        return None
    if filename not in pack["files"]:
        return None

    file_path = _pack_directory(pack_name) / filename
    if not file_path.exists():
        return None
    return filename, file_path.read_bytes()


def build_import_fixture_zip(pack_name: str) -> tuple[str, bytes] | None:
    pack = get_import_fixture_pack(pack_name)
    if pack is None or not pack["available"]:
        return None

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        for filename in pack["files"]:
            file_path = _pack_directory(pack_name) / filename
            archive.write(file_path, arcname=filename)

    return pack["zip_filename"], buffer.getvalue()
