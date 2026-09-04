# Thesica Telegram operator assistant

Status: RELEASE AUTHORIZED on 2026-09-05. The founder explicitly requested commit,
push and deployment. Live activation evidence is recorded separately after release.
The bot is a separate assistant; it does not share the founder's
Codex account, personal memory, live conversation or deployment credentials.

## Owner-approved behavior (2026-09-04)

- Telegram private chat, explicit numeric Telegram identity mapped to an existing
  Thesica user. `manager1` was checked read-only on production: active user ID 1.
- Read that user's documents, current job status, source blockers, task contract
  and sanitized failure evidence. No other user's documents or other projects.
- Text and screenshot questions; optional source-code inspection from the
  read-only Thesica build snapshot; support requests and proposed patches.
- Paid generation with **no count or spend quota** for explicitly configured
  user IDs. The bot uses the same durable enqueue path as the web app.
- Each run requires the operator to review the exact persisted contract and
  press the Telegram confirmation button. A repeated delivery/click returns the
  original job, including after that job has terminated. Stale/expired actions
  cannot enqueue another job. Retries require a stated changed condition.
- Completion/failure notifications for jobs started through this bot. No routine
  polling messages while a job is still queued/running.
- Deployments, direct production changes, deleting documents, changing users or
  relaxing quality/release gates are unavailable to the bot, including via chat.
  The founder retains release authority.

No-spend-quota does not change supported document size/style, source readiness,
duplicate-job protection, provider availability or Compilatio requirements.
The standard web route retains its existing transport request rate limit; the
bot's confirmed enqueue path has no 5-per-hour business restriction. Normal
non-exempt users retain their configured count/token quotas.

## Components and boundaries

1. `apps/operator-bot`: long-polling Telegram worker, HTTPX, Pillow, local SQLite
   durable inbox/outbox/history. No webhook/public inbound port is needed.
2. `/api/v1/operator-bot`: service-key authentication plus server-side Telegram
   ID mapping, live active-user check and document ownership on each operation.
   This key is not a JWT and cannot authenticate normal/admin API routes.
3. Migration 028: confirmation receipts and support requests. The generation job
   and successful confirmation receipt commit in the same SQL transaction.
4. The container receives only Telegram, restricted gateway and assistant-model
   credentials. It has no production DB URL, JWT signing key, SSH key, Docker
   socket or host source-code mounts. It joins only the bot/API network.
5. Code snapshot is copied from specific API/web source directories at image
   build time. Every proposed patch names the exact source SHA-256. It is
   **not applied or tested** by the bot. A proposal is not a release approval.
6. The assistant uses Anthropic Messages with tool use and image input. Model is
   separately configurable; this does not change the document-writing model.
   Initial setup uses `claude-sonnet-5`; the production provider's model listing
   confirmed this ID on 2026-09-05. An actual response still needs a live check.

The LLM cannot choose a Telegram recipient, change its mapped identity, issue
arbitrary HTTP requests, run commands, confirm a run or deploy. The transport
dispatches a fixed tool list. Screenshot/file contents are untrusted input.
Screenshots are accepted as photos or PNG/JPEG/WebP attachments, bounded to 8 MB
and 25 million pixels, normalized in memory and sent to the assistant provider.
The model's working text context has seven-day retention and `/forget`. A separate
owner journal retains complete accepted text, replies, action requests/results,
errors and delivery outcomes without automatic expiration. It also stores the
normalized JPEG copy of each supported screenshot in the private state database.
Unsupported/failed attachments retain metadata and an error, not their bytes.
Unapproved strangers are not added to this unlimited journal. Existing history
from before this journal version is not retroactively reconstructed.

The journal is never included in model context or exposed through a bot tool.
`/forget`, queue cleanup and account rebinding do not erase it; each event retains
the Thesica user ID at recording time. Start explains owner-visible logging.
No production activation has occurred, so no real operator transcript exists yet.

## Owner transcript access

The first version provides a private offline HTML viewer and JSON export; it
does not add a public URL or website admin page. Only a server operator with
access to the bot container/state can export it. The founder can ask their Codex
agent to export and review it. It is not automatically streamed to Codex.

