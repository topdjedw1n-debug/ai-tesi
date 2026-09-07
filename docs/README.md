# Thesica Documentation

This folder contains the maintained operational docs. The current founder brief for AI agents is [AGENT_SYNC.md](./AGENT_SYNC.md). Product strategy lives at the repository root in [THESICA-PLAN.md](../THESICA-PLAN.md); design rules live in [DESIGN.md](../DESIGN.md).

## Quick Navigation

| Need | File |
|---|---|
| **Agent brief (read first)** | [AGENT_SYNC.md](./AGENT_SYNC.md) |
| Local setup | [QUICK_START.md](./QUICK_START.md) |
| Admin/frontend implementation plan | [ADMIN_FRONTEND_EXECUTION_PLAN.md](./ADMIN_FRONTEND_EXECUTION_PLAN.md) |
| Rendered execution board | [ADMIN_FRONTEND_EXECUTION_PLAN.html](./ADMIN_FRONTEND_EXECUTION_PLAN.html) |
| Phase 0 readiness record | [PHASE0_READINESS_RECORD.md](./PHASE0_READINESS_RECORD.md) |
| Phase 1 run report template | [PHASE1_RUN_REPORT_TEMPLATE.md](./PHASE1_RUN_REPORT_TEMPLATE.md) |
| Phase 1 go/no-go status | [PHASE1_GO_NO_GO_DECISION.md](./PHASE1_GO_NO_GO_DECISION.md) |
| Phase 1 proof run reports | [phase1-runs/](./phase1-runs/) |
| Production deployment checklist | [setup/PRODUCTION_DEPLOYMENT_PLAN.md](./setup/PRODUCTION_DEPLOYMENT_PLAN.md) |
| Email setup | [Email/EMAIL_SETUP.md](./Email/EMAIL_SETUP.md) |
| Decision log | [sec/DECISIONS_LOG.md](./sec/DECISIONS_LOG.md) |

## Reading Order

1. [AGENT_SYNC.md](./AGENT_SYNC.md) - current founder brief, pass bar, and work queue.
2. [../THESICA-PLAN.md](../THESICA-PLAN.md) - product direction and phase gates.
3. [../DESIGN.md](../DESIGN.md) - UI and brand constraints.
4. [QUICK_START.md](./QUICK_START.md) - run the project locally.
5. [ADMIN_FRONTEND_EXECUTION_PLAN.md](./ADMIN_FRONTEND_EXECUTION_PLAN.md) - implement the internal QA-first workflow.
6. [PHASE0_READINESS_RECORD.md](./PHASE0_READINESS_RECORD.md) and [phase1-runs/](./phase1-runs/) - record proof-run evidence.

## Structure

```text
docs/
├── README.md
├── AGENT_SYNC.md
├── QUICK_START.md
├── ADMIN_FRONTEND_EXECUTION_PLAN.md
├── ADMIN_FRONTEND_EXECUTION_PLAN.html
├── PHASE0_READINESS_RECORD.md
├── PHASE1_RUN_REPORT_TEMPLATE.md
├── PHASE1_GO_NO_GO_DECISION.md
├── phase1-runs/
├── setup/
│   └── PRODUCTION_DEPLOYMENT_PLAN.md
├── Email/
│   └── EMAIL_SETUP.md
└── sec/
    └── DECISIONS_LOG.md
```

## Maintenance Rule

Keep docs current, narrow, and tied to decisions or repeatable operations. One-off smoke reports, stale release checklists, and old self-serve-first plans belong in git history, not in active navigation.

## Internal release — 07.09.2026

[Verified M0-06 release](evidence/M0-06-RELEASE-2026-09-07.md): code 585a415
was committed, pushed and installed with founder approval. manager1 production
access is active; API/web, bot connectivity and release restrictions are verified.
The same record contains exact runtime hashes, backups, rollback and test limits.

[SHORT-001](phase1-runs/SHORT-001.md) records the existing document 5 for the
first short M1 run. It is READY / PENDING REAL RUN DATA; Tanya has not started
generation or accepted an academic result. Real Compilatio and no-rewrite proof
remain required on the final DOCX.
