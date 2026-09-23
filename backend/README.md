# Medical Case Simulation Backend

FastAPI backend for AI-powered medical case simulations with SPIKES protocol.

## Architecture

```
backend/
├── src/
│   ├── app.py                    # FastAPI instance & router mounting
│   ├── config/                   # Settings & logging
│   ├── core/                     # Security, errors, deps, events, plugin manager
│   ├── db/                       # Database setup & migrations
│   ├── domain/                   # Entities (models)
│   ├── schemas/                  # Pydantic request/response schemas
│   ├── repositories/             # Data access layer
│   ├── adapters/                 # External service adapters
│   │   ├── llm/                  # LLM adapters (OpenAI, Gemini)
│   │   ├── asr/                  # Speech-to-text (Whisper)
│   │   ├── tts/                  # Text-to-speech
│   │   ├── nlu/                  # Natural language understanding
│   │   └── storage/              # File storage (Supabase)
│   ├── interfaces/               # Plugin protocols (PatientModel, Evaluator, MetricsPlugin)
│   ├── plugins/                  # Registered plugin implementations + PluginRegistry
│   ├── services/                 # Business logic
│   ├── controllers/              # API routes/controllers
│   └── scripts/                  # Seed data, one-off maintenance scripts
├── tests/                        # Test suite (mirrors src/ layout)
├── pyproject.toml                # Dependencies
└── README.md

```

## Setup

### Prerequisites

- Python 3.11+
- PostgreSQL (or SQLite for development)
- Poetry for dependency management

### Installation

1. Install dependencies:
```bash
cd backend
poetry install
```

2. Configure environment:
```bash
cp .env.example .env
# Edit .env with your configuration
```

3. Initialize database:
```bash
poetry run alembic upgrade head
```

4. Run the application:

Set `PYTHONPATH` so the backend imports resolve before starting:

PowerShell:

```powershell
$env:PYTHONPATH = "$PWD\src"
```

macOS / Linux:

```bash
export PYTHONPATH="$PWD/src"
```

```bash
poetry run python src/app.py
```

Or with uvicorn directly:
```bash
poetry run uvicorn src.app:app --reload --host 0.0.0.0 --port 8000
```

### Seeding Dev Data

Create admin accounts plus several trainee users with example cases:

- Admin:           admin@example.com / admin123
- Additional Admin: admin2@example.com / admin123
- Trainees:        alice.trainee@example.com / changeme, etc.

Run:

    poetry run seed

Re-seed from scratch (dev only):

    poetry run seed --reset

## API Documentation

Once running, visit:
- Swagger UI: http://localhost:8000/v1/docs
- ReDoc: http://localhost:8000/v1/redoc

## Key Features

### SPIKES Protocol
The dialogue service implements the SPIKES protocol for breaking bad news:
- **S**etting up the interview
- **P**erception - assess patient's perception
- **I**nvitation - obtain invitation to share info
- **K**nowledge - give knowledge and information
- **E**mpathy - address emotions with empathy
- **S**ummary - strategy and summary

### AI Adapters
- **LLM**: OpenAI GPT-4 or Google Gemini for patient simulation
- **ASR**: Whisper for speech-to-text
- **TTS**: OpenAI TTS via an extensible adapter interface
- **NLU**: Rule-based NLU for empathy detection and question classification
- **Storage**: Supabase object storage for assistant audio with a backend disk cache

### Audio Input Notes
- `POST /v1/sessions/{session_id}/audio` accepts `wav`, `ogg`, `mp3`, `webm`, and `m4a` uploads up to 10 MB.
- Audio input requires a real `openai_api_key` because transcription uses Whisper.
- The upload route validates that the session belongs to the authenticated user and is still active.
- User uploads are transcribed but not persisted after processing.
- Assistant text-to-speech uses OpenAI when the frontend audio toggle is enabled.
- Assistant audio is stored in Supabase, served through `GET /v1/turns/{turn_id}/audio`, and cached on local disk for repeat reads.
- Expired assistant audio can be purged with `poetry run cleanup-expired-audio` and scheduled in Render as a cron job.

### Scoring & Feedback
Automated scoring based on:
- Empathy level
- Question types (open vs closed)
- SPIKES protocol completion
- Communication effectiveness

## Testing

Run tests:

PowerShell:

```powershell
$env:PYTHONPATH = "$PWD\src"
poetry run pytest
```

macOS / Linux:

```bash
export PYTHONPATH="$PWD/src"
poetry run pytest
```

With coverage:
```bash
poetry run pytest --cov=src --cov-report=html
```

## Development

### Database Migrations

Create a new migration:
```bash
poetry run alembic revision --autogenerate -m "description"
```

Apply migrations:
```bash
poetry run alembic upgrade head
```

### Code Quality

Format code:
```bash
poetry run black src/
```

Lint code:
```bash
poetry run ruff src/
```

Type check:
```bash
poetry run mypy src/
```

## Deployment

### Render (recommended flow)

**Pre-deploy command — use migrations only**

Never run a script that **drops** the `core` schema in pre-deploy; that wipes production data. Use Alembic instead:

```bash
# From the backend directory (set Render “Root Directory” to `backend` if the repo root is the capstone project)
bash render_predeploy.sh
```

Equivalent one-liner:

```bash
PYTHONPATH=src poetry run alembic upgrade head
```

**Start command**

Render injects `PORT`. Bind to it so the service listens correctly:

```bash
PYTHONPATH=src poetry run uvicorn src.app:app --host 0.0.0.0 --port "${PORT:-10000}"
```

**Environment variables**

See [`env.render.example`](env.render.example) for a placeholder list. Copy values into the Render dashboard (secrets are not committed).

- **`DATABASE_URL` / `database_url`** — Pydantic accepts either casing. For the **same PostgreSQL data** as your local machine, this value must **match** your local [`.env`](.env) connection string (host, database name, credentials).
- **`SECRET_KEY` / `secret_key`** — Same rule: match local if you want tokens issued in one environment to be valid when debugging the other; otherwise use a production-only secret and re-login after deploys.
- **`CORS_ORIGINS`** — Set to your deployed frontend origin (JSON array or comma-separated), e.g. `["https://your-frontend.onrender.com"]`.

**Frontend (separate Render static site)**

Set `VITE_API_URL` to your **backend** public URL at **build** time so the SPA calls the correct API.

**Storage vs database**

PostgreSQL data (sessions, users, etc.) lives in the database configured by `DATABASE_URL` and **persists** across deploys unless you manually drop schema or truncate data.

Files under `local_storage_path` (default `./storage`) on Render’s **ephemeral filesystem** are **not** preserved across deploys. Assistant audio is also stored in **Supabase** per your settings; prefer relying on Supabase (or similar) for durable media, and treat local cache as disposable.

**Verification checklist**

| Check | Action |
|--------|--------|
| Same DB as local | Compare `DATABASE_URL` in Render with local `database_url` character-for-character. |
| JWT parity | Compare `SECRET_KEY` with local if you expect shared token behavior. |
| Pre-deploy | Confirm logs show `alembic upgrade head`. |
| Missing media only | If DB rows exist but files 404, check Supabase vs wiped `./storage`. |

### Generic production

1. Set production environment variables (see above).
2. Use a managed PostgreSQL database.
3. Run migrations: `poetry run alembic upgrade head`.
4. Run with a production ASGI server, for example:

```bash
gunicorn src.app:app -w 4 -k uvicorn.workers.UvicornWorker
```

## License

This backend is released for non-commercial research and educational use under the [PolyForm Noncommercial License 1.0.0](../LICENSE). See the repository root README for full licensing details, including the separate license covering case scripts and documentation.

