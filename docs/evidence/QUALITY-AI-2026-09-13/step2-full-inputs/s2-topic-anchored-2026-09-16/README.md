# Добір джерел з прив'язкою до теми (S2), 16.09.2026 — крок 1 після консультації №5

Дозвіл фаундера: «так» на крок 1 (код і офлайн-перевірки, без генерацій і сканів). Напрямок — [consult5-2026-09-16](../consult5-2026-09-16/README.md): лагодити забезпечення джерелами до будь-яких змін писаря. Коміт `510d584` (локальний, не доставлений і не активований).

## Що змінено

**Побудова запитів (`app/services/search_queries.py`, новий модуль поза пакетом `executor_v2`, який лишається в бюджеті 1 498 рядків):**
- вузли без власної літератури — вступ, висновки, бібліографія, індекс, sommario, ringraziamenti, appendice — не шукаються;
- глави з підрозділами не шукаються самі: запити йдуть від підрозділів (конкретні питання), а знахідки зараховуються і підрозділу, і його главі (`parents`);
- кожен запит = ядро теми + терміни вузла: локальне ядро — перші 4 змістовні слова назви теми до двокрапки без службових/загальних слів («analisi», «ruolo», «sistemi», «quadro teorico», «italiane»…); англійське ядро — 4 найчастіші змістовні слова з `terms_en` усього дерева; два запити на лист (локальний, англійський), ≤ 12 слів, без голої назви вузла;
- **відсів до верифікації:** кандидат лишається, якщо в назві + анотації трапляються ≥ 2 різних слова теми (початки слів: «digita», «market», «fideli», «client», «loyalt», «smes»…); без анотації досить одного слова в назві (Astra: брак анотації ≠ нерелевантність); одне загальне слово («sociale», «digitale») не рятує;
- PDF менеджера й бібліотека — без змін (вставляються на початок пакета, як і раніше).

**Каталоги за причиною (зонди 16.09 ≈ 01:00):**
- Crossref, ввічливий пул з `mailto`: `x-rate-limit-limit: 3` за 1 с, `x-concurrency-limit: 3` → `CROSSREF_RATE_LIMIT_RPS` 5 → 2, спільний на процес ліміт одночасних запитів на каталог 3 (`shared_slot`), `search_concurrency` 6 → 3;
- Semantic Scholar: 1 rps на всі endpoints з ключем, третина запитів при 1 rps — 429 → 0,5 rps, спільний бюджет пошуку й верифікації;
- `Retry-After` каталогу враховується (до 30 с);
- OpenAlex: кредитний бюджет `x-ratelimit-limit 1000` на вікно (скидання ≈ 2,6 год), пошук = 10 кредитів, prepaid 0 → ≈ 100 пошуків безкоштовно на вікно; ліміт не змінено «на око» (Grok), натомість запитів стало у 2,2 раза менше; далі — вимір після активації і, за потреби, передплачені кредити (пошук коштує $0,001).
- нове попередження `catalogue_unavailable`: каталог, що не відповів на ≥ 80 % своїх запитів, названо менеджеру окремо від «джерел мало».

## Перевірка без генерації (записані дерева S1 від 15.09, `tests/fixtures/scopes/`)

| Дерево | Було викликів | Стало | Перевірено (тести `tests/test_search_queries.py`) |
|---|---|---|---|
| A економіка (18 вузлів) | 162 | 72 (24 запити × 3) | вступ/висновки/бібліографія — 0 запитів; кожен запит містить слово теми; «Metodologia dell'analisi» і «Evidenze empiriche» шукаються з темою (`digital marketing piccole medie metodologia selezione casi`); |
| C інформатика (19) | 171 | 78 | те саме; ядро `raccomandazione machine learning commercio` / `collaborative filtering content-based e-commerce` |
| B право (26) | 234 | 114 | усі 19 предметних листів шукаються, структурні — ні; ядро `tutela dati personali rapporto` / `monitoring remote data work` |

