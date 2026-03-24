import csv
import os
import sys
import tempfile
import unittest
from collections import defaultdict
from pathlib import Path


TEST_DB_FILE = Path(tempfile.gettempdir()) / "kln_timetable_prompt_scenario_fixture_pack.sqlite"
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB_FILE}"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.database import Base, SessionLocal, engine  # noqa: E402
from app.models.snapshot import SnapshotSharedSession  # noqa: E402
from app.services.csv_import_analysis import analyze_enrollment_csv, ReviewRule  # noqa: E402
from app.services.import_fixtures import FIXTURE_ROOT, PRODUCTION_LIKE_PACK_NAME  # noqa: E402
from app.services.import_materialization import materialize_import_run  # noqa: E402
from app.services.lecturer_csv_import import import_lecturers_csv  # noqa: E402
from app.services.module_csv_import import import_modules_csv  # noqa: E402
from app.services.room_csv_import import import_rooms_csv  # noqa: E402
from app.services.session_csv_import import import_sessions_csv  # noqa: E402
from app.services.session_lecturer_csv_import import import_session_lecturers_csv  # noqa: E402
from app.services.snapshot_completion import (  # noqa: E402
    build_import_readiness_summary,
    build_import_workspace,
)
from app.services.timetable_v2 import (  # noqa: E402
    build_snapshot_verification_payload,
    generate_snapshot_timetables,
)
from verifiers.python_snapshot_verifier import verify_snapshot  # noqa: E402


FIXTURE_DIR = FIXTURE_ROOT / PRODUCTION_LIKE_PACK_NAME


