# Tamil Event Discovery

Tamil Event Discovery is a public event discovery and administration platform focusing on Tamil Nadu events across cultural festivals, technology conferences, arts, literature, workshops, and business expos.

Milestone 2.1 stabilizes the architecture, aligns frontend and backend schemas, provides comprehensive testing across React and FastAPI, enforces strict PostgreSQL migrations, and establishes CI/CD and production security readiness.

---

## Architecture Overview

The system follows a clean modular separation across the backend, frontend, and persistence layers:

```
tamil-event-discovery/
├── backend/
│   ├── alembic.ini                  # Alembic migration configuration
│   ├── app/
│   │   ├── api/
│   │   │   ├── admin.py             # Authenticated administration routes
│   │   │   ├── health.py            # System and database readiness probes
│   │   │   └── public.py            # Public event search and discovery routes
│   │   ├── core/
│   │   │   ├── config.py            # Pydantic Settings with production validation
│   │   │   └── security.py          # Password hashing and JWT generation/validation
│   │   ├── db/
│   │   │   ├── base.py              # Declarative Base
│   │   │   └── session.py           # Engine and DB session dependency
│   │   ├── models/
│   │   │   └── models.py            # SQLAlchemy 2.0 ORM models (Event, Category, Location, AdminUser)
│   │   ├── schemas.py               # Pydantic v2 validation models
│   │   ├── services.py              # Business logic, query filters, and status transitions
│   │   └── main.py                  # FastAPI application with lifespan management
│   ├── migrations/                  # Alembic migration scripts (0001 -> 0006)
│   ├── seed.py                      # Idempotent seed data (categories, locations, admin)
│   └── tests/                       # Comprehensive pytest suite (Unit, API, Migrations)
├── frontend/
│   ├── src/
│   │   ├── __tests__/               # Vitest component & API test suites
│   │   ├── admin.tsx                # Admin dashboard, event form, and category manager
│   │   ├── api.ts                   # Fetch client with robust header merging & auth handling
│   │   ├── App.tsx                  # React Router declarations (v7 compatible)
│   │   ├── components.tsx           # Shared UI components (EventCard, SearchFilters, etc.)
│   │   ├── pages.tsx                # Public pages (Home, Events, EventDetail, NotFound)
│   │   └── types.ts                 # TypeScript type definitions matching backend schemas
│   ├── vite.config.ts               # Vite configuration with happy-dom test environment
│   └── package.json
├── .github/
│   └── workflows/
│       └── ci.yml                   # GitHub Actions workflow (PostgreSQL 16, pytest, vitest, build)
├── docker-compose.yml               # Multi-container orchestration (PostgreSQL 16, FastAPI, Vite)
└── .env.example                     # Environment template
```

---

## Tech Stack

- **Backend:** Python 3.11+, FastAPI, SQLAlchemy 2.0, Pydantic v2, Alembic, Psycopg 3.
- **Frontend:** React 19, TypeScript, React Router 7, Vite.
- **Testing:** pytest, pytest-anyio, Vitest, Happy-DOM, Testing Library.
- **Database:** PostgreSQL 16 (production/Docker) or SQLite (local development).
- **Orchestration:** Docker Compose.

---

## Local Development Setup

### 1. Prerequisites
- Python 3.11 or higher
- Node.js 20 or higher, with `npm`
- (Optional) PostgreSQL 16 (or use SQLite for fast local development)

### 2. Backend Setup

```powershell
# Navigate to backend directory
cd backend

# Create and activate virtual environment
python -m venv .venv
.venv\Scripts\Activate.ps1    # On Linux/macOS: source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment variables (SQLite mode by default)
$env:APP_ENV="development"
$env:SECRET_KEY="local-development-secret-key-change-in-production"
$env:ADMIN_EMAIL="admin@example.com"
$env:ADMIN_PASSWORD="adminpassword123"

# Run Alembic migrations
alembic upgrade head

# Seed initial categories, locations, and admin account
python seed.py

# Start backend server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The interactive API documentation is accessible at:
- Swagger UI: [http://localhost:8000/docs](http://localhost:8000/docs)
- OpenAPI JSON: [http://localhost:8000/openapi.json](http://localhost:8000/openapi.json)
- Health check: [http://localhost:8000/api/v1/health](http://localhost:8000/api/v1/health)

### 3. Frontend Setup

In a second terminal:

```powershell
# Navigate to frontend directory
cd frontend

# Install dependencies
npm install

# Start development server
npm run dev
```

The frontend will start at [http://localhost:5173](http://localhost:5173). Vite automatically proxies `/api` requests to `http://localhost:8000`.

