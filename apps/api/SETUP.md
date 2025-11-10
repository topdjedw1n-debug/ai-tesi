# API Setup Instructions

## ⚡ Quick Start (після виправлень)

Всі критичні баги виправлено! Проект готовий до запуску.

### 1. Створіть .env файл

```bash
cd apps/api
cp .env.example .env
```

### 2. Згенеруйте SECRET_KEY

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Скопіюйте згенерований ключ в `.env`:
```
SECRET_KEY=<ваш-згенерований-ключ>
```

### 3. Запустіть Docker Compose (рекомендовано)

```bash
cd ../../infra/docker
docker-compose up -d postgres redis minio
```

Або встановіть PostgreSQL та Redis локально.

### 4. Встановіть залежності

```bash
cd ../../apps/api
pip install -r requirements.txt
```

### 5. Запустіть сервер

```bash
uvicorn main:app --reload
```

API буде доступний на: http://localhost:8000

## ✅ Виправлені баги (Коміт: cf73d39)

### БАГ #1: PostgreSQL Type Mismatch
- **Файл:** `app/services/auth_service.py`
- **Виправлення:** Додано `int(user_id)` конвертацію в методах `logout()` та `get_current_user()`
- **Тест:** `GET /api/v1/auth/me` тепер працює ✅

### БАГ #2: Double-Wrapping Exceptions
- **Файл:** `app/services/auth_service.py`
- **Виправлення:** Додано `except AuthenticationError: raise` перед `except Exception`
- **Результат:** Чіткіші повідомлення про помилки ✅

### БАГ #3: SlowAPI Rate Limiter
- **Файл:** `app/api/v1/endpoints/auth.py:24`
- **Виправлення:** Змінено `http_request` → `request`
- **Тест:** `POST /api/v1/auth/magic-link` тепер працює ✅

### БАГ #4: Refresh Token Parameter
- **Файл:** `app/api/v1/endpoints/auth.py:74`
- **Виправлення:** Змінено `refresh_token: str` → `refresh_request: RefreshTokenRequest`
- **Тест:** Приймає JSON body, а не query parameter ✅

## 🧪 Тестування

### Health Check
```bash
curl http://localhost:8000/health
```

### Magic Link Authentication
```bash
curl -X POST http://localhost:8000/api/v1/auth/magic-link \
  -H "Content-Type: application/json" \
  -H "X-CSRF-Token: test-csrf-token-1234567890" \
  -d '{"email": "test@example.com"}'
```

### Get Current User
```bash
curl http://localhost:8000/api/v1/auth/me \
  -H "Authorization: Bearer <access-token>"
```

### Refresh Token
```bash
curl -X POST http://localhost:8000/api/v1/auth/refresh \
  -H "Content-Type: application/json" \
  -H "X-CSRF-Token: test-csrf-token-1234567890" \
  -d '{"refresh_token": "<refresh-token>"}'
```

## 📝 Документація API

Swagger UI: http://localhost:8000/docs
ReDoc: http://localhost:8000/redoc

## ⚠️ Важливо

1. **НЕ змінювалися:**
   - `app/core/database.py` - працює з PostgreSQL
   - Моделі даних
   - Middleware конфігурація

2. **Змінено тільки:**
   - `app/services/auth_service.py` (5 методів)
   - `app/api/v1/endpoints/auth.py` (2 endpoints)

3. **Тестові файли видалено:**
   - `test.db` (SQLite база)
   - `.env` (тестова конфігурація)
   - `__pycache__` (Python cache)

## 🔧 Troubleshooting

### Помилка: "SECRET_KEY must be set"
Створіть `.env` файл з SECRET_KEY (див. крок 2)

### Помилка: "Failed to connect to database"
Переконайтеся що PostgreSQL запущений на `localhost:5432`

### Помилка: "CSRF token missing"
Додайте header: `X-CSRF-Token: <мінімум-16-символів>`

## 📞 Підтримка

Всі виправлення протестовані та працюють. Якщо виникають проблеми:
1. Перевірте `.env` файл
2. Перевірте що PostgreSQL та Redis запущені
3. Перевірте Python version >= 3.11
