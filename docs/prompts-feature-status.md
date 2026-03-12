# Prompts Feature Status

This maps the major product features described in `prompts.md` to the current codebase state.

Status meanings:
- `implemented`: present and broadly working in the current app
- `partial`: exists, but incomplete, inconsistent, or only lives in the old architecture
- `missing`: not meaningfully implemented yet

| Feature from `prompts.md` | Status | Where it lives now | Notes |
| --- | --- | --- | --- |
| Manual setup wizard for timetable inputs | `partial` | `frontend/src/pages/SetupStudio.jsx`, old `v2_*` dataset APIs | The wizard exists, but it still mainly writes to the old flat dataset model. |
| CSV-first import and review flow | `partial` | `csv_import_analysis.py`, `SetupStudio.jsx`, `/api/v2/imports/*` | Analysis, preview, and normalized materialization exist. The manual wizard is not yet fully built on top of the normalized snapshot. |
| Canonical student-level import persistence | `partial` | `backend/app/models/imports.py`, `academic.py`, `solver.py`, `import_materialization.py` | New normalized model layers exist, but generation/views still mostly depend on `v2_*`. |
| Shared teaching session linked to multiple modules | `partial` | `SnapshotSharedSession` model | The new model supports it, but generation and UI do not fully use it yet. |
| Clash detection based on actual student membership | `partial` | new normalized import layer, old generator partially approximates it | The target architecture supports this, but the active generation/view path is still mixed with old path-based assumptions. |
| Hard vs soft constraints split | `implemented` | generator and UI | The app already distinguishes soft constraints from mandatory constraints. |
| Hard room capacity and compatibility constraints | `partial` | old generator | Basic room/type handling exists, but room year restriction and some special room rules are not robustly enforced end to end. |
| No room overlap | `implemented` | old generator | Present in current generation logic. |
| No lecturer overlap | `implemented` | old generator | Present in current generation logic. |
| No student overlap | `partial` | old generator | Implemented through old student-group logic, not yet through the final student-membership model. |
| Working hours and lunch break | `implemented` | old generator | Present in current generation logic. |
| Multiple weekly sessions spread across days | `implemented` | soft constraints | Present as a soft constraint. |
| Extra nice-to-have preferences | `implemented` | generator + UI | Morning theory, afternoon practicals, Friday avoidance, etc. already exist as soft constraints. |
| Split one oversized session into multiple time-separated groups | `partial` | old session model + generator | There is support via `max_students_per_group`, but it needs verification against the final snapshot-based model. |
| Same-time parallel delivery across multiple rooms/lecturers | `partial` | old session model + generator | There is support via `allow_parallel_rooms`, but it is not yet moved into the new snapshot-first architecture. |
| Generate all possible timetables when feasible | `partial` | old generator | The app enumerates up to limits and reports truncation, but the exact `prompts.md` behavior is not fully aligned. |
| Stop when search space is too large | `implemented` | old generator | Current generation exposes caps/time limits and reports truncation. |
| Force user to add soft constraints when too many solutions remain | `partial` | generator response + UI | Combination suggestions exist, but the exact forcing flow from the spec is not fully enforced. |
| Default selected timetable | `implemented` | old generator + solution selection APIs | Present today. |
| Admin view | `implemented` | `ViewStudio`, `/api/v2/views` | Exists, but still derives from old solution serialization. |
| Lecturer view | `partial` | `ViewStudio`, `/api/v2/views` | Exists, but filtering is currently name-based, which is unsafe. |
| Student view | `partial` | `ViewStudio`, `/api/v2/views` | Exists, but current filtering is not robust enough for student-level truth and general-path cases. |
| Export views to CSV | `implemented` | `/api/v2/exports` | CSV export exists. |
| Export views to PDF / XLS / PNG | `missing` | not present | Only CSV export is currently implemented. |
| Seeder / demo data | `implemented` | `/api/v2/dataset/demo` | Exists in old flat dataset flow. |
| Counts derived primarily from enrollment CSV | `partial` | normalized import layer | The new import path derives counts, but the main UI/generator path is not fully using it yet. |
| Manual wizard only fills non-CSV solver metadata | `missing` | target only | This is the intended architecture, but not the current behavior. |
| Separate post-generation verification phase | `missing` | target only | No real external verification modules exist yet. |
| Three independent verifiers in different languages | `missing` | target only | Not started. |

## Current Bottom Line

The codebase has two overlapping systems:

1. The old `v2_*` path
   - manual setup
   - generation
   - views
   - default solution selection

2. The new normalized path
   - CSV analysis
   - import materialization
   - canonical import/academic/attendance models
   - early snapshot-backed manual completion model

The main project risk is not that features are absent across the board.
The main risk is that many important features exist only in the old path, while the new data model is being built separately and is not yet the active end-to-end system.

## Best Next Move

The next most valuable implementation step is:

- make the setup wizard load from and save to the normalized import snapshot workspace

That is the point where the new architecture stops being just a backend sidecar and becomes the real product path.
