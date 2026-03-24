from __future__ import annotations

import hashlib
import json
import logging
from collections import Counter, defaultdict

from sqlalchemy.orm import Session

from app.models.academic import (
    CurriculumModule,
    Programme,
    ProgrammePath,
    StudentModuleMembership,
    StudentProgrammeContext,
)
from app.models.imports import (
    ImportEnrollment,
    ImportReviewRule,
    ImportRow,
    ImportRun,
    ImportStudent,
)
from app.models.solver import AttendanceGroup, AttendanceGroupStudent
from app.services.csv_import_analysis import (
    ReviewRule,
    StagedEnrollmentRow,
    _apply_rules,
    _iter_rows,
    _latest_academic_year,
)
from app.services.enrollment_inference import STREAM_NAME_MAP

VALID_IMPORT_STATUSES = {"valid", "valid_exception"}
BROAD_ENTRY_STREAMS = {"PS", "BS"}
BULK_INSERT_CHUNK_SIZE = 5000
logger = logging.getLogger("uvicorn.error")


def _json_list(values: set[str] | list[str] | tuple[str, ...]) -> str:
    return json.dumps(sorted({str(value) for value in values if str(value).strip()}))


def _normalized_path_value(value: str | None) -> str | None:
    if value is None:
        return None
    value = str(value).strip()
    return value or None


def _is_common_path(value: str | None) -> bool:
    normalized = _normalized_path_value(value)
    return normalized in {None, "0"}


def _path_code(value: str | None) -> str:
    normalized = _normalized_path_value(value)
    return "COMMON" if _is_common_path(normalized) else f"P{normalized}"


def _path_name(stream: str, study_year: int, value: str | None) -> str:
    normalized = _normalized_path_value(value)
    if _is_common_path(normalized):
        return f"{stream} Year {study_year} Common"
    return f"{stream} Year {study_year} Path {normalized}"


def _programme_defaults(stream_code: str) -> dict:
    is_direct_entry = stream_code not in BROAD_ENTRY_STREAMS
    return {
        "name": STREAM_NAME_MAP.get(stream_code, stream_code),
        "programme_family": "broad_entry" if stream_code in BROAD_ENTRY_STREAMS else "direct_entry",
        "is_direct_entry": is_direct_entry,
        "intake_label": f"{stream_code} Intake",
    }


def _membership_role(row: StagedEnrollmentRow) -> tuple[str, bool]:
    if _is_common_path(row.effective_course_path_no):
        return ("common", True)
    return ("path_specific", False)


def _interpretation_confidence(row: StagedEnrollmentRow) -> str:
    if row.status == "valid":
        return "high"
    if row.status == "valid_exception":
        return "medium"
    return "low"


def _included_rows(
    rows: list[StagedEnrollmentRow],
    *,
    target_academic_year: str | None,
    allowed_attempts: tuple[str, ...],
) -> list[StagedEnrollmentRow]:
    return [
        row
        for row in rows
        if row.status in VALID_IMPORT_STATUSES
        and (not target_academic_year or row.academic_year == target_academic_year)
        and (not allowed_attempts or row.attempt in allowed_attempts)
    ]


def _infer_primary_path(rows: list[StagedEnrollmentRow]) -> tuple[str | None, str, set[str]]:
    path_counts = Counter(
        _normalized_path_value(row.effective_course_path_no)
        for row in rows
        if not _is_common_path(row.effective_course_path_no)
    )
    if not path_counts:
        return (None, "low", {"only_common_or_unassigned_path_rows"})
    [(top_path, top_count), *rest] = path_counts.most_common()
    ambiguity_flags: set[str] = set()
    if rest:
        ambiguity_flags.add("multiple_non_common_paths_seen")
    confidence = "high" if len(rest) == 0 else "medium"
    if sum(path_counts.values()) > top_count:
        confidence = "medium"
    return (top_path, confidence, ambiguity_flags)


