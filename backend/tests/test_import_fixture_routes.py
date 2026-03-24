import io
import os
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

from fastapi.testclient import TestClient


TEST_DB_FILE = Path(tempfile.gettempdir()) / "kln_timetable_fixture_routes_tests.sqlite"
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB_FILE}"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.database import engine  # noqa: E402
from app.main import create_app  # noqa: E402


class ImportFixtureRoutesTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(create_app())

    @classmethod
    def tearDownClass(cls):
        cls.client.close()
        engine.dispose()

    def test_lists_import_fixture_packs(self):
        response = self.client.get("/api/v2/import-fixtures")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("packs", payload)
        self.assertEqual(payload["packs"][0]["name"], "production_like")
        self.assertTrue(payload["packs"][0]["available"])

    def test_downloads_fixture_pack_zip(self):
        response = self.client.get("/api/v2/import-fixtures/production_like.zip")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["content-type"], "application/zip")
        self.assertIn(
            'attachment; filename="production_like_import_fixture_pack.zip"',
            response.headers["content-disposition"],
        )

        archive = zipfile.ZipFile(io.BytesIO(response.content))
        names = set(archive.namelist())
        self.assertEqual(
            names,
            {
                "student_enrollments.csv",
                "rooms.csv",
                "lecturers.csv",
                "modules.csv",
                "sessions.csv",
                "session_lecturers.csv",
            },
        )

    def test_downloads_raw_fixture_csv(self):
        response = self.client.get(
            "/api/v2/import-fixtures/production_like/rooms.csv"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["content-type"], "text/csv; charset=utf-8")
        self.assertIn("room_code,room_name,capacity,room_type", response.text)


if __name__ == "__main__":
    unittest.main()
