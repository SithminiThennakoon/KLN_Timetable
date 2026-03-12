from __future__ import annotations

import csv
import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from app.services.enrollment_inference import (
    DEFAULT_ENROLLMENT_CSV,
    LAB_SPLIT_LIMIT_BY_TYPE,
    STREAM_NAME_MAP,
    _parse_academic_year,
    _slug,
    _synthetic_lab_type,
    _synthetic_lecture_duration,
)

MODULE_CODE_RE = re.compile(r"^(?P<prefix>[A-Z]{4})\s*(?P<digits>\d{5})$")
ACADEMIC_YEAR_RE = re.compile(r"^\d{4}/\d{4}$")
INVALID_ANOMALIES = {
    "missing_required_field",
    "non_numeric_year",
    "malformed_academic_year",
    "unparseable_course_code",
}
DEFAULT_ATTEMPTS = ("1",)


@dataclass(frozen=True)
class ParsedModuleCode:
    subject_code: str
    nominal_year: int
    nominal_semester_code: str
    nominal_semester_bucket: int | None
    is_full_year: bool


@dataclass
class ReviewRule:
    bucket_type: str
    bucket_key: str
    action: str
    label: str | None = None


@dataclass
class StagedEnrollmentRow:
    row_number: int
    course_path_no: str
    course_code: str
    year: str
    academic_year: str
    attempt: str
    stream: str
    batch: str
    student_hash: str
    module_subject_code: str | None
    module_nominal_year: int | None
    module_nominal_semester_code: str | None
    module_nominal_semester: int | None
    is_full_year: bool
    anomaly_codes: set[str] = field(default_factory=set)
    resolved_anomaly_codes: set[str] = field(default_factory=set)
    matched_rule_actions: set[str] = field(default_factory=set)
    effective_course_path_no: str | None = None
    status: str = "valid"

    def finalize(self) -> None:
        self.status = _classify_status(self.anomaly_codes, self.matched_rule_actions)
        if self.effective_course_path_no is None:
            self.effective_course_path_no = self.course_path_no or None

    def to_sample(self) -> dict:
        return {
            "row_number": self.row_number,
            "course_code": self.course_code,
            "stream": self.stream,
            "year": self.year,
            "academic_year": self.academic_year,
            "batch": self.batch,
            "course_path_no": self.course_path_no,
            "student_hash": self.student_hash,
            "anomaly_codes": sorted(self.anomaly_codes),
        }


def _normalize_semester_bucket(value: str | None) -> int | None:
    if value == "3":
        return 1
    if value in {"2", "4"}:
        return 2
    if value == "1":
        return 1
    return None


def _parse_module_code(course_code: str) -> ParsedModuleCode | None:
    match = MODULE_CODE_RE.match(course_code.strip())
    if not match:
        return None
    digits = match.group("digits")
    semester_code = digits[1]
    return ParsedModuleCode(
        subject_code=match.group("prefix"),
        nominal_year=int(digits[0]),
        nominal_semester_code=semester_code,
        nominal_semester_bucket=_normalize_semester_bucket(semester_code),
        is_full_year=semester_code == "3",
    )


def _classify_status(anomaly_codes: set[str], matched_rule_actions: set[str]) -> str:
    if anomaly_codes & INVALID_ANOMALIES:
        return "invalid"
    unresolved = set(anomaly_codes)
    if "exclude" in matched_rule_actions:
        return "ambiguous"
    if unresolved:
        if unresolved and all(action in {"accept_exception", "treat_as_common"} for action in matched_rule_actions) and matched_rule_actions:
            return "valid_exception"
        return "ambiguous"
    return "valid"


