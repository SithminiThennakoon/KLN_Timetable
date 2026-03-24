# Minimal Setup UI Contract

## Goal

Replace the current mixed `SetupStudio` experience with a minimal setup flow that matches the canonical import/snapshot backend.

This contract is only for the setup / data import / data entry part of the system.

The target user outcome is:

1. import whatever CSVs they can export from the main system
2. understand what the system accepted
3. see exactly what is still missing
4. enter only the missing data manually
5. continue to generation

## Product Position

The setup UI is not a generic dataset editor.

It is a guided readiness workflow for one working import snapshot.

The user should not have to think in terms of:

- legacy V2 dataset tables
- solver tasks
- internal normalization stages
- full manual authoring of the whole university

The user should only have to think in terms of:

- what files they have
- what the system already understood
- what is still missing before generation

## Canonical Backend Path

The setup UI should treat this as the only primary path:

1. enrollment import materialization
2. import workspace
3. snapshot completion
4. generation readiness

Current backend pieces that already support this:

- `POST /api/v2/imports/enrollment-analysis-upload`
- `POST /api/v2/imports/enrollment-projection-upload`
- `POST /api/v2/imports/enrollment-materialize-upload`
- `GET /api/v2/imports/{import_run_id}/workspace`
- `GET /api/v2/imports/{import_run_id}/snapshot`
- snapshot CRUD endpoints for lecturers, rooms, shared sessions
- `POST /api/v2/imports/{import_run_id}/snapshot/seed-realistic-missing-data`
- generation and verification endpoints

The setup UI should not depend on:

- `/api/v2/dataset`
- `/api/v2/dataset/full`
- `/api/v2/imports/{import_run_id}/publish-legacy`

Those are transitional compatibility paths, not the target product surface.

## Minimal Screen Structure

The setup area should be one page with four sections, in this order:

1. `Import Files`
2. `What The System Understood`
3. `Missing For Generation`
4. `Continue`

No step wizard is required for MVP.

If the page is structured well, a single vertically stacked workflow is easier to understand than the current multi-step editor.

## Section 1: Import Files

Purpose:

- make CSV import the default path
- show the supported schemas clearly
- let the user import files independently

### UI behavior

Show one compact import card per supported schema:

- `Student Enrollments`
- `Rooms`
- `Lecturers`
- `Sessions`
- `Session Lecturers`
- optionally `Modules` if needed later

Each card should show:

- schema name
- one-line purpose
- download template action
- import/replace file action
- current status

Status should be one of:

- `Not imported`
- `Imported`
- `Imported with warnings`
- `Needs review`

### MVP note

Right now only the enrollment import path is fully first-class in the backend.

So the initial UI reimplementation can do this honestly:

- ship `Student Enrollments` as active
- show `Rooms`, `Lecturers`, and `Sessions` as manual-entry-backed for now
- add real CSV import buttons for those only when their backend contracts are implemented

Do not fake “full CSV support” in the UI before the backend is real.

## Section 2: What The System Understood

Purpose:

- confirm that import worked
- reduce user anxiety
- avoid forcing them into raw tables too early

Show a compact summary from the workspace:

- programmes found
- programme paths found
- attendance groups found
- curriculum modules found
- lecturers currently present
- rooms currently present
- shared sessions currently present

This section is read-mostly.

It should not look like a spreadsheet editor.

It should answer:

- “Did the system understand my import?”
- “Did it create the academic structure I expected?”

## Section 3: Missing For Generation

Purpose:

- make manual data entry targeted and minimal
- block generation for real reasons only

This is the most important part of the setup UI.

The page should show a checklist grouped by missing item type, for example:

- no rooms yet
- sessions missing lecturers
- sessions missing attendance groups
- sessions missing module links
- sessions with incompatible specific rooms
- lab-like sessions with invalid duration
- split-group sessions that cannot run with current parallel-room settings

Each checklist item must have a direct fix action.

Examples:

- `Add rooms`
- `Add lecturers`
- `Add shared session`
- `Edit 12 incomplete sessions`

### Manual entry principle

Manual entry is not a separate parallel setup mode.

It is only a gap-filling mechanism for unresolved readiness items.

That means:

- do not expose giant generic editors first
- do not ask the user to enter everything manually unless import is impossible
- open focused forms only for what is missing

## Section 4: Continue

Purpose:

- make the transition into generation obvious

Show:

- readiness result
- blocking issue count
- warning count
- `Continue to Generate` button

Behavior:

- disable continue when blocking items remain
- allow continue when only warnings remain

## Manual Forms Required For MVP

The minimum manual forms should be:

1. `Add / Edit Room`
2. `Add / Edit Lecturer`
3. `Add / Edit Shared Session`

The shared session form is the most important because it captures:

- teaching event identity
- linked curriculum modules
- attendance groups
- lecturers
- session type
- duration
- occurrences per week
- room requirement
- split/parallel semantics

This matches the actual solver-facing need much better than the old full manual dataset editor.

## What The UI Should Hide

The setup UI should not expose these concepts directly in MVP:

- degrees as manually authored top-level entities
- paths as manually authored primary entities
- full manual module catalog authoring as the default flow
- direct editing of attendance-group student membership
- any “publish to legacy dataset” action

Those are either derived from imports, advanced repair tools, or transitional implementation details.

## MVP Scope Decision

The setup UI MVP should deliberately support this practical flow:

1. import enrollment CSV
2. inspect interpreted structure
3. add missing rooms
4. add missing lecturers
5. add missing shared sessions
6. generate

This is narrower than the final multi-CSV vision, but it is honest and aligned with the current backend.

The next expansion after MVP should be:

1. add `rooms.csv`
2. add `lecturers.csv`
3. add `sessions.csv`
4. add `session_lecturers.csv`

## Current Codebase Assessment Against This Contract

### Already aligned

- import-run based workflow exists
- workspace summary data exists
- snapshot manual completion endpoints exist
- generation, verification, and export exist
- readiness-style diagnostics exist in backend service code

### Not aligned yet

- current `SetupStudio.jsx` still behaves like a large editor
- frontend service still exposes legacy dataset endpoints as normal setup tools
- setup UI mental model is still mixed between:
  - full manual dataset authoring
  - snapshot completion
  - legacy compatibility
- non-enrollment CSV imports are not yet first-class end-to-end

## Implementation Rule

When reimplementing the setup UI:

- start from this contract
- use the snapshot/import backend only
- delete UI paths that push users toward the legacy dataset editor
- add missing backend support only when the contract proves a real gap

## Immediate Build Plan

1. create a new minimal `SetupStudio` skeleton around the four sections above
2. load active import snapshot from local storage as today
3. read only:
   - import workspace
   - snapshot completion data
   - readiness summary
4. keep manual forms only for rooms, lecturers, and shared sessions
5. remove old degree/path/module/cohort full-editing surfaces from the primary page

