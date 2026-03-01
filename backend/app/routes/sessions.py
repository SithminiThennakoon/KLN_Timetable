from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.session import Session as SessionModel
from app.models.module import Module
from app.models.lecturer import Lecturer
from app.schemas.session import SessionCreate, SessionRead, SessionUpdate

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


def _session_to_read(session: SessionModel) -> SessionRead:
    lecturer_ids = [lecturer.id for lecturer in session.lecturers]
    return SessionRead(
        id=session.id,
        module_id=session.module_id,
        session_type=session.session_type,
        duration_hours=session.duration_hours,
        frequency_per_week=session.frequency_per_week,
        requires_lab_type=session.requires_lab_type,
        student_count=session.student_count,
        max_students_per_group=session.max_students_per_group,
        concurrent_split=session.concurrent_split,
        lecturer_ids=lecturer_ids,
    )


@router.get("/", response_model=list[SessionRead])
def list_sessions(db: Session = Depends(get_db)):
    sessions = db.query(SessionModel).order_by(SessionModel.id).all()
    return [_session_to_read(session) for session in sessions]


@router.post("/", response_model=SessionRead, status_code=status.HTTP_201_CREATED)
def create_session(payload: SessionCreate, db: Session = Depends(get_db)):
    module = db.query(Module).filter(Module.id == payload.module_id).first()
    if not module:
        raise HTTPException(status_code=400, detail="Module not found")
    session = SessionModel(
        module_id=payload.module_id,
        session_type=payload.session_type,
        duration_hours=payload.duration_hours,
        frequency_per_week=payload.frequency_per_week,
        requires_lab_type=payload.requires_lab_type,
        student_count=payload.student_count,
        max_students_per_group=payload.max_students_per_group,
        concurrent_split=payload.concurrent_split,
    )
    if payload.lecturer_ids:
        lecturers = db.query(Lecturer).filter(Lecturer.id.in_(payload.lecturer_ids)).all()
        if len(lecturers) != len(set(payload.lecturer_ids)):
            raise HTTPException(status_code=400, detail="One or more lecturers not found")
        session.lecturers = lecturers
    db.add(session)
    db.commit()
    db.refresh(session)
    return _session_to_read(session)


@router.put("/{session_id}", response_model=SessionRead)
def update_session(session_id: int, payload: SessionUpdate, db: Session = Depends(get_db)):
    session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if payload.module_id is not None:
        module = db.query(Module).filter(Module.id == payload.module_id).first()
        if not module:
            raise HTTPException(status_code=400, detail="Module not found")
        session.module_id = payload.module_id
    if payload.session_type is not None:
        session.session_type = payload.session_type
    if payload.duration_hours is not None:
        session.duration_hours = payload.duration_hours
    if payload.frequency_per_week is not None:
        session.frequency_per_week = payload.frequency_per_week
    if payload.requires_lab_type is not None or payload.requires_lab_type is None:
        session.requires_lab_type = payload.requires_lab_type
    if payload.student_count is not None:
        session.student_count = payload.student_count
    if payload.max_students_per_group is not None or payload.max_students_per_group is None:
        session.max_students_per_group = payload.max_students_per_group
    if payload.concurrent_split is not None:
        session.concurrent_split = payload.concurrent_split
    if payload.lecturer_ids is not None:
        lecturers = db.query(Lecturer).filter(Lecturer.id.in_(payload.lecturer_ids)).all()
        if len(lecturers) != len(set(payload.lecturer_ids)):
            raise HTTPException(status_code=400, detail="One or more lecturers not found")
        session.lecturers = lecturers
    db.commit()
    db.refresh(session)
    return _session_to_read(session)


@router.delete("/{session_id}")
def delete_session(session_id: int, db: Session = Depends(get_db)):
    session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    db.delete(session)
    db.commit()
    return {"message": "Session deleted"}
