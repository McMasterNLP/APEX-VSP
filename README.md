# APEX (AI Patient Experience Simulator) – Capstone Project

Welcome to the APEX (AI Patient Experience Simulator) Capstone Project.

## Project Overview

APEX is an AI-powered patient communication training platform for medical trainees.
It simulates doctor–patient conversations and provides structured feedback aligned with the **SPIKES communication framework** and the **Appraisal Framework for Clinical Empathy (AFCE)**.

The system combines a React + TypeScript frontend with a FastAPI backend and a plugin-based dialogue/scoring engine to:

- **Simulate realistic patient dialogue** with configurable virtual patient cases.
- **Evaluate communication quality and empathy**, including SPIKES stage coverage and AFCE-aligned metrics.
- **Provide analytics and research exports** so educators and researchers can study communication patterns over time.

Role-based access currently supports:

- **Trainee**: practice conversations, view feedback.
- **Admin**: manage cases, configure plugins, access analytics and research exports.

---

## Accessing the Hosted Version

The application is fully deployed and accessible at:

**[https://apexsimulator.org/](https://apexsimulator.org/)**

No local setup is required to evaluate the system. Use the TA review accounts below to access all features.

### TA Review Credentials

| Role    | Email                      | Password         |
| ------- | -------------------------- | ---------------- |
| Trainee | `trainee.review@apex.com`  | `ApexReview123!` |
| Admin   | `admin.review@apex.com`    | `ApexReview123!` |

> The admin account has full access to all trainee features plus the admin dashboard, research analytics, and CSV export.

---

## Trainee Demo Walkthrough

Follow these steps to experience the trainee workflow end-to-end:

1. Navigate to **[https://apexsimulator.org/](https://apexsimulator.org/)**.
2. Click **"Start a simulated session"** on the landing page.
3. On the sign-in screen, enter the trainee credentials:
   - Email: `trainee.review@apex.com`
   - Password: `ApexReview123!`
4. After signing in you will land on the **Dashboard** (`/dashboard`).
   - The dashboard lists all available virtual patient cases.
5. Click on a case card to open the case detail view.
6. Click **Start Session** to enter the chat interface (`/case/:caseId`).
7. Type your messages in the input box to converse with the simulated patient.
   - Aim for at least 2–3 turns to generate meaningful feedback.
8. When finished, click **End Session**.
9. You will be redirected to the **Feedback** page (`/feedback/:sessionId`), which shows:
   - Overall empathy score and AFCE-aligned breakdown
   - SPIKES stage progression and coverage
   - Specific strengths and missed empathy opportunities from the conversation
10. Navigate to **Sessions** (`/sessions`) in the sidebar to review all past sessions and their feedback.

---

## Admin Demo Walkthrough

The admin account provides access to all trainee features plus additional oversight and research capabilities:

1. Navigate to **[https://apexsimulator.org/](https://apexsimulator.org/)** and sign in with the admin credentials:
   - Email: `admin.review@apex.com`
   - Password: `ApexReview123!`
2. After signing in you will land on the **Dashboard**.
   - As an admin, the sidebar exposes additional navigation links.
3. Navigate to **Admin** (`/admin`) to access:
   - Session oversight (all user sessions across the platform)
   - Case management (view and inspect configured virtual patient cases)
   - User and plugin configuration details
4. Navigate to **Research** (`/research`) to access:
   - Aggregated session metrics and fairness analytics
   - Bias and demographic parity visualizations
   - **CSV export** – click the export button to download anonymized session data for offline analysis
5. Navigate to **Research Sessions** (`/research/sessions`) to:
   - Inspect individual session records with full transcripts and per-turn metrics
   - Click into any session to view a detailed breakdown at `/admin/sessions/:sessionId`

---

## Repository Structure

```
project-root/
├── backend/         # FastAPI application (API + database, plugins, services)
│   ├── src/
│   │   ├── app.py
│   │   ├── core/
│   │   ├── domain/
│   │   ├── services/
│   │   ├── repositories/
│   │   ├── controllers/
│   │   └── scripts/
│   └── README.md
│
├── frontend/        # React + Vite + TypeScript client
│   ├── src/
│   │   ├── api/
│   │   ├── components/
│   │   ├── pages/
│   │   ├── store/
│   │   └── types/
│   └── README.md
│
├── docs/            # architecture, design, and research documentation
└── README.md        # root project overview (this file)
```

---

## Core Features

- **Simulated patient interactions** – Trainees engage with virtual patients via a structured chat interface.
- **Structured empathy evaluation (SPIKES / AFCE)** – Automated metrics for stage coverage, question style, and empathic opportunity handling.
- **Session lifecycle management** – Create, resume, and close sessions with full transcript history.
- **Feedback and scoring engine** – Session summary, empathy scores, SPIKES completion, AFCE-style breakdowns, and conversation timelines.
- **Admin dashboard and research analytics** – Case management, session metrics, fairness-oriented analytics, and anonymized data export for research.
- **Research evaluation workspace** – Admin-only, non-persisting comparison of reviewed evaluators through a versioned native-plus-projection contract, capability-driven views, and sanitized exports. See [the Item 1 research evaluation documentation](docs/research/evaluation_platform/README.md).
- **Bias & fairness views** – Visualizations to inspect score consistency across anonymized cohorts (where data is available).
- **Security & role-based access** – Supabase Auth with email verification, JWT-based API authorization, trainee/admin roles, and separation between training and research views.

---

## System Architecture

At a high level, APEX uses a layered, service-oriented architecture:

- **Frontend (React + TypeScript)** → SPA that handles authentication, role-aware routing, chat UI, feedback dashboards, admin and research views.
- **Backend API (FastAPI)** → RESTful endpoints for sessions, cases, feedback, admin operations, and research exports.
- **Dialogue & Scoring Services** → domain services for dialogue management, SPIKES/AFCE scoring, session lifecycle, and feedback generation.
- **LLM Adapter & NLU Pipeline** → abstraction layer for calling LLMs (e.g., OpenAI / Gemini) and running the NLU / turn analysis pipeline.
- **Database (PostgreSQL via SQLAlchemy)** → stores users, cases, sessions, turns, feedback, and plugin configuration.

Internally, the backend follows a layered structure:

- **Controllers** (`controllers/`) – FastAPI route handlers and request/response models.
- **Services** (`services/`) – business logic for dialogue, scoring, case management, sessions, and research/export flows.
- **Repositories** (`repositories/`) – database access using SQLAlchemy models.
- **Domain entities/models** (`domain/`) – core domain types and invariants.
- **Plugins** (`plugins/`) – patient models, evaluators, and metrics providers loaded through explicit imports and a small **registry**.

At startup, the app imports a fixed list of plugin modules (`PLUGIN_MODULES` in `backend/src/plugins/load_plugins.py`). Each module registers its classes with **`PluginRegistry`**. There is **no filesystem discovery**—add your module to that list (or ensure it is imported by a module already in the list) so registration runs.

**Registering a new plugin (short version):**

1. Add a Python module under `backend/src/plugins/` (e.g. `plugins/evaluators/my_evaluator.py`) implementing the right **Protocol** (`interfaces/`).
2. At module bottom, call `PluginRegistry.register_evaluator(MyEvaluator.name, MyEvaluator)` (or the matching register helper for patient/metrics). Set class attribute **`name`** to your stable registry key (typically `module.path:ClassName`).
3. Append your module path to **`PLUGIN_MODULES`** in `load_plugins.py`.
4. Point **settings** (or case/session overrides where supported) at that **`name`** string.
5. Run **`pytest`** under `backend/tests/plugins/` and add tests for your plugin.

---

## Plugin Architecture

APEX exposes a plugin system that allows researchers to extend patient behavior, evaluation logic, and metrics without modifying core services.
There are three main plugin types (see `backend/src/plugins` and `backend/src/interfaces`):

- **PatientModel** – defines how the virtual patient responds to clinician turns (e.g., default LLM-based patient model).
- **Evaluator** – computes overall feedback for a session, combining SPIKES coverage, AFCE-style empathy analysis, and other scores.
- **MetricsPlugin** – optional research metrics via a `compute` method; session metadata can record which metrics plugins were selected for a run.

Plugins are **registered in code** (on import) and **selected** via configuration and the **PluginRegistry**. Paths use the form `module.path:ClassName`. The **plugin manager** (`core/plugin_manager.py`) can also load classes from those path strings for settings-based defaults and tests.

---

## Tech Stack

**Backend**

- FastAPI (Python) for the REST API and controllers
- SQLAlchemy ORM and Alembic migrations for PostgreSQL
- Pydantic and pydantic-settings for configuration
- Plugin-based services for dialogue, evaluation, and metrics
- Poetry for dependency management
- Pytest for automated testing

**Frontend**

- React 18 + Vite
- TypeScript
- TailwindCSS
- Zustand for global state
- shadcn/ui + lucide-react for UI components and icons
- Axios for API communication

---

## Running Locally (Optional)

> The hosted version at **[https://apexsimulator.org/](https://apexsimulator.org/)** is already fully deployed with all services configured. The steps below are only needed if you want to run APEX on your own machine.
>
> **You will need your own OpenAI and/or Gemini API keys** for the LLM-powered patient dialogue. All other configuration (Supabase, database) can be copied from the `.env.example` files in this repository.

### Prerequisites

- Python 3.11+ and [Poetry](https://python-poetry.org/)
- Node.js 18+ and npm
- A Supabase project (or use the shared project — see `.env.example`)

### Docker Compose (optional)

To run the FastAPI backend and the Vite-built frontend in containers (with **Supabase/Postgres still external** unless you add the optional local Postgres overlay), see **[docs/docker.md](docs/docker.md)** for exact commands (bash and PowerShell), a Docker smoke checklist, Poetry/pytest commands, and notes on **`VITE_*` rebuilds** and migrations. Copy the root **`.env.example`** to **`.env`**, fill in secrets and URLs, then run `docker compose build` and `docker compose up`. Do not remove or change **Render** until a Docker-based deployment is validated.

### 1. Clone the repository

```bash
git clone https://github.com/AsherHaroon/capstone.git
cd capstone
```

### 2. Backend Setup

Navigate to the backend directory and install dependencies:

```bash
cd backend
poetry install
```

Copy the example environment file and fill in your API keys:

```bash
cp .env.example .env
```

Open `backend/.env` and set at minimum:

```
openai_api_key=your-openai-api-key-here
# or
gemini_api_key=your-gemini-api-key-here
```

All other values (database URL, Supabase URL, JWT secret, etc.) are pre-filled in `.env.example` and point to the shared project — you can use them as-is for local testing.

Set `PYTHONPATH` so backend imports resolve correctly:

macOS / Linux:
```bash
export PYTHONPATH="$PWD/src"
```

PowerShell:
```powershell
$env:PYTHONPATH = "$PWD\src"
```

Run the FastAPI server:

```bash
poetry run uvicorn src.app:app --reload
```

The API will be available at `http://localhost:8000/v1`.
OpenAPI documentation is at `http://localhost:8000/docs`.

### 3. Frontend Setup

Open a new terminal, navigate to the frontend directory, and install dependencies:

```bash
cd frontend
npm install
```

Copy the example environment file:

```bash
cp .env.example .env
```

The `.env.example` already contains the correct Supabase URL and anon key for the shared project. The only value you may need to change is `VITE_API_URL` if your backend runs on a different port.

Run the development server:

```bash
npm run dev
```

The interface will be available at `http://localhost:5173`.

---

## Creating Users (Local / Development)

Authentication is handled by **Supabase Auth**. Users sign up through the frontend at `/signup` with email verification.

To create an admin user:

1. Create the user through the `/signup` page or the Supabase dashboard (**Authentication > Users > Add user**).
2. Set their role to admin in the database:

```sql
UPDATE core.users SET role = 'admin' WHERE email = 'admin@example.com';
```

---

## Roles and Permissions

| Role        | Access                                                                  |
| ----------- | ----------------------------------------------------------------------- |
| **Trainee** | Access to virtual cases, simulated patient chat, and feedback views     |
| **Admin**   | Full CRUD on cases, user/session oversight, analytics, and research API |

---

## Research Orientation

APEX is designed to support research in clinical communication training and LLM-based dialogue evaluation:

- **Anonymized research exports** – Admins can export metrics and transcripts through dedicated research endpoints for offline analysis.
- **Fairness and bias analysis** – Research views surface aggregate metrics that can be used to study score consistency across anonymized cohorts.
- **Extensible evaluation stack** – The plugin architecture allows new evaluators and metrics to be introduced for experimental studies without changing core APIs.
- **Reproducible session data** – Session transcripts, SPIKES/AFCE metrics, and feedback summaries are stored in a structured form for downstream quantitative and qualitative analysis.

---

## Team

Developed by
**Tung Ho**, **Asher Haroon**, **Michael Fedotov**, **Hammad Ur Rehman**, **Christian Canlas**, **Aaryan Kandwal**, and **Samir Matani**
as part of the McMaster University 4ZP6A Capstone Project.

Tasks and work have been split and documented using the Jira platform accessed via https://medllmcapstone.atlassian.net/jira/software/projects/SCRUM/summary
