# Setup Redesign Plan

## Goal

- make setup/import flow clear, reliable, and compatible with solver needs
- make CSV import the main path
- make manual entry a fallback for missing or unclear data
- keep solver input stable

## Step 0: Baseline Current State

- document the current setup/import/generation flow before replacing it
- identify which parts of the current codebase can be reused, which parts are transitional, and which parts should be replaced
- use this baseline to control scope and avoid rewriting stable solver-facing behavior unnecessarily

### Current State Baseline From Code

- the current system has two setup paths:
  - a legacy V2 dataset path based on `/v2/dataset`
  - a newer import workspace / snapshot path based on `/v2/imports/...`
- the frontend service layer currently exposes both paths in `frontend/src/services/timetableStudioService.js`
- the legacy V2 path writes directly into `V2Degree`, `V2Path`, `V2Lecturer`, `V2Room`, `V2StudentGroup`, `V2Module`, and `V2Session` through `replace_dataset()` in `backend/app/services/timetable_v2.py`
- `replace_dataset()` is destructive replacement, not incremental merge:
  - it deletes existing V2 solutions, generation runs, sessions, modules, groups, lecturers, rooms, paths, and degrees before recreating the dataset
- the newer import path already has separate concepts for:
  - import runs
  - programme and programme-path interpretation
  - curriculum modules
  - student module membership
  - attendance groups
  - snapshot lecturers, rooms, and shared sessions
- the current import workspace is built by `build_import_workspace()` in `backend/app/services/snapshot_completion.py`
- the current system still contains a bridge back into the legacy V2 model:
  - `build_legacy_dataset_from_import_run()` converts import-run data back into the legacy flat dataset shape
  - `/v2/imports/{import_run_id}/publish-legacy` then pushes that derived dataset through `replace_dataset()`
- generation currently has two execution paths:
  - `generate_timetables()` for the legacy V2 dataset
  - `generate_snapshot_timetables()` for import-run snapshot data
- both generation paths converge on the same solver-facing `SessionTask` shape inside `backend/app/services/timetable_v2.py`
- the solver-facing contract is more stable than the current setup/import architecture
- the most transitional parts of the current codebase are:
  - publishing import workspaces back into the legacy V2 dataset
  - destructive full-dataset replacement for setup updates
  - coexistence of parallel setup flows in the frontend
- the most reusable parts of the current codebase are:
  - solver task construction semantics
  - generation logic and verification flow
  - import-run analysis and interpreted academic structures already present in the newer import path

## Core Flow

`Import -> Validate -> Validated Source Data -> Infer -> User Review -> Accepted Setup Data -> Fill Missing Items -> Solver Input`

## Step 1: Lock The Flow

- agree on the end-to-end flow in plain language before implementation
- keep imported facts, reviewed data, and solver input as separate states

## Step 2: Define Backend Data States

### `Validated Source Data`

- trusted imported facts that passed validation
- no uncertain guesses saved here until user approves them

Primary entities in the current codebase that already fit this state well:

- `import_run`
  - one import attempt / working import snapshot
  - stores source file, status, selected academic year, allowed attempts, and notes
- `import_row`
  - one validated imported row with raw source fields preserved
  - stores parsed module hints, anomaly flags, matched review rules, and review status
- `import_student`
  - stable student identity based on `student_hash`
- `import_enrollment`
  - accepted enrollment fact derived from a validated row
  - keeps academic year, attempt, stream, study year, batch, course code, and path-like values
- supporting review entities:
  - `import_review_rule`

Rules for this state:

- preserve accepted imported facts and validation outcomes
- keep source semantics intact
- do not silently write uncertain inferred academic interpretations here
- this state is the source for later interpretation, not the final setup state

### `Accepted Setup Data`

- reviewed inferred data plus accepted imported data
- complete enough to prepare solver input

Primary entities in the current codebase that already fit this state or are close to it:

