from __future__ import annotations

import csv
from pathlib import Path

from sqlalchemy.orm import Session

from app.models.academic import CurriculumModule, StudentModuleMembership
from app.models.imports import ImportRun


REQUIRED_COLUMNS = {"module_code", "module_name"}
OPTIONAL_COLUMNS = {"subject_name", "nominal_year", "semester_bucket", "is_full_year"}
SUPPORTED_SEMESTER_BUCKETS = {"1", "2"}
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


def import_modules_csv(db: Session, *, import_run_id: int, csv_path: str) -> dict:
    import_run = db.query(ImportRun).filter(ImportRun.id == import_run_id).first()
    if import_run is None:
        raise ValueError(f"Import run {import_run_id} was not found")

    path = Path(csv_path)
    if not path.exists():
        raise FileNotFoundError(f"Modules CSV not found: {path}")

    modules = (
        db.query(CurriculumModule)
        .join(
            StudentModuleMembership,
            StudentModuleMembership.curriculum_module_id == CurriculumModule.id,
        )
        .filter(StudentModuleMembership.import_run_id == import_run_id)
        .distinct()
        .all()
    )
    modules_by_code = {
        (module.code or "").strip(): module for module in modules if (module.code or "").strip()
    }

    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle)
        raw_headers = next(reader, None)
        if raw_headers is None:
            raise ValueError("Modules CSV is empty")

        headers = [_normalize_header(value) for value in raw_headers]
        duplicate_headers = sorted({header for header in headers if header and headers.count(header) > 1})
        if duplicate_headers:
            raise ValueError(f"Modules CSV has duplicate headers: {', '.join(duplicate_headers)}")

        missing_columns = sorted(REQUIRED_COLUMNS - set(headers))
        if missing_columns:
            raise ValueError(
                f"Modules CSV is missing required columns: {', '.join(missing_columns)}"
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

        staged_modules: list[dict] = []
        seen_codes: set[str] = set()

        for row_number, values in enumerate(reader, start=2):
            if _is_blank_row(values):
                continue

            padded = list(values) + [""] * max(0, len(headers) - len(values))
            row = {headers[index]: _normalize_cell(padded[index]) for index in range(len(headers))}

            module_code = row["module_code"]
            module_name = row["module_name"]
            subject_name = row.get("subject_name") or None
            nominal_year_raw = row.get("nominal_year", "")
            semester_bucket_raw = row.get("semester_bucket", "")
            is_full_year_raw = row.get("is_full_year", "")

            row_errors: list[str] = []
            if not module_code:
                row_errors.append("blank module_code")
            if not module_name:
                row_errors.append("blank module_name")
            if module_code in seen_codes:
                row_errors.append(f"duplicate module_code '{module_code}'")
            if module_code not in modules_by_code:
                row_errors.append(
                    f"module_code '{module_code}' does not resolve to accepted enrollment-derived module data"
                )

            nominal_year = None
            if nominal_year_raw:
                try:
                    nominal_year = int(nominal_year_raw)
                    if nominal_year <= 0:
                        row_errors.append("nominal_year must be a positive integer")
                except ValueError:
                    row_errors.append("nominal_year must be a positive integer")

            semester_bucket = None
            if semester_bucket_raw:
                if semester_bucket_raw not in SUPPORTED_SEMESTER_BUCKETS:
                    row_errors.append("semester_bucket must be 1 or 2")
                else:
                    semester_bucket = int(semester_bucket_raw)

            is_full_year = None
            if is_full_year_raw:
                is_full_year = _parse_bool(is_full_year_raw)
                if is_full_year is None:
                    row_errors.append("is_full_year must be a boolean value")

            if row_errors:
                raise ValueError(f"Modules CSV row {row_number}: {'; '.join(row_errors)}")

            seen_codes.add(module_code)

            matched_module = modules_by_code[module_code]
            if nominal_year is not None and matched_module.nominal_year and nominal_year != matched_module.nominal_year:
                warnings.append(
                    {
                        "row_number": row_number,
                        "message": f"Module '{module_code}' nominal_year overrides enrollment-derived value {matched_module.nominal_year}",
                    }
                )
            if semester_bucket is not None and matched_module.semester_bucket and semester_bucket != matched_module.semester_bucket:
                warnings.append(
                    {
                        "row_number": row_number,
                        "message": f"Module '{module_code}' semester_bucket overrides enrollment-derived value {matched_module.semester_bucket}",
                    }
                )

            staged_modules.append(
                {
                    "module": matched_module,
                    "module_name": module_name,
                    "subject_name": subject_name,
                    "nominal_year": nominal_year,
                    "semester_bucket": semester_bucket,
                    "is_full_year": is_full_year,
                }
            )

    updated_modules: list[dict] = []
    for staged in staged_modules:
        module = staged["module"]
        module.name = staged["module_name"]
        if staged["subject_name"] is not None:
            module.subject_name = staged["subject_name"]
        if staged["nominal_year"] is not None:
            module.nominal_year = staged["nominal_year"]
        if staged["semester_bucket"] is not None:
            module.semester_bucket = staged["semester_bucket"]
        if staged["is_full_year"] is not None:
            module.is_full_year = staged["is_full_year"]
        db.flush()
        updated_modules.append(
            {
                "id": int(module.id),
                "code": module.code,
                "name": module.name,
                "subject_name": module.subject_name,
                "nominal_year": module.nominal_year,
                "semester_bucket": module.semester_bucket,
                "is_full_year": bool(module.is_full_year),
            }
        )

    return {
        "modules": updated_modules,
        "created_count": 0,
        "updated_count": len(updated_modules),
        "warnings": warnings,
    }
