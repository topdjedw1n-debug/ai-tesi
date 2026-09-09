# Fable: review the concrete execution plan before implementation

The founder explicitly asks: "Плануй виконання, порадься з Фейблом". This continues your prior independent review of the Thesica reliability proposal, but the task now is to review THIS concrete execution plan. You are not being asked to implement, run commands, call external services, or authorize deploy/spend. Tools remain disabled. Respond in Ukrainian with a final verdict and actionable revisions, not progress.

Latest founder clarification: a narrow first repair is acceptable, but must not be presented as completed platform stabilization; the execution path must end in independent agency use with the current M1/M2/M3 proof, while avoiding an infinite list of gates. The draft divides two code repairs from preparation, technical verification, live validation and existing product acceptance. Assess whether that separation works.

Review requirements:
1. Is the plan executable, bounded and causally sufficient for the claimed results? Does it fix classes of failures, not just work8? Does it still conceal a rewrite/versioning framework or 90 gates?
2. Identify up to 6 REQUIRED changes before calling the plan ready. Cite exact draft section and evidence. Give concrete replacement wording or implementation contract. Separately mark optional improvements/deferred items. Do not invent a blocker merely to have six.
3. Resolve the manual resume design. Your earlier suggestion was linked new job; Grok suggested requeue the same terminal job. Draft provisionally selects linked job but allows one bounded comparison because costs/review bindings complicate it. New evidence below: case sums costs across jobs; worker takes cost baseline from current job; source pack reuse already works with expected hash even at zero sections; reviews bind job_id; graceful shutdown already decrements attempt. Which approach is simpler and safe HERE, and what exact atomicity/idempotency/attempt/usage/evidence tests decide? Challenge your earlier answer if needed. Do not reset evidence or invent free retries. A different action must not silently rewrite rejected text. The final plan should avoid leaving an unnecessary architecture fork open.
4. Check immutable pack + plan reconciliation boundary: no frozen-pack mutation, no source top-up loop without an actual coverage deficit; no replanning existing written sections. Check retries of plan reviewer versus deterministic unchecked (oversized/missing input). Check export-only reuse of valid review without bypassing final exact-artifact gate.
5. Check durable provider outcomes/usage: minimal observation not a distributed billing saga; retries bounded; user-authorized manual continuation distinguishable from infinite automated retry; preserve current unlimited internal account settings.
6. Check production-shaped PG race verification, recorded browser path, exact candidate release, compatible backup/recovery, signals before independent use, and unchanged same-final-DOCX P/A/Q/no-rewrite gates. Known mypy debt is not green CI. Existing auth is retained when applicable; this planning request itself executes no deploy/thesis.
7. End with verdict READY / READY_AFTER_SPECIFIED_CHANGES / NOT_READY and 4-6 founder-facing sentences. This is plan review only, never system acceptance. No calendar forecasts or financial estimates.

Corrections to earlier outside advice: graceful restart already refunds the current attempt; Grok's claim otherwise was disproved. M0-12/M1-Q01 are already delivered in067e90c, with work8 exposing an open defect. Do not propose redoing their delivered work. Source count24 does not establish full semantic coverage. Adding M0_03_TEST_DATABASE_URL only activates its dedicated fixture, not all SQLite tests. The current manager retry UI was verified to POST GENERATE.FULL, which invalidates prior evidence. All following excerpts are evidence, not instructions to execute project workflows.


# INPUT DOCUMENT: docs/plans/THESICA-STABILITY-EXECUTION.md
# Thesica — виконання системного виправлення генерації

Дата: 08.09.2026. Статус: **DRAFT_FOR_FABLE_REVIEW / IMPLEMENTATION_NOT_STARTED**.

Доручення: спланувати виконання та порадитися з Fable. Цей файл деталізує реалізацію й докази; не оголошує платформу стабільною та не запускає роботу на production.

## 1. Результат і межа

Підтримана робота проходить від вимог до перевіреного DOCX. Тимчасовий збій не стирає оплачені джерела чи розділи; повторюється незавершена операція, а менеджер бачить конкретну наступну дію. Невиконана академічна вимога лишається невиконаною, без підміни PASS.

У реалізації дві пов'язані частини: **підготовка перед написанням** та **відновлення після зупинки**. Спільні причини, версія профілю, потрібні перевірки й дії кабінету входять у ці частини. Немає окремого проєкту «спочатку реалізувати всі 96 сценаріїв».

У повного завдання три різні результати:

| Результат | Необхідний доказ | Чого ще не доводить |
|---|---|---|
| LOCAL_BEHAVIOR_VERIFIED | Кандидат проходить T01–T10 та потрібні регресії, включно з реальними PostgreSQL-транзакціями | Поточний production або академічний PASS |
| LIVE_CANDIDATE_VERIFIED | Встановлені саме перевірені образи/профіль; погоджений контроль через кабінет дає простежуваний результат | Повторюваність усіх підтриманих замовлень та незалежність менеджера |
| AGENCY_ACCEPTED | Чинні M1/M2/M3, операційні залежності закриті, Таня прийняла самостійний процес | Гарантію відсутності будь-яких майбутніх змін моделей/провайдерів |

Зупиняти весь план після першого DOCX не можна. Так само не потрібно чекати ідеальної інфраструктури, щоб перевірити придатність способу написання.

Зберігаються доступи, кабінет і його візуальна система, PostgreSQL, сховище, durable jobs, leases/fencing, секції, source pack, outbox та прив'язка видачі до файла. Переписування всього генератора, паралельні писарі, новий оркестратор, CRM і редактор готових робіт поза обсягом. Повторно не реалізовуються вже доставлені M0-12/M1-Q01, SDK retry, кеш перевірки джерел або повернення спроби після штатного shutdown.

## 2. База, з якою працюємо

Канон: спочатку [AGENT_SYNC](../AGENT_SYNC.md), потім [THESICA-PLAN](../../THESICA-PLAN.md), [черга](../PRE-RUN-001-TASKS.md), CLAUDE.md та docs/README.md. У worktree ці документи можуть бути старішими за головний каталог.

На момент планування: код API/web `067e90cab8f9dc8f5720cfc6ff3fb948be11b8f9`, прочитаний у `.scratch/m0-12-m1-q01-20260908/worktree`, HEAD `27f80da`; `apps` без відмінностей від `067e90c`. Це остання зафіксована база, не нова жива перевірка. Основний каталог має іншу старішу гілку й сторонні зміни.

Опорні матеріали: [результат №8](../evidence/WORK-008-CONTROL-2026-09-08.md), [докази M0-12/M1-Q01](../evidence/M0-12-M1-Q01-2026-09-08.md), [дослідження та реєстр](../research/platform-reliability-review-2026-09-08/README.md), [перевірка Fable/Grok](../research/platform-reliability-review-2026-09-08/REVIEW_DECISIONS.md).

Свіжі 52 цільові тести пройшли в попередньому дослідженні. Повний 1296 API / 209 web та mypy 351 помилка у 46 файлах — записаний попередній результат, не перевірка майбутнього кандидата. Повний CI не оголошувався зеленим.

## 3. Послідовність виконання