- interpreted academic structure:
  - `programme`
  - `programme_path`
  - `student_programme_context`
  - `curriculum_module`
  - `student_module_membership`
- solver-facing accepted setup entities:
  - `attendance_group`
  - `attendance_group_student`
  - `snapshot_lecturer`
  - `snapshot_room`
  - `snapshot_shared_session`
  - join tables linking shared sessions to lecturers, modules, and attendance groups

Rules for this state:

- inferred values only enter this state after user review when they are not fully certain
- manual completion also writes into this state
- this is the main working setup state for generation readiness
- this state should support targeted re-import, review, manual completion, and readiness checks without forcing conversion into the legacy V2 dataset

### `Solver Input`

- stable contract used by the solver
- should change only if solver requirements truly change

Current concrete solver-facing shape in code:

- `SessionTask` in `backend/app/services/timetable_v2.py`
  - session identity and type
  - module identity
  - occurrence and split indexes
  - duration and room constraints
  - lecturer assignments
  - attendance-group linkage
  - exact student membership keys
  - study-year information
  - student counts and bundle/parallel-room semantics

Rules for this state:

- build this state from accepted setup data, not directly from raw imports
- keep solver semantics stable even if upstream setup flow changes
- treat this as a generated execution contract, not as an editable authoring state

### Transitional And Legacy Model Note

- the current legacy V2 dataset tables (`v2_degree`, `v2_path`, `v2_student_group`, `v2_module`, `v2_session`, `v2_room`, `v2_lecturer`) are still used in production code today
- however, they should be treated as a transitional compatibility layer rather than the target long-term accepted setup state
- the redesign should move toward using the import/academic/snapshot entities as the main accepted setup path, while avoiding unnecessary solver changes

## Step 3: Define CSV Strategy

- keep `students_processed_TT_J.csv` for enrollment/attendance truth
- design a few simple support CSVs for missing solver data
- likely CSVs:
  - `rooms.csv`
  - `lecturers.csv`
  - `sessions.csv`
  - `session_lecturers.csv`
- consider `modules.csv` only if enrollment-derived module metadata is not sufficient in practice
- keep schemas simple enough for admin export
- every importable entity should have a stable matching key for safe re-import and upsert behavior
- matching keys do not have to be university database primary keys, but they must be stable enough to avoid duplicate entities
- standardize file expectations where possible, for example UTF-8 CSVs with fixed headers
- decide early whether `modules.csv` is needed so CSV scope does not shift halfway through implementation
- handle common spreadsheet export quirks such as UTF-8 BOM in headers

## Step 4: Define Validation Rules

- validate imported CSVs before accepting them into `Validated Source Data`
- separate:
  - data validity/domain realism
  - solver completeness/compatibility
- reject or flag impossible/inconsistent cases
- validate cross-file consistency, for example:
  - modules referenced in `sessions.csv` must exist in imported enrollment-derived or accepted module data
  - rooms referenced in sessions must exist in `rooms.csv` or accepted setup data
  - lecturers referenced in `session_lecturers.csv` must exist in `lecturers.csv` or accepted setup data

## Step 4B: Lock CSV Contracts And Validation Outcomes

### Common Rules For All CSVs

- CSVs must use the template headers exactly, allowing normalization for UTF-8 BOM and surrounding whitespace
- blank rows should be ignored
- duplicate header names should reject the file
- required columns missing from the file should reject the file
- extra unknown columns may be accepted at first, but should be reported as warnings so the user knows they are ignored
- row-level validation should produce one of three outcomes:
  - `accept`
  - `needs review`
  - `reject`
- file-level validation should separate:
  - blocking errors that prevent import acceptance
  - warnings that allow import acceptance but must be shown to the user

### `student_enrollments.csv` / `students_processed_TT_J.csv`

Required columns:

- `CourseCode`
- `Year`
- `AcYear`
- `Attempt`
- `stream`
- `batch`
- `student_hash`

Optional columns:

