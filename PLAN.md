

## Full Technical Plan: KLN Timetable Generator

### Guiding Principles
- No auth for now (open admin tool)
- Manual data entry UI first, bulk import later
- Fixed weekly schedule (the timetable repeats every week for 15 weeks)
- Lecturers recorded per session (no week ranges), solver ensures no conflicts for any linked lecturer
- Generate for entire faculty at once to avoid cross-pathway/cross-department collisions
- View filterable by pathway+year, lecturer, room

---

### Phase 1: Database Model Redesign

**Drop/replace** most existing models. New schema:

```
department
  id            PK
  name          VARCHAR(100)   e.g. "Physical Science"
  code          VARCHAR(10)    e.g. "PHY_SCI"

subject
  id            PK
  name          VARCHAR(100)   e.g. "Physics"
  code          VARCHAR(10)    e.g. "PHY"
  department_id FK -> department

pathway
  id            PK
  name          VARCHAR(200)   e.g. "Physics / Pure Math / Applied Math"
  department_id FK -> department
  year          INT            e.g. 1, 2, 3, 4

pathway_subject (many-to-many)
  pathway_id    FK -> pathway
  subject_id    FK -> subject

module
  id            PK
  code          VARCHAR(25)    e.g. "PHY2101" (year inferrable from code)
  name          VARCHAR(200)   e.g. "Thermodynamics & Solid State Physics"
  subject_id    FK -> subject
  year          INT
  semester      INT            (1 or 2)

session (the atomic schedulable unit)
  id            PK
  module_id     FK -> module
  session_type  ENUM('lecture', 'practical')
  duration_hours INT           e.g. 1, 2, 3
  frequency_per_week INT       e.g. 1, 2
  requires_lab_type VARCHAR(50) NULLABLE  e.g. "physics_lab", "computer_lab"
  student_count INT            (enrolled students for this session)
  max_students_per_group INT NULLABLE (for auto-splitting, e.g. 100)
  concurrent_split BOOL DEFAULT FALSE (split groups must run at same time?)

session_lecturer (many-to-many)
  session_id    FK -> session
  lecturer_id   FK -> lecturer

lecturer
  id            PK
  name          VARCHAR(255)
  email         VARCHAR(255)
  max_hours_per_week INT

room
  id            PK
  name          VARCHAR(100)   e.g. "Physics Lab 1", "LH-301"
  capacity      INT
  room_type     ENUM('lecture_hall', 'laboratory')
  lab_type      VARCHAR(50) NULLABLE  e.g. "physics_lab", "computer_lab"
  location      VARCHAR(100)
  year_restriction INT NULLABLE (e.g. 1 = only year 1 can use)

timeslot (pre-populated, 9 slots per day, 5 days = 45 total)
  id            PK
  day           ENUM('Monday','Tuesday','Wednesday','Thursday','Friday')
  start_time    TIME           e.g. 08:00
  end_time      TIME           e.g. 09:00
  is_lunch      BOOL           (12:00-13:00 = true)

timetable_entry (generated/manual output)
  id            PK
  version       VARCHAR(50)    (generation run identifier)
  session_id    FK -> session
  room_id       FK -> room
  timeslot_id   FK -> timeslot
  group_number  INT DEFAULT 1  (for split groups: group 1, group 2, etc.)
  is_manual     BOOL DEFAULT FALSE
```

**Key relationships:**
- `pathway` -> `pathway_subject` -> `subject` -> `module` -> `session` -> `session_lecturer` -> `lecturer`
- The solver works with **sessions** as the atomic unit
- Multi-hour sessions (e.g. 2h) occupy consecutive timeslots

---

### Phase 2: Backend API (FastAPI)

All endpoints under `/api/`. No auth middleware.

| Resource | Endpoints | Notes |
|----------|-----------|-------|
| `/api/departments` | GET, POST, PUT, DELETE | Simple CRUD |
| `/api/subjects` | GET, POST, PUT, DELETE | Filtered by department |
| `/api/pathways` | GET, POST, PUT, DELETE | Pre-defined, includes pathway_subject links |
| `/api/modules` | GET, POST, PUT, DELETE | Filtered by subject, year, semester |
| `/api/sessions` | GET, POST, PUT, DELETE | Linked to modules + lecturers |
| `/api/lecturers` | GET, POST, PUT, DELETE | Simple CRUD |
| `/api/rooms` | GET, POST, PUT, DELETE | Includes lab_type, year_restriction |
| `/api/timeslots` | GET only | Pre-populated, read-only |
| `/api/timetable/generate` | POST | Runs CP-SAT solver |
| `/api/timetable/validate` | POST | Validates manual entries |
| `/api/timetable/entries` | GET, POST, PUT, DELETE | CRUD for timetable entries |
| `/api/timetable/resolve` | POST | Try to re-solve around manual entries |
| `/api/data-status` | GET | Returns what data is missing/incomplete |

---

### Phase 3: CP-SAT Solver Redesign

The solver takes ALL sessions across the faculty and schedules them.

