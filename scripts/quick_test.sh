#!/bin/bash

# TesiGo Quick Smoke Test Runner
# Run this script to quickly verify the platform is working

echo "🚀 TesiGo Quick Smoke Test"
echo "======================================"
echo ""

# Check if services are running
echo "Checking services..."
WEB_STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:3000 2>&1)
API_STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/health 2>&1)

if [ "$WEB_STATUS" != "200" ]; then
    echo "❌ Web frontend is not running on port 3000"
    echo "   Start with: cd apps/web && npm run dev"
    exit 1
fi

if [ "$API_STATUS" != "200" ]; then
    echo "❌ Backend API is not running on port 8000"
    echo "   Start with: cd apps/api && uvicorn main:app --reload"
    exit 1
fi

echo "✅ Web frontend: Running"
echo "✅ Backend API: Running"
echo ""

# Run full smoke test
echo "Running comprehensive smoke test..."
echo ""

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
bash "$SCRIPT_DIR/ui_smoke_test.sh"

EXIT_CODE=$?

echo ""
echo "======================================"
if [ $EXIT_CODE -eq 0 ]; then
    echo "✅ All tests passed!"
    echo "   Platform is ready for use."
else
    echo "❌ Some tests failed."
    echo "   Check the report above for details."
fi

exit $EXIT_CODE
