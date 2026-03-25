#import "theme.typ": *

#cover(
  "Technical Documentation",
  "Setup, deployment, verification, maintenance, and troubleshooting guide.",
  "Technical operations and support team",
)

= Contents

#outline(title: none)

= System Summary

The active product is a snapshot-first timetable system built around an import-backed workflow. The product no longer depends on the older manual-only data-entry model for normal operation.

Core application flow:

- `Setup`: import, review, materialize, enrich, repair
- `Generate`: produce candidate timetables and choose a default
- `Views`: inspect and export the selected default timetable

= Architecture

== Runtime shape

#kv-table((
  ([Frontend], [React + Vite single-page app under `frontend/`]),
  ([Backend], [FastAPI application under `backend/app/`]),
  ([Database], [SQLite by default, configured through `DATABASE_URL`]),
  ([API prefix], [`/api/v2`]),
  ([Verification], [Python route-backed verification plus Rust and Elixir verifier projects in the repo]),
))

The system is snapshot-first. Support CSVs do not create the core academic structure. Student enrolments create the snapshot, and the remaining imports enrich that snapshot.

== Key backend surfaces

- `backend/app/main.py`
- `backend/app/routes/timetable_v2.py`
- `backend/app/services/timetable_v2.py`

== Key frontend surfaces

- `frontend/src/pages/SetupStudio.jsx`
- `frontend/src/pages/GenerateStudio.jsx`
- `frontend/src/pages/ViewStudio.jsx`

== Architecture diagram

#simple-flow((
  ("Frontend", "React + Vite application serving Setup, Generate, and Views."),
  ("FastAPI backend", "Receives imports, builds snapshots, runs generation, exposes verification and view APIs."),
  ("Database", "Stores snapshots, imported support data, solutions, and verification results."),
  ("Verifier projects", "Rust and Elixir verifier projects supplement the Python-backed verification flow."),
))

= Environment Setup

== Backend prerequisites

- Python `3.11+`
- pip

Environment variables are defined in `backend/.env.example`.

#kv-table((
  ([APP_ENV], [Application environment name. Defaults to `development`.]),
  ([DATABASE_URL], [SQLite path or another SQLAlchemy-supported database URL.]),
  ([CORS_ALLOWED_ORIGINS], [Comma-separated frontend origins allowed to call the API.]),
  ([RESET_DB], [If true, drops and recreates the schema on startup. Never enable in production.]),
))

Backend startup:

