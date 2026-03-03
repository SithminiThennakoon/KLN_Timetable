from sqlalchemy import Column, Integer, String, Boolean, Time
from app.core.database import Base


class Timeslot(Base):
    __tablename__ = "timeslot"

    id = Column(Integer, primary_key=True, index=True)
    day = Column(String(10), nullable=False)
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)
    is_lunch = Column(Boolean, default=False)
