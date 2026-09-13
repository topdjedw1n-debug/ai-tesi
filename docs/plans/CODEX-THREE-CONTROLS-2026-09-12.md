# Доручення Codex — три контрольні прогони на різних брифах

**12.09.2026 · Автор: Fable. Статус: ДОРУЧЕНО фаундером 12.09.2026 («хай Codex спробує згенерувати 3 різні роботи по різних напрямах і побачимо, чи є ще падіння»).**
Основа: [пріоритет фаундера](../AGENT_SYNC.md#доручення-09092026--спочатку-робоча-платформа-планка-1010-потім),
[план перебудови](THESICA-REBUILD-EXECUTOR-2026-09-09.md) (кроки 0–4 виконані),
[контракт](CONTRACT-CABINET-EXECUTOR-2026-09-09.md), [специфікація v2](SPEC-EXECUTOR-V2-2026-09-09.md).
Зразок процедури і звіту: [контроль №12/job15](../evidence/EXECUTOR-V2-LIVE-3892cac-2026-09-12/README.md).

## 1. Ціль і критерій

Ціль етапу: «платформа працює» = генерація завершується DOCX у трьох реальних
замовленнях поспіль на різних брифах. Це доручення — перша така серія, її веде
Codex до замовлень Тані. Питання одне: **чи доходить встановлений виконавець
`3892cac` до DOCX на трьох різних напрямах, і якщо ні — де саме і чому.**

Приймання доручення: для кожної з трьох робіт є або DOCX з повним записом і
точним відтворенням, або задокументоване падіння з повним записом, офлайн
відтворенням і діагнозом. Compilatio, якість змісту і приймання Тані — не в
цьому дорученні (файли зберігаються для них).

## 2. Три брифи (фіксовані)

Усі: мова `it`, стиль `apa`, провайдер/модель за замовчуванням документа
(`anthropic` / `claude-opus-4-8`), без PDF і методички, менеджер `manager1`.
Формулювання можна редагувати стилістично; напрям, рівень і обсяг — ні.

| # | Напрям | Тип | Обсяг | Тема (`title` = `topic`) | Вимоги (`additional_requirements`) |
|---|---|---|---|---|---|
| A | Економіка | `tesi_triennale` | 20 стор. | Strategie di digital marketing per le piccole e medie imprese italiane: il ruolo dei social media nella fidelizzazione del cliente | Livello: laurea triennale in Economia aziendale. Struttura: introduzione, tre capitoli (quadro teorico del marketing digitale; social media e customer loyalty nelle PMI; analisi di casi ed evidenze empiriche), conclusioni, bibliografia. Fonti prevalentemente articoli peer-reviewed e manuali accademici; citazioni APA. |
| B | Право | `tesi_magistrale` | 30 стор. | La tutela dei dati personali nel rapporto di lavoro: il controllo a distanza dei lavoratori tra Statuto dei lavoratori e GDPR | Livello: laurea magistrale in Giurisprudenza. Struttura: introduzione, quattro capitoli (evoluzione dell'art. 4 dello Statuto dei lavoratori; il GDPR e i principi applicabili al rapporto di lavoro; il controllo a distanza e gli strumenti tecnologici; giurisprudenza e prassi del Garante), conclusioni, bibliografia. Fonti: dottrina giuridica italiana, normativa UE, articoli su riviste giuridiche; citazioni APA. |
| C | Інформатика | `tesi_triennale` | 25 стор. | Sistemi di raccomandazione basati su machine learning per il commercio elettronico: approcci collaborativi e content-based a confronto | Livello: laurea triennale in Informatica. Struttura: introduzione, tre capitoli (fondamenti dei sistemi di raccomandazione; filtraggio collaborativo e approcci content-based; valutazione sperimentale e casi applicativi nell'e-commerce), conclusioni, bibliografia. Fonti: articoli scientifici in inglese e italiano, atti di conferenze; citazioni APA. |

Чому саме так: три несхожі напрями навантажують різні місця виконавця —
економіка: змішані джерела; право: мало DOI, доктрина і нормативні акти
(перевірка посилань S5 і поведінка при непідтверджених джерелах); інформатика:
англомовні джерела, arXiv, технічний виклад. Обсяги 20–30 сторінок тримають
кожну роботу під стелею вартості (нижче).

## 3. Межі, що випливають з коду (перевірено 12.09)

- **Стеля вартості на job у `POLICY` = $5** (`cost_ceiling_cents: 500`);
  перевищення → стоп `provider_unusable_response`. Орієнтир за job15:
  ≈ $0.11 за сторінку, отже A ≈ $2.3, B ≈ $3.4, C ≈ $2.8. Роботи на 40–50
  сторінок у цьому дорученні **не запускати**: вони передбачувано впруться у
  стелю, а це константа, а не дефект. Підняття стелі — окреме рішення
  фаундера з правкою константи і встановленням.
- **Денна квота 2 job на користувача (UTC)** для менеджерів; `manager1`
  (id 1) звільнений через `UNLIMITED_GENERATION_USER_IDS=[1]`, інші менеджери —
  ні. Тому всі три роботи — на `manager1`. Сьогодні на ньому вже 1 job (job15).
- Глобальний денний ліміт 6 млн токенів: три роботи ≈ 1–1,5 млн, запас є.
  Відповідь 429 на старті = квота, не падіння виконавця; зафіксувати і не
  обходити.
- Дозволена сума цього доручення: **до $15 разом** (стеля політики × 3);
  очікувано ≈ $8–9 за обліком застосунку.

## 4. Порядок виконання

1. Перед стартом: сервер на `3892cac`, 6 служб healthy, 0 активних job,
   `generation.paused` відсутній. Зафіксувати (як `server-before` у зразку).
2. Створити чернетку A через штатні маршрути менеджера — ті самі, що
   викликає кабінет: `POST /api/v1/documents/` → `GET …/task-contract` →
   `POST …/task-contract/confirm` → `POST /api/v1/generate/full-document`
   (`mode: "start"`). Логін `manager1` через `POST /api/v1/auth/login`; пароль
   у фаундера, у докази і git не потрапляє. Якщо запуск через API недоступний
   інструментам Codex — підготувати чернетку з підтвердженим завданням і
   попросити фаундера натиснути «Підтвердити і запустити» у кабінеті.
3. Спостерігати `GET /api/v1/jobs/{job_id}/status` (етап, розділи, останній
   сигнал, вартість) до кінцевого стану. Паралельних запусків немає:
   B стартує лише після кінцевого стану A, C — після B.
4. Після кожної роботи, незалежно від результату: експортувати повний запис
   штатним способом (зразок `export-recording.py` у доказах job14/job15,
   параметризувати `document_id`/`job_id`); відтворити офлайн
   `apps/api/scripts/replay_generation.py RECORDING.json OUT --job-id N` без
   мережі й витрат; для DOCX звірити SHA-256 з відтвореним файлом.
5. Для DOCX: копія файла в докази, SHA-256, розмір, оцінка сторінок, розділи
   і слова, бібліографія n/n `verified`, 0 заглушок, 0 буквального Markdown,
   заголовки без дублів, попередження за кодами.
6. Для падіння: `stop.code`, `stage`, `section_index`, `message_uk`; що
   насправді відповіла модель (точний запит і відповідь із запису); чи
   відтворюється офлайн; діагноз — дефект виконавця (`internal_error` завжди
   дефект) чи технічний стоп за контрактом §4. **Далі запускати наступну
   роботу.** Виняток: `provider_access` (доступ/кошти) або `storage_or_db` —
   зупинитись і повідомити фаундера, бо наступні роботи впадуть так само.

## 5. Чого не робити

- Не змінювати код, налаштування, константи `POLICY`, сервер і базу.
  Правки після падіння — окреме доручення після напрямку Fable, а не в цій серії.
- Не повторювати платно роботу, що впала. Не «покращувати» бриф після падіння.
- Не запускати через адмін-маршрути, SQL або обхід квот; не чіпати старі
  роботи №1–№12 і їхні job.
- Не додавати перевірок, гейтів чи зупинок за результатами серії.
- Не проводити Compilatio і не оцінювати академічну якість: це наступний етап.

## 6. Звіт

Тека `docs/evidence/EXECUTOR-V2-THREE-CONTROLS-2026-09-12/` з `README.md`:

- таблиця по трьох роботах: документ, job, напрям/рівень/обсяг, старт і
  кінець UTC, досягнуті кроки S1–S6, розділи n/n, звернень, токенів, $ за
  обліком застосунку, попередження за кодами, DOCX SHA-256/розмір/сторінки,
  посилання verified n/n, заглушки, replay точний так/ні;
- для кожного падіння — окремий розділ за п. 4.6;
- підсумок одним рядком: «3/3 DOCX» або перелік падінь з етапом і причиною;
- сума витрат серії та кількість невідомих звернень провайдера (має бути 0).

Повні записи (`.json.gz`) лишаються поза git поруч із README, як для job15.
Після звіту: коміт лише документів (докази + рядки стану в канон) на `main`;
далі рев'ю Fable через CLI (спершу напрямок, потім факти) і рішення
фаундера про правки або перехід до кроків 5–6.

Відхилення від цього документа (інші брифи, обсяги, паралельні запуски) —
спершу запитати напрямок у Fable, не виконувати мовчки.
