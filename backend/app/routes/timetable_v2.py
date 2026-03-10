from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
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
    LookupResponse,
    ViewResponse,
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
