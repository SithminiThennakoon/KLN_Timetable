# Detailed Plan: KLN Timetable Generator

This expands `PLAN.md` with more detail, data flow, edge cases, and implementation notes.

## 1) Goals and Scope

- Generate a single faculty-wide timetable that avoids conflicts across all pathways, years, and departments.
- Support manual data entry via UI until admin provides bulk data format.
- Validate data completeness and logical consistency before generation.
- Allow manual timetable placement with conflict validation and re-solve around manual entries.
- Provide filtered timetable views by pathway+year, lecturer, and room.
- Fixed weekly schedule (repeats for 15 weeks).
- No auth for now; focus on functionality.

## 2) Core Domain Model (Detailed)

### 2.1 Department
Represents a faculty department (Physical Science, Biological Science, etc.).

Fields:
- id
- name
- code

### 2.2 Subject
Subjects that form pathways (Physics, Chemistry, Pure Math, Applied Math, etc.).

Fields:
- id
- name
- code
- department_id (FK)

### 2.3 Pathway
Fixed pathway per year (e.g., Year 2: Physics / Pure Math / Applied Math).

Fields:
- id
- name
- department_id (FK)
- year

### 2.4 PathwaySubject (M2M)
Links pathways to the three subjects they contain.

Fields:
- pathway_id (FK)
- subject_id (FK)

### 2.5 Module
Year-specific modules within a subject (module code includes year, but store year explicitly).

Fields:
- id
- code
- name
- subject_id (FK)
- year
- semester

### 2.6 Session (Atomic schedulable unit)
Represents a lecture or practical session requirement.

Fields:
- id
- module_id (FK)
- session_type (lecture | practical)
- duration_hours (1, 2, 3)
- frequency_per_week (integer)
- requires_lab_type (nullable)
- student_count (total enrolled)
- max_students_per_group (nullable; used for auto-splitting)
- concurrent_split (bool)

Notes:
- For different lecturers teaching different hours, create multiple sessions.
- For multi-hour sessions, solver must allocate consecutive slots.
- If max_students_per_group < student_count, the solver auto-creates groups.

### 2.7 SessionLecturer (M2M)
Links multiple lecturers to a session (no week ranges).

Fields:
- session_id (FK)
- lecturer_id (FK)

### 2.8 Lecturer
Fields:
- id
- name
- email
- max_hours_per_week

### 2.9 Room
Room with type and optional lab specialization.

Fields:
- id
- name
- capacity
- room_type (lecture_hall | laboratory)
- lab_type (nullable)
- location
- year_restriction (nullable)

Notes:
- A physics lab can be modeled with lab_type="physics_lab".
- If year_restriction is set, only sessions of that year can use it.

### 2.10 Timeslot
Fixed slot grid (Mon-Fri 08:00-18:00, 1-hour slots, 12:00-13:00 lunch).

Fields:
- id
- day
- start_time
- end_time
- is_lunch

### 2.11 TimetableEntry
Final scheduled output and manual overrides.

Fields:
- id
- version
- session_id
- room_id
- timeslot_id
- group_number
- is_manual

## 3) Data Integrity Rules

Mandatory before generation:
- At least 1 department
- At least 1 subject per department
- At least 1 pathway per department/year
- Each pathway linked to exactly 3 subjects
- Each module has >= 1 session
- Each session has >= 1 lecturer
- At least 1 room
- For each required lab_type, at least 1 matching room exists

Warnings (generation allowed but flagged):
- Lecturer max_hours_per_week exceeded by assigned sessions
- Room capacity insufficient for student_count
- Sessions that require splitting but no sufficient rooms for concurrency

## 4) Solver Design (CP-SAT)

### 4.1 Variables

Let:
- S = sessions (including auto-split groups)
- R = rooms
- T = timeslots (45 slots)

Decision variable:
- x[s, r, t] = 1 if session s assigned to room r at timeslot t

### 4.2 Constraints (Hard)

