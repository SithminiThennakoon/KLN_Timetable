from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.room import Room
from app.models.session import Session as SessionModel
from app.models.timeslot import Timeslot
from app.models.timetable_entry import TimetableEntry
from app.services.timetable_solver import _expand_sessions

router = APIRouter(prefix="/api/timetable", tags=["timetable"])


class ManualEntry(BaseModel):
    session_id: int = Field(..., gt=0)
    room_id: int = Field(..., gt=0)
    timeslot_id: int = Field(..., gt=0)
    group_number: int = Field(default=1, ge=1)


class ValidateRequest(BaseModel):
    entries: list[ManualEntry]


@router.post("/validate")
def validate_entries(payload: ValidateRequest, db: Session = Depends(get_db)):
    rooms = {room.id: room for room in db.query(Room).all()}
    timeslots = {ts.id: ts for ts in db.query(Timeslot).all()}
    sessions = _expand_sessions(db)
    session_lookup = {(s.session_id, s.group_number): s for s in sessions}

    conflicts = []

    for entry in payload.entries:
        key = (entry.session_id, entry.group_number)
        session = session_lookup.get(key)
        room = rooms.get(entry.room_id)
        timeslot = timeslots.get(entry.timeslot_id)
        if session is None:
            conflicts.append({"entry": entry.model_dump(), "reason": "Session not found"})
            continue
        if room is None:
            conflicts.append({"entry": entry.model_dump(), "reason": "Room not found"})
            continue
        if timeslot is None:
            conflicts.append({"entry": entry.model_dump(), "reason": "Timeslot not found"})
            continue
        if timeslot.is_lunch:
            conflicts.append({"entry": entry.model_dump(), "reason": "Lunch slot not allowed"})
        if room.capacity < session.group_size:
            conflicts.append({"entry": entry.model_dump(), "reason": "Room capacity too small"})
        if session.session_type == "lecture" and room.room_type != "lecture_hall":
            conflicts.append({"entry": entry.model_dump(), "reason": "Room type must be lecture hall"})
        if session.session_type == "practical" and room.room_type != "laboratory":
            conflicts.append({"entry": entry.model_dump(), "reason": "Room type must be laboratory"})
        if session.requires_lab_type and room.lab_type != session.requires_lab_type:
            conflicts.append({"entry": entry.model_dump(), "reason": "Lab type mismatch"})
        if room.year_restriction and room.year_restriction != session.year:
            conflicts.append({"entry": entry.model_dump(), "reason": "Room year restriction mismatch"})

    return {"valid": len(conflicts) == 0, "conflicts": conflicts}
