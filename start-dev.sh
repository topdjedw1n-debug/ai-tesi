#!/bin/bash
#
# Автоматичний запуск AI TESI в development режимі
# Використання: ./start-dev.sh
#

set -e

echo "================================================"
echo "🚀 Запуск AI TESI Development Server"
echo "================================================"
echo ""

# Визначаємо абсолютний шлях до проекту
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

# ============================================
# Перевірка .env файлів
# ============================================

echo "🔍 Перевірка .env файлів..."

if [ ! -f "$PROJECT_ROOT/apps/api/.env" ]; then
    echo "❌ Файл apps/api/.env не знайдено!"
    echo "   Запустіть спочатку: ./setup-env.sh"
    exit 1
fi

if [ ! -f "$PROJECT_ROOT/apps/web/.env.local" ]; then
    echo "❌ Файл apps/web/.env.local не знайдено!"
    echo "   Запустіть спочатку: ./setup-env.sh"
    exit 1
fi

echo "✅ .env файли знайдено"
echo ""

# ============================================
# Перевірка Docker контейнерів
# ============================================

echo "🐳 Перевірка Docker контейнерів..."

if ! docker ps | grep -q postgres; then
    echo "⚠️  PostgreSQL не запущений"
    echo "   Запускаю інфраструктуру..."
    cd "$PROJECT_ROOT/infra/docker"
    docker-compose up -d postgres redis minio minio-setup
    cd "$PROJECT_ROOT"
    echo "⏳ Чекаю 10 секунд поки бази даних ініціалізуються..."
    sleep 10
else
    echo "✅ PostgreSQL запущений"
fi

if ! docker ps | grep -q redis; then
    echo "⚠️  Redis не запущений"
    echo "   Запускаю Redis..."
    cd "$PROJECT_ROOT/infra/docker"
    docker-compose up -d redis
    cd "$PROJECT_ROOT"
else
    echo "✅ Redis запущений"
fi

echo ""

# ============================================
# Backend Setup
# ============================================

echo "📦 Налаштування Backend..."
cd "$PROJECT_ROOT/apps/api"

# Перевірка/створення virtualenv
if [ ! -d "venv" ]; then
    echo "🔧 Створення Python virtualenv..."
    python3 -m venv venv
fi

# Активація virtualenv
echo "🔧 Активація virtualenv..."
source venv/bin/activate

# Встановлення залежностей
echo "📥 Перевірка залежностей..."
pip install -q -r requirements.txt

echo "✅ Backend готовий"
echo ""

# ============================================
# Frontend Setup
# ============================================

echo "📦 Налаштування Frontend..."
cd "$PROJECT_ROOT/apps/web"

# Встановлення залежностей
if [ ! -d "node_modules" ]; then
    echo "📥 Встановлення npm залежностей..."
    npm install
else
    echo "✅ npm залежності вже встановлені"
fi

echo "✅ Frontend готовий"
echo ""

# ============================================
# Запуск серверів
# ============================================

echo "================================================"
echo "🚀 Запуск серверів"
echo "================================================"
echo ""

# Створюємо директорію для логів
mkdir -p "$PROJECT_ROOT/logs"

# Функція для cleanup при завершенні
cleanup() {
    echo ""
    echo "🛑 Зупинка серверів..."
    kill $BACKEND_PID 2>/dev/null || true
    kill $FRONTEND_PID 2>/dev/null || true
    exit 0
}

trap cleanup SIGINT SIGTERM

# Запуск Backend
echo "🔵 Запуск Backend (port 8000)..."
cd "$PROJECT_ROOT/apps/api"
source venv/bin/activate
uvicorn main:app --host 0.0.0.0 --port 8000 --reload > "$PROJECT_ROOT/logs/backend.log" 2>&1 &
BACKEND_PID=$!
echo "   PID: $BACKEND_PID"
echo "   Log: $PROJECT_ROOT/logs/backend.log"

# Чекаємо поки Backend запуститься
echo "⏳ Чекаю поки Backend запуститься..."
for i in {1..30}; do
    if curl -s http://localhost:8000/health > /dev/null 2>&1; then
        echo "✅ Backend запущений!"
        break
    fi
    if [ $i -eq 30 ]; then
        echo "❌ Backend не запустився за 30 секунд"
        echo "Лог:"
        tail -20 "$PROJECT_ROOT/logs/backend.log"
        kill $BACKEND_PID
        exit 1
    fi
    sleep 1
done

echo ""

# Запуск Frontend
echo "🟢 Запуск Frontend (port 3000)..."
cd "$PROJECT_ROOT/apps/web"
npm run dev > "$PROJECT_ROOT/logs/frontend.log" 2>&1 &
FRONTEND_PID=$!
echo "   PID: $FRONTEND_PID"
echo "   Log: $PROJECT_ROOT/logs/frontend.log"

# Чекаємо поки Frontend запуститься
echo "⏳ Чекаю поки Frontend запуститься..."
sleep 5

echo ""
echo "================================================"
echo "✅ Сервери запущені!"
echo "================================================"
echo ""
echo "🌐 URLs:"
echo "  Frontend:  http://localhost:3000"
echo "  Backend:   http://localhost:8000"
echo "  API Docs:  http://localhost:8000/docs"
echo "  MinIO UI:  http://localhost:9001"
echo ""
echo "📊 PIDs:"
echo "  Backend:   $BACKEND_PID"
echo "  Frontend:  $FRONTEND_PID"
echo ""
echo "📝 Логи:"
echo "  Backend:   tail -f $PROJECT_ROOT/logs/backend.log"
echo "  Frontend:  tail -f $PROJECT_ROOT/logs/frontend.log"
echo ""
echo "🛑 Для зупинки натисніть Ctrl+C"
echo ""
echo "⏳ Очікування..."

# Тримаємо скрипт запущеним
wait
