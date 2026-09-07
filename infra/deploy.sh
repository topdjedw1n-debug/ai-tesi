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
# Scope of this deploy: the code and literal release profile already copied to
# the server after rsync. The compose contract owns the manager-generation
# limits and quality gates, so server .env drift cannot silently change them.
set -euo pipefail

ROOT=/opt/thesica
COMPOSE_DIR="$ROOT/infra/docker"
COMPOSE_FILE=docker-compose.prod.yml
COMPOSE_ARGS=(-p docker -f "$COMPOSE_FILE")
# The installed operator gateway gets its credentials and private network from
# this overlay. Recreating API with the base file alone disconnects Tanya's bot.
if [ -f /etc/thesica/operator-bot/api.env ]; then
	COMPOSE_ARGS+=(-f docker-compose.operator-bot.yml)
elif docker inspect docker-operator-bot-1 >/dev/null 2>&1; then
	echo "СТОП: бот встановлено, але його API-конфігурація відсутня."
	exit 1
fi
STAMP=$(date +%Y%m%d-%H%M%S)
BACKUP_DIR="$ROOT/backups"
BACKUP="$BACKUP_DIR/pre-deploy-$STAMP.sql"

say() { printf '\n=== %s ===\n' "$1"; }

cd "$COMPOSE_DIR"
docker compose "${COMPOSE_ARGS[@]}" config --quiet

say "1/6 Резервна копія бази"
mkdir -p "$BACKUP_DIR"
docker exec ai-thesis-postgres sh -c 'pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB"' > "$BACKUP"
BACKUP_BYTES=$(wc -c < "$BACKUP")
# A fresh pilot database can have a complete SQL dump below 100 KB. Validate
# that pg_dump produced a non-trivial file and wrote its completion marker
# instead of guessing validity from a production-size threshold.
if [ "$BACKUP_BYTES" -lt 10000 ] || \
	! grep -q '^-- PostgreSQL database dump complete$' "$BACKUP"; then
	echo "СТОП: дамп неповний або підозріло малий ($BACKUP_BYTES байт). Деплой не продовжено."
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
docker compose "${COMPOSE_ARGS[@]}" build api web

echo "-> перевірка SDK у щойно зібраному API-образі"
if ! docker compose "${COMPOSE_ARGS[@]}" run --rm --no-deps --entrypoint python api -c \
	"from anthropic import AsyncAnthropic; import inspect, openai; from openai.resources.chat.completions import AsyncCompletions; assert hasattr(AsyncAnthropic(api_key='x'), 'messages'); assert 'max_completion_tokens' in inspect.signature(AsyncCompletions.create).parameters; print('sdk ok', openai.__version__)"; then
	echo "СТОП: новий API-образ не підтримує потрібний контракт Anthropic/OpenAI."
	echo "Чинні контейнери не перезапускались і продовжують працювати."
	exit 1
fi
echo "OK: SDK контракт"

say "5/6 Перезапуск"
docker compose "${COMPOSE_ARGS[@]}" up -d --no-deps api web
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
		echo "         docker compose ${COMPOSE_ARGS[*]} up -d --no-deps api web"
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

code=$(curl -sS -o /dev/null -w '%{http_code}' -m 15 -X POST \
	-H 'Authorization: Bearer x' \
	https://app.thesica.co/api/v1/documents/)
if [ "$code" = "401" ]; then
	printf '  OK   %-38s %s\n' "створення роботи доходить до API" "$code"
else
	printf '  ФЕЙЛ %-38s %s (очікували 401)\n' "створення роботи доходить до API" "$code"
	fail=1
fi

redirect_result=$(curl -sS -o /dev/null -w '%{http_code} %{redirect_url}' -m 15 -X POST \
	-H 'Authorization: Bearer x' \
	https://app.thesica.co/api/v1/documents)
read -r code location <<< "$redirect_result"
if [ "$code" = "307" ] && [[ "$location" == https://app.thesica.co/* ]]; then
	printf '  OK   %-38s %s %s\n' "редирект створення лишається HTTPS" "$code" "$location"
else
	printf '  ФЕЙЛ %-38s %s %s (очікували 307 і https://app.thesica.co/...)\n' \
		"редирект створення лишається HTTPS" "$code" "$location"
	fail=1
fi

echo
if [ "$fail" = 0 ]; then
	echo "ДЕПЛОЙ УСПІШНИЙ. Бекап: $BACKUP"
else
	echo "ДЕПЛОЙ ЗАВЕРШЕНО З ЗАУВАЖЕННЯМИ — перевір рядки ФЕЙЛ вище."
	echo "Відкат:  docker tag ai-thesis-api:rollback-$STAMP ai-thesis-api && \\"
	echo "         docker tag ai-thesis-web:rollback-$STAMP ai-thesis-web && \\"
	echo "         docker compose ${COMPOSE_ARGS[*]} up -d --no-deps api web"
	echo "База:    docker exec -i ai-thesis-postgres sh -c 'psql -U \"\$POSTGRES_USER\" -d \"\$POSTGRES_DB\"' < $BACKUP"
	exit 1
fi
