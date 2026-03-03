from pydantic import BaseModel, Field


class RoomBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    capacity: int = Field(..., ge=1)
    room_type: str = Field(..., min_length=1, max_length=30)
    lab_type: str | None = Field(default=None, max_length=50)
    location: str = Field(..., min_length=1, max_length=100)
    year_restriction: int | None = Field(default=None, ge=1, le=6)


class RoomCreate(RoomBase):
    pass


class RoomUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    capacity: int | None = Field(default=None, ge=1)
    room_type: str | None = Field(default=None, min_length=1, max_length=30)
    lab_type: str | None = Field(default=None, max_length=50)
    location: str | None = Field(default=None, min_length=1, max_length=100)
    year_restriction: int | None = Field(default=None, ge=1, le=6)


class RoomRead(RoomBase):
    id: int

    class Config:
        from_attributes = True
