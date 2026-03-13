from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


SoftConstraint = Literal[
    "spread_sessions_across_days",
    "prefer_morning_theory",
    "prefer_afternoon_practicals",
    "avoid_late_afternoon_starts",
    "avoid_friday_sessions",
    "prefer_standard_block_starts",
    "balance_teaching_load_across_week",
    "avoid_monday_overload",
]
PerformancePreset = Literal["balanced", "thorough", "fast_diagnostics"]
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
    student_hashes: list[str] = Field(default_factory=list)


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
    linked_module_client_keys: list[str] = Field(default_factory=list)
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


class FullDatasetResponse(DatasetUpsertRequest):
    pass


class LookupItem(BaseModel):
    id: int
    label: str


class StudentPathLookupItem(BaseModel):
    id: int | None = None
    degree_id: int
    year: int
    label: str


class LookupResponse(BaseModel):
    lecturers: list[LookupItem]
    degrees: list[LookupItem]
    student_paths: list[StudentPathLookupItem]


class SoftConstraintOption(BaseModel):
    key: SoftConstraint
    label: str
    description: str


class GenerationRequest(BaseModel):
    import_run_id: int | None = Field(default=None, gt=0)
    soft_constraints: list[SoftConstraint] = Field(default_factory=list)
    performance_preset: PerformancePreset = "balanced"
    max_solutions: int = Field(default=1000, ge=1, le=5000)
    preview_limit: int = Field(default=5, ge=1, le=100)
    time_limit_seconds: int = Field(default=180, ge=1, le=600)


class GenerationCounts(BaseModel):
    total_solutions_found: int
    preview_solution_count: int
    truncated: bool


class PerformanceTimingResponse(BaseModel):
    precheck_ms: int = 0
    model_build_ms: int = 0
    solve_ms: int = 0
    fallback_search_ms: int = 0
    room_assignment_ms: int = 0
    total_ms: int = 0


class GenerationStatsResponse(BaseModel):
    task_count: int = 0
    assignment_variable_count: int = 0
    candidate_option_count: int = 0
    feasible_combo_count: int = 0
    fallback_combo_evaluated_count: int = 0
    fallback_combo_truncated: bool = False
    exact_enumeration_single_worker: bool = True
    machine_cpu_count: int = 1
    memory_limit_mb: int = 0
    projected_group_slot_blocker_count: int = 0
    slot_variable_count: int = 0
    room_assignment_retry_count: int = 0
    room_assignment_failures: int = 0
    room_assignment_ms: int = 0
    solver_engine: str = "legacy_guarded"
    domain_reduction_ratio: float = 0.0


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


class SoftConstraintCombinationSuggestion(BaseModel):
    constraints: list[SoftConstraint] = Field(default_factory=list)
    solution_count: int = 0
    solution_count_capped: bool = False


class GenerationResponse(BaseModel):
    generation_run_id: int
    status: str
    message: str
    counts: GenerationCounts
    performance_preset: PerformancePreset
    timing: PerformanceTimingResponse
    stats: GenerationStatsResponse
    selected_soft_constraints: list[SoftConstraint]
    available_soft_constraints: list[SoftConstraintOption]
    possible_soft_constraint_combinations: list[SoftConstraintCombinationSuggestion] = Field(
        default_factory=list
    )
    solutions: list[SolutionResponse]


class DefaultSelectionRequest(BaseModel):
    solution_id: int
    import_run_id: int | None = Field(default=None, gt=0)


class ViewResponse(BaseModel):
    mode: ViewMode
    title: str
    subtitle: str
    solution: SolutionResponse


class ExportResponse(BaseModel):
    filename: str
    content_type: str
    content: str


class ImportAnalysisSampleRow(BaseModel):
    row_number: int
    course_code: str
    stream: str
    year: str
    academic_year: str
    batch: str
    course_path_no: str
    student_hash: str
    anomaly_codes: list[str] = Field(default_factory=list)


