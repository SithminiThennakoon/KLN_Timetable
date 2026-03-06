from .associations import pathway_subject_table, session_lecturer_table
from .department import Department
from .subject import Subject
from .pathway import Pathway
from .module import Module
from .session import Session
from .lecturer import Lecturer
from .room import Room
from .timeslot import Timeslot
from .timetable_entry import TimetableEntry
from .v2 import (
    V2Degree,
    V2Path,
    V2Lecturer,
    V2Room,
    V2StudentGroup,
    V2Module,
    V2Session,
    V2GenerationRun,
    V2TimetableSolution,
    V2SolutionEntry,
    v2_session_lecturer_table,
    v2_session_student_group_table,
)