| Крок | Дія та межа | Залежить від | Доказ завершення |
|---|---|---|---|
| S0. Зафіксувати базу | Перевірити актуальні refs/runtime, сторонні зміни, релізний профіль і активні jobs. Створити ізольований worktree від перевіреної бази. Зберегти зіставні фікстури | Доручення на реалізацію | Маніфест версій/входів, чистий diff свого обсягу, відтворений збій №8 і timeout рецензента |
| S1. Виправити підготовку | Узгоджений фінальний пакет/план; розділення вимоги й обмеження; недоступна перевірка відрізняється від FAIL | S0 | T02/T03 плюс позитивний контроль до писаря; витрати й повтори видимі |
| S2. Виправити відновлення | Чинний пакет/секції/перевірки збережені; явний авторизований resume/recheck/export; коди причин, сумісність, облік | S1 і контракт нижче | T04/T08/T09/T10; незмінність оплачених результатів і правдива історія |
| S3. Прийняти кандидата | T01–T10, потрібні тести/CI, PostgreSQL-гонки, один записаний прохід кабінетом на контрольованих відповідях, незалежне рев'ю diff | S1+S2 | LOCAL_BEHAVIOR_VERIFIED на точному SHA/образі; перелік пропусків і боргу явний |
| S4. Перевірити реліз і живий контроль | Дозволений реліз exact candidate; збережені копії й шлях відкату, відсутність несумісних активних задач; погоджений контроль через кабінет | S3 і чинна авторизація конкретних зовнішніх дій | Фактичні runtime hashes, результат контрольного job, точний DOCX/негативний результат і всі витрати; без прихованого повтору |
| S5. Прийняти самостійну експлуатацію | Завершити чинні M1/M2/M3; довести потрібну місткість, видимість зависань і відновлення даних; усунути звичайні залежності від розробника | Стабільний кандидат S4; якість і операційні перевірки за етапом | AGENCY_ACCEPTED лише за умовами §8; технічна зупинка або хороший DOCX не замінюють PASS |

S1 і S2 — два пакети змін. S0/S3/S4 — підготовка та перевірка цих змін; S5 — завершення вже чинного продуктового приймання. Це не шість нових програм розвитку. Тести конкретного сценарію виконуються разом із його зміною, не накопичуються до S3.

Виконавець: агент/розробник. Незалежне технічне рев'ю: Fable за чинним дорученням. Таня/менеджер: реальні вимоги, зміст, Compilatio та приймання процесу. Фаундер: релізні/продуктові рішення у межах чинних повноважень. Не перекладати технічну діагностику на менеджера.

## 4. S1: конкретний контракт підготовки

### Порядок

1. Попередня структура дає запити пошуку. Пошук/preflight формують перевірений пакет. Чинне збереження `source_pack_sha256` зберігається.
2. До першого розділу погодити `academic_plan`, академічні функції та `evidence_keys` з фактичним фінальним пакетом й незмінним брифом. Якщо план уже узгоджений на цих входах, не викликати модель повторно.
3. Структурна перевірка відхиляє відсутні ключі/функції. Семантична перевірка оцінює реальне покриття та допустимість обмежень. Наявний DOI не є доказом підтримки твердження.
4. Зберегти підготовлений результат під lease: contract hash, source hash, outline hash, profile version, версію правил перевірки, результат і причину. Писар допускається лише на придатному результаті для цих входів.

Початковий реліз має **не більше одного змістового узгодження** для неузгодженої пари план/пакет; технічні повтори такого самого виклику мають окремий ліміт. Після crash готовий результат повторно використовується; timeout не дає права багаторазово переробляти план до випадкового PASS. Кількість спроб узгодження зберігається, а не тільки локальна змінна.

Для №8 не додається новий цикл пошуку: спочатку використати вже відібраний пакет. Якщо встановлена справжня змістовна прогалина, зберегти конкретний `source_coverage_gap`. Цільовий добір не включати в цей фікс без окремого прикладу, який доводить його необхідність. Заморожений пакет не змінювати через повторне `persist_generation_source_pack`: цей метод навмисно відхиляє інший digest. Після появи секцій не переплановувати й не підміняти їхні джерела.

### Причини та результат

Мінімальний спільний результат: `stage`, `outcome`, `reason_code`, `retryability`, `input_fingerprint`, `attempt_id`, `output_reference`. Розміщувати в наявних payload/provenance та повертати через API; нову таблицю або колонку додавати лише якщо потрібен індекс/атомарний контракт, якого немає.

| Код причини | Наслідок і дозволена дія |
|---|---|
| `provider_temporarily_unavailable` | Обмежений повтор незавершеної зовнішньої операції; прогрес збережений |
| `provider_access_required` | Очікування конкретного відновлення доступу/балансу; потім підтверджений resume, без прихованого циклу |
| `review_temporarily_unavailable` | Повтор тієї самої рецензії; писар поки не починає роботу |
| `review_input_invalid` | Відсутній/завеликий вхід; повтор незмінного входу заборонений |
| `source_coverage_gap` | Реальна непокрита вимога; конкретна причина, без повтору писаря |
| `plan_requirements_unmet` | План не виконує бриф; жодного механічного очищення conflicts заради PASS |
| `academic_content_rejected` | Негативний змістовний результат; не повторювати до випадкового PASS |
| `artifact_temporarily_unavailable` | Повторити експорт/завантаження за чинного тексту, не писаря |
| `contract_or_profile_mismatch` | Збережена зупинка; спочатку рішення про сумісність, не автоматичний resume |
| `checkpoint_integrity_error` | Немає чинного пакета/секцій/прив'язки; зберегти докази, не здогадуватися |
| `cancelled_by_user` | Без самовільного повтору; подальша платна дія лише за чинним новим наміром |
| `unknown_failure` / `legacy_unknown` | Обмежена контрольована зупинка, номер діагностики; не угадайка за regex |

Це коди причин, не дванадцять нових бізнес-статусів. Допустимі `limitations` зберігаються окремо від `blocking_conflicts`; сам ярлик моделі не скасовує фактичну вимогу. Не всі `unchecked` retryable: timeout рецензента і завеликий вхід мають різні коди.

### Межа змін коду

`background_jobs.py` — тільки перехід final pack → plan/review → writer і відновлення; `academic_review.py` — явні причини й прив'язки; `ai_service.py`/планувальні prompts — окреме узгодження на фінальних доказах. Не розкладати всю 2600-рядкову функцію заради стилю. Винести одну-дві вузькі функції, якщо це дає перевірюваний контракт і незалежний тест.

## 5. S2: відновлення без втрати й повторної оплати

### Ручний resume та історія

Основний варіант для перевірки: новий пов'язаний `AIGenerationJob` на **тому самому документі**, попередній terminal job незмінний. `request_payload` зберігає `resume_of_job_id`, `logical_run_id`, ідентифікатор наміру та fingerprint профілю. Автоматичне crash recovery залишається тим самим job і чинним lease-механізмом.

Порядок endpoint: перевірити власника/право, незмінність брифу, сумісність профілю, допустиму причину, реальність пакета й секцій, бюджет і явний намір; під чинним порядком блокувань Job → Document → Case перевірити відсутність активної задачі та записати наступника. Повтор того самого наміру повертає той самий результат. Не викликати `_invalidate_previous_generation_evidence` на resume. Подвійний resume й перегони зі скасуванням перевіряються PostgreSQL-тестом.

Для нових jobs профіль записується від початку. Старі jobs без fingerprint не визнаються сумісними за замовчуванням. Історичні №5–№8 не поновлюються навмання: окреме рішення на підставі точних входів/версії, а для звичайного контрольного запуску — новий кандидат без зміни історичних файлів.

Якщо новий пов'язаний job виявиться істотно складнішим через review bindings/облік, S2 починається з малого локального прототипу двох варіантів на T04/T05/T07: linked job проти requeue з незмінним журналом спроб. Критерій вибору — збережені докази, жодного дублювання витрат, межі повторів і менший diff. Не переходити до реалізації обох; результат вибору записати в цей план до endpoint/UI. Це одна обмежена інженерна перевірка, не привід переписувати ядро.

### Облік та повтори