class PromptScenarioFixturePackTests(unittest.TestCase):
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

    def _read_csv(self, filename: str) -> list[dict[str, str]]:
        with (FIXTURE_DIR / filename).open(newline="", encoding="utf-8") as handle:
            return list(csv.DictReader(handle))

    def _import_fixture_pack(self) -> int:
        analysis = analyze_enrollment_csv(str(FIXTURE_DIR / "student_enrollments.csv"))
        review_rules = [
            ReviewRule(
                bucket_type=bucket["bucket_type"],
                bucket_key=bucket["bucket_key"],
                action="accept_exception",
                label=bucket.get("description"),
            )
            for bucket in analysis["buckets"]
        ]
        import_run = materialize_import_run(
            self.db,
            source_file=str(FIXTURE_DIR / "student_enrollments.csv"),
            review_rules=review_rules,
            allowed_attempts=("1",),
        )
        self.db.commit()
        import_run_id = int(import_run.id)

        import_rooms_csv(
            self.db,
            import_run_id=import_run_id,
            csv_path=str(FIXTURE_DIR / "rooms.csv"),
        )
        import_lecturers_csv(
            self.db,
            import_run_id=import_run_id,
            csv_path=str(FIXTURE_DIR / "lecturers.csv"),
        )
        import_modules_csv(
            self.db,
            import_run_id=import_run_id,
            csv_path=str(FIXTURE_DIR / "modules.csv"),
        )
        import_sessions_csv(
            self.db,
            import_run_id=import_run_id,
            csv_path=str(FIXTURE_DIR / "sessions.csv"),
        )
        import_session_lecturers_csv(
            self.db,
            import_run_id=import_run_id,
            csv_path=str(FIXTURE_DIR / "session_lecturers.csv"),
        )
        self.db.commit()
        return import_run_id

    def test_fixture_pack_contains_prompt_scenarios(self):
        rooms = self._read_csv("rooms.csv")
        modules = self._read_csv("modules.csv")
        sessions = self._read_csv("sessions.csv")

        self.assertGreater(sum(1 for room in rooms if room["year_restriction"]), 0)
        self.assertGreater(
            sum(1 for module in modules if module["is_full_year"].lower() == "true"),
            0,
        )
        self.assertGreater(sum(1 for session in sessions if session["module_codes"]), 0)
        self.assertGreater(sum(1 for session in sessions if session["specific_room_code"]), 0)
        self.assertGreater(
            sum(1 for session in sessions if session["allow_parallel_rooms"].lower() == "true"),
            0,
        )
        self.assertGreater(sum(1 for session in sessions if session["max_students_per_group"]), 0)
        self.assertGreater(sum(1 for session in sessions if session["required_lab_type"]), 0)
        self.assertGreater(
            sum(1 for session in sessions if int(session["occurrences_per_week"]) > 1),
            0,
        )

    def test_fixture_pack_imports_and_solver_handles_prompt_scenarios(self):
        import_run_id = self._import_fixture_pack()

        workspace = build_import_workspace(self.db, import_run_id)
        readiness = build_import_readiness_summary(self.db, import_run_id)

        self.assertTrue(readiness["ready"])
        self.assertTrue(
            any(room["year_restriction"] is not None for room in workspace["rooms"])
        )
        self.assertTrue(
            any(bool(module["is_full_year"]) for module in workspace["curriculum_modules"])
        )
        self.assertTrue(
            any(
                len(session["curriculum_module_ids"]) > 1
                for session in workspace["shared_sessions"]
            )
        )
        self.assertTrue(
            any(bool(session["specific_room_id"]) for session in workspace["shared_sessions"])
        )
        self.assertTrue(
            any(bool(session["allow_parallel_rooms"]) for session in workspace["shared_sessions"])
        )
        self.assertTrue(
            any(
                int(session["max_students_per_group"] or 0) > 0
                for session in workspace["shared_sessions"]
            )
        )
        self.assertTrue(
            any(int(session["occurrences_per_week"]) > 1 for session in workspace["shared_sessions"])
        )

        selected_session_ids: set[int] = set()
        multi_module_session = next(
            (
                session
                for session in workspace["shared_sessions"]
                if len(session["curriculum_module_ids"]) > 1
            ),
            None,
        )
        self.assertIsNotNone(multi_module_session)
        selected_session_ids.add(int(multi_module_session["id"]))

        parallel_session = next(
            (
                session
                for session in workspace["shared_sessions"]
                if bool(session["allow_parallel_rooms"])
            ),
            None,
        )
        self.assertIsNotNone(parallel_session)
        selected_session_ids.add(int(parallel_session["id"]))

        year_restricted_session = next(
            (
                session
                for session in workspace["shared_sessions"]
                if session["specific_room_id"]
                and any(
                    int(room["id"]) == int(session["specific_room_id"])
                    and room["year_restriction"] is not None
                    for room in workspace["rooms"]
                )
            ),
            None,
        )
        self.assertIsNotNone(year_restricted_session)
        selected_session_ids.add(int(year_restricted_session["id"]))

        split_session = next(
            (
                session
                for session in workspace["shared_sessions"]
                if int(session["max_students_per_group"] or 0) > 0
                and not bool(session["allow_parallel_rooms"])
            ),
            None,
        )
        self.assertIsNotNone(split_session)
        selected_session_ids.add(int(split_session["id"]))

        multi_occurrence_session = next(
            (
                session
                for session in workspace["shared_sessions"]
                if int(session["occurrences_per_week"]) > 1
            ),
            None,
        )
        self.assertIsNotNone(multi_occurrence_session)
        selected_session_ids.add(int(multi_occurrence_session["id"]))

        (
            self.db.query(SnapshotSharedSession)
            .filter(
                SnapshotSharedSession.import_run_id == import_run_id,
                SnapshotSharedSession.id.not_in(selected_session_ids),
            )
            .delete(synchronize_session=False)
        )
        self.db.commit()

        run = generate_snapshot_timetables(
            self.db,
            import_run_id=import_run_id,
            selected_soft_constraints=[],
            max_solutions=5,
            preview_limit=1,
            time_limit_seconds=30,
            performance_preset="balanced",
        )
        payload = build_snapshot_verification_payload(self.db, import_run_id)
        verification = verify_snapshot(payload)

        self.assertIn(run.status, {"optimal", "feasible", "completed"})
        self.assertTrue(verification["hard_valid"])
        self.assertEqual(verification["hard_violations"], [])
        self.assertGreater(len(payload["timetable_entries"]), 0)
        self.assertTrue(
            any(len(entry["curriculum_module_ids"]) > 1 for entry in payload["timetable_entries"])
        )
        self.assertTrue(
            any(
                entry["room"] is not None
                and entry["room"].get("year_restriction") is not None
                for entry in payload["timetable_entries"]
            )
        )
        self.assertTrue(any(int(entry["split_index"]) > 1 for entry in payload["timetable_entries"]))
        self.assertTrue(
            any(int(entry["occurrence_index"]) > 1 for entry in payload["timetable_entries"])
        )

        entries_by_parallel_slot: dict[tuple[int, int, str, int], list[dict]] = defaultdict(list)
        for entry in payload["timetable_entries"]:
            entries_by_parallel_slot[
                (
                    int(entry["shared_session_id"]),
                    int(entry["occurrence_index"]),
                    str(entry["day"]),
                    int(entry["start_minute"]),
                )
            ].append(entry)
        self.assertTrue(any(len(entries) > 1 for entries in entries_by_parallel_slot.values()))


if __name__ == "__main__":
    unittest.main()
