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


class ImportRun(Base):
    __tablename__ = "import_run"

    id = Column(Integer, primary_key=True, index=True)
    source_file = Column(String(255), nullable=False)
    source_format = Column(String(64), nullable=False, default="uok_fos_enrollment_csv")
    status = Column(String(40), nullable=False, default="analyzed")
    selected_academic_year = Column(String(20), nullable=True)
    allowed_attempts_json = Column(Text, nullable=False, default='["1"]')
    notes = Column(Text, nullable=True)
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    rows = relationship(
        "ImportRow", back_populates="import_run", cascade="all, delete-orphan"
    )
    enrollments = relationship(
        "ImportEnrollment", back_populates="import_run", cascade="all, delete-orphan"
    )
    review_rules = relationship(
        "ImportReviewRule", back_populates="import_run", cascade="all, delete-orphan"
    )


class ImportStudent(Base):
    __tablename__ = "import_student"

    id = Column(Integer, primary_key=True, index=True)
    student_hash = Column(String(64), nullable=False, unique=True, index=True)
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    rows = relationship("ImportRow", back_populates="student")
    enrollments = relationship("ImportEnrollment", back_populates="student")


class ImportReviewRule(Base):
    __tablename__ = "import_review_rule"

    id = Column(Integer, primary_key=True, index=True)
    import_run_id = Column(
        Integer, ForeignKey("import_run.id", ondelete="CASCADE"), nullable=False
    )
    bucket_type = Column(String(100), nullable=False)
    bucket_key = Column(String(255), nullable=False)
    action = Column(String(40), nullable=False)
    label = Column(String(255), nullable=True)
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    import_run = relationship("ImportRun", back_populates="review_rules")

    __table_args__ = (
        UniqueConstraint(
            "import_run_id",
            "bucket_type",
            "bucket_key",
            "action",
            name="uq_import_review_rule_run_bucket_action",
        ),
    )


class ImportRow(Base):
    __tablename__ = "import_row"

    id = Column(Integer, primary_key=True, index=True)
    import_run_id = Column(
        Integer, ForeignKey("import_run.id", ondelete="CASCADE"), nullable=False
    )
    student_id = Column(
        Integer, ForeignKey("import_student.id", ondelete="SET NULL"), nullable=True
    )
    row_number = Column(Integer, nullable=False)
    raw_course_path_no = Column(String(32), nullable=True)
    raw_course_code = Column(String(32), nullable=True)
    raw_year = Column(String(16), nullable=True)
    raw_academic_year = Column(String(16), nullable=True)
    raw_attempt = Column(String(16), nullable=True)
    raw_stream = Column(String(16), nullable=True)
    raw_batch = Column(String(16), nullable=True)
    raw_student_hash = Column(String(64), nullable=True)
    module_subject_code = Column(String(32), nullable=True)
    module_nominal_year = Column(Integer, nullable=True)
    module_nominal_semester_code = Column(String(8), nullable=True)
    module_nominal_semester = Column(Integer, nullable=True)
    is_full_year = Column(Boolean, nullable=False, default=False)
    anomaly_codes_json = Column(Text, nullable=False, default="[]")
    resolved_anomaly_codes_json = Column(Text, nullable=False, default="[]")
    matched_rule_actions_json = Column(Text, nullable=False, default="[]")
    review_status = Column(String(40), nullable=False, default="valid")
    effective_course_path_no = Column(String(32), nullable=True)
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    import_run = relationship("ImportRun", back_populates="rows")
    student = relationship("ImportStudent", back_populates="rows")
    enrollment = relationship(
        "ImportEnrollment", back_populates="import_row", uselist=False
    )

    __table_args__ = (
        UniqueConstraint(
            "import_run_id", "row_number", name="uq_import_row_run_row_number"
        ),
    )


class ImportEnrollment(Base):
    __tablename__ = "import_enrollment"

    id = Column(Integer, primary_key=True, index=True)
    import_run_id = Column(
        Integer, ForeignKey("import_run.id", ondelete="CASCADE"), nullable=False
    )
    import_row_id = Column(
        Integer, ForeignKey("import_row.id", ondelete="CASCADE"), nullable=False
    )
    student_id = Column(
        Integer, ForeignKey("import_student.id", ondelete="SET NULL"), nullable=True
    )
    academic_year = Column(String(16), nullable=True)
    attempt = Column(String(16), nullable=True)
    stream_code = Column(String(16), nullable=True)
    study_year = Column(Integer, nullable=True)
    batch = Column(String(16), nullable=True)
    raw_course_path_no = Column(String(32), nullable=True)
    effective_course_path_no = Column(String(32), nullable=True)
    course_code = Column(String(32), nullable=True)
    module_subject_code = Column(String(32), nullable=True)
    module_nominal_year = Column(Integer, nullable=True)
    module_nominal_semester_code = Column(String(8), nullable=True)
    module_nominal_semester = Column(Integer, nullable=True)
    is_full_year = Column(Boolean, nullable=False, default=False)
    review_status = Column(String(40), nullable=False, default="valid")
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    import_run = relationship("ImportRun", back_populates="enrollments")
    import_row = relationship("ImportRow", back_populates="enrollment")
    student = relationship("ImportStudent", back_populates="enrollments")

    __table_args__ = (
        UniqueConstraint(
            "import_row_id", name="uq_import_enrollment_row"
        ),
    )
