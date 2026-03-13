from __future__ import annotations

import math
import re

from sqlalchemy.orm import Session, joinedload

from app.models.academic import (
    CurriculumModule,
    Programme,
    ProgrammePath,
    StudentModuleMembership,
    StudentProgrammeContext,
)
from app.models.imports import ImportRun
from app.models.imports import ImportStudent
from app.models.snapshot import SnapshotLecturer, SnapshotRoom, SnapshotSharedSession
from app.models.solver import AttendanceGroup, AttendanceGroupStudent
from app.services.enrollment_inference import (
    LAB_SPLIT_LIMIT_BY_TYPE,
    TARGET_WEEKLY_LECTURER_HOURS,
    _split_assignment_count,
    _synthetic_lab_type,
    _synthetic_lecture_duration,
)


COURSE_CODE_RE = re.compile(r"^(?P<prefix>[A-Z]+)\s+\d{5}$")

REALISTIC_SNAPSHOT_ROOMS = [
    {
        "client_key": "room_auditorium",
        "name": "Auditorium",
        "capacity": 2000,
        "room_type": "lecture",
        "lab_type": None,
        "location": "Faculty Central",
        "year_restriction": None,
        "notes": "Realistic seed room",
    },
    {
        "client_key": "room_a11201",
        "name": "A11 201",
        "capacity": 150,
        "room_type": "lecture",
        "lab_type": None,
        "location": "A11 Complex",
        "year_restriction": None,
        "notes": "Realistic seed room",
    },
    {
        "client_key": "room_a11301",
        "name": "A11 301",
        "capacity": 150,
        "room_type": "lecture",
        "lab_type": None,
        "location": "A11 Complex",
        "year_restriction": None,
        "notes": "Realistic seed room",
    },
    {
        "client_key": "room_a7201",
        "name": "A7 201",
        "capacity": 200,
        "room_type": "lecture",
        "lab_type": None,
        "location": "A7 Complex",
        "year_restriction": None,
        "notes": "Realistic seed room",
    },
    {
        "client_key": "room_a7301",
        "name": "A7 301",
        "capacity": 300,
        "room_type": "lecture",
        "lab_type": None,
        "location": "A7 Complex",
        "year_restriction": None,
        "notes": "Realistic seed room",
    },
    {
        "client_key": "room_a7406",
        "name": "A7 406",
        "capacity": 400,
        "room_type": "lecture",
        "lab_type": None,
        "location": "A7 Complex",
        "year_restriction": None,
        "notes": "Realistic seed room",
    },
    {
        "client_key": "room_b1212",
        "name": "B1 212",
        "capacity": 800,
        "room_type": "lecture",
        "lab_type": None,
        "location": "B1 Complex",
        "year_restriction": None,
        "notes": "Realistic seed room",
    },
    {
        "client_key": "room_a11207",
        "name": "A11 207",
        "capacity": 150,
        "room_type": "lecture",
        "lab_type": None,
        "location": "A11 Complex",
        "year_restriction": None,
        "notes": "Realistic seed room",
    },
    {
        "client_key": "room_a11307",
        "name": "A11 307",
        "capacity": 150,
        "room_type": "lecture",
        "lab_type": None,
        "location": "A11 Complex",
        "year_restriction": None,
        "notes": "Realistic seed room",
    },
    {
        "client_key": "room_a7303",
        "name": "A7 303",
        "capacity": 100,
        "room_type": "lecture",
        "lab_type": None,
        "location": "A7 Complex",
        "year_restriction": None,
        "notes": "Realistic seed room",
    },
    {
        "client_key": "room_b1343",
        "name": "B1 343",
        "capacity": 50,
        "room_type": "lecture",
        "lab_type": None,
        "location": "B1 Complex",
        "year_restriction": None,
        "notes": "Realistic seed room",
    },
    {
        "client_key": "room_a7203",
        "name": "A7 203",
        "capacity": 120,
        "room_type": "lecture",
        "lab_type": None,
        "location": "A7 Complex",
        "year_restriction": None,
        "notes": "Realistic seed room",
    },
    {
        "client_key": "room_a7205",
        "name": "A7 205",
        "capacity": 120,
        "room_type": "lecture",
        "lab_type": None,
        "location": "A7 Complex",
        "year_restriction": None,
        "notes": "Realistic seed room",
    },
    {
        "client_key": "room_a11205",
        "name": "A11 205",
        "capacity": 100,
        "room_type": "lecture",
        "lab_type": None,
        "location": "A11 Complex",
        "year_restriction": None,
        "notes": "Realistic seed room",
    },
    {
        "client_key": "room_b1214",
        "name": "B1 214",
        "capacity": 120,
        "room_type": "lecture",
        "lab_type": None,
        "location": "B1 Complex",
        "year_restriction": None,
        "notes": "Realistic seed room",
    },
    {
        "client_key": "room_chemistry_lab",
        "name": "Chemistry Lab",
        "capacity": 30,
        "room_type": "lab",
        "lab_type": "chemistry",
        "location": "Science Labs",
        "year_restriction": None,
        "notes": "Realistic seed room",
    },
    {
        "client_key": "room_chemistry_lab_2",
        "name": "Chemistry Lab 2",
        "capacity": 30,
        "room_type": "lab",
        "lab_type": "chemistry",
        "location": "Science Labs",
        "year_restriction": None,
        "notes": "Realistic seed room",
    },
    {
        "client_key": "room_chemistry_lab_3",
        "name": "Chemistry Lab 3",
        "capacity": 30,
        "room_type": "lab",
        "lab_type": "chemistry",
        "location": "Science Labs",
        "year_restriction": None,
        "notes": "Realistic seed room",
    },
    {
        "client_key": "room_physics_lab_1",
        "name": "Physics Lab 1",
        "capacity": 40,
        "room_type": "lab",
        "lab_type": "physics",
        "location": "Science Labs",
        "year_restriction": None,
        "notes": "Realistic seed room",
    },
    {
        "client_key": "room_physics_lab_2",
        "name": "Physics Lab 2",
        "capacity": 40,
        "room_type": "lab",
        "lab_type": "physics",
        "location": "Science Labs",
        "year_restriction": None,
        "notes": "Realistic seed room",
    },
    {
        "client_key": "room_physics_lab_3",
        "name": "Physics Lab 3",
        "capacity": 40,
        "room_type": "lab",
        "lab_type": "physics",
        "location": "Science Labs",
        "year_restriction": None,
        "notes": "Realistic seed room",
    },
    {
        "client_key": "room_electronics_lab",
        "name": "Electronics Lab",
        "capacity": 32,
        "room_type": "lab",
        "lab_type": "electronics",
        "location": "Engineering Wing",
        "year_restriction": None,
        "notes": "Realistic seed room",
    },
    {
        "client_key": "room_electronics_lab_2",
        "name": "Electronics Lab 2",
        "capacity": 32,
        "room_type": "lab",
        "lab_type": "electronics",
        "location": "Engineering Wing",
        "year_restriction": None,
        "notes": "Realistic seed room",
    },
    {
        "client_key": "room_electronics_lab_3",
        "name": "Electronics Lab 3",
        "capacity": 32,
        "room_type": "lab",
        "lab_type": "electronics",
        "location": "Engineering Wing",
        "year_restriction": None,
        "notes": "Realistic seed room",
    },
    {
        "client_key": "room_electronics_lab_4",
        "name": "Electronics Lab 4",
        "capacity": 32,
        "room_type": "lab",
        "lab_type": "electronics",
        "location": "Engineering Wing",
        "year_restriction": None,
        "notes": "Realistic seed room",
    },
    {
        "client_key": "room_electronics_lab_5",
        "name": "Electronics Lab 5",
        "capacity": 32,
        "room_type": "lab",
        "lab_type": "electronics",
        "location": "Engineering Wing",
        "year_restriction": None,
        "notes": "Realistic seed room",
    },
    {
        "client_key": "room_computer_lab_1",
        "name": "Computer Lab 1",
        "capacity": 40,
        "room_type": "lab",
        "lab_type": "computer",
        "location": "Computing Block",
        "year_restriction": None,
        "notes": "Realistic seed room",
    },
    {
        "client_key": "room_computer_lab_2",
        "name": "Computer Lab 2",
        "capacity": 40,
        "room_type": "lab",
        "lab_type": "computer",
        "location": "Computing Block",
        "year_restriction": None,
        "notes": "Realistic seed room",
    },
    {
        "client_key": "room_computer_lab_3",
        "name": "Computer Lab 3",
        "capacity": 40,
        "room_type": "lab",
        "lab_type": "computer",
        "location": "Computing Block",
        "year_restriction": None,
        "notes": "Realistic seed room",
    },
    {
        "client_key": "room_computer_lab_4",
        "name": "Computer Lab 4",
        "capacity": 40,
        "room_type": "lab",
        "lab_type": "computer",
        "location": "Computing Block",
        "year_restriction": None,
        "notes": "Realistic seed room",
    },
    {
        "client_key": "room_biology_lab",
        "name": "Biology Lab",
        "capacity": 30,
        "room_type": "lab",
        "lab_type": "biology",
        "location": "Science Labs",
        "year_restriction": None,
        "notes": "Realistic seed room",
    },
    {
        "client_key": "room_statistics_lab",
        "name": "Statistics Lab",
        "capacity": 30,
        "room_type": "lab",
        "lab_type": "statistics",
        "location": "A11 Complex",
        "year_restriction": None,
        "notes": "Realistic seed room",
    },
    {
        "client_key": "room_statistics_lab_2",
        "name": "Statistics Lab 2",
        "capacity": 30,
        "room_type": "lab",
        "lab_type": "statistics",
        "location": "A11 Complex",
        "year_restriction": None,
        "notes": "Realistic seed room",
    },
]


