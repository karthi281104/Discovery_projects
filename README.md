# Tamil Event Discovery

Tamil Event Discovery is a fully automated public event discovery, ingestion, administration, and publishing platform focused initially on Tamil Nadu, India.

It continuously discovers and indexes publicly available events across:
- **Hackathons, Coding Contests, and Open-Source Sprints**
- **College Symposiums, Technical Fests, and Student Competitions**
- **Technology Conferences, Summits, and Developer Meetups**
- **Workshops, Bootcamps, and Hands-on Masterclasses**
- **Startup, Pitch, and Entrepreneurship Summits**
- **Academic and Research Paper Presentations**
- **Cultural Festivals, Heritage Gatherings, and Arts Events**

---

## Architecture Overview

The system consists of an API service, an asynchronous background discovery worker, an authenticated administration portal, and a responsive public web application:

```
tamil-event-discovery/
├── backend/
│   ├── alembic.ini                  # Alembic migration configuration
│   ├── app/
│   │   ├── api/
│   │   │   ├── admin.py             # Authenticated administration routes
│   │   │   ├── discovery.py         # Admin Discovery Monitor APIs
│   │   │   ├── health.py            # System and database readiness probes
│   │   │   └── public.py            # Public event search and discovery routes
│   │   ├── core/
│   │   │   ├── config.py            # Settings with production validation & discovery config
│   │   │   └── security.py          # Password hashing and JWT generation/validation
│   │   ├── db/
│   │   │   ├── base.py              # Declarative Base
│   │   │   ├── dependencies.py      # FastAPI session dependency
│   │   │   └── session.py           # Engine and DB session factory
│   │   ├── discovery/               # Automated Event Discovery Engine
│   │   │   ├── connectors/          # Protocol and format connectors
│   │   │   │   ├── api.py           # JSON REST API connector
│   │   │   │   ├── base.py          # BaseConnector interface & RawCandidate dataclass
│   │   │   │   ├── html.py          # Deterministic HTML & microdata extractor
│   │   │   │   ├── jsonld.py        # Schema.org JSON-LD Event extractor
│   │   │   │   ├── registry.py      # Connector factory
│   │   │   │   └── rss.py           # RSS / Atom XML feed connector
│   │   │   ├── deduplicator.py      # Multi-tier deduplication & matching logic
│   │   │   ├── fetcher.py           # SSRF-protected HTTP client with rate limiting
│   │   │   ├── normalizer.py        # Safe text, canonical URLs, Asia/Kolkata dates
│   │   │   ├── service.py           # Ingestion pipeline, publishing & metric aggregation
│   │   │   └── validator.py         # Candidate evidence scoring & publish validation
│   │   ├── models/                  # SQLAlchemy 2.0 ORM models
│   │   │   └── models.py            # Event, Category, Location, AdminUser, DiscoverySource, DiscoveryRun, EventSource, EventSnapshot
│   │   ├── schemas.py               # Pydantic v2 validation models
│   │   ├── services.py              # Business logic, query filters, and status transitions
│   │   ├── worker.py                # Standalone scheduled discovery worker process
│   │   └── main.py                  # FastAPI application with lifespan management
│   ├── migrations/                  # Alembic migration scripts (0001 -> 0007)
│   ├── seed.py                      # Idempotent seed catalogue & default discovery sources
│   └── tests/                       # Comprehensive pytest suite (Unit, API, Ingestion, Migrations)
├── frontend/
│   ├── src/
│   │   ├── __tests__/               # Vitest component, API, and discovery monitor test suites
│   │   ├── admin.tsx                # Admin dashboard, event forms, and tabbed manager
│   │   ├── api.ts                   # Fetch client with robust header merging & discovery methods
│   │   ├── App.tsx                  # React Router declarations (v7 compatible)
│   │   ├── components.tsx           # Shared UI components (EventCard, SearchFilters, etc.)
│   │   ├── DiscoveryMonitor.tsx     # Admin Discovery Monitor dashboard tab
│   │   ├── pages.tsx                # Public pages (Home, Events, EventDetail, NotFound)
│   │   └── types.ts                 # TypeScript type definitions matching backend schemas
│   ├── vite.config.ts               # Vite configuration with happy-dom test environment
│   └── package.json
├── .github/
│   └── workflows/
│       └── ci.yml                   # GitHub Actions workflow (PostgreSQL 16, pytest, vitest, build)
├── docker-compose.yml               # Multi-container orchestration (db, api, worker, web)
└── .env.example                     # Environment template
```

---

## Discovery & Ingestion Pipeline

The automated ingestion pipeline processes events in sequential, isolated phases:

