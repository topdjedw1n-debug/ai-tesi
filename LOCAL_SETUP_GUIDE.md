# 🚀 Інструкція з локального розгортання проекту

## ✅ Що вже зроблено

1. ✅ Створено файли конфігурації:
   - `apps/api/.env` - налаштування backend
   - `apps/web/.env.local` - налаштування frontend

2. ✅ Запущено інфраструктурні сервіси через Docker:
   - PostgreSQL (порт 5432)
   - Redis (порт 6379)
   - MinIO (порти 9000, 9001)

3. ✅ Встановлено залежності backend (Python)

## 📋 Поточний статус

### Інфраструктура (Docker)
```bash
cd infra/docker
docker-compose ps
```

Всі сервіси повинні показувати статус `healthy`:
- ✅ PostgreSQL: `localhost:5432`
- ✅ Redis: `localhost:6379`
- ✅ MinIO: `http://localhost:9000` (API), `http://localhost:9001` (Console)

**Облікові дані MinIO:**
- Логін: `minioadmin`
- Пароль: `minioadmin`

### Backend (Python/FastAPI)

**Залежності встановлено:** ✅

**Для запуску backend:**

```bash
cd apps/api
source venv/bin/activate
uvicorn main:app --reload
```

Backend буде доступний на: `http://localhost:8000`
API документація: `http://localhost:8000/docs`

### Frontend (Next.js)

**⚠️ УВАГА:** Потрібен Node.js версії 18+ (зараз встановлено 14.15.4)

**Варіанти запуску frontend:**

#### Варіант 1: Оновлення Node.js (рекомендовано для розробки)

Встановіть Node.js 18 або новіше:
- Через Homebrew: `brew install node@18`
- Або завантажте з [nodejs.org](https://nodejs.org/)

Після оновлення:
```bash
cd apps/web
npm install
npm run dev
```

Frontend буде доступний на: `http://localhost:3000`

#### Варіант 2: Запуск через Docker (для швидкого старту)

```bash
cd infra/docker
docker-compose up web -d
```

Frontend буде доступний на: `http://localhost:3000`

#### Варіант 3: Запуск всього через Docker

```bash
cd infra/docker
docker-compose up api web -d
```

Це запустить і backend, і frontend в Docker контейнерах.

## 🎯 Швидкий старт (рекомендовано)

### 1. Запустити backend локально:

```bash
# Термінал 1
cd apps/api
source venv/bin/activate
uvicorn main:app --reload
```

### 2. Запустити frontend:

**Якщо Node.js 18+ встановлено:**
```bash
# Термінал 2
cd apps/web
npm install  # якщо ще не встановлено
npm run dev
```

**Якщо Node.js 18+ НЕ встановлено - використовуйте Docker:**
```bash
# Термінал 2
cd infra/docker
docker-compose up web -d
```

### 3. Перевірити доступність:

- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs
- MinIO Console: http://localhost:9001

## ⚙️ Налаштування

### Додати API ключі для AI провайдерів

Відредагуйте `apps/api/.env` та додайте ваші ключі:

```env
OPENAI_API_KEY=your-openai-api-key
ANTHROPIC_API_KEY=your-anthropic-api-key
```

**⚠️ Без цих ключів генерація документів не працюватиме!**

### Перевірка підключення до бази даних

Backend автоматично підключається до PostgreSQL при запуску. Якщо виникають проблеми:

```bash
# Перевірте, чи запущений контейнер PostgreSQL
cd infra/docker
docker-compose ps postgres

# Перевірте логи, якщо є проблеми
docker-compose logs postgres
```

## 🛠️ Корисні команди

### Перезапуск інфраструктури
```bash
cd infra/docker
docker-compose restart
```

### Зупинка всіх сервісів
```bash
cd infra/docker
docker-compose down
```

### Перегляд логів
```bash
cd infra/docker
docker-compose logs -f [service-name]
# Приклади: postgres, redis, minio, api, web
```

### Перезапуск одного сервісу
```bash
cd infra/docker
docker-compose restart [service-name]
```

## 📝 Структура проекту

```
AI TESI/
├── apps/
│   ├── api/          # FastAPI backend
│   │   ├── .env      # Конфігурація backend
│   │   ├── venv/     # Python virtual environment
│   │   └── main.py   # Точка входу
│   └── web/          # Next.js frontend
│       ├── .env.local # Конфігурація frontend
│       └── package.json
└── infra/docker/
    └── docker-compose.yml # Docker конфігурація
```

## ❓ Вирішення проблем

### Проблема: "Cannot connect to Docker daemon"
**Рішення:** Запустіть Docker Desktop

### Проблема: "Port already in use"
**Рішення:** 
```bash
# Знайдіть процес на порту
lsof -i :8000  # для backend
lsof -i :3000  # для frontend
lsof -i :5432  # для PostgreSQL

# Зупиніть процес або змініть порт в конфігурації
```

### Проблема: "Node version not compatible"
**Рішення:** Оновіть Node.js до версії 18+ або використовуйте Docker для frontend

### Проблема: Backend не може підключитись до бази
**Рішення:**
1. Перевірте, чи запущений PostgreSQL: `docker-compose ps postgres`
2. Перевірте DATABASE_URL в `apps/api/.env`
3. Перезапустіть backend

## 🎉 Готово!

Тепер ви можете:
1. Відкрити http://localhost:3000 для frontend
2. Використовувати API на http://localhost:8000
3. Переглянути документацію API на http://localhost:8000/docs

**Приємної роботи! 🚀**

