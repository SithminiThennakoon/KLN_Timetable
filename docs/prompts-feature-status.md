# Prompts Feature Status

This maps the major product features described in `prompts.md` to the current codebase state.

Status meanings:
- `implemented`: present and broadly working in the current app
- `partial`: exists, but incomplete, inconsistent, or only lives in the old architecture
- `missing`: not meaningfully implemented yet

| Feature from `prompts.md` | Status | Where it lives now | Notes |
| --- | --- | --- | --- |
| Manual setup wizard for timetable inputs | `partial` | `frontend/src/pages/SetupStudio.jsx`, snapshot APIs | The wizard now centers on snapshot-backed non-CSV completion, but some legacy/manual-model code still exists in the component. |
| CSV-first import and review flow | `implemented` | `csv_import_analysis.py`, `SetupStudio.jsx`, `/api/v2/imports/*` | CSV import, review, normalized materialization, snapshot completion, and generation are now the active path. |
| Canonical student-level import persistence | `implemented` | `backend/app/models/imports.py`, `academic.py`, `solver.py`, `import_materialization.py` | The normalized import layers are now active in setup, generation, views, and verification. |
| Shared teaching session linked to multiple modules | `partial` | `SnapshotSharedSession` model | The new model supports it and snapshot generation consumes it, but the authoring UX around linked-module sessions still needs refinement. |
| Clash detection based on actual student membership | `implemented` | normalized import layer, snapshot generation, snapshot views, verification suite | Attendance groups are derived from student membership and the verification snapshot checks exact student overlaps. |
| Hard vs soft constraints split | `implemented` | generator and UI | The app already distinguishes soft constraints from mandatory constraints. |
| Hard room capacity and compatibility constraints | `implemented` | snapshot generation + verification suite | Capacity, room/lab capability, specific-room rules, and room year restrictions are enforced in generation and all three verifiers. |
| No room overlap | `implemented` | old generator | Present in current generation logic. |
| No lecturer overlap | `implemented` | old generator | Present in current generation logic. |
| No student overlap | `implemented` | snapshot generation + verification suite | Snapshot generation and all verifiers now check clashes against exact student membership. |
| Working hours and lunch break | `implemented` | old generator | Present in current generation logic. |
| Multiple weekly sessions spread across days | `implemented` | soft constraints | Present as a soft constraint. |
| Extra nice-to-have preferences | `implemented` | generator + UI | Morning theory, afternoon practicals, Friday avoidance, etc. already exist as soft constraints. |
| Split one oversized session into multiple time-separated groups | `partial` | snapshot session model + generator | There is support via `max_students_per_group`, but the manual UX for defining split-heavy delivery is still basic. |
| Same-time parallel delivery across multiple rooms/lecturers | `partial` | snapshot session model + generator | There is support via `allow_parallel_rooms`, but the completion UX and validation around it still need polishing. |
| Generate all possible timetables when feasible | `partial` | old generator | The app enumerates up to limits and reports truncation, but the exact `prompts.md` behavior is not fully aligned. |
| Stop when search space is too large | `implemented` | old generator | Current generation exposes caps/time limits and reports truncation. |
| Force user to add soft constraints when too many solutions remain | `partial` | generator response + UI | Combination suggestions exist, but the exact forcing flow from the spec is not fully enforced. |
| Default selected timetable | `implemented` | old generator + solution selection APIs | Present today. |
| Admin view | `implemented` | `ViewStudio`, `/api/v2/views` | Snapshot-aware admin view is active. |
| Lecturer view | `implemented` | `ViewStudio`, `/api/v2/views` | Snapshot-aware lecturer filtering now works on stable IDs. |
| Student view | `implemented` | `ViewStudio`, `/api/v2/views` | Snapshot-aware student filtering now handles year-specific general selections correctly. |
| Export views to CSV | `implemented` | `/api/v2/exports` | CSV export exists. |
| Export views to PDF / XLS / PNG | `implemented` | `ViewStudio.jsx` local export utilities | PDF/XLSX/PNG exports are implemented in the frontend. |
| Seeder / demo data | `implemented` | `/api/v2/dataset/demo` | Exists in old flat dataset flow. |
| Counts derived primarily from enrollment CSV | `implemented` | normalized import layer, snapshot workspace | Snapshot counts now derive from the imported enrollment data. |
| Manual wizard only fills non-CSV solver metadata | `partial` | snapshot completion flow | This is now the active direction, but some legacy/manual artifacts remain in Setup Studio. |
| Separate post-generation verification phase | `implemented` | verification snapshot export, verification suite, GenerateStudio verification panel | Verification snapshot export exists, the verification suite now runs Python/Rust/Elixir, and the Generate page surfaces the result. |
| Three independent verifiers in different languages | `implemented` | Python verifier, Rust verifier, Elixir verifier | All three verifier implementations now exist and consume the same verification snapshot contract. |

## Current Bottom Line

The codebase still has two overlapping systems:

1. The old `v2_*` path
   - manual setup
   - generation
   - views
   - default solution selection

2. The new normalized path
   - CSV analysis
   - import materialization
   - canonical import/academic/attendance models
   - snapshot-backed manual completion
   - snapshot-native generation
   - snapshot-aware views
   - three-verifier post-generation validation

The main project risk is no longer that the normalized model is inactive.
The main risk is that some setup/editor affordances and a few remaining rules are still split between the legacy assumptions and the newer snapshot-first model.

## Best Next Move

The next most valuable implementation step is:

- finish removing remaining legacy assumptions from Setup Studio and tighten the remaining room/session rule coverage around the snapshot model

That is the point where the product stops feeling like a bridge and starts behaving like one coherent snapshot-first system.