- `CoursePathNo`

Accept rules:

- required fields present
- `Year` is numeric
- `AcYear` matches academic-year format such as `2022/2023`
- `CourseCode` matches known parseable module-code shape

Needs review rules:

- blank `CoursePathNo`
- unusual stream/module pairing
- unusual path distribution
- module-code year mismatch against explicit `Year`
- multi-year module usage that may still be real but needs user review

Reject rules:

- missing required fields
- non-numeric `Year`
- malformed `AcYear`
- unparseable `CourseCode`
- impossible student context that breaks core academic assumptions, for example clearly incompatible simultaneous programme contexts inside the same accepted scope

Saved meaning if accepted:

- validated enrollment facts only
- not final programme/path truth

### `rooms.csv`

Required columns:

- `room_code`
- `room_name`
- `capacity`
- `room_type`

Optional columns:

- `lab_type`
- `location`
- `year_restriction`

Accept rules:

- `room_code` is unique within the file
- `room_name` is present
- `capacity` is a positive integer
- `room_type` is one of the supported internal values
- if `year_restriction` is present, it is a positive integer in supported year range

Needs review rules:

- duplicate `room_name` with different `room_code`
- suspiciously small or unusually large capacity
- `lab_type` supplied for a non-lab room
- lab room with blank `lab_type`

Reject rules:

- duplicate `room_code`
- blank `room_code` or `room_name`
- non-numeric or non-positive `capacity`
- unsupported `room_type`
- invalid `year_restriction`

Saved meaning if accepted:

- accepted room catalog and solver-relevant room properties

### `lecturers.csv`

Required columns:

- `lecturer_code`
- `name`

Optional columns:

- `email`

Accept rules:

- `lecturer_code` is unique within the file
- `name` is present

Needs review rules:

- duplicate `name` with different `lecturer_code`
- blank `email`
- non-unique email values when email is being used as a practical matching aid

Reject rules:

- duplicate `lecturer_code`
- blank `lecturer_code` or `name`

Saved meaning if accepted:

- accepted lecturer identity catalog

### `modules.csv` (Optional)

Required columns:

- `module_code`
- `module_name`

Optional columns:

- `subject_name`
- `nominal_year`
- `semester_bucket`
- `is_full_year`

Accept rules:

- `module_code` is unique within the file
- `module_name` is present
- if provided, `nominal_year` is numeric and positive
- if provided, `semester_bucket` is one of supported values
- if provided, `is_full_year` is parseable as boolean

Needs review rules:

- module exists in enrollment-derived data but metadata conflicts with inferred values
- semester/full-year values appear unusual but still parseable

Reject rules:

- duplicate `module_code`
- blank `module_code` or `module_name`
- invalid `nominal_year`, `semester_bucket`, or `is_full_year`

Saved meaning if accepted:

- accepted module metadata that supplements or overrides weakly inferred module details

### `sessions.csv`

Required columns:

- `session_code`
- `module_code`
- `session_name`
- `session_type`
- `duration_minutes`
- `occurrences_per_week`
- `required_room_type`

Optional columns:

- `required_lab_type`
- `specific_room_code`
- `max_students_per_group`
- `allow_parallel_rooms`
- `notes`

Accept rules:

- `session_code` is unique within the file
- `module_code` is present
- `session_name` is present
- `session_type` is one of supported internal values
- `duration_minutes` is a positive integer
- `occurrences_per_week` is a positive integer
- `required_room_type` is one of supported internal values
- if present, `allow_parallel_rooms` is parseable as boolean
- if present, `max_students_per_group` is a positive integer

Needs review rules:

- `module_code` does not yet resolve because enrollment/modules import is missing or incomplete
- lab-like session whose duration is not 180 minutes
- `specific_room_code` points to a room not yet imported
- room-type and session-type combination looks unusual
- `max_students_per_group` appears to imply splitting but `allow_parallel_rooms` is blank or false

Reject rules:

