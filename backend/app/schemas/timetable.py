from typing import List, Optional

from pydantic import BaseModel, Field


class CourseInput(BaseModel):
    course_id: str
    lecturer_id: str
    student_group_id: str
    sessions_per_week: int = Field(ge=1)


class RoomInput(BaseModel):
    room_id: str


class TimetableSolveRequest(BaseModel):
    days: int = Field(default=5, ge=1, le=7)
    slots_per_day: int = Field(default=8, ge=1, le=16)
    courses: List[CourseInput]
    rooms: List[RoomInput]
    lecturer_unavailable_slots: Optional[dict[str, List[int]]] = None


class TimetableEntry(BaseModel):
    course_id: str
    lecturer_id: str
    student_group_id: str
    room_id: str
    day: int
    slot: int


class TimetableSolveResponse(BaseModel):
    status: str
    total_scheduled_sessions: int
    timetable: List[TimetableEntry]
