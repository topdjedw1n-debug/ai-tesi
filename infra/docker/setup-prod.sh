#!/usr/bin/env bash
set -euo pipefail

# Generate a strong secret key if not provided
if [[ -z "${SECRET_KEY:-}" ]]; then
  export SECRET_KEY=$(python -c 'import secrets; print(secrets.token_urlsafe(48))')
  echo "Generated SECRET_KEY"
fi

echo "Starting production stack..."
docker compose -f docker-compose.prod.yml up -d --build

echo "Stack started."