1. Each session scheduled exactly frequency_per_week times.
2. Multi-hour sessions occupy consecutive slots.
3. Lunch slot disallowed.
4. Only weekday slots allowed (predefined in timeslots).
5. Room cannot host more than one session per timeslot.
6. Lecturer cannot teach more than one session per timeslot.
7. Pathway+year students cannot attend more than one session per timeslot.
8. Room type and lab_type must match session requirement.
9. Room capacity must be >= group size.
10. Year-restricted rooms can only host sessions of that year.
11. concurrent_split=true groups must run at same timeslot (different rooms).
12. Manual entries are fixed and solver must respect them.

### 4.3 Objective (Soft)

- Minimize gaps per pathway+year (cluster sessions).
- Minimize gaps per lecturer.
- Spread sessions across weekdays.
- Maximize scheduled sessions if infeasible.

## 5) Manual Timetable Workflow

### 5.1 Drag-and-drop
- Admin can drag unscheduled sessions into the timetable grid.
- Real-time conflict highlighting.
- Manual entries marked is_manual=true.

### 5.2 Validation
- Validate only (returns conflicts but does not change).
- If conflicts exist, show list with reasons.

### 5.3 Resolve Around Manual
- Lock manual entries.
- Re-run solver for remaining sessions.
- If infeasible, return reasons and keep manual entries.

## 6) API Specification (Expanded)

Base: `/api`

### CRUD
- `/departments`
- `/subjects`
- `/pathways`
- `/modules`
- `/sessions`
- `/lecturers`
- `/rooms`

### Reference
- `/timeslots` (GET only, pre-populated)

### Generation
- `/timetable/generate` (POST)
- `/timetable/entries` (GET/POST/PUT/DELETE)
- `/timetable/validate` (POST)
- `/timetable/resolve` (POST)

### Diagnostics
- `/data-status` (GET)

## 7) Frontend (UI/UX)

### 7.1 Database Management
Tabs:
- Departments
- Subjects
- Pathways
- Modules
- Sessions
- Lecturers
- Rooms

Each tab:
- Table listing
- Add/Edit/Delete modal
- Inline validation (required fields, duplicate codes, etc.)

Data Status Banner:
- Shows missing prerequisites
- Updates live

### 7.2 Constraints
Toggle hard constraints (enable/disable)

### 7.3 Generate
- Generate button
- Solver status
- Scheduled vs unscheduled counts
- Conflict list

### 7.4 View
- Weekly grid (Mon-Fri 8am-6pm)
- Filters: pathway+year, lecturer, room
- Cell shows module code + session type + room
- Drag-and-drop manual placement

## 8) Data Flow

1. Admin enters data in database tabs.
2. Data status updates until generation is possible.
3. Admin generates timetable.
4. Timetable stored in timetable_entry table with version tag.
5. Admin views/filter timetable.
6. Admin manually adjusts sessions; conflicts reported.
7. Admin can request resolve-around-manual.

## 9) Implementation Sequence (Detailed)

1. Replace backend models + schemas.
2. Add migrations or table creation for new schema.
3. Create timeslot seeding script (45 slots).
4. Implement CRUD APIs for all entities.
5. Implement data-status endpoint.
6. Rewrite solver.
7. Implement generate endpoint.
8. Implement validate + resolve endpoints.
9. Replace frontend with new pages and services.
10. Implement drag-and-drop timetable UI.
11. Add filtering, conflict highlighting, details panel.
12. Polish + testing.

## 10) Risks and Open Issues

- Solver performance could be heavy for full faculty; may need incremental or heuristic scheduling.
- Data entry volume is high; bulk import will be needed later.
- Manual adjustments can create infeasible constraints; need robust conflict reporting.

## 11) Future Enhancements (Optional)

- CSV/Excel import/export.
- Lecturer availability constraints.
- Student preferences.
- Multi-campus rooms.
- Auth + role-based access.
- Export timetable to PDF.
