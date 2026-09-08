# Thesica stability — S0–S3 evidence, 2026-09-08

Status: LOCAL_BEHAVIOR_VERIFIED. Fable claude-fable-5-1 reviewed, fixed all P1/P2 findings, then returned APPROVED_FOR_S4_PREPARATION for candidate-files.json. Production, real provider control and agency acceptance require separate evidence.

Base 27f80da9101d4faa3c71122105ed6d387cd65655 has app code identical to deployed 067e90cab8f9dc8f5720cfc6ff3fb948be11b8f9. S0 compared 116 API files and 30 release-profile values; zero active jobs. Implementation is isolated in codex/thesica-stability; unrelated main-checkout work is preserved.

## Verification

API command from apps/api: `M0_03_TEST_DATABASE_URL=postgresql+asyncpg://...@127.0.0.1:55439/postgres python -m pytest --no-cov -q`. The URL is the isolated local PostgreSQL15 service. api-reviewed.txt:1373 passed, 8 skipped,including 11 actual stability PostgreSQL tests and 2 existing release races. Skipped tests are not acceptance. Ruff passes. Mypy 351 baseline ->  348 candidate,zero new normalized messages including multiplicities. This is not green CI: pre-existing mypy debt remains; no protected merge/gate bypass.

Web:30 suites, 210 passed, 1 skipped; TypeScript,Next lint and production build passed. Web source is unchanged since those checks. Native API/worker and built Next UI use real PostgreSQL/Redis/MinIO; external scholarly/LLM/grammar responses are synthetic but go through actual SDK transport/retries. These proofs made no live provider calls,emails or production generation.

| Requirement | Actual evidence |
|---|---|
| T01 positive | positive-final.json: supported 18-page request without mandatory PDFs/methodology; explicit UI start,reload0 paid calls; job 6 completed,actual37566-byte DOCX SHA matches DB. |
| T02 final evidence | control8-reproduction.json reproduces original #8 without providers. test_stability_preparation covers immutable chapter structure,pruned/foreign keys,permissible limitation,blocking gap,missing trace. Full-stack job 11:25 provisional sources ->24 final,one reconciliation. |
| T03 reviewer | pruned-reviewer-timeout-reviewed.json: timeout then passed,identical binding,2 initial source builds,4 writer calls,1 unknown provider attempt. Tests cover invalid/oversized input,auth/quota/429/5xx,transport,breaker/Redis/DB/storage reasons and actual SDK retry caps. |
| T04 resume/usage | partial-recovery-reviewed.json jobs 12/13:0/3 completed sections with exact hashes and same job/pack;claim use preserved;6000tokens/5cents match confirmed journal. test_stability_recovery:3/3->3/6 once,old-intent replay after newer failure gives no grant. test_stability_operations:received receipt before lost counter write;round-up and round-down regressions. |
| T05 concurrency | test_stability_postgres:two resumes one grant/two receipts,manager/admin default POST races,double claim,stale owner,cancel/resume,GDPR deletion marker vs waiting resume. Actual PostgreSQL. |
| T06 safeguards | Full 1373 API suite retains worker/cancel/fencing/checkpoint/outbox/storage/shutdown regressions. |
| T07 release | Existing release-evidence suite and 2 actual PG release vs negative-review races. Negative whole-review may keep internal DOCX;exact-byte Compilatio,human and no-rewrite release gates remain. |
| T08 export only | export-recovery-reviewed.json job 14:3 synthetic storage failures ->explicitUIresume ->completed4/6;zero new writer/search/current whole-review;content/outline/section hashes,claims/tokens preserved;37564-byte DOCX SHA matches DB. Existing tests cover no carried approval on different bytes. |
| T09 UI | Screenshots and explicit start/resume proofs;web tests for reason-driven actions,stable intent,uncertain-response retry,paid acknowledgement. DefaultPOST cannot erase;non-resumable new_version needs reason,confirmation,fingerprint,intent and retains job/receipt history. Reload/login never pays automatically. |
| T10 profile/pause | Profile stamped enqueue/claim/resume;legacy/mismatch blocked. Shared pause fail-closed;actual PG pause races across manager/admin/operator shared path,batch-lock-first and reviewer-retry guards. Zero active jobs at live switch remains S4. |

