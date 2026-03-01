from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.models.associations import session_lecturer_table


class Lecturer(Base):
    __tablename__ = "lecturer"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    email = Column(String(255), nullable=False, unique=True)
    max_hours_per_week = Column(Integer, nullable=False, default=0)

    sessions = relationship("Session", secondary=session_lecturer_table, back_populates="lecturers")
