import os
import sys
import tempfile
import unittest
from pathlib import Path


TEST_DB_FILE = Path(tempfile.gettempdir()) / "kln_timetable_lecturer_csv_import_tests.sqlite"
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB_FILE}"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.database import Base, SessionLocal, engine  # noqa: E402
from app.models.imports import ImportRun  # noqa: E402
from app.models.snapshot import SnapshotLecturer  # noqa: E402
from app.services.lecturer_csv_import import import_lecturers_csv  # noqa: E402


class LecturerCsvImportTestCase(unittest.TestCase):
    def setUp(self):
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
        self.db = SessionLocal()
        import_run = ImportRun(
            source_file="students_processed_TT_J.csv",
            source_format="uok_fos_enrollment_csv",
            status="materialized",
        )
        self.db.add(import_run)
        self.db.commit()
        self.import_run_id = import_run.id

    def tearDown(self):
        self.db.close()

    def _write_csv(self, content: str) -> str:
        handle = tempfile.NamedTemporaryFile("w", delete=False, suffix=".csv", encoding="utf-8")
        try:
            handle.write(content)
        finally:
            handle.close()
        self.addCleanup(lambda: Path(handle.name).unlink(missing_ok=True))
        return handle.name

    def test_imports_lecturers_csv_and_emits_warnings(self):
        csv_path = self._write_csv(
            "lecturer_code,name,email\n"
            "LECT-CHEM-01,Dr. Silva,silva@example.edu\n"
            "LECT-MATH-01,Prof. Perera,\n"
        )

        result = import_lecturers_csv(self.db, import_run_id=self.import_run_id, csv_path=csv_path)
        self.db.commit()

        self.assertEqual(result["created_count"], 2)
        self.assertEqual(result["updated_count"], 0)
        self.assertEqual(len(result["lecturers"]), 2)
        self.assertTrue(any("has no email" in item["message"] for item in result["warnings"]))

    def test_upserts_existing_lecturer_by_code(self):
        first_csv = self._write_csv(
            "lecturer_code,name,email\n"
            "LECT-CHEM-01,Dr. Silva,silva@example.edu\n"
        )
        second_csv = self._write_csv(
            "lecturer_code,name,email\n"
            "LECT-CHEM-01,Dr. Silva,updated@example.edu\n"
        )

        import_lecturers_csv(self.db, import_run_id=self.import_run_id, csv_path=first_csv)
        self.db.commit()
        result = import_lecturers_csv(self.db, import_run_id=self.import_run_id, csv_path=second_csv)
        self.db.commit()

        self.assertEqual(result["created_count"], 0)
        self.assertEqual(result["updated_count"], 1)

        saved_lecturer = (
            self.db.query(SnapshotLecturer)
            .filter(SnapshotLecturer.import_run_id == self.import_run_id)
            .one()
        )
        self.assertEqual(saved_lecturer.email, "updated@example.edu")

    def test_rejects_duplicate_lecturer_codes_within_file(self):
        csv_path = self._write_csv(
            "lecturer_code,name,email\n"
            "LECT-CHEM-01,Dr. Silva,silva@example.edu\n"
            "LECT-CHEM-01,Prof. Silva,alt@example.edu\n"
        )

        with self.assertRaises(ValueError) as context:
            import_lecturers_csv(self.db, import_run_id=self.import_run_id, csv_path=csv_path)

        self.assertIn("duplicate lecturer_code 'LECT-CHEM-01'", str(context.exception))

    def test_rejects_same_name_with_different_lecturer_code(self):
        self.db.add(
            SnapshotLecturer(
                import_run_id=self.import_run_id,
                client_key="manual_lecturer_1",
                name="Dr. Silva",
                email="manual@example.edu",
                notes="manual",
            )
        )
        self.db.commit()
        csv_path = self._write_csv(
            "lecturer_code,name,email\n"
            "LECT-CHEM-99,Dr. Silva,silva@example.edu\n"
        )

        with self.assertRaises(ValueError) as context:
            import_lecturers_csv(self.db, import_run_id=self.import_run_id, csv_path=csv_path)

        self.assertIn("Re-import only updates matching lecturer_code values", str(context.exception))


if __name__ == "__main__":
    unittest.main()
