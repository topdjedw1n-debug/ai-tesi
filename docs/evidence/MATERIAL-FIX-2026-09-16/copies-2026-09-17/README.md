# Інші копії того самого запису (17.09.2026, $0, крок 2)

**Підстава:** скан психології — §2.3 «Autostima» 63 % AI написаний з анотації Valkenburg 2017, хоча копія статті лежить у репозиторії pure.uva.nl (скан Compilatio сам її показав). Чинний код бере одну адресу: `best_oa_location.pdf_url` з OpenAlex (або `openAccessPdf` Semantic Scholar); записи з Crossref адреси не мають узагалі (18 із 40 у пакеті психології). Учора на E2 репозиторні `pdf_url` заблокованих записів дали 0/7; сьогодні перевірено ширше: **усі `locations` OpenAlex для кожного запису з DOI** (репозиторії першими, потім журнали; лендинг-сторінки через `citation_pdf_url`, як у проді), тим самим клієнтом і заголовками, що на сервері, до 3 спроб на запис ([probe_locations.py](probe_locations.py)).

| Пакет | Записів без сторінок у прогоні | Здобуто читабельних текстів | Що саме |
|---|---:|---:|---|
| PSY doc26 ([psy-locations-probe.txt](psy-locations-probe.txt)) | 32 | **8** | Valkenburg 2017 (pure.uva.nl, 8 с.), Self-comparison with influencers (cyberpsychology.eu, 22 с.), PSMU prevalence preprint (Research Square, 16 с.), nighttime social media use & sleep (rspublisher, 8 с.), Educazione ai media digitale scuola-famiglia (fupress, 10 с.), Prevenzione del cyberbullismo a scuola (fupress, 21 с.), Oltre il cyberbullismo / EU Kids Online (fupress, 13 с.), social isolation & loneliness review (CentAUR Reading, 38/40 с.) |
| BIO doc25 ([BIO-locations-probe.txt](BIO-locations-probe.txt)) | 30 | **7** | короткі італійські статті Microbiologia medica (pagepress, 1–4 с.) ×4, Recenti Progressi ×2, Letters in Animal Biology (11 с.) |
| E2 doc24 ([E2-locations-probe.txt](E2-locations-probe.txt)) | 34 | **2** | Jambura Economic Education (P2P lending, 14 с.), Sinergie (22 с.); 10 × 403 видавців лишаються (ScienceDirect, SSRN, MDPI, Sage, OECD) |

Шість із восьми здобутків психології — записи Crossref без жодної адреси в прогоні (знайдені через `works/doi:` OpenAlex), два — інші копії заблокованих записів (pure.uva.nl, CentAUR). Тобто головний важіль — **пошук адрес за DOI для записів Crossref**, другий — перебір `locations` замість однієї «найкращої».

## Симуляція матеріалу з копіями ($0, чинний код, записаний план)

[simulate_copies.py](simulate_copies.py) → [psy-simulation.txt](psy-simulation.txt): пакет psy з 8 записаними повними текстами (BEFORE) проти 16 (AFTER, сторінки копій завантажено один раз і збережено у scratchpad сесії).

| Розділ (AI за сканом) | BEFORE — хто дає сторінки | AFTER |
|---|---|---|
| §2.1 Confronto sociale (49 %) | Advances (загальний), Cureus, PSMU, харчування | **Self-comparison with influencers** (6 в.), Valkenburg (6 в.), Advances, Cureus |
| §2.2 Immagine corporea (30 %) | Cureus | **Self-comparison with influencers** (16 в.), Cureus |
| §2.3 Autostima (63 %) | Advances, PSMU, Cureus | **Valkenburg 2017** (6 в.), Advances, PSMU, PSMU-preprint |
| §3.3 Sonno (14 %) | Cureus, Advances 12 в. | **Nighttime use & sleep review** (7 в.), Cureus, PSMU-preprint |
| §4.4 Famiglia (18 %) | харчування 17 в. | **Educazione ai media digitale** (6 в.), cyberbullismo a scuola, харчування, nighttime |
| §3.1 FoMO (35 %) | COVID-медики 12 в., Cureus | nighttime, COVID-медики 9 в., Cureus — профільні FoMO-джерела лишаються анотаціями (SSRN 403) |
| §1.3 / §4.1 (0 %, на анотаціях) | — | nighttime review 4 в., PSMU-preprint 3 в. |
| `plan_material_gap` | 6 розділів | 2 (§1.3, висновки) |

Чужі тексти нікуди не зникають (сексуальна освіта в §1.2/§5, медики в §3.1/§4.2, харчування в §1.2/§4.4) — це питання воріт (крок 1, детерміновано не вирішене), але їхня вага падає, бо профільні джерела тепер мають сторінки.

## Що з цього випливає (для консультації)

Коміт «копії» — малий і записуваний: (1) у S2 для кожного перевіреного запису зберігати список адрес (`locations` OpenAlex; для Crossref/S2-записів — один записаний виклик `works/doi:`), репозиторії першими; (2) при отриманні тексту пробувати адреси по черзі до першої з текстовим шаром (кожна спроба — уже записана залежність `executor_full_text`), не більше 3 на запис і з загальною межею на роботу; (3) тести на порядок адрес і на зупинку після першого успіху. Ціна: 0 $ моделі, ≈ 20 викликів OpenAlex і ≤ 60 HTTP-спроб на роботу. Не доводить AI-відсотки: їх дасть лише новий файл.
