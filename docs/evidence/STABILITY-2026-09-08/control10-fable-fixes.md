Code and tests are complete; nothing further depends on another tool result. Here is the report.

## Що знайдено в даних контролю 10 (до будь-яких правок)

**Виклик підготовки виконаний повністю, без обрізання.** Receipt `academic_plan_preparation`: один SDK-виклик, 32 940 вх./6 112 вих. токенів при бюджеті 10 153 (`_started.output_budget`), `received` з `msg_011CesMj…`. `IncompleteModelResponse` у лозі о 05:59 («Attempt 1/4») належить стадії `ai_service` (builder outline, 4000 → 4463 вих.), не підготовці. Отже потужність/бюджет не причина.

**Структура пройшла; відхилив `outline_problems`.** Причина відмови = перший елемент списку проблем, а це відредагована копія `academic_plan.conflicts[0]` збереженого плану (виправлена одруківка, додано «Le fonti frozen (Warren2012, Michel2017) supportano…» і «LIMITE DI EVIDENZA (permiss…»). Усі три збережені `conflicts` — це рішення про рамку, декларований ліміт доказів і відсутність джерела для 1.2–1.3, тобто не невиконані явні вимоги. `blocking_conflicts` у збереженому плані немає (планер пише лише legacy `conflicts`, `academic_context.py:74-75`).

**Що НЕ можна довести зі збережених даних:** у якому саме ключі відповіді був цей текст. Подія `academic_plan_preparation` зберігає лише `reason` = 500 символів з'єднаних проблем (перший елемент довший за 500), receipts зберігають лише дайджести. Гілки «модель поклала це у `blocking_conflicts`» і «модель поклала у `limitations`/лишила `conflicts`, а код упав у fallback» нерозрізненні. Тому я не стверджую ні справжньої академічної відмови, ні її відсутності.

**Що доведено кодом, незалежно від відповіді:** `academic_review.py:58` `plan.get("blocking_conflicts") or plan.get("conflicts") or []` — явний порожній авторитетний список `[]` через `or` провалюється в legacy `conflicts`. Промпт вимагає «Return the complete outline JSON» і «Keep … all structural fields EXACTLY», але нічого не каже про `conflicts`. Модель, що ідеально виконала контракт S1 (усе відсортовано в `limitations`, `blocking_conflicts: []`) і повернула повний JSON із `conflicts`, гарантовано отримувала `plan_requirements_unmet`. Це порушення контракту S1 (план §4 п.3: структурна перевірка = відсутні ключі/функції; допустимість обмежень = семантична перевірка; §5: `limitations` окремо від `blocking_conflicts`). Наявний тест `test_pruned_keys_and_permissible_limit…` проходив лише тому, що його `valid` не містив `conflicts`.

## Правки (лише `apps/api`)

1. **`app/services/academic_review.py`** — новий `plan_conflicts(plan)`: `blocking_conflicts` як список → авторитетний (порожній = немає невиконаних вимог); відсутній/`None` → консервативний fallback на legacy `conflicts` (рядок → один елемент); будь-який інший тип (`"nessuno"`, dict, `0`, `""`) → одна проблема «має бути списком», без примусу до «порожньо»; елементи не-рядки → `str()`, не губляться. `outline_problems` використовує його; решта перевірок (RQ/objectives, evidence_keys ⊆ pack, покриття функцій, секційні `blocking_conflicts`) без змін.
2. **`app/services/plan_preparation.py`** — промпт: три речення, що `blocking_conflicts` авторитетний, `limitations` — окремо, а `academic_plan.conflicts` — вхід для сортування, який треба опустити; «Do not erase conflicts merely to pass» збережено. Плюс `rejection_evidence()`: на `PlanRejected` у подію додається `rejection` = повний список проблем (≤20 × ≤1000 симв.), `problem_count`, `response_sha256` і поля `blocking_conflicts`/`limitations`/`conflicts` з відповіді (обмежені); промпт і план цілком не зберігаються. Retry/spend/lease/guard логіку не чіпав.
3. **`tests/test_stability_plan_conflicts.py`** (новий, SQLite): контракт `plan_conflicts` (8 позитивних/консервативних кейсів + 5 типів без списку); форма контролю 10 з legacy-списком і без нього → `completed`, титули незмінні, рецензент викликається і вирішує; справжня невиконана вимога (>500 симв.) → `plan_requirements_unmet`, повторно без виклику, `rejection` містить повний текст і поля; неправильний тип → відхилено, не стерто; порожній `blocking_conflicts` не послаблює титули/ключі/функції; межі доказу.

## Межі та ризики

- Обидва файли входять у `PROMPT_FILES` → profile fingerprint зміниться; job 10 і так terminal (`retryability: none`), потрібен `new_version`. Черга при встановленні має бути нульова.
- Семантичний рецензент тепер бачить план із `limitations` і (можливо) `conflicts`; він, а не структурна перевірка, судить допустимість — це і є контракт S1. Ярлик моделі не скасовує реальну вимогу, але доказом слугуватиме вердикт рецензента, не `outline_problems`.
- Планер і далі пише legacy `conflicts`; я не змінював його промпт (ширший обсяг).
- Не production, не академічний і не agency PASS; жодного платного виклику.

Команди для primary:
```
cd apps/api && pytest tests/test_stability_plan_conflicts.py tests/test_stability_preparation.py tests/test_stability_plan_budget.py tests/test_academic_quality.py tests/test_academic_quality_pipeline.py -q
cd apps/api && pytest -q && ruff check . && mypy app
```