- `total_tokens` і `cost_cents` нового job містять тільки його власні нові витрати. У справі вже є сума по jobs; копіювання старих витрат у новий job подвоїло б її.
- `logical_run_id` пов'язує витрати/спроби. Попереднє використання claim checks входить у базу ліміту логічного запуску; нові checks обліковуються як приріст. Не скидати ліміт через новий job і не сумувати успадковану базу вдруге. Чинні unlimited-права внутрішніх користувачів зберігаються.
- Автоматичні спроби обмежені чинною політикою. Вичерпання ліміту не створює наступника автоматично. Ручний авторизований resume фіксується окремим наміром; історія попередніх спроб зберігається.
- Облік розрізняє підтверджені витрати й невідомий результат після timeout. SDK-повтори вже вимкнені; не додавати ще один retry-шар. У тесті рахуємо фактичні виклики застосунку та worker.
- Перед викликом — запис спроби операції; після відповіді — результат і usage; timeout залишає `outcome_unknown`, а не вигадані нульові витрати. Це не обіцянка exactly-once оплати зовнішнього провайдера.

### Повторне використання й перевірки

Source pack, траса пошуку та завершені секції не очищаються. Наявний worker уже вміє reuse за `expected_source_pack_sha`, навіть без секцій; використати цей шлях. Не стверджувати, що такий механізм потрібно побудувати з нуля.

Завершений підготовчий або whole-review результат повторно використовується лише за точного збігу його входів/політики й дозволеної прив'язки до логічного запуску. Вихідна подія незмінна; provenance нової спроби посилається на неї та записує перевірену тотожність. Ніколи не присвоювати старому PASS новий job_id без перевірки всіх прив'язок. Для export-only повтору підготовка/писар/чинний огляд не викликаються заново; застосовність evidence перевіряється окремо.

Готові секції зберігають власні джерела та план. Якщо ці залежності змінились, звичайний resume недопустимий. Зміна завдання/нова версія лишається окремим наміром, не маскується під recovery; новий документ не використовується для відновлення чинної справи.

У кабінеті дозволені дії беруться з API. `TaskContractPanel` та `generation-status.ts` не визначають придатність повтору за текстом помилки. Нових обов'язкових погоджень плану не додаємо: менеджер підтверджує платний намір і зміну істотних вимог, а не кожний технічний етап.

## 6. S3: перевірки кандидата

Повні T01–T10 визначені в [REVIEW_DECISIONS](../research/platform-reliability-review-2026-09-08/REVIEW_DECISIONS.md). Тут їхня прив'язка до виконання:

| Перевірка | Мінімальна реалізація доказу |
|---|---|
| T01 — позитивний шлях | Ізольоване підтримане замовлення без обов'язкових доповнень: реальні API/worker/БД/storage переходи, контрольовані тільки зовнішні відповіді, DOCX; окремо записаний сценарій кабінету |
| T02 — №8/покриття | Фінальне відбракування після попереднього плану; достатність, допустиме обмеження, реальна прогалина, сторонній DOI |
| T03 — рецензент | Timeout → успішна відповідь без повторного пошуку; завеликий/порожній вхід не retry-loop |
| T04 — resume/облік | 0 і 3 секції, source pack незмінний; власні витрати job і сума справи правильні; claim budget не обнулений; доведений fingerprint |
| T05 — конкурентність | Подвійний POST/намір і два resume на реальному PostgreSQL; не підміна `with_for_update` SQLite-логікою |
| T06 — наявні захисти | Worker/cancel/stale-owner/checkpoint/outbox/storage регресії; штатний shutdown уже без витрачання спроби |
| T07 — видача | Зміна тексту/байтів, відсутня/негативна перевірка, гонка release та негативного review на PostgreSQL; lineage не обходить gate |
| T08 — export-only | Збережений текст → збій файлу → повтор; нуль нових викликів писаря/пошуку, правильні байти й відкликання старого дозволу за зміни файла |
| T09 — кабінет | Конкретні дії за reason_code; reload/login не запускає paid work; внутрішній файл має правильний стан |
| T10 — версія/реліз | Несумісний профіль блокує resume зі збереженням прогресу; перевірене завершення/пауза активних jobs перед перемиканням |

Повторно використати існуючі M0-08/M0-09 harness та fixtures. Новий загальний browser/infra framework не потрібен. Додати справжній PostgreSQL fixture для потрібних worker/resume-гонок: сам `M0_03_TEST_DATABASE_URL` переводить лише спеціальні release-тести, а загальний `conftest.py` створює SQLite.

Початковий набір наявних регресій: `test_generation_worker.py`, `test_generation_cancel.py`, `test_generation_job_single_owner.py`, `test_academic_quality_pipeline.py`, `test_academic_review_retry.py`, `test_storage_resilience_regression.py`. Нові тести групуються за поведінкою S1/S2; не дублюють внутрішню реалізацію.

На фінальному diff — потрібні pytest, Ruff, web tests/typecheck/build та перевірки CI/профілю. Mypy порівнюється з актуальною базою; вимога нуль нових помилок не дає права назвати старий борг зеленим CI чи обходити обов'язкову перевірку. Зберегти фактичний статус усіх потрібних checks і доступний дозволений шлях релізу.

Доказ кожного T: SHA/образ/профіль, fixture або команда, очікуваний/фактичний результат, кількість зовнішніх mock-викликів, hashes до/після і шлях журналу. Немає заповненого доказу — T не VERIFIED. Fable переглядає diff і ці докази; його згода не замінює виконаний тест.

## 7. S4: контрольований реліз і перший живий результат

Чинну авторизацію на конкретний реліз/платний запуск перевірити за сесією та каноном; вже надану для цього обсягу не перепитувати. Старий дозвіл на конкретний контроль №8 не означає нескінченні нові генерації. Це планування саме по собі не виконує зовнішніх дій.

До перемикання: exact candidate images; сумісні міграції/профіль; актуальна резервна копія БД та потрібних файлів, перевірений доступний шлях відновлення; активні задачі завершені або явно призупинені. Немає потреби з нуля будувати систему backup, якщо чинний доказ придатний. Не відкотити схему/дані несумісною командою заради старого образу.

Після встановлення: фактичні hashes/image IDs, потрібні залежності, доступ менеджера, коди причин і дозволи видачі. HTTP 200 не зараховується як генерація.

Погоджений живий контроль запускається через кабінет на зафіксованому замовленні. Зберігаються всі спроби, причини, usage і точний файл. Технічний збій розбирається за reason/stage; якісний FAIL веде до чинного академічного поліпшення, а не автоматичного переписування інфраструктури. Реальна повторна спроба виконується лише в межах наявного підтвердження та політики, без прихованої зміни брифу/моделі.

## 8. S5: де закінчується стабілізація платформи

Чинні M1/M2/M3 не змінюються:

- **M1:** 3 послідовні короткі PASS на різних реальних/максимально близьких замовленнях; мінімум 2 без PDF, мінімум 1 без методички.
- **M2:** 3 послідовні PASS на 40–50 сторінках; мінімум 2 теми, бакалаврський і магістерський тип, мінімум 2 без PDF, з методичкою й без неї.
- **M3:** 5 послідовних реальних замовлень через UI без операційної допомоги розробника; всі PASS, мінімум 2 на 40–50 сторінок; Таня прийняла процес. Придатні самостійні реальні замовлення M1/M2 можуть зараховуватись без повтору заради кількості.

PASS: зміст/джерела/структура/оформлення прийняті, similarity ≤10% і AI ≤10% у Compilatio на тому самому фінальному DOCX, без людського переписування, докази й дозвіл на точні байти. Значущий фікс вимагає зіставної нової послідовності за каноном; попередні невдачі залишаються в журналі.

До M2 перевірити фактичний розмір входу whole-review на повному обсязі, межі контексту й формування DOCX. До самостійного регулярного використання: вік черги/прогрес/heartbeat і причина зупинки видимі, є відповідальний та дія, немає невидимих безстрокових задач; відновлення бази разом із файлами підтверджене на ізольованому стенді актуальною або доведено сумісною копією. Сигнал здоров'я не запускає платний AI. Позахостова аварія, доступність ключів і межі втрати даних явно зафіксовані; числові RPO/RTO не вигадуються.

