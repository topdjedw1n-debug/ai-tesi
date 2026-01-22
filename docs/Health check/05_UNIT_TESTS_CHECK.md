# 5️⃣ ПЕРЕВІРКА UNIT ТЕСТІВ

> **Категорія:** Automated Testing - Unit
> **Час виконання:** ~15-20 хвилин
> **Залежності:** Backend + Test infrastructure
> **Критичність:** 🟡 СЕРЕДНЯ - Важливо для якості коду

---

## 🎯 МЕТА ПЕРЕВІРКИ

Запустити всі unit тести та переконатися що критична функціональність працює правильно на рівні окремих модулів та функцій.

**Що тестуємо:**
- ✅ Auth service (JWT, magic links)
- ✅ Document service (CRUD операції)
- ✅ Payment service (Stripe integration)
- ✅ Admin service (адмін функції)
- ✅ Security (IDOR protection, validation)
- ✅ AI pipeline components

---

## ✅ ПЕРЕДУМОВИ

- [ ] Backend код встановлено
- [ ] Test database налаштовано (sqlite in-memory)
- [ ] `pytest` встановлено

---

## 📋 ПОКРОКОВА ІНСТРУКЦІЯ

### Крок 1: Smoke Tests

**Що робимо:** Швидка перевірка що основні імпорти працюють

**Команда:**
```bash
cd /Users/maxmaxvel/.claude-worktrees/AI\ TESI/stupefied-fermat/apps/api

pytest tests/test_smoke.py -v
```

**Очікуваний результат:**
```
tests/test_smoke.py::test_imports_work PASSED
tests/test_smoke.py::test_settings_loaded PASSED
tests/test_smoke.py::test_database_models PASSED

====== 3 passed in 0.5s ======
```

---

### Крок 2: Authentication Tests

**Команда:**
```bash
# Всі auth тести
pytest tests/test_auth*.py -v

# JWT тести
pytest tests/test_jwt_helpers.py -v

# Magic link тести
pytest tests/test_auth_service_extended.py -v
```

**Очікуваний результат:**
```
tests/test_jwt_helpers.py::test_create_access_token PASSED
tests/test_jwt_helpers.py::test_decode_token PASSED
tests/test_auth_service_extended.py::test_magic_link_generation PASSED
tests/test_auth_service_extended.py::test_verify_magic_link PASSED

====== 8 passed in 2.3s ======
```

---

### Крок 3: Document Service Tests

**Команда:**
```bash
pytest tests/test_document*.py -v
```

**Очікуваний тести:**
- `test_create_document` - Створення документа
- `test_get_document` - Отримання документа
- `test_update_document` - Оновлення
- `test_delete_document` - Видалення
- `test_document_ownership` - IDOR protection

---

### Крок 4: Payment Tests

**Команда:**
```bash
pytest tests/test_payment*.py -v
```

**Критичні тести:**
- `test_create_payment_intent` - Stripe integration
- `test_payment_webhook` - Webhook обробка
- `test_payment_verification` - Signature verification

---

### Крок 5: Security Tests

**Команда:**
```bash
# IDOR protection
pytest tests/test_idor_protection.py -v

# File security
pytest tests/test_file_security.py -v

# General security
pytest tests/test_security.py -v
```

**Критичні перевірки:**
- Користувач не може отримати чужі документи
- File magic bytes validation працює
- JWT токени правильно валідуються

---

### Крок 6: Admin Tests

**Команда:**
```bash
pytest tests/test_admin*.py -v
```

**Перевіряємо:**
- Admin authentication
- Dashboard statistics
- User management
- Settings management

---

### Крок 7: AI Pipeline Tests

**Команда:**
```bash
pytest tests/test_ai_*.py -v --tb=short
```

**Компоненти:**
- Section generator
- RAG retriever
- Citation formatter
- Quality checker

---

### Крок 8: Refund Tests

**Команда:**
```bash
pytest tests/test_refund*.py -v
```

**Перевіряємо:**
- Refund request creation
- Admin approval flow
- Automatic refunds on errors

---

### Крок 9: Full Test Suite

**Команда:**
```bash
# Всі unit тести (без integration/e2e)
pytest tests/ -v \
  --ignore=tests/integration \
  --ignore=tests/e2e \
  --ignore=tests/load
```

**Очікуваний результат:**
```
====== 85 passed, 5 skipped in 45.2s ======
```

**Критерії успішності:**
- ✅ >= 80% passed (68+ тестів)
- ⚠️ 60-80% passed - Перевірити failures
- ❌ < 60% passed - Критичні проблеми

---

### Крок 10: Coverage Report

**Команда:**
```bash
# З coverage
pytest tests/ \
  --ignore=tests/integration \
  --cov=app \
  --cov-report=term \
  --cov-report=html

# Тільки summary
pytest tests/ --cov=app --cov-report=term | tail -20
```