- duplicate `session_code`
- blank required values
- unsupported `session_type` or `required_room_type`
- non-numeric or non-positive `duration_minutes` or `occurrences_per_week`
- invalid `max_students_per_group` or `allow_parallel_rooms`

Saved meaning if accepted:

- accepted shared-session definitions needed for solver readiness

### `session_lecturers.csv`

Required columns:

- `session_code`
- `lecturer_code`

Optional columns:

- none for MVP

Accept rules:

- pair is unique within the file

Needs review rules:

- `session_code` or `lecturer_code` does not yet resolve because prerequisite files are missing

Reject rules:

- blank `session_code` or `lecturer_code`
- duplicate identical pair rows

Saved meaning if accepted:

- accepted session-to-lecturer assignments

### Cross-File Readiness Rules

- `sessions.csv` should not become generation-ready until each accepted session resolves to:
  - a known module
  - at least one lecturer
  - a compatible room path
- unresolved cross-file references may be accepted into the working setup state as incomplete items, but they must appear in readiness checks and block generation where required
- imports should prefer preserving accepted facts plus unresolved references over silently fabricating missing links

## Step 4A: Define Import Recovery And Re-import Rules

- partial import failures must not force the user to restart everything
- invalid rows or broken references should be reported clearly and kept out of accepted data
- users should be able to re-import one file without losing unrelated accepted data
- the system should define when a re-import means:
  - merge
  - replace file-specific data
  - replace the whole setup snapshot
- the system should define how re-import interacts with manually entered or manually corrected data
- manual overrides should not be silently destroyed by a later import; re-import should follow an explicit conflict policy and warn the user when replacing accepted manual values
- provide a clear reset/start-over flow for users who want to discard the current setup and begin again

## Step 5: Define Inference Rules

- infer helpful values from validated imports where possible
- do not silently accept uncertain inferred values
- require user review for inferred values before saving them into accepted setup data
- show why a value was inferred so the user can judge whether it is trustworthy
- keep inferred values visually distinct from imported or manually entered values until accepted
- support bulk review actions for repeated inference patterns so users do not have to approve large volumes one item at a time
- consider simple inference confidence levels such as high/medium/low if they help reduce review fatigue without hiding uncertainty
- avoid unsafe or overly clever inferences that create false confidence

## Step 6: Define Missing-Data Completion

- after import and review, detect what solver-required data is still missing
- show only missing entities, links, or required properties
- manual UI should be targeted, not a giant generic form
- missing-data completion should work at entity/link level where possible, not only isolated fields
- a single manual action should be allowed to satisfy many missing items when appropriate
- keep the number of review and completion steps as low as possible so the setup flow does not become overwhelming

## Step 6A: Define Readiness Checklist

- provide one always-visible readiness view showing what is complete, what needs review, and what is still missing
- solver run should stay blocked until all hard-required setup data is satisfied
- distinguish blocking errors from non-blocking warnings
- checklist items should use actionable language, for example:
  - missing rooms
  - sessions missing lecturers
  - sessions missing duration
  - unresolved inferred programme/path mappings

## Step 7: Define Frontend Flow

- import CSVs
- show validation results
- show review UI for inferred values
- show targeted missing-data forms
- block solver run until required setup is complete
- provide downloadable template CSVs with headers and example rows
- surface clear, actionable error messages at each stage
- make re-import and replace/reset actions understandable and safe

## Step 8: Implementation Order

- backend states/models
- validation rules
- automated tests for validation and import behavior
- CSV schemas
- inference/review flow
- missing-data detection
- frontend changes
- frontend testing for the critical setup flow, especially import, review, readiness, and re-import behavior
- integration with solver input build
- after each major step, verify the new flow still preserves the solver input contract

## Step 8A: Import Execution Model

- decide whether import and validation should run synchronously or asynchronously
- use an async/background approach if real datasets are too large for a normal request-response cycle
- whichever model is used, the user should get clear progress, results, and next actions
- make this decision early enough that backend and frontend architecture do not need major rework later

