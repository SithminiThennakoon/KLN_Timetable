from __future__ import annotations

import json
import logging
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
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
    SnapshotSeedResponse,
    SnapshotCompletionResponse,
    SnapshotLecturerBatchInput,
    SnapshotLecturerBatchResponse,
    SnapshotLecturerInput,
    SnapshotLecturerResponse,
    SnapshotRoomBatchInput,
    SnapshotRoomBatchResponse,
    SnapshotRoomInput,
    SnapshotRoomResponse,
    SnapshotSharedSessionBatchInput,
    SnapshotSharedSessionBatchResponse,
    SnapshotSharedSessionInput,
    SnapshotSharedSessionResponse,
    ViewResponse,
)
from app.services.csv_import_analysis import (
    analyze_enrollment_csv,
    build_reviewed_import_projection,
    parse_review_rules,
)
from app.services.enrollment_inference import DEFAULT_ENROLLMENT_CSV
from app.services.import_materialization import (
    materialize_import_run,
    summarize_import_run,
)
from app.services.snapshot_completion import (
    build_legacy_dataset_from_import_run,
    build_import_workspace,
    create_snapshot_lecturers_batch,
    create_snapshot_lecturer,
    create_snapshot_rooms_batch,
    create_snapshot_room,
    create_snapshot_shared_sessions_batch,
    create_snapshot_shared_session,
    delete_snapshot_lecturer,
    delete_snapshot_room,
    delete_snapshot_shared_session,
    list_snapshot_completion,
    seed_realistic_snapshot_missing_data,
    update_snapshot_lecturer,
    update_snapshot_room,
    update_snapshot_shared_session,
)
from app.services.timetable_v2 import (
    build_demo_dataset,
    build_snapshot_verification_payload,
    build_view_payload,
    dataset_summary,
    export_view,
    generate_snapshot_timetables,
    generate_timetables,
    get_latest_run,
    get_latest_snapshot_run,
    lookup_options,
    read_dataset,
    replace_dataset,
    serialize_generation_run,
    serialize_snapshot_generation_run,
    set_default_solution,
    set_default_snapshot_solution,
)
from app.services.verification import (
    run_snapshot_python_verification,
    run_snapshot_verification_suite,
)

router = APIRouter(prefix="/api/v2", tags=["timetable-v2"])
logger = logging.getLogger("uvicorn.error")


def _parse_import_form_payload(
    *,
    rules_json: str | None,
    target_academic_year: str | None,
    allowed_attempts_json: str | None,
) -> ImportProjectionRequest:
    try:
        rules_payload = json.loads(rules_json) if rules_json else []
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="Invalid rules_json payload.") from exc

    try:
        attempts_payload = (
            json.loads(allowed_attempts_json)
            if allowed_attempts_json
            else ["1"]
        )
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="Invalid allowed_attempts_json payload.") from exc

    return ImportProjectionRequest(
        rules=rules_payload,
        target_academic_year=target_academic_year or None,
        allowed_attempts=attempts_payload,
    )


async def _write_upload_to_temp_file(upload: UploadFile) -> Path:
    suffix = Path(upload.filename or "enrollment.csv").suffix or ".csv"
    handle = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    try:
        content = await upload.read()
        handle.write(content)
    finally:
        handle.close()
    return Path(handle.name)


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
def get_lookups(
    import_run_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
):
    return lookup_options(db, import_run_id=import_run_id)


@router.get("/imports/enrollment-analysis", response_model=ImportAnalysisResponse)
def get_enrollment_import_analysis():
    try:
        return analyze_enrollment_csv()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/imports/enrollment-analysis-upload", response_model=ImportAnalysisResponse)
async def get_enrollment_import_analysis_from_upload(
    file: UploadFile | None = File(default=None),
):
    logger.info(
        "Enrollment analysis requested file_present=%s file_name=%s",
        bool(file),
        file.filename if file else None,
    )
    if file is None:
        try:
            response = analyze_enrollment_csv()
            logger.info(
                "Enrollment analysis completed source=%s buckets=%s",
                response.get("source_file"),
                len(response.get("buckets", [])),
            )
            return response
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    temp_path = await _write_upload_to_temp_file(file)
    try:
        response = analyze_enrollment_csv(str(temp_path))
        response["source_file"] = file.filename or "uploaded.csv"
        logger.info(
            "Enrollment analysis completed source=%s buckets=%s",
            response.get("source_file"),
            len(response.get("buckets", [])),
        )
        return response
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        temp_path.unlink(missing_ok=True)


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


