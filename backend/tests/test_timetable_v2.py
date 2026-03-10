import os
import sys
import tempfile
import unittest
from itertools import chain, repeat
from pathlib import Path
from unittest.mock import patch


TEST_DB_FILE = Path(tempfile.gettempdir()) / "kln_timetable_v2_tests.sqlite"
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB_FILE}"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.database import Base, SessionLocal, engine  # noqa: E402
from app.services.timetable_v2 import (  # noqa: E402
    SessionTask,
    build_view_payload,
    export_view,
    generate_timetables,
    get_latest_run,
    list_soft_constraint_options,
    serialize_generation_run,
    set_default_solution,
)
from app.services.timetable_v2 import replace_dataset  # noqa: E402
from app.services import timetable_v2 as timetable_v2_service  # noqa: E402
from app.schemas.v2 import DatasetUpsertRequest  # noqa: E402


def build_dataset(
    group_size=80,
    room_capacity=120,
    split_limit=None,
    allow_parallel_rooms=False,
    room_count=1,
    lecturer_count=1,
    occurrences_per_week=1,
):
    rooms = []
    for index in range(room_count):
        rooms.append(
            {
                "client_key": f"room_{index + 1}",
                "name": f"Room {index + 1}",
                "capacity": room_capacity,
                "room_type": "lab",
                "lab_type": "chem_lab",
                "location": "Science Block",
                "year_restriction": None,
            }
        )

    lecturers = []
    for index in range(lecturer_count):
        lecturers.append(
            {
                "client_key": f"lect_{index + 1}",
                "name": f"Lecturer {index + 1}",
                "email": f"lect{index + 1}@example.com",
            }
        )

    return {
        "degrees": [
            {
                "client_key": "degree_ps",
                "code": "PS",
                "name": "Physical Science",
                "duration_years": 3,
                "intake_label": "PS Intake",
            }
        ],
        "paths": [
            {
                "client_key": "path_ps_y1",
                "degree_client_key": "degree_ps",
                "year": 1,
                "code": "PHY-MATH-STAT",
                "name": "Physics Mathematics Statistics",
            }
        ],
        "lecturers": lecturers,
        "rooms": rooms,
        "student_groups": [
            {
                "client_key": "group_main",
                "degree_client_key": "degree_ps",
                "path_client_key": "path_ps_y1",
                "year": 1,
                "name": "PS Y1 Main",
                "size": group_size,
            }
        ],
        "modules": [
            {
                "client_key": "module_chem",
                "code": "CHEM101",
                "name": "Foundations of Chemistry",
                "subject_name": "Chemistry",
                "year": 1,
                "semester": 1,
                "is_full_year": False,
            }
        ],
        "sessions": [
            {
                "client_key": "session_chem_lab",
                "module_client_key": "module_chem",
                "name": "Chemistry Lab",
                "session_type": "practical",
                "duration_minutes": 180,
                "occurrences_per_week": occurrences_per_week,
                "required_room_type": "lab",
                "required_lab_type": "chem_lab",
                "specific_room_client_key": None,
                "max_students_per_group": split_limit,
                "allow_parallel_rooms": allow_parallel_rooms,
                "notes": None,
                "lecturer_client_keys": [item["client_key"] for item in lecturers],
                "student_group_client_keys": ["group_main"],
            }
        ],
    }


def build_mock_task() -> SessionTask:
    return SessionTask(
        session_id=1,
        session_name="Chemistry Lab",
        session_type="lab",
        module_id=1,
        module_code="CHEM101",
        module_name="Foundations of Chemistry",
        occurrence_index=1,
        split_index=1,
        duration_minutes=180,
        required_room_type="lab",
        required_lab_type="chem_lab",
        specific_room_id=1,
        lecturer_ids=(1,),
        student_group_ids=(1,),
        student_count=40,
        root_session_id=1,
        bundle_key=None,
    )


