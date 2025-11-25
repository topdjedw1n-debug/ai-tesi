#!/bin/bash
# Dependency vulnerability scanning for Node.js (npm)
# Scans package.json and outputs report to logs/npm-vulnerability-report.json

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
WEB_DIR="$PROJECT_ROOT/apps/web"
LOGS_DIR="$PROJECT_ROOT/logs"

# Create logs directory if it doesn't exist
mkdir -p "$LOGS_DIR"

echo "Running npm dependency vulnerability scan..."
echo "Timestamp: $(date -u +"%Y-%m-%d %H:%M:%S UTC")" > "$LOGS_DIR/npm-vulnerability-report.json"

cd "$WEB_DIR"

# Check if npm is available
if ! command -v npm &> /dev/null; then
    echo "ERROR: npm is not installed or not in PATH"
    exit 1
fi

# Run npm audit
echo "Running npm audit..."
npm audit --audit-level=moderate --json >> "$LOGS_DIR/npm-vulnerability-report.json" 2>&1 || true

echo ""
echo "npm audit complete. Report saved to: $LOGS_DIR/npm-vulnerability-report.json"

# Also output summary
echo ""
echo "Summary:"
npm audit --audit-level=moderate 2>&1 | head -20 || true
