from pydantic import BaseModel, Field


class ModuleBase(BaseModel):
    code: str = Field(..., min_length=1, max_length=25)
    name: str = Field(..., min_length=1, max_length=200)
    subject_id: int = Field(..., gt=0)
    year: int = Field(..., ge=1, le=6)
    semester: int = Field(..., ge=1, le=2)


class ModuleCreate(ModuleBase):
    pass


class ModuleUpdate(BaseModel):
    code: str | None = Field(default=None, min_length=1, max_length=25)
    name: str | None = Field(default=None, min_length=1, max_length=200)
    subject_id: int | None = Field(default=None, gt=0)
    year: int | None = Field(default=None, ge=1, le=6)
    semester: int | None = Field(default=None, ge=1, le=2)


class ModuleRead(ModuleBase):
    id: int

    class Config:
        from_attributes = True
