from pydantic import BaseModel, Field


class SessionBase(BaseModel):
    module_id: int = Field(..., gt=0)
    session_type: str = Field(..., min_length=1, max_length=20)
    duration_hours: int = Field(..., ge=1, le=6)
    frequency_per_week: int = Field(..., ge=1, le=10)
    requires_lab_type: str | None = Field(default=None, max_length=50)
    student_count: int = Field(..., ge=1)
    max_students_per_group: int | None = Field(default=None, ge=1)
    concurrent_split: bool = False


class SessionCreate(SessionBase):
    lecturer_ids: list[int] = Field(default_factory=list)


class SessionUpdate(BaseModel):
    module_id: int | None = Field(default=None, gt=0)
    session_type: str | None = Field(default=None, min_length=1, max_length=20)
    duration_hours: int | None = Field(default=None, ge=1, le=6)
    frequency_per_week: int | None = Field(default=None, ge=1, le=10)
    requires_lab_type: str | None = Field(default=None, max_length=50)
    student_count: int | None = Field(default=None, ge=1)
    max_students_per_group: int | None = Field(default=None, ge=1)
    concurrent_split: bool | None = None
    lecturer_ids: list[int] | None = None


class SessionRead(SessionBase):
    id: int
    lecturer_ids: list[int] = Field(default_factory=list)

    class Config:
        from_attributes = True
