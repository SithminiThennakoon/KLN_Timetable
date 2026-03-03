from sqlalchemy import Column, Integer, String, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.models.associations import session_lecturer_table


class Session(Base):
    __tablename__ = "session"

    id = Column(Integer, primary_key=True, index=True)
    module_id = Column(Integer, ForeignKey("module.id"), nullable=False)
    session_type = Column(String(20), nullable=False)
    duration_hours = Column(Integer, nullable=False)
    frequency_per_week = Column(Integer, nullable=False)
    requires_lab_type = Column(String(50), nullable=True)
    student_count = Column(Integer, nullable=False)
    max_students_per_group = Column(Integer, nullable=True)
    concurrent_split = Column(Boolean, default=False)

    module = relationship("Module", back_populates="sessions")
    lecturers = relationship("Lecturer", secondary=session_lecturer_table, back_populates="sessions")
