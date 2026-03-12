from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.v2 import (
    DatasetResponse,
    DatasetSummary,
    DatasetUpsertRequest,
    DefaultSelectionRequest,
    ExportResponse,
    FullDatasetResponse,
    GenerationRequest,
    GenerationResponse,
    ImportAnalysisResponse,
    ImportProjectionRequest,
    ImportProjectionResponse,
    ImportWorkspaceResponse,
    LookupResponse,
    MaterializedImportResponse,
    SnapshotCompletionResponse,
    SnapshotLecturerInput,
    SnapshotLecturerResponse,
    SnapshotRoomInput,
    SnapshotRoomResponse,
    SnapshotSharedSessionInput,
    SnapshotSharedSessionResponse,
    ViewResponse,
)
from app.services.csv_import_analysis import (
    analyze_enrollment_csv,
    build_reviewed_import_projection,
    parse_review_rules,
)
from app.services.import_materialization import (
    materialize_import_run,
    summarize_import_run,
)
from app.services.snapshot_completion import (
    build_legacy_dataset_from_import_run,
    build_import_workspace,
    create_snapshot_lecturer,
    create_snapshot_room,
    create_snapshot_shared_session,
    delete_snapshot_lecturer,
    delete_snapshot_room,
    delete_snapshot_shared_session,
    list_snapshot_completion,
    update_snapshot_lecturer,
    update_snapshot_room,
    update_snapshot_shared_session,
)
from app.services.timetable_v2 import (
    build_demo_dataset,
    build_view_payload,
    dataset_summary,
    export_view,
    generate_timetables,
    get_latest_run,
    lookup_options,
    read_dataset,
    replace_dataset,
    serialize_generation_run,
    set_default_solution,
)

router = APIRouter(prefix="/api/v2", tags=["timetable-v2"])


@router.get("/dataset", response_model=DatasetResponse)
def get_dataset_summary(db: Session = Depends(get_db)):
    return {"summary": DatasetSummary(**dataset_summary(db))}


@router.get("/dataset/full", response_model=FullDatasetResponse)
def get_full_dataset(db: Session = Depends(get_db)):
    return FullDatasetResponse(**read_dataset(db))


@router.post("/dataset", response_model=DatasetResponse)
def upsert_dataset(payload: DatasetUpsertRequest, db: Session = Depends(get_db)):
    summary = replace_dataset(db, payload)
    return {"summary": DatasetSummary(**summary)}


@router.post("/dataset/demo", response_model=DatasetResponse)
def load_demo_dataset(
    profile: str = Query(default="realistic", pattern="^(realistic|tuned)$"),
    db: Session = Depends(get_db),
):
    summary = replace_dataset(db, DatasetUpsertRequest(**build_demo_dataset(profile)))
    return {"summary": DatasetSummary(**summary)}


@router.get("/lookups", response_model=LookupResponse)
def get_lookups(db: Session = Depends(get_db)):
    return lookup_options(db)


@router.get("/imports/enrollment-analysis", response_model=ImportAnalysisResponse)
def get_enrollment_import_analysis():
    try:
        return analyze_enrollment_csv()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/imports/enrollment-projection", response_model=ImportProjectionResponse)
