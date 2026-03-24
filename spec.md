# Target Architecture

## Purpose

This document defines the target model and flow for the refactor.
It is intentionally short and should be treated as the implementation contract that sits next to `prompts.md`.

## Core model

The system has to separate 3 layers clearly.

### 1. Imported enrollment facts

These come from the enrollment csv and are the primary source of truth for attendance-related data.

Current known csv columns:

- `CoursePathNo`
- `CourseCode`
- `Year`
- `AcYear`
- `Attempt`
- `stream`
- `batch`
- `student_hash`

The atomic identity unit is the student.
Any final clash logic must be explainable in terms of actual student membership.

Raw import facts must be stored without losing ambiguity.
That means the system should preserve:

- the original imported `CoursePathNo`
- imported `stream`
- imported `Year`
- imported `AcYear`
- imported `batch`
- imported `Attempt`
- imported `CourseCode`
- the source student identity hash
- any anomaly or review decisions applied during import

### 2. Canonical normalized timetable model

This is the durable internal model used by the solver and views.

It must preserve:

- students
- imported enrollment facts
- degree / year / path metadata
- derived attendance groups used for efficient solving
- modules
- shared teaching sessions
- session-to-module mappings
- lecturers
- rooms
- session requirements and delivery rules

Important rule:

- degree / year / path is metadata and a planning layer
- the canonical clash truth is student membership

## Canonical entities

The target schema should stop collapsing everything into one flat manual dataset.
It should introduce separate entity groups.

### A. Raw import entities

These are append-only or snapshot-style records that describe what was imported.

- `import_run`
  - source file
  - imported at
  - selected academic year
  - allowed attempts
  - import rules applied
- `import_row`
  - import run id
  - raw csv fields
  - normalized course code metadata
  - anomaly flags
  - review status
- `import_student`
  - stable internal id
  - `student_hash`
- `import_enrollment`
  - student
  - import row
  - raw stream / year / batch / path values
  - module/course identity from the csv row

### B. Interpreted academic structure entities

These capture our best academic interpretation of the raw facts without pretending the raw csv is already perfect.

- `programme`
  - code such as `PS`, `BS`, `AC`, `EC`, `EM`, `PE`, `SE`, `SS`, `IM`
  - display name
  - duration
  - programme family
- `programme_path`
  - optional interpreted path definition for a programme and study year
  - may map one or more raw `CoursePathNo` values to one academic path concept
  - may also explicitly represent `common` / `unstreamed`
- `student_programme_context`
  - student
  - academic year
  - current study year
  - batch
  - interpreted programme
  - inferred primary path if one can be established
  - confidence / ambiguity flags
- `curriculum_module`
  - academic module identity
  - module code
  - subject code
  - nominal year
  - semester bucket
  - full-year flag
- `student_module_membership`
  - student
  - curriculum module
  - membership source
  - whether it is common/core/path-specific/optional if inferable

### C. Solver-facing entities

These are derived from the canonical facts and interpreted structure.

- `attendance_group`
  - a solver-efficient group of students who attend the same teaching event set
  - must always be traceable back to exact students
- `shared_session`
  - the real teaching event
  - session type
  - duration
  - occurrence count
  - room requirements
  - delivery notes
- `shared_session_module_link`
  - maps one real shared session to one or more curriculum modules
- `shared_session_attendance_group`
  - maps shared sessions to the attendance groups that actually attend
- `lecturer`
  - canonical lecturer identity
- `room`
  - canonical room identity and capabilities
- `session_requirement`
  - lab rules
  - room type rules
  - fixed room rules
  - splitting / parallel-room rules

## Immediate schema implication

The current `v2_degree` / `v2_path` / `v2_student_group` model is too compressed to serve as the final canonical model.

Specifically:

- raw imported facts and interpreted academic structure are currently mixed together
- `student_group` currently tries to act as both academic grouping and clash truth
- the final model needs a separate student-level foundation and a derived solver-group layer

### 3. Solver-facing model

The solver does not need to work directly on every raw enrollment row, but every solver attendance unit must be derivable from canonical student membership.

That means:

- clashes must be correct at student level
- shared sessions can map to more than one module
- the same real session may serve multiple curriculum identities

## Setup flow

The intended setup flow is:

1. analyze enrollment csv
2. review ambiguous buckets and import rules
3. materialize raw import facts and interpreted academic structure from the csv
4. complete missing solver metadata through the manual wizard
5. validate setup completeness
6. generate timetables

The manual wizard is not the primary attendance-authoring tool.
Its main job is to capture data the csv does not reliably provide, such as:

- rooms and room capabilities
- lecturer assignments and capabilities
- shared-session definitions where needed
- session requirements
- controlled corrections or exceptions

The manual wizard may also confirm or override inferred academic structure when the import cannot decide safely, but it should not rewrite the raw imported facts.

## Generation contract

Generation should be bounded exhaustive when feasible.

That means:

- try to enumerate all valid timetables when practical
- if the search space is too large, stop with explicit reporting
- keep hard constraints mandatory
- keep soft constraints selectable and reportable

The selected timetable becomes the default timetable for views and exports.

The generation input should come from a normalized snapshot that includes:

- the selected import run or imported snapshot
- interpreted programme/path context
- derived attendance groups
- manual solver metadata
- explicit hard and soft constraint definitions

## Verification contract

After a timetable is generated and selected, it must be verified by 3 separate external modules.

Language set:

- Elixir
- Python
- Rust

Rules:

- they must not share core verification logic
- they must consume the same normalized dataset snapshot and selected timetable
- they must independently report hard-constraint validity
- they must independently report which soft constraints are satisfied

The timetable is trusted only when all 3 verifiers agree on hard-constraint compliance.

Each verifier should consume the same exported verification snapshot.
That snapshot should contain:

- timetable entries
- shared sessions
- linked modules
- attendance groups
- exact student membership per attendance group
- lecturer assignments
- room assignments and room capabilities
- the hard-constraint set
- the soft-constraint set

## Hard-constraint expectation

At minimum, the verifier inputs and outputs must support checking:

- room capacity compatibility
- room capability compatibility
- lab-specific restrictions
- no room overlap
- no lecturer overlap
- no student overlap
- working hours
- lunch break exclusion
- weekly timetable window

## Immediate implementation consequence

Any code path that treats manual setup and csv import as equivalent full-authoring peers should be considered transitional and refactorable.
The target system is csv-first with manual completion.

The next backend refactor should therefore happen in this order:

1. add raw import persistence
2. add interpreted academic-structure persistence
3. derive solver-facing attendance groups from student membership
4. move manual setup to missing metadata and exception handling
5. refit generation and views on top of the normalized model
