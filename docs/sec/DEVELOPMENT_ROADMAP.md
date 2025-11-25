# Roadmap Development TesiGo v2.4

**Дата оновлення:** 2025-11-03
**Статус:** Оновлений план з урахуванням продуктових змін
**Базуючись на:** USER_FLOW_UPDATED.md, MASTER_DOCUMENT.md v3.0

---

## 📊 Поточний стан проекту

### ✅ Що працює
- Якісна архітектура (9/10)
- РАГ правильно інтегрований
- Phase 0 баги виправлені
- Безпека налаштована
- Background Jobs реалізовані
- DOCX export працює

### ⚠️ Що потребує уваги
- Python version mismatch (venv 3.9 vs config 3.11)
- Low test coverage (37%)
- Відсутність integration/E2E тестів
- Payment system відсутня (КРИТИЧНО - оплата перед генерацією)
- PDF export не повністю реалізований
- Custom requirements upload відсутній

### 🔄 НОВІ ПРОДУКТОВІ ВИМОГИ (2025-11-03)
- ❌ Видалити вибір AI моделі з UI
- ❌ Прибрати відображення токенів
- ❌ Видалити окрему генерацію секцій
- ❌ Прибрати редагування після генерації
- ✅ Мінімум 3 сторінки для замовлення
- ✅ Оплата ПЕРЕД генерацією
- ✅ Політика БЕЗ повернень

---

## 🎯 РЕКОМЕНДОВАНИЙ ПЛАН РОЗРОБКИ

### 🔴 P0: Критичні (1-2 дні)

#### Task 1: Виправити Python Version Mismatch

**Час:** 30 хвилин
**Пріоритет:** P0 - БЛОКУЄ

**Дії:**
```bash
cd "/Users/maxmaxvel/AI TESI"
rm -rf qa_venv
python3.11 -m venv qa_venv
source qa_venv/bin/activate
cd apps/api
pip install -r requirements.txt
```

**Перевірка:**
```bash
python --version  # Має бути 3.11.x
pytest tests/ -v
```

**Результат:** Всі тести мають проходити з Python 3.11

---

#### Task 2: Перевірити та запустити MyPy

**Час:** 1-2 години
**Пріоритет:** P0

**Дії:**
```bash
cd apps/api
source ../../qa_venv/bin/activate
mypy app/ --config-file mypy.ini
```

**Очікуваний результат:** 0 блокуючих помилок

**Якщо є помилки:**
- Фікс annotations в проблемних файлах
- Додати `# type: ignore` тільки якщо дійсно потрібно

---

#### Task 3: Додати basic unit тести

**Час:** 4-6 годин
**Пріоритет:** P0

**Створити тести:**

1. **test_document_service.py** (новый файл)
   - `test_create_document_success`
   - `test_get_document_success`
   - `test_export_document_docx`
   - `test_export_document_fails_on_incomplete`

2. **test_ai_service.py** (новый файл)
   - `test_generate_outline_success`
   - `test_generate_section_with_rag`
   - `test_get_user_usage_correctness`

**Мінімальний target:** 6-8 нових тестів, coverage ≥50%

---

### 🟠 P1: Важливі (1 тиждень)

#### Task 4: Додати PDF Export

**Час:** 1 день
**Пріоритет:** P1 - ВИСОКИЙ

**Статус:** Export endpoint є, але PDF експорт не повністю працює

**Дії:**
1. Перевірити що WeasyPrint/ReportLab правильно встановлені
2. Додати метод `_create_pdf()` в `DocumentService`
3. Інтегрувати з MinIO upload
4. Тест: `test_export_document_pdf`

**Файл:** `apps/api/app/services/document_service.py`
**Метод:** `_create_pdf(document_data: dict) -> str`

---

#### Task 5: Integration тести для API

**Час:** 1 день
**Пріоритет:** P1

**Створити:**
- `test_api_endpoints.py`
  - `test_auth_flow` (register → login → me)
  - `test_create_document_flow`
  - `test_generate_outline_flow`
  - `test_export_document_flow`

**Метрика:** 4-6 integration тестів

---

#### Task 6: Activate Background Jobs в endpoint

**Час:** 2-3 години
**Пріоритет:** P1

**Статус:** `BackgroundJobService` реалізований, але не використовується в endpoints

**Дії:**
1. Перевірити `/generate/full-document` endpoint
2. Інтегрувати `BackgroundJobService.generate_full_document()`
3. Тест: concurrent generation requests

**Файл:** `apps/api/app/api/v1/endpoints/generate.py`

---

### 🟡 P2: Середньої важливості (2 тижні)

#### Task 7: Додати Payment System

**Час:** 1 тиждень
**Пріоритет:** P2 - MVP CRITICAL

**Компоненти:**
1. **Payment Model** (`apps/api/app/models/payment.py`)
   - Payment records
   - Stripe payment_intent_id
   - Status tracking

