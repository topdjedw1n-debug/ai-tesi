# Telegram operator assistant release — 2026-09-05

Status: DEPLOYED, HEALTHY, AWAITING TANYA'S TELEGRAM ID.

## Authorization and exact scope

Founder explicitly requested commit, push and deploy. The subsequent instruction
deferred Tanya's ID until later; no message was sent to her by the deployment agent.

- Code commit: `34d8f79a77471d7588b8832a3506e71a734b593f`.
- Pushed branch: `codex/telegram-operator-bot`. It is not merged into main.
- Runtime: Hetzner `95.216.184.254`, `/opt/thesica`, Compose project `docker`.
- Updated API; added Telegram worker, private journal and additive migration 028.
- Web image and proxy routes unchanged. Restart policy is now `unless-stopped`
  for API, bot, web, PostgreSQL, Redis and MinIO; existing backing services were
  not recreated. A physical server reboot was not performed.
- All unrelated working-tree and staged documentation was preserved. The release
  was committed from an isolated checkout containing only 17 scoped files.

## Verification

- 78 relevant API tests and 25 transport/journal tests passed in the isolated
  release checkout. The 10 gateway tests were rerun after annotation cleanup.
- Repository pre-commit checks passed. Both new API modules passed targeted
  mypy with silent dependency following. This is not whole-repository mypy PASS.
- Independent gateway/transport/journal review completed; all findings were fixed
  and targeted fixes re-reviewed. No remaining targeted finding was reported.
- GitHub CI is not triggered by pushes to this feature branch under the current
  workflow filters. No claim is made that the full GitHub workflow passed.
- 226 delivered API, bot, source snapshot and Compose files matched the commit.
  110 API files inside the running container also matched their source hashes.
- Built API SDK compatibility and secret-exclusion preflight passed.
- All 29 runtime profile values matched the canonical release profile.
- All six services running and healthy. API/web ports remain loopback-only;
  the bot, database, Redis and MinIO have no published ports.
- Eight HTTPS checks passed: health, login, dashboard, closed registration,
  blocked magic-link, authenticated document creation, protected bot gateway,
  and HTTPS-preserving document redirect.
- In a separate diagnostic process using the installed API and real database,
  manager1 ownership, unrestricted generation permission, deployment denial,
  unknown-actor rejection and both new schema tables passed. Its temporary test
  mapping was never installed in the running API.
- From the live bot container, the internal gateway correctly rejected an
  unmapped actor. Bot state is mode 600, running as UID 10001 without database,
  signing-key or Docker-socket access. Live HTML/JSON exports and SQLite online
  backup/readback passed. The owner journal currently contains zero events.
- BotFather token validated as `@Thesica_bot`; no pre-existing webhook.
  `claude-sonnet-5` appeared in the provider's model list and returned live text.
  Only a small assistant smoke request was made; no document generation started.

## Backup and rollback

Backup directory: `/opt/thesica/backups/operator-bot-20260904-210547`.
The timestamp in the directory is UTC; this record uses Europe/Kyiv.

- PostgreSQL custom dump: 189,671 bytes. Restored successfully into an isolated
  PostgreSQL 15 container without published ports; restored tables were queried.
  The disposable restore container was removed afterwards.
- Previous source archive: 9,380,667 bytes; MinIO archive: 11,177 bytes. Both
  archives were read back. Existing files and database volumes were preserved.
- Private previous Compose environment and current online bot-state backup are
  retained in the same protected backup directory; no secrets are in Git.
- Previous API tag: `ai-thesis-api:operator-rollback-20260904-210547`.
- Previous API image: `sha256:a2ed08b79644ed1e16021db7e7f8f4bb99636def020b400ba8cedb9ae9d99775`.

For rollback, stop only the operator worker, restore the previous source archive
and API image, then recreate API with the previous Compose configuration and
existing project/volumes. Preserve migration 028 and bot state. Database restore
is unnecessary for this additive release. Re-run the HTTPS checks afterwards.

Live markers: `/opt/thesica/.operator-bot-release.json` and
`/opt/thesica/.operator-bot-canary.json`. The old global `.release-sha` is not used
as evidence for the unchanged web image or this scoped release.

## Remaining activation step

Telegram mapping remains `{}`. manager1 is active Thesica user ID 1; its unlimited
generation exemption is configured. When Tanya presses Start, the bot reveals
only her numeric Telegram ID. The founder must identify that ID before it is
mapped to manager1. No account has been enrolled by guessing identity.

Tanya's real text/screenshot workflow, confirmed paid generation and terminal
notification still require her enrollment. Deployment is not proof of academic
quality, Compilatio PASS or M1–M3 completion.
