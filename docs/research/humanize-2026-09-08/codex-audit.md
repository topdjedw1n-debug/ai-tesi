# Humanize: read-only audit of implementation and historical evidence

Date: 2026-09-08. Author: Codex audit subagent.

Scope: local source, current founder brief/release profile, historical experiment records, and one offline pure-function probe. No production access, paid generation, detector calls, code/config/canon changes, or changes to existing artifacts. The working tree contains substantial unrelated work; all of it was preserved. Line references describe the files as read during this audit and may move during concurrent M0-12/M1-Q01 work.

## Answer to the premise

Humanize **has run and has sometimes lowered GPTZero scores**. It is therefore inaccurate to say it has never operated or never lowered any score. There is **no documented full accepted result satisfying today's combined Compilatio similarity ≤10%, AI ≤10%, content/source acceptance and no human rewrite** in the inspected records.

The lowest recorded Compilatio AI result after the historical rescue pipeline is **14% AI with 4% similarity**, from Validation-6. That was considered encouraging under the historical experiment, but it does not pass the current ≤10/≤10 contract. Green checkmarks in old reports do not establish current product PASS.

The latest recorded real work №7 has **manager-entered similarity 3% and AI 47%**, an attached report and a binding to the DOCX hash. Its current recorded blocker is AI/content evidence, not high textual similarity. The technical report explicitly says it did not independently interpret the PDF. This audit does not strengthen that evidence claim.

Evidence:

- `docs/phase1-runs/MODEL-MATRIX-EXPERIMENT.md:411-443`: Validation-6 design and results.
- `docs/AGENT_SYNC.md:69-85`: current combined acceptance contract.
- `docs/evidence/M0-11-2026-09-08.md:114-141`: exact №7 artifact and manager-entered results; 15 uncertain claims, missing content/no-rewrite acceptance, no M1 PASS.
- `docs/phase1-runs/RUN-001.md:3-5`, `RUN-002.md:3-5`, `RUN-003.md:3-5`: pending records rather than completed proof runs.

## Why it is disabled

1. The active brief explicitly keeps Humanizer off and requires work on content, sources and generation quality: `docs/AGENT_SYNC.md:190-202`. The user's current research request authorizes reconsidering the approach; this audit does not interpret it as an instruction to change the deployed switch.
2. Both local defaults and the production deployment definition explicitly disable it: `apps/api/app/core/config.py:117-120`, `infra/docker/docker-compose.prod.yml:131-133`, `apps/api/tests/release_profile.py:32`. The deployment comment requires paired evidence before re-enabling. The saved current model-catalog evidence also records `HUMANIZER_ENABLED=false`: `docs/evidence/M1-Q02-MODEL-CATALOG-2026-09-08.json:7`. Live containers were not rechecked in this subtask.
3. The historical optimization target was GPTZero. Its apparent improvements did not reliably transfer to Compilatio, the actual acceptance detector. This is evidence of a mismatch on a small sample, not proof of a universal anti-correlation.
4. Raw Opus on one experiment scored 16% Compilatio AI, within the range of other rescued Opus outputs (14–21%). That motivated measuring a baseline without automatic rewriting. These are different outputs, not a randomized paired estimate of Humanizer benefit.
5. The planned stronger paired comparison was not completed with raw baselines in the inspected written record. Hence benefit was not established before the switch was kept off.

## Historical results and their limits

