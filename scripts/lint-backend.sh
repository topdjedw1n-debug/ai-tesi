#!/bin/bash
# Backend linting script
# Usage: ./scripts/lint-backend.sh

set -e

cd "$(dirname "$0")/../apps/api" || exit 1

# Create logs directory
mkdir -p ../../logs/tasks/full-verification

echo "Running ruff check..."
ruff check app/ --output-format=text > ../../logs/tasks/full-verification/lint.txt 2>&1 || true

echo "Running ruff format check..."
ruff format --check app/ >> ../../logs/tasks/full-verification/lint.txt 2>&1 || true

echo "Running black check..."
black --check app/ >> ../../logs/tasks/full-verification/lint.txt 2>&1 || true

echo "Running isort check..."
isort --check-only app/ >> ../../logs/tasks/full-verification/lint.txt 2>&1 || true

echo "Linting complete. Results saved to logs/tasks/full-verification/lint.txt"

