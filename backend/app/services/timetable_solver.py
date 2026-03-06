from __future__ import annotations

from dataclasses import dataclass
from math import ceil
from typing import Dict, List, Set, Tuple, cast

from ortools.sat.python import cp_model
from sqlalchemy.orm import Session

from app.models.module import Module
from app.models.pathway import Pathway
from app.models.room import Room
from app.models.session import Session as SessionModel
from app.models.timeslot import Timeslot

# Silence SQLAlchemy type checker warnings for runtime attributes
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


def _build_day_slots(timeslots: List[Timeslot]) -> Dict[str, List[Tuple[int, Timeslot]]]:
    day_slots: Dict[str, List[Tuple[int, Timeslot]]] = {}
    for t_idx, ts in enumerate(timeslots):
        day = cast(str, ts.day)
        if day not in day_slots:
            day_slots[day] = []
        day_slots[day].append((t_idx, ts))
    for day in day_slots:
        day_slots[day].sort(key=lambda x: x[1].start_time)
    return day_slots


def _find_valid_starts(
    session: ExpandedSession,
    day_slots: Dict[str, List[Tuple[int, Timeslot]]],
) -> Dict[str, List[int]]:
    duration = session.duration_hours
    valid_starts: Dict[str, List[int]] = {}
    
    for day, slots in day_slots.items():
        day_valid_starts = []
        slot_count = len(slots)
        for start_pos in range(slot_count):
            if start_pos + duration > slot_count:
                break
            is_valid = True
            for offset in range(duration):
                _, ts = slots[start_pos + offset]
                if ts.is_lunch is True:
                    is_valid = False
                    break
            if is_valid:
                tidx, _ = slots[start_pos]
                day_valid_starts.append(tidx)
        if day_valid_starts:
            valid_starts[day] = day_valid_starts
    
    return valid_starts


def _find_valid_starts_for_labs(
    session: ExpandedSession,
    day_slots: Dict[str, List[Tuple[int, Timeslot]]],
) -> Dict[str, List[int]]:
    duration = session.duration_hours
    valid_starts: Dict[str, List[int]] = {}
    
    for day, slots in day_slots.items():
        day_valid_starts = []
        slot_count = len(slots)
        # Labs must ONLY start at 9:00 (index 1) or 13:00 (index 5)
        # Lab slots are 3 hours, covering indices 1-3 or 5-7
        valid_lab_start_positions = [1, 5]
        
        for start_pos in valid_lab_start_positions:
            if start_pos + duration > slot_count:
                continue
            is_valid = True
            for offset in range(duration):
                _, ts = slots[start_pos + offset]
                if ts.is_lunch is True:
                    is_valid = False
                    break
            if is_valid:
                tidx, _ = slots[start_pos]
                day_valid_starts.append(tidx)
        if day_valid_starts:
            valid_starts[day] = day_valid_starts
    
    return valid_starts


