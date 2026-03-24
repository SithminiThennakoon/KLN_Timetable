use serde::{Deserialize, Serialize};
use std::collections::{BTreeMap, BTreeSet};
use std::env;
use std::fs;
use std::io::{self, Read};
use std::process::ExitCode;

const START_MINUTE: i32 = 8 * 60;
const END_MINUTE: i32 = 18 * 60;
const LUNCH_START: i32 = 12 * 60;
const LUNCH_END: i32 = 13 * 60;
const DAY_ORDER: [&str; 5] = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"];

#[derive(Debug, Deserialize, Clone)]
struct Room {
    id: i32,
    name: String,
    capacity: i32,
    room_type: Option<String>,
    lab_type: Option<String>,
    year_restriction: Option<i32>,
}

#[derive(Debug, Deserialize, Clone)]
struct AttendanceGroup {
    id: i32,
    study_year: i32,
    student_hashes: Vec<String>,
}

#[derive(Debug, Deserialize, Clone)]
struct SharedSession {
    id: i32,
    name: String,
    session_type: Option<String>,
    occurrences_per_week: i32,
    required_room_type: Option<String>,
    required_lab_type: Option<String>,
    specific_room_id: Option<i32>,
    lecturer_ids: Vec<i32>,
    attendance_group_ids: Vec<i32>,
}

#[derive(Debug, Deserialize, Clone)]
struct TimetableEntry {
    shared_session_id: i32,
    day: String,
    start_minute: i32,
    duration_minutes: i32,
    occurrence_index: i32,
    room: Room,
    lecturer_ids: Vec<i32>,
    attendance_group_ids: Vec<i32>,
    #[serde(default)]
    student_hashes: Vec<String>,
    #[serde(default)]
    study_years: Vec<i32>,
}

#[derive(Debug, Deserialize)]
struct Snapshot {
    selected_soft_constraints: Vec<String>,
    rooms: Vec<Room>,
    attendance_groups: Vec<AttendanceGroup>,
    shared_sessions: Vec<SharedSession>,
    timetable_entries: Vec<TimetableEntry>,
}

#[derive(Debug, Serialize)]
struct Violation {
    constraint: String,
    message: String,
}

#[derive(Debug, Serialize)]
struct SoftSummary {
    key: String,
    label: String,
    satisfied: bool,
    details: String,
}

#[derive(Debug, Serialize)]
struct Stats {
    entry_count: usize,
    room_count: usize,
    attendance_group_count: usize,
    shared_session_count: usize,
}

#[derive(Debug, Serialize)]
struct VerificationResult {
    verifier: String,
    hard_valid: bool,
    hard_violations: Vec<Violation>,
    soft_summary: Vec<SoftSummary>,
    stats: Stats,
}

#[derive(Debug, Clone)]
struct EntryContext {
    entry: TimetableEntry,
    session: SharedSession,
    student_hashes: BTreeSet<String>,
    study_years: BTreeSet<i32>,
}

fn overlaps(start_a: i32, end_a: i32, start_b: i32, end_b: i32) -> bool {
    start_a < end_b && start_b < end_a
}

fn is_theory(session_type: &Option<String>) -> bool {
    matches!(
        session_type.as_deref().map(|value| value.to_lowercase()),
        Some(value) if value == "lecture" || value == "tutorial" || value == "seminar"
    )
}

fn is_practical(session: &SharedSession) -> bool {
    if let Some(session_type) = session.session_type.as_deref() {
        let lowered = session_type.to_lowercase();
        if lowered == "practical" || lowered == "lab" || lowered == "laboratory" {
            return true;
        }
    }
    session.required_lab_type.is_some()
        || session.required_room_type.as_deref() == Some("lab")
}

fn standard_start_allowed(duration_minutes: i32, start_minute: i32) -> bool {
    if duration_minutes >= 180 {
        return start_minute == 9 * 60 || start_minute == 13 * 60;
    }
    if duration_minutes == 120 {
        return start_minute == 8 * 60 || start_minute == 10 * 60 || start_minute == 13 * 60;
    }
    if duration_minutes == 90 {
        return start_minute == 8 * 60 || start_minute == 13 * 60;
    }
    if duration_minutes == 60 {
        return start_minute == 8 * 60
            || start_minute == 10 * 60
            || start_minute == 13 * 60
            || start_minute == 15 * 60;
    }
    true
}

