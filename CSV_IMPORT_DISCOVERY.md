## CSV Import Discovery

This document captures the current shared understanding of `students_processed_TT_J.csv` before implementation of a reviewed CSV import flow.

It is intentionally written as a discovery snapshot, not a final technical contract.

## Source File

- File: `students_processed_TT_J.csv`
- Header:
  - `CoursePathNo`
  - `CourseCode`
  - `Year`
  - `AcYear`
  - `Attempt`
  - `stream`
  - `batch`
  - `student_hash`

## Verified Facts

- The file behaves like row-level enrollment data.
- One row appears to represent one student registered for one module in one academic year and one attempt.
- Duplicate `(student_hash, CourseCode, AcYear, Attempt)` rows were not found in the current file.
- `Attempt` is always `1` in the current CSV snapshot.
- `batch` means intake year.
- `AcYear` means the academic year of the registration, and is different from `batch`.
- `CoursePathNo` means the main subject combination chosen by the student.
- `CoursePathNo` is only unique within a degree/stream.
- `student_hash` is the closest thing to an individual student identifier available in the CSV.

## Module Code Understanding

- Module codes use a `SUBJ 12345` style format.
- The first four letters represent the subject.
- The first digit in the numeric part usually indicates the module's nominal year.
- The second digit usually indicates semester semantics:
  - `1` = semester 1
  - `2` = semester 2
  - `3` = full year
- The current CSV also contains many modules with second digit `4`.
- Existing code already treats semester digit `4` like semester 2 for timetable bucketing.
- The remaining digits are not currently required for timetable generation.
- Some real modules have nominal year digit `0` such as `BSSS 01512`.
- Those `0xxxx` modules are valid source codes and must not be treated as parse failures.

## Clarified Meaning Of `Year`

- `Year` should be treated as the year that the module is offered to the students in this dataset.
- In many ordinary cases, this matches the first digit of the module code.
- There are valid exceptions where the CSV `Year` does not match the module code's nominal year.

Examples already acknowledged by the user:

- Some management or service modules are offered to science students in later years.
- Some compulsory catch-up rules can make a Level 1 module appear for Level 3 students.
- Some modules with year digit `4` appear to be offered to Year 3 students.

Because of that, module-code year must be treated as a validation signal, not as the final source of truth.

## Current Mismatch Findings

The CSV contains systematic `Year` vs module-code-year mismatches.

Observed totals from analysis of the current file:

- Total rows: `253356`
- Unique students: `7146`
- Mismatched rows: `13044`
- Unique mismatched module codes: `275`
- Semester digit counts:
  - `1`: `127097`
  - `2`: `105261`
  - `3`: `7874`
  - `4`: `13124`
- Modules with nominal year digit `0`: `6`
  - `BSSS 01512`
  - `BSSS 01522`
  - `BSSS 01532`
  - `BSSS 01542`
  - `BSSS 01552`
  - `BSSS 01562`
- Blank field counts in the current CSV snapshot:
  - `CoursePathNo`: `28`
  - `batch`: `0`
  - `Attempt`: `0`
  - `AcYear`: `0`
- Malformed `AcYear` rows detected with `YYYY/YYYY` check: `0`

Important implication:

- Mismatches are not just random row noise.
- Some mismatches are part of real curriculum behavior.
- The import pipeline must classify mismatch patterns instead of assuming they are always data errors.
- Some fields that look structurally optional in the raw file, such as `CoursePathNo`, still need an explicit review policy because blanks do exist.

## Important Known Risk

The current realistic dataset builder does not preserve exact student-level clash semantics.

- It converts enrollment rows into generated student groups.
- It can create overlapping group membership.
- The solver currently protects exact student groups more strongly than shared underlying students.

This means raw registration data and generated clash units are not currently equivalent.

## Decisions Already Leaning Toward Consensus

- The future CSV import path should preserve exact registrations as much as possible.
- Ambiguous data should not be silently dropped.
- Ambiguous records should be reviewed in grouped patterns rather than prompting row by row.
- Unresolved records should remain visible in an audit trail, even if excluded from timetable demand.

## Still Unclear / Needs Phase 1 Handling

- How common modules that cut across paths should be represented in timetable demand.
- Which mismatch patterns are accepted curriculum exceptions versus suspicious anomalies.
- How the system should distinguish real lecture-attending demand from registration records that do not imply lecture attendance.
- How exact student-level overlap should be represented efficiently enough for generation.
- Whether blank `CoursePathNo` should mean a path-independent/common-module case or an incomplete source row.

## What This Means For Implementation

Pre-Phase-1 conclusion:

- The CSV is useful and structured enough to import.
- But it should enter a staging and review pipeline first.
- It should not be treated as already-clean timetable demand.