| Experiment | What actually improved or failed | What it proves |
|---|---|---|
| Phase 1, one pass, 03 July | Original doc9 sample GPTZero 34.6; every new one-pass candidate worse, best 52.6. Historical doc9 multi-pass provenance separately recorded 66.1→17.1 and 52.3→33.8. | One-pass rewriting could worsen an already lower-scoring text; multi-pass sometimes lowered this diagnostic detector. `MODEL-MATRIX-EXPERIMENT.md:95-123`. |
| Phase 2 v1 | GPT-4 self-rescue 56.4→96.7→51.9; Opus→GPT-4 42→29.4 but panel score 52 failed; GPT-5.5→GPT-4 hit context length and silently returned original. | Aggressive style instructions and smaller model context caused failures; detector improvement did not establish content quality. `MODEL-MATRIX-EXPERIMENT.md:136-155`. |
| Phase 2 v3 | doc18 completed with GPTZero 4.0/10.2/7.7; doc19 completed with 30.2/33.9/1.8. | Technical completion and section diagnostic scores, not Compilatio PASS. `MODEL-MATRIX-EXPERIMENT.md:177-197`. |
| Phase 4, paired section experiment | Same Opus raw input 96.5: serial 79, best-of-N+freeze 26. Sonnet raw 94.4: serial 47, best-of-N+freeze 54. | Some benefit on one Opus section, none on one Sonnet section. Best-of-N and freeze were changed together and 9 vs 3 candidates were tried, so effects are confounded. `MODEL-MATRIX-EXPERIMENT.md:289-337`. |
| Phase 4c, Compilatio | GPT-4 result ~7 GPTZero → **53 AI / 0 similarity** in Compilatio. Opus results → **19/0** and **21/0**. | The proxy detector ranking did not transfer in these three outputs. No current ≤10/≤10 PASS. `MODEL-MATRIX-EXPERIMENT.md:373-409`. |
| Validation-6 | 4/6 generations completed. Paired topic/source pack: rescued Opus **14 AI / 4 similarity**, rescued GPT-4 **35/10**. | Writer comparison inside a rescue pipeline; no raw-vs-edited control and no current PASS. `MODEL-MATRIX-EXPERIMENT.md:411-451`. |
| Block 1, raw writers | Compilatio AI/similarity: Opus **16/5**, Sonnet-5 **38/8**, GPT-4o **76/6**, GPT-5.5 **57/8**, GPT-5.4 **33/7**. | One theme, different generated outputs, Humanizer off. `HANDOFF-2026-07-03.md:113-145`. |
| Block 2, same drafts edited | Recorded **total suspicious**: Opus→GPT-4o 44; GPT-5.4→GPT-4o 27; same GPT-5.4→Opus 20. Raw baselines still pending in record. | 20 vs 27 is same-draft comparison between editors, but these numbers are not separately AI/similarity and do not measure improvement from raw. `HANDOFF-2026-07-03.md:183-212`. |

Do not repeat the old assertion that 44% proves GPT-4o damaged raw Opus: the compared raw 20% came from another topic, and both were total suspicious rather than AI-only. The historical author explicitly wrote that raw baselines were still needed (`HANDOFF-2026-07-03.md:199-204`).

Historical sources above are repository records, not newly rerun experiments. Files from the old experiments are still present in `/Users/maxmaxvel/Downloads/THESICA-BLOCK2/`, `/Users/maxmaxvel/Downloads/THESICA-MODEL-MATRIX/`, `/Users/maxmaxvel/Downloads/THESICA-VALIDATION-6/`, along with `detailed-report_it_...pdf` and `certificate-report_it_...pdf` files. Their existence was verified by listing; PDF contents and authenticity were not revalidated here.

## Current implementation: reuse and defects before enabling

### Existing useful controls

- Canonical source keys travel through the rewrite and are rendered afterward. Unknown keys and added/dropped source sets are rejected: `background_jobs.py:2323-2355`, `2451-2475`, `1132-1152`.
- Citation markers and long quotes are frozen and restored; dropped known markers roll back: `humanizer.py:194-235`.
- Some language drift is checked: `humanizer.py:237-245`.
- Claim verification occurs after the final Humanizer text and uses its canonical markers: `background_jobs.py:2527-2547`.
- A corruption heuristic rejects grossly garbled best-of-N outputs: `humanizer.py:56-82`, `507-524`.
- LLM usage is recorded by the actual editor model: `humanizer.py:326-333`, `365-372`.
- Final artifact/release checks already bind decisions to exact file bytes. Preserve this layer.

### P1: wrong optimization target for the actual acceptance criterion

`humanize_multi_pass` instantiates `AIDetectionChecker`, then selects the minimum score (`humanizer.py:427-440`, `492-539`). The checker uses GPTZero with Originality fallback (`ai_detection_checker.py:19-30`, `58-73`). It does not call Compilatio, inspect similarity matches, or understand why a match exists. The rescue trigger uses `QUALITY_MAX_AI_DETECTION_SCORE` and aims five points below it (`background_jobs.py:772-787`); the local default is 55 (`config.py:145-148`). This is unrelated to the final Compilatio ≤10/≤10 contract.

Consequence: simply enabling the switch reactivates an optimizer for a diagnostic proxy that has already disagreed with the target detector. It is not a plagiarism correction system.

### P1: grammar and early similarity evidence can refer to an earlier text

Grammar and plagiarism checks run on the result of the initial single pass (`background_jobs.py:2372-2415`). Multi-pass rescue can then replace the text (`2430-2448`), yet the already captured grammar/plagiarism values enter `final_check_breakdown` (`2506-2524`). There is no recheck between the replacement and that evidence construction. Downstream claim and panel checks do not retroactively make those earlier grammar/plagiarism measurements valid for the new text.

Consequence: with Humanizer on, displayed/stored checks may describe different bytes. All relevant content checks must run after the final edit and bind to its hash; an additional edit must invalidate them.

### P1: citation preservation is weaker than citation correctness

