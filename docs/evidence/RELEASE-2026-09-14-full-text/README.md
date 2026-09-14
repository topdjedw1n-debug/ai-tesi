# Реліз «повнотекстові докази» на app.thesica.co — підготовлено, чекає на дозвіл інструмента (14.09.2026)

**Підстава:** фаундер 14.09: «Окей, в тебе все так, працюй» у відповідь на пропозицію (а) реліз сьогоднішнього коду на сервер за планом розгортання, (б) службовий акаунт `control1` без денної квоти. Виконавець — Fable.

## Стан (14.09, 15:10)

Виконано з дозволом фаундера («Додаю тобі дозвіл»):
- крок 1 — попередній серверний пакет збережено: `/opt/thesica/releases/pre-full-text-20260914` (181 МБ, `apps` + `infra`);
- крок 2 — код доставлено: `rsync` перелічив рівно 18 файлів ([rsync-itemized.txt](rsync-itemized.txt): 9 змінених модулів API, `full_text_sources.py`, 6 скриптів, 3 тести; web без змін); SHA-256 `full_text_sources.py`, `executor_v2/sources.py`, `executor_v2/sections.py` на сервері збігаються з локальними (`0d84e96c…`, `4aec3b41…`, `5caebc35…`).

**Не виконано — інструмент відхиляє незалежно від дозволу в чаті:**
- крок 3 (акаунт `control1`) — створення облікових записів і введення паролів для мене заборонені правилами середовища (категорія «створення акаунтів»), фільтр повертає «Remote Shell Writes»;
- крок 5 (`deploy.sh`) — фільтр повертає «Production Deploy» навіть після доданого дозволу.

Живий сервер досі на образі від 12.09 (`IMAGE_OLD`, `full_text_sources.py` є на диску, але не в контейнері). Стан узгоджений: код доставлено, реліз не активовано; відкат доставки — `releases/pre-full-text-20260914`.

Що зробити фаундеру (5–10 хвилин, у терміналі на цьому Mac):
1. `ssh thesica 'bash /opt/thesica/infra/deploy.sh'` — реліз (крок 5), скрипт сам робить дамп, теги відкату, збірку, перевірки; вивід зберегти у `deploy.log` у цій теці.
2. Крок 3 — команда нижче (пароль друкується один раз); крок 4 — зняти квоту з нового id; потім `ssh thesica 'cd /opt/thesica/infra/docker && docker compose -p docker -f docker-compose.prod.yml -f docker-compose.operator-bot.yml up -d --no-deps api'`, щоб API підхопив env.
3. Передати мені доступ без пароля в чаті: файл `~/.thesica/control1.env` з рядком `CONTROL_REFRESH_TOKEN=…` (токен оновлення живе 7 днів; отримати: `curl -s -X POST https://app.thesica.co/api/v1/auth/login -H 'Content-Type: application/json' -d '{"username":"control1","password":"…"}'` → поле `refresh_token`), або `CONTROL_LOGIN=control1` і `CONTROL_PASSWORD=…` (тоді драйвер логіниться паролем сам). Драйвер — `apps/api/scripts/cabinet_control.py`.

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
