#!/bin/bash
# Environment variables validation script for TesiGo
# Validates that all required production environment variables are set
# and meet security requirements

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Counters
ERRORS=0
WARNINGS=0
CHECKS=0

echo -e "${BLUE}================================================${NC}"
echo -e "${BLUE}TesiGo Environment Variables Validation${NC}"
echo -e "${BLUE}================================================${NC}"
echo ""

# Function to print error
error() {
    echo -e "${RED}[ERROR]${NC} $1"
    ((ERRORS++))
}

# Function to print warning
warning() {
    echo -e "${YELLOW}[WARN]${NC} $1"
    ((WARNINGS++))
}

# Function to print success
success() {
    echo -e "${GREEN}[OK]${NC} $1"
}

# Function to check if variable is set
check_var() {
    local var_name=$1
    local min_length=${2:-1}
    local var_value="${!var_name}"
    
    ((CHECKS++))
    
    if [ -z "$var_value" ]; then
        error "$var_name is not set"
        return 1
    elif [ ${#var_value} -lt $min_length ]; then
        error "$var_name is too short (${#var_value} chars, minimum: $min_length)"
        return 1
    else
        success "$var_name is set (${#var_value} chars)"
        return 0
    fi
}

# Function to check if variable contains example/placeholder value
check_not_example() {
    local var_name=$1
    local var_value="${!var_name}"
    
    if [[ "$var_value" =~ CHANGE_THIS|your-|example|test|minioadmin|sk-proj-your|sk-ant-your|tvly-your ]]; then
        error "$var_name contains placeholder value. Must be changed for production!"
        return 1
    fi
    return 0
}

# Load environment file if provided
ENV_FILE="${1:-.env}"
if [ -f "$ENV_FILE" ]; then
    echo -e "Loading environment from: ${BLUE}$ENV_FILE${NC}"
    export $(grep -v '^#' "$ENV_FILE" | xargs)
    echo ""
else
    warning "Environment file '$ENV_FILE' not found, checking system environment"
    echo ""
fi

echo -e "${BLUE}=== Critical Security Variables ===${NC}"
check_var "SECRET_KEY" 64
check_not_example "SECRET_KEY"
check_var "JWT_SECRET" 64
check_not_example "JWT_SECRET"
echo ""

echo -e "${BLUE}=== Database Configuration ===${NC}"
check_var "DATABASE_URL" 20
if [[ "$DATABASE_URL" =~ tesigo_password|CHANGE_THIS ]]; then
    error "DATABASE_URL contains default password. Must be changed!"
fi
echo ""

echo -e "${BLUE}=== AI API Keys ===${NC}"
check_var "OPENAI_API_KEY" 20
check_not_example "OPENAI_API_KEY"
check_var "ANTHROPIC_API_KEY" 20
check_not_example "ANTHROPIC_API_KEY"
check_var "TAVILY_API_KEY" 15
check_not_example "TAVILY_API_KEY"
echo ""

echo -e "${BLUE}=== Storage Configuration ===${NC}"
check_var "MINIO_ENDPOINT" 5
check_var "MINIO_ACCESS_KEY" 10
check_var "MINIO_SECRET_KEY" 20
check_var "MINIO_BUCKET" 5
if [[ "$MINIO_ACCESS_KEY" == "minioadmin" || "$MINIO_SECRET_KEY" == "minioadmin" ]]; then
    error "MinIO credentials are default. Must be changed for production!"
fi
echo ""

echo -e "${BLUE}=== Redis Configuration ===${NC}"
check_var "REDIS_URL" 10
echo ""

echo -e "${BLUE}=== Payment (Stripe) ===${NC}"
check_var "STRIPE_SECRET_KEY" 20
check_var "STRIPE_WEBHOOK_SECRET" 20
if [[ "$STRIPE_SECRET_KEY" =~ sk_test ]]; then
    warning "STRIPE_SECRET_KEY is test key (sk_test). Use sk_live for production!"
fi
echo ""

echo -e "${BLUE}=== SMTP/Email Configuration ===${NC}"
if check_var "SMTP_HOST" 5; then
    check_var "SMTP_PORT" 2
    check_var "SMTP_USER" 5
    check_var "SMTP_PASSWORD" 8
    check_var "SMTP_FROM_EMAIL" 5
else
    warning "SMTP not configured - email notifications will fail"
fi
echo ""

echo -e "${BLUE}=== Environment Settings ===${NC}"
check_var "ENVIRONMENT" 3
if [ "$ENVIRONMENT" == "production" ] && [ "$DEBUG" == "true" ]; then
    error "DEBUG=true in production environment!"
fi
check_var "CORS_ALLOWED_ORIGINS" 5
check_var "ALLOWED_HOSTS" 5
echo ""

echo -e "${BLUE}=== Optional Services ===${NC}"
if [ -n "$SENTRY_DSN" ]; then
    success "Sentry error tracking configured"
else
    warning "SENTRY_DSN not set - error tracking disabled"
fi

if [ -n "$GPTZERO_API_KEY" ] || [ -n "$ORIGINALITY_AI_API_KEY" ]; then
    success "AI detection API configured"
else
    warning "AI detection APIs not configured"
fi

if [ -n "$COPYSCAPE_API_KEY" ]; then
    success "Plagiarism check API configured"
else
    warning "Copyscape API not configured - plagiarism checks may fail"
fi
echo ""

# Summary
echo -e "${BLUE}================================================${NC}"
echo -e "${BLUE}Validation Summary${NC}"
echo -e "${BLUE}================================================${NC}"
echo -e "Total checks: ${BLUE}$CHECKS${NC}"
echo -e "Errors:       ${RED}$ERRORS${NC}"
echo -e "Warnings:     ${YELLOW}$WARNINGS${NC}"
echo ""

if [ $ERRORS -eq 0 ]; then
    if [ $WARNINGS -eq 0 ]; then
        echo -e "${GREEN}✓ All environment variables are properly configured!${NC}"
        exit 0
    else
        echo -e "${YELLOW}⚠ Configuration has warnings but is acceptable${NC}"
        echo -e "${YELLOW}  Consider fixing warnings for optimal setup${NC}"
        exit 0
    fi
else
    echo -e "${RED}✗ Configuration has $ERRORS critical error(s)!${NC}"
    echo -e "${RED}  Fix errors before deploying to production${NC}"
    exit 1
fi