**Variables:** `x[session_id, room_id, timeslot_id, group_num] = BoolVar`

**Hard Constraints:**
1. Each session scheduled exactly `frequency_per_week` times
2. Multi-hour sessions occupy consecutive timeslots (no lunch break in middle)
3. No lunch slot (12-1pm) used
4. Only weekday 8am-6pm slots
5. One session per room per timeslot
6. No lecturer conflict: for each timeslot, each lecturer teaches at most 1 session
7. No pathway conflict: for each timeslot, students in a pathway have at most 1 session (considering shared subjects across pathways)
8. Room type matching: lectures -> lecture_halls, practicals -> matching lab_type
9. Room capacity >= group size
10. Year-restricted rooms enforced
11. Concurrent split groups scheduled at same timeslot (different rooms)
12. Manual entries (is_manual=true) are fixed, solver works around them

**Soft Constraints (optimization objectives):**
- Minimize gaps between sessions for each pathway+year
- Minimize gaps for each lecturer
- Spread sessions across the week (avoid all sessions on one day)
- Maximize scheduled sessions (if not all fit)

---

### Phase 4: Frontend (React + Vite) - Complete Rebuild

**Navigation:** Database | Constraints | Generate | View

#### 4a. Database Page (tabbed)
Tabs: **Departments | Subjects | Pathways | Modules | Sessions | Lecturers | Rooms**

Each tab:
- Table with all entries
- Add/Edit/Delete modals
- Session tab is the most complex: shows module, type, duration, frequency, linked lecturers, split config

**Data Status Banner:** At the top of the Database page, a persistent status bar:
- "Missing: 3 modules have no sessions defined"
- "Missing: 2 sessions have no lecturers assigned"  
- "Missing: No rooms of type 'physics_lab' exist"
- "Ready to generate!" (when all data is sufficient)

#### 4b. Constraints Page
- Hardcoded constraint list (the ones from the solver)
- Toggle enable/disable
- Not dynamically user-created (these are solver constraints, not arbitrary)

#### 4c. Generate Page
- "Generate Timetable" button
- Shows solver status: running, optimal, feasible, infeasible
- Shows stats: total sessions scheduled, unscheduled sessions, conflicts
- Error details if infeasible

#### 4d. View Page
- **Default view:** Weekly grid (Mon-Fri, 8am-6pm)
- **Filters:** Pathway + Year, Lecturer, Room
- Timetable cells show: Module code, Room, Session type
- Click cell for full details
- **Drag-and-drop** for manual entry: admin drags sessions from an unscheduled list onto the grid
- Conflict highlighting in real-time (red borders, tooltip explaining conflict)
- "Validate" button: checks all manual entries
- "Re-solve around manual entries" button: locks manual entries and re-runs solver for the rest

---

### Phase 5: Data Validation System

The `/api/data-status` endpoint checks:

| Check | Status |
|-------|--------|
| At least 1 department exists | Required |
| At least 1 subject per department | Required |
| At least 1 pathway defined | Required |
| All pathways have 3 subjects linked | Required |
| At least 1 module per subject per year/semester | Required |
| All modules have at least 1 session | Required |
| All sessions have at least 1 lecturer | Required |
| At least 1 room exists | Required |
| For each session requiring a lab type, a matching room exists | Required |
| Room capacity sufficient for session student counts | Warning |
| Lecturer max_hours not exceeded by total session hours | Warning |

---

### Implementation Order

| Step | What | Effort |
|------|------|--------|
| **1** | New database models + migrations (drop old tables) | Backend |
| **2** | Pre-populate timeslots (45 slots) | Backend |
| **3** | CRUD APIs for all entities | Backend |
| **4** | Data validation endpoint | Backend |
| **5** | Frontend: Database page with all tabs + data status banner | Frontend |
| **6** | CP-SAT solver rewrite with all constraints | Backend |
| **7** | Generate API + frontend generate page | Both |
| **8** | View page: weekly grid with filters | Frontend |
| **9** | View page: drag-and-drop manual entry | Frontend |
| **10** | Validate + resolve-around-manual APIs | Backend |
| **11** | Polish, edge cases, testing | Both |

---

### What Gets Deleted

- All current models except the DB connection setup (`core/database.py`, `core/config.py`)
- All current routes (replaced entirely)
- All current schemas (replaced entirely)
- All current frontend pages (replaced entirely)
- `AdminLogin`, `StudentLogin` dummy models
- All current frontend services (replaced)
- Auth routes + security module (not needed for now)

### What Gets Kept

- `backend/app/core/database.py` (engine, SessionLocal, Base, get_db)
- `backend/app/core/config.py` (settings)
- `backend/main.py` (uvicorn entry point)
- `backend/app/main.py` (FastAPI app factory - rewritten but same structure)
- `frontend/vite.config.js`
- `frontend/package.json` (will add dependencies)
- `.env` files
- `run-all.ps1`

---

Does this plan look right to you? Anything you want to change, add, or remove before I start implementing?