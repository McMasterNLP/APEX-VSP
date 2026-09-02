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
