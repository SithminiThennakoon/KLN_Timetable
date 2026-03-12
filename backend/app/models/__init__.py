from app.models.academic import (
    CurriculumModule,
    Programme,
    ProgrammePath,
    StudentModuleMembership,
    StudentProgrammeContext,
)
from app.models.imports import (
    ImportEnrollment,
    ImportReviewRule,
    ImportRow,
    ImportRun,
    ImportStudent,
)
from app.models.solver import AttendanceGroup, AttendanceGroupStudent
from app.models.snapshot import (
    SnapshotLecturer,
    SnapshotRoom,
    SnapshotSharedSession,
)
from app.models.v2 import (
    V2Degree,
    V2GenerationRun,
    V2Lecturer,
    V2Module,
    V2Path,
    V2Room,
    V2Session,
    V2SolutionEntry,
    V2StudentGroup,
    V2TimetableSolution,
)

__all__ = [
    "AttendanceGroup",
    "AttendanceGroupStudent",
    "CurriculumModule",
    "ImportEnrollment",
    "ImportReviewRule",
    "ImportRow",
    "ImportRun",
    "ImportStudent",
    "Programme",
    "ProgrammePath",
    "SnapshotLecturer",
    "SnapshotRoom",
    "SnapshotSharedSession",
    "StudentModuleMembership",
    "StudentProgrammeContext",
    "V2Degree",
    "V2GenerationRun",
    "V2Lecturer",
    "V2Module",
    "V2Path",
    "V2Room",
    "V2Session",
    "V2SolutionEntry",
    "V2StudentGroup",
    "V2TimetableSolution",
]
