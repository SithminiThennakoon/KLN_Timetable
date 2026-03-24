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


snapshot_shared_session_lecturer_table = Table(
    "snapshot_shared_session_lecturer",
    Base.metadata,
    Column(
        "shared_session_id",
        Integer,
        ForeignKey("snapshot_shared_session.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "lecturer_id",
        Integer,
        ForeignKey("snapshot_lecturer.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


snapshot_shared_session_module_table = Table(
    "snapshot_shared_session_module",
    Base.metadata,
    Column(
        "shared_session_id",
        Integer,
        ForeignKey("snapshot_shared_session.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "curriculum_module_id",
        Integer,
        ForeignKey("curriculum_module.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


snapshot_shared_session_attendance_group_table = Table(
    "snapshot_shared_session_attendance_group",
    Base.metadata,
    Column(
        "shared_session_id",
        Integer,
        ForeignKey("snapshot_shared_session.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "attendance_group_id",
        Integer,
        ForeignKey("attendance_group.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


class SnapshotLecturer(Base):
    __tablename__ = "snapshot_lecturer"

    id = Column(Integer, primary_key=True, index=True)
    import_run_id = Column(
        Integer, ForeignKey("import_run.id", ondelete="CASCADE"), nullable=False
    )
    client_key = Column(String(64), nullable=True)
    name = Column(String(200), nullable=False)
    email = Column(String(255), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    import_run = relationship("ImportRun")
    sessions = relationship(
        "SnapshotSharedSession",
        secondary=snapshot_shared_session_lecturer_table,
        back_populates="lecturers",
    )

    __table_args__ = (
        UniqueConstraint(
            "import_run_id",
            "name",
            name="uq_snapshot_lecturer_run_name",
        ),
    )


class SnapshotRoom(Base):
    __tablename__ = "snapshot_room"

    id = Column(Integer, primary_key=True, index=True)
    import_run_id = Column(
        Integer, ForeignKey("import_run.id", ondelete="CASCADE"), nullable=False
    )
    client_key = Column(String(64), nullable=True)
    name = Column(String(100), nullable=False)
    capacity = Column(Integer, nullable=False)
    room_type = Column(String(30), nullable=False)
    lab_type = Column(String(50), nullable=True)
    location = Column(String(100), nullable=False)
    year_restriction = Column(Integer, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    import_run = relationship("ImportRun")
    specific_sessions = relationship(
        "SnapshotSharedSession", back_populates="specific_room"
    )

    __table_args__ = (
        UniqueConstraint(
            "import_run_id",
            "name",
            name="uq_snapshot_room_run_name",
        ),
    )


class SnapshotSharedSession(Base):
    __tablename__ = "snapshot_shared_session"

    id = Column(Integer, primary_key=True, index=True)
    import_run_id = Column(
        Integer, ForeignKey("import_run.id", ondelete="CASCADE"), nullable=False
    )
    client_key = Column(String(64), nullable=True)
    name = Column(String(200), nullable=False)
    session_type = Column(String(30), nullable=False)
    duration_minutes = Column(Integer, nullable=False)
    occurrences_per_week = Column(Integer, nullable=False)
    required_room_type = Column(String(30), nullable=True)
    required_lab_type = Column(String(50), nullable=True)
    specific_room_id = Column(
        Integer,
        ForeignKey("snapshot_room.id", ondelete="SET NULL"),
        nullable=True,
    )
    max_students_per_group = Column(Integer, nullable=True)
    allow_parallel_rooms = Column(Boolean, nullable=False, default=False)
    notes = Column(Text, nullable=True)
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    import_run = relationship("ImportRun")
    specific_room = relationship("SnapshotRoom", back_populates="specific_sessions")
    lecturers = relationship(
        "SnapshotLecturer",
        secondary=snapshot_shared_session_lecturer_table,
        back_populates="sessions",
    )
    curriculum_modules = relationship(
        "CurriculumModule",
        secondary=snapshot_shared_session_module_table,
    )
    attendance_groups = relationship(
        "AttendanceGroup",
        secondary=snapshot_shared_session_attendance_group_table,
    )

    __table_args__ = (
        UniqueConstraint(
            "import_run_id",
            "name",
            "session_type",
            name="uq_snapshot_shared_session_run_name_type",
        ),
    )
