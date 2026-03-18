import os
import sys
import tempfile
import unittest
from pathlib import Path


TEST_DB_FILE = Path(tempfile.gettempdir()) / "kln_timetable_module_csv_import_tests.sqlite"
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB_FILE}"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.database import Base, SessionLocal, engine  # noqa: E402
from app.models.academic import CurriculumModule, StudentModuleMembership  # noqa: E402
from app.models.imports import ImportRun, ImportStudent  # noqa: E402
from app.services.module_csv_import import import_modules_csv  # noqa: E402


class ModuleCsvImportTestCase(unittest.TestCase):
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
        self.db.flush()

        student = ImportStudent(student_hash="stu_hash_0001")
        module = CurriculumModule(
            code="CHEM 11612",
            canonical_code="CHEM 11612",
            name="Old Chemistry Name",
            subject_name="Chemistry",
            subject_code="CHEM",
            nominal_year=1,
            semester_bucket=1,
            is_full_year=False,
        )
        self.db.add_all([student, module])
        self.db.flush()
        self.db.add(
            StudentModuleMembership(
                import_run_id=import_run.id,
                student_id=student.id,
                curriculum_module_id=module.id,
                student_programme_context_id=None,
                import_enrollment_id=None,
                membership_source="import",
            )
        )
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

    def test_updates_module_metadata(self):
        csv_path = self._write_csv(
            "module_code,module_name,subject_name,nominal_year,semester_bucket,is_full_year\n"
            "CHEM 11612,Foundations of Chemistry,Chemistry,1,2,false\n"
        )

        result = import_modules_csv(self.db, import_run_id=self.import_run_id, csv_path=csv_path)
        self.db.commit()

        self.assertEqual(result["created_count"], 0)
        self.assertEqual(result["updated_count"], 1)
        self.assertEqual(result["modules"][0]["name"], "Foundations of Chemistry")
        self.assertEqual(result["modules"][0]["semester_bucket"], 2)

    def test_warns_when_overriding_enrollment_derived_metadata(self):
        csv_path = self._write_csv(
            "module_code,module_name,subject_name,nominal_year,semester_bucket,is_full_year\n"
            "CHEM 11612,Foundations of Chemistry,Chemistry,2,1,false\n"
        )

        result = import_modules_csv(self.db, import_run_id=self.import_run_id, csv_path=csv_path)

        self.assertTrue(any("nominal_year overrides" in item["message"] for item in result["warnings"]))

    def test_rejects_unknown_module_code(self):
        csv_path = self._write_csv(
            "module_code,module_name,subject_name,nominal_year,semester_bucket,is_full_year\n"
            "NOPE 99999,Unknown Module,Unknown,1,1,false\n"
        )

        with self.assertRaises(ValueError) as context:
            import_modules_csv(self.db, import_run_id=self.import_run_id, csv_path=csv_path)

        self.assertIn("does not resolve to accepted enrollment-derived module data", str(context.exception))


if __name__ == "__main__":
    unittest.main()
