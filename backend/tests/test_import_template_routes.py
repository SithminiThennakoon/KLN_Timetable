import os
import sys
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient


TEST_DB_FILE = Path(tempfile.gettempdir()) / "kln_timetable_template_routes_tests.sqlite"
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB_FILE}"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.database import engine  # noqa: E402
from app.main import create_app  # noqa: E402


class ImportTemplateRoutesTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(create_app())

    @classmethod
    def tearDownClass(cls):
        cls.client.close()
        engine.dispose()

    def test_lists_import_templates(self):
        response = self.client.get("/api/v2/imports/templates")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        names = {item["name"] for item in payload["templates"]}
        self.assertIn("student_enrollments", names)
        self.assertIn("rooms", names)
        self.assertIn("lecturers", names)
        self.assertIn("modules", names)
        self.assertIn("sessions", names)
        self.assertIn("session_lecturers", names)

    def test_downloads_student_enrollment_template_csv(self):
        response = self.client.get("/api/v2/imports/templates/student_enrollments")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["content-type"], "text/csv; charset=utf-8")
        self.assertIn(
            'attachment; filename="student_enrollments_template.csv"',
            response.headers["content-disposition"],
        )
        self.assertIn(
            "CoursePathNo,CourseCode,Year,AcYear,Attempt,stream,batch,student_hash",
            response.text,
        )

    def test_returns_404_for_unknown_import_template(self):
        response = self.client.get("/api/v2/imports/templates/not_real")

        self.assertEqual(response.status_code, 404)
        self.assertIn("Import template not found", response.json()["detail"])


if __name__ == "__main__":
    unittest.main()