fn build_entry_context(snapshot: &Snapshot) -> Vec<EntryContext> {
    let groups_by_id: BTreeMap<i32, AttendanceGroup> = snapshot
        .attendance_groups
        .iter()
        .cloned()
        .map(|group| (group.id, group))
        .collect();
    let sessions_by_id: BTreeMap<i32, SharedSession> = snapshot
        .shared_sessions
        .iter()
        .cloned()
        .map(|session| (session.id, session))
        .collect();

    snapshot
        .timetable_entries
        .iter()
        .cloned()
        .map(|entry| {
            let session = sessions_by_id
                .get(&entry.shared_session_id)
                .expect("missing shared session")
                .clone();
            let group_ids = if entry.attendance_group_ids.is_empty() {
                session.attendance_group_ids.clone()
            } else {
                entry.attendance_group_ids.clone()
            };
            let mut student_hashes: BTreeSet<String> = entry.student_hashes.iter().cloned().collect();
            let mut study_years: BTreeSet<i32> = entry.study_years.iter().cloned().collect();
            if student_hashes.is_empty() && study_years.is_empty() {
                for group_id in group_ids {
                    if let Some(group) = groups_by_id.get(&group_id) {
                        study_years.insert(group.study_year);
                        for student_hash in &group.student_hashes {
                            student_hashes.insert(student_hash.clone());
                        }
                    }
                }
            }
            EntryContext {
                entry,
                session,
                student_hashes,
                study_years,
            }
        })
        .collect()
}

fn verify_hard_constraints(snapshot: &Snapshot) -> Vec<Violation> {
    let entries = build_entry_context(snapshot);
    let mut violations = Vec::new();
    let mut room_day_entries: BTreeMap<(i32, String), Vec<EntryContext>> = BTreeMap::new();
    let mut lecturer_day_entries: BTreeMap<(i32, String), Vec<EntryContext>> = BTreeMap::new();
    let mut student_day_entries: BTreeMap<(String, String), Vec<EntryContext>> = BTreeMap::new();

    for item in entries.iter().cloned() {
        let room = &item.entry.room;
        let start_minute = item.entry.start_minute;
        let end_minute = item.entry.start_minute + item.entry.duration_minutes;
        let student_count = item.student_hashes.len() as i32;
        let lecturer_ids = if item.entry.lecturer_ids.is_empty() {
            item.session.lecturer_ids.clone()
        } else {
            item.entry.lecturer_ids.clone()
        };

        if lecturer_ids.is_empty() {
            violations.push(Violation {
                constraint: "lecturer_assignment".to_string(),
                message: format!("Session \"{}\" has no lecturer assigned.", item.session.name),
            });
        }

        if student_count > room.capacity {
            violations.push(Violation {
                constraint: "room_capacity_compatibility".to_string(),
                message: format!(
                    "Session \"{}\" has {} students but room \"{}\" only holds {}.",
                    item.session.name, student_count, room.name, room.capacity
                ),
            });
        }
        if let Some(required_room_type) = item.session.required_room_type.as_deref() {
            if room.room_type.as_deref() != Some(required_room_type) {
                violations.push(Violation {
                    constraint: "room_capability_compatibility".to_string(),
                    message: format!(
                        "Session \"{}\" requires room type \"{}\" but was placed in \"{}\".",
                        item.session.name,
                        required_room_type,
                        room.room_type.clone().unwrap_or_default()
                    ),
                });
            }
        }
        if let Some(required_lab_type) = item.session.required_lab_type.as_deref() {
            if room.lab_type.as_deref() != Some(required_lab_type) {
                violations.push(Violation {
                    constraint: "room_capability_compatibility".to_string(),
                    message: format!(
                        "Session \"{}\" requires lab type \"{}\" but room \"{}\" is \"{}\".",
                        item.session.name,
                        required_lab_type,
                        room.name,
                        room.lab_type.clone().unwrap_or_default()
                    ),
                });
            }
        }
        if let Some(room_year_restriction) = room.year_restriction {
            if item
                .study_years
                .iter()
                .any(|study_year| *study_year != room_year_restriction)
            {
                violations.push(Violation {
                    constraint: "room_year_restriction".to_string(),
                    message: format!(
                        "Session \"{}\" includes study years {:?} but room \"{}\" is restricted to year {}.",
                        item.session.name, item.study_years, room.name, room_year_restriction
                    ),
                });
            }
        }
        if let Some(specific_room_id) = item.session.specific_room_id {
            if room.id != specific_room_id {
                violations.push(Violation {
                    constraint: "specific_room_restrictions".to_string(),
                    message: format!(
                        "Session \"{}\" must use room #{} but was placed in room #{}.",
                        item.session.name, specific_room_id, room.id
                    ),
                });
            }
        }
        if start_minute < START_MINUTE || end_minute > END_MINUTE {
            violations.push(Violation {
                constraint: "working_hours_only".to_string(),
                message: format!("Session \"{}\" falls outside working hours.", item.session.name),
            });
        }
        if overlaps(start_minute, end_minute, LUNCH_START, LUNCH_END) {
            violations.push(Violation {
                constraint: "lunch_break_protection".to_string(),
                message: format!("Session \"{}\" overlaps the lunch window.", item.session.name),
            });
        }

        room_day_entries
            .entry((room.id, item.entry.day.clone()))
            .or_default()
            .push(item.clone());
        for lecturer_id in lecturer_ids {
            lecturer_day_entries
                .entry((lecturer_id, item.entry.day.clone()))
                .or_default()
                .push(item.clone());
        }
        for student_hash in &item.student_hashes {
            student_day_entries
                .entry((student_hash.clone(), item.entry.day.clone()))
                .or_default()
                .push(item.clone());
        }
    }

    for ((room_id, day), room_entries) in room_day_entries {
        for i in 0..room_entries.len() {
            for j in (i + 1)..room_entries.len() {
                if overlaps(
                    room_entries[i].entry.start_minute,
                    room_entries[i].entry.start_minute + room_entries[i].entry.duration_minutes,
                    room_entries[j].entry.start_minute,
                    room_entries[j].entry.start_minute + room_entries[j].entry.duration_minutes,
                ) {
                    violations.push(Violation {
                        constraint: "no_room_overlap".to_string(),
                        message: format!("Room #{} is double-booked on {}.", room_id, day),
                    });
                }
            }
        }
    }

    for ((lecturer_id, day), lecturer_entries) in lecturer_day_entries {
        for i in 0..lecturer_entries.len() {
            for j in (i + 1)..lecturer_entries.len() {
                if overlaps(
                    lecturer_entries[i].entry.start_minute,
                    lecturer_entries[i].entry.start_minute + lecturer_entries[i].entry.duration_minutes,
                    lecturer_entries[j].entry.start_minute,
                    lecturer_entries[j].entry.start_minute + lecturer_entries[j].entry.duration_minutes,
                ) {
                    violations.push(Violation {
                        constraint: "no_lecturer_overlap".to_string(),
                        message: format!("Lecturer #{} is assigned to overlapping sessions on {}.", lecturer_id, day),
                    });
                }
            }
        }
    }

    for ((_, day), student_entries) in student_day_entries {
        for i in 0..student_entries.len() {
            for j in (i + 1)..student_entries.len() {
                if overlaps(
                    student_entries[i].entry.start_minute,
                    student_entries[i].entry.start_minute + student_entries[i].entry.duration_minutes,
                    student_entries[j].entry.start_minute,
                    student_entries[j].entry.start_minute + student_entries[j].entry.duration_minutes,
                ) {
                    violations.push(Violation {
                        constraint: "no_student_overlap".to_string(),
                        message: format!("Student membership overlaps on {}.", day),
                    });
                }
            }
        }
    }

    violations
}