def _dedupe_ids(values: list[int]) -> list[int]:
    seen: set[int] = set()
    ordered: list[int] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            ordered.append(value)
    return ordered


def _require_import_run(db: Session, import_run_id: int) -> ImportRun:
    import_run = db.query(ImportRun).filter(ImportRun.id == import_run_id).first()
    if not import_run:
        raise ValueError(f"Import run not found: {import_run_id}")
    return import_run


def _require_snapshot_lecturer(
    db: Session, import_run_id: int, lecturer_id: int
) -> SnapshotLecturer:
    lecturer = (
        db.query(SnapshotLecturer)
        .filter(
            SnapshotLecturer.id == lecturer_id,
            SnapshotLecturer.import_run_id == import_run_id,
        )
        .first()
    )
    if not lecturer:
        raise ValueError(
            f"Snapshot lecturer not found for import run {import_run_id}: {lecturer_id}"
        )
    return lecturer


def _require_snapshot_room(
    db: Session, import_run_id: int, room_id: int
) -> SnapshotRoom:
    room = (
        db.query(SnapshotRoom)
        .filter(
            SnapshotRoom.id == room_id,
            SnapshotRoom.import_run_id == import_run_id,
        )
        .first()
    )
    if not room:
        raise ValueError(
            f"Snapshot room not found for import run {import_run_id}: {room_id}"
        )
    return room


def _require_snapshot_session(
    db: Session, import_run_id: int, shared_session_id: int
) -> SnapshotSharedSession:
    shared_session = (
        db.query(SnapshotSharedSession)
        .filter(
            SnapshotSharedSession.id == shared_session_id,
            SnapshotSharedSession.import_run_id == import_run_id,
        )
        .first()
    )
    if not shared_session:
        raise ValueError(
            f"Snapshot shared session not found for import run {import_run_id}: {shared_session_id}"
        )
    return shared_session