---

## PostgreSQL Configuration

To run with local or remote PostgreSQL instead of SQLite:

1. Ensure PostgreSQL is running and create a database:
   ```sql
   CREATE DATABASE event_discovery;
   CREATE USER event_discovery WITH ENCRYPTED PASSWORD 'your_password';
   GRANT ALL PRIVILEGES ON DATABASE event_discovery TO event_discovery;
   ```
2. Set the `DATABASE_URL` environment variable:
   ```powershell
   $env:DATABASE_URL="postgresql+psycopg://event_discovery:your_password@localhost:5432/event_discovery"
   ```
3. Run migrations and seed data:
   ```powershell
   alembic upgrade head
   python seed.py
   ```

---

## Environment Configuration

Configuration is managed via Pydantic Settings with automatic environment variable parsing.

| Variable | Default | Purpose | Production Rules |
| :--- | :--- | :--- | :--- |
| `APP_ENV` | `development` | Runtime environment (`development`, `test`, `production`) | Must be set to `production` in production. |
| `DATABASE_URL` | `sqlite:///./event_discovery.db` | SQLAlchemy connection string | **Must** use PostgreSQL in production. SQLite is rejected when `APP_ENV=production`. |
| `SECRET_KEY` | Development default | Key for signing JWT auth tokens | **Must** be changed to a cryptographically random string (min 32 chars). Default is rejected. |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `60` | Token validity lifetime in minutes | Configurable. |
| `ADMIN_EMAIL` | `admin@example.com` | Default admin email | Must be explicitly configured. |
| `ADMIN_PASSWORD` | `change-me` | Initial admin password | Default password is **rejected** when `APP_ENV=production`. |
| `CORS_ORIGINS` | `http://localhost:5173` | Allowed CORS origins (comma-separated) | Should match your deployed frontend domain. |

> [!IMPORTANT]
> When `APP_ENV=production`, the application validates security parameters at startup and crashes immediately if default credentials, weak secret keys, or SQLite databases are detected.

---

## Database Migrations (Alembic)

Alembic is the **authoritative single source of truth** for database schema definitions. `Base.metadata.create_all()` is strictly bypassed in favor of Alembic.

```powershell
cd backend

# Apply all migrations to the latest revision
alembic upgrade head

# Roll back all migrations to clean slate
alembic downgrade base

# Roll back one migration step
alembic downgrade -1

# Show current migration state
alembic current

# Show migration history
alembic history --verbose

# Verify single head
alembic heads
```

### Migration History
- `0001_initial`: Initial schema for categories, locations, events, and admin users.
- `0002_event_slug_featured`: Adds `slug` and `is_featured` to events with cross-database safe ID casting.
- `0003_milestone_event_fields`: Normalized date, organizer, registration URL, and status columns.
- `0004_complete_milestone2_schema`: Extended fields (`registration_deadline`, `fee`, `currency`, `tags`, `eligibility`, `contact_email`, `official_website`), indexes, and category `icon`.
- `0005_repair_category_icon`: Idempotent batch alteration ensuring `icon` on categories across existing deployments.
- `0006_location_verified_venue`: Adds `is_verified_venue` flag distinguishing physical venues from geographic district hubs.

---

## Seed Data Management

The seed script (`backend/seed.py`) is completely **idempotent** and can be run repeatedly without duplicating records or corrupting existing IDs.

```powershell
cd backend

# Standard seed (categories, locations, admin user, and sample event if in development)
python seed.py

# Seed catalogue without sample events
python seed.py --no-sample
```

- **Categories:** Populates core Tamil Nadu event domains (Cultural & Festivals, Music & Dance, Literature & Poetry, Tech & Startups, Sports & Fitness, Food & Culinary, Workshops & Heritage).
- **Locations:** Populates verified venues with complete street addresses (e.g., Chennai Trade Centre, Kalaivanar Arangam, Codissia Complex) and regional geographic hubs marked with `is_verified_venue = False`.
- **Sample Events:** Created **only** when `APP_ENV != "production"`.

---

## Running with Docker Compose

Docker Compose runs the entire stack with PostgreSQL 16, backend API, and frontend web client in isolated containers:

```powershell
# Copy environment file and adjust secrets
cp .env.example .env

# Build and start all services
docker compose up --build

# Run in background
docker compose up -d

# View logs
docker compose logs -f

# Stop and remove containers (data preserved in postgres_data volume)
docker compose down
```

