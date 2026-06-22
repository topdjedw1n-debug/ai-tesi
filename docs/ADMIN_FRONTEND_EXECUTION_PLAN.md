# Admin, Roles and Frontend UX Execution Plan

**Project:** Thesica / TesiGo
**Date:** 2026-06-22
**Status:** Draft for execution
**Owner:** product + engineering
**Source strategy:** `TESIGO-PLAN.md`, `DESIGN.md`, current `apps/web/app/admin/*`, current FastAPI admin/payment/document endpoints.

This document fills the current gap in the QA-first roadmap: the plan already explains why the platform must prove quality internally before client self-serve, but it does not define enough detail for the admin console, editor workspace, client portal, and implementation prompts.

The goal is to make execution sequential, testable, and hard to misinterpret.

---

## 1. Core Decision

The frontend must be split into four surfaces:

1. **Public website** - marketing and lead capture. No promise of bypassing AI or plagiarism detection.
2. **Client portal** - request, quote/payment, safe status, delivery files, revisions.
3. **Manager/Admin console** - internal production control, QA evidence, release gate, payments, refunds, users, audit.
4. **Editor workspace** - narrow queue of editorial tasks created from QA findings.

The current app already has pieces of admin, payments, documents, settings, refunds, and provenance. The implementation should organize those pieces around the QA-first production workflow instead of expanding early self-serve.

---

## 2. Done Definition

This work is done when an internal manager can take a real order from intake to release decision without using database tools, server logs, or developer help, and a client can see only safe order state and released files.

### Primary Signal

Manager-visible production flow works:

```text
intake -> generation job -> QA evidence -> editor task(s) -> rerun QA -> release decision -> delivery package
```

### Pass / Fail Criteria

- A manager can create or import a production case with topic, language, page count, deadline, citation style, files, and client notes.
- Admin document detail shows production status, QA status, job status, cost/tokens, human minutes, QA evidence, editor tasks, and release decision.
- Release is blocked when blocking QA gates fail, unless a manager/admin records an override reason.
- Editor can see assigned findings, edit or mark them resolved, and trigger targeted QA rerun.
- Client portal never shows raw AI output as final delivery before release approval.

### Secondary Signals

- Backend tests cover status transitions, RBAC, release gate, audit log, and override behavior.
- Frontend tests cover critical UI states: loading, failed QA, blocked release, override modal, editor task completion, client-safe status.
- Admin and client pages follow `DESIGN.md`: Scholarly Press, warm paper surfaces, green semantic action, no blue/purple SaaS styling.

### Stop Condition

Stop and reframe if two implementation attempts do not improve the primary signal. Do not add dashboards, charts, or settings while production case, QA evidence, and release gate remain unclear.

---

## 3. Role Model

### Roles

| Role | Purpose | Must See | Must Not See / Do |
|---|---|---|---|
| `admin` | System owner | Users, roles, settings, payments, refunds, all orders, audit, overrides | Nothing sensitive outside operational need; no raw secrets |
| `manager` | Owns production case | Intake, jobs, QA evidence, editor tasks, delivery, human minutes, release decision | System settings unless explicitly allowed |
| `editor` | Fixes quality findings | Assigned tasks, document sections, findings, comments, QA rerun result | Payments, global settings, unrelated client data |
| `client` | Buyer / requester | Own requests, safe status, uploaded files, released deliverables, messages | Raw AI output before release, internal QA details, other users |
| `support` | Later operator | Orders, clients, status, refunds request intake | Release override, global settings, raw provider logs |

### Permission Rules

- `admin` can override any gate with reason.
- `manager` can override only configured warning gates or blocking gates if policy allows it.
- `editor` cannot release or override.
- `client` cannot trigger generation directly in Phases 1-2.
- Every release, override, retry, assignment, and delivery event writes audit trail.

---

## 4. Data Model Direction

The current `Document` model is too broad for the operational workflow. Do not replace it immediately. Add a thin production layer around it.

### Recommended New Concepts

#### ProductionCase

Represents the business order / internal case.

Required fields:

