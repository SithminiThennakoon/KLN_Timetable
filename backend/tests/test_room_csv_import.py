import os
import sys
import tempfile
import unittest
from pathlib import Path


TEST_DB_FILE = Path(tempfile.gettempdir()) / "kln_timetable_room_csv_import_tests.sqlite"
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB_FILE}"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.database import Base, SessionLocal, engine  # noqa: E402
from app.models.imports import ImportRun  # noqa: E402
from app.models.snapshot import SnapshotRoom  # noqa: E402
from app.services.room_csv_import import import_rooms_csv  # noqa: E402


class RoomCsvImportTestCase(unittest.TestCase):
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

    def test_imports_rooms_csv_and_emits_warnings(self):
        csv_path = self._write_csv(
            "room_code,room_name,capacity,room_type,lab_type,location,year_restriction\n"
            "A7-H1,A7 Hall 1,180,lecture,,A7 Building,\n"
            "CHEM-LAB-1,Chemistry Lab 1,30,lab,,Science Block,\n"
        )

        result = import_rooms_csv(self.db, import_run_id=self.import_run_id, csv_path=csv_path)
        self.db.commit()

        self.assertEqual(result["created_count"], 2)
        self.assertEqual(result["updated_count"], 0)
        self.assertEqual(len(result["rooms"]), 2)
        self.assertTrue(any("has no lab_type" in item["message"] for item in result["warnings"]))

    def test_upserts_existing_room_by_room_code(self):
        first_csv = self._write_csv(
            "room_code,room_name,capacity,room_type,lab_type,location,year_restriction\n"
            "A7-H1,A7 Hall 1,180,lecture,,A7 Building,\n"
        )
        second_csv = self._write_csv(
            "room_code,room_name,capacity,room_type,lab_type,location,year_restriction\n"
            "A7-H1,A7 Hall 1,220,lecture,,Updated Building,\n"
        )

        import_rooms_csv(self.db, import_run_id=self.import_run_id, csv_path=first_csv)
        self.db.commit()
        result = import_rooms_csv(self.db, import_run_id=self.import_run_id, csv_path=second_csv)
        self.db.commit()

        self.assertEqual(result["created_count"], 0)
        self.assertEqual(result["updated_count"], 1)

        saved_room = (
            self.db.query(SnapshotRoom)
            .filter(SnapshotRoom.import_run_id == self.import_run_id)
            .one()
        )
        self.assertEqual(saved_room.capacity, 220)
        self.assertEqual(saved_room.location, "Updated Building")

    def test_rejects_duplicate_room_codes_within_file(self):
        csv_path = self._write_csv(
            "room_code,room_name,capacity,room_type,lab_type,location,year_restriction\n"
            "A7-H1,A7 Hall 1,180,lecture,,A7 Building,\n"
            "A7-H1,A7 Hall 1 Annex,90,lecture,,A7 Building,\n"
        )

        with self.assertRaises(ValueError) as context:
            import_rooms_csv(self.db, import_run_id=self.import_run_id, csv_path=csv_path)

        self.assertIn("duplicate room_code 'A7-H1'", str(context.exception))

    def test_rejects_same_name_with_different_room_code(self):
        self.db.add(
            SnapshotRoom(
                import_run_id=self.import_run_id,
                client_key="manual_room_1",
                name="A7 Hall 1",
                capacity=180,
                room_type="lecture",
                lab_type=None,
                location="A7 Building",
                year_restriction=None,
                notes="manual",
            )
        )
        self.db.commit()
        csv_path = self._write_csv(
            "room_code,room_name,capacity,room_type,lab_type,location,year_restriction\n"
            "A7-H1-CSV,A7 Hall 1,180,lecture,,A7 Building,\n"
        )

        with self.assertRaises(ValueError) as context:
            import_rooms_csv(self.db, import_run_id=self.import_run_id, csv_path=csv_path)

        self.assertIn("Re-import only updates matching room_code values", str(context.exception))


if __name__ == "__main__":
    unittest.main()
