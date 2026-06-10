#!/bin/bash

# TesiGo Manual UI Smoke Test - API Backend Verification
# This script tests all backend endpoints that power the UI scenarios

# Don't exit on errors - we want to test everything
set +e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

API_BASE="http://localhost:8000"
WEB_BASE="http://localhost:3000"

# Counters
PASS_COUNT=0
FAIL_COUNT=0
BLOCKED_COUNT=0

# Test results storage
REPORT_FILE="/tmp/tesigo_smoke_test_$(date +%Y%m%d_%H%M%S).txt"

log_test() {
    echo -e "${BLUE}[TEST]${NC} $1" | tee -a "$REPORT_FILE"
}

log_pass() {
    echo -e "${GREEN}[PASS]${NC} $1" | tee -a "$REPORT_FILE"
    ((PASS_COUNT++))
}

log_fail() {
    echo -e "${RED}[FAIL]${NC} $1" | tee -a "$REPORT_FILE"
    ((FAIL_COUNT++))
}

log_blocked() {
    echo -e "${YELLOW}[BLOCKED]${NC} $1" | tee -a "$REPORT_FILE"
    ((BLOCKED_COUNT++))
}

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1" | tee -a "$REPORT_FILE"
}

echo "========================================" | tee "$REPORT_FILE"
echo "TesiGo Pre-Production Smoke Test Report" | tee -a "$REPORT_FILE"
echo "Date: $(date)" | tee -a "$REPORT_FILE"
echo "========================================" | tee -a "$REPORT_FILE"
echo "" | tee -a "$REPORT_FILE"

# Store cookies and tokens
COOKIE_JAR="/tmp/tesigo_cookies.txt"
rm -f "$COOKIE_JAR"

# ============================================
# SCENARIO 1: Home Page / Landing
# ============================================
log_test "SCENARIO 1: Home Page / Landing"
log_info "URL: $WEB_BASE"

HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$WEB_BASE")
log_info "HTTP Status: $HTTP_CODE"

if [ "$HTTP_CODE" = "200" ]; then
    log_pass "Home page loads successfully"
else
    log_fail "Home page returned $HTTP_CODE (expected 200)"
fi
echo "" | tee -a "$REPORT_FILE"

# ============================================
# SCENARIO 2: API Health Check
# ============================================
log_test "SCENARIO 2: API Health Check"
log_info "URL: $API_BASE/health"

HEALTH_RESPONSE=$(curl -s "$API_BASE/health")
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$API_BASE/health")
log_info "HTTP Status: $HTTP_CODE"
log_info "Response: $HEALTH_RESPONSE"

if [ "$HTTP_CODE" = "200" ] && echo "$HEALTH_RESPONSE" | grep -q "healthy"; then
    log_pass "API health check successful"
else
    log_fail "API health check failed"
fi
echo "" | tee -a "$REPORT_FILE"

# ============================================
# SCENARIO 3: Admin Login (Simple Auth for Testing)
# ============================================
log_test "SCENARIO 3: Admin Login (Simple Auth)"
log_info "URL: POST $API_BASE/api/v1/auth/admin-login"
log_info "Credentials: admin@tesigo.com / admin123"

