from sqlalchemy import Table, Column, Integer, ForeignKey
from app.core.database import Base

pathway_subject_table = Table(
    "pathway_subject",
    Base.metadata,
    Column("pathway_id", Integer, ForeignKey("pathway.id"), primary_key=True),
    Column("subject_id", Integer, ForeignKey("subject.id"), primary_key=True),
)

session_lecturer_table = Table(
    "session_lecturer",
    Base.metadata,
    Column("session_id", Integer, ForeignKey("session.id"), primary_key=True),
    Column("lecturer_id", Integer, ForeignKey("lecturer.id"), primary_key=True),
)
