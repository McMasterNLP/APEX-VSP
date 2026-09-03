# Running APEX with Docker

This guide covers the **optional** Docker workflow for the full stack (FastAPI backend + Vite/React frontend). It does **not** replace the existing Poetry + npm local setup in the repository root `README.md`.

**Render (unchanged by this workflow):** these paths are not modified when you add or use Docker; Render continues to use your dashboard settings and:

- `backend/render_predeploy.sh`
- `backend/README.md` (Render deployment section)

Validate a Docker-based deployment in staging before turning off Render.

---

## Prerequisites

- [Docker](https://docs.docker.com/get-docker/) and Docker Compose v2
- A **PostgreSQL** database reachable from the backend container — typically **Supabase** (same as production) with `DATABASE_URL` using `sslmode=require` where required
- Supabase project values: **JWT secret** (backend), **URL + anon key** (frontend build)

---

## Environment files

- **Root** `.env.example` consolidates the same variables as `backend/.env.example` and `frontend/.env.example` (naming may differ in case; Pydantic accepts both).
- Copy to **`.env`** at the repo root for Compose. **`.env` is listed in `.gitignore`** — do not commit secrets.

---

## `VITE_*` and rebuilds (important)

`VITE_API_URL`, `VITE_SUPABASE_URL`, and `VITE_SUPABASE_ANON_KEY` are **embedded at frontend image build time** (`npm run build` inside the Dockerfile). Changing them in `.env` does **not** update a running frontend container until you **rebuild** the frontend image:

```bash
docker compose build frontend --no-cache
docker compose up
```

Or rebuild everything:

```bash
docker compose build --no-cache
docker compose up
```

---

## Quick start (external database)

### Bash (macOS / Linux / Git Bash)

```bash
cp .env.example .env
# Edit .env: DATABASE_URL, SUPABASE_JWT_SECRET, OPENAI_API_KEY, GEMINI_API_KEY,
#   CORS_ORIGINS, PUBLIC_BASE_URL, VITE_API_URL, VITE_SUPABASE_URL, VITE_SUPABASE_ANON_KEY

docker compose build
docker compose up
```

Equivalent one-shot (build if needed, then start):

```bash
docker compose up --build
```

### PowerShell (Windows)

```powershell
Copy-Item .env.example .env
# Edit .env with the same variables as above.

docker compose build
docker compose up
```

Or:

```powershell
docker compose up --build
```

### Verify API and open UI

```bash
curl http://localhost:8000/health
```

PowerShell (if `curl` is unavailable):

```powershell
Invoke-WebRequest -Uri http://localhost:8000/health -UseBasicParsing | Select-Object -ExpandProperty Content
```

**Web app:** open **http://localhost:8080** (Compose maps host `8080` → nginx `80`).

**API / docs:** **http://localhost:8000** — OpenAPI: **http://localhost:8000/v1/docs**

---

## Local PostgreSQL (optional)

For a **self-contained local database** only (not for production), use the overlay file. This starts **PostgreSQL 16** with user/password/database `apex` / `apex` / `apex` and a named volume for data. The backend’s `DATABASE_URL` is overridden to point at that service.

### Bash

```bash
docker compose -f docker-compose.yml -f docker-compose.local.yml up --build
```

### PowerShell

```powershell
docker compose -f docker-compose.yml -f docker-compose.local.yml up --build
```

- Postgres is exposed on the host at **port 5433** (mapped to 5432 in the container) to reduce clashes with an existing Postgres on 5432.
- You still need valid Supabase **Auth** configuration in `.env` if you exercise login flows (`SUPABASE_JWT_SECRET`).

### One-shot: migrate and fully seed the local database (recommended)

This is the fastest path to a locally running app with real, reviewable data
for Item 1 (evaluator comparison), Item 2A (prediction review), and Item 2B
(span authoring) -- not just bare trainee sessions. It runs the **backend
and frontend natively** (Poetry/npm), with only PostgreSQL in Docker; it
never touches the shared Supabase project or `backend/.env`'s `DATABASE_URL`.

```bash
make local-up
```

This brings up Postgres (`docker compose ... up postgres -d --wait`),
applies the one manual fix a fresh local Postgres always needs before its
first migration (see below), runs `alembic upgrade head`, and runs the full
seed script -- all idempotent, safe to run repeatedly. It prints the next
two commands to run in separate terminals:

```bash
make backend-dev-local   # FastAPI on http://localhost:8000, using the local DB
make frontend-dev        # Vite on http://localhost:5173
```

Use `backend-dev-local`, not the plain `backend-dev` described earlier in
this doc -- the latter reads `DATABASE_URL` from `backend/.env`, which
points at the shared Supabase project by default.

**Why the schema needs a manual step at all:** every ORM model defaults to
the `core` schema (`backend/src/db/metadata.py`), but no migration has ever
created that schema -- on the shared Supabase project it already exists,
with the *database's own* default `search_path` set to `core, public`
outside of any migration, so every historical migration's unqualified
`CREATE TABLE` has always silently landed in `core` there. A fresh local
Postgres has neither the schema nor that `search_path` default, so replaying
the full migration history against it fails on the very first migration
that creates a table. `make db-local-up` fixes this for you every time
(idempotent: safe even if it's already fixed):

```bash
docker compose -f docker-compose.yml -f docker-compose.local.yml \
  exec -T postgres psql -U apex -d apex \
  -c "CREATE SCHEMA IF NOT EXISTS core; ALTER DATABASE apex SET search_path TO core, public;"
```

A dedicated migration
(`backend/src/db/migrations/versions/1fc6c6467582_ensure_core_schema_exists.py`)
also creates the schema if it's somehow still missing by the time it runs,
but the `search_path` setting itself has to happen at the database level,
before the historical chain runs -- that can't be done portably from inside
a migration against an arbitrary database name, which is why `db-local-up`
handles it as a separate step rather than relying on the migration alone.

**On `alembic revision --autogenerate` never being fully quiet:** running
autogenerate again against a fully-migrated local database does not produce
an empty diff -- it reliably regenerates a large "drop then recreate" set of
foreign-key operations across every `core`-schema table, identical every
time you re-run it (immediately after applying it, or from a fresh database,
the diff is byte-for-byte the same). This is a known category of Alembic
limitation when a table's `schema` is set explicitly (every model here
defaults to `schema="core"`) but the constraint was first created without an
explicit `source_schema`/`referent_schema`: Alembic's reflection-based
constraint comparison doesn't recognize the reflected FK as matching the
target metadata, even though the resulting DDL is semantically identical. It
is safe to ignore (nothing is actually different), but do not accept an
autogenerate-produced migration here without inspecting it column-by-column
first -- a real, additive change would appear as `add_column`/`alter_column`
operations mixed into the same noisy diff, not as a completely separate,
obviously-real-looking migration.

Other targets, all against the same local database (`db=apex user=apex
password=apex` on `localhost:5433`), useful once you're past the first
one-shot run:

```bash
make db-local-up       # bring up Postgres + fix schema/search_path (idempotent)
make db-local-migrate  # alembic upgrade head, against the local DB only
make db-local-seed     # run the full seed script again (idempotent)
make db-local-reset    # DESTROYS the local volume, then up + migrate + seed from scratch
```

`db-local-reset` runs `docker compose ... down -v`, which deletes the named
volume (`apex_pg_data`) and everything in it. It only ever touches the local
Docker volume -- never the shared Supabase database -- but it is otherwise
irreversible for whatever local data you had.

**What gets seeded** (`backend/src/scripts/seed_local_dev.py`, which extends
rather than replaces the existing `seed_demo_sessions.py`):

- the demo case and the 5 demo/review users from `demo_seed_mapping.json`
  (created idempotently if missing -- these don't need real Supabase Auth
  accounts locally, since nothing logs in as them; they're only referenced
  by foreign key);
- the original 15 demo sessions (5 users x 3 empathy-quality fixtures), all
  explicitly pinned to the offline, rule-based baseline evaluator (see the
  caveat below);
- 3 additional sessions sharing the "good" fixture's transcript, one each
  frozen to `hybrid_v1`, `hybrid_v2`, and `ace_ct_inspired` -- so the Admin
  Session Logs list and the Research Evaluation panel have a real transcript
  to compare all four evaluators against. These three intentionally have no
  persisted feedback: computing it for real needs a live OpenAI/Gemini call,
  which this script must never make. Compute it yourself later, on demand,
  through the Research Evaluation panel's existing explicit live-execution
  opt-in.
- one dedicated synthetic session with a saved Item 1 baseline evaluation
  run, an Item 2A annotation set, and a sample Item 2B reviewed state (one
  confirmed prediction, one rejected prediction, one typed boundary
  correction, one human-added span, and a `not_assessed` coverage
  declaration) -- something to inspect immediately without authoring
  everything by hand first. It does not seed a relation or an "assessed"
  coverage level; author those yourself in the workspace UI.

**A caveat worth knowing, found while building this:** `settings.evaluator_plugin`
(the fallback used by any case that doesn't set its own override) defaults
to `apex_hybrid_evaluator`, a live-LLM-requiring evaluator -- so seeding
sessions for a case without an explicit override attempts a real OpenAI call
the moment feedback is generated for it (silently degrading to a rule-only
fallback if the call fails, as it does with a placeholder key, but making a
real, paid call with a real one). `seed_local_dev.py` pins its demo case's
`evaluator_plugin` explicitly to avoid this, mirroring the same pattern
`scripts/run_seeded_evaluator_case_study.py` already uses -- but this is
worth knowing if you write other local seeding for a case that doesn't set
its own `evaluator_plugin`.

---

## Migrations (Alembic)

The backend container **entrypoint** runs `alembic upgrade head` before starting Uvicorn by default (similar in spirit to `backend/render_predeploy.sh` on Render).

- To **skip** migrations in the container (e.g. multiple replicas; run migrations once elsewhere): set `RUN_MIGRATIONS=0` in `.env`.
- **One-off migration** with Compose:

  ```bash
  docker compose run --rm backend poetry run alembic upgrade head
  ```

---

## Volumes

- **`backend_storage`:** mounted at `/app/storage` for local media cache and default `LOCAL_STORAGE_PATH` / `AUDIO_CACHE_PATH` behavior. Ephemeral cache is fine for many deployments; assistant audio durability is expected via Supabase when configured.

---

## Docker smoke / regression checklist

After `docker compose up` (or `up --build`), run through these in order:

| Step | Command or action | Expected |
|------|-------------------|----------|
| 1 | `curl http://localhost:8000/health` (or `Invoke-WebRequest` as above) | JSON includes `"status":"healthy"` |
| 2 | Open **http://localhost:8080** | SPA loads without console errors for missing `VITE_*` |
| 3 | Sign in (Supabase Auth) | Redirect to dashboard or protected route |
| 4 | Open a case / start session | Session API responds |
| 5 | Send a text turn | Patient reply returns |
| 6 | End session → open feedback | Feedback loads for session |
| 7 | Optional: voice / TTS | Requires valid `OPENAI_API_KEY` and related config |
| 8 | Admin: Research / export (if applicable) | `CORS_ORIGINS` includes `http://localhost:8080`; admin role works |

---

## Backend tests with Poetry (not Docker)

Run the automated suite from **`backend/`** with `PYTHONPATH` set so imports resolve (`config`, `controllers`, … live under `src/`).

### Bash

```bash
cd backend
export PYTHONPATH="$PWD/src"
poetry install
poetry run pytest
```

With coverage:

```bash
poetry run pytest --cov=src --cov-report=html
```

### PowerShell

```powershell
cd backend
$env:PYTHONPATH = "$PWD\src"
poetry install
poetry run pytest
```

Other useful commands (from `backend/README.md`): `poetry run black src/`, `poetry run ruff src/`, `poetry run mypy src/`.

---

## Troubleshooting

- **CORS errors:** ensure `CORS_ORIGINS` includes the exact browser origin (scheme + host + port), e.g. `http://localhost:8080`.
- **Broken assistant audio links:** set `PUBLIC_BASE_URL` to the public URL of the API.
- **WebSockets:** the default `nginx.conf` does not proxy `/v1/ws`; the browser connects to `VITE_API_URL` directly. Ensure that origin allows WebSockets and that proxies (if any) forward `Upgrade` / `Connection` headers.

### Research evaluation execution policy

Item 1 research evaluation is offline-safe by default. Keep
`RESEARCH_ALLOW_LIVE_EVALUATIONS=false` unless an approved deployment is
intended to send completed-session transcript content to a configured model
provider. A live run still requires an administrator to select a live evaluator
and explicitly submit `allow_live=true`; ACE-CT-inspired execution also retains
its separate experimental-rubric policy gate. Changing this backend value does
not require rebuilding the frontend image, but the backend container must be
restarted.

---

## Render unchanged

Adding or using Docker images does **not** modify Render services. Render continues to use its configured build/start commands and `backend/render_predeploy.sh` until you change hosting in the Render dashboard.
