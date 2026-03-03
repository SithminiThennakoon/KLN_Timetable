from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.department import Department
from app.models.subject import Subject
from app.models.pathway import Pathway
from app.models.module import Module
from app.models.session import Session as SessionModel
from app.models.lecturer import Lecturer
from app.models.room import Room

router = APIRouter(prefix="/api/data-status", tags=["data-status"])


@router.get("/")
def get_data_status(db: Session = Depends(get_db)):
    issues = []
    warnings = []

    dept_count = db.query(Department).count()
    if dept_count == 0:
        issues.append("No departments found")

    subject_count = db.query(Subject).count()
    if subject_count == 0:
        issues.append("No subjects found")

    pathway_count = db.query(Pathway).count()
    if pathway_count == 0:
        issues.append("No pathways found")

    module_count = db.query(Module).count()
    if module_count == 0:
        issues.append("No modules found")

    session_count = db.query(SessionModel).count()
    if session_count == 0:
        issues.append("No sessions found")

    lecturer_count = db.query(Lecturer).count()
    if lecturer_count == 0:
        issues.append("No lecturers found")

    room_count = db.query(Room).count()
    if room_count == 0:
        issues.append("No rooms found")

    if pathway_count > 0:
        pathways = db.query(Pathway).all()
        for pathway in pathways:
            if len(pathway.subjects) != 3:
                issues.append(f"Pathway {pathway.id} does not have exactly 3 subjects")

    if session_count > 0:
        sessions = db.query(SessionModel).all()
        for session in sessions:
            if len(session.lecturers) == 0:
                issues.append(f"Session {session.id} has no lecturers assigned")
            if session.requires_lab_type:
                matching_rooms = db.query(Room).filter(Room.lab_type == session.requires_lab_type).count()
                if matching_rooms == 0:
                    issues.append(f"No rooms found for lab type {session.requires_lab_type}")
            if session.max_students_per_group and session.student_count > session.max_students_per_group:
                if session.concurrent_split and room_count == 0:
                    warnings.append(f"Session {session.id} requires split but no rooms available")

    return {
        "ready": len(issues) == 0,
        "issues": issues,
        "warnings": warnings,
    }
