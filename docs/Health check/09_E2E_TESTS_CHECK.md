# 9️⃣ ПЕРЕВІРКА E2E ТЕСТІВ (End-to-End)

> **Категорія:** Automated Testing - E2E
> **Час виконання:** ~20-30 хвилин
> **Залежності:** Full stack running (Frontend + Backend + Infrastructure)
> **Критичність:** 🔴 ВИСОКА - Тестує реальні user flows

---

## 🎯 МЕТА ПЕРЕВІРКИ

Протестувати повні користувацькі сценарії від початку до кінця, імітуючи реальну поведінку користувача.

**Критичні flows:**
- ✅ Registration → Login → Dashboard
- ✅ Create Document → Generate → Download
- ✅ Payment flow → Stripe → Access
- ✅ Admin login → Dashboard → Management

---

## ✅ ПЕРЕДУМОВИ

- [ ] Frontend running (`localhost:3000`)
- [ ] Backend running (`localhost:8000`)
- [ ] Infrastructure (PostgreSQL, Redis, MinIO)
- [ ] Stripe test mode active
- [ ] Email service configured (або mock)

---

## 📋 ПОКРОКОВА ІНСТРУКЦІЯ

### Крок 1: User Registration & Login Flow

**Scenario:** Новий користувач реєструється та логінитьсся

**Кроки (manual або automated):**
```bash
# 1. Request magic link
curl -X POST http://localhost:8000/api/v1/auth/magic-link \
  -H "Content-Type: application/json" \
  -d '{"email": "e2e-test@example.com"}' | jq

# Очікується: 200 + "Magic link sent"

# 2. Отримати test token (в реальності з email)
# Для E2E використовуємо test endpoint або mock
TEST_TOKEN="test-magic-link-$(date +%s)"

# 3. Verify token
ACCESS_TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/verify \
  -H "Content-Type: application/json" \
  -d "{\"token\": \"$TEST_TOKEN\"}" | jq -r '.access_token')

# 4. Access dashboard
curl -s http://localhost:8000/api/v1/documents \
  -H "Authorization: Bearer $ACCESS_TOKEN" | jq

# Очікується: 200 + empty list (новий користувач)
```

**Success criteria:**
- ✅ Magic link sent (200)
- ✅ Token verified (200 + JWT)
- ✅ Dashboard accessible з токеном

---

### Крок 2: Document Creation Flow

**Scenario:** Користувач створює новий документ

**Script:**
```bash
# 1. Create document
DOC_RESPONSE=$(curl -s -X POST http://localhost:8000/api/v1/documents \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "E2E Test Document",
    "topic": "Artificial Intelligence in Healthcare",
    "language": "en",
    "target_pages": 10,
    "work_type": "thesis"
  }')

DOC_ID=$(echo $DOC_RESPONSE | jq -r '.id')
echo "✅ Document created: ID=$DOC_ID"

# 2. Verify document exists
curl -s http://localhost:8000/api/v1/documents/$DOC_ID \
  -H "Authorization: Bearer $ACCESS_TOKEN" | jq '.title'

# Очікується: "E2E Test Document"

# 3. Update document
curl -s -X PATCH http://localhost:8000/api/v1/documents/$DOC_ID \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"target_pages": 15}' | jq '.target_pages'

# Очікується: 15
```

**Success criteria:**
- ✅ Document created (201)
- ✅ Document retrievable (200)
- ✅ Document updatable (200)

---

### Крок 3: Payment → Generation Flow

**Scenario:** Користувач оплачує та запускає генерацію

**Script:**
```bash
# 1. Create payment intent
PAYMENT_RESPONSE=$(curl -s -X POST http://localhost:8000/api/v1/payment/create-intent \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"document_id\": $DOC_ID,
    \"pages\": 10
  }")

CLIENT_SECRET=$(echo $PAYMENT_RESPONSE | jq -r '.client_secret')
PAYMENT_INTENT_ID=$(echo $PAYMENT_RESPONSE | jq -r '.payment_intent_id')

echo "✅ Payment intent created: $PAYMENT_INTENT_ID"

# 2. Simulate Stripe payment success (test webhook)
curl -X POST http://localhost:8000/api/v1/payment/webhook \
  -H "Content-Type: application/json" \
  -H "Stripe-Signature: test-signature" \
  -d "{
    \"type\": \"payment_intent.succeeded\",
    \"data\": {
      \"object\": {
        \"id\": \"$PAYMENT_INTENT_ID\",
        \"status\": \"succeeded\",
        \"metadata\": {
          \"document_id\": \"$DOC_ID\"
        }
      }
    }
  }"

echo "✅ Payment webhook processed"

# 3. Verify payment recorded
sleep 2
curl -s http://localhost:8000/api/v1/payment/history \
  -H "Authorization: Bearer $ACCESS_TOKEN" | jq '.[0].status'

# Очікується: "completed"

# 4. Check generation started
curl -s http://localhost:8000/api/v1/jobs?document_id=$DOC_ID \
  -H "Authorization: Bearer $ACCESS_TOKEN" | jq '.[0].status'

# Очікується: "queued" або "running"
```

