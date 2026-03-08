#!/bin/bash
# ============================================================================
# AI Thesis - Manual Deployment Script
# ============================================================================
# Use this script for manual deployments or troubleshooting
# This does the same as GitHub Actions but can be run directly on server
# ============================================================================

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

PROJECT_DIR="$HOME/ai-thesis"
DOCKER_COMPOSE_FILE="$PROJECT_DIR/infra/docker/docker-compose.prod.yml"
ENV_FILE="$PROJECT_DIR/.env.production"

echo -e "${BLUE}🚀 AI Thesis Deployment Script${NC}"
echo "=================================="

# ============================================================================
# Check prerequisites
# ============================================================================
echo -e "\n${GREEN}🔍 Checking prerequisites...${NC}"

if ! command -v docker &> /dev/null; then
    echo -e "${RED}❌ Docker is not installed. Run setup-ec2-server.sh first!${NC}"
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo -e "${RED}❌ Docker Compose is not installed. Run setup-ec2-server.sh first!${NC}"
    exit 1
fi

if [ ! -d "$PROJECT_DIR" ]; then
    echo -e "${RED}❌ Project directory not found: $PROJECT_DIR${NC}"
    echo "Run: git clone https://github.com/topdjedw1n-debug/ai-tesi.git $PROJECT_DIR"
    exit 1
fi

if [ ! -f "$ENV_FILE" ]; then
    echo -e "${RED}❌ Environment file not found: $ENV_FILE${NC}"
    echo "Please create .env.production file with all required variables"
    exit 1
fi

echo -e "${GREEN}✅ All prerequisites satisfied${NC}"

# ============================================================================
# Pull latest code
# ============================================================================
echo -e "\n${GREEN}📥 Pulling latest code from repository...${NC}"
cd "$PROJECT_DIR"
git fetch origin
CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
echo "Current branch: $CURRENT_BRANCH"
git pull origin "$CURRENT_BRANCH"

# ============================================================================
# Backup current database (optional but recommended)
# ============================================================================
echo -e "\n${YELLOW}💾 Creating database backup...${NC}"
BACKUP_DIR="$PROJECT_DIR/backups"
mkdir -p "$BACKUP_DIR"
BACKUP_FILE="$BACKUP_DIR/db_backup_$(date +%Y%m%d_%H%M%S).sql"

if docker ps | grep -q ai-thesis-postgres; then
    docker exec ai-thesis-postgres pg_dump -U postgres ai_thesis > "$BACKUP_FILE" 2>/dev/null || true
    if [ -f "$BACKUP_FILE" ] && [ -s "$BACKUP_FILE" ]; then
        echo -e "${GREEN}✅ Database backup created: $BACKUP_FILE${NC}"
    else
        echo -e "${YELLOW}⚠️  Database backup skipped (no existing data or error)${NC}"
        rm -f "$BACKUP_FILE"
    fi
else
    echo -e "${YELLOW}⚠️  Database container not running, skipping backup${NC}"
fi

# ============================================================================
# Stop current containers
# ============================================================================
echo -e "\n${GREEN}🛑 Stopping current containers...${NC}"
cd "$PROJECT_DIR/infra/docker"
docker-compose -f docker-compose.prod.yml down || true

# ============================================================================
# Clean up old images (optional)
# ============================================================================
read -p "Clean up old Docker images? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${GREEN}🧹 Cleaning up old Docker images...${NC}"
    docker image prune -f
fi

# ============================================================================
# Build and start new containers
# ============================================================================
echo -e "\n${GREEN}🏗️  Building and starting containers...${NC}"
docker-compose -f docker-compose.prod.yml --env-file "$ENV_FILE" up -d --build

# ============================================================================
# Wait for services to be healthy
# ============================================================================
echo -e "\n${GREEN}⏳ Waiting for services to become healthy...${NC}"
sleep 10

# Check PostgreSQL
echo -n "Checking PostgreSQL... "
for i in {1..30}; do
    if docker exec ai-thesis-postgres pg_isready -U postgres &>/dev/null; then
        echo -e "${GREEN}✅${NC}"
        break
    fi
    sleep 1
    echo -n "."
done

# Check Redis
echo -n "Checking Redis... "
for i in {1..30}; do
    if docker exec ai-thesis-redis redis-cli ping &>/dev/null; then
        echo -e "${GREEN}✅${NC}"
        break
    fi
    sleep 1
    echo -n "."
done

# ============================================================================
# Run database migrations
# ============================================================================
echo -e "\n${GREEN}🗄️  Running database migrations...${NC}"
docker-compose -f docker-compose.prod.yml exec -T api alembic upgrade head || {
    echo -e "${RED}❌ Migration failed!${NC}"
    echo "Check logs: docker-compose -f docker-compose.prod.yml logs api"
    exit 1
}

# ============================================================================
# Verify deployment
# ============================================================================
echo -e "\n${GREEN}🔍 Verifying deployment...${NC}"
docker-compose -f docker-compose.prod.yml ps

echo -e "\n${BLUE}📊 Container Status:${NC}"
docker-compose -f docker-compose.prod.yml ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}"

# ============================================================================
# Health checks
# ============================================================================
echo -e "\n${GREEN}🏥 Running health checks...${NC}"

# Get server IP
SERVER_IP=$(curl -s ifconfig.me)

# Check backend
echo -n "Backend API... "
if curl -sf "http://localhost:8000/health" > /dev/null; then
    echo -e "${GREEN}✅${NC}"
else
    echo -e "${RED}❌${NC}"
fi

# Check frontend
echo -n "Frontend... "
if curl -sf "http://localhost:3000/api/health" > /dev/null; then
    echo -e "${GREEN}✅${NC}"
else
    echo -e "${RED}❌${NC}"
fi

# ============================================================================
# Show logs
# ============================================================================
echo -e "\n${YELLOW}📋 Recent logs (last 20 lines):${NC}"
docker-compose -f docker-compose.prod.yml logs --tail=20

# ============================================================================
# Success message
# ============================================================================
echo -e "\n${GREEN}=================================="
echo "✅ Deployment completed successfully!"
echo "==================================${NC}"
echo ""
echo "🌐 Services are available at:"
echo "   - Frontend:     http://$SERVER_IP:3000"
echo "   - Backend API:  http://$SERVER_IP:8000"
echo "   - API Docs:     http://$SERVER_IP:8000/docs"
echo "   - MinIO:        http://$SERVER_IP:9000"
echo "   - MinIO Console: http://$SERVER_IP:9001"
echo ""
echo "📊 Useful commands:"
echo "   - View logs:       cd $PROJECT_DIR/infra/docker && docker-compose -f docker-compose.prod.yml logs -f"
echo "   - Container status: docker-compose -f docker-compose.prod.yml ps"
echo "   - Restart service:  docker-compose -f docker-compose.prod.yml restart <service>"
echo "   - Stop all:        docker-compose -f docker-compose.prod.yml down"
echo ""
echo "🔍 Troubleshooting:"
echo "   - Check API logs:  docker-compose -f docker-compose.prod.yml logs api"
echo "   - Check DB logs:   docker-compose -f docker-compose.prod.yml logs postgres"
echo "   - Shell into API:  docker-compose -f docker-compose.prod.yml exec api bash"
echo ""
