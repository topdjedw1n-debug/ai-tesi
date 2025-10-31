#!/bin/bash
# Generate OpenAPI schema baseline
# Usage: ./scripts/generate-openapi.sh

set -e

cd "$(dirname "$0")/.." || exit 1

# Set SECRET_KEY for app initialization
export SECRET_KEY="${SECRET_KEY:-test-secret-key-min-32-chars-required-for-validation}"
export JWT_SECRET="${JWT_SECRET:-$SECRET_KEY}"

echo "Generating OpenAPI schema..."

cd apps/api || exit 1

# Create logs directory
mkdir -p ../../logs/tasks/full-verification

# Generate OpenAPI JSON using uvicorn or direct app export
python3 -c "
import json
import os
os.environ['SECRET_KEY'] = os.getenv('SECRET_KEY', 'test-secret-key-min-32-chars-required-for-validation')
os.environ['JWT_SECRET'] = os.getenv('JWT_SECRET', os.environ['SECRET_KEY'])

from main import app

openapi_schema = app.openapi()
with open('../../logs/tasks/full-verification/openapi_baseline.json', 'w') as f:
    json.dump(openapi_schema, f, indent=2)

print('OpenAPI schema saved to logs/tasks/full-verification/openapi_baseline.json')
"

# Generate API diff (placeholder, will compare against baseline in future runs)
echo "# API Diff Report" > ../../logs/tasks/full-verification/apidiff.txt
echo "Baseline OpenAPI schema generated at: $(date)" >> ../../logs/tasks/full-verification/apidiff.txt
echo "" >> ../../logs/tasks/full-verification/apidiff.txt
echo "Compare future schema changes against baseline:" >> ../../logs/tasks/full-verification/apidiff.txt
echo "  diff logs/tasks/full-verification/openapi_baseline.json <new_schema>" >> ../../logs/tasks/full-verification/apidiff.txt

echo "OpenAPI generation complete. Baseline saved."