def _iter_rows(path: str) -> list[StagedEnrollmentRow]:
    csv_path = Path(path)
    if not csv_path.exists():
        raise FileNotFoundError(f"Enrollment CSV not found: {csv_path}")

    rows: list[StagedEnrollmentRow] = []
    with csv_path.open(encoding="utf-8") as handle:
        for row_number, raw in enumerate(csv.DictReader(handle), start=2):
            course_path_no = (raw.get("CoursePathNo") or "").strip()
            course_code = (raw.get("CourseCode") or "").strip()
            year = (raw.get("Year") or "").strip()
            academic_year = (raw.get("AcYear") or "").strip()
            attempt = (raw.get("Attempt") or "").strip()
            stream = (raw.get("stream") or "").strip()
            batch = (raw.get("batch") or "").strip()
            student_hash = (raw.get("student_hash") or "").strip()
            parsed_code = _parse_module_code(course_code)
            anomalies: set[str] = set()

            if not all([student_hash, course_code, year, academic_year, stream]):
                anomalies.add("missing_required_field")
            if not year.isdigit():
                anomalies.add("non_numeric_year")
            if not ACADEMIC_YEAR_RE.match(academic_year):
                anomalies.add("malformed_academic_year")
            if not attempt:
                anomalies.add("missing_attempt")
            if not batch:
                anomalies.add("missing_batch")
            if not course_path_no:
                anomalies.add("blank_course_path")
            if parsed_code is None:
                anomalies.add("unparseable_course_code")
            else:
                if parsed_code.nominal_year == 0:
                    anomalies.add("nominal_year_zero")
                if parsed_code.nominal_semester_bucket is None:
                    anomalies.add("semester_code_unusual")
                if year.isdigit() and parsed_code.nominal_year != int(year):
                    anomalies.add("year_code_mismatch")

            row = StagedEnrollmentRow(
                row_number=row_number,
                course_path_no=course_path_no,
                course_code=course_code,
                year=year,
                academic_year=academic_year,
                attempt=attempt,
                stream=stream,
                batch=batch,
                student_hash=student_hash,
                module_subject_code=parsed_code.subject_code if parsed_code else None,
                module_nominal_year=parsed_code.nominal_year if parsed_code else None,
                module_nominal_semester_code=parsed_code.nominal_semester_code if parsed_code else None,
                module_nominal_semester=parsed_code.nominal_semester_bucket if parsed_code else None,
                is_full_year=parsed_code.is_full_year if parsed_code else False,
                anomaly_codes=anomalies,
            )
            rows.append(row)
    _add_global_anomalies(rows)
    for row in rows:
        row.finalize()
    return rows


def _add_global_anomalies(rows: list[StagedEnrollmentRow]) -> None:
    validish_rows = [row for row in rows if "unparseable_course_code" not in row.anomaly_codes]
    streams_by_module: dict[str, Counter[str]] = defaultdict(Counter)
    paths_by_module_context: dict[tuple[str, str, str], Counter[str]] = defaultdict(Counter)
    years_by_module: dict[str, set[str]] = defaultdict(set)
    mismatches_by_module: Counter[str] = Counter()

    for row in validish_rows:
        streams_by_module[row.course_code][row.stream] += 1
        paths_by_module_context[(row.stream, row.year, row.course_code)][row.course_path_no or "(blank)"] += 1
        if row.year:
            years_by_module[row.course_code].add(row.year)
        if "year_code_mismatch" in row.anomaly_codes:
            mismatches_by_module[row.course_code] += 1

    for row in validish_rows:
        stream_counts = streams_by_module[row.course_code]
        total_for_module = sum(stream_counts.values())
        if len(stream_counts) > 1 and total_for_module > 0:
            ratio = stream_counts[row.stream] / total_for_module
            if ratio <= 0.2 or stream_counts[row.stream] <= 5:
                row.anomaly_codes.add("unusual_stream_module_pair")

        path_counts = paths_by_module_context[(row.stream, row.year, row.course_code)]
        if len(path_counts) >= 3 or ("(blank)" in path_counts and len(path_counts) >= 2):
            row.anomaly_codes.add("unusual_path_distribution")

        if len(years_by_module[row.course_code]) > 1:
            row.anomaly_codes.add("multi_year_module_code")

        if mismatches_by_module[row.course_code] and mismatches_by_module[row.course_code] <= 3:
            row.anomaly_codes.add("rare_module_pattern")


