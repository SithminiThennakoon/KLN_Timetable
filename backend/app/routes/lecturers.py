from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.core.database import get_db
from app.models.user import User, UserRole

router = APIRouter(prefix="/api/lecturers", tags=["lecturers"]) 


def ensure_lecturers_table(db: Session) -> None:
    db.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS lecturers (
                Lecturer_ID INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                email VARCHAR(255) NOT NULL,
                max_teaching_hours INT NOT NULL DEFAULT 0
            )
            """
        )
    )
    db.commit()

@router.get("/", response_model=list[dict])
def list_lecturers(db: Session = Depends(get_db)):
    """Return a list of users where role is lecturer."""
    try:
        ensure_lecturers_table(db)
        result = db.execute(
            text("""
                SELECT
                    Lecturer_ID as id,
                    name,
                    email,
                    max_teaching_hours
                FROM lecturers
                ORDER BY Lecturer_ID DESC
            """)
        )
        return [
            {
                "id": row.id,
                "name": row.name,
                "email": row.email,
                "max_teaching_hours": row.max_teaching_hours
            }
            for row in result
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/", response_model=dict)
def create_lecturer(payload: dict, db: Session = Depends(get_db)):
    try:
        ensure_lecturers_table(db)
        name = payload.get("name")
        email = payload.get("email")
        max_teaching_hours = payload.get("max_teaching_hours")

        if not name or not email:
            raise HTTPException(status_code=400, detail="Name and email are required")

        db.execute(
            text(
                """
                INSERT INTO lecturers (name, email, max_teaching_hours)
                VALUES (:name, :email, :max_teaching_hours)
                """
            ),
            {
                "name": name,
                "email": email,
                "max_teaching_hours": int(max_teaching_hours) if max_teaching_hours is not None else 0
            }
        )
        db.commit()
        lecturer_id = db.execute(text("SELECT LAST_INSERT_ID()")).scalar()

        return {
            "id": int(lecturer_id) if lecturer_id is not None else 0,
            "name": name,
            "email": email,
            "max_teaching_hours": int(max_teaching_hours) if max_teaching_hours is not None else 0
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{lecturer_id}")
def update_lecturer(lecturer_id: int, payload: dict, db: Session = Depends(get_db)):
    try:
        ensure_lecturers_table(db)
        name = payload.get("name")
        email = payload.get("email")
        max_teaching_hours = payload.get("max_teaching_hours")

        if not name or not email:
            raise HTTPException(status_code=400, detail="Name and email are required")

        result = db.execute(
            text(
                """
                UPDATE lecturers
                SET name = :name,
                    email = :email,
                    max_teaching_hours = :max_teaching_hours
                WHERE Lecturer_ID = :lecturer_id
                """
            ),
            {
                "name": name,
                "email": email,
                "max_teaching_hours": int(max_teaching_hours) if max_teaching_hours is not None else 0,
                "lecturer_id": lecturer_id
            }
        )
        db.commit()

        if getattr(result, "rowcount", 0) == 0:
            raise HTTPException(status_code=404, detail="Lecturer not found")

        return {
            "id": lecturer_id,
            "name": name,
            "email": email,
            "max_teaching_hours": int(max_teaching_hours) if max_teaching_hours is not None else 0
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{lecturer_id}")
def delete_lecturer(lecturer_id: int, db: Session = Depends(get_db)):
    try:
        ensure_lecturers_table(db)
        result = db.execute(
            text("DELETE FROM lecturers WHERE Lecturer_ID = :lecturer_id"),
            {"lecturer_id": lecturer_id}
        )
        db.commit()

        if getattr(result, "rowcount", 0) == 0:
            raise HTTPException(status_code=404, detail="Lecturer not found")

        return {"message": "Lecturer deleted"}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
