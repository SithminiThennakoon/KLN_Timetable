import os
import sys
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient


TEST_DB_FILE = Path(tempfile.gettempdir()) / "kln_timetable_snapshot_workspace_api.sqlite"
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB_FILE}"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.database import Base, SessionLocal, engine  # noqa: E402
from app.main import create_app  # noqa: E402
from app.services.import_materialization import materialize_import_run  # noqa: E402


SOURCE_FILE = str(Path(__file__).resolve().parents[2] / "students_processed_TT_J.csv")


class SnapshotWorkspaceApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
        cls.client = TestClient(create_app())

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

    def test_workspace_endpoint_returns_materialized_counts(self):
        import_run_id = self._materialize_import()

        response = self.client.get(f"/api/v2/imports/{import_run_id}/workspace")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["import_run_id"], import_run_id)
        self.assertGreater(len(payload["curriculum_modules"]), 0)
        self.assertGreater(len(payload["attendance_groups"]), 0)

    def test_workspace_endpoint_returns_404_for_missing_import_run(self):
        response = self.client.get("/api/v2/imports/999999/workspace")

        self.assertEqual(response.status_code, 404)
        self.assertIn("import run", response.json()["detail"].lower())

    def test_seed_endpoint_populates_workspace_entities(self):
        import_run_id = self._materialize_import()

        seed_response = self.client.post(
            f"/api/v2/imports/{import_run_id}/snapshot/seed-realistic-missing-data"
        )
        workspace_response = self.client.get(f"/api/v2/imports/{import_run_id}/workspace")

        self.assertEqual(seed_response.status_code, 200)
        seed_payload = seed_response.json()
        self.assertGreater(seed_payload["lecturers_created"], 0)
        self.assertGreater(seed_payload["rooms_created"], 0)
        self.assertGreater(seed_payload["shared_sessions_created"], 0)

        self.assertEqual(workspace_response.status_code, 200)
        workspace_payload = workspace_response.json()
        self.assertGreater(len(workspace_payload["lecturers"]), 0)
        self.assertGreater(len(workspace_payload["rooms"]), 0)
        self.assertGreater(len(workspace_payload["shared_sessions"]), 0)


if __name__ == "__main__":
    unittest.main()