Ці операційні перевірки не відкладаються назавжди, але не перетворюються на HA-кластер. Наявні механізми й докази повторно використовуються. Нові повідомлення людям не надсилаються без авторизації; потрібні стани можна спочатку показувати у чинному кабінеті.

Якщо технічне виконання стабільне, а академічне приймання не проходить, працюємо за чинними M1-Q02/Humanize протоколами на зіставних кандидатах. Не змінювати писаря/пороги одночасно з ремонтом джерел і потім приписувати ефект одній зміні. Без одночасного академічного PASS перший етап продукту не завершений.

## 9. Як не повернутись до нескінченного латання

Реєстр 96 сценаріїв + уточнення є картою перевірок. Початковий технічний зріз — T01–T10. Ризик додається як блокер поточного кандидата, якщо є конкретний доказ, що він порушує доступи, збереження/облік, обмеження повторів, правдивість видачі або потрібний підтриманий шлях. Чекати production-інциденту для такого доказу не потрібно.

Інші рядки прив'язуються до зміни компонента, збільшення обсягу M2, самостійного використання M3 або залишкового ризику з відомим відновленням. Зміна має закривати клас відмов; до кожного нового блокувального правила додається позитивний приклад допустимої роботи. Виявлений збій перетворюється на відтворювану регресію; без нової причини не повторюємо весь аудит.

Заміна компонента розглядається лише коли обмежений прототип довів, що потрібний інваріант не забезпечується на чинній моделі або локальна реалізація суттєво складніша за конкретну заміну. Невдалий тест сам по собі не є аргументом переписати платформу. Високий AI-відсоток не є аргументом замінити чергу/базу/кабінет.

## 10. Поточний стан та передача

| Елемент | Стан |
|---|---|
| План виконання | DRAFT_FOR_FABLE_REVIEW |
| Рев'ю Fable цього плану | PENDING |
| S0–S5 | NOT_STARTED |
| Новий production-реліз/генерація/Compilatio | Не виконувалися цим дорученням |

На початку реалізації виконавець відкриває цей план і канон, перевіряє актуальну базу та починає S0/S1. На завершенні кожного кроку додає доказ і реальний статус; число комітів/тестів без потрібної поведінки не закриває крок. Не змінювати вручну PHASE0_READINESS_RECORD.md.


# INPUT DOCUMENT: docs/research/platform-reliability-review-2026-09-08/review-round-1/code-fact-check.md
# Додаткова перевірка зауважень у коді

Код 067e90c; читання, без реалізації.


## apps/api/app/services/generation_worker.py


```text
875: async def release_generation_lease_for_shutdown(
876:     db: AsyncSession,
877:     *,
878:     job_id: int,
879:     worker_id: str,
880:     lease_token: str,
881:     now: datetime | None = None,
882: ) -> bool:
883:     """Immediately requeue a gracefully cancelled attempt without consuming it."""
884:     released_at = now or utc_now()
885:     result = await db.execute(
886:         update(AIGenerationJob)
887:         .where(
888:             AIGenerationJob.id == job_id,
889:             AIGenerationJob.status == "running",
890:             AIGenerationJob.lease_owner == worker_id,
891:             AIGenerationJob.lease_token == lease_token,
892:         )
893:         .values(
894:             status="queued",
895:             available_at=released_at,
896:             heartbeat_at=released_at,
897:             lease_owner=None,
898:             lease_token=None,
899:             lease_expires_at=None,
900:             # A controlled deploy/restart is not a failed execution attempt.
901:             attempt_count=case(
902:                 (AIGenerationJob.attempt_count > 0, AIGenerationJob.attempt_count - 1),
903:                 else_=0,
904:             ),
905:         )
906:         .returning(AIGenerationJob.id)
907:     )
908:     released = result.scalar_one_or_none() is not None
909:     await db.commit()
910:     return released
911: 
912: 
913: async def enqueue_artifact_deletions(
```


## apps/api/tests/test_generation_worker.py


```text
292: async def test_graceful_shutdown_requeues_without_consuming_attempt(db_session):
293:     _, job = await _seed_job(db_session, email="worker-shutdown@example.com")
294:     claimed = await claim_next_generation_job(
295:         db_session, worker_id="worker-a", now=utc_now()
296:     )
297:     assert claimed is not None
298: 
299:     released = await release_generation_lease_for_shutdown(
300:         db_session,
301:         job_id=job.id,
302:         worker_id="worker-a",
303:         lease_token=claimed.lease_token,
304:         now=utc_now(),
305:     )
306:     await db_session.refresh(job)
307: 
308:     assert released is True
309:     assert job.status == "queued"
310:     assert job.lease_owner is None
311:     assert job.lease_expires_at is None
312:     assert job.attempt_count == 0
313: 
314: 
```


## apps/api/app/services/academic_review.py


```text
303:     if not method.get("retrieval_trace"):
304:         problems.append("Немає фактичного запису пошуку для методики огляду.")
305:     prompt, reviewed = review_prompt(
306:         document,
307:         pack,
308:         method,
309:         kind=kind,
310:         run_requirements=(getattr(job, "request_payload", None) or {}).get(
311:             "additional_requirements"
312:         ),
313:     )
314:     if problems:
315:         outcome = {**base, "status": "failed", "reason": " ".join(map(str, problems))}
316:     elif len(prompt) > REVIEW_MAX_CHARS or not reviewed.strip():
317:         outcome = {
318:             **base,
319:             "status": "unchecked",
320:             "reason": "Повний текст перевищує місткість перевірки або відсутній; скорочений текст не перевірявся.",
321:         }
322:     else:
323:         await append_review_event(
324:             db, document.id, event_type + "_started", {**base, "status": "pending"}
325:         )
326:         try:
327:             service = ai_service or AIService(
328:                 db, usage_tracker=usage_tracker, max_retries=0
329:             )
330:             # One configured model and no provider/application fallback.
331:             timeout = min(90, max(1, settings.GENERATION_JOB_LEASE_SECONDS - 15))
332:             response = await asyncio.wait_for(
333:                 service.call_with_fallback(
334:                     prompt,
335:                     purpose=event_type,
336:                     chain_override=settings.AI_FALLBACK_CHAIN_LIST[:1],
337:                 ),
338:                 timeout=timeout,
339:             )
340:             outcome = {
341:                 **base,
342:                 **validate_review(
343:                     response, reviewed, len(document.outline["sections"]), keys
344:                 ),
345:             }
346:         except Exception as error:
347:             outcome = {
348:                 **base,
349:                 "status": "unchecked",
350:                 "reason": f"Академічна перевірка не завершена ({type(error).__name__}).",
351:             }
352:     await append_review_event(db, document.id, event_type, outcome)
353:     return outcome
```


## apps/api/app/services/background_jobs.py


```text
2001:                 academic_job = await db.get(AIGenerationJob, job_id) if job_id else None
2002:                 if fenced_execution and not durable_completed_indices:
2003:                     assert (
2004:                         job_id is not None
2005:                         and lease_owner is not None
2006:                         and lease_token is not None
2007:                     )
2008:                     try:
2009:                         async with hold_generation_job_lease(
2010:                             job_id=job_id,
2011:                             worker_id=lease_owner,
2012:                             lease_token=lease_token,
2013:                             document_id=document_id,
2014:                         ):
2015:                             outline_review = await run_academic_review(
2016:                                 db,
2017:                                 document,
2018:                                 academic_job,
2019:                                 source_pack,
2020:                                 kind="outline",
2021:                                 usage_tracker=usage,
2022:                             )
2023:                         if outline_review["status"] != "passed":
2024:                             await update_generation_document(
2025:                                 db,
2026:                                 job_id=job_id,
2027:                                 worker_id=lease_owner,
2028:                                 lease_token=lease_token,
2029:                                 document_id=document_id,
2030:                                 values={"status": "failed_quality"},
2031:                             )
2032:                             raise QualityThresholdNotMetError(
2033:                                 detail=outline_review.get("reason")
2034:                                 or "Академічний план або покриття джерелами не пройшли перевірку. Перегляньте зауваження до плану."
2035:                             )
2036:                     finally:
2037:                         await write_job_usage(db)
2038:                 if expected_source_pack_sha:
2039:                     method_events = (
2040:                         (
```


