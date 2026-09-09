Виконано лише A+C у двох дозволених файлах. Статус: **NOT READY_FOR_LIVE** — офлайн-тести зелені, але це не доказ поведінки живої моделі і не закриває доказову прогалину.

## Змінені файли

**`apps/api/app/services/plan_preparation.py`** (+108/−14 після pinned Black 23.12.1 / Ruff 0.1.8 з кешу pre-commit)
- **A.** `PlanRejected(message, *, detail)`; `_structure(kind, field, section_index, before, after)` з `_bounded` (≤1000 симв./елемент, ≤20 елементів, `None` лишається `None`). `reconcile_outline` віддає точний `detail`: `section_count` (before/after кількість), `section_title` (індекс, обидва заголовки), `section_field` (індекс, ключ, before/after; для доданого ключа before=`None`), `top_field`. Повідомлення містять індекс і ключ («…структуру розділу 2: поле 'subsections'»). `rejection_evidence(..., structure=)` додає `rejection.structure` лише за структурної відмови; ціла відповідь не логується. Оригінальний outline не мутується.
- **C.** Промпт вимагає лише `{"academic_plan": {research_question, objectives, limitations, blocking_conflicts}, "sections": [{exact title + main_points/academic_functions/evidence_keys/limitations/blocking_conflicts}]}` і прямо забороняє повертати `subsections/estimated_words/key_concepts`. Сервер зливає: незмінні секційні поля — з оригіналу; `academic_plan` — merge поверх оригінального (пропущені ключі зберігаються; legacy `conflicts` викидається **лише** якщо відповідь дала список `blocking_conflicts`, інакше лишається і блокує консервативно); не-dict `academic_plan` → `MalformedPlanResponse`. Повне echo сумісне; будь-яке повторене незмінне поле з іншим значенням, доданий ключ секції, змінені кількість/порядок/заголовок або сторонній top-level ключ — відмова. Бюджет виходу, retry, lease guard, облік, заморожений пакет не змінені (бюджет усе ще рахується від збереженого outline — тест це фіксує).

**`apps/api/tests/test_stability_plan_structure.py`** (новий, 18 кейсів): sparse-злиття зі збереженням subsections/estimated_words/key_concepts і `scope_note`; повне echo сумісне; sparse без `blocking_conflicts` зберігає legacy `conflicts`; 7 параметризованих відмов (subsections/estimated_words/key_concepts/новий ключ/порядок/кількість/top-level) з точним `detail`; межі evidence; `SECTION_FIELDS` зафіксовані; персистована відмова через `prepare_final_plan` (`rejection.structure` = kind/section_index 2/field/before/after, повторний виклик без моделі); **справжній `blocking_conflicts` відхиляє структурно валідну sparse-відповідь** без `structure`.

## Виконані перевірки (офлайн, без ключів/мережі)
```
pytest test_stability_plan_structure/plan_conflicts/preparation/plan_budget/preparation_postgres/academic_quality → 100 passed, 3 skipped (PG без M0_03_TEST_DATABASE_URL)
ruff (venv 0.14.7 і pinned 0.1.8) → clean; black 23.12.1 (pinned) застосовано; mypy → 0 діагностик у plan_preparation.py (100 наявних в інших 14 файлах)
```

## Що ця корекція НЕ доводить
- Що Opus 4.8 повертає sparse-формат і не повторює/не змінює незмінні поля — fixture синтетичний. Contract-розбіжність тепер дасть точний `structure`, але не гарантує проходження.
- Що заморожений пакет покриває вимоги брифу. Контроль 11: 0 джерел з термоорегуляцією/гіпотермією, 0 з NANDA/NOC/NIC; sparse-контракт цього не змінює — блокер лишається законним.
- Що семантичний рецензент пройде: він жодного разу не запускався на цьому брифі.

## Конкретні блокери до будь-якого платного контролю (з інспектованого коду)
1. `source_pack._build_queries` (744-774) — запити лише topic + заголовки розділів; `_ALT_TITLE_QUERY_CAP=4` (40/556) відрізає Cap.4/Conclusioni англійською; підрозділи/key_concepts не запитуються. Це окремий scope root; тут не чіпав.
2. `source_pack_preflight.needs_top_up` (48-49) зупиняє пошук за лічильником (24 verified = target), не за покриттям розділів.
3. `_on_topic_score` (802-841) без домен-гейту для перинатальної теми; примітка primary слушна: OR-гейт з `nurs*/infermier*` не відсіє Rolle/Zulu — потрібен перинатальний/неонатальний anchor і вимір до/після на фактичних 32 персистованих рядках (не 48 сирих кандидатах).
4. Планер будує `evidence_keys` на джерелах без абстрактів (усі 7 ключів №11 відкинуті preflight) — узгодження їх переписує, але план змістовно спирався на неіснуючі докази.

## Потрібне full-scenario доказування перед новим платним запуском
Офлайн-прогін точного брифу №11 крізь весь конвеєр (пакет → preflight → підготовка → рецензент → писар → DOCX) на записаних/контрольованих зовнішніх відповідях, включно з: (a) replay 32 фактичних рядків №11 через новий добір із виміряним before/after; (b) sparse-відповідь у формі, яку реально дає модель (хоча б одна збережена справжня відповідь підготовки; наявні лише дайджести); (c) явний негативний шлях `source_coverage_gap` для NANDA-I/NOC/NIC, якщо абстрактної літератури немає, з рішенням менеджера про uploaded-джерела. Без (a)–(c) черговий платний контроль знову перевірятиме гіпотези за гроші.