def build_enrollment_projection(payload: ImportProjectionRequest):
    try:
        return build_reviewed_import_projection(
            rules=parse_review_rules([rule.model_dump() for rule in payload.rules]),
            target_academic_year=payload.target_academic_year,
            allowed_attempts=tuple(payload.allowed_attempts),
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/imports/enrollment-load", response_model=DatasetResponse)
def load_enrollment_projection(
    payload: ImportProjectionRequest,
    db: Session = Depends(get_db),
):
    try:
        projection = build_reviewed_import_projection(
            rules=parse_review_rules([rule.model_dump() for rule in payload.rules]),
            target_academic_year=payload.target_academic_year,
            allowed_attempts=tuple(payload.allowed_attempts),
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    summary = replace_dataset(db, DatasetUpsertRequest(**projection["dataset"]))
    return {"summary": DatasetSummary(**summary)}


@router.post("/imports/enrollment-materialize", response_model=MaterializedImportResponse)
def materialize_enrollment_import(
    payload: ImportProjectionRequest,
    db: Session = Depends(get_db),
):
    try:
        import_run = materialize_import_run(
            db,
            source_file="students_processed_TT_J.csv",
            review_rules=parse_review_rules([rule.model_dump() for rule in payload.rules]),
            target_academic_year=payload.target_academic_year,
            allowed_attempts=tuple(payload.allowed_attempts),
        )
        db.commit()
        return summarize_import_run(db, int(import_run.id))
    except FileNotFoundError as exc:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get(
    "/imports/{import_run_id}/snapshot",
    response_model=SnapshotCompletionResponse,
)
def get_import_snapshot_completion(import_run_id: int, db: Session = Depends(get_db)):
    try:
        return list_snapshot_completion(db, import_run_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get(
    "/imports/{import_run_id}/workspace",
    response_model=ImportWorkspaceResponse,
)
def get_import_workspace(import_run_id: int, db: Session = Depends(get_db)):
    try:
        return build_import_workspace(db, import_run_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post(
    "/imports/{import_run_id}/publish-legacy",
    response_model=DatasetResponse,
)
def publish_import_workspace_to_legacy_dataset(
    import_run_id: int,
    db: Session = Depends(get_db),
):
    try:
        dataset = build_legacy_dataset_from_import_run(db, import_run_id)
        summary = replace_dataset(db, DatasetUpsertRequest(**dataset))
        return {"summary": DatasetSummary(**summary)}
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post(
    "/imports/{import_run_id}/snapshot/lecturers",
    response_model=SnapshotLecturerResponse,
)
def create_import_snapshot_lecturer(
    import_run_id: int,
    payload: SnapshotLecturerInput,
    db: Session = Depends(get_db),
):
    try:
        lecturer = create_snapshot_lecturer(
            db,
            import_run_id=import_run_id,
            client_key=payload.client_key,
            name=payload.name,
            email=payload.email,
            notes=payload.notes,
        )
        db.commit()
        return lecturer
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail="Snapshot lecturer already exists") from exc


@router.put(
    "/imports/{import_run_id}/snapshot/lecturers/{lecturer_id}",
    response_model=SnapshotLecturerResponse,
)
def update_import_snapshot_lecturer(
    import_run_id: int,
    lecturer_id: int,
    payload: SnapshotLecturerInput,
    db: Session = Depends(get_db),
):
    try:
        lecturer = update_snapshot_lecturer(
            db,
            import_run_id=import_run_id,
            lecturer_id=lecturer_id,
            client_key=payload.client_key,
            name=payload.name,
            email=payload.email,
            notes=payload.notes,
        )
        db.commit()
        return lecturer
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail="Snapshot lecturer already exists") from exc


@router.delete("/imports/{import_run_id}/snapshot/lecturers/{lecturer_id}", status_code=204)
def delete_import_snapshot_lecturer(
    import_run_id: int,
    lecturer_id: int,
    db: Session = Depends(get_db),
):
    try:
        delete_snapshot_lecturer(db, import_run_id=import_run_id, lecturer_id=lecturer_id)
        db.commit()
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post(
    "/imports/{import_run_id}/snapshot/rooms",
    response_model=SnapshotRoomResponse,
)
def create_import_snapshot_room(
    import_run_id: int,
    payload: SnapshotRoomInput,
    db: Session = Depends(get_db),
):
    try:
        room = create_snapshot_room(
            db,
            import_run_id=import_run_id,
            client_key=payload.client_key,
            name=payload.name,
            capacity=payload.capacity,
            room_type=payload.room_type,
            lab_type=payload.lab_type,
            location=payload.location,
            year_restriction=payload.year_restriction,
            notes=payload.notes,
        )
        db.commit()
        return room
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail="Snapshot room already exists") from exc


@router.put(
    "/imports/{import_run_id}/snapshot/rooms/{room_id}",
    response_model=SnapshotRoomResponse,
)
def update_import_snapshot_room(
    import_run_id: int,
    room_id: int,
    payload: SnapshotRoomInput,
    db: Session = Depends(get_db),
):
    try:
        room = update_snapshot_room(
            db,
            import_run_id=import_run_id,
            room_id=room_id,
            client_key=payload.client_key,
            name=payload.name,
            capacity=payload.capacity,
            room_type=payload.room_type,
            lab_type=payload.lab_type,
            location=payload.location,
            year_restriction=payload.year_restriction,
            notes=payload.notes,
        )
        db.commit()
        return room
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail="Snapshot room already exists") from exc