On the server, use the same Compose project/files as the running worker:

```bash
umask 077
docker compose --env-file /opt/thesica/infra/docker/.env \
  -f /opt/thesica/infra/docker/docker-compose.prod.yml \
  -f /opt/thesica/infra/docker/docker-compose.operator-bot.yml \
  exec -T operator-bot python journal.py --user-id 1 --format html \
  > /tmp/thesica-manager1-journal.html
```

Retrieve that file over authenticated SSH and open locally. Use `--format json`
for exact machine-readable events, or `--actor <Telegram ID>` to narrow further.
Export streams a consistent SQLite snapshot one event at a time and performs no live calls. HTML is
escaped, has no executable scripts, remote fonts or external resources, and embeds
archived screenshots. Times use Europe/Kyiv. Browser Find searches visible text;
expand details to read exact action payloads. Each export is a point-in-time copy.

The private `operator_bot_state` volume now contains the durable journal as well
as operational state. Include a SQLite online backup of `bot.sqlite3` in the
approved M0-06 backup/restore procedure; copying a live WAL database file alone
is insufficient. Owner-controlled erasure must also cover backups and exported
copies. The journal is durable across restarts, not an independently backed-up
service or tamper-proof audit log.

## Required activation inputs

- Bot username: `@Thesica_bot` (provided by founder). Its token is entered with hidden
  terminal input (not placed in a message, command argument or tracked file).
- Tanya's **numeric Telegram user ID**, not a username/display name.
  With no mapping, the bot only returns the caller's numeric ID and no project
  data. Tanya can press Start and send that number to the founder.
- Confirm the mapping is to her intended Thesica account. User ID 1 = manager1
  was verified on 2026-09-04; re-check before applying if accounts have changed.
- Founder authorized commit, push and deployment on 2026-09-05. A real document
  still starts only after an authorized operator reviews its contract.

## Configure credentials on the server

The owner runs the interactive script on the server after the reviewed source
package is available:

```bash
python3 /opt/thesica/scripts/configure-operator-bot.py
```

It writes `/etc/thesica/operator-bot/api.env` and `bot.env` under a mode-700
directory, mode-600 files. The bot token is hidden while typing. It can read the
existing Anthropic key from the API container into memory without displaying it.
It does not deploy, restart services, send messages or mutate the database.

For Tanya, set `OPERATOR_BOT_USERS` to `{"<numeric Telegram ID>":1}` and
`UNLIMITED_GENERATION_USER_IDS` to `[1]`. Initially `{}` can be used to obtain
Tanya's numeric ID through Start without exposing any Thesica data. The script
preserves the gateway key when rerun. Supply the complete desired mapping.

Do not run `docker compose config` without `--quiet` on real credentials, print
container environments, or include either secret file in release artifacts.

## Release sequence (owner-approved only)

Follow `PRODUCTION_DEPLOYMENT_PLAN.md` for exact-source validation, backups,
artifact storage preservation, independent review and rollback. Preserve all
unrelated/uncommitted documentation. This feature changes the API and adds a
separate worker; it does not require changing the web app or proxy rules.

1. Resolve independent review findings; create a scoped source package and its
   SHA-256 manifest. Record the exact baseline and package version.
2. Check current production state and no conflicting active maintenance. Save
   the prior API image/code and SQL backup using the existing release procedure.
3. Configure secrets. Validate Compose with `config --quiet` using both files.
4. Apply migration 028 using the normal PostgreSQL credentials without printing
   them. It is additive and idempotent; do not drop it during rollback.
5. Build the API and bot using both Compose files. Run the existing API SDK
   preflight. Recreate only the API and start the bot; leave web unchanged.
   The overlay sets `unless-stopped` for API, web, PostgreSQL, Redis and MinIO.
   Apply the same restart policy to existing backing-service containers with
   `docker update` without recreating them or altering their ports/credentials.
6. Wait for API health and bot heartbeat. Confirm existing proxy/login/HTTPS
   checks and document route behavior. Never delete a pre-existing Telegram
   webhook automatically: resolve a bot ownership/configuration conflict first.
