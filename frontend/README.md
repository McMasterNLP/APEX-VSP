# APEX (AI Patient Experience Simulator) - Frontend

A React + TypeScript client for the APEX (AI Patient Experience Simulator) platform, built with Vite, TailwindCSS, and shadcn/ui, backed by the FastAPI service in `../backend`.

## Tech Stack

- **React 19** - UI framework
- **TypeScript** - Type safety
- **Vite** - Build tool and dev server
- **TailwindCSS** - Utility-first CSS framework
- **shadcn/ui** + **lucide-react** - Component library and icons
- **React Router DOM** - Client-side routing
- **Zustand** - Global auth state
- **Axios** - HTTP client, with a JWT interceptor attaching Supabase auth tokens to every request

## Prerequisites

- Node.js 18+ and npm
- A running instance of the FastAPI backend (see `../backend/README.md`), or the shared hosted deployment's API URL

## Installation

```bash
npm install
```

## Environment Setup

Copy the example environment file and fill in the values:

```bash
cp .env.example .env
```

At minimum you need:

- `VITE_API_URL` - the backend's base URL (e.g. `http://localhost:8000`)
- `VITE_SUPABASE_URL` and `VITE_SUPABASE_ANON_KEY` - Supabase project credentials (the same project the backend uses)

`VITE_*` variables are compile-time: changing them requires restarting `npm run dev` (or rebuilding for production), not just a page refresh.

## Development Server

```bash
npm run dev
```

The app runs at `http://localhost:5173` and talks to the backend at `VITE_API_URL`. Authentication is handled entirely by Supabase Auth; there is no mock or offline mode, a running backend and Supabase project are required.

## Routes

| Path | Page | Notes |
| --- | --- | --- |
| `/` | Home | Landing page |
| `/login`, `/signup` | Auth | Supabase-backed sign-in/sign-up |
| `/dashboard` | Dashboard | Case list, start/resume a session |
| `/case/:caseId` | Case chat | Live trainee ↔ simulated patient conversation |
| `/feedback/:sessionId` | Feedback | Scored report for a closed session |
| `/sessions`, `/sessions/:sessionId` | Sessions | Trainee's own session history |
| `/cases` | Cases | Admin case management |
| `/analytics` | Analytics | Trainee-facing analytics |
| `/usage` | Usage | Per-user daily usage against chat/audio/evaluator limits |
| `/admin` | Admin | Session oversight, case management, user/plugin config, Usage dashboard |
| `/admin/sessions/:sessionId` | Session detail | Full transcript and feedback detail for one session |
| `/research` | Research | Research portal: analytics, fairness views, exports |
| `/research/sessions` | Research Sessions | Per-session records with transcripts and metrics |
| `/research/evaluate/:sessionId` | Evaluation workspace | Nested tabs: `overview`, `run`, `runs`, `review`, `validate`, `export` |
| `/docs/user-guide` | User Guide | In-app trainee walkthrough |
| `/docs/admin-guide` | Admin Guide | In-app admin walkthrough |
| `/docs/research-workflow-guide` | Research Workflow Guide | In-app research walkthrough |
| `/docs/plugin-developer-guide`, `/docs/developer-onboarding` | Developer docs | Plugin authoring and repo onboarding |

## Backend Integration

All API calls go through `src/api/*.ts`, using an Axios client (`src/api/client.ts`) configured with `VITE_API_URL` and a request interceptor that attaches the current Supabase session's JWT. There is no mock data layer, every page reads from and writes to the live backend.

## Testing

```bash
npm run test:run   # single run
npm run test       # watch mode
```

## Linting and Type Checking

```bash
npm run lint
npx tsc --noEmit
```

## Production Build

```bash
npm run build
```

Outputs a static bundle to `dist/`, served by the Docker image described in `../README.md` (Docker Compose) and deployed as a Render Web Service in production.

## License

This frontend is released for non-commercial research and educational use under the [PolyForm Noncommercial License 1.0.0](../LICENSE).
