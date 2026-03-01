from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.models.associations import pathway_subject_table


class Subject(Base):
    __tablename__ = "subject"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    code = Column(String(10), nullable=False)
    department_id = Column(Integer, ForeignKey("department.id"), nullable=False)

    department = relationship("Department")
    pathways = relationship("Pathway", secondary=pathway_subject_table, back_populates="subjects")
