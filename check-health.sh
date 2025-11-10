#!/bin/bash
#
# Перевірка стану AI TESI сервісів
# Використання: ./check-health.sh
#

echo "================================================"
echo "🔍 Перевірка стану AI TESI"
echo "================================================"
echo ""

# Функція для перевірки сервісу
check_service() {
    local name=$1
    local url=$2

    if curl -s -f "$url" > /dev/null 2>&1; then
        echo "✅ $name - OK"
        return 0
    else
        echo "❌ $name - FAIL"
        return 1
    fi
}

# Перевірка Docker контейнерів
echo "🐳 Docker контейнери:"
docker ps --format "table {{.Names}}\t{{.Status}}" | grep -E "postgres|redis|minio" || echo "⚠️  Контейнери не запущені"
echo ""

# Перевірка сервісів
echo "🌐 Сервіси:"
check_service "PostgreSQL      " "http://localhost:5432" || echo "   Порт: 5432"
check_service "Redis           " "http://localhost:6379" || echo "   Порт: 6379"
check_service "MinIO           " "http://localhost:9000" || echo "   Порт: 9000"
check_service "Backend Health  " "http://localhost:8000/health"
check_service "Backend API Docs" "http://localhost:8000/docs"
check_service "Frontend        " "http://localhost:3000"

echo ""
echo "================================================"

# Якщо Backend працює - показуємо детальну інформацію
if curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo ""
    echo "📊 Backend Health:"
    curl -s http://localhost:8000/health | python3 -m json.tool 2>/dev/null || curl -s http://localhost:8000/health
    echo ""
fi

echo ""
echo "🔗 URLs для відкриття:"
echo "  Frontend:  http://localhost:3000"
echo "  Backend:   http://localhost:8000"
echo "  API Docs:  http://localhost:8000/docs"
echo "  MinIO UI:  http://localhost:9001"
echo ""
