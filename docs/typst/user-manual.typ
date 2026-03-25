#import "theme.typ": *

#cover(
  "User Manual",
  "End-user guide for operating the system from setup through timetable export.",
  "End users",
)

= Contents

#outline(title: none)

= Purpose

This manual explains how to use the active timetable product without touching the codebase. The live application is organized around three pages:

- `Setup`
- `Generate`
- `Views`

This document is intended for timetable administrators and routine operational users. It covers the workflow, required inputs, and recovery steps for common issues.

= System Overview

The system is snapshot-first. That means you do not build the timetable directly from scattered forms. Instead, you first create a snapshot of the academic structure from student enrolment data, then enrich that snapshot with the remaining teaching and room information.

#simple-flow((
  ("Import student enrolments", "Analyze the enrolment CSV and review ambiguous cases."),
  ("Materialize the snapshot", "Use the reviewed enrolment import to create the working academic snapshot."),
  ("Enrich the snapshot", "Import rooms, lecturers, modules, sessions, and session-lecturer links as needed."),
  ("Repair small gaps", "Add small missing local fixes only when the readiness list asks for them."),
  ("Generate and verify", "Produce timetable solutions, pick a default, and verify the selected solution."),
  ("Inspect and export", "Use the Views page to inspect admin, lecturer, or student timetables and export them."),
))

= Before You Start

== Files you may need

- `student_enrollments.csv`
- `rooms.csv`
- `lecturers.csv`
- `modules.csv`
- `sessions.csv`
- `session_lecturers.csv`

If you do not yet have real support CSVs, the `Utilities` area in `Setup` can download a realistic fixture pack for full import testing.

== What each file does

#kv-table((
  ([Student enrolments], [Creates the academic snapshot. This is the only CSV that defines which students take which modules.]),
  ([Rooms], [Adds room capacities, room types, locations, and year restrictions.]),
  ([Lecturers], [Adds staffing identities used by sessions.]),
  ([Modules], [Adds optional module metadata when enrolment-derived information is not enough.]),
  ([Sessions], [Defines the teachable sessions the generator will place.]),
  ([Session lecturers], [Links sessions to lecturers.]),
))

= Setup Page

== Step 1: Import student enrolments

On `Setup`, start with the `Student Enrolments` card.

Use this flow:

1. click `Import CSV`
2. choose `student_enrollments.csv`
3. click `Analyze Import`
4. inspect the `Needs Review` section
5. adjust any review-bucket overrides if needed
6. click `Review Import`
7. click `Use This Import`

Support CSV imports remain unavailable until the enrolment import has been materialized. Rooms, lecturers, and sessions are attached to a snapshot, so the enrolment import is always the first step.

== Review buckets

The review section lists enrolment patterns that require an explicit decision instead of an automatic assumption.

Typical cases include:

- a module code appearing with multiple CSV year values
- a CSV year not matching the nominal module year
- patterns that may indicate common teaching or other ambiguity

Use the default review action for the common path, then override only the buckets that need a different interpretation.

== Utilities

The `Utilities` panel is intentionally secondary.

Use it when you need:

- a realistic import fixture pack for testing
- to reopen an older snapshot on purpose
- to start a fresh setup session deliberately

If you are doing routine timetable work, stay in the main flow and avoid Utilities unless you need one of those specific actions.

== Step 2: Import support CSVs

Once the snapshot exists, import the support CSVs that your source system can provide. The app uses the readiness list to show what is still missing.

Suggested import order:

1. `Rooms`
2. `Lecturers`
3. `Modules` if needed
4. `Sessions`
5. `Session Lecturers`

== Step 3: Repair missing local issues

Use the repair area only for small local fixes. Examples:

- adding a room that is missing from the source extract
- adding a lecturer that is missing from the source extract
- fixing a small number of missing links for a shared session

Do not treat the app like a spreadsheet editor for large source-data problems. If the issue affects many rows, fix the CSV and reimport it.

= Generate Page

The `Generate` page is used only after Setup is ready.

== Generate timetable solutions

Click the generate action to build candidate timetables from the active snapshot.

The system enforces hard constraints such as:

- room capacity
- room compatibility
- specific-room restrictions
- lecturer clash prevention
- student clash prevention
- working hours
- lunch break protection

== Optional preferences

Optional preferences narrow the solution space, but they are not mandatory constraints.

Examples include:

- spread repeated sessions across different days
- keep theory sessions in the morning
- keep practicals in the afternoon
- avoid Friday sessions

Use these only when:

- the solution space is too broad
- the faculty wants a narrower style of timetable

== Verification

After selecting a generated timetable, run verification. The system currently surfaces:

- completed verifiers
- missing verifiers
- hard-constraint pass/fail status
- verifier-specific summaries

If required verifiers are missing, the timetable may still exist, but it is not fully trusted yet.

= Views Page

The `Views` page shows the selected default timetable.

Available modes:

- `Admin`
- `Lecturer`
- `Student`

== Layout controls

Users can switch between:

- `Calendar`
- `Agenda`

They can also choose the density mode and inspect a single weekday inside the calendar view.

== Export behavior

All view exports are audience-aware.

#kv-table((
  ([Lecturer / Student PDF and PNG], [Whole-week visual export intended for reading and sharing.]),
  ([Lecturer / Student CSV and XLSX], [Whole-week data export.]),
  ([Admin PDF and PNG], [Whole-week visual export or daily bundle, depending on the selected scope.]),
  ([Admin CSV and XLSX], [Whole-week data export.]),
))

= Common Problems

== “Support CSV import is not available yet”

Cause:
- the enrolment import has not been materialized yet

Fix:
- finish `Analyze Import`
- `Review Import`
- `Use This Import`

== “Generation is blocked”

Cause:
- Setup still has blocking readiness issues

Fix:
- check the readiness list
- import the missing CSVs or repair the listed local gaps

== “Timetable is not fully trusted yet”

Cause:
- one or more verifiers did not complete

Fix:
- run verification again
- check whether the missing verifier runtimes are installed on the host machine

= Operating Guidelines

- start from enrolment truth first
- use support CSVs before using local repair
- keep local repair for small, targeted issues
- use optional preferences only when needed
- verify the selected default timetable before distributing exports
