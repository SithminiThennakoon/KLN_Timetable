from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.sql import func
from app.core.database import Base

class TimeTable(Base):
    __tablename__ = "time_table"

    timetable_ID = Column(Integer, primary_key=True, autoincrement=True)
    version = Column(String(50))
    Day = Column(String(20))
    Lecturer_ID = Column(Integer)
    Group_Group_ID = Column(Integer, ForeignKey("group.Group_ID"), nullable=False)
    Room_ID = Column(Integer)
    TimeSlot_ID = Column(Integer)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    model_config = {"from_attributes": True}