fn summarize_soft_constraints(snapshot: &Snapshot) -> Vec<SoftSummary> {
    let entries = build_entry_context(snapshot);
    let sessions_by_id: BTreeMap<i32, SharedSession> = snapshot
        .shared_sessions
        .iter()
        .cloned()
        .map(|session| (session.id, session))
        .collect();

    let mut occurrence_days: BTreeMap<i32, BTreeMap<i32, String>> = BTreeMap::new();
    let mut daily_minutes: BTreeMap<String, i32> =
        DAY_ORDER.iter().map(|day| ((*day).to_string(), 0)).collect();

    for item in &entries {
        occurrence_days
            .entry(item.entry.shared_session_id)
            .or_default()
            .insert(item.entry.occurrence_index, item.entry.day.clone());
        *daily_minutes.entry(item.entry.day.clone()).or_default() += item.entry.duration_minutes;
    }

    snapshot
        .selected_soft_constraints
        .iter()
        .map(|key| match key.as_str() {
            "spread_sessions_across_days" => {
                let offenders: Vec<String> = occurrence_days
                    .iter()
                    .filter_map(|(session_id, day_map)| {
                        let session = sessions_by_id.get(session_id)?;
                        if session.occurrences_per_week <= 1 {
                            return None;
                        }
                        let unique_days: BTreeSet<String> = day_map.values().cloned().collect();
                        if unique_days.len() == day_map.len() {
                            None
                        } else {
                            Some(session.name.clone())
                        }
                    })
                    .collect();
                SoftSummary {
                    key: key.clone(),
                    label: "Spread repeated sessions across different days".to_string(),
                    satisfied: offenders.is_empty(),
                    details: if offenders.is_empty() {
                        "Repeated sessions are on distinct days.".to_string()
                    } else {
                        format!("Repeated sessions still share days: {}", offenders.join(", "))
                    },
                }
            }
            "prefer_morning_theory" => {
                let offenders: Vec<String> = entries
                    .iter()
                    .filter(|item| is_theory(&item.session.session_type) && item.entry.start_minute + item.entry.duration_minutes > LUNCH_START)
                    .map(|item| item.session.name.clone())
                    .collect();
                SoftSummary {
                    key: key.clone(),
                    label: "Keep theory sessions in the morning".to_string(),
                    satisfied: offenders.is_empty(),
                    details: if offenders.is_empty() {
                        "All theory sessions finish before lunch.".to_string()
                    } else {
                        format!("Theory sessions extend past lunch: {}", offenders.join(", "))
                    },
                }
            }
            "prefer_afternoon_practicals" => {
                let offenders: Vec<String> = entries
                    .iter()
                    .filter(|item| {
                        if !is_practical(&item.session) {
                            return false;
                        }
                        let start = item.entry.start_minute;
                        let duration = item.entry.duration_minutes;
                        if duration >= 180 {
                            start != LUNCH_END
                        } else if duration >= 120 {
                            start != LUNCH_END && start != 14 * 60
                        } else {
                            start < LUNCH_END
                        }
                    })
                    .map(|item| item.session.name.clone())
                    .collect();
                SoftSummary {
                    key: key.clone(),
                    label: "Keep practicals in the afternoon".to_string(),
                    satisfied: offenders.is_empty(),
                    details: if offenders.is_empty() {
                        "All practical sessions start in the preferred afternoon window.".to_string()
                    } else {
                        format!("Practical sessions start too early: {}", offenders.join(", "))
                    },
                }
            }
            "avoid_late_afternoon_starts" => {
                let offenders: Vec<String> = entries
                    .iter()
                    .filter(|item| item.entry.start_minute > 14 * 60)
                    .map(|item| item.session.name.clone())
                    .collect();
                SoftSummary {
                    key: key.clone(),
                    label: "Avoid late-afternoon starts".to_string(),
                    satisfied: offenders.is_empty(),
                    details: if offenders.is_empty() {
                        "No session starts after 2:00 PM.".to_string()
                    } else {
                        format!("Late starts remain: {}", offenders.join(", "))
                    },
                }
            }
            "avoid_friday_sessions" => {
                let offenders: Vec<String> = entries
                    .iter()
                    .filter(|item| item.entry.day == "Friday" && is_theory(&item.session.session_type))
                    .map(|item| item.session.name.clone())
                    .collect();
                SoftSummary {
                    key: key.clone(),
                    label: "Avoid Friday sessions".to_string(),
                    satisfied: offenders.is_empty(),
                    details: if offenders.is_empty() {
                        "No theory sessions are scheduled on Friday.".to_string()
                    } else {
                        format!("Friday theory sessions remain: {}", offenders.join(", "))
                    },
                }
            }
            "prefer_standard_block_starts" => {
                let offenders: Vec<String> = entries
                    .iter()
                    .filter(|item| !standard_start_allowed(item.entry.duration_minutes, item.entry.start_minute))
                    .map(|item| item.session.name.clone())
                    .collect();
                SoftSummary {
                    key: key.clone(),
                    label: "Use standard block starts".to_string(),
                    satisfied: offenders.is_empty(),
                    details: if offenders.is_empty() {
                        "All sessions use standard block starts.".to_string()
                    } else {
                        format!("Non-standard starts remain: {}", offenders.join(", "))
                    },
                }
            }
            "balance_teaching_load_across_week" => {
                let peak = daily_minutes.values().copied().max().unwrap_or(0);
                let trough = daily_minutes.values().copied().min().unwrap_or(0);
                SoftSummary {
                    key: key.clone(),
                    label: "Balance teaching load across the week".to_string(),
                    satisfied: peak - trough <= 180,
                    details: format!("Daily load spread: {:?}", daily_minutes),
                }
            }
            "avoid_monday_overload" => {
                let monday = *daily_minutes.get("Monday").unwrap_or(&0);
                let others: Vec<i32> = daily_minutes
                    .iter()
                    .filter(|(day, _)| day.as_str() != "Monday")
                    .map(|(_, minutes)| *minutes)
                    .collect();
                let satisfied = others.iter().min().map(|value| monday <= *value).unwrap_or(true);
                SoftSummary {
                    key: key.clone(),
                    label: "Avoid Monday overload".to_string(),
                    satisfied,
                    details: format!("Daily load spread: {:?}", daily_minutes),
                }
            }
            _ => SoftSummary {
                key: key.clone(),
                label: key.clone(),
                satisfied: false,
                details: "Unknown soft constraint key.".to_string(),
            },
        })
        .collect()
}

