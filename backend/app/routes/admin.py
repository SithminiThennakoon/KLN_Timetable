from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.core.database import get_db, engine
from app.models.admin_login import AdminLogin
from app.models.student_login import StudentLogin
from app.schemas.admin import GroupCreate, GroupResponse, CourseCreate, CourseResponse, DepartmentCreate, DepartmentResponse, RoomCreate, RoomResponse, SemesterCreate, SemesterResponse

router = APIRouter(prefix="/api/admin", tags=["admin"])

# Semesters endpoints
@router.post("/semesters", response_model=SemesterResponse)
def create_semester(
    semester: SemesterCreate,
    db: Session = Depends(get_db)
):
    """Create a new semester"""
    try:
        print(f"DEBUG: Received semester data: {semester}")
        
        from app.models.semester import Semester as SemesterModel
        
        new_semester = SemesterModel(
            Semester_name=semester.semesterName,
            Academic_year=semester.academicYear
        )
        
        db.add(new_semester)
        db.commit()
        db.refresh(new_semester)
        
        print(f"DEBUG: Semester created with ID: {new_semester.Semester_ID}")

        return SemesterResponse(
            id=new_semester.Semester_ID,
            semesterName=semester.semesterName,
            academicYear=semester.academicYear
        )
    except Exception as e:
        print(f"DEBUG: Error: {e}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating semester: {str(e)}"
        )

@router.get("/semesters")
def get_semesters(db: Session = Depends(get_db)):
    """Get all semesters"""
    try:
        result = db.execute(
            text("""
                SELECT
                    Semester_ID as id,
                    Semester_name as semesterName,
                    Academic_year as academicYear
                FROM semester
                ORDER BY Academic_year DESC, Semester_ID
            """)
        )

        semesters = []
        for row in result:
            semesters.append({
                "id": row.id,
                "name": row.semesterName,
                "academicYear": row.academicYear
            })

        return semesters
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching semesters: {str(e)}"
        )


# Groups (Batches) endpoints
@router.post("/groups", response_model=GroupResponse)
def create_group(group: GroupCreate, db: Session = Depends(get_db)):
    """Create a new group/batch"""
    try:
        with engine.connect() as conn:
            result = conn.execute(
                text("""
                    INSERT INTO `group` (Group_name, Semester_Semester_ID, Student_count)
                    VALUES (:group_name, :semester_id, :student_count)
                """),
                {
                    "group_name": group.groupName,
                    "semester_id": group.semesterId,
                    "student_count": group.studentCount
                }
            )
            conn.commit()
            group_id = result.lastrowid

        return GroupResponse(
            id=group_id,
            groupName=group.groupName,
            semesterId=group.semesterId,
            studentCount=group.studentCount
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating group: {str(e)}"
        )

@router.get("/groups")
def get_groups(db: Session = Depends(get_db)):
    """Get all groups with semester details"""
    try:
        result = db.execute(
            text("""
                SELECT
                    g.Group_ID as id,
                    g.Group_name as groupName,
                    g.Semester_Semester_ID as semesterId,
                    g.Student_count as studentCount,
                    s.Semester_name as semesterName,
                    s.Academic_year as academicYear
                FROM `group` g
                LEFT JOIN semester s ON g.Semester_Semester_ID = s.Semester_ID
                ORDER BY g.Group_ID DESC
            """)
        )

        groups = []
        for row in result:
            groups.append(GroupResponse(
                id=row.id,
                groupName=row.groupName,
                semesterId=row.semesterId,
                studentCount=row.studentCount
            ))

        return groups
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching groups: {str(e)}"
        )

@router.get("/groups/{group_id}", response_model=GroupResponse)
def get_group(group_id: int, db: Session = Depends(get_db)):
    """Get a specific group"""
    try:
        result = db.execute(
            text("""
                SELECT
                    g.Group_ID as id,
                    g.Group_name as groupName,
                    g.Semester_Semester_ID as semesterId,
                    g.Student_count as studentCount,
                    s.Semester_name as semesterName,
                    s.Academic_year as academicYear
                FROM `group` g
                LEFT JOIN semester s ON g.Semester_Semester_ID = s.Semester_ID
                WHERE g.Group_ID = :group_id
            """),
            {"group_id": group_id}
        ).fetchone()

        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Group not found"
            )

        return GroupResponse(
            id=result.id,
            groupName=result.groupName,
            semesterId=result.semesterId,
            studentCount=result.studentCount
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching group: {str(e)}"
        )

