# 📋 DECISIONS LOG - TesiGo v2.3

> Всі архітектурні та технічні рішення з обґрунтуванням

**Формат:** Проблема → Рішення → Чому саме так

---

## 🏗️ Architecture Decisions

### FastAPI vs Django
**Вибрали:** FastAPI
**Чому:**
- Async з коробки (критично для AI APIs)
- Автоматична документація (OpenAPI)
- Type hints та валідація (Pydantic)
- Швидкість (2-3x швидше Django)

### PostgreSQL vs MongoDB
**Вибрали:** PostgreSQL
**Чому:**
- ACID транзакції (критично для платежів)
- JSON поля для flexible schemas
- Надійність та стабільність
- Краща підтримка в екосистемі Python

### Next.js vs React SPA
**Вибрали:** Next.js
**Чому:**
- SSR для SEO
- App Router (новий стандарт)
- Built-in оптимізації
- Простіший деплой

---

## 💰 Business Decisions

### Pay-per-page vs Subscription
**Вибрали:** Pay-per-page
**Чому:**
- Прозора модель для користувачів
- Платиш тільки за що використав
- Простіше розрахувати costs
- Немає проблем з refunds

### EUR vs Multi-currency
**Вибрали:** Тільки EUR
**Чому:**
- Спрощує бухгалтерію
- Немає currency conversion
- Один прайс для всіх
- Можна додати пізніше

### Simple pricing approach
**Рішення:** Фіксована ціна для користувача (€0.50/сторінка), трекінг токенів без складних розрахунків
**Чому:**
- Простота важливіша за точність
- Користувач платить фіксовану ціну незалежно від моделі
- Трекаємо токени для статистики, не для billing
- Система працює навіть якщо провайдери змінять ціни
- Немає потреби в складній логіці цін

**Реалізація:**
- Використовуємо існуючі поля `tokens_used` в Document
- Простий daily limit на користувача (опціонально)
- Admin статистика для моніторингу
- Ціна для користувача завжди €0.50/сторінка

---

## 🤖 AI Strategy Decisions

### OpenAI + Anthropic (no alternatives yet)
**Рішення:** Фокус на 2 провайдерах
**Чому:**
- Найкраща якість
- Стабільні API
- Альтернативи додамо коли буде потреба
- Self-hosted занадто дорого зараз

### AI Self-Learning Strategy
**Рішення:** Fine-tuning на основі успішних документів
**Чому:**
- Постійне покращення якості без ручного втручання
- Адаптація до специфіки кожного ринку (IT, ES, CS, EN, DE, FR)
- Зниження витрат через менше регенерацій
- Конкурентна перевага через унікальні моделі

**Реалізація:**
- Збір документів з оцінкою 4+ зірок
- Фільтрація за plagiarism < 15% та AI detection < 55%
- Monthly retraining при накопиченні 100+ документів
- A/B тестування перед розгортанням

**Статус:** Відкладено до накопичення критичної маси даних

### Retry механізми
**Рішення:** Exponential backoff + provider fallback
```python
delays = [2, 4, 8, 16, 32]
fallback: GPT-4 → GPT-3.5 → Claude
```
**Чому:**
- Захист від temporary failures
- Користувач не помітить збій
- Автоматичне відновлення

### Memory management
**Рішення:** Генерація по логічних розділах
**Чому:**
- Не розбиваємо розділи посередині
- Streaming в БД (не RAM)
- Max 200 сторінок на документ
- Clear memory після кожного розділу

---

## 🔒 Security Decisions

### Magic links vs Passwords
**Вибрали:** Magic links
**Чому:**
- Немає паролів = немає їх витоку
- Простіше для користувачів
- Немає password reset проблем
- Modern approach

### JWT storage
**Рішення:** httpOnly cookies + Redis sessions
**Чому:**
- Захист від XSS
- Можливість revoke tokens
- Centralized session management

