Локальний запуск компіляції/тестів у цьому середовищі заблоковано дозволами, тому виконання лишається за primary. Звіт нижче.

## Діагноз (підтверджено логом і знімком БД)

Підготовка плану (`academic_plan_preparation`) один раз запитала повний outline із загальним лімітом 4000 вихідних токенів; відповідь обрізана `stop_reason=max_tokens` (receipt 32846/4000 received, оплачено). Успадкована `ModelResponseRecovery` подвоїла бюджет, але `AIService(max_retries=0)` не дав повторити запит. `IncompleteModelResponse` (підклас `ValueError`) через `AllProvidersFailedError` дійшов до `failure_reason` як `unknown_failure` → terminal, лише `new_version`. Рецензент не виносив вердикту. Калібрування з логу: ~48 с на 4000 токенів (≈80 ток/с), тобто валідна відповідь на 8000 токенів уже не вклалася б у зовнішні 90 с; heartbeat під hold чекав 32 с на row lock.

## Правки (лише apps/api)

- `services/model_response_recovery.py` — `IncompleteModelResponse(message, *, budget_exhausted=False)`; `validate` позначає обрізання саме на стелі моделі (сумісно зі старими викликами).
- `services/generation_operations.py` — `operation_output_budget` ContextVar (без нових обов'язкових аргументів у `_call_ai_provider`).
- `services/ai_service.py` — `call_with_fallback(..., output_tokens=None)` виставляє бюджет у ContextVar; `_call_openai/_call_anthropic` беруть перший бюджет звідти, обрізаний стелею моделі; поведінка без бюджету незмінна (4000/8000).
- `services/generation_outcomes.py` — `IncompleteModelResponse`: вичерпана стеля → `review_input_invalid` (review) / `unknown_failure` (інше); не вичерпана (порожня/обрізана нижче стелі) → `*_temporarily_unavailable`. Ніколи не академічний вердикт.
- `services/retry_strategy.py` — обрізання на стелі не повторюється з тим самим лімітом (жодної оплати того ж обрізаного тексту двічі).
- `services/plan_preparation.py` — бюджет виводу `min(стеля, max(8000, len(serialized outline)))` (для control 9: 9973 > 8000 > 4000); `AIService(max_retries=1)` = одна технічна повторна спроба тієї самої задачі зі збільшеним бюджетом; зовнішній `wait_for` = сума SDK-таймаутів обох обмежених запитів + 30 с (замість фіксованих 90 с); `PlanRejected` (валідний, але порушує структуру/вимоги → `plan_requirements_unmet`, status failed) відокремлено від `MalformedPlanResponse`/incomplete (technical, status unchecked, outcome `unusable`, `budget_exhausted` у payload); `_started` подія записує `output_budget`/`technical_retries`. Один змістовий reconciliation на worker-attempt збережено, пакет/секції не чіпаються, fallback провайдерів не додано.

## Тести (`tests/test_stability_plan_budget.py`, новий; не виконувались мною)

Реальний `AIService`/`RetryStrategy`/`ModelResponseRecovery` на синтетичному Anthropic-транспорті:
1. SDK-відповідь `max_tokens` → повторний запит того самого промпта і моделі з 16000 → completed; `max_retries=1`; receipts 4 (2 received) зі стадією `academic_plan_preparation`; журнал == tracker == сума usage; один `_started`; pack sha і заголовки незмінні.
2. Обрізання і на стелі → `review_input_invalid`, не academic/unknown, 2 виклики, outline незмінний, `budget_exhausted=True`.
3. Outline розміром ≥ стелі → бюджет 16000, після обрізання лише 1 виклик.
4. Порожня (×2) та malformed відповідь → `review_temporarily_unavailable`, `unusable`, обмежено.
5. Повний, але структурно порушений план → `plan_requirements_unmet`, status failed, без технічного повтору (1 виклик).
6. Форма control 9 (6 розділів, ~10k символів, синтетичні заголовки) → бюджет = довжина > 8000 > 4000; зовнішній wait ≥ сума SDK-таймаутів; попередні 90 с менші за SDK-таймаут першого запиту.
7. `failure_reason` для incomplete у різних стадіях і обгортці `AllProvidersFailedError`.

Команди для primary:
```
cd apps/api && pytest tests/test_stability_plan_budget.py tests/test_stability_preparation.py tests/test_model_response_recovery.py tests/test_stability_operations.py tests/test_stability_outcomes.py -q
cd apps/api && pytest -q && ruff check . && mypy app   # порівняти з базою 351
```

## Залишкові зауваження

- Hold job-row під час підготовки тепер може тривати довше за lease 120 с (верхня межа ≈ 990 с при бюджеті 8000; реально 1–3 хв). Перехоплення неможливе, поки рядок заблокований; на успіху hold поновлює lease. На невдачі довше 120 с lease не поновлюється, і результат записується наступним claim-циклом (без платного виклику для terminal-причин). Це існуюча властивість `hold_generation_job_lease`, я її не змінював.
- `run_academic_review` (outline/whole) лишається на 4000/90 с: вихід — короткий вердикт, але той самий клас можливий; не чіпав без відтвореного випадку.
- `ai_service.py` і `plan_preparation.py` входять у profile fingerprint: job 9 і будь-які queued задачі стануть `contract_or_profile_mismatch`; для document 9 потрібен явний `new_version`, історія job 9 (63904/58 центів, `unknown_failure`) не переписується.
- Не S4/agency PASS; жодної живої генерації не запускав.