- `id`
- `client_user_id`
- `document_id`
- `manager_id`
- `editor_id`
- `title`
- `topic`
- `language`
- `country`
- `work_type`
- `target_pages`
- `deadline_at`
- `citation_style`
- `requirements_text`
- `intake_status`
- `generation_status`
- `qa_status`
- `editorial_status`
- `payment_status`
- `delivery_status`
- `human_minutes_budget`
- `human_minutes_used`
- `release_status`
- `created_at`
- `updated_at`

Status dimensions should stay separate. Do not collapse everything into one `status`.

#### ReleaseGateResult

Represents one gate result for one production case or document.

Fields:

- `case_id`
- `gate_key`
- `severity`: `blocking | warning | info`
- `status`: `passed | failed | warning | no_data | skipped`
- `summary`
- `evidence_json`
- `checked_at`
- `provider`
- `can_override`
- `overridden_by`
- `override_reason`
- `overridden_at`

Gate keys for v1:

- `citation_verification`
- `claim_support`
- `section_quality`
- `plagiarism_proxy`
- `ai_detection_proxy`
- `editorial_review`
- `delivery_package`

#### EditorTask

Created from failed/warning QA findings.

Fields:

- `case_id`
- `document_id`
- `section_id`
- `assigned_to`
- `finding_key`
- `severity`
- `title`
- `description`
- `source_gate`
- `status`: `open | in_progress | resolved | rejected`
- `resolution_notes`
- `minutes_spent`

#### AuditEvent

Use existing admin audit logging if enough. Otherwise extend it.

Must capture:

- actor
- action
- target type/id
- before/after where useful
- reason for risky actions
- timestamp
- correlation id

---

## 5. Product Surfaces

## 5.1 Manager/Admin Console

### Navigation

Required sections:

- Dashboard
- Production Cases
- QA Review
- Editor Tasks
- Documents
- Payments
- Refunds
- Users
- Settings
- Audit Logs

Existing admin routes can remain, but the primary route should become production oriented.

### Dashboard

Purpose: show operational risk, not vanity metrics.

Cards:

- Open production cases
- Due in 48 hours
- Stuck generation jobs
- Failed blocking QA gates
- Waiting for editor
- Ready for release review
- Token cost today
- Refund/payment alerts

Tables:

- Deadline risk queue
- Failed QA queue
- Recent release decisions

Avoid prioritizing MRR, ARPU, churn, and marketing metrics until Phase 3.

### Production Case List

Columns:

- Case ID
- Client
- Title/topic
- Language
- Pages
- Deadline
- Manager
- Editor
- Generation status
- QA status
- Editorial status
- Release status
- Human minutes used/budget

Filters:

- status group
- deadline risk
- manager
- editor
- QA failed
- ready for release
- payment pending
- overdue

### Production Case Detail

Tabs:

1. Overview
2. Intake
3. Generation
4. QA Evidence
5. Editor Tasks
6. Payments
7. Delivery
8. Audit

#### Overview

Show:

- case summary
- client
- deadline
- status timeline
- human minutes budget and used
- release blocker summary
- next recommended action

#### Intake

Show/edit:

- topic
- language
- country
- university/context notes
- work type
- target pages
- citation style
- requirements
- uploaded files
- manager notes

#### Generation

Show:

- current job
- progress
- model/provider
- token cost
- retries
- failure reason
- section generation status

Actions:

- start generation
- retry failed job
- regenerate section
- cancel job

#### QA Evidence

Show gate cards:

- citation verification
- claim support
- section quality panel
- plagiarism proxy
- AI detection proxy
- external detector manual result
- provenance timeline

Each card must show:

- passed/failed/warning/no data
- evidence source
- last checked
- blocking or advisory
- action needed

#### Editor Tasks

Show:

- tasks by section
- finding severity
- assigned editor
- status
- minutes spent
- resolution notes

Actions:

- assign editor
- create manual task
- reopen task
- rerun QA for resolved task

#### Delivery

Show:

- release checklist
- final DOCX/PDF
- QA summary
- manager approval
- delivery timestamp
- revision window

Actions:

- approve release
- override gate with reason
- deliver to client
- request editor fixes

Release button must be disabled if blocking gates fail without valid override.

---

## 5.2 Editor Workspace

