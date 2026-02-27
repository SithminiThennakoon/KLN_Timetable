from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.user import User, UserRole

router = APIRouter(prefix="/api/lecturers", tags=["lecturers"]) 

@router.get("/", response_model=list[dict])
def list_lecturers(db: Session = Depends(get_db)):
    """Return a list of users where role is lecturer."""
    try:
        lecturers = db.query(User).filter(User.role == UserRole.LECTURER).all()
        return [{
            "id": u.id,
            "name": u.name
        } for u in lecturers]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
