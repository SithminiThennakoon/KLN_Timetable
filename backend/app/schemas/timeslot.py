from datetime import time
from pydantic import BaseModel


class TimeslotRead(BaseModel):
    id: int
    day: str
    start_time: time
    end_time: time
    is_lunch: bool

    class Config:
        from_attributes = True