fn verify_snapshot(snapshot: &Snapshot) -> VerificationResult {
    let hard_violations = verify_hard_constraints(snapshot);
    VerificationResult {
        verifier: "rust".to_string(),
        hard_valid: hard_violations.is_empty(),
        hard_violations,
        soft_summary: summarize_soft_constraints(snapshot),
        stats: Stats {
            entry_count: snapshot.timetable_entries.len(),
            room_count: snapshot.rooms.len(),
            attendance_group_count: snapshot.attendance_groups.len(),
            shared_session_count: snapshot.shared_sessions.len(),
        },
    }
}

fn read_snapshot(path: &str) -> Result<Snapshot, String> {
    let raw = if path == "-" {
        let mut buffer = String::new();
        io::stdin()
            .read_to_string(&mut buffer)
            .map_err(|err| err.to_string())?;
        buffer
    } else {
        fs::read_to_string(path).map_err(|err| err.to_string())?
    };
    serde_json::from_str(&raw).map_err(|err| err.to_string())
}

fn main() -> ExitCode {
    let args: Vec<String> = env::args().collect();
    if args.len() != 2 {
        eprintln!("usage: rust_snapshot_verifier <snapshot.json|- >");
        return ExitCode::from(2);
    }

    let snapshot = match read_snapshot(&args[1]) {
        Ok(snapshot) => snapshot,
        Err(err) => {
            eprintln!("{err}");
            return ExitCode::from(2);
        }
    };

    let result = verify_snapshot(&snapshot);
    println!("{}", serde_json::to_string_pretty(&result).unwrap());
    if result.hard_valid {
        ExitCode::from(0)
    } else {
        ExitCode::from(1)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn snapshot_json() -> Snapshot {
        serde_json::from_str(
            r#"{
              "selected_soft_constraints": ["prefer_morning_theory"],
              "rooms": [
                {"id": 1, "name": "Hall A", "capacity": 80, "room_type": "lecture", "lab_type": null, "year_restriction": null}
              ],
              "attendance_groups": [
                {"id": 1, "study_year": 1, "student_hashes": ["s1", "s2", "s3"]}
              ],
              "shared_sessions": [
                {
                  "id": 1,
                  "name": "CHEM 101 Lecture",
                  "session_type": "lecture",
                  "duration_minutes": 120,
                  "occurrences_per_week": 1,
                  "required_room_type": "lecture",
                  "required_lab_type": null,
                  "specific_room_id": null,
                  "lecturer_ids": [1],
                  "attendance_group_ids": [1]
                }
              ],
              "timetable_entries": [
                {
                  "shared_session_id": 1,
                  "day": "Monday",
                  "start_minute": 480,
                  "duration_minutes": 120,
                  "occurrence_index": 1,
                  "room": {"id": 1, "name": "Hall A", "capacity": 80, "room_type": "lecture", "lab_type": null, "year_restriction": null},
                  "lecturer_ids": [1],
                  "attendance_group_ids": [1]
                }
              ]
            }"#,
        )
        .unwrap()
    }

    #[test]
    fn valid_snapshot_passes() {
        let result = verify_snapshot(&snapshot_json());
        assert!(result.hard_valid);
    }

    #[test]
    fn capacity_violation_is_reported() {
        let mut snapshot = snapshot_json();
        snapshot.timetable_entries[0].room.capacity = 1;
        let result = verify_snapshot(&snapshot);
        assert!(!result.hard_valid);
        assert!(result
            .hard_violations
            .iter()
            .any(|item| item.constraint == "room_capacity_compatibility"));
    }

    #[test]
    fn room_year_restriction_violation_is_reported() {
        let mut snapshot = snapshot_json();
        snapshot.timetable_entries[0].room.year_restriction = Some(2);
        let result = verify_snapshot(&snapshot);
        assert!(!result.hard_valid);
        assert!(result
            .hard_violations
            .iter()
            .any(|item| item.constraint == "room_year_restriction"));
    }

    #[test]
    fn missing_lecturer_assignment_is_reported() {
        let mut snapshot = snapshot_json();
        snapshot.shared_sessions[0].lecturer_ids = vec![];
        snapshot.timetable_entries[0].lecturer_ids = vec![];
        let result = verify_snapshot(&snapshot);
        assert!(!result.hard_valid);
        assert!(result
            .hard_violations
            .iter()
            .any(|item| item.constraint == "lecturer_assignment"));
    }
}
