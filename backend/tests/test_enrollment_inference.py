import csv
import sys
import tempfile
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.enrollment_inference import build_realistic_demo_dataset_from_enrollment_csv  # noqa: E402
from app.schemas.v2 import DatasetUpsertRequest  # noqa: E402


def _append_rows(rows, *, course_path_no, course_code, year, academic_year, stream, batch, student_count):
    for index in range(student_count):
        rows.append(
            {
                "CoursePathNo": course_path_no,
                "CourseCode": course_code,
                "Year": str(year),
                "AcYear": academic_year,
                "Attempt": "1",
                "stream": stream,
                "batch": batch,
                "student_hash": f"{stream}_{year}_{course_path_no}_{batch}_{course_code}_{index}",
            }
        )


class EnrollmentInferenceTests(unittest.TestCase):
    def test_realistic_demo_builder_normalizes_semesters_and_generates_multi_year_dataset(self):
        rows = []

        # Year 1: one very large shared cohort to force a 120-minute lecture.
        _append_rows(
            rows,
            course_path_no="1",
            course_code="CHEM 11312",
            year=1,
            academic_year="2022/2023",
            stream="PS",
            batch="2022",
            student_count=250,
        )
        _append_rows(
            rows,
            course_path_no="1",
            course_code="PHYS 12412",
            year=1,
            academic_year="2022/2023",
            stream="PS",
            batch="2022",
            student_count=250,
        )

        # Years 2-4: smaller cohorts with second-digit semester buckets 3/4
        # to verify normalization back into the app's two-semester model.
        for year, batch in ((2, "2021"), (3, "2020"), (4, "2019")):
            _append_rows(
                rows,
                course_path_no="1",
                course_code=f"CHEM {year}1312",
                year=year,
                academic_year="2022/2023",
                stream="PS",
                batch=batch,
                student_count=24,
            )
            _append_rows(
                rows,
                course_path_no="1",
                course_code=f"PHYS {year}2412",
                year=year,
                academic_year="2022/2023",
                stream="PS",
                batch=batch,
                student_count=24,
            )

        with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="", suffix=".csv", delete=False) as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=[
                    "CoursePathNo",
                    "CourseCode",
                    "Year",
                    "AcYear",
                    "Attempt",
                    "stream",
                    "batch",
                    "student_hash",
                ],
            )
            writer.writeheader()
            writer.writerows(rows)
            csv_path = handle.name

        self.addCleanup(lambda: Path(csv_path).unlink(missing_ok=True))

        dataset = build_realistic_demo_dataset_from_enrollment_csv(csv_path)
        DatasetUpsertRequest(**dataset)

        modules = dataset["modules"]
        sessions = dataset["sessions"]
        semesters = {module["semester"] for module in modules}
        years = {module["year"] for module in modules}
        durations = {session["duration_minutes"] for session in sessions}
        lecture_sessions = [session for session in sessions if session["session_type"] == "lecture"]
        lab_sessions = [session for session in sessions if session["session_type"] == "lab"]

        self.assertEqual(semesters, {1, 2})
        self.assertEqual(years, {1, 2, 3, 4})
        self.assertTrue(all(module["semester"] in {1, 2} for module in modules))
        self.assertTrue(any(session["duration_minutes"] == 120 for session in lecture_sessions))
        self.assertTrue(any(session["duration_minutes"] == 180 for session in lab_sessions))
        self.assertTrue(all(session["duration_minutes"] in {60, 120, 180} for session in sessions))
        self.assertGreaterEqual(len(lab_sessions), 1)


if __name__ == "__main__":
    unittest.main()
