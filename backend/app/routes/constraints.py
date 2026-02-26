from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.core.database import get_db
from app.models.constraint import Constraint
from app.schemas.constraint import ConstraintRead, ConstraintUpdate

router = APIRouter(prefix="/api/constraints", tags=["constraints"])

@router.get("/", response_model=List[ConstraintRead])
def read_constraints(db: Session = Depends(get_db)):
    return db.query(Constraint).all()

@router.patch("/{constraint_id}", response_model=ConstraintRead)
def update_constraint_enabled(constraint_id: int, patch: ConstraintUpdate, db: Session = Depends(get_db)):
    constraint = db.query(Constraint).filter(Constraint.Constraint_ID == constraint_id).first()
    if constraint is None:
        raise HTTPException(status_code=404, detail="Constraint not found")
    constraint.enabled = patch.enabled
    db.commit()
    db.refresh(constraint)
    return constraint
