# 7️⃣ ПЕРЕВІРКА API ENDPOINTS (Ручна)

> **Категорія:** Manual API Testing
> **Час виконання:** ~20-30 хвилин
> **Залежності:** Backend running + Infrastructure
> **Критичність:** 🔴 ВИСОКА - Фактична перевірка роботи API

---

## 🎯 МЕТА ПЕРЕВІРКИ

Вручну протестувати всі критичні API endpoints з реальними HTTP запитами, імітуючи поведінку реального користувача/frontend.

**Що тестуємо:**
- ✅ Authentication flow (magic link → verify → JWT)
- ✅ Documents CRUD (create, read, update, delete)
- ✅ Generation API (start generation, track progress)
- ✅ Payment API (Stripe integration)
- ✅ Admin API (dashboard, management)
- ✅ Error responses (401, 403, 404, 422, 500)

---

## ✅ ПЕРЕДУМОВИ

- [ ] Backend запущено на `localhost:8000`
- [ ] PostgreSQL/Redis running
- [ ] `curl` або `httpie` встановлено
- [ ] `jq` для парсингу JSON (опціонально)

---

## 📋 ПОКРОКОВА ІНСТРУКЦІЯ

### Крок 1: Health Check

**Базова перевірка:**
```bash
curl -s http://localhost:8000/health | jq
```

**Очікуваний результат:**
```json
{
  "status": "healthy",
  "database": "connected",
  "redis": "connected",
  "version": "2.3.0"
}
```

---

### Крок 2: Authentication - Request Magic Link

**Команда:**
```bash
curl -X POST http://localhost:8000/api/v1/auth/magic-link \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com"
  }' | jq
```

**Очікуваний результат:**
```json
{
  "message": "Magic link sent to email",
  "email": "test@example.com"
}
```

**Перевірка помилок:**
```bash
# Невалідний email
curl -X POST http://localhost:8000/api/v1/auth/magic-link \
  -H "Content-Type: application/json" \
  -d '{"email": "not-an-email"}' | jq

# Очікується: 422 Validation Error
```

---

### Крок 3: Authentication - Verify Token (Mock)

**Отримати test token:**
```bash
# В реальності token приходить на email
# Для тесту можна створити через admin або використати test endpoint
TEST_TOKEN="test-magic-token-123"

curl -X POST http://localhost:8000/api/v1/auth/verify \
  -H "Content-Type: application/json" \
  -d "{
    \"token\": \"$TEST_TOKEN\"
  }" | jq
```

**Очікуваний результат:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

**Зберегти токен:**
```bash
ACCESS_TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/verify \
  -H "Content-Type: application/json" \
  -d '{"token": "test-token"}' | jq -r '.access_token')

echo "Token: $ACCESS_TOKEN"
```

---

### Крок 4: Protected Endpoint Test

**Без токену (401):**
```bash
curl -s http://localhost:8000/api/v1/documents | jq
```

**Очікується:**
```json
{
  "detail": "Not authenticated"
}
```

**З токеном (200):**
```bash
curl -s http://localhost:8000/api/v1/documents \
  -H "Authorization: Bearer $ACCESS_TOKEN" | jq
```

---

### Крок 5: Documents - Create

**Команда:**
```bash
curl -X POST http://localhost:8000/api/v1/documents \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Test Document",
    "topic": "AI in Healthcare",
    "language": "en",
    "target_pages": 10,
    "work_type": "thesis"
  }' | jq
```

**Очікуваний результат:**
```json
{
  "id": 1,
  "title": "Test Document",
  "topic": "AI in Healthcare",
  "language": "en",
  "target_pages": 10,
  "status": "draft",
  "created_at": "2025-12-03T10:00:00Z"
}
```

**Зберегти document ID:**
```bash
DOC_ID=$(curl -s -X POST http://localhost:8000/api/v1/documents \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"title": "Test", "topic": "AI", "language": "en", "target_pages": 5}' \
  | jq -r '.id')

echo "Document ID: $DOC_ID"
```

---

### Крок 6: Documents - Get

**Команда:**
```bash
curl -s http://localhost:8000/api/v1/documents/$DOC_ID \
  -H "Authorization: Bearer $ACCESS_TOKEN" | jq
```