class ImportAnalysisBucket(BaseModel):
    bucket_type: str
    bucket_key: str
    description: str
    status: str
    row_count: int
    sample_rows: list[ImportAnalysisSampleRow] = Field(default_factory=list)


class ImportAnalysisSummary(BaseModel):
    total_rows: int
    valid_rows: int
    valid_exception_rows: int
    ambiguous_rows: int
    invalid_rows: int
    included_rows: int
    excluded_rows: int
    unique_students: int
    review_bucket_count: int


class ImportAnalysisResponse(BaseModel):
    source_file: str
    summary: ImportAnalysisSummary
    anomaly_counts: dict[str, int] = Field(default_factory=dict)
    semester_digit_counts: dict[str, int] = Field(default_factory=dict)
    buckets: list[ImportAnalysisBucket] = Field(default_factory=list)


class ImportReviewRuleInput(BaseModel):
    bucket_type: str = Field(..., min_length=1)
    bucket_key: str = Field(..., min_length=1)
    action: Literal["accept_exception", "exclude", "treat_as_common"]
    label: str | None = None


class ImportProjectionRequest(BaseModel):
    rules: list[ImportReviewRuleInput] = Field(default_factory=list)
    target_academic_year: str | None = None
    allowed_attempts: list[str] = Field(default_factory=lambda: ["1"])


class ImportProjectionSummary(BaseModel):
    projected_rows: int
    excluded_rows: int
    degrees: int
    paths: int
    lecturers: int
    rooms: int
    student_groups: int
    modules: int
    sessions: int


class ImportProjectionResponse(BaseModel):
    analysis: ImportAnalysisResponse
    target_academic_year: str | None = None
    allowed_attempts: list[str] = Field(default_factory=list)
    projection_summary: ImportProjectionSummary
    dataset: FullDatasetResponse


class MaterializedImportCounts(BaseModel):
    rows: int
    students: int
    enrollments: int
    programmes: int
    programme_paths: int
    curriculum_modules: int
    student_programme_contexts: int
    student_module_memberships: int
    attendance_groups: int


class MaterializedImportResponse(BaseModel):
    import_run_id: int
    source_file: str
    status: str
    selected_academic_year: str | None = None
    allowed_attempts: list[str] = Field(default_factory=list)
    counts: MaterializedImportCounts


class SnapshotSeedResponse(BaseModel):
    import_run_id: int
    lecturers_created: int = 0
    rooms_created: int = 0
    shared_sessions_created: int = 0


class SnapshotLecturerInput(BaseModel):
    client_key: str | None = Field(default=None, min_length=1)
    name: str = Field(..., min_length=1)
    email: str | None = None
    notes: str | None = None


class SnapshotLecturerResponse(BaseModel):
    id: int
    import_run_id: int
    client_key: str | None = None
    name: str
    email: str | None = None
    notes: str | None = None


class SnapshotLecturerBatchInput(BaseModel):
    lecturers: list[SnapshotLecturerInput] = Field(default_factory=list)


class SnapshotLecturerBatchResponse(BaseModel):
    lecturers: list[SnapshotLecturerResponse] = Field(default_factory=list)


class SnapshotRoomInput(BaseModel):
    client_key: str | None = Field(default=None, min_length=1)
    name: str = Field(..., min_length=1)
    capacity: int = Field(..., gt=0)
    room_type: str = Field(..., min_length=1)
    lab_type: str | None = None
    location: str = Field(..., min_length=1)
    year_restriction: int | None = Field(default=None, ge=1, le=6)
    notes: str | None = None


class SnapshotRoomResponse(BaseModel):
    id: int
    import_run_id: int
    client_key: str | None = None
    name: str
    capacity: int
    room_type: str
    lab_type: str | None = None
    location: str
    year_restriction: int | None = None
    notes: str | None = None


class SnapshotRoomBatchInput(BaseModel):
    rooms: list[SnapshotRoomInput] = Field(default_factory=list)


