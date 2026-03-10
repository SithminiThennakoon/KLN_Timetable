# Azure VM + Cloudflare Pages Deployment

Target shape:

- backend: Azure Linux VM
- frontend: Cloudflare Pages
- database: SQLite on the VM

## Backend on Azure VM

Suggested runtime:

- Ubuntu LTS VM
- Python 3.11+
- reverse proxy with Nginx or Caddy
- systemd service for the FastAPI app
- service template: `deploy/azure/kln-timetable.service`
- proxy template: `deploy/azure/nginx.kln-timetable.conf`

Required backend environment:

```env
APP_ENV=production
DATABASE_URL=sqlite:////var/lib/kln-timetable/app.db
CORS_ALLOWED_ORIGINS=https://your-project.pages.dev,https://timetable.example.com
RESET_DB=false
```

Recommended startup command:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Backend env example in repo:

- `backend/.env.example`

Notes:

- keep one backend process when using SQLite
- create and own the database directory before first boot
- use `/health` for VM and reverse proxy checks

## Frontend on Cloudflare Pages

Build settings:

- framework preset: `Vite`
- build command: `npm run build`
- output directory: `dist`

Required frontend environment:

```env
VITE_API_BASE_URL=https://api.example.com/api
```

Frontend env example in repo:

- `frontend/.env.production.example`

Notes:

- configure your backend public hostname first
- Cloudflare Pages should serve the SPA fallback from `frontend/public/_redirects`

## VM setup checklist

1. Clone the repo to `/opt/kln-timetable`.
2. Create the Python virtualenv and install `backend/requirements.txt`.
3. Copy `backend/.env.example` to `backend/.env` and set the production values.
4. Create `/var/lib/kln-timetable` and grant write access to the service user.
5. Install `deploy/azure/kln-timetable.service` into systemd and enable it.
6. Install `deploy/azure/nginx.kln-timetable.conf` into Nginx and set the real API hostname.
7. Add HTTPS with Certbot or Cloudflare origin certificates.

## Validation Checklist

- backend responds on `GET /health`
- frontend can call `GET /api/v2/dataset`
- generation works against the SQLite-backed deployment DB
- CORS allows the production frontend origin and blocks unknown origins
