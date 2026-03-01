from __future__ import annotations

from dataclasses import dataclass
from math import ceil
from typing import Dict, List, Tuple, cast

from ortools.sat.python import cp_model
from sqlalchemy.orm import Session

from app.models.module import Module
from app.models.pathway import Pathway
from app.models.room import Room
from app.models.session import Session as SessionModel
from app.models.timeslot import Timeslot

# Silence SQLAlchemy type checker warnings for runtime attributes
# This avoids treating ORM columns as Column[...] at type-check time.
# It does not affect runtime behavior.
# type: ignore


@dataclass(frozen=True)
class ExpandedSession:
    session_id: int
    module_id: int
    session_type: str
    duration_hours: int
    frequency_per_week: int
    requires_lab_type: str | None
    student_count: int
    max_students_per_group: int | None
    concurrent_split: bool
    lecturer_ids: tuple[int, ...]
    year: int
    pathway_ids: tuple[int, ...]
    group_number: int
    group_size: int


def _build_pathway_map(db: Session) -> Dict[int, tuple[int, ...]]:
    pathways = db.query(Pathway).all()
    module_to_pathways: Dict[int, List[int]] = {}
    for pathway in pathways:
        subject_ids = [cast(int, subject.id) for subject in pathway.subjects]
        if not subject_ids:
            continue
        modules = db.query(Module).filter(Module.subject_id.in_(subject_ids), Module.year == pathway.year).all()
        for module in modules:
            module_to_pathways.setdefault(cast(int, module.id), []).append(cast(int, pathway.id))
    return {module_id: tuple(sorted(ids)) for module_id, ids in module_to_pathways.items()}


def _expand_sessions(db: Session) -> List[ExpandedSession]:
    module_pathways = _build_pathway_map(db)
    sessions = db.query(SessionModel).all()
    expanded: List[ExpandedSession] = []
    for session in sessions:
        lecturer_ids = tuple(sorted([cast(int, lecturer.id) for lecturer in session.lecturers]))
        module = session.module
        pathway_ids = module_pathways.get(cast(int, module.id), tuple())
        student_count = int(cast(int, session.student_count))
        max_students = cast(int | None, session.max_students_per_group)
        if max_students is not None and student_count > max_students:
            group_count = int(ceil(float(student_count) / float(max_students)))
            group_size = int(ceil(float(student_count) / float(group_count)))
            for idx in range(group_count):
                expanded.append(
                    ExpandedSession(
                        session_id=cast(int, session.id),
                        module_id=cast(int, session.module_id),
                        session_type=cast(str, session.session_type),
                        duration_hours=cast(int, session.duration_hours),
                        frequency_per_week=cast(int, session.frequency_per_week),
                        requires_lab_type=cast(str | None, session.requires_lab_type),
                        student_count=student_count,
                        max_students_per_group=max_students,
                        concurrent_split=cast(bool, session.concurrent_split),
                        lecturer_ids=lecturer_ids,
                        year=cast(int, module.year),
                        pathway_ids=pathway_ids,
                        group_number=idx + 1,
                        group_size=group_size,
                    )
                )
        else:
            expanded.append(
                ExpandedSession(
                    session_id=cast(int, session.id),
                    module_id=cast(int, session.module_id),
                    session_type=cast(str, session.session_type),
                    duration_hours=cast(int, session.duration_hours),
                    frequency_per_week=cast(int, session.frequency_per_week),
                    requires_lab_type=cast(str | None, session.requires_lab_type),
                    student_count=student_count,
                    max_students_per_group=max_students,
                    concurrent_split=cast(bool, session.concurrent_split),
                    lecturer_ids=lecturer_ids,
                    year=cast(int, module.year),
                    pathway_ids=pathway_ids,
                    group_number=1,
                    group_size=student_count,
                )
            )
    return expanded


def _valid_room_for_session(room: Room, session: ExpandedSession) -> bool:
    capacity = cast(int, room.capacity)
    room_type = cast(str, room.room_type)
    lab_type = cast(str | None, room.lab_type)
    year_restriction = cast(int | None, room.year_restriction)
    if capacity < session.group_size:
        return False
    if session.session_type == "lecture" and room_type != "lecture_hall":
        return False
    if session.session_type == "practical" and room_type != "laboratory":
        return False
    if session.requires_lab_type and lab_type != session.requires_lab_type:
        return False
    if year_restriction is not None and year_restriction != session.year:
        return False
    return True


