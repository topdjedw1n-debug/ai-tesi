Усі потрібні дані зібрано; формую фінальний вердикт.

## Напрямок: DIRECTION_APPROVED

Код заморожений на тій самій цілі: менеджер доходить до DOCX, перевірки лише попереджають, нових стопів немає. Політика ізольована в `request_payload.generation_policy`, легасі-шлях суворий, історія №5–№11 незмінна. Стоп-перелік у коді збігається з планом (доступ провайдера, непридатна відповідь після повторів, БД/сховище, скасування/lease).

## Реальні докази і пропорційність

- **Справжній запис є один:** `real_writer_stage_11.json` — один виклик Opus 4.8, `outcome: received`, `stop_reason: end_turn`, 26030/3222 токенів, $0.21, replay через `SectionGenerator` без SDK (`test_platform_first_corpus.py:161–243`, лог 14 passed). Це доказ запису/відтворення одного етапу, не повного №11 і не якості.
- **Синтетика:** 6 сценаріїв воркер→DOCX→CLI-replay (27 passed), 429→повтор на справжньому pydantic-об'єкті (`test_model_recording.py:217–280`). Повний API-прогін завершився: 1442 passed, 24 skipped, 0 failed (`platform-api-final.txt:295`); Postgres 14, web 19, tsc 0. Стара «1 failed» у `platform-latest-focused.txt` — той самий prompt-тест до правки на SimpleNamespace, у фіналі зелений.
- Diff + тести достатньо; маніфести не потрібні. Платний повний прогін для закриття локального обсягу не потрібен.

## Коректність: перевірка 16 знахідок і що лишилось

Підтверджено виправленими за кодом: 1 (`replay_generation.py:217–220`, тест передає `request_payload.additional_requirements`), 2 (`source_pack_preflight.py:303` через `retrieval_time(..., 0)`, сценарій `missing_abstract`), 3 (`generation_operations.py:137–149`, `raise_recorded_error` відновлює SDK/httpx-помилки, невідомі типи → `ReplayIncomplete`), 4 (`replay_snapshot.py:100–106`, runner сідає попередні спроби з експорту), 5 (`prompt_builder.py:191–192`), 6–7 (`standard_references.py:44, 131–133`, тести з `[STD:nanda-i]`/fence), 8 (`STANDARD_SOURCE_RULES` рядки 19–20), 9 (`ai_service.py:821–830`, тест на «do not plan sections»), 10 (`background_jobs.py:2649–2692` humanizer через `advisory`, відкат до тексту писаря при зміні ключів; multi-pass вимкнено на 802–806 — задокументовано, ок), 11 (`brief_source_scopes` 14 scope, `scope_query` ≤8 слів, alt-кеп 4, кеш перекладу), 12 (`sdk_key`), 13 (`production_case_service.py:1137–1148`), 14 (`REPLAY_SETTING_NAMES` без KEY/URL/PATH, `LANGUAGETOOL_API_URL` окремо; підміна `DATABASE_URL` у tape ігнорується), 15 (bytes у `json_value`, pydantic-тести), 16 (`_record_provenance` для snapshot/warning піднімає `RecordingPersistenceError`).

**Один must-fix платформи, доведений реальним записом, а не синтетикою:**

- **Сирий маркер `[Selix2015]` у тексті DOCX.** `section.md:9` містить `[Selix2015]` дослівно. Це не вигадка моделі: джерело є в `source_rows` (id 284, Nancy Green Selix, 2015), але з `citation_key: null` і `unverified`, тобто preflight його відкинув, а `evidence_keys` плану (рядки 137, 167, 255, 286) досі на нього посилаються. Писар отримує «APPROVED OUTLINE … evidence_keys: Selix2015» поруч із пакетом без такого ключа й чесно цитує його. У режимі попереджень підготовка плану на такому ключі падає в warning (`academic_review.py:96–98` → `PlanRejected`), початковий план зберігається зі стале-ключами, а на фінальній збірці `leaked_markers` лише попереджає (`background_jobs.py:3863–3870`). §3 плану: службових маркерів у DOCX немає; для `[STD:]` це вже виконано, для ключів пакета — ні. Мінімальна правка: (а) в `generator.py` після `convert_pack_markers` рендерити кожен нерозв'язаний ключ нейтрально з самого ключа, як зроблено для STD (`Selix2015` → «(Selix, 2015)»), без запису в бібліографію, з попередженням «цитата без джерела в пакеті: Selix2015»; (б) у prompt писаря передавати outline з `evidence_keys`, відфільтрованими за ключами замороженого пакета (не змінюючи збережений план), і фіксувати відкинуті ключі в тому ж попередженні. Тест: реальний fixture №11 → `"[Selix2015]" not in result["content"]`.

**Не блокує, зафіксувати як наступну ітерацію:**

- Формат цитати без року для кількох авторів: `standard_references.py:104` дає «(Sue Moorhead; Elizabeth Swanson; Marion Johnson; Meridean L. Maas, s.d.)» (`section.md:19, 23`). Треба прізвище + «et al.» через `CitationFormatter.format_intext` з year=None або власна APA-скорочена форма. Це рендер платформи, не модель.
- Якість самого тексту (не платформа): розділ тримає межу компетенцій, відкрито декларує брак порогових значень у пакеті, не вигадує чисел; стандартні NANDA/NOC/WHO позначені як неперевірені — очікувана поведінка. Подвійні дужки «(Joseph, 2020), (Kumar et al., 2026)» — стиль моделі, для менеджера.

**Вердикт:** LOCAL_IMPLEMENTATION_READY після одного must-fix вище (нейтральний рендер нерозв'язаних ключів пакета + фільтр `evidence_keys` у prompt). Усе інше з мого попереднього списку закрито кодом і тестами. Живий/платний статус, приймання Танею й сервер — окремі дозволи, як і раніше.
