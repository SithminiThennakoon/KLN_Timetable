from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.sql import func
from app.core.database import Base

class Group(Base):
    __tablename__ = "group"

    Group_ID = Column(Integer, primary_key=True, index=True, autoincrement=True)
    Group_name = Column(String(100), nullable=False)
    Semester_Semester_ID = Column(Integer, ForeignKey("semester.Semester_ID"), nullable=False)
    Student_count = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    model_config = {"from_attributes": True}
