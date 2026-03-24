import os
import sys
import tempfile
import unittest
from pathlib import Path


TEST_DB_FILE = Path(tempfile.gettempdir()) / "kln_timetable_snapshot_workspace_flow.sqlite"
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB_FILE}"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.database import Base, SessionLocal, engine  # noqa: E402
from app.models.academic import CurriculumModule  # noqa: E402
from app.models.snapshot import SnapshotSharedSession  # noqa: E402
from app.services.import_materialization import materialize_import_run  # noqa: E402
from app.services.snapshot_completion import (  # noqa: E402
    build_import_readiness_summary,
    build_import_workspace,
    seed_realistic_snapshot_missing_data,
)
from app.services.timetable_v2 import (  # noqa: E402
    _build_snapshot_tasks,
    build_snapshot_verification_payload,
    generate_snapshot_timetables,
)
from verifiers.python_snapshot_verifier import verify_snapshot  # noqa: E402


SOURCE_FILE = str(Path(__file__).resolve().parents[2] / "students_processed_TT_J.csv")


class SnapshotWorkspaceFlowTests(unittest.TestCase):
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

    def _materialize_import(self) -> int:
        import_run = materialize_import_run(
            self.db,
            source_file=SOURCE_FILE,
            review_rules=[],
            allowed_attempts=("1",),
        )
        self.db.commit()
        return int(import_run.id)

    def _seed_import(self, import_run_id: int) -> dict:
        summary = seed_realistic_snapshot_missing_data(
            self.db,
            import_run_id=import_run_id,
        )
        self.db.commit()
        return summary

    def test_readiness_before_seed_reports_missing_snapshot_requirements(self):
        import_run_id = self._materialize_import()

        readiness = build_import_readiness_summary(self.db, import_run_id)

        self.assertFalse(readiness["ready"])
        self.assertIn("Import rooms.csv or add rooms manually.", readiness["blocking"])
        self.assertIn("Import lecturers.csv or add lecturers manually.", readiness["blocking"])
        self.assertIn("Import sessions.csv or add teaching sessions manually.", readiness["blocking"])
        self.assertGreater(readiness["counts"]["curriculum_modules"], 0)
        self.assertGreater(readiness["counts"]["attendance_groups"], 0)

    def test_materialized_workspace_links_modules_to_attendance_groups(self):
        import_run_id = self._materialize_import()

        workspace = build_import_workspace(self.db, import_run_id)
        linked_modules = [
            module for module in workspace["curriculum_modules"] if module["attendance_group_ids"]
        ]

        self.assertGreater(len(workspace["curriculum_modules"]), 0)
        self.assertGreater(len(linked_modules), 0)
        self.assertTrue(
            all(isinstance(group_id, int) for module in linked_modules for group_id in module["attendance_group_ids"])
        )

    def test_seeded_workspace_becomes_ready_and_is_bounded(self):
        import_run_id = self._materialize_import()

        seed_summary = self._seed_import(import_run_id)
        readiness = build_import_readiness_summary(self.db, import_run_id)

        self.assertTrue(readiness["ready"])
        self.assertGreater(seed_summary["lecturers_created"], 0)
        self.assertGreater(seed_summary["rooms_created"], 0)
        self.assertGreater(seed_summary["shared_sessions_created"], 0)
        self.assertGreaterEqual(seed_summary["shared_sessions_created"], 300)

    def test_generated_snapshot_payload_passes_python_verifier(self):
        import_run_id = self._materialize_import()
        self._seed_import(import_run_id)

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

    def test_generated_payload_includes_student_hashes_for_audience_details(self):
        import_run_id = self._materialize_import()
        self._seed_import(import_run_id)
        generate_snapshot_timetables(
            self.db,
            import_run_id=import_run_id,
            selected_soft_constraints=[],
            max_solutions=5,
            preview_limit=1,
            time_limit_seconds=30,
            performance_preset="balanced",
        )

        payload = build_snapshot_verification_payload(self.db, import_run_id)
        entries_with_hashes = [
            entry for entry in payload["timetable_entries"] if entry.get("student_hashes")
        ]

        self.assertGreater(len(entries_with_hashes), 0)
        self.assertTrue(
            all(isinstance(student_hash, str) for entry in entries_with_hashes for student_hash in entry["student_hashes"])
        )

    def test_snapshot_tasks_preserve_all_linked_module_ids_for_shared_sessions(self):
        import_run_id = self._materialize_import()
        self._seed_import(import_run_id)

        shared_session = (
            self.db.query(SnapshotSharedSession)
            .filter(SnapshotSharedSession.import_run_id == import_run_id)
            .order_by(SnapshotSharedSession.id.asc())
            .first()
        )
        self.assertIsNotNone(shared_session)
        existing_ids = {int(module.id) for module in shared_session.curriculum_modules}
        self.assertGreater(len(existing_ids), 0)

        workspace = build_import_workspace(self.db, import_run_id)
        extra_module = next(
            (
                module
                for module in workspace["curriculum_modules"]
                if int(module["id"]) not in existing_ids
            ),
            None,
        )
        self.assertIsNotNone(extra_module)

        shared_session.curriculum_modules.append(
            self.db.get(CurriculumModule, int(extra_module["id"]))
        )
        self.db.commit()

        tasks, _sessions, _rooms, _lecturer_names, _group_names = _build_snapshot_tasks(
            self.db, import_run_id
        )
        matching_tasks = [task for task in tasks if task.session_id == int(shared_session.id)]

        self.assertGreater(len(matching_tasks), 0)
        for task in matching_tasks:
            self.assertEqual(set(task.module_ids), existing_ids | {int(extra_module["id"])})
            self.assertIsNone(task.module_id)


if __name__ == "__main__":
    unittest.main()