Purpose: reduce human reading time by sending the editor directly to problematic sections.

Routes:

- `/editor`
- `/editor/tasks`
- `/editor/tasks/[id]`

Screens:

- My task queue
- Task detail
- Section editor
- QA finding context
- Submit resolution

Task detail must show:

- case title
- deadline
- section title
- current content
- specific finding
- evidence from gate
- expected fix
- notes
- minutes timer/input

Actions:

- start task
- save draft
- mark resolved
- reject with reason
- request manager clarification

The editor should not need to read the whole document unless the finding requires it.

---

## 5.3 Client Portal

Purpose: safe order status and delivery. It must not expose raw generation as final output.

Routes:

- `/portal`
- `/portal/orders`
- `/portal/orders/[id]`
- `/portal/orders/new`
- `/portal/payments/[id]`
- `/portal/revisions/[id]`

Client-safe statuses:

- Request received
- Requirements review
- Drafting
- Quality review
- Editorial review
- Preparing delivery
- Delivered
- Revision requested

Client must not see:

- internal gate names by default
- raw AI output before release
- exact AI detector bypass language
- provider logs
- internal editor comments

Client can see:

- order details
- uploaded files
- safe progress state
- payment/quote
- final released files
- revision request form
- support messages

---

## 5.4 Public Website

The public website is Phase 3.

Pages:

- homepage
- how it works
- pricing / request quote
- FAQ
- start order
- login
- terms
- privacy
- refund policy

Allowed positioning:

```text
AI-assisted academic drafting with human quality controls.
```

Disallowed positioning:

```text
Guaranteed bypass of AI detectors.
Guaranteed plagiarism-free under every university system.
```

---

## 6. Implementation Phases

## Phase A - Align Current Admin Around QA-First

**Goal:** make existing admin document screens reflect production risk.

Tasks:

1. Audit existing admin routes and APIs.
2. Rename or reframe dashboard metrics from SaaS vanity metrics to production metrics.
3. Add QA Evidence tab to admin document detail if not already complete.
4. Add release status placeholder and blocked release UI.
5. Add clear "No data" states for missing gates.

Acceptance:

- Admin document detail shows QA evidence and provenance.
- Missing gate data is not shown as passed.
- Dashboard highlights stuck jobs, failed QA, deadline risk.

Validation:

- Frontend unit tests for admin document detail states.
- API contract check for admin document detail.

## Phase B - Production Case Layer

**Goal:** separate business order state from raw document state.

Tasks:

1. Add `ProductionCase` model/table or equivalent migration.
2. Add schemas and endpoints:
   - `GET /api/v1/admin/production-cases`
   - `POST /api/v1/admin/production-cases`
   - `GET /api/v1/admin/production-cases/{id}`
   - `PATCH /api/v1/admin/production-cases/{id}`
3. Link `ProductionCase` to `Document`, client user, manager, and editor.
4. Add status dimensions and deadline/human minutes fields.
5. Add admin list/detail pages.

Acceptance:

- Manager can create a production case without touching payment.
- Existing documents can be displayed through a production case wrapper.
- Status dimensions are separate.

Validation:

- Backend model/schema tests.
- Endpoint permission tests.
- Frontend create/list/detail smoke tests.

## Phase C - Release Gate Contract

**Goal:** make release decision explicit and auditable.

Tasks:

1. Define gate config in code:
   - key
   - label
   - severity
   - source
   - pass condition
   - override policy
2. Add `ReleaseGateResult` storage or normalize from provenance plus manual results.
3. Add endpoint:
   - `GET /api/v1/admin/production-cases/{id}/release-gates`
   - `POST /api/v1/admin/production-cases/{id}/release-gates/{gate}/override`
   - `POST /api/v1/admin/production-cases/{id}/release`
4. Block release when blocking gates fail or have no data unless policy allows override.
5. Write audit events for release and override.

Acceptance:

- Release cannot happen with failed blocking gate unless override is valid.
- Override requires reason and actor.
- UI explains the blocker.

Validation:

- TDD-first backend tests for all gate combinations.
- Frontend tests for disabled release and override modal.

## Phase D - Editor Workspace

**Goal:** turn QA findings into focused editorial tasks.