## Step 8B: Define Solver Input Contract Explicitly

- document the current solver-facing input contract in plain language and keep it as a reference during refactoring
- list which fields are hard-required before generation can run
- verify after each setup-flow change that the resulting accepted setup data can still produce the same solver input semantics
- treat the solver input contract as stable unless solver requirements truly change

### Current `SessionTask` Contract

Each generated solver task currently needs these fields:

- session identity:
  - `session_id`
  - `session_name`
  - `session_type`
- module identity:
  - `module_id`
  - `module_code`
  - `module_name`
- scheduling identity:
  - `occurrence_index`
  - `split_index`
  - `root_session_id`
  - `bundle_key` for same-time parallel-room parts when needed
- delivery requirements:
  - `duration_minutes`
  - `required_room_type`
  - `required_lab_type`
  - `specific_room_id`
- people and attendance:
  - `lecturer_ids`
  - `student_group_ids`
  - `student_membership_keys`
  - `study_years`
  - `student_count`

### Minimum Generation-Ready Meaning

Accepted setup data is generation-ready only when it can produce tasks with all hard-required solver semantics present.

At minimum, generation-ready setup must provide:

- at least one schedulable session
- at least one room
- for every session:
  - linked module identity
  - session name
  - session type
  - duration in minutes
  - occurrences per week
  - at least one lecturer assignment
  - attendance groups or equivalent accepted attendance mapping
- for every attendance mapping used by a session:
  - exact or traceable student membership
  - student count
  - study-year metadata sufficient for room restriction checks
- for every room referenced or eligible:
  - capacity
  - room type
  - lab type where relevant
  - year restriction where relevant

### Hard Precheck Expectations Already Present In Code

Before solving, current prechecks already assume or enforce that:

- rooms exist
- every task has at least one lecturer assigned
- every task has at least one compatible room
- lab-like tasks must be exactly 180 minutes
- same-time parallel-room bundles must have a shared feasible slot across all parts

This means the redesigned setup flow should block generation until these conditions can be satisfied from accepted setup data.

### Practical Translation For Setup Flow

The setup system does not need to expose `SessionTask` directly to the user.

But before generation is allowed, the accepted setup state must be able to answer all of these questions reliably:

- what real sessions exist?
- which modules does each session serve?
- which attendance groups attend each session?
- which exact students are inside those attendance groups?
- which lecturers teach each session?
- how long is each session and how often does it occur?
- what kind of room can host it?
- if the audience is too large, can it split and run in parallel rooms?

If any of those questions cannot be answered, the readiness checklist should surface the missing accepted setup data instead of letting generation fail deep inside the solver.

## Step 8C: Mapping Rules

- define where terminology mapping is allowed, for example between imported programme/path/module labels and accepted internal names
- keep mapping rules explicit, reviewable, and limited in scope
- do not let mapping logic become a hidden second source of truth

## Step 9: Audit And History

- keep enough metadata to explain where accepted data came from:
  - imported
  - inferred then user-approved
  - manually entered
- record file import time and source file identity where practical
- keep the audit MVP small at first, for example source and last-modified information
- defer full change-history features unless they become clearly necessary

## Step 10: First-Time User Flow

- define whether setup should feel like a guided sequence, a flexible dashboard, or a hybrid of both
- keep the first-time experience clear enough that a user can understand what to do next without deep system knowledge
- use the readiness checklist to support orientation, not just validation blocking

## Guiding Principles

- do not force everything into one CSV
- do not assume university exports are solver-ready
- do not mix raw facts, inferred values, and solver input
- keep solver input as stable as possible
- prefer review and completion over silent guessing
- provide clear, actionable feedback whenever validation or review blocks progress
- keep mapping and audit scope controlled so they do not become hidden sources of complexity
- keep the MVP narrow and avoid scope creep during implementation
