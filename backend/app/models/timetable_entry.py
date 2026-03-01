from sqlalchemy import Column, Integer, String, Boolean, ForeignKey
from app.core.database import Base


class TimetableEntry(Base):
    __tablename__ = "timetable_entry"

    id = Column(Integer, primary_key=True, index=True)
    version = Column(String(50), nullable=False)
    session_id = Column(Integer, ForeignKey("session.id"), nullable=False)
    room_id = Column(Integer, ForeignKey("room.id"), nullable=False)
    timeslot_id = Column(Integer, ForeignKey("timeslot.id"), nullable=False)
    group_number = Column(Integer, nullable=False, default=1)
    is_manual = Column(Boolean, default=False)