class TimetableV2Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)

    def setUp(self):
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
        self.db = SessionLocal()

    def tearDown(self):
        self.db.close()

    def test_infeasible_generation_reports_room_diagnostics(self):
        payload = DatasetUpsertRequest(**build_dataset(room_capacity=20, split_limit=None))
        replace_dataset(self.db, payload)

        run = generate_timetables(
            self.db,
            selected_soft_constraints=[],
            max_solutions=10,
            preview_limit=3,
            time_limit_seconds=10,
        )

        self.assertEqual(run.status, "infeasible")
        self.assertIn("Diagnostics:", run.message)
        self.assertIn("CHEM101 / Chemistry Lab", run.message)
        self.assertIn("no room", run.message.lower())

    def test_generation_splits_single_large_group_into_internal_parts(self):
        payload = DatasetUpsertRequest(**build_dataset(room_capacity=40, split_limit=40, room_count=2))
        replace_dataset(self.db, payload)

        run = generate_timetables(
            self.db,
            selected_soft_constraints=[],
            max_solutions=10,
            preview_limit=2,
            time_limit_seconds=10,
        )
        serialized = serialize_generation_run(get_latest_run(self.db))

        self.assertIn(run.status, {"optimal", "feasible"})
        self.assertGreaterEqual(serialized["counts"]["total_solutions_found"], 1)
        entry_group_names = [
            group_name
            for entry in serialized["solutions"][0]["entries"]
            for group_name in entry["student_group_names"]
        ]
        self.assertTrue(any("Part 1" in name for name in entry_group_names))
        self.assertTrue(any("Part 2" in name for name in entry_group_names))

    def test_default_solution_can_be_switched_between_preview_solutions(self):
        payload = DatasetUpsertRequest(**build_dataset(room_capacity=120, room_count=2))
        replace_dataset(self.db, payload)

        generate_timetables(
            self.db,
            selected_soft_constraints=[],
            max_solutions=20,
            preview_limit=2,
            time_limit_seconds=10,
        )
        run = get_latest_run(self.db)
        self.assertIsNotNone(run)
        self.assertGreaterEqual(len(run.solutions), 2)

        second_solution = sorted(run.solutions, key=lambda item: item.ordinal)[1]
        set_default_solution(self.db, int(second_solution.id))

        refreshed = get_latest_run(self.db)
        defaults = [solution for solution in refreshed.solutions if solution.is_default]
        self.assertEqual(len(defaults), 1)
        self.assertEqual(int(defaults[0].id), int(second_solution.id))

    def test_parallel_room_session_succeeds_with_matching_rooms_and_lecturers(self):
        payload = DatasetUpsertRequest(
            **build_dataset(
                room_capacity=40,
                split_limit=40,
                allow_parallel_rooms=True,
                room_count=2,
                lecturer_count=2,
            )
        )
        replace_dataset(self.db, payload)

        generate_timetables(
            self.db,
            selected_soft_constraints=[],
            max_solutions=10,
            preview_limit=2,
            time_limit_seconds=10,
        )
        serialized = serialize_generation_run(get_latest_run(self.db))

        self.assertGreaterEqual(serialized["counts"]["total_solutions_found"], 1)
        entries = serialized["solutions"][0]["entries"]
        self.assertEqual(len(entries), 2)
        slot_keys = {(entry["day"], entry["start_minute"]) for entry in entries}
        self.assertEqual(len(slot_keys), 1)

    def test_parallel_room_session_reports_lecturer_shortage(self):
        payload = DatasetUpsertRequest(
            **build_dataset(
                room_capacity=40,
                split_limit=40,
                allow_parallel_rooms=True,
                room_count=2,
                lecturer_count=1,
            )
        )
        replace_dataset(self.db, payload)

        run = generate_timetables(
            self.db,
            selected_soft_constraints=[],
            max_solutions=10,
            preview_limit=2,
            time_limit_seconds=10,
        )

        self.assertEqual(run.status, "infeasible")
        self.assertIn("Parallel-room sessions need at least one lecturer", run.message)

    def test_generation_marks_truncation_when_solution_limit_is_hit(self):
        payload = DatasetUpsertRequest(
            **build_dataset(room_capacity=120, room_count=2, occurrences_per_week=1)
        )
        replace_dataset(self.db, payload)

        generate_timetables(
            self.db,
            selected_soft_constraints=[],
            max_solutions=1,
            preview_limit=1,
            time_limit_seconds=10,
        )
        serialized = serialize_generation_run(get_latest_run(self.db))

        self.assertTrue(serialized["counts"]["truncated"])
        self.assertEqual(serialized["counts"]["preview_solution_count"], 1)
        self.assertTrue(serialized["solutions"][0]["is_representative"])

    def test_student_view_filters_entries_by_degree_and_path(self):
        payload = DatasetUpsertRequest(
            **{
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
                        "client_key": "path_ps_y1",
                        "degree_client_key": "degree_ps",
                        "year": 1,
                        "code": "PHY-MATH-STAT",
                        "name": "Physics Mathematics Statistics",
                    },
                    {
                        "client_key": "path_bs_y1",
                        "degree_client_key": "degree_bs",
                        "year": 1,
                        "code": "ZOO-CHEM-MICRO",
                        "name": "Zoology Chemistry Microbiology",
                    },
                ],
                "lecturers": [
                    {
                        "client_key": "lect_1",
                        "name": "Lecturer 1",
                        "email": "lect1@example.com",
                    }
                ],
                "rooms": [
                    {
                        "client_key": "room_1",
                        "name": "Room 1",
                        "capacity": 200,
                        "room_type": "lab",
                        "lab_type": "chem_lab",
                        "location": "Science Block",
                        "year_restriction": None,
                    }
                ],
                "student_groups": [
                    {
                        "client_key": "group_ps",
                        "degree_client_key": "degree_ps",
                        "path_client_key": "path_ps_y1",
                        "year": 1,
                        "name": "PS Y1 Main",
                        "size": 50,
                    },
                    {
                        "client_key": "group_bs",
                        "degree_client_key": "degree_bs",
                        "path_client_key": "path_bs_y1",
                        "year": 1,
                        "name": "BS Y1 Main",
                        "size": 45,
                    },
                ],
                "modules": [
                    {
                        "client_key": "module_chem",
                        "code": "CHEM101",
                        "name": "Foundations of Chemistry",
                        "subject_name": "Chemistry",
                        "year": 1,
                        "semester": 1,
                        "is_full_year": False,
                    },
                    {
                        "client_key": "module_phys",
                        "code": "PHYS101",
                        "name": "Mechanics",
                        "subject_name": "Physics",
                        "year": 1,
                        "semester": 1,
                        "is_full_year": False,
                    },
                ],
                "sessions": [
                    {
                        "client_key": "session_chem_shared",
                        "module_client_key": "module_chem",
                        "name": "Chemistry Lab",
                        "session_type": "practical",
                        "duration_minutes": 180,
                        "occurrences_per_week": 1,
                        "required_room_type": "lab",
                        "required_lab_type": "chem_lab",
                        "specific_room_client_key": None,
                        "max_students_per_group": None,
                        "allow_parallel_rooms": False,
                        "notes": None,
                        "lecturer_client_keys": ["lect_1"],
                        "student_group_client_keys": ["group_ps", "group_bs"],
                    },
                    {
                        "client_key": "session_phys_ps_only",
                        "module_client_key": "module_phys",
                        "name": "Physics Lab",
                        "session_type": "practical",
                        "duration_minutes": 180,
                        "occurrences_per_week": 1,
                        "required_room_type": "lab",
                        "required_lab_type": "chem_lab",
                        "specific_room_client_key": None,
                        "max_students_per_group": None,
                        "allow_parallel_rooms": False,
                        "notes": None,
                        "lecturer_client_keys": ["lect_1"],
                        "student_group_client_keys": ["group_ps"],
                    },
                ],
            }
        )
        replace_dataset(self.db, payload)
        generate_timetables(
            self.db,
            selected_soft_constraints=[],
            max_solutions=20,
            preview_limit=3,
            time_limit_seconds=10,
        )

        ps_view = build_view_payload(self.db, mode="student", degree_id=1, path_id=1)
        bs_view = build_view_payload(self.db, mode="student", degree_id=2, path_id=2)

        ps_modules = {entry["module_code"] for entry in ps_view["solution"]["entries"]}
        bs_modules = {entry["module_code"] for entry in bs_view["solution"]["entries"]}

        self.assertEqual(ps_modules, {"CHEM101", "PHYS101"})
        self.assertEqual(bs_modules, {"CHEM101"})

    def test_conflicting_soft_constraint_returns_possible_combinations(self):
        payload = DatasetUpsertRequest(**build_dataset())
        replace_dataset(self.db, payload)

        infeasible_result = {
            "status": "infeasible",
            "message": "No possible timetables satisfy the selected constraints.",
            "solutions": [],
            "truncated": False,
            "tasks": [],
            "timing": {
                "precheck_ms": 1,
                "model_build_ms": 2,
                "solve_ms": 3,
                "fallback_search_ms": 0,
                "total_ms": 6,
            },
            "stats": {
                "task_count": 0,
                "assignment_variable_count": 0,
                "candidate_option_count": 0,
                "feasible_combo_count": 0,
                "fallback_combo_evaluated_count": 0,
                "fallback_combo_truncated": False,
                "exact_enumeration_single_worker": True,
                "machine_cpu_count": 4,
            },
        }
        feasible_result = {
            "status": "optimal",
            "message": "Generated timetable solutions.",
            "solutions": [[(0, 1, "Monday", 480)]],
            "truncated": False,
            "tasks": [],
            "timing": {
                "precheck_ms": 1,
                "model_build_ms": 2,
                "solve_ms": 3,
                "fallback_search_ms": 0,
                "total_ms": 6,
            },
            "stats": {
                "task_count": 0,
                "assignment_variable_count": 1,
                "candidate_option_count": 1,
                "feasible_combo_count": 0,
                "fallback_combo_evaluated_count": 0,
                "fallback_combo_truncated": False,
                "exact_enumeration_single_worker": True,
                "machine_cpu_count": 4,
            },
        }

        with patch.object(
            timetable_v2_service,
            "_solve_internal",
            side_effect=chain([infeasible_result], repeat(feasible_result)),
        ):
            run = generate_timetables(
                self.db,
                selected_soft_constraints=[
                    "avoid_friday_sessions",
                    "spread_sessions_across_days",
                ],
                max_solutions=10,
                preview_limit=2,
                time_limit_seconds=10,
            )

        serialized = serialize_generation_run(get_latest_run(self.db))
        self.assertIn(
            "Selected nice-to-have constraints cannot be satisfied together.",
            run.message,
        )
        self.assertTrue(serialized["possible_soft_constraint_combinations"])
        self.assertTrue(
            any(
                combo["constraints"] == ["avoid_friday_sessions"]
                or combo["constraints"] == ["spread_sessions_across_days"]
                for combo in serialized["possible_soft_constraint_combinations"]
            )
        )
        self.assertTrue(
            all("solution_count" in combo for combo in serialized["possible_soft_constraint_combinations"])
        )

    def test_generation_response_includes_performance_stats(self):
        payload = DatasetUpsertRequest(**build_dataset())
        replace_dataset(self.db, payload)

        run = generate_timetables(
            self.db,
            selected_soft_constraints=[],
            max_solutions=5,
            preview_limit=1,
            time_limit_seconds=10,
            performance_preset="thorough",
        )

        serialized = serialize_generation_run(run)
        self.assertEqual(serialized["performance_preset"], "thorough")
        self.assertIn("timing", serialized)
        self.assertIn("stats", serialized)
        self.assertGreaterEqual(serialized["stats"]["assignment_variable_count"], 1)
        self.assertGreaterEqual(serialized["stats"]["candidate_option_count"], 1)
        self.assertGreaterEqual(serialized["stats"]["memory_limit_mb"], 1)

    def test_fallback_only_checks_subsets_of_selected_constraints(self):
        payload = DatasetUpsertRequest(**build_dataset())
        replace_dataset(self.db, payload)

        infeasible_result = {
            "status": "infeasible",
            "message": "No possible timetables satisfy the selected constraints.",
            "solutions": [],
            "truncated": False,
            "tasks": [],
            "timing": {
                "precheck_ms": 0,
                "model_build_ms": 0,
                "solve_ms": 0,
                "fallback_search_ms": 0,
                "total_ms": 0,
            },
            "stats": {
                "task_count": 0,
                "assignment_variable_count": 0,
                "candidate_option_count": 0,
                "feasible_combo_count": 0,
                "fallback_combo_evaluated_count": 0,
                "fallback_combo_truncated": False,
                "exact_enumeration_single_worker": True,
                "machine_cpu_count": 4,
            },
        }
        feasible_result = {
            **infeasible_result,
            "status": "feasible",
            "message": "Generated timetable solutions.",
            "solutions": [[(0, 1, "Monday", 480)]],
            "tasks": [build_mock_task()],
        }

        seen_combos: list[list[str]] = []

        def solve_side_effect(_db, combo, *_args, **_kwargs):
            seen_combos.append(list(combo))
            if combo == [
                "avoid_friday_sessions",
                "spread_sessions_across_days",
            ]:
                return infeasible_result
            return feasible_result

        with patch.object(
            timetable_v2_service,
            "_solve_internal",
            side_effect=solve_side_effect,
        ):
            generate_timetables(
                self.db,
                selected_soft_constraints=[
                    "avoid_friday_sessions",
                    "spread_sessions_across_days",
                ],
                max_solutions=10,
                preview_limit=2,
                time_limit_seconds=10,
            )

        self.assertEqual(
            seen_combos,
            [
                ["avoid_friday_sessions", "spread_sessions_across_days"],
                ["avoid_friday_sessions"],
                ["spread_sessions_across_days"],
            ],
        )

    def test_soft_constraint_options_include_additional_preferences(self):
        option_keys = {option.key for option in list_soft_constraint_options()}
        self.assertEqual(
            option_keys,
            {
                "spread_sessions_across_days",
                "prefer_morning_theory",
                "prefer_afternoon_practicals",
                "avoid_late_afternoon_starts",
                "avoid_friday_sessions",
                "prefer_standard_block_starts",
                "balance_teaching_load_across_week",
                "avoid_monday_overload",
            },
        )

    def test_generation_returns_resource_limited_when_model_budget_is_exceeded(self):
        payload = DatasetUpsertRequest(**build_dataset(room_capacity=120, room_count=2))
        replace_dataset(self.db, payload)

        with patch.object(timetable_v2_service, "MAX_ASSIGNMENT_VARIABLE_BUDGET", 1):
            run = generate_timetables(
                self.db,
                selected_soft_constraints=[],
                max_solutions=5,
                preview_limit=1,
                time_limit_seconds=10,
            )

        serialized = serialize_generation_run(get_latest_run(self.db))
        self.assertEqual(run.status, "resource_limited")
        self.assertEqual(serialized["status"], "resource_limited")
        self.assertIn("projected model size is too large", run.message)
        self.assertGreater(serialized["stats"]["assignment_variable_count"], 1)

    def test_practical_afternoon_soft_constraint_pushes_lab_after_lunch(self):
        payload = DatasetUpsertRequest(**build_dataset())
        replace_dataset(self.db, payload)

        generate_timetables(
            self.db,
            selected_soft_constraints=["prefer_afternoon_practicals"],
            max_solutions=5,
            preview_limit=1,
            time_limit_seconds=10,
        )

        serialized = serialize_generation_run(get_latest_run(self.db))
        entry = serialized["solutions"][0]["entries"][0]
        self.assertGreaterEqual(entry["start_minute"], 13 * 60)

    def test_lab_sessions_use_fixed_three_hour_blocks(self):
        payload = DatasetUpsertRequest(**build_dataset())
        replace_dataset(self.db, payload)

        generate_timetables(
            self.db,
            selected_soft_constraints=[],
            max_solutions=5,
            preview_limit=1,
            time_limit_seconds=10,
        )

        serialized = serialize_generation_run(get_latest_run(self.db))
        entry = serialized["solutions"][0]["entries"][0]
        self.assertEqual(entry["duration_minutes"], 180)
        self.assertIn(entry["start_minute"], {9 * 60, 13 * 60})

    def test_invalid_lab_duration_is_reported_as_infeasible(self):
        payload = build_dataset()
        payload["sessions"][0]["duration_minutes"] = 120
        replace_dataset(self.db, DatasetUpsertRequest(**payload))

        run = generate_timetables(
            self.db,
            selected_soft_constraints=[],
            max_solutions=5,
            preview_limit=1,
            time_limit_seconds=10,
        )

        self.assertEqual(run.status, "infeasible")
        self.assertIn("3-hour lab block", run.message)

    def test_export_view_csv_contains_expected_headers_and_entry_values(self):
        payload = DatasetUpsertRequest(**build_dataset())
        replace_dataset(self.db, payload)
        generate_timetables(
            self.db,
            selected_soft_constraints=[],
            max_solutions=5,
            preview_limit=1,
            time_limit_seconds=10,
        )

        view_payload = build_view_payload(self.db, mode="admin")
        export_payload = export_view(view_payload, "csv")

        self.assertEqual(export_payload.filename, "admin-timetable.csv")
        self.assertEqual(export_payload.content_type, "text/csv")

        import base64

        csv_text = base64.b64decode(export_payload.content).decode("utf-8")
        self.assertIn("Day,Start,Duration,Module Code,Module Name,Session,Room", csv_text)
        self.assertIn("CHEM101", csv_text)
        self.assertIn("Chemistry Lab", csv_text)

    def test_export_view_xls_returns_tabular_excel_payload(self):
        payload = DatasetUpsertRequest(**build_dataset())
        replace_dataset(self.db, payload)
        generate_timetables(
            self.db,
            selected_soft_constraints=[],
            max_solutions=5,
            preview_limit=1,
            time_limit_seconds=10,
        )

        view_payload = build_view_payload(self.db, mode="admin")
        export_payload = export_view(view_payload, "xls")

        self.assertEqual(export_payload.filename, "admin-timetable.xls")
        self.assertEqual(export_payload.content_type, "application/vnd.ms-excel")

        import base64

        workbook_text = base64.b64decode(export_payload.content).decode("utf-8")
        self.assertIn("Day\tStart\tDuration\tModule\tRoom\tLecturers\tGroups", workbook_text)
        self.assertIn("CHEM101", workbook_text)


if __name__ == "__main__":
    unittest.main()
