from pydantic import BaseModel, Field


class PathwayBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    department_id: int = Field(..., gt=0)
    year: int = Field(..., ge=1, le=6)


class PathwayCreate(PathwayBase):
    subject_ids: list[int] = Field(default_factory=list)


class PathwayUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    department_id: int | None = Field(default=None, gt=0)
    year: int | None = Field(default=None, ge=1, le=6)
    subject_ids: list[int] | None = None


class PathwayRead(PathwayBase):
    id: int
    subject_ids: list[int] = Field(default_factory=list)

    class Config:
        from_attributes = True
