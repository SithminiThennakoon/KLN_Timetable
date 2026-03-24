import os
import sys
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient


TEST_DB_FILE = Path(tempfile.gettempdir()) / "kln_timetable_legacy_endpoints_tests.sqlite"
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB_FILE}"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.main import create_app  # noqa: E402


class LegacyEndpointsRetiredTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(create_app())

    def test_enrollment_load_endpoint_is_retired(self):
        response = self.client.post(
            "/api/v2/imports/enrollment-load",
            json={"rules": [], "allowed_attempts": ["1"]},
        )

        self.assertEqual(response.status_code, 410)
        self.assertIn("retired", response.json()["detail"])

    def test_publish_legacy_endpoint_is_retired(self):
        response = self.client.post("/api/v2/imports/1/publish-legacy")

        self.assertEqual(response.status_code, 410)
        self.assertIn("retired", response.json()["detail"])


if __name__ == "__main__":
    unittest.main()
