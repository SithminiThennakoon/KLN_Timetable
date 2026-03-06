from __future__ import annotations

import base64
import csv
import io
import itertools
import json
from collections import defaultdict
from dataclasses import dataclass
from typing import Iterable

from ortools.sat.python import cp_model
from sqlalchemy.orm import Session, joinedload

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

DAY_ORDER = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
DAY_INDEX = {day: idx for idx, day in enumerate(DAY_ORDER)}
START_MINUTE = 8 * 60
END_MINUTE = 18 * 60
LUNCH_START = 12 * 60
LUNCH_END = 13 * 60
SOFT_CONSTRAINTS = {
    "spread_sessions_across_days": SoftConstraintOption(
        key="spread_sessions_across_days",
        label="Spread repeated sessions across different days",
        description="Modules with multiple weekly sessions should be spread across different days when possible.",
    )
}


@dataclass(frozen=True)
class SplitAssignment:
    split_index: int
    student_group_ids: tuple[int, ...]
    student_count: int


@dataclass(frozen=True)
class SessionTask:
    session_id: int
    session_name: str
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
    student_count: int
    root_session_id: int


def list_soft_constraint_options() -> list[SoftConstraintOption]:
    return list(SOFT_CONSTRAINTS.values())


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
            SplitAssignment(split_index=1, student_group_ids=tuple(), student_count=0)
        ]

    total = sum(int(group.size) for group in groups)
    limit = session.max_students_per_group
    if not limit or total <= limit:
        return [
            SplitAssignment(
                split_index=1,
                student_group_ids=tuple(int(group.id) for group in groups),
                student_count=total,
            )
        ]

    assignments: list[SplitAssignment] = []
    current_ids: list[int] = []
    current_total = 0
    split_index = 1
    for group in groups:
        size = int(group.size)
        if current_ids and current_total + size > limit:
            assignments.append(
                SplitAssignment(
                    split_index=split_index,
                    student_group_ids=tuple(current_ids),
                    student_count=current_total,
                )
            )
            split_index += 1
            current_ids = []
            current_total = 0
        current_ids.append(int(group.id))
        current_total += size

    if current_ids:
        assignments.append(
            SplitAssignment(
                split_index=split_index,
                student_group_ids=tuple(current_ids),
                student_count=current_total,
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
        for occurrence_index in range(1, int(session.occurrences_per_week) + 1):
            for split in split_assignments:
                tasks.append(
                    SessionTask(
                        session_id=int(session.id),
                        session_name=session.name,
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
                        lecturer_ids=lecturer_ids,
                        student_group_ids=split.student_group_ids,
                        student_count=split.student_count,
                        root_session_id=int(session.id),
                    )
                )
    return tasks


def _room_matches(room: V2Room, task: SessionTask) -> bool:
    if room.capacity < task.student_count:
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
    for day in DAY_ORDER:
        minute = START_MINUTE
        while minute + task.duration_minutes <= END_MINUTE:
            if _is_timeslot_valid(minute, task.duration_minutes):
                starts.append((day, minute))
            minute += 30
    return starts


def _overlap(start_a: int, duration_a: int, start_b: int, duration_b: int) -> bool:
    end_a = start_a + duration_a
    end_b = start_b + duration_b
    return start_a < end_b and start_b < end_a


def _all_soft_constraint_combinations() -> list[list[str]]:
    keys = sorted(SOFT_CONSTRAINTS.keys())
    combinations: list[list[str]] = []
    for length in range(1, len(keys) + 1):
        for combo in itertools.combinations(keys, length):
            combinations.append(list(combo))
    return combinations


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


def _solve_internal(
    db: Session,
    selected_soft_constraints: list[str],
    max_solutions: int,
    time_limit_seconds: int,
) -> dict:
    tasks = _build_tasks(db)
    rooms = db.query(V2Room).order_by(V2Room.id).all()
    if not tasks:
        return {
            "status": "empty",
            "message": "Enter session data before generating a timetable.",
            "solutions": [],
            "truncated": False,
            "tasks": tasks,
        }
    if not rooms:
        return {
            "status": "infeasible",
            "message": "No rooms available for timetable generation.",
            "solutions": [],
            "truncated": False,
            "tasks": tasks,
        }

    model = cp_model.CpModel()
    assignment_vars: dict[tuple[int, int, str, int], cp_model.IntVar] = {}
    room_lookup = {int(room.id): room for room in rooms}
    room_ids = [int(room.id) for room in rooms]

    candidates_by_task: dict[int, list[tuple[int, str, int]]] = defaultdict(list)
    for task_index, task in enumerate(tasks):
        starts = _candidate_starts(task)
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
        }

    for task_index in range(len(tasks)):
        vars_for_task = [
            assignment_vars[(task_index, room_id, day, start_minute)]
            for room_id, day, start_minute in candidates_by_task[task_index]
        ]
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
                        student_blockers[student_group_id].append(var)
            for vars_for_lecturer in lecturer_blockers.values():
                if vars_for_lecturer:
                    model.Add(sum(vars_for_lecturer) <= 1)
            for vars_for_group in student_blockers.values():
                if vars_for_group:
                    model.Add(sum(vars_for_group) <= 1)

    if "spread_sessions_across_days" in selected_soft_constraints:
        grouped_occurrences: dict[int, dict[str, list[cp_model.IntVar]]] = defaultdict(
            lambda: defaultdict(list)
        )
        for task_index, task in enumerate(tasks):
            for room_id, day, start_minute in candidates_by_task[task_index]:
                grouped_occurrences[task.root_session_id][day].append(
                    assignment_vars[(task_index, room_id, day, start_minute)]
                )
        for root_session_id, by_day in grouped_occurrences.items():
            tasks_for_root = [
                task for task in tasks if task.root_session_id == root_session_id
            ]
            occurrence_count = max(
                (task.occurrence_index for task in tasks_for_root), default=1
            )
            if occurrence_count <= 1:
                continue
            for vars_for_day in by_day.values():
                if vars_for_day:
                    model.Add(sum(vars_for_day) <= 1)

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = float(time_limit_seconds)
    solver.parameters.enumerate_all_solutions = True
    solver.parameters.num_search_workers = 1

    collector = _SolutionCollector(assignment_vars, max_solutions)
    status = solver.SearchForAllSolutions(model, collector)

    status_name = "feasible" if collector.solutions else "infeasible"
    if status == cp_model.OPTIMAL and collector.solutions:
        status_name = "optimal"
    elif status == cp_model.FEASIBLE and collector.solutions:
        status_name = "feasible"

    message = "Generated timetable solutions."
    if not collector.solutions:
        message = "No possible timetables satisfy the selected constraints."
    elif collector.truncated:
        message = "Too many possible timetables to enumerate fully within the configured limit."

    return {
        "status": status_name,
        "message": message,
        "solutions": collector.solutions,
        "truncated": collector.truncated,
        "tasks": tasks,
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


def generate_timetables(
    db: Session,
    selected_soft_constraints: Iterable[str],
    max_solutions: int,
    preview_limit: int,
    time_limit_seconds: int,
) -> V2GenerationRun:
    selected_soft_constraints = list(selected_soft_constraints)
    result = _solve_internal(
        db, selected_soft_constraints, max_solutions, time_limit_seconds
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
            db.add(
                V2SolutionEntry(
                    solution_id=int(solution_row.id),
                    session_id=entry["session_id"],
                    occurrence_index=entry["occurrence_index"],
                    split_index=entry["split_index"],
                    room_id=entry["room_id"],
                    day=entry["day"],
                    start_minute=entry["start_minute"],
                    duration_minutes=entry["duration_minutes"],
                )
            )

    if result["status"] == "infeasible" and selected_soft_constraints:
        possible_combinations = []
        for combo in _all_soft_constraint_combinations():
            combo_result = _solve_internal(db, combo, 1, min(time_limit_seconds, 15))
            if combo_result["solutions"]:
                possible_combinations.append(combo)
        if possible_combinations:
            run.message = (
                "Selected nice-to-have constraints cannot be satisfied together."
            )
            run.possible_soft_constraint_combinations = json.dumps(
                possible_combinations
            )

    db.commit()
    db.refresh(run)
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
        degree_path_labels = []
        total_students = 0
        group_names = []
        for group in session.student_groups:
            degree_name = group.degree.code
            path_name = group.path.code if group.path else "General"
            degree_path_labels.append(f"{degree_name} Y{group.year} {path_name}")
            total_students += int(group.size)
            group_names.append(group.name)
        payload.append(
            {
                "session_id": int(entry.session_id),
                "session_name": session.name,
                "module_code": module.code,
                "module_name": module.name,
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
    combos = json.loads(run.possible_soft_constraint_combinations or "[]")
    selected = [item for item in run.selected_soft_constraints.split(",") if item]
    return {
        "generation_run_id": int(run.id),
        "status": run.status,
        "message": run.message or "",
        "counts": {
            "total_solutions_found": int(run.total_solutions_found),
            "preview_solution_count": len(run.solutions),
            "truncated": bool(run.truncated),
        },
        "selected_soft_constraints": selected,
        "available_soft_constraints": list_soft_constraint_options(),
        "possible_soft_constraint_combinations": combos,
        "solutions": [
            serialize_solution(solution)
            for solution in sorted(run.solutions, key=lambda item: item.ordinal)
        ],
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


def build_view_payload(
    db: Session,
    mode: str,
    lecturer_id: int | None = None,
    student_group_id: int | None = None,
) -> dict:
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
        group = (
            db.query(V2StudentGroup)
            .filter(V2StudentGroup.id == student_group_id)
            .first()
        )
        if not group:
            raise ValueError("Student group not found")
        entries = [
            entry for entry in entries if group.name in entry["student_group_names"]
        ]
        title = f"Student Timetable - {group.name}"
        subtitle = "Sessions attended by the selected degree/path group."
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


def lookup_options(db: Session) -> dict:
    lecturers = db.query(V2Lecturer).order_by(V2Lecturer.name).all()
    student_groups = db.query(V2StudentGroup).order_by(V2StudentGroup.name).all()
    return {
        "lecturers": [{"id": int(item.id), "label": item.name} for item in lecturers],
        "student_groups": [
            {"id": int(item.id), "label": item.name} for item in student_groups
        ],
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


def build_demo_dataset() -> dict:
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
        ],
        "paths": [
            {
                "client_key": "path_ps_phy_math_stat",
                "degree_client_key": "degree_ps",
                "year": 1,
                "code": "PHY-MATH-STAT",
                "name": "Physics, Mathematics, Statistics",
            },
            {
                "client_key": "path_bs_zoo_chem_micro",
                "degree_client_key": "degree_bs",
                "year": 1,
                "code": "ZOO-CHEM-MICRO",
                "name": "Zoology, Chemistry, Microbiology",
            },
        ],
        "lecturers": [
            {
                "client_key": "lect_fernando",
                "name": "Dr Fernando",
                "email": "fernando@example.com",
            },
            {
                "client_key": "lect_perera",
                "name": "Dr Perera",
                "email": "perera@example.com",
            },
            {
                "client_key": "lect_silva",
                "name": "Dr Silva",
                "email": "silva@example.com",
            },
        ],
        "rooms": [
            {
                "client_key": "room_a7301",
                "name": "A7 301",
                "capacity": 120,
                "room_type": "lecture",
                "lab_type": None,
                "location": "A7 Building",
                "year_restriction": None,
            },
            {
                "client_key": "room_phy_lab_1",
                "name": "Physics Lab 1",
                "capacity": 40,
                "room_type": "lab",
                "lab_type": "physics_lab",
                "location": "Physics Wing",
                "year_restriction": 1,
            },
            {
                "client_key": "room_chem_lab_1",
                "name": "Chemistry Lab 1",
                "capacity": 40,
                "room_type": "lab",
                "lab_type": "chemistry_lab",
                "location": "Chemistry Wing",
                "year_restriction": None,
            },
        ],
        "student_groups": [
            {
                "client_key": "group_ps_y1_main",
                "degree_client_key": "degree_ps",
                "path_client_key": "path_ps_phy_math_stat",
                "year": 1,
                "name": "PS Y1 Physics-Mathematics-Statistics",
                "size": 80,
            },
            {
                "client_key": "group_bs_y1_main",
                "degree_client_key": "degree_bs",
                "path_client_key": "path_bs_zoo_chem_micro",
                "year": 1,
                "name": "BS Y1 Zoology-Chemistry-Microbiology",
                "size": 60,
            },
        ],
        "modules": [
            {
                "client_key": "mod_phys101",
                "code": "PHYS101",
                "name": "Mechanics",
                "subject_name": "Physics",
                "year": 1,
                "semester": 1,
                "is_full_year": False,
            },
            {
                "client_key": "mod_chem101",
                "code": "CHEM101",
                "name": "Foundations of Chemistry",
                "subject_name": "Chemistry",
                "year": 1,
                "semester": 1,
                "is_full_year": False,
            },
            {
                "client_key": "mod_stat101",
                "code": "STAT101",
                "name": "Statistics I",
                "subject_name": "Statistics",
                "year": 1,
                "semester": 1,
                "is_full_year": False,
            },
        ],
        "sessions": [
            {
                "client_key": "sess_phys101_lec",
                "module_client_key": "mod_phys101",
                "name": "Mechanics Lecture",
                "session_type": "lecture",
                "duration_minutes": 60,
                "occurrences_per_week": 2,
                "required_room_type": "lecture",
                "required_lab_type": None,
                "specific_room_client_key": None,
                "max_students_per_group": None,
                "allow_parallel_rooms": False,
                "notes": None,
                "lecturer_client_keys": ["lect_fernando"],
                "student_group_client_keys": ["group_ps_y1_main"],
            },
            {
                "client_key": "sess_chem101_lec",
                "module_client_key": "mod_chem101",
                "name": "Chemistry Lecture",
                "session_type": "lecture",
                "duration_minutes": 60,
                "occurrences_per_week": 2,
                "required_room_type": "lecture",
                "required_lab_type": None,
                "specific_room_client_key": None,
                "max_students_per_group": None,
                "allow_parallel_rooms": False,
                "notes": "Shared chemistry lecture across degrees.",
                "lecturer_client_keys": ["lect_perera"],
                "student_group_client_keys": ["group_ps_y1_main", "group_bs_y1_main"],
            },
            {
                "client_key": "sess_chem101_lab",
                "module_client_key": "mod_chem101",
                "name": "Chemistry Lab",
                "session_type": "practical",
                "duration_minutes": 180,
                "occurrences_per_week": 1,
                "required_room_type": "lab",
                "required_lab_type": "chemistry_lab",
                "specific_room_client_key": "room_chem_lab_1",
                "max_students_per_group": 40,
                "allow_parallel_rooms": False,
                "notes": None,
                "lecturer_client_keys": ["lect_perera", "lect_silva"],
                "student_group_client_keys": ["group_bs_y1_main"],
            },
            {
                "client_key": "sess_stat101_lec",
                "module_client_key": "mod_stat101",
                "name": "Statistics Lecture",
                "session_type": "lecture",
                "duration_minutes": 60,
                "occurrences_per_week": 2,
                "required_room_type": "lecture",
                "required_lab_type": None,
                "specific_room_client_key": None,
                "max_students_per_group": None,
                "allow_parallel_rooms": False,
                "notes": None,
                "lecturer_client_keys": ["lect_silva"],
                "student_group_client_keys": ["group_ps_y1_main"],
            },
        ],
    }
