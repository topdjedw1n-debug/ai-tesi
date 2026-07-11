# Контрольний прогін A — мінімальне ядро, без методички (11.07.2026)

Документ 61, job 50, користувач controlruns20260711@example.org (локальний стенд).
**Результат: COMPLETED** — 3/3 розділи, DOCX експортовано, 0 ретраїв, 0 ручних втручань.

- Вхід: тема (economia circolare / PMI italiane), tesi_magistrale, it, 10 стор., APA. Модель дефолтна = голова fallback-ланцюга (anthropic/claude-opus-4-8); наукові PDF не завантажувались.
- Контракт: basis `standard_academic`, структура = **assumed** (system_default), підтверджено менеджером до старту (sha `6c9e1a…`, обидві події в провенансі).
- Час: 12:42:39 → 12:46:52 UTC = **4 хв 13 с**. Вартість: **€0.60** (60 cost_cents), 88 864 токени.
- Гейти: grounding — без жодного фейлу; граматика 100/95/100; плагіат 0% скрізь; AI-детекція **failed** 95.5/48.4/95.7 % (поріг 35%, неблокуюча за контрактом); панель 88.5/90/86.5 (3/3 рецензенти); цитати strict **23/23 verified**; твердження: 49 заявлено, 47 перевірено — 40 supported / 1 unsupported / 8 uncertain (неблокуюче).
- DOCX: `ai-thesis-documents/documents/11/61/61-76cc78d020a97c69.docx`, 45 807 байт, sha256 `76cc78d020a97c691e8791587365bf915ba6accac6aa8d00b1849c1116229caf` (див. docx-artifact.txt; release_status=blocked — дефолт до окремого ручного релізу, не збій).

## Файли

| Файл | Що це |
|---|---|
| task-contract-pre.json | контракт до старту (GET /task-contract) |
| task-contract-confirm-response.json | відповідь POST /task-contract/confirm |
| task-contract-provenance.json | події task_contract / task_contract_confirmed з провенансу |
| outline.json | план (3 розділи, назви+обсяги) |
| final-text.md | фінальний текст розділів з БД + посекційні бібліографії |
| docx-artifact.txt | шлях/розмір/sha256 DOCX |
| sources.json | document_sources: 38 записів (24 у пакеті, 23 процитовано і верифіковано) |
| sections-meta.json | бали гейтів по розділах |
| provenance-events.json | повний ledger (30 подій) |
| job.json, production-case.json, document.json | стан job/кейса/документа |

Помічені дефекти (нічого не виправлялось): 1 сирий маркер `[Kayıkçı2022]` у §2.5; author-метадані з малої літери («saputro», «hadijah»); 1 процитоване джерело (Dey et al., 2020) не потрапило в перелік верифікації (23 замість 24) і лишилось `unverified` у document_sources.