**Очікуваний результат:**
```json
{
  "id": 1,
  "title": "Test Document",
  "status": "draft",
  ...
}
```

**Test IDOR (спроба отримати чужий документ):**
```bash
# Спробувати отримати документ з ID=999 (не існує або чужий)
curl -s http://localhost:8000/api/v1/documents/999 \
  -H "Authorization: Bearer $ACCESS_TOKEN" | jq

# Очікується: 404 або 403
```

---

### Крок 7: Documents - Update

**Команда:**
```bash
curl -X PATCH http://localhost:8000/api/v1/documents/$DOC_ID \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Updated Title",
    "target_pages": 15
  }' | jq
```

**Очікуваний результат:**
```json
{
  "id": 1,
  "title": "Updated Title",
  "target_pages": 15,
  "updated_at": "2025-12-03T10:05:00Z"
}
```

---

### Крок 8: Documents - List

**Команда:**
```bash
curl -s http://localhost:8000/api/v1/documents \
  -H "Authorization: Bearer $ACCESS_TOKEN" | jq
```

**Очікуваний результат:**
```json
{
  "items": [
    {
      "id": 1,
      "title": "Test Document",
      ...
    }
  ],
  "total": 1,
  "page": 1,
  "per_page": 50
}
```

---

### Крок 9: Generation - Start

**Команда:**
```bash
curl -X POST http://localhost:8000/api/v1/generate \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"document_id\": $DOC_ID
  }" | jq
```

**Очікуваний результат:**
```json
{
  "job_id": 1,
  "status": "queued",
  "document_id": 1,
  "message": "Generation started"
}
```

**Зберегти job ID:**
```bash
JOB_ID=$(curl -s -X POST http://localhost:8000/api/v1/generate \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"document_id\": $DOC_ID}" | jq -r '.job_id')
```

---

### Крок 10: Generation - Check Status

**Команда:**
```bash
curl -s http://localhost:8000/api/v1/jobs/$JOB_ID \
  -H "Authorization: Bearer $ACCESS_TOKEN" | jq
```

**Очікуваний результат:**
```json
{
  "id": 1,
  "status": "running",
  "progress": 45,
  "current_stage": "Generating section 2 of 5",
  "estimated_time_remaining": 180
}
```

**Polling loop:**
```bash
while true; do
  STATUS=$(curl -s http://localhost:8000/api/v1/jobs/$JOB_ID \
    -H "Authorization: Bearer $ACCESS_TOKEN" | jq -r '.status')

  echo "Status: $STATUS"

  if [ "$STATUS" = "completed" ] || [ "$STATUS" = "failed" ]; then
    break
  fi

  sleep 5
done
```

---

### Крок 11: Payment - Create Intent

**Команда:**
```bash
curl -X POST http://localhost:8000/api/v1/payment/create-intent \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"document_id\": $DOC_ID,
    \"pages\": 10
  }" | jq
```

**Очікуваний результат:**
```json
{
  "client_secret": "pi_1234567890_secret_abcdef",
  "amount": 500,
  "currency": "eur",
  "payment_intent_id": "pi_1234567890"
}
```

---

### Крок 12: Admin - Login

**Команда:**
```bash
curl -X POST http://localhost:8000/api/v1/admin/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "admin@tesigo.com",
    "password": "admin123"
  }' | jq
```

**Очікуваний результат:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "is_admin": true
}
```

**Зберегти admin token:**
```bash
ADMIN_TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/admin/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@tesigo.com", "password": "admin123"}' \
  | jq -r '.access_token')
```

---

### Крок 13: Admin - Dashboard Stats

**Команда:**
```bash
curl -s http://localhost:8000/api/v1/admin/dashboard \
  -H "Authorization: Bearer $ADMIN_TOKEN" | jq
```

**Очікуваний результат:**
```json
{
  "total_users": 15,
  "total_documents": 42,
  "total_revenue": 1250.50,
  "active_jobs": 3,
  "completed_today": 8
}
```

---

### Крок 14: Rate Limiting Test

**Команда:**
```bash
# Відправити 101 запит швидко (ліміт 100/min)
for i in {1..101}; do
  RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/health)
  echo "Request $i: $RESPONSE"

  if [ "$RESPONSE" = "429" ]; then
    echo "✅ Rate limit enforced at request $i"
    break
  fi
