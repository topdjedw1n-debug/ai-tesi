#!/bin/bash
# Dependency vulnerability scanning for Python (pip)
# Scans requirements.txt and outputs report to logs/vulnerability-report.txt

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
API_DIR="$PROJECT_ROOT/apps/api"
LOGS_DIR="$PROJECT_ROOT/logs"

# Create logs directory if it doesn't exist
mkdir -p "$LOGS_DIR"

echo "Running Python dependency vulnerability scan..."
echo "Timestamp: $(date -u +"%Y-%m-%d %H:%M:%S UTC")" > "$LOGS_DIR/vulnerability-report.txt"
echo "========================================" >> "$LOGS_DIR/vulnerability-report.txt"
echo "" >> "$LOGS_DIR/vulnerability-report.txt"

cd "$API_DIR"

# Check if safety is installed
if ! command -v safety &> /dev/null; then
    echo "Installing safety..."
    pip install safety || {
        echo "ERROR: Failed to install safety. Please install manually: pip install safety"
        exit 1
    }
fi

# Run safety check
echo "Running safety check on requirements.txt..."
safety check -r requirements.txt --json >> "$LOGS_DIR/vulnerability-report.txt" 2>&1 || true

# Run pip-audit if available
if command -v pip-audit &> /dev/null; then
    echo "" >> "$LOGS_DIR/vulnerability-report.txt"
    echo "========================================" >> "$LOGS_DIR/vulnerability-report.txt"
    echo "pip-audit results:" >> "$LOGS_DIR/vulnerability-report.txt"
    echo "========================================" >> "$LOGS_DIR/vulnerability-report.txt"
    pip-audit -r requirements.txt --format json >> "$LOGS_DIR/vulnerability-report.txt" 2>&1 || true
else
    echo "" >> "$LOGS_DIR/vulnerability-report.txt"
    echo "Note: pip-audit not installed. Install with: pip install pip-audit" >> "$LOGS_DIR/vulnerability-report.txt"
fi

echo ""
echo "Vulnerability scan complete. Report saved to: $LOGS_DIR/vulnerability-report.txt"
cat "$LOGS_DIR/vulnerability-report.txt"
