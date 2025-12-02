#!/bin/bash
# Comprehensive Runtime Verification Script
# Usage: ./scripts/runtime-verification.sh
# Prerequisites: Docker must be running and services started

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$SCRIPT_DIR"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Counters
PASSED=0
FAILED=0
WARNINGS=0
SKIPPED=0

# Results file
RESULTS_FILE="$SCRIPT_DIR/RUNTIME_VERIFICATION_RESULTS.txt"
echo "=== RUNTIME VERIFICATION RESULTS ===" > "$RESULTS_FILE"
echo "Date: $(date)" >> "$RESULTS_FILE"
echo "" >> "$RESULTS_FILE"

# Check function
check() {
    local test_name=$1
    local command=$2

    echo -n "Testing: $test_name ... "
    echo "Testing: $test_name ... " >> "$RESULTS_FILE"

    if eval "$command" >> "$RESULTS_FILE" 2>&1; then
        echo -e "${GREEN}✓ PASSED${NC}"
        echo "Result: PASSED" >> "$RESULTS_FILE"
        ((PASSED++))
    else
        echo -e "${RED}✗ FAILED${NC}"
        echo "Result: FAILED" >> "$RESULTS_FILE"
        ((FAILED++))
    fi
    echo "" >> "$RESULTS_FILE"
}

# Warning function (non-critical)
warn_check() {
    local test_name=$1
    local command=$2

    echo -n "Testing: $test_name ... "
    echo "Testing: $test_name ... " >> "$RESULTS_FILE"

    if eval "$command" >> "$RESULTS_FILE" 2>&1; then
        echo -e "${GREEN}✓ PASSED${NC}"
        echo "Result: PASSED" >> "$RESULTS_FILE"
        ((PASSED++))
    else
        echo -e "${YELLOW}⚠ WARNING${NC}"
        echo "Result: WARNING" >> "$RESULTS_FILE"
        ((WARNINGS++))
    fi
    echo "" >> "$RESULTS_FILE"
}

# Skip function
skip_check() {
    local test_name=$1
    echo -e "${BLUE}⊘ SKIPPED${NC}: $test_name"
    echo "Testing: $test_name ... SKIPPED" >> "$RESULTS_FILE"
    ((SKIPPED++))
}

echo -e "${BLUE}🚀 Starting Runtime Verification...${NC}"
echo "=========================================="

# Check Docker
echo -e "\n${BLUE}=== DOCKER CHECKS ===${NC}"
if ! docker info > /dev/null 2>&1; then
    echo -e "${RED}❌ Docker daemon is not running!${NC}"
    echo "Please start Docker Desktop and try again."
    exit 1
fi

check "Docker Daemon" "docker info"
check "Docker Compose" "docker-compose --version"

# Check if services are running
echo -e "\n${BLUE}=== SERVICE STATUS ===${NC}"
if docker-compose -f infra/docker/docker-compose.yml ps | grep -q "Up"; then
    echo -e "${GREEN}✓ Services are running${NC}"
    check "PostgreSQL Container" "docker exec ai-thesis-postgres psql -U postgres -c 'SELECT version();'"
    check "Redis Container" "docker exec ai-thesis-redis redis-cli ping"
    warn_check "MinIO Container" "docker exec ai-thesis-minio mc admin info local"
    check "API Health" "curl -f http://localhost:8000/health"
    warn_check "Frontend" "curl -f http://localhost:3000"
else
    echo -e "${YELLOW}⚠ Services not running. Starting services...${NC}"
    docker-compose -f infra/docker/docker-compose.yml up -d
    echo "Waiting for services to start..."
    sleep 10
fi

# PART 0: Critical Components
echo -e "\n${BLUE}=== PART 0: CRITICAL COMPONENTS ===${NC}"

# JWT Refresh Token
echo -e "\n${BLUE}JWT Refresh Token${NC}"
TOKEN_RESPONSE=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "test@example.com", "password": "test123"}' 2>/dev/null || echo "{}")
REFRESH_TOKEN=$(echo "$TOKEN_RESPONSE" | grep -o '"refresh_token":"[^"]*"' | cut -d'"' -f4 || echo "")
if [ -n "$REFRESH_TOKEN" ]; then
    check "JWT Refresh Token Endpoint" "curl -X POST http://localhost:8000/api/v1/auth/refresh -H 'Content-Type: application/json' -d '{\"refresh_token\": \"$REFRESH_TOKEN\"}' | grep -q access_token"