def _validate_same_run_modules(
    db: Session, import_run_id: int, curriculum_module_ids: list[int]
) -> list[CurriculumModule]:
    if not curriculum_module_ids:
        return []
    modules = (
        db.query(CurriculumModule)
        .join(
            StudentModuleMembership,
            StudentModuleMembership.curriculum_module_id == CurriculumModule.id,
        )
        .filter(
            CurriculumModule.id.in_(curriculum_module_ids),
            StudentModuleMembership.import_run_id == import_run_id,
        )
        .distinct()
        .all()
    )
    module_ids = {int(module.id) for module in modules}
    missing_ids = sorted(set(curriculum_module_ids) - module_ids)
    if missing_ids:
        raise ValueError(
            f"Curriculum modules are not available in import run {import_run_id}: {missing_ids}"
        )
    return modules


def _validate_same_run_attendance_groups(
    db: Session, import_run_id: int, attendance_group_ids: list[int]
) -> list[AttendanceGroup]:
    if not attendance_group_ids:
        return []
    attendance_groups = (
        db.query(AttendanceGroup)
        .filter(
            AttendanceGroup.id.in_(attendance_group_ids),
            AttendanceGroup.import_run_id == import_run_id,
        )
        .all()
    )
    found_ids = {int(group.id) for group in attendance_groups}
    missing_ids = sorted(set(attendance_group_ids) - found_ids)
    if missing_ids:
        raise ValueError(
            f"Attendance groups are not available in import run {import_run_id}: {missing_ids}"
        )
    return attendance_groups


def _serialize_snapshot_lecturer(lecturer: SnapshotLecturer) -> dict:
    return {
        "id": int(lecturer.id),
        "import_run_id": int(lecturer.import_run_id),
        "client_key": lecturer.client_key,
        "name": lecturer.name,
        "email": lecturer.email,
        "notes": lecturer.notes,
    }


def _serialize_snapshot_room(room: SnapshotRoom) -> dict:
    return {
        "id": int(room.id),
        "import_run_id": int(room.import_run_id),
        "client_key": room.client_key,
        "name": room.name,
        "capacity": room.capacity,
        "room_type": room.room_type,
        "lab_type": room.lab_type,
        "location": room.location,
        "year_restriction": room.year_restriction,
        "notes": room.notes,
    }


def _serialize_snapshot_shared_session(shared_session: SnapshotSharedSession) -> dict:
    return {
        "id": int(shared_session.id),
        "import_run_id": int(shared_session.import_run_id),
        "client_key": shared_session.client_key,
        "name": shared_session.name,
        "session_type": shared_session.session_type,
        "duration_minutes": shared_session.duration_minutes,
        "occurrences_per_week": shared_session.occurrences_per_week,
        "required_room_type": shared_session.required_room_type,
        "required_lab_type": shared_session.required_lab_type,
        "specific_room_id": shared_session.specific_room_id,
        "max_students_per_group": shared_session.max_students_per_group,
        "allow_parallel_rooms": shared_session.allow_parallel_rooms,
        "notes": shared_session.notes,
        "lecturer_ids": [int(lecturer.id) for lecturer in shared_session.lecturers],
        "curriculum_module_ids": [
            int(module.id) for module in shared_session.curriculum_modules
        ],
        "attendance_group_ids": [
            int(group.id) for group in shared_session.attendance_groups
        ],
    }


def _course_prefix(course_code: str, subject_name: str) -> str:
    match = COURSE_CODE_RE.match(course_code.strip())
    if match:
        return match.group("prefix")
    normalized = re.sub(r"[^A-Za-z0-9]+", " ", subject_name).strip()
    return (normalized.split(" ")[0].upper() if normalized else "GEN")[:8]


def list_snapshot_completion(db: Session, import_run_id: int) -> dict:
    _require_import_run(db, import_run_id)

    lecturers = (
        db.query(SnapshotLecturer)
        .filter(SnapshotLecturer.import_run_id == import_run_id)
        .order_by(SnapshotLecturer.name.asc())
        .all()
    )
    rooms = (
        db.query(SnapshotRoom)
        .filter(SnapshotRoom.import_run_id == import_run_id)
        .order_by(SnapshotRoom.name.asc())
        .all()
    )
    shared_sessions = (
        db.query(SnapshotSharedSession)
        .filter(SnapshotSharedSession.import_run_id == import_run_id)
        .order_by(SnapshotSharedSession.name.asc(), SnapshotSharedSession.id.asc())
        .all()
    )
    return {
        "import_run_id": import_run_id,
        "lecturers": [_serialize_snapshot_lecturer(lecturer) for lecturer in lecturers],
        "rooms": [_serialize_snapshot_room(room) for room in rooms],
        "shared_sessions": [
            _serialize_snapshot_shared_session(shared_session)
            for shared_session in shared_sessions
        ],
    }