```
[Discovery Sources Registry]
             │
             ▼
[Scheduled Worker / Admin Trigger]
             │
             ▼
[SSRF-Protected SafeFetcher] (DNS check, private IP block, rate limits, robots.txt)
             │
             ▼
[Connector Extraction] (RSS/Atom, Schema.org JSON-LD, Semantic HTML, REST API)
             │
             ▼
[Field Normalization] (Clean text, canonical URLs, Asia/Kolkata timezone, event types, districts)
             │
             ▼
[Candidate Validation] (Evidence score >= 0.70, non-generic title, valid date & URL)
             │
             ├── If Invalid ──► Record Validation Failure in Run Metrics
             │
             ▼
[Deduplication Engine] (Exact External ID, Canonical URL, Ticket Link, or Date + Title Similarity)
             │
             ├── Match Found ──► Link EventSource, update changed fields, add snapshot
             │
             └── No Match ────► Auto-Publish: create Event with status='published', is_published=True
                                 Generate unique slug, map category/location, create EventSource
```

### Key Engineering Features
- **No Mandatory Admin Approval:** Valid candidates meeting evidence criteria are published automatically and immediately appear on public routes.
- **SSRF Protection:** Resolves hostnames via DNS and rejects loopback (`127.0.0.0/8`), private networks (`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`), link-local (`169.254.0.0/16`), and multicast targets across every hop (including redirects).
- **Failure Isolation:** Each source runs in an independent boundary. A failure in one source records a failed run and updates source error status without disrupting remaining sources.
- **Deduplication & Provenance:** Multiple sources referring to the same physical event are linked to a single `Event` via `EventSource` and `EventSnapshot` records.
- **Automatic Event Expiry:** A scheduled sweep safely marks past published events as `expired` when their end date has passed.

---

## Local Development Setup

### 1. Prerequisites
- Python 3.11+
- Node.js 20+ with `npm`
- (Optional) PostgreSQL 16 (or use SQLite for fast local development)

### 2. Backend & Worker Setup

```powershell
cd backend

# Create and activate virtual environment
python -m venv .venv
.venv\Scripts\Activate.ps1    # On Linux/macOS: source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment variables
$env:APP_ENV="development"
$env:SECRET_KEY="local-development-secret-key-change-in-production"
$env:ADMIN_EMAIL="admin@example.com"
$env:ADMIN_PASSWORD="adminpassword123"

# Run Alembic migrations up to head (0007)
alembic upgrade head

# Seed categories, locations, admin user, and configured discovery sources.
# No fabricated sample events are created by default.
python seed.py

# Start FastAPI server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

To run the automated discovery worker locally:

```powershell
# In a new terminal (inside backend with activated venv):
python -m app.worker

# Or execute a one-off run across due sources and exit:
python -m app.worker --once

# Optional development-only demo event (never use for real catalogue data):
python seed.py --sample
```

### 3. Frontend Setup

```powershell
cd frontend
npm install
npm run dev
```

Visit [http://localhost:5173](http://localhost:5173). Access the admin dashboard at [http://localhost:5173/admin/login](http://localhost:5173/admin/login).

---

## Environment Configuration

| Variable | Default | Purpose | Production Rules |
| :--- | :--- | :--- | :--- |
| `APP_ENV` | `development` | Runtime environment (`development`, `test`, `production`) | Must be `production` in production. |
| `DATABASE_URL` | `sqlite:///./event_discovery.db` | Database connection string | Must use PostgreSQL in production. |
| `SECRET_KEY` | Default | Key for signing JWT auth tokens | Must be at least 32 characters in production. |
| `ADMIN_EMAIL` | `admin@example.com` | Default admin email | Must be explicitly configured. |
| `ADMIN_PASSWORD` | `change-me` | Initial admin password | Default password rejected in production. |
| `DISCOVERY_ENABLED` | `true` | Master switch for automated discovery worker | Enable or disable crawling globally. |
| `DISCOVERY_INTERVAL_MINUTES` | `60` | Default discovery loop interval in minutes | Periodic check interval. |
| `DISCOVERY_REQUEST_TIMEOUT` | `15` | Timeout for outbound HTTP requests in seconds | Prevents slow sources from hanging worker. |
| `DISCOVERY_MAX_PAGES_PER_SOURCE`| `10` | Maximum pages fetched per run per source | Prevents unbounded crawling. |
| `DISCOVERY_MAX_CONCURRENT_SOURCES`| `3` | Maximum sources crawled concurrently | Protects CPU and network bandwidth. |
| `DISCOVERY_USER_AGENT` | `TamilEventDiscoveryBot/1.0...` | Custom User-Agent header for crawl requests | Follows polite web crawler conventions. |

