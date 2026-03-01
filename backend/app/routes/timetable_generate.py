from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.timetable_entry import TimetableEntry
from app.models.timeslot import Timeslot
from app.models.room import Room
from app.schemas.timetable_generate import TimetableGenerateResponse
from app.services.timetable_solver import solve_timetable, _expand_sessions

router = APIRouter(prefix="/api/timetable", tags=["timetable"])


@router.post("/generate", response_model=TimetableGenerateResponse)
def generate_timetable(db: Session = Depends(get_db)):
    try:
        status, results, diagnostics = solve_timetable(db)
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
                is_manual=False,
            )
        )
    db.commit()

    total = len(results)
    unscheduled = max(len(sessions) - total, 0)
    return TimetableGenerateResponse(
        status=status,
        total_scheduled_sessions=total,
        unscheduled_sessions=unscheduled,
        version=version,
        diagnostics=diagnostics,
    )
