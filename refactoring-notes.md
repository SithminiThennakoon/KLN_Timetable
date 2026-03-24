# Refactoring Notes

## Biggest business logic and user flow issues

### 1. Destructive save/load flows replace the entire dataset

Several setup actions that look incremental are actually full dataset replacements.

- `persistAddedRecord()` immediately saves the whole draft when a modal add action is used, such as "Save Lecturer".
- Enrollment import also replaces the entire dataset.
- `replace_dataset()` deletes all setup data and every generated run/solution before reinserting the new payload.

Why this is a problem:

- Adding one lecturer, room, module, or session can silently wipe generated timetable runs.
- Loading reviewed enrollment data is effectively a destructive overwrite, not a merge/update flow.
- The UI mixes local draft editing with immediate destructive persistence, which is easy for operators to misunderstand.

Relevant references:

- `frontend/src/pages/SetupStudio.jsx`
- `backend/app/routes/timetable_v2.py`
- `backend/app/services/timetable_v2.py`

### 2. Student timetable filtering is wrong for "Year N - General"

The student lookup API exposes year-specific general options like "Year 1 - General" and "Year 2 - General", but the frontend does not send the year when the user selects a general option.

Current behavior:

- The frontend sends `degreeId` and omits `pathId` for "general".
- The backend then loads all pathless groups for that degree, without filtering by year.

Why this is a problem:

- "Year 1 - General" and "Year 2 - General" can resolve to the same timetable.
- Student timetable exports can include the wrong cohort set.
- The UI suggests a level of precision the backend does not honor.

Relevant references:

- `frontend/src/pages/ViewStudio.jsx`
- `backend/app/services/timetable_v2.py`

### 3. Lecturer and student timetable filtering uses names instead of stable IDs

Serialized solution entries store `lecturer_names` and `student_group_names`, and the view logic filters against those strings.

Why this is a problem:

- Duplicate lecturer names can merge multiple lecturers into one timetable view.
- Duplicate student group names can leak sessions into the wrong student timetable.
- This is identity corruption in a domain where stable IDs already exist.

Relevant references:

- `backend/app/services/timetable_v2.py`

### 4. `cohort_year` is a UI-only field and is not truly persisted

Setup Studio exposes calendar year on cohorts and uses it in session-side filtering, but the backend schema and persistence path do not actually carry that field through as part of student groups.

Current behavior:

- The frontend builds and edits `cohort_year`.
- `StudentGroupInput` does not define `cohort_year`.
- `read_dataset()` does not return it.
- `replace_dataset()` does not persist it to `V2StudentGroup`.

Why this is a problem:

- Users can set calendar-year cohort data and lose it after save/reload.
- Session filtering based on `cohort_year` operates on transient frontend state instead of durable data.
- The UI implies a real business concept that the backend does not support.

Relevant references:

- `frontend/src/pages/SetupStudio.jsx`
- `backend/app/schemas/v2.py`
- `backend/app/services/timetable_v2.py`

### 5. Room year restrictions are captured but not enforced

The room setup flow asks users to enter `year_restriction`, and the guidance text says the solver uses year restrictions, but the actual room matching logic does not consider that field.

Current behavior:

- The UI captures `year_restriction`.
- The backend schema stores it.
- The frontend validation/matching logic only checks room type, lab type, and specific room.
- The scheduling flow does not appear to apply `year_restriction` during matching.

Why this is a problem:

- Users believe they are constraining room allocation when they are not.
- Schedules can place cohorts into rooms that were meant to be restricted away from them.
- This creates a high-trust UX mismatch between setup inputs and actual solver behavior.

Relevant references:

- `frontend/src/pages/SetupStudio.jsx`
- `frontend/src/pages/setup/RoomsStep.jsx`
- `frontend/src/pages/setup/setupHelpers.js`
- `backend/app/schemas/v2.py`

## Recommended refactor order

1. Fix destructive save semantics so incremental actions do not wipe runs or replace unrelated setup data.
2. Fix timetable view filtering to use stable IDs, not names.
3. Fix student general-year filtering so the selected year is part of the request and backend query.
4. Either fully implement `cohort_year` end to end or remove it from the UI until it is real.
5. Either enforce `year_restriction` in validation/solver logic or remove/relabel it so operators are not misled.

## Future work after demo

### CSV and import realism

- The CSV is good enough as the primary student-attendance source, but not enough as a full timetable-input source.
- It still leaves major non-CSV teaching data to be entered manually:
  - lecturers
  - rooms and room capabilities
  - shared teaching structure
  - weekly teaching intent
- A large portion of raw CSV rows are still excluded or ambiguous during import, especially around:
  - cross-year module registrations
  - common modules
  - repeaters
  - path ambiguity

### Sample seed realism issues

- The current realistic sample missing-data seed is operational, but still too synthetic.
- It seeds sessions for only part of the imported module set, not the full imported academic world.
- It currently exercises almost no same-time parallel teaching behavior.
- It still produces some tiny one-student or two-student weekly sessions that are likely repeater or exception cases and should not behave like standard scheduled teaching.
- Some derived attendance-group labels appear too simplistic for the actual module mix they carry, so group labeling may be misleading even when underlying student membership is correct.

### Generated timetable realism issues

- The sample-generated timetable is verifier-valid, but some patterns still look unrealistic:
  - very heavy Friday concentration
  - near-saturated flagship lecture rooms
  - a few cohorts with unusually high weekly hours
  - placeholder lecturer workloads that may not resemble real faculty allocation
- The biggest realism risk is not solver correctness now; it is whether the seeded sample world resembles the real faculty strongly enough for meaningful demo confidence.

### Best follow-up work after the demo

1. Separate repeater-style and tiny exception groups from normal weekly teaching seeding.
2. Improve attendance-group labeling so mixed/common groups are represented honestly.
3. Expand realistic seeding to cover shared teaching patterns and more realistic lecturer assignment.
4. Rebalance seeded room and day usage so demo generations are less artificially skewed.
5. Re-check which imported modules should become active weekly teaching demand versus historical or exceptional enrollments.
