# Thesica Documentation

M0-10 **VERIFIED**, 08.09.2026: повідомлення про №5 звірено з БД і
журналом. Є лише job5 від 07.09 о 14:16 UTC, до встановлення виправлень;
нової спроби після M0-09 немає. Web `b85d28b` встановлено й перевірено
08.09 о 11:41 UTC: зрозумілий перехід до повтору та форма перед старими
розділами. API лишається `db9f887`. 208 web-тестів пройшли, 1 пропущено;
живий браузер і незмінність №5 підтверджені. Наступна дія — штатно
підтвердити одну нову спробу №5, потім приймати якість її готового DOCX.
M0/M1 загалом не закрито. [Докази M0-10](evidence/M0-10-2026-09-08.md).

Операційне оновлення 07.09.2026: **M0-09 VERIFIED**, `db9f887` встановлено.
Пріоритет фаундера — спочатку справна технічна генерація для агенції,
потім якість тексту, AI та плагіат. Три DOCX зі справжніми провайдерами
в ізольованому стеку, 9/9 відновлень, 1194 API-тести й живі перевірки
підтверджені. №5 має історичний FAIL, нового production-прогону не було.
Наступна дія — один штатний прогін №5, потім якість того самого DOCX.
Тестові завершення не є M1 PASS; менеджери не тестують технічні дефекти.
[Звіт і докази M0-09](evidence/M0-09-2026-09-07.md).

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