Tasks:

1. Add `EditorTask` model/table or equivalent.
2. Generate editor tasks from QA findings.
3. Add endpoints:
   - `GET /api/v1/editor/tasks`
   - `GET /api/v1/editor/tasks/{id}`
   - `PATCH /api/v1/editor/tasks/{id}`
   - `POST /api/v1/editor/tasks/{id}/resolve`
4. Add manager assignment UI.
5. Add editor task list/detail UI.
6. Add minutes spent tracking.
7. Add rerun QA action after resolution.

Acceptance:

- Editor can resolve a finding without seeing unrelated admin data.
- Manager sees task status on production case.
- Human minutes update production case economics.

Validation:

- RBAC tests: editor cannot access payments/settings/release override.
- Frontend tests for task queue and resolution.

## Phase E - Client Portal Safe Status

**Goal:** give client visibility without exposing internal/raw output.

Tasks:

1. Define client-safe status mapping from internal statuses.
2. Add client order endpoints:
   - `GET /api/v1/portal/orders`
   - `GET /api/v1/portal/orders/{id}`
   - `POST /api/v1/portal/orders`
   - `POST /api/v1/portal/orders/{id}/revision-request`
3. Add portal routes and layout.
4. Show payment/quote when Phase 3 is active.
5. Show delivery files only after release.

Acceptance:

- Client sees safe status, not internal gate detail.
- Client cannot download unreleased files.
- Client cannot trigger generation directly in Phase 1-2.

Validation:

- API permission tests.
- Frontend tests for unreleased/released states.

## Phase F - Public Website and Sales

**Goal:** connect demand to controlled production flow.

Tasks:

1. Rewrite public homepage to match Thesica Scholarly Press positioning.
2. Add lead/order CTA into portal intake.
3. Add FAQ and refund policy.
4. Add pricing/request quote flow.
5. Enable payment only after production readiness criteria are met.

Acceptance:

- Public copy avoids bypass claims.
- New request enters production flow.
- Payment does not bypass QA or manager release.

Validation:

- Content review.
- Playwright smoke for homepage -> order request.

---

## 7. Suggested Build Order

Use this order. Do not start at the public website.

1. Audit and map current admin/document/payment APIs.
2. Add QA-first dashboard changes.
3. Add production case data layer.
4. Add production case admin list/detail.
5. Add release gate contract and audit.
6. Add editor task data layer.
7. Add editor workspace.
8. Add client-safe portal status.
9. Add delivery package and released file controls.
10. Add payment/quote wiring.
11. Rewrite public website and onboarding.
12. Run real Phase 1/2 operational test.

---

## 8. Prompt Pack for Execution

Use these prompts one at a time. Each prompt assumes the agent will inspect the repo, classify the task, implement, validate, and report. Do not ask the agent to do all phases in one pass.

### Prompt 1 - Audit Current Admin and Frontend State

```text
Ми реалізуємо QA-first admin/frontend план з docs/ADMIN_FRONTEND_EXECUTION_PLAN.md.

Задача: зроби read-only аудит поточного стану admin/frontend/backend API без змін у коді.

Контекст:
- Основний roadmap: TESIGO-PLAN.md
- Дизайн: DESIGN.md
- Новий execution plan: docs/ADMIN_FRONTEND_EXECUTION_PLAN.md
- Поточні web routes: apps/web/app/admin, apps/web/app/dashboard, apps/web/app/payment
- Поточні API: apps/api/app/api/v1/endpoints

Що треба видати:
1. Які екрани admin вже є.
2. Які backend endpoints вже є.
3. Що вже покриває QA evidence/provenance.
4. Що відсутнє для production case, release gate, editor workspace, client-safe portal.
5. Рекомендований перший маленький implementation slice.

Не редагуй файли. Не запускай широкі тести. Якщо запускаєш команди, тільки read-only.
```

### Prompt 2 - Reframe Admin Dashboard Around Production Risk

