# M0-08 technical QA evidence

These scripts are the **executed isolated harness**, not a production runner.
The authoritative result and boundaries are in [the report](../M0-08-2026-09-07.md)
and [JSON evidence](../M0-08-2026-09-07.json). Screenshots contain synthetic QA work.

The environment used a scratch directory containing these scripts and a
`worktree` checkout of the candidate. Web ran on `127.0.0.1:3120`, API on
`127.0.0.1:8320`; PostgreSQL/Redis/MinIO were private containers in Compose
project `thesica-resilience`. The API mounted `apps/api` at `/app` and the scratch
directory at `/qa`, then ran `uvicorn provider_fixture:app --host 0.0.0.0 --port 8000`.
Web was built/started only with `NEXT_PUBLIC_API_URL=http://localhost:8320`.

Create **only isolated** test users and storage bucket `resilience-documents`;
use synthetic local secrets. Apply the committed release profile, operator ID 1,
worker lease 20s, heartbeat 3s, retry base2/max5 seconds. First verify the normal
rate limiter; disable it only for repeated isolated stress calls. For reproducing
ISSUE-008 set `CLAIM_VERIFICATION_MAX_CHECKS=50`, then compare with release100.
No production credentials, data or provider keys may enter this harness.

`provider_fixture.py` replaces external scholarly/LLM/grammar responses, writes
stage evidence and rejects external httpx calls. It does **not** replace the API,
worker, locks, database, DOCX exporter or MinIO. Modes and stage holds live in
scratch `control.json`, e.g. `{"mode":"success","hold":"writer_2"}` or
`{"mode":"many_claims","hold":null}`. Never run two fault cases concurrently:
they intentionally share this control file and may stop a dependency container.

`api-control.cjs` reads `browser-state.json` produced by a real local QA login.
That private authentication file and the private environment are intentionally
not checked in. Refresh that session if it expires; the native helper is not the
application's session-refresh implementation. Run scripts from the scratch
directory, with Playwright installed in `worktree/apps/web/node_modules`.

Executed commands included `node pipeline-matrix.cjs providers`, `recovery`,
`redis`, `storage` and `database`; `node browser-core.cjs`, `cancel-upload.cjs`,
`browser-release.cjs` and `browser-upload-failure.cjs`. Browser-release uses the
specific **isolated** document14 from this execution; select an equivalent newly
completed fixture before replay. The individual scripts preserve the recorded
test steps; they are not a one-command environment installer.

Permanent regressions are committed under `apps/api/tests` and
`apps/web/**/__tests__` with ISSUE-001 through ISSUE-009 in their comments. Run
the API suite from the repository checkout with `pytest -o asyncio_mode=auto`;
container mounts must preserve the repository depth for runtime-contract tests.
Real PostgreSQL lock tests additionally require an isolated
`M0_03_TEST_DATABASE_URL`. Never point that variable at production.