def build_import_workspace(db: Session, import_run_id: int) -> dict:
    import_run = _require_import_run(db, import_run_id)
    snapshot_completion = list_snapshot_completion(db, import_run_id)

    programmes = (
        db.query(Programme)
        .join(StudentProgrammeContext, StudentProgrammeContext.programme_id == Programme.id)
        .filter(StudentProgrammeContext.import_run_id == import_run_id)
        .distinct()
        .order_by(Programme.code.asc(), Programme.id.asc())
        .all()
    )
    programme_paths = (
        db.query(ProgrammePath)
        .join(
            StudentProgrammeContext,
            StudentProgrammeContext.programme_path_id == ProgrammePath.id,
        )
        .filter(StudentProgrammeContext.import_run_id == import_run_id)
        .distinct()
        .order_by(
            ProgrammePath.programme_id.asc(),
            ProgrammePath.study_year.asc(),
            ProgrammePath.code.asc(),
        )
        .all()
    )
    curriculum_modules = (
        db.query(CurriculumModule)
        .join(
            StudentModuleMembership,
            StudentModuleMembership.curriculum_module_id == CurriculumModule.id,
        )
        .filter(StudentModuleMembership.import_run_id == import_run_id)
        .distinct()
        .order_by(
            CurriculumModule.nominal_year.asc(),
            CurriculumModule.code.asc(),
            CurriculumModule.id.asc(),
        )
        .all()
    )
    attendance_groups = (
        db.query(AttendanceGroup)
        .filter(AttendanceGroup.import_run_id == import_run_id)
        .order_by(
            AttendanceGroup.study_year.asc(),
            AttendanceGroup.label.asc(),
            AttendanceGroup.id.asc(),
        )
        .all()
    )
    attendance_group_by_signature = {
        (group.academic_year, group.membership_signature): int(group.id)
        for group in attendance_groups
    }
    module_membership_rows = (
        db.query(
            StudentModuleMembership.curriculum_module_id,
            StudentModuleMembership.student_id,
            StudentProgrammeContext.academic_year,
        )
        .outerjoin(
            StudentProgrammeContext,
            StudentProgrammeContext.id == StudentModuleMembership.student_programme_context_id,
        )
        .filter(StudentModuleMembership.import_run_id == import_run_id)
        .order_by(
            StudentModuleMembership.curriculum_module_id.asc(),
            StudentModuleMembership.student_id.asc(),
        )
        .all()
    )
    module_student_ids: dict[tuple[int, str], set[int]] = {}
    for curriculum_module_id, student_id, academic_year in module_membership_rows:
        if curriculum_module_id is None or student_id is None or not academic_year:
            continue
        key = (int(curriculum_module_id), academic_year)
        existing = module_student_ids.get(key)
        if existing is None:
            existing = set()
            module_student_ids[key] = existing
        existing.add(int(student_id))

    module_attendance_group_ids: dict[int, list[int]] = {}
    for (curriculum_module_id, academic_year), student_ids in module_student_ids.items():
        signature = ",".join(str(student_id) for student_id in sorted(student_ids))
        attendance_group_id = attendance_group_by_signature.get((academic_year, signature))
        if attendance_group_id is None:
            continue
        module_attendance_group_ids.setdefault(curriculum_module_id, []).append(attendance_group_id)

    return {
        "import_run_id": int(import_run.id),
        "selected_academic_year": import_run.selected_academic_year,
        "programmes": [
            {
                "id": int(programme.id),
                "code": programme.code,
                "name": programme.name,
                "duration_years": programme.duration_years,
                "intake_label": programme.intake_label,
            }
            for programme in programmes
        ],
        "programme_paths": [
            {
                "id": int(path.id),
                "programme_id": int(path.programme_id),
                "study_year": path.study_year,
                "code": path.code,
                "name": path.name,
                "is_common": path.is_common,
            }
            for path in programme_paths
        ],
        "curriculum_modules": [
            {
                "id": int(module.id),
                "code": module.code,
                "name": module.name,
                "subject_name": module.subject_name,
                "nominal_year": module.nominal_year,
                "semester_bucket": module.semester_bucket,
                "is_full_year": module.is_full_year,
                "attendance_group_ids": sorted(
                    module_attendance_group_ids.get(int(module.id), [])
                ),
            }
            for module in curriculum_modules
        ],
        "attendance_groups": [
            {
                "id": int(group.id),
                "programme_id": int(group.programme_id) if group.programme_id else None,
                "programme_path_id": int(group.programme_path_id)
                if group.programme_path_id
                else None,
                "academic_year": group.academic_year,
                "study_year": group.study_year,
                "label": group.label,
                "student_count": group.student_count,
            }
            for group in attendance_groups
        ],
        "lecturers": snapshot_completion["lecturers"],
        "rooms": snapshot_completion["rooms"],
        "shared_sessions": snapshot_completion["shared_sessions"],
    }


def _unique_legacy_module_code(
    used_codes: set[str],
    *,
    base_code: str,
    nominal_year: int | None,
    semester_bucket: int | None,
    module_id: int,
) -> str:
    candidate = base_code or f"MODULE-{module_id}"
    if candidate not in used_codes:
        used_codes.add(candidate)
        return candidate

    suffix = f"-Y{nominal_year or 0}S{semester_bucket or 0}"
    candidate_with_suffix = f"{candidate}{suffix}"
    if candidate_with_suffix not in used_codes:
        used_codes.add(candidate_with_suffix)
        return candidate_with_suffix

    deduped = f"{candidate_with_suffix}-{module_id}"
    used_codes.add(deduped)
    return deduped


