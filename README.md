# Tamil Event Discovery

Tamil Event Discovery is a public event discovery platform focused initially on Tamil Nadu. Milestone 2 adds event management, public search and filtering, and protected administration.

## Stack and architecture

- **Frontend:** React, TypeScript, Vite
- **Backend:** Python, FastAPI, SQLAlchemy 2.0, Pydantic
- **Database:** PostgreSQL with Docker; SQLite by default for no-Docker development
- **Migrations:** Alembic

Backend layers are separated into `app/models.py`, `app/schemas.py`, `app/services.py`, `app/api/`, and `app/db/`. The frontend keeps API communication in `src/api.ts`, shared types in `src/types.ts`, reusable cards in `src/components.tsx`, public pages in `src/pages.tsx`, and administration in `src/admin.tsx`.

## Run without Docker

### Backend (PowerShell)

```powershell
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:SECRET_KEY="replace-this-with-a-long-random-secret"
$env:ADMIN_EMAIL="admin@example.com"
$env:ADMIN_PASSWORD="change-this-local-password"
alembic upgrade head
uvicorn app.main:app --reload
```

SQLite is used at `backend/event_discovery.db` by default. No PostgreSQL server is required for local development.

### Frontend (second terminal)

```powershell
cd frontend
npm install
npm run dev
```

Open <http://localhost:5173>. API docs are at <http://localhost:8000/docs>.

To use PostgreSQL locally, set `DATABASE_URL` to a `postgresql+psycopg://...` URL before running Alembic and Uvicorn.

## Run with Docker Compose

Copy `.env.example` to `.env`, replace all development secrets, then run:

```powershell
docker compose up --build
```

The website runs at <http://localhost:5173>, the API at <http://localhost:8000>, and PostgreSQL data is stored in the `postgres_data` volume.

## Database and seed data

```powershell
cd backend
alembic upgrade head
python -m app.seed
```

The migration creates normalized `events`, `categories`, `locations`, and `admin_users` tables with indexes and constraints. The seed command adds the initial Tamil Nadu categories and locations and creates the configured admin account if it does not exist. Never use the example admin password outside local development.

## API endpoints

### Public

- `GET /api/v1/events` — published events with pagination, search and filters
- `GET /api/v1/events/{slug}` — one published event
- `GET /api/v1/events/featured` — featured published events
- `GET /api/v1/events/upcoming` — upcoming published events
- `GET /api/v1/categories` — active categories
- `GET /api/v1/locations` — active Tamil Nadu locations
- `GET /api/v1/health` — API/database health

### Admin

Authenticate with `POST /api/v1/admin/login`, then send `Authorization: Bearer <access_token>`:

- `GET|POST /api/v1/admin/events`
- `GET|PUT|DELETE /api/v1/admin/events/{id}`
- `PATCH /api/v1/admin/events/{id}/publish`
- `PATCH /api/v1/admin/events/{id}/reject`
- `PATCH /api/v1/admin/events/{id}/feature`
- `GET|POST /api/v1/admin/categories`
- `PUT|DELETE /api/v1/admin/categories/{id}`

Draft, pending, rejected, cancelled, and expired events are never returned by public event endpoints.

## Tests and validation

```powershell
cd backend
pytest -q
python -m compileall -q app

cd ..\frontend
npm run build
```

## Environment

See [.env.example](./.env.example). Do not commit `.env` or production credentials. The frontend admin area is available at `/admin/login`; public browsing is available at `/` and `/events`.

## Known limitations and Milestone 3

The current frontend provides the public discovery flow and core admin event creation/actions. Rich admin editing, category management screens, production deployment hardening, and automated discovery/crawling remain follow-up work. Milestone 3 should add source ingestion, structured extraction, duplicate detection, verification evidence, and an admin review queue without automatically publishing unverified events.