```text
Реалізуй перший маленький slice з docs/ADMIN_FRONTEND_EXECUTION_PLAN.md: Phase A, admin dashboard має показувати production risk, а не SaaS vanity metrics.

Вимоги:
- Прочитай TESIGO-PLAN.md, DESIGN.md і поточні admin dashboard файли.
- Заміни або доповни dashboard cards так, щоб першим були: open cases/documents, stuck jobs, failed QA/no data QA, deadline risk placeholder, ready for release placeholder, token cost today.
- Якщо backend ще не має production case, використовуй існуючі documents/jobs/admin stats і явно показуй placeholder states тільки там, де даних реально нема.
- Не показуй missing data як passed.
- Дотримуйся Scholarly Press design direction.
- Додай/онови focused frontend tests, якщо поруч уже є тестова інфраструктура.

Acceptance:
- /admin/dashboard ясно відповідає: що горить у production process?
- Старі MRR/ARPU/churn не домінують Phase 1-2 dashboard.
- Лоадинг/помилка/empty states не ламають сторінку.

Валідація:
- Запусти найменший релевантний frontend test або typecheck.
- Якщо не можеш запустити, поясни чому і який substitute signal використав.
```

### Prompt 3 - Add Production Case Backend Skeleton

```text
Реалізуй Phase B backend skeleton з docs/ADMIN_FRONTEND_EXECUTION_PLAN.md.

Задача:
- Додай production case layer навколо існуючого Document, не переписуючи Document.
- Додай модель/міграцію/schema/service/endpoints для ProductionCase або локальний еквівалент, який відповідає плану.
- Статуси мають бути розділені: intake_status, generation_status, qa_status, editorial_status, payment_status, delivery_status, release_status.
- ProductionCase має лінкуватися до document_id, client_user_id, manager_id, editor_id.
- Додай human_minutes_budget, human_minutes_used, deadline_at, citation_style, requirements_text.

Endpoints мінімум:
- GET /api/v1/admin/production-cases
- POST /api/v1/admin/production-cases
- GET /api/v1/admin/production-cases/{id}
- PATCH /api/v1/admin/production-cases/{id}

Acceptance:
- Admin/manager може створити production case без Stripe.
- Існуючий document може бути прив'язаний до case.
- Permission checks не слабші за admin documents.

TDD:
- Почни з focused backend tests для create/list/get/update і permission denial.
- Потім реалізація.

Валідація:
- Запусти targeted pytest для нових tests.
```

### Prompt 4 - Build Production Case Admin UI

```text
Реалізуй admin UI для Production Cases згідно docs/ADMIN_FRONTEND_EXECUTION_PLAN.md.

Задача:
- Додай routes:
  - /admin/production-cases
  - /admin/production-cases/[id]
  - за потреби /admin/production-cases/new
- Додай API client methods у apps/web/lib/api/admin.ts або відповідному файлі.
- List має показувати case id, client, topic/title, language, pages, deadline, manager/editor, generation_status, qa_status, editorial_status, release_status, human minutes.
- Detail має tabs: Overview, Intake, Generation, QA Evidence, Editor Tasks, Payments, Delivery, Audit.
- Для tabs без backend даних зроби чесні "No data yet" / "Not implemented yet" states, але не fake success.

Design:
- Використовуй DESIGN.md: теплі поверхні, зелені action states, restrained admin density.
- Не додавай синій/фіолетовий SaaS стиль.

Acceptance:
- Manager бачить production case як operational object, не просто raw document.
- UI не вимагає developer tools для базового огляду стану.

Валідація:
- Запусти focused frontend tests або TypeScript check для web.
```

### Prompt 5 - Implement Release Gate Contract

```text
Реалізуй Release Gate Contract з docs/ADMIN_FRONTEND_EXECUTION_PLAN.md.

Задача:
- Почни TDD-first.
- Додай gate config у backend: citation_verification, claim_support, section_quality, plagiarism_proxy, ai_detection_proxy, editorial_review, delivery_package.
- Для кожного gate опиши severity, source, pass condition, can_override.
- Додай storage для ReleaseGateResult або нормалізацію з існуючого provenance + manual result.
- Додай endpoints:
  - GET /api/v1/admin/production-cases/{id}/release-gates
  - POST /api/v1/admin/production-cases/{id}/release-gates/{gate}/override
  - POST /api/v1/admin/production-cases/{id}/release
- Release має бути заблокований, якщо blocking gate failed/no_data і немає валідного override.
- Override вимагає reason і пише audit event.

Acceptance:
- Failed blocking gate блокує release.
- No data для blocking gate теж блокує release, якщо policy не каже інакше.
- Override неможливий без reason.
- Audit log містить actor, gate, reason, timestamp.

Валідація:
- Запусти targeted backend tests.
```

