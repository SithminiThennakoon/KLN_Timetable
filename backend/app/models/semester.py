from sqlalchemy import Column, Integer, String, DateTime
from app.core.database import Base
from sqlalchemy.sql import func

class Semester(Base):
    __tablename__ = "semester"

    Semester_ID = Column(Integer, primary_key=True, index=True, autoincrement=True)
    Semester_name = Column(String(50), nullable=False)
    Academic_year = Column(String(20), nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())

    model_config = {"from_attributes": True}
