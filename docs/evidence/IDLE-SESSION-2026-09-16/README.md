# Сесія простою 16.09.2026 — виконання плану перед першим живим замовленням

Підстава: [план сесії, редакція 3](../../plans/IDLE-SESSION-2026-09-16.md) (затверджений Astra і Grok, консультації [№7](../QUALITY-AI-2026-09-13/step2-full-inputs/consult7-2026-09-16/README.md) і [№7b](../QUALITY-AI-2026-09-13/step2-full-inputs/consult7b-2026-09-16/README.md)). Виконавець — Fable. Без генерацій, сканів і лабораторних прогонів; кожен пункт — окремий коміт.

## Пункт 1 — правові посилання й хибна заглушка

**Що змінено.**

- `app/services/citation_render.py`. `legal_label`: дужка офіційної назви — «(UE) 2016/679» (також CE/CEE/EU/EC/Euratom перед числом) — не примітка; обрізання, як і раніше, на першій примітці («(Statuto dei lavoratori)», «(GDPR)»), «, testo vigente» прибирається. Нова `legal_citation(label, title, locator)` для локатора статті на правовому джерелі: (а) та сама стаття, що в назві акта («…, n. 151, art. 23» + «art. 23, comma 1») — одне посилання «(…, n. 151, art. 23, comma 1)»; (б) стаття зміненого акта, названа в дужці назви «(Modifiche all'articolo 4 della legge 20 maggio 1970, n. 300)», — «(Legge 20 maggio 1970, n. 300, art. 4, comma 1, come modificato dall'art. 23, Decreto legislativo 14 settembre 2015, n. 151)»; (в) будь-яке інше поєднання лишається як написано («…, art. 23, art. 171») — друге «art.» не видаляється механічно. Сторінковий локатор для актів не показується (без змін). Бібліографія — повні назви менеджера (без змін).
- `app/services/placeholder_notes.py` (новий помічник поза пакетом виконавця; `executor_v2/assemble.py` викликає його, пакет 1 490 рядків). «da verificare» / «soggetta a verifica» — заглушка лише як (1) нотатка про матеріал: іменник materia / manuali / manualistica / linee guida / fonte(i) / dati / riferimenti / citazioni / bibliografia / letteratura / testo(i) / documento(i) / standard не далі ніж за два слова перед фразою; або (2) самостійний фрагмент між розділовими знаками чи в дужках («Da verificare.», «[da verificare]», «(da verificare)»). «[citation needed]» і «TODO» — точний збіг із межами слова, як і раніше. Перелік фраз у `POLICY["placeholder_phrases"]` і підказка писарю не змінені.

**Докази.**

