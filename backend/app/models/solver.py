from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class AttendanceGroup(Base):
    __tablename__ = "attendance_group"

    id = Column(Integer, primary_key=True, index=True)
    import_run_id = Column(
        Integer, ForeignKey("import_run.id", ondelete="CASCADE"), nullable=False
    )
    academic_year = Column(String(16), nullable=False)
    study_year = Column(Integer, nullable=True)
    programme_id = Column(
        Integer, ForeignKey("programme.id", ondelete="SET NULL"), nullable=True
    )
    programme_path_id = Column(
        Integer, ForeignKey("programme_path.id", ondelete="SET NULL"), nullable=True
    )
    label = Column(String(255), nullable=False)
    derivation_basis = Column(String(64), nullable=False, default="student_membership")
    membership_signature = Column(String(40), nullable=False)
    interpretation_confidence = Column(String(32), nullable=True)
    student_count = Column(Integer, nullable=False, default=0)
    notes = Column(Text, nullable=True)
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    import_run = relationship("ImportRun")
    programme = relationship("Programme")
    programme_path = relationship("ProgrammePath")
    students = relationship(
        "AttendanceGroupStudent",
        back_populates="attendance_group",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        UniqueConstraint(
            "import_run_id",
            "academic_year",
            "membership_signature",
            name="uq_attendance_group_run_year_signature",
        ),
    )


class AttendanceGroupStudent(Base):
    __tablename__ = "attendance_group_student"

    id = Column(Integer, primary_key=True, index=True)
    attendance_group_id = Column(
        Integer, ForeignKey("attendance_group.id", ondelete="CASCADE"), nullable=False
    )
    student_id = Column(
        Integer, ForeignKey("import_student.id", ondelete="CASCADE"), nullable=False
    )
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    attendance_group = relationship(
        "AttendanceGroup", back_populates="students"
    )
    student = relationship("ImportStudent")

    __table_args__ = (
        UniqueConstraint(
            "attendance_group_id",
            "student_id",
            name="uq_attendance_group_student_group_student",
        ),
    )
