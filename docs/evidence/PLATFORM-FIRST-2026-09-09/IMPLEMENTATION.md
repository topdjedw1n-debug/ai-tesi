# Platform-first: local implementation, 2026-09-09

Status: **LOCAL_IMPLEMENTATION_READY**, Fable **DIRECTION_APPROVED / LOCAL_IMPLEMENTATION_READY**, all required local checks complete. Branch `codex/thesica-platform-first`, isolated worktree `.scratch/stability-20260908/ac-local`. No server changes or full paid generation.

## Implemented in the approved order

- PF01: inventoried locally available works 7–11. None contains a complete original model-call recording. Partial outlines and work 7 text remain labelled historical persisted output; historical statuses were not changed.
- PF02: durable full SDK request/response/error before parsing, with job/stage/section/attempt/usage/time; external retrieval/cache/file/checker inputs captured too. Offline CLI executes the actual worker and DOCX export with network disabled, exact input matching, isolated SQLite/object storage and no live fallback. Missing/ambiguous recording is explicitly incomplete.
- PF03: new manager jobs use `platform-first-v1`; retrieval, preparation, academic reviews, grounding, claim/panel/quality findings are warnings visible in the production case. Bad preparation keeps the initial outline. One configured editor pass remains; quality scores no longer trigger rewrites. Initial outline/writer access or unusable response after bounded retries, required storage/DB/checkpoint failure, cancellation and stale-worker exit retain their technical semantics. Warning/record storage failures cannot silently pass. Release policy still requires the same final file and existing Compilatio/no-rewrite/manager authorization.
- PF04: standard academic sources may supplement retrieved evidence. Structured reference metadata is removed from prose and carried separately as unverified manager findings; no invented DOI/page/verification. The original work 11 brief yields 14 nested search scopes. Concise scoped queries, limited alternate-language expansion and per-attempt translation reuse avoid duplicate retrieval. Lexical false-positive calibration remains deferred.
- PF05: seven scenarios with synthetic external inputs run the real fenced worker through actual DOCX export and strict offline replay. Historical partial corpus, one actual new writer-stage response and real PostgreSQL concurrency checks are separate evidence classes.

## Real changed-stage call and cost

Two calls of the same changed writer stage used the unchanged work 11 master-level Italian perinatal brief, saved source pack and chapter 2 target. Aggregate **$0.42 usage-based cost** ($0.21 + $0.21), 58,534 tokens, approved per-stage ceiling $5, remaining $4.58. No full job or additional writer calls. Full request/SDK response fixtures: `apps/api/tests/fixtures/platform_first/real_writer_stage_11{,_v2}.json`.

| Observation | First prompt | Final prompt |
|---|---|---|
| Words returned | 1,065 | 1,112 |
| Unresolved citation key in prose | Selix2015 | None |
| Standard references outside pack | 3, unverified | 4, unverified |
| Complete response recorded | Yes | Yes |
| Exact prompt replay | Passed on initial code | Passed on final code |

The first recorded response also exercises the final neutral citation renderer without a new model call. Its old prompt is explicitly flagged changed, so it is **not** evidence for the final prompt. The final response is replayed through the actual `SectionGenerator` with exact request matching and identical final text/bibliography. Filtering removes stale evidence keys only from a copied prompt outline; all saved chapters, requirements and historical inputs remain unchanged. Unresolved citations remain explicit manager findings and never become verified bibliography entries. Standard NANDA-I/NOC/WHO references remain unverified. APA formatting for multiple authors without a known year and institutional-author surnaming (World Health Organization -> Organization) is deferred per Fable's nonblocking notes.

This is a bounded before/after observation of one chapter, not proof of general text quality, a whole work 11 replay or three real orders. `stage-spend.json` contains both receipts; Fable CLI review usage is separate from the writer-stage budget.

## Validation

- Full API suite after production changes: **1,445 passed, 24 skipped**, no failures. Existing warnings: pytest configuration/deprecations.
- The final actual model response was then added to the corpus: **16 corpus tests passed**, including both real responses, unchanged historical 7–11 records, source-scope preservation and real work 7 text export.
- **Seven** scenarios with synthetic external inputs run the actual fenced worker -> DOCX -> strict offline CLI replay; part of the full API suite. They cover sparse sources, negative reviewer/preparation, standard references, missing-abstract enrichment, unavailable editor and unresolved citation formatting.
- **14 real local PostgreSQL tests passed**, including cancellation/lease/receipt and plan-preparation concurrency checks. Local test container stopped afterwards.
- **19 frontend tests passed**, TypeScript passed. API-level warning visibility was reproduced failing before adding the response schema field and then verified through the real endpoint; 83 affected tests passed at that checkpoint.
- Ruff and `git diff --check` passed. Full and focused logs retained in this directory. Fable read-only CLI reviews are saved alongside this report.

## Local replay

From `apps/api`: `python scripts/replay_generation.py RECORDING.json NEW_OUTPUT_DIRECTORY`. Export `document_provenance` including the initial `generation_replay_inputs`, model and dependency events; pass `--job-id`/`--worker-attempt` if needed. The output directory must be new. `--allow-request-changes` is diagnostic only and flags a changed request; it cannot prove a changed prompt. The stage-only fixture above is replayed by `test_recorded_real_writer_stage_11_replays_exact_prompt_without_sdk`, not presented as a complete job recording.

## Remaining acceptance

Full real job capture/replay, three distinct real orders completed without developer intervention, Tanya acceptance, Compilatio on the final DOCX and content/source acceptance remain unverified. Full paid runs and installation on the server still require the founder's separate explicit “yes”.