- Тести: `tests/test_citation_render.py` (+2: назва з дужкою; локатори на актах із власною статтею — три випадки плану, Статут лишається «n. 300», невідоме поєднання лишається як є), `tests/test_placeholder_notes.py` (+3: обидві хибні фрази права 16.09 і фраза економіки 14.09 проходять; 11 справжніх нотаток корпусу job12 та самостійні фрагменти ловляться). Наявні `test_executor_v2_recorded_corpus` (нотатки job12 у §2–§6) і параметризований `test_offline_docx_warnings_and_exact_replay` — без змін і зелені. Повний прогін API: **1 460 passed, 23 skipped** (базовий прогін до правки: 1 455 passed); black/ruff чисті.
- Перезбірка записаних робіт без моделі (`scripts/rerender_recording.py`, записи лабораторії fixes-B і nocap-B від 16.09, код до/після правки):

  | Запис | Абзаців | Змінених абзаців | Різниця лише всередині правових дужок | Бібліографія | Розділи / бібл. / цитати без стор. | Байти |
  |---|---|---|---|---|---|---|
  | fixes-B | 155 | 14 | так (перевірено маскуванням дужок) | без змін (5 правових рядків) | 14 / 6+13 / 4 — без змін | 56 955 → 57 000 |
  | nocap-B | 180 | 18 | так | без змін (6) | 19 / 6+14 / 13 — без змін | 60 057 → 60 204 |

  Форми до → після. fixes-B: «(Regolamento)» ×2 і «(Regolamento, art. 88, comma 1/2)» ×8 → «(Regolamento (UE) 2016/679 del Parlamento europeo e del Consiglio[, art. 88, comma N])» ×10; «(…, n. 151, art. 23, art. 23, comma 1/2)» ×3 → «(…, n. 151, art. 23, comma 1/2)»; «(…, n. 151, art. 23, art. 4, comma 1/2/3)» ×6 → «(Legge 20 maggio 1970, n. 300, art. 4, comma N, come modificato dall'art. 23, Decreto legislativo 14 settembre 2015, n. 151)». nocap-B: 9 форм GDPR (art. 5/6/9/13/35/88) так само, одне злиття «art. 23, comma 1»; «(Decreto legislativo 30 giugno 2003, n. 196, art. 114, comma 1)» і «(Legge 20 maggio 1970, n. 300, art. 4, comma N)» — без змін.
- Заглушки на записах (помічник на текстах розділів): fixes-B — 2 хибні («da verificare caso per caso», «da verificare strumento per strumento») → 0; fresh-A §3 («resta, tuttavia, da verificare, poiché la fonte…») → 0; корпус job12 — 11 нотаток → 11.

**Межа правила** (записано, не змінюється в цій сесії): «I dati raccolti restano da verificare» ловиться (іменник dati + фраза) — це попередження менеджеру, не зупинка.

**Помічено, поза планом** (внесено в «Поза сесією» плану): локатор «art. 5, comma 1, lett. a)» обрізається на «comma 1», «lett. a)» лишається за дужкою; суфікс статті в `ARTICLE_LOCATOR` не покриває «bis/ter».

## Пункт 2 — видимий 429 Semantic Scholar

**Що змінено.** `rag_retriever.retrieve` і `search_semantic_scholar` отримали `raise_on_error` (як уже мали `search_crossref`/`search_openalex`): за запитом відмова каталогу (HTTP 429, timeout, transport) піднімається винятком, а не стає `[]`; типовий контракт (`[]` на помилку) для решти викликів не змінений. Виконавець (`executor_v2/sources.search`) просить усі три каталоги піднімати відмову: записана залежність `executor_search` фіксує `outcome: failed` зі статусом (429), `catalogue_unavailable` спрацьовує при ≥ 80 % відмов каталогу, порожня відповідь 200 — результат, не відмова; інші каталоги продовжують. Повторів понад наявні, зміни лімітів і другого ключа немає.

**Докази.** `tests/test_rag_retriever.py::test_semantic_scholar_failures_are_raised_when_requested` (429 → виняток зі статусом; timeout → виняток; 200/порожньо → `[]`; без прапорця — `[]` як раніше), `tests/test_executor_v2.py::test_catalogue_failure_is_visible_and_empty_answers_are_not` (S2 із реальним `search`: Semantic Scholar 429 на кожен запит → одне попередження `catalogue_unavailable: semantic_scholar`, записи `executor_search` зі `status_code 429`; Crossref 200/порожньо — без попередження; OpenAlex дає пакет — S2 і план завершуються). Записаний корпус (`test_executor_v2_recorded_corpus`, `test_platform_first_corpus`) — без змін. Повний прогін API: **1 462 passed, 23 skipped**; black/ruff чисті. Пакет `executor_v2` — 1 491 рядок.

**Що це дає менеджеру.** Досі при 429 від Semantic Scholar (16.09: половина запитів зонда) пакет мовчки будувався лише з Crossref/OpenAlex; тепер у попередженнях роботи з'являється «Каталог джерел не відповідав: semantic_scholar» (пункт 3 показує його текстом на сторінці роботи).