2. **Payment Service** (`apps/api/app/services/payment_service.py`)
   - Create payment
   - Stripe integration
   - Webhook handler

3. **Payment Endpoints** (`apps/api/app/api/v1/endpoints/payment.py`)
   - POST `/payment/create`
   - POST `/payment/webhook`
   - GET `/payment/status`

4. **Stripe Setup:**
   ```bash
   pip install stripe
   ```

**Залежності:**
- Stripe account
- Stripe API keys (test mode для початку)

---

#### Task 8: Custom Requirements Upload

**Час:** 3-4 дні
**Пріоритет:** P2

**Компоненти:**
1. **Upload Endpoint**
   - POST `/documents/{id}/custom-requirements/upload`
   - File validation (PDF, DOCX)
   - Store в MinIO

2. **Parsing Service**
   - PDF parsing (PyPDF2 - вже є)
   - DOCX parsing (python-docx - вже є)
   - Extract text

3. **Integration**
   - Використовувати в prompts
   - Додати context до generation

**Файл:** `apps/api/app/services/custom_requirements_service.py` (новий)

---

#### Task 9: Покращити test coverage до 80%+

**Час:** 1 тиждень
**Пріоритет:** P2

**Дії:**
1. Додати тести для всіх сервісів
2. Додати тести для middleware
3. Додати тести для schemas
4. Додати edge cases

**Target:**
- `document_service.py`: 80%+ (зараз 11%)
- `ai_service.py`: 80%+ (зараз 21%)
- `auth_service.py`: 80%+ (зараз 18%)

---

## 📅 TIMELINE

### Week 1: P0 Tasks
- Day 1: Python 3.11 fix + MyPy check
- Day 2-3: Basic unit tests
- **Result:** Stable foundation з Python 3.11

### Week 2: P1 Tasks
- Day 1: PDF export
- Day 2: Integration tests
- Day 3-4: Background jobs activation
- **Result:** MVP features працюють

### Week 3-4: P2 Tasks
- Week 3: Payment system
- Week 4: Custom requirements + coverage
- **Result:** Production-ready MVP

**Загалом:** 3-4 тижні до production-ready MVP

---

## 🎯 SHORT MVP (Без Payment)

Якщо потрібно launch швидше, можна зробити MVP БЕЗ оплати:

### 2-Week MVP:
- Week 1: P0 tasks
- Week 2: PDF export + Integration tests + Coverage improvement
- **Result:** MVP без оплати, але з усіма core features

**Ризик:** Немає монетизації, але можна launch для beta testing

---

## ✅ SUCCESS CRITERIA

### MVP Ready Checklist:
- [ ] Python 3.11 в venv
- [ ] MyPy: 0 blocking errors
- [ ] Coverage: ≥50% (minimum), ≥80% (ideal)
- [ ] PDF export працює
- [ ] Integration tests passing
- [ ] Background jobs активні
- [ ] All smoke tests pass

### Production Ready (додатково):
- [ ] Payment system functional
- [ ] Custom requirements upload
- [ ] Coverage ≥80%
- [ ] E2E тести
- [ ] Monitoring setup
- [ ] Production deployment tested

---

## 📊 PRIORITY RANKING

| Task | Priority | Time | Blocking? |
|------|----------|------|-----------|
| Python 3.11 fix | P0 | 30 min | BLOCKS all |
| MyPy check | P0 | 1-2h | BLOCKS |
| Unit tests | P0 | 1 day | BLOCKS |
| PDF export | P1 | 1 day | Important |
| Integration tests | P1 | 1 day | Important |
| Background jobs | P1 | 3h | Important |
| Payment system | P2 | 1 week | Nice-to-have |
| Custom upload | P2 | 4 days | Nice-to-have |
| Coverage 80% | P2 | 1 week | Nice-to-have |

---

## 🎯 РЕКОМЕНДАЦІЯ

### Для запуску MVP:

**Швидкий варіант (2 тижні):**
1. P0 tasks (2 дні)
2. PDF export (1 день)
3. Integration tests (1 день)
4. Coverage improvement (4 дні)
5. Polish (2 дні)

**Повний варіант (3-4 тижні):**
1. P0 + P1 tasks (2 тижні)
2. P2 tasks (2 тижні)
3. Payment integration
4. Production ready

**Спочатку зроби:**
- Python 3.11 fix (30 хв)
- MyPy check (1-2h)
- Unit tests (1 день)

**Потім виріши:**
- Швидкий MVP (без оплати)?
- Повний MVP (з оплатою)?

---

## 💡 ДОДАТКОВІ РЕКОМЕНДАЦІЇ

1. **Focus на тести** - це головна прогалина
2. **Не нові features** - покращити існуючі спочатку
3. **Payment можна додати потім** - спочатку запусти beta
4. **Coverage step by step** - 50% → 70% → 80%
5. **Integration tests важливіші** за unit tests для MVP

---

**Дата:** 2025-01-XX
**Версія:** 1.0
**Статус:** READY FOR APPROVAL