@router.post("/imports/enrollment-projection-upload", response_model=ImportProjectionResponse)
async def build_enrollment_projection_from_upload(
    file: UploadFile | None = File(default=None),
    rules_json: str | None = Form(default=None),
    target_academic_year: str | None = Form(default=None),
    allowed_attempts_json: str | None = Form(default=None),
):
    payload = _parse_import_form_payload(
        rules_json=rules_json,
        target_academic_year=target_academic_year,
        allowed_attempts_json=allowed_attempts_json,
    )
    logger.info(
        "Enrollment projection requested file_present=%s file_name=%s rules=%s target_year=%s allowed_attempts=%s",
        bool(file),
        file.filename if file else None,
        len(payload.rules),
        payload.target_academic_year,
        payload.allowed_attempts,
    )
    if file is None:
        try:
            response = build_reviewed_import_projection(
                rules=parse_review_rules([rule.model_dump() for rule in payload.rules]),
                target_academic_year=payload.target_academic_year,
                allowed_attempts=tuple(payload.allowed_attempts),
            )
            logger.info(
                "Enrollment projection completed source=%s summary=%s",
                response.get("analysis", {}).get("source_file"),
                response.get("projection_summary"),
            )
            return response
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    temp_path = await _write_upload_to_temp_file(file)
    try:
        response = build_reviewed_import_projection(
            path=str(temp_path),
            rules=parse_review_rules([rule.model_dump() for rule in payload.rules]),
            target_academic_year=payload.target_academic_year,
            allowed_attempts=tuple(payload.allowed_attempts),
        )
        response["analysis"]["source_file"] = file.filename or "uploaded.csv"
        logger.info(
            "Enrollment projection completed source=%s summary=%s",
            response.get("analysis", {}).get("source_file"),
            response.get("projection_summary"),
        )
        return response
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        temp_path.unlink(missing_ok=True)


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


@router.post("/imports/enrollment-materialize-upload", response_model=MaterializedImportResponse)
async def materialize_enrollment_import_from_upload(
    db: Session = Depends(get_db),
    file: UploadFile | None = File(default=None),
    rules_json: str | None = Form(default=None),
    target_academic_year: str | None = Form(default=None),
    allowed_attempts_json: str | None = Form(default=None),
):
    payload = _parse_import_form_payload(
        rules_json=rules_json,
        target_academic_year=target_academic_year,
        allowed_attempts_json=allowed_attempts_json,
    )
    logger.info(
        "Enrollment materialize requested file_present=%s file_name=%s rules=%s target_year=%s allowed_attempts=%s",
        bool(file),
        file.filename if file else None,
        len(payload.rules),
        payload.target_academic_year,
        payload.allowed_attempts,
    )
    if file is None:
        try:
            import_run = materialize_import_run(
                db,
                source_file=str(DEFAULT_ENROLLMENT_CSV),
                review_rules=parse_review_rules([rule.model_dump() for rule in payload.rules]),
                target_academic_year=payload.target_academic_year,
                allowed_attempts=tuple(payload.allowed_attempts),
                notes="Bundled sample CSV materialized via upload-compatible route.",
            )
            db.commit()
            response = summarize_import_run(db, int(import_run.id))
            logger.info(
                "Enrollment materialize completed import_run_id=%s counts=%s",
                response.get("import_run_id"),
                response.get("counts"),
            )
            return response
        except FileNotFoundError as exc:
            db.rollback()
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            db.rollback()
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    temp_path = await _write_upload_to_temp_file(file)
    try:
        import_run = materialize_import_run(
            db,
            source_file=str(temp_path),
            review_rules=parse_review_rules([rule.model_dump() for rule in payload.rules]),
            target_academic_year=payload.target_academic_year,
            allowed_attempts=tuple(payload.allowed_attempts),
            notes=f"Uploaded source file: {file.filename or 'uploaded.csv'}",
        )
        import_run.source_file = file.filename or "uploaded.csv"
        db.commit()
        response = summarize_import_run(db, int(import_run.id))
        logger.info(
            "Enrollment materialize completed import_run_id=%s counts=%s",
            response.get("import_run_id"),
            response.get("counts"),
        )
        return response
    except FileNotFoundError as exc:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        temp_path.unlink(missing_ok=True)


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
    "/imports/{import_run_id}/snapshot/seed-realistic-missing-data",
    response_model=SnapshotSeedResponse,
)
def seed_import_snapshot_realistic_missing_data(
    import_run_id: int,
    db: Session = Depends(get_db),
):
    try:
        summary = seed_realistic_snapshot_missing_data(db, import_run_id=import_run_id)
        db.commit()
        return summary
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=400, detail="Snapshot seed conflicted with existing records"
        ) from exc