### File upload security
**Рішення:** Magic bytes validation + streaming
**Чому:**
- Не довіряємо file extensions
- Захист від malicious files
- Немає обмеження розміру (streaming)

---

## 🚀 Performance Decisions

### Async everywhere
**Рішення:** Всі I/O операції async
**Чому:**
- Не блокуємо thread pool
- Краще масштабування
- Природньо для AI APIs

### Background jobs
**Рішення:** BackgroundJobService (вже є!)
**Чому:**
- Генерація не блокує request
- Можна показувати прогрес
- Resilient to failures

### DR-012: Redis Checkpoints for Generation Recovery
**Date:** 01.12.2025
**Status:** ✅ Accepted & Implemented
**Context:**
- Problem: 100-page document = 45 min generation, crash at 85% = loss of 35 min AI costs ($5-10 wasted)
- User paid but received nothing, must regenerate from scratch = doubled costs
- Need recovery mechanism to resume generation from last completed section

**Decision:** Use Redis for checkpoint storage (not DB table)

**Technical Implementation:**
```python
# Checkpoint structure:
checkpoint = {
    "document_id": int,
    "last_completed_section_index": int,
    "total_sections": int,
    "completed_at": str (ISO timestamp),
    "status": "in_progress"
}

# Storage: Redis key "checkpoint:doc:{document_id}"
# TTL: 3600 seconds (1 hour)
# Save: After each section completes
# Load: On job start
# Clear: On success OR failure
```

**Consequences:**
- ✅ **Cost savings:** $5-10 per failed document avoided
- ✅ **User satisfaction:** No "lost my payment" complaints
- ✅ **System reliability:** Handles crashes gracefully
- ✅ **Time savings:** No full regeneration needed
- ⚠️ **Limitation:** Checkpoint lost if Redis restarts (acceptable - rare event)
- ⚠️ **Memory:** One checkpoint per active document (~200 bytes)

**Alternatives Considered:**
1. **Database table for checkpoints**
   - ❌ Slower than Redis (I/O overhead)
   - ❌ Requires migrations, adds schema complexity
   - ❌ Permanent storage not needed (temporary data)

2. **No checkpointing (status quo)**
   - ❌ Wastes API costs on crash
   - ❌ Poor user experience
   - ❌ No recovery mechanism

3. **File-based checkpoints (JSON files)**
   - ❌ Slower than Redis
   - ❌ Disk I/O overhead
   - ❌ No automatic cleanup

**Trade-off Analysis:**
- **Speed:** Redis (milliseconds) vs DB (10-50ms) vs File (50-200ms)
- **Reliability:** Redis 99.9% uptime sufficient for temporary data
- **Complexity:** Redis = simple set/get/delete vs DB = migrations/models
- **Auto-cleanup:** Redis TTL vs manual cleanup for DB/File

**Why Redis Won:**
- Temporary data (1 hour max lifecycle)
- Fast read/write (< 1ms)
- Built-in TTL (no cleanup code needed)
- Already in infrastructure
- Simple implementation (3 Redis calls)

**Implementation Details:**
- Files modified: `background_jobs.py` (+92 lines)
- Tests created: `test_checkpoint_recovery.py` (+394 lines, 4 test cases)
- Time: 2h 15min actual (vs 2-3h planned)
- Tasks: 3.7.1-3.7.6 (save, load, cleanup, idempotency, metrics)

**Known Risks & Mitigations:**
- **Risk:** Redis connection failure
  - **Mitigation:** Try/except blocks, log warning, continue generation without checkpoint
  - **Impact:** Non-critical, checkpoint is optimization not requirement

- **Risk:** Checkpoint out of sync with DB
  - **Mitigation:** Idempotency check (query DB before generating each section)
  - **Impact:** Prevented by defensive check

- **Risk:** TTL too short for long generations
  - **Mitigation:** 1 hour TTL sufficient for 200 pages (~60 min generation)
  - **Impact:** Acceptable, 200 pages is max limit