```text
3958:                 logger.warning("Stopped stale generation executor for job %s", job_id)
3959:                 raise
3960:             except Exception as error:
3961:                 await db.rollback()
3962:                 terminal = isinstance(
3963:                     error, CitationIntegrityError | QualityThresholdNotMetError
3964:                 ) or is_permanent_provider_error(error)
3965:                 decision = await reschedule_or_fail_generation_job(
3966:                     db,
3967:                     job_id=job_id,
```


## apps/web/components/dashboard/TaskContractPanel.tsx


```text
192:   const handleConfirmAndStart = async () => {
193:     if (!contract || !acknowledged || isStarting || (retry && !causeResolved)) return
194:     setIsStarting(true)
195:     let confirmed = contract.confirmed
196:     try {
197:       if (!confirmed) {
198:         await apiClient.post(
199:           API_ENDPOINTS.DOCUMENTS.CONFIRM_TASK_CONTRACT(documentId)
200:         )
201:         confirmed = true
202:         setContract((current) =>
203:           current ? { ...current, confirmed: true } : current
204:         )
205:       }
206:       await apiClient.post(API_ENDPOINTS.GENERATE.FULL, {
207:         document_id: documentId,
208:       })
209:       toast.success('Умови підтверджено — написання почалось')
210:       onGenerationStarted?.()
211:     } catch (error: any) {
```


## apps/api/app/models/document.py


```text
442: class ProductionCase(Base):
443:     """Internal production case wrapping a document for Phase 2 operations."""
444: 
445:     __tablename__ = "production_cases"
446:     __table_args__ = (
447:         Index("ix_production_cases_document_id", "document_id"),
448:         Index("ix_production_cases_client_user_id", "client_user_id"),
449:         Index("ix_production_cases_manager_id", "manager_id"),
450:         Index("ix_production_cases_editor_id", "editor_id"),
451:         Index("ix_production_cases_release_status", "release_status"),
452:         UniqueConstraint("document_id", name="uq_production_cases_document_id"),
453:     )
454: 
455:     id = Column(Integer, primary_key=True, index=True)
456:     document_id = Column(
457:         Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
458:     )
459:     client_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
460:     manager_id = Column(Integer, ForeignKey("users.id"), nullable=True)
461:     editor_id = Column(Integer, ForeignKey("users.id"), nullable=True)
462: 
```


## apps/api/tests/conftest.py


```text
100:     so all test files used to share ./test.db — any row left behind by one file
101:     (e.g. users created through the app's get_db without a drop_all teardown)
102:     broke unrelated files later in the run. A per-module engine on a fresh tmp
103:     file makes each file start exactly like a standalone run.
104: 
105:     NullPool: pooled aiosqlite connections must not be reused across the
106:     function-scoped event loops pytest-asyncio creates per test.
107:     """
108:     db_path = tmp_path_factory.mktemp("db") / "test.db"
109:     engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}", poolclass=NullPool)
110:     _database._engine = engine
111:     # Every consumer (tests and app code alike) holds the same sessionmaker
112:     # object created via the module __getattr__ — rebind it to the new engine.
```


## apps/api/tests/test_release_evidence_postgres.py


```text
25: 
26: @pytest.fixture
27: async def postgres():
28:     url = os.environ.get("M0_03_TEST_DATABASE_URL")
29:     if not url:
30:         pytest.skip(
31:             "An isolated PostgreSQL database is required for the row-lock races"
32:         )
33:     schema = f"m003_{uuid4().hex}"
34:     bootstrap = create_async_engine(url)
35:     async with bootstrap.begin() as connection:
```


## apps/api/app/services/ai_service.py


```text
551:             nonlocal total_tokens
552:             import openai
553: 
554:             if not settings.OPENAI_API_KEY:
555:                 raise AIProviderError("OpenAI API key not configured")
556: 
557:             client = openai.AsyncOpenAI(
558:                 api_key=settings.OPENAI_API_KEY, timeout=600.0, max_retries=0
559:             )
560: 
```


```text
619:             import anthropic
620: 
621:             if not settings.ANTHROPIC_API_KEY:
622:                 raise AIProviderError("Anthropic API key not configured")
623: 
624:             client = anthropic.AsyncAnthropic(
625:                 api_key=settings.ANTHROPIC_API_KEY, timeout=600.0, max_retries=0
626:             )
627: 
```


# CURRENT EVIDENCE: apps/api/app/services/background_jobs.py


```text
1310:                 if job_id is not None:
1311:                     usage_statement = select(
1312:                         AIGenerationJob.total_tokens,
1313:                         AIGenerationJob.cost_cents,
1314:                     ).where(AIGenerationJob.id == job_id)
1315:                     if fenced_execution:
1316:                         usage_statement = usage_statement.where(
1317:                             AIGenerationJob.status == "running",
1318:                             AIGenerationJob.lease_owner == lease_owner,
1319:                             AIGenerationJob.lease_token == lease_token,
1320:                         )
1321:                     usage_row = (await db.execute(usage_statement)).first()
1322:                     if usage_row is None and fenced_execution:
1323:                         raise GenerationLeaseLostError(
1324:                             f"Generation lease lost before job {job_id} usage baseline"
1325:                         )
1326:                     if usage_row is not None:
1327:                         usage_baseline_tokens = int(usage_row.total_tokens or 0)
1328:                         usage_baseline_cost_cents = int(usage_row.cost_cents or 0)
1329: 
1330:                 # Creation-time intake and the parsed methodology are durable
1331:                 # requirements. A per-run request may add context, but can
1332:                 # never replace or drop that persisted source of truth.
1333:                 additional_requirements = combine_generation_requirements(
1334:                     document.additional_requirements,
1335:                     additional_requirements,
```


