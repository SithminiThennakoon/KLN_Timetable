import os
import sys
import tempfile
import unittest
from pathlib import Path


TEST_DB_FILE = Path(tempfile.gettempdir()) / "kln_timetable_python_verifier_tests.sqlite"
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB_FILE}"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from verifiers.python_snapshot_verifier import verify_snapshot  # noqa: E402


def build_snapshot(*, room_capacity=80, include_overlap=False, friday_theory=False):
    first_day = "Friday" if friday_theory else "Monday"
    second_entry = {
        "shared_session_id": 2,
        "solution_entry_id": 2,
        "day": "Monday",
        "start_minute": 13 * 60,
        "duration_minutes": 120,
        "occurrence_index": 1,
        "split_index": 1,
        "room": {
            "id": 2,
            "name": "Lab 1",
            "capacity": 30,
            "room_type": "lab",
            "lab_type": "chemistry",
            "location": "Science Block",
            "year_restriction": None,
        },
        "lecturer_ids": [2],
        "curriculum_module_ids": [2],
        "attendance_group_ids": [2],
    }
    if include_overlap:
        second_entry = {
            **second_entry,
            "day": first_day,
            "start_minute": 8 * 60 + 30,
            "room": {
                "id": 1,
                "name": "Hall A",
                "capacity": room_capacity,
                "room_type": "lecture",
                "lab_type": None,
                "location": "Main Building",
                "year_restriction": None,
            },
            "lecturer_ids": [1],
            "attendance_group_ids": [1],
        }

    return {
        "selected_soft_constraints": [
            "prefer_morning_theory",
            "avoid_friday_sessions",
        ],
        "rooms": [
            {
                "id": 1,
                "name": "Hall A",
                "capacity": room_capacity,
                "room_type": "lecture",
                "lab_type": None,
                "location": "Main Building",
                "year_restriction": None,
            },
            {
                "id": 2,
                "name": "Lab 1",
                "capacity": 30,
                "room_type": "lab",
                "lab_type": "chemistry",
                "location": "Science Block",
                "year_restriction": None,
            },
        ],
        "attendance_groups": [
            {
                "id": 1,
                "label": "PS Y1 P1",
                "study_year": 1,
                "student_count": 40,
                "student_hashes": [f"s-{index}" for index in range(40)],
            },
            {
                "id": 2,
                "label": "AC Y2 P1",
                "study_year": 2,
                "student_count": 20,
                "student_hashes": [f"a-{index}" for index in range(20)],
            },
        ],
        "shared_sessions": [
            {
                "id": 1,
                "name": "CHEM 101 Lecture",
                "session_type": "lecture",
                "duration_minutes": 120,
                "occurrences_per_week": 1,
                "required_room_type": "lecture",
                "required_lab_type": None,
                "specific_room_id": None,
                "lecturer_ids": [1],
                "attendance_group_ids": [1],
                "curriculum_module_ids": [1],
            },
            {
                "id": 2,
                "name": "CHEM 101 Lab",
                "session_type": "lab",
                "duration_minutes": 120,
                "occurrences_per_week": 1,
                "required_room_type": "lab",
                "required_lab_type": "chemistry",
                "specific_room_id": 2,
                "lecturer_ids": [2],
                "attendance_group_ids": [2],
                "curriculum_module_ids": [2],
            },
        ],
        "timetable_entries": [
            {
                "shared_session_id": 1,
                "solution_entry_id": 1,
                "day": first_day,
                "start_minute": 8 * 60,
                "duration_minutes": 120,
                "occurrence_index": 1,
                "split_index": 1,
                "room": {
                    "id": 1,
                    "name": "Hall A",
                    "capacity": room_capacity,
                    "room_type": "lecture",
                    "lab_type": None,
                    "location": "Main Building",
                    "year_restriction": None,
                },
                "lecturer_ids": [1],
                "curriculum_module_ids": [1],
                "attendance_group_ids": [1],
            },
            second_entry,
        ],
    }


class PythonSnapshotVerifierTests(unittest.TestCase):
    def test_valid_snapshot_passes_hard_checks(self):
        result = verify_snapshot(build_snapshot())
        self.assertTrue(result["hard_valid"])
        self.assertEqual(result["hard_violations"], [])

    def test_capacity_violation_is_reported(self):
        result = verify_snapshot(build_snapshot(room_capacity=20))
        self.assertFalse(result["hard_valid"])
        self.assertTrue(
            any(
                item["constraint"] == "room_capacity_compatibility"
                for item in result["hard_violations"]
            )
        )

    def test_overlap_violation_is_reported(self):
        result = verify_snapshot(build_snapshot(include_overlap=True))
        self.assertFalse(result["hard_valid"])
        self.assertTrue(
            any(
                item["constraint"] == "no_room_overlap"
                for item in result["hard_violations"]
            )
        )
        self.assertTrue(
            any(
                item["constraint"] == "no_lecturer_overlap"
                for item in result["hard_violations"]
            )
        )
        self.assertTrue(
            any(
                item["constraint"] == "no_student_overlap"
                for item in result["hard_violations"]
            )
        )

    def test_selected_soft_constraints_are_summarized(self):
        result = verify_snapshot(build_snapshot(friday_theory=True))
        soft_by_key = {item["key"]: item for item in result["soft_summary"]}
        self.assertIn("avoid_friday_sessions", soft_by_key)
        self.assertFalse(soft_by_key["avoid_friday_sessions"]["satisfied"])


if __name__ == "__main__":
    unittest.main()
