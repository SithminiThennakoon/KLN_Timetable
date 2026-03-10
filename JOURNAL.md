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

## 2026-03-07T01:35:00+05:30

- Added backend and frontend automated coverage for the active v2 export flows, including local PDF/XLSX/PNG branching and backend CSV/XLS payload checks
- Removed inactive legacy frontend pages, styles, services, and alternate entry files, keeping only the v2 studio flow and its minimal API client
- Removed inactive legacy backend routes, schemas, models, old solver code, auth/security remnants, and the old timeslot startup seeding path
- Updated README files so the repository documentation now matches the active v2 timetable product and current verification commands

## 2026-03-10T19:45:00+05:30

- Overhauled the Timetable Views page (ViewStudio.jsx) with a completely new UI: replaced the single-day calendar lane layout with a full 5-day week grid showing all days simultaneously (Google Calendar style), with time axis on left, one column per day, and sessions as absolutely-positioned blocks per column
- Replaced the sparse agenda card list with a compact table-style agenda view showing time, module code, session name, room, lecturer, and student count as dense rows grouped by day with sticky day headers and colour-accent left borders
- Replaced the collapsible side drawer with a centred modal overlay that appears when any session is clicked in either view, showing all session fields (module, time/duration, room+location, lecturers, groups, degree paths, student count) in a clean two-column detail grid; modal closes on Escape or overlay click
- Reorganised the toolbar into two rows: Row 1 has the page title, Admin/Lecturer/Student mode toggles, and contextual filter dropdowns + Apply button; Row 2 has View (Calendar/Agenda), Density (Compact/Comfortable/Expanded), and Export (PDF/CSV/XLSX/PNG) controls
- Rewrote all related CSS in index.css: removed old calendar-stage, agenda-entry, detail-drawer, day-load-strip, view-layout-grid, and density-toolbar blocks; added week-cal-*, agenda-table-*, modal-*, and vs-toolbar-* rulesets; confirmed production build passes with zero errors

## 20:15

- Fixed the week calendar's unreadable lane-split layout: replaced buildDayPlacements (6-lane parallel algorithm) with groupOverlappingEntries, which renders one full-width card per time-slot group and tracks extras for a popover
- Added SlotPopover component: an absolutely-anchored dropdown listing all sessions in a slot group, each row clickable to open SessionModal, closes on Escape or outside-click
- Rewrote WeekCalendar render loop to use groupOverlappingEntries; cards span the full day column with an amber +N badge and amber left-border when a group has extras; clicking a lone session opens the modal directly, clicking a stacked group opens the popover first
- Updated PNG export path to use groupOverlappingEntries instead of the old buildDayPlacements
- Added new CSS rules to index.css: .wce-top-line (flex row for code + badge), .wce-extras-badge (amber pill), .wce-type-room (type dot + room text), .wce-type-dot.is-lecture / .is-lab (coloured 5 px circle), .week-cal-entry.has-extras (amber left border), and the full .slot-popover / .slot-popover-header / .slot-popover-close / .slot-popover-row / .spr-* family
- Removed now-unused .wce-lecturer rule; updated day column minmax from 0 to 160px so columns remain readable at any density
- Production build passes with zero errors

## 2026-03-10T21:10:00+05:30

- Replaced 5-column WeekCalendar with a single-day DayCalendar: one full-width column for the selected day, making session cards large and readable instead of 5 tiny ~160px-wide strips
- Added DayPicker tab bar (Mon/Tue/Wed/Thu/Fri) between the toolbar and the calendar card; each tab shows a session-count badge and highlights the active day; auto-selects the first day with entries when data loads
- DayCalendar uses the same groupOverlappingEntries + SlotPopover logic; cards now have left/right margin of 6px (was 3px); tall cards (≥72px) show the time range as a third line
- exportDay state removed; PDF/PNG exports now use selectedDay directly, so the export always reflects the currently viewed day
- Removed now-unused week-cal-header, week-cal-header-day, week-cal-day-name, week-cal-day-meta CSS; added .day-picker, .day-picker-btn, .dp-day-name, .dp-count, .wce-time rules; updated responsive media query
- Production build passes with zero errors

