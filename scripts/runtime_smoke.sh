#!/usr/bin/env bash

set -euo pipefail

API_URL="${API_URL:-http://localhost:8000}"
WEB_URL="${WEB_URL:-http://localhost:3000}"

pass() {
  echo "✅ $1"
}

fail() {
  echo "❌ $1"
  exit 1
}

check_status() {
  local name="$1"
  local url="$2"
  local expected="$3"

  local status
  status=$(curl -s -o /dev/null -w "%{http_code}" "$url" || true)
  if [[ -z "$status" ]]; then
    status="000"
  fi

  if [[ "$status" == "$expected" ]]; then
    pass "$name ($url) -> $status"
  else
    fail "$name ($url) expected $expected got $status"
  fi
}

check_not_404_405() {
  local name="$1"
  local method="$2"
  local url="$3"
  local auth_header="${4:-}"
  local body="${5:-}"

  local status
  if [[ -n "$auth_header" && -n "$body" ]]; then
    status=$(curl -s -o /dev/null -w "%{http_code}" \
      -X "$method" \
      -H "$auth_header" \
      -H "Content-Type: application/json" \
      -d "$body" \
      "$url" || true)
  elif [[ -n "$auth_header" ]]; then
    status=$(curl -s -o /dev/null -w "%{http_code}" \
      -X "$method" \
      -H "$auth_header" \
      "$url" || true)
  else
    status=$(curl -s -o /dev/null -w "%{http_code}" -X "$method" "$url" || true)
  fi

  if [[ -z "$status" ]]; then
    status="000"
  fi

  if [[ "$status" == "404" || "$status" == "405" ]]; then
    fail "$name ($method $url) returned $status (contract mismatch)"
  fi

  pass "$name ($method $url) -> $status"
}

echo "Running runtime smoke checks..."
echo "API_URL=$API_URL"
echo "WEB_URL=$WEB_URL"

# Required health checks
check_status "API health" "$API_URL/health" "200"
check_status "Web health" "$WEB_URL/api/health" "200"

# Optional authenticated smoke checks (requires tokens)
if [[ -n "${USER_BEARER_TOKEN:-}" ]]; then
  status=$(curl -s -o /dev/null -w "%{http_code}" \
    -H "Authorization: Bearer $USER_BEARER_TOKEN" \
    "$API_URL/api/v1/auth/me")
  if [[ "$status" == "200" ]]; then
    pass "User auth smoke (/api/v1/auth/me)"
  else
    fail "User auth smoke expected 200 got $status"
  fi
else
  echo "⚠️ Skipping user auth smoke (USER_BEARER_TOKEN not set)"
fi

if [[ -n "${ADMIN_BEARER_TOKEN:-}" ]]; then
  status=$(curl -s -o /dev/null -w "%{http_code}" \
    -H "Authorization: Bearer $ADMIN_BEARER_TOKEN" \
    "$API_URL/api/v1/admin/stats")
  if [[ "$status" == "200" ]]; then
    pass "Admin auth smoke (/api/v1/admin/stats)"
  else
    fail "Admin auth smoke expected 200 got $status"
  fi
else
  echo "⚠️ Skipping admin auth smoke (ADMIN_BEARER_TOKEN not set)"
fi

# Contract smoke checks (routes exist and method is accepted)
if [[ -n "${USER_BEARER_TOKEN:-}" ]]; then
  check_not_404_405 \
    "Generate full-document contract" \
    "POST" \
    "$API_URL/api/v1/generate/full-document" \
    "Authorization: Bearer $USER_BEARER_TOKEN" \
    "{}"

  check_not_404_405 \
    "Payment history contract" \
    "GET" \
    "$API_URL/api/v1/payment/history" \
    "Authorization: Bearer $USER_BEARER_TOKEN"

  check_not_404_405 \
    "Refund list contract" \
    "GET" \
    "$API_URL/api/v1/refunds" \
    "Authorization: Bearer $USER_BEARER_TOKEN"
else
  echo "⚠️ Skipping user contract smoke (USER_BEARER_TOKEN not set)"
fi

if [[ -n "${ADMIN_BEARER_TOKEN:-}" ]]; then
  check_not_404_405 \
    "Admin block contract" \
    "PUT" \
    "$API_URL/api/v1/admin/users/999999/block" \
    "Authorization: Bearer $ADMIN_BEARER_TOKEN" \
    '{"reason":"runtime smoke"}'

  check_not_404_405 \
    "Admin unblock contract" \
    "PUT" \
    "$API_URL/api/v1/admin/users/999999/unblock" \
    "Authorization: Bearer $ADMIN_BEARER_TOKEN"

  check_not_404_405 \
    "Admin make-admin contract" \
    "POST" \
    "$API_URL/api/v1/admin/users/999999/make-admin" \
    "Authorization: Bearer $ADMIN_BEARER_TOKEN" \
    '{"is_admin":true,"is_super_admin":false}'

  check_not_404_405 \
    "Admin logout contract" \
    "POST" \
    "$API_URL/api/v1/admin/auth/logout" \
    "Authorization: Bearer $ADMIN_BEARER_TOKEN"
else
  echo "⚠️ Skipping admin contract smoke (ADMIN_BEARER_TOKEN not set)"
fi

echo "Runtime smoke checks finished."
