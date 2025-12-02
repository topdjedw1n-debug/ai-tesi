#!/bin/bash

# AI Thesis Platform - Development Setup Script

set -e

echo "🚀 Setting up AI Thesis Platform for development..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    print_error "Docker is not installed. Please install Docker first."
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    print_error "Docker Compose is not installed. Please install Docker Compose first."
    exit 1
fi

# Check if Node.js is installed (for local development)
if ! command -v node &> /dev/null; then
    print_warning "Node.js is not installed. You'll need it for local frontend development."
fi

# Check if Python is installed (for local development)
if ! command -v python3 &> /dev/null; then
    print_warning "Python 3 is not installed. You'll need it for local backend development."
fi

print_status "Starting infrastructure services..."

# Start database, Redis, and MinIO
cd infra/docker
docker-compose up -d postgres redis minio minio-setup

print_status "Waiting for services to be ready..."
sleep 10

# Check if services are running
if ! docker-compose ps | grep -q "Up"; then
    print_error "Failed to start infrastructure services"
    exit 1
fi

print_success "Infrastructure services started successfully!"

# Setup backend
print_status "Setting up backend..."
cd ../../apps/api

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    print_status "Creating Python virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment and install dependencies
print_status "Installing Python dependencies..."
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

print_success "Backend setup completed!"

# Setup frontend
print_status "Setting up frontend..."
cd ../web

# Install Node.js dependencies
if [ -f "package.json" ]; then
    print_status "Installing Node.js dependencies..."
    npm install
    print_success "Frontend setup completed!"
else
    print_warning "package.json not found in frontend directory"
fi

# Create environment files
print_status "Creating environment files..."

# Backend .env
if [ ! -f "apps/api/.env" ]; then
    cat > apps/api/.env << EOF
# Environment
ENVIRONMENT=development
DEBUG=true

# Database
DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5432/ai_thesis_platform

# Security
SECRET_KEY=dev-secret-key-change-in-production
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7

# CORS
ALLOWED_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
ALLOWED_HOSTS=localhost,127.0.0.1,0.0.0.0

# AI Providers (Add your API keys)
OPENAI_API_KEY=your-openai-api-key
ANTHROPIC_API_KEY=your-anthropic-api-key

# Redis
REDIS_URL=redis://localhost:6379

# MinIO/S3
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_BUCKET=ai-thesis-documents
MINIO_SECURE=false

# Rate Limiting
RATE_LIMIT_PER_MINUTE=60
EOF
    print_success "Created backend .env file"
fi

# Frontend .env.local
if [ ! -f "apps/web/.env.local" ]; then
    cat > apps/web/.env.local << EOF
# API Configuration
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_APP_NAME=AI Thesis Platform
NEXT_PUBLIC_APP_VERSION=1.0.0

# Authentication
NEXT_PUBLIC_AUTH_ENABLED=true

# Feature Flags
NEXT_PUBLIC_ANALYTICS_ENABLED=false
NEXT_PUBLIC_DEBUG_MODE=true
EOF
    print_success "Created frontend .env.local file"
fi

print_success "🎉 Development setup completed!"
echo ""
echo "📋 Next steps:"
echo "1. Add your AI API keys to apps/api/.env"
echo "2. Start the backend: cd apps/api && source venv/bin/activate && uvicorn main:app --reload"
echo "3. Start the frontend: cd apps/web && npm run dev"
echo "4. Access the application at http://localhost:3000"
echo "5. API documentation at http://localhost:8000/docs"
echo ""
echo "🐳 Or use Docker for everything:"
echo "   cd infra/docker && docker-compose up"
echo ""
print_success "Happy coding! 🚀"