### Prompt 6 - Add Release Gate UI

```text
Додай Release Gate UI у production case detail.

Вимоги:
- У tab QA Evidence показати gate cards: status, severity, source, last checked, summary, evidence, action needed.
- У tab Delivery показати release checklist.
- Release button disabled, якщо є blocking failed/no_data gate.
- Override modal доступний тільки manager/admin policy, вимагає reason.
- Після override gate card показує хто і чому override зробив.

Acceptance:
- Manager розуміє, чому release заблокований.
- Не можна випадково видати raw/failed роботу.
- Missing evidence не виглядає як success.

Валідація:
- Frontend tests для failed/no_data/passed/override states.
```

### Prompt 7 - Add Editor Task Backend

```text
Реалізуй EditorTask backend з docs/ADMIN_FRONTEND_EXECUTION_PLAN.md.

Задача:
- Додай модель/міграцію/schema/service/endpoints для editor tasks.
- Task має лінкуватися до production case, document, optional section, assigned editor, source gate/finding.
- Статуси: open, in_progress, resolved, rejected.
- Поля: severity, title, description, resolution_notes, minutes_spent.

Endpoints:
- GET /api/v1/editor/tasks
- GET /api/v1/editor/tasks/{id}
- PATCH /api/v1/editor/tasks/{id}
- POST /api/v1/editor/tasks/{id}/resolve
- Admin/manager endpoint для assign/create task, якщо потрібно.

Permissions:
- Editor бачить тільки assigned tasks.
- Editor не бачить payments/settings/release override.
- Manager/admin бачать tasks for their/all cases according to existing permission model.

TDD:
- Permission tests обов'язкові.
- Status transition tests обов'язкові.
```

### Prompt 8 - Build Editor Workspace

```text
Побудуй Editor Workspace.

Routes:
- /editor
- /editor/tasks
- /editor/tasks/[id]

UI:
- My tasks queue з deadline, severity, case title, section, status.
- Task detail з finding context, section content, evidence, notes, minutes input.
- Actions: start, save notes, mark resolved, reject with reason.

Constraints:
- Editor workspace не має показувати payments, refunds, global settings, unrelated clients.
- UX має бути вузький і робочий: редактор приходить до конкретної проблеми, а не читає все з нуля.
- Дотримуйся DESIGN.md.

Acceptance:
- Editor може закрити finding і записати minutes_spent.
- Manager бачить зміну task status у production case.

Валідація:
- Frontend tests або e2e smoke для task queue/detail.
```

### Prompt 9 - Add Client-Safe Portal Status

```text
Реалізуй client-safe portal status з docs/ADMIN_FRONTEND_EXECUTION_PLAN.md.

Задача:
- Визнач mapping internal statuses -> client-safe statuses:
  Request received, Requirements review, Drafting, Quality review, Editorial review, Preparing delivery, Delivered, Revision requested.
- Додай або адаптуй portal/dashboard endpoints так, щоб client бачив тільки свої orders/cases.
- Не показуй raw AI output до release approval.
- Не дозволяй download unreleased files.
- Не дозволяй client trigger generation напряму у Phase 1-2.

UI:
- /portal або існуючий /dashboard адаптувати тільки якщо це не ламає admin/editor separation.
- Order detail показує safe status, payment/quote, uploaded files, released files, revision request.

Acceptance:
- Client бачить зрозумілий статус без internal QA leakage.
- Released files з'являються тільки після release.
- Permission tests закривають доступ до чужих order/case.

Валідація:
- Backend permission tests.
- Frontend tests for unreleased vs delivered states.
```

### Prompt 10 - Payment and Quote Wiring

