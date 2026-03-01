from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.models.associations import pathway_subject_table


class Pathway(Base):
    __tablename__ = "pathway"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    department_id = Column(Integer, ForeignKey("department.id"), nullable=False)
    year = Column(Integer, nullable=False)

    department = relationship("Department")
    subjects = relationship("Subject", secondary=pathway_subject_table, back_populates="pathways")