@router.put("/groups/{group_id}", response_model=GroupResponse)
def update_group(group_id: int, group: GroupCreate, db: Session = Depends(get_db)):
    """Update a group"""
    try:
        result = db.execute(
            text("""
                UPDATE `group`
                SET Group_name = :group_name,
                    Semester_Semester_ID = :semester_id,
                    Student_count = :student_count
                WHERE Group_ID = :group_id
            """),
            {
                "group_id": group_id,
                "group_name": group.groupName,
                "semester_id": group.semesterId,
                "student_count": group.studentCount
            }
        )
        db.commit()

        return GroupResponse(
            id=group_id,
            groupName=group.groupName,
            semesterId=group.semesterId,
            studentCount=group.studentCount
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating group: {str(e)}"
        )

@router.delete("/groups/{group_id}")
def delete_group(group_id: int, db: Session = Depends(get_db)):
    """Delete a group"""
    try:
        result = db.execute(
            text("DELETE FROM `group` WHERE Group_ID = :group_id"),
            {"group_id": group_id}
        )
        db.commit()

        if result.rowcount == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Group not found"
            )

        return {"message": "Group deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting group: {str(e)}"
        )

@router.post("/save-to-timetable")
def save_to_timetable(group_ids: list[int], db: Session = Depends(get_db)):
    """Save selected groups to time_table using group_ID"""
    try:
        for group_id in group_ids:
            db.execute(
                text("""
                    INSERT INTO time_table (Group_Group_ID)
                    VALUES (:group_id)
                """),
                {"group_id": group_id}
            )

        db.commit()

        return {
            "message": f"Successfully saved {len(group_ids)} groups to timetable",
            "count": len(group_ids)
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error saving to timetable: {str(e)}"
        )


# Courses endpoints
@router.post("/courses", response_model=CourseResponse)
def create_course(course: CourseCreate, db: Session = Depends(get_db)):
    """Create a new course"""
    # Implementation would go here
    pass

@router.get("/courses", response_model=list[CourseResponse])
def get_courses(db: Session = Depends(get_db)):
    """Get all courses"""
    # Implementation would go here
    return []

@router.get("/courses/{course_id}", response_model=CourseResponse)
def get_course(course_id: int, db: Session = Depends(get_db)):
    """Get a specific course"""
    # Implementation would go here
    pass

@router.put("/courses/{course_id}", response_model=CourseResponse)
def update_course(course_id: int, course: CourseCreate, db: Session = Depends(get_db)):
    """Update a course"""
    # Implementation would go here
    pass

@router.delete("/courses/{course_id}")
def delete_course(course_id: int, db: Session = Depends(get_db)):
    """Delete a course"""
    # Implementation would go here
    pass

# Departments endpoints
@router.post("/departments", response_model=DepartmentResponse)
def create_department(department: DepartmentCreate, db: Session = Depends(get_db)):
    """Create a new department"""
    # Implementation would go here
    pass

@router.get("/departments", response_model=list[DepartmentResponse])
def get_departments(db: Session = Depends(get_db)):
    """Get all departments"""
    # Implementation would go here
    return []

@router.get("/departments/{department_id}", response_model=DepartmentResponse)
def get_department(department_id: int, db: Session = Depends(get_db)):
    """Get a specific department"""
    # Implementation would go here
    pass

@router.put("/departments/{department_id}", response_model=DepartmentResponse)
def update_department(department_id: int, department: DepartmentCreate, db: Session = Depends(get_db)):
    """Update a department"""
    # Implementation would go here
    pass

@router.delete("/departments/{department_id}")
def delete_department(department_id: int, db: Session = Depends(get_db)):
    """Delete a department"""
    # Implementation would go here
    pass

# Rooms endpoints
@router.post("/rooms", response_model=RoomResponse)
def create_room(room: RoomCreate, db: Session = Depends(get_db)):
    """Create a new room"""
    # Implementation would go here
    pass

@router.get("/rooms", response_model=list[RoomResponse])
def get_rooms(db: Session = Depends(get_db)):
    """Get all rooms"""
    # Implementation would go here
    return []

@router.get("/rooms/{room_id}", response_model=RoomResponse)
def get_room(room_id: int, db: Session = Depends(get_db)):
    """Get a specific room"""
    # Implementation would go here
    pass

@router.put("/rooms/{room_id}", response_model=RoomResponse)
def update_room(room_id: int, room: RoomCreate, db: Session = Depends(get_db)):
    """Update a room"""
    # Implementation would go here
    pass

@router.delete("/rooms/{room_id}")
def delete_room(room_id: int, db: Session = Depends(get_db)):
    """Delete a room"""
    # Implementation would go here
    pass