def _bucket_for_anomaly(row: StagedEnrollmentRow, anomaly_code: str) -> tuple[str, str, str]:
    if anomaly_code == "year_code_mismatch":
        return (
            anomaly_code,
            f"year={row.year}|nominal_year={row.module_nominal_year}",
            f"CSV Year {row.year} does not match nominal module year {row.module_nominal_year}.",
        )
    if anomaly_code == "blank_course_path":
        return (
            anomaly_code,
            f"stream={row.stream}|year={row.year}|subject={row.module_subject_code or 'unknown'}",
            "CoursePathNo is blank and needs review as common-module data or missing source structure.",
        )
    if anomaly_code == "missing_attempt":
        return (anomaly_code, f"stream={row.stream}|year={row.year}", "Attempt is missing and the row cannot yet be interpreted safely.")
    if anomaly_code == "missing_batch":
        return (anomaly_code, f"stream={row.stream}|year={row.year}", "Batch is missing and cohort lineage cannot be reconstructed safely.")
    if anomaly_code == "malformed_academic_year":
        return (anomaly_code, f"academic_year={row.academic_year or 'blank'}", "AcYear is missing or not in YYYY/YYYY format.")
    if anomaly_code == "nominal_year_zero":
        return (anomaly_code, f"course_code={row.course_code}", "Module code has nominal year digit 0 and needs explicit interpretation.")
    if anomaly_code == "semester_code_unusual":
        return (anomaly_code, f"semester_code={row.module_nominal_semester_code or 'unknown'}", "Module code semester digit is outside the currently recognized timetable semantics.")
    if anomaly_code == "missing_required_field":
        return (anomaly_code, f"stream={row.stream or 'blank'}|course_code={row.course_code or 'blank'}", "One or more required fields are missing.")
    if anomaly_code == "non_numeric_year":
        return (anomaly_code, f"year={row.year or 'blank'}", "Year is missing or non-numeric.")
    if anomaly_code == "unparseable_course_code":
        return (anomaly_code, f"course_code={row.course_code or 'blank'}", "CourseCode does not match the expected SUBJ 12345 format.")
    if anomaly_code == "unusual_stream_module_pair":
        return (anomaly_code, f"course_code={row.course_code}|stream={row.stream}", "Module appears in an unusually rare stream for its observed registrations.")
    if anomaly_code == "unusual_path_distribution":
        return (anomaly_code, f"course_code={row.course_code}|stream={row.stream}|year={row.year}", "Module spans many paths or mixes blank and non-blank paths, suggesting common teaching or data ambiguity.")
    if anomaly_code == "rare_module_pattern":
        return (anomaly_code, f"course_code={row.course_code}", "Module anomaly appears only a few times and may be a special rule or a data issue.")
    if anomaly_code == "multi_year_module_code":
        return (anomaly_code, f"course_code={row.course_code}", "The same module code appears with multiple CSV Year values and needs reviewed interpretation.")
    return (anomaly_code, anomaly_code, anomaly_code)


def _rule_map(rules: list[ReviewRule]) -> dict[tuple[str, str], list[ReviewRule]]:
    mapping: dict[tuple[str, str], list[ReviewRule]] = defaultdict(list)
    for rule in rules:
        mapping[(rule.bucket_type, rule.bucket_key)].append(rule)
    return mapping


def _apply_rules(rows: list[StagedEnrollmentRow], rules: list[ReviewRule]) -> None:
    by_key = _rule_map(rules)
    for row in rows:
        actions: set[str] = set()
        for anomaly in list(row.anomaly_codes):
            bucket_type, bucket_key, _ = _bucket_for_anomaly(row, anomaly)
            for rule in by_key.get((bucket_type, bucket_key), []):
                actions.add(rule.action)
                if rule.action == "treat_as_common":
                    row.effective_course_path_no = None
                if rule.action in {"accept_exception", "treat_as_common"}:
                    row.resolved_anomaly_codes.add(anomaly)
        row.matched_rule_actions = actions
        unresolved = row.anomaly_codes - row.resolved_anomaly_codes
        if row.anomaly_codes and not unresolved and actions & {"accept_exception", "treat_as_common"}:
            row.status = "valid_exception"
        else:
            row.status = _classify_status(unresolved, row.matched_rule_actions)
        if row.effective_course_path_no is None:
            row.effective_course_path_no = row.course_path_no or None


