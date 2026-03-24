import os
import sys
import tempfile
import unittest
from pathlib import Path


TEST_DB_FILE = Path(tempfile.gettempdir()) / "kln_timetable_session_lecturer_csv_import_tests.sqlite"
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB_FILE}"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.database import Base, SessionLocal, engine  # noqa: E402
from app.models.academic import CurriculumModule, StudentModuleMembership  # noqa: E402
from app.models.imports import ImportRun, ImportStudent  # noqa: E402
from app.models.snapshot import SnapshotLecturer, SnapshotSharedSession  # noqa: E402
from app.services.lecturer_csv_import import import_lecturers_csv  # noqa: E402
from app.services.session_csv_import import import_sessions_csv  # noqa: E402
from app.services.session_lecturer_csv_import import (  # noqa: E402
    import_session_lecturers_csv,
)


class SessionLecturerCsvImportTestCase(unittest.TestCase):
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
            name="Foundations of Chemistry",
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

        lecturers_csv = self._write_csv(
            "lecturer_code,name,email\n"
            "LECT-CHEM-01,Dr. Silva,silva@example.edu\n"
            "LECT-CHEM-02,Prof. Perera,perera@example.edu\n"
        )
        sessions_csv = self._write_csv(
            "session_code,module_code,session_name,session_type,duration_minutes,occurrences_per_week,required_room_type,required_lab_type,specific_room_code,max_students_per_group,allow_parallel_rooms,notes\n"
            "CHEM11612-LEC,CHEM 11612,Chemistry Lecture,lecture,120,2,lecture,,,,false,Main lecture\n"
        )
        import_lecturers_csv(self.db, import_run_id=self.import_run_id, csv_path=lecturers_csv)
        import_sessions_csv(self.db, import_run_id=self.import_run_id, csv_path=sessions_csv)
        self.db.commit()

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

    def test_links_lecturers_to_sessions(self):
        csv_path = self._write_csv(
            "session_code,lecturer_code\n"
            "CHEM11612-LEC,LECT-CHEM-01\n"
            "CHEM11612-LEC,LECT-CHEM-02\n"
        )

        result = import_session_lecturers_csv(
            self.db, import_run_id=self.import_run_id, csv_path=csv_path
        )
        self.db.commit()

        self.assertEqual(result["created_count"], 0)
        self.assertEqual(result["updated_count"], 1)
        self.assertEqual(len(result["shared_sessions"]), 1)

        saved = (
            self.db.query(SnapshotSharedSession)
            .filter(SnapshotSharedSession.import_run_id == self.import_run_id)
            .one()
        )
        self.assertEqual(len(saved.lecturers), 2)

    def test_preserves_existing_links_when_adding_more(self):
        first_csv = self._write_csv(
            "session_code,lecturer_code\n"
            "CHEM11612-LEC,LECT-CHEM-01\n"
        )
        second_csv = self._write_csv(
            "session_code,lecturer_code\n"
            "CHEM11612-LEC,LECT-CHEM-02\n"
        )

        import_session_lecturers_csv(self.db, import_run_id=self.import_run_id, csv_path=first_csv)
        self.db.commit()
        import_session_lecturers_csv(self.db, import_run_id=self.import_run_id, csv_path=second_csv)
        self.db.commit()

        saved = (
            self.db.query(SnapshotSharedSession)
            .filter(SnapshotSharedSession.import_run_id == self.import_run_id)
            .one()
        )
        self.assertEqual(len(saved.lecturers), 2)

    def test_rejects_unknown_session_or_lecturer(self):
        csv_path = self._write_csv(
            "session_code,lecturer_code\n"
            "NOPE-LEC,LECT-CHEM-01\n"
        )

        with self.assertRaises(ValueError) as context:
            import_session_lecturers_csv(
                self.db, import_run_id=self.import_run_id, csv_path=csv_path
            )

        self.assertIn("does not resolve to an imported session", str(context.exception))


if __name__ == "__main__":
    unittest.main()
