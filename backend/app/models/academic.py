from sqlalchemy import (
    Boolean,
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


class Programme(Base):
    __tablename__ = "programme"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(16), nullable=False, unique=True, index=True)
    name = Column(String(255), nullable=False)
    duration_years = Column(Integer, nullable=True)
    intake_label = Column(String(100), nullable=True)
    programme_family = Column(String(64), nullable=True)
    is_direct_entry = Column(Boolean, nullable=False, default=False)
    notes = Column(Text, nullable=True)
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    paths = relationship(
        "ProgrammePath", back_populates="programme", cascade="all, delete-orphan"
    )
    contexts = relationship(
        "StudentProgrammeContext", back_populates="programme"
    )


class ProgrammePath(Base):
    __tablename__ = "programme_path"

    id = Column(Integer, primary_key=True, index=True)
    programme_id = Column(
        Integer, ForeignKey("programme.id", ondelete="CASCADE"), nullable=False
    )
    study_year = Column(Integer, nullable=False)
    code = Column(String(40), nullable=False)
    name = Column(String(255), nullable=False)
    is_common = Column(Boolean, nullable=False, default=False)
    raw_course_path_nos_json = Column(Text, nullable=False, default="[]")
    interpretation_confidence = Column(String(32), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    programme = relationship("Programme", back_populates="paths")
    contexts = relationship("StudentProgrammeContext", back_populates="programme_path")

    __table_args__ = (
        UniqueConstraint(
            "programme_id",
            "study_year",
            "code",
            name="uq_programme_path_programme_year_code",
        ),
    )


class CurriculumModule(Base):
    __tablename__ = "curriculum_module"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(32), nullable=False, index=True)
    canonical_code = Column(String(32), nullable=True, index=True)
    name = Column(String(255), nullable=False)
    subject_name = Column(String(120), nullable=False)
    subject_code = Column(String(32), nullable=True, index=True)
    nominal_year = Column(Integer, nullable=True)
    semester_bucket = Column(Integer, nullable=True)
    is_full_year = Column(Boolean, nullable=False, default=False)
    notes = Column(Text, nullable=True)
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    memberships = relationship(
        "StudentModuleMembership", back_populates="curriculum_module"
    )

    __table_args__ = (
        UniqueConstraint(
            "code",
            "nominal_year",
            "semester_bucket",
            name="uq_curriculum_module_code_year_semester",
        ),
    )


class StudentProgrammeContext(Base):
    __tablename__ = "student_programme_context"

    id = Column(Integer, primary_key=True, index=True)
    import_run_id = Column(
        Integer, ForeignKey("import_run.id", ondelete="CASCADE"), nullable=False
    )
    student_id = Column(
        Integer, ForeignKey("import_student.id", ondelete="CASCADE"), nullable=False
    )
    programme_id = Column(
        Integer, ForeignKey("programme.id", ondelete="RESTRICT"), nullable=False
    )
    programme_path_id = Column(
        Integer, ForeignKey("programme_path.id", ondelete="SET NULL"), nullable=True
    )
    academic_year = Column(String(16), nullable=False)
    study_year = Column(Integer, nullable=False)
    batch = Column(String(16), nullable=True)
    inferred_primary_path_code = Column(String(40), nullable=True)
    interpretation_confidence = Column(String(32), nullable=True)
    ambiguity_flags_json = Column(Text, nullable=False, default="[]")
    notes = Column(Text, nullable=True)
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    import_run = relationship("ImportRun")
    student = relationship("ImportStudent")
    programme = relationship("Programme", back_populates="contexts")
    programme_path = relationship("ProgrammePath", back_populates="contexts")
    memberships = relationship(
        "StudentModuleMembership", back_populates="student_programme_context"
    )

    __table_args__ = (
        UniqueConstraint(
            "import_run_id",
            "student_id",
            "academic_year",
            "study_year",
            "programme_id",
            name="uq_student_programme_context_run_student_year_programme",
        ),
    )


class StudentModuleMembership(Base):
    __tablename__ = "student_module_membership"

    id = Column(Integer, primary_key=True, index=True)
    import_run_id = Column(
        Integer, ForeignKey("import_run.id", ondelete="CASCADE"), nullable=False
    )
    student_id = Column(
        Integer, ForeignKey("import_student.id", ondelete="CASCADE"), nullable=False
    )
    student_programme_context_id = Column(
        Integer,
        ForeignKey("student_programme_context.id", ondelete="SET NULL"),
        nullable=True,
    )
    curriculum_module_id = Column(
        Integer, ForeignKey("curriculum_module.id", ondelete="CASCADE"), nullable=False
    )
    import_enrollment_id = Column(
        Integer, ForeignKey("import_enrollment.id", ondelete="SET NULL"), nullable=True
    )
    membership_source = Column(String(40), nullable=False, default="import")
    membership_role = Column(String(40), nullable=True)
    is_common_module = Column(Boolean, nullable=False, default=False)
    is_optional = Column(Boolean, nullable=False, default=False)
    interpretation_confidence = Column(String(32), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    import_run = relationship("ImportRun")
    student = relationship("ImportStudent")
    student_programme_context = relationship(
        "StudentProgrammeContext", back_populates="memberships"
    )
    curriculum_module = relationship(
        "CurriculumModule", back_populates="memberships"
    )
    import_enrollment = relationship("ImportEnrollment")

    __table_args__ = (
        UniqueConstraint(
            "import_run_id",
            "student_id",
            "curriculum_module_id",
            "import_enrollment_id",
            name="uq_student_module_membership_run_student_module_enrollment",
        ),
    )
