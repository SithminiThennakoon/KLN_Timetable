import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.import_templates import (  # noqa: E402
    get_import_template,
    list_import_templates,
    render_import_template_csv,
)


class ImportTemplatesTestCase(unittest.TestCase):
    def test_lists_expected_templates(self):
        templates = list_import_templates()
        names = {item["name"] for item in templates}

        self.assertIn("student_enrollments", names)
        self.assertIn("rooms", names)
        self.assertIn("lecturers", names)
        self.assertIn("sessions", names)
        self.assertIn("session_lecturers", names)

    def test_renders_rooms_template_csv(self):
        rendered = render_import_template_csv("rooms")

        self.assertIsNotNone(rendered)
        filename, content = rendered
        self.assertEqual(filename, "rooms_template.csv")
        self.assertIn("room_code,room_name,capacity,room_type,lab_type,location,year_restriction", content)
        self.assertIn("CHEM-LAB-1,Chemistry Lab 1,30,lab,chemistry,Science Block,", content)

    def test_returns_none_for_unknown_template(self):
        self.assertIsNone(get_import_template("unknown_template"))
        self.assertIsNone(render_import_template_csv("unknown_template"))


if __name__ == "__main__":
    unittest.main()
