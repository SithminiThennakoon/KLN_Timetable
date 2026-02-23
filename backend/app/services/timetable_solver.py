from collections import defaultdict

from ortools.sat.python import cp_model

from app.schemas.timetable import TimetableEntry, TimetableSolveRequest, TimetableSolveResponse


def solve_timetable(request: TimetableSolveRequest) -> TimetableSolveResponse:
    model = cp_model.CpModel()

    total_slots = request.days * request.slots_per_day
    unavailable = request.lecturer_unavailable_slots or {}

    x = {}
    for c_idx, course in enumerate(request.courses):
        for r_idx, room in enumerate(request.rooms):
            for t in range(total_slots):
                if t in unavailable.get(course.lecturer_id, []):
                    continue
                x[(c_idx, r_idx, t)] = model.NewBoolVar(f"x_c{c_idx}_r{r_idx}_t{t}")

    for c_idx, course in enumerate(request.courses):
        vars_for_course = [
            var
            for (ci, _, _), var in x.items()
            if ci == c_idx
        ]
        model.Add(sum(vars_for_course) == course.sessions_per_week)

    for r_idx, _room in enumerate(request.rooms):
        for t in range(total_slots):
            vars_for_room_slot = [
                x[(c_idx, r_idx, t)]
                for c_idx in range(len(request.courses))
                if (c_idx, r_idx, t) in x
            ]
            if vars_for_room_slot:
                model.Add(sum(vars_for_room_slot) <= 1)

    lecturer_to_courses = defaultdict(list)
    group_to_courses = defaultdict(list)
    for c_idx, course in enumerate(request.courses):
        lecturer_to_courses[course.lecturer_id].append(c_idx)
        group_to_courses[course.student_group_id].append(c_idx)

    for t in range(total_slots):
        for course_indices in lecturer_to_courses.values():
            vars_for_lecturer_slot = [
                x[(c_idx, r_idx, t)]
                for c_idx in course_indices
                for r_idx in range(len(request.rooms))
                if (c_idx, r_idx, t) in x
            ]
            if vars_for_lecturer_slot:
                model.Add(sum(vars_for_lecturer_slot) <= 1)

        for course_indices in group_to_courses.values():
            vars_for_group_slot = [
                x[(c_idx, r_idx, t)]
                for c_idx in course_indices
                for r_idx in range(len(request.rooms))
                if (c_idx, r_idx, t) in x
            ]
            if vars_for_group_slot:
                model.Add(sum(vars_for_group_slot) <= 1)

    model.Maximize(sum(x.values()))

    solver = cp_model.CpSolver()
    status = solver.Solve(model)

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return TimetableSolveResponse(
            status="infeasible",
            total_scheduled_sessions=0,
            timetable=[],
        )

    timetable = []
    for (c_idx, r_idx, t), var in x.items():
        if solver.Value(var) == 1:
            course = request.courses[c_idx]
            room = request.rooms[r_idx]
            day = t // request.slots_per_day
            slot = t % request.slots_per_day
            timetable.append(
                TimetableEntry(
                    course_id=course.course_id,
                    lecturer_id=course.lecturer_id,
                    student_group_id=course.student_group_id,
                    room_id=room.room_id,
                    day=day,
                    slot=slot,
                )
            )

    return TimetableSolveResponse(
        status="optimal" if status == cp_model.OPTIMAL else "feasible",
        total_scheduled_sessions=len(timetable),
        timetable=sorted(timetable, key=lambda e: (e.day, e.slot, e.room_id)),
    )