---

## Database Migrations (Alembic)

```powershell
cd backend

# Apply all migrations to the latest revision (0007)
alembic upgrade head

# Roll back all migrations to clean slate
alembic downgrade base

# Verify single head
alembic heads
```

### Migration History
- `0001_initial`: Base schema for categories, locations, events, admin users.
- `0002_event_slug_featured`: Slugs, featured flag, ID casting compatibility.
- `0003_milestone_event_fields`: Normalized date, organizer, registration columns.
- `0004_complete_milestone2_schema`: Extended fields, indexes, category icon.
- `0005_repair_category_icon`: Idempotent batch alteration for icon column.
- `0006_location_verified_venue`: Venue verification flag on physical locations.
- `0006_alembic_version_length`: Widens Alembic's version marker before the long automated-discovery revision.
- `0007_automated_discovery_pipeline`: Source registry (`discovery_sources`), run history (`discovery_runs`), source provenance (`event_sources`), and raw audit snapshots (`event_snapshots`).

---

## Production Deployment with Docker Compose

Docker Compose coordinates PostgreSQL 16, FastAPI backend, automated discovery worker, and Vite frontend web client:

```powershell
# Copy environment file
cp .env.example .env

# Build and start all 4 services
docker compose up --build -d

# Check service logs
docker compose logs -f api
docker compose logs -f worker
docker compose logs -f web

# Stop services
docker compose down
```

Services:
- `db`: PostgreSQL 16 Alpine container with persistent volume and health check probe.
- `api`: FastAPI REST API on port `8000`.
- `worker`: Standalone discovery worker running `python -m app.worker`.
- `web`: Web UI on port `5173`.

---

## Admin Discovery Monitor API Reference

Send `Authorization: Bearer <token>` obtained via `/api/v1/admin/login`.

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/api/v1/admin/discovery/sources` | List all registered discovery sources. |
| `POST` | `/api/v1/admin/discovery/sources` | Register a new discovery source. |
| `PUT` | `/api/v1/admin/discovery/sources/{id}` | Update source parameters, region, or interval. |
| `PATCH`| `/api/v1/admin/discovery/sources/{id}/toggle` | Enable or disable a discovery source. |
| `DELETE`| `/api/v1/admin/discovery/sources/{id}` | Remove a discovery source. |
| `GET` | `/api/v1/admin/discovery/runs` | Paginated discovery run execution history. |
| `GET` | `/api/v1/admin/discovery/runs/{id}` | Detailed run metrics and validation exceptions. |
| `POST` | `/api/v1/admin/discovery/run` | Manually trigger discovery across all enabled sources. |
| `POST` | `/api/v1/admin/discovery/run/{source_id}` | Manually trigger discovery for a specific source. |
| `GET` | `/api/v1/admin/discovery/metrics` | System-wide discovery metrics (created, updated, skipped, errors). |
| `GET` | `/api/v1/admin/discovery/candidates` | List recent candidate validation exceptions for investigation. |
| `GET` | `/api/v1/admin/discovery/events/{id}/sources` | Inspect source attribution and provenance for an event. |

---

## Testing & Verification

### Backend Tests (pytest)
```powershell
cd backend
pytest -v
```
All **58 tests** pass across unit, API, SSRF protection, connectors, normalizer, validator, deduplication, auto-publishing, and migration validation.

### Frontend Tests (Vitest)
```powershell
cd frontend
npm test
```
All **27 tests** pass across 5 test suites.

### Frontend Production Build
```powershell
cd frontend
npm run build
```
Compiles TypeScript types (`tsc -b`) and generates production Vite bundle with 0 errors.

---

## Known Source Limitations & Scope

- **Supported Formats:** RSS/Atom XML feeds, Schema.org JSON-LD event metadata embedded in HTML, semantic HTML listings with configurable CSS selectors, and REST JSON APIs.
- **JavaScript Rendering:** Headless browser rendering is not required for standard public feeds or structured Schema.org data. Websites relying on client-side SPA rendering without Schema.org tags require their API feed to be registered directly.
- **Robots.txt & Terms:** The fetcher respects host rate limits and robots.txt guidelines. Sources gated by CAPTCHAs, bot protections, or paywalls are strictly excluded.
- **Coverage Measurement:** Source coverage is measured empirically through persistent metrics (`pages_checked`, `candidates_found`, `events_created`, `events_updated`, `duplicates_skipped`, `validation_failures`) visible in the Admin Discovery Monitor.
