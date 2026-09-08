# Thesica stability — S0–S3 evidence, 2026-09-08

Status: LOCAL_BEHAVIOR_VERIFIED. Fable claude-fable-5-1 reviewed, fixed all P1/P2 findings, then returned APPROVED_FOR_S4_PREPARATION for candidate-files.json. Production, real provider control and agency acceptance require separate evidence.

Base27f80da9101d4faa3c71122105ed6d387cd65655 has app code identical to deployed067e90cab8f9dc8f5720cfc6ff3fb948be11b8f9. S0 compared116 API files and30 release-profile values; zero active jobs. Implementation is isolated in codex/thesica-stability; unrelated main-checkout work is preserved.

## Verification

API command from apps/api: `M0_03_TEST_DATABASE_URL=postgresql+asyncpg://...@127.0.0.1:55439/postgres python -m pytest --no-cov -q`. The URL is the isolated local PostgreSQL15 service. api-reviewed.txt:1373 passed,8 skipped,including11 actual stability PostgreSQL tests and2 existing release races. Skipped tests are not acceptance. Ruff passes. Mypy351 baseline ->348 candidate,zero new normalized messages including multiplicities. This is not green CI: pre-existing mypy debt remains; no protected merge/gate bypass.

Web:30 suites,210 passed,1 skipped; TypeScript,Next lint and production build passed. Web source is unchanged since those checks. Native API/worker and built Next UI use real PostgreSQL/Redis/MinIO; external scholarly/LLM/grammar responses are synthetic but go through actual SDK transport/retries. These proofs made no live provider calls,emails or production generation.

| Requirement | Actual evidence |
|---|---|
| T01 positive | positive-final.json: supported18-page request without mandatory PDFs/methodology; explicit UI start,reload0 paid calls; job6 completed,actual37566-byte DOCX SHA matches DB. |
| T02 final evidence | control8-reproduction.json reproduces original #8 without providers. test_stability_preparation covers immutable chapter structure,pruned/foreign keys,permissible limitation,blocking gap,missing trace. Full-stack job11:25 provisional sources ->24 final,one reconciliation. |
| T03 reviewer | pruned-reviewer-timeout-reviewed.json: timeout then passed,identical binding,2 initial source builds,4 writer calls,1 unknown provider attempt. Tests cover invalid/oversized input,auth/quota/429/5xx,transport,breaker/Redis/DB/storage reasons and actual SDK retry caps. |
| T04 resume/usage | partial-recovery-reviewed.json jobs12/13:0/3 completed sections with exact hashes and same job/pack;claim use preserved;6000tokens/5cents match confirmed journal. test_stability_recovery:3/3->3/6 once,old-intent replay after newer failure gives no grant. test_stability_operations:received receipt before lost counter write;round-up and round-down regressions. |
| T05 concurrency | test_stability_postgres:two resumes one grant/two receipts,manager/admin default POST races,double claim,stale owner,cancel/resume,GDPR deletion marker vs waiting resume. Actual PostgreSQL. |
| T06 safeguards | Full1373 API suite retains worker/cancel/fencing/checkpoint/outbox/storage/shutdown regressions. |
| T07 release | Existing release-evidence suite and2 actualPG release vs negative-review races. Negative whole-review may keep internal DOCX;exact-byte Compilatio,human and no-rewrite release gates remain. |
| T08 export only | export-recovery-reviewed.json job14:3 synthetic storage failures ->explicitUIresume ->completed4/6;zero new writer/search/current whole-review;content/outline/section hashes,claims/tokens preserved;37564-byte DOCX SHA matches DB. Existing tests cover no carried approval on different bytes. |
| T09 UI | Screenshots and explicit start/resume proofs;web tests for reason-driven actions,stable intent,uncertain-response retry,paid acknowledgement. DefaultPOST cannot erase;non-resumable new_version needs reason,confirmation,fingerprint,intent and retains job/receipt history. Reload/login never pays automatically. |
| T10 profile/pause | Profile stamped enqueue/claim/resume;legacy/mismatch blocked. Shared pause fail-closed;actualPG pause races across manager/admin/operator shared path,batch-lock-first and reviewer-retry guards. Zero active jobs at live switch remains S4. |

## Review and corrected failures

Fable's fix and final reads had no permission denials. First review could not read two evidence paths outside cwd; later rounds had explicit directory access. Final review mentions two evidence files still being produced. Both final export and usage results are now included; check-usage assertions passed for jobs11–14. One output filename initially remained the earlier generic name; it was corrected and the checks rerun.

Pre-fix full-stack job7 exposed4cents vs5 journal due to per-attempt rounding. Cumulative per-model rounding fixes both loss and inflation; current jobs11–14 match confirmed journal. Unknown timeouts remain explicit,not free. Earlier synthetic missing-bucket/export failure and two test-fixture mistakes remain in .scratch/stability-20260908/evidence history. No historical business work was rewritten.

## Remaining boundaries

S4: exact built images,first-install ingress closure including operator bot,zero queued/running,fresh database+file restore proof,runtime verification and authorized live control. No migrations,writer/model switch or quality-threshold changes. Full-file profile hashes deliberately block stopped jobs after a relevant deployment. Legacy non-journal costs have an offset;legacy jobs without this profile cannot resume.

S5: actual M1/M2/M3,and same-final-DOCX Compilatio similarity<=10%,AI<=10%,human content/source/format acceptance,no rewrite,Tanya's independent-process acceptance. Synthetic verdicts/local DOCX files do not satisfy them. Numerical RPO/RTO and off-host recovery are not established by local tests.

Archived text logs normalize trailing whitespace and terminal carriage returns only. log-hashes.json preserves both raw and archived SHA-256; original logs remain in the local execution evidence directory.

The mandatory commit hook applied Black formatting after the final review. formatting-equivalence.json proves identical Python AST for all15 changed files. candidate-files.json records final formatted bytes; the previous reviewed manifest and verdict remain traceable in the execution directory. Images are rebuilt from these exact bytes.
