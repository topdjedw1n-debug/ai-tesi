#!/bin/bash
#
# Автоматичне створення .env файлів для AI TESI
# Використання: ./setup-env.sh
#

set -e

echo "================================================"
echo "🔧 Налаштування .env файлів для AI TESI"
echo "================================================"
echo ""

# Визначаємо абсолютний шлях до проекту
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

echo "📁 Проект: $PROJECT_ROOT"
echo ""

# ============================================
# Backend .env
# ============================================

BACKEND_ENV="$PROJECT_ROOT/apps/api/.env"

echo "📝 Створення Backend .env..."

if [ -f "$BACKEND_ENV" ]; then
    echo "⚠️  Файл $BACKEND_ENV вже існує"
    echo "   Створюю backup: $BACKEND_ENV.backup"
    cp "$BACKEND_ENV" "$BACKEND_ENV.backup"
fi

cat > "$BACKEND_ENV" << 'EOF'
# Environment
ENVIRONMENT=development
DEBUG=True

# Security - ВАЖЛИВО: Змініть для production!
SECRET_KEY=dev-secret-key-min-32-chars-CHANGE-IN-PRODUCTION-12345678

# Database
DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5432/ai_thesis_platform

# Redis
REDIS_URL=redis://localhost:6379

# MinIO Storage
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_BUCKET=ai-thesis-documents
MINIO_SECURE=false

# AI Providers (опціонально - для генерації)
OPENAI_API_KEY=
ANTHROPIC_API_KEY=

# Email (опціонально - для production)
SMTP_HOST=
SMTP_PORT=587
SMTP_USER=
SMTP_PASSWORD=
EMAILS_FROM_EMAIL=
EMAILS_FROM_NAME=

# Monitoring (опціонально)
SENTRY_DSN=

# CORS
ALLOWED_ORIGINS=["http://localhost:3000","http://127.0.0.1:3000"]
ALLOWED_HOSTS=["localhost","127.0.0.1","0.0.0.0"]

# Rate Limiting
RATE_LIMIT_PER_MINUTE=60
EOF

echo "✅ Backend .env створено: $BACKEND_ENV"
echo ""

# ============================================
# Frontend .env.local
# ============================================

FRONTEND_ENV="$PROJECT_ROOT/apps/web/.env.local"

echo "📝 Створення Frontend .env.local..."

if [ -f "$FRONTEND_ENV" ]; then
    echo "⚠️  Файл $FRONTEND_ENV вже існує"
    echo "   Створюю backup: $FRONTEND_ENV.backup"
    cp "$FRONTEND_ENV" "$FRONTEND_ENV.backup"
fi

cat > "$FRONTEND_ENV" << 'EOF'
NEXT_PUBLIC_API_URL=http://localhost:8000
EOF

echo "✅ Frontend .env.local створено: $FRONTEND_ENV"
echo ""

# ============================================
# Підсумок
# ============================================

echo "================================================"
echo "✅ Налаштування завершено!"
echo "================================================"
echo ""
echo "📋 Створені файли:"
echo "  1. $BACKEND_ENV"
echo "  2. $FRONTEND_ENV"
echo ""
echo "🔍 Перевірка:"
ls -lh "$BACKEND_ENV" "$FRONTEND_ENV"
echo ""
echo "🚀 Наступний крок: запустіть ./start-dev.sh"
echo ""