def build_legacy_dataset_from_import_run(db: Session, import_run_id: int) -> dict:
    _require_import_run(db, import_run_id)

    programmes = (
        db.query(Programme)
        .join(StudentProgrammeContext, StudentProgrammeContext.programme_id == Programme.id)
        .filter(StudentProgrammeContext.import_run_id == import_run_id)
        .distinct()
        .order_by(Programme.code.asc(), Programme.id.asc())
        .all()
    )
    programme_paths = (
        db.query(ProgrammePath)
        .join(
            StudentProgrammeContext,
            StudentProgrammeContext.programme_path_id == ProgrammePath.id,
        )
        .filter(StudentProgrammeContext.import_run_id == import_run_id)
        .distinct()
        .order_by(
            ProgrammePath.programme_id.asc(),
            ProgrammePath.study_year.asc(),
            ProgrammePath.code.asc(),
        )
        .all()
    )
    lecturers = (
        db.query(SnapshotLecturer)
        .filter(SnapshotLecturer.import_run_id == import_run_id)
        .order_by(SnapshotLecturer.name.asc(), SnapshotLecturer.id.asc())
        .all()
    )
    rooms = (
        db.query(SnapshotRoom)
        .filter(SnapshotRoom.import_run_id == import_run_id)
        .order_by(SnapshotRoom.name.asc(), SnapshotRoom.id.asc())
        .all()
    )
    attendance_groups = (
        db.query(AttendanceGroup)
        .filter(AttendanceGroup.import_run_id == import_run_id)
        .order_by(AttendanceGroup.label.asc(), AttendanceGroup.id.asc())
        .all()
    )
    student_hashes_by_group_id: dict[int, list[str]] = {}
    if attendance_groups:
        group_ids = [int(group.id) for group in attendance_groups]
        student_rows = (
            db.query(
                AttendanceGroupStudent.attendance_group_id,
                AttendanceGroupStudent.student_id,
                ImportStudent.student_hash,
            )
            .join(ImportStudent, ImportStudent.id == AttendanceGroupStudent.student_id)
            .filter(AttendanceGroupStudent.attendance_group_id.in_(group_ids))
            .order_by(
                AttendanceGroupStudent.attendance_group_id.asc(),
                AttendanceGroupStudent.student_id.asc(),
            )
            .all()
        )
        for attendance_group_id, _student_id, student_hash in student_rows:
            if not student_hash:
                continue
            student_hashes_by_group_id.setdefault(int(attendance_group_id), []).append(
                student_hash
            )
    curriculum_modules = (
        db.query(CurriculumModule)
        .join(
            StudentModuleMembership,
            StudentModuleMembership.curriculum_module_id == CurriculumModule.id,
        )
        .filter(StudentModuleMembership.import_run_id == import_run_id)
        .distinct()
        .order_by(
            CurriculumModule.nominal_year.asc(),
            CurriculumModule.semester_bucket.asc(),
            CurriculumModule.code.asc(),
            CurriculumModule.id.asc(),
        )
        .all()
    )
    shared_sessions = (
        db.query(SnapshotSharedSession)
        .options(
            joinedload(SnapshotSharedSession.lecturers),
            joinedload(SnapshotSharedSession.curriculum_modules),
            joinedload(SnapshotSharedSession.attendance_groups),
            joinedload(SnapshotSharedSession.specific_room),
        )
        .filter(SnapshotSharedSession.import_run_id == import_run_id)
        .order_by(SnapshotSharedSession.name.asc(), SnapshotSharedSession.id.asc())
        .all()
    )

    used_module_codes: set[str] = set()
    legacy_module_code_by_id: dict[int, str] = {}
    for module in curriculum_modules:
        legacy_module_code_by_id[int(module.id)] = _unique_legacy_module_code(
            used_codes=used_module_codes,
            base_code=module.code,
            nominal_year=module.nominal_year,
            semester_bucket=module.semester_bucket,
            module_id=int(module.id),
        )

    return {
        "degrees": [
            {
                "client_key": f"import_degree_{int(programme.id)}",
                "code": programme.code,
                "name": programme.name,
                "duration_years": int(programme.duration_years or 3),
                "intake_label": programme.intake_label or f"{programme.code} Intake",
            }
            for programme in programmes
        ],
        "paths": [
            {
                "client_key": f"import_path_{int(path.id)}",
                "degree_client_key": f"import_degree_{int(path.programme_id)}",
                "year": int(path.study_year),
                "code": path.code,
                "name": path.name,
            }
            for path in programme_paths
        ],
        "lecturers": [
            {
                "client_key": f"import_lecturer_{int(lecturer.id)}",
                "name": lecturer.name,
                "email": lecturer.email,
            }
            for lecturer in lecturers
        ],
        "rooms": [
            {
                "client_key": f"import_room_{int(room.id)}",
                "name": room.name,
                "capacity": int(room.capacity),
                "room_type": room.room_type,
                "lab_type": room.lab_type,
                "location": room.location,
                "year_restriction": room.year_restriction,
            }
            for room in rooms
        ],
        "student_groups": [
            {
                "client_key": f"import_group_{int(group.id)}",
                "degree_client_key": f"import_degree_{int(group.programme_id)}"
                if group.programme_id
                else None,
                "path_client_key": f"import_path_{int(group.programme_path_id)}"
                if group.programme_path_id
                else None,
                "year": int(group.study_year or 1),
                "name": group.label,
                "size": int(group.student_count),
                "student_hashes": student_hashes_by_group_id.get(int(group.id), []),
            }
            for group in attendance_groups
            if group.programme_id
        ],
        "modules": [
            {
                "client_key": f"import_module_{int(module.id)}",
                "code": legacy_module_code_by_id[int(module.id)],
                "name": module.name,
                "subject_name": module.subject_name,
                "year": int(module.nominal_year or 1),
                "semester": int(module.semester_bucket or 1),
                "is_full_year": bool(module.is_full_year),
            }
            for module in curriculum_modules
        ],
        "sessions": [
            {
                "client_key": f"import_session_{int(shared_session.id)}",
                "module_client_key": (
                    f"import_module_{int(sorted(shared_session.curriculum_modules, key=lambda item: int(item.id))[0].id)}"
                    if shared_session.curriculum_modules
                    else None
                ),
                "linked_module_client_keys": [
                    f"import_module_{int(module.id)}"
                    for module in sorted(
                        shared_session.curriculum_modules, key=lambda item: int(item.id)
                    )[1:]
                ],
                "name": shared_session.name,
                "session_type": shared_session.session_type,
                "duration_minutes": int(shared_session.duration_minutes),
                "occurrences_per_week": int(shared_session.occurrences_per_week),
                "required_room_type": shared_session.required_room_type,
                "required_lab_type": shared_session.required_lab_type,
                "specific_room_client_key": (
                    f"import_room_{int(shared_session.specific_room_id)}"
                    if shared_session.specific_room_id
                    else None
                ),
                "max_students_per_group": shared_session.max_students_per_group,
                "allow_parallel_rooms": bool(shared_session.allow_parallel_rooms),
                "notes": shared_session.notes,
                "lecturer_client_keys": [
                    f"import_lecturer_{int(lecturer.id)}"
                    for lecturer in sorted(
                        shared_session.lecturers, key=lambda item: int(item.id)
                    )
                ],
                "student_group_client_keys": [
                    f"import_group_{int(group.id)}"
                    for group in sorted(
                        shared_session.attendance_groups, key=lambda item: int(item.id)
                    )
                    if group.programme_id
                ],
            }
            for shared_session in shared_sessions
            if shared_session.curriculum_modules
        ],
    }