```powershell
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

== Frontend prerequisites

- Node.js `18+`
- npm

Frontend startup:

```powershell
cd frontend
npm install
npm run dev
```

Default frontend environment:

```env
VITE_API_BASE_URL=/api
```

= Import and Snapshot Model

== Import templates

The backend exposes six import templates through `/api/v2/imports/templates`.

They cover:

- student enrolments
- rooms
- lecturers
- modules
- sessions
- session lecturers

Template definitions live in `backend/app/services/import_templates.py`.

== Fixture pack

The project also ships a realistic six-file fixture pack:

- `backend/testdata/import_fixtures/production_like/`

The fixture-pack generator is:

- `backend/scripts/generate_import_fixture_pack.py`

This pack is useful for:

- end-to-end import testing
- support debugging
- handover demonstrations

== Snapshot lifecycle

#simple-flow((
  ("Enrollment analysis", "The uploaded enrolment CSV is analyzed and review buckets are created."),
  ("Projection review", "The chosen review rules are projected into an interpreted import."),
  ("Materialization", "The projection is turned into an import snapshot with academic structure."),
  ("Snapshot enrichment", "Rooms, lecturers, modules, sessions, and session-lecturer links are imported into that snapshot."),
  ("Generation and verification", "The finished snapshot is used for solver runs and post-generation verification."),
))

= API Surface

The active API router is `backend/app/routes/timetable_v2.py`.

Important route families:

#kv-table((
  ([Import templates and fixtures], [`/imports/templates`, `/import-fixtures`]),
  ([Enrollment analysis and materialization], [`/imports/enrollment-*`]),
  ([Snapshot enrichment], [`/imports/{import_run_id}/*-upload`]),
  ([Snapshot workspace and repair], [`/imports/{import_run_id}/workspace`, `/imports/{import_run_id}/snapshot/*`]),
  ([Generation], [`/generate`, `/generate/latest`, `/solutions/default`]),
  ([Verification], [`/imports/{import_run_id}/verification*`]),
  ([Views and exports], [`/views`, `/exports`]),
))

= Verification

The verification contract is documented in `docs/verification-contract.md`.

Repo layout:

- Python verifier: API-backed verification route
- Rust verifier: `verifiers/rust_snapshot_verifier/`
- Elixir verifier: `verifiers/elixir_snapshot_verifier/`

Verification result interpretation:

- a generated timetable is not fully trusted only because the solver found a result
- it becomes trustworthy when the required verifiers complete and the hard constraints pass

= Export Behavior

The export behavior is audience-aware.

#kv-table((
  ([Lecturer and student visual exports], [Whole-week PDF and PNG]),
  ([Lecturer and student data exports], [Whole-week CSV and XLSX]),
  ([Admin visual exports], [Whole-week or daily-bundle PDF and PNG]),
  ([Admin data exports], [Whole-week CSV and XLSX]),
))

Practical note:

- PDF, PNG, and XLSX rendering are still handled in the frontend
- the backend export route remains active for data-oriented export paths and filenames

= Deployment

Checked-in deployment assets:

- `deploy/azure/kln-timetable.service`
- `deploy/azure/nginx.kln-timetable.conf`

== Deployment diagram

#simple-flow((
  ("Static frontend", "Served to browser clients and calls the API using the configured base URL."),
  ("Nginx reverse proxy", "Proxies API traffic to the backend service."),
  ("FastAPI service", "Runs `uvicorn app.main:app` behind systemd."),
  ("SQLite database", "Stores the working data set on the same host."),
))

The checked-in service template assumes:

#kv-table((
  ([App directory], [/opt/kln-timetable]),
  ([Service user], [kln]),
  ([Env file], [/opt/kln-timetable/backend/.env]),
  ([Backend bind], [127.0.0.1:8000]),
  ([Process manager], [systemd]),
  ([Reverse proxy], [Nginx]),
))

Production baseline:

- keep a single backend instance when using SQLite
- place the SQLite database file on persistent storage
- set exact allowed CORS origins
- keep `RESET_DB=false`

= Troubleshooting

== Backend does not start

Check:

- Python virtual environment exists
- dependencies are installed
- `.env` values are valid
- the database path is writable

If startup is failing during schema creation:

- inspect `DATABASE_URL`
- check whether the selected database engine matches the SQLAlchemy models and constraints

== Frontend cannot call backend

Check:

- backend is reachable on `localhost:8000`
- frontend is using the correct API base URL
- `CORS_ALLOWED_ORIGINS` includes the frontend origin

== Support CSV imports are blocked in Setup

Cause:
- the enrolment import was not materialized yet

Fix:
- finish analysis, review, and `Use This Import`

== Verification is not fully trusted

Cause:
- one or more verifier runtimes are unavailable or failed

Check:

- Python verifier route output
- Rust toolchain availability
- Elixir/Erlang toolchain availability

== Export issues

Export implementation note:
- visual exports depend on browser-side rendering capabilities

If a user reports export failure:

- reproduce in the active browser
- check whether the issue is only for visual formats or also affects CSV/XLSX
- distinguish business-logic errors from client rendering failures

= Maintenance Notes

- keep the fixture pack in sync with the active import contract
- regenerate the fixture pack when session/import schemas change
- update `README.md` and the Typst manuals when the user flow changes materially
- keep verification contract changes reflected in both API docs and technical handover material
