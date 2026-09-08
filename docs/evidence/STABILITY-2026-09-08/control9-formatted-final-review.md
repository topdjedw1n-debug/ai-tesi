## Підтверджую: APPROVED_FOR_S4_PREPARATION для точного маніфесту `control9-formatted-manifest.json` (коміт 061e2c3)

Що звірено (лише читанням, без команд):

- **Маніфест узгоджений.** 11 із 14 файлів мають ті самі SHA-256, що й у схваленому мною маніфесті. Три змінені файли мають `after_sha256` з `control9-hook-equivalence.json`: `generation_outcomes.py` 9ecd…, `plan_preparation.py` b93d5…, `test_stability_preparation_postgres.py` 5a38…. Web-байти незмінні.
- **`plan_preparation.py`** — перечитав функцію `prepare_final_plan` у закомічених байтах: логіка guard/зовнішнього очікування/класифікації ідентична схваленій; змінене лише перенесення вкладеного тернарного `"rejected" if … else "unusable" if … else "outcome_unknown"`. AST-еквівалентність, заявлена primary, збігається з тим, що я бачу.
- **`generation_outcomes.py`** — гілка `IncompleteModelResponse` у `failure_reason` та `retryability` в `outcome_fields` семантично ті самі; змінено лише обгортання дужками/переноси.
- **Тест (єдина не-AST зміна).** Рядок 415: `(finished,) = (e for e in events if e.event_type == PREPARATION)` замість списку. Для розпакування в один елемент генератор еквівалентний: 0 елементів → `ValueError` (not enough values), >1 → `ValueError` (too many values), тож сила твердження «рівно одна подія preparation» збережена. Модуль повторно виконано на реальному PostgreSQL: 3 passed, 4.33 с (`control9-post-hook-postgres.txt`).

Обмеження цього підтвердження: я не перераховував SHA-256 файлів у коміті самостійно (виконання команд у цій сесії заблоковано), тож збіг «байти коміту ↔ маніфест» спирається на записи primary; збіг «зміст ↔ схвалена логіка» перевірено мною безпосередньо. Попередні докази (1385/16 PG, web 213, QA-знімки) лишаються чинними на рівні поведінки.

Не production, не академічний і не agency PASS; новий платний контроль потребує окремої авторизації за §7. Раніше названі неблокуючі зауваження (retrying показує «0 с» до настання `available_at`, profile fingerprint робить чергу `contract_or_profile_mismatch` при встановленні, outline review ≤ 90 с під lease) не змінилися.
