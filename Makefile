PYTHONPATH_BACKEND_SRC := $(subst \,/,$(abspath backend/src))
EVALUATOR_CASE_STUDY_PYTHONPATH ?= $(PYTHONPATH_BACKEND_SRC)
EVALUATOR_CASE_STUDY_BASELINE_OUTPUT ?= evaluation/seeded_baseline_case_study.json
.PHONY: backend backend-dev backend-install frontend frontend-dev frontend-install db-migrate evaluator-case-study-baseline

backend: backend-install backend-dev

ifeq ($(OS),Windows_NT)
backend-install:
	@powershell -NoProfile -Command "cd 'backend'; $$env:PYTHONPATH = '$(PYTHONPATH_BACKEND_SRC)'; poetry install"

backend-dev:
	@powershell -NoProfile -Command "cd 'backend'; $$env:PYTHONPATH = '$(PYTHONPATH_BACKEND_SRC)'; poetry run uvicorn src.app:app --reload"

db-migrate:
	@powershell -NoProfile -Command "cd 'backend'; $$env:PYTHONPATH = '$(PYTHONPATH_BACKEND_SRC)'; poetry run alembic upgrade head"
else
backend-install:
	@cd backend && PYTHONPATH=$(PYTHONPATH_BACKEND_SRC) poetry install

backend-dev:
	@cd backend && PYTHONPATH=$(PYTHONPATH_BACKEND_SRC) poetry run uvicorn src.app:app --reload

db-migrate:
	@cd backend && PYTHONPATH=$(PYTHONPATH_BACKEND_SRC) poetry run alembic upgrade head
endif

frontend: frontend-install frontend-dev

frontend-install:
	@cd frontend && npm install

frontend-dev:
	@cd frontend && npm run dev

evaluator-case-study-baseline:
	@cd backend && PYTHONPATH="$(EVALUATOR_CASE_STUDY_PYTHONPATH)" poetry run python -m scripts.run_seeded_evaluator_case_study --evaluators baseline --output "$(EVALUATOR_CASE_STUDY_BASELINE_OUTPUT)"
