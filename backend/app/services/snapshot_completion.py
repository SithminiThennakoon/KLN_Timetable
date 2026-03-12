from __future__ import annotations

from sqlalchemy.orm import Session, joinedload

from app.models.academic import (
    CurriculumModule,
    Programme,
    ProgrammePath,
    StudentModuleMembership,
    StudentProgrammeContext,
)
from app.models.imports import ImportRun
from app.models.snapshot import SnapshotLecturer, SnapshotRoom, SnapshotSharedSession
from app.models.solver import AttendanceGroup, AttendanceGroupStudent


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
        .options(
            joinedload(AttendanceGroup.students).joinedload(AttendanceGroupStudent.student)
        )
        .filter(AttendanceGroup.import_run_id == import_run_id)
        .order_by(AttendanceGroup.label.asc(), AttendanceGroup.id.asc())
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
                "student_hashes": [
                    group_student.student.student_hash
                    for group_student in sorted(
                        group.students, key=lambda item: int(item.student_id)
                    )
                    if group_student.student and group_student.student.student_hash
                ],
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
