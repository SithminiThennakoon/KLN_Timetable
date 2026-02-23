from pydantic import BaseModel, Field
from typing import List, Optional

# Batch schemas
class BatchBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    year: int = Field(..., gt=1900, lt=2100)
    semester: str = Field(..., min_length=1, max_length=20)
    strength: int = Field(..., gt=0)

class BatchCreate(BatchBase):
    pass

class BatchResponse(BatchBase):
    id: int

    class Config:
        orm_mode = True

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

    class Config:
        orm_mode = True

# Department schemas
class DepartmentBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    code: str = Field(..., min_length=1, max_length=10)

class DepartmentCreate(DepartmentBase):
    pass

class DepartmentResponse(DepartmentBase):
    id: int

    class Config:
        orm_mode = True

# Room schemas
class RoomBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=50)
    capacity: int = Field(..., gt=0)
    building: str = Field(..., min_length=1, max_length=50)
    type: str = Field(..., min_length=1, max_length=20)

class RoomCreate(RoomBase):
    pass

class RoomResponse(RoomBase):
    id: int

    class Config:
        orm_mode = True

# Batch with courses relationship
class BatchWithCourses(BatchResponse):
    courses: List[CourseResponse] = []

    class Config:
        orm_mode = True