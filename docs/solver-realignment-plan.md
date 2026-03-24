# Solver Realignment Plan

This file is a working guide for ongoing solver/system fixes.

It is intentionally written to survive context compaction better than chat history.

## Current intent

We should NOT blindly restore the system to `prompts.md`.

Instead:

- use `prompts.md` mainly as the best description of real-life timetable behavior and solver capability requirements
- preserve later improvements made after implementation
- prefer the simplest model that still handles the real university cases
- be skeptical of both the old spec and the current code
- optimize for practical admin workflows, usable setup, and correct solver behavior

## Canonical direction

Treat the newer CSV/import-based flow as the intended direction unless a concrete issue proves otherwise.

Very simple shape:

1. raw import facts
2. reviewed / corrected import facts
3. interpreted academic structure
4. solver-facing attendance/session/resource model
5. generation
6. verification

In code, that currently maps roughly to:

- raw import: `backend/app/models/imports.py`
- academic/interpreted: `backend/app/models/academic.py`
- solver attendance truth: `backend/app/models/solver.py`
- solver setup/session metadata: `backend/app/models/snapshot.py`
- generation/view/export: `backend/app/services/timetable_v2.py`
- verification: `backend/app/services/verification.py`

## Important framing

The main goal is:

- make sure solver logic can handle the real situations described in `prompts.md`
- while preserving the good architectural/product improvements added later

The comparison standard is therefore:

- `prompts.md` = baseline for solver capability
- current codebase = baseline for newer system improvements
- target state = keep improvements, close real solver/data-model/setup gaps

## What already seems right

- CSV-first setup with manual completion wizard
- preserving raw import facts separately from interpreted academic structure
- attendance groups derived from real student membership
- shared teaching sessions linked to multiple curriculum modules
- separate verification phase with multiple verifiers
- support for split sessions and same-time parallel rooms

## Main known issues

### 1. Transitional architecture still active

The codebase still has both:

- old legacy `v2_*` dataset path
- newer import/snapshot path

This split truth is the biggest architectural problem.

### 2. Shared-session model is not fully clean internally

Even in snapshot solving, some internal code still falls back to a `primary_module_id` style assumption.

Target mental model should be:

- the shared teaching session is the real object
- module identities are linked interpretations of that same event

### 3. Some real-world constraints are still thin or missing

Potentially missing / under-modeled:

- lecturer availability / blackouts
- room availability / blackout periods
- richer room capabilities/equipment
- session-level fixed/preferred/forbidden timing
- alternate-week / irregular teaching
- correction tools for wrongly derived attendance structures

These should only be added if they are practically needed.

### 4. Legacy retirement is incomplete

At least some legacy bridge endpoints still existed while tests expected them to be retired.

## Progress update

The following fixes have already been implemented in code:

- legacy `POST /api/v2/imports/enrollment-load` now returns `410 Gone`
- legacy `POST /api/v2/imports/{import_run_id}/publish-legacy` now returns `410 Gone`
- snapshot readiness helper was restored so tests and snapshot journey code can evaluate setup completeness
- import workspace module mapping now attaches derived attendance groups more realistically instead of relying on exact signature matches only
- demo snapshot seeding now produces a solvable canonical snapshot journey instead of overloading a few lecturers immediately
- snapshot solver paths now avoid redundant coarse group blockers when exact student membership keys are already present

## What is now covered by tests

- retired legacy endpoints return `410`
- demo import -> seed -> readiness -> generation journey reaches a feasible/generated state
- snapshot readiness is blocked before rooms/lecturers/shared sessions exist
- seeding populates missing snapshot data and produces a ready workspace
- generated verification payload passes the Python hard-constraint verifier
- seeded snapshot generation exposes student hashes in verification payloads
- demo seeding is bounded to a practical sample size rather than exploding into an unrealistic test dataset

## What still needs deeper work

- remove remaining hybrid legacy branches from generate/view/export paths
- clean `primary_module_id` style assumptions that still leak into shared-session internals
- validate split-session semantics against real student-level overlap behavior
- decide whether additional real-world constraints are actually needed before modeling them

## Testing strategy going forward

Focus tests on the canonical snapshot path first.

Priority order:

1. service-level tests for import materialization, readiness, seeding, generation, and verification
2. API tests for snapshot workspace endpoints and retired legacy endpoints
3. regression tests for shared-session, split-session, and student-overlap invariants
4. only then broader UI/integration coverage where it helps protect the canonical flow

The main principle is:

- if a behavior matters to real timetable generation, there should be a direct backend test for it

## Practical evaluation rule for future work

For each issue, classify as one of:

- `keep` = newer implementation is a real improvement
- `fix` = current implementation cannot support an important real-world case
- `clarify` = old spec and newer implementation diverge and need a decision
- `remove` = leftover legacy/transitional code that should be retired

## Current working defaults

- prefer simplest model that still handles reality
- do not revert to manual-first design
- do not preserve legacy code just because it exists
- do not add theoretical solver features unless they matter in real faculty operation
- ask the user when a choice materially changes product behavior or system scope

## High-priority implementation direction

1. retire low-value legacy bridge endpoints that should no longer be used
2. stabilize canonical snapshot/import path
3. clean solver-facing shared-session semantics
4. verify generation + verification path with tests
5. only then expand missing real-world constraints if needed

## Known uncertainties / decisions still open

These are not blockers for basic cleanup, but they may affect later work.

### Enumeration policy

`prompts.md` talks about generating all possible timetables, but the current system uses practical limits, truncation, and representative previews.

Current recommendation:

- keep bounded practical generation unless there is a concrete reason to enforce exhaustive enumeration in production

### Student view granularity

Current design is closer to:

- degree/path/year-based student timetable views

instead of:

- per-actual-student personalized views

This is probably fine unless a real requirement says otherwise.

### Attendance-group correction UX

Current import pipeline derives attendance groups automatically.

Unclear whether real users will need:

- lightweight correction only
- or full manual editing of derived attendance groups

### Missing resource constraints

Need to validate with real faculty/admin workflows whether we actually need:

- lecturer unavailability
- room blackout periods
- session timing locks/preferences

These should be added based on real operational need, not speculation.

## Immediate next-step checklist

- [x] retire clearly dead legacy bridge endpoints
- [x] restore/compat-fix missing readiness helper used by tests/journey code
- [x] run focused backend tests around canonical snapshot journey
- [ ] expand canonical snapshot test coverage further
- [ ] inspect remaining hybrid behavior in generate/view/export
- [ ] decide next highest-value cleanup after tests
