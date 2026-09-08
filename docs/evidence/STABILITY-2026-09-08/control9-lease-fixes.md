Готово. Правки внесені лише в `apps/api` (2 сервісні файли + 1 новий тестовий файл); harness, evidence, доки та попередню шести-файлову правку бюджету не чіпав.

## Діагноз, підтверджений кодом

У `background_jobs.py:2063-2084` `prepare_final_plan` і `run_academic_review` обидва виконувалися всередині `hold_generation_job_lease`, який тримає `SELECT … FOR UPDATE` на рядку Job в окремому з'єднанні на весь час зовнішнього виклику. `renew_generation_lease` (heartbeat) і `cancel_active_generation_job` беруть той самий рядок, тому чекали позаду провайдера. Після мого попереднього збільшення зовнішнього wait до суми SDK-таймаутів це блокування могло тривати до ~20 хв.

## Правки

**`apps/api/app/services/plan_preparation.py`**
- Новий необов'язковий параметр `persist_guard: PersistGuard | None` (`Callable[[], AbstractAsyncContextManager]`). Без нього — `_unguarded` (no-op), тож наявні тести й прямі виклики не змінюються.
- Guard тепер обгортає **лише** тривкі записи: (1) подія `_started`; (2) фінальна подія `completed`/`unchecked`/`failed` разом із записом `document.outline`. Зовнішній `wait_for(call_with_fallback)` виконується **поза** guard — рядок Job вільний.
- Класифікація помилки (`plan_requirements_unmet` / `review_temporarily_unavailable` / `failure_reason`, `budget_exhausted`) не змінена, але виняток тепер зберігається у `failure` і піднімається після guarded-запису. Якщо lease втрачено (cancel / takeover / expiry), guard кидає `GenerationLeaseLostError` **до** будь-якого запису: пізній результат не торкається outline, не додає події спроби, `raise failure` не відбувається.
- Receipts `generation_provider_attempt` пишуться SDK-обгорткою в окремій сесії, як і раніше, тому фактична витрата фіксується навіть після cancel.

**`apps/api/app/services/background_jobs.py`** (блок ~2062-2099)
- `prepare_final_plan(..., persist_guard=functools.partial(hold_generation_job_lease, job_id=…, worker_id=…, lease_token=…, document_id=…))` — без зовнішнього `async with`.
- `validate_outline` винесено з-під guard (чиста функція).
- `run_academic_review(kind="outline")` лишається у своєму окремому `hold_generation_job_lease` з незмінним bounded-таймаутом ≤ 90 с. `finally: write_job_usage(db)` без змін.
- Глобальний lease, fencing, writer/модель, семантичні та release-гейти не чіпав.

## Тести: `apps/api/tests/test_stability_preparation_postgres.py` (новий, opt-in через `M0_03_TEST_DATABASE_URL`, fixture `postgres` з `test_release_evidence_postgres`)

Сід: документ/пакет з `example()`, реальний `User`, `AIGenerationJob` з коректними `profile_sha256`/`generation_contract_sha256`, реальний `claim_next_generation_job("worker-a")`, pruned-ключ змушує викликати модель. Стадія запускається у власній сесії з `hold_generation_job_lease` як guard — точно як воркер.

1. **Cancel + heartbeat під час утримуваного виклику** (реальний `AIService` на синтетичному Anthropic-транспорті, відповідь чекає на `release`): `renew_generation_lease` повертає True і `heartbeat_at`/`lease_expires_at` зростають, поки відповідь висить; `cancel_active_generation_job` завершується за < 5 с при неопущеному провайдері; після release задача кидає `GenerationLeaseLostError`; job `cancelled`, document `failed`, `digest(outline)` незмінний, секцій 0, події `academic_plan_preparation` немає, `_started` одна; receipts `started`/`received` є, `journal_usage` = 32846+5200, unknown 0.
2. **Takeover + пізня невдача**: lease прострочується під час очікування, `worker-b` перехоплює (attempt 2); пізній `TimeoutError` старої спроби → `GenerationLeaseLostError`, події не додано, lease нового власника байт-у-байт незмінний; новий власник виконує узгодження заново на тих самих незмінних входах → `completed`, `worker_attempt` 2, guard поновив lease.
3. **Затримана невдача під живим lease**: lease штучно скорочено до 2 с, heartbeat поновлює його поза блокуванням; пізня malformed-відповідь → `GenerationStageError(review_temporarily_unavailable)`, подія `unchecked`/`unusable` записана, owner/token незмінні, expiry ≥ поновленого, receipts + журнал 32846+40.

Команди для primary:
```
cd apps/api && M0_03_TEST_DATABASE_URL=… pytest tests/test_stability_preparation_postgres.py -q
cd apps/api && pytest tests/test_stability_plan_budget.py tests/test_stability_preparation.py tests/test_stability_postgres.py tests/test_generation_cancel.py tests/test_citation_pipeline_integration.py -q
cd apps/api && pytest -q && ruff check . && mypy app
node ../harness/preparation-cancel-replay.cjs   # очікую cancelled_while_provider_waiting=true, heartbeat_advanced=true, outline_sha незмінний
```

## Залишкові зауваження

- Тести я не запускав (без Bash). Найімовірніші місця збою, якщо будуть: сід на PostgreSQL з явним `Document.id=71` і FK на користувача (я створюю `User` і підставляю `user_id`), та порівняння aware-datetime з PG.
- `run_academic_review` (outline) і далі тримає рядок Job до 90 с — свідомо не чіпав, як домовлено. Той самий клас проблеми там можливий лише в межах 90 с.
- `plan_preparation.py` і `background_jobs.py` входять у profile fingerprint (як і в попередній правці): усі queued/running задачі стануть `contract_or_profile_mismatch`, для document 9 потрібен `new_version`.
- У воркері після lease-loss `finally: write_job_usage(db)` є fenced no-op, а зовнішній handler робить `write_job_usage_monotonic` — це наявна логіка, її достатньо; receipts і так фіксують витрату.
- Doc-рядок `hold_generation_job_lease` і `docs/plans/THESICA-STABILITY-EXECUTION.md` не оновлював — це за primary.
- Не S4/agency PASS; живих викликів не було.
