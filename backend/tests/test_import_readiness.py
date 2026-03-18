import os
import sys
import tempfile
import unittest
from pathlib import Path


TEST_DB_FILE = Path(tempfile.gettempdir()) / "kln_timetable_import_readiness_tests.sqlite"
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB_FILE}"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.database import Base, SessionLocal, engine  # noqa: E402
from app.models.academic import CurriculumModule, StudentModuleMembership  # noqa: E402
from app.models.imports import ImportRun, ImportStudent  # noqa: E402
from app.models.snapshot import SnapshotLecturer, SnapshotRoom, SnapshotSharedSession  # noqa: E402
from app.models.solver import AttendanceGroup  # noqa: E402
from app.services.snapshot_completion import (  # noqa: E402
    build_import_readiness_summary,
    require_import_ready_for_generation,
)


class ImportReadinessTestCase(unittest.TestCase):
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

    def tearDown(self):
        self.db.close()

    def test_reports_missing_setup_layers(self):
        summary = build_import_readiness_summary(self.db, self.import_run_id)

        self.assertFalse(summary["ready"])
        self.assertIn("Import rooms.csv or add rooms manually.", summary["blocking"])
        self.assertIn("Import lecturers.csv or add lecturers manually.", summary["blocking"])
        self.assertIn("Import sessions.csv or add teaching sessions manually.", summary["blocking"])

        with self.assertRaises(ValueError) as context:
            require_import_ready_for_generation(self.db, self.import_run_id)
        self.assertIn("Import snapshot is not ready for generation:", str(context.exception))

    def test_reports_session_level_gaps(self):
        room = SnapshotRoom(
            import_run_id=self.import_run_id,
            client_key="A7-H1",
            name="A7 Hall 1",
            capacity=180,
            room_type="lecture",
            lab_type=None,
            location="A7",
            year_restriction=None,
            notes="",
        )
        lecturer = SnapshotLecturer(
            import_run_id=self.import_run_id,
            client_key="LECT-01",
            name="Dr. Silva",
            email=None,
            notes="",
        )
        session = SnapshotSharedSession(
            import_run_id=self.import_run_id,
            client_key="CHEM11612-LAB",
            name="Chemistry Lab",
            session_type="lab",
            duration_minutes=120,
            occurrences_per_week=1,
            required_room_type="lab",
            required_lab_type="chemistry",
            specific_room_id=None,
            max_students_per_group=30,
            allow_parallel_rooms=False,
            notes="",
        )
        self.db.add_all([room, lecturer, session])
        self.db.commit()

        summary = build_import_readiness_summary(self.db, self.import_run_id)

        self.assertIn("1 session still need lecturers.", summary["blocking"])
        self.assertIn("1 session still need attendance groups.", summary["blocking"])
        self.assertIn("1 session still need module links.", summary["blocking"])
        self.assertIn("1 lab-like session are not 180 minutes.", summary["warnings"])
        self.assertIn("1 split-limited session do not allow parallel rooms.", summary["warnings"])

    def test_reports_specific_room_mismatch(self):
        bad_room = SnapshotRoom(
            import_run_id=self.import_run_id,
            client_key="A7-H1",
            name="A7 Hall 1",
            capacity=20,
            room_type="lecture",
            lab_type=None,
            location="A7",
            year_restriction=None,
            notes="",
        )
        session = SnapshotSharedSession(
            import_run_id=self.import_run_id,
            client_key="CHEM11612-LAB",
            name="Chemistry Lab",
            session_type="lab",
            duration_minutes=180,
            occurrences_per_week=1,
            required_room_type="lab",
            required_lab_type="chemistry",
            specific_room=bad_room,
            max_students_per_group=None,
            allow_parallel_rooms=False,
            notes="",
        )
        self.db.add_all([bad_room, session])
        self.db.commit()

        summary = build_import_readiness_summary(self.db, self.import_run_id)

        self.assertIn(
            "Chemistry Lab has no room that can host it in required room A7 Hall 1.",
            summary["blocking"],
        )

    def test_reports_weekly_overload_warnings(self):
        room = SnapshotRoom(
            import_run_id=self.import_run_id,
            client_key="A7-H1",
            name="A7 Hall 1",
            capacity=300,
            room_type="lecture",
            lab_type=None,
            location="A7",
            year_restriction=None,
            notes="",
        )
        lecturer = SnapshotLecturer(
            import_run_id=self.import_run_id,
            client_key="LECT-01",
            name="Dr. Silva",
            email=None,
            notes="",
        )
        group = AttendanceGroup(
            import_run_id=self.import_run_id,
            academic_year="2022/2023",
            study_year=1,
            programme_id=None,
            programme_path_id=None,
            label="Y1 Chemistry",
            derivation_basis="student_membership",
            membership_signature="1",
            interpretation_confidence="high",
            student_count=40,
            notes="",
        )
        session = SnapshotSharedSession(
            import_run_id=self.import_run_id,
            client_key="CHEM11612-LEC",
            name="Chemistry Lecture",
            session_type="lecture",
            duration_minutes=300,
            occurrences_per_week=10,
            required_room_type="lecture",
            required_lab_type=None,
            specific_room=room,
            max_students_per_group=None,
            allow_parallel_rooms=False,
            notes="",
        )
        session.lecturers.append(lecturer)
        session.attendance_groups.append(group)
        self.db.add_all([room, lecturer, group, session])
        self.db.commit()

        summary = build_import_readiness_summary(self.db, self.import_run_id)

        self.assertTrue(
            any("Dr. Silva is assigned" in warning for warning in summary["warnings"])
        )
        self.assertTrue(
            any("Y1 Chemistry requires" in warning for warning in summary["warnings"])
        )

    def test_allows_generation_when_readiness_is_clear(self):
        room = SnapshotRoom(
            import_run_id=self.import_run_id,
            client_key="A7-H1",
            name="A7 Hall 1",
            capacity=300,
            room_type="lecture",
            lab_type=None,
            location="A7",
            year_restriction=None,
            notes="",
        )
        lecturer = SnapshotLecturer(
            import_run_id=self.import_run_id,
            client_key="LECT-01",
            name="Dr. Silva",
            email=None,
            notes="",
        )
        group = AttendanceGroup(
            import_run_id=self.import_run_id,
            academic_year="2022/2023",
            study_year=1,
            programme_id=None,
            programme_path_id=None,
            label="Y1 Chemistry",
            derivation_basis="student_membership",
            membership_signature="2",
            interpretation_confidence="high",
            student_count=40,
            notes="",
        )
        session = SnapshotSharedSession(
            import_run_id=self.import_run_id,
            client_key="CHEM11612-LEC",
            name="Chemistry Lecture",
            session_type="lecture",
            duration_minutes=120,
            occurrences_per_week=2,
            required_room_type="lecture",
            required_lab_type=None,
            specific_room=room,
            max_students_per_group=None,
            allow_parallel_rooms=False,
            notes="",
        )
        session.lecturers.append(lecturer)
        session.attendance_groups.append(group)
        session.curriculum_modules.append(self.db.query(CurriculumModule).one())
        self.db.add_all([room, lecturer, group, session])
        self.db.commit()

        summary = require_import_ready_for_generation(self.db, self.import_run_id)
        self.assertTrue(summary["ready"])


if __name__ == "__main__":
    unittest.main()
