from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.lecturer import Lecturer
from app.schemas.lecturer import LecturerCreate, LecturerRead, LecturerUpdate

router = APIRouter(prefix="/api/lecturers", tags=["lecturers"])


@router.get("/", response_model=list[LecturerRead])
def list_lecturers(db: Session = Depends(get_db)):
    return db.query(Lecturer).order_by(Lecturer.id).all()


@router.post("/", response_model=LecturerRead, status_code=status.HTTP_201_CREATED)
def create_lecturer(payload: LecturerCreate, db: Session = Depends(get_db)):
    existing = db.query(Lecturer).filter(Lecturer.email == payload.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Lecturer email already exists")
    lecturer = Lecturer(
        name=payload.name,
        email=payload.email,
        max_hours_per_week=payload.max_hours_per_week,
    )
    db.add(lecturer)
    db.commit()
    db.refresh(lecturer)
    return lecturer


@router.put("/{lecturer_id}", response_model=LecturerRead)
def update_lecturer(lecturer_id: int, payload: LecturerUpdate, db: Session = Depends(get_db)):
    lecturer = db.query(Lecturer).filter(Lecturer.id == lecturer_id).first()
    if not lecturer:
        raise HTTPException(status_code=404, detail="Lecturer not found")
    if payload.email is not None:
        existing = db.query(Lecturer).filter(Lecturer.email == payload.email, Lecturer.id != lecturer_id).first()
        if existing:
            raise HTTPException(status_code=400, detail="Lecturer email already exists")
        lecturer.email = payload.email
    if payload.name is not None:
        lecturer.name = payload.name
    if payload.max_hours_per_week is not None:
        lecturer.max_hours_per_week = payload.max_hours_per_week
    db.commit()
    db.refresh(lecturer)
    return lecturer


@router.delete("/{lecturer_id}")
def delete_lecturer(lecturer_id: int, db: Session = Depends(get_db)):
    lecturer = db.query(Lecturer).filter(Lecturer.id == lecturer_id).first()
    if not lecturer:
        raise HTTPException(status_code=404, detail="Lecturer not found")
    db.delete(lecturer)
    db.commit()
    return {"message": "Lecturer deleted"}
