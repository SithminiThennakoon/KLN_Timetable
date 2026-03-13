from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any


DAY_ORDER = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
START_MINUTE = 8 * 60
END_MINUTE = 18 * 60
LUNCH_START = 12 * 60
LUNCH_END = 13 * 60

SOFT_CONSTRAINT_LABELS = {
    "spread_sessions_across_days": "Spread repeated sessions across different days",
    "prefer_morning_theory": "Keep theory sessions in the morning",
    "prefer_afternoon_practicals": "Keep practicals in the afternoon",
    "avoid_late_afternoon_starts": "Avoid late-afternoon starts",
    "avoid_friday_sessions": "Avoid Friday sessions",
    "prefer_standard_block_starts": "Use standard block starts",
    "balance_teaching_load_across_week": "Balance teaching load across the week",
    "avoid_monday_overload": "Avoid Monday overload",
}


def _overlap(start_a: int, end_a: int, start_b: int, end_b: int) -> bool:
    return start_a < end_b and start_b < end_a


def _is_theory(session_type: str | None) -> bool:
    return (session_type or "").lower() in {"lecture", "tutorial", "seminar"}


def _is_practical(session: dict[str, Any]) -> bool:
    session_type = (session.get("session_type") or "").lower()
    if session_type in {"practical", "lab", "laboratory"}:
        return True
    return bool(session.get("required_lab_type")) or session.get("required_room_type") == "lab"


def _standard_start_allowed(duration_minutes: int, start_minute: int) -> bool:
    if duration_minutes >= 180:
        return start_minute in {9 * 60, 13 * 60}
    if duration_minutes == 120:
        return start_minute in {8 * 60, 10 * 60, 13 * 60}
    if duration_minutes == 90:
        return start_minute in {8 * 60, 13 * 60}
    if duration_minutes == 60:
        return start_minute in {8 * 60, 10 * 60, 13 * 60, 15 * 60}
    return True


