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

## 2026-03-10T22:00:00+05:30

- Admin calendar: replaced the single groupOverlappingEntries column (which collapsed ~90 sessions/day into 2 giant +44/+45 stacked blocks) with a multi-lane horizontally-scrollable grid
- Added buildLanePlacements: interval-scheduling algorithm that assigns each session to the first lane (column) it fits in with no time overlap; produces the minimum lane count needed (max concurrent sessions at any moment, typically 15–25 for the admin view)
- Added AdminDayCalendar component: renders laneCount columns each minmax(240px, 1fr) wide inside an overflow-x:auto wrapper; reuses week-cal-entry, wce-* and week-cal-hour-line CSS unchanged; each card shows module code + room + type dot + session name + time range depending on card height
- ViewStudio render: mode==="admin" && layoutMode==="calendar" renders AdminDayCalendar; lecturer/student modes keep DayCalendar (single column) unchanged
- Added .admin-cal-wrapper (overflow-x+y auto, max-height 72vh) and .admin-cal-lane-col (min-width 240px) CSS rules
- Cleared global AGENTS.md (~/.config/opencode/AGENTS.md) and local AGENTS.md (repo root) as requested
- Production build passes with zero errors

## 2026-03-10T22:30:00+05:30

- Added progressive card detail lines to both AdminDayCalendar and DayCalendar: cards ≥100px show a lecturer line (compact: "Dr. Silva +2") with a subtle top divider; cards ≥130px show a students line ("120 students · Y1S1, Y2S2 +1 more")
- Both new lines use compactLecturerNames and compactAudienceLabels helpers already in the file
- Added .wce-lecturer-line (0.68rem, weight 600, rgba white 0.7, border-top separator) and .wce-students-line (0.65rem, weight 500, rgba white 0.48) CSS rules
- Production build passes with zero errors

## 2026-03-10T23:10:00+05:30

- Improved AgendaView in ViewStudio.jsx: time cell now shows start–end range ("08:00" + "↳ 10:00") instead of start + duration; module code cell gains a colored 7px type-dot (blue=lecture, teal=lab) matching the calendar card tone; room cell becomes two-line (room name + room_location sub-line); lecturer cell gets a native title tooltip with all names for overflow cases; students cell becomes two-line (bold count + compact degree_path_labels below)
- Added .at-type-dot (7px circle, default #4a8bbf), .agenda-table-row.is-lab .at-type-dot (#3da8a8), .at-room-name, .at-room-loc, .at-groups CSS rules
- Updated .at-code to flex+gap to accommodate the new dot; .at-room to flex-column; .at-students to flex-column+right-align with .at-students strong and .at-groups sub-line; .at-time small to "↳ end-time" style
- Responsive 980px override updated to align-items:start for taller multi-line cells; at-room still shown in mobile layout, at-lecturer/at-students still hidden on narrow screens
- Production build passes with zero errors

## 2026-03-10T23:45:00+05:30

- Introduced dual-theme (dark/light) support across the entire frontend; default for new visitors is light mode
- Rewrote index.css `:root` block into `[data-theme="dark"]` and `[data-theme="light"]` blocks covering ~130 CSS custom properties (bg-page, card surfaces, ink scale, accent, header, calendar/agenda entries, modal, buttons, banners, overlays, badges); all ~1730 lines of rules now consume `var(--)` tokens instead of hard-coded hex/rgba values
- Rewrote App.css so all navbar colors reference `var(--)` tokens; added `.header-right` wrapper class for flex-row alignment of nav links + toggle button
- Added `src/hooks/useTheme.js`: reads/writes `localStorage` key `kln-theme`, syncs `data-theme` attribute on `<html>`, exposes `{ theme, toggle }`
- Edited `src/main.jsx`: synchronous IIFE sets `data-theme` before first paint to eliminate flash of wrong theme
- Updated `MainNavbar.jsx`: converted from arrow-expression to function body, imported `useTheme`, wrapped nav in `.header-right` div, added `<button className="theme-toggle">` with ☀/☾ icon and aria-label
- Light mode accent: deep navy `#1d4ed8`; light surfaces: page `#f0f4f8`, cards `#ffffff` with subtle shadows
- Production build passes with zero errors

## 2026-03-10T23:55:00+05:30

- Audited every CSS variable and hard-coded color value across both [data-theme] blocks and all rule declarations
- Fixed light-mode info banner: was copying dark theme's `#064e3b` dark-green background/`#6ee7b7` text (unreadable on white); replaced with `#ecfdf5` bg / `#065f46` text / `#10b981` bar — standard Tailwind emerald light style
- Fixed light-mode error banner: tightened to `#fef2f2` / `#7f1d1d` / `#ef4444` for correct light-surface contrast
- Added `--btn-danger-text` to both theme blocks (dark: `#ffffff`, light: `#7f1d1d`); removed the `[data-theme="dark"] .danger-btn { color:#ffffff }` override rule — now fully token-driven
- Added `--field-invalid-border`, `--field-invalid-shadow`, `--field-invalid-text` to both theme blocks; dark uses warm orange-red, light uses clean red (`#dc2626`); replaced three hard-coded color literals in `.field-invalid` and `.field-hint.invalid` rules with `var(--)`
- Fixed `--ink-300` duplicate in light block: was same value as `--ink-400` (`#94a3b8`); corrected to `#b8c5d3` so the ink hierarchy is visually distinct
- Production build passes with zero errors