def create_snapshot_lecturer(
    db: Session,
    *,
    import_run_id: int,
    client_key: str | None,
    name: str,
    email: str | None,
    notes: str | None,
) -> dict:
    _require_import_run(db, import_run_id)
    lecturer = SnapshotLecturer(
        import_run_id=import_run_id,
        client_key=client_key,
        name=name,
        email=email,
        notes=notes,
    )
    db.add(lecturer)
    db.flush()
    return _serialize_snapshot_lecturer(lecturer)


def create_snapshot_lecturers_batch(
    db: Session,
    *,
    import_run_id: int,
    lecturers: list[dict],
) -> list[dict]:
    if not lecturers:
        _require_import_run(db, import_run_id)
        return []
    return [
        create_snapshot_lecturer(
            db,
            import_run_id=import_run_id,
            client_key=lecturer.get("client_key"),
            name=lecturer["name"],
            email=lecturer.get("email"),
            notes=lecturer.get("notes"),
        )
        for lecturer in lecturers
    ]


def update_snapshot_lecturer(
    db: Session,
    *,
    import_run_id: int,
    lecturer_id: int,
    client_key: str | None,
    name: str,
    email: str | None,
    notes: str | None,
) -> dict:
    lecturer = _require_snapshot_lecturer(db, import_run_id, lecturer_id)
    lecturer.client_key = client_key
    lecturer.name = name
    lecturer.email = email
    lecturer.notes = notes
    db.flush()
    return _serialize_snapshot_lecturer(lecturer)


def create_snapshot_room(
    db: Session,
    *,
    import_run_id: int,
    client_key: str | None,
    name: str,
    capacity: int,
    room_type: str,
    lab_type: str | None,
    location: str,
    year_restriction: int | None,
    notes: str | None,
) -> dict:
    _require_import_run(db, import_run_id)
    room = SnapshotRoom(
        import_run_id=import_run_id,
        client_key=client_key,
        name=name,
        capacity=capacity,
        room_type=room_type,
        lab_type=lab_type,
        location=location,
        year_restriction=year_restriction,
        notes=notes,
    )
    db.add(room)
    db.flush()
    return _serialize_snapshot_room(room)


def create_snapshot_rooms_batch(
    db: Session,
    *,
    import_run_id: int,
    rooms: list[dict],
) -> list[dict]:
    if not rooms:
        _require_import_run(db, import_run_id)
        return []
    return [
        create_snapshot_room(
            db,
            import_run_id=import_run_id,
            client_key=room.get("client_key"),
            name=room["name"],
            capacity=room["capacity"],
            room_type=room["room_type"],
            lab_type=room.get("lab_type"),
            location=room["location"],
            year_restriction=room.get("year_restriction"),
            notes=room.get("notes"),
        )
        for room in rooms
    ]


def update_snapshot_room(
    db: Session,
    *,
    import_run_id: int,
    room_id: int,
    client_key: str | None,
    name: str,
    capacity: int,
    room_type: str,
    lab_type: str | None,
    location: str,
    year_restriction: int | None,
    notes: str | None,
) -> dict:
    room = _require_snapshot_room(db, import_run_id, room_id)
    room.client_key = client_key
    room.name = name
    room.capacity = capacity
    room.room_type = room_type
    room.lab_type = lab_type
    room.location = location
    room.year_restriction = year_restriction
    room.notes = notes
    db.flush()
    return _serialize_snapshot_room(room)


def create_snapshot_shared_session(
    db: Session,
    *,
    import_run_id: int,
    client_key: str | None,
    name: str,
    session_type: str,
    duration_minutes: int,
    occurrences_per_week: int,
    required_room_type: str | None,
    required_lab_type: str | None,
    specific_room_id: int | None,
    max_students_per_group: int | None,
    allow_parallel_rooms: bool,
    notes: str | None,
    lecturer_ids: list[int],
    curriculum_module_ids: list[int],
    attendance_group_ids: list[int],
) -> dict:
    _require_import_run(db, import_run_id)
    specific_room = (
        _require_snapshot_room(db, import_run_id, specific_room_id)
        if specific_room_id is not None
        else None
    )
    lecturer_ids = _dedupe_ids(lecturer_ids)
    curriculum_module_ids = _dedupe_ids(curriculum_module_ids)
    attendance_group_ids = _dedupe_ids(attendance_group_ids)
    lecturers = [
        _require_snapshot_lecturer(db, import_run_id, lecturer_id)
        for lecturer_id in lecturer_ids
    ]
    curriculum_modules = _validate_same_run_modules(
        db, import_run_id, curriculum_module_ids
    )
    attendance_groups = _validate_same_run_attendance_groups(
        db, import_run_id, attendance_group_ids
    )

    shared_session = SnapshotSharedSession(
        import_run_id=import_run_id,
        client_key=client_key,
        name=name,
        session_type=session_type,
        duration_minutes=duration_minutes,
        occurrences_per_week=occurrences_per_week,
        required_room_type=required_room_type,
        required_lab_type=required_lab_type,
        specific_room_id=int(specific_room.id) if specific_room else None,
        max_students_per_group=max_students_per_group,
        allow_parallel_rooms=allow_parallel_rooms,
        notes=notes,
    )
    shared_session.lecturers = lecturers
    shared_session.curriculum_modules = curriculum_modules
    shared_session.attendance_groups = attendance_groups
    db.add(shared_session)
    db.flush()
    return _serialize_snapshot_shared_session(shared_session)