```text
Підключи payment/quote flow до production case, не обходячи QA-first process.

Вимоги:
- Payment status має бути окремий від generation_status і release_status.
- Оплата може створити або активувати production case, але не має напряму видавати raw AI result.
- Refund/request refund має лінкуватися до case/order.
- Admin бачить payment/refund у production case detail.
- Client бачить тільки свій payment/refund status.

Acceptance:
- Paid не означає Released.
- Released неможливий без release gate decision.
- Refund audit trail існує.

Валідація:
- Targeted backend tests for payment status transitions.
- Frontend tests for payment pending/paid/refund requested.
```

### Prompt 11 - Public Website Rewrite for Phase 3

```text
Перепиши public website під Thesica QA-first positioning.

Контекст:
- DESIGN.md - Scholarly Press
- TESIGO-PLAN.md - не обіцяємо bypass detection
- docs/ADMIN_FRONTEND_EXECUTION_PLAN.md - Phase F

Вимоги:
- Homepage має продавати "AI-assisted academic drafting with human quality controls".
- Не використовуй claims про guaranteed bypass AI/plagiarism detectors.
- CTA веде до request/order intake, але production QA gate лишається внутрішнім.
- Візуальний стиль: Thesica Scholarly Press, не generic AI SaaS.
- Додай/онови FAQ з чесними обмеженнями.

Acceptance:
- Користувач розуміє, що сервіс дає керований production process, а не магічну кнопку.
- Copy не створює policy/reputation risk.

Валідація:
- Frontend tests/smoke.
- Manual content review summary.
```

### Prompt 12 - End-to-End Operational Smoke

```text
Проведи end-to-end operational smoke для QA-first flow.

Flow:
1. Admin/manager створює production case.
2. Прив'язує або створює document.
3. Запускає generation або використовує існуючий completed document fixture.
4. Переглядає QA evidence.
5. Створює/призначає editor task.
6. Editor resolves task.
7. Manager reruns/checks gate.
8. Manager approves release або бачить blocked release.
9. Client бачить safe status і released files тільки після release.

Що видати:
- Які кроки пройшли.
- Де flow зламався.
- Які endpoints/UI states missing.
- Primary signal status: met / partially validated / not met.
- Мінімальний next fix.

Не приховуй failed validation.
```

---

## 9. Test Matrix

| Area | Required Tests |
|---|---|
| ProductionCase API | create/list/get/update, filters, permissions |
| Status dimensions | independent transitions, invalid transitions rejected |
| Release gates | passed, failed, warning, no_data, override, audit |
| Editor tasks | assignment, editor visibility, resolve/reject, minutes tracking |
| Client portal | own orders only, safe status, unreleased file denial |
| Payments | paid does not imply released, refund linked to case |
| Frontend admin | blocked release UI, no data states, dashboard risk cards |
| Frontend editor | task queue, task detail, resolution |
| Frontend client | order status, delivered files, revision request |

---

## 10. Risks and Guardrails

- **Risk:** building client self-serve too early.
  **Guardrail:** client portal starts with safe status only; no raw output before release.

- **Risk:** one `document.status` becomes overloaded.
  **Guardrail:** separate production status dimensions.

- **Risk:** QA gates look green when data is missing.
  **Guardrail:** `no_data` is a first-class state and blocks release for blocking gates.

- **Risk:** editor becomes a full manual rewrite bottleneck.
  **Guardrail:** editor tasks are finding-specific and minutes are tracked.

- **Risk:** public copy creates detector-bypass liability.
  **Guardrail:** approved positioning only: quality controls, not bypass claims.

- **Risk:** admin dashboard optimizes for vanity metrics.
  **Guardrail:** Phase 1-2 dashboard prioritizes production risk.

---

## 11. Documentation Updates Needed Later

When implementation begins, update these docs only when durable behavior changes:

- `TESIGO-PLAN.md` - add a short reference to this execution plan.
- `docs/USER_EXPERIENCE_STRUCTURE.md` - mark old self-serve-first sections as superseded or rewrite around internal-first.
- `docs/MASTER_DOCUMENT.md` - update architecture/contracts once production case and release gates exist.
- `docs/PHASE1_RUN_REPORT_TEMPLATE.md` - add production case ID, release gate summary, editor task minutes.

Do not update docs for every temporary UI placeholder.
