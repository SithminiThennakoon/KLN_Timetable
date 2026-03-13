from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class SnapshotGenerationRun(Base):
    __tablename__ = "snapshot_generation_run"

    id = Column(Integer, primary_key=True, index=True)
    import_run_id = Column(
        Integer, ForeignKey("import_run.id", ondelete="CASCADE"), nullable=False
    )
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

    import_run = relationship("ImportRun")
    solutions = relationship(
        "SnapshotTimetableSolution",
        back_populates="generation_run",
        cascade="all, delete-orphan",
    )


class SnapshotTimetableSolution(Base):
    __tablename__ = "snapshot_timetable_solution"

    id = Column(Integer, primary_key=True, index=True)
    generation_run_id = Column(
        Integer,
        ForeignKey("snapshot_generation_run.id", ondelete="CASCADE"),
        nullable=False,
    )
    ordinal = Column(Integer, nullable=False)
    is_default = Column(Boolean, nullable=False, default=False)
    is_representative = Column(Boolean, nullable=False, default=False)
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    generation_run = relationship("SnapshotGenerationRun", back_populates="solutions")
    entries = relationship(
        "SnapshotSolutionEntry",
        back_populates="solution",
        cascade="all, delete-orphan",
    )


class SnapshotSolutionEntry(Base):
    __tablename__ = "snapshot_solution_entry"
    __mapper_args__ = {"eager_defaults": False}

    id = Column(Integer, primary_key=True, index=True)
    solution_id = Column(
        Integer,
        ForeignKey("snapshot_timetable_solution.id", ondelete="CASCADE"),
        nullable=False,
    )
    shared_session_id = Column(
        Integer,
        ForeignKey("snapshot_shared_session.id", ondelete="CASCADE"),
        nullable=False,
    )
    room_id = Column(
        Integer, ForeignKey("snapshot_room.id", ondelete="CASCADE"), nullable=False
    )
    day = Column(String(20), nullable=False)
    start_minute = Column(Integer, nullable=False)
    duration_minutes = Column(Integer, nullable=False)
    occurrence_index = Column(Integer, nullable=False)
    split_index = Column(Integer, nullable=False)
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    solution = relationship("SnapshotTimetableSolution", back_populates="entries")
    shared_session = relationship("SnapshotSharedSession")
    room = relationship("SnapshotRoom")
