#!/bin/bash
# Run mypy type checking
# Usage: ./scripts/typecheck.sh

set -e

cd "$(dirname "$0")/../apps/api" || exit 1

# Create logs directory
mkdir -p ../../logs/tasks/full-verification

echo "Running mypy type checking..."
mypy app/ --config-file=mypy.ini --show-error-codes > ../../logs/tasks/full-verification/typecheck.txt 2>&1 || true

echo "Type checking complete. Results saved to logs/tasks/full-verification/typecheck.txt"
echo "Error count: $(grep -c "error:" ../../logs/tasks/full-verification/typecheck.txt || echo "0")"