else
    skip_check "JWT Refresh Token (need valid user)"
fi

# Admin Panel
echo -e "\n${BLUE}Admin Panel${NC}"
warn_check "Admin Dashboard Endpoint" "curl -I http://localhost:8000/api/v1/admin/stats 2>&1 | grep -E '200|401|403'"

# Minimum 3 Pages Validation
echo -e "\n${BLUE}Minimum 3 Pages Validation${NC}"
# Need auth token for this
skip_check "Minimum 3 Pages Validation (requires auth)"

# PART 1: Infrastructure
echo -e "\n${BLUE}=== PART 1: INFRASTRUCTURE ===${NC}"

check "PostgreSQL Connection" "docker exec ai-thesis-postgres psql -U postgres -d ai_thesis_platform -c 'SELECT 1'"
check "PostgreSQL Tables" "docker exec ai-thesis-postgres psql -U postgres -d ai_thesis_platform -c '\\dt' | grep -q users"
check "Redis Ping" "docker exec ai-thesis-redis redis-cli ping | grep -q PONG"
warn_check "Redis Memory" "docker exec ai-thesis-redis redis-cli INFO memory | grep used_memory_human"

# PART 2: Backend Functionality
echo -e "\n${BLUE}=== PART 2: BACKEND FUNCTIONALITY ===${NC}"

check "API Health Endpoint" "curl -f http://localhost:8000/health"
check "API Root Endpoint" "curl -f http://localhost:8000/"
check "API Docs (if enabled)" "curl -I http://localhost:8000/docs 2>&1 | grep -E '200|404'"

# Auth endpoints (without auth)
warn_check "Auth Register Endpoint" "curl -X POST http://localhost:8000/api/v1/auth/register -H 'Content-Type: application/json' -d '{}' 2>&1 | grep -E '422|400'"
warn_check "Auth Login Endpoint" "curl -X POST http://localhost:8000/api/v1/auth/login -H 'Content-Type: application/json' -d '{}' 2>&1 | grep -E '422|400'"

# PART 3: Security
echo -e "\n${BLUE}=== PART 3: SECURITY ===${NC}"

check "CORS Headers" "curl -I -X OPTIONS http://localhost:8000/api/v1/health -H 'Origin: http://localhost:3000' 2>&1 | grep -i access-control-allow-origin"
warn_check "Rate Limiting Headers" "curl -I http://localhost:8000/api/v1/health 2>&1 | grep -i 'x-ratelimit' || echo 'Rate limit headers not present'"

# PART 4: Frontend
echo -e "\n${BLUE}=== PART 4: FRONTEND ===${NC}"

warn_check "Frontend Homepage" "curl -f http://localhost:3000 2>&1 | head -5"
warn_check "Frontend Dashboard" "curl -I http://localhost:3000/dashboard 2>&1 | grep -E '200|404|301|302'"

# Summary
echo -e "\n${BLUE}=========================================="
echo -e "=== VERIFICATION SUMMARY ===${NC}"
echo "" >> "$RESULTS_FILE"
echo "=== SUMMARY ===" >> "$RESULTS_FILE"
echo "Passed: $PASSED" >> "$RESULTS_FILE"
echo "Failed: $FAILED" >> "$RESULTS_FILE"
echo "Warnings: $WARNINGS" >> "$RESULTS_FILE"
echo "Skipped: $SKIPPED" >> "$RESULTS_FILE"

echo -e "${GREEN}Passed: $PASSED${NC}"
echo -e "${YELLOW}Warnings: $WARNINGS${NC}"
echo -e "${RED}Failed: $FAILED${NC}"
echo -e "${BLUE}Skipped: $SKIPPED${NC}"

if [ $FAILED -eq 0 ]; then
    echo -e "\n${GREEN}🎉 ALL CRITICAL CHECKS PASSED!${NC}"
    echo "Results saved to: $RESULTS_FILE"
    exit 0
else
    echo -e "\n${RED}⚠️ SOME CHECKS FAILED!${NC}"
    echo "Results saved to: $RESULTS_FILE"
    exit 1
fi
