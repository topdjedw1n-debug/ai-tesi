# 6️⃣ ПЕРЕВІРКА ІНТЕГРАЦІЙНИХ ТЕСТІВ

> **Категорія:** Automated Testing - Integration
> **Час виконання:** ~10-15 хвилин
> **Залежності:** Infrastructure + Backend + Database
> **Критичність:** 🟡 СЕРЕДНЯ - Тестує взаємодію компонентів

---

## 🎯 МЕТА ПЕРЕВІРКИ

Перевірити що різні компоненти системи правильно взаємодіють між собою: API з БД, Backend з Redis, AI pipeline з зовнішніми сервісами.

**Що тестуємо:**
- ✅ API Integration (endpoint → database → response)
- ✅ Database CRUD операції з реальною БД
- ✅ Redis checkpoint recovery механізм
- ✅ Quality pipeline integration
- ✅ Rate limiter з Redis backend
- ✅ Background jobs coordination

---

## ✅ ПЕРЕДУМОВИ

- [ ] Docker контейнери running (PostgreSQL, Redis)
- [ ] Backend запущено або може запуститись
- [ ] Integration tests environment налаштовано

---

## 📋 ПОКРОКОВА ІНСТРУКЦІЯ

### Крок 1: API Integration Tests

**Що робимо:** Тестуємо повний цикл API request → DB → response

**Команда:**
```bash
cd /Users/maxmaxvel/.claude-worktrees/AI\ TESI/stupefied-fermat/apps/api

pytest tests/test_api_integration.py -v
```

**Що тестується:**
- Create document → DB record створено
- Get document → Правильні дані повернуто
- Update document → Зміни збережено в БД
- Delete document → Record видалено
- Authentication flow → JWT → Protected endpoint

**Очікуваний результат:**
```
tests/test_api_integration.py::test_full_document_flow PASSED
tests/test_api_integration.py::test_auth_flow PASSED
tests/test_api_integration.py::test_payment_flow PASSED

====== 5 passed in 8.2s ======
```

---

### Крок 2: Database Integration

**Що робимо:** Тестуємо реальні database операції

**Команда:**
```bash
pytest tests/test_database_integration.py -v
```

**Критичні тести:**
```python
# User CRUD
test_create_user_in_db()
test_query_user_from_db()
test_update_user_in_db()
test_delete_user_cascade()  # Перевірка foreign keys

# Transaction rollback
test_transaction_rollback_on_error()

# Concurrent access
test_multiple_sessions_same_record()
```

---

### Крок 3: Redis Integration

**Що робимо:** Тестуємо Redis для checkpoint recovery

**Команда:**
```bash
pytest tests/test_checkpoint_recovery.py -v
```

**Що перевіряється:**
- Checkpoint save after section generation
- Checkpoint load on job restart
- Checkpoint cleanup after completion
- TTL expiration (1 hour)
- Idempotency check

**Очікуваний результат:**
```
tests/test_checkpoint_recovery.py::test_save_checkpoint PASSED
tests/test_checkpoint_recovery.py::test_load_checkpoint PASSED
tests/test_checkpoint_recovery.py::test_resume_from_checkpoint PASSED
tests/test_checkpoint_recovery.py::test_checkpoint_ttl PASSED

====== 4 passed in 3.5s ======
```

---

### Крок 4: Quality Pipeline Integration

**Що робимо:** Тестуємо повний AI quality pipeline

**Команда:**
```bash
pytest tests/test_quality_integration.py -v
```

**Pipeline stages:**
1. Text generation (mock AI)
2. Grammar check (LanguageTool)
3. Plagiarism check (mock Originality.AI)
4. AI detection (mock GPTZero)
5. Quality score calculation

**Очікуваний результат:**
```
tests/test_quality_integration.py::test_full_quality_pipeline PASSED
tests/test_quality_integration.py::test_quality_thresholds PASSED
tests/test_quality_integration.py::test_retry_on_quality_fail PASSED

====== 3 passed in 12.1s ======
```

---

### Крок 5: Rate Limiter Integration

**Що робимо:** Тестуємо rate limiting з Redis

**Команда:**
```bash
pytest tests/test_rate_limiter_integration.py -v
```

**Сценарії:**
- 100 requests/minute per IP → Block на 101st
- Per-user limits → Різні користувачі не впливають
- Redis unavailable → Fallback (no rate limit або in-memory)

**Очікуваний результат:**
```
tests/test_rate_limiter_integration.py::test_ip_rate_limit PASSED
tests/test_rate_limiter_integration.py::test_user_rate_limit PASSED
tests/test_rate_limiter_integration.py::test_rate_limit_headers PASSED

====== 3 passed in 5.4s ======
```

---

### Крок 6: Background Jobs Integration

**Що робимо:** Тестуємо координацію background jobs

**Команда:**
```bash
pytest tests/test_background_jobs_integration.py -v
```

