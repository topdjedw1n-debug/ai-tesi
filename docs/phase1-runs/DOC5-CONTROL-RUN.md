# Контрольний прогін doc 5 — репетиція RUN-001 (Етап B6)

**Статус:** ГОТОВИЙ ДО ЗАПУСКУ (код Етапів B1–B5 змержено, тести зелені)

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