`CitationFreezer.all_present` only checks substring membership (`citation_freezer.py:108-110`), and `restore` replaces any count of a token (`101-105`). The downstream guard compares sets, so it allows moving citations (`background_jobs.py:1138-1141`). It does not guarantee one occurrence per original anchor or continued attachment to the same claim. Short quotations below ten words are not frozen (`citation_freezer.py:40-43`, `66-70`). A quotation being short does not make its wording freely editable.

Offline probe executed against the actual local `CitationFreezer` module, without provider imports or calls:

| Candidate with mapping C1→Rossi2023, C2→Bianchi2021 | `all_present` | Result |
|---|---|---|
| Duplicate C1, preserve C2 | true | Citation duplication survives restore. |
| Put C2 on claim A and C1 on claim B | true | Claim/source attachment swaps. |
| Preserve C1/C2 and add unknown C9 | true | Unknown `⟦C9⟧` remains after restore. |

The downstream semantic claim verifier is valuable but is not a complete before/after equivalence proof: it extracts cited sentences (`claim_verifier.py:249-264`, `288-316`). Uncited content, dropped claims, scope/negation changes, and quotations need explicit invariants as well. These probe results show local guard limitations; they are not claims that every corrupt candidate would pass all downstream release gates.

### P1: truncated or failed edit lacks a structured failure outcome

The OpenAI and Anthropic edit calls use fixed output limits and return text without checking finish/stop reasons (`humanizer.py:305-334`, `350-375`). The single-pass method has no general empty-output or length-retention check before returning (`247-282`); the garbling check exists only in the multi-pass candidate selector. A truncated answer can retain all citations if they occur before the truncation. Returning the original on any exception or language/citation rejection is safer than accepting corruption, but the caller receives only a string and cannot distinguish accepted change, rejected candidate and provider error (`226-245`, `257-282`).

### P2: provenance cannot prove Humanizer success

The pipeline writes an event named `humanized` even when the feature is off; the payload includes scores and a multi-pass flag but no applied/status flag, editor identity, original/candidate hashes, or rejection reason (`background_jobs.py:3066-3079`). The baseline score is measured after the unconditional initial pass, not on the raw writer output (`2305-2315`, `2430-2448`). Thus the event name or a before/after score cannot establish that editing ran successfully or improved the raw draft.

### Evidence caveats in tests and style heuristics

`apps/api/tests/test_humanizer_best_of_n.py:1-5` explicitly states both the editor and detector are mocked. These tests prove selection mechanics only.

`stylometrics.py:40-42` explicitly says the empirical work is English-only and its cutoffs are uncalibrated. Calling the implementation's markers “confirmed” does not establish a Compilatio classifier specification for Italian. Its own `10-14` warns that it is not a detector and does not predict Compilatio. The historical broad transfer assumption must not be reused as established fact.

## Minimum sufficient editor contract

1. **Input:** immutable original text/hash; approved outline and target language/register; source pack and claim-to-source anchors; identified content/similarity findings. The baseline and the candidate are separate artifacts.
2. **Separate reasons:** similarity findings drive quotation/attribution/synthesis correction; weak logic or repetitive language drive quality editing. An AI percentage alone does not identify a specific factual or textual defect to fix.
3. **Candidate:** one targeted, bounded editing pass on identified passages. Keep strong passages intact; retain original and candidate. Avoid whole-document serial rewrites as a default.
4. **Protected data:** exact quotations of every length, numbers/units/dates, entities, formulas, source identities, reference list and claim attachments. Any intended factual revision needs explicit supporting evidence, not merely a lower score.
5. **Structured result:** `accepted`, `rejected_integrity`, `rejected_quality`, `provider_error`, `no_change`; actual provider/model, prompt version, finish reason, input/output hashes, change reasons and usage.
6. **Acceptance:** complete output; no extra/missing/duplicate placeholders; same quotation bytes and source attachments; no dropped required arguments; no unsupported new claim; no lost negation/uncertainty/scope; grammar, originality review and academic quality evaluated on the final candidate. Reject or revert on a failed check.
7. **Artifact:** export the accepted candidate as a new DOCX version, render it, hash its actual bytes and attach fresh Compilatio results. Preserve the old DOCX/report unchanged. A lower AI score is not a replacement for source/content correctness.
8. **Proof:** a paired comparison starting from identical raw drafts and source packs, with blinded content judgment and both final artifacts checked under the same detector/report settings. Record every failure and exact AI/similarity dimensions. Do not extrapolate a section win to a full-document PASS.

The minimum offline verification set should deliberately mutate number, negation, scope, source anchor, short quote, citation multiplicity, unknown placeholder, missing paragraph and truncated provider response. These are meaningful integrity regressions, unlike tests that only mirror the wording of the prompt.

Recommendation: retain the current off switch while preparing this editor contract and experiment. Treat the existing citation/source/claim/release infrastructure as reusable. Do not revive score-only best-of-N as the default production solution without paired content-preserving evidence.