**Success Metrics:**
- Checkpoint save rate: > 99% (measure in production)
- Recovery success rate: > 95% (when checkpoint exists)
- Cost savings: Estimated $50-100/month (10-20 crashes avoided)

### Caching strategy
**Рішення:** Cache тільки технічні дані
**НЕ кешуємо:** Згенерований контент
**Чому:**
- Кожна робота унікальна
- Ризик плагіату
- Cache тільки search results, configs

---

## 🎨 UX Decisions

### Auto-save
**Рішення:** LocalStorage + backend drafts
**Чому:**
- Не втрачаємо роботу користувача
- Recovery після crash
- Version history

### Progress tracking
**Рішення:** WebSocket updates (без preview/cancel)
**Чому:**
- Real-time feedback
- НЕ робимо preview (непотрібно)
- НЕ робимо cancel (складно)

### Error handling
**Рішення:** User-friendly messages + error codes
**Чому:**
- Користувач розуміє що робити
- Support може допомогти по коду
- Не показуємо technical details

---

## 🚫 What We DON'T Do (Consciously)

### НЕ робимо зараз:
1. **Live preview** - непотрібна складність
2. **Cancel generation** - рідко використовується
3. **Self-hosted models** - занадто дорого
4. **Fine-tuning** - немає даних поки
5. **Ukrainian language** - обмеження моделей
6. **Multiple currencies** - складність без value
7. **Subscription model** - не підходить для use case
8. **Blockchain/Crypto** - немає реальної потреби
9. **Social features** - не core функціональність
10. **Mobile apps** - web-first approach

### Відкладено до v3.0:
- Alternative AI providers
- Advanced analytics
- Collaboration features
- API for third parties
- Multi-language UI

---

## 🔧 Technical Debt (Accepted)

### Що знаємо але не фіксимо:
1. **Vendor lock-in** - вирішимо коли буде проблема
2. **Hardcoded limits** - 200 pages max (OK for MVP)
3. **No unit tests** - додамо після launch
4. **Basic monitoring** - розширимо по потребі
5. **Manual deployment** - автоматизуємо пізніше

---

## 📊 Trade-offs Matrix

| Feature | Complexity | Value | Decision |
|---------|------------|-------|----------|
| Basic generation | Low | High | ✅ DO |
| Retry mechanisms | Medium | High | ✅ DO |
| Auto-save | Medium | High | ✅ DO |
| Progress bar | Low | Medium | ✅ DO |
| Live preview | High | Low | ❌ DON'T |
| Cancel generation | High | Low | ❌ DON'T |
| Self-hosted AI | Very High | Medium | ❌ DON'T |
| Multi-currency | High | Low | ❌ DON'T |
| Mobile apps | Very High | Medium | ⏸️ LATER |
| Collaboration | High | Medium | ⏸️ LATER |

---

## ✅ Critical Fixes Priority

### Must fix before launch (1 day):
1. **IDOR Protection** (2 hours)
2. **JWT Hardening** (30 min)
3. **File Magic Bytes** (2 hours)
4. **Basic Backup** (1 hour)

### Should fix before launch (1 week):
1. BackgroundJobService integration
2. Webhook signature verification
3. ~~Price quotes system~~ (відхилено - не потрібно)
4. GDPR consent flow

### Nice to have (after launch):
1. Advanced monitoring
2. Performance optimization
3. Extended test coverage
4. API documentation

---

## 📝 Decision Records Format

```markdown
### DR-001: [Decision Title]
**Date:** YYYY-MM-DD
**Status:** Accepted/Rejected/Superseded
**Context:** What problem we're solving
**Decision:** What we decided
**Consequences:** What happens as result
**Alternatives:** What else we considered
```

---

**This document is the source of truth for all technical decisions**
**Update it when making new architectural choices**
**Never delete, only mark as superseded**