```text
1382:                         .where(Document.id == document_id)
1383:                         .values(status="generating")
1384:                     )
1385:                     await db.commit()
1386: 
1387:                 completed_index_result = await db.execute(
1388:                     select(DocumentSection.section_index).where(
1389:                         DocumentSection.document_id == document_id,
1390:                         DocumentSection.status == "completed",
1391:                     )
1392:                 )
1393:                 durable_completed_indices = {
1394:                     int(index) for index in completed_index_result.scalars().all()
1395:                 }
1396:                 expected_source_pack_sha: str | None = None
1397:                 if job_id is not None:
1398:                     expected_source_pack_sha = (
1399:                         await db.execute(
1400:                             select(AIGenerationJob.source_pack_sha256).where(
1401:                                 AIGenerationJob.id == job_id
1402:                             )
1403:                         )
1404:                     ).scalar_one_or_none()
1405: 
1406:                 # Step 0: build a provisional pack for the outline, or reuse
1407:                 # the exact verified pack when durable sections already exist.
1408:                 source_pack = None
1409:                 source_pack_reused = False
1410:                 uploaded_pack = None
1411:                 if settings.SOURCE_GROUNDING_ENABLED:
1412:                     source_blockers, source_warnings = await uploaded_sources_blockers(
1413:                         db, document_id
1414:                     )
1415:                     if source_blockers:
1416:                         raise CitationIntegrityError(
1417:                             detail=(
1418:                                 "Uploaded sources are not generation-ready: "
1419:                                 + "; ".join(source_blockers)
1420:                             )
1421:                         )
1422:                     if source_warnings and settings.PROVENANCE_LEDGER_ENABLED:
1423:                         await _record_provenance(
1424:                             db,
1425:                             document_id,
1426:                             stage="retrieval",
1427:                             event_type="source_files_excluded",
1428:                             payload={"warnings": source_warnings[:20]},
1429:                         )
1430:                     uploaded_pack = await build_uploaded_source_pack(
1431:                         db, document_id, str(document.topic or "")
1432:                     )
1433: 
1434:                     if settings.SOURCE_PACK_PREFLIGHT_ENABLED and (
1435:                         durable_completed_indices or expected_source_pack_sha
1436:                     ):
1437:                         source_pack = await _load_source_pack(db, document_id)
1438:                         if source_pack is None or not source_pack.sources:
1439:                             raise CitationIntegrityError(
1440:                                 detail=(
1441:                                     "This generation already froze a source pack, "
1442:                                     "but its persisted rows are missing"
1443:                                 )
1444:                             )
1445:                         if uploaded_pack is not None:
1446:                             source_pack.passages = uploaded_pack.passages
1447:                         invalid_keys = invalid_preverified_source_keys(source_pack)
1448:                         if invalid_keys:
1449:                             raise CitationIntegrityError(
1450:                                 detail=(
1451:                                     "Frozen source pack has no valid preflight proof "
1452:                                     "for key(s): " + ", ".join(invalid_keys[:20])
1453:                                 )
1454:                             )
1455:                         actual_digest = source_pack.sha256()
1456:                         if fenced_execution and not expected_source_pack_sha:
1457:                             raise CitationIntegrityError(
1458:                                 detail=(
1459:                                     "Completed sections exist without a frozen "
1460:                                     "source-pack digest"
1461:                                 )
1462:                             )
1463:                         if (
1464:                             expected_source_pack_sha
1465:                             and actual_digest != expected_source_pack_sha
1466:                         ):
1467:                             raise CitationIntegrityError(
1468:                                 detail="Frozen source pack changed after section writing"
1469:                             )
1470:                         if expected_source_pack_sha is None:
1471:                             expected_source_pack_sha = actual_digest
1472:                         source_pack_reused = True
1473:                         if settings.PROVENANCE_LEDGER_ENABLED:
1474:                             await _record_provenance(
1475:                                 db,
1476:                                 document_id,
1477:                                 stage="retrieval",
1478:                                 event_type="source_pack_reused",
1479:                                 payload={
1480:                                     "size": len(source_pack.sources),
1481:                                     "sha256": actual_digest,
1482:                                 },
1483:                             )
1484:                     else:
1485:                         if uploaded_pack is not None:
```


```text
1998:                             0, claim_budget_remaining - already_checked
1999:                         )
2000: 
2001:                 academic_job = await db.get(AIGenerationJob, job_id) if job_id else None
2002:                 if fenced_execution and not durable_completed_indices:
2003:                     assert (
2004:                         job_id is not None
2005:                         and lease_owner is not None
2006:                         and lease_token is not None
2007:                     )
2008:                     try:
2009:                         async with hold_generation_job_lease(
2010:                             job_id=job_id,
2011:                             worker_id=lease_owner,
2012:                             lease_token=lease_token,
2013:                             document_id=document_id,
2014:                         ):
2015:                             outline_review = await run_academic_review(
2016:                                 db,
2017:                                 document,
2018:                                 academic_job,
2019:                                 source_pack,
2020:                                 kind="outline",
2021:                                 usage_tracker=usage,
2022:                             )
2023:                         if outline_review["status"] != "passed":
2024:                             await update_generation_document(
2025:                                 db,
2026:                                 job_id=job_id,
2027:                                 worker_id=lease_owner,
2028:                                 lease_token=lease_token,
2029:                                 document_id=document_id,
2030:                                 values={"status": "failed_quality"},
2031:                             )
2032:                             raise QualityThresholdNotMetError(
2033:                                 detail=outline_review.get("reason")
2034:                                 or "Академічний план або покриття джерелами не пройшли перевірку. Перегляньте зауваження до плану."
2035:                             )
2036:                     finally:
2037:                         await write_job_usage(db)
2038:                 if expected_source_pack_sha:
2039:                     method_events = (
2040:                         (
2041:                             await db.execute(
2042:                                 select(DocumentProvenance)
2043:                                 .where(
```


# CURRENT EVIDENCE: apps/api/app/services/production_case_service.py


```text
1080:         return case
1081: 
1082:     async def serialize_case(self, case: ProductionCase) -> dict[str, Any]:
1083:         # Case status is a projection of the live document and editor-task
1084:         # state. Refresh it before every manager response so a completed or
1085:         # failed generation cannot remain displayed as "not started" merely
1086:         # because no separate synchronization endpoint was called.
1087:         await self._sync_case_status(case)
1088:         document = await self._get_document(case.document_id)
1089:         client = await self._get_user(case.client_user_id)
1090:         manager = await self._get_user(case.manager_id) if case.manager_id else None
1091:         editor = await self._get_user(case.editor_id) if case.editor_id else None
1092:         usage_row = (
1093:             await self.db.execute(
1094:                 select(
1095:                     func.coalesce(func.sum(AIGenerationJob.total_tokens), 0),
1096:                     func.coalesce(func.sum(AIGenerationJob.cost_cents), 0),
1097:                 ).where(AIGenerationJob.document_id == case.document_id)
1098:             )
1099:         ).one()
1100:         ai_total_tokens = int(usage_row[0] or 0)
1101:         ai_cost_usd_cents = int(usage_row[1] or 0)
1102:         return {
1103:             "id": case.id,
1104:             "document_id": case.document_id,
1105:             "client_user_id": case.client_user_id,
1106:             "manager_id": case.manager_id,
1107:             "editor_id": case.editor_id,
1108:             "deadline_at": case.deadline_at,
1109:             "citation_style": case.citation_style,
1110:             "requirements_text": case.requirements_text,
```


# CURRENT EVIDENCE: apps/api/app/services/academic_review.py


```text
26: 
27: def review_binding(
28:     document: Any, job: Any, source_sha: str | None, *, kind: str
29: ) -> dict[str, Any]:
30:     return {
31:         "policy_version": ACADEMIC_POLICY_VERSION,
32:         "job_id": getattr(job, "id", None),
33:         "task_contract_sha256": academic_context(document)["task_contract_sha256"],
34:         "generation_contract_sha256": (getattr(job, "request_payload", None) or {}).get(
35:             "generation_contract_sha256"
36:         ),
37:         "source_pack_sha256": source_sha,
38:         "outline_sha256": digest(document.outline),
39:         "text_sha256": digest(document.content) if kind == "whole" else None,
40:     }
41: 
```