def _analysis_payload(rows: list[StagedEnrollmentRow], source_file: str) -> dict:
    status_counts: Counter[str] = Counter(row.status for row in rows)
    anomaly_counts: Counter[str] = Counter()
    semester_digit_counts: Counter[str] = Counter()
    bucket_rows: dict[tuple[str, str], list[StagedEnrollmentRow]] = defaultdict(list)
    bucket_descriptions: dict[tuple[str, str], str] = {}

    for row in rows:
        if row.module_nominal_semester_code:
            semester_digit_counts[row.module_nominal_semester_code] += 1
        for anomaly in sorted(row.anomaly_codes):
            anomaly_counts[anomaly] += 1
            bucket_type, bucket_key, description = _bucket_for_anomaly(row, anomaly)
            bucket_rows[(bucket_type, bucket_key)].append(row)
            bucket_descriptions[(bucket_type, bucket_key)] = description

    buckets = []
    for (bucket_type, bucket_key), bucket_items in sorted(bucket_rows.items(), key=lambda item: (-len(item[1]), item[0][0], item[0][1])):
        buckets.append(
            {
                "bucket_type": bucket_type,
                "bucket_key": bucket_key,
                "description": bucket_descriptions[(bucket_type, bucket_key)],
                "status": "ambiguous" if bucket_type not in INVALID_ANOMALIES else "invalid",
                "row_count": len(bucket_items),
                "sample_rows": [item.to_sample() for item in bucket_items[:5]],
            }
        )

    return {
        "source_file": source_file,
        "summary": {
            "total_rows": len(rows),
            "valid_rows": status_counts["valid"],
            "valid_exception_rows": status_counts["valid_exception"],
            "ambiguous_rows": status_counts["ambiguous"],
            "invalid_rows": status_counts["invalid"],
            "included_rows": status_counts["valid"] + status_counts["valid_exception"],
            "excluded_rows": status_counts["ambiguous"] + status_counts["invalid"],
            "unique_students": len({row.student_hash for row in rows if row.student_hash}),
            "review_bucket_count": len(buckets),
        },
        "anomaly_counts": dict(sorted(anomaly_counts.items())),
        "semester_digit_counts": dict(sorted(semester_digit_counts.items())),
        "buckets": buckets,
    }


def analyze_enrollment_csv(path: str = str(DEFAULT_ENROLLMENT_CSV), rules: list[ReviewRule] | None = None) -> dict:
    rows = _iter_rows(path)
    if rules:
        _apply_rules(rows, rules)
    return _analysis_payload(rows, str(Path(path)))


def _latest_academic_year(rows: list[StagedEnrollmentRow]) -> str | None:
    years = {row.academic_year for row in rows if row.academic_year and ACADEMIC_YEAR_RE.match(row.academic_year)}
    if not years:
        return None
    return max(years, key=_parse_academic_year)


def _synthetic_rooms() -> list[dict]:
    return [
        {"client_key": "room_auditorium", "name": "Auditorium", "capacity": 400, "room_type": "lecture", "lab_type": None, "location": "Faculty Central", "year_restriction": None},
        {"client_key": "room_a11_201", "name": "A11 201", "capacity": 150, "room_type": "lecture", "lab_type": None, "location": "A11 Complex", "year_restriction": None},
        {"client_key": "room_a7_406", "name": "A7 406", "capacity": 120, "room_type": "lecture", "lab_type": None, "location": "A7 Complex", "year_restriction": None},
        {"client_key": "room_bio_lab_1", "name": "Biology Lab 1", "capacity": 30, "room_type": "lab", "lab_type": "biology", "location": "Science Block", "year_restriction": None},
        {"client_key": "room_chem_lab_1", "name": "Chemistry Lab 1", "capacity": 30, "room_type": "lab", "lab_type": "chemistry", "location": "Science Block", "year_restriction": None},
        {"client_key": "room_comp_lab_1", "name": "Computer Lab 1", "capacity": 40, "room_type": "lab", "lab_type": "computer", "location": "A11 Complex", "year_restriction": None},
        {"client_key": "room_phys_lab_1", "name": "Physics Lab 1", "capacity": 40, "room_type": "lab", "lab_type": "physics", "location": "Science Block", "year_restriction": None},
        {"client_key": "room_stats_lab_1", "name": "Statistics Lab 1", "capacity": 30, "room_type": "lab", "lab_type": "statistics", "location": "A11 Complex", "year_restriction": None},
        {"client_key": "room_elec_lab_1", "name": "Electronics Lab 1", "capacity": 32, "room_type": "lab", "lab_type": "electronics", "location": "Electronics Block", "year_restriction": None},
    ]


