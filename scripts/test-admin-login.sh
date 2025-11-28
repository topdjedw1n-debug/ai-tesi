#!/bin/bash
# Admin Login Test Script
# Tests admin authentication and displays token

set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${BLUE}🔑 Testing Admin Login...${NC}\n"

# Test endpoint
echo -e "${YELLOW}→ Sending login request${NC}"
RESPONSE=$(curl -s -X POST http://localhost:8000/api/v1/auth/admin-login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@tesigo.com","password":"admin123"}')

# Check if successful
if echo "$RESPONSE" | jq -e '.access_token' > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Login successful!${NC}\n"
    
    # Extract data
    ACCESS_TOKEN=$(echo "$RESPONSE" | jq -r '.access_token')
    USER_ID=$(echo "$RESPONSE" | jq -r '.user.id')
    USER_EMAIL=$(echo "$RESPONSE" | jq -r '.user.email')
    IS_ADMIN=$(echo "$RESPONSE" | jq -r '.user.is_admin')
    
    echo -e "${GREEN}📊 Response:${NC}"
    echo "$RESPONSE" | jq '.'
    
    echo -e "\n${GREEN}🎫 Access Token:${NC}"
    echo "$ACCESS_TOKEN"
    
    echo -e "\n${GREEN}👤 User Info:${NC}"
    echo "  ID:       $USER_ID"
    echo "  Email:    $USER_EMAIL"
    echo "  Is Admin: $IS_ADMIN"
    
    echo -e "\n${BLUE}💡 To use this token:${NC}"
    echo "export TOKEN=\"$ACCESS_TOKEN\""
    echo "curl http://localhost:8000/api/v1/admin/dashboard -H \"Authorization: Bearer \$TOKEN\""
    
else
    echo -e "${YELLOW}❌ Login failed!${NC}\n"
    echo -e "${YELLOW}Response:${NC}"
    echo "$RESPONSE" | jq '.' || echo "$RESPONSE"
    exit 1
fi