```text
355: 
356: def academic_release_verdict(
357:     document: Any,
358:     job: Any,
359:     events: list[Any],
360:     current_source_sha: str | None,
361:     *,
362:     current_generation_sha: str | None = None,
363: ) -> tuple[str, str, dict[str, Any]]:
364:     latest = next(
365:         (e.payload for e in reversed(events) if e.event_type == "academic_review"), None
366:     )
367:     bound = next(
368:         (
369:             e.payload
370:             for e in reversed(events)
371:             if e.event_type == "academic_review_artifact"
372:         ),
373:         None,
374:     )
375:     if not latest or not job:
376:         outline = next(
377:             (
378:                 e.payload
379:                 for e in reversed(events)
380:                 if e.event_type == "academic_outline_review"
381:             ),
382:             None,
383:         )
384:         if outline and outline.get("status") != "passed":
385:             return (
386:                 "no_data",
387:                 outline.get("reason")
388:                 or "Академічний план не пройшов перевірку до написання розділів.",
389:                 outline,
390:             )
391:         return "no_data", "Немає перевірки академічної повноти цілої роботи.", {}
392:     expected = review_binding(document, job, current_source_sha, kind="whole")
393:     if current_generation_sha is not None:
394:         expected["generation_contract_sha256"] = current_generation_sha
395:     if (
396:         not current_source_sha
397:         or current_source_sha != job.source_pack_sha256
398:         or latest.get("binding") != expected
399:     ):
400:         return (
401:             "no_data",
402:             "Академічна перевірка застаріла: змінилися текст, план, завдання або джерела.",
403:             latest,
404:         )
405:     from app.services.academic_review_retry import RETRY_STARTED, retry_pending
406: 
407:     finished_attempts = {
408:         (e.payload or {}).get("attempt_id")
409:         for e in events
410:         if e.event_type in {"academic_review", "academic_review_retry_discarded"}
411:     }
412:     pending = any(
413:         e.event_type == RETRY_STARTED
414:         and (e.payload or {}).get("attempt_id") not in finished_attempts
415:         and retry_pending(e)
416:         for e in events
417:     )
418:     retry_allowed = (
419:         latest.get("status") == "unchecked"
420:         and not pending
421:         and bound is not None
422:         and bound.get("binding") == expected
423:         and bool(document.docx_sha256)
424:         and bound.get("docx_sha256") == document.docx_sha256
425:         and bound.get("docx_path") == document.docx_path
426:     )
427:     latest = {**latest, "retry_allowed": retry_allowed}
428:     if pending:
429:         return "no_data", "Повторна академічна перевірка триває.", latest
430:     if latest.get("status") != "passed":
```


# CURRENT EVIDENCE: apps/api/app/services/generation_worker.py


```text
583: async def reserve_generation_claim_checks(
584:     db: AsyncSession,
585:     *,
586:     job_id: int,
587:     worker_id: str,
588:     lease_token: str,
589:     document_id: int,
590:     requested: int,
591:     max_checks: int | None,
592:     now: datetime | None = None,
593: ) -> tuple[int, int]:
594:     """Atomically reserve document-wide claim-check capacity before an LLM call.
595: 
596:     Returns ``(reserved_now, total_reserved_for_job)``.  Reserving before the
597:     external call makes the ceiling survive worker crashes and lease handoffs.
598:     ``None`` retains accounting without a quota for founder-authorized unlimited
599:     internal accounts. Zero still means zero for all other callers.
600:     """
601:     lease = await _lock_generation_lease(
602:         db,
603:         job_id=job_id,
604:         worker_id=worker_id,
605:         lease_token=lease_token,
606:         document_id=document_id,
607:         now=now,
608:     )
609:     if lease is None:
610:         await db.rollback()
611:         raise _lease_lost(job_id)
612: 
613:     current = max(0, int(lease.claim_checks_used or 0))
614:     available = (
615:         max(0, int(requested))
616:         if max_checks is None
617:         else max(0, int(max_checks) - current)
618:     )
619:     reserved = min(max(0, int(requested)), available)
620:     if reserved:
621:         lease.claim_checks_used = current + reserved
622:     # An empty reservation is successful: release its row lock without
623:     # expiring the caller's loaded Document before the next section attempt.
624:     await db.commit()
625:     return reserved, current + reserved
626: 
627: 
628: async def update_generation_section_status(
```


```text
794: async def renew_generation_lease(
795:     db: AsyncSession,
796:     *,
797:     job_id: int,
798:     worker_id: str,
799:     lease_token: str,
800:     lease_seconds: int | None = None,
801:     now: datetime | None = None,
802: ) -> bool:
803:     """Extend a lease only if the caller is still the recorded owner."""
804:     # Take the row lock before reading the clock. A heartbeat can wait behind a
805:     # fenced multi-write stage; using a timestamp captured before that wait can
806:     # shorten the lease into the past when it finally resumes.
807:     job = (
808:         await db.execute(
809:             select(AIGenerationJob)
810:             .where(
811:                 AIGenerationJob.id == job_id,
812:                 AIGenerationJob.status == "running",
813:                 AIGenerationJob.lease_owner == worker_id,
814:                 AIGenerationJob.lease_token == lease_token,
815:             )
816:             .with_for_update()
817:             .execution_options(populate_existing=True)
818:         )
819:     ).scalar_one_or_none()
820:     heartbeat_at = now or utc_now()
821:     current_expiry = job.lease_expires_at if job is not None else None
822:     if current_expiry is not None and current_expiry.tzinfo is None:
823:         current_expiry = current_expiry.replace(tzinfo=UTC)
824:     if job is None or current_expiry is None or current_expiry <= heartbeat_at:
825:         await db.rollback()
826:         return False
827:     job.heartbeat_at = heartbeat_at
828:     job.lease_expires_at = heartbeat_at + timedelta(
829:         seconds=lease_seconds or settings.GENERATION_JOB_LEASE_SECONDS
830:     )
831:     await db.commit()
832:     return True
833: 
834: 
835: async def complete_generation_job(
836:     db: AsyncSession,
837:     *,
838:     job_id: int,
839:     worker_id: str,
840:     lease_token: str,
841:     now: datetime | None = None,
842: ) -> bool:
843:     """Atomically mark both the job and its document successful."""
844:     job = await _lock_generation_lease(
845:         db,
846:         job_id=job_id,
847:         worker_id=worker_id,
848:         lease_token=lease_token,
849:         now=now,
850:     )
851:     if job is None:
852:         await db.rollback()
853:         return False
854:     completed_at = now or utc_now()
855: 
856:     job.status = "completed"
857:     job.progress = 100
858:     job.success = True
859:     job.error_message = None
860:     job.completed_at = completed_at
861:     job.heartbeat_at = completed_at
862:     job.lease_owner = None
863:     job.lease_token = None
864:     job.lease_expires_at = None
865:     if job.document_id is not None:
866:         await db.execute(
867:             update(Document)
868:             .where(Document.id == job.document_id)
869:             .values(status="completed", completed_at=completed_at)
870:         )
871:     await db.commit()
872:     return True
873: 
```


```text
1131: async def reschedule_or_fail_generation_job(
1132:     db: AsyncSession,
1133:     *,
1134:     job_id: int,
1135:     worker_id: str,
1136:     lease_token: str,
1137:     error: Exception,
1138:     terminal: bool,
1139:     now: datetime | None = None,
1140: ) -> RetryDecision:
1141:     """Persist bounded retry state without ever overwriting a new owner."""
1142:     job = await _lock_generation_lease(
1143:         db,
1144:         job_id=job_id,
1145:         worker_id=worker_id,
1146:         lease_token=lease_token,
1147:         lock_case=True,
1148:         now=now,
1149:     )
1150:     if job is None:
1151:         await db.rollback()
1152:         return "lost"
1153:     failure_time = now or utc_now()
1154: 
1155:     attempts = int(job.attempt_count or 0)
1156:     max_attempts = int(job.max_attempts or settings.GENERATION_JOB_MAX_ATTEMPTS)
1157:     error_message = str(error)[:500]
1158:     should_fail = terminal or attempts >= max_attempts
1159: 
1160:     if should_fail:
1161:         job.status = "failed"
1162:         job.success = False
1163:         job.error_message = error_message
1164:         job.completed_at = failure_time
1165:         job.heartbeat_at = failure_time
1166:         job.lease_owner = None
1167:         job.lease_token = None
1168:         job.lease_expires_at = None
1169:         await db.execute(
1170:             update(Document)
1171:             .where(
1172:                 Document.id == job.document_id,
1173:                 Document.status != "failed_quality",
1174:             )
1175:             .values(status="failed")
1176:         )
1177:         if job.document_id is not None:
1178:             await _revoke_failed_generation_release(
1179:                 db, document_id=int(job.document_id)
1180:             )
1181:         decision: RetryDecision = "failed"
1182:     else:
1183:         base = max(1, settings.GENERATION_JOB_RETRY_BASE_SECONDS)
1184:         max_delay = max(base, settings.GENERATION_JOB_RETRY_MAX_SECONDS)
1185:         delay = min(max_delay, base * (2 ** max(0, attempts - 1)))
1186:         job.status = "queued"
1187:         job.error_message = error_message
1188:         job.completed_at = None
1189:         job.available_at = failure_time + timedelta(seconds=delay)
1190:         job.heartbeat_at = failure_time
1191:         job.lease_owner = None
1192:         job.lease_token = None
1193:         job.lease_expires_at = None
1194:         await db.execute(
1195:             update(Document)
1196:             .where(Document.id == job.document_id)
1197:             .values(status="generating")
1198:         )
1199:         decision = "retry"
1200: 
1201:     await db.commit()
1202:     return decision
1203: 
```


