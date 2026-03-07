# KLN Timetable System

Web app for building and generating Faculty of Science timetables for the University of Kelaniya.

The active product is the rebuilt `v2` timetable flow. Legacy auth, dashboard, and CRUD codepaths have been removed from the running app and the repo now centers on:

- guided manual dataset entry
- full timetable generation with hard constraints
- optional nice-to-have constraints
- default timetable selection
- admin, lecturer, and student timetable views
- PDF, CSV, XLSX, and PNG exports

## Active Workflow

1. Open `Setup` and enter the timetable dataset manually.
2. Define degrees, paths, lecturers, rooms, student cohorts, modules, and sessions.
3. Generate timetables in `Generate`.
4. Review the number of valid solutions and pick a default timetable.
5. Open `Views` to inspect the default timetable in admin, lecturer, or student mode.
6. Export the current view if needed.

## Product Rules

- No authentication or login flow.
- Weekly timetable only.
- Working hours are `08:00` to `18:00`, Monday to Friday.
- Lunch break is `12:00` to `13:00` with no sessions.
- Session durations must be multiples of `30` minutes.
- Hard constraints include:
  - room capacity
  - room/session compatibility
  - specific-room restrictions
  - room clash prevention
  - lecturer clash prevention
  - student-group clash prevention
- Nice-to-have constraints currently include:
  - spreading repeated weekly sessions across different days

## Current Implementation

### Frontend

Active pages:

- [frontend/src/pages/SetupStudio.jsx](/home/sasindu/Documents/Projects/UOK Sithu Timetable/KLN_Timetable/frontend/src/pages/SetupStudio.jsx)
- [frontend/src/pages/GenerateStudio.jsx](/home/sasindu/Documents/Projects/UOK Sithu Timetable/KLN_Timetable/frontend/src/pages/GenerateStudio.jsx)
- [frontend/src/pages/ViewStudio.jsx](/home/sasindu/Documents/Projects/UOK Sithu Timetable/KLN_Timetable/frontend/src/pages/ViewStudio.jsx)

Active service layer:

- [frontend/src/services/timetableStudioService.js](/home/sasindu/Documents/Projects/UOK Sithu Timetable/KLN_Timetable/frontend/src/services/timetableStudioService.js)
- [frontend/src/services/apiClient.js](/home/sasindu/Documents/Projects/UOK Sithu Timetable/KLN_Timetable/frontend/src/services/apiClient.js)

### Backend

Active backend entrypoints:

- [backend/app/main.py](/home/sasindu/Documents/Projects/UOK Sithu Timetable/KLN_Timetable/backend/app/main.py)
- [backend/app/routes/timetable_v2.py](/home/sasindu/Documents/Projects/UOK Sithu Timetable/KLN_Timetable/backend/app/routes/timetable_v2.py)
- [backend/app/services/timetable_v2.py](/home/sasindu/Documents/Projects/UOK Sithu Timetable/KLN_Timetable/backend/app/services/timetable_v2.py)
- [backend/app/models/v2.py](/home/sasindu/Documents/Projects/UOK Sithu Timetable/KLN_Timetable/backend/app/models/v2.py)
- [backend/app/schemas/v2.py](/home/sasindu/Documents/Projects/UOK Sithu Timetable/KLN_Timetable/backend/app/schemas/v2.py)

## API Surface

Mounted API prefix: `/api/v2`

- `GET /dataset`
- `GET /dataset/full`
- `POST /dataset`
- `POST /dataset/demo`
- `GET /lookups`
- `POST /generate`
- `GET /generate/latest`
- `POST /solutions/default`
- `GET /views`
- `GET /exports`

## Setup

### Backend

Requirements:

- Python 3.11+ is recommended
- MySQL is the intended database

Environment:

```env
DATABASE_URL=mysql+pymysql://user:password@localhost:3306/kln_timetable
RESET_DB=false
```

Run:

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

Backend runs on `http://localhost:8000` by default.

### Frontend

Requirements:

- Node.js 18+

Run:

```bash
cd frontend
npm install
npm run dev
```

Frontend runs through Vite.

## Desktop Launcher

A repo-local desktop launcher GUI is available at [launcher_gui.py](/home/sasindu/Documents/Projects/UOK Sithu Timetable/KLN_Timetable/launcher_gui.py).

Run it from the repo root:

```bash
.venv/bin/python launcher_gui.py
```

For a non-technical Linux user, use one of these instead:

- double-click [Launch KLN Timetable.sh](/home/sasindu/Documents/Projects/UOK Sithu Timetable/KLN_Timetable/Launch%20KLN%20Timetable.sh)
- or place [kln-timetable-launcher.desktop](/home/sasindu/Documents/Projects/UOK Sithu Timetable/KLN_Timetable/kln-timetable-launcher.desktop) on the desktop/app launcher and run it like a normal Linux app

The launcher can:

- start the repo-local MariaDB, backend, and frontend together
- stop them cleanly
- restart the full stack
- show separate backend and frontend log panes
- copy backend and frontend logs independently

Cleanup behavior is safe by default:

- stops repo-local launcher-managed services
- clears stale MariaDB pid/socket state when no live DB process owns it
- reports external port conflicts instead of killing unrelated processes

## Verification

Backend:

```bash
python -m compileall backend/app
.venv/bin/python -m unittest backend.tests.test_timetable_v2
```

Frontend:

```bash
cd frontend
npm test
npm run build
```

## Test Coverage

Backend regression coverage currently includes:

- infeasibility diagnostics
- internal cohort splitting
- parallel-room scheduling success and failure
- truncation behavior
- default solution switching
- degree/path student filtering
- soft-constraint fallback behavior
- CSV and XLS export payload shaping

Frontend coverage currently includes:

- setup wizard hydration, validation, and save shaping
- generation request and threshold messaging
- student view filtering
- export path selection and local export payload shaping

## Known Limits

- Export tests validate branching and payload shaping, not binary document fidelity.
- PDF and PNG exports are generated client-side, so document rendering depends on browser capabilities.
- XLS backend export still exists only as a basic tabular payload for API completeness; the active UI downloads real `.xlsx` files client-side.
- The solver supports internal splitting and same-time parallel-room sessions, but very specialized teaching patterns may still need future extension.

## Branch

Current development branch for the rebuild:

- `feature/v2-timetable-rebuild`
