from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.timetable_entry import TimetableEntry
from app.schemas.expanded_session import ExpandedSessionRead
from app.services.timetable_solver import _expand_sessions

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


@router.get("/unscheduled", response_model=list[ExpandedSessionRead])
def list_unscheduled_sessions(db: Session = Depends(get_db)):
    expanded = _expand_sessions(db)
    scheduled_keys = {
        (entry.session_id, entry.group_number)
        for entry in db.query(TimetableEntry).all()
    }
    unscheduled = [
        session
        for session in expanded
        if (session.session_id, session.group_number) not in scheduled_keys
    ]
    return [
        ExpandedSessionRead(
            session_id=session.session_id,
            module_id=session.module_id,
            session_type=session.session_type,
            duration_hours=session.duration_hours,
            frequency_per_week=session.frequency_per_week,
            requires_lab_type=session.requires_lab_type,
            student_count=session.student_count,
            max_students_per_group=session.max_students_per_group,
            concurrent_split=session.concurrent_split,
            lecturer_ids=list(session.lecturer_ids),
            year=session.year,
            pathway_ids=list(session.pathway_ids),
            group_number=session.group_number,
            group_size=session.group_size,
        )
        for session in unscheduled
    ]
