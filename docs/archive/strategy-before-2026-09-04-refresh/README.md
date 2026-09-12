# Thesica

Thesica is a QA-first academic production platform. The product direction is internal-first: managers and editors prove that generated work can pass quality gates within a human-minutes budget before any broad client self-serve flow is expanded.

## Current Source Of Truth

| Need | Document |
|---|---|
| **Agent brief (read first)** | [docs/AGENT_SYNC.md](./docs/AGENT_SYNC.md) |
| Product strategy and phase gates | [THESICA-PLAN.md](./THESICA-PLAN.md) |
| Design system and visual rules | [DESIGN.md](./DESIGN.md) |
| Current task list | [docs/PRE-RUN-001-TASKS.md](./docs/PRE-RUN-001-TASKS.md) |
| Local setup | [docs/QUICK_START.md](./docs/QUICK_START.md) |
| Production deployment checklist | [docs/setup/PRODUCTION_DEPLOYMENT_PLAN.md](./docs/setup/PRODUCTION_DEPLOYMENT_PLAN.md) |
| Everything else (docs index) | [docs/README.md](./docs/README.md) |
| Deprecated / absorbed docs | [docs/archive/](./docs/archive/README.md) |

## Quick Start

Use the maintained setup guide:

```bash
open docs/QUICK_START.md
```

Short version:

```bash
cd infra/docker
docker-compose up -d

cd ../../apps/api
uvicorn main:app --reload --port 8000

cd ../web
npm run dev
```

Then open `http://localhost:3000`.

## Architecture

```text
Next.js web app -> FastAPI API -> PostgreSQL
                         |
                         +-> Redis
                         +-> MinIO
                         +-> OpenAI / Anthropic providers
```

Core surfaces:

- Public website and client-safe portal for later phases.
- Manager/admin console for production cases, QA evidence, release gates, payments, refunds, users, and audit.
- Editor workspace for findings-specific editorial tasks.
- Phase 1 proof-run artifacts for real internal orders.

## Development

```bash
# Backend
cd apps/api
pytest tests/ -q

# Frontend
cd apps/web
npm run lint
npm run type-check
npm run test -- --runInBand
```

Record durable product and architecture decisions in [docs/AGENT_SYNC.md](./docs/AGENT_SYNC.md) (the historical decision log lives in [docs/archive/DECISIONS_LOG.md](./docs/archive/DECISIONS_LOG.md)). Keep temporary implementation shortcuts explicit in code comments with owner, reason, and removal condition.

## Documentation Policy

This repository intentionally keeps documentation lean. If a document describes an old one-off report, stale release state, or the retired self-serve-first blueprint, it should not be treated as current product truth. Use the documents listed above before adding or changing docs.
