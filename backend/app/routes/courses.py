from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.course import Course
from app.schemas.course import CourseCreate, CourseResponse
from sqlalchemy import text

router = APIRouter(prefix="/api/courses", tags=["courses"]) 

@router.post("/", response_model=CourseResponse)
def create_course(course: CourseCreate, db: Session = Depends(get_db)):
    try:
        # Decide which hours column to use
        lecture_hours = course.hours_per_week if not course.is_practical else None
        practical_hours = course.hours_per_week if course.is_practical else None

        db.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS course (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    course_code VARCHAR(25) NOT NULL UNIQUE,
                    course_name VARCHAR(100) NOT NULL,
                    lecture_hours_per_week INT NULL,
                    practical_hours_per_week INT NULL,
                    lecturer_id INT NOT NULL
                )
                """
            )
        )

        fk_name = db.execute(
            text(
                """
                SELECT CONSTRAINT_NAME
                FROM information_schema.KEY_COLUMN_USAGE
                WHERE TABLE_SCHEMA = DATABASE()
                  AND TABLE_NAME = 'course'
                  AND COLUMN_NAME = 'lecturer_id'
                  AND REFERENCED_TABLE_NAME IS NOT NULL
                """
            )
        ).scalar()

        if fk_name:
            db.execute(text(f"ALTER TABLE course DROP FOREIGN KEY {fk_name}"))

        db.commit()
        
        db_course = Course(
            course_code=course.course_code,
            course_name=course.course_name,
            lecture_hours_per_week=lecture_hours,
            practical_hours_per_week=practical_hours,
            lecturer_id=course.lecturer_id
        )
        db.add(db_course)
        db.commit()
        db.refresh(db_course)
        return db_course
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating course: {str(e)}"
        )

@router.get("/", response_model=list[CourseResponse])
def list_courses(db: Session = Depends(get_db)):
    try:
        return db.query(Course).all()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error listing courses: {str(e)}"
        )

@router.put("/{course_id}", response_model=CourseResponse)
def update_course(course_id: int, course: CourseCreate, db: Session = Depends(get_db)):
    try:
        lecture_hours = course.hours_per_week if not course.is_practical else None
        practical_hours = course.hours_per_week if course.is_practical else None

        db_course = db.query(Course).filter(Course.id == course_id).first()
        if not db_course:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")

        setattr(db_course, "course_code", course.course_code)
        setattr(db_course, "course_name", course.course_name)
        setattr(db_course, "lecture_hours_per_week", lecture_hours)
        setattr(db_course, "practical_hours_per_week", practical_hours)
        setattr(db_course, "lecturer_id", course.lecturer_id)

        db.commit()
        db.refresh(db_course)
        return db_course
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating course: {str(e)}"
        )

@router.delete("/{course_id}")
def delete_course(course_id: int, db: Session = Depends(get_db)):
    try:
        db_course = db.query(Course).filter(Course.id == course_id).first()
        if not db_course:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")

        db.delete(db_course)
        db.commit()
        return {"message": "Course deleted"}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting course: {str(e)}"
        )
