from pydantic import BaseModel, Field


class TimetableEntryBase(BaseModel):
    version: str = Field(..., min_length=1, max_length=50)
    session_id: int = Field(..., gt=0)
    room_id: int = Field(..., gt=0)
    timeslot_id: int = Field(..., gt=0)
    group_number: int = Field(default=1, ge=1)
    is_manual: bool = False


class TimetableEntryCreate(TimetableEntryBase):
    pass


class TimetableEntryUpdate(BaseModel):
    version: str | None = Field(default=None, min_length=1, max_length=50)
    session_id: int | None = Field(default=None, gt=0)
    room_id: int | None = Field(default=None, gt=0)
    timeslot_id: int | None = Field(default=None, gt=0)
    group_number: int | None = Field(default=None, ge=1)
    is_manual: bool | None = None


class TimetableEntryRead(TimetableEntryBase):
    id: int

    class Config:
        from_attributes = True
