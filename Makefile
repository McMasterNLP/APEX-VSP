PYTHONPATH_BACKEND_SRC := $(subst \,/,$(abspath backend/src))
EVALUATOR_CASE_STUDY_PYTHONPATH ?= $(PYTHONPATH_BACKEND_SRC)
EVALUATOR_CASE_STUDY_BASELINE_OUTPUT ?= evaluation/seeded_baseline_case_study.json

# Local-only PostgreSQL (docker-compose.local.yml overlay): db=apex user=apex
# password=apex on host port 5433. Every db-local-* / backend-dev-local target
# below overrides DATABASE_URL inline for that one command only, so it can
# never fall back to whatever backend/.env points at (the shared Supabase
# project) even by accident. This is a separate, local-only path -- it does
# not touch backend/.env, frontend/.env, or the shared Supabase database.
LOCAL_DB_URL := postgresql+psycopg2://apex:apex@localhost:5433/apex
LOCAL_COMPOSE := docker compose -f docker-compose.yml -f docker-compose.local.yml

.PHONY: backend backend-dev backend-dev-local backend-install frontend frontend-dev frontend-install \
	db-migrate db-local-up db-local-migrate db-local-seed db-local-reset local-up \
	evaluator-case-study-baseline evaluator-case-study-baseline-overwrite

backend: backend-install backend-dev

ifeq ($(OS),Windows_NT)
backend-install:
	@powershell -NoProfile -Command "cd 'backend'; $$env:PYTHONPATH = '$(PYTHONPATH_BACKEND_SRC)'; poetry install"

backend-dev:
	@powershell -NoProfile -Command "cd 'backend'; $$env:PYTHONPATH = '$(PYTHONPATH_BACKEND_SRC)'; poetry run uvicorn src.app:app --reload"

backend-dev-local:
	@powershell -NoProfile -Command "cd 'backend'; $$env:PYTHONPATH = '$(PYTHONPATH_BACKEND_SRC)'; $$env:DATABASE_URL = '$(LOCAL_DB_URL)'; poetry run uvicorn src.app:app --reload"

db-migrate:
	@powershell -NoProfile -Command "cd 'backend'; $$env:PYTHONPATH = '$(PYTHONPATH_BACKEND_SRC)'; poetry run alembic upgrade head"

db-local-up:
	@$(LOCAL_COMPOSE) up postgres -d --wait
	@powershell -NoProfile -Command "$(LOCAL_COMPOSE) exec -T postgres psql -U apex -d apex -c 'CREATE SCHEMA IF NOT EXISTS core; ALTER DATABASE apex SET search_path TO core, public;'"

db-local-migrate:
	@powershell -NoProfile -Command "cd 'backend'; $$env:PYTHONPATH = '$(PYTHONPATH_BACKEND_SRC)'; $$env:DATABASE_URL = '$(LOCAL_DB_URL)'; poetry run alembic upgrade head"

db-local-seed:
	@powershell -NoProfile -Command "cd 'backend'; $$env:PYTHONPATH = '$(PYTHONPATH_BACKEND_SRC)'; $$env:DATABASE_URL = '$(LOCAL_DB_URL)'; poetry run python -m scripts.seed_local_dev"
else
backend-install:
	@cd backend && PYTHONPATH=$(PYTHONPATH_BACKEND_SRC) poetry install

backend-dev:
	@cd backend && PYTHONPATH=$(PYTHONPATH_BACKEND_SRC) poetry run uvicorn src.app:app --reload

backend-dev-local:
	@cd backend && PYTHONPATH=$(PYTHONPATH_BACKEND_SRC) DATABASE_URL="$(LOCAL_DB_URL)" poetry run uvicorn src.app:app --reload

db-migrate:
	@cd backend && PYTHONPATH=$(PYTHONPATH_BACKEND_SRC) poetry run alembic upgrade head

# Idempotent: safe to run against an already-up, already-initialized database.
# CREATE SCHEMA IF NOT EXISTS is a no-op if core already exists; setting
# search_path is a plain overwrite of the same value every time.
db-local-up:
	@$(LOCAL_COMPOSE) up postgres -d --wait
	@$(LOCAL_COMPOSE) exec -T postgres psql -U apex -d apex -c "CREATE SCHEMA IF NOT EXISTS core; ALTER DATABASE apex SET search_path TO core, public;"
	@echo "Local Postgres is up: postgresql://apex:apex@localhost:5433/apex"

db-local-migrate:
	@cd backend && PYTHONPATH=$(PYTHONPATH_BACKEND_SRC) DATABASE_URL="$(LOCAL_DB_URL)" poetry run alembic upgrade head

db-local-seed:
	@cd backend && PYTHONPATH=$(PYTHONPATH_BACKEND_SRC) DATABASE_URL="$(LOCAL_DB_URL)" poetry run python -m scripts.seed_local_dev
endif

# Full wipe (drops the named volume too) and clean rebuild from scratch.
db-local-reset:
	@$(LOCAL_COMPOSE) down -v
	@$(MAKE) db-local-up
	@$(MAKE) db-local-migrate
	@$(MAKE) db-local-seed

# One-shot happy path: local Postgres up, migrated, seeded. Does not start the
# backend or frontend dev servers -- run those yourself in separate terminals
# (see the printed instructions) so their logs stay visible and you can stop
# either one independently.
local-up: db-local-up db-local-migrate db-local-seed
	@echo ""
	@echo "Local stack is up, migrated, and seeded."
	@echo "Now, in two separate terminals, run:"
	@echo "  make backend-dev-local   # FastAPI on http://localhost:8000, using the local DB"
	@echo "  make frontend-dev        # Vite on http://localhost:5173"
	@echo ""
	@echo "Use 'make backend-dev-local', not 'make backend-dev': the latter reads"
	@echo "DATABASE_URL from backend/.env, which points at the shared Supabase project."

frontend: frontend-install frontend-dev

frontend-install:
	@cd frontend && npm install

frontend-dev:
	@cd frontend && npm run dev

evaluator-case-study-baseline:
	@cd backend && PYTHONPATH="$(EVALUATOR_CASE_STUDY_PYTHONPATH)" poetry run python \
		-m scripts.run_seeded_evaluator_case_study \
		--evaluators baseline \
		--output "$(EVALUATOR_CASE_STUDY_BASELINE_OUTPUT)"

evaluator-case-study-baseline-overwrite:
	@cd backend && PYTHONPATH="$(EVALUATOR_CASE_STUDY_PYTHONPATH)" poetry run python \
		-m scripts.run_seeded_evaluator_case_study \
		--evaluators baseline \
		--output "$(EVALUATOR_CASE_STUDY_BASELINE_OUTPUT)" \
		--overwrite
