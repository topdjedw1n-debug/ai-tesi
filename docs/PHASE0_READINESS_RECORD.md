# Phase 0 Readiness Record

**Status:** CONTRACT LOCKED — CORE BARRIERS IMPLEMENTED LOCALLY, LIVE PROOF PENDING
**Last updated:** 2026-07-10
**Purpose:** This is the canonical readiness artifact for starting Phase 1 proof runs. The manager should not fill this full record by hand; the admin quick setup writes the operational decisions here.
**Implementation note:** The first contour is a narrow Italian master's thesis based on the University of Bologna guidance. Compilatio is the relevant manual external signal for Italy; GPTZero is diagnostic only and must not decide release. No AI-detector percentage is treated as ground truth. Release requires the complete evidence set and a human decision.

## Test Contour

- Country / university context: Italy
- Exact university/context: Università di Bologna; source guidance: `docs/methodiche/UNIBO-linee-guida-tesi-magistrale.pdf`
- Language: Italian
- Work type: `tesi di laurea magistrale`, compilative/literature-review contour; no fabricated empirical data
- Sanity-run size: 20 pages, explicitly non-deliverable preflight
- Target full-run size: 40 pages minimum for the proof run (guidance range: 40-120 pages)
- Citation style: APA, as recommended by the selected guidance
- Required structure: introduction; numbered chapters/paragraphs/subparagraphs; literature review and research question; conclusions; bibliography and sitography
- Formatting baseline: A4; justified text; page numbers; each chapter starts on a new page; numbered figures/tables with titles and sources; no University of Bologna logo
- Quotation rule: literal quotations are exceptional, quoted and accompanied by author, date, source, and page

## Detector Access

- Plagiarism checker: Copyscape as an early web signal; Compilatio as the manual Italian release artifact
- Plagiarism checker type: full-document evidence required before release
- Plagiarism threshold: no unquoted copied passage; similarity percentage is recorded but is not sufficient by itself
- AI detector: Compilatio manual signal; GPTZero diagnostic only
- AI-risk threshold: no automatic pass/fail threshold until the Compilatio evidence set is large enough to calibrate one
- Turnitin AI access: No direct access
- Proxy detector, if Turnitin is unavailable: Compilatio for the selected Italian contour
- Detector limitations/proxy status: detector scores are probabilistic evidence, not proof of authorship. GPTZero was anti-correlated with Compilatio in the current small internal sample and cannot be used for release.
- Proxy recording surface: production case detector-result release gate for
  `plagiarism_proxy` and `ai_detection_proxy`; the decision is explicit and is
  bound to the exact exported file bytes. Both Compilatio decisions must refer
  to the same format and the same byte fingerprint; only that approved format
  can be downloaded after release.
- Evidence owner: NOT SET
- Evidence date: 2026-07-10

## Economics Baseline

- Price band: EUR 100-200
- Estimated AI generation cost: EUR 0.61 measured for a 5-page run with the full academic layer (panel, strict grounding/citations, claim audit) — restart drill 2026-07-10; projected EUR 5-10 for a 40-page run including regeneration allowance. Full-size measurement still pending
- Estimated detector/proxy cost: NOT SET
- Estimated editor cost: NOT SET
- Estimated total cost: NOT SET
- Human-written comparison cost: NOT SET
- Cost source: NOT SET
- Human-minutes status: optional for current Phase 0; record during Phase 1 if available
- Manager setup budget: NOT SET
- Editor review budget: NOT SET
- Editing/remediation budget: NOT SET
- Detector/rerun budget: NOT SET
- Delivery prep budget: NOT SET
- Total human-minutes budget: NOT SET
- Budget source: NOT SET

## Citation Gate State

