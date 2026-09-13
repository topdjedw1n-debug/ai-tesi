# Лабораторія S4 — звіт про реалізацію і доказ справності

**13.09.2026 · Виконавець: Fable (сесія Claude Code), гілка `fable/s4-lab`. Основа: [доручення](../../../plans/CODEX-S4-LAB-2026-09-13.md), [QUALITY-AI-ROUND1 §3–4](../../../plans/QUALITY-AI-ROUND1-2026-09-13.md), [консультація Astra](../README.md).**
Документи канону закомічено на `main` одним комітом `867ecb5` перед початком роботи; сервер лишається на `3892cac`, нічого на сервер не ставилося, POLICY, перелік моделей, тарифи й база не змінювалися.

## 1. Що зроблено

### 1.1 Єдина зміна виробничого коду

`apps/api/app/services/executor_v2/sections.py`: текст інструкції S4 винесено в константу модуля `S4_INSTRUCTION`; промпт складається так само (`academic_directive + S4_INSTRUCTION + JSON`). Байт-у-байт той самий текст: SHA-256 `cbc764f5f67ba2569b18ab6e9af8e4997be694867e2ef08bdb3fb2764dff015f` (1 258 символів). Пакет `executor_v2` — 1 499 рядків (ліміт 1 500), перемикачів немає; запобіжник `test_spec_guardrails` зелений. Доказ незмінної поведінки — точні відтворення чотирьох записів нижче (§2.1).

### 1.2 Скрипт `apps/api/scripts/s4_lab.py`