## Review and corrected failures

Fable's fix and final reads had no permission denials. First review could not read two evidence paths outside cwd; later rounds had explicit directory access. Final review mentions two evidence files still being produced. Both final export and usage results are now included; check-usage assertions passed for jobs11–14. One output filename initially remained the earlier generic name; it was corrected and the checks rerun.

Pre-fix full-stack job7 exposed4cents vs5 journal due to per-attempt rounding. Cumulative per-model rounding fixes both loss and inflation; current jobs11–14 match confirmed journal. Unknown timeouts remain explicit,not free. Earlier synthetic missing-bucket/export failure and two test-fixture mistakes remain in .scratch/stability-20260908/evidence history. No historical business work was rewritten.

## Remaining boundaries

S4: exact built images,first-install ingress closure including operator bot,zero queued/running,fresh database+file restore proof,runtime verification and authorized live control. No migrations,writer/model switch or quality-threshold changes. Full-file profile hashes deliberately block stopped jobs after a relevant deployment. Legacy non-journal costs have an offset;legacy jobs without this profile cannot resume.

S5: actual M1/M2/M3,and same-final-DOCX Compilatio similarity<=10%,AI<=10%,human content/source/format acceptance,no rewrite,Tanya's independent-process acceptance. Synthetic verdicts/local DOCX files do not satisfy them. Numerical RPO/RTO and off-host recovery are not established by local tests.

Archived text logs normalize trailing whitespace and terminal carriage returns only. log-hashes.json preserves both raw and archived SHA-256; original logs remain in the local execution evidence directory.

The mandatory commit hook applied Black formatting after the final review. formatting-equivalence.json proves identical Python AST for all15 changed files. candidate-files.json records final formatted bytes; the previous reviewed manifest and verdict remain traceable in the execution directory. Images are rebuilt from these exact bytes.

## S4 installed candidate — 20:20:59 UTC

Code 189aba72ba11d73cad4a30e5203da44ea0261bd0 is committed/pushed and installed. API image 850a4e428e7c9910bbda1ebcd482c1d953e697b9202e5dc09eab0e23088c983e;web image 2112a7e8f317c9ad1c2d4af7340a068e12285863d60f71114bb0d41459dd6437;build x7ixzspzw9qVTZ3oqryTS. All 122 current API modules match; 30 production-profile values unchanged; 6 services healthy. Bot retained its image/code 7249e50 and container,only stopped/restarted for the ingress barrier. No migrations or env changes.

Caddy blocked every mutating API request and the internal operator-bot path was stopped before the first installation. Four public start/retry/resume/review-retry probes returned503. Zero active jobs at switch. Read-only live browser verified 3 routes with 0 paid/mutating requests and 0 page/API errors;old #8 correctly offers explicit new-version action rather than guessing compatibility. Exact hashes of 8 documents, 8 jobs, 11 sections, 143 provenance events and 8 cases were identical before/after runtime switch. New paid generation has not started. Ingress restored and bot healthy after checks.

Fresh backup:/opt/thesica/backups/stability-20260908. Isolated PostgreSQL restore matches all5 business-table row sets;restored MinIO API streams match both original objects by SHA-256(total 222522 bytes). Database+files restoration passed. This is same-host recovery;off-host copy/access and numeric RPO/RTO remain unverified,not invented.

Exact formatted-image 156 runtime tests passed. The earlier pre-format image full run had 1345 passes, 21 skips, 15 failures caused solely by absent infra/workflow files in the verification mount. All 15 are included in the 156 successful final-image tests. Do not call the formatted-image run a full 1373 run;native 1373 and AST equivalence are separate evidence.

Prepared production draft 9/case 11 preserves the exact brief,uploaded university requirements and contract hash of the prior control. It is draft,without an outline or DOCX; 0 paid calls. The requested single-control approval is pending under execution-plan §7. Live provider generation and S5 academic/manager acceptance remain open,so LIVE_CANDIDATE_VERIFIED/AGENCY_ACCEPTED are not claimed.
