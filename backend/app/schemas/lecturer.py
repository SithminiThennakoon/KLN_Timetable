from pydantic import BaseModel, Field


class LecturerBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    email: str = Field(..., min_length=3, max_length=255)
    max_hours_per_week: int = Field(default=0, ge=0, le=60)


class LecturerCreate(LecturerBase):
    pass


class LecturerUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    email: str | None = Field(default=None, min_length=3, max_length=255)
    max_hours_per_week: int | None = Field(default=None, ge=0, le=60)


class LecturerRead(LecturerBase):
    id: int

    class Config:
        from_attributes = True
