from pydantic import BaseModel
from typing import Optional

class CourseCreate(BaseModel):
    course_code: str
    course_name: str
    hours_per_week: int
    lecturer_id: int
    is_practical: bool

class CourseResponse(BaseModel):
    id: int
    course_code: str
    course_name: str
    lecture_hours_per_week: Optional[int]
    practical_hours_per_week: Optional[int]
    lecturer_id: int

    class Config:
        orm_mode = True
