## CSV Import Phase 1 Spec

This document defines the Phase 1 contract for importing enrollment-style CSV data into a reviewed staging pipeline.

Phase 1 does not yet implement full generation behavior. It defines the data meaning, review categories, and acceptance rules needed before building the importer.

## Phase 1 Goals

- Define what each CSV field means inside the system.
- Define which derived fields the importer must calculate.
- Define anomaly categories and review buckets.
- Define what is accepted automatically, what requires review, and what is invalid.
- Define the minimum audit output expected from an import run.

## Scope

Phase 1 applies to CSVs shaped like `students_processed_TT_J.csv`.

Expected columns:

- `CoursePathNo`
- `CourseCode`
- `Year`
- `AcYear`
- `Attempt`
- `stream`
- `batch`
- `student_hash`

## Data Contract

### Raw Fields

- `student_hash`
  - Meaning: anonymized individual student identifier.
  - Phase 1 status: primary person key for exact registration preservation.

- `CourseCode`
  - Meaning: module code taken by the student.
  - Phase 1 status: primary module key from the source file.

- `Year`
  - Meaning: the year in which the module is offered to the students represented by this row.
  - Phase 1 status: authoritative operational year for import logic.
  - Note: this field is allowed to differ from the module-code nominal year.

- `AcYear`
  - Meaning: academic year of the registration.
  - Phase 1 status: source context field for filtering and cohort reconstruction.

- `Attempt`
  - Meaning: module attempt number from the source data.
  - Phase 1 status: preserved as source metadata.

- `stream`
  - Meaning: degree/program family.
  - Phase 1 status: top-level academic grouping.

- `batch`
  - Meaning: intake year.
  - Phase 1 status: cohort lineage field, not interchangeable with `AcYear`.

- `CoursePathNo`
  - Meaning: main subject combination chosen by the student within the degree/program.
  - Phase 1 status: path-like grouping field.
  - Constraint: only unique inside the `stream` context.

### Derived Fields

The importer must derive these values from `CourseCode` when possible:

- `module_subject_code`
  - First four-letter subject prefix.

- `module_nominal_year`
  - First digit of the numeric part.

- `module_nominal_semester`
  - Second digit of the numeric part.
  - Interpretation:
    - `1` => semester 1
    - `2` => semester 2
    - `3` => full year
    - `4` => treat as semester 2 for timetable bucketing, but preserve the raw code value
  - Any other value should be preserved but flagged.

- `module_nominal_semester_code`
  - Raw second digit from the module code.
  - This is preserved even when it is later normalized for timetable use.

- `module_code_parse_status`
  - `parsed`
  - `unparsed`

- `module_nominal_year`
  - Note: `0` is allowed as a parsed nominal year because the CSV contains real modules such as `BSSS 01512`.
  - Nominal year `0` is not automatically invalid, but it will normally require review because it cannot directly match taught years `1-4`.

## Validation Rules

### Automatically Valid

A row is automatically valid for staging when all of the following hold:

- required fields are present:
  - `student_hash`
  - `CourseCode`
  - `Year`
  - `AcYear`
  - `stream`
- `AcYear` matches `YYYY/YYYY`
- `Year` is numeric
- `CourseCode` parses into the expected prefix + digits structure

Automatic validity means the row enters staging, not that it is automatically accepted as timetable demand.

Additional field handling rules:

- `batch`
  - required for automatic validity
  - missing `batch` makes the row `ambiguous` at minimum, and may be promoted to `invalid` if no recovery rule exists

- `Attempt`
  - required source metadata
  - missing `Attempt` makes the row `ambiguous`

- `CoursePathNo`
  - may be present or blank in raw data
  - blank `CoursePathNo` is not automatically invalid
  - blank `CoursePathNo` must enter review because it may indicate a common module, path-independent teaching, or incomplete source data

### Automatically Invalid

A row is automatically invalid when any of the following hold:

- missing required fields
- non-numeric `Year`
- malformed `AcYear`
- unparseable `CourseCode`
- impossible or empty person/module identity

Invalid rows must be quarantined and reported.

