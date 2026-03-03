from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.timeslot import Timeslot
from app.schemas.timeslot import TimeslotRead

router = APIRouter(prefix="/api/timeslots", tags=["timeslots"])


@router.get("/", response_model=list[TimeslotRead])
def list_timeslots(db: Session = Depends(get_db)):
    return db.query(Timeslot).order_by(Timeslot.id).all()