def _build_entry_context(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    groups_by_id = {int(item["id"]): item for item in snapshot.get("attendance_groups", [])}
    sessions_by_id = {int(item["id"]): item for item in snapshot.get("shared_sessions", [])}
    rooms_by_id = {int(item["id"]): item for item in snapshot.get("rooms", [])}

    entries: list[dict[str, Any]] = []
    for raw in snapshot.get("timetable_entries", []):
        session = sessions_by_id[int(raw["shared_session_id"])]
        room = raw.get("room") or rooms_by_id[int(raw["room_id"])]
        attendance_group_ids = [int(item) for item in raw.get("attendance_group_ids") or session.get("attendance_group_ids", [])]
        lecturer_ids = [int(item) for item in raw.get("lecturer_ids") or session.get("lecturer_ids", [])]
        student_hashes: set[str] = set()
        study_years: set[int] = set()
        for group_id in attendance_group_ids:
            group = groups_by_id.get(group_id)
            if not group:
                continue
            student_hashes.update(group.get("student_hashes", []))
            study_year = group.get("study_year")
            if study_year is not None:
                study_years.add(int(study_year))
        entries.append(
            {
                "solution_entry_id": int(raw["solution_entry_id"]),
                "shared_session_id": int(raw["shared_session_id"]),
                "occurrence_index": int(raw["occurrence_index"]),
                "split_index": int(raw["split_index"]),
                "day": raw["day"],
                "start_minute": int(raw["start_minute"]),
                "end_minute": int(raw["start_minute"]) + int(raw["duration_minutes"]),
                "duration_minutes": int(raw["duration_minutes"]),
                "room": room,
                "session": session,
                "attendance_group_ids": attendance_group_ids,
                "lecturer_ids": lecturer_ids,
                "student_hashes": student_hashes,
                "study_years": study_years,
            }
        )
    return entries


def _violation(constraint: str, message: str, **details: Any) -> dict[str, Any]:
    payload = {"constraint": constraint, "message": message}
    payload.update(details)
    return payload


def _verify_hard_constraints(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    violations: list[dict[str, Any]] = []
    entries = _build_entry_context(snapshot)

    room_day_entries: dict[tuple[int, str], list[dict[str, Any]]] = defaultdict(list)
    lecturer_day_entries: dict[tuple[int, str], list[dict[str, Any]]] = defaultdict(list)
    student_day_entries: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)

    for entry in entries:
        session = entry["session"]
        room = entry["room"]
        student_count = len(entry["student_hashes"])
        start_minute = entry["start_minute"]
        end_minute = entry["end_minute"]

        if not entry["lecturer_ids"]:
            violations.append(
                _violation(
                    "lecturer_assignment",
                    f'Session "{session["name"]}" has no lecturer assigned.',
                    shared_session_id=entry["shared_session_id"],
                )
            )

        if student_count > int(room["capacity"]):
            violations.append(
                _violation(
                    "room_capacity_compatibility",
                    f'Session "{session["name"]}" has {student_count} students but room "{room["name"]}" only holds {room["capacity"]}.',
                    shared_session_id=entry["shared_session_id"],
                    room_id=int(room["id"]),
                    student_count=student_count,
                    room_capacity=int(room["capacity"]),
                )
            )

        required_room_type = session.get("required_room_type")
        if required_room_type and room.get("room_type") != required_room_type:
            violations.append(
                _violation(
                    "room_capability_compatibility",
                    f'Session "{session["name"]}" requires room type "{required_room_type}" but was placed in "{room.get("room_type")}".',
                    shared_session_id=entry["shared_session_id"],
                    room_id=int(room["id"]),
                )
            )

        required_lab_type = session.get("required_lab_type")
        if required_lab_type and room.get("lab_type") != required_lab_type:
            violations.append(
                _violation(
                    "room_capability_compatibility",
                    f'Session "{session["name"]}" requires lab type "{required_lab_type}" but room "{room["name"]}" is "{room.get("lab_type")}".',
                    shared_session_id=entry["shared_session_id"],
                    room_id=int(room["id"]),
                )
            )

        room_year_restriction = room.get("year_restriction")
        if room_year_restriction is not None and any(
            int(study_year) != int(room_year_restriction)
            for study_year in entry["study_years"]
        ):
            violations.append(
                _violation(
                    "room_year_restriction",
                    f'Session "{session["name"]}" includes study years {sorted(entry["study_years"])} but room "{room["name"]}" is restricted to year {room_year_restriction}.',
                    shared_session_id=entry["shared_session_id"],
                    room_id=int(room["id"]),
                    room_year_restriction=int(room_year_restriction),
                    study_years=sorted(entry["study_years"]),
                )
            )

        specific_room_id = session.get("specific_room_id")
        if specific_room_id and int(room["id"]) != int(specific_room_id):
            violations.append(
                _violation(
                    "specific_room_restrictions",
                    f'Session "{session["name"]}" must use room #{specific_room_id} but was placed in room #{room["id"]}.',
                    shared_session_id=entry["shared_session_id"],
                    room_id=int(room["id"]),
                    specific_room_id=int(specific_room_id),
                )
            )

        if start_minute < START_MINUTE or end_minute > END_MINUTE:
            violations.append(
                _violation(
                    "working_hours_only",
                    f'Session "{session["name"]}" falls outside working hours.',
                    shared_session_id=entry["shared_session_id"],
                    day=entry["day"],
                    start_minute=start_minute,
                    end_minute=end_minute,
                )
            )

        if _overlap(start_minute, end_minute, LUNCH_START, LUNCH_END):
            violations.append(
                _violation(
                    "lunch_break_protection",
                    f'Session "{session["name"]}" overlaps the lunch window.',
                    shared_session_id=entry["shared_session_id"],
                    day=entry["day"],
                    start_minute=start_minute,
                    end_minute=end_minute,
                )
            )

        room_day_entries[(int(room["id"]), entry["day"])].append(entry)
        for lecturer_id in entry["lecturer_ids"]:
            lecturer_day_entries[(int(lecturer_id), entry["day"])].append(entry)
        for student_hash in entry["student_hashes"]:
            student_day_entries[(student_hash, entry["day"])].append(entry)

    for (room_id, day), room_entries in room_day_entries.items():
        ordered = sorted(room_entries, key=lambda item: (item["start_minute"], item["end_minute"]))
        for index, current in enumerate(ordered):
            for other in ordered[index + 1 :]:
                if not _overlap(current["start_minute"], current["end_minute"], other["start_minute"], other["end_minute"]):
                    continue
                violations.append(
                    _violation(
                        "no_room_overlap",
                        f'Room #{room_id} is double-booked on {day}.',
                        room_id=room_id,
                        day=day,
                        shared_session_ids=[current["shared_session_id"], other["shared_session_id"]],
                    )
                )

    for (lecturer_id, day), lecturer_entries in lecturer_day_entries.items():
        ordered = sorted(lecturer_entries, key=lambda item: (item["start_minute"], item["end_minute"]))
        for index, current in enumerate(ordered):
            for other in ordered[index + 1 :]:
                if not _overlap(current["start_minute"], current["end_minute"], other["start_minute"], other["end_minute"]):
                    continue
                violations.append(
                    _violation(
                        "no_lecturer_overlap",
                        f"Lecturer #{lecturer_id} is assigned to overlapping sessions on {day}.",
                        lecturer_id=lecturer_id,
                        day=day,
                        shared_session_ids=[current["shared_session_id"], other["shared_session_id"]],
                    )
                )

    for (student_hash, day), student_entries in student_day_entries.items():
        ordered = sorted(student_entries, key=lambda item: (item["start_minute"], item["end_minute"]))
        for index, current in enumerate(ordered):
            for other in ordered[index + 1 :]:
                if not _overlap(current["start_minute"], current["end_minute"], other["start_minute"], other["end_minute"]):
                    continue
                violations.append(
                    _violation(
                        "no_student_overlap",
                        f"Student membership overlaps on {day}.",
                        student_hash=student_hash,
                        day=day,
                        shared_session_ids=[current["shared_session_id"], other["shared_session_id"]],
                    )
                )

    return violations


def _summarize_soft_constraints(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    entries = _build_entry_context(snapshot)
    sessions_by_id = {int(item["id"]): item for item in snapshot.get("shared_sessions", [])}
    selected = list(snapshot.get("selected_soft_constraints", []))
    daily_minutes = {day: 0 for day in DAY_ORDER}
    for entry in entries:
        daily_minutes[entry["day"]] += int(entry["duration_minutes"])

    occurrence_days: dict[int, dict[int, str]] = defaultdict(dict)
    for entry in entries:
        occurrence_days[entry["shared_session_id"]][entry["occurrence_index"]] = entry["day"]

    results: list[dict[str, Any]] = []
    for key in selected:
        satisfied = True
        details = ""
        if key == "spread_sessions_across_days":
            offenders = []
            for session_id, day_map in occurrence_days.items():
                session = sessions_by_id.get(session_id)
                if not session or int(session.get("occurrences_per_week") or 1) <= 1:
                    continue
                if len(set(day_map.values())) != len(day_map):
                    offenders.append(session["name"])
            satisfied = len(offenders) == 0
            details = "Repeated sessions are on distinct days." if satisfied else f"Repeated sessions still share days: {', '.join(offenders[:5])}"
        elif key == "prefer_morning_theory":
            offenders = [item["session"]["name"] for item in entries if _is_theory(item["session"].get("session_type")) and item["end_minute"] > LUNCH_START]
            satisfied = len(offenders) == 0
            details = "All theory sessions finish before lunch." if satisfied else f"Theory sessions extend past lunch: {', '.join(offenders[:5])}"
        elif key == "prefer_afternoon_practicals":
            offenders = []
            for item in entries:
                if not _is_practical(item["session"]):
                    continue
                start_minute = item["start_minute"]
                duration_minutes = item["duration_minutes"]
                if duration_minutes >= 180 and start_minute != LUNCH_END:
                    offenders.append(item["session"]["name"])
                elif duration_minutes >= 120 and start_minute not in {LUNCH_END, 14 * 60}:
                    offenders.append(item["session"]["name"])
                elif duration_minutes < 120 and start_minute < LUNCH_END:
                    offenders.append(item["session"]["name"])
            satisfied = len(offenders) == 0
            details = "All practical sessions start in the preferred afternoon window." if satisfied else f"Practical sessions start too early: {', '.join(offenders[:5])}"
        elif key == "avoid_late_afternoon_starts":
            offenders = [item["session"]["name"] for item in entries if item["start_minute"] > 14 * 60]
            satisfied = len(offenders) == 0
            details = "No session starts after 2:00 PM." if satisfied else f"Late starts remain: {', '.join(offenders[:5])}"
        elif key == "avoid_friday_sessions":
            offenders = [item["session"]["name"] for item in entries if item["day"] == "Friday" and _is_theory(item["session"].get("session_type"))]
            satisfied = len(offenders) == 0
            details = "No theory sessions are scheduled on Friday." if satisfied else f"Friday theory sessions remain: {', '.join(offenders[:5])}"
        elif key == "prefer_standard_block_starts":
            offenders = [item["session"]["name"] for item in entries if not _standard_start_allowed(item["duration_minutes"], item["start_minute"])]
            satisfied = len(offenders) == 0
            details = "All sessions use standard block starts." if satisfied else f"Non-standard starts remain: {', '.join(offenders[:5])}"
        elif key == "balance_teaching_load_across_week":
            peak = max(daily_minutes.values()) if daily_minutes else 0
            trough = min(daily_minutes.values()) if daily_minutes else 0
            satisfied = (peak - trough) <= 180
            details = f"Daily load spread: {daily_minutes}."
        elif key == "avoid_monday_overload":
            monday = daily_minutes.get("Monday", 0)
            others = [minutes for day, minutes in daily_minutes.items() if day != "Monday"]
            satisfied = monday <= min(others) if others else True
            details = f"Daily load spread: {daily_minutes}."
        else:
            details = "Unknown soft constraint key."

        results.append(
            {
                "key": key,
                "label": SOFT_CONSTRAINT_LABELS.get(key, key),
                "satisfied": satisfied,
                "details": details,
            }
        )
    return results


def verify_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    entries = snapshot.get("timetable_entries", [])
    hard_violations = _verify_hard_constraints(snapshot)
    return {
        "verifier": "python",
        "hard_valid": len(hard_violations) == 0,
        "hard_violations": hard_violations,
        "soft_summary": _summarize_soft_constraints(snapshot),
        "stats": {
            "entry_count": len(entries),
            "room_count": len(snapshot.get("rooms", [])),
            "attendance_group_count": len(snapshot.get("attendance_groups", [])),
            "shared_session_count": len(snapshot.get("shared_sessions", [])),
        },
    }


def _load_snapshot(path: str) -> dict[str, Any]:
    if path == "-":
        return json.load(__import__("sys").stdin)
    with Path(path).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify a snapshot timetable JSON payload.")
    parser.add_argument("snapshot", help="Path to snapshot JSON file or - for stdin")
    args = parser.parse_args()

    result = verify_snapshot(_load_snapshot(args.snapshot))
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["hard_valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
