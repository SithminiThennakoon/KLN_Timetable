from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import List, cast
from app.core.database import get_db
from app.models.constraint import Constraint
from app.schemas.constraint import ConstraintRead, ConstraintUpdate, ConstraintBase

router = APIRouter(prefix="/api/constraints", tags=["constraints"])


def ensure_timetable_constraint_table(db: Session) -> None:
    db.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS time_table_constraint (
                id INT AUTO_INCREMENT PRIMARY KEY,
                constraint_id INT NOT NULL
            )
            """
        )
    )
    db.commit()

@router.get("/", response_model=List[ConstraintRead])
def read_constraints(db: Session = Depends(get_db)):
    return db.query(Constraint).all()

@router.post("/", response_model=ConstraintRead)
def create_constraint(constraint: ConstraintBase, db: Session = Depends(get_db)):
    new_constraint = Constraint(
        name=constraint.name,
        description=constraint.description,
        enabled=True
    )
    db.add(new_constraint)
    db.commit()
    db.refresh(new_constraint)
    return new_constraint

@router.patch("/{constraint_id}", response_model=ConstraintRead)
def update_constraint_enabled(constraint_id: int, patch: ConstraintUpdate, db: Session = Depends(get_db)):
    constraint = db.query(Constraint).filter(Constraint.Constraint_ID == constraint_id).first()
    if constraint is None:
        raise HTTPException(status_code=404, detail="Constraint not found")
    setattr(constraint, "enabled", bool(patch.enabled))
    db.commit()
    db.refresh(constraint)
    return constraint

@router.delete("/{constraint_id}")
def delete_constraint(constraint_id: int, db: Session = Depends(get_db)):
    constraint = db.query(Constraint).filter(Constraint.Constraint_ID == constraint_id).first()
    if constraint is None:
        raise HTTPException(status_code=404, detail="Constraint not found")
    db.delete(constraint)
    db.commit()
    return {"message": "Constraint deleted"}

@router.get("/selection")
def get_constraint_selection(db: Session = Depends(get_db)):
    ensure_timetable_constraint_table(db)
    result = db.execute(
        text("SELECT constraint_id FROM time_table_constraint")
    )
    return [row.constraint_id for row in result]

@router.post("/selection")
def save_constraint_selection(constraint_ids: List[int], db: Session = Depends(get_db)):
    ensure_timetable_constraint_table(db)
    db.execute(text("DELETE FROM time_table_constraint"))
    for constraint_id in constraint_ids:
        db.execute(
            text("INSERT INTO time_table_constraint (constraint_id) VALUES (:constraint_id)"),
            {"constraint_id": constraint_id}
        )
    db.commit()
    return {"message": "Constraints saved", "count": len(constraint_ids)}
