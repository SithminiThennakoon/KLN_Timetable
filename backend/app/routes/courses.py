from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.course import Course
from app.schemas.course import CourseCreate, CourseResponse
from app.models.user import User

router = APIRouter(prefix="/api/courses", tags=["courses"]) 

@router.post("/", response_model=CourseResponse)
def create_course(course: CourseCreate, db: Session = Depends(get_db)):
    try:
        # Decide which hours column to use
        lecture_hours = course.hours_per_week if not course.is_practical else None
        practical_hours = course.hours_per_week if course.is_practical else None
        
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
