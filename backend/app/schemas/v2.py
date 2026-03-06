from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


SoftConstraint = Literal["spread_sessions_across_days"]
ViewMode = Literal["admin", "lecturer", "student"]


class DegreeInput(BaseModel):
    client_key: str = Field(..., min_length=1)
    code: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)
    duration_years: int = Field(..., ge=1, le=6)
    intake_label: str = Field(..., min_length=1)


class PathInput(BaseModel):
    client_key: str = Field(..., min_length=1)
    degree_client_key: str = Field(..., min_length=1)
    year: int = Field(..., ge=1, le=6)
    code: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)


class LecturerInput(BaseModel):
    client_key: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)
    email: str | None = None


class RoomInput(BaseModel):
    client_key: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)
    capacity: int = Field(..., gt=0)
    room_type: str = Field(..., min_length=1)
    lab_type: str | None = None
    location: str = Field(..., min_length=1)
    year_restriction: int | None = Field(default=None, ge=1, le=6)


class StudentGroupInput(BaseModel):
    client_key: str = Field(..., min_length=1)
    degree_client_key: str = Field(..., min_length=1)
    path_client_key: str | None = None
    year: int = Field(..., ge=1, le=6)
    name: str = Field(..., min_length=1)
    size: int = Field(..., gt=0)


class ModuleInput(BaseModel):
    client_key: str = Field(..., min_length=1)
    code: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)
    subject_name: str = Field(..., min_length=1)
    year: int = Field(..., ge=1, le=6)
    semester: int = Field(..., ge=1, le=2)
    is_full_year: bool = False


class SessionInput(BaseModel):
    client_key: str = Field(..., min_length=1)
    module_client_key: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)
    session_type: str = Field(..., min_length=1)
    duration_minutes: int = Field(..., gt=0, multiple_of=30)
    occurrences_per_week: int = Field(..., gt=0, le=10)
    required_room_type: str | None = None
    required_lab_type: str | None = None
    specific_room_client_key: str | None = None
    max_students_per_group: int | None = Field(default=None, gt=0)
    allow_parallel_rooms: bool = False
    notes: str | None = None
    lecturer_client_keys: list[str] = Field(default_factory=list)
    student_group_client_keys: list[str] = Field(default_factory=list)


class DatasetUpsertRequest(BaseModel):
    degrees: list[DegreeInput] = Field(default_factory=list)
    paths: list[PathInput] = Field(default_factory=list)
    lecturers: list[LecturerInput] = Field(default_factory=list)
    rooms: list[RoomInput] = Field(default_factory=list)
    student_groups: list[StudentGroupInput] = Field(default_factory=list)
    modules: list[ModuleInput] = Field(default_factory=list)
    sessions: list[SessionInput] = Field(default_factory=list)


class DatasetSummary(BaseModel):
    degrees: int
    paths: int
    lecturers: int
    rooms: int
    student_groups: int
    modules: int
    sessions: int


class DatasetResponse(BaseModel):
    summary: DatasetSummary


class LookupItem(BaseModel):
    id: int
    label: str


class LookupResponse(BaseModel):
    lecturers: list[LookupItem]
    student_groups: list[LookupItem]


class SoftConstraintOption(BaseModel):
    key: SoftConstraint
    label: str
    description: str


class GenerationRequest(BaseModel):
    soft_constraints: list[SoftConstraint] = Field(default_factory=list)
    max_solutions: int = Field(default=1000, ge=1, le=5000)
    preview_limit: int = Field(default=5, ge=1, le=100)
    time_limit_seconds: int = Field(default=60, ge=1, le=300)


class GenerationCounts(BaseModel):
    total_solutions_found: int
    preview_solution_count: int
    truncated: bool


class SolutionEntryResponse(BaseModel):
    session_id: int
    session_name: str
    module_code: str
    module_name: str
    room_name: str
    room_location: str
    day: str
    start_minute: int
    duration_minutes: int
    occurrence_index: int
    split_index: int
    lecturer_names: list[str]
    student_group_names: list[str]
    degree_path_labels: list[str]
    total_students: int


class SolutionResponse(BaseModel):
    solution_id: int
    ordinal: int
    is_default: bool
    is_representative: bool
    entries: list[SolutionEntryResponse]


class GenerationResponse(BaseModel):
    generation_run_id: int
    status: str
    message: str
    counts: GenerationCounts
    selected_soft_constraints: list[SoftConstraint]
    available_soft_constraints: list[SoftConstraintOption]
    possible_soft_constraint_combinations: list[list[SoftConstraint]] = Field(
        default_factory=list
    )
    solutions: list[SolutionResponse]


class DefaultSelectionRequest(BaseModel):
    solution_id: int


class ViewResponse(BaseModel):
    mode: ViewMode
    title: str
    subtitle: str
    solution: SolutionResponse


class ExportResponse(BaseModel):
    filename: str
    content_type: str
    content: str
