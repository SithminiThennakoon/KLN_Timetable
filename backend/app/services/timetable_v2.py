from __future__ import annotations

import base64
import csv
import io
import itertools
import json
import os
import time
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Iterable

from ortools.sat.python import cp_model
from sqlalchemy import insert
from sqlalchemy.orm import Session, joinedload

from app.core.database import engine
from app.models.imports import ImportStudent
from app.models.academic import Programme, ProgrammePath
from app.models.snapshot import SnapshotLecturer, SnapshotRoom, SnapshotSharedSession
from app.models.snapshot_generation import (
    SnapshotGenerationRun,
    SnapshotSolutionEntry,
    SnapshotTimetableSolution,
)
from app.models.solver import AttendanceGroup, AttendanceGroupStudent
from app.models.v2 import (
    V2Degree,
    V2GenerationRun,
    V2Lecturer,
    V2Module,
    V2Path,
    V2Room,
    V2Session,
    V2SolutionEntry,
    V2StudentGroup,
    V2TimetableSolution,
)
from app.schemas.v2 import ExportResponse, SoftConstraintOption
from app.services.csv_import_analysis import decode_student_hashes, encode_student_hashes
from app.services.enrollment_inference import (
    build_realistic_demo_dataset_from_enrollment_csv,
)

DAY_ORDER = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
DAY_INDEX = {day: idx for idx, day in enumerate(DAY_ORDER)}
START_MINUTE = 8 * 60
END_MINUTE = 18 * 60
LUNCH_START = 12 * 60
LUNCH_END = 13 * 60
WEEKLY_SCHEDULABLE_MINUTES = 5 * ((END_MINUTE - START_MINUTE) - (LUNCH_END - LUNCH_START))
SOFT_CONSTRAINTS = {
    "spread_sessions_across_days": SoftConstraintOption(
        key="spread_sessions_across_days",
        label="Spread repeated sessions across different days",
        description="Modules with multiple weekly sessions should be spread across different days when possible.",
    ),
    "prefer_morning_theory": SoftConstraintOption(
        key="prefer_morning_theory",
        label="Keep theory sessions in the morning",
        description="Prefer lectures and tutorials to finish before lunch when possible.",
    ),
    "prefer_afternoon_practicals": SoftConstraintOption(
        key="prefer_afternoon_practicals",
        label="Keep practicals in the afternoon",
        description="Prefer practical and lab sessions to start after lunch so morning halls stay free for theory.",
    ),
    "avoid_late_afternoon_starts": SoftConstraintOption(
        key="avoid_late_afternoon_starts",
        label="Avoid late-afternoon starts",
        description="Prefer sessions to start by 3:00 PM so the timetable does not bunch up near the end of the day.",
    ),
    "avoid_friday_sessions": SoftConstraintOption(
        key="avoid_friday_sessions",
        label="Avoid Friday sessions",
        description="Prefer teaching to stay within Monday to Thursday when possible so Friday remains lighter.",
    ),
    "prefer_standard_block_starts": SoftConstraintOption(
        key="prefer_standard_block_starts",
        label="Use standard block starts",
        description="Prefer sessions to begin on the faculty's common block boundaries instead of arbitrary half-hour placements.",
    ),
    "balance_teaching_load_across_week": SoftConstraintOption(
        key="balance_teaching_load_across_week",
        label="Balance teaching load across the week",
        description="Prefer the weekly teaching load to stay spread across weekdays instead of bunching heavily at the start.",
    ),
    "avoid_monday_overload": SoftConstraintOption(
        key="avoid_monday_overload",
        label="Avoid Monday overload",
        description="Prefer Monday to carry no more scheduled teaching events than the other weekdays.",
    ),
}

PERFORMANCE_PRESETS = {
    "balanced": {
        "fallback_combo_limit": 10,
        "fallback_time_limit_seconds": 8,
        "probe_num_workers": max(1, min((os.cpu_count() or 1) - 1, 4)),
    },
    "thorough": {
        "fallback_combo_limit": 20,
        "fallback_time_limit_seconds": 15,
        "probe_num_workers": max(1, min(os.cpu_count() or 1, 6)),
    },
    "fast_diagnostics": {
        "fallback_combo_limit": 6,
        "fallback_time_limit_seconds": 5,
        "probe_num_workers": max(1, min((os.cpu_count() or 1) - 1, 3)),
    },
}

LARGE_DATASET_SESSION_THRESHOLD = 250
DEFAULT_SOLVER_MEMORY_LIMIT_MB = max(
    512, int(os.getenv("TIMETABLE_SOLVER_MEMORY_LIMIT_MB", "4096"))
)
MAX_ASSIGNMENT_VARIABLE_BUDGET = max(
    100_000, int(os.getenv("TIMETABLE_MAX_ASSIGNMENT_VARIABLES", "400000"))
)
MAX_CANDIDATE_OPTION_BUDGET = max(
    100_000, int(os.getenv("TIMETABLE_MAX_CANDIDATE_OPTIONS", "500000"))
)
MAX_GROUP_SLOT_BLOCKER_BUDGET = max(
    10_000, int(os.getenv("TIMETABLE_MAX_GROUP_SLOT_BLOCKERS", "200000"))
)


@dataclass(frozen=True)
class SplitAssignment:
    split_index: int
    student_group_ids: tuple[int, ...]
    student_count: int
    fragments: tuple[tuple[int, int, str], ...]


@dataclass(frozen=True)
class SessionTask:
    session_id: int
    session_name: str
    session_type: str
    module_id: int
    module_code: str
    module_name: str
    occurrence_index: int
    split_index: int
    duration_minutes: int
    required_room_type: str | None
    required_lab_type: str | None
    specific_room_id: int | None
    lecturer_ids: tuple[int, ...]
    student_group_ids: tuple[int, ...]
    student_membership_keys: tuple[str, ...]
    study_years: tuple[int, ...]
    student_count: int
    root_session_id: int
    bundle_key: tuple[int, int] | None


@dataclass(frozen=True)
class SolveProfile:
    performance_preset: str
    fallback_combo_limit: int
    fallback_time_limit_seconds: int
    probe_num_workers: int
    fallback_combo_count_cap: int
    memory_limit_mb: int


def _partition_lecturers(
    lecturer_ids: tuple[int, ...], chunk_count: int
) -> list[tuple[int, ...]]:
    if chunk_count <= 0:
        return []
    if not lecturer_ids:
        return [tuple() for _ in range(chunk_count)]
    if len(lecturer_ids) < chunk_count:
        raise ValueError(
            "Parallel-room sessions need at least one lecturer per room assignment."
        )

    assignments: list[list[int]] = [[] for _ in range(chunk_count)]
    for index, lecturer_id in enumerate(lecturer_ids):
        assignments[index % chunk_count].append(lecturer_id)
    return [tuple(items) for items in assignments]


def list_soft_constraint_options() -> list[SoftConstraintOption]:
    return list(SOFT_CONSTRAINTS.values())


def _resolve_solve_profile(performance_preset: str) -> SolveProfile:
    config = PERFORMANCE_PRESETS.get(performance_preset, PERFORMANCE_PRESETS["balanced"])
    return SolveProfile(
        performance_preset=performance_preset
        if performance_preset in PERFORMANCE_PRESETS
        else "balanced",
        fallback_combo_limit=int(config["fallback_combo_limit"]),
        fallback_time_limit_seconds=int(config["fallback_time_limit_seconds"]),
        probe_num_workers=int(config["probe_num_workers"]),
        fallback_combo_count_cap=101,
        memory_limit_mb=DEFAULT_SOLVER_MEMORY_LIMIT_MB,
    )


@dataclass(frozen=True)
class CandidateSizing:
    assignment_variable_count: int
    candidate_option_count: int
    max_candidates_per_task: int
    group_slot_blocker_count: int


def _resource_limited_result(
    started_at: float,
    tasks: list[SessionTask],
    *,
    message: str,
    precheck_ms: int = 0,
    model_build_ms: int = 0,
    solve_ms: int = 0,
    assignment_variable_count: int = 0,
    candidate_option_count: int = 0,
    group_slot_blocker_count: int = 0,
    enumerate_all_solutions: bool = True,
) -> dict:
    return {
        "status": "resource_limited",
        "message": message,
        "solutions": [],
        "truncated": False,
        "tasks": tasks,
        "timing": {
            "precheck_ms": precheck_ms,
            "model_build_ms": model_build_ms,
            "solve_ms": solve_ms,
            "fallback_search_ms": 0,
            "total_ms": int((time.perf_counter() - started_at) * 1000),
        },
        "stats": {
            "task_count": len(tasks),
            "assignment_variable_count": assignment_variable_count,
            "candidate_option_count": candidate_option_count,
            "feasible_combo_count": 0,
            "fallback_combo_evaluated_count": 0,
            "fallback_combo_truncated": False,
            "exact_enumeration_single_worker": enumerate_all_solutions,
            "machine_cpu_count": os.cpu_count() or 1,
            "memory_limit_mb": DEFAULT_SOLVER_MEMORY_LIMIT_MB,
            "projected_group_slot_blocker_count": group_slot_blocker_count,
        },
    }


def _is_timeslot_valid(start_minute: int, duration_minutes: int) -> bool:
    end_minute = start_minute + duration_minutes
    if start_minute < START_MINUTE or end_minute > END_MINUTE:
        return False
    if start_minute < LUNCH_END and end_minute > LUNCH_START:
        return False
    return duration_minutes > 0 and start_minute % 30 == 0


def _build_split_assignments(session: V2Session) -> list[SplitAssignment]:
    groups = sorted(session.student_groups, key=lambda item: item.id)
    if not groups:
        return [
            SplitAssignment(
                split_index=1,
                student_group_ids=tuple(),
                student_count=0,
                fragments=tuple(),
            )
        ]

    total = sum(int(group.size) for group in groups)
    limit = session.max_students_per_group
    if not limit or total <= limit:
        return [
            SplitAssignment(
                split_index=1,
                student_group_ids=tuple(int(group.id) for group in groups),
                student_count=total,
                fragments=tuple(
                    (int(group.id), int(group.size), group.name) for group in groups
                ),
            )
        ]

    assignments: list[SplitAssignment] = []
    current_ids: set[int] = set()
    current_fragments: list[tuple[int, int, str]] = []
    current_total = 0
    split_index = 1
    for group in groups:
        remaining = int(group.size)
        part_index = 1
        while remaining > 0:
            available = limit - current_total
            if current_total > 0 and available == 0:
                assignments.append(
                    SplitAssignment(
                        split_index=split_index,
                        student_group_ids=tuple(sorted(current_ids)),
                        student_count=current_total,
                        fragments=tuple(current_fragments),
                    )
                )
                split_index += 1
                current_ids = set()
                current_fragments = []
                current_total = 0
                available = limit

            fragment_size = min(remaining, available)
            fragment_label = (
                group.name
                if fragment_size == int(group.size) and part_index == 1
                else f"{group.name} (Part {part_index})"
            )
            current_ids.add(int(group.id))
            current_fragments.append((int(group.id), fragment_size, fragment_label))
            current_total += fragment_size
            remaining -= fragment_size
            part_index += 1

            if current_total >= limit:
                assignments.append(
                    SplitAssignment(
                        split_index=split_index,
                        student_group_ids=tuple(sorted(current_ids)),
                        student_count=current_total,
                        fragments=tuple(current_fragments),
                    )
                )
                split_index += 1
                current_ids = set()
                current_fragments = []
                current_total = 0

    if current_fragments:
        assignments.append(
            SplitAssignment(
                split_index=split_index,
                student_group_ids=tuple(sorted(current_ids)),
                student_count=current_total,
                fragments=tuple(current_fragments),
            )
        )
    return assignments


def _build_snapshot_split_assignments(
    session: SnapshotSharedSession,
) -> list[SplitAssignment]:
    groups = sorted(session.attendance_groups, key=lambda item: item.id)
    if not groups:
        return [
            SplitAssignment(
                split_index=1,
                student_group_ids=tuple(),
                student_count=0,
                fragments=tuple(),
            )
        ]

    total = sum(int(group.student_count) for group in groups)
    limit = session.max_students_per_group
    if not limit or total <= limit:
        return [
            SplitAssignment(
                split_index=1,
                student_group_ids=tuple(int(group.id) for group in groups),
                student_count=total,
                fragments=tuple(
                    (int(group.id), int(group.student_count), group.label)
                    for group in groups
                ),
            )
        ]

    assignments: list[SplitAssignment] = []
    current_ids: set[int] = set()
    current_fragments: list[tuple[int, int, str]] = []
    current_total = 0
    split_index = 1
    for group in groups:
        remaining = int(group.student_count)
        part_index = 1
        while remaining > 0:
            available = limit - current_total
            if current_total > 0 and available == 0:
                assignments.append(
                    SplitAssignment(
                        split_index=split_index,
                        student_group_ids=tuple(sorted(current_ids)),
                        student_count=current_total,
                        fragments=tuple(current_fragments),
                    )
                )
                split_index += 1
                current_ids = set()
                current_fragments = []
                current_total = 0
                available = limit

            fragment_size = min(remaining, available)
            fragment_label = (
                group.label
                if fragment_size == int(group.student_count) and part_index == 1
                else f"{group.label} (Part {part_index})"
            )
            current_ids.add(int(group.id))
            current_fragments.append((int(group.id), fragment_size, fragment_label))
            current_total += fragment_size
            remaining -= fragment_size
            part_index += 1

            if current_total >= limit:
                assignments.append(
                    SplitAssignment(
                        split_index=split_index,
                        student_group_ids=tuple(sorted(current_ids)),
                        student_count=current_total,
                        fragments=tuple(current_fragments),
                    )
                )
                split_index += 1
                current_ids = set()
                current_fragments = []
                current_total = 0

    if current_fragments:
        assignments.append(
            SplitAssignment(
                split_index=split_index,
                student_group_ids=tuple(sorted(current_ids)),
                student_count=current_total,
                fragments=tuple(current_fragments),
            )
        )
    return assignments


def _build_tasks(db: Session) -> list[SessionTask]:
    sessions = (
        db.query(V2Session)
        .options(
            joinedload(V2Session.module),
            joinedload(V2Session.lecturers),
            joinedload(V2Session.student_groups).joinedload(V2StudentGroup.degree),
            joinedload(V2Session.student_groups).joinedload(V2StudentGroup.path),
        )
        .order_by(V2Session.id)
        .all()
    )

    tasks: list[SessionTask] = []
    for session in sessions:
        lecturer_ids = tuple(sorted(int(item.id) for item in session.lecturers))
        split_assignments = _build_split_assignments(session)
        student_membership_keys = tuple(
            sorted(
                {
                    student_hash
                    for group in session.student_groups
                    for student_hash in decode_student_hashes(group.student_hashes_json)
                }
            )
        )
        lecturer_chunks = (
            _partition_lecturers(lecturer_ids, len(split_assignments))
            if session.allow_parallel_rooms
            else [lecturer_ids for _ in split_assignments]
        )
        study_year_by_group_id = {
            int(group.id): int(group.year)
            for group in session.student_groups
        }
        for occurrence_index in range(1, int(session.occurrences_per_week) + 1):
            for split, assigned_lecturers in zip(
                split_assignments, lecturer_chunks, strict=True
            ):
                tasks.append(
                    SessionTask(
                        session_id=int(session.id),
                        session_name=session.name,
                        session_type=session.session_type,
                        module_id=int(session.module_id),
                        module_code=session.module.code,
                        module_name=session.module.name,
                        occurrence_index=occurrence_index,
                        split_index=split.split_index,
                        duration_minutes=int(session.duration_minutes),
                        required_room_type=session.required_room_type,
                        required_lab_type=session.required_lab_type,
                        specific_room_id=int(session.specific_room_id)
                        if session.specific_room_id
                        else None,
                        lecturer_ids=assigned_lecturers,
                        student_group_ids=split.student_group_ids,
                        student_membership_keys=student_membership_keys,
                        study_years=tuple(
                            sorted(
                                {
                                    study_year_by_group_id[group_id]
                                    for group_id in split.student_group_ids
                                    if group_id in study_year_by_group_id
                                }
                            )
                        ),
                        student_count=split.student_count,
                        root_session_id=int(session.id),
                        bundle_key=(int(session.id), occurrence_index)
                        if session.allow_parallel_rooms and len(split_assignments) > 1
                        else None,
                    )
                )
    return tasks


def _build_snapshot_tasks(
    db: Session, import_run_id: int
) -> tuple[
    list[SessionTask],
    list[SnapshotSharedSession],
    list[SnapshotRoom],
    dict[int, str],
    dict[int, str],
]:
    sessions = (
        db.query(SnapshotSharedSession)
        .options(
            joinedload(SnapshotSharedSession.curriculum_modules),
            joinedload(SnapshotSharedSession.lecturers),
            joinedload(SnapshotSharedSession.attendance_groups)
            .joinedload(AttendanceGroup.students)
            .joinedload(AttendanceGroupStudent.student),
        )
        .filter(SnapshotSharedSession.import_run_id == import_run_id)
        .order_by(SnapshotSharedSession.id)
        .all()
    )
    rooms = (
        db.query(SnapshotRoom)
        .filter(SnapshotRoom.import_run_id == import_run_id)
        .order_by(SnapshotRoom.id)
        .all()
    )

    lecturer_names: dict[int, str] = {}
    group_names: dict[int, str] = {}
    tasks: list[SessionTask] = []
    for session in sessions:
        lecturer_ids = tuple(sorted(int(item.id) for item in session.lecturers))
        for lecturer in session.lecturers:
            lecturer_names[int(lecturer.id)] = lecturer.name
        for group in session.attendance_groups:
            group_names[int(group.id)] = group.label

        module_ids = sorted(int(module.id) for module in session.curriculum_modules)
        module_codes = [module.code for module in session.curriculum_modules]
        module_names = [module.name for module in session.curriculum_modules]
        primary_module_id = module_ids[0] if module_ids else 0
        module_code = " / ".join(module_codes) if module_codes else session.name
        module_name = " / ".join(module_names) if module_names else session.name

        split_assignments = _build_snapshot_split_assignments(session)
        student_membership_keys = tuple(
            sorted(
                {
                    attendance_student.student.student_hash
                    for group in session.attendance_groups
                    for attendance_student in group.students
                    if attendance_student.student is not None
                }
            )
        )
        lecturer_chunks = (
            _partition_lecturers(lecturer_ids, len(split_assignments))
            if session.allow_parallel_rooms
            else [lecturer_ids for _ in split_assignments]
        )
        study_year_by_group_id = {
            int(group.id): int(group.study_year)
            for group in session.attendance_groups
        }
        for occurrence_index in range(1, int(session.occurrences_per_week) + 1):
            for split, assigned_lecturers in zip(
                split_assignments, lecturer_chunks, strict=True
            ):
                tasks.append(
                    SessionTask(
                        session_id=int(session.id),
                        session_name=session.name,
                        session_type=session.session_type,
                        module_id=primary_module_id,
                        module_code=module_code,
                        module_name=module_name,
                        occurrence_index=occurrence_index,
                        split_index=split.split_index,
                        duration_minutes=int(session.duration_minutes),
                        required_room_type=session.required_room_type,
                        required_lab_type=session.required_lab_type,
                        specific_room_id=int(session.specific_room_id)
                        if session.specific_room_id
                        else None,
                        lecturer_ids=assigned_lecturers,
                        student_group_ids=split.student_group_ids,
                        student_membership_keys=student_membership_keys,
                        study_years=tuple(
                            sorted(
                                {
                                    study_year_by_group_id[group_id]
                                    for group_id in split.student_group_ids
                                    if group_id in study_year_by_group_id
                                }
                            )
                        ),
                        student_count=split.student_count,
                        root_session_id=int(session.id),
                        bundle_key=(int(session.id), occurrence_index)
                        if session.allow_parallel_rooms and len(split_assignments) > 1
                        else None,
                    )
                )

    return tasks, sessions, rooms, lecturer_names, group_names


def _session_modules(session: V2Session) -> list[V2Module]:
    ordered: list[V2Module] = []
    seen: set[int] = set()
    primary_id = int(session.module_id)
    if session.module is not None:
        ordered.append(session.module)
        seen.add(primary_id)
    for module in sorted(session.linked_modules, key=lambda item: int(item.id)):
        module_id = int(module.id)
        if module_id in seen:
            continue
        ordered.append(module)
        seen.add(module_id)
    return ordered


def _format_session_module_code(session: V2Session) -> str:
    modules = _session_modules(session)
    if not modules:
        return session.module.code
    return " / ".join(module.code for module in modules)


def _format_session_module_name(session: V2Session) -> str:
    modules = _session_modules(session)
    if not modules:
        return session.module.name
    return " / ".join(module.name for module in modules)


def _room_matches(room: V2Room, task: SessionTask) -> bool:
    if room.capacity < task.student_count:
        return False
    if room.year_restriction is not None and any(
        int(study_year) != int(room.year_restriction) for study_year in task.study_years
    ):
        return False
    if task.required_room_type and room.room_type != task.required_room_type:
        return False
    if task.required_lab_type and room.lab_type != task.required_lab_type:
        return False
    if task.specific_room_id and int(room.id) != task.specific_room_id:
        return False
    return True


def _candidate_starts(task: SessionTask) -> list[tuple[str, int]]:
    starts: list[tuple[str, int]] = []
    if _is_lab_task(task):
        if task.duration_minutes != 180:
            return starts
        for day in DAY_ORDER:
            for minute in (9 * 60, 13 * 60):
                if _is_timeslot_valid(minute, task.duration_minutes):
                    starts.append((day, minute))
        return starts
    for day in DAY_ORDER:
        minute = START_MINUTE
        while minute + task.duration_minutes <= END_MINUTE:
            if _is_timeslot_valid(minute, task.duration_minutes):
                starts.append((day, minute))
            minute += 30
    return starts


def _is_theory_task(task: SessionTask) -> bool:
    session_type = (task.session_type or "").lower()
    return session_type in {"lecture", "tutorial", "seminar"}


def _is_practical_task(task: SessionTask) -> bool:
    session_type = (task.session_type or "").lower()
    if session_type in {"practical", "lab", "laboratory"}:
        return True
    return bool(task.required_lab_type) or task.required_room_type == "lab"


def _is_lab_task(task: SessionTask) -> bool:
    session_type = (task.session_type or "").lower()
    return (
        session_type in {"lab", "laboratory"}
        or bool(task.required_lab_type)
        or task.required_room_type == "lab"
    )


def _soft_constraint_allows_start(
    task: SessionTask, day: str, start_minute: int, selected_soft_constraints: list[str]
) -> bool:
    end_minute = start_minute + task.duration_minutes
    if (
        "avoid_friday_sessions" in selected_soft_constraints
        and day == "Friday"
        and _is_theory_task(task)
    ):
        return False
    if "prefer_standard_block_starts" in selected_soft_constraints:
        if task.duration_minutes >= 180 and start_minute not in {9 * 60, 13 * 60}:
            return False
        if task.duration_minutes == 120 and start_minute not in {8 * 60, 10 * 60, 13 * 60}:
            return False
        if task.duration_minutes == 90 and start_minute not in {8 * 60, 13 * 60}:
            return False
        if task.duration_minutes == 60 and start_minute not in {8 * 60, 10 * 60, 13 * 60, 15 * 60}:
            return False
    if "prefer_morning_theory" in selected_soft_constraints and _is_theory_task(task):
        if end_minute > LUNCH_START:
            return False
    if (
        "prefer_afternoon_practicals" in selected_soft_constraints
        and _is_practical_task(task)
    ):
        if task.duration_minutes >= 180:
            return start_minute == LUNCH_END
        if task.duration_minutes >= 120:
            return start_minute in {LUNCH_END, 14 * 60}
        if start_minute < LUNCH_END:
            return False
    if "avoid_late_afternoon_starts" in selected_soft_constraints and start_minute > 14 * 60:
        return False
    return True


def _overlap(start_a: int, duration_a: int, start_b: int, duration_b: int) -> bool:
    end_a = start_a + duration_a
    end_b = start_b + duration_b
    return start_a < end_b and start_b < end_a


def _all_soft_constraint_combinations() -> list[list[str]]:
    keys = sorted(SOFT_CONSTRAINTS.keys())
    combinations: list[list[str]] = []
    for length in range(len(keys), 0, -1):
        for combo in itertools.combinations(keys, length):
            combinations.append(list(combo))
    return combinations


def _selected_soft_constraint_subsets(selected_soft_constraints: Iterable[str]) -> list[list[str]]:
    keys = sorted({key for key in selected_soft_constraints if key in SOFT_CONSTRAINTS})
    combinations: list[list[str]] = []
    for length in range(len(keys) - 1, 0, -1):
        for combo in itertools.combinations(keys, length):
            combinations.append(list(combo))
    return combinations


def _sorted_soft_constraint_combinations(combinations: list[list[str]]) -> list[list[str]]:
    return sorted(
        combinations,
        key=lambda combo: (-len(combo), ",".join(combo)),
    )


def _format_diagnostic_message(summary: str, issues: list[str]) -> str:
    if not issues:
        return summary
    lines = [summary, "", "Diagnostics:"]
    lines.extend(f"- {issue}" for issue in issues[:8])
    if len(issues) > 8:
        lines.append(f"- ...and {len(issues) - 8} more issue(s)")
    return "\n".join(lines)


