from __future__ import annotations

import csv
import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[3]
DEFAULT_ENROLLMENT_CSV = ROOT_DIR / "students_processed_TT_J.csv"
ACADEMIC_YEAR_RE = re.compile(r"^(?P<start>\d{4})/(?P<end>\d{4})$")
COURSE_CODE_RE = re.compile(r"^(?P<prefix>[A-Z]+)\s+(?P<digits>\d{5})$")
MIN_COHORT_SIZE = 0
MAX_COURSES_PER_STREAM_YEAR_SEMESTER = 100
TARGET_WEEKLY_LECTURER_HOURS = 35
PATH_CORE_PARTICIPATION_THRESHOLD = 0.8
OPTIONAL_MODULE_CODES = {
    # Handbook-audited optional BECS modules. The realistic demo should treat
    # them as non-mandatory demand unless explicitly modeled separately.
    "BECS 11722",
    "BECS 12742",
    "BECS 21722",
    "BECS 21732",
}

STREAM_NAME_MAP = {
    "AC": "Applied Chemistry",
    "BS": "Biological Science",
    "EC": "Electronics and Computer Science",
    "EM": "Environmental Management",
    "PE": "Physics and Electronics",
    "PS": "Physical Science",
}

LAB_TYPE_BY_PREFIX = {
    "APCH": "chemistry",
    "BIOL": "biology",
    "CHEM": "chemistry",
    "CMSK": "computer",
    "COSC": "computer",
    "ELEC": "electronics",
    "PHYS": "physics",
    "SENG": "computer",
    "STAT": "statistics",
}

EXPLICIT_LAB_MODULE_TYPES = {
    # BECS explicit laboratory units from UoK handbooks / detailed curriculum.
    "BECS 11431": "electronics",
    "BECS 12451": "electronics",
    "BECS 21431": "electronics",
    "BECS 22451": "electronics",
    "BECS 31421": "electronics",
    "BECS 32451": "electronics",
}

LAB_SPLIT_LIMIT_BY_TYPE = {
    "biology": 30,
    "chemistry": 30,
    "computer": 40,
    "electronics": 32,
    "physics": 40,
    "statistics": 30,
}


@dataclass(frozen=True)
class EnrollmentRecord:
    course_path_no: str
    course_code: str
    year: int
    academic_year: str
    attempt: str
    stream: str
    batch: str
    student_hash: str


def _parse_academic_year(value: str) -> tuple[int, int]:
    match = ACADEMIC_YEAR_RE.match(value.strip())
    if not match:
        return (0, 0)
    return (int(match.group("start")), int(match.group("end")))


def _course_parts(course_code: str) -> tuple[str, int | None, str | None]:
    match = COURSE_CODE_RE.match(course_code.strip())
    if not match:
        return (course_code.strip() or "GEN", None, None)
    digits = match.group("digits")
    return (match.group("prefix"), int(digits[0]), digits[1])


def _normalize_semester_bucket(value: str | None) -> int:
    if value in {"2", "4"}:
        return 2
    return 1


def _course_semester_bucket(course_code: str) -> int:
    _, _, inferred_semester = _course_parts(course_code)
    return _normalize_semester_bucket(inferred_semester)


def _stable_mod(value: str, divisor: int) -> int:
    return sum(ord(char) for char in value) % divisor


def _is_default_mandatory_demo_course(course_code: str) -> bool:
    return course_code not in OPTIONAL_MODULE_CODES


def _synthetic_lecture_duration(course_code: str, audience_size: int) -> int:
    if audience_size >= 250 or _stable_mod(course_code, 4) == 0:
        return 120
    return 60


def _synthetic_lab_type(prefix: str, course_code: str, year: int, audience_size: int) -> str | None:
    explicit_lab_type = EXPLICIT_LAB_MODULE_TYPES.get(course_code)
    if explicit_lab_type:
        return explicit_lab_type
    lab_type = LAB_TYPE_BY_PREFIX.get(prefix)
    if not lab_type:
        return None
    max_audience_by_lab_type = {
        "biology": 90,
        "chemistry": 90,
        "computer": 120,
        "electronics": 96,
        "physics": 120,
        "statistics": 90,
    }
    if audience_size > max_audience_by_lab_type[lab_type]:
        return None
    if year >= 4 and _stable_mod(course_code, 2) == 1:
        return None
    if prefix in {"CMSK", "COSC", "SENG"} and _stable_mod(course_code, 3) != 0:
        return None
    return lab_type


