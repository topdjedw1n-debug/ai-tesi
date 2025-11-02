#!/bin/bash
# Health Check Script for TesiGo Project
# Checks: Python version, tests, MyPy, coverage

set -e

echo "═══════════════════════════════════════════════════════════"
echo "           TesiGo Project Health Check"
echo "═══════════════════════════════════════════════════════════"
echo ""

cd "$(dirname "$0")/.."
cd apps/api

# Activate venv if exists
if [ -f "../../qa_venv/bin/activate" ]; then
    source ../../qa_venv/bin/activate
    echo "✅ Virtual environment activated"
else
    echo "⚠️  Virtual environment not found, using system Python"
fi

echo ""
echo "1️⃣  Python Version Check"
echo "───────────────────────────────────────────────────────────"
PYTHON_VERSION=$(python --version 2>&1)
echo "   $PYTHON_VERSION"

if python -c "import sys; exit(0 if sys.version_info >= (3, 11) else 1)" 2>/dev/null; then
    echo "   ✅ Python 3.11+ detected"
else
    echo "   ❌ Python 3.11+ required"
    exit 1
fi

echo ""
echo "2️⃣  Tests Status"
echo "───────────────────────────────────────────────────────────"
if command -v pytest &> /dev/null; then
    pytest tests/ -q --tb=no --maxfail=3 2>&1 | tail -3
    TEST_STATUS=${PIPESTATUS[0]}
    if [ $TEST_STATUS -eq 0 ]; then
        echo "   ✅ All tests passing"
    else
        echo "   ❌ Some tests failing"
    fi
else
    echo "   ⚠️  pytest not installed"
    TEST_STATUS=1
fi

echo ""
echo "3️⃣  MyPy Type Checking"
echo "───────────────────────────────────────────────────────────"
if command -v mypy &> /dev/null; then
    MYPY_OUTPUT=$(mypy app/ --config-file mypy.ini 2>&1 | tail -5)
    MYPY_ERRORS=$(mypy app/ --config-file mypy.ini 2>&1 | grep -c "error:" || echo "0")
    echo "$MYPY_OUTPUT"
    if [ "$MYPY_ERRORS" -eq 0 ]; then
        echo "   ✅ No MyPy errors"
    elif [ "$MYPY_ERRORS" -le 50 ]; then
        echo "   ⚠️  MyPy errors: $MYPY_ERRORS (within threshold)"
    else
        echo "   ❌ MyPy errors: $MYPY_ERRORS (exceeds threshold of 50)"
    fi
else
    echo "   ⚠️  mypy not installed"
    MYPY_ERRORS=999
fi

echo ""
echo "4️⃣  Coverage Status"
echo "───────────────────────────────────────────────────────────"
if command -v pytest &> /dev/null && command -v coverage &> /dev/null; then
    pytest tests/ --cov=app --cov-report=term-missing -q 2>&1 | grep "TOTAL" || echo "   ⚠️  Coverage not available"
else
    echo "   ⚠️  Coverage tools not available"
fi

echo ""
echo "5️⃣  Ruff Linting"
echo "───────────────────────────────────────────────────────────"
if command -v ruff &> /dev/null; then
    RUFF_OUTPUT=$(ruff check . 2>&1)
    RUFF_ERRORS=$(echo "$RUFF_OUTPUT" | grep -c "error\|Error" || echo "0")
    if [ "$RUFF_ERRORS" -eq 0 ]; then
        echo "   ✅ No Ruff errors"
    else
        echo "$RUFF_OUTPUT" | head -5
        echo "   ❌ Ruff errors found: $RUFF_ERRORS"
    fi
else
    echo "   ⚠️  ruff not installed"
fi

echo ""
echo "═══════════════════════════════════════════════════════════"

# Final status
if [ $TEST_STATUS -eq 0 ] && [ "$MYPY_ERRORS" -le 50 ]; then
    echo "✅ Project is HEALTHY"
    exit 0
else
    echo "❌ Project has ISSUES"
    exit 1
fi

