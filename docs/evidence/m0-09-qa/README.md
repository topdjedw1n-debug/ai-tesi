# M0-09 generation completion QA

Executed isolated harness; [results and limits](../M0-09-2026-09-07.md),
[machine evidence](../M0-09-2026-09-07.json). These are recorded test steps,
not a production runner or a one-command environment installer.

Use a scratch directory containing these files and a candidate checkout at
`worktree`. Compose project: `thesica-completion`; private PostgreSQL 15,
Redis 7 and MinIO; API `127.0.0.1:8330`. PostgreSQL local user/database:
`resilience`; container `thesica-completion-postgres-1`. Mount candidate
`apps/api` at `/app`, scratch at `/qa`, `PYTHONPATH=/app:/qa`. Run
`uvicorn provider_fixture:app --host 0.0.0.0 --port 8000` in the API container.
Apply migrations only to that empty local database; create the local storage
bucket `resilience-documents`; run `seed.py` only against this isolated database.
Its fixed password is a synthetic fixture, never a production credential.

Use the committed 30-value release profile, operator/unlimited IDs `[1]`,
synthetic secrets and provider keys, lease20/heartbeat3/retry2..5 seconds.
Set the local API rate limiter off for this repeated matrix; its actual
5/hour limit was already tested in M0-08. No production data, credentials or
real provider keys belong in the synthetic harness. Private environment and
authentication files are deliberately excluded from git.

Log in to the local API as `qa-manager`; save only its short-lived access token
to scratch `qa-token` (mode600). `api-control.cjs` uses that session. Run
`node completion-matrix.cjs` from scratch. Nine cases execute serially because
they share `control.json`. Each must finish the same job in one worker attempt,
download a valid DOCX and match its stored SHA-256. The script records all
result rows and the fixture records SDK requests in `provider-calls.jsonl`.

The fixture intercepts external scholarly, grammar and HTTP provider responses;
SDK request serialization, output parsing, retry handling, actual HTTP API,
worker, PostgreSQL, Redis, MinIO and DOCX formatting remain real. Scores and
text are explicitly synthetic. Never count them as Compilatio or M1 PASS.
The helper itself has no token refresh; renew its local token when expired.
Product browser/session recovery is covered separately in M0-08.

Four **separate real provider runs** used `uvicorn main:app`, private provider
keys and the same isolated local storage, with no fixture import. They are
recorded including the failed first education run. `inspect-real.py` checks
downloaded files, markers and saved section evidence. It expects the result
JSONs and DOCX files named in the machine evidence at `/qa`. Those files are
retained locally under root `.scratch/m0-09/`; no private keys are retained
with them. Page numbers in the results are requested targets, not rendered
page counts. Paid replay is not part of the synthetic harness.

`source-live-baseline.jsonl` records read-only scholarly searches on four topics
before the fixes, with manually supplied English translations, zero LLM calls
and no database writes. It demonstrates the existing normal retrieval path;
the new automatic repair paths are supported by the matrix and real runs.
