# Thesica

Thesica is a QA-first academic production platform. The product direction is internal-first: managers and editors prove that generated work can pass quality gates within a human-minutes budget before any broad client self-serve flow is expanded.

## Current Source Of Truth

| Need | Document |
|---|---|
| Product strategy and phase gates | [THESICA-PLAN.md](./THESICA-PLAN.md) |
| Design system and visual rules | [DESIGN.md](./DESIGN.md) |
| Rendered design proof | [thesica-brandbook.html](./thesica-brandbook.html) |
| Local setup | [docs/QUICK_START.md](./docs/QUICK_START.md) |
| Admin/frontend execution plan | [docs/ADMIN_FRONTEND_EXECUTION_PLAN.md](./docs/ADMIN_FRONTEND_EXECUTION_PLAN.md) |
| Phase 0 readiness | [docs/PHASE0_READINESS_RECORD.md](./docs/PHASE0_READINESS_RECORD.md) |
| Phase 1 run template | [docs/PHASE1_RUN_REPORT_TEMPLATE.md](./docs/PHASE1_RUN_REPORT_TEMPLATE.md) |
| Phase 1 go/no-go status | [docs/PHASE1_GO_NO_GO_DECISION.md](./docs/PHASE1_GO_NO_GO_DECISION.md) |
| Production deployment checklist | [docs/setup/PRODUCTION_DEPLOYMENT_PLAN.md](./docs/setup/PRODUCTION_DEPLOYMENT_PLAN.md) |
| Decision history | [docs/sec/DECISIONS_LOG.md](./docs/sec/DECISIONS_LOG.md) |

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

Record durable architecture and product decisions in [docs/sec/DECISIONS_LOG.md](./docs/sec/DECISIONS_LOG.md). Keep temporary implementation shortcuts explicit in code comments with owner, reason, and removal condition.

## Documentation Policy

This repository intentionally keeps documentation lean. If a document describes an old one-off report, stale release state, or the retired self-serve-first blueprint, it should not be treated as current product truth. Use the documents listed above before adding or changing docs.