**Очікуваний coverage:**
```
---------- coverage: ----------
Name                              Stmts   Miss  Cover
-----------------------------------------------------
app/core/security.py                 45      5    89%
app/services/auth_service.py        123     25    80%
app/api/v1/endpoints/auth.py         89     15    83%
...
-----------------------------------------------------
TOTAL                              2345    987    58%
```

**Критерії (згідно MASTER_DOCUMENT.md):**
- ✅ >= 48% = Baseline OK
- 🎯 >= 60% = Good
- 🌟 >= 80% = Excellent

---

### Крок 11: Specific Module Testing

**Високопріоритетні модулі для окремого тестування:**

```bash
# Security (критично!)
pytest tests/test_security.py -v --cov=app/core/security --cov-report=term

# Payment (критично!)
pytest tests/test_payment.py -v --cov=app/services/payment_service --cov-report=term

# Auth (критично!)
pytest tests/test_auth_service_extended.py -v --cov=app/services/auth_service --cov-report=term
```

---

### Крок 12: Test Performance

**Що робимо:** Вимірюємо швидкість тестів

**Команда:**
```bash
# З timing
pytest tests/ --ignore=tests/integration --durations=10
```

**Очікуваний результат:**
```
slowest 10 durations:
3.45s call     tests/test_ai_pipeline_integration.py::test_full_generation
2.12s call     tests/test_payment.py::test_stripe_webhook
1.89s call     tests/test_document_service.py::test_large_document
...
```

**Критерії:**
- ✅ Total time < 60s = Швидко
- ⚠️ 60-120s = Прийнятно
- ❌ > 120s = Повільно (оптимізувати)

---

### Крок 13: Failed Tests Analysis

**Якщо є failures:**

```bash
# Детальний вивід для failed тестів
pytest tests/ --ignore=tests/integration -v --tb=long -x

# Тільки failed тести
pytest tests/ --lf  # last failed

# Specific test with debug
pytest tests/test_payment.py::test_webhook_verification -vv -s
```

---

## 🔍 ПЕРЕВІРКА РЕЗУЛЬТАТІВ

### Чеклист успішного проходження:

**Smoke tests:**
- [ ] 3/3 passed (imports, settings, models)

**Core functionality:**
- [ ] Auth tests >= 80% passed
- [ ] Document tests >= 80% passed
- [ ] Payment tests >= 80% passed
- [ ] Security tests = 100% passed (критично!)

**Coverage:**
- [ ] Overall >= 48% (baseline)
- [ ] Security modules >= 80%
- [ ] Payment modules >= 70%

---

## ⚠️ ТИПОВІ ПОМИЛКИ ТА РІШЕННЯ

| Помилка | Причина | Рішення |
|---------|---------|---------|
| `No module named 'pytest'` | Не встановлено | `pip install pytest pytest-asyncio` |
| `Database not found` | Test DB не створено | Використовує sqlite in-memory автоматично |
| `Fixture not found` | Конфлікт fixtures | Перевірити `conftest.py` |
| `ImportError` | Неправильний PYTHONPATH | `cd apps/api` перед запуском |
| Tests hang | Async не завершується | Використати `pytest-timeout` |

---

## 📊 КРИТЕРІЇ УСПІШНОСТІ

### ✅ ТЕСТ ПРОЙДЕНО ЯКЩО:

- >= 80% unit tests passed (68+ з 85)
- Security tests = 100% passed
- Payment tests >= 90% passed
- Coverage >= 48%
- No critical failures

### ❌ ТЕСТ ПРОВАЛЕНО ЯКЩО:

- < 60% tests passed
- Security tests failed (будь-які!)
- Payment tests < 70% passed
- Critical module coverage < 30%

---

## 🔗 ЗВ'ЯЗОК З ІНШИМИ ПЕРЕВІРКАМИ

**⬆️ Залежить від:**
- `03_BACKEND_CHECK.md` - Backend код

**⬇️ Впливає на:**
- `06_INTEGRATION_TESTS_CHECK.md` - Integration tests
- Загальна впевненість в якості коду

**Критичність:** 🟡 СЕРЕДНЯ - важливо для якості

---

## 🚀 ШВИДКИЙ СТАРТ

```bash
# Quick unit tests check
cd apps/api && \
pytest tests/ --ignore=tests/integration -q && \
echo "✅ Unit tests PASSED"
```

---

**Дата створення:** 2025-12-03
**Версія:** 1.0
**Автор:** AI Assistant
**Попередня перевірка:** `04_STATIC_ANALYSIS_CHECK.md`
**Наступна перевірка:** `06_INTEGRATION_TESTS_CHECK.md`
