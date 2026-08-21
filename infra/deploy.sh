#!/usr/bin/env bash
# Production deploy for app.thesica.co — run ON the server:
#
#     ssh thesica 'bash /opt/thesica/infra/deploy.sh'
#
# Order matters. The API image is built from a tree that expects migrations
# 024-027, so the schema is applied BEFORE the new containers start. The
# database is dumped first and the current images are tagged, so a failed
# deploy can be rolled back with the commands printed at the end.
#
# Scope of this deploy: the code that is already on the server after rsync.
# It deliberately does NOT change generation behaviour — METHODOLOGY_REQUIRED,
# free-generation limits and the source-pack preflight profile stay exactly as
# they are and are handled as a separate, verified step (docs/AGENT_SYNC.md §13).
set -euo pipefail

ROOT=/opt/thesica
COMPOSE_DIR="$ROOT/infra/docker"
COMPOSE_FILE=docker-compose.prod.yml
STAMP=$(date +%Y%m%d-%H%M%S)
BACKUP_DIR="$ROOT/backups"
BACKUP="$BACKUP_DIR/pre-deploy-$STAMP.sql"

say() { printf '\n=== %s ===\n' "$1"; }

cd "$COMPOSE_DIR"

say "1/6 Резервна копія бази"
mkdir -p "$BACKUP_DIR"
docker exec ai-thesis-postgres sh -c 'pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB"' > "$BACKUP"
BACKUP_BYTES=$(wc -c < "$BACKUP")
if [ "$BACKUP_BYTES" -lt 100000 ]; then
	echo "СТОП: дамп підозріло малий ($BACKUP_BYTES байт). Деплой не продовжено."
	exit 1
fi
echo "OK: $BACKUP ($BACKUP_BYTES байт)"

say "2/6 Мітка поточних образів для відкату"
docker tag ai-thesis-api "ai-thesis-api:rollback-$STAMP"
docker tag ai-thesis-web "ai-thesis-web:rollback-$STAMP"
echo "OK: rollback-$STAMP"

say "3/6 Міграції 024-027"
# Кожна міграція написана з IF NOT EXISTS, тож повторний запуск безпечний.
for f in "$ROOT"/apps/api/migrations/02[4-7]_*.sql; do
	echo "-> $(basename "$f")"
	docker exec -i ai-thesis-postgres \
		sh -c 'psql -v ON_ERROR_STOP=1 -q -U "$POSTGRES_USER" -d "$POSTGRES_DB"' < "$f"
done
echo "OK: схема оновлена"

say "4/6 Збірка образів"
docker compose -f "$COMPOSE_FILE" build api web

say "5/6 Перезапуск"
docker compose -f "$COMPOSE_FILE" up -d api web
for i in $(seq 1 30); do
	sleep 3
	if curl -fsS -o /dev/null http://127.0.0.1:8000/health; then
		echo "OK: API живий через $((i * 3))с"
		break
	fi
	if [ "$i" = 30 ]; then
		echo "СТОП: API не піднявся за 90с."
		echo "Логи:    docker logs ai-thesis-api --tail 50"
		echo "Відкат:  docker tag ai-thesis-api:rollback-$STAMP ai-thesis-api && \\"
		echo "         docker tag ai-thesis-web:rollback-$STAMP ai-thesis-web && \\"
		echo "         docker compose -f $COMPOSE_FILE up -d api web"
		exit 1
	fi
done

say "6/6 Перевірка живої системи"
fail=0
check() { # опис, url, очікуваний код
	code=$(curl -s -o /dev/null -w '%{http_code}' -m 15 "$2")
	if [ "$code" = "$3" ]; then
		printf '  OK   %-38s %s\n' "$1" "$code"
	else
		printf '  ФЕЙЛ %-38s %s (очікували %s)\n' "$1" "$code" "$3"
		fail=1
	fi
}
check "здоров'я API"            https://app.thesica.co/health 200
check "сторінка входу"          https://app.thesica.co/auth/login 200
check "кабінет"                 https://app.thesica.co/dashboard 200
check "сторінка реєстрації веде на вхід" https://app.thesica.co/auth/register 302
code=$(curl -s -o /dev/null -w '%{http_code}' -m 15 -X POST \
	-H 'Content-Type: application/json' -d '{"email":"deploy-check"}' \
	https://app.thesica.co/api/v1/auth/magic-link)
if [ "$code" = "403" ]; then
	printf '  OK   %-38s %s\n' "самореєстрація заблокована" "$code"
else
	printf '  ФЕЙЛ %-38s %s (очікували 403)\n' "самореєстрація заблокована" "$code"
	fail=1
fi

echo
if [ "$fail" = 0 ]; then
	echo "ДЕПЛОЙ УСПІШНИЙ. Бекап: $BACKUP"
else
	echo "ДЕПЛОЙ ЗАВЕРШЕНО З ЗАУВАЖЕННЯМИ — перевір рядки ФЕЙЛ вище."
	echo "Відкат:  docker tag ai-thesis-api:rollback-$STAMP ai-thesis-api && \\"
	echo "         docker tag ai-thesis-web:rollback-$STAMP ai-thesis-web && \\"
	echo "         docker compose -f $COMPOSE_FILE up -d api web"
	echo "База:    docker exec -i ai-thesis-postgres sh -c 'psql -U \"\$POSTGRES_USER\" -d \"\$POSTGRES_DB\"' < $BACKUP"
fi
