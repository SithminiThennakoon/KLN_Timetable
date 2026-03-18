from __future__ import annotations

import csv
import io


IMPORT_TEMPLATES: dict[str, dict] = {
    "student_enrollments": {
        "filename": "student_enrollments_template.csv",
        "label": "Student Enrollments",
        "description": "Student-to-module enrollment facts imported from the university system.",
        "columns": [
            "CoursePathNo",
            "CourseCode",
            "Year",
            "AcYear",
            "Attempt",
            "stream",
            "batch",
            "student_hash",
        ],
        "rows": [
            ["1", "CHEM 11612", "1", "2022/2023", "1", "PS", "2022", "stu_hash_0001"],
            ["1", "AMAT 11113", "1", "2022/2023", "1", "PS", "2022", "stu_hash_0001"],
        ],
    },
    "rooms": {
        "filename": "rooms_template.csv",
        "label": "Rooms",
        "description": "Teaching rooms, capacities, and room capabilities used by the solver.",
        "columns": [
            "room_code",
            "room_name",
            "capacity",
            "room_type",
            "lab_type",
            "location",
            "year_restriction",
        ],
        "rows": [
            ["A7-H1", "A7 Hall 1", "180", "lecture", "", "A7 Building", ""],
            ["CHEM-LAB-1", "Chemistry Lab 1", "30", "lab", "chemistry", "Science Block", ""],
        ],
    },
    "lecturers": {
        "filename": "lecturers_template.csv",
        "label": "Lecturers",
        "description": "Lecturer identities used for staffing sessions.",
        "columns": ["lecturer_code", "name", "email"],
        "rows": [
            ["LECT-CHEM-01", "Dr. Silva", "silva@example.edu"],
            ["LECT-MATH-01", "Prof. Perera", "perera@example.edu"],
        ],
    },
    "modules": {
        "filename": "modules_template.csv",
        "label": "Modules",
        "description": "Optional module metadata when enrollment-derived details are not enough.",
        "columns": [
            "module_code",
            "module_name",
            "subject_name",
            "nominal_year",
            "semester_bucket",
            "is_full_year",
        ],
        "rows": [
            ["CHEM 11612", "Foundations of Chemistry", "Chemistry", "1", "1", "false"],
            ["AMAT 11113", "Calculus I", "Applied Mathematics", "1", "1", "false"],
        ],
    },
    "sessions": {
        "filename": "sessions_template.csv",
        "label": "Sessions",
        "description": "Actual teachable session definitions required before generation can run.",
        "columns": [
            "session_code",
            "module_code",
            "session_name",
            "session_type",
            "duration_minutes",
            "occurrences_per_week",
            "required_room_type",
            "required_lab_type",
            "specific_room_code",
            "max_students_per_group",
            "allow_parallel_rooms",
            "notes",
        ],
        "rows": [
            [
                "CHEM11612-LEC",
                "CHEM 11612",
                "Chemistry Lecture",
                "lecture",
                "120",
                "2",
                "lecture",
                "",
                "",
                "",
                "false",
                "Main weekly lecture",
            ],
            [
                "CHEM11612-LAB",
                "CHEM 11612",
                "Chemistry Lab",
                "lab",
                "180",
                "1",
                "lab",
                "chemistry",
                "CHEM-LAB-1",
                "30",
                "true",
                "Split if needed by lab capacity",
            ],
        ],
    },
    "session_lecturers": {
        "filename": "session_lecturers_template.csv",
        "label": "Session Lecturers",
        "description": "Many-to-many links between sessions and lecturers.",
        "columns": ["session_code", "lecturer_code"],
        "rows": [
            ["CHEM11612-LEC", "LECT-CHEM-01"],
            ["CHEM11612-LAB", "LECT-CHEM-01"],
        ],
    },
}


def list_import_templates() -> list[dict]:
    return [
        {
            "name": name,
            "filename": template["filename"],
            "label": template["label"],
            "description": template["description"],
            "columns": list(template["columns"]),
        }
        for name, template in IMPORT_TEMPLATES.items()
    ]


def get_import_template(name: str) -> dict | None:
    template = IMPORT_TEMPLATES.get(name)
    if template is None:
        return None
    return {
        "name": name,
        "filename": template["filename"],
        "label": template["label"],
        "description": template["description"],
        "columns": list(template["columns"]),
        "rows": [list(row) for row in template["rows"]],
    }


def render_import_template_csv(name: str) -> tuple[str, str] | None:
    template = get_import_template(name)
    if template is None:
        return None

    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(template["columns"])
    writer.writerows(template["rows"])
    return template["filename"], buffer.getvalue()
