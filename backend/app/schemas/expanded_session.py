from pydantic import BaseModel


class ExpandedSessionRead(BaseModel):
    session_id: int
    module_id: int
    session_type: str
    duration_hours: int
    frequency_per_week: int
    requires_lab_type: str | None
    student_count: int
    max_students_per_group: int | None
    concurrent_split: bool
    lecturer_ids: list[int]
    year: int
    pathway_ids: list[int]
    group_number: int
    group_size: int
