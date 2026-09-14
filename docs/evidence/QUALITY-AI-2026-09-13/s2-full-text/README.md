# Повнотекстові докази в S2/S4 — реалізація і доказ за $0 (14.09.2026)

**Виконавець: Fable (сесія Claude Code, виконавець і архітектор). Проєкт: [S2-FULL-TEXT-EVIDENCE-2026-09-14](../../../plans/S2-FULL-TEXT-EVIDENCE-2026-09-14.md) (§13 — рев'ю Astra і правки, [astra-review/](astra-review/)). Платних прогонів і сканів не було; сервер, POLICY, перелік моделей, база — не змінювалися.**

## 1. Що зроблено в коді

| Де | Що |
|---|---|
| `app/services/full_text_sources.py` (новий) | посилання на відкритий PDF з відповідей OpenAlex (`best_oa_location.pdf_url` → `open_access.oa_url`) і Semantic Scholar (`openAccessPdf.url`); записана залежність `executor_full_text` (потокове завантаження ≤25 МБ, редиректи, один перехід за `<meta citation_pdf_url>`, сторінки тексту через `extract_pdf_pages`, відмови як дані: `http_403`, `not_pdf`, `no_text_layer`, `too_large`; транспортні помилки — записана відмова); вікна документа через штатний `split_passages`; `attach_full_text` (отримання для відібраних джерел, перезаморожування уривка «анотація + релевантні сторінки», `evidence_level="pdf"`, зведення `full_text`); `section_evidence` — відбір вікон на розділ |
| `ai_pipeline/rag_retriever.py` | рядки пошуку OpenAlex/S2 несуть `canonical_metadata.open_access_url`; S2 запитує поле `openAccessPdf`; кеш зберігає це поле |
| `executor_v2/sources.py` (S2) | злиття посилання між провайдерами; збереження в метаданих після перевірки; отримання повних текстів для відібраних джерел (`attach_full_text`); подія `executor_full_text`; попередження `source_full_text_unavailable`; знайдений запис завантаженої роботи вилучається (`sources_equivalent`) — раніше такий дубль зупиняв роботу помилкою збереження пакета |
| `executor_v2/sections.py` (S4) | докази розділу через `section_evidence`; подія `executor_section_evidence`; умовне речення `FULL_TEXT_RULE` після незмінної `S4_INSTRUCTION`, лише коли є вікна |
| `executor_v2/run.py` | побудова рядків завантажених файлів винесена в `uploaded_sources.executor_source_rows` (той самий результат); `ctx.scopes` для S4 |
| `executor_v2/warnings.py` | +1 код (info): «Повний текст частини джерел не отримано автоматично; використано анотації. За потреби завантажте PDF.» |
| `source_evidence.py` | уривок для будь-якого джерела з пасажами — «анотація + сторінки за темою» (для завантажених — байт у байт як раніше) |
| `ai_pipeline/citation_formatter.py` | інституційні автори: + Corte, Cassazione, Tribunale, Consiglio, Repubblica, Parlamento, Commissione, Garante, Autorità, Court, Parliament, Commission («(Cassazione, 2021)» → «(Corte di Cassazione, 2021)») |
| `scripts/s4_lab.py` | `--uploaded-sources` (PDF через штатний розбір → записаний вхід як завантажені файли), `--recorded-outline` (план зі стрічки попри змінений запит S3; у звіті `request_changed`), `--allow-host`; нова залежність поза стрічкою йде наживо, як `verify` |
| `scripts/section_evidence_report.py` (новий) | офлайн-звіт по кожному розділу запису: документи, вікна, сторінки, символи, бали; за бажанням — довідка OpenAlex за DOI і штатний фетч |

Пакет `executor_v2` — **1 496 рядків** (ліміт 1 500), перемикачів немає; нові константи (`SECTION_EVIDENCE_CHARS=20000`, `DOCUMENT_EVIDENCE_CHARS=16000`, `MIN_RELEVANCE=0.30`, `MIN_MATCHED_TERMS=5`, `RELATIVE_FLOOR=0.5`) — у модулі повних текстів, `POLICY` не змінено. Міграцій немає.

## 2. Тести (повні числа)

- API `pytest tests/ -q`: **1420 passed, 23 skipped, 0 failed (105.14s)**.
- Web `npm run test -- --runInBand`: **31/31 suites, 211 passed, 1 skipped, 0 failed**.
- Нові/змінені: `tests/test_full_text_sources.py` (7: посилання з провайдерів; фетч — PDF, перехід за meta, 403, не-PDF, скан, ліміт розміру; вікна й зшивання; відбір — запланований/доповнений/поза планом, уривок при прогалині, форма без повних текстів байт у байт; бюджет по колу; `attach_full_text` з успіхом, 403 і транспортною помилкою), `tests/test_executor_v2.py` (+3: повний текст доходить до промпту S4 і подій; пакети лише з анотаціями дають історичний промпт без правила; **записані отримання відтворюються без мережі, включно з відмовою 403 і `ConnectError`**, той самий відбиток пакета), `tests/test_s4_lab.py` (+1: специфікація завантажень), словник попереджень оновлено.
- `ruff check` — чисто; `black --check` — чисто на змінених файлах.

## 3. Точні відтворення після змін — побайтово ([reports/](reports/))

| Запис | DOCX SHA-256 | `cmp` з еталоном | Спожито звернень |
|---|---|---|---|
| A, job16 | `08e203b5…c1cb426f` | так | 8/8 |
| B, job17 | `69c1bd76…43e77792` | так | 27/27 |
| C, job18 | `d0bf1da2…90b68b8` | так | 8/8 |
| job15 (3892cac) | `a4e217c0…9fd9fdd` | так | 21/21 |

Усі — `status=completed`, `request_changed=false` для кожного запиту, витрат 0. Промпт S4 старих записів не змінився: правило додається лише за наявності вікон, а старі рядки пошуку не мають посилань на PDF, тож нових отримань немає.

## 4. Доказ штатного шляху на записі B за $0

### 4.1 Сухий прогін з недійсним ключем ([dry-run-B/](dry-run-B/))

Команда: запис B (job17), `--mode live --live-sections 1 --cost-cap-usd 1 --uploaded-sources uploads/uploaded-sources-B.json --recorded-outline --secrets-file <файл з недійсним ключем>`. Три PDF ([uploads/](uploads/)): art. 4 (1 с.), Cass. 25732/2021 (11 с. — фрагменти М1), Ghionzoli 2025 (40 с.).

- S1 зі стрічки; S2 штатно: пакет 40 джерел, у ньому `ART4`, `CASS25732`, `GHIONZOLI2025` як завантажені (`evidence_level=pdf`, уривки 1 180 / 1 500 / 1 809 символів), знайдений запис Ghionzoli `Keb3f04ff6686` вилучено як дубль; S3 зі стрічки (`request_changed: true`, прапорець у звіті).
- §1 «Introduzione» наживо: штатний відбір дав чотири заплановані уривки (анотації, без змін) + `GHIONZOLI2025` 12 вікон (с. 2, 14, 16–18, 20, 26, 28, 36; 10 076 символів) + `CASS25732` 12 вікон (с. 2, 4–6, 8, 9, 11; 8 659 символів); `ART4` до §1 не потрапив (0,29 < 0,30). Подія `executor_section_evidence` — [section-1-evidence-event.json](dry-run-B/section-1-evidence-event.json).
- Записаний запит S4 §1 — [section-1-prompt.txt](dry-run-B/section-1-prompt.txt): 26 497 символів, `S4_INSTRUCTION` незмінна, після неї `FULL_TEXT_RULE`, докази у формі `{"key","text"}` з мітками `[page N]`; модель `claude-opus-4-8`, `max_tokens 4256`.
- Провайдер відповів 401 → штатна зупинка `provider_access` на §1; витрат 0; живих звернень 1 (відмова).

### 4.2 Офлайн-звіт по 24 розділах ([section-report-B/uploads.md](section-report-B/uploads.md))

Ті самі три PDF через штатні `section_evidence` для кожного розділу записаного плану: 24/24 розділи отримують повнотекстові вікна; `ART4` — у §2, 3, 6, 13, 14, 18 (розділи про art. 4); `CASS25732` — у 19 розділах (не у §7, 8, 12, 16, 17, 19, 22); `GHIONZOLI2025` — усюди різними сторінками. Обсяг 16,7–23,7 тис. символів на розділ. Прогалини лексичного відбору видно: art. 4 не доходить до §5 (Jobs Act) і §16 (videosorveglianza — у нормі «impianti audiovisivi»), фрагмент постанови про GPS — до §16 (у М1 їх давали вручну). Калібрування, за яким обрано поріг 0,30 і ≥5 термінів: сторонній англомовний документ про моніторинг моста набирав 0,49–0,63 за термінами scope і 0,00 за словами розділу.

### 4.3 Відкриті PDF пакета B штатним фетчем ([section-report-B/open-access.md](section-report-B/open-access.md))

Довідка OpenAlex за DOI (імітація сьогоднішніх рядків пошуку) дала посилання для 26 з 40 джерел; штатний `full_text` отримав текст для **11**: EJPLT ×5 (15–48 с.), Labour & Law Issues (26 с.), Stato e Chiese (67 с.), BUP (387 с.), zenodo через `citation_pdf_url` (58 с.), Milano UP (6 с.), Giornale di cardiologia (66 с., стороннє джерело пакета). Відмови: FUP ×4, IRIS, T&F, ScienceDirect, MDPI — `http_403` (Cloudflare/платні); Yale, World Bank, OpenEdition — `not_pdf`; одна транспортна. За планом S3 повні тексти доходять до 12 з 24 розділів (Ka0418ffc6496, K66f7f6a6f0a4, Keb3f04ff6686, Kb925177ec80e, Kc6a04e74719f).

## 5. Межі

- Доказ — промпт і відбір, не текст і не Compilatio: жоден розділ не писався.
- Відбір лексичний (`score_passage`), без семантики; англомовні документи оцінюються окремим запитом за `terms_en`; номер сторінки PDF — єдиний локатор.
- `--recorded-outline` доводить маршрутизацію S4, не роботу нового S3 з новим пакетом; у кроці 2 S3 працює штатно.
- Живий один розділ за $0,1–0,15 на записі B не робився: штатний відбір змінює й попередні розділи, тож без повного прогону він не є доказом ефекту.
- Нормативні акти й рішення — через завантаження менеджером (PDF); автоматичний правовий фетч не реалізовано (див. проєкт §3).
