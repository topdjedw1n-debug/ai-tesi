#!/bin/bash
# AWS EC2 Server Setup Script for TesiGo Platform
# Скопіюйте цей скрипт на сервер та запустіть: bash aws-server-setup.sh

set -e  # Зупинитися при помилці

echo "🚀 Початок встановлення TesiGo Platform на AWS EC2..."
echo ""

# Оновлення системи
echo "📦 Оновлення системних пакетів..."
sudo apt-get update
sudo apt-get upgrade -y

# Встановлення базових утиліт
echo "📦 Встановлення базових утиліт..."
sudo apt-get install -y \
    curl \
    wget \
    git \
    nano \
    unzip \
    ca-certificates \
    gnupg \
    lsb-release

# Встановлення Docker
echo "🐳 Встановлення Docker..."
if ! command -v docker &> /dev/null; then
    curl -fsSL https://get.docker.com -o get-docker.sh
    sudo sh get-docker.sh
    rm get-docker.sh
    echo "✅ Docker встановлено"
else
    echo "✅ Docker вже встановлено"
fi

# Додавання користувача ubuntu до групи docker
echo "👤 Додавання користувача до групи docker..."
sudo usermod -aG docker ubuntu || echo "⚠️  Користувач вже в групі docker"

# Встановлення Docker Compose
echo "🐳 Встановлення Docker Compose..."
if ! command -v docker compose &> /dev/null; then
    sudo apt-get install -y docker-compose-plugin
    echo "✅ Docker Compose встановлено"
else
    echo "✅ Docker Compose вже встановлено"
fi

# Встановлення додаткових залежностей для Python (якщо потрібно)
echo "🐍 Встановлення Python залежностей..."
sudo apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    build-essential \
    libpq-dev

# Налаштування firewall
echo "🔥 Налаштування firewall..."
sudo ufw --force enable || echo "⚠️  UFW вже налаштовано"
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
echo "✅ Firewall налаштовано"

# Створення робочої директорії
echo "📁 Створення робочої директорії..."
mkdir -p ~/tesigo-platform
cd ~/tesigo-platform

# Перевірка встановлення
echo ""
echo "🔍 Перевірка встановлення..."
echo ""

if command -v docker &> /dev/null; then
    DOCKER_VERSION=$(docker --version)
    echo "✅ Docker: $DOCKER_VERSION"
else
    echo "❌ Docker не встановлено"
fi

if command -v docker compose &> /dev/null; then
    COMPOSE_VERSION=$(docker compose version)
    echo "✅ Docker Compose: $COMPOSE_VERSION"
else
    echo "❌ Docker Compose не встановлено"
fi

if command -v git &> /dev/null; then
    GIT_VERSION=$(git --version)
    echo "✅ Git: $GIT_VERSION"
else
    echo "❌ Git не встановлено"
fi

# Тест Docker
echo ""
echo "🧪 Тестування Docker..."
sudo docker run --rm hello-world > /dev/null 2>&1 && echo "✅ Docker працює правильно" || echo "⚠️  Проблема з Docker"

echo ""
echo "✨ Встановлення завершено!"
echo ""
echo "📋 Наступні кроки:"
echo "1. Встановіть права для docker (вийдіть і зайдіть знову через SSH)"
echo "2. Клонуйте репозиторій: git clone <your-repo-url> ~/tesigo-platform"
echo "3. Налаштуйте .env файл"
echo "4. Запустіть: docker compose -f docker-compose.prod.yml up -d"
echo ""
echo "💡 Щоб застосувати зміни групи docker, виконайте:"
echo "   exit"
echo "   (підключіться знову через SSH)"
echo ""