def create_snapshot_shared_sessions_batch(
    db: Session,
    *,
    import_run_id: int,
    shared_sessions: list[dict],
) -> list[dict]:
    if not shared_sessions:
        _require_import_run(db, import_run_id)
        return []
    return [
        create_snapshot_shared_session(
            db,
            import_run_id=import_run_id,
            client_key=shared_session.get("client_key"),
            name=shared_session["name"],
            session_type=shared_session["session_type"],
            duration_minutes=shared_session["duration_minutes"],
            occurrences_per_week=shared_session["occurrences_per_week"],
            required_room_type=shared_session.get("required_room_type"),
            required_lab_type=shared_session.get("required_lab_type"),
            specific_room_id=shared_session.get("specific_room_id"),
            max_students_per_group=shared_session.get("max_students_per_group"),
            allow_parallel_rooms=shared_session.get("allow_parallel_rooms", False),
            notes=shared_session.get("notes"),
            lecturer_ids=shared_session.get("lecturer_ids", []),
            curriculum_module_ids=shared_session.get("curriculum_module_ids", []),
            attendance_group_ids=shared_session.get("attendance_group_ids", []),
        )
        for shared_session in shared_sessions
    ]


def update_snapshot_shared_session(
    db: Session,
    *,
    import_run_id: int,
    shared_session_id: int,
    client_key: str | None,
    name: str,
    session_type: str,
    duration_minutes: int,
    occurrences_per_week: int,
    required_room_type: str | None,
    required_lab_type: str | None,
    specific_room_id: int | None,
    max_students_per_group: int | None,
    allow_parallel_rooms: bool,
    notes: str | None,
    lecturer_ids: list[int],
    curriculum_module_ids: list[int],
    attendance_group_ids: list[int],
) -> dict:
    shared_session = _require_snapshot_session(db, import_run_id, shared_session_id)
    specific_room = (
        _require_snapshot_room(db, import_run_id, specific_room_id)
        if specific_room_id is not None
        else None
    )
    lecturer_ids = _dedupe_ids(lecturer_ids)
    curriculum_module_ids = _dedupe_ids(curriculum_module_ids)
    attendance_group_ids = _dedupe_ids(attendance_group_ids)
    lecturers = [
        _require_snapshot_lecturer(db, import_run_id, lecturer_id)
        for lecturer_id in lecturer_ids
    ]
    curriculum_modules = _validate_same_run_modules(
        db, import_run_id, curriculum_module_ids
    )
    attendance_groups = _validate_same_run_attendance_groups(
        db, import_run_id, attendance_group_ids
    )

    shared_session.client_key = client_key
    shared_session.name = name
    shared_session.session_type = session_type
    shared_session.duration_minutes = duration_minutes
    shared_session.occurrences_per_week = occurrences_per_week
    shared_session.required_room_type = required_room_type
    shared_session.required_lab_type = required_lab_type
    shared_session.specific_room_id = int(specific_room.id) if specific_room else None
    shared_session.max_students_per_group = max_students_per_group
    shared_session.allow_parallel_rooms = allow_parallel_rooms
    shared_session.notes = notes
    shared_session.lecturers = lecturers
    shared_session.curriculum_modules = curriculum_modules
    shared_session.attendance_groups = attendance_groups
    db.flush()
    return _serialize_snapshot_shared_session(shared_session)


def delete_snapshot_lecturer(db: Session, *, import_run_id: int, lecturer_id: int) -> None:
    lecturer = _require_snapshot_lecturer(db, import_run_id, lecturer_id)
    db.delete(lecturer)
    db.flush()


def delete_snapshot_room(db: Session, *, import_run_id: int, room_id: int) -> None:
    room = _require_snapshot_room(db, import_run_id, room_id)
    db.delete(room)
    db.flush()


def delete_snapshot_shared_session(
    db: Session, *, import_run_id: int, shared_session_id: int
) -> None:
    shared_session = _require_snapshot_session(db, import_run_id, shared_session_id)
    db.delete(shared_session)
    db.flush()


