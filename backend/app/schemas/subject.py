from pydantic import BaseModel, Field


class SubjectBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    code: str = Field(..., min_length=1, max_length=10)
    department_id: int = Field(..., gt=0)


class SubjectCreate(SubjectBase):
    pass


class SubjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    code: str | None = Field(default=None, min_length=1, max_length=10)
    department_id: int | None = Field(default=None, gt=0)


class SubjectRead(SubjectBase):
    id: int

    class Config:
        from_attributes = True
