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
    # === DEPARTMENTS ===
    physical = Department(name="Physical Science", code="PHY_SCI")
    biological = Department(name="Biological Science", code="BIO_SCI")
    db.add_all([physical, biological])
    db.commit()

    # === SUBJECTS ===
    subjects_data = [
        ("Pure Mathematics", "PMAT", physical.id),
        ("Applied Mathematics", "AMAT", physical.id),
        ("Statistics", "STAT", physical.id),
        ("Physics", "PHYS", physical.id),
        ("Chemistry", "CHEM", physical.id),
        ("Electronics", "ELEC", physical.id),
        ("Computer Science", "COSC", physical.id),
        ("Computer Studies", "COST", physical.id),
        ("Biochemistry", "BIOC", biological.id),
        ("Microbiology", "MIBI", biological.id),
        ("Plant Biology", "PLBL", biological.id),
        ("Zoology", "ZOOL", biological.id),
        ("Environmental Conservation & Management", "ENCM", biological.id),
        ("Applied Chemistry", "APCH", physical.id),
        ("Electronics & Computer Science", "BECS", physical.id),
        ("Management Accounting", "MACS", physical.id),
        ("Management & Applied Science", "MAPS", physical.id),
        ("Management", "MGMT", physical.id),
        ("Common Skills", "CMSK", physical.id),
    ]
    subjects = [Subject(name=name, code=code, department_id=dept_id) for name, code, dept_id in subjects_data]
    db.add_all(subjects)
    db.commit()

    subject_map = {s.code: s for s in subjects}

    # === ROOMS ===
    rooms_data = [
        ("A11 201", 200, "lecture_hall", None, "A11 Building", None),
        ("A11 207", 150, "lecture_hall", None, "A11 Building", None),
        ("A11 307", 120, "lecture_hall", None, "A11 Building", None),
        ("A7 201", 150, "lecture_hall", None, "A7 Building", None),
        ("A7 301", 100, "lecture_hall", None, "A7 Building", None),
        ("A7 303", 100, "lecture_hall", None, "A7 Building", None),
        ("A7 406", 80, "lecture_hall", None, "A7 Building", None),
        ("B1 212", 200, "lecture_hall", None, "B1 Building", None),
        ("B1 343", 150, "lecture_hall", None, "B1 Building", None),
        ("B1 203", 50, "laboratory", "zoology_lab", "B1 Building", None),
        ("B1 207", 50, "laboratory", "zoology_lab", "B1 Building", None),
        ("Chemistry Lab", 60, "laboratory", "chemistry_lab", "Science Wing", None),
        ("Physics Lab", 60, "laboratory", "physics_lab", "Science Wing", None),
        ("Physics Lab 2", 60, "laboratory", "physics_lab", "Science Wing", None),
        ("Computer Lab", 70, "laboratory", "computer_lab", "Tech Block", None),
        ("Computer Lab 2", 70, "laboratory", "computer_lab", "Tech Block", None),
        ("Computer Lab 3", 70, "laboratory", "computer_lab", "Tech Block", None),
        ("Computer Lab 4", 70, "laboratory", "computer_lab", "Tech Block", None),
        ("EM Lab", 40, "laboratory", "em_lab", "Science Wing", None),
        ("EM Lab 2", 40, "laboratory", "em_lab", "Science Wing", None),
        ("APCH Lab", 50, "laboratory", "chemistry_lab", "Science Wing", None),
        ("PLBL Lab", 60, "laboratory", "plant_bio_lab", "Science Wing", None),
        ("PLBL Lab 2", 60, "laboratory", "plant_bio_lab", "Science Wing", None),
        ("MIBI Lab", 50, "laboratory", "microbio_lab", "Science Wing", None),
        ("Gymnasium/Ground", 200, "laboratory", "gymnasium", "Sports Complex", None),
        ("Gymnasium 2", 200, "laboratory", "gymnasium", "Sports Complex", None),
        ("Auditorium", 300, "lecture_hall", None, "Main Building", None),
    ]
    rooms = [Room(name=name, capacity=cap, room_type=rtype, lab_type=ltype, location=loc, year_restriction=yr)
             for name, cap, rtype, ltype, loc, yr in rooms_data]
    db.add_all(rooms)
    db.commit()

    # === LECTURERS ===
    lecturers_data = [
        ("Prof. K. Perera", "perera@kln.ac.lk", 12),
        ("Prof. S. De Silva", "desilva@kln.ac.lk", 12),
        ("Prof. N. Fernando", "fernando@kln.ac.lk", 12),
        ("Dr. R. Jayasinghe", "jayasinghe@kln.ac.lk", 10),
        ("Dr. M. Wickramasinghe", "wickramasinghe@kln.ac.lk", 10),
        ("Dr. V. Perera", "vperera@kln.ac.lk", 8),
        ("Prof. T. Bandaranaike", "bandaranaike@kln.ac.lk", 12),
        ("Dr. R. Wijewardena", "wijewardena@kln.ac.lk", 10),
        ("Dr. A. Gunasekara", "gunasekara@kln.ac.lk", 10),
        ("Ms. S. Fonseka", "sfonseka@kln.ac.lk", 10),
        ("Dr. P. Dissanayake", "dissanayake@kln.ac.lk", 10),
        ("Dr. M. De Alwis", "dealwis@kln.ac.lk", 10),
        ("Dr. L. Ranil", "ranil@kln.ac.lk", 8),
        ("Dr. S. Kumara", "kumara@kln.ac.lk", 10),
        ("Dr. H. Pathirana", "pathirana@kln.ac.lk", 10),
        ("Ms. N. Rodrigo", "rodrigo@kln.ac.lk", 10),
        ("Ms. K. Weerawardena", "weerawardena@kln.ac.lk", 10),
        ("Prof. B. Atapattu", "atapattu@kln.ac.lk", 12),
        ("Dr. G. Senanayake", "senanayake@kln.ac.lk", 10),
        ("Dr. W. Liyanage", "liyanage@kln.ac.lk", 10),
        ("Prof. M. Abeysekera", "abeysekera@kln.ac.lk", 12),
        ("Dr. U. Peiris", "peiris@kln.ac.lk", 8),
        ("Prof. A. De Zoysa", "dezoysa@kln.ac.lk", 12),
        ("Dr. D. Samarasinghe", "samarasinghe@kln.ac.lk", 10),
        ("Dr. C. Ratnayake", "ratnayake@kln.ac.lk", 10),
        ("Prof. J. Silva", "jsilva@kln.ac.lk", 12),
        ("Dr. K. Nandasena", "nandasena@kln.ac.lk", 10),
        ("Ms. A. Wickremesinghe", "awickremesinghe@kln.ac.lk", 10),
        ("Prof. P. Udaphi", "udaphi@kln.ac.lk", 12),
        ("Dr. R. Munasinghe", "munasinghe@kln.ac.lk", 10),
        ("Dr. N. De Silva", "ndesilva@kln.ac.lk", 10),
        ("Dr. K. Jayawardena", "kjayawardena@kln.ac.lk", 10),
        ("Ms. S. Mendis", "smendis@kln.ac.lk", 10),
        ("Dr. A. Rathnayake", "arathnayake@kln.ac.lk", 10),
        ("Prof. D. Paranavithana", "paranavithana@kln.ac.lk", 12),
        ("Dr. L. Colombage", "lcolombage@kln.ac.lk", 10),
    ]
    lecturers = [Lecturer(name=name, email=email, max_hours_per_week=hrs) for name, email, hrs in lecturers_data]
    db.add_all(lecturers)
    db.commit()

    lect_map = {i: lecturers[i] for i in range(len(lecturers))}

    # === PATHWAYS ===
    pathways_data = [
        # Physical Science Stream - Year 1
        ("AMAT + PMAT + PHYS", physical.id, 1),
        ("AMAT + PMAT + COSC", physical.id, 1),
        ("AMAT + PMAT + COST", physical.id, 1),
        ("AMAT + PMAT + STAT", physical.id, 1),
        ("AMAT + PMAT + ELEC", physical.id, 1),
        ("PMAT + PHYS + CHEM", physical.id, 1),
        ("PMAT + PHYS + COSC", physical.id, 1),
        ("PMAT + PHYS + ELEC", physical.id, 1),
        ("PMAT + COSC + STAT", physical.id, 1),
        ("PMAT + COST + STAT", physical.id, 1),
        # Biological Science Stream - Year 1
        ("BIOC + MIBI + PLBL + ZOOL", biological.id, 1),
        ("BIOC + MIBI + ZOOL + COST", biological.id, 1),
        ("BIOC + MIBI + PLBL + COST", biological.id, 1),
        ("BIOC + PLBL + ZOOL", biological.id, 1),
        ("PLBL + ZOOL + COST", biological.id, 1),
        ("MIBI + PLBL + ZOOL", biological.id, 1),
        ("BIOC + MIBI + ZOOL", biological.id, 1),
        ("BIOC + MIBI + PLBL", biological.id, 1),
        # Specialized - Year 1
        ("APCH + CHEM + MGMT", physical.id, 1),
        ("COSC + PMAT + PHYS", physical.id, 1),
        # Year 2 pathways
        ("AMAT + PMAT + PHYS", physical.id, 2),
        ("AMAT + PMAT + COSC", physical.id, 2),
        ("AMAT + PMAT + COST", physical.id, 2),
        ("AMAT + PMAT + STAT", physical.id, 2),
        ("AMAT + PMAT + ELEC", physical.id, 2),
        ("PMAT + PHYS + CHEM", physical.id, 2),
        ("PMAT + PHYS + COSC", physical.id, 2),
        ("PMAT + PHYS + ELEC", physical.id, 2),
        ("PMAT + COSC + STAT", physical.id, 2),
        ("PMAT + COST + STAT", physical.id, 2),
        # Biological Science Year 2
        ("BIOC + MIBI + PLBL + ZOOL", biological.id, 2),
        ("BIOC + MIBI + ZOOL + COST", biological.id, 2),
        ("BIOC + MIBI + PLBL + COST", biological.id, 2),
        ("BIOC + PLBL + ZOOL", biological.id, 2),
        ("PLBL + ZOOL + COST", biological.id, 2),
        ("MIBI + PLBL + ZOOL", biological.id, 2),
        ("BIOC + MIBI + ZOOL", biological.id, 2),
        ("BIOC + MIBI + PLBL", biological.id, 2),
        # Specialized Year 2
        ("APCH + CHEM + MGMT", physical.id, 2),
        ("COSC + PMAT + PHYS", physical.id, 2),
        ("PHYS + ELEC + COST + AMAT", physical.id, 2),
        ("PHYS + ELEC + COST + PMAT", physical.id, 2),
        ("ENCM + PLBL + ZOOL + CHEM + MIBI", biological.id, 2),
        ("ELEC + COSC + MACS + PMAT", physical.id, 2),
        # Year 3 pathways (Honours)
        ("PMAT + AMAT + STAT", physical.id, 3),
        ("PHYS + CHEM + AMAT", physical.id, 3),
        ("COSC + STAT + PMAT", physical.id, 3),
        ("BIOC + MIBI + PLBL", biological.id, 3),
        ("BIOC + MIBI + ZOOL", biological.id, 3),
        # Year 4 pathways (Honours)
        ("PMAT Hons", physical.id, 4),
        ("PHYS Hons", physical.id, 4),
        ("CHEM Hons", physical.id, 4),
        ("COSC Hons", physical.id, 4),
        ("BIOC Hons", biological.id, 4),
        ("MIBI Hons", biological.id, 4),
    ]
    pathways = [Pathway(name=name, department_id=dept_id, year=year) for name, dept_id, year in pathways_data]
    db.add_all(pathways)
    db.commit()

    # Assign subjects to pathways using proper code parsing
    for pathway in pathways:
        subject_codes = [code.strip() for code in pathway.name.split(" + ")]
        pathway.subjects = []
        for code in subject_codes:
            if code in subject_map:
                pathway.subjects.append(subject_map[code])
    db.commit()

    # === MODULES ===
    modules_data = [
        # Year 1 Modules (Sem II based on real timetable)
        ("PMAT 12242", "Calculus II", subject_map["PMAT"].id, 1, 2),
        ("PMAT 12253", "Linear Algebra I", subject_map["PMAT"].id, 1, 2),
        ("PMAT 12203", "Foundation Mathematics", subject_map["PMAT"].id, 1, 2),
        ("AMAT 12242", "Applied Mathematics II", subject_map["AMAT"].id, 1, 2),
        ("AMAT 12253", "Mathematical Methods", subject_map["AMAT"].id, 1, 2),
        ("STAT 12643", "Probability & Statistics I", subject_map["STAT"].id, 1, 2),
        ("STAT 12652", "Statistical Methods", subject_map["STAT"].id, 1, 2),
        ("STAT 14522", "Statistics for Life Sciences", subject_map["STAT"].id, 1, 2),
        ("PHYS 12542", "Classical Mechanics", subject_map["PHYS"].id, 1, 2),
        ("PHYS 12552", "Electromagnetism", subject_map["PHYS"].id, 1, 2),
        ("PHYS 12561", "Physics Practical I", subject_map["PHYS"].id, 1, 2),
        ("CHEM 12642", "Organic Chemistry I", subject_map["CHEM"].id, 1, 2),
        ("CHEM 12652", "Inorganic Chemistry I", subject_map["CHEM"].id, 1, 2),
        ("CHEM 12661", "Chemistry Practical I", subject_map["CHEM"].id, 1, 2),
        ("ELEC 12534", "Basic Electronics", subject_map["ELEC"].id, 1, 2),
        ("ELEC 12541", "Electronics Practical", subject_map["ELEC"].id, 1, 2),
        ("COSC 12033", "Introduction to Computing", subject_map["COSC"].id, 1, 2),
        ("COSC 12043", "Programming Fundamentals", subject_map["COSC"].id, 1, 2),
        ("COST 12032", "Introduction to IT", subject_map["COST"].id, 1, 2),
        ("COST 12043", "Business Computing", subject_map["COST"].id, 1, 2),
        ("BIOC 12612", "Biomolecules", subject_map["BIOC"].id, 1, 2),
        ("BIOC 12622", "Cell Biology", subject_map["BIOC"].id, 1, 2),
        ("BIOC 12632", "Biochemistry Practical", subject_map["BIOC"].id, 1, 2),
        ("MIBI 12514", "Microbiology I", subject_map["MIBI"].id, 1, 2),
        ("MIBI 12522", "Microbiology Practical I", subject_map["MIBI"].id, 1, 2),
        ("MIBI 12532", "Applied Microbiology", subject_map["MIBI"].id, 1, 2),
        ("PLBL 12513", "Plant Diversity", subject_map["PLBL"].id, 1, 2),
        ("PLBL 12523", "Plant Physiology", subject_map["PLBL"].id, 1, 2),
        ("PLBL 12543", "Plant Ecology", subject_map["PLBL"].id, 1, 2),
        ("ZOOL 12703", "Animal Diversity", subject_map["ZOOL"].id, 1, 2),
        ("ZOOL 12711", "Zoology Practical I", subject_map["ZOOL"].id, 1, 2),
        ("ZOOL 12722", "Comparative Anatomy", subject_map["ZOOL"].id, 1, 2),
        ("ZOOL 12733", "EM Techniques", subject_map["ZOOL"].id, 1, 2),
        ("ENCM 12732", "Environmental Science", subject_map["ENCM"].id, 1, 2),
        ("ENCM 12742", "Ecology Basics", subject_map["ENCM"].id, 1, 2),
        ("ENCM 12752", "Environmental Chemistry", subject_map["ENCM"].id, 1, 2),
        ("APCH 12622", "General Chemistry II", subject_map["APCH"].id, 1, 2),
        ("APCH 12632", "Industrial Chemistry", subject_map["APCH"].id, 1, 2),
        ("BECS 12233", "Intro to Electronics & CS", subject_map["BECS"].id, 1, 2),
        ("BECS 12243", "Digital Systems", subject_map["BECS"].id, 1, 2),
        ("BECS 12443", "Data Structures", subject_map["BECS"].id, 1, 2),
        ("BECS 12451", "Database Systems", subject_map["BECS"].id, 1, 2),
        ("BECS 12462", "Software Engineering", subject_map["BECS"].id, 1, 2),
        ("BECS 12623", "Web Technologies", subject_map["BECS"].id, 1, 2),
        ("BECS 12712", "Computer Networks", subject_map["BECS"].id, 1, 2),
        ("BECS 12742", "Operating Systems", subject_map["BECS"].id, 1, 2),
        ("MACS 12532", "Financial Accounting", subject_map["MACS"].id, 1, 2),
        ("MGMT 12022", "Principles of Management", subject_map["MGMT"].id, 1, 2),
        ("ACLT 12022", "Academic Literacy", subject_map["CMSK"].id, 1, 2),
        ("CMSK 14012", "Sports I", subject_map["CMSK"].id, 1, 2),
        ("CMSK 14032", "Leadership Skills", subject_map["CMSK"].id, 1, 2),
        ("CMSK 14042", "Entrepreneurship", subject_map["CMSK"].id, 1, 2),
        # Year 2 Modules
        ("PMAT 22282", "Real Analysis", subject_map["PMAT"].id, 2, 2),
        ("PMAT 22293", "Abstract Algebra", subject_map["PMAT"].id, 2, 2),
        ("AMAT 22282", "Differential Equations", subject_map["AMAT"].id, 2, 2),
        ("AMAT 22292", "Numerical Methods", subject_map["AMAT"].id, 2, 2),
        ("STAT 22632", "Probability & Statistics II", subject_map["STAT"].id, 2, 2),
        ("STAT 22642", "Regression Analysis", subject_map["STAT"].id, 2, 2),
        ("STAT 22651", "Statistical Computing", subject_map["STAT"].id, 2, 2),
        ("PHYS 22533", "Quantum Mechanics", subject_map["PHYS"].id, 2, 2),
        ("PHYS 22541", "Physics Practical II", subject_map["PHYS"].id, 2, 2),
        ("PHYS 22553", "Thermodynamics", subject_map["PHYS"].id, 2, 2),
        ("CHEM 22702", "Organic Chemistry II", subject_map["CHEM"].id, 2, 2),
        ("CHEM 22712", "Physical Chemistry I", subject_map["CHEM"].id, 2, 2),
        ("CHEM 22721", "Chemistry Practical II", subject_map["CHEM"].id, 2, 2),
        ("ELEC 22534", "Circuit Theory", subject_map["ELEC"].id, 2, 2),
        ("ELEC 22541", "Electronics Practical II", subject_map["ELEC"].id, 2, 2),
        ("COSC 22073", "Algorithms & Data Structures", subject_map["COSC"].id, 2, 2),
        ("COSC 22083", "Software Development", subject_map["COSC"].id, 2, 2),
        ("COST 22073", "Information Systems", subject_map["COST"].id, 2, 2),
        ("COST 22082", "System Analysis", subject_map["COST"].id, 2, 2),
        ("BIOC 22642", "Metabolism", subject_map["BIOC"].id, 2, 2),
        ("BIOC 22652", "Molecular Biology", subject_map["BIOC"].id, 2, 2),
        ("BIOC 22661", "Biochemistry Practical II", subject_map["BIOC"].id, 2, 2),
        ("MIBI 22534", "Microbial Physiology", subject_map["MIBI"].id, 2, 2),
        ("MIBI 22542", "Microbiology Practical II", subject_map["MIBI"].id, 2, 2),
        ("MIBI 22554", "Environmental Microbiology", subject_map["MIBI"].id, 2, 2),
        ("MIBI 22562", "Industrial Microbiology", subject_map["MIBI"].id, 2, 2),
        ("PLBL 22541", "Plant Biotechnology", subject_map["PLBL"].id, 2, 2),
        ("PLBL 22554", "Plant Molecular Biology", subject_map["PLBL"].id, 2, 2),
        ("PLBL 22561", "Plant Biology Practical II", subject_map["PLBL"].id, 2, 2),
        ("ZOOL 22732", "Animal Physiology", subject_map["ZOOL"].id, 2, 2),
        ("ZOOL 22742", "Developmental Biology", subject_map["ZOOL"].id, 2, 2),
        ("ZOOL 22752", "Zoology Practical II", subject_map["ZOOL"].id, 2, 2),
        ("ENCM 22762", "Conservation Biology", subject_map["ENCM"].id, 2, 2),
        ("ENCM 22773", "Environmental Impact Assessment", subject_map["ENCM"].id, 2, 2),
        ("ENCM 22782", "Waste Management", subject_map["ENCM"].id, 2, 2),
        ("ENCM 22791", "Environmental Monitoring", subject_map["ENCM"].id, 2, 2),
        ("ENCM 22802", "GIS for Environment", subject_map["ENCM"].id, 2, 2),
        ("APCH 22692", "Analytical Chemistry", subject_map["APCH"].id, 2, 2),
        ("APCH 22712", "Industrial Processes", subject_map["APCH"].id, 2, 2),
        ("APCH 22721", "Applied Chemistry Practical", subject_map["APCH"].id, 2, 2),
        ("APCH 22732", "Quality Control", subject_map["APCH"].id, 2, 2),
        ("BECS 22233", "Microcontroller Programming", subject_map["BECS"].id, 2, 2),
        ("BECS 22243", "Embedded Systems", subject_map["BECS"].id, 2, 2),
        ("BECS 22443", "Object Oriented Programming", subject_map["BECS"].id, 2, 2),
        ("BECS 22451", "Database Management", subject_map["BECS"].id, 2, 2),
        ("BECS 22623", "Mobile App Development", subject_map["BECS"].id, 2, 2),
        ("BECS 22711", "Computer Architecture", subject_map["BECS"].id, 2, 2),
        ("BECS 22712", "Network Security", subject_map["BECS"].id, 2, 2),
        ("BECS 22732", "Cloud Computing", subject_map["BECS"].id, 2, 2),
        ("BECS 22811", "Project Management", subject_map["BECS"].id, 2, 2),
        ("MACS 22563", "Cost Accounting", subject_map["MACS"].id, 2, 2),
        ("MAPS 22603", "Business Statistics", subject_map["MAPS"].id, 2, 2),
        ("MGMT 22022", "Organizational Behavior", subject_map["MGMT"].id, 2, 2),
    ]

    modules = [Module(code=code, name=name, subject_id=subj_id, year=yr, semester=sem)
              for code, name, subj_id, yr, sem in modules_data]
    db.add_all(modules)
    db.commit()

    module_map = {m.code: m for m in modules}

    # === SESSIONS ===
    # Session format: (module_code, session_type, duration_hours, frequency_per_week, lab_type, student_count, max_students_per_group, concurrent_split, [lecturer_indices])

    # Lecturer assignment strategy: Each subject has 2-3 dedicated lecturers, 1 lecturer per session
    # Year 1 Sessions
    sessions_data = [
        # PMAT (lecturers 0-1)
        (module_map["PMAT 12242"], "lecture", 1, 2, None, 180, None, False, [0]),
        (module_map["PMAT 12253"], "lecture", 1, 2, None, 160, None, False, [1]),
        (module_map["PMAT 12203"], "lecture", 1, 1, None, 200, None, False, [0]),
        # AMAT (lecturers 1-2)
        (module_map["AMAT 12242"], "lecture", 1, 2, None, 140, None, False, [1]),
        (module_map["AMAT 12253"], "lecture", 1, 2, None, 120, None, False, [2]),
        # STAT (lecturers 2-3)
        (module_map["STAT 12643"], "lecture", 1, 2, None, 100, None, False, [2]),
        (module_map["STAT 12652"], "lecture", 1, 2, None, 80, None, False, [3]),
        (module_map["STAT 14522"], "lecture", 1, 2, None, 150, None, False, [2]),
        # PHYS (lecturers 3-4)
        (module_map["PHYS 12542"], "lecture", 1, 2, None, 180, None, False, [3]),
        (module_map["PHYS 12552"], "lecture", 1, 1, None, 180, None, False, [4]),
        (module_map["PHYS 12561"], "practical", 3, 1, "physics_lab", 180, 45, True, [4]),
        # CHEM (lecturers 4-6)
        (module_map["CHEM 12642"], "lecture", 1, 1, None, 160, None, False, [4]),
        (module_map["CHEM 12652"], "lecture", 1, 2, None, 160, None, False, [5]),
        (module_map["CHEM 12661"], "practical", 3, 1, "chemistry_lab", 160, 40, True, [6]),
        # ELEC (lecturers 6-7)
        (module_map["ELEC 12534"], "lecture", 1, 1, None, 120, None, False, [6]),
        (module_map["ELEC 12541"], "practical", 3, 1, "computer_lab", 60, 30, True, [7]),
        # COSC (lecturers 7-8)
        (module_map["COSC 12033"], "lecture", 1, 1, None, 200, None, False, [7]),
        (module_map["COSC 12043"], "practical", 3, 1, "computer_lab", 200, 50, True, [7]),
        # COST (lecturers 8-9)
        (module_map["COST 12032"], "lecture", 1, 1, None, 150, None, False, [9]),
        (module_map["COST 12043"], "lecture", 1, 1, None, 150, None, False, [9]),
        (module_map["COST 12043"], "practical", 3, 1, "computer_lab", 150, 40, True, [8]),
        # BIOC (lecturers 10-11)
        (module_map["BIOC 12612"], "lecture", 1, 1, None, 140, None, False, [10]),
        (module_map["BIOC 12622"], "lecture", 1, 1, None, 140, None, False, [12]),
        (module_map["BIOC 12632"], "practical", 3, 1, "chemistry_lab", 140, 35, True, [10]),
        # MIBI (lecturers 11-12)
        (module_map["MIBI 12514"], "lecture", 1, 1, None, 120, None, False, [11]),
        (module_map["MIBI 12522"], "practical", 3, 1, "em_lab", 60, 30, True, [11]),
        # PLBL (lecturers 12-13)
        (module_map["PLBL 12513"], "lecture", 1, 1, None, 100, None, False, [12]),
        (module_map["PLBL 12523"], "lecture", 1, 1, None, 100, None, False, [13]),
        (module_map["PLBL 12523"], "practical", 3, 1, "plant_bio_lab", 100, 50, True, [13]),
        (module_map["PLBL 12543"], "lecture", 1, 1, None, 80, None, False, [13]),
        # ZOOL (lecturers 13-14)
        (module_map["ZOOL 12703"], "lecture", 1, 1, None, 140, None, False, [13]),
        (module_map["ZOOL 12711"], "practical", 3, 1, "zoology_lab", 140, 35, True, [14]),
        (module_map["ZOOL 12722"], "lecture", 1, 1, None, 100, None, False, [14]),
        (module_map["ZOOL 12733"], "practical", 3, 1, "em_lab", 70, 35, True, [13]),
        # ENCM (lecturers 15-16)
        (module_map["ENCM 12732"], "lecture", 1, 2, None, 60, None, False, [15]),
        (module_map["ENCM 12742"], "lecture", 1, 2, None, 60, None, False, [16]),
        (module_map["ENCM 12752"], "lecture", 1, 2, None, 50, None, False, [16]),
        # APCH (lecturers 17-18)
        (module_map["APCH 12622"], "lecture", 1, 2, None, 80, None, False, [17]),
        (module_map["APCH 12632"], "lecture", 1, 2, None, 80, None, False, [18]),
        # BECS Year 1 (lecturers 18-20, 25-26)
        (module_map["BECS 12233"], "lecture", 1, 1, None, 100, None, False, [18]),
        (module_map["BECS 12243"], "lecture", 1, 1, None, 100, None, False, [19]),
        (module_map["BECS 12443"], "lecture", 1, 1, None, 90, None, False, [19]),
        (module_map["BECS 12443"], "practical", 3, 1, "computer_lab", 90, 45, True, [20]),
        (module_map["BECS 12451"], "lecture", 1, 1, None, 90, None, False, [20]),
        (module_map["BECS 12451"], "practical", 3, 1, "computer_lab", 90, 45, True, [20]),
        (module_map["BECS 12462"], "lecture", 1, 1, None, 80, None, False, [25]),
        (module_map["BECS 12623"], "lecture", 1, 1, None, 80, None, False, [26]),
        (module_map["BECS 12712"], "lecture", 1, 1, None, 70, None, False, [26]),
        (module_map["BECS 12742"], "lecture", 1, 1, None, 70, None, False, [26]),
        # MACS/MAPS (lecturer 26)
        (module_map["MACS 12532"], "lecture", 1, 2, None, 120, None, False, [26]),
        # MGMT (lecturer 29)
        (module_map["MGMT 12022"], "lecture", 1, 2, None, 180, None, False, [29]),
        # CMSK (lecturers 30-32, 33)
        (module_map["ACLT 12022"], "lecture", 1, 1, None, 300, 150, True, [33]),
        (module_map["CMSK 14012"], "practical", 2, 1, "gymnasium", 300, 150, True, [33]),
        (module_map["CMSK 14032"], "lecture", 2, 1, None, 300, 150, True, [30]),
        (module_map["CMSK 14042"], "lecture", 1, 1, None, 250, None, False, [31]),
    ]

    # Year 2 Sessions
    sessions_data.extend([
        # PMAT (lecturers 0-1)
        (module_map["PMAT 22282"], "lecture", 1, 2, None, 140, None, False, [0]),
        (module_map["PMAT 22293"], "lecture", 1, 2, None, 120, None, False, [1]),
        # AMAT (lecturers 1-2)
        (module_map["AMAT 22282"], "lecture", 1, 2, None, 100, None, False, [1]),
        (module_map["AMAT 22292"], "lecture", 1, 2, None, 80, None, False, [2]),
        # STAT (lecturers 2-3, 5-6)
        (module_map["STAT 22632"], "lecture", 1, 2, None, 80, None, False, [2]),
        (module_map["STAT 22642"], "lecture", 1, 2, None, 70, None, False, [3]),
        (module_map["STAT 22651"], "practical", 2, 1, "computer_lab", 60, 30, True, [5]),
        # PHYS (lecturers 3-4)
        (module_map["PHYS 22533"], "lecture", 1, 2, None, 150, None, False, [3]),
        (module_map["PHYS 22541"], "practical", 3, 1, "physics_lab", 150, 50, True, [4]),
        (module_map["PHYS 22553"], "lecture", 1, 2, None, 140, None, False, [4]),
        # CHEM (lecturers 5-6)
        (module_map["CHEM 22702"], "lecture", 1, 2, None, 140, None, False, [6]),
        (module_map["CHEM 22712"], "lecture", 1, 2, None, 130, None, False, [5]),
        (module_map["CHEM 22721"], "practical", 3, 1, "chemistry_lab", 140, 35, True, [6]),
        # ELEC (lecturers 6-7)
        (module_map["ELEC 22534"], "lecture", 1, 2, None, 100, None, False, [6]),
        (module_map["ELEC 22541"], "practical", 3, 1, "computer_lab", 50, 25, True, [7]),
        # COSC (lecturers 7-8)
        (module_map["COSC 22073"], "lecture", 1, 1, None, 120, None, False, [8]),
        (module_map["COSC 22073"], "practical", 2, 1, "computer_lab", 120, 60, True, [8]),
        (module_map["COSC 22083"], "lecture", 1, 1, None, 100, None, False, [8]),
        (module_map["COSC 22083"], "practical", 3, 1, "computer_lab", 100, 50, True, [8]),
        # COST (lecturers 8-9, 33)
        (module_map["COST 22073"], "lecture", 1, 1, None, 90, None, False, [9]),
        (module_map["COST 22073"], "practical", 3, 1, "computer_lab", 90, 45, True, [9]),
        (module_map["COST 22082"], "lecture", 1, 1, None, 80, None, False, [9]),
        # BIOC (lecturers 10-11)
        (module_map["BIOC 22642"], "lecture", 1, 2, None, 100, None, False, [10]),
        (module_map["BIOC 22652"], "lecture", 1, 2, None, 100, None, False, [11]),
        (module_map["BIOC 22661"], "practical", 2, 1, "chemistry_lab", 100, 50, True, [10]),
        # MIBI (lecturers 11-12)
        (module_map["MIBI 22534"], "lecture", 1, 1, None, 80, None, False, [11]),
        (module_map["MIBI 22542"], "practical", 3, 1, "em_lab", 80, 40, True, [11]),
        (module_map["MIBI 22554"], "lecture", 1, 1, None, 60, None, False, [12]),
        (module_map["MIBI 22562"], "practical", 3, 1, "em_lab", 60, 30, True, [12]),
        (module_map["MIBI 22554"], "lecture", 1, 1, None, 60, None, False, [12]),
        (module_map["MIBI 22562"], "practical", 3, 1, "em_lab", 60, 30, True, [13]),
        # PLBL (lecturers 12-13)
        (module_map["PLBL 22541"], "lecture", 1, 1, None, 70, None, False, [12]),
        (module_map["PLBL 22541"], "practical", 3, 1, "computer_lab", 70, 35, True, [13]),
        (module_map["PLBL 22554"], "lecture", 1, 1, None, 60, None, False, [13]),
        (module_map["PLBL 22561"], "practical", 3, 1, "plant_bio_lab", 70, 35, True, [13]),
        # ZOOL (lecturers 13-14)
        (module_map["ZOOL 22732"], "lecture", 1, 1, None, 100, None, False, [13]),
        (module_map["ZOOL 22742"], "lecture", 1, 1, None, 80, None, False, [14]),
        (module_map["ZOOL 22752"], "practical", 3, 1, "zoology_lab", 100, 50, True, [14]),
        # ENCM (lecturers 15-16)
        (module_map["ENCM 22762"], "lecture", 1, 1, None, 50, None, False, [15]),
        (module_map["ENCM 22773"], "lecture", 1, 1, None, 45, None, False, [16]),
        (module_map["ENCM 22782"], "lecture", 1, 1, None, 40, None, False, [16]),
        (module_map["ENCM 22791"], "lecture", 1, 1, None, 40, None, False, [16]),
        (module_map["ENCM 22802"], "practical", 3, 1, "computer_lab", 40, 20, True, [16]),
        # APCH (lecturers 17-18)
        (module_map["APCH 22692"], "lecture", 1, 1, None, 70, None, False, [17]),
        (module_map["APCH 22712"], "lecture", 1, 1, None, 70, None, False, [18]),
        (module_map["APCH 22721"], "practical", 3, 1, "chemistry_lab", 70, 35, True, [17]),
        (module_map["APCH 22732"], "lecture", 1, 1, None, 60, None, False, [18]),
        # BECS Year 2 (lecturers 18-20, 30-32, 25-26)
        (module_map["BECS 22233"], "lecture", 1, 1, None, 80, None, False, [18]),
        (module_map["BECS 22233"], "practical", 2, 1, "computer_lab", 80, 40, True, [30]),
        (module_map["BECS 22243"], "lecture", 1, 1, None, 70, None, False, [19]),
        (module_map["BECS 22443"], "lecture", 1, 1, None, 80, None, False, [19]),
        (module_map["BECS 22443"], "practical", 2, 1, "computer_lab", 80, 40, True, [31]),
        (module_map["BECS 22451"], "lecture", 1, 1, None, 70, None, False, [20]),
        (module_map["BECS 22451"], "practical", 3, 1, "computer_lab", 70, 35, True, [32]),
        (module_map["BECS 22623"], "lecture", 1, 1, None, 60, None, False, [26]),
        (module_map["BECS 22623"], "practical", 3, 1, "computer_lab", 60, 30, True, [26]),
        (module_map["BECS 22711"], "lecture", 1, 1, None, 60, None, False, [26]),
        (module_map["BECS 22712"], "lecture", 1, 1, None, 55, None, False, [26]),
        (module_map["BECS 22732"], "lecture", 1, 1, None, 50, None, False, [26]),
        (module_map["BECS 22811"], "lecture", 1, 1, None, 50, None, False, [20]),
        # MACS/MAPS (lecturers 20, 26)
        (module_map["MACS 22563"], "lecture", 1, 1, None, 80, None, False, [26]),
        (module_map["MAPS 22603"], "lecture", 1, 1, None, 70, None, False, [20]),
        # MGMT (lecturer 29)
        (module_map["MGMT 22022"], "lecture", 1, 1, None, 150, None, False, [29]),
    ])

    # Create sessions
    for module_obj, sess_type, dur, freq, lab_type, stu_count, max_grp, concurrent, lect_indices in sessions_data:
        session = SessionModel(
            module_id=module_obj.id,
            session_type=sess_type,
            duration_hours=dur,
            frequency_per_week=freq,
            requires_lab_type=lab_type,
            student_count=stu_count,
            max_students_per_group=max_grp,
            concurrent_split=concurrent,
            lecturers=[lect_map[i] for i in lect_indices]
        )
        db.add(session)

    db.commit()
    print(f"Seeded {len(sessions_data)} sessions")

    # === WORKLOAD VERIFICATION ===
    print("\n=== LECTURER WORKLOAD VERIFICATION ===")
    from math import ceil
    sessions = db.query(SessionModel).all()
    
    workload = {}
    for session in sessions:
        module = session.module
        hours_per_occurrence = session.duration_hours * session.frequency_per_week
        
        if session.concurrent_split and session.max_students_per_group:
            num_groups = ceil(session.student_count / session.max_students_per_group)
            lecturer_hours = hours_per_occurrence
        else:
            num_groups = 1
            lecturer_hours = hours_per_occurrence
        
        for lecturer in session.lecturers:
            lecturer_id = lecturer.id
            if lecturer_id not in workload:
                workload[lecturer_id] = {"name": lecturer.name, "max_hours": lecturer.max_hours_per_week, "total": 0, "sessions": []}
            workload[lecturer_id]["total"] += lecturer_hours
            workload[lecturer_id]["sessions"].append(f"{module.code} ({session.session_type}, {lecturer_hours}h)")
    
    print(f"\n{'ID':<3} {'Name':<25} {'Hours':<6} {'Max':<6} {'Status':<10} {'Sessions'}")
    print("-" * 100)
    over_limit_count = 0
    for lecturer in lecturers:
        if lecturer.id in workload:
            data = workload[lecturer.id]
            hours = data["total"]
            max_h = data["max_hours"]
            status = "OVER" if hours > max_h else "OK"
            if hours > max_h:
                over_limit_count += 1
            print(f"{lecturer.id:<3} {lecturer.name:<25} {hours:<6.1f} {max_h:<6} {status:<10} {', '.join(data['sessions'][:5])}")
        else:
            print(f"{lecturer.id:<3} {lecturer.name:<25} 0.0     {lecturer.max_hours_per_week:<6} OK         (no sessions)")
    
    print(f"\nTotal lecturers over limit: {over_limit_count}/{len(lecturers)}")


if __name__ == "__main__":
    db = SessionLocal()
    try:
        reset_tables(db)
        seed_demo(db)
        print("\nRealistic UOK timetable data seeded successfully!")
    finally:
        db.close()