- `PROVENANCE_LEDGER_ENABLED`: explicitly enabled in the production runtime contract
- `SOURCE_GROUNDING_ENABLED`: explicitly enabled in the production runtime contract
- `GROUNDING_GATE_ENABLED`: explicitly enabled with `strict` policy in the production runtime contract
- `CITATION_VERIFICATION_ENABLED`: explicitly enabled in the production runtime contract
- `CITATION_VERIFICATION_POLICY`: `strict` in the production runtime contract
- `CLAIM_VERIFICATION_ENABLED`: explicitly enabled; remains evidence-producing rather than generation-blocking until full-text support is available
- `QUALITY_PANEL_ENABLED`: explicitly enabled in the production runtime contract
- `HUMANIZER_ENABLED`: disabled for the baseline proof contour; any later use requires a paired comparison
- Crossref access: CONFIRMED from local machine on 2026-06-30 via HTTP 200 smoke request
- OpenAlex access: CONFIRMED from local machine on 2026-06-30 via HTTP 200 smoke request
- Semantic Scholar access/key: CONFIRMED — authenticated key configured in local `apps/api/.env`; smoke request returned HTTP 200 on 2026-07-01. The prior HTTP 403 on 2026-06-30 was a placeholder/invalid key value; unkeyed access returns HTTP 429. S2 is now the 4th live bibliographic provider (Crossref/OpenAlex/Semantic Scholar/arXiv).
- arXiv access: CONFIRMED from local machine on 2026-06-30 via HTTP 200 smoke request
- Target environment evidence: DEPLOYED to production (app.thesica.co, Hetzner) on 2026-07-10 at commit 26c4183 — DB backed up, migrations 013-023 applied cleanly, api/web rebuilt and healthy, generation worker started with zero polling errors, strict academic contract verified inside the running container (grounding strict, citation strict, claim verification, panel on, humanizer off). Forced mid-generation restart proven locally (see restart drill); a prod mid-generation restart can be exercised during RUN-001
- Known blind spots:
  - GPTZero is diagnostic only and must not be represented as Turnitin AI or Compilatio.
  - The early web plagiarism signal now checks every text chunk. It is not an academic-database guarantee and does not replace the manual full-artifact Compilatio check.
  - Current grounding uses metadata and abstract excerpts, not full PDFs or page-level evidence.
  - Page-level evidence from user-supplied source PDFs remains pending until full-text PDF retrieval is implemented.
  - The normal client download is now bound to a released artifact and its exact file hash; a live/pre-production proof is still pending.
  - Methodology, intake fields, APA, production-case requirements, model choice and the durable job are bound by one generation-contract fingerprint. Changing those inputs invalidates release until a new run succeeds.
  - Durable single-owner recovery is implemented and covered by automated restart/retry tests. Every content, source, evidence and artifact write is fenced against a stale worker. PROVEN LIVE 2026-07-10: SIGKILL mid-generation → lease-expiry reclaim (attempt 2), resume from checkpoint without duplicate sections, single sha256-bound artifact; live cancel fenced a still-running executor (`docs/phase1-runs/RESTART-DRILL-2026-07-10.md`). After DDL migrations the API process MUST be restarted (stale asyncpg prepared statements).
  - Semantic Scholar key/access: RESOLVED on 2026-07-01 — a valid authenticated key is configured and verified (HTTP 200). All four providers (Crossref/OpenAlex/Semantic Scholar/arXiv) are now reachable.

## People And Release Ownership

- Manager for RUN-001: NOT SET
- Editor for RUN-001: Assigned after the sanity-run draft is ready
- Release decision owner: NOT SET
- Detector evidence owner: Founder for the first Compilatio proof run; named delegate pending
- Ownership note: the manager creates and tracks the case; the editor edits flagged content; the release owner decides whether delivery is allowed; the detector evidence owner records Compilatio and full-document plagiarism evidence. GPTZero cannot release or reject a case.

## Remediation Plan

- If detector evidence is concerning before delivery: Do not deliver. Inspect the exact passages, repair factual/citation/style issues, re-check the complete artifact, and release only after manager approval. Do not run automatic detector-evasion rewriting.
- If client/university rejects or returns work: Open an editor escalation, rewrite failed sections, re-run checks, and record the final decision in the production case.
- Maximum extra human minutes: Track extra work during RUN-001; if expected total cost exceeds target margin, mark economics as failed.
- Client delivery/refund policy: Client receives only manager-approved final delivery. Failed detector/citation evidence blocks delivery.

## Phase 1 Start Criteria

Phase 1 may start only when all items are true:

- [x] Контур першого тесту
- [x] Реальна університетська методичка та APA
- [x] Compilatio визначено як основний зовнішній сигнал; GPTZero не є гейтом
- [x] Вимоги з анкети та файла доведено до генерації в повному наскрізному тесті
- [x] Нормальне завантаження фізично заблоковане до проходження release gates
- [x] Примусовий рестарт довів відновлення без дублів (local drill 2026-07-10, `docs/phase1-runs/RESTART-DRILL-2026-07-10.md`; a short prod restart check remains after deploy)
- [x] Ранній веб-сигнал плагіату перевіряє весь текст; Compilatio повного артефакту лишається обов'язковою ручною перевіркою
- [ ] Собівартість одного прогону
- [ ] Відповідальний за RUN-001
- [x] Що робимо, якщо перевірка падає

## Stop Condition

If any required detector, citation provider, export, or recovery check is unavailable, the case remains blocked. An unavailable or unchecked result is never a pass.
