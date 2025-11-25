#!/bin/bash
# Run smoke tests with SECRET_KEY configured
# Usage: ./scripts/run-smoke-tests.sh

set -e

cd "$(dirname "$0")/.." || exit 1

# Set SECRET_KEY for tests (required by config validation)
export SECRET_KEY="${SECRET_KEY:-test-secret-key-min-32-chars-required-for-validation}"
export JWT_SECRET="${JWT_SECRET:-$SECRET_KEY}"
export DATABASE_URL="${DATABASE_URL:-postgresql+asyncpg://postgres:password@localhost:5432/ai_thesis_platform}"
export DISABLE_RATE_LIMIT="${DISABLE_RATE_LIMIT:-true}"  # Disable rate limiting for tests

echo "Running smoke tests with SECRET_KEY configured..."
echo "SECRET_KEY length: ${#SECRET_KEY}"

cd apps/api || exit 1

# Run pytest with smoke marker
pytest ../../tests/test_smoke.py -v --cov=app --cov-report=xml:../../coverage.xml --cov-report=term-missing

echo "Smoke tests complete. Coverage report: coverage.xml"