def _estimate_candidate_sizing(
    tasks: list[SessionTask],
    candidates_by_task: dict[int, list[tuple[int, str, int]]],
) -> CandidateSizing:
    candidate_option_count = sum(len(candidates) for candidates in candidates_by_task.values())
    assignment_variable_count = candidate_option_count
    max_candidates_per_task = max(
        (len(candidates) for candidates in candidates_by_task.values()),
        default=0,
    )

    group_slot_blocker_count = 0
    for day in DAY_ORDER:
        for minute in range(START_MINUTE, END_MINUTE, 30):
            blockers_by_group: dict[int, int] = defaultdict(int)
            blockers_by_student: dict[str, int] = defaultdict(int)
            for task_index, task in enumerate(tasks):
                overlaps = 0
                for _, candidate_day, candidate_start in candidates_by_task[task_index]:
                    if candidate_day != day or not _overlap(
                        candidate_start, task.duration_minutes, minute, 30
                    ):
                        continue
                    overlaps += 1
                if overlaps == 0:
                    continue
                for student_group_id in task.student_group_ids:
                    blockers_by_group[student_group_id] += overlaps
                for student_key in task.student_membership_keys:
                    blockers_by_student[student_key] += overlaps
            group_slot_blocker_count += sum(blockers_by_group.values()) + sum(blockers_by_student.values())

    return CandidateSizing(
        assignment_variable_count=assignment_variable_count,
        candidate_option_count=candidate_option_count,
        max_candidates_per_task=max_candidates_per_task,
        group_slot_blocker_count=group_slot_blocker_count,
    )


def _precheck_diagnostics(
    tasks: list[SessionTask],
    rooms: list[V2Room] | list[SnapshotRoom],
    lecturer_names: dict[int, str],
    group_names: dict[int, str],
) -> list[str]:
    issues: list[str] = []
    room_lookup = {int(room.id): room for room in rooms}

    if not rooms:
        issues.append("No rooms are available in the current dataset.")
        return issues

    tasks_by_bundle: dict[tuple[int, int], list[SessionTask]] = defaultdict(list)
    lecturer_minutes: dict[int, int] = defaultdict(int)
    group_minutes: dict[int, int] = defaultdict(int)
    group_session_minutes: dict[tuple[int, int, int], int] = {}

    for task in tasks:
        for lecturer_id in task.lecturer_ids:
            lecturer_minutes[int(lecturer_id)] += task.duration_minutes
        for group_id in task.student_group_ids:
            group_session_key = (
                int(group_id),
                int(task.root_session_id),
                int(task.occurrence_index),
            )
            group_session_minutes[group_session_key] = max(
                group_session_minutes.get(group_session_key, 0),
                int(task.duration_minutes),
            )
        if _is_lab_task(task) and task.duration_minutes != 180:
            issues.append(
                f"{task.module_code} / {task.session_name} must be scheduled as one 3-hour lab block (180 minutes)."
            )
            continue
        matching_rooms = [room for room in rooms if _room_matches(room, task)]
        if not matching_rooms:
            issue = (
                f'{task.module_code} / {task.session_name} has no room that can host '
                f"split {task.split_index} with {task.student_count} students"
            )
            if task.specific_room_id:
                room = room_lookup.get(task.specific_room_id)
                room_name = room.name if room else f"room #{task.specific_room_id}"
                issue += f" in required room {room_name}"
            elif task.study_years:
                issue += " for study year"
                if len(task.study_years) > 1:
                    issue += "s"
                issue += " " + ", ".join(str(item) for item in task.study_years)
            elif task.required_lab_type:
                issue += f" requiring lab type {task.required_lab_type}"
            elif task.required_room_type:
                issue += f" requiring room type {task.required_room_type}"
            issues.append(issue + ".")
            continue

        if task.bundle_key is not None:
            tasks_by_bundle[task.bundle_key].append(task)

        if task.bundle_key is not None and len(task.lecturer_ids) == 0:
            issues.append(
                f"{task.module_code} / {task.session_name} is marked for parallel rooms but has no lecturer assigned to split {task.split_index}."
            )

    for bundle_key, bundle_tasks in tasks_by_bundle.items():
        shared_slots: set[tuple[str, int]] | None = None
        for task in bundle_tasks:
            task_slots = {
                (day, start_minute)
                for day, start_minute in _candidate_starts(task)
                for room in rooms
                if _room_matches(room, task)
            }
            shared_slots = task_slots if shared_slots is None else shared_slots & task_slots
        if not shared_slots:
            sample = bundle_tasks[0]
            issues.append(
                f"{sample.module_code} / {sample.session_name} cannot place all same-time parallel room parts into a shared slot for occurrence {sample.occurrence_index}."
            )

    for lecturer_id, scheduled_minutes in sorted(
        lecturer_minutes.items(), key=lambda item: item[1], reverse=True
    ):
        if scheduled_minutes <= WEEKLY_SCHEDULABLE_MINUTES:
            continue
        lecturer_name = lecturer_names.get(lecturer_id, f"lecturer #{lecturer_id}")
        issues.append(
            f"{lecturer_name} is assigned {scheduled_minutes // 60:.1f} weekly hours, which exceeds the timetable capacity of {WEEKLY_SCHEDULABLE_MINUTES // 60} hours."
        )

    for (group_id, _session_id, _occurrence_index), session_minutes in (
        group_session_minutes.items()
    ):
        group_minutes[group_id] += session_minutes

    for group_id, scheduled_minutes in sorted(
        group_minutes.items(), key=lambda item: item[1], reverse=True
    ):
        if scheduled_minutes <= WEEKLY_SCHEDULABLE_MINUTES:
            continue
        group_name = group_names.get(group_id, f"group #{group_id}")
        issues.append(
            f"{group_name} requires {scheduled_minutes // 60:.1f} weekly hours, which exceeds the timetable capacity of {WEEKLY_SCHEDULABLE_MINUTES // 60} hours."
        )

    return issues


class _SolutionCollector(cp_model.CpSolverSolutionCallback):
    def __init__(
        self,
        variables: dict[tuple[int, int, str, int], cp_model.IntVar],
        max_solutions: int,
    ):
        super().__init__()
        self._variables = variables
        self._max_solutions = max_solutions
        self.solutions: list[list[tuple[int, int, str, int]]] = []
        self.truncated = False

    def on_solution_callback(self) -> None:
        current: list[tuple[int, int, str, int]] = []
        for key, var in self._variables.items():
            if self.Value(var):
                current.append(key)
        self.solutions.append(current)
        if len(self.solutions) >= self._max_solutions:
            self.truncated = True
            self.StopSearch()


