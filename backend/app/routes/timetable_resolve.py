from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.timetable_entry import TimetableEntry
from app.schemas.timetable_generate import TimetableGenerateResponse
from app.services.timetable_solver import solve_timetable

router = APIRouter(prefix="/api/timetable", tags=["timetable"])


class ResolveEntry(BaseModel):
    session_id: int = Field(..., gt=0)
    room_id: int = Field(..., gt=0)
    timeslot_id: int = Field(..., gt=0)
    group_number: int = Field(default=1, ge=1)


class ResolveRequest(BaseModel):
    entries: list[ResolveEntry]


@router.post("/resolve", response_model=TimetableGenerateResponse)
def resolve_around_manual(payload: ResolveRequest, db: Session = Depends(get_db)):
    fixed_entries = [
        (entry.session_id, entry.room_id, entry.timeslot_id, entry.group_number)
        for entry in payload.entries
    ]
    status, results, diagnostics = solve_timetable(db, fixed_entries=fixed_entries)
    
    # Persist the resolved entries
    from datetime import datetime
    from app.models.timeslot import Timeslot
    from app.models.room import Room
    from app.services.timetable_solver import _expand_sessions
    
    sessions = _expand_sessions(db)
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
    
    if status == "infeasible":
        return TimetableGenerateResponse(
            status="infeasible",
            total_scheduled_sessions=0,
            unscheduled_sessions=0,
            version="",
            diagnostics=diagnostics,
        )

    return TimetableGenerateResponse(
        status=status,
        total_scheduled_sessions=len(results),
        unscheduled_sessions=0,
        version=version,
        diagnostics=diagnostics,
    )
