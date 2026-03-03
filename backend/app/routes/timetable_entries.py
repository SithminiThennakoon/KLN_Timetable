from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.timetable_entry import TimetableEntry
from app.schemas.timetable_entry import TimetableEntryCreate, TimetableEntryRead, TimetableEntryUpdate

router = APIRouter(prefix="/api/timetable/entries", tags=["timetable"])


@router.get("/", response_model=list[TimetableEntryRead])
def list_entries(db: Session = Depends(get_db)):
    return db.query(TimetableEntry).order_by(TimetableEntry.id).all()


@router.post("/", response_model=TimetableEntryRead, status_code=status.HTTP_201_CREATED)
def create_entry(payload: TimetableEntryCreate, db: Session = Depends(get_db)):
    entry = TimetableEntry(
        version=payload.version,
        session_id=payload.session_id,
        room_id=payload.room_id,
        timeslot_id=payload.timeslot_id,
        group_number=payload.group_number,
        is_manual=payload.is_manual,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


@router.put("/{entry_id}", response_model=TimetableEntryRead)
def update_entry(entry_id: int, payload: TimetableEntryUpdate, db: Session = Depends(get_db)):
    entry = db.query(TimetableEntry).filter(TimetableEntry.id == entry_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")
    if payload.version is not None:
        entry.version = payload.version
    if payload.session_id is not None:
        entry.session_id = payload.session_id
    if payload.room_id is not None:
        entry.room_id = payload.room_id
    if payload.timeslot_id is not None:
        entry.timeslot_id = payload.timeslot_id
    if payload.group_number is not None:
        entry.group_number = payload.group_number
    if payload.is_manual is not None:
        entry.is_manual = payload.is_manual
    db.commit()
    db.refresh(entry)
    return entry


@router.delete("/{entry_id}")
def delete_entry(entry_id: int, db: Session = Depends(get_db)):
    entry = db.query(TimetableEntry).filter(TimetableEntry.id == entry_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")
    db.delete(entry)
    db.commit()
    return {"message": "Entry deleted"}
