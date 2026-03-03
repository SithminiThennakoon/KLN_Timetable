from sqlalchemy import Column, Integer, String, ForeignKey
from app.core.database import Base

class Course(Base):
    __tablename__ = "course"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    course_code = Column(String(25), unique=True, nullable=False)
    course_name = Column(String(100), nullable=False)
    lecture_hours_per_week = Column(Integer, nullable=True)
    practical_hours_per_week = Column(Integer, nullable=True)
    lecturer_id = Column(Integer, nullable=False)

    # Optionally, created_at/updated_at fields can be added if needed