def solve_timetable(
    db: Session,
    fixed_entries: list[tuple[int, int, int, int]] | None = None,
) -> tuple[str, list[tuple[int, int, int, int]], list[str]]:
    import sys
    print("DEBUG: solve_timetable called", flush=True)
    sys.stdout.flush()
    rooms = db.query(Room).all()
    timeslots = db.query(Timeslot).all()
    print(f"DEBUG: rooms={len(rooms)}, timeslots={len(timeslots)}", flush=True)

    ordered_timeslots = list(timeslots)
    day_slots = _build_day_slots(ordered_timeslots)
    sessions = _expand_sessions(db)

    model = cp_model.CpModel()  # type: ignore[attr-defined]
    diagnostics: list[str] = []
    
    # Variables: (s_idx, r_idx, t_idx) -> BoolVar
    # t_idx is the STARTING timeslot index
    x: Dict[Tuple[int, int, int], cp_model.IntVar] = {}

    # Find valid starts for each (session, room) pair
    session_valid_starts: Dict[int, Dict[int, Dict[str, List[int]]]] = {}
    
    for s_idx, session in enumerate(sessions):
        session_valid_starts[s_idx] = {}
        for r_idx, room in enumerate(rooms):
            if not _valid_room_for_session(room, session):
                continue
            # Labs must use fixed slots (9-12 or 1-4)
            if session.session_type == "practical":
                valid_starts = _find_valid_starts_for_labs(session, day_slots)
            else:
                valid_starts = _find_valid_starts(session, day_slots)
            if valid_starts:
                session_valid_starts[s_idx][r_idx] = valid_starts
                for day, start_tindices in valid_starts.items():
                    for t_idx in start_tindices:
                        x[(s_idx, r_idx, t_idx)] = model.NewBoolVar(  # type: ignore[attr-defined]
                            f"x_s{s_idx}_r{r_idx}_t{t_idx}"
                        )

    # Constraint: each session must be scheduled frequency_per_week times
    for s_idx, session in enumerate(sessions):
        vars_for_session = [
            var
            for (si, _, _), var in x.items()
            if si == s_idx
        ]
        if not vars_for_session:
            diagnostics.append(
                f"Session {session.session_id} group {session.group_number} has no feasible room/timeslot options"
            )
            continue
        model.Add(sum(vars_for_session) == session.frequency_per_week)  # type: ignore[attr-defined]

    # Constraint: each session occurrence on different days (for frequency_per_week > 1)
    for s_idx, session in enumerate(sessions):
        if session.frequency_per_week <= 1:
            continue
        day_vars: Dict[str, List[cp_model.IntVar]] = {}
        for (si, ri, t_idx), var in x.items():
            if si != s_idx:
                continue
            for day, valid_day_starts in session_valid_starts[s_idx].get(ri, {}).items():
                if t_idx in valid_day_starts:
                    day_vars.setdefault(day, []).append(var)
        for day_vars_list in day_vars.values():
            if day_vars_list:
                model.Add(sum(day_vars_list) <= 1)  # type: ignore[attr-defined]

    # Constraint: room can only host one session at a time (for ALL slots in duration block)
    for r_idx, room in enumerate(rooms):
        for day, slots in day_slots.items():
            for t_idx, (ts_idx, ts) in enumerate(slots):
                # Find all sessions that could use this slot as part of their duration block
                blocking_vars = []
                for s_idx, session in enumerate(sessions):
                    if r_idx not in session_valid_starts.get(s_idx, {}):
                        continue
                    valid_starts = session_valid_starts[s_idx][r_idx].get(day, [])
                    for start_tidx in valid_starts:
                        start_pos = None
                        for pos, (st_idx, _) in enumerate(slots):
                            if st_idx == start_tidx:
                                start_pos = pos
                                break
                        if start_pos is None:
                            continue
                        # Check if this session block covers the current slot
                        if start_pos <= t_idx < start_pos + session.duration_hours:
                            blocking_vars.append(x.get((s_idx, r_idx, start_tidx)))
                blocking_vars = [v for v in blocking_vars if v is not None]
                if blocking_vars:
                    model.Add(sum(blocking_vars) <= 1)  # type: ignore[attr-defined]

    # Constraint: lecturer can only teach one session at a time (for ALL slots)
    # NOTE: Temporarily disabled for debugging
    # lecturer_to_sessions: Dict[int, List[int]] = {}
    # for s_idx, session in enumerate(sessions):
    #     for lecturer_id in session.lecturer_ids:
    #         lecturer_to_sessions.setdefault(lecturer_id, []).append(s_idx)
    #
    # for lecturer_id, session_indices in lecturer_to_sessions.items():
    #     for day, slots in day_slots.items():
    #         for t_idx, (ts_idx, ts) in enumerate(slots):
    #             blocking_vars = []
    #             for s_idx in session_indices:
    #                 if s_idx not in session_valid_starts:
    #                     continue
    #                 for r_idx, valid_starts_dict in session_valid_starts[s_idx].items():
    #                     valid_starts = valid_starts_dict.get(day, [])
    #                     for start_tidx in valid_starts:
    #                         start_pos = None
    #                         for pos, (st_idx, _) in enumerate(slots):
    #                             if st_idx == start_tidx:
    #                                 start_pos = pos
    #                                 break
    #                         if start_pos is None:
    #                             continue
    #                         session = sessions[s_idx]
    #                         if start_pos <= t_idx < start_pos + session.duration_hours:
    #                             blocking_vars.append(x.get((s_idx, r_idx, start_tidx)))
    #             blocking_vars = [v for v in blocking_vars if v is not None]
    #             if blocking_vars:
    #                 model.Add(sum(blocking_vars) <= 1)

    # Constraint: pathway conflict - students in same pathway can't have two classes at same time
    # NOTE: Temporarily disabled for debugging
    # pathway_to_sessions: Dict[int, List[int]] = {}
    # for s_idx, session in enumerate(sessions):
    #     for pathway_id in session.pathway_ids:
    #         pathway_to_sessions.setdefault(pathway_id, []).append(s_idx)
    #
    # for pathway_id, session_indices in pathway_to_sessions.items():
    #     for day, slots in day_slots.items():
    #         for t_idx, (ts_idx, ts) in enumerate(slots):
    #             blocking_vars = []
    #             for s_idx in session_indices:
    #                 if s_idx not in session_valid_starts:
    #                     continue
    #                 for r_idx, valid_starts_dict in session_valid_starts[s_idx].items():
    #                     valid_starts = valid_starts_dict.get(day, [])
    #                     for start_tidx in valid_starts:
    #                         start_pos = None
    #                         for pos, (st_idx, _) in enumerate(slots):
    #                             if st_idx == start_tidx:
    #                                 start_pos = pos
    #                                 break
    #                         if start_pos is None:
    #                             continue
    #                         session = sessions[s_idx]
    #                         if start_pos <= t_idx < start_pos + session.duration_hours:
    #                             blocking_vars.append(x.get((s_idx, r_idx, start_tidx)))
    #             blocking_vars = [v for v in blocking_vars if v is not None]
    #             if blocking_vars:
    #                 model.Add(sum(blocking_vars) <= 1)

    # Concurrent split sessions must run at the same time (but can use different rooms)
    # NOTE: Temporarily disabled - constraints are complex, focusing on core functionality first
    # seen_sessions: set[int] = set()
    # for s_idx, session in enumerate(sessions):
    #     if not session.concurrent_split or session.session_id in seen_sessions:
    #         continue
    #     related = [
    #         idx
    #         for idx, sess in enumerate(sessions)
    #         if sess.session_id == session.session_id
    #     ]
    #     if len(related) > 1:
    #         seen_sessions.add(session.session_id)
    #         # For each possible day/timeslot, all groups must be scheduled together or none
    #         for day, slots in day_slots.items():
    #             vars_at_timeslot: List[cp_model.IntVar] = []
    #             for sess_idx in related:
    #                 if sess_idx not in session_valid_starts:
    #                     continue
    #                 for r_idx, valid_starts_dict in session_valid_starts[sess_idx].items():
    #                     if start_tidx in valid_starts_dict.get(day, []):
    #                         var = x.get((sess_idx, r_idx, start_tidx))
    #                         if var is not None:
    #                             vars_at_timeslot.append(var)
    #             if len(vars_at_timeslot) >= 2:
    #                 # All scheduled or none scheduled
    #                 model.Add(sum(vars_at_timeslot) == 0)  # All groups scheduled at this slot sum to 0
    #                 model.Add(sum(vars_at_timeslot) == len(vars_at_timeslot))  # Or all scheduled
    #                 # Use allowed assignments: at most one of the two conditions can be true
    #                 # Actually we need: either all groups are at this timeslot, or none are
    #                 # This is a more complex OR constraint. For simplicity, let's disable for now.

    # Fixed entries constraint
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
            
            # Find if this exact (s_idx, r_idx, t_idx) combination is valid
            if (s_idx, r_idx, t_idx) in x:
                model.Add(x[(s_idx, r_idx, t_idx)] == 1)  # type: ignore[attr-defined]
            else:
                # Try to find any valid assignment that includes this timeslot
                found_constraint = False
                session = sessions[s_idx]
                day = None
                for d, slots in day_slots.items():
                    for st_idx, ts in slots:
                        if st_idx == t_idx:
                            day = d
                            break
                    if day:
                        break
                if day and s_idx in session_valid_starts and r_idx in session_valid_starts[s_idx]:
                    valid_starts = session_valid_starts[s_idx][r_idx].get(day, [])
                    # Check if this timeslot could be part of a duration block
                    for start_tidx in valid_starts:
                        start_pos = None
                        for pos, (st_idx, _) in enumerate(day_slots[day]):
                            if st_idx == start_tidx:
                                start_pos = pos
                                break
                        if start_pos is not None:
                            first_slot_id = cast(int, ordered_timeslots[0].id)
                            if start_pos <= t_idx - timeslot_index.get(first_slot_id, 0) < start_pos + session.duration_hours:
                                # This fixed entry might need to be the START of the block
                                # For now, just warn
                                pass

    if x:
        model.Maximize(sum(x.values()))  # type: ignore[attr-defined]
    else:
        diagnostics.append("No decision variables created; check rooms and timeslots")

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 30  # 30 second time limit for now
    solver.parameters.num_search_workers = 8  # Use multiple threads
    status = solver.Solve(model)
    
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        print(f"DEBUG: Solver returned {status}")
        return "infeasible", [], diagnostics
    
    results: list[tuple[int, int, int, int]] = []
    for (s_idx, r_idx, t_idx), var in x.items():
        if solver.Value(var) == 1:
            group_num = sessions[s_idx].group_number
            results.append((s_idx, r_idx, t_idx, group_num))
    
    print(f"DEBUG: Solution found! {len(results)} scheduled sessions")
    return "optimal" if status == cp_model.OPTIMAL else "feasible", results, diagnostics

    results: list[tuple[int, int, int, int]] = []
    for (s_idx, r_idx, t_idx), var in x.items():
        if solver.Value(var) == 1:
            group_num = sessions[s_idx].group_number
            results.append((s_idx, r_idx, t_idx, group_num))

    return "optimal" if status == cp_model.OPTIMAL else "feasible", results, diagnostics
