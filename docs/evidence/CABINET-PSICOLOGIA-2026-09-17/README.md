# Репетиція через кабінет: психологія (соцмережі й благополуччя підлітків), магістерська, 20 сторінок — 17.09.2026

**Підстава:** фаундер 17.09 («Так, але давай не економіку, а психологію»; «саме економіка не обов'язкова» — повтор E2 лишається доказом за $0 на записах) після доставки виправлення матеріалу `90a678f`: четверта дисципліна, магістерський рівень (рамка вступу з двокрапкою), заморожений писар, через кабінет, без PDF. Мій бриф: [brief.json](brief.json) (tesi magistrale, 20 сторінок, APA; підрозділи: confronto sociale, immagine corporea, autostima, FoMO, uso problematico, sonno, regolazione emotiva, fattori protettivi, prevenzione a scuola e in famiglia). Запуск драйвером із мого терміналу під `manager1`.

**Хід.** Робота №26 / запуск №29: S1 09:40:22 UTC (18 с) → S2 12,2 хв (09:40:40–09:52:53: пошук 84 запити за хвилину, 292 верифікації за 11 хв — Semantic Scholar 429, arXiv тайм-аути) → S3 2 хв → S4 5,7 хв (16 розділів) → S5/S6 → DOCX 10:00:50. **$2,06**, 286 105 токенів, 38 викликів моделі. Пакет після S2 — 40 джерел, більшість про соцмережі й підлітків, кожен вузол ≥ 2 джерела → продовжено без втручання. Експорт через клієнтський маршрут — 409 (немає випущеного артефакту; за задумом), файл запису знято з S3.

**Файл запису:** [PSY-doc26-job29-c69ba0ec.docx](PSY-doc26-job29-c69ba0ec.docx), sha256 `c69ba0ecd5d85bed24c9825543782719b71b5337e5c6e29c31646542559de598`, 56 537 байт, 22 сторінки; на скан у `Downloads/Thesica-на-скан-10-2026-09-17/`. Записка редактору: [nota-redattore-PSY-doc26.md](nota-redattore-PSY-doc26.md). Факти запуску: [run-facts.json](run-facts.json); знімок пакета з покриттям вузлів: [PSY-doc26-pack-snapshot.json](PSY-doc26-pack-snapshot.json); події без текстів розділів: [PSY-doc26-events.json](PSY-doc26-events.json); матеріал по розділах і цитування: [PSY-doc26-material-analysis.txt](PSY-doc26-material-analysis.txt); діагноз воріт: [PSY-doc26-gate-margins.txt](PSY-doc26-gate-margins.txt) ([gate_margins.py](gate_margins.py) на повному записі doc26 у scratchpad сесії, 7,7 MB).

## Що показав прогін до скану

| | |
|---|---|
| Пакет | 40 (Crossref 18 / OpenAlex 22): повний текст 8, анотація 31, без тексту 1; покриття вузлів (own-терміни): усі предметні вузли ≥ 2 (sonno 2, autostima 10, FoMO 8, PSMU 7, immagine corporea 5, confronto sociale 29) |
| Повні тексти | 8/22; відмови: 12 × HTTP 403 (MDPI ×3, handle.net ×2, OUP ×2, ScienceDirect, JAACAP/Elsevier, Wiley, AHA, flore.unifi), 2 × not_pdf (Elsevier landing, AAP) |
| По темі серед повних текстів | **3 із 8**: «Problematic Social Media Use: … Nationally Representative Adolescent Sample» (13 с.), «The Impact of Social Media on the Mental Health of Adolescents and Young Adults» (10 с.), «Advances in Social Media Research» (28 с., загальний огляд); **не по темі 5**: «Educare (al)la sessualità» (дисертація, 214 с.), «A rapid review of the impact of COVID-19 on the mental health of healthcare workers» (18 с.), «The influence of parental practices on child … food consumption» (14 с.), «Preventing school disaffection … ESF projects» (13 с.), «New trends in drug addiction: the synthetic drugs» (8 с.) — усі пройшли doc-gate і секційний іспит, запропоновані як матеріал у 9 розділо-слотах (§1, §2, §3, §5, §8, §9, §12, §13, §14, §15) |
| Що з цього в тексті | сторонні тексти не цитуються ніде, крім §14 «Interventi di prevenzione in famiglia»: 7 речень на статті про харчування (17 вікон, єдиний повний текст розділу); «Advances in Social Media Research» — 6 згадок (§3, §15), доречно |
| Розділи без повнотекстових документів | 2 із 14 у тілі: §4 Misure del benessere psicologico, §11 Regolazione emotiva (плюс §16 висновки — за задумом); причини в попередженні словами |
| Рамка | вступ написаний останнім (порядок 2…16, 1) — «Introduzione: domanda di ricerca e cornice del problema» розпізнано; вступ відкривається фактом, висновки відповідають на питання |
| Посилання в тексті | ≈186 на 26 записів бібліографії; найчастіші Bányai 2017 (24 = 13 %), motives scale (15), benessere soggettivo bambini (12), nighttime use & sleep (12), FoMO distress (10); лапки 0,5 %; «(…); (…)» ×6 |
| Попередження | 17: `source_full_text_unavailable` ×1 (14 ключів), `source_no_readable_text` ×1, `plan_material_gap` ×6 (§4, §6, §8, §10, §11, §16 без першоджерела), `outline_scope_unmapped` ×5, `section_without_documents` ×3 (§4, §11: «про питання, але без повного тексту»; §16: «не про питання розділу»), `review_note` ×1 |
| Рецензент S6 | PASS; зауваження: Coherent thesis-style review with clear research question, logical four-chapter structure, and integrated discussion. Claims are consistently tied to citations with page numbers where relevant, and the author repeatedly and appropriately flags limitations: cross-sectional designs, non-adolescent samples (university students, children, clinical adult populations), construct-transfer caveats, and data-access constraints. Note the opening statistic attributes US Pew-type data (24% 'almost constantly', 71% multiplatform) to Bányai et al. 2017 p.1, which is a likely mis-citation, but it is used consistently and does not affect argument integrity. Some sources are only loosely on-topic (substance-use coping, healthcare-worker resilience, food-consumption parental mediation), yet these are transparently marked as construct extensions rather than direct evidence. Bibliography is complete and matches in-text citations. Overall academically sound and internally consistent. |
| Записка редактору | чисел і цитат поза доступними текстами не знайдено; цитат без сторінки немає; **дефект записки:** причини попереджень («без першоджерела», «про питання, але без повного тексту») потрапляють в італійську записку українською — перекласти у `scripts/editor_note.py` окремим комітом |

## Що виправлення матеріалу зробило і чого не зробило

**Зробило.** Розсадка за власними термінами вузла: кожен підрозділ отримав джерела саме про себе (у E2 27 профільних записів не мали місць). Рамка з двокрапкою: вступ останнім (у E2 — першим, 50 % AI). Жодне джерело не веде роботу так, як книга кібер-ризику в E2 (13 % проти 23 % цитувань у топ-джерела). Причини «без документів» — словами.

**Не зробило.** Ворота «документ по темі» і секційний іспит пропустили 5 чужих повних текстів із 8. Діагноз ([PSY-doc26-gate-margins.txt](PSY-doc26-gate-margins.txt)): якорі теми будуються з 6-символьних префіксів слів теми — для цієї теми це `social`, `media`, `use`, `out`, `preven`, `psycho`, `well-b`, `body`, `fear`, `adoles`, `beness`; частка вікон із таким якорем у дисертації про сексуальну освіту 0,59, в огляді про медиків 0,67, у статті про харчування 0,52 — усі ≥ 0,5. Секційний іспит пропускає за `shared ≥ 3` загальних слів (COVID-медики → §8 FoMO через «fear/out/psychological») або за own-термінами, які збігаються буквально, але не за популяцією (огляд про медиків → §12 «fattori protettivi: supporto sociale e resilienza», own = 4). В економіці й біології ті самі правила працювали, бо якорі там специфічні (crowdfunding, minibond, fintech, antibiot…). Той самий загальний якір пропускає в пакет і анотації не по темі (кардіологічні настанови — за `preven`, `use`), а заповнення пакета «читабельні першими» їх підтягує.

**Кандидат правки ($0, довести на чотирьох записах doc23–26 тим самим `material_report.py` + `gate_margins.py`):** якорі теми = багатослівні фрази теми та вузлів («social media», «fear of missing out», «confronto sociale», «regolazione emotiva», «benessere psicologico») плюс поодинокі слова від 7 символів, без коротких загальних (`use`, `out`, `social`, `media`, `preven`, `psycho`, `body`, `fear`); ті самі якорі для on-topic у S2, для doc-gate і для заповнення пакета; у секційному іспиті не рахувати «shared» слова, які є в темі й у більшості пакета. Очікування: дисертація про сексуальну освіту, медики COVID, харчування, dropout, наркотики — без сторінок; три профільні тексти — на місці; A2/E2/BIO — без втрат. Запасний варіант — суд моделі на документ (≈ $0,02/док), якщо детермінований відсів не розділить огляд про медиків і розділ про захисні чинники.

## Скан (фаундер, 17.09 ≈ 13:55) — [detailed-report-PSY-2026-09-17.pdf](detailed-report-PSY-2026-09-17.pdf)

**Similarity 6 %, AI 20 %, у лапках < 1 %** (файл 55,21 kB, 8 114 слів = DOCX запису). **Перший файл на замороженому писарі вище рівня 15 %** (серія: економіка 3/3, економіка-магістр 6/8, біологія 5/<1, психологія-магістр 6/20). Джерела збігів — усі < 1 % (репозиторії unimib, unipd, ujaen, fupress, nurse24…): переказ визначень, без донора.

По розділах (AI за підкресленнями, similarity за підкресленнями — лише частина 6 %; [persection-PSY.json](persection-PSY.json)):

| Розділ | Слів | AI % | sim % |
|---|---:|---:|---:|
| Introduzione: domanda di ricerca e cornice del problema | 411 | 0.0 | 0.0 |
| 1.1 Diffusione dei social media in adolescenza | 501 | 13.8 | 0.0 |
| 1.2 Modelli teorici sull'uso dei social media | 479 | 14.4 | 1.0 |
| 1.3 Misure del benessere psicologico | 394 | 0.0 | 0.0 |
| 2.1 Teoria del confronto sociale e immagini idealizzate | 464 | 48.9 | 2.2 |
| 2.2 Immagine corporea e social media | 467 | 29.6 | 0.0 |
| 2.3 Autostima e uso dei social media | 428 | 63.3 | 0.0 |
| 3.1 Fear of missing out (FoMO) | 417 | 34.8 | 0.0 |
| 3.2 Uso problematico dei social media | 522 | 0.0 | 0.0 |
| 3.3 Qualità del sonno negli adolescenti | 484 | 13.8 | 0.0 |
| 4.1 Regolazione emotiva in adolescenza | 468 | 0.0 | 0.0 |
| 4.2 Fattori protettivi: supporto sociale e resilienza | 432 | 34.5 | 0.0 |
| 4.3 Interventi di prevenzione a scuola | 484 | 28.9 | 1.4 |
| 4.4 Interventi di prevenzione in famiglia | 503 | 18.1 | 0.0 |
| 5. Discussione: integrazione dei meccanismi e implicazioni | 419 | 22.4 | 0.0 |
| Conclusioni, limiti e prospettive future | 316 | 48.1 | 0.0 |
| Bibliografia | 755 | 0.0 | 0.0 |

Зведено: вступ **0 %** (E2 було 50 % — рамка з двокрапкою спрацювала: вступ останнім, із фактів), висновки **48 %** (новий пік; E2 і біологія — 0 %), тіло 22,6 %, дискусія 22 %; розділи на анотаціях (§1.3, §4.1) — 0 %; §4.4 на статті про харчування — 18 %.

**Прочитання.** AI тут не йде за походженням сторінок: §2.3 «Autostima» 63 % при 14 вікнах профільних текстів і 0 чужих, §3.2 «Uso problematico» 0 % з тими самими трьома текстами; розділи без сторінок — 0 %. Підкреслене — (а) речення, побудовані з анотацій профільних джерел розділу, коли наявні сторінки про інше (Valkenburg 2017 у §2.3, Martin & Gentry і Moreno-Padilla у §2.1 — жодне з них не має відкритого PDF у нашому пакеті, хоча скан показує копію Valkenburg у репозиторії pure.uva.nl), (б) мета-проза про межі дизайну, доступ до даних і майбутні дослідження у висновках (48 %). Не підкреслене — текст із конкретикою зі сторінок саме про питання розділу (Bányai p. 2 у §3.2). Гіпотеза (один файл, без повторного скану): захищає не наявність сторінок, а сторінки *про питання розділу*; конструктна проза психології («X впливає на Y», «медіація», «межі дизайну») ближча до моделі детектора, ніж молекулярна біологія чи кредит ПМІ. Три попередні файли лишаються доказами саме тих файлів.

**За правилами серії:** невдача → розбір запису, без автоматичного платного повтору. Нічого у писарі, плані чи рамці не змінено. Що на столі (рішення фаундера): (1) $0 — звуження якорів на чотирьох записах (матеріал; на AI цього файла прямо не впливає, бо профільні джерела §2.1/§2.3 не мали PDF); (2) $0 — інші копії того самого запису з репозиторіїв (pure.uva.nl для Valkenburg 2017 — саме те, що бракувало §2.3), раніше 0/7 на E2, тут є прямий приклад; (3) консультація Astra + Grok з таблицею по розділах перед будь-якою зміною рамки висновків або правил плану («limiti e prospettive future» як мета-текст); (4) без платних прогонів до рішення. Записка редактору й файл — лише для читання, не для видачі.
