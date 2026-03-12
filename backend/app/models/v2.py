from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Table,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


v2_session_lecturer_table = Table(
    "v2_session_lecturer",
    Base.metadata,
    Column(
        "session_id",
        Integer,
        ForeignKey("v2_session.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "lecturer_id",
        Integer,
        ForeignKey("v2_lecturer.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


v2_session_student_group_table = Table(
    "v2_session_student_group",
    Base.metadata,
    Column(
        "session_id",
        Integer,
        ForeignKey("v2_session.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "student_group_id",
        Integer,
        ForeignKey("v2_student_group.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)

v2_session_module_table = Table(
    "v2_session_module",
    Base.metadata,
    Column(
        "session_id",
        Integer,
        ForeignKey("v2_session.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "module_id",
        Integer,
        ForeignKey("v2_module.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


class V2Degree(Base):
    __tablename__ = "v2_degree"

    id = Column(Integer, primary_key=True, index=True)
    client_key = Column(String(64), nullable=False, unique=True, index=True)
    code = Column(String(20), nullable=False, unique=True)
    name = Column(String(200), nullable=False)
    duration_years = Column(Integer, nullable=False)
    intake_label = Column(String(100), nullable=False)
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    paths = relationship(
        "V2Path", back_populates="degree", cascade="all, delete-orphan"
    )
    student_groups = relationship(
        "V2StudentGroup", back_populates="degree", cascade="all, delete-orphan"
    )


class V2Path(Base):
    __tablename__ = "v2_path"

    id = Column(Integer, primary_key=True, index=True)
    client_key = Column(String(64), nullable=False, unique=True, index=True)
    degree_id = Column(
        Integer, ForeignKey("v2_degree.id", ondelete="CASCADE"), nullable=False
    )
    year = Column(Integer, nullable=False)
    code = Column(String(40), nullable=False)
    name = Column(String(200), nullable=False)
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    degree = relationship("V2Degree", back_populates="paths")
    student_groups = relationship("V2StudentGroup", back_populates="path")

    __table_args__ = (
        UniqueConstraint(
            "degree_id", "year", "code", name="uq_v2_path_degree_year_code"
        ),
    )


class V2Lecturer(Base):
    __tablename__ = "v2_lecturer"

    id = Column(Integer, primary_key=True, index=True)
    client_key = Column(String(64), nullable=False, unique=True, index=True)
    name = Column(String(200), nullable=False)
    email = Column(String(255), nullable=True)
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    sessions = relationship(
        "V2Session", secondary=v2_session_lecturer_table, back_populates="lecturers"
    )


class V2Room(Base):
    __tablename__ = "v2_room"

    id = Column(Integer, primary_key=True, index=True)
    client_key = Column(String(64), nullable=False, unique=True, index=True)
    name = Column(String(100), nullable=False, unique=True)
    capacity = Column(Integer, nullable=False)
    room_type = Column(String(30), nullable=False)
    lab_type = Column(String(50), nullable=True)
    location = Column(String(100), nullable=False)
    year_restriction = Column(Integer, nullable=True)
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class V2StudentGroup(Base):
    __tablename__ = "v2_student_group"

    id = Column(Integer, primary_key=True, index=True)
    client_key = Column(String(64), nullable=False, unique=True, index=True)
    degree_id = Column(
        Integer, ForeignKey("v2_degree.id", ondelete="CASCADE"), nullable=False
    )
    path_id = Column(
        Integer, ForeignKey("v2_path.id", ondelete="SET NULL"), nullable=True
    )
    year = Column(Integer, nullable=False)
    name = Column(String(200), nullable=False)
    size = Column(Integer, nullable=False)
    student_hashes_json = Column(Text, nullable=True)
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    degree = relationship("V2Degree", back_populates="student_groups")
    path = relationship("V2Path", back_populates="student_groups")
    sessions = relationship(
        "V2Session",
        secondary=v2_session_student_group_table,
        back_populates="student_groups",
    )


class V2Module(Base):
    __tablename__ = "v2_module"

    id = Column(Integer, primary_key=True, index=True)
    client_key = Column(String(64), nullable=False, unique=True, index=True)
    code = Column(String(30), nullable=False, unique=True)
    name = Column(String(200), nullable=False)
    subject_name = Column(String(120), nullable=False)
    year = Column(Integer, nullable=False)
    semester = Column(Integer, nullable=False)
    is_full_year = Column(Boolean, default=False, nullable=False)
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    sessions = relationship(
        "V2Session", back_populates="module", cascade="all, delete-orphan"
    )
    linked_sessions = relationship(
        "V2Session",
        secondary=v2_session_module_table,
        back_populates="linked_modules",
    )


class V2Session(Base):
    __tablename__ = "v2_session"

    id = Column(Integer, primary_key=True, index=True)
    client_key = Column(String(64), nullable=False, unique=True, index=True)
    module_id = Column(
        Integer, ForeignKey("v2_module.id", ondelete="CASCADE"), nullable=False
    )
    name = Column(String(200), nullable=False)
    session_type = Column(String(30), nullable=False)
    duration_minutes = Column(Integer, nullable=False)
    occurrences_per_week = Column(Integer, nullable=False)
    required_room_type = Column(String(30), nullable=True)
    required_lab_type = Column(String(50), nullable=True)
    specific_room_id = Column(
        Integer, ForeignKey("v2_room.id", ondelete="SET NULL"), nullable=True
    )
    max_students_per_group = Column(Integer, nullable=True)
    allow_parallel_rooms = Column(Boolean, default=False, nullable=False)
    notes = Column(Text, nullable=True)
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    module = relationship("V2Module", back_populates="sessions")
    linked_modules = relationship(
        "V2Module",
        secondary=v2_session_module_table,
        back_populates="linked_sessions",
    )
    specific_room = relationship("V2Room")
    lecturers = relationship(
        "V2Lecturer", secondary=v2_session_lecturer_table, back_populates="sessions"
    )
    student_groups = relationship(
        "V2StudentGroup",
        secondary=v2_session_student_group_table,
        back_populates="sessions",
    )


class V2GenerationRun(Base):
    __tablename__ = "v2_generation_run"

    id = Column(Integer, primary_key=True, index=True)
    status = Column(String(40), nullable=False)
    selected_soft_constraints = Column(Text, nullable=False, default="")
    total_solutions_found = Column(Integer, nullable=False, default=0)
    truncated = Column(Boolean, nullable=False, default=False)
    max_solutions = Column(Integer, nullable=False, default=1000)
    time_limit_seconds = Column(Integer, nullable=False, default=180)
    message = Column(Text, nullable=True)
    possible_soft_constraint_combinations = Column(Text, nullable=False, default="")
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    solutions = relationship(
        "V2TimetableSolution",
        back_populates="generation_run",
        cascade="all, delete-orphan",
    )


class V2TimetableSolution(Base):
    __tablename__ = "v2_timetable_solution"

    id = Column(Integer, primary_key=True, index=True)
    generation_run_id = Column(
        Integer, ForeignKey("v2_generation_run.id", ondelete="CASCADE"), nullable=False
    )
    ordinal = Column(Integer, nullable=False)
    is_default = Column(Boolean, nullable=False, default=False)
    is_representative = Column(Boolean, nullable=False, default=False)
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    generation_run = relationship("V2GenerationRun", back_populates="solutions")
    entries = relationship(
        "V2SolutionEntry", back_populates="solution", cascade="all, delete-orphan"
    )


class V2SolutionEntry(Base):
    __tablename__ = "v2_solution_entry"
    __mapper_args__ = {"eager_defaults": False}

    id = Column(Integer, primary_key=True, index=True)
    solution_id = Column(
        Integer,
        ForeignKey("v2_timetable_solution.id", ondelete="CASCADE"),
        nullable=False,
    )
    session_id = Column(
        Integer, ForeignKey("v2_session.id", ondelete="CASCADE"), nullable=False
    )
    occurrence_index = Column(Integer, nullable=False)
    split_index = Column(Integer, nullable=False)
    room_id = Column(
        Integer, ForeignKey("v2_room.id", ondelete="CASCADE"), nullable=False
    )
    day = Column(String(20), nullable=False)
    start_minute = Column(Integer, nullable=False)
    duration_minutes = Column(Integer, nullable=False)
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    solution = relationship("V2TimetableSolution", back_populates="entries")
    session = relationship("V2Session")
    room = relationship("V2Room")