done
```

**Очікуваний результат:**
```
Request 100: 200
Request 101: 429  # Too Many Requests
✅ Rate limit enforced
```

---

### Крок 15: Error Responses Test

**404 Not Found:**
```bash
curl -s http://localhost:8000/api/v1/nonexistent | jq
# Очікується: {"detail": "Not Found"}
```

**422 Validation Error:**
```bash
curl -X POST http://localhost:8000/api/v1/documents \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"title": ""}' | jq  # Empty title
# Очікується: 422 з деталями validation errors
```

**500 Internal Server Error (симуляція):**
```bash
# Якщо є test endpoint для trigger 500
curl -s http://localhost:8000/api/v1/test/error-500 | jq
```

---

## 🔍 ПЕРЕВІРКА РЕЗУЛЬТАТІВ

### Чеклист успішного проходження:

**Authentication:**
- [ ] Magic link request працює (200)
- [ ] Token verification працює (200 + JWT)
- [ ] Protected endpoints блокують без токену (401)

**Documents CRUD:**
- [ ] Create document (201)
- [ ] Get document (200)
- [ ] Update document (200)
- [ ] List documents (200)
- [ ] IDOR protection працює (404/403 для чужих)

**Generation:**
- [ ] Start generation (202 + job_id)
- [ ] Check job status (200 + progress)

**Payment:**
- [ ] Create payment intent (200 + client_secret)

**Admin:**
- [ ] Admin login (200 + token)
- [ ] Dashboard stats (200 + data)

**Error Handling:**
- [ ] 401 для unauthorized
- [ ] 404 для не існуючих ресурсів
- [ ] 422 для validation errors
- [ ] 429 для rate limit exceed

---

## ⚠️ ТИПОВІ ПОМИЛКИ ТА РІШЕННЯ

| Помилка | Причина | Рішення |
|---------|---------|---------|
| `Connection refused` | Backend не запущено | `uvicorn main:app` |
| `401 Unauthorized` | Токен прострочений | Отримати новий токен |
| `404 Not Found` | Неправильний endpoint | Перевірити `/docs` |
| `500 Internal Server Error` | Backend crash | Перевірити `logs/app.log` |
| `CORS error` (browser) | CORS не налаштовано | Додати origin в settings |

---

## 📊 КРИТЕРІЇ УСПІШНОСТІ

### ✅ ТЕСТ ПРОЙДЕНО ЯКЩО:

- Всі auth endpoints працюють
- CRUD операції успішні
- IDOR protection активна
- Rate limiting працює
- Error responses правильні (коректні HTTP коди)
- Admin endpoints доступні з admin токеном

### ❌ ТЕСТ ПРОВАЛЕНО ЯКЩО:

- Auth flow broken
- IDOR vulnerability (можна отримати чужі дані)
- Rate limiting не працює
- 500 errors на валідних запитах
- Admin endpoints доступні без auth

---

## 🔗 ЗВ'ЯЗОК З ІНШИМИ ПЕРЕВІРКАМИ

**⬆️ Залежить від:**
- `03_BACKEND_CHECK.md` - Backend running

**⬇️ Впливає на:**
- `08_FRONTEND_CHECK.md` - Frontend використовує ці API
- `09_E2E_TESTS_CHECK.md` - E2E flows

**Критичність:** 🔴 ВИСОКА - це реальна функціональність!

---

## 🚀 ШВИДКИЙ СТАРТ

```bash
# Quick API check script
curl -s http://localhost:8000/health | jq '.status' && \
curl -s http://localhost:8000/ | jq '.message' && \
echo "✅ API endpoints responding"
```

---

**Дата створення:** 2025-12-03
**Версія:** 1.0
**Автор:** AI Assistant
**Попередня перевірка:** `06_INTEGRATION_TESTS_CHECK.md`
**Наступна перевірка:** `08_FRONTEND_CHECK.md`