## Anomaly Classification

Phase 1 defines four statuses for staged rows and row groups.

- `valid`
  - No detected issue that requires review.

- `valid_exception`
  - The row breaks a naive rule, but matches an allowed curriculum exception or an approved review rule.

- `ambiguous`
  - The row may be legitimate, but Phase 1 cannot classify it safely using existing rules.

- `invalid`
  - The row cannot be trusted structurally.

## Required Review Buckets

The importer must group ambiguous or exception-heavy rows into review buckets, not prompt row by row.

Minimum bucket types:

- `year_code_mismatch`
  - CSV `Year` differs from `module_nominal_year`.

- `unusual_stream_module_pair`
  - module appears in a stream where it is rare or unexpected.

- `unusual_path_distribution`
  - module appears across paths in a way that suggests a common module or path-independent teaching.

- `rare_module_pattern`
  - isolated or low-frequency anomalies that do not fit an already approved rule.

- `semester_code_unusual`
  - module-code semester digit is outside the normal timetable semantics.

- `blank_course_path`
  - row has no `CoursePathNo` and requires interpretation.

- `missing_attempt`
  - row has no `Attempt` value.

- `missing_batch`
  - row has no `batch` value.

- `malformed_academic_year`
  - `AcYear` is present but not in `YYYY/YYYY` format.

- `nominal_year_zero`
  - module code starts with nominal year digit `0` and needs explicit interpretation.

## Review Policy

Phase 1 review must work at pattern level.

Examples of reviewable pattern policies:

- accept all rows for `MGMT 11022` where `Year = 2`
- accept all `Year = 3` / `module_nominal_year = 4` rows for approved subject families
- treat certain modules as path-independent common modules
- treat semester digit `4` as semester bucket `2` while preserving the raw code
- classify blank `CoursePathNo` rows as approved path-independent/common-module data where justified
- keep certain modules excluded from timetable demand until clarified

## Acceptance Rules

### Source Of Truth Priority

When fields disagree, use this priority in Phase 1:

1. reviewed import rule
2. CSV explicit field values
3. module-code-derived hints

This means:

- `Year` from CSV wins over nominal module-code year unless a review rule says otherwise.
- module-code year is a warning signal, not the final truth source.
- raw parsed module-code fields must remain preserved even if reviewed scheduling fields differ.

### Raw Fields vs Reviewed Scheduling Fields

Phase 1 separates source parsing from reviewed scheduling interpretation.

Raw parsed fields include:

- `module_nominal_year`
- `module_nominal_semester_code`
- `module_nominal_semester`

Later reviewed scheduling fields may include:

- effective timetable year
- semester bucket
- full-year status
- path interpretation

Phase 2 and later phases must not overwrite reviewed scheduling decisions with raw module-code assumptions.

### Unresolved Ambiguity Policy

If a row or bucket remains unresolved after automated checks and user review:

- keep it in the import audit output
- mark it as unresolved
- exclude it from timetable-demand generation by default
- never drop it silently

## Audit Output Requirements

Every import run must be able to produce a summary containing at least:

- total rows read
- valid rows
- valid-exception rows
- ambiguous rows
- invalid rows
- rows excluded from timetable demand
- rows included in timetable demand
- review buckets created
- review rules applied

## Decisions Stored As Rules

Phase 1 assumes user classifications should be reusable.

Decision rules should be representable in a machine-readable form such as:

- match by exact module code
- match by module subject prefix
- match by `(stream, Year, module_nominal_year)`
- match by `(stream, Year, module_nominal_semester_code)`
- match by common-module designation
- match by known catch-up module policy

## Non-Goals For Phase 1

Phase 1 does not yet define:

- final database schema for staged imports
- final UI screens for review
- student-level solver constraints
- final transformation from reviewed registrations into timetable sessions/cohorts

Those belong to later phases.

## Exit Criteria

Phase 1 is complete when:

- the CSV field contract is agreed
- anomaly categories are agreed
- unresolved-data policy is agreed
- audit expectations are agreed
- import review decisions can be expressed as reusable rules
