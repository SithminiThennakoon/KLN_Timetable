# Backend Model Migration

This document maps the current `v2_*` backend model to the target csv-first architecture.

## Current model summary

The current backend compresses 3 concerns into one layer:

- academic structure
- attendance / clash truth
- solver-facing grouping

That compression mainly happens through `v2_student_group`.

Today:

- `v2_degree` stores programme-level metadata
- `v2_path` stores academic path labels
- `v2_student_group` stores both:
  - academic grouping
  - effective clash membership through `student_hashes_json`
- `v2_module` stores curriculum module identity
- `v2_session` stores the real teaching event, but still depends on the flattened group model
- `v2_generation_run` / `v2_timetable_solution` / `v2_solution_entry` store solver outputs

## Main problems in the current model

### 1. `v2_student_group` does too much

It currently acts as:

- academic cohort
- imported audience bucket
- clash unit
- session attendance group
- partial storage for student-level truth

Those roles need to be separated.

### 2. Raw import facts are not preserved

The current import pipeline projects csv rows directly into the flattened v2 dataset.
That means the system loses:

- raw `CoursePathNo`
- import ambiguity
- review decisions at row/bucket level
- the distinction between imported fact and inferred academic structure

### 3. Manual and import flows collapse into the same persistence shape

The backend currently treats:

- manual authoring
- demo loading
- reviewed import projection

as alternate ways to replace the same `DatasetUpsertRequest` model.

That is transitional only.

## Mapping current entities to target entities

### `v2_degree`

Current role:

- degree/programme metadata

Target:

- becomes `programme`

Likely preserved fields:

- code
- name
- duration_years
- intake_label

Notes:

- direct replacement conceptually
- should stop being the top-level owner of clash truth

### `v2_path`

Current role:

- year-specific academic path labels

Target:

- becomes `programme_path`

Likely preserved fields:

- degree/programme relation
- year
- code
- name

Notes:

- path should become interpreted academic structure, not raw imported truth
- may need explicit support for `common` / `unstreamed` / inferred paths

### `v2_student_group`

Current role:

- degree/path/year group
- size
- student membership via `student_hashes_json`

Target:

This must split into multiple layers:

- `import_student`
- `import_row`
- `import_enrollment`
- `student_programme_context`
- `student_module_membership`
- `attendance_group`

What survives:

- some current groups may become derived `attendance_group` records
- `student_hashes_json` should be replaced by normalized student membership relations

What is removed from this one-table concept:

- raw import storage
- canonical clash truth
- interpreted path assignment

### `v2_module`

Current role:

- curriculum module identity

Target:

- becomes `curriculum_module`

Likely preserved fields:

- code
- name
- subject_name
- year
- semester
- is_full_year

Notes:

- current model is close, but the final system should distinguish raw imported course identity from normalized curriculum-module identity when needed

### `v2_session`

Current role:

- real teaching event
- room requirements
- lecturer assignments
- linked modules
- attending student groups

Target:

- becomes `shared_session`
- plus join tables:
  - `shared_session_module_link`
  - `shared_session_attendance_group`

Likely preserved fields:

- name
- session_type
- duration_minutes
- occurrences_per_week
- required_room_type
- required_lab_type
- specific_room_id
- max_students_per_group
- allow_parallel_rooms
- notes

Notes:

- this is one of the current entities that is already close to the final concept
- the main change is what it links to

### `v2_lecturer`

Current role:

- canonical lecturer identity

Target:

- stays `lecturer`

Likely preserved fields:

- name
- email

Notes:

- mostly stable concept

### `v2_room`

Current role:

- canonical room identity and capability data

Target:

- stays `room`

Likely preserved fields:

- name
- capacity
- room_type
- lab_type
- location
- year_restriction

Notes:

- concept survives, but enforcement logic must be fixed

### `v2_generation_run`

Current role:

- stores one generation execution and soft-constraint selection

Target:

- stays `generation_run`

Likely preserved fields:

- status
- selected_soft_constraints
- total_solutions_found
- truncated
- max_solutions
- time_limit_seconds
- message
- possible_soft_constraint_combinations

Needs additions:

- explicit normalized data snapshot reference
- verification status summary

### `v2_timetable_solution`

Current role:

- stores candidate/default solutions

Target:

- stays `timetable_solution`

Likely preserved fields:

- ordinal
- is_default
- is_representative

Needs additions:

- maybe verification agreement summary

### `v2_solution_entry`

Current role:

- scheduled placement of a session occurrence in a room/time

Target:

- stays `solution_entry`

Likely preserved fields:

- session id
- occurrence_index
- split_index
- room id
- day
- start_minute
- duration_minutes

Notes:

- stable concept

## Target new tables

The backend should add these new canonical groups.

### Raw import layer

- `import_run`
- `import_row`
- `import_student`
- `import_enrollment`
- `import_review_rule`

### Interpreted academic layer

- `programme`
- `programme_path`
- `student_programme_context`
- `curriculum_module`
- `student_module_membership`

### Solver-facing derived layer

- `attendance_group`
- `attendance_group_student`
- `shared_session`
- `shared_session_module_link`
- `shared_session_attendance_group`

### Verification layer

- `verification_run`
- `verification_result`

## Migration order

### Stage 1

Add the raw import layer without deleting `v2_*`.

Goal:

- preserve imported facts and ambiguity
- stop losing meaning during import

### Stage 2

Add interpreted academic-structure tables.

Goal:

- represent programme/path context without forcing it to be the final clash truth

### Stage 3

Add derived attendance groups and refit the solver input builder.

Goal:

- solver continues to work on efficient groups
- groups become traceable back to exact students

### Stage 4

Refit manual setup so it edits:

- rooms
- lecturers
- shared sessions
- solver requirements
- controlled corrections

and does not act as the primary attendance authoring flow.

### Stage 5

Refit timetable views so they use canonical identities instead of matching names or flattened groups.

### Stage 6

Add external verification snapshot export and the 3 verifier integrations.

## Practical conclusion

The current backend is not wrong everywhere.

What can survive with limited conceptual change:

- rooms
- lecturers
- modules
- shared-session style session entity
- generation runs
- solutions
- solution entries

What must be fundamentally redesigned:

- student grouping
- import persistence
- path interpretation
- clash truth
