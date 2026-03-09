# Frontend

Vite + React frontend for the active v2 timetable studio flow.

## Active Pages

- `Setup`
- `Generate`
- `Views`

The old login/dashboard/CRUD frontend has been removed from the active codebase.

## Commands

```bash
npm install
npm run dev
npm test
npm run build
```

## Notes

- `PDF`, `PNG`, and `XLSX` exports are generated client-side.
- Heavy export libraries are lazy-loaded so they do not inflate the initial app bundle.
- The frontend talks to the backend through `/api/v2`.
