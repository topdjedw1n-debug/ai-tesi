# Phase 0 Readiness Record

**Status:** NOT READY
**Last updated:** 2026-06-30
**Purpose:** This is the canonical readiness artifact for starting Phase 1 proof runs. The manager should not fill this full record by hand; the admin quick setup writes the operational decisions here.
**Implementation note:** Turnitin AI is not available directly for the first contour, so GPTZero is the Phase 1 AI-detection proxy. Plagiarism checking is recorded as pending until the next edits and agreement. Human minutes remain optional; the current operating priority is production cost versus a fully human-written workflow.

## Test Contour

- Country / university context: Italy
- Exact university/context: NOT SET
- Language: Italian
- Work type: bachelor thesis
- Sanity-run size: 20 pages
- Target full-run size: 60-70 pages after a 20-page sanity run
- Citation style: to be confirmed per order

## Detector Access

- Plagiarism checker: To be added after next edits and agreement
- Plagiarism checker type: post-edit agreement
- Plagiarism threshold: To be set after next edits and agreement
- AI detector: GPTZero
- AI-risk threshold: < 20%
- Turnitin AI access: No direct access
- Proxy detector, if Turnitin is unavailable: GPTZero
- Detector limitations/proxy status: GPTZero is a proxy signal, not Turnitin AI or an exact university detector.
- Planned proxy recording surface: production case detector-result release gate
  endpoint for `plagiarism_proxy` and `ai_detection_proxy`
- Evidence owner: NOT SET
- Evidence date: 2026-06-30

## Economics Baseline

- Price band: EUR 100-200
- Estimated AI generation cost: NOT SET
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

- `PROVENANCE_LEDGER_ENABLED`: true by application default; not explicitly set in local `apps/api/.env`
- `CITATION_VERIFICATION_ENABLED`: false by application default; not explicitly set in local `apps/api/.env`
- `CITATION_VERIFICATION_POLICY`: `mark_only` by application default; not explicitly set in local `apps/api/.env`
- Crossref access: CONFIRMED from local machine on 2026-06-30 via HTTP 200 smoke request
- OpenAlex access: CONFIRMED from local machine on 2026-06-30 via HTTP 200 smoke request
- Semantic Scholar access/key: CONFIRMED — authenticated key configured in local `apps/api/.env`; smoke request returned HTTP 200 on 2026-07-01. The prior HTTP 403 on 2026-06-30 was a placeholder/invalid key value; unkeyed access returns HTTP 429. S2 is now the 4th live bibliographic provider (Crossref/OpenAlex/Semantic Scholar/arXiv).
- arXiv access: CONFIRMED from local machine on 2026-06-30 via HTTP 200 smoke request
- Target environment evidence: local smoke check recorded; production/preprod target environment pending before live delivery
- Known blind spots:
  - GPTZero is only a proxy and must not be represented as Turnitin AI.
  - Plagiarism checker is pending after the next edits and agreement.
  - Citation verification remains effectively disabled until `CITATION_VERIFICATION_ENABLED=true` is set in the target environment.
  - Semantic Scholar key/access: RESOLVED on 2026-07-01 — a valid authenticated key is configured and verified (HTTP 200). All four providers (Crossref/OpenAlex/Semantic Scholar/arXiv) are now reachable.

## People And Release Ownership

- Manager for RUN-001: NOT SET
- Editor for RUN-001: Assigned after the sanity-run draft is ready
- Release decision owner: NOT SET
- Detector evidence owner: NOT SET
- Ownership note: the manager creates and tracks the case; the editor edits flagged content; the release owner decides whether delivery is allowed; the detector evidence owner runs GPTZero/plagiarism checks and records the numbers.

## Remediation Plan

- If detector fails before delivery: Do not deliver. Run editor remediation or regenerate flagged sections, re-check GPTZero/plagiarism, and release only after manager approval.
- If client/university rejects or returns work: Open an editor escalation, rewrite failed sections, re-run checks, and record the final decision in the production case.
- Maximum extra human minutes: Track extra work during RUN-001; if expected total cost exceeds target margin, mark economics as failed.
- Client delivery/refund policy: Client receives only manager-approved final delivery. Failed detector/citation evidence blocks delivery.

## Phase 1 Start Criteria

Phase 1 may start only when all items are true:

- [ ] Контур першого тесту
- [x] GPTZero threshold
- [ ] Собівартість одного прогону
- [ ] Відповідальний за RUN-001
- [x] Що робимо, якщо перевірка падає

## Stop Condition

If any required detector or citation provider is unavailable, record the proxy and limitation here before running Phase 1. If no credible proxy exists, do not treat Phase 1 detector pass/fail as valid evidence.