**Що перевіряється:**
- Job створення в БД
- Job status updates (queued → running → completed)
- Job failure handling (retry mechanism)
- Race condition prevention (no duplicate jobs)
- WebSocket notifications

---

### Крок 7: Full Integration Suite

**Команда:**
```bash
# Всі integration тести
pytest tests/integration/ -v

# Або через pattern
pytest tests/test_*_integration.py -v
```

**Очікуваний результат:**
```
====== 18 passed, 2 skipped in 34.5s ======
```

**Критерії:**
- ✅ >= 90% passed = Excellent
- ⚠️ 70-90% passed = Needs attention
- ❌ < 70% passed = Critical issues

---

### Крок 8: Database State Verification

**Що робимо:** Перевіряємо що тести не залишають "сміття" в БД

**Команда:**
```bash
# До тестів
echo "SELECT COUNT(*) FROM users;" | docker exec -i ai-thesis-postgres psql -U postgres -d ai_thesis_platform

# Запустити тести
pytest tests/integration/ -v

# Після тестів (повинно бути те саме або fixtures cleanup)
echo "SELECT COUNT(*) FROM users;" | docker exec -i ai-thesis-postgres psql -U postgres -d ai_thesis_platform
```

**Fixtures повинні робити cleanup:**
```python
@pytest.fixture
async def test_user(db):
    user = User(email="test@example.com")
    db.add(user)
    await db.commit()
    yield user
    await db.delete(user)
    await db.commit()
```

---

### Крок 9: Redis State Verification

**Команда:**
```bash
# До тестів
docker exec ai-thesis-redis redis-cli DBSIZE

# Запустити тести з Redis
pytest tests/test_checkpoint_recovery.py -v

# Після тестів (повинні бути cleanup)
docker exec ai-thesis-redis redis-cli DBSIZE
```

---

### Крок 10: Performance Integration Tests

**Команда:**
```bash
# З timing
pytest tests/integration/ --durations=10
```

**Очікуваний час:**
- Single API integration test: < 2s
- Database CRUD test: < 1s
- Redis checkpoint test: < 0.5s
- Full quality pipeline: < 15s

---

## 🔍 ПЕРЕВІРКА РЕЗУЛЬТАТІВ

### Чеклист успішного проходження:

- [ ] API integration tests >= 90% passed
- [ ] Database CRUD операції працюють
- [ ] Redis checkpoint механізм працює
- [ ] Quality pipeline integration успішна
- [ ] Rate limiter з Redis працює
- [ ] Немає database leaks (cleanup працює)
- [ ] Redis cleanup працює

---

## ⚠️ ТИПОВІ ПОМИЛКИ ТА РІШЕННЯ

| Помилка | Причина | Рішення |
|---------|---------|---------|
| `Database connection refused` | PostgreSQL не running | `docker-compose up -d postgres` |
| `Redis connection timeout` | Redis не доступний | `docker-compose restart redis` |
| `Transaction rollback failed` | Nested transactions | Використати `SAVEPOINT` |
| `Test database not empty` | Cleanup не спрацював | Додати `@pytest.fixture` cleanup |
| Tests slow (> 60s) | Не використовується test DB | Перевірити `TEST_DATABASE_URL` |

---

## 📊 КРИТЕРІЇ УСПІШНОСТІ

### ✅ ТЕСТ ПРОЙДЕНО ЯКЩО:

- >= 90% integration tests passed
- Database CRUD працює коректно
- Redis integration без помилок
- Quality pipeline проходить всі стадії
- Немає data leaks після тестів

### ❌ ТЕСТ ПРОВАЛЕНО ЯКЩО:

- < 70% tests passed
- Database connection fails
- Redis integration broken
- Data leaks (cleanup не працює)
- Background jobs race conditions

---

## 🔗 ЗВ'ЯЗОК З ІНШИМИ ПЕРЕВІРКАМИ

**⬆️ Залежить від:**
- `01_INFRASTRUCTURE_CHECK.md` - Docker контейнери
- `03_BACKEND_CHECK.md` - Backend код
- `05_UNIT_TESTS_CHECK.md` - Unit тести базові

**⬇️ Впливає на:**
- `07_API_ENDPOINTS_CHECK.md` - API manual testing
- `09_E2E_TESTS_CHECK.md` - End-to-end flows

**Критичність:** 🟡 СЕРЕДНЯ - важливо для production readiness

---

## 🚀 ШВИДКИЙ СТАРТ

```bash
# Quick integration check
cd apps/api && \
pytest tests/test_*_integration.py -q && \
echo "✅ Integration tests PASSED"
```

---

**Дата створення:** 2025-12-03
**Версія:** 1.0
**Автор:** AI Assistant
**Попередня перевірка:** `05_UNIT_TESTS_CHECK.md`
**Наступна перевірка:** `07_API_ENDPOINTS_CHECK.md`
