# AI Marketing Intelligence OS

An autonomous multi-product AI marketing workforce that discovers signals, routes them to the right product, and takes permissioned actions — all visualised in a real-time 3D command center.

![Stack](https://img.shields.io/badge/FastAPI-0.115-009688?style=flat-square&logo=fastapi)
![Stack](https://img.shields.io/badge/Next.js-15-black?style=flat-square&logo=nextdotjs)
![Stack](https://img.shields.io/badge/Temporal-1.x-blue?style=flat-square)
![Stack](https://img.shields.io/badge/PostgreSQL-16-336791?style=flat-square&logo=postgresql)
![Stack](https://img.shields.io/badge/React_Three_Fiber-8.x-orange?style=flat-square)
![Tests](https://img.shields.io/badge/tests-54_passing-4ade80?style=flat-square)

---

## Architecture Overview

```
contracts/          ← Single source of truth: JSON Schema for all events & enums
  events/           ← 20+ event payload schemas
  enums/            ← worker_state, logical_zone, worker_event_type, worker_type
scripts/            ← Type generation (Python + TypeScript from contracts)
apps/
  api/              ← FastAPI backend (Python 3.12, SQLAlchemy 2 async)
  web/              ← Next.js 15 frontend (React 19, React Three Fiber)
infra/              ← Docker Compose (PostgreSQL, Redis, Temporal, PgBouncer)
```

### Key ADRs

| ADR | Decision |
|-----|----------|
| ADR-001 | SQLAlchemy 2 + Alembic is the single DB schema authority. No Drizzle. |
| ADR-002 | Journal-first events: write to `event_journal` (Postgres) then fan-out on Redis Streams |
| ADR-003 | Temporal from day one. Mission = Workflow, Task = Activity. No custom retry logic. |
| ADR-004 | `organization_id` on all tables + PostgreSQL RLS from phase 0 |
| ADR-005 | Backend events carry `logicalZone` enum. Frontend maps to 3D coords via `ZoneRegistry`. |

---

## Features by Phase

| Phase | What's built |
|-------|-------------|
| 0 | JSON Schema contracts, type generation (Python + TypeScript), Docker Compose scaffold |
| 1 | Full domain schema (40+ tables), Alembic migrations, JWT auth, AES-256-GCM credentials, RLS, seed data |
| 2 | EventBusPort abstraction, RedisStreamsEventBus, EventPublisher journal-first, idempotency |
| 3 | WorkerStateMachine, BudgetManager, task dependency DAG resolver, mission/task REST API |
| 4 | Temporal MissionWorkflow + TaskWorkflow, 4-wave parallel execution, human approval gate, crash recovery |
| 5 | 8 deterministic simulation scenarios through production EventPublisher |
| 6 | WebSocket with subscription filtering, 50ms batching, snapshot + replay endpoints |
| 7 | 3D Command Center — 12 zones, Worker3D robots, XState animations, DataPackage3D orbs, LOD |
| 8 | WorkerDetail, MissionDetail, WhyPanel (Claim→Evidence chain), ApprovalPanel, Replay system |
| 9 | PortfolioRouter — keyword scoring, false-positive exclusion via `problems_not_solved`, gap detection |
| 10 | BaseSourceConnector + registry, 5 connectors (Web, RSS, Search, Reddit, News), rate limiter, health monitor |
| 11 | CrawlFrontier, InformationGainEstimator, ResearchBudgetManager, StoppingCriteria, DeduplicationEngine |
| 12 | EvidencePipeline, CriticWorker (PASS/LOW_CONFIDENCE/RESEARCH_AGAIN/CONTRADICTED), ContradictionDetector, EntityResolver |
| 13 | CompetitorIntelligence change detection, MarketProblemMiner, PortfolioGapDetector, AnomalyDetector |
| 14 | ActionPolicyEngine (7-layer), OutcomeObserver |
| 15 | LearningWorker, StrategyUpdater, feedback loop |
| 16 | RateLimitMiddleware, OpenTelemetry, structlog JSON, SIGTERM graceful shutdown, Dockerfiles, CI |

---

## Quick Start (Local)

### Prerequisites
- Python 3.12+
- Node.js 22+
- [uv](https://docs.astral.sh/uv/) — `pip install uv`
- Docker Desktop (for PostgreSQL, Redis, Temporal)

### 1. Clone & configure

```bash
git clone https://github.com/rishabhrk2345/worker.git
cd worker
cp .env.example .env
```

Edit `.env` — replace the placeholder secrets:

```bash
# Generate JWT secret
python -c "import secrets; print(secrets.token_hex(32))"

# Generate credential encryption key
python -c "import secrets, base64; print(base64.b64encode(secrets.token_bytes(32)).decode())"
```

Add your API keys: `OPENAI_API_KEY`, `ANTHROPIC_API_KEY` (optional — simulation mode works without them).

### 2. Start infrastructure

```bash
docker-compose -f infra/docker-compose.yml up postgres redis temporal -d
```

### 3. Backend setup

```bash
cd apps/api
uv sync
uv run alembic upgrade head
uv run python -m seed.seed
```

### 4. Generate types from contracts

```bash
# From repo root
make contracts-validate
```

### 5. Start services

```bash
# Terminal 1 — API (port 8000)
make dev-backend

# Terminal 2 — Temporal worker
make dev-temporal

# Terminal 3 — Frontend (port 3000)
make dev-frontend
```

### 6. Open

| Service | URL |
|---------|-----|
| 3D Command Center | http://localhost:3000 |
| API docs | http://localhost:8000/docs |
| Temporal UI | http://localhost:8080 |

### Run a demo

```bash
# Trigger all 8 simulation scenarios
make simulation

# Or run the portfolio matching smoke test
make portfolio-test
```

---

## Running Tests

```bash
make test          # All 54 backend tests
make test-frontend # TypeScript type check
```

---

## Project Structure

```
apps/api/
├── core/           config, database, security, rbac, event_bus, event_publisher,
│                   worker_state_machine, task_orchestration, rate_limiting, observability
├── models/         SQLAlchemy ORM models (40+ tables across 11 files)
├── routers/        FastAPI route handlers (11 routers)
├── services/       Business logic: portfolio_router, crawl_frontier, research_engine,
│                   evidence_pipeline, competitor_intelligence, action_policy, learning
├── connectors/     Source connectors: website, rss, search, reddit, news
├── temporal/       Workflows (MissionWorkflow, TaskWorkflow, SupervisorWorkflow) + activities
├── simulation/     8 deterministic scenario scripts
├── seed/           Database seed (org, 5 products, 15 sources, 46 worker types, 20 workers)
├── alembic/        Migrations
└── tests/          54 tests across phases 1–9

apps/web/
├── app/            Next.js App Router pages
├── components/
│   ├── scene/      3D: CommandCenter, ZoneRegistry, Worker3D, DataPackage3D, 12 zones, cameras
│   └── panels/     UI: WorkerDetail, MissionDetail, WhyPanel, ApprovalPanel, ReplayControls, etc.
└── lib/
    ├── store/      Zustand stores (worker, event, mission, product, source, ui)
    ├── ws/         WebSocket client + event dispatcher
    ├── replay/     ReplayController
    └── api/        Typed API client

contracts/          JSON Schema contracts (source of truth for both Python and TypeScript types)
infra/              Docker Compose, PgBouncer, Postgres init, Temporal config
scripts/            validate-contracts.py, gen-python-types.py, gen-ts-types.js, export-openapi.py
```

---

## Environment Variables

See [`.env.example`](.env.example) for the full list. Key ones:

| Variable | Purpose |
|----------|---------|
| `DATABASE_URL` | PostgreSQL connection (asyncpg) |
| `REDIS_URL` | Redis for event bus |
| `TEMPORAL_HOST` | Temporal server address |
| `JWT_SECRET` | HS256 signing key (min 32 chars) |
| `CREDENTIAL_ENCRYPTION_KEY` | AES-256-GCM base64 key for source credentials |
| `OPENAI_API_KEY` | LLM routing via LiteLLM |
| `SIMULATION_MODE` | `true` = use deterministic scenarios, `false` = live |

---

## License

MIT