- Web UI: [http://localhost:5173](http://localhost:5173)
- API: [http://localhost:8000](http://localhost:8000)
- PostgreSQL container: Port `5432`

---

## Testing & Quality Assurance

### Backend Tests (pytest)
Runs unit, integration, authentication, authorization, filtering, validation, and migration lifecycle tests:

```powershell
cd backend
pytest -v

# Or run specific test modules:
pytest tests/test_events_crud.py -v
pytest tests/test_public_api.py -v
pytest tests/test_admin_auth_and_actions.py -v
pytest tests/test_postgres_migrations.py -v
```

> [!NOTE]
> `tests/test_postgres_migrations.py` validates SQLite migration upgrade/downgrade/upgrade lifecycle and data preservation by default. When `TEST_POSTGRES_URL` is set (or in CI), it executes full migration testing against PostgreSQL 16.

### Frontend Tests (Vitest)
Runs unit, component, API client, and routing tests:

```powershell
cd frontend
npm test
```

### Production Build & Type Checking
Verifies TypeScript compiler types and builds optimized Vite bundle:

```powershell
cd frontend
npm run build
```

---

## API Endpoints Reference

### Public API (Unauthenticated)

Public routes strictly return only active, published events. Draft, pending, rejected, cancelled, and expired events are excluded.

| Method | Endpoint | Query Parameters | Description |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/v1/events` | `page`, `page_size`, `search`, `category`, `district`, `city`, `time_filter`, `sort_by` | Paginated event listing with filtering and search across title, short description, and description. |
| `GET` | `/api/v1/events/{slug}` | — | Retrieve single published event details by unique slug. |
| `GET` | `/api/v1/events/featured` | `limit` (default: 6) | List curated featured published events. |
| `GET` | `/api/v1/events/upcoming` | `limit` (default: 10) | List upcoming published events (chronological order). |
| `GET` | `/api/v1/categories` | — | List all active event categories. |
| `GET` | `/api/v1/locations` | `district`, `verified_only` | List active Tamil Nadu locations with venue verification status. |
| `GET` | `/api/v1/health` | — | Health probe returning database status and timestamp. |

### Admin API (Protected — Bearer JWT)

Send `Authorization: Bearer <token>` obtained via `/api/v1/admin/login`.

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `POST` | `/api/v1/admin/login` | Authenticate admin credentials and retrieve JWT bearer access token. |
| `GET` | `/api/v1/admin/me` | Current authenticated admin profile. |
| `GET` | `/api/v1/admin/metrics` | Dashboard statistics (total events, published, pending review, categories). |
| `GET` | `/api/v1/admin/events` | List all events (including drafts, pending, published, rejected, cancelled). |
| `POST` | `/api/v1/admin/events` | Create new event with server-side validation. |
| `GET` | `/api/v1/admin/events/{id}` | Retrieve specific event by ID for viewing or editing. |
| `PUT` | `/api/v1/admin/events/{id}` | Update existing event details and metadata. |
| `DELETE`| `/api/v1/admin/events/{id}` | Permanently delete an event. |
| `PATCH`| `/api/v1/admin/events/{id}/publish` | Publish event (enforces publish requirements & valid transition matrix). |
| `PATCH`| `/api/v1/admin/events/{id}/reject` | Reject event with reason note. |
| `PATCH`| `/api/v1/admin/events/{id}/feature` | Toggle featured status (`{"is_featured": true/false}`). |
| `GET` | `/api/v1/admin/categories` | List all categories (active & inactive). |
| `POST` | `/api/v1/admin/categories` | Create new category. |
| `PUT` | `/api/v1/admin/categories/{id}` | Update category details. |
| `DELETE`| `/api/v1/admin/categories/{id}` | Deactivate or remove category. |
| `GET` | `/api/v1/admin/locations` | List all locations with venue verification flag. |
| `POST` | `/api/v1/admin/locations` | Create new location with verified venue metadata. |

---

## Continuous Integration (CI)

GitHub Actions workflow (`.github/workflows/ci.yml`) runs automatically on push and pull requests to `main` and `master`:

1. **Backend Job:**
   - Spins up a live `postgres:16-alpine` service container with health checks.
   - Installs dependencies from `backend/requirements.txt`.
   - Runs Alembic migrations (`upgrade head` -> `downgrade base` -> `upgrade head`) against PostgreSQL.
   - Executes `pytest` against PostgreSQL, asserting 100% test pass rate for all unit, API, and migration validation suites.
2. **Frontend Job:**
   - Sets up Node.js 22 with dependency caching.
   - Executes Vitest component, routing, and API test suites.
   - Executes TypeScript compiler check (`tsc -b`) and Vite production build.
