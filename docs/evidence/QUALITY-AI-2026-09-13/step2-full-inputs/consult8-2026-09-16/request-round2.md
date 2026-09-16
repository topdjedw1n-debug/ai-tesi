**Note for the reviewer: everything you need is inside this prompt (situation, both round-1 answers, Fable's proposals). Do not look for a request file. Reading the repository files listed at the end is optional.**

# Consultation #8 — round 2: converge on the best and most needed fix and its implementation

Same situation as round 1 (repeated below for a stateless session). You now see three things: (1) the other reviewer's round-1 answer, (2) your own round-1 answer, (3) Fable's proposals, written before reading either answer. The founder's instruction: "find together the best and most needed solution for us and its implementation."

Answer in this order:
1. **Verdict on direction** — which single change is the most needed now (one of the options on the table or a combination), and why; name what you reject and why.
2. **Where you disagree** with the other reviewer or with Fable — state the disagreement and the evidence that would settle it.
3. **Implementation** of the chosen change: stages, where in the pipeline (S2 fetch / S2 selection / before S3 / warnings), what is recorded for replay, what the manager sees, the $0 proof on the three recorded runs, the confirmation run(s) and their acceptance criteria, cost and time. Keep the writer (S4 rules) untouched.
4. **Risks to the AI/similarity results already achieved** and how the plan guards them.

Be decisive: the founder wants one plan to implement, not a menu.

## Situation (as in round 1)

## Goal and constraints (canon, 16.09.2026)
- Platform first: a manager alone reaches a DOCX; delivery bar similarity ≤ 10 % AND AI ≤ 10 % on the exact final DOCX; no human rewriting; content accepted by the agency (Tanya) after an editor's reading. Verification of sources is the system's job.
- The writer is frozen (S4 rules2-B text, plan v2, framing rules, plan check, no legal-window cap, quote budget); consultations #6–#7b: no new writer/plan rule sentences, no lab runs of the same law work, no model change, no mandatory PDFs as policy.
- Founder today: "We need to fix this [weak material], but without harming what we built in terms of AI and plagiarism, and aim for stable results." The next real order from Tanya can arrive any time; every code change must be provable at $0 on recorded runs before a paid run.

## What happened today (all on the same frozen writer, all through the cabinet, no manager PDFs)
| Work | Level | Sources with full text | Full texts on topic | Body sections written on abstracts only | Compilatio similarity / AI |
|---|---|---|---|---|---|
| Economics A2 (digital marketing, SMEs), 16.09 morning | bachelor | 9/17 | 9 | 0 | 3 % / 3 % |
| Economics E2 (SME credit and fintech), 16.09 evening | master | 6/16 | 1 | 6 of 13 | 6 % / 8 % |
| Biology (antibiotic resistance), 16.09 evening | bachelor | 10/20 | 8 | 1 of 11 | 5 % / <1 % |

Three files in a row under the bar on three disciplines. The detector is not the problem any more. The problem is what the writer is given:

1. **Full texts are refused by publishers.** Of the open-access links found by Crossref/OpenAlex, 10/16 (economics) and 9/20 (biology) answered HTTP 403: ScienceDirect (JavaScript challenge page), SSRN, MDPI, Sage, Wiley, ASM, OECD iLibrary and three Italian university repositories (handle.net → Cloudflare-style block). I re-tested from my Mac: plain browser headers → 403; a Chrome-impersonating TLS client (curl_cffi) → 0/20 PDFs (MDPI returns 200 with a 2 kB HTML stub). Unpaywall's best_oa_location points to the same publisher URLs. Alternatives checked at $0: Europe PMC has full text for 5/20 (all biology, none of economics); OpenAlex lists a repository copy with a pdf_url for 7/20 (not tested for reachability). So the system reads whatever does not block, which is not the same as what is relevant.
2. **Off-topic full texts pass into the pack and become the main material.** In E2 the only large readable text was a 348-page book on cyber-risk regulation in banking; it received 47 of 208 in-text citations, and the S6 reviewer flagged the mismatch. In biology two off-topic Italian theses (HIV integrase; a hyaluronic-acid ester) were fetched; one was offered as material in two sections (not cited in the end). The selection score of the evidence windows does not separate them: the cyber-risk book scored 0.32–1.16 across five sections, the on-topic fintech review 0.72–1.13 (score = term overlap between windows and the section's queries). The on-topic record filter passed the book because its title mentions the banking market.
3. **Sections without material are written on abstracts.** E2: P2P lending, crowdfunding, minibond, complementarity, costs, discussion — six sections; no source about crowdfunding or minibond exists in the pack at all. The detector scored those sections 0–28 % (mean 7.9 % vs 1.8 % with documents), so the price is mostly content, not AI.
4. **The master's introduction "about the work"** (research question, objectives, methodology) scored 50 % AI in E2, while the bachelor's introductions written from a fact scored 0 % (A2, biology). The frame writes the introduction last from the findings; the master's structure invites meta-text.
5. What an editor would see but the detector does not: a methodology section that describes other studies' methods (A2); 47 citations to a book off topic (E2); the same opening sentence three times (E2).

## What the system already has (so you do not propose it again)
- S2: topic-anchored queries per subject subsection (Crossref, OpenAlex, Semantic Scholar with visible failures), on-topic filter on title/abstract, verification of every candidate, full-text fetch of open-access links with a plain HTTP client, per-section evidence windows (round-robin, character budgets), warnings `section_without_documents`, `plan_material_gap`, `source_full_text_unavailable`, shown to the manager in words on the work page.
- S3 plan check: a primary document leads each subject section; case sections without a case source are flagged.
- S4 writer frozen; S5 renders and verifies citations; S6 advisory review.
- Recorded runs of all three works (packs, windows, full-text pages, section texts) — any change can be replayed at $0.


---

# Round-1 answer of reviewer A (Astra / Codex)

1. **Напрямок: найпотрібніше зараз — добирати матеріал за тим, чи він дозволяє відповісти на питання розділу.**

Три файли під 10/10 дають підставу зберегти писаря. Вони ще не доводять стабільності результату або прийнятності змісту. Наступна зміна має усувати конкретну причину слабких робіт: доступний великий документ отримує роль головного джерела, хоча потрібне питання він майже не розкриває.

Критерій успіху: для предметного питання можна показати **конкретний придатний уривок і пояснити, що саме він підтверджує**. Кількість PDF, розмір пакета і високий збіг слів цього не замінюють.

Я б не вводив нових правил писаря, нового модельного рецензента, обов’язкових PDF від менеджера, автоматичної зупинки через прогалини або довільної стелі цитувань одного джерела. Також не підвищував би просто поріг нинішнього score: ваші результати вже показують, що він недостатньо розділяє придатний і сторонній матеріал.

2. **Рішення трьох проблем матеріалу.**

**Заблоковані тексти — запасні адреси тієї самої праці.** Це найменша перша зміна в отриманні матеріалу.

Зараз [отримання повних текстів](/Users/maxmaxvel/AI%20TESI/apps/api/app/services/full_text_sources.py:69) зберігає одну адресу OpenAlex. Я б зберігав список доступних копій під час об’єднання результатів каталогів. Успішне завантаження залишав би як є; після відмови пробував би обмежену кількість інших адрес того самого джерела.

Перший маршрут — репозиторні `locations[].pdf_url` OpenAlex. Його `best_oa_location` обирається за властивостями копії, зокрема перевагою видавця, а не за доступністю для нашого завантажувача. Тому повторне отримання лише «найкращої» адреси закономірно повертає до того самого блокування. [Документація OpenAlex](https://help.openalex.org/data/works/open-access/).

Перевіряти потрібно зміст відповіді, відповідність праці та версію документа. HTTP 200 із HTML-заглушкою не є отриманим текстом; сторінки репозиторної версії не можна видавати за пагінацію видавничої.

Europe PMC — наступний цільовий маршрут для біології. Його API справді надає XML відкритих повних текстів. Але нинішній шлях матеріалу формує `[page N]`: XML потребує коректних локаторів, його не можна просто нарізати на вигадані «сторінки». Тому я почав би з придатних PDF-копій, а XML додавав окремо після перевірки сумісності з чинним цитуванням. [Europe PMC API](https://europepmc.org/RestfulWebService).

**Доказ за $0:** перевірити вже знайдені сім репозиторних адрес, записати справжні відповіді та повторити обробку без мережі. Рахувати нові придатні тексти й покриті питання, враховуючи дублікати. Сім адрес поки не означають сім отриманих документів. Старі записи 403 самі по собі не доведуть працездатність нового маршруту.

**Ризик:** новий матеріал змінить письмо навіть за незмінної інструкції. Можливе зростання similarity через ближчий переказ; незмінний бюджет цитат цього не гарантує. Обхід антибот-захисту після вже невдалих перевірок я зараз не розвивав би.

**Домінування стороннього тексту — однакова перевірка придатності для всіх джерел розділу.**

У [доборі вікон](/Users/maxmaxvel/AI%20TESI/apps/api/app/services/full_text_sources.py:334) є конкретна асиметрія: назване планом джерело обходить поріг, застосований до інших документів. Якщо вікна не потрапили в добір, його збережений уривок усе одно повертається. Крім того, поле `question` уже існує в записаних планах, але `section_queries` його не використовує.

Я б перевіряв пару **«питання розділу — уривок»**, розрізняючи опору для відповіді, допоміжний контекст і сторонній матеріал. Перший варіант без нового виклику моделі:

- використовувати специфічні поняття питання та вже наявні двомовні терміни S1;
- перевіряти їх у змістовному контексті уривка, а не лише в назві, списку літератури або загальних словах;
- застосовувати однакові умови до запланованих і доданих джерел;
- не повертати відкинутий сторонній текст через запасний уривок.

Це кандидат на покращення відсіву, **не доведений семантичний класифікатор**. Його придатність треба встановити на записаному матеріалі.

Книгу Tomasi я не забороняв би цілком за назвою: збережені сторінки 46 і 52 справді містять матеріал про альтернативне фінансування. Проте визначення crowdfunding не робить книгу достатньою основою для висновків про вартість, доступність і ефективність фінансування ПМІ.

**Доказ за $0:** для фактичних пар «питання — запропонований уривок» у трьох роботах зафіксувати очікувану придатність і порівняти старий та новий добір. Перевіряти одночасно вилучення сторонніх фрагментів і збереження корисних. Показник — не «Tomasi зник», а «непридатний матеріал перестав підміняти відповідь».

**Ризик:** надто суворий відсів збільшить дефіцит матеріалу. Тому його не можна приймати лише за успішне видалення поганих прикладів; потрібні позитивні приклади A2 та біології. Ліміти правових вікон і правила цитування залишаються чинними.

**Розділи без матеріалу — спочатку встановити причину прогалини, потім один обмежений прохід доповнення.**

Тут записи уточнюють початковий діагноз. У всіх шести проблемних розділах E2 книга має `windows=0`, **`capped=true`**, але писар отримує її збережений уривок зі сторінок 46 і 52. Отже, це не буквально шість розділів лише на анотаціях. У біології розділ про біоплівки справді отримує тільки анотації. [Запис E2](/Users/maxmaxvel/AI%20TESI/docs/evidence/CABINET-ECONOMIA-2-2026-09-16/E2-doc24-events.json).

Потрібно розділяти: джерело не знайдене; текст недоступний; текст непридатний; придатний матеріал відсічений добором. Для цих випадків різні дії.

До остаточного заморожування пакета я додав би один обмежений прохід: використати вже знайдених кандидатів для непокритих питань, спробувати їхні альтернативні копії; додатковий пошук робити лише там, де відповідного кандидата взагалі немає. Не збільшувати весь пакет навмання й не знімати всі обмеження: це може лише дати Tomasi більше місця.

Обговоренню не обов’язково потрібен окремий PDF — воно може спиратися на достатні докази основних розділів. А опис власної методології потребує фактів про виконану роботу. Чужі інтерв’ю не підтверджують, що ця робота проводила інтерв’ю. Саме отримання додаткових PDF цю помилку A2 не виправить.

**Доказ за $0:** повторний добір із записаних кандидатів і текстів має показати для кожного питання нову опору або чесно збережену прогалину. Відсутні в записі результати нового пошуку доведеться окремо отримати й записати через безкоштовний маршрут. Не підміняти їх вигаданими успішними відповідями.

**Ризик:** зайві запити, затримка та нова нерелевантність. Тому один прохід із наявними обмеженнями; залишкова прогалина залишається попередженням, а не новою причиною падіння генерації.

Для всіх трьох змін межа доказу одна: **за $0 можна довести кращий добір і технічну поведінку, але не майбутні відсотки Compilatio**. Стару відповідь писаря не можна підставити під змінений матеріал і назвати це доказом збереження 10/10. Це перевіряється на наступному реальному замовленні, на його точному DOCX.

3. **Вступ магістерської: так, варто перевірити й виправити застосування вже погодженої рамки.**

У записі E2 вступ завершено **о 17:05:26 UTC**, другий розділ — о 17:05:50, висновки — о 17:10:10. Вступ написаний першим. В A2 та біології він написаний останнім.

Це суперечить передумові, що вступ E2 вже створювався наприкінці з отриманих findings. Найімовірніший кандидат — розпізнавання розширеної назви `Introduzione: domanda di ricerca, obiettivi e metodologia`. Точну причину класифікації ще треба підтвердити; порядок подій уже встановлений. У [виклику S4](/Users/maxmaxvel/AI%20TESI/apps/api/app/services/executor_v2/sections.py:24) ознака рамкового розділу керує підключенням чинної інструкції та findings.

Найменший крок: перевірити розпізнавання вступу й висновків із розширеними назвами та відновити порядок «тіло → висновки → вступ». **Без нових речень інструкції й без видалення дослідницького питання, цілей або методології.**

За $0 на записаних планах перевіряються порядок, передані findings і застосування чинної рамки. Зниження 50 % цим ще не доводиться. Редактор оцінює результат, але не переписує його.

4. **Правило для реальних замовлень Тані: часткова нестача документів не зупиняє генерацію, але не дає дозволу на видачу.**

Менеджер продовжує роботу за чинним режимом. Наявні попередження з конкретними розділами переходять у записку редактору. Таня не повинна шукати PDF, перевіряти посилання або переписувати слабкі розділи.

Скасування — для порожнього або явно чужого пакета за чинним правилом. Обіцянки «зупинити за $0,10 після S2» тут немає: автоматичної паузи немає, а `section_without_documents` у коді формується вже перед письмом відповідного розділу.

Після завершення — один скан незмінного DOCX і редакторське читання. Якщо потрібне питання не розкрите або джерела не підтверджують написане, файл не приймається навіть за 3/3. Редактор фіксує дефект змісту; перевірка джерел і його подальше системне усунення залишаються відповідальністю платформи.



---

# Round-1 answer of reviewer B (Grok)

Спочатку прочитаю канон, докази трьох сьогоднішніх робіт і код шляху матеріалів — без ваших пропозицій, щоб відповідь не була прив’язана до вже готового рішення.Канон прочитаний. Далі — докази трьох робіт і код добору матеріалів.Докази зібрані. Тепер дивлюся, як саме система відбирає, качає й оцінює матеріал.**Напрямок: робити зараз. Одна зміна — писар має читати текст, який відповідає питанню розділу, а не «який PDF випадково відкрився».**

Три файли під 10/10 це вже довели: детектор більше не головна стіна. Стіна — матеріал. Ранок (економіка, 9 повних текстів по темі) і біологія (8 по темі) дали прийнятний для детектора файл, бо пощастило з відкритими копіями. Вечір (магістерська економіка) дав 6/8 на детекторі й роботу, яку редактор не прийме: шість розділів без документів і 47 посилань на книгу не по темі. Стабільність — це прибрати цю лотерею, не чіпаючи замороженого писаря.

**Чого явно не робити:** нові речення правил писаря чи плану; зміна моделі; лабораторні прогони тих самих робіт; обов’язкові PDF як політика; зупинка генерації через попередження; обхід видавничих стін (браузерний TLS, підміна клієнта — уже перевірено, 0 з 20 PDF); Europe PMC як головний фікс (0 з економіки); пауза після пошуку джерел у коді; загострення перевірки плану «про запас».

---

## 1. Напрямок

Найпотрібніша зміна зараз: **на вході до розділу лишати лише читабельний текст, який відповідає питанню цього розділу.** Два механізми, в цьому порядку:

1. коли видавець відмовляє, брати іншу вже відому копію того самого запису;
2. повний текст веде розділ лише якщо він про це питання, а не просто «про банки» чи «про Італію».

Спочатку (1), потім (2). Якщо зробити лише відсів чужого, вечірня економіка стане ще порожнішою, і штучний інтелект на файлі може підповзти до 10. Якщо зробити лише нові адреси без відсіву, наступна випадкова книга на 300 сторінок знову забере роботу.

Це наближає ціль етапу: менеджер сам доходить до DOCX, а зміст уже не будується з чужого тому. Писар, план і модель не чіпаємо. Доказ — на трьох сьогоднішніх записах за $0, без нового платного письма.

---

## 2. Три проблеми матеріалу

### Заблоковані повні тексти

**Що зламано.** Система зберігає одну адресу — «найкращу відкриту» з каталогу — і качає її звичайним HTTP. Видавці (ScienceDirect, SSRN, MDPI, Sage, Wiley, ASM, OECD) і частина університетських репозиторіїв відповідають 403. Unpaywall веде на ті самі видавничі адреси. Підміна браузера не рятує: MDPI віддав 200 і порожню HTML-заглушку. Читається не найкраще джерело, а те, яке не вміє закритися.

**Механізм.** Не битися зі стіною. Для кожного вже знайденого запису зберігати **усі** відомі PDF-адреси (у OpenAlex це не одна «найкраща», а список копій, зокрема репозиторійні; те саме, де є, у Semantic Scholar). Порядок спроб: репозиторій / PMC / прямий файл → видавець. Перша відповідь із текстовим шаром перемагає. Клієнт той самий, що зараз. Нових каталогів і нового обходу Captcha не треба. Europe PMC лишити як можливу додаткову копію для біомедицини, не як фікс економіки.

**Доказ за $0.** На записаних DOI двох вечірніх робіт (16 і 20 записів з відкритим посиланням) безкоштовно перепитати OpenAlex список копій і прогнати їх тим самим завантажувачем, що в проді. Критерій: скільки з 10+9 відмов стають сторінками; чи серед нових сторінок є тексти про краудфандинг / мінібонди / біоплівки. Письмо не запускати. Якщо з 7 репозиторійних `pdf_url` жоден не відкривається — цей шлях закритий фактом, і не будуємо навколо нього продукт.

**Ризик для 3/3 і 5/<1.** Низький, якщо нові сторінки лише **додаються** до вже прочитаних. Ранкова економіка і біологія не втрачають свої 9 і 8 текстів. Схожість може трохи зрости, бо з’явиться більше справжнього переказу; на трьох файлах при 8–10 повних текстах вона була 3–6 %. Штучний інтелект на добрих текстах падав, не ріс.

### Чужі повні тексти забирають роботу

**Що зламано.** Фільтр «по темі» дивиться на назву й анотацію запису двома словами теми. Книга про кіберризик у банківському ринку проходить, бо там є банк. Далі вона стає «першоджерелом» (є PDF), перевірка плану ставить її першою в розділ, а оцінка вікон — збіг слів запиту розділу зі сторінкою. Запит розділу повний банківських слів, тому книга дає 0,32–1,16 нарівні з оглядом fintech (0,72–1,13). Бюджет вікон крутиться по документах: 348 сторінок → 47 цитат. У біології той самий тип: дві чужі дисертації пройшли в пакет, одна потрапила в матеріал двох розділів.

Дірка вже відома коду: сторонній документ **без** плану в розділ не пускають (поріг за словами саме цього розділу). Документ, який план поставив першим, цей поріг **обходить**. Саме тому книга вела і краудфандинг, і мінібонди.

**Механізм.** Той самий поріг, що вже стоїть на незапланованих документах, застосувати і до запланованих **вікон**. Немає слів питання розділу в назві/анотації або в найкращих вікнах — розділ отримує лише коротку анотацію, не сторінки. Перевірка плану не підставляє першим PDF, який не відповідає словам розділу. Писар не змінюється: він як і раніше пише з того, що йому дали.

Калібрування порога — на трьох записаних пакетах, не «на око»:

- вечірня економіка: книга про кіберризик і текст про міграції у Венето **не** дають вікон розділам про P2P / краудфандинг / мінібонди;
- біологія: ВІЛ-інтеграза і ефір гіалуронової кислоти **не** входять у розділи про резистентність;
- ранок і вісім біологічних текстів по темі **залишаються**.

Окремо не закривати «довгий PDF = погано»: довгий **по темі** текст — це якраз те, чого не вистачало ввечері.

**Доказ за $0.** Прогін уже наявної функції добору вікон на трьох записаних пакетах і вікнах. Без моделі. Критерій — таблиця «які ключі з вікнами в якому розділі» до/після. Успіх: 47 цитат на кіберкнигу стають неможливими, бо вона більше не стоїть у матеріалі чужих розділів.

**Ризик.** Якщо зробити це **без** нових копій, вечірня економіка матиме ще більше розділів на анотаціях. На вже виміряному файлі такі розділи мали в середньому 7,9 % ШІ проти 1,8 % з документами; файл був 8 %. Отже відсів без нових текстів — це ризик підповзти до планки, не виграш. Порядок обов’язковий: спочатку інші копії, потім відсів.

### Розділи без матеріалу

**Що зламано.** У пакеті 40 джерел не було жодної назви з crowdfunding/minibond, хоча це слова теми **після двокрапки** і окремі розділи плану. Ядро пошуку бере перші чотири змістовні слова **до** двокрапки: «доступ, кредит, малі, середні». Краудфандинг і мінібонди в ядро не входять. Далі 40 місць заповнюються тим, що каталоги віддали на «кредит ПМІ». Розділ пишеться з анотацій або, гірше, з чужого PDF, який план підставив як першоджерело.

**Механізм, два шари.**

1. **Добір місць у пакеті** (без нових запитів, якщо хіти вже є в записі пошуку): серед уже знайдених кандидатів тримати хоча б одне джерело, у назві чи анотації якого є власні слова кожного предметного листка (crowdfunding, minibond, P2P), а не лише загальне «кредит». Якщо в записаних відповідях каталогів таких рядків немає — тоді, і лише тоді, ядро запиту має брати характерні слова з **усієї** теми, включно з частиною після двокрапки, а не обрізати її. Це не нові речення плану, це той самий побудовник запитів.
2. **Чесність розділу:** немає документа по питанню — розділ лишається з попередженням «без документів», писар пише з анотацій, як зараз. Не зливати розділи, не вигадувати джерело, не зупиняти генерацію.

**Доказ за $0.** Спочатку полічити в записаних відповідях каталогів вечірньої економіки, чи crowdfunding/minibond узагалі приходили і їх витіснили з 40, чи їх не було. Це вирішує, чи достатньо перерозподілу місць, чи треба ще ядро запиту. Перерозподіл і нові рядки запитів перевіряються на записаних деревах плану (як уже робили для ранкової економіки) без письма. Живий пошук нових рядків — копійки квоти каталогу, не платне письмо; його можна зробити окремим зондом, не прогоном роботи.

**Ризик.** Якщо з’являться справжні тексти про краудфандинг, розділи стануть схожі на ранок, а не на вечір: і зміст, і ШІ. Якщо їх немає і ми лише чесно пишемо з анотацій (без кіберкниги) — ШІ розділу може лишитися близько 8 %, файл не повинен розвалити similarity (там донор — Banca d'Italia, не чужа дисертація).

---

## 3. Магістерський вступ на 50 %

**Зараз не чіпати. Не рамку, не план, не писаря. Лишити редактору.**

Правило вступу вже вимагає відкрити фактом із готових розділів і забороняє описувати структуру роботи. Бакалаврські вступи з фактом дали 0 %. Пік 50 % сів на назву «питання, цілі, методологія», яку попросив бриф магістра, і на мета-текст «про роботу». Це не дірка матеріалу в тому ж сенсі, що кіберкнига: тіло тієї ж роботи мало 4,5 % ШІ.

Нове речення правила вступу заборонене консультаціями. Міняти рамку чи план заради одного розділу одного файла — це розморожування писаря під виглядом матеріалу. Після фіксу матеріалу цей пік може лишитися: тоді це окреме рішення, не сьогодні.

Редактор уже бачить повтор першого речення тричі. На видачу цього файла цього досить.

---

## 4. Що робити Танї на живому замовленні, поки код ще старий

Вона **не** судить, чи PDF по темі: це робота системи. Вона дивиться текст попереджень на сторінці роботи після завершення (пошук одразу переходить у план, паузи немає — і її не додаємо).

- **Пакет порожній або явно чужий** (як і зараз) — скасувати, не писати.
- **0–1 розділ тіла «без документів», назви повних текстів схожі на тему** — як біологія: один скан точного файла, читання редактора, видача за звичайними правилами.
- **Кілька розділів тіла «без документів»** (як шість увечері) — це чернетка для редактора, не кандидат на видачу клієнту. Роботу **не** переписувати. Один скан точного файла лишається (рівні 15/14 і 10/10 як зараз). У записці редактору вже є ці розділи — їх і читати першими.
- **PDF клієнта** — лише якщо клієнт їх уже дав. Не збирати PDF «щоб система запрацювала».
- Не зупиняти роботу посеред письма через попередження плану. Не кликати розробника всередині замовлення, якщо пакет не порожній і не чужий.

Якщо наступне замовлення прийде до правки — воно йде на тому, що на сервері. Виправлення спочатку доводиться на трьох сьогоднішніх записах за $0, і лише тоді — окремий коміт і доставка.

---

**Найменший достатній наступний крок:** на записаних DOI вечора перевірити, які репозиторійні копії взагалі відкриваються тим самим завантажувачем; паралельно на трьох записаних пакетах показати таблицю вікон до/після порога «документ відповідає питанню розділу». Якщо жодна чужа копія не відкривається — лишається лише поріг і чесне попередження, без ілюзії, що ми «навчились качати ScienceDirect». Письмо, скан і живе замовлення Тані в цей доказ не входять.

---

# Fable's proposals and added facts

## Fable's proposals (round 2 — written before reading your round-1 answers, sent after them)

Direction I lean to: fix the **material path before the writer** (S2 fetch and selection), leave S3/S4 frozen, prove every change at $0 on the three recorded runs, then confirm with at most one cabinet run per discipline. Nothing that adds a blocking stop; every new signal is a warning the manager sees.

A. **Read what can be read: alternative open-access locations before giving up** (S2 fetch, `full_text_sources`). Today: one URL per record (Crossref/OpenAlex `oa_url`), plain HTTP client, 403 → nothing. Proposal: for every record with a DOI, try in order (1) Europe PMC full-text XML through its REST API (biomedicine; 5/20 of today's blocked items have a PMCID, and the API returned the full text for all three I tried, ≈ 500 kB each, no bot wall), (2) OpenAlex repository locations — **tested: 0/7 readable** (landing pages or the same 403 walls, PMC's own pdf endpoint returns an HTML stub), so this step is weak, (3) CORE API for repository copies (untested; needs a free key), (4) the publisher URL last. Honest expectation: biomedicine gains a lot from (1); economics/law/computer science gain little from any of these — there the readable material comes from the manager's PDFs or from a headless browser, which is untested and heavy. Record which location worked. Not proposed: a headless browser in the API container (heavy, fragile, and ScienceDirect's challenge may still block) — to be decided only if (1)–(3) leave most items unread. Proof at $0: run the fetcher offline on the 20 blocked items of E2/biology and count readable PDFs; then one S2-only rerun of the E2 brief (≈ $0.07) to see the full-text count on the same brief.

B. **A document-level relevance check for full texts before they become material** (S2, after fetch, before the evidence windows). Today the record passes an on-topic filter on title/abstract (the cyber-risk book passed because "mercato bancario" is in its title), and the window score is term overlap — it cannot tell a 348-page off-topic book from a review on the topic. Proposal: for each fetched full text, one short model judgment on title + abstract + first pages against the thesis topic and the subject subsections ("is this document about the topic; which subsections does it serve; verdict on_topic / partly / off"), ≈ $0.01–0.03 per document (≤ 20 per work, ≈ $0.3). Off-topic documents keep their verified bibliography row but contribute no windows; the manager sees `source_off_topic` as a warning with the title. No change to the writer, the plan or the on-topic record filter. Proof at $0: replay the recorded packs of A2/E2/biology with the recorded judgments (or run the judgment on the 25 fetched documents once, ≈ $0.5) and check that the cyber-risk book, "Migrazioni in Veneto", the HIV thesis are excluded and the fintech review, the AMR review, stewardship are kept; then replay S4 evidence selection to show the six E2 sections lose the book's windows.

C. **Targeted second search for subsections left without material**, before S3, using the subsection's own terms and an open-access-available filter (OpenAlex `is_oa` + a location that is a repository/PMC), so that "crowdfunding" and "minibond" get sources the system can actually read. Only when a subject subsection has zero full-text windows after A+B. Warning stays if still empty. Proof: recorded E2 scopes → which subsections trigger, what the query returns (live catalogue calls ≈ $0).

D. **Master's introduction** — not now. Observe on the next master's file; if the "about the work" introduction repeats at ≥ 30 %, adjust the frame rule later (writer change → after real orders). The bachelor's introductions are at 0 %.

E. **Operational rule for Tanya now** (no code): if the work page after S2 shows `section_without_documents` for two or more subject sections, the manager attaches the client's PDFs for those subsections or asks the client, and only then starts; otherwise the work runs and the editor reads those sections first. The stop at that point costs ≈ $0.07.

Order: A → B → C; D observe; E immediately. Time: A one day, B one day, C half a day, all provable at $0 on the recorded runs, then one cabinet run per discipline (≈ $2 + one scan each) as confirmation. Risk to AI/similarity: A and C add readable on-topic text (the direction that produced 3/3 and 5/<1); B removes off-topic text — the only risk is a false "off-topic" verdict that leaves a section on abstracts, which is the state we already have today and is visible as a warning.

### Facts added after round 1 (from my own checks, $0)
- OpenAlex repository copies of today's blocked records: **0 of 7 readable** with the production client (landing pages or the same 403 walls; PMC's own pdf endpoint returns an HTML stub). Grok's condition "if none of the seven opens, that path is closed by fact" is met.
- Europe PMC REST full-text XML: **3 of 3 fetched** (≈ 500 kB each) — a real route for biomedicine only; needs its own locators (Astra's point: no invented `[page N]`).
- Astra's two findings I had missed and accept: (a) the planned source bypasses the window threshold and, with `capped = true`, its stored excerpt is still handed to the writer — so the six E2 sections were not written on abstracts alone but on the cyber-risk book's excerpt (pages 46, 52); (b) the E2 introduction was written **first** (17:05:26 UTC), not last: the frame detection did not recognise the extended title "Introduzione: domanda di ricerca, obiettivi e metodologia". That is a defect of the existing frame logic, not a new rule — I would fix the detection and the order, with a test on the recorded plans, no new sentences.
- Grok's finding I accept: the query core takes the first four content words before the colon, so "crowdfunding" and "minibond" never entered the search; the recorded catalogue answers can show whether such records were found and pushed out of the 40 seats or never found.

### Where I now stand (for round 2)
Most needed change, in one sentence: **the same suitability test for every document a section receives (planned or added), plus honest alternative copies and Europe PMC for what is blocked, plus a query core that includes the topic's own subject words** — three small, replayable S2/S3 changes, no writer change, provable on the three recorded runs. My earlier idea of a model judgment per full text (B) I keep only as a fallback if the term-based suitability test cannot separate the recorded good and bad cases; the reviewers' term-based version is cheaper and replayable without a model.


## Facts added by Fable after round 1 (new, from the recorded run of E2, $0)
- The catalogues DID return crowdfunding/minibond records for E2: 32 distinct titles ("Equity crowdfunding: caratteristiche, problematiche e diffusione", "Crowdfunding: The Case of Italy", "Why SMEs go to crowdfunding?", "PROS AND CONS OF MINIBONDS ... IN THE ITALIAN MARKET", "Le emissioni di minibond delle imprese in rete" ...); 31 went to verification and 27 were verified. **None entered the pack of 40.** The node-coverage rule ("at least two sources with text per subject node") was satisfied by generic bank-credit records that the same crowdfunding query had also returned (the pack shows 11–12 sources "covering" the crowdfunding and minibond nodes, none of them about crowdfunding or minibond). So the loss is in the seat allocation after verification, not in the queries and not in the on-topic filter.
- The E2 introduction "Introduzione: domanda di ricerca, obiettivi e metodologia" was not recognised as a frame section (`FRAME_TITLES` accepts "Introduzione" alone or with "generale/finale/e ..." but not a colon); it was therefore written first, without the framing rule and without the findings. Same for any "Discussione: ..." title.

---

## Files you may read (repository root is your working directory, read-only)
- Evidence of today's three runs: `docs/evidence/QUALITY-AI-2026-09-13/step2-full-inputs/s2-topic-anchored-2026-09-16/README.md` (economics A2), `docs/evidence/CABINET-ECONOMIA-2-2026-09-16/README.md` (E2: pack, full texts, per-section scan, the 403 diagnosis), `docs/evidence/CABINET-BIOLOGIA-2026-09-16/README.md` (biology).
- Code of the material path: `apps/api/app/services/executor_v2/sources.py` (S2), `apps/api/app/services/search_queries.py` (topic-anchored queries and the on-topic filter), `apps/api/app/services/full_text_sources.py` (open-access fetch, per-section evidence windows and their score), `apps/api/app/services/plan_check.py` (S3 plan check), `apps/api/app/services/executor_v2/sections.py` (S4 call; do not propose changing `writer_rules.py`).
- Canon: `docs/AGENT_SYNC.md` (block `founder-priority-2026-09-09`, state of 16.09), `docs/plans/IDLE-SESSION-2026-09-16.md`.