@router.post(
    "/imports/{import_run_id}/snapshot/lecturers/batch",
    response_model=SnapshotLecturerBatchResponse,
)
def create_import_snapshot_lecturers_batch(
    import_run_id: int,
    payload: SnapshotLecturerBatchInput,
    db: Session = Depends(get_db),
):
    try:
        lecturers = create_snapshot_lecturers_batch(
            db,
            import_run_id=import_run_id,
            lecturers=[item.model_dump() for item in payload.lecturers],
        )
        db.commit()
        return {"lecturers": lecturers}
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=400, detail="One or more snapshot lecturers already exist"
        ) from exc


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
    "/imports/{import_run_id}/snapshot/rooms/batch",
    response_model=SnapshotRoomBatchResponse,
)
def create_import_snapshot_rooms_batch(
    import_run_id: int,
    payload: SnapshotRoomBatchInput,
    db: Session = Depends(get_db),
):
    try:
        rooms = create_snapshot_rooms_batch(
            db,
            import_run_id=import_run_id,
            rooms=[item.model_dump() for item in payload.rooms],
        )
        db.commit()
        return {"rooms": rooms}
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=400, detail="One or more snapshot rooms already exist"
        ) from exc


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
    "/imports/{import_run_id}/snapshot/shared-sessions/batch",
    response_model=SnapshotSharedSessionBatchResponse,
)
def create_import_snapshot_shared_sessions_batch(
    import_run_id: int,
    payload: SnapshotSharedSessionBatchInput,
    db: Session = Depends(get_db),
):
    try:
        shared_sessions = create_snapshot_shared_sessions_batch(
            db,
            import_run_id=import_run_id,
            shared_sessions=[item.model_dump() for item in payload.shared_sessions],
        )
        db.commit()
        return {"shared_sessions": shared_sessions}
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=400, detail="One or more snapshot shared sessions already exist"
        ) from exc


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
    if payload.import_run_id:
        run = generate_snapshot_timetables(
            db,
            import_run_id=payload.import_run_id,
            selected_soft_constraints=payload.soft_constraints,
            performance_preset=payload.performance_preset,
            max_solutions=payload.max_solutions,
            preview_limit=payload.preview_limit,
            time_limit_seconds=payload.time_limit_seconds,
        )
        return serialize_snapshot_generation_run(run)
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
def latest_generation(
    import_run_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
):
    if import_run_id:
        run = get_latest_snapshot_run(db, import_run_id)
        if not run:
            raise HTTPException(status_code=404, detail="No generation run found")
        return serialize_snapshot_generation_run(run)
    run = get_latest_run(db)
    if not run:
        raise HTTPException(status_code=404, detail="No generation run found")
    return serialize_generation_run(run)


@router.post("/solutions/default", response_model=GenerationResponse)
def set_default(payload: DefaultSelectionRequest, db: Session = Depends(get_db)):
    if payload.import_run_id:
        try:
            set_default_snapshot_solution(
                db,
                import_run_id=payload.import_run_id,
                solution_id=payload.solution_id,
            )
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        run = get_latest_snapshot_run(db, payload.import_run_id)
        if not run:
            raise HTTPException(status_code=404, detail="No generation run found")
        return serialize_snapshot_generation_run(run)
    try:
        set_default_solution(db, payload.solution_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    run = get_latest_run(db)
    if not run:
        raise HTTPException(status_code=404, detail="No generation run found")
    return serialize_generation_run(run)


@router.get("/imports/{import_run_id}/verification-snapshot", response_model=dict)
def get_snapshot_verification_snapshot(
    import_run_id: int,
    db: Session = Depends(get_db),
):
    try:
        return build_snapshot_verification_payload(db, import_run_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/imports/{import_run_id}/verification/python", response_model=dict)
def run_python_snapshot_verification_route(
    import_run_id: int,
    db: Session = Depends(get_db),
):
    try:
        return run_snapshot_python_verification(db, import_run_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/imports/{import_run_id}/verification", response_model=dict)
def run_snapshot_verification_suite_route(
    import_run_id: int,
    db: Session = Depends(get_db),
):
    try:
        return run_snapshot_verification_suite(db, import_run_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/views", response_model=ViewResponse)
def view_timetable(
    mode: str = Query(default="admin"),
    import_run_id: int | None = Query(default=None),
    lecturer_id: int | None = Query(default=None),
    student_group_id: int | None = Query(default=None),
    degree_id: int | None = Query(default=None),
    path_id: int | None = Query(default=None),
    study_year: int | None = Query(default=None),
    db: Session = Depends(get_db),
):
    try:
        return build_view_payload(
            db,
            mode=mode,
            import_run_id=import_run_id,
            lecturer_id=lecturer_id,
            student_group_id=student_group_id,
            degree_id=degree_id,
            path_id=path_id,
            study_year=study_year,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/exports", response_model=ExportResponse)
def export_timetable(
    mode: str = Query(default="admin"),
    export_format: str = Query(default="csv"),
    import_run_id: int | None = Query(default=None),
    lecturer_id: int | None = Query(default=None),
    student_group_id: int | None = Query(default=None),
    degree_id: int | None = Query(default=None),
    path_id: int | None = Query(default=None),
    study_year: int | None = Query(default=None),
    db: Session = Depends(get_db),
):
    try:
        view_payload = build_view_payload(
            db,
            mode=mode,
            import_run_id=import_run_id,
            lecturer_id=lecturer_id,
            student_group_id=student_group_id,
            degree_id=degree_id,
            path_id=path_id,
            study_year=study_year,
        )
        return export_view(view_payload, export_format)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
