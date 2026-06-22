# Phase 0 Readiness Record

**Status:** NOT READY
**Last updated:** 2026-06-22
**Purpose:** This is the canonical readiness artifact for starting Phase 1 proof runs. Do not mark Phase 0 complete until every required field below has a concrete value and evidence source.

## Test Contour

- Country / university context: Italy target contour, exact university not confirmed
- Language: Italian
- Work type: bachelor thesis
- Target full-run size: 60-70 pages after a 20-page sanity run
- Citation style: to be confirmed per order

## Detector Access

- Plagiarism checker: NOT CONFIRMED
- Plagiarism threshold: NOT SET
- AI detector: NOT CONFIRMED
- AI-risk threshold: NOT SET
- Turnitin AI access: NOT CONFIRMED
- Proxy detector, if Turnitin is unavailable: NOT SELECTED
- Evidence owner:
- Evidence date:

## Human-Minutes Budget

- Price band: EUR 100-200
- Manager setup budget: NOT SET
- Editor review budget: NOT SET
- Editing/remediation budget: NOT SET
- Detector/rerun budget: NOT SET
- Total human-minutes budget: NOT SET
- Budget source:

## Citation Gate State

- `PROVENANCE_LEDGER_ENABLED`: expected true for Phase 1
- `CITATION_VERIFICATION_ENABLED`: NOT CONFIRMED for target environment
- `CITATION_VERIFICATION_POLICY`: NOT CONFIRMED for target environment
- Crossref access: NOT CONFIRMED
- OpenAlex access: NOT CONFIRMED
- Semantic Scholar access/key: NOT CONFIRMED
- arXiv access: NOT CONFIRMED
- Known blind spots:

## Phase 1 Start Criteria

Phase 1 may start only when all items are true:

- [ ] First university/context selected.
- [ ] Plagiarism checker and pass threshold recorded.
- [ ] AI detector and pass threshold recorded.
- [ ] Detector limitations/proxy status recorded.
- [ ] Human-minutes budget calculated from expected margin.
- [ ] Citation gate provider access checked in the target environment.
- [ ] Manager/editor assigned for the first run.
- [ ] Remediation plan exists for a failed live order.

## Stop Condition

If any required detector or citation provider is unavailable, record the proxy and limitation here before running Phase 1. If no credible proxy exists, do not treat Phase 1 detector pass/fail as valid evidence.
