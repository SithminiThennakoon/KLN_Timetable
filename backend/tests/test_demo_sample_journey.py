import os
import sys
import tempfile
import unittest
from pathlib import Path


TEST_DB_FILE = Path(tempfile.gettempdir()) / "kln_timetable_demo_sample_journey_tests.sqlite"
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB_FILE}"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.database import Base, SessionLocal, engine  # noqa: E402
from app.services.import_materialization import materialize_import_run  # noqa: E402
from app.services.snapshot_completion import (  # noqa: E402
    build_import_readiness_summary,
    seed_realistic_snapshot_missing_data,
)
from app.services.timetable_v2 import generate_snapshot_timetables  # noqa: E402


class DemoSampleJourneyTestCase(unittest.TestCase):
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

    def test_sample_demo_journey_reaches_generation(self):
        import_run = materialize_import_run(
            self.db,
            source_file=str(Path(__file__).resolve().parents[2] / "students_processed_TT_J.csv"),
            review_rules=[],
            allowed_attempts=("1",),
        )
        self.db.commit()

        seed_summary = seed_realistic_snapshot_missing_data(
            self.db, import_run_id=int(import_run.id)
        )
        self.db.commit()

        readiness = build_import_readiness_summary(self.db, int(import_run.id))
        run = generate_snapshot_timetables(
            self.db,
            import_run_id=int(import_run.id),
            selected_soft_constraints=[],
            max_solutions=10,
            preview_limit=1,
            time_limit_seconds=30,
            performance_preset="balanced",
        )

        self.assertGreater(seed_summary["shared_sessions_created"], 0)
        self.assertTrue(readiness["ready"])
        self.assertIn(run.status, {"optimal", "feasible", "completed"})
        self.assertGreaterEqual(run.total_solutions_found, 1)


if __name__ == "__main__":
    unittest.main()
