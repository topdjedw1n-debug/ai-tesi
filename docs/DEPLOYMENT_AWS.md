# AWS EC2 Deployment Guide

Complete guide for deploying TesiGo on AWS EC2.

## Prerequisites

- AWS EC2 instance (Amazon Linux 2023 or similar)
- SSH access to the instance
- Domain name or public IP address
- API keys for OpenAI, Anthropic, Stripe, etc.

## Step 1: System Preparation

```bash
# Update system
sudo dnf update -y

# Install Docker
sudo dnf install -y docker
sudo systemctl start docker
sudo systemctl enable docker
sudo usermod -aG docker ec2-user

# Install Docker Compose v2
sudo mkdir -p /usr/local/lib/docker/cli-plugins
sudo curl -SL https://github.com/docker/compose/releases/download/v2.24.0/docker-compose-linux-x86_64 -o /usr/local/lib/docker/cli-plugins/docker-compose
sudo chmod +x /usr/local/lib/docker/cli-plugins/docker-compose

# Install Git
sudo dnf install -y git

# Log out and back in for docker group to take effect
exit
```

## Step 2: Clone Repository

```bash
cd ~
git clone https://github.com/YOUR_USERNAME/ai-tesi.git ai-thesis
cd ai-thesis
```

## Step 3: Environment Configuration

```bash
# Copy production example
cp apps/api/.env.production.example .env.production

# Edit with your values
nano .env.production
```

**Important variables to set:**

```bash
# Database
POSTGRES_PASSWORD=YourSecurePassword123

# Security
SECRET_KEY=$(python3 scripts/generate_secrets.py)
JWT_SECRET=$(python3 scripts/generate_secrets.py)

# API Keys
OPENAI_API_KEY=sk-proj-...
ANTHROPIC_API_KEY=sk-ant-...
TAVILY_API_KEY=tvly-...
STRIPE_SECRET_KEY=sk_live_...
STRIPE_WEBHOOK_SECRET=whsec_...

# Server Configuration (replace with your IP)
SERVER_IP=98.88.34.179
CORS_ALLOWED_ORIGINS=http://${SERVER_IP}:3000
ALLOWED_HOSTS=["${SERVER_IP}","localhost","127.0.0.1"]
FRONTEND_URL=http://${SERVER_IP}:3000
NEXT_PUBLIC_API_URL=http://${SERVER_IP}:8000
```

## Step 4: Build Docker Images

```bash
# Build API
cd apps/api
docker build -t ai-thesis-api:latest .

# Build Web with correct API URL
cd ../web
docker build --build-arg NEXT_PUBLIC_API_URL=http://YOUR_SERVER_IP:8000 --no-cache -t ai-thesis-web:latest .

cd ~/ai-thesis
```

## Step 5: Database Setup

```bash
# Create Docker network
docker network create ai-thesis-network

# Start infrastructure services
docker run -d \
  --name ai-thesis-postgres \
  --network ai-thesis-network \
  -p 5432:5432 \
  -e POSTGRES_DB=ai_thesis_platform \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD=YourSecurePassword123 \
  -v postgres_data:/var/lib/postgresql/data \
  postgres:15-alpine

docker run -d \
  --name ai-thesis-redis \
  --network ai-thesis-network \
  -p 6379:6379 \
  redis:7-alpine

docker run -d \
  --name ai-thesis-minio \
  --network ai-thesis-network \
  -p 9000:9000 \
  -p 9001:9001 \
  -e MINIO_ROOT_USER=minioadmin \
  -e MINIO_ROOT_PASSWORD=YourSecureMinioPassword \
  -v minio_data:/data \
  minio/minio server /data --console-address ":9001"

# Wait for PostgreSQL to be ready
sleep 10

# Run migrations
docker cp apps/api/migrations ai-thesis-postgres:/tmp/
docker exec ai-thesis-postgres psql -U postgres -d ai_thesis_platform -f /tmp/migrations/001_initial_schema.sql
docker exec ai-thesis-postgres psql -U postgres -d ai_thesis_platform -f /tmp/migrations/005_add_missing_columns.sql

# Create admin user
docker exec -it ai-thesis-postgres psql -U postgres -d ai_thesis_platform -c "
INSERT INTO users (email, full_name, is_verified, is_admin, hashed_password, created_at)
VALUES ('admin@tesigo.com', 'Admin', true, true, '\$2b\$12\$YOUR_HASHED_PASSWORD', NOW())
ON CONFLICT (email) DO NOTHING;
"
```

## Step 6: Start Application Services

```bash
# Create symlink for env file
ln -sf ~/.env.production ~/ai-thesis/infra/docker/.env

# Start API
docker run -d \
  --name ai-thesis-api \
  --network ai-thesis-network \
  -p 8000:8000 \
  --env-file ~/.env.production \
  ai-thesis-api:latest

# Start Web
docker run -d \
  --name ai-thesis-web \
  --network host \
  -p 3000:3000 \
  ai-thesis-web:latest

# Check status
docker ps
docker logs ai-thesis-api --tail 50
docker logs ai-thesis-web --tail 50
```

## Step 7: Verify Deployment

```bash
# Test API health
curl http://localhost:8000/health

# Test frontend
curl http://localhost:3000

# Test from external network
curl http://YOUR_SERVER_IP:8000/health
```

## Troubleshooting

### CORS Errors

Make sure `CORS_ALLOWED_ORIGINS` in `.env.production` matches your frontend URL:

```bash
CORS_ALLOWED_ORIGINS=http://YOUR_SERVER_IP:3000
```

### Database Connection Errors

Check PostgreSQL is running and accessible:

```bash
docker exec ai-thesis-postgres psql -U postgres -d ai_thesis_platform -c "SELECT 1;"
```

### Frontend Shows localhost:8000

Rebuild web image with correct API URL:

```bash
cd apps/web
docker stop ai-thesis-web && docker rm ai-thesis-web
docker build --build-arg NEXT_PUBLIC_API_URL=http://YOUR_SERVER_IP:8000 --no-cache -t ai-thesis-web:latest .
docker run -d --name ai-thesis-web --network host -p 3000:3000 ai-thesis-web:latest
```

## Updating Deployment

```bash
# Pull latest changes
cd ~/ai-thesis
git pull origin main

# Rebuild images
cd apps/api && docker build -t ai-thesis-api:latest .
cd ../web && docker build --build-arg NEXT_PUBLIC_API_URL=http://YOUR_SERVER_IP:8000 -t ai-thesis-web:latest .

# Restart services
docker stop ai-thesis-api ai-thesis-web
docker rm ai-thesis-api ai-thesis-web

docker run -d --name ai-thesis-api --network ai-thesis-network -p 8000:8000 --env-file ~/.env.production ai-thesis-api:latest
docker run -d --name ai-thesis-web --network host -p 3000:3000 ai-thesis-web:latest
```

## Security Notes

1. **Never commit `.env.production`** with real credentials
2. Use **strong passwords** for PostgreSQL, MinIO, admin users
3. Consider using **AWS Secrets Manager** for sensitive data
4. Set up **SSL/TLS** with Let's Encrypt for production
5. Configure **firewall rules** to restrict access
6. Enable **CloudWatch** monitoring
7. Set up **automatic backups** for database

## Performance Optimization

1. Use **Amazon RDS** for PostgreSQL in production
2. Use **ElastiCache** for Redis
3. Use **S3** instead of MinIO
4. Set up **CloudFront CDN** for static assets
5. Configure **Application Load Balancer**
6. Enable **auto-scaling** for EC2 instances
