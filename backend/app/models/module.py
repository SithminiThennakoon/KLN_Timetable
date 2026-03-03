from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base


class Module(Base):
    __tablename__ = "module"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(25), nullable=False, unique=True)
    name = Column(String(200), nullable=False)
    subject_id = Column(Integer, ForeignKey("subject.id"), nullable=False)
    year = Column(Integer, nullable=False)
    semester = Column(Integer, nullable=False)

    subject = relationship("Subject")
    sessions = relationship("Session", back_populates="module", cascade="all, delete-orphan")
