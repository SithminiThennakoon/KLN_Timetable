import os
import sys
import tempfile
import unittest
from pathlib import Path


TEST_DB_FILE = Path(tempfile.gettempdir()) / "kln_timetable_session_csv_import_tests.sqlite"
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB_FILE}"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.database import Base, SessionLocal, engine  # noqa: E402
from app.models.academic import CurriculumModule, StudentModuleMembership  # noqa: E402
from app.models.imports import ImportRun, ImportStudent  # noqa: E402
from app.models.snapshot import SnapshotRoom, SnapshotSharedSession  # noqa: E402
from app.services.session_csv_import import import_sessions_csv  # noqa: E402


class SessionCsvImportTestCase(unittest.TestCase):
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
        room = SnapshotRoom(
            import_run_id=import_run.id,
            client_key="CHEM-LAB-1",
            name="Chemistry Lab 1",
            capacity=30,
            room_type="lab",
            lab_type="chemistry",
            location="Science Block",
            year_restriction=None,
            notes="seed",
        )
        self.db.add_all([student, module, room])
        self.db.flush()
        membership = StudentModuleMembership(
            import_run_id=import_run.id,
            student_id=student.id,
            curriculum_module_id=module.id,
            student_programme_context_id=None,
            import_enrollment_id=None,
            membership_source="import",
        )
        self.db.add(membership)
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

    def test_imports_sessions_csv(self):
        csv_path = self._write_csv(
            "session_code,module_code,session_name,session_type,duration_minutes,occurrences_per_week,required_room_type,required_lab_type,specific_room_code,max_students_per_group,allow_parallel_rooms,notes\n"
            "CHEM11612-LEC,CHEM 11612,Chemistry Lecture,lecture,120,2,lecture,,,,false,Main lecture\n"
            "CHEM11612-LAB,CHEM 11612,Chemistry Lab,lab,180,1,lab,chemistry,CHEM-LAB-1,30,true,Main lab\n"
        )

        result = import_sessions_csv(self.db, import_run_id=self.import_run_id, csv_path=csv_path)
        self.db.commit()

        self.assertEqual(result["created_count"], 2)
        self.assertEqual(result["updated_count"], 0)
        self.assertEqual(len(result["shared_sessions"]), 2)

    def test_upserts_existing_session_by_code(self):
        first_csv = self._write_csv(
            "session_code,module_code,session_name,session_type,duration_minutes,occurrences_per_week,required_room_type,required_lab_type,specific_room_code,max_students_per_group,allow_parallel_rooms,notes\n"
            "CHEM11612-LEC,CHEM 11612,Chemistry Lecture,lecture,120,2,lecture,,,,false,First\n"
        )
        second_csv = self._write_csv(
            "session_code,module_code,session_name,session_type,duration_minutes,occurrences_per_week,required_room_type,required_lab_type,specific_room_code,max_students_per_group,allow_parallel_rooms,notes\n"
            "CHEM11612-LEC,CHEM 11612,Chemistry Lecture Updated,lecture,90,1,lecture,,,,false,Updated\n"
        )

        import_sessions_csv(self.db, import_run_id=self.import_run_id, csv_path=first_csv)
        self.db.commit()
        result = import_sessions_csv(self.db, import_run_id=self.import_run_id, csv_path=second_csv)
        self.db.commit()

        self.assertEqual(result["created_count"], 0)
        self.assertEqual(result["updated_count"], 1)

        saved = (
            self.db.query(SnapshotSharedSession)
            .filter(SnapshotSharedSession.import_run_id == self.import_run_id)
            .one()
        )
        self.assertEqual(saved.name, "Chemistry Lecture Updated")
        self.assertEqual(saved.duration_minutes, 90)

    def test_rejects_unknown_module_code(self):
        csv_path = self._write_csv(
            "session_code,module_code,session_name,session_type,duration_minutes,occurrences_per_week,required_room_type,required_lab_type,specific_room_code,max_students_per_group,allow_parallel_rooms,notes\n"
            "UNKNOWN-LEC,NOPE 99999,Unknown Lecture,lecture,120,1,lecture,,,,false,Bad\n"
        )

        with self.assertRaises(ValueError) as context:
            import_sessions_csv(self.db, import_run_id=self.import_run_id, csv_path=csv_path)

        self.assertIn("do not resolve to accepted module data", str(context.exception))

    def test_imports_multi_module_session_from_module_codes_column(self):
        student = self.db.query(ImportStudent).first()
        self.assertIsNotNone(student)
        second_module = CurriculumModule(
            code="CHEM 22612",
            canonical_code="CHEM 22612",
            name="Advanced Chemistry",
            subject_name="Chemistry",
            subject_code="CHEM",
            nominal_year=2,
            semester_bucket=1,
            is_full_year=False,
        )
        self.db.add(second_module)
        self.db.flush()
        self.db.add(
            StudentModuleMembership(
                import_run_id=self.import_run_id,
                student_id=int(student.id),
                curriculum_module_id=second_module.id,
                student_programme_context_id=None,
                import_enrollment_id=None,
                membership_source="import",
            )
        )
        self.db.commit()

        csv_path = self._write_csv(
            "session_code,module_code,module_codes,session_name,session_type,duration_minutes,occurrences_per_week,required_room_type,required_lab_type,specific_room_code,max_students_per_group,allow_parallel_rooms,notes\n"
            "CHEM11612-SHARED,CHEM 11612,CHEM 22612,Shared Chemistry Lecture,lecture,120,1,lecture,,,,false,Shared\n"
        )

        result = import_sessions_csv(self.db, import_run_id=self.import_run_id, csv_path=csv_path)
        self.db.commit()

        self.assertEqual(result["created_count"], 1)
        saved = (
            self.db.query(SnapshotSharedSession)
            .filter(SnapshotSharedSession.import_run_id == self.import_run_id)
            .one()
        )
        self.assertEqual(
            {module.code for module in saved.curriculum_modules},
            {"CHEM 11612", "CHEM 22612"},
        )

    def test_rejects_same_name_type_with_different_session_code(self):
        self.db.add(
            SnapshotSharedSession(
                import_run_id=self.import_run_id,
                client_key="manual_session_1",
                name="Chemistry Lecture",
                session_type="lecture",
                duration_minutes=120,
                occurrences_per_week=2,
                required_room_type="lecture",
                required_lab_type=None,
                specific_room_id=None,
                max_students_per_group=None,
                allow_parallel_rooms=False,
                notes="manual",
            )
        )
        self.db.commit()
        csv_path = self._write_csv(
            "session_code,module_code,session_name,session_type,duration_minutes,occurrences_per_week,required_room_type,required_lab_type,specific_room_code,max_students_per_group,allow_parallel_rooms,notes\n"
            "CHEM11612-LEC-CSV,CHEM 11612,Chemistry Lecture,lecture,120,2,lecture,,,,false,Conflict\n"
        )

        with self.assertRaises(ValueError) as context:
            import_sessions_csv(self.db, import_run_id=self.import_run_id, csv_path=csv_path)

        self.assertIn("Re-import only updates matching session_code values", str(context.exception))


if __name__ == "__main__":
    unittest.main()