def _split_assignment_count(group_sizes: list[int], limit: int | None) -> int:
    if not group_sizes:
        return 1
    total = sum(group_sizes)
    if not limit or total <= limit:
        return 1

    split_count = 0
    current_total = 0
    for size in sorted(group_sizes):
        remaining = int(size)
        while remaining > 0:
            available = limit - current_total
            if current_total > 0 and available == 0:
                split_count += 1
                current_total = 0
                available = limit
            fragment_size = min(remaining, available)
            current_total += fragment_size
            remaining -= fragment_size
            if current_total >= limit:
                split_count += 1
                current_total = 0

    if current_total > 0:
        split_count += 1
    return max(1, split_count)


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")


def load_enrollment_records(path: str = str(DEFAULT_ENROLLMENT_CSV)) -> tuple[EnrollmentRecord, ...]:
    csv_path = Path(path)
    if not csv_path.exists():
        raise FileNotFoundError(f"Enrollment CSV not found: {csv_path}")

    records: list[EnrollmentRecord] = []
    with csv_path.open(encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            course_code = (row.get("CourseCode") or "").strip()
            student_hash = (row.get("student_hash") or "").strip()
            stream = (row.get("stream") or "").strip()
            academic_year = (row.get("AcYear") or "").strip()
            year_value = (row.get("Year") or "").strip()
            if not all([course_code, student_hash, stream, academic_year, year_value]):
                continue
            try:
                year = int(year_value)
            except ValueError:
                continue
            records.append(
                EnrollmentRecord(
                    course_path_no=(row.get("CoursePathNo") or "").strip() or "0",
                    course_code=course_code,
                    year=year,
                    academic_year=academic_year,
                    attempt=(row.get("Attempt") or "").strip() or "1",
                    stream=stream,
                    batch=(row.get("batch") or "").strip() or "unknown",
                    student_hash=student_hash,
                )
            )
    return tuple(records)


def build_realistic_demo_dataset_from_enrollment_csv(
    path: str = str(DEFAULT_ENROLLMENT_CSV),
) -> dict:
    records = load_enrollment_records(path)
    if not records:
        raise ValueError("Enrollment CSV is empty.")

    latest_academic_year = max((record.academic_year for record in records), key=_parse_academic_year)
    current_records = [
        record
        for record in records
        if record.academic_year == latest_academic_year and record.attempt == "1"
    ]
    if not current_records:
        raise ValueError("Enrollment CSV did not contain current-year attempt-1 records.")

    semester_counts: Counter[int] = Counter(
        _course_semester_bucket(record.course_code) for record in current_records
    )
    selected_semester = max(
        semester_counts.items(), key=lambda item: (item[1], -item[0])
    )[0]
    current_records = [
        record
        for record in current_records
        if _course_semester_bucket(record.course_code) == selected_semester
    ]

    # Pick the largest batch for each stream/year/path to represent the current cohort.
    cohort_membership: dict[tuple[str, int, str, str], set[str]] = defaultdict(set)
    for record in current_records:
        cohort_membership[
            (record.stream, record.year, record.course_path_no, record.batch)
        ].add(record.student_hash)

    selected_batches: dict[tuple[str, int, str], tuple[str, set[str]]] = {}
    for (stream, year, path_no, batch), members in cohort_membership.items():
        if len(members) < MIN_COHORT_SIZE:
            continue
        key = (stream, year, path_no)
        current = selected_batches.get(key)
        if current is None or len(members) > len(current[1]) or (
            len(members) == len(current[1]) and batch > current[0]
        ):
            selected_batches[key] = (batch, members)

    if not selected_batches:
        raise ValueError("Enrollment CSV did not contain any cohorts large enough to seed the realistic demo.")

    path_numbers_by_stream_year: dict[tuple[str, int], set[str]] = defaultdict(set)
    for stream, year, path_no in selected_batches:
        path_numbers_by_stream_year[(stream, year)].add(path_no)

    degrees = []
    duration_by_stream: dict[str, int] = {}
    for stream, year, _ in selected_batches:
        duration_by_stream[stream] = max(duration_by_stream.get(stream, 0), year)

    degree_client_key_by_stream: dict[str, str] = {}
    for stream in sorted(duration_by_stream):
        client_key = f"degree_{_slug(stream)}"
        degree_client_key_by_stream[stream] = client_key
        degrees.append(
            {
                "client_key": client_key,
                "code": stream,
                "name": STREAM_NAME_MAP.get(stream, stream),
                "duration_years": duration_by_stream[stream],
                "intake_label": f"{stream} Intake",
            }
        )

    paths = []
    path_client_key_by_key: dict[tuple[str, int, str], str] = {}
    for (stream, year), path_numbers in sorted(path_numbers_by_stream_year.items()):
        create_paths = len(path_numbers) > 1 or any(path_no not in {"0", "1"} for path_no in path_numbers)
        if not create_paths:
            continue
        for path_no in sorted(path_numbers, key=lambda value: int(value) if value.isdigit() else value):
            client_key = f"path_{_slug(stream)}_y{year}_p{_slug(path_no)}"
            path_client_key_by_key[(stream, year, path_no)] = client_key
            paths.append(
                {
                    "client_key": client_key,
                    "degree_client_key": degree_client_key_by_stream[stream],
                    "year": year,
                    "code": f"{stream}-P{path_no}",
                    "name": f"{stream} Year {year} Path {path_no}",
                }
            )

    student_groups = []
    group_client_key_by_key: dict[tuple[str, int, str], str] = {}
    selected_students_to_group_keys: dict[str, set[str]] = defaultdict(set)
    group_meta_by_client_key: dict[str, dict[str, str | int | None]] = {}
    for (stream, year, path_no), (batch, members) in sorted(selected_batches.items()):
        group_client_key = f"group_{_slug(stream)}_y{year}_p{_slug(path_no)}"
        group_client_key_by_key[(stream, year, path_no)] = group_client_key
        for student_hash in members:
            selected_students_to_group_keys[student_hash].add(group_client_key)
        group_payload = {
            "client_key": group_client_key,
            "degree_client_key": degree_client_key_by_stream[stream],
            "path_client_key": path_client_key_by_key.get((stream, year, path_no)),
            "year": year,
            "name": f"{stream} Y{year} Batch {batch} Path {path_no}",
            "size": len(members),
        }
        group_meta_by_client_key[group_client_key] = {
            "stream": stream,
            "year": year,
            "path_no": path_no,
            "batch": batch,
            "degree_client_key": degree_client_key_by_stream[stream],
            "path_client_key": path_client_key_by_key.get((stream, year, path_no)),
            "name": group_payload["name"],
        }
        student_groups.append(group_payload)

    group_size_by_client_key = {
        group["client_key"]: int(group["size"]) for group in student_groups
    }

    course_students: dict[str, set[str]] = defaultdict(set)
    course_group_student_members: dict[str, dict[str, set[str]]] = defaultdict(
        lambda: defaultdict(set)
    )
    course_group_keys: dict[str, set[str]] = defaultdict(set)
    course_year: dict[str, int] = {}
    course_subject_prefix: dict[str, str] = {}
    stream_year_semester_course_counts: dict[tuple[str, int, int], Counter[str]] = defaultdict(Counter)

    for record in current_records:
        group_keys = selected_students_to_group_keys.get(record.student_hash)
        if not group_keys:
            continue
        prefix, inferred_year, inferred_semester = _course_parts(record.course_code)
        course_students[record.course_code].add(record.student_hash)
        for group_key in group_keys:
            course_group_student_members[record.course_code][group_key].add(record.student_hash)
        course_year[record.course_code] = record.year
        course_subject_prefix[record.course_code] = prefix
        semester_bucket = _normalize_semester_bucket(inferred_semester)
        stream_year_semester_course_counts[(record.stream, record.year, semester_bucket)][record.course_code] += 1

    subgroup_counter = 0
    for course_code, group_members in course_group_student_members.items():
        for group_key, enrolled_students in group_members.items():
            base_group_size = group_size_by_client_key[group_key]
            participation_ratio = len(enrolled_students) / base_group_size if base_group_size else 0
            if participation_ratio >= PATH_CORE_PARTICIPATION_THRESHOLD:
                course_group_keys[course_code].add(group_key)
                continue

            subgroup_counter += 1
            meta = group_meta_by_client_key[group_key]
            subgroup_client_key = f"group_{_slug(course_code)}_{subgroup_counter}"
            subgroup_payload = {
                "client_key": subgroup_client_key,
                "degree_client_key": meta["degree_client_key"],
                "path_client_key": meta["path_client_key"],
                "year": int(meta["year"]),
                "name": f"{meta['name']} {course_code} Cohort",
                "size": len(enrolled_students),
            }
            student_groups.append(subgroup_payload)
            group_size_by_client_key[subgroup_client_key] = len(enrolled_students)
            course_group_keys[course_code].add(subgroup_client_key)

    selected_courses: set[str] = set()
    for key, counter in stream_year_semester_course_counts.items():
        if not counter:
            # Fallback to any course in the same stream/year/semester bucket when no matching
            # code pattern is found in the current selection.
            for record in current_records:
                prefix, inferred_year, inferred_semester = _course_parts(record.course_code)
                semester_bucket = _normalize_semester_bucket(inferred_semester)
                if (
                    record.stream == key[0]
                    and record.year == key[1]
                    and semester_bucket == key[2]
                    and record.student_hash in selected_students_to_group_keys
                ):
                    counter[record.course_code] += 1
        if not counter:
            continue
        ranked_courses = sorted(
            counter.items(),
            key=lambda item: (
                -len(course_students[item[0]]),
                -len(course_group_keys[item[0]]),
                item[0],
            ),
        )
        for course_code, _ in ranked_courses[:MAX_COURSES_PER_STREAM_YEAR_SEMESTER]:
            selected_courses.add(course_code)

    selected_courses = {
        course_code
        for course_code in selected_courses
        if _is_default_mandatory_demo_course(course_code)
    }

    modules = []
    lecturer_prefixes = sorted({_course_parts(course_code)[0] for course_code in selected_courses})
    course_session_minutes: dict[str, int] = {}

    for course_code in sorted(selected_courses):
        prefix, inferred_year, inferred_semester = _course_parts(course_code)
        audience_size = sum(
            group_size_by_client_key[group_key] for group_key in course_group_keys[course_code]
        )
        lecture_duration = _synthetic_lecture_duration(course_code, audience_size)
        total_minutes = lecture_duration
        lab_type = _synthetic_lab_type(prefix, course_code, course_year[course_code], audience_size)
        if lab_type:
            split_limit = LAB_SPLIT_LIMIT_BY_TYPE[lab_type]
            group_sizes = [
                group_size_by_client_key[group_key]
                for group_key in course_group_keys[course_code]
            ]
            lab_split_count = _split_assignment_count(group_sizes, split_limit)
            total_minutes += 180 * lab_split_count
        course_session_minutes[course_code] = total_minutes
        modules.append(
            {
                "client_key": f"mod_{_slug(course_code)}",
                "code": course_code,
                "name": course_code,
                "subject_name": prefix,
                "year": inferred_year or course_year[course_code],
                "semester": _normalize_semester_bucket(inferred_semester),
                "is_full_year": False,
            }
        )

    lecturer_target_minutes = TARGET_WEEKLY_LECTURER_HOURS * 60
    lecturer_client_keys_by_prefix: dict[str, list[str]] = {}
    lecturers = []
    for prefix in lecturer_prefixes:
        prefix_courses = [
            course_code
            for course_code in selected_courses
            if _course_parts(course_code)[0] == prefix
        ]
        total_prefix_minutes = sum(course_session_minutes[course_code] for course_code in prefix_courses)
        lecturer_count = max(1, math.ceil(total_prefix_minutes / lecturer_target_minutes))
        prefix_keys = []
        for index in range(lecturer_count):
            client_key = f"lect_{_slug(prefix)}_{index + 1}"
            prefix_keys.append(client_key)
            lecturers.append(
                {
                    "client_key": client_key,
                    "name": f"{prefix} Lecturer {index + 1}",
                    "email": f"{_slug(prefix)}.{index + 1}@science.kln.ac.lk",
                }
            )
        lecturer_client_keys_by_prefix[prefix] = prefix_keys

    lecturer_assignment_by_course: dict[str, str] = {}
    lecturer_minutes_by_client_key = {lecturer["client_key"]: 0 for lecturer in lecturers}
    for prefix in lecturer_prefixes:
        prefix_courses = sorted(
            (
                course_code
                for course_code in selected_courses
                if _course_parts(course_code)[0] == prefix
            ),
            key=lambda course_code: (-course_session_minutes[course_code], course_code),
        )
        prefix_lecturers = lecturer_client_keys_by_prefix[prefix]
        for course_code in prefix_courses:
            assigned_lecturer = min(
                prefix_lecturers,
                key=lambda client_key: (lecturer_minutes_by_client_key[client_key], client_key),
            )
            lecturer_assignment_by_course[course_code] = assigned_lecturer
            lecturer_minutes_by_client_key[assigned_lecturer] += course_session_minutes[course_code]

    ranked_audience_sizes = sorted(
        (
            sum(group_size_by_client_key[group_key] for group_key in course_group_keys[course_code])
            for course_code in selected_courses
        ),
        reverse=True,
    )
    largest_audience = ranked_audience_sizes[0] if ranked_audience_sizes else 120
    second_largest_audience = (
        ranked_audience_sizes[1] if len(ranked_audience_sizes) > 1 else max(180, largest_audience // 2)
    )
    third_largest_audience = (
        ranked_audience_sizes[2] if len(ranked_audience_sizes) > 2 else max(120, second_largest_audience // 2)
    )

    rooms = [
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
            "client_key": "room_a7303",
            "name": "A7 303",
            "capacity": 100,
            "room_type": "lecture",
            "lab_type": None,
            "location": "A7 Complex",
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
            "client_key": "room_a7203",
            "name": "A7 203",
            "capacity": 120,
            "room_type": "lecture",
            "lab_type": None,
            "location": "A7 Complex",
            "year_restriction": None,
        },
        {
            "client_key": "room_a7205",
            "name": "A7 205",
            "capacity": 120,
            "room_type": "lecture",
            "lab_type": None,
            "location": "A7 Complex",
            "year_restriction": None,
        },
        {
            "client_key": "room_a11205",
            "name": "A11 205",
            "capacity": 100,
            "room_type": "lecture",
            "lab_type": None,
            "location": "A11 Complex",
            "year_restriction": None,
        },
        {
            "client_key": "room_b1214",
            "name": "B1 214",
            "capacity": 120,
            "room_type": "lecture",
            "lab_type": None,
            "location": "B1 Complex",
            "year_restriction": None,
        },
        {
            "client_key": "room_chemistry_lab",
            "name": "Chemistry Lab",
            "capacity": 30,
            "room_type": "lab",
            "lab_type": "chemistry",
            "location": "Science Labs",
            "year_restriction": None,
        },
        {
            "client_key": "room_chemistry_lab_2",
            "name": "Chemistry Lab 2",
            "capacity": 30,
            "room_type": "lab",
            "lab_type": "chemistry",
            "location": "Science Labs",
            "year_restriction": None,
        },
        {
            "client_key": "room_chemistry_lab_3",
            "name": "Chemistry Lab 3",
            "capacity": 30,
            "room_type": "lab",
            "lab_type": "chemistry",
            "location": "Science Labs",
            "year_restriction": None,
        },
        {
            "client_key": "room_physics_lab_1",
            "name": "Physics Lab 1",
            "capacity": 40,
            "room_type": "lab",
            "lab_type": "physics",
            "location": "Science Labs",
            "year_restriction": None,
        },
        {
            "client_key": "room_physics_lab_2",
            "name": "Physics Lab 2",
            "capacity": 40,
            "room_type": "lab",
            "lab_type": "physics",
            "location": "Science Labs",
            "year_restriction": None,
        },
        {
            "client_key": "room_physics_lab_3",
            "name": "Physics Lab 3",
            "capacity": 40,
            "room_type": "lab",
            "lab_type": "physics",
            "location": "Science Labs",
            "year_restriction": None,
        },
        {
            "client_key": "room_electronics_lab",
            "name": "Electronics Lab",
            "capacity": 32,
            "room_type": "lab",
            "lab_type": "electronics",
            "location": "Engineering Wing",
            "year_restriction": None,
        },
        {
            "client_key": "room_electronics_lab_2",
            "name": "Electronics Lab 2",
            "capacity": 32,
            "room_type": "lab",
            "lab_type": "electronics",
            "location": "Engineering Wing",
            "year_restriction": None,
        },
        {
            "client_key": "room_electronics_lab_3",
            "name": "Electronics Lab 3",
            "capacity": 32,
            "room_type": "lab",
            "lab_type": "electronics",
            "location": "Engineering Wing",
            "year_restriction": None,
        },
        {
            "client_key": "room_electronics_lab_4",
            "name": "Electronics Lab 4",
            "capacity": 32,
            "room_type": "lab",
            "lab_type": "electronics",
            "location": "Engineering Wing",
            "year_restriction": None,
        },
        {
            "client_key": "room_electronics_lab_5",
            "name": "Electronics Lab 5",
            "capacity": 32,
            "room_type": "lab",
            "lab_type": "electronics",
            "location": "Engineering Wing",
            "year_restriction": None,
        },
        {
            "client_key": "room_computer_lab_1",
            "name": "Computer Lab 1",
            "capacity": 40,
            "room_type": "lab",
            "lab_type": "computer",
            "location": "Computing Block",
            "year_restriction": None,
        },
        {
            "client_key": "room_computer_lab_3",
            "name": "Computer Lab 3",
            "capacity": 40,
            "room_type": "lab",
            "lab_type": "computer",
            "location": "Computing Block",
            "year_restriction": None,
        },
        {
            "client_key": "room_computer_lab_4",
            "name": "Computer Lab 4",
            "capacity": 40,
            "room_type": "lab",
            "lab_type": "computer",
            "location": "Computing Block",
            "year_restriction": None,
        },
        {
            "client_key": "room_computer_lab_2",
            "name": "Computer Lab 2",
            "capacity": 40,
            "room_type": "lab",
            "lab_type": "computer",
            "location": "Computing Block",
            "year_restriction": None,
        },
        {
            "client_key": "room_biology_lab",
            "name": "Biology Lab",
            "capacity": 30,
            "room_type": "lab",
            "lab_type": "biology",
            "location": "Science Labs",
            "year_restriction": None,
        },
        {
            "client_key": "room_statistics_lab",
            "name": "Statistics Lab",
            "capacity": 30,
            "room_type": "lab",
            "lab_type": "statistics",
            "location": "A11 Complex",
            "year_restriction": None,
        },
        {
            "client_key": "room_statistics_lab_2",
            "name": "Statistics Lab 2",
            "capacity": 30,
            "room_type": "lab",
            "lab_type": "statistics",
            "location": "A11 Complex",
            "year_restriction": None,
        },
    ]

    sessions = []
    for course_code in sorted(selected_courses):
        prefix = course_subject_prefix[course_code]
        year = course_year[course_code]
        audience_size = sum(
            group_size_by_client_key[group_key] for group_key in course_group_keys[course_code]
        )
        lecture_duration = _synthetic_lecture_duration(course_code, audience_size)
        assigned_lecturer = lecturer_assignment_by_course[course_code]
        sessions.append(
            {
                "client_key": f"session_{_slug(course_code)}_lecture",
                "module_client_key": f"mod_{_slug(course_code)}",
                "linked_module_client_keys": [],
                "name": f"{course_code} Lecture",
                "session_type": "lecture",
                "duration_minutes": lecture_duration,
                "occurrences_per_week": 1,
                "required_room_type": "lecture",
                "required_lab_type": None,
                "specific_room_client_key": None,
                "max_students_per_group": None,
                "allow_parallel_rooms": False,
                "notes": f"Seeded from real enrollment data for {latest_academic_year} semester {selected_semester}.",
                "lecturer_client_keys": [assigned_lecturer],
                "student_group_client_keys": sorted(course_group_keys[course_code]),
            }
        )
        lab_type = _synthetic_lab_type(prefix, course_code, year, audience_size)
        if lab_type:
            sessions.append(
                {
                    "client_key": f"session_{_slug(course_code)}_lab",
                    "module_client_key": f"mod_{_slug(course_code)}",
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
                    "notes": f"Synthetic laboratory block inferred from real enrollment data for {latest_academic_year} semester {selected_semester}.",
                    "lecturer_client_keys": [assigned_lecturer],
                    "student_group_client_keys": sorted(course_group_keys[course_code]),
                }
            )

    return {
        "degrees": degrees,
        "paths": paths,
        "lecturers": lecturers,
        "rooms": rooms,
        "student_groups": student_groups,
        "modules": modules,
        "sessions": sessions,
    }
