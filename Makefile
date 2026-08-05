# BOTMARKET developer tasks.
#
#   make install   # backend venv + frontend node_modules
#   make dev       # what to run in two terminals
#   make test      # pytest + frontend typecheck
#   make demo      # seed a world and advance it 20 ticks

VENV    := .venv
PY      := $(VENV)/bin/python
PIP     := $(VENV)/bin/pip
BIN     := $(VENV)/bin

.PHONY: help install install-backend install-frontend dev dev-backend dev-frontend \
        test test-backend test-frontend lint fmt seed tick demo reset keygen \
        install-live docker clean

help: ## Show the available targets.
	@grep -hE '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

install: install-backend install-frontend ## Install backend and frontend dependencies.

install-backend: ## Create the venv and install the backend in editable mode.
	python3 -m venv $(VENV)
	$(PIP) install -q -e "backend[postgres,dev]"

install-frontend: ## Install frontend dependencies from the lockfile.
	cd frontend && npm ci

dev: ## Print the two commands to run for local development.
	@echo "Run these in separate terminals:"
	@echo "  make dev-backend    # API on http://localhost:8000"
	@echo "  make dev-frontend   # dashboard on http://localhost:3000"

dev-backend: ## Run the API with autoreload.
	$(BIN)/uvicorn botmarket.main:app --reload

dev-frontend: ## Run the Next.js dashboard.
	cd frontend && npm run dev

test: test-backend test-frontend ## Run every check.

test-backend: ## Run the pytest suite.
	cd backend && ../$(PY) -m pytest

test-frontend: ## Typecheck the dashboard.
	cd frontend && npx tsc --noEmit

lint: ## Lint the backend.
	$(BIN)/ruff check backend/src backend/tests

fmt: ## Autofix backend lint findings.
	$(BIN)/ruff check --fix backend/src backend/tests

seed: ## Create the starter roster of agents.
	$(BIN)/botmarket seed

tick: ## Advance the simulation one tick.
	$(BIN)/botmarket tick

reset: ## Drop every table and start over.
	$(BIN)/botmarket reset

keygen: ## Print a VENUE_ENCRYPTION_KEY for live trading.
	$(BIN)/botmarket keygen

install-live: ## Install the optional exchange SDKs for live trading.
	$(PIP) install -q -e "backend[postgres,dev,live]"

demo: reset seed ## Reset, seed, and run 20 ticks.
	$(BIN)/botmarket tick --count 20
	$(BIN)/botmarket state

docker: ## Bring up the full stack (API, dashboard, Postgres, Redis).
	docker compose up --build

clean: ## Remove build artefacts and the local database.
	rm -rf $(VENV) botmarket.db frontend/.next frontend/node_modules
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
