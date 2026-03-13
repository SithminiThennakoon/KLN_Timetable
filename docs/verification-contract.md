# Verification Contract

The generated timetable is not trusted only because the solver returned a result.
It must be checked against the normalized verification snapshot.

## Current snapshot source

- `GET /api/v2/imports/{import_run_id}/verification-snapshot`
- `GET /api/v2/imports/{import_run_id}/verification`
- `GET /api/v2/imports/{import_run_id}/verification/python`

## Snapshot contents

The verification snapshot includes:

- selected timetable entries
- shared sessions
- attendance groups
- exact student membership per attendance group
- lecturers
- rooms
- selected soft constraints
- hard-constraint identifiers

## Verifier output contract

Each verifier should return JSON with this shape:

```json
{
  "verifier": "python",
  "hard_valid": true,
  "hard_violations": [],
  "soft_summary": [],
  "stats": {
    "entry_count": 0,
    "room_count": 0,
    "attendance_group_count": 0
  }
}
```

## Hard constraints to check

- room capacity compatibility
- room capability compatibility
- room year restriction
- specific room restrictions
- no room overlap
- no lecturer overlap
- no student overlap
- working hours only
- lunch break protection

## Current implementation status

- Python verifier: implemented and callable through the API
- Rust verifier: implemented and callable through the verification suite
- Elixir verifier: implemented and callable through the verification suite
