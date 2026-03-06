from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.timetable_entry import TimetableEntry
from app.models.timeslot import Timeslot
from app.models.room import Room
from app.schemas.timetable_generate import (
    TimetableGenerateResponse,
    TimetablePreviewResponse,
    TimetableSaveRequest,
    TimetableSaveResponse,
)
from app.services.timetable_solver import solve_timetable, _expand_sessions

router = APIRouter(prefix="/api/timetable", tags=["timetable"])


@router.post("/generate", response_model=TimetableGenerateResponse)
def generate_timetable(db: Session = Depends(get_db)):
    import sys
    print("DEBUG: generate endpoint called", flush=True)
    try:
        status, results, diagnostics = solve_timetable(db)
        print(f"DEBUG: status={status}, results={len(results)}", flush=True)
        sessions = _expand_sessions(db)
    except Exception as exc:
        print(f"Generate failed: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))
    if status == "infeasible":
        return TimetableGenerateResponse(
            status="infeasible",
            total_scheduled_sessions=0,
            unscheduled_sessions=len(sessions),
            version="",
            diagnostics=diagnostics,
        )

    version = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    ordered_timeslots = db.query(Timeslot).order_by(Timeslot.id).all()
    rooms = db.query(Room).order_by(Room.id).all()

    for (s_idx, r_idx, t_idx, group_number) in results:
        db.add(
            TimetableEntry(
                version=version,
                session_id=sessions[s_idx].session_id,
                room_id=rooms[r_idx].id,
                timeslot_id=ordered_timeslots[t_idx].id,
                group_number=group_number,
                duration_hours=sessions[s_idx].duration_hours,
                is_manual=False,
            )
        )
    db.commit()

    scheduled_session_ids = set(s[0] for s in results)
    total = len(scheduled_session_ids)
    unscheduled = len(sessions) - total
    return TimetableGenerateResponse(
        status=status,
        total_scheduled_sessions=total,
        unscheduled_sessions=unscheduled,
        version=version,
        diagnostics=diagnostics,
    )


@router.post("/preview", response_model=TimetablePreviewResponse)
def preview_timetable(db: Session = Depends(get_db)):
    print("DEBUG: preview endpoint called", flush=True)
    try:
        status, results, diagnostics = solve_timetable(db)
        print(f"DEBUG: preview status={status}, results={len(results)}", flush=True)
        sessions = _expand_sessions(db)
    except Exception as exc:
        print(f"Preview failed: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))
    
    if status == "infeasible":
        return TimetablePreviewResponse(
            status="infeasible",
            total_scheduled_sessions=0,
            unscheduled_sessions=len(sessions),
            results=[],
            diagnostics=diagnostics,
        )

    scheduled_session_ids = set(s[0] for s in results)
    total = len(scheduled_session_ids)
    unscheduled = len(sessions) - total
    
    return TimetablePreviewResponse(
        status=status,
        total_scheduled_sessions=total,
        unscheduled_sessions=unscheduled,
        results=[list(r) for r in results],
        diagnostics=diagnostics,
    )


@router.post("/save", response_model=TimetableSaveResponse)
def save_timetable(payload: TimetableSaveRequest, db: Session = Depends(get_db)):
    print("DEBUG: save endpoint called", flush=True)
    results = payload.results
    
    if not results:
        raise HTTPException(status_code=400, detail="No results to save")
    
    sessions = _expand_sessions(db)
    ordered_timeslots = db.query(Timeslot).order_by(Timeslot.id).all()
    rooms = db.query(Room).order_by(Room.id).all()
    version = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    
    saved_count = 0
    for (s_idx, r_idx, t_idx, group_number) in results:
        if s_idx < len(sessions) and r_idx < len(rooms) and t_idx < len(ordered_timeslots):
            db.add(
                TimetableEntry(
                    version=version,
                    session_id=sessions[s_idx].session_id,
                    room_id=rooms[r_idx].id,
                    timeslot_id=ordered_timeslots[t_idx].id,
                    group_number=group_number,
                    duration_hours=sessions[s_idx].duration_hours,
                    is_manual=True,
                )
            )
            saved_count += 1
    
    db.commit()
    
    return TimetableSaveResponse(
        status="saved",
        version=version,
        total_scheduled_sessions=saved_count,
        message=f"Successfully saved {saved_count} sessions",
    )


@router.get("/latest-version")
def get_latest_version(db: Session = Depends(get_db)):
    latest_entry = (
        db.query(TimetableEntry)
        .order_by(TimetableEntry.id.desc())
        .first()
    )
    if latest_entry:
        return {"version": latest_entry.version}
    return {"version": None}
