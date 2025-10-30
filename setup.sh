#!/bin/bash

# AI Thesis Platform Setup Script
# This script sets up the development environment for the AI Thesis Platform

set -e

echo "🚀 Setting up AI Thesis Platform..."

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

# Check if required tools are installed
check_requirements() {
    print_status "Checking requirements..."
    
    # Check Node.js
    if ! command -v node &> /dev/null; then
        print_error "Node.js is not installed. Please install Node.js 18+ and try again."
        exit 1
    fi
    
    # Check Python
    if ! command -v python3 &> /dev/null; then
        print_error "Python 3 is not installed. Please install Python 3.11+ and try again."
        exit 1
    fi
    
    # Check Docker
    if ! command -v docker &> /dev/null; then
        print_error "Docker is not installed. Please install Docker and try again."
        exit 1
    fi
    
    # Check Docker Compose
    if ! command -v docker-compose &> /dev/null; then
        print_error "Docker Compose is not installed. Please install Docker Compose and try again."
        exit 1
    fi
    
    print_success "All requirements are met!"
}

# Setup environment files
setup_env_files() {
    print_status "Setting up environment files..."
    
    # Copy .env.example to .env if it doesn't exist
    if [ ! -f .env ]; then
        cp env.example .env
        print_success "Created .env file from env.example"
    else
        print_warning ".env file already exists, skipping..."
    fi
    
    # Create .env files for frontend and backend
    if [ ! -f apps/web/.env.local ]; then
        cat > apps/web/.env.local << EOF
NEXT_PUBLIC_API_URL=http://localhost:8000
EOF
        print_success "Created apps/web/.env.local"
    fi
    
    if [ ! -f apps/api/.env ]; then
        cp env.example apps/api/.env
        print_success "Created apps/api/.env"
    fi
}

# Setup backend
setup_backend() {
    print_status "Setting up backend..."
    
    cd apps/api
    
    # Create virtual environment
    if [ ! -d "venv" ]; then
        python3 -m venv venv
        print_success "Created Python virtual environment"
    fi
    
    # Activate virtual environment and install dependencies
    source venv/bin/activate
    pip install --upgrade pip
    pip install -r requirements.txt
    print_success "Installed Python dependencies"
    
    cd ../..
}

# Setup frontend
setup_frontend() {
    print_status "Setting up frontend..."
    
    cd apps/web
    
    # Install dependencies
    npm install
    print_success "Installed Node.js dependencies"
    
    cd ../..
}

# Setup infrastructure
setup_infrastructure() {
    print_status "Setting up infrastructure..."
    
    cd infra/docker
    
    # Start services
    docker-compose up -d
    print_success "Started PostgreSQL, Minio, and Redis services"
    
    # Wait for services to be ready
    print_status "Waiting for services to be ready..."
    sleep 10
    
    cd ../..
}

# Run database migrations
run_migrations() {
    print_status "Running database migrations..."
    
    cd apps/api
    source venv/bin/activate
    
    # TODO: Add Alembic migrations when they are created
    print_warning "Database migrations will be added in the next iteration"
    
    cd ../..
}

# Build frontend
build_frontend() {
    print_status "Building frontend..."
    
    cd apps/web
    npm run build
    print_success "Frontend built successfully"
    
    cd ../..
}

# Print next steps
print_next_steps() {
    print_success "Setup completed successfully! 🎉"
    echo ""
    echo "Next steps:"
    echo "1. Update the .env files with your API keys and configuration"
    echo "2. Start the backend: cd apps/api && source venv/bin/activate && uvicorn main:app --reload"
    echo "3. Start the frontend: cd apps/web && npm run dev"
    echo "4. Visit http://localhost:3000 to see the application"
    echo ""
    echo "Infrastructure services are running:"
    echo "- PostgreSQL: localhost:5432"
    echo "- Minio: http://localhost:9000 (admin/admin)"
    echo "- Redis: localhost:6379"
    echo ""
    echo "For more information, see the README.md file."
}

# Main execution
main() {
    check_requirements
    setup_env_files
    setup_backend
    setup_frontend
    setup_infrastructure
    run_migrations
    build_frontend
    print_next_steps
}

# Run main function
main "$@"
