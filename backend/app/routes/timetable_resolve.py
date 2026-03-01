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
    status, results = solve_timetable(db, fixed_entries=fixed_entries)
    if status == "infeasible":
        return TimetableGenerateResponse(
            status="infeasible",
            total_scheduled_sessions=0,
            unscheduled_sessions=0,
            version="",
        )

    return TimetableGenerateResponse(
        status=status,
        total_scheduled_sessions=len(results),
        unscheduled_sessions=0,
        version="",
    )