def build_reviewed_import_projection(
    path: str = str(DEFAULT_ENROLLMENT_CSV),
    rules: list[ReviewRule] | None = None,
    target_academic_year: str | None = None,
    allowed_attempts: tuple[str, ...] = DEFAULT_ATTEMPTS,
) -> dict:
    rows = _iter_rows(path)
    if rules:
        _apply_rules(rows, rules)
    analysis = _analysis_payload(rows, str(Path(path)))

    included_rows = [row for row in rows if row.status in {"valid", "valid_exception"}]
    if target_academic_year is None:
        target_academic_year = _latest_academic_year(included_rows)
    projected_rows = [
        row
        for row in included_rows
        if (not target_academic_year or row.academic_year == target_academic_year)
        and (not allowed_attempts or row.attempt in allowed_attempts)
    ]

    degrees = []
    degree_keys: dict[str, str] = {}
    for stream in sorted({row.stream for row in projected_rows}):
        client_key = f"degree_{_slug(stream)}"
        degree_keys[stream] = client_key
        degrees.append(
            {
                "client_key": client_key,
                "code": stream,
                "name": STREAM_NAME_MAP.get(stream, stream),
                "duration_years": max(int(row.year) for row in projected_rows if row.stream == stream and row.year.isdigit()),
                "intake_label": f"{stream} Intake",
            }
        )

    paths = []
    path_keys: dict[tuple[str, str, str], str] = {}
    for row in projected_rows:
        effective_path = row.effective_course_path_no
        if not effective_path:
            continue
        key = (row.stream, row.year, effective_path)
        if key in path_keys:
            continue
        client_key = f"path_{_slug(row.stream)}_y{row.year}_p{_slug(effective_path)}"
        path_keys[key] = client_key
        paths.append(
            {
                "client_key": client_key,
                "degree_client_key": degree_keys[row.stream],
                "year": int(row.year),
                "code": f"{row.stream}-P{effective_path}",
                "name": f"{row.stream} Year {row.year} Path {effective_path}",
            }
        )

    module_years: dict[str, set[int]] = defaultdict(set)
    for row in projected_rows:
        if row.year.isdigit():
            module_years[row.course_code].add(int(row.year))
    modules = []
    module_client_keys: dict[tuple[str, int], str] = {}
    module_display_codes: dict[tuple[str, int], str] = {}
    for course_code, years in sorted(module_years.items()):
        for year in sorted(years):
            key = (course_code, year)
            client_key = f"mod_{_slug(course_code)}_y{year}"
            module_client_keys[key] = client_key
            display_code = course_code if len(years) == 1 else f"{course_code} [Y{year}]"
            module_display_codes[key] = display_code
            sample_row = next(row for row in projected_rows if row.course_code == course_code and int(row.year) == year)
            modules.append(
                {
                    "client_key": client_key,
                    "code": display_code,
                    "name": course_code,
                    "subject_name": sample_row.module_subject_code or course_code.split()[0],
                    "year": year,
                    "semester": sample_row.module_nominal_semester or 1,
                    "is_full_year": bool(sample_row.is_full_year),
                }
            )

    audience_members: dict[tuple[str, str, str, str | None, str], set[str]] = defaultdict(set)
    for row in projected_rows:
        audience_members[(row.stream, row.year, row.batch, row.effective_course_path_no, row.course_code)].add(row.student_hash)

    student_groups = []
    group_keys: dict[tuple[str, str, str, str | None, str], str] = {}
    for key, members in sorted(audience_members.items()):
        stream, year, batch, effective_path, course_code = key
        client_key = f"group_{_slug(stream)}_y{year}_b{_slug(batch)}_p{_slug(effective_path or 'common')}_{_slug(course_code)}"
        group_keys[key] = client_key
        label_path = f"Path {effective_path}" if effective_path else "Common"
        student_groups.append(
            {
                "client_key": client_key,
                "degree_client_key": degree_keys[stream],
                "path_client_key": path_keys.get((stream, year, effective_path)) if effective_path else None,
                "year": int(year),
                "name": f"{stream} Y{year} Batch {batch} {label_path} {course_code} Cohort",
                "size": len(members),
                "student_hashes": sorted(members),
            }
        )

    lecturers = []
    lecturer_keys: dict[str, str] = {}
    for subject in sorted({module["subject_name"] for module in modules}):
        client_key = f"lect_{_slug(subject)}_1"
        lecturer_keys[subject] = client_key
        lecturers.append(
            {
                "client_key": client_key,
                "name": f"{subject} Lecturer 1",
                "email": f"{_slug(subject)}.1@science.kln.ac.lk",
            }
        )

    sessions = []
    for key, client_key in sorted(module_client_keys.items()):
        course_code, year = key
        linked_groups = [
            group_keys[audience_key]
            for audience_key in sorted(group_keys)
            if audience_key[0] in degree_keys and audience_key[1] == str(year) and audience_key[4] == course_code
        ]
        audience_size = sum(
            next(group["size"] for group in student_groups if group["client_key"] == group_key)
            for group_key in linked_groups
        )
        subject = next(module["subject_name"] for module in modules if module["client_key"] == client_key)
        sessions.append(
            {
                "client_key": f"session_{_slug(course_code)}_y{year}_lecture",
                "module_client_key": client_key,
                "linked_module_client_keys": [],
                "name": f"{course_code} Lecture",
                "session_type": "lecture",
                "duration_minutes": _synthetic_lecture_duration(course_code, audience_size),
                "occurrences_per_week": 1,
                "required_room_type": "lecture",
                "required_lab_type": None,
                "specific_room_client_key": None,
                "max_students_per_group": None,
                "allow_parallel_rooms": False,
                "notes": f"Reviewed import projection for {target_academic_year or 'current'}",
                "lecturer_client_keys": [lecturer_keys[subject]],
                "student_group_client_keys": linked_groups,
            }
        )
        lab_type = _synthetic_lab_type(subject, course_code, year, audience_size)
        if lab_type:
            sessions.append(
                {
                    "client_key": f"session_{_slug(course_code)}_y{year}_lab",
                    "module_client_key": client_key,
                    "linked_module_client_keys": [],
                    "name": f"{course_code} Lab",
                    "session_type": "lab",
                    "duration_minutes": 180,
                    "occurrences_per_week": 1,
                    "required_room_type": "lab",
                    "required_lab_type": lab_type,
                    "specific_room_client_key": None,
                    "max_students_per_group": LAB_SPLIT_LIMIT_BY_TYPE[lab_type],
                    "allow_parallel_rooms": False,
                    "notes": f"Reviewed import projection for {target_academic_year or 'current'}",
                    "lecturer_client_keys": [lecturer_keys[subject]],
                    "student_group_client_keys": linked_groups,
                }
            )

    dataset = {
        "degrees": degrees,
        "paths": sorted(paths, key=lambda item: (item["degree_client_key"], item["year"], item["code"])),
        "lecturers": lecturers,
        "rooms": _synthetic_rooms(),
        "student_groups": student_groups,
        "modules": modules,
        "sessions": sessions,
    }
    return {
        "analysis": analysis,
        "target_academic_year": target_academic_year,
        "allowed_attempts": list(allowed_attempts),
        "projection_summary": {
            "projected_rows": len(projected_rows),
            "excluded_rows": len(rows) - len(projected_rows),
            "degrees": len(dataset["degrees"]),
            "paths": len(dataset["paths"]),
            "lecturers": len(dataset["lecturers"]),
            "rooms": len(dataset["rooms"]),
            "student_groups": len(dataset["student_groups"]),
            "modules": len(dataset["modules"]),
            "sessions": len(dataset["sessions"]),
        },
        "dataset": dataset,
    }


def parse_review_rules(raw_rules: list[dict] | None) -> list[ReviewRule]:
    if not raw_rules:
        return []
    return [ReviewRule(**rule) for rule in raw_rules]


def encode_student_hashes(student_hashes: list[str]) -> str | None:
    if not student_hashes:
        return None
    return json.dumps(sorted(set(student_hashes)))


def decode_student_hashes(value: str | None) -> list[str]:
    if not value:
        return []
    try:
        decoded = json.loads(value)
    except json.JSONDecodeError:
        return []
    if not isinstance(decoded, list):
        return []
    return [str(item) for item in decoded if str(item).strip()]