def _solve_internal_legacy(
    db: Session,
    selected_soft_constraints: list[str],
    max_solutions: int,
    time_limit_seconds: int,
    *,
    enumerate_all_solutions: bool = True,
    num_search_workers: int = 1,
) -> dict:
    started_at = time.perf_counter()
    precheck_ms = 0
    model_build_ms = 0
    solve_ms = 0

    sessions = (
        db.query(V2Session)
        .options(
            joinedload(V2Session.module),
            joinedload(V2Session.linked_modules),
            joinedload(V2Session.lecturers),
            joinedload(V2Session.student_groups).joinedload(V2StudentGroup.degree),
            joinedload(V2Session.student_groups).joinedload(V2StudentGroup.path),
        )
        .order_by(V2Session.id)
        .all()
    )
    rooms = db.query(V2Room).order_by(V2Room.id).all()
    try:
        tasks = _build_tasks(db)
    except ValueError as exc:
        return {
            "status": "infeasible",
            "message": str(exc),
            "solutions": [],
            "truncated": False,
            "tasks": [],
            "timing": {
                "precheck_ms": precheck_ms,
                "model_build_ms": model_build_ms,
                "solve_ms": solve_ms,
                "fallback_search_ms": 0,
                "total_ms": int((time.perf_counter() - started_at) * 1000),
            },
            "stats": {
                "task_count": 0,
                "assignment_variable_count": 0,
                "candidate_option_count": 0,
                "feasible_combo_count": 0,
                "fallback_combo_evaluated_count": 0,
                "fallback_combo_truncated": False,
                "exact_enumeration_single_worker": enumerate_all_solutions,
                "machine_cpu_count": os.cpu_count() or 1,
            },
        }
    if not tasks:
        return {
            "status": "empty",
            "message": "Enter session data before generating a timetable.",
            "solutions": [],
            "truncated": False,
            "tasks": tasks,
            "timing": {
                "precheck_ms": precheck_ms,
                "model_build_ms": model_build_ms,
                "solve_ms": solve_ms,
                "fallback_search_ms": 0,
                "total_ms": int((time.perf_counter() - started_at) * 1000),
            },
            "stats": {
                "task_count": len(tasks),
                "assignment_variable_count": 0,
                "candidate_option_count": 0,
                "feasible_combo_count": 0,
                "fallback_combo_evaluated_count": 0,
                "fallback_combo_truncated": False,
                "exact_enumeration_single_worker": enumerate_all_solutions,
                "machine_cpu_count": os.cpu_count() or 1,
            },
        }
    if not rooms:
        return {
            "status": "infeasible",
            "message": "No rooms available for timetable generation.",
            "solutions": [],
            "truncated": False,
            "tasks": tasks,
            "timing": {
                "precheck_ms": precheck_ms,
                "model_build_ms": model_build_ms,
                "solve_ms": solve_ms,
                "fallback_search_ms": 0,
                "total_ms": int((time.perf_counter() - started_at) * 1000),
            },
            "stats": {
                "task_count": len(tasks),
                "assignment_variable_count": 0,
                "candidate_option_count": 0,
                "feasible_combo_count": 0,
                "fallback_combo_evaluated_count": 0,
                "fallback_combo_truncated": False,
                "exact_enumeration_single_worker": enumerate_all_solutions,
                "machine_cpu_count": os.cpu_count() or 1,
            },
        }

    precheck_started_at = time.perf_counter()
    lecturer_names = {
        int(lecturer.id): lecturer.name
        for session in sessions
        for lecturer in session.lecturers
    }
    group_names = {
        int(group.id): group.name
        for session in sessions
        for group in session.student_groups
    }
    diagnostics = _precheck_diagnostics(tasks, rooms, lecturer_names, group_names)
    precheck_ms = int((time.perf_counter() - precheck_started_at) * 1000)
    if diagnostics:
        return {
            "status": "infeasible",
            "message": _format_diagnostic_message(
                "No possible timetables satisfy the current hard constraints.",
                diagnostics,
            ),
            "solutions": [],
            "truncated": False,
            "tasks": tasks,
            "timing": {
                "precheck_ms": precheck_ms,
                "model_build_ms": model_build_ms,
                "solve_ms": solve_ms,
                "fallback_search_ms": 0,
                "total_ms": int((time.perf_counter() - started_at) * 1000),
            },
            "stats": {
                "task_count": len(tasks),
                "assignment_variable_count": 0,
                "candidate_option_count": 0,
                "feasible_combo_count": 0,
                "fallback_combo_evaluated_count": 0,
                "fallback_combo_truncated": False,
                "exact_enumeration_single_worker": enumerate_all_solutions,
                "machine_cpu_count": os.cpu_count() or 1,
            },
        }

    model_build_started_at = time.perf_counter()
    model = cp_model.CpModel()
    assignment_vars: dict[tuple[int, int, str, int], cp_model.IntVar] = {}
    room_lookup = {int(room.id): room for room in rooms}
    room_ids = [int(room.id) for room in rooms]

    candidates_by_task: dict[int, list[tuple[int, str, int]]] = defaultdict(list)
    for task_index, task in enumerate(tasks):
        starts = [
            (day, start_minute)
            for day, start_minute in _candidate_starts(task)
            if _soft_constraint_allows_start(
                task, day, start_minute, selected_soft_constraints
            )
        ]
        for room_id in room_ids:
            room = room_lookup[room_id]
            if not _room_matches(room, task):
                continue
            for day, start_minute in starts:
                var = model.NewBoolVar(
                    f"task_{task_index}_room_{room_id}_{day}_{start_minute}"
                )
                assignment_vars[(task_index, room_id, day, start_minute)] = var
                candidates_by_task[task_index].append((room_id, day, start_minute))

    if any(not candidates for candidates in candidates_by_task.values()) or len(
        candidates_by_task
    ) != len(tasks):
        return {
            "status": "infeasible",
            "message": "Some sessions have no valid room or time options.",
            "solutions": [],
            "truncated": False,
            "tasks": tasks,
            "timing": {
                "precheck_ms": precheck_ms,
                "model_build_ms": int((time.perf_counter() - model_build_started_at) * 1000),
                "solve_ms": solve_ms,
                "fallback_search_ms": 0,
                "total_ms": int((time.perf_counter() - started_at) * 1000),
            },
            "stats": {
                "task_count": len(tasks),
                "assignment_variable_count": len(assignment_vars),
                "candidate_option_count": sum(
                    len(candidates) for candidates in candidates_by_task.values()
                ),
                "feasible_combo_count": 0,
                "fallback_combo_evaluated_count": 0,
                "fallback_combo_truncated": False,
                "exact_enumeration_single_worker": enumerate_all_solutions,
                "machine_cpu_count": os.cpu_count() or 1,
            },
        }

    sizing = _estimate_candidate_sizing(tasks, candidates_by_task)
    if (
        sizing.assignment_variable_count > MAX_ASSIGNMENT_VARIABLE_BUDGET
        or sizing.candidate_option_count > MAX_CANDIDATE_OPTION_BUDGET
        or sizing.group_slot_blocker_count > MAX_GROUP_SLOT_BLOCKER_BUDGET
    ):
        limit_reasons = []
        if sizing.assignment_variable_count > MAX_ASSIGNMENT_VARIABLE_BUDGET:
            limit_reasons.append(
                f"{sizing.assignment_variable_count} assignment variables exceeds the local safety budget of {MAX_ASSIGNMENT_VARIABLE_BUDGET}"
            )
        if sizing.candidate_option_count > MAX_CANDIDATE_OPTION_BUDGET:
            limit_reasons.append(
                f"{sizing.candidate_option_count} candidate options exceeds the local safety budget of {MAX_CANDIDATE_OPTION_BUDGET}"
            )
        if sizing.group_slot_blocker_count > MAX_GROUP_SLOT_BLOCKER_BUDGET:
            limit_reasons.append(
                f"{sizing.group_slot_blocker_count} projected student-group blocker references exceeds the local safety budget of {MAX_GROUP_SLOT_BLOCKER_BUDGET}"
            )
        return _resource_limited_result(
            started_at,
            tasks,
            message=(
                "Generation was stopped before solving because the projected model size is too large for the current local safety limits: "
                + "; ".join(limit_reasons)
                + ". Try a pruning-friendly constraint set or raise the local solver limits."
            ),
            precheck_ms=precheck_ms,
            model_build_ms=int((time.perf_counter() - model_build_started_at) * 1000),
            assignment_variable_count=sizing.assignment_variable_count,
            candidate_option_count=sizing.candidate_option_count,
            group_slot_blocker_count=sizing.group_slot_blocker_count,
            enumerate_all_solutions=enumerate_all_solutions,
        )

    for task_index in range(len(tasks)):
        if tasks[task_index].bundle_key is not None:
            continue
        vars_for_task = [
            assignment_vars[(task_index, room_id, day, start_minute)]
            for room_id, day, start_minute in candidates_by_task[task_index]
        ]
        model.Add(sum(vars_for_task) == 1)

    bundle_tasks: dict[tuple[int, int], list[int]] = defaultdict(list)
    for task_index, task in enumerate(tasks):
        if task.bundle_key is not None:
            bundle_tasks[task.bundle_key].append(task_index)

    bundle_slot_vars: dict[tuple[tuple[int, int], str, int], cp_model.IntVar] = {}
    for bundle_key, task_indexes in bundle_tasks.items():
        shared_slots: set[tuple[str, int]] | None = None
        for task_index in task_indexes:
            task_slots = {
                (day, start_minute)
                for _, day, start_minute in candidates_by_task[task_index]
            }
            shared_slots = task_slots if shared_slots is None else shared_slots & task_slots

        if not shared_slots:
            return {
                "status": "infeasible",
                "message": "Some parallel-room sessions have no shared time options across required rooms.",
                "solutions": [],
                "truncated": False,
                "tasks": tasks,
                "timing": {
                    "precheck_ms": precheck_ms,
                    "model_build_ms": int((time.perf_counter() - model_build_started_at) * 1000),
                    "solve_ms": solve_ms,
                    "fallback_search_ms": 0,
                    "total_ms": int((time.perf_counter() - started_at) * 1000),
                },
                "stats": {
                    "task_count": len(tasks),
                    "assignment_variable_count": len(assignment_vars),
                    "candidate_option_count": sum(
                        len(candidates) for candidates in candidates_by_task.values()
                    ),
                    "feasible_combo_count": 0,
                    "fallback_combo_evaluated_count": 0,
                    "fallback_combo_truncated": False,
                    "exact_enumeration_single_worker": enumerate_all_solutions,
                    "machine_cpu_count": os.cpu_count() or 1,
                    "memory_limit_mb": DEFAULT_SOLVER_MEMORY_LIMIT_MB,
                    "projected_group_slot_blocker_count": sizing.group_slot_blocker_count,
                },
            }

        shared_slot_vars = []
        for day, start_minute in sorted(shared_slots, key=lambda item: (DAY_INDEX[item[0]], item[1])):
            slot_var = model.NewBoolVar(
                f"bundle_{bundle_key[0]}_{bundle_key[1]}_{day}_{start_minute}"
            )
            bundle_slot_vars[(bundle_key, day, start_minute)] = slot_var
            shared_slot_vars.append(slot_var)
        model.Add(sum(shared_slot_vars) == 1)

        for task_index in task_indexes:
            vars_for_task = []
            for day, start_minute in sorted(shared_slots, key=lambda item: (DAY_INDEX[item[0]], item[1])):
                matching_room_vars = [
                    assignment_vars[(task_index, room_id, candidate_day, candidate_start)]
                    for room_id, candidate_day, candidate_start in candidates_by_task[task_index]
                    if candidate_day == day and candidate_start == start_minute
                ]
                if not matching_room_vars:
                    return {
                        "status": "infeasible",
                        "message": "A parallel-room session could not be aligned to the same time across all room assignments.",
                        "solutions": [],
                        "truncated": False,
                        "tasks": tasks,
                        "timing": {
                            "precheck_ms": precheck_ms,
                            "model_build_ms": int((time.perf_counter() - model_build_started_at) * 1000),
                            "solve_ms": solve_ms,
                            "fallback_search_ms": 0,
                            "total_ms": int((time.perf_counter() - started_at) * 1000),
                        },
                        "stats": {
                            "task_count": len(tasks),
                            "assignment_variable_count": len(assignment_vars),
                            "candidate_option_count": sum(
                                len(candidates) for candidates in candidates_by_task.values()
                            ),
                            "feasible_combo_count": 0,
                            "fallback_combo_evaluated_count": 0,
                            "fallback_combo_truncated": False,
                            "exact_enumeration_single_worker": enumerate_all_solutions,
                            "machine_cpu_count": os.cpu_count() or 1,
                        },
                    }
                model.Add(sum(matching_room_vars) == bundle_slot_vars[(bundle_key, day, start_minute)])
                vars_for_task.extend(matching_room_vars)
            model.Add(sum(vars_for_task) == 1)

    for room_id in room_ids:
        for day in DAY_ORDER:
            for minute in range(START_MINUTE, END_MINUTE, 30):
                blockers = []
                for task_index, task in enumerate(tasks):
                    for (
                        candidate_room_id,
                        candidate_day,
                        candidate_start,
                    ) in candidates_by_task[task_index]:
                        if candidate_room_id != room_id or candidate_day != day:
                            continue
                        if _overlap(candidate_start, task.duration_minutes, minute, 30):
                            blockers.append(
                                assignment_vars[
                                    (task_index, room_id, day, candidate_start)
                                ]
                            )
                if blockers:
                    model.Add(sum(blockers) <= 1)

    for day in DAY_ORDER:
        for minute in range(START_MINUTE, END_MINUTE, 30):
            lecturer_blockers: dict[int, list[cp_model.IntVar]] = defaultdict(list)
            student_blockers: dict[int, list[cp_model.IntVar]] = defaultdict(list)
            student_membership_blockers: dict[str, list[cp_model.IntVar]] = defaultdict(list)
            for task_index, task in enumerate(tasks):
                for room_id, candidate_day, candidate_start in candidates_by_task[
                    task_index
                ]:
                    if candidate_day != day or not _overlap(
                        candidate_start, task.duration_minutes, minute, 30
                    ):
                        continue
                    var = assignment_vars[
                        (task_index, room_id, candidate_day, candidate_start)
                    ]
                    for lecturer_id in task.lecturer_ids:
                        lecturer_blockers[lecturer_id].append(var)
                    for student_group_id in task.student_group_ids:
                        if task.bundle_key is not None:
                            bundle_var = bundle_slot_vars.get((task.bundle_key, candidate_day, candidate_start))
                            if bundle_var is not None:
                                student_blockers[student_group_id].append(bundle_var)
                                continue
                        student_blockers[student_group_id].append(var)
                    for student_key in task.student_membership_keys:
                        if task.bundle_key is not None:
                            bundle_var = bundle_slot_vars.get((task.bundle_key, candidate_day, candidate_start))
                            if bundle_var is not None:
                                student_membership_blockers[student_key].append(bundle_var)
                                continue
                        student_membership_blockers[student_key].append(var)
            for vars_for_lecturer in lecturer_blockers.values():
                if vars_for_lecturer:
                    model.Add(sum(vars_for_lecturer) <= 1)
            for blockers_for_group in student_blockers.values():
                unique_vars = list(dict.fromkeys(blockers_for_group))
                if unique_vars:
                    model.Add(sum(unique_vars) <= 1)
            for blockers_for_student in student_membership_blockers.values():
                unique_vars = list(dict.fromkeys(blockers_for_student))
                if unique_vars:
                    model.Add(sum(unique_vars) <= 1)

    occurrence_day_vars: dict[tuple[int, int], dict[str, list[cp_model.IntVar]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for task_index, task in enumerate(tasks):
        for room_id, day, start_minute in candidates_by_task[task_index]:
            bundle_var = None
            if task.bundle_key is not None:
                bundle_var = bundle_slot_vars.get((task.bundle_key, day, start_minute))
            occurrence_day_vars[(task.root_session_id, task.occurrence_index)][day].append(
                bundle_var
                if bundle_var is not None
                else assignment_vars[(task_index, room_id, day, start_minute)]
            )

    occurrence_day_flags: dict[tuple[int, int], dict[str, cp_model.IntVar]] = defaultdict(dict)
    grouped_by_root: dict[int, dict[int, dict[str, list[cp_model.IntVar]]]] = defaultdict(dict)
    for (root_session_id, occurrence_index), by_day in occurrence_day_vars.items():
        grouped_by_root[root_session_id][occurrence_index] = by_day
        for day, vars_for_day in by_day.items():
            unique_vars = list(dict.fromkeys(vars_for_day))
            day_flag = model.NewBoolVar(
                f"occ_{root_session_id}_{occurrence_index}_{day}"
            )
            model.AddMaxEquality(day_flag, unique_vars)
            occurrence_day_flags[(root_session_id, occurrence_index)][day] = day_flag

    if "spread_sessions_across_days" in selected_soft_constraints:
        for root_session_id, occurrences in grouped_by_root.items():
            tasks_for_root = [task for task in tasks if task.root_session_id == root_session_id]
            occurrence_count = max(
                (task.occurrence_index for task in tasks_for_root), default=1
            )
            if occurrence_count <= 1:
                continue
            for day in DAY_ORDER:
                day_flags = []
                for occurrence_index in occurrences:
                    day_flag = occurrence_day_flags[(root_session_id, occurrence_index)].get(day)
                    if day_flag is not None:
                        day_flags.append(day_flag)
                if day_flags:
                    model.Add(sum(day_flags) <= 1)

    if (
        "balance_teaching_load_across_week" in selected_soft_constraints
        or "avoid_monday_overload" in selected_soft_constraints
    ):
        daily_load_vars: dict[str, cp_model.IntVar] = {}
        all_occurrences = sorted(occurrence_day_flags.keys())
        for day in DAY_ORDER:
            day_flags = [
                occurrence_day_flags[occurrence].get(day)
                for occurrence in all_occurrences
                if occurrence_day_flags[occurrence].get(day) is not None
            ]
            if day_flags:
                load_var = model.NewIntVar(0, len(all_occurrences), f"daily_load_{day}")
                model.Add(load_var == sum(day_flags))
            else:
                load_var = model.NewIntVar(0, 0, f"daily_load_{day}")
            daily_load_vars[day] = load_var

        if "balance_teaching_load_across_week" in selected_soft_constraints:
            max_load = model.NewIntVar(0, len(all_occurrences), "max_daily_load")
            min_load = model.NewIntVar(0, len(all_occurrences), "min_daily_load")
            model.AddMaxEquality(max_load, list(daily_load_vars.values()))
            model.AddMinEquality(min_load, list(daily_load_vars.values()))
            model.Add(max_load - min_load <= 2)

        if "avoid_monday_overload" in selected_soft_constraints:
            monday_load = daily_load_vars["Monday"]
            for day in DAY_ORDER[1:]:
                model.Add(monday_load <= daily_load_vars[day] + 1)

    model_build_ms = int((time.perf_counter() - model_build_started_at) * 1000)
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = float(time_limit_seconds)
    solver.parameters.enumerate_all_solutions = enumerate_all_solutions
    solver.parameters.num_search_workers = max(1, int(num_search_workers))
    solver.parameters.max_memory_in_mb = int(DEFAULT_SOLVER_MEMORY_LIMIT_MB)

    collector = _SolutionCollector(assignment_vars, max_solutions)
    solve_started_at = time.perf_counter()
    if enumerate_all_solutions:
        status = solver.SearchForAllSolutions(model, collector)
    else:
        status = solver.Solve(model)
        if status in {cp_model.OPTIMAL, cp_model.FEASIBLE}:
            current: list[tuple[int, int, str, int]] = []
            for key, var in assignment_vars.items():
                if solver.Value(var):
                    current.append(key)
            collector.solutions.append(current)
    solve_ms = int((time.perf_counter() - solve_started_at) * 1000)

    status_name = "feasible" if collector.solutions else "infeasible"
    if status == cp_model.OPTIMAL and collector.solutions:
        status_name = "optimal"
    elif status == cp_model.FEASIBLE and collector.solutions:
        status_name = "feasible"
    elif status == cp_model.UNKNOWN and not collector.solutions:
        status_name = "resource_limited"

    message = "Generated timetable solutions."
    if status_name == "resource_limited":
        message = (
            "Generation stopped without a solution before the bounded solve budget completed. "
            "Try a pruning-friendly constraint set, a higher time limit, or the decomposed large-dataset engine."
        )
    elif not collector.solutions:
        message = _format_diagnostic_message(
            "No possible timetables satisfy the selected constraints.",
            [
                "Check whether high-frequency sessions are competing for the same lecturers, rooms, or cohorts.",
                "Check whether split limits or specific-room requirements are too restrictive for the available rooms.",
                "If you selected nice-to-have constraints, try generating once without them to confirm hard-constraint feasibility.",
            ],
        )
    elif collector.truncated:
        message = "Too many possible timetables to enumerate fully within the configured limit."

    return {
        "status": status_name,
        "message": message,
        "solutions": collector.solutions,
        "truncated": collector.truncated,
        "tasks": tasks,
        "timing": {
            "precheck_ms": precheck_ms,
            "model_build_ms": model_build_ms,
            "solve_ms": solve_ms,
            "fallback_search_ms": 0,
            "total_ms": int((time.perf_counter() - started_at) * 1000),
        },
        "stats": {
            "task_count": len(tasks),
            "assignment_variable_count": len(assignment_vars),
            "candidate_option_count": sum(
                len(candidates) for candidates in candidates_by_task.values()
            ),
            "feasible_combo_count": 0,
            "fallback_combo_evaluated_count": 0,
            "fallback_combo_truncated": False,
            "exact_enumeration_single_worker": bool(
                enumerate_all_solutions and max(1, int(num_search_workers)) == 1
            ),
            "machine_cpu_count": os.cpu_count() or 1,
            "memory_limit_mb": DEFAULT_SOLVER_MEMORY_LIMIT_MB,
            "projected_group_slot_blocker_count": sizing.group_slot_blocker_count,
        },
    }


def _entry_from_assignment(
    task: SessionTask, room: V2Room, day: str, start_minute: int
) -> dict:
    return {
        "session_id": task.session_id,
        "occurrence_index": task.occurrence_index,
        "split_index": task.split_index,
        "room_id": int(room.id),
        "day": day,
        "start_minute": start_minute,
        "duration_minutes": task.duration_minutes,
    }


def _task_eligible_room_ids(task: SessionTask, rooms: list[V2Room]) -> tuple[int, ...]:
    return tuple(sorted(int(room.id) for room in rooms if _room_matches(room, task)))


def _build_room_matching(
    task_indexes: list[int],
    tasks: list[SessionTask],
    eligible_rooms_by_task: dict[int, tuple[int, ...]],
) -> dict[int, int] | None:
    by_task = {
        task_index: list(eligible_rooms_by_task[task_index])
        for task_index in sorted(
            task_indexes,
            key=lambda item: (len(eligible_rooms_by_task[item]), item),
        )
    }
    room_to_task: dict[int, int] = {}

    def assign(task_index: int, seen: set[int]) -> bool:
        for room_id in by_task[task_index]:
            if room_id in seen:
                continue
            seen.add(room_id)
            current = room_to_task.get(room_id)
            if current is None or assign(current, seen):
                room_to_task[room_id] = task_index
                return True
        return False

    for task_index in by_task:
        if not assign(task_index, set()):
            return None
    return {task_index: room_id for room_id, task_index in room_to_task.items()}


def _build_day_room_matching(
    assigned_entries: list[tuple[int, int]],
    tasks: list[SessionTask],
    eligible_rooms_by_task: dict[int, tuple[int, ...]],
) -> dict[int, int] | None:
    entry_by_task = {task_index: start_minute for task_index, start_minute in assigned_entries}
    task_indexes = tuple(sorted(entry_by_task))
    room_assignments: dict[int, list[tuple[int, int, int]]] = defaultdict(list)
    task_to_room: dict[int, int] = {}
    feasible_cache: dict[tuple[int, frozenset[tuple[int, tuple[tuple[int, int], ...]]]], tuple[int, ...]] = {}

    def feasible_rooms(task_index: int) -> tuple[int, ...]:
        cache_key = (
            task_index,
            frozenset(
                (room_id, tuple(slots))
                for room_id, slots in room_assignments.items()
            ),
        )
        cached = feasible_cache.get(cache_key)
        if cached is not None:
            return cached
        task = tasks[task_index]
        start_minute = entry_by_task[task_index]
        result = tuple(
            room_id
            for room_id in eligible_rooms_by_task[task_index]
            if all(
                not _overlap(
                    start_minute,
                    task.duration_minutes,
                    assigned_start,
                    assigned_end - assigned_start,
                )
                for _, assigned_start, assigned_end in room_assignments[room_id]
            )
        )
        feasible_cache[cache_key] = result
        return result

    def choose_next_task() -> tuple[int, tuple[int, ...]] | None:
        best_task_index: int | None = None
        best_rooms: tuple[int, ...] = ()
        best_key: tuple[int, int, int, int] | None = None
        for task_index in task_indexes:
            if task_index in task_to_room:
                continue
            rooms = feasible_rooms(task_index)
            task = tasks[task_index]
            start_minute = entry_by_task[task_index]
            key = (
                len(rooms),
                len(eligible_rooms_by_task[task_index]),
                -task.duration_minutes,
                start_minute,
            )
            if best_key is None or key < best_key:
                best_key = key
                best_task_index = task_index
                best_rooms = rooms
                if len(best_rooms) <= 1:
                    break
        if best_task_index is None:
            return None
        return best_task_index, best_rooms

    def assign() -> bool:
        choice = choose_next_task()
        if choice is None:
            return True
        task_index, rooms = choice
        task = tasks[task_index]
        start_minute = entry_by_task[task_index]
        end_minute = start_minute + task.duration_minutes
        if not rooms:
            return False
        for room_id in rooms:
            room_assignments[room_id].append((task_index, start_minute, end_minute))
            task_to_room[task_index] = room_id
            if assign():
                return True
            room_assignments[room_id].pop()
            task_to_room.pop(task_index, None)
        return False

    return task_to_room if assign() else None


def _diagnose_day_room_infeasibility(
    assigned_entries: list[tuple[int, int]],
    tasks: list[SessionTask],
    eligible_rooms_by_task: dict[int, tuple[int, ...]],
    rooms: list[V2Room],
) -> str:
    room_by_id = {int(room.id): room for room in rooms}
    pressure_by_pool: dict[tuple[str, str | None], dict[str, int]] = {}

    for minute in range(START_MINUTE, END_MINUTE, 30):
        overlapping = [
            (task_index, start_minute)
            for task_index, start_minute in assigned_entries
            if _overlap(
                start_minute,
                tasks[task_index].duration_minutes,
                minute,
                30,
            )
        ]
        if not overlapping:
            continue

        by_pool: dict[tuple[str, str | None], set[int]] = defaultdict(set)
        demand_by_pool: Counter[tuple[str, str | None]] = Counter()
        for task_index, _ in overlapping:
            eligible_rooms = eligible_rooms_by_task[task_index]
            pools = {
                (room_by_id[room_id].room_type, room_by_id[room_id].lab_type)
                for room_id in eligible_rooms
            }
            for pool in pools:
                demand_by_pool[pool] += 1
            for room_id in eligible_rooms:
                room = room_by_id[room_id]
                by_pool[(room.room_type, room.lab_type)].add(room_id)

        for pool, demand in demand_by_pool.items():
            capacity = len(by_pool.get(pool, set()))
            if demand > capacity:
                current = pressure_by_pool.setdefault(
                    pool,
                    {
                        "minute": minute,
                        "demand": demand,
                        "capacity": capacity,
                    },
                )
                if demand - capacity > current["demand"] - current["capacity"]:
                    current["minute"] = minute
                    current["demand"] = demand
                    current["capacity"] = capacity

    if not pressure_by_pool:
        return "Exact room assignment failed for a dense day layout, but no single room pool overload was isolated."

    pool, summary = max(
        pressure_by_pool.items(),
        key=lambda item: item[1]["demand"] - item[1]["capacity"],
    )
    room_type, lab_type = pool
    label = f"{room_type} rooms"
    if lab_type:
        label = f"{lab_type} labs"
    hour = summary["minute"] // 60
    minute = summary["minute"] % 60
    return (
        f"Exact room assignment failed because {label} were overloaded around "
        f"{hour:02d}:{minute:02d}. Demand was {summary['demand']} tasks for "
        f"{summary['capacity']} eligible rooms in that pool."
    )


def _solve_internal_decomposed(
    db: Session,
    selected_soft_constraints: list[str],
    max_solutions: int,
    time_limit_seconds: int,
    *,
    enumerate_all_solutions: bool = True,
    num_search_workers: int = 1,
    max_retry_cuts: int = 12,
) -> dict:
    started_at = time.perf_counter()
    sessions = (
        db.query(V2Session)
        .options(
            joinedload(V2Session.module),
            joinedload(V2Session.linked_modules),
            joinedload(V2Session.lecturers),
            joinedload(V2Session.student_groups).joinedload(V2StudentGroup.degree),
            joinedload(V2Session.student_groups).joinedload(V2StudentGroup.path),
        )
        .order_by(V2Session.id)
        .all()
    )
    rooms = db.query(V2Room).order_by(V2Room.id).all()

    try:
        tasks = _build_tasks(db)
    except ValueError as exc:
        result = _solve_internal_legacy(
            db,
            selected_soft_constraints,
            max_solutions,
            time_limit_seconds,
            enumerate_all_solutions=enumerate_all_solutions,
            num_search_workers=num_search_workers,
        )
        result["stats"]["solver_engine"] = "legacy_guarded"
        return result

    if not tasks or not rooms:
        result = _solve_internal_legacy(
            db,
            selected_soft_constraints,
            max_solutions,
            time_limit_seconds,
            enumerate_all_solutions=enumerate_all_solutions,
            num_search_workers=num_search_workers,
        )
        result["stats"]["solver_engine"] = "legacy_guarded"
        return result

    precheck_started_at = time.perf_counter()
    lecturer_names = {
        int(lecturer.id): lecturer.name
        for session in sessions
        for lecturer in session.lecturers
    }
    group_names = {
        int(group.id): group.name
        for session in sessions
        for group in session.student_groups
    }
    diagnostics = _precheck_diagnostics(tasks, rooms, lecturer_names, group_names)
    precheck_ms = int((time.perf_counter() - precheck_started_at) * 1000)
    if diagnostics:
        result = _solve_internal_legacy(
            db,
            selected_soft_constraints,
            max_solutions,
            time_limit_seconds,
            enumerate_all_solutions=enumerate_all_solutions,
            num_search_workers=num_search_workers,
        )
        result["stats"]["solver_engine"] = "legacy_guarded"
        return result

    eligible_rooms_by_task = {
        task_index: _task_eligible_room_ids(task, rooms)
        for task_index, task in enumerate(tasks)
    }
    room_pool_by_task: dict[int, tuple[str, str | None] | None] = {}
    room_capacity_by_pool: Counter[tuple[str, str | None]] = Counter()
    room_by_id = {int(room.id): room for room in rooms}
    for room in rooms:
        room_capacity_by_pool[(room.room_type, room.lab_type)] += 1
    for task_index, eligible_rooms in eligible_rooms_by_task.items():
        pools = {
            (room_by_id[room_id].room_type, room_by_id[room_id].lab_type)
            for room_id in eligible_rooms
        }
        room_pool_by_task[task_index] = next(iter(pools)) if len(pools) == 1 else None
    slot_candidates_by_task: dict[int, list[tuple[str, int]]] = {}
    legacy_candidate_option_count = 0
    for task_index, task in enumerate(tasks):
        starts = [
            (day, start_minute)
            for day, start_minute in _candidate_starts(task)
            if _soft_constraint_allows_start(
                task, day, start_minute, selected_soft_constraints
            )
        ]
        slot_candidates_by_task[task_index] = starts
        legacy_candidate_option_count += len(starts) * len(eligible_rooms_by_task[task_index])

    if any(not starts for starts in slot_candidates_by_task.values()):
        return {
            "status": "infeasible",
            "message": "Some sessions have no valid time options.",
            "solutions": [],
            "truncated": False,
            "tasks": tasks,
            "timing": {
                "precheck_ms": precheck_ms,
                "model_build_ms": 0,
                "solve_ms": 0,
                "fallback_search_ms": 0,
                "total_ms": int((time.perf_counter() - started_at) * 1000),
                "room_assignment_ms": 0,
            },
            "stats": {
                "task_count": len(tasks),
                "assignment_variable_count": 0,
                "candidate_option_count": legacy_candidate_option_count,
                "feasible_combo_count": 0,
                "fallback_combo_evaluated_count": 0,
                "fallback_combo_truncated": False,
                "exact_enumeration_single_worker": False,
                "machine_cpu_count": os.cpu_count() or 1,
                "memory_limit_mb": DEFAULT_SOLVER_MEMORY_LIMIT_MB,
                "projected_group_slot_blocker_count": 0,
                "slot_variable_count": 0,
                "room_assignment_retry_count": 0,
                "room_assignment_failures": 0,
                "room_assignment_ms": 0,
                "solver_engine": "decomposed_exact",
                "domain_reduction_ratio": 0.0,
            },
        }

    retry_cuts: list[tuple[str, tuple[tuple[int, int], ...]]] = []
    room_assignment_failures = 0
    room_assignment_ms = 0
    last_room_assignment_diagnostic = ""

    for retry_index in range(max_retry_cuts + 1):
        model_build_started_at = time.perf_counter()
        model = cp_model.CpModel()
        slot_vars: dict[tuple[int, str, int], cp_model.IntVar] = {}
        bundle_tasks: dict[tuple[int, int], list[int]] = defaultdict(list)

        for task_index, task in enumerate(tasks):
            if task.bundle_key is not None:
                bundle_tasks[task.bundle_key].append(task_index)

        bundle_slot_vars: dict[tuple[tuple[int, int], str, int], cp_model.IntVar] = {}
        for bundle_key, task_indexes in bundle_tasks.items():
            shared_slots: set[tuple[str, int]] | None = None
            for task_index in task_indexes:
                task_slots = set(slot_candidates_by_task[task_index])
                shared_slots = task_slots if shared_slots is None else shared_slots & task_slots
            if not shared_slots:
                return {
                    "status": "infeasible",
                    "message": "Some parallel-room sessions have no shared time options across required rooms.",
                    "solutions": [],
                    "truncated": False,
                    "tasks": tasks,
                    "timing": {
                        "precheck_ms": precheck_ms,
                        "model_build_ms": int((time.perf_counter() - model_build_started_at) * 1000),
                        "solve_ms": 0,
                        "fallback_search_ms": 0,
                        "total_ms": int((time.perf_counter() - started_at) * 1000),
                        "room_assignment_ms": room_assignment_ms,
                    },
                    "stats": {
                        "task_count": len(tasks),
                        "assignment_variable_count": 0,
                        "candidate_option_count": legacy_candidate_option_count,
                        "feasible_combo_count": 0,
                        "fallback_combo_evaluated_count": 0,
                        "fallback_combo_truncated": False,
                        "exact_enumeration_single_worker": False,
                        "machine_cpu_count": os.cpu_count() or 1,
                        "memory_limit_mb": DEFAULT_SOLVER_MEMORY_LIMIT_MB,
                        "projected_group_slot_blocker_count": 0,
                        "slot_variable_count": 0,
                        "room_assignment_retry_count": retry_index,
                        "room_assignment_failures": room_assignment_failures,
                        "room_assignment_ms": room_assignment_ms,
                        "solver_engine": "decomposed_exact",
                        "domain_reduction_ratio": 0.0,
                    },
                }
            shared_slot_vars = []
            for day, start_minute in sorted(shared_slots, key=lambda item: (DAY_INDEX[item[0]], item[1])):
                bundle_var = model.NewBoolVar(
                    f"bundle_{bundle_key[0]}_{bundle_key[1]}_{day}_{start_minute}"
                )
                bundle_slot_vars[(bundle_key, day, start_minute)] = bundle_var
                shared_slot_vars.append(bundle_var)
            model.Add(sum(shared_slot_vars) == 1)

        for task_index, task in enumerate(tasks):
            if task.bundle_key is not None:
                for day, start_minute in slot_candidates_by_task[task_index]:
                    bundle_var = bundle_slot_vars.get((task.bundle_key, day, start_minute))
                    if bundle_var is not None:
                        slot_vars[(task_index, day, start_minute)] = bundle_var
                continue
            vars_for_task = []
            for day, start_minute in slot_candidates_by_task[task_index]:
                var = model.NewBoolVar(f"task_{task_index}_{day}_{start_minute}")
                slot_vars[(task_index, day, start_minute)] = var
                vars_for_task.append(var)
            model.Add(sum(vars_for_task) == 1)

        slot_variable_count = len(
            {
                key
                for key in slot_vars
                if tasks[key[0]].bundle_key is None
            }
        )
        domain_reduction_ratio = 1.0 - (
            slot_variable_count / max(1, legacy_candidate_option_count)
        )

        for day, task_assignments in retry_cuts:
            cut_vars = [
                slot_vars[(task_index, day, start_minute)]
                for task_index, start_minute in task_assignments
            ]
            model.Add(sum(cut_vars) <= len(cut_vars) - 1)

        for day in DAY_ORDER:
            for minute in range(START_MINUTE, END_MINUTE, 30):
                lecturer_blockers: dict[int, list[cp_model.IntVar]] = defaultdict(list)
                student_blockers: dict[int, list[cp_model.IntVar]] = defaultdict(list)
                student_membership_blockers: dict[str, list[cp_model.IntVar]] = defaultdict(list)
                singleton_room_blockers: dict[int, list[cp_model.IntVar]] = defaultdict(list)
                room_pool_blockers: dict[tuple[str, str | None], list[cp_model.IntVar]] = defaultdict(list)
                for task_index, task in enumerate(tasks):
                    for candidate_day, candidate_start in slot_candidates_by_task[task_index]:
                        if candidate_day != day or not _overlap(
                            candidate_start, task.duration_minutes, minute, 30
                        ):
                            continue
                        var = slot_vars[(task_index, candidate_day, candidate_start)]
                        for lecturer_id in task.lecturer_ids:
                            lecturer_blockers[lecturer_id].append(var)
                        for student_group_id in task.student_group_ids:
                            student_blockers[student_group_id].append(var)
                        for student_key in task.student_membership_keys:
                            student_membership_blockers[student_key].append(var)
                        eligible_rooms = eligible_rooms_by_task[task_index]
                        if len(eligible_rooms) == 1:
                            singleton_room_blockers[eligible_rooms[0]].append(var)
                        room_pool = room_pool_by_task[task_index]
                        if room_pool is not None:
                            room_pool_blockers[room_pool].append(var)
                for vars_for_lecturer in lecturer_blockers.values():
                    if vars_for_lecturer:
                        model.Add(sum(dict.fromkeys(vars_for_lecturer)) <= 1)
                for blockers_for_group in student_blockers.values():
                    unique_vars = list(dict.fromkeys(blockers_for_group))
                    if unique_vars:
                        model.Add(sum(unique_vars) <= 1)
                for blockers_for_student in student_membership_blockers.values():
                    unique_vars = list(dict.fromkeys(blockers_for_student))
                    if unique_vars:
                        model.Add(sum(unique_vars) <= 1)
                for blockers_for_room in singleton_room_blockers.values():
                    unique_vars = list(dict.fromkeys(blockers_for_room))
                    if unique_vars:
                        model.Add(sum(unique_vars) <= 1)
                for room_pool, blockers_for_pool in room_pool_blockers.items():
                    unique_vars = list(dict.fromkeys(blockers_for_pool))
                    if unique_vars:
                        model.Add(sum(unique_vars) <= room_capacity_by_pool[room_pool])

        decision_vars: list[cp_model.IntVar] = []
        for task_index, task in sorted(
            enumerate(tasks),
            key=lambda item: (
                len(eligible_rooms_by_task[item[0]]),
                len(slot_candidates_by_task[item[0]]),
                -item[1].duration_minutes,
                item[0],
            ),
        ):
            seen_vars: set[int] = set()
            for day, start_minute in slot_candidates_by_task[task_index]:
                var = slot_vars[(task_index, day, start_minute)]
                if id(var) in seen_vars:
                    continue
                seen_vars.add(id(var))
                decision_vars.append(var)
        if decision_vars:
            model.AddDecisionStrategy(
                decision_vars,
                cp_model.CHOOSE_FIRST,
                cp_model.SELECT_MAX_VALUE,
            )

        occurrence_day_vars: dict[tuple[int, int], dict[str, list[cp_model.IntVar]]] = defaultdict(
            lambda: defaultdict(list)
        )
        for task_index, task in enumerate(tasks):
            for day, start_minute in slot_candidates_by_task[task_index]:
                occurrence_day_vars[(task.root_session_id, task.occurrence_index)][day].append(
                    slot_vars[(task_index, day, start_minute)]
                )

        occurrence_day_flags: dict[tuple[int, int], dict[str, cp_model.IntVar]] = defaultdict(dict)
        grouped_by_root: dict[int, dict[int, dict[str, list[cp_model.IntVar]]]] = defaultdict(dict)
        for (root_session_id, occurrence_index), by_day in occurrence_day_vars.items():
            grouped_by_root[root_session_id][occurrence_index] = by_day
            for day, vars_for_day in by_day.items():
                unique_vars = list(dict.fromkeys(vars_for_day))
                day_flag = model.NewBoolVar(
                    f"occ_{root_session_id}_{occurrence_index}_{day}"
                )
                model.AddMaxEquality(day_flag, unique_vars)
                occurrence_day_flags[(root_session_id, occurrence_index)][day] = day_flag

        if "spread_sessions_across_days" in selected_soft_constraints:
            for root_session_id, occurrences in grouped_by_root.items():
                occurrence_count = max(occurrences.keys(), default=1)
                if occurrence_count <= 1:
                    continue
                for day in DAY_ORDER:
                    day_flags = [
                        occurrence_day_flags[(root_session_id, occurrence_index)].get(day)
                        for occurrence_index in occurrences
                        if occurrence_day_flags[(root_session_id, occurrence_index)].get(day) is not None
                    ]
                    if day_flags:
                        model.Add(sum(day_flags) <= 1)

        if (
            "balance_teaching_load_across_week" in selected_soft_constraints
            or "avoid_monday_overload" in selected_soft_constraints
        ):
            daily_load_vars: dict[str, cp_model.IntVar] = {}
            all_occurrences = sorted(occurrence_day_flags.keys())
            for day in DAY_ORDER:
                day_flags = [
                    occurrence_day_flags[occurrence].get(day)
                    for occurrence in all_occurrences
                    if occurrence_day_flags[occurrence].get(day) is not None
                ]
                if day_flags:
                    load_var = model.NewIntVar(0, len(all_occurrences), f"daily_load_{day}")
                    model.Add(load_var == sum(day_flags))
                else:
                    load_var = model.NewIntVar(0, 0, f"daily_load_{day}")
                daily_load_vars[day] = load_var

            if "balance_teaching_load_across_week" in selected_soft_constraints:
                max_load = model.NewIntVar(0, len(all_occurrences), "max_daily_load")
                min_load = model.NewIntVar(0, len(all_occurrences), "min_daily_load")
                model.AddMaxEquality(max_load, list(daily_load_vars.values()))
                model.AddMinEquality(min_load, list(daily_load_vars.values()))
                model.Add(max_load - min_load <= 2)

            if "avoid_monday_overload" in selected_soft_constraints:
                monday_load = daily_load_vars["Monday"]
                for day in DAY_ORDER[1:]:
                    model.Add(monday_load <= daily_load_vars[day] + 1)

        model_build_ms = int((time.perf_counter() - model_build_started_at) * 1000)
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = float(time_limit_seconds)
        solver.parameters.enumerate_all_solutions = False
        solver.parameters.num_search_workers = max(1, int(num_search_workers))
        solver.parameters.max_memory_in_mb = int(DEFAULT_SOLVER_MEMORY_LIMIT_MB)
        solver.parameters.search_branching = cp_model.FIXED_SEARCH

        solve_started_at = time.perf_counter()
        status = solver.Solve(model)
        solve_ms = int((time.perf_counter() - solve_started_at) * 1000)

        if status == cp_model.UNKNOWN:
            return _resource_limited_result(
                started_at,
                tasks,
                message=(
                    "Generation stopped without a solution before the bounded solve budget completed. "
                    "The decomposed engine reduced the search space, but this run still exhausted the current local time or memory budget."
                ),
                precheck_ms=precheck_ms,
                model_build_ms=model_build_ms,
                solve_ms=solve_ms,
                assignment_variable_count=slot_variable_count,
                candidate_option_count=legacy_candidate_option_count,
                group_slot_blocker_count=0,
                enumerate_all_solutions=False,
            ) | {
                "timing": {
                    "precheck_ms": precheck_ms,
                    "model_build_ms": model_build_ms,
                    "solve_ms": solve_ms,
                    "fallback_search_ms": 0,
                    "total_ms": int((time.perf_counter() - started_at) * 1000),
                    "room_assignment_ms": room_assignment_ms,
                },
                "stats": {
                    "task_count": len(tasks),
                    "assignment_variable_count": slot_variable_count,
                    "candidate_option_count": legacy_candidate_option_count,
                    "feasible_combo_count": 0,
                    "fallback_combo_evaluated_count": 0,
                    "fallback_combo_truncated": False,
                    "exact_enumeration_single_worker": False,
                    "machine_cpu_count": os.cpu_count() or 1,
                    "memory_limit_mb": DEFAULT_SOLVER_MEMORY_LIMIT_MB,
                    "projected_group_slot_blocker_count": 0,
                    "slot_variable_count": slot_variable_count,
                    "room_assignment_retry_count": retry_index,
                    "room_assignment_failures": room_assignment_failures,
                    "room_assignment_ms": room_assignment_ms,
                    "solver_engine": "decomposed_exact",
                    "domain_reduction_ratio": domain_reduction_ratio,
                },
            }

        if status not in {cp_model.OPTIMAL, cp_model.FEASIBLE}:
            return {
                "status": "infeasible",
                "message": _format_diagnostic_message(
                    "No possible timetables satisfy the selected constraints.",
                    [
                        "Check whether high-frequency sessions are competing for the same lecturers, rooms, or cohorts.",
                        "Check whether split limits or specific-room requirements are too restrictive for the available rooms.",
                        "If you selected nice-to-have constraints, try generating once without them to confirm hard-constraint feasibility.",
                    ],
                ),
                "solutions": [],
                "truncated": False,
                "tasks": tasks,
                "timing": {
                    "precheck_ms": precheck_ms,
                    "model_build_ms": model_build_ms,
                    "solve_ms": solve_ms,
                    "fallback_search_ms": 0,
                    "total_ms": int((time.perf_counter() - started_at) * 1000),
                    "room_assignment_ms": room_assignment_ms,
                },
                "stats": {
                    "task_count": len(tasks),
                    "assignment_variable_count": slot_variable_count,
                    "candidate_option_count": legacy_candidate_option_count,
                    "feasible_combo_count": 0,
                    "fallback_combo_evaluated_count": 0,
                    "fallback_combo_truncated": False,
                    "exact_enumeration_single_worker": False,
                    "machine_cpu_count": os.cpu_count() or 1,
                    "memory_limit_mb": DEFAULT_SOLVER_MEMORY_LIMIT_MB,
                    "projected_group_slot_blocker_count": 0,
                    "slot_variable_count": slot_variable_count,
                    "room_assignment_retry_count": retry_index,
                    "room_assignment_failures": room_assignment_failures,
                    "room_assignment_ms": room_assignment_ms,
                    "solver_engine": "decomposed_exact",
                    "domain_reduction_ratio": domain_reduction_ratio,
                },
            }

        assigned_by_day: dict[str, list[tuple[int, int]]] = defaultdict(list)
        for task_index in range(len(tasks)):
            for day, start_minute in slot_candidates_by_task[task_index]:
                if solver.Value(slot_vars[(task_index, day, start_minute)]):
                    assigned_by_day[day].append((task_index, start_minute))
                    break

        room_matching_started_at = time.perf_counter()
        final_solution: list[tuple[int, int, str, int]] = []
        failed_cut: tuple[str, tuple[tuple[int, int], ...]] | None = None
        for day, entries in sorted(
            assigned_by_day.items(),
            key=lambda item: DAY_INDEX[item[0]],
        ):
            matching = _build_day_room_matching(entries, tasks, eligible_rooms_by_task)
            if matching is None:
                failed_cut = (day, tuple(sorted(entries)))
                room_assignment_failures += 1
                last_room_assignment_diagnostic = _diagnose_day_room_infeasibility(
                    entries,
                    tasks,
                    eligible_rooms_by_task,
                    rooms,
                )
                break
            start_by_task = {task_index: start for task_index, start in entries}
            for task_index, room_id in matching.items():
                final_solution.append((task_index, room_id, day, start_by_task[task_index]))
        room_assignment_ms += int((time.perf_counter() - room_matching_started_at) * 1000)

        if failed_cut is None:
            return {
                "status": "optimal" if status == cp_model.OPTIMAL else "feasible",
                "message": "Generated timetable solutions.",
                "solutions": [sorted(final_solution)],
                "truncated": False,
                "tasks": tasks,
                "timing": {
                    "precheck_ms": precheck_ms,
                    "model_build_ms": model_build_ms,
                    "solve_ms": solve_ms,
                    "fallback_search_ms": 0,
                    "total_ms": int((time.perf_counter() - started_at) * 1000),
                    "room_assignment_ms": room_assignment_ms,
                },
                "stats": {
                    "task_count": len(tasks),
                    "assignment_variable_count": slot_variable_count,
                    "candidate_option_count": legacy_candidate_option_count,
                    "feasible_combo_count": 0,
                    "fallback_combo_evaluated_count": 0,
                    "fallback_combo_truncated": False,
                    "exact_enumeration_single_worker": False,
                    "machine_cpu_count": os.cpu_count() or 1,
                    "memory_limit_mb": DEFAULT_SOLVER_MEMORY_LIMIT_MB,
                    "projected_group_slot_blocker_count": 0,
                    "slot_variable_count": slot_variable_count,
                    "room_assignment_retry_count": retry_index,
                    "room_assignment_failures": room_assignment_failures,
                    "room_assignment_ms": room_assignment_ms,
                    "solver_engine": "decomposed_exact",
                    "domain_reduction_ratio": domain_reduction_ratio,
                },
            }

        retry_cuts.append(failed_cut)

    return _resource_limited_result(
        started_at,
        tasks,
        message=(
            "Generation was stopped because exact room assignment could not be completed within the local retry budget. "
            "The time assignment stage found candidate schedules, but concrete room matching kept failing. "
            f"{last_room_assignment_diagnostic}".strip()
        ),
        precheck_ms=precheck_ms,
        solve_ms=0,
        model_build_ms=0,
        assignment_variable_count=0,
        candidate_option_count=legacy_candidate_option_count,
        group_slot_blocker_count=0,
        enumerate_all_solutions=False,
    ) | {
        "timing": {
            "precheck_ms": precheck_ms,
            "model_build_ms": 0,
            "solve_ms": 0,
            "fallback_search_ms": 0,
            "total_ms": int((time.perf_counter() - started_at) * 1000),
            "room_assignment_ms": room_assignment_ms,
        },
        "stats": {
            "task_count": len(tasks),
            "assignment_variable_count": 0,
            "candidate_option_count": legacy_candidate_option_count,
            "feasible_combo_count": 0,
            "fallback_combo_evaluated_count": 0,
            "fallback_combo_truncated": False,
            "exact_enumeration_single_worker": False,
            "machine_cpu_count": os.cpu_count() or 1,
            "memory_limit_mb": DEFAULT_SOLVER_MEMORY_LIMIT_MB,
            "projected_group_slot_blocker_count": 0,
            "slot_variable_count": 0,
            "room_assignment_retry_count": max_retry_cuts,
            "room_assignment_failures": room_assignment_failures,
            "room_assignment_ms": room_assignment_ms,
            "solver_engine": "decomposed_exact",
            "domain_reduction_ratio": 0.0,
        },
    }


def _solve_internal(
    db: Session,
    selected_soft_constraints: list[str],
    max_solutions: int,
    time_limit_seconds: int,
    *,
    enumerate_all_solutions: bool = True,
    num_search_workers: int = 1,
) -> dict:
    session_count = db.query(V2Session).count()
    if session_count > LARGE_DATASET_SESSION_THRESHOLD:
        return _solve_internal_decomposed(
            db,
            selected_soft_constraints,
            max_solutions,
            time_limit_seconds,
            enumerate_all_solutions=enumerate_all_solutions,
            num_search_workers=num_search_workers,
        )
    result = _solve_internal_legacy(
        db,
        selected_soft_constraints,
        max_solutions,
        time_limit_seconds,
        enumerate_all_solutions=enumerate_all_solutions,
        num_search_workers=num_search_workers,
    )
    result["stats"].setdefault("solver_engine", "legacy_guarded")
    result["timing"].setdefault("room_assignment_ms", 0)
    result["stats"].setdefault("slot_variable_count", 0)
    result["stats"].setdefault("room_assignment_retry_count", 0)
    result["stats"].setdefault("room_assignment_failures", 0)
    result["stats"].setdefault("room_assignment_ms", 0)
    result["stats"].setdefault("domain_reduction_ratio", 0.0)
    return result


def _solve_snapshot_internal(
    *,
    tasks: list[SessionTask],
    rooms: list[SnapshotRoom],
    lecturer_names: dict[int, str],
    group_names: dict[int, str],
    selected_soft_constraints: list[str],
    max_solutions: int,
    time_limit_seconds: int,
    num_search_workers: int = 1,
    max_retry_cuts: int = 12,
) -> dict:
    started_at = time.perf_counter()
    if not tasks:
        return {
            "status": "empty",
            "message": "Enter session data before generating a timetable.",
            "solutions": [],
            "truncated": False,
            "tasks": tasks,
            "timing": {
                "precheck_ms": 0,
                "model_build_ms": 0,
                "solve_ms": 0,
                "fallback_search_ms": 0,
                "total_ms": int((time.perf_counter() - started_at) * 1000),
                "room_assignment_ms": 0,
            },
            "stats": {
                "task_count": 0,
                "assignment_variable_count": 0,
                "candidate_option_count": 0,
                "feasible_combo_count": 0,
                "fallback_combo_evaluated_count": 0,
                "fallback_combo_truncated": False,
                "exact_enumeration_single_worker": False,
                "machine_cpu_count": os.cpu_count() or 1,
                "memory_limit_mb": DEFAULT_SOLVER_MEMORY_LIMIT_MB,
                "projected_group_slot_blocker_count": 0,
                "slot_variable_count": 0,
                "room_assignment_retry_count": 0,
                "room_assignment_failures": 0,
                "room_assignment_ms": 0,
                "solver_engine": "snapshot_decomposed_exact",
                "domain_reduction_ratio": 0.0,
            },
        }
    if not rooms:
        return {
            "status": "infeasible",
            "message": "No rooms available for timetable generation.",
            "solutions": [],
            "truncated": False,
            "tasks": tasks,
            "timing": {
                "precheck_ms": 0,
                "model_build_ms": 0,
                "solve_ms": 0,
                "fallback_search_ms": 0,
                "total_ms": int((time.perf_counter() - started_at) * 1000),
                "room_assignment_ms": 0,
            },
            "stats": {
                "task_count": len(tasks),
                "assignment_variable_count": 0,
                "candidate_option_count": 0,
                "feasible_combo_count": 0,
                "fallback_combo_evaluated_count": 0,
                "fallback_combo_truncated": False,
                "exact_enumeration_single_worker": False,
                "machine_cpu_count": os.cpu_count() or 1,
                "memory_limit_mb": DEFAULT_SOLVER_MEMORY_LIMIT_MB,
                "projected_group_slot_blocker_count": 0,
                "slot_variable_count": 0,
                "room_assignment_retry_count": 0,
                "room_assignment_failures": 0,
                "room_assignment_ms": 0,
                "solver_engine": "snapshot_decomposed_exact",
                "domain_reduction_ratio": 0.0,
            },
        }

    precheck_started_at = time.perf_counter()
    diagnostics = _precheck_diagnostics(tasks, rooms, lecturer_names, group_names)
    precheck_ms = int((time.perf_counter() - precheck_started_at) * 1000)
    if diagnostics:
        return {
            "status": "infeasible",
            "message": _format_diagnostic_message(
                "No possible timetables satisfy the current hard constraints.",
                diagnostics,
            ),
            "solutions": [],
            "truncated": False,
            "tasks": tasks,
            "timing": {
                "precheck_ms": precheck_ms,
                "model_build_ms": 0,
                "solve_ms": 0,
                "fallback_search_ms": 0,
                "total_ms": int((time.perf_counter() - started_at) * 1000),
                "room_assignment_ms": 0,
            },
            "stats": {
                "task_count": len(tasks),
                "assignment_variable_count": 0,
                "candidate_option_count": 0,
                "feasible_combo_count": 0,
                "fallback_combo_evaluated_count": 0,
                "fallback_combo_truncated": False,
                "exact_enumeration_single_worker": False,
                "machine_cpu_count": os.cpu_count() or 1,
                "memory_limit_mb": DEFAULT_SOLVER_MEMORY_LIMIT_MB,
                "projected_group_slot_blocker_count": 0,
                "slot_variable_count": 0,
                "room_assignment_retry_count": 0,
                "room_assignment_failures": 0,
                "room_assignment_ms": 0,
                "solver_engine": "snapshot_decomposed_exact",
                "domain_reduction_ratio": 0.0,
            },
        }

    eligible_rooms_by_task = {
        task_index: _task_eligible_room_ids(task, rooms)
        for task_index, task in enumerate(tasks)
    }
    room_pool_by_task: dict[int, tuple[str, str | None] | None] = {}
    room_capacity_by_pool: Counter[tuple[str, str | None]] = Counter()
    room_by_id = {int(room.id): room for room in rooms}
    for room in rooms:
        room_capacity_by_pool[(room.room_type, room.lab_type)] += 1
    for task_index, eligible_rooms in eligible_rooms_by_task.items():
        pools = {
            (room_by_id[room_id].room_type, room_by_id[room_id].lab_type)
            for room_id in eligible_rooms
        }
        room_pool_by_task[task_index] = next(iter(pools)) if len(pools) == 1 else None

    slot_candidates_by_task: dict[int, list[tuple[str, int]]] = {}
    legacy_candidate_option_count = 0
    for task_index, task in enumerate(tasks):
        starts = [
            (day, start_minute)
            for day, start_minute in _candidate_starts(task)
            if _soft_constraint_allows_start(
                task, day, start_minute, selected_soft_constraints
            )
        ]
        slot_candidates_by_task[task_index] = starts
        legacy_candidate_option_count += len(starts) * len(eligible_rooms_by_task[task_index])

    if any(not starts for starts in slot_candidates_by_task.values()):
        return {
            "status": "infeasible",
            "message": "Some sessions have no valid time options.",
            "solutions": [],
            "truncated": False,
            "tasks": tasks,
            "timing": {
                "precheck_ms": precheck_ms,
                "model_build_ms": 0,
                "solve_ms": 0,
                "fallback_search_ms": 0,
                "total_ms": int((time.perf_counter() - started_at) * 1000),
                "room_assignment_ms": 0,
            },
            "stats": {
                "task_count": len(tasks),
                "assignment_variable_count": 0,
                "candidate_option_count": legacy_candidate_option_count,
                "feasible_combo_count": 0,
                "fallback_combo_evaluated_count": 0,
                "fallback_combo_truncated": False,
                "exact_enumeration_single_worker": False,
                "machine_cpu_count": os.cpu_count() or 1,
                "memory_limit_mb": DEFAULT_SOLVER_MEMORY_LIMIT_MB,
                "projected_group_slot_blocker_count": 0,
                "slot_variable_count": 0,
                "room_assignment_retry_count": 0,
                "room_assignment_failures": 0,
                "room_assignment_ms": 0,
                "solver_engine": "snapshot_decomposed_exact",
                "domain_reduction_ratio": 0.0,
            },
        }

    retry_cuts: list[tuple[str, tuple[tuple[int, int], ...]]] = []
    room_assignment_failures = 0
    room_assignment_ms = 0
    last_room_assignment_diagnostic = ""

    for retry_index in range(max_retry_cuts + 1):
        model_build_started_at = time.perf_counter()
        model = cp_model.CpModel()
        slot_vars: dict[tuple[int, str, int], cp_model.IntVar] = {}
        bundle_tasks: dict[tuple[int, int], list[int]] = defaultdict(list)

        for task_index, task in enumerate(tasks):
            if task.bundle_key is not None:
                bundle_tasks[task.bundle_key].append(task_index)

        bundle_slot_vars: dict[tuple[tuple[int, int], str, int], cp_model.IntVar] = {}
        for bundle_key, task_indexes in bundle_tasks.items():
            shared_slots: set[tuple[str, int]] | None = None
            for task_index in task_indexes:
                task_slots = set(slot_candidates_by_task[task_index])
                shared_slots = task_slots if shared_slots is None else shared_slots & task_slots
            if not shared_slots:
                return {
                    "status": "infeasible",
                    "message": "Some parallel-room sessions have no shared time options across required rooms.",
                    "solutions": [],
                    "truncated": False,
                    "tasks": tasks,
                    "timing": {
                        "precheck_ms": precheck_ms,
                        "model_build_ms": int((time.perf_counter() - model_build_started_at) * 1000),
                        "solve_ms": 0,
                        "fallback_search_ms": 0,
                        "total_ms": int((time.perf_counter() - started_at) * 1000),
                        "room_assignment_ms": room_assignment_ms,
                    },
                    "stats": {
                        "task_count": len(tasks),
                        "assignment_variable_count": 0,
                        "candidate_option_count": legacy_candidate_option_count,
                        "feasible_combo_count": 0,
                        "fallback_combo_evaluated_count": 0,
                        "fallback_combo_truncated": False,
                        "exact_enumeration_single_worker": False,
                        "machine_cpu_count": os.cpu_count() or 1,
                        "memory_limit_mb": DEFAULT_SOLVER_MEMORY_LIMIT_MB,
                        "projected_group_slot_blocker_count": 0,
                        "slot_variable_count": 0,
                        "room_assignment_retry_count": retry_index,
                        "room_assignment_failures": room_assignment_failures,
                        "room_assignment_ms": room_assignment_ms,
                        "solver_engine": "snapshot_decomposed_exact",
                        "domain_reduction_ratio": 0.0,
                    },
                }
            shared_slot_vars = []
            for day, start_minute in sorted(shared_slots, key=lambda item: (DAY_INDEX[item[0]], item[1])):
                bundle_var = model.NewBoolVar(
                    f"bundle_{bundle_key[0]}_{bundle_key[1]}_{day}_{start_minute}"
                )
                bundle_slot_vars[(bundle_key, day, start_minute)] = bundle_var
                shared_slot_vars.append(bundle_var)
            model.Add(sum(shared_slot_vars) == 1)

        for task_index, task in enumerate(tasks):
            if task.bundle_key is not None:
                for day, start_minute in slot_candidates_by_task[task_index]:
                    bundle_var = bundle_slot_vars.get((task.bundle_key, day, start_minute))
                    if bundle_var is not None:
                        slot_vars[(task_index, day, start_minute)] = bundle_var
                continue
            vars_for_task = []
            for day, start_minute in slot_candidates_by_task[task_index]:
                var = model.NewBoolVar(f"task_{task_index}_{day}_{start_minute}")
                slot_vars[(task_index, day, start_minute)] = var
                vars_for_task.append(var)
            model.Add(sum(vars_for_task) == 1)

        slot_variable_count = len(
            {
                key
                for key in slot_vars
                if tasks[key[0]].bundle_key is None
            }
        )
        domain_reduction_ratio = 1.0 - (
            slot_variable_count / max(1, legacy_candidate_option_count)
        )

        for day, task_assignments in retry_cuts:
            cut_vars = [
                slot_vars[(task_index, day, start_minute)]
                for task_index, start_minute in task_assignments
            ]
            model.Add(sum(cut_vars) <= len(cut_vars) - 1)

        for day in DAY_ORDER:
            for minute in range(START_MINUTE, END_MINUTE, 30):
                lecturer_blockers: dict[int, list[cp_model.IntVar]] = defaultdict(list)
                student_blockers: dict[int, list[cp_model.IntVar]] = defaultdict(list)
                student_membership_blockers: dict[str, list[cp_model.IntVar]] = defaultdict(list)
                singleton_room_blockers: dict[int, list[cp_model.IntVar]] = defaultdict(list)
                room_pool_blockers: dict[tuple[str, str | None], list[cp_model.IntVar]] = defaultdict(list)
                for task_index, task in enumerate(tasks):
                    for candidate_day, candidate_start in slot_candidates_by_task[task_index]:
                        if candidate_day != day or not _overlap(
                            candidate_start, task.duration_minutes, minute, 30
                        ):
                            continue
                        var = slot_vars[(task_index, candidate_day, candidate_start)]
                        for lecturer_id in task.lecturer_ids:
                            lecturer_blockers[lecturer_id].append(var)
                        for student_group_id in task.student_group_ids:
                            student_blockers[student_group_id].append(var)
                        for student_key in task.student_membership_keys:
                            student_membership_blockers[student_key].append(var)
                        eligible_rooms = eligible_rooms_by_task[task_index]
                        if len(eligible_rooms) == 1:
                            singleton_room_blockers[eligible_rooms[0]].append(var)
                        room_pool = room_pool_by_task[task_index]
                        if room_pool is not None:
                            room_pool_blockers[room_pool].append(var)
                for vars_for_lecturer in lecturer_blockers.values():
                    if vars_for_lecturer:
                        model.Add(sum(dict.fromkeys(vars_for_lecturer)) <= 1)
                for blockers_for_group in student_blockers.values():
                    unique_vars = list(dict.fromkeys(blockers_for_group))
                    if unique_vars:
                        model.Add(sum(unique_vars) <= 1)
                for blockers_for_student in student_membership_blockers.values():
                    unique_vars = list(dict.fromkeys(blockers_for_student))
                    if unique_vars:
                        model.Add(sum(unique_vars) <= 1)
                for blockers_for_room in singleton_room_blockers.values():
                    unique_vars = list(dict.fromkeys(blockers_for_room))
                    if unique_vars:
                        model.Add(sum(unique_vars) <= 1)
                for room_pool, blockers_for_pool in room_pool_blockers.items():
                    unique_vars = list(dict.fromkeys(blockers_for_pool))
                    if unique_vars:
                        model.Add(sum(unique_vars) <= room_capacity_by_pool[room_pool])

        decision_vars: list[cp_model.IntVar] = []
        for task_index, task in sorted(
            enumerate(tasks),
            key=lambda item: (
                len(eligible_rooms_by_task[item[0]]),
                len(slot_candidates_by_task[item[0]]),
                -item[1].duration_minutes,
                item[0],
            ),
        ):
            seen_vars: set[int] = set()
            for day, start_minute in slot_candidates_by_task[task_index]:
                var = slot_vars[(task_index, day, start_minute)]
                if id(var) in seen_vars:
                    continue
                seen_vars.add(id(var))
                decision_vars.append(var)
        if decision_vars:
            model.AddDecisionStrategy(
                decision_vars,
                cp_model.CHOOSE_FIRST,
                cp_model.SELECT_MAX_VALUE,
            )

        occurrence_day_vars: dict[tuple[int, int], dict[str, list[cp_model.IntVar]]] = defaultdict(
            lambda: defaultdict(list)
        )
        for task_index, task in enumerate(tasks):
            for day, start_minute in slot_candidates_by_task[task_index]:
                occurrence_day_vars[(task.root_session_id, task.occurrence_index)][day].append(
                    slot_vars[(task_index, day, start_minute)]
                )

        occurrence_day_flags: dict[tuple[int, int], dict[str, cp_model.IntVar]] = defaultdict(dict)
        grouped_by_root: dict[int, dict[int, dict[str, list[cp_model.IntVar]]]] = defaultdict(dict)
        for (root_session_id, occurrence_index), by_day in occurrence_day_vars.items():
            grouped_by_root[root_session_id][occurrence_index] = by_day
            for day, vars_for_day in by_day.items():
                unique_vars = list(dict.fromkeys(vars_for_day))
                day_flag = model.NewBoolVar(
                    f"occ_{root_session_id}_{occurrence_index}_{day}"
                )
                model.AddMaxEquality(day_flag, unique_vars)
                occurrence_day_flags[(root_session_id, occurrence_index)][day] = day_flag

        if "spread_sessions_across_days" in selected_soft_constraints:
            for root_session_id, occurrences in grouped_by_root.items():
                occurrence_count = max(occurrences.keys(), default=1)
                if occurrence_count <= 1:
                    continue
                for day in DAY_ORDER:
                    day_flags = [
                        occurrence_day_flags[(root_session_id, occurrence_index)].get(day)
                        for occurrence_index in occurrences
                        if occurrence_day_flags[(root_session_id, occurrence_index)].get(day) is not None
                    ]
                    if day_flags:
                        model.Add(sum(day_flags) <= 1)

        if (
            "balance_teaching_load_across_week" in selected_soft_constraints
            or "avoid_monday_overload" in selected_soft_constraints
        ):
            daily_load_vars: dict[str, cp_model.IntVar] = {}
            all_occurrences = sorted(occurrence_day_flags.keys())
            for day in DAY_ORDER:
                day_flags = [
                    occurrence_day_flags[occurrence].get(day)
                    for occurrence in all_occurrences
                    if occurrence_day_flags[occurrence].get(day) is not None
                ]
                if day_flags:
                    load_var = model.NewIntVar(0, len(all_occurrences), f"daily_load_{day}")
                    model.Add(load_var == sum(day_flags))
                else:
                    load_var = model.NewIntVar(0, 0, f"daily_load_{day}")
                daily_load_vars[day] = load_var

            if "balance_teaching_load_across_week" in selected_soft_constraints:
                max_load = model.NewIntVar(0, len(all_occurrences), "max_daily_load")
                min_load = model.NewIntVar(0, len(all_occurrences), "min_daily_load")
                model.AddMaxEquality(max_load, list(daily_load_vars.values()))
                model.AddMinEquality(min_load, list(daily_load_vars.values()))
                model.Add(max_load - min_load <= 2)

            if "avoid_monday_overload" in selected_soft_constraints:
                monday_load = daily_load_vars["Monday"]
                for day in DAY_ORDER[1:]:
                    model.Add(monday_load <= daily_load_vars[day] + 1)

        model_build_ms = int((time.perf_counter() - model_build_started_at) * 1000)
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = float(time_limit_seconds)
        solver.parameters.enumerate_all_solutions = False
        solver.parameters.num_search_workers = max(1, int(num_search_workers))
        solver.parameters.max_memory_in_mb = int(DEFAULT_SOLVER_MEMORY_LIMIT_MB)
        solver.parameters.search_branching = cp_model.FIXED_SEARCH

        solve_started_at = time.perf_counter()
        status = solver.Solve(model)
        solve_ms = int((time.perf_counter() - solve_started_at) * 1000)

        if status == cp_model.UNKNOWN:
            return _resource_limited_result(
                started_at,
                tasks,
                message=(
                    "Generation stopped without a solution before the bounded solve budget completed. "
                    "The snapshot generator reduced the search space, but this run still exhausted the current local time or memory budget."
                ),
                precheck_ms=precheck_ms,
                model_build_ms=model_build_ms,
                solve_ms=solve_ms,
                assignment_variable_count=slot_variable_count,
                candidate_option_count=legacy_candidate_option_count,
                group_slot_blocker_count=0,
                enumerate_all_solutions=False,
            ) | {
                "timing": {
                    "precheck_ms": precheck_ms,
                    "model_build_ms": model_build_ms,
                    "solve_ms": solve_ms,
                    "fallback_search_ms": 0,
                    "total_ms": int((time.perf_counter() - started_at) * 1000),
                    "room_assignment_ms": room_assignment_ms,
                },
                "stats": {
                    "task_count": len(tasks),
                    "assignment_variable_count": slot_variable_count,
                    "candidate_option_count": legacy_candidate_option_count,
                    "feasible_combo_count": 0,
                    "fallback_combo_evaluated_count": 0,
                    "fallback_combo_truncated": False,
                    "exact_enumeration_single_worker": False,
                    "machine_cpu_count": os.cpu_count() or 1,
                    "memory_limit_mb": DEFAULT_SOLVER_MEMORY_LIMIT_MB,
                    "projected_group_slot_blocker_count": 0,
                    "slot_variable_count": slot_variable_count,
                    "room_assignment_retry_count": retry_index,
                    "room_assignment_failures": room_assignment_failures,
                    "room_assignment_ms": room_assignment_ms,
                    "solver_engine": "snapshot_decomposed_exact",
                    "domain_reduction_ratio": domain_reduction_ratio,
                },
            }

        if status not in {cp_model.OPTIMAL, cp_model.FEASIBLE}:
            return {
                "status": "infeasible",
                "message": _format_diagnostic_message(
                    "No possible timetables satisfy the selected constraints.",
                    [
                        "Check whether high-frequency sessions are competing for the same lecturers, rooms, or cohorts.",
                        "Check whether split limits or specific-room requirements are too restrictive for the available rooms.",
                        "If you selected nice-to-have constraints, try generating once without them to confirm hard-constraint feasibility.",
                    ],
                ),
                "solutions": [],
                "truncated": False,
                "tasks": tasks,
                "timing": {
                    "precheck_ms": precheck_ms,
                    "model_build_ms": model_build_ms,
                    "solve_ms": solve_ms,
                    "fallback_search_ms": 0,
                    "total_ms": int((time.perf_counter() - started_at) * 1000),
                    "room_assignment_ms": room_assignment_ms,
                },
                "stats": {
                    "task_count": len(tasks),
                    "assignment_variable_count": slot_variable_count,
                    "candidate_option_count": legacy_candidate_option_count,
                    "feasible_combo_count": 0,
                    "fallback_combo_evaluated_count": 0,
                    "fallback_combo_truncated": False,
                    "exact_enumeration_single_worker": False,
                    "machine_cpu_count": os.cpu_count() or 1,
                    "memory_limit_mb": DEFAULT_SOLVER_MEMORY_LIMIT_MB,
                    "projected_group_slot_blocker_count": 0,
                    "slot_variable_count": slot_variable_count,
                    "room_assignment_retry_count": retry_index,
                    "room_assignment_failures": room_assignment_failures,
                    "room_assignment_ms": room_assignment_ms,
                    "solver_engine": "snapshot_decomposed_exact",
                    "domain_reduction_ratio": domain_reduction_ratio,
                },
            }

        assigned_by_day: dict[str, list[tuple[int, int]]] = defaultdict(list)
        for task_index in range(len(tasks)):
            for day, start_minute in slot_candidates_by_task[task_index]:
                if solver.Value(slot_vars[(task_index, day, start_minute)]):
                    assigned_by_day[day].append((task_index, start_minute))
                    break

        room_matching_started_at = time.perf_counter()
        final_solution: list[tuple[int, int, str, int]] = []
        failed_cut: tuple[str, tuple[tuple[int, int], ...]] | None = None
        for day, entries in sorted(
            assigned_by_day.items(),
            key=lambda item: DAY_INDEX[item[0]],
        ):
            matching = _build_day_room_matching(entries, tasks, eligible_rooms_by_task)
            if matching is None:
                failed_cut = (day, tuple(sorted(entries)))
                room_assignment_failures += 1
                last_room_assignment_diagnostic = _diagnose_day_room_infeasibility(
                    entries,
                    tasks,
                    eligible_rooms_by_task,
                    rooms,
                )
                break
            start_by_task = {task_index: start for task_index, start in entries}
            for task_index, room_id in matching.items():
                final_solution.append((task_index, room_id, day, start_by_task[task_index]))
        room_assignment_ms += int((time.perf_counter() - room_matching_started_at) * 1000)

        if failed_cut is None:
            return {
                "status": "optimal" if status == cp_model.OPTIMAL else "feasible",
                "message": "Generated timetable solutions.",
                "solutions": [sorted(final_solution)],
                "truncated": False,
                "tasks": tasks,
                "timing": {
                    "precheck_ms": precheck_ms,
                    "model_build_ms": model_build_ms,
                    "solve_ms": solve_ms,
                    "fallback_search_ms": 0,
                    "total_ms": int((time.perf_counter() - started_at) * 1000),
                    "room_assignment_ms": room_assignment_ms,
                },
                "stats": {
                    "task_count": len(tasks),
                    "assignment_variable_count": slot_variable_count,
                    "candidate_option_count": legacy_candidate_option_count,
                    "feasible_combo_count": 0,
                    "fallback_combo_evaluated_count": 0,
                    "fallback_combo_truncated": False,
                    "exact_enumeration_single_worker": False,
                    "machine_cpu_count": os.cpu_count() or 1,
                    "memory_limit_mb": DEFAULT_SOLVER_MEMORY_LIMIT_MB,
                    "projected_group_slot_blocker_count": 0,
                    "slot_variable_count": slot_variable_count,
                    "room_assignment_retry_count": retry_index,
                    "room_assignment_failures": room_assignment_failures,
                    "room_assignment_ms": room_assignment_ms,
                    "solver_engine": "snapshot_decomposed_exact",
                    "domain_reduction_ratio": domain_reduction_ratio,
                },
            }

        retry_cuts.append(failed_cut)

    return _resource_limited_result(
        started_at,
        tasks,
        message=(
            "Generation was stopped because exact room assignment could not be completed within the local retry budget. "
            "The time assignment stage found candidate schedules, but concrete room matching kept failing. "
            f"{last_room_assignment_diagnostic}".strip()
        ),
        precheck_ms=precheck_ms,
        solve_ms=0,
        model_build_ms=0,
        assignment_variable_count=0,
        candidate_option_count=legacy_candidate_option_count,
        group_slot_blocker_count=0,
        enumerate_all_solutions=False,
    ) | {
        "timing": {
            "precheck_ms": precheck_ms,
            "model_build_ms": 0,
            "solve_ms": 0,
            "fallback_search_ms": 0,
            "total_ms": int((time.perf_counter() - started_at) * 1000),
            "room_assignment_ms": room_assignment_ms,
        },
        "stats": {
            "task_count": len(tasks),
            "assignment_variable_count": 0,
            "candidate_option_count": legacy_candidate_option_count,
            "feasible_combo_count": 0,
            "fallback_combo_evaluated_count": 0,
            "fallback_combo_truncated": False,
            "exact_enumeration_single_worker": False,
            "machine_cpu_count": os.cpu_count() or 1,
            "memory_limit_mb": DEFAULT_SOLVER_MEMORY_LIMIT_MB,
            "projected_group_slot_blocker_count": 0,
            "slot_variable_count": 0,
            "room_assignment_retry_count": max_retry_cuts,
            "room_assignment_failures": room_assignment_failures,
            "room_assignment_ms": room_assignment_ms,
            "solver_engine": "snapshot_decomposed_exact",
            "domain_reduction_ratio": 0.0,
        },
    }


def generate_timetables(
    db: Session,
    selected_soft_constraints: Iterable[str],
    max_solutions: int,
    preview_limit: int,
    time_limit_seconds: int,
    performance_preset: str = "balanced",
) -> V2GenerationRun:
    selected_soft_constraints = list(selected_soft_constraints)
    solve_profile = _resolve_solve_profile(performance_preset)
    session_count = db.query(V2Session).count()
    use_feasible_first_search = session_count > LARGE_DATASET_SESSION_THRESHOLD
    result = _solve_internal(
        db,
        selected_soft_constraints,
        max_solutions,
        time_limit_seconds,
        enumerate_all_solutions=not use_feasible_first_search,
        num_search_workers=(
            solve_profile.probe_num_workers if use_feasible_first_search else 1
        ),
    )

    run = V2GenerationRun(
        status=result["status"],
        selected_soft_constraints=",".join(selected_soft_constraints),
        total_solutions_found=len(result["solutions"]),
        truncated=result["truncated"],
        max_solutions=max_solutions,
        time_limit_seconds=time_limit_seconds,
        message=result["message"],
    )
    db.add(run)
    db.flush()

    room_lookup = {int(room.id): room for room in db.query(V2Room).all()}
    tasks: list[SessionTask] = result["tasks"]
    solution_entry_rows: list[dict] = []
    for ordinal, solution in enumerate(result["solutions"][:preview_limit], start=1):
        solution_row = V2TimetableSolution(
            generation_run_id=int(run.id),
            ordinal=ordinal,
            is_default=ordinal == 1 and len(result["solutions"]) == 1,
            is_representative=ordinal == 1
            and (result["truncated"] or len(result["solutions"]) > 100),
        )
        db.add(solution_row)
        db.flush()
        for task_index, room_id, day, start_minute in solution:
            task = tasks[task_index]
            entry = _entry_from_assignment(
                task, room_lookup[room_id], day, start_minute
            )
            solution_entry_rows.append(
                {
                    "solution_id": int(solution_row.id),
                    "session_id": entry["session_id"],
                    "occurrence_index": entry["occurrence_index"],
                    "split_index": entry["split_index"],
                    "room_id": entry["room_id"],
                    "day": entry["day"],
                    "start_minute": entry["start_minute"],
                    "duration_minutes": entry["duration_minutes"],
                }
            )

    fallback_started_at = time.perf_counter()
    possible_combinations: list[dict] = []
    fallback_combo_evaluated_count = 0
    fallback_combo_truncated = False
    if result["status"] == "infeasible" and selected_soft_constraints:
        for combo in _selected_soft_constraint_subsets(selected_soft_constraints):
            if len(possible_combinations) >= solve_profile.fallback_combo_limit:
                fallback_combo_truncated = True
                break
            combo_result = _solve_internal(
                db,
                combo,
                solve_profile.fallback_combo_count_cap,
                min(time_limit_seconds, solve_profile.fallback_time_limit_seconds),
                enumerate_all_solutions=not use_feasible_first_search,
                num_search_workers=(
                    solve_profile.probe_num_workers if use_feasible_first_search else 1
                ),
            )
            fallback_combo_evaluated_count += 1
            if combo_result["solutions"]:
                solution_count = int(len(combo_result["solutions"]))
                count_capped = bool(
                    combo_result["truncated"]
                    or solution_count >= solve_profile.fallback_combo_count_cap
                )
                possible_combinations.append(
                    {
                        "constraints": combo,
                        "solution_count": min(solution_count, 100),
                        "solution_count_capped": count_capped,
                    }
                )
        if possible_combinations:
            possible_combinations = sorted(
                possible_combinations,
                key=lambda item: (
                    -len(item["constraints"]),
                    item["constraints"],
                ),
            )
            run.message = (
                "Selected nice-to-have constraints cannot be satisfied together."
            )
            run.possible_soft_constraint_combinations = json.dumps(
                possible_combinations
            )
            if fallback_combo_truncated:
                run.message += " Showing the first feasible alternatives found within the fallback search budget."

    db.commit()

    if solution_entry_rows:
        with engine.begin() as connection:
            for row in solution_entry_rows:
                connection.execute(insert(V2SolutionEntry).values(**row))

    db.refresh(run)
    result["timing"]["fallback_search_ms"] = int(
        (time.perf_counter() - fallback_started_at) * 1000
    )
    result["timing"]["total_ms"] = (
        result["timing"]["precheck_ms"]
        + result["timing"]["model_build_ms"]
        + result["timing"]["solve_ms"]
        + result["timing"]["fallback_search_ms"]
    )
    result["stats"]["feasible_combo_count"] = len(possible_combinations)
    result["stats"]["fallback_combo_evaluated_count"] = fallback_combo_evaluated_count
    result["stats"]["fallback_combo_truncated"] = fallback_combo_truncated
    run._performance_preset = solve_profile.performance_preset
    run._timing = result["timing"]
    run._stats = result["stats"]
    return run


def generate_snapshot_timetables(
    db: Session,
    import_run_id: int,
    selected_soft_constraints: Iterable[str],
    max_solutions: int,
    preview_limit: int,
    time_limit_seconds: int,
    performance_preset: str = "balanced",
) -> SnapshotGenerationRun:
    selected_soft_constraints = list(selected_soft_constraints)
    solve_profile = _resolve_solve_profile(performance_preset)
    tasks, _sessions, rooms, lecturer_names, group_names = _build_snapshot_tasks(
        db, import_run_id
    )
    result = _solve_snapshot_internal(
        tasks=tasks,
        rooms=rooms,
        lecturer_names=lecturer_names,
        group_names=group_names,
        selected_soft_constraints=selected_soft_constraints,
        max_solutions=max_solutions,
        time_limit_seconds=time_limit_seconds,
        num_search_workers=solve_profile.probe_num_workers,
    )

    run = SnapshotGenerationRun(
        import_run_id=import_run_id,
        status=result["status"],
        selected_soft_constraints=",".join(selected_soft_constraints),
        total_solutions_found=len(result["solutions"]),
        truncated=result["truncated"],
        max_solutions=max_solutions,
        time_limit_seconds=time_limit_seconds,
        message=result["message"],
    )
    db.add(run)
    db.flush()

    room_lookup = {int(room.id): room for room in rooms}
    tasks_list: list[SessionTask] = result["tasks"]
    solution_entry_rows: list[dict] = []
    for ordinal, solution in enumerate(result["solutions"][:preview_limit], start=1):
        solution_row = SnapshotTimetableSolution(
            generation_run_id=int(run.id),
            ordinal=ordinal,
            is_default=ordinal == 1 and len(result["solutions"]) == 1,
            is_representative=ordinal == 1
            and (result["truncated"] or len(result["solutions"]) > 100),
        )
        db.add(solution_row)
        db.flush()
        for task_index, room_id, day, start_minute in solution:
            task = tasks_list[task_index]
            entry = _entry_from_assignment(
                task, room_lookup[room_id], day, start_minute
            )
            solution_entry_rows.append(
                {
                    "solution_id": int(solution_row.id),
                    "shared_session_id": entry["session_id"],
                    "occurrence_index": entry["occurrence_index"],
                    "split_index": entry["split_index"],
                    "room_id": entry["room_id"],
                    "day": entry["day"],
                    "start_minute": entry["start_minute"],
                    "duration_minutes": entry["duration_minutes"],
                }
            )

    db.commit()

    if solution_entry_rows:
        with engine.begin() as connection:
            for row in solution_entry_rows:
                connection.execute(insert(SnapshotSolutionEntry).values(**row))

    db.refresh(run)
    run._performance_preset = solve_profile.performance_preset
    run._timing = result["timing"]
    run._stats = result["stats"]
    return run


def set_default_solution(db: Session, solution_id: int) -> V2TimetableSolution:
    solution = (
        db.query(V2TimetableSolution)
        .filter(V2TimetableSolution.id == solution_id)
        .first()
    )
    if not solution:
        raise ValueError("Solution not found")
    run_id = int(solution.generation_run_id)
    db.query(V2TimetableSolution).filter(
        V2TimetableSolution.generation_run_id == run_id
    ).update({V2TimetableSolution.is_default: False}, synchronize_session=False)
    solution.is_default = True
    db.commit()
    db.refresh(solution)
    return solution


def _solution_entry_payload(solution: V2TimetableSolution) -> list[dict]:
    payload = []
    for entry in sorted(
        solution.entries,
        key=lambda item: (
            DAY_INDEX.get(item.day, 99),
            item.start_minute,
            item.room.name,
        ),
    ):
        session = entry.session
        module = session.module
        split_map = {
            item.split_index: item for item in _build_split_assignments(session)
        }
        split_assignment = split_map.get(
            int(entry.split_index),
            SplitAssignment(
                split_index=int(entry.split_index),
                student_group_ids=tuple(),
                student_count=0,
                fragments=tuple(),
            ),
        )
        degree_path_labels = []
        total_students = int(split_assignment.student_count)
        group_names = []
        fragment_count_by_group = defaultdict(int)
        fragment_labels_by_group: dict[int, list[str]] = defaultdict(list)
        for group_id, fragment_size, fragment_label in split_assignment.fragments:
            fragment_count_by_group[group_id] += 1
            fragment_labels_by_group[group_id].append(fragment_label)
        allowed_group_ids = set(split_assignment.student_group_ids)
        for group in session.student_groups:
            if split_assignment.student_group_ids and int(group.id) not in allowed_group_ids:
                continue
            degree_name = group.degree.code
            path_name = group.path.code if group.path else "General"
            degree_path_labels.append(f"{degree_name} Y{group.year} {path_name}")
            group_id = int(group.id)
            if fragment_count_by_group.get(group_id, 0) <= 1:
                label = (
                    fragment_labels_by_group[group_id][0]
                    if fragment_labels_by_group.get(group_id)
                    else group.name
                )
                group_names.append(label)
            else:
                group_names.extend(fragment_labels_by_group[group_id])
        payload.append(
            {
                "session_id": int(entry.session_id),
                "session_name": session.name,
                "module_code": _format_session_module_code(session),
                "module_name": _format_session_module_name(session),
                "room_name": entry.room.name,
                "room_location": entry.room.location,
                "day": entry.day,
                "start_minute": int(entry.start_minute),
                "duration_minutes": int(entry.duration_minutes),
                "occurrence_index": int(entry.occurrence_index),
                "split_index": int(entry.split_index),
                "lecturer_names": [lecturer.name for lecturer in session.lecturers],
                "student_group_names": group_names,
                "degree_path_labels": sorted(set(degree_path_labels)),
                "total_students": total_students,
            }
        )
    return payload


def serialize_solution(solution: V2TimetableSolution) -> dict:
    return {
        "solution_id": int(solution.id),
        "ordinal": int(solution.ordinal),
        "is_default": bool(solution.is_default),
        "is_representative": bool(solution.is_representative),
        "entries": _solution_entry_payload(solution),
    }


def serialize_generation_run(run: V2GenerationRun) -> dict:
    raw_combos = json.loads(run.possible_soft_constraint_combinations or "[]")
    combos = []
    for item in raw_combos:
        if isinstance(item, list):
            combos.append(
                {
                    "constraints": item,
                    "solution_count": 0,
                    "solution_count_capped": False,
                }
            )
        else:
            combos.append(item)
    selected = [item for item in run.selected_soft_constraints.split(",") if item]
    timing = getattr(
        run,
        "_timing",
        {
            "precheck_ms": 0,
            "model_build_ms": 0,
            "solve_ms": 0,
            "fallback_search_ms": 0,
            "room_assignment_ms": 0,
            "total_ms": 0,
        },
    )
    stats = getattr(
        run,
        "_stats",
        {
            "task_count": 0,
            "assignment_variable_count": 0,
            "candidate_option_count": 0,
            "feasible_combo_count": len(combos),
            "fallback_combo_evaluated_count": 0,
            "fallback_combo_truncated": False,
            "exact_enumeration_single_worker": True,
            "machine_cpu_count": os.cpu_count() or 1,
            "memory_limit_mb": 0,
            "projected_group_slot_blocker_count": 0,
            "slot_variable_count": 0,
            "room_assignment_retry_count": 0,
            "room_assignment_failures": 0,
            "room_assignment_ms": 0,
            "solver_engine": "legacy_guarded",
            "domain_reduction_ratio": 0.0,
        },
    )
    return {
        "generation_run_id": int(run.id),
        "status": run.status,
        "message": run.message or "",
        "counts": {
            "total_solutions_found": int(run.total_solutions_found),
            "preview_solution_count": len(run.solutions),
            "truncated": bool(run.truncated),
        },
        "performance_preset": getattr(run, "_performance_preset", "balanced"),
        "timing": timing,
        "stats": stats,
        "selected_soft_constraints": selected,
        "available_soft_constraints": list_soft_constraint_options(),
        "possible_soft_constraint_combinations": combos,
        "solutions": [
            serialize_solution(solution)
            for solution in sorted(run.solutions, key=lambda item: item.ordinal)
        ],
    }


def _snapshot_solution_entry_payload(solution: SnapshotTimetableSolution) -> list[dict]:
    payload = []
    for entry in sorted(
        solution.entries,
        key=lambda item: (
            DAY_INDEX.get(item.day, 99),
            item.start_minute,
            item.room.name,
        ),
    ):
        session = entry.shared_session
        split_map = {
            item.split_index: item for item in _build_snapshot_split_assignments(session)
        }
        split_assignment = split_map.get(
            int(entry.split_index),
            SplitAssignment(
                split_index=int(entry.split_index),
                student_group_ids=tuple(),
                student_count=0,
                fragments=tuple(),
            ),
        )
        group_labels = []
        degree_path_labels = []
        fragment_count_by_group = defaultdict(int)
        fragment_labels_by_group: dict[int, list[str]] = defaultdict(list)
        for group_id, _fragment_size, fragment_label in split_assignment.fragments:
            fragment_count_by_group[group_id] += 1
            fragment_labels_by_group[group_id].append(fragment_label)
        allowed_group_ids = set(split_assignment.student_group_ids)
        for group in session.attendance_groups:
            if split_assignment.student_group_ids and int(group.id) not in allowed_group_ids:
                continue
            degree_path_labels.append(group.label)
            group_id = int(group.id)
            if fragment_count_by_group.get(group_id, 0) <= 1:
                label = (
                    fragment_labels_by_group[group_id][0]
                    if fragment_labels_by_group.get(group_id)
                    else group.label
                )
                group_labels.append(label)
            else:
                group_labels.extend(fragment_labels_by_group[group_id])

        modules = sorted(session.curriculum_modules, key=lambda item: int(item.id))
        payload.append(
            {
                "session_id": int(entry.shared_session_id),
                "session_name": session.name,
                "module_code": " / ".join(module.code for module in modules) or session.name,
                "module_name": " / ".join(module.name for module in modules) or session.name,
                "room_name": entry.room.name,
                "room_location": entry.room.location,
                "day": entry.day,
                "start_minute": int(entry.start_minute),
                "duration_minutes": int(entry.duration_minutes),
                "occurrence_index": int(entry.occurrence_index),
                "split_index": int(entry.split_index),
                "lecturer_names": [lecturer.name for lecturer in session.lecturers],
                "student_group_names": group_labels,
                "degree_path_labels": sorted(set(degree_path_labels)),
                "total_students": int(split_assignment.student_count),
            }
        )
    return payload


def serialize_snapshot_solution(solution: SnapshotTimetableSolution) -> dict:
    return {
        "solution_id": int(solution.id),
        "ordinal": int(solution.ordinal),
        "is_default": bool(solution.is_default),
        "is_representative": bool(solution.is_representative),
        "entries": _snapshot_solution_entry_payload(solution),
    }


def serialize_snapshot_generation_run(run: SnapshotGenerationRun) -> dict:
    raw_combos = json.loads(run.possible_soft_constraint_combinations or "[]")
    combos = []
    for item in raw_combos:
        if isinstance(item, list):
            combos.append(
                {
                    "constraints": item,
                    "solution_count": 0,
                    "solution_count_capped": False,
                }
            )
        else:
            combos.append(item)
    selected = [item for item in run.selected_soft_constraints.split(",") if item]
    timing = getattr(
        run,
        "_timing",
        {
            "precheck_ms": 0,
            "model_build_ms": 0,
            "solve_ms": 0,
            "fallback_search_ms": 0,
            "room_assignment_ms": 0,
            "total_ms": 0,
        },
    )
    stats = getattr(
        run,
        "_stats",
        {
            "task_count": 0,
            "assignment_variable_count": 0,
            "candidate_option_count": 0,
            "feasible_combo_count": 0,
            "fallback_combo_evaluated_count": 0,
            "fallback_combo_truncated": False,
            "exact_enumeration_single_worker": False,
            "machine_cpu_count": os.cpu_count() or 1,
            "memory_limit_mb": DEFAULT_SOLVER_MEMORY_LIMIT_MB,
            "projected_group_slot_blocker_count": 0,
            "slot_variable_count": 0,
            "room_assignment_retry_count": 0,
            "room_assignment_failures": 0,
            "room_assignment_ms": 0,
            "solver_engine": "snapshot_decomposed_exact",
            "domain_reduction_ratio": 0.0,
        },
    )
    return {
        "generation_run_id": int(run.id),
        "status": run.status,
        "message": run.message or "Generated timetable solutions.",
        "counts": {
            "total_solutions_found": int(run.total_solutions_found),
            "preview_solution_count": len(run.solutions),
            "truncated": bool(run.truncated),
        },
        "performance_preset": getattr(run, "_performance_preset", "balanced"),
        "timing": timing,
        "stats": stats,
        "selected_soft_constraints": selected,
        "available_soft_constraints": list_soft_constraint_options(),
        "possible_soft_constraint_combinations": combos,
        "solutions": [serialize_snapshot_solution(solution) for solution in run.solutions],
    }


def get_latest_run(db: Session) -> V2GenerationRun | None:
    return (
        db.query(V2GenerationRun)
        .options(
            joinedload(V2GenerationRun.solutions)
            .joinedload(V2TimetableSolution.entries)
            .joinedload(V2SolutionEntry.room),
            joinedload(V2GenerationRun.solutions)
            .joinedload(V2TimetableSolution.entries)
            .joinedload(V2SolutionEntry.session)
            .joinedload(V2Session.module),
            joinedload(V2GenerationRun.solutions)
            .joinedload(V2TimetableSolution.entries)
            .joinedload(V2SolutionEntry.session)
            .joinedload(V2Session.linked_modules),
            joinedload(V2GenerationRun.solutions)
            .joinedload(V2TimetableSolution.entries)
            .joinedload(V2SolutionEntry.session)
            .joinedload(V2Session.lecturers),
            joinedload(V2GenerationRun.solutions)
            .joinedload(V2TimetableSolution.entries)
            .joinedload(V2SolutionEntry.session)
            .joinedload(V2Session.student_groups)
            .joinedload(V2StudentGroup.degree),
            joinedload(V2GenerationRun.solutions)
            .joinedload(V2TimetableSolution.entries)
            .joinedload(V2SolutionEntry.session)
            .joinedload(V2Session.student_groups)
            .joinedload(V2StudentGroup.path),
        )
        .order_by(V2GenerationRun.id.desc())
        .first()
    )


def get_latest_snapshot_run(
    db: Session, import_run_id: int
) -> SnapshotGenerationRun | None:
    return (
        db.query(SnapshotGenerationRun)
        .options(
            joinedload(SnapshotGenerationRun.solutions)
            .joinedload(SnapshotTimetableSolution.entries)
            .joinedload(SnapshotSolutionEntry.room),
            joinedload(SnapshotGenerationRun.solutions)
            .joinedload(SnapshotTimetableSolution.entries)
            .joinedload(SnapshotSolutionEntry.shared_session)
            .joinedload(SnapshotSharedSession.curriculum_modules),
            joinedload(SnapshotGenerationRun.solutions)
            .joinedload(SnapshotTimetableSolution.entries)
            .joinedload(SnapshotSolutionEntry.shared_session)
            .joinedload(SnapshotSharedSession.lecturers),
            joinedload(SnapshotGenerationRun.solutions)
            .joinedload(SnapshotTimetableSolution.entries)
            .joinedload(SnapshotSolutionEntry.shared_session)
            .joinedload(SnapshotSharedSession.attendance_groups)
            .joinedload(AttendanceGroup.programme),
            joinedload(SnapshotGenerationRun.solutions)
            .joinedload(SnapshotTimetableSolution.entries)
            .joinedload(SnapshotSolutionEntry.shared_session)
            .joinedload(SnapshotSharedSession.attendance_groups)
            .joinedload(AttendanceGroup.programme_path),
        )
        .filter(SnapshotGenerationRun.import_run_id == import_run_id)
        .order_by(SnapshotGenerationRun.id.desc())
        .first()
    )


def get_solution(db: Session, solution_id: int) -> V2TimetableSolution | None:
    return (
        db.query(V2TimetableSolution)
        .options(
            joinedload(V2TimetableSolution.entries).joinedload(V2SolutionEntry.room),
            joinedload(V2TimetableSolution.entries)
            .joinedload(V2SolutionEntry.session)
            .joinedload(V2Session.module),
            joinedload(V2TimetableSolution.entries)
            .joinedload(V2SolutionEntry.session)
            .joinedload(V2Session.linked_modules),
            joinedload(V2TimetableSolution.entries)
            .joinedload(V2SolutionEntry.session)
            .joinedload(V2Session.lecturers),
            joinedload(V2TimetableSolution.entries)
            .joinedload(V2SolutionEntry.session)
            .joinedload(V2Session.student_groups)
            .joinedload(V2StudentGroup.degree),
            joinedload(V2TimetableSolution.entries)
            .joinedload(V2SolutionEntry.session)
            .joinedload(V2Session.student_groups)
            .joinedload(V2StudentGroup.path),
        )
        .filter(V2TimetableSolution.id == solution_id)
        .first()
    )


def set_default_snapshot_solution(
    db: Session, import_run_id: int, solution_id: int
) -> SnapshotTimetableSolution:
    solution = (
        db.query(SnapshotTimetableSolution)
        .join(SnapshotGenerationRun)
        .filter(
            SnapshotTimetableSolution.id == solution_id,
            SnapshotGenerationRun.import_run_id == import_run_id,
        )
        .first()
    )
    if not solution:
        raise ValueError("Solution not found")
    run_id = int(solution.generation_run_id)
    db.query(SnapshotTimetableSolution).filter(
        SnapshotTimetableSolution.generation_run_id == run_id
    ).update({SnapshotTimetableSolution.is_default: False}, synchronize_session=False)
    solution.is_default = True
    db.commit()
    db.refresh(solution)
    return solution


def _snapshot_lookup_options(db: Session, import_run_id: int) -> dict:
    lecturers = (
        db.query(SnapshotLecturer)
        .filter(SnapshotLecturer.import_run_id == import_run_id)
        .order_by(SnapshotLecturer.name)
        .all()
    )
    attendance_groups = (
        db.query(AttendanceGroup)
        .options(
            joinedload(AttendanceGroup.programme),
            joinedload(AttendanceGroup.programme_path),
        )
        .filter(AttendanceGroup.import_run_id == import_run_id)
        .order_by(
            AttendanceGroup.programme_id,
            AttendanceGroup.study_year,
            AttendanceGroup.programme_path_id,
            AttendanceGroup.id,
        )
        .all()
    )
    degrees_by_id: dict[int, dict] = {}
    student_paths: list[dict] = []
    seen_paths: set[tuple[int, int, int | None]] = set()
    for group in attendance_groups:
        if not group.programme_id or not group.programme:
            continue
        degrees_by_id[int(group.programme_id)] = {
            "id": int(group.programme.id),
            "label": f"{group.programme.code} - {group.programme.name}",
        }
        if group.study_year is None:
            continue
        key = (int(group.programme_id), int(group.study_year), int(group.programme_path_id) if group.programme_path_id else None)
        if key in seen_paths:
            continue
        seen_paths.add(key)
        student_paths.append(
            {
                "id": int(group.programme_path_id) if group.programme_path_id else None,
                "degree_id": int(group.programme_id),
                "year": int(group.study_year),
                "label": f"Year {int(group.study_year)} - {group.programme_path.code if group.programme_path else 'General'}",
            }
        )
    student_paths.sort(key=lambda item: (item["degree_id"], item["year"], item["label"]))
    return {
        "lecturers": [{"id": int(item.id), "label": item.name} for item in lecturers],
        "degrees": sorted(degrees_by_id.values(), key=lambda item: item["label"]),
        "student_paths": student_paths,
    }


def _build_snapshot_view_payload(
    db: Session,
    *,
    import_run_id: int,
    mode: str,
    lecturer_id: int | None = None,
    degree_id: int | None = None,
    path_id: int | None = None,
    study_year: int | None = None,
) -> dict:
    run = get_latest_snapshot_run(db, import_run_id)
    if not run or not run.solutions:
        raise ValueError("No generated timetable available")

    solution = next((item for item in run.solutions if item.is_default), run.solutions[0])
    serialized = serialize_snapshot_solution(solution)
    real_entries = sorted(
        solution.entries,
        key=lambda item: (
            DAY_INDEX.get(item.day, 99),
            item.start_minute,
            item.room.name,
        ),
    )
    entry_pairs = list(zip(real_entries, serialized["entries"], strict=True))

    if mode == "lecturer":
        lecturer = (
            db.query(SnapshotLecturer)
            .filter(
                SnapshotLecturer.import_run_id == import_run_id,
                SnapshotLecturer.id == lecturer_id,
            )
            .first()
        )
        if not lecturer:
            raise ValueError("Lecturer not found")
        entries = [
            payload
            for real_entry, payload in entry_pairs
            if any(int(item.id) == int(lecturer.id) for item in real_entry.shared_session.lecturers)
        ]
        title = f"Lecturer Timetable - {lecturer.name}"
        subtitle = "Sessions taught by the selected lecturer."
    elif mode == "student":
        if not degree_id:
            raise ValueError("Degree not found")
        programme = db.query(Programme).filter(Programme.id == degree_id).first()
        if not programme:
            raise ValueError("Degree not found")
        if not study_year:
            raise ValueError("Study year not found")
        target_groups = (
            db.query(AttendanceGroup)
            .filter(
                AttendanceGroup.import_run_id == import_run_id,
                AttendanceGroup.programme_id == degree_id,
                AttendanceGroup.study_year == study_year,
                AttendanceGroup.programme_path_id == path_id if path_id else AttendanceGroup.programme_path_id.is_(None),
            )
            .all()
        )
        if not target_groups:
            raise ValueError("Student path has no matching groups")
        target_group_ids = {int(group.id) for group in target_groups}
        target_label = (
            f"{programme.code} - {next((group.programme_path.code for group in target_groups if group.programme_path), 'General')}"
            if path_id
            else f"{programme.code} - Year {study_year} General"
        )
        entries = [
            payload
            for real_entry, payload in entry_pairs
            if any(
                int(group.id) in target_group_ids
                for group in real_entry.shared_session.attendance_groups
            )
        ]
        subtitle = "Sessions attended by the selected degree and path."
        title = f"Student Timetable - {target_label}"
    else:
        entries = [payload for _real_entry, payload in entry_pairs]
        title = "Faculty Timetable"
        subtitle = "Default faculty timetable with all session details."

    serialized["entries"] = entries
    return {
        "mode": mode,
        "title": title,
        "subtitle": subtitle,
        "solution": serialized,
    }


def build_snapshot_verification_payload(db: Session, import_run_id: int) -> dict:
    run = get_latest_snapshot_run(db, import_run_id)
    if not run or not run.solutions:
        raise ValueError("No generated timetable available")

    solution = next((item for item in run.solutions if item.is_default), run.solutions[0])
    attendance_groups = (
        db.query(AttendanceGroup)
        .options(
            joinedload(AttendanceGroup.programme),
            joinedload(AttendanceGroup.programme_path),
            joinedload(AttendanceGroup.students).joinedload(AttendanceGroupStudent.student),
        )
        .filter(AttendanceGroup.import_run_id == import_run_id)
        .order_by(AttendanceGroup.id)
        .all()
    )
    rooms = (
        db.query(SnapshotRoom)
        .filter(SnapshotRoom.import_run_id == import_run_id)
        .order_by(SnapshotRoom.id)
        .all()
    )
    lecturers = (
        db.query(SnapshotLecturer)
        .filter(SnapshotLecturer.import_run_id == import_run_id)
        .order_by(SnapshotLecturer.id)
        .all()
    )

    entries = []
    for entry in sorted(
        solution.entries,
        key=lambda item: (
            DAY_INDEX.get(item.day, 99),
            item.start_minute,
            int(item.shared_session_id),
        ),
    ):
        session = entry.shared_session
        entries.append(
            {
                "shared_session_id": int(entry.shared_session_id),
                "solution_entry_id": int(entry.id),
                "day": entry.day,
                "start_minute": int(entry.start_minute),
                "duration_minutes": int(entry.duration_minutes),
                "occurrence_index": int(entry.occurrence_index),
                "split_index": int(entry.split_index),
                "room": {
                    "id": int(entry.room.id),
                    "name": entry.room.name,
                    "capacity": int(entry.room.capacity),
                    "room_type": entry.room.room_type,
                    "lab_type": entry.room.lab_type,
                    "location": entry.room.location,
                    "year_restriction": entry.room.year_restriction,
                },
                "lecturer_ids": [int(item.id) for item in session.lecturers],
                "curriculum_module_ids": [int(item.id) for item in session.curriculum_modules],
                "attendance_group_ids": [int(item.id) for item in session.attendance_groups],
            }
        )

    return {
        "version": 1,
        "import_run_id": int(import_run_id),
        "generation_run_id": int(run.id),
        "solution_id": int(solution.id),
        "selected_soft_constraints": [
            item for item in run.selected_soft_constraints.split(",") if item
        ],
        "hard_constraints": [
            "room_capacity_compatibility",
            "room_capability_compatibility",
            "room_year_restriction",
            "specific_room_restrictions",
            "no_room_overlap",
            "no_lecturer_overlap",
            "no_student_overlap",
            "working_hours_only",
            "lunch_break_protection",
        ],
        "rooms": [
            {
                "id": int(room.id),
                "name": room.name,
                "capacity": int(room.capacity),
                "room_type": room.room_type,
                "lab_type": room.lab_type,
                "location": room.location,
                "year_restriction": room.year_restriction,
            }
            for room in rooms
        ],
        "lecturers": [
            {
                "id": int(lecturer.id),
                "name": lecturer.name,
                "email": lecturer.email,
            }
            for lecturer in lecturers
        ],
        "attendance_groups": [
            {
                "id": int(group.id),
                "label": group.label,
                "academic_year": group.academic_year,
                "study_year": group.study_year,
                "programme_id": int(group.programme_id) if group.programme_id else None,
                "programme_code": group.programme.code if group.programme else None,
                "programme_path_id": int(group.programme_path_id) if group.programme_path_id else None,
                "programme_path_code": group.programme_path.code if group.programme_path else None,
                "student_count": int(group.student_count),
                "student_hashes": [
                    item.student.student_hash
                    for item in group.students
                    if item.student is not None
                ],
            }
            for group in attendance_groups
        ],
        "shared_sessions": [
            {
                "id": int(session.id),
                "name": session.name,
                "session_type": session.session_type,
                "duration_minutes": int(session.duration_minutes),
                "occurrences_per_week": int(session.occurrences_per_week),
                "required_room_type": session.required_room_type,
                "required_lab_type": session.required_lab_type,
                "specific_room_id": int(session.specific_room_id) if session.specific_room_id else None,
                "max_students_per_group": int(session.max_students_per_group) if session.max_students_per_group else None,
                "allow_parallel_rooms": bool(session.allow_parallel_rooms),
                "lecturer_ids": [int(item.id) for item in session.lecturers],
                "curriculum_module_ids": [int(item.id) for item in session.curriculum_modules],
                "attendance_group_ids": [int(item.id) for item in session.attendance_groups],
            }
            for session in sorted(
                {entry.shared_session for entry in solution.entries},
                key=lambda item: int(item.id),
            )
        ],
        "timetable_entries": entries,
    }


def build_view_payload(
    db: Session,
    mode: str,
    import_run_id: int | None = None,
    lecturer_id: int | None = None,
    student_group_id: int | None = None,
    degree_id: int | None = None,
    path_id: int | None = None,
    study_year: int | None = None,
) -> dict:
    if import_run_id:
        return _build_snapshot_view_payload(
            db,
            import_run_id=import_run_id,
            mode=mode,
            lecturer_id=lecturer_id,
            degree_id=degree_id,
            path_id=path_id,
            study_year=study_year,
        )

    run = get_latest_run(db)
    if not run or not run.solutions:
        raise ValueError("No generated timetable available")

    solution = next(
        (item for item in run.solutions if item.is_default), run.solutions[0]
    )
    serialized = serialize_solution(solution)
    entries = serialized["entries"]

    if mode == "lecturer":
        lecturer = db.query(V2Lecturer).filter(V2Lecturer.id == lecturer_id).first()
        if not lecturer:
            raise ValueError("Lecturer not found")
        entries = [
            entry for entry in entries if lecturer.name in entry["lecturer_names"]
        ]
        title = f"Lecturer Timetable - {lecturer.name}"
        subtitle = "Sessions taught by the selected lecturer."
    elif mode == "student":
        if not degree_id:
            raise ValueError("Degree not found")
        degree = db.query(V2Degree).filter(V2Degree.id == degree_id).first()
        if not degree:
            raise ValueError("Degree not found")
        path = None
        if path_id:
            path = db.query(V2Path).filter(V2Path.id == path_id).first()
            if not path:
                raise ValueError("Path not found")
            groups = (
                db.query(V2StudentGroup)
                .filter(
                    V2StudentGroup.degree_id == degree_id,
                    V2StudentGroup.path_id == path_id,
                    V2StudentGroup.year == path.year,
                )
                .all()
            )
            if not groups:
                raise ValueError("Student path has no matching groups")
            target_group_names = {group.name for group in groups}
            target_label = f"{degree.code} - {path.code}"
            subtitle = "Sessions attended by the selected degree and path."
        else:
            if not study_year:
                raise ValueError("Study year not found")
            groups = (
                db.query(V2StudentGroup)
                .filter(
                    V2StudentGroup.degree_id == degree_id,
                    V2StudentGroup.path_id.is_(None),
                    V2StudentGroup.year == study_year,
                )
                .all()
            )
            if not groups:
                raise ValueError("General student group not found for the selected degree")
            target_group_names = {group.name for group in groups}
            target_label = f"{degree.code} - Year {study_year} General"
            subtitle = "Sessions attended by the selected degree cohort."
        entries = [
            entry
            for entry in entries
            if any(name in target_group_names for name in entry["student_group_names"])
        ]
        title = f"Student Timetable - {target_label}"
    else:
        title = "Faculty Timetable"
        subtitle = "Default faculty timetable with all session details."

    serialized["entries"] = entries
    return {
        "mode": mode,
        "title": title,
        "subtitle": subtitle,
        "solution": serialized,
    }


def export_view(view_payload: dict, export_format: str) -> ExportResponse:
    entries = view_payload["solution"]["entries"]
    filename_root = view_payload["mode"]

    if export_format == "csv":
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(
            [
                "Day",
                "Start",
                "Duration",
                "Module Code",
                "Module Name",
                "Session",
                "Room",
                "Lecturers",
                "Student Groups",
                "Degree Paths",
                "Students",
            ]
        )
        for entry in entries:
            writer.writerow(
                [
                    entry["day"],
                    entry["start_minute"],
                    entry["duration_minutes"],
                    entry["module_code"],
                    entry["module_name"],
                    entry["session_name"],
                    entry["room_name"],
                    "; ".join(entry["lecturer_names"]),
                    "; ".join(entry["student_group_names"]),
                    "; ".join(entry["degree_path_labels"]),
                    entry["total_students"],
                ]
            )
        data = buffer.getvalue().encode("utf-8")
        return ExportResponse(
            filename=f"{filename_root}-timetable.csv",
            content_type="text/csv",
            content=base64.b64encode(data).decode("ascii"),
        )

    if export_format == "xls":
        buffer = io.StringIO()
        buffer.write(
            "\t".join(
                ["Day", "Start", "Duration", "Module", "Room", "Lecturers", "Groups"]
            )
        )
        buffer.write("\n")
        for entry in entries:
            buffer.write(
                "\t".join(
                    [
                        entry["day"],
                        str(entry["start_minute"]),
                        str(entry["duration_minutes"]),
                        entry["module_code"],
                        entry["room_name"],
                        "; ".join(entry["lecturer_names"]),
                        "; ".join(entry["student_group_names"]),
                    ]
                )
            )
            buffer.write("\n")
        data = buffer.getvalue().encode("utf-8")
        return ExportResponse(
            filename=f"{filename_root}-timetable.xls",
            content_type="application/vnd.ms-excel",
            content=base64.b64encode(data).decode("ascii"),
        )

    plain_text = [view_payload["title"], view_payload["subtitle"], ""]
    for entry in entries:
        plain_text.append(
            f"{entry['day']} {entry['start_minute']} ({entry['duration_minutes']}m) | {entry['module_code']} | {entry['session_name']} | {entry['room_name']} | {', '.join(entry['lecturer_names'])}"
        )
    data = "\n".join(plain_text).encode("utf-8")
    content_type = "application/pdf" if export_format == "pdf" else "image/png"
    extension = export_format
    return ExportResponse(
        filename=f"{filename_root}-timetable.{extension}",
        content_type=content_type,
        content=base64.b64encode(data).decode("ascii"),
    )


def dataset_summary(db: Session) -> dict:
    return {
        "degrees": db.query(V2Degree).count(),
        "paths": db.query(V2Path).count(),
        "lecturers": db.query(V2Lecturer).count(),
        "rooms": db.query(V2Room).count(),
        "student_groups": db.query(V2StudentGroup).count(),
        "modules": db.query(V2Module).count(),
        "sessions": db.query(V2Session).count(),
    }


def read_dataset(db: Session) -> dict:
    degrees = db.query(V2Degree).order_by(V2Degree.id).all()
    paths = db.query(V2Path).order_by(V2Path.id).all()
    lecturers = db.query(V2Lecturer).order_by(V2Lecturer.id).all()
    rooms = db.query(V2Room).order_by(V2Room.id).all()
    student_groups = db.query(V2StudentGroup).order_by(V2StudentGroup.id).all()
    modules = db.query(V2Module).order_by(V2Module.id).all()
    sessions = (
        db.query(V2Session)
        .options(
            joinedload(V2Session.lecturers),
            joinedload(V2Session.student_groups),
        )
        .order_by(V2Session.id)
        .all()
    )

    degree_key_by_id = {int(item.id): item.client_key for item in degrees}
    path_key_by_id = {int(item.id): item.client_key for item in paths}
    room_key_by_id = {int(item.id): item.client_key for item in rooms}
    module_key_by_id = {int(item.id): item.client_key for item in modules}

    return {
        "degrees": [
            {
                "client_key": item.client_key,
                "code": item.code,
                "name": item.name,
                "duration_years": int(item.duration_years),
                "intake_label": item.intake_label,
            }
            for item in degrees
        ],
        "paths": [
            {
                "client_key": item.client_key,
                "degree_client_key": degree_key_by_id[int(item.degree_id)],
                "year": int(item.year),
                "code": item.code,
                "name": item.name,
            }
            for item in paths
        ],
        "lecturers": [
            {
                "client_key": item.client_key,
                "name": item.name,
                "email": item.email,
            }
            for item in lecturers
        ],
        "rooms": [
            {
                "client_key": item.client_key,
                "name": item.name,
                "capacity": int(item.capacity),
                "room_type": item.room_type,
                "lab_type": item.lab_type,
                "location": item.location,
                "year_restriction": item.year_restriction,
            }
            for item in rooms
        ],
        "student_groups": [
            {
                "client_key": item.client_key,
                "degree_client_key": degree_key_by_id[int(item.degree_id)],
                "path_client_key": path_key_by_id.get(int(item.path_id))
                if item.path_id
                else None,
                "year": int(item.year),
                "name": item.name,
                "size": int(item.size),
                "student_hashes": decode_student_hashes(item.student_hashes_json),
            }
            for item in student_groups
        ],
        "modules": [
            {
                "client_key": item.client_key,
                "code": item.code,
                "name": item.name,
                "subject_name": item.subject_name,
                "year": int(item.year),
                "semester": int(item.semester),
                "is_full_year": bool(item.is_full_year),
            }
            for item in modules
        ],
        "sessions": [
            {
                "client_key": item.client_key,
                "module_client_key": module_key_by_id[int(item.module_id)],
                "linked_module_client_keys": [
                    module_key_by_id[int(module.id)]
                    for module in _session_modules(item)[1:]
                    if int(module.id) in module_key_by_id
                ],
                "name": item.name,
                "session_type": item.session_type,
                "duration_minutes": int(item.duration_minutes),
                "occurrences_per_week": int(item.occurrences_per_week),
                "required_room_type": item.required_room_type,
                "required_lab_type": item.required_lab_type,
                "specific_room_client_key": room_key_by_id.get(int(item.specific_room_id))
                if item.specific_room_id
                else None,
                "max_students_per_group": item.max_students_per_group,
                "allow_parallel_rooms": bool(item.allow_parallel_rooms),
                "notes": item.notes,
                "lecturer_client_keys": [
                    lecturer.client_key
                    for lecturer in sorted(item.lecturers, key=lambda row: row.id)
                ],
                "student_group_client_keys": [
                    group.client_key
                    for group in sorted(item.student_groups, key=lambda row: row.id)
                ],
            }
            for item in sessions
        ],
    }


def lookup_options(db: Session, import_run_id: int | None = None) -> dict:
    if import_run_id:
        return _snapshot_lookup_options(db, import_run_id)
    lecturers = db.query(V2Lecturer).order_by(V2Lecturer.name).all()
    degrees = db.query(V2Degree).order_by(V2Degree.code).all()
    paths = db.query(V2Path).order_by(V2Path.degree_id, V2Path.year, V2Path.code).all()
    student_paths = [
        {
            "id": int(item.id),
            "degree_id": int(item.degree_id),
            "year": int(item.year),
            "label": f"Year {int(item.year)} - {item.code}",
        }
        for item in paths
    ]
    path_keys = {
        (int(item.degree_id), int(item.year))
        for item in paths
    }
    for degree in degrees:
        for year in range(1, int(degree.duration_years) + 1):
            if (int(degree.id), year) in path_keys:
                continue
            student_paths.append(
                {
                    "id": None,
                    "degree_id": int(degree.id),
                    "year": year,
                    "label": f"Year {year} - General",
                }
            )
    student_paths.sort(key=lambda item: (item["degree_id"], item["year"], item["label"]))
    return {
        "lecturers": [{"id": int(item.id), "label": item.name} for item in lecturers],
        "degrees": [{"id": int(item.id), "label": f"{item.code} - {item.name}"} for item in degrees],
        "student_paths": student_paths,
    }


def replace_dataset(db: Session, payload) -> dict:
    db.query(V2SolutionEntry).delete()
    db.query(V2TimetableSolution).delete()
    db.query(V2GenerationRun).delete()
    db.query(V2Session).delete()
    db.query(V2Module).delete()
    db.query(V2StudentGroup).delete()
    db.query(V2Lecturer).delete()
    db.query(V2Room).delete()
    db.query(V2Path).delete()
    db.query(V2Degree).delete()
    db.flush()

    degree_map: dict[str, V2Degree] = {}
    path_map: dict[str, V2Path] = {}
    lecturer_map: dict[str, V2Lecturer] = {}
    room_map: dict[str, V2Room] = {}
    group_map: dict[str, V2StudentGroup] = {}
    module_map: dict[str, V2Module] = {}

    for item in payload.degrees:
        row = V2Degree(**item.model_dump())
        db.add(row)
        db.flush()
        degree_map[item.client_key] = row

    for item in payload.paths:
        row = V2Path(
            client_key=item.client_key,
            degree_id=int(degree_map[item.degree_client_key].id),
            year=item.year,
            code=item.code,
            name=item.name,
        )
        db.add(row)
        db.flush()
        path_map[item.client_key] = row

    for item in payload.lecturers:
        row = V2Lecturer(**item.model_dump())
        db.add(row)
        db.flush()
        lecturer_map[item.client_key] = row

    for item in payload.rooms:
        row = V2Room(**item.model_dump())
        db.add(row)
        db.flush()
        room_map[item.client_key] = row

    for item in payload.student_groups:
        row = V2StudentGroup(
            client_key=item.client_key,
            degree_id=int(degree_map[item.degree_client_key].id),
            path_id=int(path_map[item.path_client_key].id)
            if item.path_client_key
            else None,
            year=item.year,
            name=item.name,
            size=item.size,
            student_hashes_json=encode_student_hashes(item.student_hashes),
        )
        db.add(row)
        db.flush()
        group_map[item.client_key] = row

    for item in payload.modules:
        row = V2Module(**item.model_dump())
        db.add(row)
        db.flush()
        module_map[item.client_key] = row

    for item in payload.sessions:
        row = V2Session(
            client_key=item.client_key,
            module_id=int(module_map[item.module_client_key].id),
            name=item.name,
            session_type=item.session_type,
            duration_minutes=item.duration_minutes,
            occurrences_per_week=item.occurrences_per_week,
            required_room_type=item.required_room_type,
            required_lab_type=item.required_lab_type,
            specific_room_id=int(room_map[item.specific_room_client_key].id)
            if item.specific_room_client_key
            else None,
            max_students_per_group=item.max_students_per_group,
            allow_parallel_rooms=item.allow_parallel_rooms,
            notes=item.notes,
        )
        linked_modules = []
        seen_module_keys = {item.module_client_key}
        for key in item.linked_module_client_keys:
            if key in seen_module_keys or key not in module_map:
                continue
            linked_modules.append(module_map[key])
            seen_module_keys.add(key)
        row.linked_modules = [module_map[item.module_client_key], *linked_modules]
        row.lecturers = [
            lecturer_map[key]
            for key in item.lecturer_client_keys
            if key in lecturer_map
        ]
        row.student_groups = [
            group_map[key] for key in item.student_group_client_keys if key in group_map
        ]
        db.add(row)

    db.commit()
    return dataset_summary(db)


def build_legacy_realistic_demo_dataset() -> dict:
    return {
        "degrees": [
            {
                "client_key": "degree_ps",
                "code": "PS",
                "name": "Physical Science",
                "duration_years": 3,
                "intake_label": "PS Intake",
            },
            {
                "client_key": "degree_bs",
                "code": "BS",
                "name": "Biological Science",
                "duration_years": 3,
                "intake_label": "BS Intake",
            },
            {
                "client_key": "degree_encm",
                "code": "ENCM",
                "name": "Environmental Conservation and Management",
                "duration_years": 3,
                "intake_label": "ENCM Intake",
            },
            {
                "client_key": "degree_apch",
                "code": "APCH",
                "name": "Applied Chemistry",
                "duration_years": 4,
                "intake_label": "APCH Intake",
            },
            {
                "client_key": "degree_becs",
                "code": "BECS",
                "name": "Electronics and Computer Science",
                "duration_years": 4,
                "intake_label": "BECS Intake",
            },
            {
                "client_key": "degree_pe",
                "code": "PE",
                "name": "Physics and Electronics",
                "duration_years": 3,
                "intake_label": "PE Intake",
            },
        ],
        "paths": [
            {
                "client_key": "path_ps_y1_general",
                "degree_client_key": "degree_ps",
                "year": 1,
                "code": "PS-G1",
                "name": "Physical Science General",
            },
            {
                "client_key": "path_bs_y1_general",
                "degree_client_key": "degree_bs",
                "year": 1,
                "code": "BS-G1",
                "name": "Biological Science General",
            },
            {
                "client_key": "path_ps_elec",
                "degree_client_key": "degree_ps",
                "year": 2,
                "code": "PS-ELEC",
                "name": "Physical Science Electronics Focus",
            },
            {
                "client_key": "path_ps_stat",
                "degree_client_key": "degree_ps",
                "year": 2,
                "code": "PS-STAT",
                "name": "Physical Science Statistics Focus",
            },
            {
                "client_key": "path_bs_mibi",
                "degree_client_key": "degree_bs",
                "year": 2,
                "code": "BS-MIBI",
                "name": "Biological Science Microbiology Focus",
            },
            {
                "client_key": "path_bs_bioc",
                "degree_client_key": "degree_bs",
                "year": 2,
                "code": "BS-BIOC",
                "name": "Biological Science Biochemistry Focus",
            },
        ],
        "lecturers": [
            {
                "client_key": "lect_fernando",
                "name": "Dr Fernando",
                "email": "fernando@science.kln.ac.lk",
            },
            {
                "client_key": "lect_perera",
                "name": "Dr Perera",
                "email": "perera@science.kln.ac.lk",
            },
            {
                "client_key": "lect_silva",
                "name": "Dr Silva",
                "email": "silva@science.kln.ac.lk",
            },
            {
                "client_key": "lect_jayasinghe",
                "name": "Ms Jayasinghe",
                "email": "jayasinghe@science.kln.ac.lk",
            },
            {
                "client_key": "lect_wijesinghe",
                "name": "Dr Wijesinghe",
                "email": "wijesinghe@science.kln.ac.lk",
            },
            {
                "client_key": "lect_gunawardena",
                "name": "Dr Gunawardena",
                "email": "gunawardena@science.kln.ac.lk",
            },
            {
                "client_key": "lect_abeysinghe",
                "name": "Dr Abeysinghe",
                "email": "abeysinghe@science.kln.ac.lk",
            },
            {
                "client_key": "lect_ranasinghe",
                "name": "Prof Ranasinghe",
                "email": "ranasinghe@science.kln.ac.lk",
            },
            {
                "client_key": "lect_kumari",
                "name": "Ms Kumari",
                "email": "kumari@science.kln.ac.lk",
            },
            {
                "client_key": "lect_de_silva",
                "name": "Dr De Silva",
                "email": "desilva@science.kln.ac.lk",
            },
        ],
        "rooms": [
            {
                "client_key": "room_auditorium",
                "name": "Auditorium",
                "capacity": 2000,
                "room_type": "lecture",
                "lab_type": None,
                "location": "Faculty Central",
                "year_restriction": None,
            },
            {
                "client_key": "room_a11201",
                "name": "A11 201",
                "capacity": 150,
                "room_type": "lecture",
                "lab_type": None,
                "location": "A11 Complex",
                "year_restriction": None,
            },
            {
                "client_key": "room_a11301",
                "name": "A11 301",
                "capacity": 150,
                "room_type": "lecture",
                "lab_type": None,
                "location": "A11 Complex",
                "year_restriction": None,
            },
            {
                "client_key": "room_a11207",
                "name": "A11 207",
                "capacity": 150,
                "room_type": "lecture",
                "lab_type": None,
                "location": "A11 Complex",
                "year_restriction": None,
            },
            {
                "client_key": "room_a11307",
                "name": "A11 307",
                "capacity": 150,
                "room_type": "lecture",
                "lab_type": None,
                "location": "A11 Complex",
                "year_restriction": None,
            },
            {
                "client_key": "room_a7201",
                "name": "A7 201",
                "capacity": 200,
                "room_type": "lecture",
                "lab_type": None,
                "location": "A7 Complex",
                "year_restriction": None,
            },
            {
                "client_key": "room_a7301",
                "name": "A7 301",
                "capacity": 300,
                "room_type": "lecture",
                "lab_type": None,
                "location": "A7 Complex",
                "year_restriction": None,
            },
            {
                "client_key": "room_a7303",
                "name": "A7 303",
                "capacity": 100,
                "room_type": "lecture",
                "lab_type": None,
                "location": "A7 Complex",
                "year_restriction": None,
            },
            {
                "client_key": "room_a7406",
                "name": "A7 406",
                "capacity": 400,
                "room_type": "lecture",
                "lab_type": None,
                "location": "A7 Complex",
                "year_restriction": None,
            },
            {
                "client_key": "room_b1212",
                "name": "B1 212",
                "capacity": 800,
                "room_type": "lecture",
                "lab_type": None,
                "location": "B1 Complex",
                "year_restriction": None,
            },
            {
                "client_key": "room_b1343",
                "name": "B1 343",
                "capacity": 50,
                "room_type": "lecture",
                "lab_type": None,
                "location": "B1 Complex",
                "year_restriction": None,
            },
            {
                "client_key": "room_computer_lab",
                "name": "Computer LAB",
                "capacity": 50,
                "room_type": "lab",
                "lab_type": "computer",
                "location": "Statistics and Computer Science",
                "year_restriction": None,
            },
            {
                "client_key": "room_electronics_lab",
                "name": "Electronics Lab",
                "capacity": 40,
                "room_type": "lab",
                "lab_type": "electronics",
                "location": "Physics and Electronics",
                "year_restriction": 1,
            },
            {
                "client_key": "room_chemistry_lab",
                "name": "Chemistry Lab",
                "capacity": 60,
                "room_type": "lab",
                "lab_type": "chemistry",
                "location": "Chemistry Department",
                "year_restriction": None,
            },
            {
                "client_key": "room_physics_lab",
                "name": "Physics Lab 1",
                "capacity": 40,
                "room_type": "lab",
                "lab_type": "physics",
                "location": "Physics Department",
                "year_restriction": None,
            },
            {
                "client_key": "room_em_lab",
                "name": "EM Labs",
                "capacity": 40,
                "room_type": "lab",
                "lab_type": "environmental",
                "location": "Zoology and Environmental Management",
                "year_restriction": None,
            },
            {
                "client_key": "room_gym",
                "name": "Gymnasium/Ground",
                "capacity": 120,
                "room_type": "lab",
                "lab_type": "sports",
                "location": "Sports Unit",
                "year_restriction": None,
            },
        ],
        "student_groups": [
            {
                "client_key": "group_ps_y1",
                "degree_client_key": "degree_ps",
                "path_client_key": "path_ps_y1_general",
                "year": 1,
                "name": "PS Y1 General",
                "size": 60,
            },
            {
                "client_key": "group_bs_y1",
                "degree_client_key": "degree_bs",
                "path_client_key": "path_bs_y1_general",
                "year": 1,
                "name": "BS Y1 General",
                "size": 60,
            },
            {
                "client_key": "group_encm_y1",
                "degree_client_key": "degree_encm",
                "path_client_key": None,
                "year": 1,
                "name": "ENCM Y1 Direct",
                "size": 30,
            },
            {
                "client_key": "group_apch_y1",
                "degree_client_key": "degree_apch",
                "path_client_key": None,
                "year": 1,
                "name": "APCH Y1 Direct",
                "size": 30,
            },
            {
                "client_key": "group_becs_y1",
                "degree_client_key": "degree_becs",
                "path_client_key": None,
                "year": 1,
                "name": "BECS Y1 Direct",
                "size": 40,
            },
            {
                "client_key": "group_pe_y1",
                "degree_client_key": "degree_pe",
                "path_client_key": None,
                "year": 1,
                "name": "PE Y1 Direct",
                "size": 30,
            },
            {
                "client_key": "group_ps_y2_elec",
                "degree_client_key": "degree_ps",
                "path_client_key": "path_ps_elec",
                "year": 2,
                "name": "PS Y2 Electronics Focus",
                "size": 30,
            },
            {
                "client_key": "group_ps_y2_stat",
                "degree_client_key": "degree_ps",
                "path_client_key": "path_ps_stat",
                "year": 2,
                "name": "PS Y2 Statistics Focus",
                "size": 25,
            },
            {
                "client_key": "group_bs_y2_mibi",
                "degree_client_key": "degree_bs",
                "path_client_key": "path_bs_mibi",
                "year": 2,
                "name": "BS Y2 Microbiology Focus",
                "size": 24,
            },
            {
                "client_key": "group_bs_y2_bioc",
                "degree_client_key": "degree_bs",
                "path_client_key": "path_bs_bioc",
                "year": 2,
                "name": "BS Y2 Biochemistry Focus",
                "size": 24,
            },
            {
                "client_key": "group_ps_y3",
                "degree_client_key": "degree_ps",
                "path_client_key": None,
                "year": 3,
                "name": "PS Y3 General",
                "size": 22,
            },
            {
                "client_key": "group_bs_y3",
                "degree_client_key": "degree_bs",
                "path_client_key": None,
                "year": 3,
                "name": "BS Y3 General",
                "size": 22,
            },
            {
                "client_key": "group_encm_y2",
                "degree_client_key": "degree_encm",
                "path_client_key": None,
                "year": 2,
                "name": "ENCM Y2 Direct",
                "size": 28,
            },
            {
                "client_key": "group_encm_y3",
                "degree_client_key": "degree_encm",
                "path_client_key": None,
                "year": 3,
                "name": "ENCM Y3 Direct",
                "size": 24,
            },
            {
                "client_key": "group_pe_y2",
                "degree_client_key": "degree_pe",
                "path_client_key": None,
                "year": 2,
                "name": "PE Y2 Direct",
                "size": 28,
            },
            {
                "client_key": "group_pe_y3",
                "degree_client_key": "degree_pe",
                "path_client_key": None,
                "year": 3,
                "name": "PE Y3 Direct",
                "size": 24,
            },
            {
                "client_key": "group_apch_y2",
                "degree_client_key": "degree_apch",
                "path_client_key": None,
                "year": 2,
                "name": "APCH Y2 Direct",
                "size": 28,
            },
            {
                "client_key": "group_apch_y3",
                "degree_client_key": "degree_apch",
                "path_client_key": None,
                "year": 3,
                "name": "APCH Y3 Direct",
                "size": 24,
            },
            {
                "client_key": "group_apch_y4",
                "degree_client_key": "degree_apch",
                "path_client_key": None,
                "year": 4,
                "name": "APCH Y4 Direct",
                "size": 20,
            },
            {
                "client_key": "group_becs_y2",
                "degree_client_key": "degree_becs",
                "path_client_key": None,
                "year": 2,
                "name": "BECS Y2 Direct",
                "size": 34,
            },
            {
                "client_key": "group_becs_y3",
                "degree_client_key": "degree_becs",
                "path_client_key": None,
                "year": 3,
                "name": "BECS Y3 Direct",
                "size": 30,
            },
            {
                "client_key": "group_becs_y4",
                "degree_client_key": "degree_becs",
                "path_client_key": None,
                "year": 4,
                "name": "BECS Y4 Direct",
                "size": 24,
            },
        ],
        "modules": [
            {
                "client_key": "mod_aclt11012",
                "code": "ACLT 11012",
                "name": "Academic Literacy",
                "subject_name": "Literacy",
                "year": 1,
                "semester": 1,
                "is_full_year": False,
            },
            {
                "client_key": "mod_cmsk11012",
                "code": "CMSK 11012",
                "name": "Complementary Skill Development",
                "subject_name": "Skills",
                "year": 1,
                "semester": 1,
                "is_full_year": False,
            },
            {
                "client_key": "mod_macs11012",
                "code": "MACS 11012",
                "name": "Management and Computer Studies",
                "subject_name": "Management and IT",
                "year": 1,
                "semester": 1,
                "is_full_year": False,
            },
            {
                "client_key": "mod_amat11012",
                "code": "AMAT 11012",
                "name": "Foundations in Applied Maths",
                "subject_name": "Mathematics",
                "year": 1,
                "semester": 1,
                "is_full_year": False,
            },
            {
                "client_key": "mod_stat11613",
                "code": "STAT 11613",
                "name": "Fundamentals of Statistics",
                "subject_name": "Statistics",
                "year": 1,
                "semester": 1,
                "is_full_year": False,
            },
            {
                "client_key": "mod_stat11621",
                "code": "STAT 11621",
                "name": "Statistical Laboratory",
                "subject_name": "Statistics",
                "year": 1,
                "semester": 1,
                "is_full_year": False,
            },
            {
                "client_key": "mod_chem11612",
                "code": "CHEM 11612",
                "name": "Atomic Structure and Periodic Table",
                "subject_name": "Chemistry",
                "year": 1,
                "semester": 1,
                "is_full_year": False,
            },
            {
                "client_key": "mod_chem11631",
                "code": "CHEM 11631",
                "name": "Basic Chemical Analysis Laboratory",
                "subject_name": "Chemistry",
                "year": 1,
                "semester": 1,
                "is_full_year": False,
            },
            {
                "client_key": "mod_phys11512",
                "code": "PHYS 11512",
                "name": "Mechanics and Properties of Matter",
                "subject_name": "Physics",
                "year": 1,
                "semester": 1,
                "is_full_year": False,
            },
            {
                "client_key": "mod_phys11521",
                "code": "PHYS 11521",
                "name": "Elementary Physics Laboratory I",
                "subject_name": "Physics",
                "year": 1,
                "semester": 1,
                "is_full_year": False,
            },
            {
                "client_key": "mod_elec11534",
                "code": "ELEC 11534",
                "name": "Basic Electronics",
                "subject_name": "Electronics",
                "year": 1,
                "semester": 1,
                "is_full_year": False,
            },
            {
                "client_key": "mod_elec11541",
                "code": "ELEC 11541",
                "name": "Basic Electronics Laboratory",
                "subject_name": "Electronics",
                "year": 1,
                "semester": 1,
                "is_full_year": False,
            },
            {
                "client_key": "mod_biol11512",
                "code": "BIOL 11512",
                "name": "Scope and Fundamentals of Microbiology",
                "subject_name": "Microbiology",
                "year": 1,
                "semester": 1,
                "is_full_year": False,
            },
            {
                "client_key": "mod_biol11542",
                "code": "BIOL 11542",
                "name": "Animal Form and Function",
                "subject_name": "Zoology",
                "year": 1,
                "semester": 1,
                "is_full_year": False,
            },
            {
                "client_key": "mod_encm11702",
                "code": "ENCM 11702",
                "name": "Evolution of Earth and Biogeography",
                "subject_name": "Environmental Management",
                "year": 1,
                "semester": 1,
                "is_full_year": False,
            },
            {
                "client_key": "mod_encm11713",
                "code": "ENCM 11713",
                "name": "Basic Geology",
                "subject_name": "Environmental Management",
                "year": 1,
                "semester": 1,
                "is_full_year": False,
            },
            {
                "client_key": "mod_apch11612",
                "code": "APCH 11612",
                "name": "Computer Skills for Chemists",
                "subject_name": "Applied Chemistry",
                "year": 1,
                "semester": 1,
                "is_full_year": False,
            },
            {
                "client_key": "mod_becs11212",
                "code": "BECS 11212",
                "name": "Foundations in Computer Science",
                "subject_name": "Computer Science",
                "year": 1,
                "semester": 1,
                "is_full_year": False,
            },
            {
                "client_key": "mod_becs11223",
                "code": "BECS 11223",
                "name": "Fundamentals of Programming",
                "subject_name": "Computer Science",
                "year": 1,
                "semester": 1,
                "is_full_year": False,
            },
            {
                "client_key": "mod_chem22702",
                "code": "CHEM 22702",
                "name": "Inorganic Chemistry",
                "subject_name": "Chemistry",
                "year": 2,
                "semester": 2,
                "is_full_year": False,
            },
            {
                "client_key": "mod_chem22721",
                "code": "CHEM 22721",
                "name": "Analytical Chemistry Laboratory",
                "subject_name": "Chemistry",
                "year": 2,
                "semester": 2,
                "is_full_year": False,
            },
            {
                "client_key": "mod_elec22534",
                "code": "ELEC 22534",
                "name": "Analogue Electronics",
                "subject_name": "Electronics",
                "year": 2,
                "semester": 2,
                "is_full_year": False,
            },
            {
                "client_key": "mod_mibi22554",
                "code": "MIBI 22554",
                "name": "Microbial Genetics",
                "subject_name": "Microbiology",
                "year": 2,
                "semester": 2,
                "is_full_year": False,
            },
            {
                "client_key": "mod_bioc22642",
                "code": "BIOC 22642",
                "name": "Biochemical Regulation",
                "subject_name": "Biochemistry",
                "year": 2,
                "semester": 2,
                "is_full_year": False,
            },
            {
                "client_key": "mod_phys33612",
                "code": "PHYS 33612",
                "name": "Modern Physics",
                "subject_name": "Physics",
                "year": 3,
                "semester": 1,
                "is_full_year": False,
            },
            {
                "client_key": "mod_encm32712",
                "code": "ENCM 32712",
                "name": "Environmental Pollution",
                "subject_name": "Environmental Management",
                "year": 3,
                "semester": 1,
                "is_full_year": False,
            },
            {
                "client_key": "mod_apch34612",
                "code": "APCH 34612",
                "name": "Advanced Analytical Chemistry",
                "subject_name": "Applied Chemistry",
                "year": 3,
                "semester": 1,
                "is_full_year": False,
            },
            {
                "client_key": "mod_apch44812",
                "code": "APCH 44812",
                "name": "Industrial Chemistry Project",
                "subject_name": "Applied Chemistry",
                "year": 4,
                "semester": 2,
                "is_full_year": False,
            },
            {
                "client_key": "mod_becs22421",
                "code": "BECS 22421",
                "name": "Data Structures",
                "subject_name": "Computer Science",
                "year": 2,
                "semester": 2,
                "is_full_year": False,
            },
            {
                "client_key": "mod_becs33431",
                "code": "BECS 33431",
                "name": "Computer Architecture",
                "subject_name": "Computer Engineering",
                "year": 3,
                "semester": 1,
                "is_full_year": False,
            },
            {
                "client_key": "mod_becs44641",
                "code": "BECS 44641",
                "name": "Embedded Systems Project",
                "subject_name": "Computer Engineering",
                "year": 4,
                "semester": 2,
                "is_full_year": False,
            },
        ],
        "sessions": [
            {
                "client_key": "sess_aclt11012_lecture",
                "module_client_key": "mod_aclt11012",
                "name": "Academic Literacy Lecture",
                "session_type": "lecture",
                "duration_minutes": 120,
                "occurrences_per_week": 1,
                "required_room_type": "lecture",
                "required_lab_type": None,
                "specific_room_client_key": "room_auditorium",
                "max_students_per_group": None,
                "allow_parallel_rooms": False,
                "notes": None,
                "lecturer_client_keys": ["lect_jayasinghe"],
                "student_group_client_keys": [
                    "group_ps_y1",
                    "group_bs_y1",
                    "group_encm_y1",
                    "group_apch_y1",
                    "group_becs_y1",
                    "group_pe_y1",
                ],
            },
            {
                "client_key": "sess_macs11012_lecture",
                "module_client_key": "mod_macs11012",
                "name": "Management and Computer Studies Lecture",
                "session_type": "lecture",
                "duration_minutes": 120,
                "occurrences_per_week": 1,
                "required_room_type": "lecture",
                "required_lab_type": None,
                "specific_room_client_key": "room_auditorium",
                "max_students_per_group": None,
                "allow_parallel_rooms": False,
                "notes": "Shared common module for most first-year cohorts.",
                "lecturer_client_keys": ["lect_ranasinghe"],
                "student_group_client_keys": [
                    "group_ps_y1",
                    "group_bs_y1",
                    "group_becs_y1",
                    "group_pe_y1",
                ],
            },
            {
                "client_key": "sess_amat11012_lecture",
                "module_client_key": "mod_amat11012",
                "name": "Applied Maths Lecture",
                "session_type": "lecture",
                "duration_minutes": 60,
                "occurrences_per_week": 2,
                "required_room_type": "lecture",
                "required_lab_type": None,
                "specific_room_client_key": "room_auditorium",
                "max_students_per_group": None,
                "allow_parallel_rooms": False,
                "notes": None,
                "lecturer_client_keys": ["lect_wijesinghe"],
                "student_group_client_keys": ["group_ps_y1", "group_pe_y1"],
            },
            {
                "client_key": "sess_stat11613_lecture",
                "module_client_key": "mod_stat11613",
                "name": "Fundamentals of Statistics Lecture",
                "session_type": "lecture",
                "duration_minutes": 60,
                "occurrences_per_week": 2,
                "required_room_type": "lecture",
                "required_lab_type": None,
                "specific_room_client_key": "room_auditorium",
                "max_students_per_group": None,
                "allow_parallel_rooms": False,
                "notes": None,
                "lecturer_client_keys": ["lect_silva"],
                "student_group_client_keys": ["group_ps_y1", "group_ps_y2_stat"],
            },
            {
                "client_key": "sess_chem11612_lecture",
                "module_client_key": "mod_chem11612",
                "name": "Atomic Structure Lecture",
                "session_type": "lecture",
                "duration_minutes": 60,
                "occurrences_per_week": 2,
                "required_room_type": "lecture",
                "required_lab_type": None,
                "specific_room_client_key": "room_auditorium",
                "max_students_per_group": None,
                "allow_parallel_rooms": False,
                "notes": "Shared chemistry theory across biological and applied chemistry groups.",
                "lecturer_client_keys": ["lect_perera"],
                "student_group_client_keys": ["group_bs_y1", "group_apch_y1"],
            },
            {
                "client_key": "sess_chem11631_lab",
                "module_client_key": "mod_chem11631",
                "name": "Basic Chemical Analysis Lab",
                "session_type": "lab",
                "duration_minutes": 180,
                "occurrences_per_week": 1,
                "required_room_type": "lab",
                "required_lab_type": "chemistry",
                "specific_room_client_key": "room_chemistry_lab",
                "max_students_per_group": 60,
                "allow_parallel_rooms": False,
                "notes": "Year 1 chemistry practical in split groups.",
                "lecturer_client_keys": ["lect_perera", "lect_gunawardena"],
                "student_group_client_keys": ["group_bs_y1", "group_apch_y1"],
            },
            {
                "client_key": "sess_phys11512_lecture",
                "module_client_key": "mod_phys11512",
                "name": "Mechanics and Matter Lecture",
                "session_type": "lecture",
                "duration_minutes": 60,
                "occurrences_per_week": 2,
                "required_room_type": "lecture",
                "required_lab_type": None,
                "specific_room_client_key": "room_auditorium",
                "max_students_per_group": None,
                "allow_parallel_rooms": False,
                "notes": None,
                "lecturer_client_keys": ["lect_fernando"],
                "student_group_client_keys": ["group_ps_y1", "group_pe_y1"],
            },
            {
                "client_key": "sess_phys11521_lab",
                "module_client_key": "mod_phys11521",
                "name": "Elementary Physics Lab",
                "session_type": "lab",
                "duration_minutes": 180,
                "occurrences_per_week": 1,
                "required_room_type": "lab",
                "required_lab_type": "physics",
                "specific_room_client_key": "room_physics_lab",
                "max_students_per_group": 40,
                "allow_parallel_rooms": False,
                "notes": "Large first-year physics cohorts rotate in lab groups.",
                "lecturer_client_keys": ["lect_fernando", "lect_abeysinghe"],
                "student_group_client_keys": ["group_ps_y1", "group_pe_y1"],
            },
            {
                "client_key": "sess_elec11534_lecture",
                "module_client_key": "mod_elec11534",
                "name": "Basic Electronics Lecture",
                "session_type": "lecture",
                "duration_minutes": 60,
                "occurrences_per_week": 2,
                "required_room_type": "lecture",
                "required_lab_type": None,
                "specific_room_client_key": "room_auditorium",
                "max_students_per_group": None,
                "allow_parallel_rooms": False,
                "notes": "Heavy theory load observed for electronics foundation units.",
                "lecturer_client_keys": ["lect_abeysinghe"],
                "student_group_client_keys": ["group_ps_y1", "group_becs_y1", "group_pe_y1"],
            },
            {
                "client_key": "sess_elec11541_lab",
                "module_client_key": "mod_elec11541",
                "name": "Basic Electronics Lab",
                "session_type": "lab",
                "duration_minutes": 180,
                "occurrences_per_week": 1,
                "required_room_type": "lab",
                "required_lab_type": "electronics",
                "specific_room_client_key": "room_electronics_lab",
                "max_students_per_group": 40,
                "allow_parallel_rooms": False,
                "notes": "Electronics practical delivered in rotating lab groups.",
                "lecturer_client_keys": ["lect_abeysinghe", "lect_de_silva"],
                "student_group_client_keys": ["group_becs_y1", "group_pe_y1"],
            },
            {
                "client_key": "sess_biol11512_lecture",
                "module_client_key": "mod_biol11512",
                "name": "Microbiology Foundations Lecture",
                "session_type": "lecture",
                "duration_minutes": 60,
                "occurrences_per_week": 2,
                "required_room_type": "lecture",
                "required_lab_type": None,
                "specific_room_client_key": "room_a11201",
                "max_students_per_group": None,
                "allow_parallel_rooms": False,
                "notes": None,
                "lecturer_client_keys": ["lect_gunawardena"],
                "student_group_client_keys": ["group_bs_y1", "group_bs_y2_mibi"],
            },
            {
                "client_key": "sess_biol11542_lecture",
                "module_client_key": "mod_biol11542",
                "name": "Animal Form and Function Lecture",
                "session_type": "lecture",
                "duration_minutes": 60,
                "occurrences_per_week": 2,
                "required_room_type": "lecture",
                "required_lab_type": None,
                "specific_room_client_key": "room_a11201",
                "max_students_per_group": None,
                "allow_parallel_rooms": False,
                "notes": None,
                "lecturer_client_keys": ["lect_kumari"],
                "student_group_client_keys": ["group_bs_y1"],
            },
            {
                "client_key": "sess_encm11702_lecture",
                "module_client_key": "mod_encm11702",
                "name": "Earth and Biogeography Lecture",
                "session_type": "lecture",
                "duration_minutes": 60,
                "occurrences_per_week": 2,
                "required_room_type": "lecture",
                "required_lab_type": None,
                "specific_room_client_key": "room_a11207",
                "max_students_per_group": None,
                "allow_parallel_rooms": False,
                "notes": None,
                "lecturer_client_keys": ["lect_ranasinghe"],
                "student_group_client_keys": ["group_encm_y1"],
            },
            {
                "client_key": "sess_encm11713_lecture",
                "module_client_key": "mod_encm11713",
                "name": "Basic Geology Lecture",
                "session_type": "lecture",
                "duration_minutes": 60,
                "occurrences_per_week": 3,
                "required_room_type": "lecture",
                "required_lab_type": None,
                "specific_room_client_key": "room_a11207",
                "max_students_per_group": None,
                "allow_parallel_rooms": False,
                "notes": None,
                "lecturer_client_keys": ["lect_ranasinghe"],
                "student_group_client_keys": ["group_encm_y1"],
            },
            {
                "client_key": "sess_apch11612_lab",
                "module_client_key": "mod_apch11612",
                "name": "Computer Skills for Chemists Lab",
                "session_type": "lab",
                "duration_minutes": 180,
                "occurrences_per_week": 1,
                "required_room_type": "lab",
                "required_lab_type": "computer",
                "specific_room_client_key": "room_computer_lab",
                "max_students_per_group": 50,
                "allow_parallel_rooms": False,
                "notes": "Computer skills practical for applied chemistry intake.",
                "lecturer_client_keys": ["lect_jayasinghe"],
                "student_group_client_keys": ["group_apch_y1"],
            },
            {
                "client_key": "sess_becs11212_lecture",
                "module_client_key": "mod_becs11212",
                "name": "Foundations in Computer Science Lecture",
                "session_type": "lecture",
                "duration_minutes": 60,
                "occurrences_per_week": 2,
                "required_room_type": "lecture",
                "required_lab_type": None,
                "specific_room_client_key": "room_b1212",
                "max_students_per_group": None,
                "allow_parallel_rooms": False,
                "notes": None,
                "lecturer_client_keys": ["lect_de_silva"],
                "student_group_client_keys": ["group_becs_y1"],
            },
            {
                "client_key": "sess_becs11223_lecture",
                "module_client_key": "mod_becs11223",
                "name": "Fundamentals of Programming Lecture",
                "session_type": "lecture",
                "duration_minutes": 90,
                "occurrences_per_week": 2,
                "required_room_type": "lecture",
                "required_lab_type": None,
                "specific_room_client_key": "room_b1212",
                "max_students_per_group": None,
                "allow_parallel_rooms": False,
                "notes": None,
                "lecturer_client_keys": ["lect_de_silva"],
                "student_group_client_keys": ["group_becs_y1"],
            },
            {
                "client_key": "sess_becs11223_lab",
                "module_client_key": "mod_becs11223",
                "name": "Fundamentals of Programming Lab",
                "session_type": "lab",
                "duration_minutes": 180,
                "occurrences_per_week": 1,
                "required_room_type": "lab",
                "required_lab_type": "computer",
                "specific_room_client_key": "room_computer_lab",
                "max_students_per_group": 50,
                "allow_parallel_rooms": False,
                "notes": "Programming practical in split groups.",
                "lecturer_client_keys": ["lect_de_silva", "lect_jayasinghe"],
                "student_group_client_keys": ["group_becs_y1"],
            },
            {
                "client_key": "sess_chem22702_lecture",
                "module_client_key": "mod_chem22702",
                "name": "Inorganic Chemistry Lecture",
                "session_type": "lecture",
                "duration_minutes": 90,
                "occurrences_per_week": 2,
                "required_room_type": "lecture",
                "required_lab_type": None,
                "specific_room_client_key": "room_a11201",
                "max_students_per_group": None,
                "allow_parallel_rooms": False,
                "notes": "Higher-year chemistry shared by BS biochemistry and APCH cohorts.",
                "lecturer_client_keys": ["lect_perera"],
                "student_group_client_keys": ["group_bs_y2_bioc", "group_apch_y2"],
            },
            {
                "client_key": "sess_chem22721_lab",
                "module_client_key": "mod_chem22721",
                "name": "Analytical Chemistry Laboratory",
                "session_type": "lab",
                "duration_minutes": 180,
                "occurrences_per_week": 1,
                "required_room_type": "lab",
                "required_lab_type": "chemistry",
                "specific_room_client_key": "room_chemistry_lab",
                "max_students_per_group": 30,
                "allow_parallel_rooms": False,
                "notes": "Shared analytical lab block.",
                "lecturer_client_keys": ["lect_perera", "lect_gunawardena"],
                "student_group_client_keys": ["group_bs_y2_bioc", "group_apch_y2"],
            },
            {
                "client_key": "sess_elec22534_lecture",
                "module_client_key": "mod_elec22534",
                "name": "Analogue Electronics Lecture",
                "session_type": "lecture",
                "duration_minutes": 90,
                "occurrences_per_week": 2,
                "required_room_type": "lecture",
                "required_lab_type": None,
                "specific_room_client_key": "room_a7301",
                "max_students_per_group": None,
                "allow_parallel_rooms": False,
                "notes": "Shared electronics theory for PS-ELEC, BECS and PE Year 2.",
                "lecturer_client_keys": ["lect_abeysinghe"],
                "student_group_client_keys": ["group_ps_y2_elec", "group_becs_y2", "group_pe_y2"],
            },
            {
                "client_key": "sess_mibi22554_lecture",
                "module_client_key": "mod_mibi22554",
                "name": "Microbial Genetics Lecture",
                "session_type": "lecture",
                "duration_minutes": 60,
                "occurrences_per_week": 2,
                "required_room_type": "lecture",
                "required_lab_type": None,
                "specific_room_client_key": "room_a11207",
                "max_students_per_group": None,
                "allow_parallel_rooms": False,
                "notes": None,
                "lecturer_client_keys": ["lect_gunawardena"],
                "student_group_client_keys": ["group_bs_y2_mibi"],
            },
            {
                "client_key": "sess_bioc22642_lecture",
                "module_client_key": "mod_bioc22642",
                "name": "Biochemical Regulation Lecture",
                "session_type": "lecture",
                "duration_minutes": 60,
                "occurrences_per_week": 2,
                "required_room_type": "lecture",
                "required_lab_type": None,
                "specific_room_client_key": "room_a11307",
                "max_students_per_group": None,
                "allow_parallel_rooms": False,
                "notes": None,
                "lecturer_client_keys": ["lect_kumari"],
                "student_group_client_keys": ["group_bs_y2_bioc"],
            },
            {
                "client_key": "sess_becs22421_lecture",
                "module_client_key": "mod_becs22421",
                "name": "Data Structures Lecture",
                "session_type": "lecture",
                "duration_minutes": 90,
                "occurrences_per_week": 2,
                "required_room_type": "lecture",
                "required_lab_type": None,
                "specific_room_client_key": "room_b1212",
                "max_students_per_group": None,
                "allow_parallel_rooms": False,
                "notes": None,
                "lecturer_client_keys": ["lect_de_silva"],
                "student_group_client_keys": ["group_becs_y2"],
            },
            {
                "client_key": "sess_phys33612_lecture",
                "module_client_key": "mod_phys33612",
                "name": "Modern Physics Lecture",
                "session_type": "lecture",
                "duration_minutes": 90,
                "occurrences_per_week": 2,
                "required_room_type": "lecture",
                "required_lab_type": None,
                "specific_room_client_key": "room_a7201",
                "max_students_per_group": None,
                "allow_parallel_rooms": False,
                "notes": "Shared advanced physics theory.",
                "lecturer_client_keys": ["lect_fernando"],
                "student_group_client_keys": ["group_ps_y3", "group_pe_y3"],
            },
            {
                "client_key": "sess_encm32712_lecture",
                "module_client_key": "mod_encm32712",
                "name": "Environmental Pollution Lecture",
                "session_type": "lecture",
                "duration_minutes": 60,
                "occurrences_per_week": 2,
                "required_room_type": "lecture",
                "required_lab_type": None,
                "specific_room_client_key": "room_a11207",
                "max_students_per_group": None,
                "allow_parallel_rooms": False,
                "notes": None,
                "lecturer_client_keys": ["lect_ranasinghe"],
                "student_group_client_keys": ["group_encm_y3"],
            },
            {
                "client_key": "sess_apch34612_lecture",
                "module_client_key": "mod_apch34612",
                "name": "Advanced Analytical Chemistry Lecture",
                "session_type": "lecture",
                "duration_minutes": 90,
                "occurrences_per_week": 2,
                "required_room_type": "lecture",
                "required_lab_type": None,
                "specific_room_client_key": "room_a11201",
                "max_students_per_group": None,
                "allow_parallel_rooms": False,
                "notes": None,
                "lecturer_client_keys": ["lect_perera"],
                "student_group_client_keys": ["group_apch_y3"],
            },
            {
                "client_key": "sess_becs33431_lecture",
                "module_client_key": "mod_becs33431",
                "name": "Computer Architecture Lecture",
                "session_type": "lecture",
                "duration_minutes": 90,
                "occurrences_per_week": 2,
                "required_room_type": "lecture",
                "required_lab_type": None,
                "specific_room_client_key": "room_b1212",
                "max_students_per_group": None,
                "allow_parallel_rooms": False,
                "notes": None,
                "lecturer_client_keys": ["lect_de_silva"],
                "student_group_client_keys": ["group_becs_y3"],
            },
            {
                "client_key": "sess_apch44812_project",
                "module_client_key": "mod_apch44812",
                "name": "Industrial Chemistry Project Seminar",
                "session_type": "seminar",
                "duration_minutes": 120,
                "occurrences_per_week": 1,
                "required_room_type": "seminar",
                "required_lab_type": None,
                "specific_room_client_key": "room_b1343",
                "max_students_per_group": None,
                "allow_parallel_rooms": False,
                "notes": "Final-year project supervision block.",
                "lecturer_client_keys": ["lect_perera", "lect_jayasinghe"],
                "student_group_client_keys": ["group_apch_y4"],
            },
            {
                "client_key": "sess_becs44641_project",
                "module_client_key": "mod_becs44641",
                "name": "Embedded Systems Project Lab",
                "session_type": "lab",
                "duration_minutes": 180,
                "occurrences_per_week": 1,
                "required_room_type": "lab",
                "required_lab_type": "computer",
                "specific_room_client_key": "room_computer_lab",
                "max_students_per_group": 24,
                "allow_parallel_rooms": False,
                "notes": "Final-year BECS project lab block.",
                "lecturer_client_keys": ["lect_de_silva", "lect_abeysinghe"],
                "student_group_client_keys": ["group_becs_y4"],
            },
        ],
    }


def build_tuned_demo_dataset() -> dict:
    return {
        "degrees": [
            {
                "client_key": "degree_ps",
                "code": "PS",
                "name": "Physical Science",
                "duration_years": 1,
                "intake_label": "PS Intake",
            },
            {
                "client_key": "degree_bs",
                "code": "BS",
                "name": "Biological Science",
                "duration_years": 1,
                "intake_label": "BS Intake",
            },
            {
                "client_key": "degree_encm",
                "code": "ENCM",
                "name": "Environmental Conservation and Management",
                "duration_years": 1,
                "intake_label": "ENCM Intake",
            },
            {
                "client_key": "degree_apch",
                "code": "APCH",
                "name": "Applied Chemistry",
                "duration_years": 1,
                "intake_label": "APCH Intake",
            },
            {
                "client_key": "degree_becs",
                "code": "BECS",
                "name": "Electronics and Computer Science",
                "duration_years": 1,
                "intake_label": "BECS Intake",
            },
            {
                "client_key": "degree_pe",
                "code": "PE",
                "name": "Physics and Electronics",
                "duration_years": 1,
                "intake_label": "PE Intake",
            },
        ],
        "paths": [
            {
                "client_key": "path_ps_y1_general",
                "degree_client_key": "degree_ps",
                "year": 1,
                "code": "PS-G1",
                "name": "Physical Science General",
            },
            {
                "client_key": "path_bs_y1_general",
                "degree_client_key": "degree_bs",
                "year": 1,
                "code": "BS-G1",
                "name": "Biological Science General",
            },
        ],
        "lecturers": [
            {"client_key": "lect_jayasinghe", "name": "Ms Jayasinghe", "email": "jayasinghe@science.kln.ac.lk"},
            {"client_key": "lect_ranasinghe", "name": "Prof Ranasinghe", "email": "ranasinghe@science.kln.ac.lk"},
            {"client_key": "lect_wijesinghe", "name": "Dr Wijesinghe", "email": "wijesinghe@science.kln.ac.lk"},
            {"client_key": "lect_fernando", "name": "Dr Fernando", "email": "fernando@science.kln.ac.lk"},
            {"client_key": "lect_perera", "name": "Dr Perera", "email": "perera@science.kln.ac.lk"},
            {"client_key": "lect_abeysinghe", "name": "Dr Abeysinghe", "email": "abeysinghe@science.kln.ac.lk"},
            {"client_key": "lect_de_silva", "name": "Dr De Silva", "email": "desilva@science.kln.ac.lk"},
        ],
        "rooms": [
            {
                "client_key": "room_auditorium",
                "name": "Auditorium",
                "capacity": 260,
                "room_type": "lecture",
                "lab_type": None,
                "location": "Faculty Central",
                "year_restriction": None,
            },
            {
                "client_key": "room_a11201",
                "name": "A11 201",
                "capacity": 120,
                "room_type": "lecture",
                "lab_type": None,
                "location": "A11 Complex",
                "year_restriction": None,
            },
            {
                "client_key": "room_b1212",
                "name": "B1 212",
                "capacity": 80,
                "room_type": "lecture",
                "lab_type": None,
                "location": "B1 Complex",
                "year_restriction": None,
            },
            {
                "client_key": "room_chemistry_lab",
                "name": "Chemistry Lab",
                "capacity": 60,
                "room_type": "lab",
                "lab_type": "chemistry",
                "location": "Chemistry Department",
                "year_restriction": None,
            },
            {
                "client_key": "room_physics_lab",
                "name": "Physics Lab 1",
                "capacity": 40,
                "room_type": "lab",
                "lab_type": "physics",
                "location": "Physics Department",
                "year_restriction": 1,
            },
            {
                "client_key": "room_computer_lab",
                "name": "Computer LAB",
                "capacity": 40,
                "room_type": "lab",
                "lab_type": "computer",
                "location": "Statistics and Computer Science",
                "year_restriction": None,
            },
        ],
        "student_groups": [
            {
                "client_key": "group_ps_y1",
                "degree_client_key": "degree_ps",
                "path_client_key": "path_ps_y1_general",
                "year": 1,
                "name": "PS Y1 General",
                "size": 60,
            },
            {
                "client_key": "group_bs_y1",
                "degree_client_key": "degree_bs",
                "path_client_key": "path_bs_y1_general",
                "year": 1,
                "name": "BS Y1 General",
                "size": 60,
            },
            {
                "client_key": "group_encm_y1",
                "degree_client_key": "degree_encm",
                "path_client_key": None,
                "year": 1,
                "name": "ENCM Y1 Direct",
                "size": 30,
            },
            {
                "client_key": "group_apch_y1",
                "degree_client_key": "degree_apch",
                "path_client_key": None,
                "year": 1,
                "name": "APCH Y1 Direct",
                "size": 30,
            },
            {
                "client_key": "group_becs_y1",
                "degree_client_key": "degree_becs",
                "path_client_key": None,
                "year": 1,
                "name": "BECS Y1 Direct",
                "size": 40,
            },
            {
                "client_key": "group_pe_y1",
                "degree_client_key": "degree_pe",
                "path_client_key": None,
                "year": 1,
                "name": "PE Y1 Direct",
                "size": 30,
            },
        ],
        "modules": [
            {"client_key": "mod_aclt11012", "code": "ACLT 11012", "name": "Academic Literacy", "subject_name": "Literacy", "year": 1, "semester": 1, "is_full_year": False},
            {"client_key": "mod_macs11012", "code": "MACS 11012", "name": "Management and Computer Studies", "subject_name": "Management and IT", "year": 1, "semester": 1, "is_full_year": False},
            {"client_key": "mod_amat11012", "code": "AMAT 11012", "name": "Foundations in Applied Maths", "subject_name": "Mathematics", "year": 1, "semester": 1, "is_full_year": False},
            {"client_key": "mod_phys11512", "code": "PHYS 11512", "name": "Mechanics and Properties of Matter", "subject_name": "Physics", "year": 1, "semester": 1, "is_full_year": False},
            {"client_key": "mod_phys11521", "code": "PHYS 11521", "name": "Elementary Physics Laboratory I", "subject_name": "Physics", "year": 1, "semester": 1, "is_full_year": False},
            {"client_key": "mod_chem11612", "code": "CHEM 11612", "name": "Atomic Structure and Periodic Table", "subject_name": "Chemistry", "year": 1, "semester": 1, "is_full_year": False},
            {"client_key": "mod_chem11631", "code": "CHEM 11631", "name": "Basic Chemical Analysis Laboratory", "subject_name": "Chemistry", "year": 1, "semester": 1, "is_full_year": False},
            {"client_key": "mod_becs11223", "code": "BECS 11223", "name": "Fundamentals of Programming", "subject_name": "Computer Science", "year": 1, "semester": 1, "is_full_year": False},
            {"client_key": "mod_becs11224", "code": "BECS 11224", "name": "Programming Laboratory", "subject_name": "Computer Science", "year": 1, "semester": 1, "is_full_year": False},
        ],
        "sessions": [
            {
                "client_key": "sess_aclt11012_lecture",
                "module_client_key": "mod_aclt11012",
                "name": "Academic Literacy Lecture",
                "session_type": "lecture",
                "duration_minutes": 120,
                "occurrences_per_week": 1,
                "required_room_type": "lecture",
                "required_lab_type": None,
                "specific_room_client_key": "room_auditorium",
                "max_students_per_group": None,
                "allow_parallel_rooms": False,
                "notes": None,
                "lecturer_client_keys": ["lect_jayasinghe"],
                "student_group_client_keys": ["group_ps_y1", "group_bs_y1", "group_encm_y1", "group_apch_y1", "group_becs_y1", "group_pe_y1"],
            },
            {
                "client_key": "sess_macs11012_lecture",
                "module_client_key": "mod_macs11012",
                "name": "Management and Computer Studies Lecture",
                "session_type": "lecture",
                "duration_minutes": 120,
                "occurrences_per_week": 1,
                "required_room_type": "lecture",
                "required_lab_type": None,
                "specific_room_client_key": "room_auditorium",
                "max_students_per_group": None,
                "allow_parallel_rooms": False,
                "notes": None,
                "lecturer_client_keys": ["lect_ranasinghe"],
                "student_group_client_keys": ["group_ps_y1", "group_bs_y1", "group_becs_y1", "group_pe_y1"],
            },
            {
                "client_key": "sess_amat11012_lecture",
                "module_client_key": "mod_amat11012",
                "name": "Applied Maths Lecture",
                "session_type": "lecture",
                "duration_minutes": 120,
                "occurrences_per_week": 2,
                "required_room_type": "lecture",
                "required_lab_type": None,
                "specific_room_client_key": "room_auditorium",
                "max_students_per_group": None,
                "allow_parallel_rooms": False,
                "notes": None,
                "lecturer_client_keys": ["lect_wijesinghe"],
                "student_group_client_keys": ["group_ps_y1", "group_pe_y1"],
            },
            {
                "client_key": "sess_phys11512_lecture",
                "module_client_key": "mod_phys11512",
                "name": "Mechanics and Matter Lecture",
                "session_type": "lecture",
                "duration_minutes": 120,
                "occurrences_per_week": 2,
                "required_room_type": "lecture",
                "required_lab_type": None,
                "specific_room_client_key": "room_auditorium",
                "max_students_per_group": None,
                "allow_parallel_rooms": False,
                "notes": None,
                "lecturer_client_keys": ["lect_fernando"],
                "student_group_client_keys": ["group_ps_y1", "group_pe_y1"],
            },
            {
                "client_key": "sess_phys11521_lab",
                "module_client_key": "mod_phys11521",
                "name": "Elementary Physics Lab",
                "session_type": "lab",
                "duration_minutes": 180,
                "occurrences_per_week": 1,
                "required_room_type": "lab",
                "required_lab_type": "physics",
                "specific_room_client_key": "room_physics_lab",
                "max_students_per_group": 40,
                "allow_parallel_rooms": False,
                "notes": None,
                "lecturer_client_keys": ["lect_fernando", "lect_abeysinghe"],
                "student_group_client_keys": ["group_ps_y1", "group_pe_y1"],
            },
            {
                "client_key": "sess_chem11612_lecture",
                "module_client_key": "mod_chem11612",
                "name": "Atomic Structure Lecture",
                "session_type": "lecture",
                "duration_minutes": 120,
                "occurrences_per_week": 2,
                "required_room_type": "lecture",
                "required_lab_type": None,
                "specific_room_client_key": "room_a11201",
                "max_students_per_group": None,
                "allow_parallel_rooms": False,
                "notes": None,
                "lecturer_client_keys": ["lect_perera"],
                "student_group_client_keys": ["group_bs_y1", "group_apch_y1", "group_encm_y1"],
            },
            {
                "client_key": "sess_chem11631_lab",
                "module_client_key": "mod_chem11631",
                "name": "Basic Chemical Analysis Lab",
                "session_type": "lab",
                "duration_minutes": 180,
                "occurrences_per_week": 1,
                "required_room_type": "lab",
                "required_lab_type": "chemistry",
                "specific_room_client_key": "room_chemistry_lab",
                "max_students_per_group": 60,
                "allow_parallel_rooms": False,
                "notes": None,
                "lecturer_client_keys": ["lect_perera"],
                "student_group_client_keys": ["group_bs_y1", "group_apch_y1"],
            },
            {
                "client_key": "sess_becs11223_lecture",
                "module_client_key": "mod_becs11223",
                "name": "Fundamentals of Programming Lecture",
                "session_type": "lecture",
                "duration_minutes": 120,
                "occurrences_per_week": 2,
                "required_room_type": "lecture",
                "required_lab_type": None,
                "specific_room_client_key": "room_b1212",
                "max_students_per_group": None,
                "allow_parallel_rooms": False,
                "notes": None,
                "lecturer_client_keys": ["lect_de_silva"],
                "student_group_client_keys": ["group_becs_y1"],
            },
            {
                "client_key": "sess_becs11224_lab",
                "module_client_key": "mod_becs11224",
                "name": "Programming Lab",
                "session_type": "lab",
                "duration_minutes": 180,
                "occurrences_per_week": 1,
                "required_room_type": "lab",
                "required_lab_type": "computer",
                "specific_room_client_key": "room_computer_lab",
                "max_students_per_group": 40,
                "allow_parallel_rooms": False,
                "notes": None,
                "lecturer_client_keys": ["lect_de_silva"],
                "student_group_client_keys": ["group_becs_y1"],
            },
        ],
    }


def build_demo_dataset(profile: str = "realistic") -> dict:
    if profile == "tuned":
        return build_tuned_demo_dataset()
    try:
        return build_realistic_demo_dataset_from_enrollment_csv()
    except Exception:
        return build_legacy_realistic_demo_dataset()