**Success criteria:**
- ✅ Payment intent created
- ✅ Webhook processed (200)
- ✅ Payment recorded in history
- ✅ Generation auto-started

---

### Крок 4: Generation Progress Tracking

**Scenario:** Відстеження прогресу генерації

**Script:**
```bash
# 1. Get job ID
JOB_ID=$(curl -s http://localhost:8000/api/v1/jobs?document_id=$DOC_ID \
  -H "Authorization: Bearer $ACCESS_TOKEN" | jq -r '.[0].id')

echo "Tracking job: $JOB_ID"

# 2. Poll job status
MAX_ATTEMPTS=60  # 5 хвилин (60 * 5s)
ATTEMPT=0

while [ $ATTEMPT -lt $MAX_ATTEMPTS ]; do
  JOB_STATUS=$(curl -s http://localhost:8000/api/v1/jobs/$JOB_ID \
    -H "Authorization: Bearer $ACCESS_TOKEN")

  STATUS=$(echo $JOB_STATUS | jq -r '.status')
  PROGRESS=$(echo $JOB_STATUS | jq -r '.progress')

  echo "[$ATTEMPT] Status: $STATUS, Progress: $PROGRESS%"

  if [ "$STATUS" = "completed" ]; then
    echo "✅ Generation completed"
    break
  elif [ "$STATUS" = "failed" ]; then
    echo "❌ Generation failed"
    echo $JOB_STATUS | jq '.error'
    exit 1
  fi

  sleep 5
  ATTEMPT=$((ATTEMPT + 1))
done

if [ $ATTEMPT -eq $MAX_ATTEMPTS ]; then
  echo "⚠️ Timeout: Generation took > 5 min"
fi
```

**Success criteria:**
- ✅ Job status transitions: queued → running → completed
- ✅ Progress updates (0% → 100%)
- ✅ Completes within reasonable time (< 5 min for test doc)

---

### Крок 5: Document Download Flow

**Scenario:** Користувач скачує згенерований документ

**Script:**
```bash
# 1. Verify document completed
DOC_STATUS=$(curl -s http://localhost:8000/api/v1/documents/$DOC_ID \
  -H "Authorization: Bearer $ACCESS_TOKEN" | jq -r '.status')

if [ "$DOC_STATUS" != "completed" ]; then
  echo "❌ Document not completed: $DOC_STATUS"
  exit 1
fi

echo "✅ Document status: completed"

# 2. Download DOCX
curl -s http://localhost:8000/api/v1/documents/$DOC_ID/download?format=docx \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -o /tmp/e2e-test-document.docx

# 3. Verify file downloaded
if [ -f /tmp/e2e-test-document.docx ]; then
  FILE_SIZE=$(stat -f%z /tmp/e2e-test-document.docx 2>/dev/null || stat -c%s /tmp/e2e-test-document.docx)
  echo "✅ DOCX downloaded: $FILE_SIZE bytes"

  # Перевірити що це справді DOCX (magic bytes)
  FILE_TYPE=$(file /tmp/e2e-test-document.docx)
  echo "File type: $FILE_TYPE"

  if echo $FILE_TYPE | grep -q "Microsoft Word"; then
    echo "✅ Valid DOCX file"
  else
    echo "❌ Invalid file format"
    exit 1
  fi
else
  echo "❌ Download failed"
  exit 1
fi

# 4. Download PDF
curl -s http://localhost:8000/api/v1/documents/$DOC_ID/download?format=pdf \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -o /tmp/e2e-test-document.pdf

# 5. Verify PDF
if [ -f /tmp/e2e-test-document.pdf ]; then
  FILE_SIZE=$(stat -f%z /tmp/e2e-test-document.pdf 2>/dev/null || stat -c%s /tmp/e2e-test-document.pdf)
  echo "✅ PDF downloaded: $FILE_SIZE bytes"

  FILE_TYPE=$(file /tmp/e2e-test-document.pdf)
  if echo $FILE_TYPE | grep -q "PDF"; then
    echo "✅ Valid PDF file"
  else
    echo "❌ Invalid PDF format"
    exit 1
  fi
fi

# Cleanup
rm -f /tmp/e2e-test-document.{docx,pdf}
```

**Success criteria:**
- ✅ Document status = "completed"
- ✅ DOCX download successful (valid file)
- ✅ PDF download successful (valid file)
- ✅ Files > 0 bytes

---

### Крок 6: Admin Flow

**Scenario:** Адмін логінитьcя та переглядає статистику

