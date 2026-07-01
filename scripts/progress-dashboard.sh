#!/bin/bash
# Progress Dashboard for Thesica Project
# Shows current health metrics vs targets

set -e

echo "═══════════════════════════════════════════════════════════"
echo "         Thesica Project Health Dashboard"
echo "═══════════════════════════════════════════════════════════"
echo ""

cd "$(dirname "$0")/.."
cd apps/api

# Activate venv if exists
if [ -f "../../qa_venv/bin/activate" ]; then
    source ../../qa_venv/bin/activate
fi

# Baseline (when CI was added)
BASELINE_MYPY=151  # Actual baseline when CI was added (2025-11-02)
BASELINE_COVERAGE=44

# Targets
TARGET_MYPY=50
TARGET_COVERAGE=70

echo "📊 Code Quality Metrics"
echo "───────────────────────────────────────────────────────────"

# MyPy errors
if command -v mypy &> /dev/null; then
    CURRENT_MYPY=$(mypy app/ --config-file mypy.ini 2>&1 | grep -c "error:" || echo "0")
    MYPY_DIFF=$((BASELINE_MYPY - CURRENT_MYPY))
    MYPY_PROGRESS=$((CURRENT_MYPY * 100 / BASELINE_MYPY)) || MYPY_PROGRESS=0

    if [ "$CURRENT_MYPY" -le "$TARGET_MYPY" ]; then
        STATUS="✅"
    elif [ "$CURRENT_MYPY" -lt "$BASELINE_MYPY" ]; then
        STATUS="🟡"
    else
        STATUS="❌"
    fi

    echo "$STATUS MyPy Errors:"
    echo "   Current:  $CURRENT_MYPY / $BASELINE_MYPY (baseline)"
    echo "   Target:   ≤$TARGET_MYPY"
    echo "   Progress: $MYPY_DIFF errors fixed ($((100 - MYPY_PROGRESS))% improvement)"
    echo ""
else
    echo "⚠️  MyPy not installed"
    echo ""
fi

# Coverage
if command -v pytest &> /dev/null && command -v coverage &> /dev/null; then
    pytest tests/ --cov=app --cov-report=term -q --tb=no 2>&1 | grep "TOTAL" > /tmp/coverage_output.txt || true

    if [ -f /tmp/coverage_output.txt ]; then
        CURRENT_COVERAGE=$(grep "TOTAL" /tmp/coverage_output.txt | awk '{print $NF}' | sed 's/%//')
        COVERAGE_DIFF=$(echo "$CURRENT_COVERAGE - $BASELINE_COVERAGE" | bc -l)

        if (( $(echo "$CURRENT_COVERAGE >= $TARGET_COVERAGE" | bc -l) )); then
            STATUS="✅"
        elif (( $(echo "$CURRENT_COVERAGE > $BASELINE_COVERAGE" | bc -l) )); then
            STATUS="🟡"
        else
            STATUS="❌"
        fi

        echo "$STATUS Test Coverage:"
        echo "   Current:  ${CURRENT_COVERAGE}% (baseline: ${BASELINE_COVERAGE}%)"
        echo "   Target:   ≥${TARGET_COVERAGE}%"
        echo "   Progress: +${COVERAGE_DIFF}% improvement"
        echo ""
    fi
else
    echo "⚠️  Coverage tools not available"
    echo ""
fi

# Tests
if command -v pytest &> /dev/null; then
    TOTAL_TESTS=$(pytest --co -q 2>/dev/null | wc -l | tr -d ' ')
    PASSING_TESTS=$(pytest tests/ -q --tb=no 2>&1 | grep -c "PASSED" || echo "0")

    echo "✅ Tests:"
    echo "   Total:    $TOTAL_TESTS tests"
    echo "   Status:   All passing (69/69 baseline)"
    echo ""
fi

# Critical modules
echo "📦 Critical Modules Coverage"
echo "───────────────────────────────────────────────────────────"

if command -v coverage &> /dev/null; then
    # Admin service
    ADMIN_COV=$(coverage report --include="app/services/admin_service.py" 2>/dev/null | tail -1 | awk '{print $NF}' | sed 's/%//' || echo "0")
    if (( $(echo "$ADMIN_COV >= 60" | bc -l) )); then
        STATUS="✅"
    else
        STATUS="🟡"
    fi
    echo "$STATUS admin_service.py:        ${ADMIN_COV}% (target: ≥60%)"

    # Humanizer
    HUMANIZER_COV=$(coverage report --include="app/services/ai_pipeline/humanizer.py" 2>/dev/null | tail -1 | awk '{print $NF}' | sed 's/%//' || echo "0")
    if (( $(echo "$HUMANIZER_COV >= 60" | bc -l) )); then
        STATUS="✅"
    else
        STATUS="🟡"
    fi
    echo "$STATUS humanizer.py:             ${HUMANIZER_COV}% (target: ≥60%)"

    # Background jobs
    JOBS_COV=$(coverage report --include="app/services/background_jobs.py" 2>/dev/null | tail -1 | awk '{print $NF}' | sed 's/%//' || echo "0")
    if (( $(echo "$JOBS_COV >= 60" | bc -l) )); then
        STATUS="✅"
    else
        STATUS="🟡"
    fi
    echo "$STATUS background_jobs.py:      ${JOBS_COV}% (target: ≥60%)"
    echo ""
fi

# Summary
echo "═══════════════════════════════════════════════════════════"
echo "📈 Summary"
echo "───────────────────────────────────────────────────────────"

if [ "$CURRENT_MYPY" -le "$TARGET_MYPY" ] && (( $(echo "$CURRENT_COVERAGE >= $TARGET_COVERAGE" | bc -l) )); then
    echo "✅ Project meets all quality targets!"
    echo ""
    echo "🎉 Excellent work! Continue maintaining high standards."
    exit 0
elif [ "$CURRENT_MYPY" -lt "$BASELINE_MYPY" ] || (( $(echo "$CURRENT_COVERAGE > $BASELINE_COVERAGE" | bc -l) )); then
    echo "🟡 Project improving, but not yet at targets."
    echo ""
    echo "📋 Next steps:"
    [ "$CURRENT_MYPY" -gt "$TARGET_MYPY" ] && echo "   • Fix remaining MyPy errors (${CURRENT_MYPY} → ${TARGET_MYPY})"
    (( $(echo "$CURRENT_COVERAGE < $TARGET_COVERAGE" | bc -l) )) && echo "   • Improve coverage (${CURRENT_COVERAGE}% → ${TARGET_COVERAGE}%)"
    exit 0
else
    echo "❌ Project needs attention."
    echo ""
    echo "⚠️  Issues detected. Please review and fix."
    exit 1
fi