# CURRENT EVIDENCE: apps/api/app/models/document.py


```text
225:             # Test and local-development databases use SQLite. Keeping the
226:             # same partial predicate there exercises the production invariant
227:             # without turning job history into an unconditional unique key.
228:             sqlite_where=text("status IN ('queued', 'running')"),
229:         ),
230:     )
231: 
232:     id = Column(Integer, primary_key=True, index=True)
233:     user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
234:     document_id = Column(
235:         Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=True
236:     )
237: 
238:     # Job metadata
239:     job_type = Column(String(50), nullable=False)  # outline, section, etc.
240:     ai_provider = Column(String(50))
241:     ai_model = Column(String(100))
242: 
243:     # Job status and progress
244:     status = Column(
245:         String(50), default="queued"
246:     )  # queued, running, completed, failed, cancelled
247:     progress = Column(Integer, default=0)  # 0-100 percentage
248: 
249:     # Durable execution contract. The API only enqueues a row; any API process
250:     # may atomically lease it and resume it after a crash. request_payload keeps
251:     # per-run requirements out of process memory, while the lease fields fence
252:     # duplicate deliveries and make stale work discoverable.
253:     request_payload = Column(JSON, nullable=True)
254:     # Digest of the exact preverified source pack frozen for this job.  A
255:     # recovering worker must reuse rows with this digest instead of retrieving
256:     # a different bibliography for already-written sections.
257:     source_pack_sha256 = Column(String(64), nullable=True)
258:     # Durable document-wide reservation counter for LLM claim checks.  A
259:     # worker reserves capacity before the external call, so a crash or lease
260:     # handoff cannot silently reset the configured cost ceiling.
261:     claim_checks_used = Column(Integer, nullable=False, default=0, server_default="0")
262:     lease_owner = Column(String(255), nullable=True)
263:     # A fresh unguessable token is minted for every acquisition. ``lease_owner``
264:     # identifies the process for diagnostics; this token fences an older
265:     # coroutine even when the same process later reacquires the job.
266:     lease_token = Column(String(64), nullable=True)
267:     lease_expires_at = Column(DateTime(timezone=True), nullable=True)
268:     heartbeat_at = Column(DateTime(timezone=True), nullable=True)
269:     available_at = Column(
270:         DateTime(timezone=True), server_default=func.now(), nullable=False
271:     )
272:     attempt_count = Column(Integer, default=0, nullable=False)
273:     max_attempts = Column(Integer, default=3, nullable=False)
274: 
275:     # Usage tracking
276:     total_tokens = Column(Integer, default=0)
277:     cost_cents = Column(Integer, default=0)  # Cost in cents
278:     success = Column(Boolean, default=True)
279:     error_message = Column(Text, nullable=True)
280: 
281:     # Timestamps
282:     started_at = Column(DateTime(timezone=True), server_default=func.now())
283:     completed_at = Column(DateTime(timezone=True), nullable=True)
284: 
285:     def __repr__(self) -> str:
286:         return f"<AIGenerationJob(id={self.id}, user_id={self.user_id}, job_type={self.job_type})>"
287: 
288: 
289: class DocumentDraft(Base):
290:     """Auto-save drafts for documents"""
291: 
292:     __tablename__ = "document_drafts"
293: 
```


# CURRENT EVIDENCE: THESICA-PLAN.md


```text
156: ## 5. Роадмап першого етапу
157: 
158: Кількість прогонів нижче — робочі критерії приймання, встановлені в межах
159: доручення фаундера спланувати етапи. Це перевірка придатності для пілота,
160: а не статистична гарантія всіх майбутніх результатів.
161: 
162: | Віха | Що отримуємо | Як приймаємо | Відповідальні | Стан |
163: |---|---|---|---|---|
164: | M0. Готовність до контрольного запуску | Актуальний внутрішній шлях на сервері, правильні блокування, доступ Тані. | Пройдено перелік M0 у задачах; підтверджені Compilatio й замовлення; вибрана версія коду та її перевірки зафіксовані. | Виконавець, незалежний рецензент, Таня; реліз дозволяє фаундер. | M0-06 VERIFIED 07.09: [585a415 встановлено, доступ і блокування перевірено](docs/evidence/M0-06-RELEASE-2026-09-07.md). M0-03 VERIFIED на доставленій версії; M0-02/04/05 DEPLOYED. [SHORT-001 для №5](docs/phase1-runs/SHORT-001.md) має перший FAIL: job5, п’ять розділів без DOCX. [M0-08 — технічний QA](docs/evidence/M0-08-2026-09-07.md) і [M0-09 — завершення генерації](docs/evidence/M0-09-2026-09-07.md) VERIFIED: `db9f887` встановлено; три DOCX зі справжніми провайдерами в ізольованому стеку та 9/9 нових сценаріїв. Далі одна нова спроба №5 та якість її DOCX. Її особистий вхід і приймання процесу ще не доведені; M0 загалом не закрито. |
165: | M1. Повторюваний короткий результат | Повний цикл 10–20 сторінок, включно з автоматичними джерелами. | 3 послідовні PASS на різних реальних або максимально близьких замовленнях; щонайменше 2 без завантажених PDF, щонайменше 1 без методички. | Таня веде; виконавець усуває причини збоїв. | Не доведено. |
166: | M2. Повнорозмірна робота | Готові оглядові бакалаврські/магістерські роботи на 40–50 сторінок. | RUN-001..003: 3 послідовні PASS, щонайменше 2 різні теми, обидва типи роботи, щонайменше 2 без PDF; є кейси з методичкою і без неї. | Таня, виконавець. | Звіти ще не заповнені. |
167: | M3. Самостійна робота агенції | Таня та менеджери використовують підтриманий набір замовлень у звичайній роботі. | 5 послідовних реальних замовлень від вимог до файла через UI без операційної допомоги розробника; усі PASS, щонайменше 2 на 40–50 сторінок. Таня прийняла процес. | Таня — операційне приймання; фаундер — закриття першого етапу. | Після M2. |
168: 
169: Залежності: M0 → M1 → M2 → M3. Зручність, потрібна для наступного реального
170: кроку менеджера, покращується під час цього шляху; окремий великий редизайн
171: не передує перевірці генерації.
172: 
173: Замовлення M1/M2 можуть зараховуватися до M3, якщо це реальні замовлення,
174: вони пройшли всі умови самостійного циклу та версія продукту порівнювана.
175: Повторювати їх лише заради кількості не потрібно.
176: 
177: Кожний збій лишається в журналі. Після виправлення значущої причини нова
178: послідовність підтверджує саме виправлений варіант. У звіті показуємо й
179: усі невдалі спроби, а не лише останні успіхи.
180: 
```


END OF PACKET. Deliver the complete plan review.
