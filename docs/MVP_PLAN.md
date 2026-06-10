# 🚀 MVP ПЛАН - TesiGo Platform

**Оновлено:** 24 лютого 2026
**Статус:** 🟡 **RELEASE CANDIDATE (CONDITIONAL GO)**

---

## 🎯 ПОТОЧНИЙ СТАН (FACT-BASED)

### ✅ Quality gates (24.02.2026)
- Backend: `pytest tests/ -q` → **396 passed, 6 skipped, 0 failed**
- Frontend: `npm run lint` → **pass**
- Frontend: `npm run type-check` → **pass**
- Frontend: `npm run test -- --runInBand` → **12 suites, 125 passed, 1 skipped**
- Frontend: `npm run build` → **pass**

### ✅ Runtime smoke (prod-like Docker)
- API health: `GET /health` → **200**
- Web health: `GET /api/health` → **200**
- Auth smoke: `GET /api/v1/auth/me` → **200**
- Admin smoke: `GET /api/v1/admin/stats` → **200**
- Contract smoke (auth):
  - `GET /api/v1/refunds` → **200**
  - `GET /api/v1/payment/history` → **200**
  - `POST /api/v1/generate/full-document` → **422** (expected validation error, route exists)
- Примітка: запуск `scripts/runtime_smoke.sh` з sandbox-host повертає `000` на localhost; контрактні/auth перевірки валідовані зсередини контейнера API.

### ✅ P1 Hotfixes (24.02.2026)
1. `GET /api/v1/documents/stats` більше не повертає `422` через перехоплення dynamic route.
   - Fix: `/stats` переставлено вище `/{document_id}` у `documents.py`.
   - Regression: `apps/api/tests/test_documents_stats_endpoint.py`.
2. Admin users UI показує Block/Unblock коректно.
   - Fix: нормалізація payload у `apps/web/lib/api/admin.ts` (canonical `is_active`).
   - Fix: fallback-логіка рендера в `UsersTable.tsx` і `UserDetails.tsx`.
   - Regression: додаткові тести в `UsersTable.test.tsx`.

---

## ✅ ЗРОБЛЕНО В ЦИКЛІ STABILITY + OPERATIONAL MATCH

1. Backend reliability fixes:
- logging reserved key conflict fixed (`task_args_snapshot`);
- defensive DB guards + checkpoint cleanup paths stabilized.

2. FE/BE contract sync:
- generation contract aligned (`/full-document`, `/usage/{user_id}`);
- admin contract aligned (`logout`, `block/unblock`, `make-admin`, `bulk user_ids`);
- invalid pricing config endpoint removed from client constants.

3. Refunds Wave 3B (full restore):
- added user read endpoints on backend:
  - `GET /api/v1/refunds`
  - `GET /api/v1/refunds/{id}`
- replaced frontend fallback-only refunds client with real API calls;
- added user refund UI pages:
  - `/payment/refunds`
  - `/payment/refunds/[id]`

4. Frontend quality gates:
- strict `next build` flags kept enabled (`ignoreBuildErrors=false`, `ignoreDuringBuilds=false`);
- Jest/Playwright isolation preserved;
- checkout flow uses centralized API client.

5. Runtime/infra:
- web health endpoint available (`/api/health`);
- prod compose defaults updated for payment/refund flows enabled,
  with kill-switch flags still available.

6. CI hard gate:
- mandatory jobs: `repo-hygiene`, `backend-pytest`, `web-lint`, `web-typecheck`, `web-jest`, `web-build`.

---

## ⚠️ ТИМЧАСОВІ / ВІДКЛАДЕНІ РІШЕННЯ

### 1. Feature-Flag Kill Switches for Payment/Refund Flows
- **Файли:**
  - `apps/web/lib/feature-flags.ts`
  - `infra/docker/docker-compose.prod.yml`
- **Статус:** `Implemented` (operational safeguard)
- **Примітка:** флоу увімкнені за замовчуванням; прапорці залишаються аварійним вимикачем.

### 2. Email Notifications for Refund Decisions
- **Файл:** `apps/api/app/services/refund_service.py`
- **Проблема:** TODO на email approve/reject ще не реалізований.
- **Статус:** `Deferred (Wave 2+)`
- **Пріоритет:** 🟡 MEDIUM
- **Оцінка:** 3-4h

### 3. External RAG APIs (Perplexity/Tavily/Serper)
- **Статус:** `Deferred (Wave 2+)`
- **Причина:** поза release scope “Operational MASTER compliance”.

### 4. Payment/Refund Manual UI Smoke (current cycle)
- **Статус:** `Deferred (current cycle scope)`
- **Причина:** зафіксоване рішення циклу — пропустити payment/refund browser smoke.
- **Наслідок:** фінальний статус лише `Conditional Go`, не `Strict Go`.

### 5. Stripe Mode Risk in Pre-Prod
- **Файли:**
  - `apps/api/.env`
  - `apps/web/.env.local`
- **Статус:** `Known risk`
- **Проблема:** live Stripe keys у pre-prod середовищі можуть спричинити реальні списання.
- **Рекомендація:** для smoke використовувати test keys.

---

## 🔴 GO-LIVE CHECKLIST (MUST PASS)

1. Staging/prod-like Docker stack healthy (`api`, `web`, `postgres`, `redis`, `minio`).
2. Runtime smoke pass:
- user login;
- admin login/logout;
- admin block/unblock/make-admin;
- generation flow;
- payment create/verify/history;
- refund create/list/detail;
- `GET /health` (API), `GET /api/health` (Web).
3. Manual UI smoke sign-off у браузері (release checklist).
4. Відсутність P0/P1 дефектів у логах і релізному репорті.

---

## 🧾 ENV FLAGS (KILL SWITCHES)

```bash
# user payment/refund flows (enabled by default)
NEXT_PUBLIC_ENABLE_USER_PAYMENT_FLOW=true
NEXT_PUBLIC_ENABLE_USER_REFUND_FLOW=true
```

Для аварійного вимкнення у runtime:

```bash
NEXT_PUBLIC_ENABLE_USER_PAYMENT_FLOW=false
NEXT_PUBLIC_ENABLE_USER_REFUND_FLOW=false
```

---

**Last Updated:** 24.02.2026