def solve_timetable(
    db: Session,
    fixed_entries: list[tuple[int, int, int, int]] | None = None,
) -> tuple[str, list[tuple[int, int, int, int]], list[str]]:
    rooms = db.query(Room).all()
    timeslots = db.query(Timeslot).all()

    ordered_timeslots = list(timeslots)
    sessions = _expand_sessions(db)

    model = cp_model.CpModel()  # type: ignore[attr-defined]
    diagnostics: list[str] = []
    x: Dict[tuple[int, int, int, int], cp_model.IntVar] = {}

    for s_idx, session in enumerate(sessions):
        for r_idx, room in enumerate(rooms):
            if not _valid_room_for_session(room, session):
                continue
            for t_idx, ts in enumerate(ordered_timeslots):
                if bool(ts.is_lunch):
                    continue
                x[(s_idx, r_idx, t_idx, session.group_number)] = model.NewBoolVar(  # type: ignore[attr-defined]
                    f"x_s{s_idx}_r{r_idx}_t{t_idx}_g{session.group_number}"
                )

    for s_idx, session in enumerate(sessions):
        vars_for_session = [
            var
            for (si, _, _, _), var in x.items()
            if si == s_idx
        ]
        if not vars_for_session:
            diagnostics.append(
                f"Session {session.session_id} group {session.group_number} has no feasible room/timeslot options"
            )
        if session.frequency_per_week > 1:
            diagnostics.append(
                f"Session {session.session_id} group {session.group_number} frequency_per_week={session.frequency_per_week} not supported yet"
            )
        if session.duration_hours > 1:
            diagnostics.append(
                f"Session {session.session_id} group {session.group_number} duration_hours={session.duration_hours} not supported yet"
            )
        model.Add(sum(vars_for_session) == session.frequency_per_week)  # type: ignore[attr-defined]

    slot_per_day = 10

    for r_idx, _room in enumerate(rooms):
        for t_idx, _ts in enumerate(ordered_timeslots):
            vars_for_room_slot = [
                x[(s_idx, r_idx, t_idx, sessions[s_idx].group_number)]
                for s_idx in range(len(sessions))
                if (s_idx, r_idx, t_idx, sessions[s_idx].group_number) in x
            ]
            if vars_for_room_slot:
                model.Add(sum(vars_for_room_slot) <= 1)  # type: ignore[attr-defined]

    lecturer_to_sessions: Dict[int, List[int]] = {}
    for s_idx, session in enumerate(sessions):
        for lecturer_id in session.lecturer_ids:
            lecturer_to_sessions.setdefault(lecturer_id, []).append(s_idx)

    for t_idx, _ts in enumerate(ordered_timeslots):
        for session_indices in lecturer_to_sessions.values():
            vars_for_lecturer = [
                x[(s_idx, r_idx, t_idx, sessions[s_idx].group_number)]
                for s_idx in session_indices
                for r_idx in range(len(rooms))
                if (s_idx, r_idx, t_idx, sessions[s_idx].group_number) in x
            ]
            if vars_for_lecturer:
                model.Add(sum(vars_for_lecturer) <= 1)  # type: ignore[attr-defined]

    pathway_to_sessions: Dict[int, List[int]] = {}
    for s_idx, session in enumerate(sessions):
        for pathway_id in session.pathway_ids:
            pathway_to_sessions.setdefault(pathway_id, []).append(s_idx)

    for t_idx, _ts in enumerate(ordered_timeslots):
        for session_indices in pathway_to_sessions.values():
            vars_for_pathway = [
                x[(s_idx, r_idx, t_idx, sessions[s_idx].group_number)]
                for s_idx in session_indices
                for r_idx in range(len(rooms))
                if (s_idx, r_idx, t_idx, sessions[s_idx].group_number) in x
            ]
            if vars_for_pathway:
                model.Add(sum(vars_for_pathway) <= 1)  # type: ignore[attr-defined]

    seen_sessions: set[int] = set()
    for s_idx, session in enumerate(sessions):
        if not session.concurrent_split or session.session_id in seen_sessions:
            continue
        related = [
            (idx, sess)
            for idx, sess in enumerate(sessions)
            if sess.session_id == session.session_id
        ]
        if len(related) > 1:
            seen_sessions.add(session.session_id)
            for t_idx, _ts in enumerate(ordered_timeslots):
                for (idx_a, sess_a) in related:
                    vars_a = [
                        x[(idx_a, r_idx, t_idx, sess_a.group_number)]
                        for r_idx in range(len(rooms))
                        if (idx_a, r_idx, t_idx, sess_a.group_number) in x
                    ]
                    for (idx_b, sess_b) in related:
                        if idx_a >= idx_b:
                            continue
                        vars_b = [
                            x[(idx_b, r_idx, t_idx, sess_b.group_number)]
                            for r_idx in range(len(rooms))
                            if (idx_b, r_idx, t_idx, sess_b.group_number) in x
                        ]
                        if vars_a and vars_b:
                            model.Add(sum(vars_a) == sum(vars_b))  # type: ignore[attr-defined]

    for s_idx, session in enumerate(sessions):
        for t_idx, _ts in enumerate(ordered_timeslots):
            vars_for_time = [
                x[(s_idx, r_idx, t_idx, session.group_number)]
                for r_idx in range(len(rooms))
                if (s_idx, r_idx, t_idx, session.group_number) in x
            ]
            if vars_for_time:
                model.Add(sum(vars_for_time) <= 1)  # type: ignore[attr-defined]

    if fixed_entries:
        room_index = {cast(int, room.id): idx for idx, room in enumerate(rooms)}
        timeslot_index = {cast(int, ts.id): idx for idx, ts in enumerate(ordered_timeslots)}
        for session_id, room_id, timeslot_id, group_number in fixed_entries:
            try:
                s_idx = next(
                    idx
                    for idx, sess in enumerate(sessions)
                    if sess.session_id == session_id and sess.group_number == group_number
                )
            except StopIteration:
                continue
            if room_id not in room_index or timeslot_id not in timeslot_index:
                continue
            r_idx = room_index[int(room_id)]
            t_idx = timeslot_index[int(timeslot_id)]
            if (s_idx, r_idx, t_idx, group_number) in x:
                model.Add(x[(s_idx, r_idx, t_idx, group_number)] == 1)  # type: ignore[attr-defined]

    if x:
        model.Maximize(sum(x.values()))  # type: ignore[attr-defined]
    else:
        diagnostics.append("No decision variables created; check rooms and timeslots")

    solver = cp_model.CpSolver()
    status = solver.Solve(model)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return "infeasible", [], diagnostics

    results: list[tuple[int, int, int, int]] = []
    for (s_idx, r_idx, t_idx, group_number), var in x.items():
        if solver.Value(var) == 1:
            results.append((s_idx, r_idx, t_idx, group_number))

    return "optimal" if status == cp_model.OPTIMAL else "feasible", results, diagnostics