def _group_label(
    *,
    academic_year: str,
    study_year: int | None,
    programme_code: str | None,
    path_code: str | None,
    student_count: int,
) -> str:
    parts = [academic_year]
    if programme_code:
        parts.append(programme_code)
    if study_year is not None:
        parts.append(f"Y{study_year}")
    if path_code:
        parts.append(path_code)
    return f"{' '.join(parts)} ({student_count} students)"


def _bulk_insert_mappings(db: Session, model, mappings: list[dict]) -> None:
    if not mappings:
        return
    for start in range(0, len(mappings), BULK_INSERT_CHUNK_SIZE):
        db.bulk_insert_mappings(model, mappings[start : start + BULK_INSERT_CHUNK_SIZE])


def summarize_import_run(db: Session, import_run_id: int) -> dict:
    import_run = (
        db.query(ImportRun)
        .filter(ImportRun.id == import_run_id)
        .first()
    )
    if not import_run:
        raise ValueError(f"Import run not found: {import_run_id}")

    return {
        "import_run_id": int(import_run.id),
        "source_file": import_run.source_file,
        "status": import_run.status,
        "selected_academic_year": import_run.selected_academic_year,
        "allowed_attempts": json.loads(import_run.allowed_attempts_json or "[]"),
        "counts": {
            "rows": db.query(ImportRow).filter(ImportRow.import_run_id == import_run_id).count(),
            "students": db.query(ImportEnrollment.student_id)
            .filter(ImportEnrollment.import_run_id == import_run_id)
            .distinct()
            .count(),
            "enrollments": db.query(ImportEnrollment).filter(ImportEnrollment.import_run_id == import_run_id).count(),
            "programmes": db.query(StudentProgrammeContext.programme_id)
            .filter(StudentProgrammeContext.import_run_id == import_run_id)
            .distinct()
            .count(),
            "programme_paths": db.query(ProgrammePath.id)
            .join(Programme, Programme.id == ProgrammePath.programme_id)
            .filter(
                Programme.code.in_(
                    db.query(ImportEnrollment.stream_code)
                    .filter(ImportEnrollment.import_run_id == import_run_id)
                    .distinct()
                )
            )
            .count(),
            "curriculum_modules": db.query(StudentModuleMembership.curriculum_module_id)
            .filter(StudentModuleMembership.import_run_id == import_run_id)
            .distinct()
            .count(),
            "student_programme_contexts": db.query(StudentProgrammeContext)
            .filter(StudentProgrammeContext.import_run_id == import_run_id)
            .count(),
            "student_module_memberships": db.query(StudentModuleMembership)
            .filter(StudentModuleMembership.import_run_id == import_run_id)
            .count(),
            "attendance_groups": db.query(AttendanceGroup)
            .filter(AttendanceGroup.import_run_id == import_run_id)
            .count(),
        },
    }


