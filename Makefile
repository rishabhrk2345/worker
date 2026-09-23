.PHONY: help dev dev-backend dev-frontend dev-temporal test test-backend test-frontend \
        lint migrate seed contracts-validate export-openapi simulation clean \
        docker-up docker-down docker-logs portfolio-test

help:
	@echo "AI Marketing Intelligence OS — Development Commands"
	@echo "==================================================="
	@echo ""
	@echo "Setup:"
	@echo "  make contracts-validate  Validate JSON schemas + generate Python & TS types"
	@echo "  make migrate             Run Alembic database migrations (head)"
	@echo "  make seed                Seed database (org, products, sources, workers)"
	@echo ""
	@echo "Development:"
	@echo "  make dev-backend         Start FastAPI backend (port 8000)"
	@echo "  make dev-frontend        Start Next.js frontend (port 3000)"
	@echo "  make dev-temporal        Start Temporal activity worker"
	@echo "  make simulation          Run all 8 deterministic simulation scenarios"
	@echo ""
	@echo "Testing:"
	@echo "  make test                Run all tests (backend)"
	@echo "  make test-backend        pytest with verbose output"
	@echo "  make test-frontend       TypeScript type check"
	@echo "  make portfolio-test      Run portfolio matching smoke test"
	@echo ""
	@echo "Docker:"
	@echo "  make docker-up           Start full stack via docker-compose"
	@echo "  make docker-down         Stop and clean containers"
	@echo "  make docker-logs         Follow all container logs"
	@echo ""
	@echo "Tools:"
	@echo "  make export-openapi      Export FastAPI OpenAPI spec to contracts/"
	@echo "  make clean               Remove __pycache__, .pytest_cache, etc."

# ── Contracts ─────────────────────────────────────────────────────────────────

contracts-validate:
	python scripts/validate-contracts.py
	python scripts/gen-python-types.py
	node scripts/gen-ts-types.js

export-openapi:
	cd apps/api && uv run python ../../scripts/export-openapi.py

# ── Database ──────────────────────────────────────────────────────────────────

migrate:
	cd apps/api && uv run alembic upgrade head

migrate-down:
	cd apps/api && uv run alembic downgrade base

seed:
	cd apps/api && uv run python -m seed.seed

# ── Development servers ───────────────────────────────────────────────────────

dev-backend:
	cd apps/api && uv run uvicorn main:app --reload --port 8000 --host 0.0.0.0 --log-level info

dev-frontend:
	cd apps/web && npm run dev

dev-temporal:
	cd apps/api && uv run python -m temporal.worker

simulation:
	cd apps/api && uv run python -m simulation.run_all

# ── Tests ─────────────────────────────────────────────────────────────────────

test: test-backend

test-backend:
	cd apps/api && uv run pytest tests/ -v --tb=short --no-header

test-frontend:
	cd apps/web && npm run type-check

portfolio-test:
	@echo "Running portfolio matching smoke test..."
	curl -s -X POST http://localhost:8000/api/intelligence/match \
	  -H "Content-Type: application/json" \
	  -d '{"problem_statement": "My Facebook ROAS does not match Stripe revenue", "intent_score": 0.9}' \
	  | python -m json.tool

# ── Docker ────────────────────────────────────────────────────────────────────

docker-up:
	docker-compose -f infra/docker-compose.yml up -d
	@echo "Stack starting..."
	@echo "  API:          http://localhost:8000/docs"
	@echo "  Frontend:     http://localhost:3000"
	@echo "  Temporal UI:  http://localhost:8080"

docker-down:
	docker-compose -f infra/docker-compose.yml down -v

docker-logs:
	docker-compose -f infra/docker-compose.yml logs -f

# ── Cleanup ───────────────────────────────────────────────────────────────────

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".next" -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
	@echo "Cleaned."