**Script:**
```bash
# 1. Admin login
ADMIN_TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/admin/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@tesigo.com", "password": "admin123"}' \
  | jq -r '.access_token')

if [ "$ADMIN_TOKEN" = "null" ] || [ -z "$ADMIN_TOKEN" ]; then
  echo "❌ Admin login failed"
  exit 1
fi

echo "✅ Admin logged in"

# 2. Get dashboard stats
STATS=$(curl -s http://localhost:8000/api/v1/admin/dashboard \
  -H "Authorization: Bearer $ADMIN_TOKEN")

echo "Admin Dashboard:"
echo $STATS | jq '{
  total_users,
  total_documents,
  total_revenue,
  active_jobs
}'

# 3. List users
USERS=$(curl -s http://localhost:8000/api/v1/admin/users \
  -H "Authorization: Bearer $ADMIN_TOKEN" | jq 'length')

echo "✅ Total users: $USERS"

# 4. List documents
DOCS=$(curl -s http://localhost:8000/api/v1/admin/documents \
  -H "Authorization: Bearer $ADMIN_TOKEN" | jq 'length')

echo "✅ Total documents: $DOCS"
```

**Success criteria:**
- ✅ Admin login successful
- ✅ Dashboard stats accessible
- ✅ Users list accessible
- ✅ Documents list accessible

---

### Крок 7: Refund Request Flow

**Scenario:** Користувач запитує refund

**Script:**
```bash
# 1. Request refund
REFUND_RESPONSE=$(curl -s -X POST http://localhost:8000/api/v1/refunds/request \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"payment_id\": 1,
    \"reason\": \"E2E test refund request\"
  }")

REFUND_ID=$(echo $REFUND_RESPONSE | jq -r '.id')
echo "✅ Refund requested: ID=$REFUND_ID"

# 2. Admin reviews refund
curl -s -X POST http://localhost:8000/api/v1/admin/refunds/$REFUND_ID/approve \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"admin_note": "E2E test approval"}' | jq '.status'

# Очікується: "approved"

echo "✅ Refund approved by admin"
```

**Success criteria:**
- ✅ Refund request created
- ✅ Admin can approve
- ✅ Status updates correctly

---

### Крок 8: Full E2E Test Suite (Automated)

**Якщо є pytest-based E2E tests:**
```bash
cd /Users/maxmaxvel/.claude-worktrees/AI\ TESI/stupefied-fermat/apps/api

# Run E2E tests
pytest tests/e2e/ -v --tb=short

# Або specific test
pytest tests/test_e2e_full_flow.py -v
```

---

### Крок 9: Cleanup

**Після E2E тестів:**
```bash
# Видалити тестові дані
curl -X DELETE http://localhost:8000/api/v1/documents/$DOC_ID \
  -H "Authorization: Bearer $ACCESS_TOKEN"

echo "✅ Test document deleted"

# Логаут
curl -X POST http://localhost:8000/api/v1/auth/logout \
  -H "Authorization: Bearer $ACCESS_TOKEN"

echo "✅ Logged out"
```

---

## 🔍 ПЕРЕВІРКА РЕЗУЛЬТАТІВ

### Чеклист успішного проходження:

**User Flow:**
- [ ] Registration/Login працює
- [ ] Document creation успішна
- [ ] Payment flow завершується
- [ ] Generation completes
- [ ] Download працює (DOCX + PDF)

**Admin Flow:**
- [ ] Admin login працює
- [ ] Dashboard accessible
- [ ] User/Document management працює

**Business Logic:**
- [ ] Refund request flow працює
- [ ] Webhooks processing correct
- [ ] Background jobs complete

---

## ⚠️ ТИПОВІ ПОМИЛКИ ТА РІШЕННЯ

| Помилка | Причина | Рішення |
|---------|---------|---------|
| `Generation timeout` | AI API slow | Збільшити timeout або mock |
| `Payment webhook failed` | Signature verification | Use test signature |
| `Document not found` | Race condition | Add delay after creation |
| `Admin auth failed` | Wrong credentials | Check default admin account |
| `Download file empty` | Generation incomplete | Wait for completion |

---

## 📊 КРИТЕРІЇ УСПІШНОСТІ

### ✅ ТЕСТ ПРОЙДЕНО ЯКЩО:

- Full user flow completes end-to-end
- Payment → Generation → Download працює
- Admin flows accessible
- Всі критичні endpoints respond correctly
- Files download successfully

### ❌ ТЕСТ ПРОВАЛЕНО ЯКЩО:

- User flow breaks at any step
- Payment processing fails
- Generation doesn't complete
- Downloads fail або empty files
- Admin auth broken

---

## 🔗 ЗВ'ЯЗОК З ІНШИМИ ПЕРЕВІРКАМИ

**⬆️ Залежить від:**
- `01-08` - Всі попередні перевірки повинні пройти

**⬇️ Впливає на:**
- Production readiness decision

**Критичність:** 🔴 НАЙВИЩА - це реальні user scenarios!

---

## 🚀 ШВИДКИЙ СТАРТ

```bash
# Quick E2E check script
bash scripts/test_e2e_flow.sh
```

---

**Дата створення:** 2025-12-03
**Версія:** 1.0
**Автор:** AI Assistant
**Попередня перевірка:** `08_FRONTEND_CHECK.md`
**Наступна перевірка:** `10_EXTERNAL_SERVICES_CHECK.md`