@router.delete("/imports/{import_run_id}/snapshot/rooms/{room_id}", status_code=204)
def delete_import_snapshot_room(
    import_run_id: int,
    room_id: int,
    db: Session = Depends(get_db),
):
    try:
        delete_snapshot_room(db, import_run_id=import_run_id, room_id=room_id)
        db.commit()
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post(
    "/imports/{import_run_id}/snapshot/shared-sessions",
    response_model=SnapshotSharedSessionResponse,
)
def create_import_snapshot_shared_session(
    import_run_id: int,
    payload: SnapshotSharedSessionInput,
    db: Session = Depends(get_db),
):
    try:
        shared_session = create_snapshot_shared_session(
            db,
            import_run_id=import_run_id,
            client_key=payload.client_key,
            name=payload.name,
            session_type=payload.session_type,
            duration_minutes=payload.duration_minutes,
            occurrences_per_week=payload.occurrences_per_week,
            required_room_type=payload.required_room_type,
            required_lab_type=payload.required_lab_type,
            specific_room_id=payload.specific_room_id,
            max_students_per_group=payload.max_students_per_group,
            allow_parallel_rooms=payload.allow_parallel_rooms,
            notes=payload.notes,
            lecturer_ids=payload.lecturer_ids,
            curriculum_module_ids=payload.curriculum_module_ids,
            attendance_group_ids=payload.attendance_group_ids,
        )
        db.commit()
        return shared_session
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=400, detail="Snapshot shared session already exists"
        ) from exc


@router.put(
    "/imports/{import_run_id}/snapshot/shared-sessions/{shared_session_id}",
    response_model=SnapshotSharedSessionResponse,
)
def update_import_snapshot_shared_session(
    import_run_id: int,
    shared_session_id: int,
    payload: SnapshotSharedSessionInput,
    db: Session = Depends(get_db),
):
    try:
        shared_session = update_snapshot_shared_session(
            db,
            import_run_id=import_run_id,
            shared_session_id=shared_session_id,
            client_key=payload.client_key,
            name=payload.name,
            session_type=payload.session_type,
            duration_minutes=payload.duration_minutes,
            occurrences_per_week=payload.occurrences_per_week,
            required_room_type=payload.required_room_type,
            required_lab_type=payload.required_lab_type,
            specific_room_id=payload.specific_room_id,
            max_students_per_group=payload.max_students_per_group,
            allow_parallel_rooms=payload.allow_parallel_rooms,
            notes=payload.notes,
            lecturer_ids=payload.lecturer_ids,
            curriculum_module_ids=payload.curriculum_module_ids,
            attendance_group_ids=payload.attendance_group_ids,
        )
        db.commit()
        return shared_session
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=400, detail="Snapshot shared session already exists"
        ) from exc


@router.delete(
    "/imports/{import_run_id}/snapshot/shared-sessions/{shared_session_id}",
    status_code=204,
)
def delete_import_snapshot_shared_session(
    import_run_id: int,
    shared_session_id: int,
    db: Session = Depends(get_db),
):
    try:
        delete_snapshot_shared_session(
            db,
            import_run_id=import_run_id,
            shared_session_id=shared_session_id,
        )
        db.commit()
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/generate", response_model=GenerationResponse)
def generate(payload: GenerationRequest, db: Session = Depends(get_db)):
    run = generate_timetables(
        db,
        selected_soft_constraints=payload.soft_constraints,
        performance_preset=payload.performance_preset,
        max_solutions=payload.max_solutions,
        preview_limit=payload.preview_limit,
        time_limit_seconds=payload.time_limit_seconds,
    )
    return serialize_generation_run(run)


@router.get("/generate/latest", response_model=GenerationResponse)
def latest_generation(db: Session = Depends(get_db)):
    run = get_latest_run(db)
    if not run:
        raise HTTPException(status_code=404, detail="No generation run found")
    return serialize_generation_run(run)


@router.post("/solutions/default", response_model=GenerationResponse)
def set_default(payload: DefaultSelectionRequest, db: Session = Depends(get_db)):
    try:
        set_default_solution(db, payload.solution_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    run = get_latest_run(db)
    if not run:
        raise HTTPException(status_code=404, detail="No generation run found")
    return serialize_generation_run(run)


@router.get("/views", response_model=ViewResponse)
def view_timetable(
    mode: str = Query(default="admin"),
    lecturer_id: int | None = Query(default=None),
    student_group_id: int | None = Query(default=None),
    degree_id: int | None = Query(default=None),
    path_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
):
    try:
        return build_view_payload(
            db,
            mode=mode,
            lecturer_id=lecturer_id,
            student_group_id=student_group_id,
            degree_id=degree_id,
            path_id=path_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/exports", response_model=ExportResponse)
def export_timetable(
    mode: str = Query(default="admin"),
    export_format: str = Query(default="csv"),
    lecturer_id: int | None = Query(default=None),
    student_group_id: int | None = Query(default=None),
    degree_id: int | None = Query(default=None),
    path_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
):
    try:
        view_payload = build_view_payload(
            db,
            mode=mode,
            lecturer_id=lecturer_id,
            student_group_id=student_group_id,
            degree_id=degree_id,
            path_id=path_id,
        )
        return export_view(view_payload, export_format)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
