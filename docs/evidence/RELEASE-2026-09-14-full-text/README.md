# Реліз «повнотекстові докази» на app.thesica.co — підготовлено, чекає на дозвіл інструмента (14.09.2026)

**Підстава:** фаундер 14.09: «Окей, в тебе все так, працюй» у відповідь на пропозицію (а) реліз сьогоднішнього коду на сервер за планом розгортання, (б) службовий акаунт `control1` без денної квоти. Виконавець — Fable.

## Стан

Усе локальне зроблено; жоден крок на сервері **не виконано**: середовище Claude Code в автоматичному режимі відхиляє будь-який запис на віддалений сервер (`ssh thesica …` зі змінами, `rsync` на сервер) з причиною «Remote Shell Writes», а також читання бази продакшену через `psql` («Production Reads»). Дозвіл «так» у чаті цього не знімає — потрібне правило дозволу в налаштуваннях Claude Code (див. нижче) або виконання команд фаундером.

Що вже перевірено без запису:
- сервер живий: 6 контейнерів healthy; образи API/web від 12.09 10:51 (`3892cac`, у контейнері 1 498 рядків `executor_v2`, `full_text_sources.py` відсутній); `UNLIMITED_GENERATION_USER_IDS=[1]` живе в `/etc/thesica/operator-bot/api.env`;
- «сухий» rsync (`-n`) показав рівно очікувані файли: 9 змінених модулів API, 1 новий (`full_text_sources.py`), нові скрипти лабораторії й тести; web не змінюється. З пакета треба виключити `.DS_Store`, `coverage.xml`, `infra/docker/uploads/`;
- код: `main` = `d15305a` (+ цей запис); повні тести API на цьому коді: **1421 passed, 23 skipped, 0 failed** (125,9 с); web: 211 passed, 1 skipped; `ruff` чисто;
- міграцій немає; `POLICY`, перелік моделей, профіль релізу не змінюються; змінюється лише поведінка S2/S4 (повні тексти) — див. [S2-FULL-TEXT-EVIDENCE-2026-09-14](../../plans/S2-FULL-TEXT-EVIDENCE-2026-09-14.md).

## Команди релізу (у цьому порядку; кожна — запис на сервер)

1. Зберегти попередній серверний пакет (план §5):
   ```bash
   ssh thesica 'mkdir -p /opt/thesica/releases/pre-full-text-20260914 && cp -a /opt/thesica/apps /opt/thesica/infra /opt/thesica/releases/pre-full-text-20260914/ && du -sh /opt/thesica/releases/pre-full-text-20260914'
   ```
2. Доставити вибраний код (з кореня репозиторію на `d15305a`):
   ```bash
   rsync -rlc --itemize-changes --exclude='.env*' --exclude='node_modules' --exclude='.next' --exclude='.git' --exclude='__pycache__' --exclude='*.pyc' --exclude='venv' --exclude='.venv' --exclude='qa_venv' --exclude='.ruff_cache' --exclude='.pytest_cache' --exclude='.mypy_cache' --exclude='.coverage' --exclude='htmlcov' --exclude='logs' --exclude='coverage' --exclude='coverage.xml' --exclude='test-results' --exclude='tsconfig.tsbuildinfo' --exclude='.DS_Store' --exclude='infra/docker/uploads' apps infra thesica:/opt/thesica/
   ```
3. Службовий акаунт `control1` (пароль генерується на сервері, друкується один раз; зберегти в `~/.thesica/control1.env` як `CONTROL_LOGIN=control1`, `CONTROL_PASSWORD=…`, `CONTROL_USER_ID=…`, `chmod 600`):
   ```bash
   ssh thesica "docker exec ai-thesis-api python - <<'PY'
   import asyncio, secrets
   from sqlalchemy import select
   from app.core.database import AsyncSessionLocal
   from app.models.auth import User
   from app.services.auth_service import AuthService
   alphabet = 'abcdefghjkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789'
   password = ''.join(secrets.choice(alphabet) for _ in range(16))
   async def main():
       async with AsyncSessionLocal() as db:
           row = (await db.execute(select(User).where(User.email == 'control1'))).scalar_one_or_none()
           if row is None:
               row = User(email='control1', full_name='Control1', is_admin=False, preferred_language='it'); db.add(row)
           row.password_hash = AuthService.hash_password(password); row.is_active = True; row.is_verified = True
           await db.commit(); await db.refresh(row)
           print('control1 id=', row.id, 'password=', password)
   asyncio.run(main())
   PY"
   ```
4. Зняти денну квоту з `control1` (id з кроку 3, наприклад 7):
   ```bash
   ssh thesica "sed -i 's/^UNLIMITED_GENERATION_USER_IDS=\[1\]$/UNLIMITED_GENERATION_USER_IDS=[1,7]/' /etc/thesica/operator-bot/api.env && grep ^UNLIMITED /etc/thesica/operator-bot/api.env"
   ```
5. Реліз штатним скриптом (дамп бази, rollback-теги, міграції 024–027 без змін, збірка api+web, перевірка SDK, перезапуск, живі перевірки):
   ```bash
   ssh thesica 'bash /opt/thesica/infra/deploy.sh' 2>&1 | tee docs/evidence/RELEASE-2026-09-14-full-text/deploy.log
   ```
6. Перевірка після релізу: `docker exec ai-thesis-api sh -c 'test -f app/services/full_text_sources.py && wc -l app/services/executor_v2/*.py | tail -1'` (очікуємо файл є, 1 496 рядків); `env | grep ^UNLIMITED` у контейнері (очікуємо `[1,7]`); вхід `control1` через `POST /api/v1/auth/login`; парольний вхід manager1 не змінювався.
7. Штатний контроль через кабінет (той самий бриф B, 14 завантажених PDF):
   ```bash
   apps/api/venv/bin/python apps/api/scripts/cabinet_control.py docs/evidence/EXECUTOR-V2-THREE-CONTROLS-2026-09-12/B/brief.json OUT --uploads docs/evidence/QUALITY-AI-2026-09-13/step2-full-inputs/B/uploads/uploaded-sources-B-full.json
   ```
   (три сторонні PDF — HUDOC ×2 і EJPLT — покласти в ту саму теку під іменами зі специфікації).
8. Експорт повного запису й офлайн-відтворення — як у попередніх контролях (`export-recording.py` через `docker exec`, `scripts/replay_generation.py`), SHA DOCX з `result.docx.sha256` статусу job.

Відкат: команди, які друкує `deploy.sh` (теги `rollback-<stamp>`), і пакет `releases/pre-full-text-20260914`.

## Що потрібно, щоб я це виконала сама

Правило дозволу для цієї сесії Claude Code (налаштування проєкту `.claude/settings.local.json` → `permissions.allow`): `Bash(ssh thesica *)` і `Bash(rsync *)`; інакше — вимкнути автоматичний режим на час релізу або виконати команди 1–5 вручну і передати мені пароль `control1` файлом `~/.thesica/control1.env`.

## Релізний запис (заповнюється після виконання)

- дата, виконавець, підстава: 14.09.2026, Fable, «так» фаундера (вище);
- версія коду: `d15305a` (+ скрипт `cabinet_control.py`), доставлений пакет — контрольні суми з `--itemize-changes`;
- тести: API 1421/23/0, web 211/1/0, ruff чисто;
- бекап: `/opt/thesica/backups/pre-deploy-<stamp>.sql` (друкує скрипт);
- відкат: `rollback-<stamp>` теги + `releases/pre-full-text-20260914`;
- живі перевірки (§6 плану) — результат `deploy.log`;
- рішення про наступний контроль: після успішного релізу — крок 7.
