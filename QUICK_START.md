# 🚀 Швидкий запуск AI TESI

## Крок 1: Створіть .env для Backend

Створіть файл `apps/api/.env` з таким вмістом:

```bash
# Environment
ENVIRONMENT=development
DEBUG=True

# Security - ОБОВ'ЯЗКОВО змініть!
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

# CORS
ALLOWED_ORIGINS=["http://localhost:3000","http://127.0.0.1:3000"]
ALLOWED_HOSTS=["localhost","127.0.0.1","0.0.0.0"]
```

## Крок 2: Створіть .env для Frontend

Створіть файл `apps/web/.env.local` з таким вмістом:

```bash
NEXT_PUBLIC_API_URL=http://localhost:8000
```

## Крок 3: Запустіть Backend

```bash
cd "/Users/maxmaxvel/AI TESI/apps/api"

# Активуйте virtualenv (якщо є)
source venv/bin/activate

# Або створіть новий
# python -m venv venv
# source venv/bin/activate

# Встановіть залежності (якщо ще не встановлені)
pip install -r requirements.txt

# Запустіть сервер
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

**Очікуваний результат:**

```
INFO:     Uvicorn running on http://0.0.0.0:8000
INFO:     Application startup complete.
```

## Крок 4: Запустіть Frontend (в НОВОМУ терміналі)

```bash
cd "/Users/maxmaxvel/AI TESI/apps/web"

# Встановіть залежності (якщо ще не встановлені)
npm install

# Запустіть dev сервер
npm run dev
```

**Очікуваний результат:**

```
ready - started server on 0.0.0.0:3000
```

## 🧪 Перевірка

### 1. Перевірте Backend (http://localhost:8000)

```bash
# Health check
curl http://localhost:8000/health

# Очікувана відповідь:
# {"status":"healthy","version":"1.0.0","environment":"development"}
```

### 2. Перевірте API Docs

Відкрийте в браузері: http://localhost:8000/docs

### 3. Перевірте Frontend

Відкрийте в браузері: http://localhost:3000

## ⚠️ Можливі помилки

### Backend не запускається

**Помилка: "SECRET_KEY must be set"**

```bash
# Перевірте що .env файл існує
ls apps/api/.env

# Перевірте вміст
cat apps/api/.env | grep SECRET_KEY
```

**Помилка: "Failed to connect to database"**

```bash
# Перевірте що PostgreSQL запущений
docker ps | grep postgres

# Або перезапустіть
cd infra/docker
docker-compose restart postgres
```

**Помилка: "Module not found"**

```bash
# Перевстановіть залежності
pip install -r requirements.txt
```

### Frontend не запускається

**Помилка: "Cannot find module"**

```bash
# Видаліть node_modules та перевстановіть
rm -rf node_modules package-lock.json
npm install
```

**Помилка: "Port 3000 already in use"**

```bash
# Використайте інший порт
PORT=3001 npm run dev
```

## 📝 Корисні команди

### Перевірка Docker контейнерів

```bash
cd "/Users/maxmaxvel/AI TESI/infra/docker"
docker-compose ps
```

### Логи контейнерів

```bash
docker-compose logs postgres
docker-compose logs redis
docker-compose logs minio
```

### Перезапуск інфраструктури

```bash
docker-compose down
docker-compose up -d postgres redis minio minio-setup
```

## 🎯 Швидка команда (все разом)

Якщо shell працює нормально:

```bash
# Термінал 1: Backend
cd "/Users/maxmaxvel/AI TESI/apps/api" && \
source venv/bin/activate && \
uvicorn main:app --reload

# Термінал 2: Frontend (в новому вікні)
cd "/Users/maxmaxvel/AI TESI/apps/web" && \
npm run dev
```

## ✅ Успішний запуск

Якщо все запустилось:

- ✅ Backend: http://localhost:8000
- ✅ API Docs: http://localhost:8000/docs
- ✅ Frontend: http://localhost:3000
- ✅ PostgreSQL: localhost:5432
- ✅ Redis: localhost:6379
- ✅ MinIO: http://localhost:9001

**Проект готовий до роботи!** 🚀
