from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.core.database import get_db
from app.models.admin_login import AdminLogin
from app.models.student_login import StudentLogin

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])

@router.get("/stats")
def get_dashboard_stats(db: Session = Depends(get_db)):
    """Get dashboard statistics"""
    try:
        total_admins = db.query(func.count(AdminLogin.id)).scalar()
        total_students = db.query(func.count(StudentLogin.stu_id)).scalar()
        
        return {
            "total_admins": total_admins,
            "total_students": total_students,
            "total_courses": 45,
            "total_lecturers": 32,
            "total_classrooms": 28,
            "departments": 6,
            "generated_timetables": 12
        }
    except Exception as e:
        return {
            "total_admins": 0,
            "total_students": 0,
            "total_courses": 0,
            "total_lecturers": 0,
            "total_classrooms": 0,
            "departments": 0,
            "generated_timetables": 0
        }

@router.get("/recent-activity")
def get_recent_activity(db: Session = Depends(get_db)):
    """Get recent activity"""
    return [
        {"id": 1, "action": "Generated timetable for Computer Science", "time": "2 hours ago", "type": "success"},
        {"id": 2, "action": "Added new lecturer Dr. John Smith", "time": "5 hours ago", "type": "info"},
        {"id": 3, "action": "Updated Mathematics department courses", "time": "1 day ago", "type": "warning"},
        {"id": 4, "action": "Deleted classroom LB-101", "time": "2 days ago", "type": "error"}
    ]
