# Journal

## 2025-03-06T17:45:00+05:30

- Reorganized prompts.md into 9 logical sections without changing any words
- Moved faculty degree details (PS, BS, ENCM, AC, ECS, PE) from end to beginning for better context
- Fixed duplicate numbering in constraints section (items 5, 6, 7, 8 were duplicated)
- Grouped related content: faculty overview, degree structure, constraints, timetable format, session conflicts, generation process, views/export, data import
- Added AGENTS.md with project-specific instructions

## 2026-03-06T23:52:20+05:30

- Added a new v2 timetable domain model aligned to the prompts.md workflow with degrees, paths, student groups, modules, sessions, generation runs, solutions, and solution entries
- Implemented a new OR-Tools based v2 solver flow with hard constraints, selectable soft constraints, solution enumeration, truncation handling, default solution selection, and view/export payload generation
- Added new `/api/v2` backend routes for dataset loading, generation, default selection, lookups, views, and exports
- Replaced the active frontend flow with Setup, Generate, and Views studio pages that work against the new v2 APIs
- Verified backend compilation and frontend production build after installing frontend dependencies

## 23:58

- Created feature branch `feature/v2-timetable-rebuild` for the complete v2 timetable system rebuild