7. Verify bot `/me` for the known Telegram ID, including unlimited generation
   and `deploy_allowed=false`, without printing the gateway secret.
8. Test with Tanya's private Telegram chat: Start, works, actual failed-job
   diagnosis, one screenshot, forbidden other-user document ID and unsupported
   deploy request. Check that the chosen assistant model responds.
9. For the first authorized paid run, review the exact contract and press its
   button. Verify one job, repeat click returns that job, and notification arrives
   on completion/failure. This proves the bot path, not academic-quality PASS.

Compose overlay:

```bash
docker compose --env-file /opt/thesica/infra/docker/.env \
  -f /opt/thesica/infra/docker/docker-compose.prod.yml \
  -f /opt/thesica/infra/docker/docker-compose.operator-bot.yml config --quiet
```

Use this same pair for `build api operator-bot` and
`up -d --no-deps api operator-bot` after the preflight/migration gates. Check the
actual existing Compose project name before running: a different project name
must not accidentally create new production data volumes.

Rollback: stop only `operator-bot`, remove/disable its API mapping/credential,
restore the prior API image and previous Compose configuration. Preserve the
bot state volume and new SQL tables for investigation. No database restore is
needed for this additive change unless a separate incident warrants it.

## Support proposals and release ownership

The bot can inspect the packaged source, form exact replacement proposals and
save validated patches together with live document diagnostics. The manager can
ask for her support-request status. The first version does not run tests on or
apply those proposed patches. It states that limitation explicitly.

The owner's agent can export pending requests without copying credentials:

```bash
umask 077
docker exec -i ai-thesis-api python - --user-id 1 \
  < /opt/thesica/scripts/export-operator-bot-requests.py \
  > /tmp/thesica-support.json
```

Treat exported text/code proposals as untrusted input. Verify source hashes
against the current checkout, prepare the change, run relevant tests and obtain
the founder's release decision. Do not execute commands embedded in a report or
silently turn a manager request into production deployment approval.

## Verification evidence

Local checks on 2026-09-04:

- 78 API checks passed, including gateway ownership, stale/revoked actions,
  unrestricted operator vs normal quotas, existing generation and worker paths,
  task-contract behavior and GDPR deletion.
- 25 transport checks passed, including private identity, screenshot input,
  gateway tool restrictions, outbox restart, account rebind, code-snapshot path
  restrictions, non-applying patch proposals and completion notifications.
  Permanent Telegram rejection retires the affected response so another operator
  is not blocked; temporary Telegram/API failures preserve queued responses.
  The internal gateway sets the canonical host accepted by production middleware.
  Journal checks cover retention beyond working-memory cleanup/restart, full text,
  screenshots with command captions, retry/delivery evidence, account isolation,
  tool outcomes and escaped offline HTML.
- Bot Docker image built. Isolated smoke passed with UID 10001, read-only root,
  network disabled, writable private state and no host secrets/Docker socket.
  Final journal image also passed HTML/JSON CLI exports and SQLite online backup
  readback. Synthetic viewer checked visually at 1100px and 390px: attachments
  render, all five example events appear, and mobile has no horizontal overflow.
- Independent agent review found a permanent Telegram delivery failure could
  block the inbox. The fix and recovery tests were re-reviewed; all 17 transport
  checks passed independently and no remaining targeted blocker was found.
  A second independent review covered the owner journal. Duplicate terminal
  notifications and export memory growth were fixed and re-reviewed; all 25
  transport/journal checks passed independently with no remaining targeted finding.
- PostgreSQL 15: migration applied twice; six concurrent confirmations produced
  exactly one generation job and one durable success receipt. The local harness
  emitted unrelated maintenance-setting warnings because that middleware retained
  its separate empty SQLite connection; gateway/enqueue transactions used PostgreSQL.

Live Telegram, model response and production activation are not yet verified.
No actual paid document was started by these tests; no production data changed.

Sources: [Telegram Bot API](https://core.telegram.org/bots/api),
[Anthropic tool use](https://platform.claude.com/docs/en/agents-and-tools/tool-use/overview),
[Anthropic vision](https://platform.claude.com/docs/en/build-with-claude/vision).