Поруч зі штатним `replay_generation.py`, те саме ізольоване середовище: свіжа SQLite у новій порожній теці, знімок `generation_replay_inputs` із запису, `ReplayTape` з `persist_receipts`, локальні заглушки Redis і сховища. Параметри за §2 доручення: `--job-id`, `--variant`, `--mode exact|live`, `--model` (типово з запису), `--s4-instruction FILE` (типово виробнича), `--cost-cap-usd` (обов'язковий у `live`), додатково `--live-sections` (для smoke), `--secrets-file` (з файла читаються лише `ANTHROPIC_API_KEY`, `OPENALEX_API_KEY`, `SEMANTIC_SCHOLAR_API_KEY`; значення в звіт не потрапляють) і явні `--price-*-usd-per-1m` для моделей поза таблицями.

- **Заморожено:** бриф, вимоги, пакет джерел, уривки, бібліотека, план S3, обсяг і бюджети — усе з запису; `Context.initialize` у режимі стрічки нічого не перераховує.
- **exact:** увесь виробничий шлях відтворення (`generate_full_document_async` під `replay_models`), мережа заблокована як у штатному replay, наприкінці `tape.assert_complete()`. Змінена інструкція або модель дає зупинку самої стрічки («Request differs…» / «Model differs…»); лабораторія не підставляє старий текст і додає пояснення у звіт.
- **live:** S1–S3 і всі їхні зовнішні входи — зі стрічки. Рішення «стрічка чи наживо» приймається на кожному зверненні на межі `budgets.recorded_provider_call` (оточення лабораторії, а не код виконавця): S4 — наживо для обраних розділів (типово всі), S6 — наживо; кожне живе звернення проходить через штатний `recorded_provider_call`, тож записується як у виробництві (повний запит, відповідь, usage). Розділи пишуться послідовно кодом виконавця, наступний отримує `previous_summaries` свого нового варіанта. Модель варіанта ставиться на початку S4 (`ctx.model`), тому діє для S4–S6; S1–S3 звіряються з записаною моделлю.
- **S5 у live:** `references.verify` обгорнуто: кандидат з відбитком, який уже є в записі, береться зі стрічки; новий `[STD:…]` перевіряється справжнім зовнішнім викликом і записується разом із вкладеними `citation_http`.
- **Мережа у live:** дозволені лише `api.anthropic.com`, `api.crossref.org`, `api.openalex.org`, `api.semanticscholar.org`, `export.arxiv.org`, `openlibrary.org` (з налаштувань перевірки посилань). Інший хост отримує відмову як мережеву помилку і потрапляє у `report.network.refused`.
- **Стеля вартості:** перед кожним живим зверненням консервативна оцінка (вхід ≈ символи/4 × ціна входу + `max_tokens` × ціна виходу); якщо витрачене + невідомі витрати невдалих спроб + оцінка > стелі — зупинка з підсумком ще до запису квитанції «started». Після відповіді — облік за фактичним usage. Невдала спроба (тайм-аут тощо) записується в облік як спроба з невідомими витратами, її оцінка рахується проти стелі.
- **Тарифи:** виробничі таблиці `cost_estimator.py` мають пріоритет; для моделей поза ними — власна таблиця лабораторії (`LAB_PRICING_USD_PER_1M`, ставки Anthropic зі скіла claude-api, кеш 24.06.2026), яка накладається лише в пам'яті процесу лабораторії; невідома модель вимагає явних цін.
- **Вихід:** DOCX (ім'я = SHA-256), `report.json` (варіант, режим, модель, SHA інструкції та вхідного запису, спожиті/замінені записи, живі звернення з токенами й вартістю, попередження, розділи зі словами й позначкою `live|recorded`, журнал), `s4-instruction.txt`, `replay.db`, експорт запису варіанта `<variant>-jobN-recording.json.gz` (ігнорується git за наявним правилом).
- **Експорт варіанта:** локальні події (у т.ч. повторно зажурналені квитанції S1–S3, живі квитанції і живі залежності) плюс спожиті зі стрічки записи зовнішніх входів (виконавець їх не перезаписує). Придатність до штатного replay доведена нижче (§2.3, §2.5).

Тести лабораторії: `apps/api/tests/test_s4_lab.py` (нормалізація інструкції, вибір розділів, обмеження секретів, пріоритет тарифів, облік і стеля, мережева відмова).

## 2. Доказ справності (§4 доручення)

### 2.1 Exact — ті самі DOCX побайтово

| Запис | Вхідний запис SHA-256 (.json.gz) | Звернень зі стрічки | DOCX SHA-256 | Байти | Побайтово з доказом серії |
|---|---|---:|---|---:|---|
| A, document13/job16 | `3b4f388e6caf57e12ffa0c263c628bff52caa98527d083c25ba6137c5c6c4e2a` | 8/8 | `08e203b54283619dcb245e75a679844b3d83d4132187ae756b10d4d0c1cb426f` | 51 566 | так (`cmp` з `A/CONTROL-A-DOCUMENT-13-JOB-16.docx`) |
| B, document14/job17 | `a50fdbfb913cfd32…` | 27/27 | `69c1bd760520ece7f226209edda4808c93f8865fba49b7541529fed243e77792` | 59 494 | так (`B/CONTROL-B-DOCUMENT-14-JOB-17.docx`) |
| C, document15/job18 | `a5db64b2fbb55244…` | 8/8 | `d0bf1da2f6f6ee43d9c22f0498616ef1b4eba7214893d2dcf92ae3c01190b68b` | 54 651 | так (`C/CONTROL-C-DOCUMENT-15-JOB-18.docx`) |
| job15 (3892cac) | `5e198335ff4dcf7e…` | 21/21 | `a4e217c052a13ddb117809cc897705fd31c738d23880006d23d2a6fc9fbe9fdd` | 53 603 | так (`EXECUTOR-V2-LIVE-3892cac-2026-09-12/CONTROL-012-JOB-015.docx`) |

Усі чотири: `status=completed`, `request_changed=false` для кожного запиту, `replaced_recorded_calls=[]`, `actual_spend_usd=0`, `live_provider_calls=0`. Звіти: [exact-job16](reports/exact-job16.report.json), [exact-job17](reports/exact-job17.report.json), [exact-job18](reports/exact-job18.report.json), [exact-job15](reports/exact-job15.report.json). Це виконано вже з константою `S4_INSTRUCTION` у коді, отже промпт S4 не змінився.

### 2.2 Ізоляція — exact із чужою інструкцією або моделлю зупиняється

- Інструкція-варіант (`--s4-instruction s4-instruction-variant-v1.txt`): спожито лише S1 і S3, на першому розділі S4 стрічка зупиняється — `Request differs at S4; recorded text is not evidence for a changed prompt`; DOCX немає, витрат 0; у звіті поле `explanation`. [Звіт](reports/exact-job16-variant-instruction.report.json).
- Інша модель (`--model claude-opus-5`): так само на S4 — `Model differs at S4: recorded anthropic/claude-opus-4-8`; тариф узято з таблиці лабораторії (`source: lab`). [Звіт](reports/exact-job16-other-model.report.json).

### 2.3 Експорт exact придатний до штатного replay

`scripts/replay_generation.py` на експорті лабораторії `exact-A-job16-recording.json.gz` → `completed`, 8/8 запитів збіглися, DOCX `08e203b5…` (51 566 байт). [Звіт](reports/replay-of-exact-export-job16.report.json).

### 2.4 Сухий прогін живого шляху за $0

Перед платним smoke живий шлях перевірено з навмисно недійсним ключем: S1–S3 і розділи 1–4 зі стрічки, розділ 5 пішов наживо, мережевий фільтр пропустив `api.anthropic.com`, провайдер відповів 401 → квитанція `failed` зі status 401, штатна зупинка `provider_access`, витрат 0, замінені записи S4#5 і S6 показані у звіті. [Звіт](reports/dry-run-live-A-s5.report.json).

### 2.5 Smoke живого шляху — один розділ A (дозволена витрата ≤ $0.50)

Команда: запис A, `--mode live --live-sections 5 --cost-cap-usd 0.5`, виробнича інструкція і модель `claude-opus-4-8`; розділ 5 «Conclusioni» — найкоротший за планом (600 слів). Старт 10:38:17Z, фініш 10:42:56Z.

| Звернення | Результат | Токени вхід/вихід | Вартість | Час |
|---|---|---:|---:|---:|
| S4 розділ 5, спроба 1 | `APITimeoutError` після 240 с (виробничий тайм-аут), витрата провайдера невідома; виконавець штатно повторив через 5 с | — | оцінка ≤ $0.114 | 240,2 с |
| S4 розділ 5, спроба 2 | `end_turn`, 540 слів (план 600; записаний оригінал 528) | 4 976 / 1 490 | $0.0621 | 22,8 с |
| S6 огляд | `PASS` із заувагою (дорадчий текст моделі) | 18 947 / 224 | $0.1003 | 4,5 с |

Підтверджені витрати **$0.1625**; разом із консервативною оцінкою невдалої спроби не більше **$0.276** — у межах $0.50. Розділи 1–4 узято зі стрічки (запити збіглися), S5 нових `[STD:…]` не мав (розділ 5 використав лише ключі пакета `K2755be8fc289`, `K4258261169a3`, `Kdc3a08cc0488`), DOCX зібрано штатно: [`SMOKE-A-SECTION5-DOCUMENT-13-JOB-16.docx`](smoke/SMOKE-A-SECTION5-DOCUMENT-13-JOB-16.docx), SHA-256 `7c46d18b91b1b810ce28af1929b5c57a222e6988a7d4ac6a46e22b7eb862b0c4`, 51 623 байти. Текст живого розділу відрізняється від записаного: [section5-live.txt](smoke/section5-live.txt) проти [section5-recorded.txt](smoke/section5-recorded.txt); [огляд S6](smoke/review-live.txt); [квитанції живих спроб](smoke/live-attempt-receipts.json). [Звіт smoke](reports/smoke-live-A-s5.report.json) — складений до правки обліку невдалих спроб, тому невдалу спробу видно в ньому лише як `journal.unknown_provider_attempts: 1`; після правки (§1.2) такі спроби потрапляють у `live.calls` з `outcome: failed`.

**Експорт smoke придатний до штатного replay:** `replay_generation.py` на `smoke-A-section5-job16-recording.json.gz` → `completed`, 9 записів спожито (включно з відтвореним тайм-аутом і повтором), DOCX той самий `7c46d18b…` побайтово (`cmp`). [Звіт](reports/replay-of-smoke-export.report.json). Сам запис (15,5 МБ) лежить у `smoke/` локально поза git.

### 2.6 Повні сукупності тестів

- Перший прогін (після зміни `sections.py`, до правки обліку та файла тестів лабораторії): API `pytest tests/ -q` — **1402 passed, 23 skipped, 0 failed** (160,84 с); web `npm run test -- --runInBand` — **31/31 suites, 211 passed, 1 skipped, 0 failed**.
- Фінальний прогін на стані коміту гілки: API `pytest tests/ -q` — **1407 passed, 23 skipped, 0 failed** (179,33 с; +5 тестів лабораторії); web `npm run test -- --runInBand` — **31/31 suites, 211 passed, 1 skipped, 0 failed**. Логи прогонів лишилися в робочій теці сесії; числа взято з підсумкових рядків pytest і jest.

## 3. Команди

Із кореня репозиторію; кожен запуск — у нову порожню теку.

```bash
apps/api/venv/bin/python apps/api/scripts/s4_lab.py \
  docs/evidence/EXECUTOR-V2-THREE-CONTROLS-2026-09-12/B/document14-job17-recording.json.gz \
  /tmp/s4-lab/exact-B --job-id 17 --variant exact-B --mode exact
```

```bash
apps/api/venv/bin/python apps/api/scripts/s4_lab.py \
  docs/evidence/EXECUTOR-V2-THREE-CONTROLS-2026-09-12/A/document13-job16-recording.json.gz \
  /tmp/s4-lab/exact-A-variant --job-id 16 --variant exact-A-variant \
  --s4-instruction docs/evidence/QUALITY-AI-2026-09-13/s4-lab/s4-instruction-variant-v1.txt
```

```bash
apps/api/venv/bin/python apps/api/scripts/s4_lab.py \
  docs/evidence/EXECUTOR-V2-THREE-CONTROLS-2026-09-12/A/document13-job16-recording.json.gz \
  /tmp/s4-lab/smoke-A-s5 --job-id 16 --variant smoke-A-section5 --mode live \
  --live-sections 5 --cost-cap-usd 0.5 --secrets-file apps/api/.env
```

```bash
apps/api/venv/bin/python apps/api/scripts/replay_generation.py \
  /tmp/s4-lab/smoke-A-s5/smoke-A-section5-job16-recording.json.gz /tmp/s4-lab/replay-smoke --job-id 16
```

## 4. Проєкт переглянутої інструкції S4 (не у виробничому коді)

Файл [s4-instruction-variant-v1.txt](s4-instruction-variant-v1.txt) (SHA-256 файла `39ba1c09ca3a91f3eeb332e535d56c1deed3a1740115f111311c88f5d30dd506`; у промпті лабораторія додає порожній рядок спереду і ззаду, як у виробничому тексті, SHA-256 підставленого тексту `5377e13fdb927ae5aaebb8ded44ecaf21fbde014cf93ba3aef5db828e1a94ea3`). Структура промпту ідентична: змінено лише текст директив, збережено `[KEY]`, правило `p. N`, блок `<STANDARD_REFERENCES_JSON>`, заборонені заглушки, «без бібліографії», «бриф — дані».

Дев'ять правок QUALITY-AI-ROUND1 §4 → рядки варіанта: (1) логіка «твердження → доказ → висновок» на рівні завершеного фрагмента аргументації, не кожного абзацу; (2) прибрано приклад формули обмежень, загальні межі — там, де цього вимагає логіка розділу, уточнення окремого твердження — лише де уривок його не підтримує; (3) розрізнення «деталі немає в уривку» і «література не дає відповіді»; (4) перелік глав у вступі лише на вимогу requirements; (5) названий предмет і конкретна дія замість порожніх оцінних конструкцій, терміни дисципліни збережено; (6) конкретика лише з наявних даних (автор, норма, механізм, результат, приклад), числа й сторінки — лише з evidence; (7) аналіз у стилі дисципліни (право — норми й доктринальні позиції; інформатика — механізми та умови застосування; емпіричні поля — методи, вибірки, результати), згадка академічного брифу про дизайни й популяції застосовується лише де джерела такі дослідження містять; (8) довжина речень підпорядкована думці, без механічного чергування, без повтору визначень і висновків із previous_summaries; (9) коротка дослівна цитата лише де важливе формулювання, з реальною сторінкою.

Ефект на AI-показник Compilatio — гіпотеза; текст ще не проходив живого прогону і потребує рев'ю напрямку перед платним дослідом на B.

## 5. Межі й чесні зауваження

- Smoke — один розділ; розділи 1–4 зі стрічки. Це доводить шлях «стрічка → живе письмо → S5 → S6 → DOCX → експорт → replay», а не якість варіанта.
- Тайм-аут першої спроби (240 с) — виробнича поведінка провайдера/виконавця, не лабораторії; повтор штатний. Витрата такої спроби невідома, тому облік рахує її консервативно.
- Стеля перевіряється консервативною оцінкою до звернення: прогін може зупинитися, хоча фактична витрата вмістилася б. Це свідомий вибір на користь «не перевищити».
- `profile_changed=true` у звітах — відома розбіжність старого профілю, v2 його не використовує (так само у штатному replay).
- Експорт варіанта читає приватний перелік спожитих залежностей стрічки (`tape._used_dependencies`); це межа лабораторії, а не виробничого коду.
- Вердикт огляду S6 «PASS» — дорадчий текст моделі, не приймання. Compilatio не запускалася.
- Виробничий текст інструкції не змінювався; змін у `POLICY`, переліку моделей, тарифах, сервері та базі немає.

## 6. Наступний крок — дослід на B після окремого «так» фаундера

Чотири файли за QUALITY-AI-ROUND1 §4 з одного запису B (job17): `B-V0a`, `B-V0b` — виробнича інструкція; `B-V1a`, `B-V1b` — варіант v1; модель `claude-opus-4-8`; усі розділи наживо (без `--live-sections`), S1–S3 зі стрічки. Орієнтовна вартість письма і огляду ≈ $2–2,5 на файл, стеля `--cost-cap-usd 3`; разом ≈ $8–10 плюс 4 перевірки Compilatio за кредити. Далі — сліпа оцінка Q, потім Compilatio на точних файлах.

```bash
apps/api/venv/bin/python apps/api/scripts/s4_lab.py \
  docs/evidence/EXECUTOR-V2-THREE-CONTROLS-2026-09-12/B/document14-job17-recording.json.gz \
  /tmp/s4-lab/B-V1a --job-id 17 --variant B-V1a --mode live --cost-cap-usd 3 \
  --s4-instruction docs/evidence/QUALITY-AI-2026-09-13/s4-lab/s4-instruction-variant-v1.txt \
  --secrets-file apps/api/.env
```