Відсів на реальному пакеті A (40 записів S2 від 15.09): відкинуто 36, лишилися 4 — «PMI Marketing…», «Innovative digital marketing strategies for SMEs», «Social media analytics… fidelización del cliente», «Setting the future of digital and social media marketing research»; відкинуто «Copper complexes…», «Tortura e razzismo», «Lessico…», «Valutazione della ricerca», «Repertori dei movimenti ecclesiali», шість «Introduzione»/«Obiettivi della ricerca», педагогіку, музеї, турагенції. (Анотації у фікстурі обрізані до 300 символів, тож у роботі відсів м'якший.) Регресія права: записаний пакет з 14 PDF проходить старим шляхом (завантаження не фільтруються); тест відключення каталогів тепер очікує `catalogue_unavailable` ×3 перед `source_coverage_gap`. API: 1 449 passed, 23 skipped.

## Що лишилося до живого запуску

1. **Доставка й активація — за фаундером** (фільтр блокує мені rsync): з кореня репозиторію
   `rsync -ai --relative apps/api/app apps/api/tests thesica:/opt/thesica/` і `ssh thesica 'bash /opt/thesica/infra/deploy.sh'`. Ліміти змінено в коді, середовище сервера чіпати не треба.
2. **Живий зонд 8–10 запитів** після активації (`scripts`-снiпет у scratchpad, виконується всередині контейнера API через штатний ретривер): частка 429 по каталогах; якщо OpenAlex далі 100 % — передплачені кредити (≈ $0,07 на роботу) або менше запитів.
3. **Одна економіка через кабінет** (той самий бриф, без PDF) з гейтом «предметні розділи мають повний текст по темі»; скан лише за гейтом; право не перезапускати; писар — окремо, пізніше, на записаному пакеті B.

## Активовано і зондовано (16.09 ≈ 12:40 за Києвом)

Фаундер доставив і активував (`rsync` + `deploy.sh`, «Вроді готово»); чексуми семи змінених модулів у контейнері API збігаються з локальними, контейнери перезапущені. Живий зонд усередині контейнера штатним ретривером (перші 10 запитів дерева економіки в кожен каталог, послідовно, 58 с): Crossref 10/10 (100 рядків), OpenAlex 10/10 (97 рядків — кредитне вікно оновилось), Semantic Scholar 10/10 без винятків, але 5 із 10 запитів отримали 429 всередині ретривера (він ловить помилку й повертає порожній список; 37 рядків з 5 вдалих) — тобто при 0,5 rps Semantic Scholar усе одно віддає кожен другий запит, а `catalogue_unavailable` для нього не спрацює, бо помилка гаситься в ретривері (відомий борг: ретривер S2 має повертати відмову, як `_scholarly_json`). Для економіки цього достатньо: OpenAlex + Crossref дають ~10 кандидатів на запит. Наступне — одна економіка через кабінет після окремого «так» (≈ $2), з перевіркою пакета після S2 і скасуванням, якщо предметні розділи не отримають повних текстів по темі.

## Економіка через кабінет з новим добором (16.09 08:02–08:14 UTC, «Так, дозволяю») — гейт пройдено, на скан

Документ 23 / job 26, той самий бриф без PDF: **$1,50**, 11 розділів, 6 556 слів, лапки 0,3 %. S2 6 хв (учора 15). Пакет 40 (22 Crossref, 18 OpenAlex; Semantic Scholar — 0, як у зонді), **усі по темі**; повних текстів 9 із 17 спроб (5 × 403, 2 × транспорт, 1 × не PDF): «Esportazioni e e-commerce delle imprese italiane» (126 стор.), «Social media marketing strategy: definition, conceptualization, taxonomy…» (20), «Creative crowdsourcing… comunicazione di marketing» (24), «Digital and Social Media Marketing — Construction SMEs» (18), «Drivers of Digital Transformation in SMEs» (14), «SMEs… VUCA… digital» (24), «Social media marketing and advertising» (34), «Effect of social networking sites… SMEs' innovation» (16), «PMI Marketing…» (113). 18 записів без тексту (Crossref-розділи книг: «Email marketing», «Social Media Marketing»…) → `source_no_readable_text` 18; `catalogue_unavailable` не спрацював (S2 гасить 429 у ретривері — борг).

| § | Розділ | Документи з вікнами | Вікон |
|---|---|---|---|
| 2 | Evoluzione dal marketing tradizionale al digitale | PMI Marketing | 18 |
| 3 | Strumenti e canali | PMI Marketing, Esportazioni/e-commerce, Crowdsourcing marketing | 26 |
| 4 | Digital marketing nelle PMI | Construction SMEs, Drivers of DT in SMEs, Esportazioni, PMI Marketing | 24 |
| 5 | Social media nella comunicazione d'impresa | SMM strategy, SMM & advertising, Construction SMEs, Esportazioni | 24 |
| 6 | Fidelizzazione del cliente | PMI Marketing, Social networking sites & SMEs | 22 |
| 7 | SMM e relazione con il cliente nelle PMI | SMM strategy, Social networking sites & SMEs | 22 |
| 8 | Metodologia | Crowdsourcing marketing | 2 |
| 9 | Casi di PMI italiane | Crowdsourcing, SMM & advertising, Construction SMEs, SMM strategy | 23 |
| 10 | Discussione | Drivers of DT, Construction SMEs, Esportazioni | 23 |
| 11 | Conclusioni | Drivers of DT | 6 |
| 1 | Introduzione | Crowdsourcing marketing | 19 |

Порядок письма §2–§10 → §11 → §1. Гейт «предметні розділи мають повний текст по темі» — пройдено (учора: 7 із 12 без). На скан: `Downloads/Thesica-на-скан-7-2026-09-16/A-economia-cabinet-2026-09-16.docx` (sha `404d339b…`, README з правилами). Змістові зауваги до скану: вступ починається з туристичних ПМІ Тоскани (найбільший текст пакета); висновки переказують «primo/secondo/terzo capitolo» (3 фрази-дорожні карти всупереч CONCLUSIONS_RULE); дві цитати англійською в італійському тексті (Verhoef 2021); рецензент S6: одруківка «il modello di offre», англіцизм «settla»; під «customer loyalty» немає окремого повнотекстового джерела (§6 спирається на PMI Marketing і статтю про соцмережі та інновації).
