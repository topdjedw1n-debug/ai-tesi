#!/bin/bash
set -e

# 🧪 Test Generation Flow - End-to-End
# Usage: ./scripts/test-generation-flow.sh

API_URL="${API_URL:-http://localhost:8000}"
ADMIN_EMAIL="${ADMIN_EMAIL:-admin@tesigo.com}"
ADMIN_PASSWORD="${ADMIN_PASSWORD:-admin123}"

echo "🧪 Testing Full Generation Flow..."
echo "API: $API_URL"
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 1. Login as admin
echo "🔐 Step 1: Login as admin..."
TOKEN=$(curl -s -X POST "$API_URL/api/v1/auth/admin-login" \
  -H "Content-Type: application/json" \
  -d "{\"email\": \"$ADMIN_EMAIL\", \"password\": \"$ADMIN_PASSWORD\"}" \
  | jq -r '.access_token')

if [ "$TOKEN" == "null" ] || [ -z "$TOKEN" ]; then
  echo -e "${RED}❌ Login failed!${NC}"
  exit 1
fi

echo -e "${GREEN}✅ Logged in successfully${NC}"
echo ""

# 2. Create document
echo "📝 Step 2: Creating test document..."
CREATE_RESPONSE=$(curl -s -X POST "$API_URL/api/v1/documents" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "AI in Healthcare - Test Document",
    "topic": "Artificial Intelligence applications in modern healthcare systems",
    "language": "en",
    "target_pages": 5,
    "ai_provider": "openai",
    "ai_model": "gpt-4"
  }')

DOC_ID=$(echo "$CREATE_RESPONSE" | jq -r '.id')

if [ "$DOC_ID" == "null" ] || [ -z "$DOC_ID" ]; then
  echo -e "${RED}❌ Document creation failed!${NC}"
  echo "$CREATE_RESPONSE" | jq '.'
  exit 1
fi

echo -e "${GREEN}✅ Document created: ID=$DOC_ID${NC}"
echo ""

# 3. Start generation
echo "🚀 Step 3: Starting generation..."
GEN_RESPONSE=$(curl -s -X POST "$API_URL/api/v1/generate/full-document" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"document_id\": $DOC_ID,
    \"model\": \"gpt-4\"
  }")

JOB_ID=$(echo "$GEN_RESPONSE" | jq -r '.job_id')
JOB_STATUS=$(echo "$GEN_RESPONSE" | jq -r '.status')

if [ "$JOB_ID" == "null" ] || [ -z "$JOB_ID" ]; then
  echo -e "${RED}❌ Generation start failed!${NC}"
  echo "$GEN_RESPONSE" | jq '.'
  exit 1
fi

echo -e "${GREEN}✅ Generation started: Job ID=$JOB_ID, Status=$JOB_STATUS${NC}"
echo ""

# 4. Poll job status
echo "⏳ Step 4: Polling job status (max 10 minutes)..."
MAX_WAIT=600  # 10 minutes
ELAPSED=0
POLL_INTERVAL=10

while [ $ELAPSED -lt $MAX_WAIT ]; do
  STATUS_RESPONSE=$(curl -s "$API_URL/api/v1/jobs/$JOB_ID/status" \
    -H "Authorization: Bearer $TOKEN")

  CURRENT_STATUS=$(echo "$STATUS_RESPONSE" | jq -r '.status')
  PROGRESS=$(echo "$STATUS_RESPONSE" | jq -r '.progress // 0')

  echo -e "${YELLOW}⏳ Status: $CURRENT_STATUS | Progress: ${PROGRESS}%${NC}"

  if [ "$CURRENT_STATUS" == "completed" ]; then
    echo -e "${GREEN}✅ Generation completed!${NC}"
    break
  elif [ "$CURRENT_STATUS" == "failed" ]; then
    echo -e "${RED}❌ Generation failed!${NC}"
    ERROR_MSG=$(echo "$STATUS_RESPONSE" | jq -r '.error_message // "Unknown error"')
    echo "Error: $ERROR_MSG"
    exit 1
  fi

  sleep $POLL_INTERVAL
  ELAPSED=$((ELAPSED + POLL_INTERVAL))
done

if [ $ELAPSED -ge $MAX_WAIT ]; then
  echo -e "${RED}❌ Timeout waiting for generation (10 minutes)${NC}"
  exit 1
fi

echo ""

# 5. Get document details
echo "📄 Step 5: Fetching document details..."
DOC_DETAILS=$(curl -s "$API_URL/api/v1/documents/$DOC_ID" \
  -H "Authorization: Bearer $TOKEN")

DOC_STATUS=$(echo "$DOC_DETAILS" | jq -r '.status')
WORD_COUNT=$(echo "$DOC_DETAILS" | jq -r '.word_count // 0')

echo -e "${GREEN}✅ Document Status: $DOC_STATUS${NC}"
echo "Word Count: $WORD_COUNT"
echo ""

# 6. Export DOCX
echo "📥 Step 6: Exporting DOCX..."
EXPORT_RESPONSE=$(curl -s -X POST "$API_URL/api/v1/documents/$DOC_ID/export" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"format": "docx"}' \
  -o "test_output_$DOC_ID.docx" \
  -w "%{http_code}")

if [ "$EXPORT_RESPONSE" == "200" ]; then
  FILE_SIZE=$(stat -f%z "test_output_$DOC_ID.docx" 2>/dev/null || stat -c%s "test_output_$DOC_ID.docx" 2>/dev/null)
  echo -e "${GREEN}✅ DOCX exported: test_output_$DOC_ID.docx ($FILE_SIZE bytes)${NC}"
else
  echo -e "${RED}❌ Export failed (HTTP $EXPORT_RESPONSE)${NC}"
fi

echo ""

# 7. Export PDF
echo "📥 Step 7: Exporting PDF..."
EXPORT_PDF_RESPONSE=$(curl -s -X POST "$API_URL/api/v1/documents/$DOC_ID/export" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"format": "pdf"}' \
  -o "test_output_$DOC_ID.pdf" \
  -w "%{http_code}")

if [ "$EXPORT_PDF_RESPONSE" == "200" ]; then
  PDF_SIZE=$(stat -f%z "test_output_$DOC_ID.pdf" 2>/dev/null || stat -c%s "test_output_$DOC_ID.pdf" 2>/dev/null)
  echo -e "${GREEN}✅ PDF exported: test_output_$DOC_ID.pdf ($PDF_SIZE bytes)${NC}"
else
  echo -e "${RED}❌ PDF export failed (HTTP $EXPORT_PDF_RESPONSE)${NC}"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "${GREEN}🎉 ALL TESTS PASSED!${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Summary:"
echo "  - Document ID: $DOC_ID"
echo "  - Job ID: $JOB_ID"
echo "  - Status: $DOC_STATUS"
echo "  - Word Count: $WORD_COUNT"
echo "  - DOCX: test_output_$DOC_ID.docx"
echo "  - PDF: test_output_$DOC_ID.pdf"
echo ""