LOGIN_RESPONSE=$(curl -s -c "$COOKIE_JAR" -X POST "$API_BASE/api/v1/auth/admin-login" \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@tesigo.com","password":"admin123"}' \
  -w "\nHTTP_CODE:%{http_code}")

HTTP_CODE=$(echo "$LOGIN_RESPONSE" | grep "HTTP_CODE:" | cut -d':' -f2)
RESPONSE_BODY=$(echo "$LOGIN_RESPONSE" | sed '/HTTP_CODE:/d')

log_info "HTTP Status: $HTTP_CODE"
log_info "Response: $RESPONSE_BODY"

if [ "$HTTP_CODE" = "200" ]; then
    ADMIN_TOKEN=$(echo "$RESPONSE_BODY" | grep -o '"access_token":"[^"]*"' | cut -d'"' -f4)
    if [ -n "$ADMIN_TOKEN" ]; then
        log_pass "Admin login successful, token received"
        log_info "Token: ${ADMIN_TOKEN:0:20}..."
    else
        log_fail "Admin login returned 200 but no token found"
    fi
else
    log_fail "Admin login failed with HTTP $HTTP_CODE"
fi
echo "" | tee -a "$REPORT_FILE"

# ============================================
# SCENARIO 4: Magic Link Token Verification
# ============================================
log_test "SCENARIO 4: Magic Link Token Verification (testuser)"
log_info "URL: POST $API_BASE/api/v1/auth/verify-magic-link"
log_info "Token: cJ7GrTuMqnIjDjAkWy13ABZ9gNrNuQRLBchGI5S6Zng"

MAGIC_RESPONSE=$(curl -s -X POST "$API_BASE/api/v1/auth/verify-magic-link" \
  -H "Content-Type: application/json" \
  -d '{"token":"cJ7GrTuMqnIjDjAkWy13ABZ9gNrNuQRLBchGI5S6Zng"}' \
  -w "\nHTTP_CODE:%{http_code}")

HTTP_CODE=$(echo "$MAGIC_RESPONSE" | grep "HTTP_CODE:" | cut -d':' -f2)
RESPONSE_BODY=$(echo "$MAGIC_RESPONSE" | sed '/HTTP_CODE:/d')

log_info "HTTP Status: $HTTP_CODE"
log_info "Response: $RESPONSE_BODY"

if [ "$HTTP_CODE" = "200" ]; then
    USER_TOKEN=$(echo "$RESPONSE_BODY" | grep -o '"access_token":"[^"]*"' | cut -d'"' -f4)
    if [ -n "$USER_TOKEN" ]; then
        log_pass "Magic link verification successful"
    else
        log_fail "Magic link returned 200 but no token"
    fi
elif [ "$HTTP_CODE" = "401" ] || [ "$HTTP_CODE" = "400" ]; then
    log_info "Token expired or invalid (expected for old tokens)"
    log_blocked "Cannot test user flows without valid magic link token"
    USER_TOKEN=""
else
    log_fail "Magic link verification failed with HTTP $HTTP_CODE"
    USER_TOKEN=""
fi
echo "" | tee -a "$REPORT_FILE"

# ============================================
# SCENARIO 5: Admin Dashboard Stats
# ============================================
if [ -n "$ADMIN_TOKEN" ]; then
    log_test "SCENARIO 5: Admin Dashboard Stats"
    log_info "URL: GET $API_BASE/api/v1/admin/stats"

    STATS_RESPONSE=$(curl -s -X GET "$API_BASE/api/v1/admin/stats" \
      -H "Authorization: Bearer $ADMIN_TOKEN" \
      -w "\nHTTP_CODE:%{http_code}")

    HTTP_CODE=$(echo "$STATS_RESPONSE" | grep "HTTP_CODE:" | cut -d':' -f2)
    RESPONSE_BODY=$(echo "$STATS_RESPONSE" | sed '/HTTP_CODE:/d')

    log_info "HTTP Status: $HTTP_CODE"
    log_info "Response: $RESPONSE_BODY"

    if [ "$HTTP_CODE" = "200" ]; then
        log_pass "Admin stats retrieved successfully"
    elif [ "$HTTP_CODE" = "404" ]; then
        log_fail "Admin stats endpoint not found (404)"
    else
        log_fail "Admin stats failed with HTTP $HTTP_CODE"
    fi
else
    log_blocked "SCENARIO 5: Admin Dashboard Stats - No admin token"
fi
echo "" | tee -a "$REPORT_FILE"

# ============================================
# SCENARIO 6: Admin Users List
# ============================================
if [ -n "$ADMIN_TOKEN" ]; then
    log_test "SCENARIO 6: Admin Users List"
    log_info "URL: GET $API_BASE/api/v1/admin/users"

    USERS_RESPONSE=$(curl -s -X GET "$API_BASE/api/v1/admin/users" \
      -H "Authorization: Bearer $ADMIN_TOKEN" \
      -w "\nHTTP_CODE:%{http_code}")

    HTTP_CODE=$(echo "$USERS_RESPONSE" | grep "HTTP_CODE:" | cut -d':' -f2)
    RESPONSE_BODY=$(echo "$USERS_RESPONSE" | sed '/HTTP_CODE:/d')

    log_info "HTTP Status: $HTTP_CODE"

    if [ "$HTTP_CODE" = "200" ]; then
        USER_COUNT=$(echo "$RESPONSE_BODY" | grep -o '"email"' | wc -l | tr -d ' ')
        log_info "Users found: $USER_COUNT"
        log_pass "Admin users list retrieved successfully"

        # Find testuser ID for later tests
        TESTUSER_ID=$(echo "$RESPONSE_BODY" | grep -o '"id":[0-9]*,"email":"testuser@tesigo.com"' | grep -o '[0-9]*' | head -1)
        if [ -n "$TESTUSER_ID" ]; then
            log_info "Found testuser@tesigo.com with ID: $TESTUSER_ID"
        fi
    else
        log_fail "Admin users list failed with HTTP $HTTP_CODE"
    fi
else
    log_blocked "SCENARIO 6: Admin Users List - No admin token"
fi
echo "" | tee -a "$REPORT_FILE"

# ============================================
# SCENARIO 7: Admin Block User
# ============================================
if [ -n "$ADMIN_TOKEN" ] && [ -n "$TESTUSER_ID" ]; then
    log_test "SCENARIO 7: Admin Block User"
    log_info "URL: PUT $API_BASE/api/v1/admin/users/$TESTUSER_ID/block"

    BLOCK_RESPONSE=$(curl -s -X PUT "$API_BASE/api/v1/admin/users/$TESTUSER_ID/block" \
      -H "Authorization: Bearer $ADMIN_TOKEN" \
      -H "Content-Type: application/json" \
      -d '{"reason":"Testing block functionality"}' \
      -w "\nHTTP_CODE:%{http_code}")

    HTTP_CODE=$(echo "$BLOCK_RESPONSE" | grep "HTTP_CODE:" | cut -d':' -f2)
    RESPONSE_BODY=$(echo "$BLOCK_RESPONSE" | sed '/HTTP_CODE:/d')

    log_info "HTTP Status: $HTTP_CODE"
    log_info "Response: $RESPONSE_BODY"

    if [ "$HTTP_CODE" = "200" ]; then
        log_pass "User blocked successfully"
    else
        log_fail "Block user failed with HTTP $HTTP_CODE"
    fi
else
    log_blocked "SCENARIO 7: Admin Block User - No admin token or testuser ID"
fi
echo "" | tee -a "$REPORT_FILE"

# ============================================
# SCENARIO 8: Admin Unblock User
# ============================================
if [ -n "$ADMIN_TOKEN" ] && [ -n "$TESTUSER_ID" ]; then
    log_test "SCENARIO 8: Admin Unblock User"
    log_info "URL: PUT $API_BASE/api/v1/admin/users/$TESTUSER_ID/unblock"

    UNBLOCK_RESPONSE=$(curl -s -X PUT "$API_BASE/api/v1/admin/users/$TESTUSER_ID/unblock" \
      -H "Authorization: Bearer $ADMIN_TOKEN" \
      -w "\nHTTP_CODE:%{http_code}")

    HTTP_CODE=$(echo "$UNBLOCK_RESPONSE" | grep "HTTP_CODE:" | cut -d':' -f2)
    RESPONSE_BODY=$(echo "$UNBLOCK_RESPONSE" | sed '/HTTP_CODE:/d')

    log_info "HTTP Status: $HTTP_CODE"
    log_info "Response: $RESPONSE_BODY"

    if [ "$HTTP_CODE" = "200" ]; then
        log_pass "User unblocked successfully"
    else
        log_fail "Unblock user failed with HTTP $HTTP_CODE"
    fi
else
    log_blocked "SCENARIO 8: Admin Unblock User - No admin token or testuser ID"
fi
echo "" | tee -a "$REPORT_FILE"

# ============================================
# SCENARIO 9: Admin Make Admin
# ============================================
if [ -n "$ADMIN_TOKEN" ] && [ -n "$TESTUSER_ID" ]; then
    log_test "SCENARIO 9: Admin Make Admin (Grant Admin Role)"
    log_info "URL: POST $API_BASE/api/v1/admin/users/$TESTUSER_ID/make-admin"

    MAKEADMIN_RESPONSE=$(curl -s -X POST "$API_BASE/api/v1/admin/users/$TESTUSER_ID/make-admin" \
      -H "Authorization: Bearer $ADMIN_TOKEN" \
      -H "Content-Type: application/json" \
      -d '{"is_admin":true,"is_super_admin":false}' \
      -w "\nHTTP_CODE:%{http_code}")

    HTTP_CODE=$(echo "$MAKEADMIN_RESPONSE" | grep "HTTP_CODE:" | cut -d':' -f2)
    RESPONSE_BODY=$(echo "$MAKEADMIN_RESPONSE" | sed '/HTTP_CODE:/d')

    log_info "HTTP Status: $HTTP_CODE"
    log_info "Response: $RESPONSE_BODY"

    if [ "$HTTP_CODE" = "200" ]; then
        log_pass "User promoted to admin successfully"
    else
        log_fail "Make admin failed with HTTP $HTTP_CODE"
    fi
else
    log_blocked "SCENARIO 9: Admin Make Admin - No admin token or testuser ID"
fi
echo "" | tee -a "$REPORT_FILE"

# ============================================
# SCENARIO 10: Payment History (requires auth)
# ============================================
if [ -n "$USER_TOKEN" ]; then
    log_test "SCENARIO 10: User Payment History"
    log_info "URL: GET $API_BASE/api/v1/payment/history"

    PAYMENT_RESPONSE=$(curl -s -X GET "$API_BASE/api/v1/payment/history" \
      -H "Authorization: Bearer $USER_TOKEN" \
      -w "\nHTTP_CODE:%{http_code}")

    HTTP_CODE=$(echo "$PAYMENT_RESPONSE" | grep "HTTP_CODE:" | cut -d':' -f2)
    RESPONSE_BODY=$(echo "$PAYMENT_RESPONSE" | sed '/HTTP_CODE:/d')

    log_info "HTTP Status: $HTTP_CODE"

    if [ "$HTTP_CODE" = "200" ]; then
        log_pass "Payment history retrieved successfully"
        log_info "Response: $RESPONSE_BODY"
    elif [ "$HTTP_CODE" = "404" ]; then
        log_fail "Payment history endpoint not found (404)"
    else
        log_fail "Payment history failed with HTTP $HTTP_CODE"
    fi
elif [ -n "$ADMIN_TOKEN" ]; then
    log_test "SCENARIO 10: Payment History (using admin token)"
    log_info "URL: GET $API_BASE/api/v1/payment/history"

    PAYMENT_RESPONSE=$(curl -s -X GET "$API_BASE/api/v1/payment/history" \
      -H "Authorization: Bearer $ADMIN_TOKEN" \
      -w "\nHTTP_CODE:%{http_code}")

    HTTP_CODE=$(echo "$PAYMENT_RESPONSE" | grep "HTTP_CODE:" | cut -d':' -f2)
    RESPONSE_BODY=$(echo "$PAYMENT_RESPONSE" | sed '/HTTP_CODE:/d')

    log_info "HTTP Status: $HTTP_CODE"
    log_info "Response: $RESPONSE_BODY"

    if [ "$HTTP_CODE" = "200" ]; then
        log_pass "Payment history retrieved successfully"
    elif [ "$HTTP_CODE" = "404" ]; then
        log_fail "Payment history endpoint not found (404)"
    else
        log_fail "Payment history failed with HTTP $HTTP_CODE"
    fi
else
    log_blocked "SCENARIO 10: Payment History - No auth token"
fi
echo "" | tee -a "$REPORT_FILE"

# ============================================
# SCENARIO 11: Refunds List
# ============================================
if [ -n "$USER_TOKEN" ]; then
    log_test "SCENARIO 11: User Refunds List"
    log_info "URL: GET $API_BASE/api/v1/refunds"

    REFUNDS_RESPONSE=$(curl -s -X GET "$API_BASE/api/v1/refunds" \
      -H "Authorization: Bearer $USER_TOKEN" \
      -w "\nHTTP_CODE:%{http_code}")

    HTTP_CODE=$(echo "$REFUNDS_RESPONSE" | grep "HTTP_CODE:" | cut -d':' -f2)
    RESPONSE_BODY=$(echo "$REFUNDS_RESPONSE" | sed '/HTTP_CODE:/d')

    log_info "HTTP Status: $HTTP_CODE"

    if [ "$HTTP_CODE" = "200" ]; then
        log_pass "Refunds list retrieved successfully"
        log_info "Response: $RESPONSE_BODY"
    elif [ "$HTTP_CODE" = "404" ]; then
        log_fail "Refunds endpoint not found (404)"
    else
        log_fail "Refunds list failed with HTTP $HTTP_CODE"
    fi
elif [ -n "$ADMIN_TOKEN" ]; then
    log_test "SCENARIO 11: Refunds List (using admin token)"
    log_info "URL: GET $API_BASE/api/v1/refunds"

    REFUNDS_RESPONSE=$(curl -s -X GET "$API_BASE/api/v1/refunds" \
      -H "Authorization: Bearer $ADMIN_TOKEN" \
      -w "\nHTTP_CODE:%{http_code}")

    HTTP_CODE=$(echo "$REFUNDS_RESPONSE" | grep "HTTP_CODE:" | cut -d':' -f2)
    RESPONSE_BODY=$(echo "$REFUNDS_RESPONSE" | sed '/HTTP_CODE:/d')

    log_info "HTTP Status: $HTTP_CODE"
    log_info "Response: $RESPONSE_BODY"

    if [ "$HTTP_CODE" = "200" ]; then
        log_pass "Refunds list retrieved successfully"
    elif [ "$HTTP_CODE" = "404" ]; then
        log_fail "Refunds endpoint not found (404)"
    else
        log_fail "Refunds list failed with HTTP $HTTP_CODE"
    fi
else
    log_blocked "SCENARIO 11: Refunds List - No auth token"
fi
echo "" | tee -a "$REPORT_FILE"

# ============================================
# SCENARIO 12: Document Generation Flow
# ============================================
if [ -n "$USER_TOKEN" ]; then
    log_test "SCENARIO 12: Document Generation/Creation"
    log_info "URL: POST $API_BASE/api/v1/documents/"

    DOC_RESPONSE=$(curl -s -X POST "$API_BASE/api/v1/documents/" \
      -H "Authorization: Bearer $USER_TOKEN" \
      -H "Content-Type: application/json" \
      -d '{"title":"Test Thesis","topic":"Machine Learning in Healthcare","type":"thesis","pages":3,"language":"en"}' \
      -w "\nHTTP_CODE:%{http_code}")

    HTTP_CODE=$(echo "$DOC_RESPONSE" | grep "HTTP_CODE:" | cut -d':' -f2)
    RESPONSE_BODY=$(echo "$DOC_RESPONSE" | sed '/HTTP_CODE:/d')

    log_info "HTTP Status: $HTTP_CODE"
    log_info "Response: $RESPONSE_BODY"

    if [ "$HTTP_CODE" = "201" ] || [ "$HTTP_CODE" = "200" ]; then
        log_pass "Document creation endpoint works"
    elif [ "$HTTP_CODE" = "402" ]; then
        log_info "Payment required (expected behavior if no credits)"
        log_pass "Document creation returns correct 402 for payment"
    elif [ "$HTTP_CODE" = "404" ]; then
        log_fail "Documents endpoint not found (404)"
    else
        log_fail "Document creation failed with HTTP $HTTP_CODE"
    fi
elif [ -n "$ADMIN_TOKEN" ]; then
    log_test "SCENARIO 12: Document Generation (using admin token)"
    log_info "URL: POST $API_BASE/api/v1/documents/"

    DOC_RESPONSE=$(curl -s -X POST "$API_BASE/api/v1/documents/" \
      -H "Authorization: Bearer $ADMIN_TOKEN" \
      -H "Content-Type: application/json" \
      -d '{"title":"Test Thesis","topic":"Machine Learning in Healthcare","type":"thesis","pages":3,"language":"en"}' \
      -w "\nHTTP_CODE:%{http_code}")

    HTTP_CODE=$(echo "$DOC_RESPONSE" | grep "HTTP_CODE:" | cut -d':' -f2)
    RESPONSE_BODY=$(echo "$DOC_RESPONSE" | sed '/HTTP_CODE:/d')

    log_info "HTTP Status: $HTTP_CODE"
    log_info "Response: $RESPONSE_BODY"

    if [ "$HTTP_CODE" = "201" ] || [ "$HTTP_CODE" = "200" ]; then
        log_pass "Document creation endpoint works"
    elif [ "$HTTP_CODE" = "402" ]; then
        log_info "Payment required (expected)"
        log_pass "Document creation returns correct 402"
    elif [ "$HTTP_CODE" = "404" ]; then
        log_fail "Documents endpoint not found (404)"
    else
        log_fail "Document creation failed with HTTP $HTTP_CODE"
    fi
else
    log_blocked "SCENARIO 12: Document Generation - No auth token"
fi
echo "" | tee -a "$REPORT_FILE"

# ============================================
# SCENARIO 13: User Dashboard/Documents List
# ============================================
if [ -n "$USER_TOKEN" ]; then
    log_test "SCENARIO 13: User Documents List"
    log_info "URL: GET $API_BASE/api/v1/documents/"

    DOCS_RESPONSE=$(curl -s -X GET "$API_BASE/api/v1/documents/" \
      -H "Authorization: Bearer $USER_TOKEN" \
      -w "\nHTTP_CODE:%{http_code}")

    HTTP_CODE=$(echo "$DOCS_RESPONSE" | grep "HTTP_CODE:" | cut -d':' -f2)
    RESPONSE_BODY=$(echo "$DOCS_RESPONSE" | sed '/HTTP_CODE:/d')

    log_info "HTTP Status: $HTTP_CODE"

    if [ "$HTTP_CODE" = "200" ]; then
        log_pass "Documents list retrieved successfully"
        log_info "Response: $RESPONSE_BODY"
    elif [ "$HTTP_CODE" = "404" ]; then
        log_fail "Documents list endpoint not found (404)"
    else
        log_fail "Documents list failed with HTTP $HTTP_CODE"
    fi
elif [ -n "$ADMIN_TOKEN" ]; then
    log_test "SCENARIO 13: Documents List (using admin token)"
    log_info "URL: GET $API_BASE/api/v1/documents/"

    DOCS_RESPONSE=$(curl -s -X GET "$API_BASE/api/v1/documents/" \
      -H "Authorization: Bearer $ADMIN_TOKEN" \
      -w "\nHTTP_CODE:%{http_code}")

    HTTP_CODE=$(echo "$DOCS_RESPONSE" | grep "HTTP_CODE:" | cut -d':' -f2)
    RESPONSE_BODY=$(echo "$DOCS_RESPONSE" | sed '/HTTP_CODE:/d')

    log_info "HTTP Status: $HTTP_CODE"
    log_info "Response: $RESPONSE_BODY"

    if [ "$HTTP_CODE" = "200" ]; then
        log_pass "Documents list retrieved successfully"
    elif [ "$HTTP_CODE" = "404" ]; then
        log_fail "Documents list endpoint not found (404)"
    else
        log_fail "Documents list failed with HTTP $HTTP_CODE"
    fi
else
    log_blocked "SCENARIO 13: Documents List - No auth token"
fi
echo "" | tee -a "$REPORT_FILE"

# ============================================
# SCENARIO 14: Audit Logs (Admin)
# ============================================
if [ -n "$ADMIN_TOKEN" ]; then
    log_test "SCENARIO 14: Admin Audit Logs (Activity)"
    log_info "URL: GET $API_BASE/api/v1/admin/dashboard/activity"

    AUDIT_RESPONSE=$(curl -s -X GET "$API_BASE/api/v1/admin/dashboard/activity" \
      -H "Authorization: Bearer $ADMIN_TOKEN" \
      -w "\nHTTP_CODE:%{http_code}")

    HTTP_CODE=$(echo "$AUDIT_RESPONSE" | grep "HTTP_CODE:" | cut -d':' -f2)
    RESPONSE_BODY=$(echo "$AUDIT_RESPONSE" | sed '/HTTP_CODE:/d')

    log_info "HTTP Status: $HTTP_CODE"

    if [ "$HTTP_CODE" = "200" ]; then
        log_pass "Audit logs retrieved successfully"
        log_info "Response preview: ${RESPONSE_BODY:0:200}"
    elif [ "$HTTP_CODE" = "404" ]; then
        log_fail "Audit logs endpoint not found (404)"
    else
        log_fail "Audit logs failed with HTTP $HTTP_CODE"
    fi
else
    log_blocked "SCENARIO 14: Audit Logs - No admin token"
fi
echo "" | tee -a "$REPORT_FILE"

# ============================================
# Summary
# ============================================
echo "" | tee -a "$REPORT_FILE"
echo "========================================" | tee -a "$REPORT_FILE"
echo "TEST SUMMARY" | tee -a "$REPORT_FILE"
echo "========================================" | tee -a "$REPORT_FILE"
echo -e "${GREEN}PASSED: $PASS_COUNT${NC}" | tee -a "$REPORT_FILE"
echo -e "${RED}FAILED: $FAIL_COUNT${NC}" | tee -a "$REPORT_FILE"
echo -e "${YELLOW}BLOCKED: $BLOCKED_COUNT${NC}" | tee -a "$REPORT_FILE"
echo "========================================" | tee -a "$REPORT_FILE"
echo "" | tee -a "$REPORT_FILE"
echo "Full report saved to: $REPORT_FILE" | tee -a "$REPORT_FILE"

# Cleanup
rm -f "$COOKIE_JAR"

# Exit with appropriate code
if [ $FAIL_COUNT -gt 0 ]; then
    exit 1
else
    exit 0
fi
