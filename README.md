# KLN Timetable System

Snapshot-first timetable builder and generator for the Faculty of Science, University of Kelaniya.

The active product flow is:

1. `Setup`
2. `Generate`
3. `Views`

The system imports student enrolment data first, materializes an academic snapshot, enriches that snapshot with support CSVs or small local fixes, generates timetable solutions, verifies the selected solution, and exports audience-specific views.

## What The Product Does

- imports student enrolments from CSV
- reviews and materializes an academic snapshot
- imports support CSVs for rooms, lecturers, modules, sessions, and session-lecturer links
- repairs small missing data directly inside Setup
- generates hard-constraint-valid timetable solutions
- applies optional nice-to-have preferences during generation
- verifies the selected solution with Python, Rust, and Elixir verifiers
- shows admin, lecturer, and student timetable views
- exports timetable views as `PDF`, `CSV`, `XLSX`, and `PNG`

## Active Workflow

### 1. Setup

- import `student_enrollments.csv`
- analyze review buckets
- review the projected import
- click `Use This Import` to materialize the snapshot
- import any support CSVs the source system can provide
- repair only the remaining local issues that the readiness list identifies

### 2. Generate

- generate timetable solutions from the active snapshot
- add optional preferences only when the solution space is too broad or when the faculty wants a narrower result
- choose a default solution
- run verification against the normalized snapshot

### 3. Views

- inspect the default timetable in `admin`, `lecturer`, or `student` mode
- export the current view using the format appropriate for the audience

## Quick Start

### Backend

Requirements:

- Python `3.11+`

Environment:

```env
APP_ENV=development
DATABASE_URL=sqlite:///./backend/data/kln_timetable.db
CORS_ALLOWED_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
RESET_DB=false
```

Run:

```powershell
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

### Frontend

Requirements:

- Node.js `18+`

Run:

```powershell
cd frontend
npm install
npm run dev
```

Frontend default URL:

- `http://localhost:5173`

Backend default URL:

- `http://127.0.0.1:8000`

## Important Repo Paths

- active API: `backend/app/routes/timetable_v2.py`
- backend entrypoint: `backend/app/main.py`
- setup page: `frontend/src/pages/SetupStudio.jsx`
- generate page: `frontend/src/pages/GenerateStudio.jsx`
- views page: `frontend/src/pages/ViewStudio.jsx`
- realistic import fixtures: `backend/testdata/import_fixtures/production_like/`
- fixture generator: `backend/scripts/generate_import_fixture_pack.py`
- deployment assets: `deploy/azure/`

## Documentation

The handover manuals are authored in Typst under `docs/typst/`.

Deliverables:

- `User Manual.pdf`
- `Technical Documentation.pdf`
- `ABC Handover.pdf`

Source files:

- `docs/typst/user-manual.typ`
- `docs/typst/technical-documentation.typ`
- `docs/typst/abc-handover.typ`
- `docs/typst/README.md`

## Deployment Shape

Recommended low-cost production shape:

- backend on a single Linux VM
- frontend on static hosting
- SQLite on the same VM as the backend
- reverse proxy using the templates in `deploy/azure/`

The checked-in systemd and Nginx templates assume:

- backend working directory `/opt/kln-timetable`
- service user `kln`
- `uvicorn app.main:app --host 127.0.0.1 --port 8000`

## Verification Notes

- Python verification is available through the active API
- Rust and Elixir verifiers exist in the repo and are part of the broader verification suite
- a timetable is only fully trusted when the required verifiers complete successfully

Related docs:

- `docs/verification-contract.md`
- `docs/prompts-feature-status.md`

## Known Practical Limits

- PDF and PNG exports are generated client-side
- `CSV` and `XLSX` are data-first exports
- visual export scope differs by audience:
  - `lecturer` and `student`: whole-week visual exports
  - `admin`: whole-week or daily-bundle visual exports
- large enrolment imports can take noticeable time during materialization
