from sqlalchemy.orm import Session
from sqlalchemy import text

from app.core.database import SessionLocal
from app.models.department import Department
from app.models.subject import Subject
from app.models.pathway import Pathway
from app.models.module import Module
from app.models.session import Session as SessionModel
from app.models.lecturer import Lecturer
from app.models.room import Room


def reset_tables(db: Session) -> None:
    db.execute(text("SET FOREIGN_KEY_CHECKS=0;"))
    db.query(SessionModel).delete()
    db.query(Module).delete()
    db.query(Pathway).delete()
    db.query(Subject).delete()
    db.query(Department).delete()
    db.query(Lecturer).delete()
    db.query(Room).delete()
    db.commit()
    db.execute(text("SET FOREIGN_KEY_CHECKS=1;"))


def seed_demo(db: Session) -> None:
    physical = Department(name="Physical Science", code="PHY_SCI")
    biological = Department(name="Biological Science", code="BIO_SCI")
    db.add_all([physical, biological])
    db.commit()

    subjects = [
        Subject(name="Physics", code="PHY", department_id=physical.id),
        Subject(name="Chemistry", code="CHM", department_id=physical.id),
        Subject(name="Pure Mathematics", code="PMT", department_id=physical.id),
        Subject(name="Applied Mathematics", code="AMT", department_id=physical.id),
        Subject(name="Computer Science", code="CSC", department_id=physical.id),
        Subject(name="Biology", code="BIO", department_id=biological.id),
    ]
    db.add_all(subjects)
    db.commit()

    subject_map = {s.code: s for s in subjects}

    pathways = [
        Pathway(name="Physics / Pure Math / Applied Math", department_id=physical.id, year=2),
        Pathway(name="Chemistry / Pure Math / Applied Math", department_id=physical.id, year=2),
        Pathway(name="Computer Science / Pure Math / Applied Math", department_id=physical.id, year=2),
        Pathway(name="Biology / Chemistry / Physics", department_id=biological.id, year=2),
    ]
    pathways[0].subjects = [subject_map["PHY"], subject_map["PMT"], subject_map["AMT"]]
    pathways[1].subjects = [subject_map["CHM"], subject_map["PMT"], subject_map["AMT"]]
    pathways[2].subjects = [subject_map["CSC"], subject_map["PMT"], subject_map["AMT"]]
    pathways[3].subjects = [subject_map["BIO"], subject_map["CHM"], subject_map["PHY"]]
    db.add_all(pathways)
    db.commit()

    lecturers = [
        Lecturer(name="Dr. Perera", email="perera@kln.ac.lk", max_hours_per_week=12),
        Lecturer(name="Dr. Silva", email="silva@kln.ac.lk", max_hours_per_week=10),
        Lecturer(name="Dr. Jayasinghe", email="jayasinghe@kln.ac.lk", max_hours_per_week=12),
        Lecturer(name="Dr. Fernando", email="fernando@kln.ac.lk", max_hours_per_week=8),
        Lecturer(name="Ms. Rodrigo", email="rodrigo@kln.ac.lk", max_hours_per_week=10),
    ]
    db.add_all(lecturers)
    db.commit()

    rooms = [
        Room(name="LH-101", capacity=220, room_type="lecture_hall", lab_type=None, location="Main", year_restriction=None),
        Room(name="LH-201", capacity=140, room_type="lecture_hall", lab_type=None, location="Main", year_restriction=None),
        Room(name="Physics Lab 1", capacity=100, room_type="laboratory", lab_type="physics_lab", location="Science Wing", year_restriction=2),
        Room(name="Physics Lab 2", capacity=100, room_type="laboratory", lab_type="physics_lab", location="Science Wing", year_restriction=2),
        Room(name="Chemistry Lab", capacity=80, room_type="laboratory", lab_type="chemistry_lab", location="Science Wing", year_restriction=None),
        Room(name="CS Lab", capacity=60, room_type="laboratory", lab_type="computer_lab", location="Tech Block", year_restriction=None),
        Room(name="CS Lab 2", capacity=60, room_type="laboratory", lab_type="computer_lab", location="Tech Block", year_restriction=None),
    ]
    db.add_all(rooms)
    db.commit()

    modules = [
        Module(code="PHY2101", name="Thermodynamics", subject_id=subject_map["PHY"].id, year=2, semester=1),
        Module(code="PHY2102", name="Solid State Physics", subject_id=subject_map["PHY"].id, year=2, semester=1),
        Module(code="PHY2103", name="Physics Practical", subject_id=subject_map["PHY"].id, year=2, semester=1),
        Module(code="CHM2101", name="Organic Chemistry", subject_id=subject_map["CHM"].id, year=2, semester=1),
        Module(code="CHM2102", name="Chemistry Practical", subject_id=subject_map["CHM"].id, year=2, semester=1),
        Module(code="PMT2101", name="Ordinary Differential Equations", subject_id=subject_map["PMT"].id, year=2, semester=1),
        Module(code="AMT2101", name="Applied Statistics", subject_id=subject_map["AMT"].id, year=2, semester=1),
        Module(code="CSC2101", name="Data Structures", subject_id=subject_map["CSC"].id, year=2, semester=1),
        Module(code="CSC2102", name="Programming Lab", subject_id=subject_map["CSC"].id, year=2, semester=1),
        Module(code="BIO2101", name="Cell Biology", subject_id=subject_map["BIO"].id, year=2, semester=1),
    ]
    db.add_all(modules)
    db.commit()

    module_map = {m.code: m for m in modules}

    sessions = [
        SessionModel(
            module_id=module_map["PMT2101"].id,
            session_type="lecture",
            duration_hours=1,
            frequency_per_week=1,
            requires_lab_type=None,
            student_count=180,
            max_students_per_group=None,
            concurrent_split=False,
            lecturers=[lecturers[0]],
        ),
        SessionModel(
            module_id=module_map["PHY2101"].id,
            session_type="lecture",
            duration_hours=1,
            frequency_per_week=1,
            requires_lab_type=None,
            student_count=200,
            max_students_per_group=None,
            concurrent_split=False,
            lecturers=[lecturers[1]],
        ),
        SessionModel(
            module_id=module_map["PHY2101"].id,
            session_type="lecture",
            duration_hours=1,
            frequency_per_week=1,
            requires_lab_type=None,
            student_count=200,
            max_students_per_group=None,
            concurrent_split=False,
            lecturers=[lecturers[2]],
        ),
        SessionModel(
            module_id=module_map["PHY2103"].id,
            session_type="practical",
            duration_hours=1,
            frequency_per_week=1,
            requires_lab_type="physics_lab",
            student_count=200,
            max_students_per_group=100,
            concurrent_split=False,
            lecturers=[lecturers[1]],
        ),
        SessionModel(
            module_id=module_map["CHM2101"].id,
            session_type="lecture",
            duration_hours=1,
            frequency_per_week=1,
            requires_lab_type=None,
            student_count=160,
            max_students_per_group=None,
            concurrent_split=False,
            lecturers=[lecturers[3]],
        ),
        SessionModel(
            module_id=module_map["CHM2102"].id,
            session_type="practical",
            duration_hours=1,
            frequency_per_week=1,
            requires_lab_type="chemistry_lab",
            student_count=160,
            max_students_per_group=80,
            concurrent_split=False,
            lecturers=[lecturers[3]],
        ),
        SessionModel(
            module_id=module_map["CSC2101"].id,
            session_type="lecture",
            duration_hours=1,
            frequency_per_week=1,
            requires_lab_type=None,
            student_count=120,
            max_students_per_group=None,
            concurrent_split=False,
            lecturers=[lecturers[4]],
        ),
        SessionModel(
            module_id=module_map["CSC2102"].id,
            session_type="practical",
            duration_hours=1,
            frequency_per_week=1,
            requires_lab_type="computer_lab",
            student_count=120,
            max_students_per_group=60,
            concurrent_split=False,
            lecturers=[lecturers[4]],
        ),
        SessionModel(
            module_id=module_map["BIO2101"].id,
            session_type="lecture",
            duration_hours=1,
            frequency_per_week=1,
            requires_lab_type=None,
            student_count=140,
            max_students_per_group=None,
            concurrent_split=False,
            lecturers=[lecturers[0]],
        ),
    ]
    db.add_all(sessions)
    db.commit()


if __name__ == "__main__":
    db = SessionLocal()
    try:
        reset_tables(db)
        seed_demo(db)
        print("Demo data seeded successfully.")
    finally:
        db.close()
