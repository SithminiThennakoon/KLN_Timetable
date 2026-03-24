import os
import sys
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient


TEST_DB_FILE = Path(tempfile.gettempdir()) / "kln_timetable_csv_routes_tests.sqlite"
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB_FILE}"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.database import Base, SessionLocal, engine  # noqa: E402
from app.main import create_app  # noqa: E402
from app.models.academic import CurriculumModule, StudentModuleMembership  # noqa: E402
from app.models.imports import ImportRun, ImportStudent  # noqa: E402
from app.models.snapshot import SnapshotLecturer, SnapshotRoom, SnapshotSharedSession  # noqa: E402


class ImportCsvRoutesTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(create_app())

    @classmethod
    def tearDownClass(cls):
        cls.client.close()
        engine.dispose()

    def setUp(self):
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
        self.db = SessionLocal()

    def tearDown(self):
        self.db.close()

    def _seed_materialized_import_run(self) -> tuple[int, int]:
        import_run = ImportRun(
            source_file="students_processed_TT_J.csv",
            source_format="uok_fos_enrollment_csv",
            status="materialized",
        )
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
        self.db.add_all([import_run, student, module])
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
        return int(import_run.id), int(module.id)

    def _post_csv(self, url: str, filename: str, content: str):
        return self.client.post(
            url,
            files={"file": (filename, content.encode("utf-8"), "text/csv")},
        )

    def test_uploads_modules_csv(self):
        import_run_id, module_id = self._seed_materialized_import_run()

        response = self._post_csv(
            f"/api/v2/imports/{import_run_id}/modules-upload",
            "modules.csv",
            "module_code,module_name,subject_name,nominal_year,semester_bucket,is_full_year\n"
            "CHEM 11612,Foundations of Chemistry,Chemistry,1,1,false\n",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["created_count"], 0)
        self.assertEqual(payload["updated_count"], 1)
        self.assertEqual(payload["modules"][0]["id"], module_id)

        self.db.expire_all()
        module = self.db.query(CurriculumModule).filter(CurriculumModule.id == module_id).first()
        self.assertIsNotNone(module)
        self.assertEqual(module.name, "Foundations of Chemistry")

    def test_uploads_rooms_csv(self):
        import_run_id, _module_id = self._seed_materialized_import_run()

        response = self._post_csv(
            f"/api/v2/imports/{import_run_id}/rooms-upload",
            "rooms.csv",
            "room_code,room_name,capacity,room_type,lab_type,location,year_restriction\n"
            "A7-H1,A7 Hall 1,180,lecture,,A7 Building,\n",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["created_count"], 1)
        self.assertEqual(payload["updated_count"], 0)
        self.assertEqual(payload["rooms"][0]["client_key"], "A7-H1")

        self.db.expire_all()
        room = self.db.query(SnapshotRoom).filter(SnapshotRoom.import_run_id == import_run_id).first()
        self.assertIsNotNone(room)
        self.assertEqual(room.name, "A7 Hall 1")

    def test_uploads_lecturers_csv(self):
        import_run_id, _module_id = self._seed_materialized_import_run()

        response = self._post_csv(
            f"/api/v2/imports/{import_run_id}/lecturers-upload",
            "lecturers.csv",
            "lecturer_code,name,email\n"
            "LECT-CHEM-01,Dr. Silva,silva@example.edu\n",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["created_count"], 1)
        self.assertEqual(payload["updated_count"], 0)
        self.assertEqual(payload["lecturers"][0]["client_key"], "LECT-CHEM-01")

        self.db.expire_all()
        lecturer = (
            self.db.query(SnapshotLecturer)
            .filter(SnapshotLecturer.import_run_id == import_run_id)
            .first()
        )
        self.assertIsNotNone(lecturer)
        self.assertEqual(lecturer.name, "Dr. Silva")

    def test_uploads_sessions_csv(self):
        import_run_id, module_id = self._seed_materialized_import_run()

        response = self._post_csv(
            f"/api/v2/imports/{import_run_id}/sessions-upload",
            "sessions.csv",
            "session_code,module_code,session_name,session_type,duration_minutes,occurrences_per_week,required_room_type,required_lab_type,specific_room_code,max_students_per_group,allow_parallel_rooms,notes\n"
            "CHEM11612-LEC,CHEM 11612,Chemistry Lecture,lecture,120,2,lecture,,,,false,Main weekly lecture\n",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["created_count"], 1)
        self.assertEqual(payload["updated_count"], 0)
        self.assertEqual(payload["shared_sessions"][0]["client_key"], "CHEM11612-LEC")
        self.assertEqual(payload["shared_sessions"][0]["curriculum_module_ids"], [module_id])

        self.db.expire_all()
        session = (
            self.db.query(SnapshotSharedSession)
            .filter(SnapshotSharedSession.import_run_id == import_run_id)
            .first()
        )
        self.assertIsNotNone(session)
        self.assertEqual(session.name, "Chemistry Lecture")

    def test_uploads_session_lecturers_csv(self):
        import_run_id, _module_id = self._seed_materialized_import_run()

        lecturers_response = self._post_csv(
            f"/api/v2/imports/{import_run_id}/lecturers-upload",
            "lecturers.csv",
            "lecturer_code,name,email\n"
            "LECT-CHEM-01,Dr. Silva,silva@example.edu\n",
        )
        self.assertEqual(lecturers_response.status_code, 200)

        sessions_response = self._post_csv(
            f"/api/v2/imports/{import_run_id}/sessions-upload",
            "sessions.csv",
            "session_code,module_code,session_name,session_type,duration_minutes,occurrences_per_week,required_room_type,allow_parallel_rooms\n"
            "CHEM11612-LEC,CHEM 11612,Chemistry Lecture,lecture,120,2,lecture,false\n",
        )
        self.assertEqual(sessions_response.status_code, 200)

        response = self._post_csv(
            f"/api/v2/imports/{import_run_id}/session-lecturers-upload",
            "session_lecturers.csv",
            "session_code,lecturer_code\n"
            "CHEM11612-LEC,LECT-CHEM-01\n",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["created_count"], 0)
        self.assertEqual(payload["updated_count"], 1)
        self.assertEqual(len(payload["shared_sessions"][0]["lecturer_ids"]), 1)

        self.db.expire_all()
        session = (
            self.db.query(SnapshotSharedSession)
            .filter(SnapshotSharedSession.import_run_id == import_run_id)
            .first()
        )
        self.assertIsNotNone(session)
        self.assertEqual(len(session.lecturers), 1)

    def test_upload_route_returns_404_for_missing_import_run(self):
        response = self._post_csv(
            "/api/v2/imports/999/rooms-upload",
            "rooms.csv",
            "room_code,room_name,capacity,room_type\nA7-H1,A7 Hall 1,180,lecture\n",
        )

        self.assertEqual(response.status_code, 404)
        self.assertIn("Import run 999 was not found", response.json()["detail"])

    def test_imports_demo_bundle_into_snapshot(self):
        import_run_id, _module_id = self._seed_materialized_import_run()

        response = self.client.post(f"/api/v2/imports/{import_run_id}/demo-bundle")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["import_run_id"], import_run_id)
        self.assertIn("lecturers_created", payload)
        self.assertIn("rooms_created", payload)
        self.assertIn("shared_sessions_created", payload)

    def test_workspace_includes_structured_readiness(self):
        import_run_id, _module_id = self._seed_materialized_import_run()

        response = self.client.get(f"/api/v2/imports/{import_run_id}/workspace")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("readiness", payload)
        self.assertFalse(payload["readiness"]["ready"])
        self.assertGreaterEqual(len(payload["readiness"]["import_needed"]), 1)
        self.assertEqual(payload["readiness"]["repair_needed"], [])


if __name__ == "__main__":
    unittest.main()
