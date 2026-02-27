from pydantic import BaseModel, Field
from typing import List, Optional

# Group (Batch) schemas
class GroupBase(BaseModel):
    groupName: str = Field(..., min_length=1, max_length=100, description="Batch/Group name")
    semesterId: int = Field(..., gt=0, description="Semester ID from Semester table")
    studentCount: int = Field(..., gt=0, description="Number of students (strength)")

class GroupCreate(GroupBase):
    pass

class GroupResponse(GroupBase):
    id: int

model_config = {"from_attributes": True}


# Course schemas
class CourseBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    code: str = Field(..., min_length=1, max_length=20)
    credits: int = Field(..., gt=0, lt=10)
    department_id: int

class CourseCreate(CourseBase):
    pass

class CourseResponse(CourseBase):
    id: int

    model_config = {"from_attributes": True}

# Department schemas
class DepartmentBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    code: str = Field(..., min_length=1, max_length=10)

class DepartmentCreate(DepartmentBase):
    pass

class DepartmentResponse(DepartmentBase):
    id: int

    model_config = {"from_attributes": True}

# Semester schemas
class SemesterBase(BaseModel):
    semesterName: str
    academicYear: str

class SemesterCreate(SemesterBase):
    pass

class SemesterResponse(SemesterBase):
    id: int
    model_config = {"from_attributes": True}

# Room schemas
class RoomBase(BaseModel):
    roomName: str = Field(..., min_length=1, max_length=100, alias="name")
    roomType: str = Field(..., min_length=1, max_length=50, alias="type")
    location: str = Field(..., min_length=1, max_length=100, alias="building")
    capacity: int = Field(..., gt=0)
    isLaboratory: int = Field(0, ge=0, le=1)
    isLectureHall: int = Field(0, ge=0, le=1)

    model_config = {"populate_by_name": True}

class RoomCreate(RoomBase):
    pass

class RoomResponse(RoomBase):
    id: int

    model_config = {"from_attributes": True, "populate_by_name": True}

# Batch with courses relationship
class BatchWithCourses(GroupResponse):
    courses: List[CourseResponse] = []

    model_config = {"from_attributes": True}

# Group with semester details
class GroupWithSemester(GroupResponse):
    semesterName: str
    academicYear: str

    model_config = {"from_attributes": True}
