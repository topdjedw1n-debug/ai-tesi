#!/bin/bash
# Скрипт для автоматичного запуску тестів з повною перевіркою
# Використання: ./scripts/run-tests.sh [--all|--smoke|--integration]

set -e  # Зупинитися на першій помилці

cd "$(dirname "$0")/.." || exit 1

# Кольори для виводу
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}=== Запуск тестів AI Thesis Platform ===${NC}"
echo ""

# Перевірка віртуального середовища
if [ ! -d "qa_venv" ]; then
    echo -e "${RED}❌ Помилка: qa_venv не знайдено${NC}"
    echo "Створіть віртуальне середовище: python3 -m venv qa_venv"
    exit 1
fi

# Активувати віртуальне середовище
source qa_venv/bin/activate

# Перейти в директорію API
cd apps/api || exit 1

# Встановити змінні середовища для тестів
export SECRET_KEY="test-secret-key-minimum-32-chars-long-1234567890"
export JWT_SECRET="$SECRET_KEY"
export DATABASE_URL="sqlite+aiosqlite:///./test.db"
export REDIS_URL="redis://localhost:6379/0"
export ENVIRONMENT="test"
export DISABLE_RATE_LIMIT="true"
export CORS_ALLOWED_ORIGINS="http://localhost:3000,http://127.0.0.1:3000"

# Визначити тип тестів
TEST_TYPE="${1:---all}"

case "$TEST_TYPE" in
    --smoke)
        echo -e "${YELLOW}Запуск smoke тестів...${NC}"
        pytest tests/ -m smoke -v --tb=short
        ;;
    --integration)
        echo -e "${YELLOW}Запуск integration тестів...${NC}"
        pytest tests/integration/ -v --tb=short
        ;;
    --all|*)
        echo -e "${YELLOW}Запуск всіх тестів...${NC}"
        pytest tests/ --ignore=tests/integration -v --tb=short
        ;;
esac

TEST_EXIT_CODE=$?

echo ""
if [ $TEST_EXIT_CODE -eq 0 ]; then
    echo -e "${GREEN}✅ Всі тести пройшли успішно!${NC}"
else
    echo -e "${RED}❌ Деякі тести не пройшли (exit code: $TEST_EXIT_CODE)${NC}"
    echo -e "${YELLOW}Перевірте вивід вище для деталей${NC}"
fi

exit $TEST_EXIT_CODE