class SnapshotRoomBatchResponse(BaseModel):
    rooms: list[SnapshotRoomResponse] = Field(default_factory=list)


class SnapshotSharedSessionInput(BaseModel):
    client_key: str | None = Field(default=None, min_length=1)
    name: str = Field(..., min_length=1)
    session_type: str = Field(..., min_length=1)
    duration_minutes: int = Field(..., gt=0, multiple_of=30)
    occurrences_per_week: int = Field(..., gt=0, le=10)
    required_room_type: str | None = None
    required_lab_type: str | None = None
    specific_room_id: int | None = Field(default=None, gt=0)
    max_students_per_group: int | None = Field(default=None, gt=0)
    allow_parallel_rooms: bool = False
    notes: str | None = None
    lecturer_ids: list[int] = Field(default_factory=list)
    curriculum_module_ids: list[int] = Field(default_factory=list)
    attendance_group_ids: list[int] = Field(default_factory=list)


class SnapshotSharedSessionResponse(BaseModel):
    id: int
    import_run_id: int
    client_key: str | None = None
    name: str
    session_type: str
    duration_minutes: int
    occurrences_per_week: int
    required_room_type: str | None = None
    required_lab_type: str | None = None
    specific_room_id: int | None = None
    max_students_per_group: int | None = None
    allow_parallel_rooms: bool
    notes: str | None = None
    lecturer_ids: list[int] = Field(default_factory=list)
    curriculum_module_ids: list[int] = Field(default_factory=list)
    attendance_group_ids: list[int] = Field(default_factory=list)


class SnapshotSharedSessionBatchInput(BaseModel):
    shared_sessions: list[SnapshotSharedSessionInput] = Field(default_factory=list)


class SnapshotSharedSessionBatchResponse(BaseModel):
    shared_sessions: list[SnapshotSharedSessionResponse] = Field(default_factory=list)


class SnapshotCompletionResponse(BaseModel):
    import_run_id: int
    lecturers: list[SnapshotLecturerResponse] = Field(default_factory=list)
    rooms: list[SnapshotRoomResponse] = Field(default_factory=list)
    shared_sessions: list[SnapshotSharedSessionResponse] = Field(default_factory=list)


class ImportWorkspaceProgrammeResponse(BaseModel):
    id: int
    code: str
    name: str
    duration_years: int | None = None
    intake_label: str | None = None


class ImportWorkspaceProgrammePathResponse(BaseModel):
    id: int
    programme_id: int
    study_year: int
    code: str
    name: str
    is_common: bool = False


class ImportWorkspaceCurriculumModuleResponse(BaseModel):
    id: int
    code: str
    name: str
    subject_name: str
    nominal_year: int | None = None
    semester_bucket: int | None = None
    is_full_year: bool = False
    attendance_group_ids: list[int] = Field(default_factory=list)


class ImportWorkspaceAttendanceGroupResponse(BaseModel):
    id: int
    programme_id: int | None = None
    programme_path_id: int | None = None
    academic_year: str | None = None
    study_year: int | None = None
    label: str
    student_count: int


class ImportWorkspaceResponse(BaseModel):
    import_run_id: int
    selected_academic_year: str | None = None
    programmes: list[ImportWorkspaceProgrammeResponse] = Field(default_factory=list)
    programme_paths: list[ImportWorkspaceProgrammePathResponse] = Field(default_factory=list)
    curriculum_modules: list[ImportWorkspaceCurriculumModuleResponse] = Field(
        default_factory=list
    )
    attendance_groups: list[ImportWorkspaceAttendanceGroupResponse] = Field(
        default_factory=list
    )
    lecturers: list[SnapshotLecturerResponse] = Field(default_factory=list)
    rooms: list[SnapshotRoomResponse] = Field(default_factory=list)
    shared_sessions: list[SnapshotSharedSessionResponse] = Field(default_factory=list)
