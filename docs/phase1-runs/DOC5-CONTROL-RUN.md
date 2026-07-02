# Контрольний прогін doc 5 — репетиція RUN-001 (Етап B6)

**Статус:** ВИКОНАНО — doc 5 (02.07, знайшов 3 діри) → B-fix хвиля → doc 6
(02.07, чек-лист закрито) → doc 8 стрес-тест поза освітньою темою (02.07,
знайшов двомовну діру) → bilingual-фікс → **doc 9 (02.07, ціль виконано)**

## Результат doc 9 (COVID-19/економіка США — тема doc 8 після bilingual-фікса)

Фікс: пак шукає/скорить джерела італійською ТА англійською (переклад теми
одним LLM-викликом у wrapper'і), новий блокуючий release-гейт
`source_availability` (порожній пак = failed, underfilled = warning),
+ у пак потрапляють лише цитовані джерела (автор+рік — doc-9 прогін №1
впав на безавторному Crossref-рядку, job 7: 20 318 ток. / $0.79 чесно
записано).

Таблиця «було/стало» (doc 8 → doc 9, та сама тема, 3 секції):

| Метрика | doc 8 (було) | doc 9 (стало) |
|---|---|---|
| Пак: джерела по темі | 0 з 7 (urban blight, міграція, фарма...) | **12 з 12 про COVID-економіку** |
| Пак: underfilled / поріг | true / нишком 0.35→0.175 | **false / чесний 0.35** |
| Пак: mean on_topic (built→rebuilt) | 0.247 → 0.253 | **0.622 → 0.456** |
| Grounding-фейли / exhausted | 9 / 3 (всі секції) | **0 / 0** (чистий прохід, подій немає) |
| Claims: unsupported / uncertain | 4 / 4 (з 12) | **0** / 7 (з 18, 11 supported) |
| Grammar по секціях | 90 / 90 / 75 | 95 / 95 / 90 |
| Плагіат (Copyscape, live) | 0% збігів | 0% збігів |
| AI-детекція по секціях | 27.2 / 12.7 / 4.8 | 17.1 / 34.6 / 33.8 (passed, але s2/s3 впритул до порога 35 — уважніше на довших доках) |
| Панель | 90.5 / 79 / 85.8 | 93.2 / 93.0 / 91.5 |
| Citation gate | passed (20 verified, але офтоп) | passed (14 verified, по темі) |
| Токени / вартість (успішний job) | 48 780 / $1.84 | 43 654 / $1.64 (+ $0.79 невдалий прогін №1) |
| Бібліографія по секціях | — | 7 / 6 / 5 референсів, DOCX експортовано |
| Події паку | без bilingual | `bilingual: true`, underfilled чесно в гейт |

Ціль (≥8 джерел по темі; underfilled=false; grounding 9→≤2, exhausted 3→0;
unsupported 4→≤1; grammar/plagiarism/AI не гірше порога) — **виконано**.

Compilatio-артефакт: `~/Downloads/COVID_economia_USA_doc9_bilingual.txt`
(завантажити вручну).

Примітка: у прогоні №1 знайдено і виправлено латентний баг — builder
приймав безавторні/безрічні джерела, а citation formatter їх жорстко
відкидає посеред генерації; тепер фільтр на вході в пак (коміт 6adf03b).

## Результат doc 6 (після B-fix хвилі, комміти aaa665f..d2a4773)

- Токени/вартість: 36 157 ток., $1.32 (job 4) ✓
- Source pack: 10 джерел, всі verified ✓
- Плагіат: ЖИВИЙ Copyscape (кредити списуються), 100% unique по секціях ✓
  (Данте-контроль: 14.63% unique / 12 збігів — детектор реально ловить)
- Claim-audit: 23 claims / 16 LLM-checked / 13 supported / 0 unsupported ✓
  (doc 5 було 0 — екстрактор не бачив пак-ключів)
- Grammar: 70 / 100 / 85 (doc 5: 40) — артефакти вирізання анкорів усунуто ✓
- Панель: 91.5–93.5, події зі status ✓
- Bibliografia в DOCX: по секціях 8/6/8 референсів ✓
- AI-детекція: чесний `unchecked` («All AI detection providers
  unavailable») — ключа ще немає; це і є живий негативний тест B1:
  гейт unchecked → реліз блокується до override ✓
- Grounding: rate 1.0, hedging 9.93/1000, has_evidence по всіх секціях ✓
- Compilatio-артефакт: `~/Downloads/AI_e_istruzione_doc6_bfix.txt` —
  завантажити вручну, локально плагіат-еталон не вимірюється.

**Лишилось до RUN-001:** GPTZero Professional ключ (AI-гейт оживе) +
рішення C-блоку (пороги, Compilatio-процес, відповідальні).

Мета: повний цикл з усіма чесними доказами — пак → генерація → grounding
gate → citation verified → claim-audit → panel → Bibliografia в DOCX →
токени/вартість записані. Це репетиція RUN-001 перед реальним внутрішнім
замовленням.

## Передумови

- [ ] Міграція `012_section_bibliography.sql` застосована до БД
      (`psql ... -f apps/api/migrations/012_section_bibliography.sql`;
      міграція 011 вже застосована раніше).
- [ ] `apps/api/.env` — прапорці вже увімкнені (02.07.2026):
      `SOURCE_GROUNDING_ENABLED=true`, `GROUNDING_GATE_ENABLED=true`
      (mark_only), `CITATION_VERIFICATION_ENABLED=true` (mark_only),
      `CLAIM_VERIFICATION_ENABLED=true` (max 50, non-blocking),
      `QUALITY_PANEL_ENABLED=true`, `QUALITY_GATES_ENABLED=true`.
- [ ] Ключі провайдерів живі: OpenAI/Anthropic, S2 (перевірений раніше,
      HTTP 200), LanguageTool доступний.
- [ ] API+web+Redis+Postgres підняті local-first (рішення 01.07.2026).

## Прогін

1. Створити документ: італійська тема, зіставна з doc 4 (той самий
   контур: ~20 стор.), провайдер/модель як у doc 4 для порівнянності.
2. Запустити повну генерацію (`generate_full_document_async` через UI/API —
   тепер вона передає `job_id`, тож usage пишеться інкрементально).
3. Після завершення — експорт DOCX і PDF (фоновий шлях робить DOCX сам).

## Чек-лист доказів

- [ ] **Source pack**: `document_sources` має рядки з `citation_key`,
      `is_in_upfront_pack=true`, `on_topic_score >= 0.35` (примітка: при
      underfilled-паку поріг легітимно релаксується до 0.175).
- [ ] **Grounding gate**: НЕМАЄ хибних `no concrete evidence`-фейлів на
      секціях із названими системами (B4.1). Увага: на чистому проході
      гейт подій НЕ пише — у провенансі події з'являються лише на фейлах
      (`grounding_gate_failed`/`exhausted`); відсутність подій = добре.
- [ ] **Citation verification**: `citation_gate` подія зі `status`
      (`passed` або `warning` при not_found — НЕ чистий passed; B1).
- [ ] **Claim-audit**: `claim_check_summary` подія, `checked <= 50`,
      `DocumentSection.claim_verification` заповнено (B5). Для менеджера:
      «non-blocking» стосується лише генерації — unsupported claims НЕ
      валять генерацію, але release-гейт `claim_support` БЛОКУЄ видачу до
      audited override; 0 витягнутих claims = warning (теж блокує).
- [ ] **Panel**: `panel_review` події, скори в `DocumentSection.quality_panel`
      (B5); вартість панелі видно в токенах (B3).
- [ ] **Grammar**: `>= 85` після вирізання цитатних анкорів (B4.2). Якщо ні —
      задокументувати причину тут (порівняти matches із doc 4).
- [ ] **Бібліографія**: DOCX містить розділ `Bibliografia` (Heading 1) з
      реальними DOI-рядками з пака; PDF аналогічно (B2).
- [ ] **Токени/вартість**: `AIGenerationJob.total_tokens > 0`,
      `cost_cents > 0`; у кейсі видно AI cost у € (B3) — вхід для
      Economics Baseline (крок C3).
- [ ] **Негативний тест (B1)**: окремий короткий прогін із вимкненою
      AI-детекцією — виставити `AI_DETECTION_ENABLED=false` АБО прибрати
      ОБИДВА ключі (GPTZero **і** Originality: сам лише GPTZero-ключ не
      дасть Unchecked — спрацює fallback на Originality) → у QA Evidence
      «AI detection: Unchecked» амбером, section_quality гейт unchecked,
      реліз заблоковано до override.

## Кого вважати «зарахованим»

Усі пункти чек-листа закриті або мають задокументоване пояснення. Результати
перенести в `RUN-001.md`-формат (шаблон `PHASE1_RUN_REPORT_TEMPLATE.md`) та
оновити TESIGO-PLAN.md.

## SQL-шпаргалка для перевірки

```sql
-- Токени/вартість джоба
SELECT id, status, total_tokens, cost_cents FROM ai_generation_jobs
 WHERE document_id = :doc_id ORDER BY id DESC;

-- Бібліографія по секціях
SELECT section_index, jsonb_array_length(bibliography) AS refs,
       pack_keys_used FROM document_sections
 WHERE document_id = :doc_id ORDER BY section_index;

-- Гейти в провенансі
SELECT event_type, payload->>'status' AS status, payload->>'passed' AS passed
  FROM document_provenance
 WHERE document_id = :doc_id
   AND event_type IN ('quality_gate','citation_gate','claim_check_summary',
                      'panel_review')
 ORDER BY id;
```