def materialize_import_run(
    db: Session,
    *,
    source_file: str,
    review_rules: list[ReviewRule] | None = None,
    target_academic_year: str | None = None,
    allowed_attempts: tuple[str, ...] = ("1",),
    notes: str | None = None,
) -> ImportRun:
    rows = _iter_rows(source_file)
    logger.info("Import materialization parsed rows=%s source=%s", len(rows), source_file)
    review_rules = review_rules or []
    if review_rules:
        _apply_rules(rows, review_rules)

    included = [row for row in rows if row.status in VALID_IMPORT_STATUSES]
    if target_academic_year is None:
        target_academic_year = _latest_academic_year(included)
    projected_rows = _included_rows(
        rows,
        target_academic_year=target_academic_year,
        allowed_attempts=allowed_attempts,
    )
    logger.info(
        "Import materialization selected academic_year=%s included_rows=%s projected_rows=%s",
        target_academic_year,
        len(included),
        len(projected_rows),
    )

    import_run = ImportRun(
        source_file=source_file,
        source_format="uok_fos_enrollment_csv",
        status="materialized",
        selected_academic_year=target_academic_year,
        allowed_attempts_json=json.dumps(list(allowed_attempts)),
        notes=notes,
    )
    db.add(import_run)
    db.flush()

    if review_rules:
        db.add_all(
            [
                ImportReviewRule(
                    import_run_id=int(import_run.id),
                    bucket_type=rule.bucket_type,
                    bucket_key=rule.bucket_key,
                    action=rule.action,
                    label=rule.label,
                )
                for rule in review_rules
            ]
        )

    unique_hashes = sorted(
        {
            row.student_hash
            for row in rows
            if row.student_hash and row.student_hash.strip()
        }
    )
    student_id_by_hash = {
        student_hash: int(student_id)
        for student_id, student_hash in db.query(
            ImportStudent.id,
            ImportStudent.student_hash,
        )
        .filter(ImportStudent.student_hash.in_(unique_hashes))
        .all()
    }
    missing_student_hashes = [
        student_hash for student_hash in unique_hashes if student_hash not in student_id_by_hash
    ]
    if missing_student_hashes:
        _bulk_insert_mappings(
            db,
            ImportStudent,
            [{"student_hash": student_hash} for student_hash in missing_student_hashes],
        )
        db.flush()
        student_id_by_hash.update(
            {
                student_hash: int(student_id)
                for student_id, student_hash in db.query(
                    ImportStudent.id,
                    ImportStudent.student_hash,
                )
                .filter(ImportStudent.student_hash.in_(missing_student_hashes))
                .all()
            }
        )
    logger.info(
        "Import materialization students existing=%s created=%s",
        len(student_id_by_hash) - len(missing_student_hashes),
        len(missing_student_hashes),
    )

    row_mappings: list[dict] = []
    for row in rows:
        student_id = student_id_by_hash.get(row.student_hash) if row.student_hash else None
        row_mappings.append(
            {
                "import_run_id": int(import_run.id),
                "student_id": student_id,
                "row_number": row.row_number,
                "raw_course_path_no": _normalized_path_value(row.course_path_no),
                "raw_course_code": row.course_code,
                "raw_year": row.year,
                "raw_academic_year": row.academic_year,
                "raw_attempt": row.attempt,
                "raw_stream": row.stream,
                "raw_batch": row.batch,
                "raw_student_hash": row.student_hash,
                "module_subject_code": row.module_subject_code,
                "module_nominal_year": row.module_nominal_year,
                "module_nominal_semester_code": row.module_nominal_semester_code,
                "module_nominal_semester": row.module_nominal_semester,
                "is_full_year": bool(row.is_full_year),
                "anomaly_codes_json": _json_list(row.anomaly_codes),
                "resolved_anomaly_codes_json": _json_list(row.resolved_anomaly_codes),
                "matched_rule_actions_json": _json_list(row.matched_rule_actions),
                "review_status": row.status,
                "effective_course_path_no": _normalized_path_value(row.effective_course_path_no),
            }
        )
    _bulk_insert_mappings(db, ImportRow, row_mappings)
    db.flush()
    logger.info("Import materialization persisted import_rows=%s", len(row_mappings))

    row_id_by_number = {
        int(row_number): int(row_id)
        for row_id, row_number in db.query(ImportRow.id, ImportRow.row_number)
        .filter(ImportRow.import_run_id == int(import_run.id))
        .all()
    }

    enrollment_mappings: list[dict] = []
    for row in rows:
        student_id = student_id_by_hash.get(row.student_hash) if row.student_hash else None
        enrollment_mappings.append(
            {
                "import_run_id": int(import_run.id),
                "import_row_id": row_id_by_number[row.row_number],
                "student_id": student_id,
                "academic_year": row.academic_year or None,
                "attempt": row.attempt or None,
                "stream_code": row.stream or None,
                "study_year": int(row.year) if row.year.isdigit() else None,
                "batch": row.batch or None,
                "raw_course_path_no": _normalized_path_value(row.course_path_no),
                "effective_course_path_no": _normalized_path_value(row.effective_course_path_no),
                "course_code": row.course_code or None,
                "module_subject_code": row.module_subject_code,
                "module_nominal_year": row.module_nominal_year,
                "module_nominal_semester_code": row.module_nominal_semester_code,
                "module_nominal_semester": row.module_nominal_semester,
                "is_full_year": bool(row.is_full_year),
                "review_status": row.status,
            }
        )
    _bulk_insert_mappings(db, ImportEnrollment, enrollment_mappings)
    db.flush()
    logger.info("Import materialization persisted import_enrollments=%s", len(enrollment_mappings))

    projected_streams = sorted({row.stream for row in projected_rows if row.stream})
    existing_programmes = {
        programme.code: programme
        for programme in db.query(Programme)
        .filter(Programme.code.in_(projected_streams))
        .all()
    }
    new_programmes = []
    for stream_code in projected_streams:
        if stream_code in existing_programmes:
            continue
        defaults = _programme_defaults(stream_code)
        duration_years = max(
            int(row.year)
            for row in projected_rows
            if row.stream == stream_code and row.year.isdigit()
        )
        new_programmes.append(
            Programme(
                code=stream_code,
                name=defaults["name"],
                duration_years=duration_years,
                intake_label=defaults["intake_label"],
                programme_family=defaults["programme_family"],
                is_direct_entry=defaults["is_direct_entry"],
            )
        )
    if new_programmes:
        db.add_all(new_programmes)
        db.flush()
        for programme in new_programmes:
            existing_programmes[programme.code] = programme
    logger.info(
        "Import materialization programmes total=%s created=%s",
        len(existing_programmes),
        len(new_programmes),
    )

    projected_path_keys = sorted(
        {
            (row.stream, int(row.year), _path_code(row.effective_course_path_no))
            for row in projected_rows
            if row.stream and row.year.isdigit()
        }
    )
    relevant_programme_ids = [int(programme.id) for programme in existing_programmes.values()]
    existing_paths = {
        (int(path.programme_id), int(path.study_year), path.code): path
        for path in db.query(ProgrammePath)
        .filter(ProgrammePath.programme_id.in_(relevant_programme_ids))
        .all()
    }
    new_paths = []
    for stream_code, study_year, path_code in projected_path_keys:
        programme = existing_programmes[stream_code]
        key = (int(programme.id), study_year, path_code)
        if key in existing_paths:
            continue
        raw_values = {
            _normalized_path_value(row.effective_course_path_no) or "0"
            for row in projected_rows
            if row.stream == stream_code
            and row.year.isdigit()
            and int(row.year) == study_year
            and _path_code(row.effective_course_path_no) == path_code
        }
        new_paths.append(
            ProgrammePath(
                programme_id=int(programme.id),
                study_year=study_year,
                code=path_code,
                name=_path_name(stream_code, study_year, path_code.removeprefix("P") if path_code != "COMMON" else "0"),
                is_common=path_code == "COMMON",
                raw_course_path_nos_json=json.dumps(sorted(raw_values)),
                interpretation_confidence="high" if path_code != "COMMON" else "medium",
            )
        )
    if new_paths:
        db.add_all(new_paths)
        db.flush()
        for path in new_paths:
            key = (int(path.programme_id), int(path.study_year), path.code)
            existing_paths[key] = path
    logger.info(
        "Import materialization programme_paths total=%s created=%s",
        len(existing_paths),
        len(new_paths),
    )

    sample_row_by_module_key: dict[tuple[str, int | None, int | None], StagedEnrollmentRow] = {}
    for row in projected_rows:
        if row.course_code:
            sample_row_by_module_key.setdefault(
                (row.course_code, row.module_nominal_year, row.module_nominal_semester),
                row,
            )

    module_keys = sorted(
        {
            (
                row.course_code,
                row.module_nominal_year,
                row.module_nominal_semester,
            )
            for row in projected_rows
            if row.course_code
        }
    )
    existing_modules = {
        (module.code, module.nominal_year, module.semester_bucket): module
        for module in db.query(CurriculumModule)
        .filter(CurriculumModule.code.in_([key[0] for key in module_keys]))
        .all()
    }
    new_modules = []
    for course_code, nominal_year, semester_bucket in module_keys:
        key = (course_code, nominal_year, semester_bucket)
        if key in existing_modules:
            continue
        sample_row = sample_row_by_module_key[key]
        new_modules.append(
            CurriculumModule(
                code=course_code,
                canonical_code=course_code,
                name=course_code,
                subject_name=sample_row.module_subject_code or course_code.split()[0],
                subject_code=sample_row.module_subject_code,
                nominal_year=nominal_year,
                semester_bucket=semester_bucket,
                is_full_year=bool(sample_row.is_full_year),
            )
        )
    if new_modules:
        db.add_all(new_modules)
        db.flush()
        for module in new_modules:
            key = (module.code, module.nominal_year, module.semester_bucket)
            existing_modules[key] = module
    logger.info(
        "Import materialization curriculum_modules total=%s created=%s",
        len(existing_modules),
        len(new_modules),
    )

    projected_row_numbers = [row.row_number for row in projected_rows]
    projected_enrollment_id_by_row_number = {
        int(row_number): int(enrollment_id)
        for row_number, enrollment_id in db.query(
            ImportRow.row_number,
            ImportEnrollment.id,
        )
        .join(ImportEnrollment, ImportEnrollment.import_row_id == ImportRow.id)
        .filter(
            ImportRow.import_run_id == int(import_run.id),
            ImportEnrollment.import_run_id == int(import_run.id),
            ImportRow.row_number.in_(projected_row_numbers),
        )
        .all()
    }

    context_rows: dict[tuple[int, str, int, int], list[StagedEnrollmentRow]] = defaultdict(list)
    for row in projected_rows:
        student_id = student_id_by_hash.get(row.student_hash) if row.student_hash else None
        if not student_id or not row.year.isdigit() or not row.stream:
            continue
        programme = existing_programmes[row.stream]
        context_rows[
            (
                int(student_id),
                row.academic_year,
                int(row.year),
                int(programme.id),
            )
        ].append(row)

    context_entities: dict[tuple[int, str, int, int], StudentProgrammeContext] = {}
    for key, context_group_rows in context_rows.items():
        student_id, academic_year, study_year, programme_id = key
        primary_path, confidence, ambiguity_flags = _infer_primary_path(context_group_rows)
        path_entity = existing_paths.get(
            (
                programme_id,
                study_year,
                _path_code(primary_path),
            )
        )
        context = StudentProgrammeContext(
            import_run_id=int(import_run.id),
            student_id=student_id,
            programme_id=programme_id,
            programme_path_id=int(path_entity.id) if path_entity else None,
            academic_year=academic_year,
            study_year=study_year,
            batch=context_group_rows[0].batch or None,
            inferred_primary_path_code=_path_code(primary_path) if primary_path else None,
            interpretation_confidence=confidence,
            ambiguity_flags_json=_json_list(ambiguity_flags),
        )
        db.add(context)
        context_entities[key] = context
    if context_entities:
        db.flush()
    logger.info(
        "Import materialization student_programme_contexts=%s",
        len(context_entities),
    )

    membership_mappings: list[dict] = []
    membership_rows_by_module: dict[int, list[tuple[int, str, int | None, int | None]]] = defaultdict(list)
    for row in projected_rows:
        student_id = student_id_by_hash.get(row.student_hash) if row.student_hash else None
        if not student_id or not row.year.isdigit() or not row.stream:
            continue
        programme = existing_programmes[row.stream]
        context_key = (
            int(student_id),
            row.academic_year,
            int(row.year),
            int(programme.id),
        )
        context = context_entities.get(context_key)
        module = existing_modules.get(
            (row.course_code, row.module_nominal_year, row.module_nominal_semester)
        )
        if not module:
            continue
        enrollment_id = projected_enrollment_id_by_row_number.get(row.row_number)
        membership_role, is_common_module = _membership_role(row)
        membership_mappings.append(
            {
                "import_run_id": int(import_run.id),
                "student_id": int(student_id),
                "student_programme_context_id": int(context.id) if context else None,
                "curriculum_module_id": int(module.id),
                "import_enrollment_id": int(enrollment_id) if enrollment_id else None,
                "membership_source": "import",
                "membership_role": membership_role,
                "is_common_module": is_common_module,
                "is_optional": False,
                "interpretation_confidence": _interpretation_confidence(row),
            }
        )
        membership_rows_by_module[int(module.id)].append(
            (
                int(student_id),
                row.academic_year,
                int(programme.id),
                int(context.programme_path_id) if context and context.programme_path_id else None,
            )
        )
    if membership_mappings:
        _bulk_insert_mappings(db, StudentModuleMembership, membership_mappings)
        db.flush()
    logger.info(
        "Import materialization student_module_memberships=%s",
        len(membership_mappings),
    )

    programme_by_id = {int(programme.id): programme for programme in existing_programmes.values()}
    path_by_id = {int(path.id): path for path in existing_paths.values()}
    study_year_by_student_and_year: dict[tuple[int, str], int] = {}
    for context in context_entities.values():
        study_year_by_student_and_year[(int(context.student_id), context.academic_year)] = int(
            context.study_year
        )

    pending_attendance_groups: dict[tuple[str, str], tuple[AttendanceGroup, list[int]]] = {}
    attendance_group_students: list[AttendanceGroupStudent] = []
    for module_id, member_rows in membership_rows_by_module.items():
        student_ids = sorted({student_id for student_id, *_ in member_rows})
        if not student_ids:
            continue
        academic_year = member_rows[0][1]
        signature = ",".join(str(student_id) for student_id in student_ids)
        signature_hash = hashlib.sha1(signature.encode("utf-8")).hexdigest()
        key = (academic_year, signature_hash)
        if key not in pending_attendance_groups:
            programme_counts = Counter(programme_id for _, _, programme_id, _ in member_rows if programme_id)
            path_counts = Counter(path_id for _, _, _, path_id in member_rows if path_id)
            dominant_programme_id = programme_counts.most_common(1)[0][0] if programme_counts else None
            dominant_path_id = path_counts.most_common(1)[0][0] if path_counts else None
            programme = programme_by_id.get(dominant_programme_id)
            path = path_by_id.get(dominant_path_id)
            study_year = next(
                (
                    study_year_by_student_and_year.get((student_id, academic_year))
                    for student_id in student_ids
                    if study_year_by_student_and_year.get((student_id, academic_year)) is not None
                ),
                None,
            )
            attendance_group = AttendanceGroup(
                import_run_id=int(import_run.id),
                academic_year=academic_year,
                study_year=study_year,
                programme_id=dominant_programme_id,
                programme_path_id=dominant_path_id,
                label=_group_label(
                    academic_year=academic_year,
                    study_year=study_year,
                    programme_code=programme.code if programme else None,
                    path_code=path.code if path else None,
                    student_count=len(student_ids),
                ),
                derivation_basis="module_membership_signature",
                membership_signature=signature_hash,
                interpretation_confidence="medium",
                student_count=len(student_ids),
            )
            pending_attendance_groups[key] = (attendance_group, student_ids)
    if pending_attendance_groups:
        db.add_all([attendance_group for attendance_group, _ in pending_attendance_groups.values()])
        db.flush()
        for attendance_group, student_ids in pending_attendance_groups.values():
            attendance_group_students.extend(
                [
                    AttendanceGroupStudent(
                        attendance_group_id=int(attendance_group.id),
                        student_id=student_id,
                    )
                    for student_id in student_ids
                ]
            )
    if attendance_group_students:
        db.add_all(attendance_group_students)

    logger.info(
        "Import materialization attendance_groups=%s attendance_group_students=%s",
        len(pending_attendance_groups),
        len(attendance_group_students),
    )
    db.flush()
    logger.info("Import materialization finished import_run_id=%s", int(import_run.id))
    return import_run
