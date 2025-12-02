#!/bin/bash

# Скрипт для швидкого запуску гри "Змійка"

echo "🐍 Запуск гри Змійка..."
echo ""

# Перехід до директорії frontend
cd "$(dirname "$0")/../apps/web" || exit 1

# Перевірка Node.js
NODE_VERSION=$(node --version 2>/dev/null)
if [ -z "$NODE_VERSION" ]; then
    echo "❌ Помилка: Node.js не встановлено!"
    echo "Встановіть Node.js 18+ з https://nodejs.org/"
    exit 1
fi

echo "✅ Node.js версія: $NODE_VERSION"
echo ""

# Перевірка залежностей
if [ ! -d "node_modules" ]; then
    echo "📦 Встановлення залежностей..."
    npm install
    echo ""
fi

# Перевірка порту
if lsof -Pi :3000 -sTCP:LISTEN -t >/dev/null 2>&1 ; then
    echo "⚠️  Порт 3000 вже зайнятий!"
    echo "Зупиняю процес на порту 3000..."
    lsof -ti:3000 | xargs kill -9 2>/dev/null
    sleep 2
    echo ""
fi

echo "🚀 Запуск dev сервера..."
echo "📍 Гра буде доступна на: http://localhost:3000/snake"
echo ""
echo "Натисніть Ctrl+C для зупинки"
echo ""

# Запуск dev сервера
npm run dev