def seed_realistic_snapshot_missing_data(db: Session, *, import_run_id: int) -> dict:
    workspace = build_import_workspace(db, import_run_id)

    attendance_group_by_id = {
        int(group["id"]): group for group in workspace["attendance_groups"]
    }
    modules = workspace["curriculum_modules"]
    existing_lecturer_names = {
        lecturer["name"].strip().lower()
        for lecturer in workspace["lecturers"]
        if lecturer.get("name")
    }
    existing_room_names = {
        room["name"].strip().lower() for room in workspace["rooms"] if room.get("name")
    }

    existing_session_module_ids: set[int] = set()
    for shared_session in workspace["shared_sessions"]:
        existing_session_module_ids.update(shared_session["curriculum_module_ids"])

    rooms_to_create = [
        room
        for room in REALISTIC_SNAPSHOT_ROOMS
        if room["name"].strip().lower() not in existing_room_names
    ]
    created_rooms = create_snapshot_rooms_batch(
        db, import_run_id=import_run_id, rooms=rooms_to_create
    )

    module_meta_all: list[dict] = []
    semester_weight_by_bucket: dict[int, int] = {}
    for module in modules:
        attendance_group_ids = [int(value) for value in module["attendance_group_ids"]]
        audience_sizes = [
            int(attendance_group_by_id[group_id]["student_count"])
            for group_id in attendance_group_ids
            if group_id in attendance_group_by_id
        ]
        audience_size = sum(audience_sizes)
        semester_bucket = int(module["semester_bucket"] or 1)
        semester_weight_by_bucket[semester_bucket] = (
            semester_weight_by_bucket.get(semester_bucket, 0) + max(1, audience_size)
        )
        module_meta_all.append(
            {
                "id": int(module["id"]),
                "code": module["code"],
                "name": module["name"],
                "nominal_year": int(module["nominal_year"] or 1),
                "semester_bucket": semester_bucket,
                "is_full_year": bool(module.get("is_full_year")),
                "attendance_group_ids": attendance_group_ids,
                "audience_size": audience_size,
                "audience_sizes": audience_sizes,
            }
        )

    selected_semester_bucket = None
    if semester_weight_by_bucket:
        selected_semester_bucket = max(
            semester_weight_by_bucket.items(),
            key=lambda item: (item[1], -item[0]),
        )[0]

    module_meta: list[dict] = []
    prefix_minutes: dict[str, int] = {}
    prefix_module_count: dict[str, int] = {}
    for module in module_meta_all:
        if (
            selected_semester_bucket is not None
            and not module["is_full_year"]
            and module["semester_bucket"] != selected_semester_bucket
        ):
            continue
        prefix = _course_prefix(module["code"], module["name"])
        lecture_duration = _synthetic_lecture_duration(module["code"], module["audience_size"])
        lab_type = _synthetic_lab_type(
            prefix,
            module["code"],
            module["nominal_year"],
            module["audience_size"],
        )
        total_minutes = lecture_duration
        if lab_type:
            total_minutes += 180 * _split_assignment_count(
                module["audience_sizes"],
                LAB_SPLIT_LIMIT_BY_TYPE[lab_type],
            )
        module["prefix"] = prefix
        module["lecture_duration"] = lecture_duration
        module["lab_type"] = lab_type
        module["total_minutes"] = total_minutes
        prefix_minutes[prefix] = prefix_minutes.get(prefix, 0) + total_minutes
        prefix_module_count[prefix] = prefix_module_count.get(prefix, 0) + 1
        module_meta.append(module)

    lecturer_target_minutes = TARGET_WEEKLY_LECTURER_HOURS * 60
    lecturers_to_create: list[dict] = []
    for prefix in sorted(prefix_minutes):
        lecturer_count = max(
            1,
            min(
                6,
                math.ceil(prefix_minutes[prefix] / lecturer_target_minutes),
            ),
        )
        if prefix_module_count[prefix] >= 8:
            lecturer_count = max(lecturer_count, 2)
        for index in range(lecturer_count):
            name = f"{prefix} Lecturer {index + 1}"
            if name.strip().lower() in existing_lecturer_names:
                continue
            existing_lecturer_names.add(name.strip().lower())
            lecturers_to_create.append(
                {
                    "client_key": f"seed_lecturer_{prefix.lower()}_{index + 1}",
                    "name": name,
                    "email": f"{prefix.lower()}.{index + 1}@science.kln.ac.lk",
                    "notes": "Realistic seed lecturer",
                }
            )

    created_lecturers = create_snapshot_lecturers_batch(
        db, import_run_id=import_run_id, lecturers=lecturers_to_create
    )

    snapshot_lecturers = (
        db.query(SnapshotLecturer)
        .filter(SnapshotLecturer.import_run_id == import_run_id)
        .order_by(SnapshotLecturer.name.asc(), SnapshotLecturer.id.asc())
        .all()
    )
    lecturer_ids_by_prefix: dict[str, list[int]] = {}
    for lecturer in snapshot_lecturers:
        name = lecturer.name or ""
        prefix = name.split(" Lecturer ")[0].strip().upper()
        lecturer_ids_by_prefix.setdefault(prefix, []).append(int(lecturer.id))

    lecturer_minutes_by_id = {int(lecturer.id): 0 for lecturer in snapshot_lecturers}
    shared_sessions_to_create: list[dict] = []
    for module in sorted(module_meta, key=lambda item: item["code"]):
        if module["id"] in existing_session_module_ids:
            continue
        prefix_lecturer_ids = lecturer_ids_by_prefix.get(module["prefix"], [])
        assigned_lecturer_ids: list[int] = []
        if prefix_lecturer_ids:
            assigned_lecturer_id = min(
                prefix_lecturer_ids,
                key=lambda lecturer_id: (
                    lecturer_minutes_by_id.get(lecturer_id, 0),
                    lecturer_id,
                ),
            )
            lecturer_minutes_by_id[assigned_lecturer_id] = (
                lecturer_minutes_by_id.get(assigned_lecturer_id, 0)
                + module["total_minutes"]
            )
            assigned_lecturer_ids = [assigned_lecturer_id]

        shared_sessions_to_create.append(
            {
                "client_key": f"seed_session_{module['code'].lower().replace(' ', '_')}_lecture",
                "name": f"{module['code']} Lecture",
                "session_type": "lecture",
                "duration_minutes": module["lecture_duration"],
                "occurrences_per_week": 1,
                "required_room_type": "lecture",
                "required_lab_type": None,
                "specific_room_id": None,
                "max_students_per_group": None,
                "allow_parallel_rooms": False,
                "notes": "Realistic seed session adapted from the legacy demo builder.",
                "lecturer_ids": assigned_lecturer_ids,
                "curriculum_module_ids": [module["id"]],
                "attendance_group_ids": module["attendance_group_ids"],
            }
        )
        if module["lab_type"]:
            shared_sessions_to_create.append(
                {
                    "client_key": f"seed_session_{module['code'].lower().replace(' ', '_')}_lab",
                    "name": f"{module['code']} Lab",
                    "session_type": "lab",
                    "duration_minutes": 180,
                    "occurrences_per_week": 1,
                    "required_room_type": "lab",
                    "required_lab_type": module["lab_type"],
                    "specific_room_id": None,
                    "max_students_per_group": LAB_SPLIT_LIMIT_BY_TYPE[module["lab_type"]],
                    "allow_parallel_rooms": False,
                    "notes": "Realistic seed lab session adapted from the legacy demo builder.",
                    "lecturer_ids": assigned_lecturer_ids,
                    "curriculum_module_ids": [module["id"]],
                    "attendance_group_ids": module["attendance_group_ids"],
                }
            )

    created_shared_sessions = create_snapshot_shared_sessions_batch(
        db,
        import_run_id=import_run_id,
        shared_sessions=shared_sessions_to_create,
    )

    return {
        "import_run_id": import_run_id,
        "lecturers_created": len(created_lecturers),
        "rooms_created": len(created_rooms),
        "shared_sessions_created": len(created_shared_sessions),
    }
