# 🚨 Активні ризики та задачі для виправлення

> **Тільки ті ризики, з якими треба працювати ЗАРАЗ**

**Дата створення:** 01.12.2025
**Статус:** 🔴 ACTION REQUIRED
**Owner:** @maxmaxvel + AI Agent

---

## 🔴 КРИТИЧНІ (Must Fix Before Production)

### 1. Issue #2: Pass on API Error (Phase 2)

**Проблема:** Якщо GPTZero/Copyscape/LanguageTool API падає → контент проходить без перевірки

**Код:**
```python
# _check_grammar_quality(), _check_plagiarism_quality(), _check_ai_detection_quality()
except Exception as e:
    return (None, 0, True, None)  # ❌ Pass by default!
```

**Ризик:**
- 70% плагіату проходить як "OK"
- Репутаційна шкода
- Потенційні юридичні проблеми

**Рішення (2h):**
```python
# 1. Додати в config.py:
QUALITY_GATES_STRICT_MODE: bool = Field(
    default=False,
    description="True = fail on API error (production), False = pass (dev)"
)

# 2. Змінити helper functions:
except Exception as e:
    if settings.QUALITY_GATES_STRICT_MODE:
        return (None, 0, False, f"API error: {e}")  # ❌ FAIL on error
    else:
        return (None, 0, True, None)  # ⚠️ Pass for dev/testing

# 3. Production .env:
QUALITY_GATES_STRICT_MODE=true
```

**Файли:**
- `app/core/config.py` (+5 lines)
- `app/services/background_jobs.py` (3 helper functions)
- `.env.example` (+1 line)

**Дедлайн:** ⚠️ Before production launch
**Час:** 2h
**Пріоритет:** 🔴 P0

---

### 2. Issue #3: API Rate Limits (Phase 2)

**Проблема:** GPTZero = 50 req/hour, Copyscape = 100 req/hour
**Ризик:** 5 concurrent docs × 20 sections × 3 attempts = 300 calls/hour → **API BLOCKING**

**Сценарій:**
```
Worst Case:
- 5 documents одночасно
- 20 sections кожен
- 3 attempts per section
= 300 calls/hour

GPTZero limit: 50/hour
Result: BLOCKED ❌ → всі документи падають
```

**Рішення (3h):**
```python
# 1. Встановити fastapi-limiter
pip install fastapi-limiter redis

# 2. Додати rate limiter middleware:
from fastapi_limiter import FastAPILimiter
from fastapi_limiter.depends import RateLimiter

# In main.py
@app.on_event("startup")
async def startup():
    await FastAPILimiter.init(redis)

# 3. Обгорнути quality check functions:
@rate_limit(calls=45, period=3600)  # 45/hour (buffer під 50)
async def _check_ai_detection_quality(...):
    ...

# 4. Queue для overflow:
if rate_limit_exceeded:
    await quality_check_queue.enqueue(section_id)
    # Retry after 1 hour
```

**Файли:**
- `requirements.txt` (+1 line)
- `app/main.py` (+10 lines init)
- `app/services/background_jobs.py` (rate limiter decorators)
- `app/services/quality_check_queue.py` (+150 lines NEW)

**Дедлайн:** ⚠️ Before scaling to 20+ concurrent jobs
**Час:** 3h
**Пріоритет:** 🔴 P0 (blocker for scale)

---

## 🟡 ВАЖЛИВІ (Should Fix Soon)

### 3. Risk #2: Partial Completion Strategy (Phase 2 - Strategy 1) 🔴 CRITICAL

**Проблема:** Документ може fail після всіх regeneration attempts → full refund + AI costs loss

**Сценарій:**
```
User платить €25 → Генерація 45/50 секцій OK → Секція 46 fails після 3 attempts
→ Весь документ failed → Refund €25 → Total loss €33 (refund + AI costs + support)
```

**Статистика ймовірності failure:**
- 20 sections: 64% ймовірність хоча б 1 fail
- 50 sections: 92% ймовірність хоча б 1 fail
- 100 sections: 99% ймовірність хоча б 1 fail

**Рішення - Partial Completion Fallback (CRITICAL - Strategy 1):**
```python
# Implementation в background_jobs.py (після generation loop)
sections_completed = len([s for s in sections if s.status == "completed"])
completion_rate = sections_completed / total_sections

if completion_rate >= 0.80:  # 80%+ готово
    job.status = "completed_with_warnings"
    job.quality_warnings = [
        f"Section {failed_idx} below quality threshold"
    ]
    document.status = "completed"
    # Deliver документ з попередженням ✅
else:  # <80% готово
    job.status = "failed_quality"
    await trigger_refund(payment_id)  # Auto refund ❌
```

**Потрібне рішення від @maxmaxvel:**
1. Який threshold для delivery? (80%? 85%? 90%?)
2. Чи показувати missing sections в UI?
3. Чи давати discount якщо < 100%?

**Файли:**
- `app/services/background_jobs.py` (після generation loop)
- `app/schemas/job.py` (add quality_warnings: List[str])

**Дедлайн:** ⚠️ BEFORE production launch
**Час:** 1h (після user approval)
**Пріоритет:** 🟡 P1 (**CRITICAL** - Risk #2 Strategy 1)

---

### 4. Risk #3: WebSocket Heartbeats (Phase 2 - Strategy 1) 🔴 MUST IMPLEMENT

**Проблема:** WebSocket disconnect під час довгої regeneration (6+ min без updates)

**Сценарій:**
```
T=0: WebSocket connected ✅
T=5min: Section regenerating (no updates sent)
T=7min: Browser/proxy timeout → disconnect ❌
T=10min: User думає "зависло" → reload page
```

**Browser/proxy timeouts:**
- Chrome: ~5 min
- Safari: ~30 sec
- Nginx: 60 sec (default)
- CloudFlare: 100 sec

**Рішення - Heartbeat Messages (MUST IMPLEMENT - Strategy 1):**
```python
# background_jobs.py
import asyncio

async def send_periodic_heartbeat(user_id: int, job_id: int):
    """Send heartbeat every 10 seconds during long operations"""
    while True:
        await asyncio.sleep(10)

        job = await db.get(AIGenerationJob, job_id)
        if job.status not in ["running", "generating"]:
            break

        await manager.send_progress(user_id, {
            "type": "heartbeat",
            "job_id": job_id,
            "timestamp": datetime.utcnow().isoformat(),
            "message": "Generation in progress..."
        })

# В generate_full_document_async:
asyncio.create_task(send_periodic_heartbeat(user_id, job.id))
```

**Файли:**
- `app/services/background_jobs.py` (в generate_full_document_async)

**Дедлайн:** ⚠️ Before production
**Час:** 20 min
**Пріоритет:** 🟡 P1 (**MUST IMPLEMENT** - Risk #3 Strategy 1)

---

### 5. Risk #3: State Persistence in DB (Phase 2 - Strategy 3) ✅ RECOMMENDED

**Проблема:** Progress тільки в WebSocket → lost on disconnect

**Рішення - Save Progress to DB (RECOMMENDED - Strategy 3):**
```python
# Save прогрес в DB для fallback
await db.execute(
    update(AIGenerationJob)
    .where(AIGenerationJob.id == job_id)
    .values(
        current_section=section_index,
        current_attempt=attempt,
        progress_percentage=progress,
        last_update=datetime.utcnow()
    )
)
await db.commit()
```

**Frontend fallback:**
```typescript
// On WebSocket disconnect:
websocket.onclose = async () => {
    // Fetch last known progress from DB
    const progress = await fetch(`/api/jobs/${jobId}/progress`);
    updateUI(progress);  // Show last known state
    setTimeout(reconnect, 2000);
};
```

**Файли:**
- `app/models/job.py` (add: current_section, current_attempt, progress_percentage)
- `app/services/background_jobs.py` (save progress кожної секції)
- `app/api/v1/endpoints/jobs.py` (GET /jobs/{id}/progress endpoint)
- `apps/web/lib/websocket.ts` (fallback logic)

**Дедлайн:** Before production
**Час:** 30 min
**Пріоритет:** 🟡 P1 (**RECOMMENDED** - Risk #3 Strategy 3)

---

### 6. Issue #1: Tests Not Run (Phase 2)

**Проблема:** `test_quality_gates.py` створено але не виконано

**Ризик:**
- Mocks можуть мати помилки
- Тести можуть падати на першому запуску
- Невідомі баги в production

**Рішення (30 min):**
```bash
cd /Users/maxmaxvel/AI\ TESI/apps/api
pytest tests/test_quality_gates.py -v

# Якщо падають:
# 1. Виправити imports
# 2. Виправити mocks
# 3. Запустити знову
```

**Очікуваний результат:**
- 3 тести мають пройти
- Можливо потрібні minor fixes (imports, mocks)

**Дедлайн:** Перед Phase 4
**Час:** 30 min
**Пріоритет:** 🟡 P1

---

### 7. Issue #8: Partial Completion - User Decision (Phase 2)

**Проблема:** Якщо 5/20 секцій падають → що робити?
**Ризик:** User отримує 75% документа але платить 100%

**Сценарії:**

**A: 19/20 секцій (95% complete)**
- Користувач: Можливо задоволений
- Рішення: Доставити з попередженням?

**B: 10/20 секцій (50% complete)**
- Користувач: НЕЗАДОВОЛЕНИЙ
- Рішення: Автоматичний refund?

**Потрібне рішення від @maxmaxvel:**
```python
# Який threshold використовувати?

if completion_rate < 0.80:  # 80%? 85%? 90%?
    # AUTO REFUND
    await refund_service.auto_refund(payment_id)
    job.status = "failed_insufficient_quality"

elif completion_rate < 1.0:  # 80-99%
    # DELIVER WITH WARNING
    job.status = "completed_with_warnings"
    await notify_user(f"Document {completion_rate:.0%} complete")

else:  # 100%
    # PERFECT
    job.status = "completed"
```

**Питання до User:**
1. Який мінімальний completion rate для delivery? (80%? 85%? 90%?)
2. Чи показувати missing sections в UI?
3. Чи давати discount якщо < 100%?

**Дедлайн:** Перед production launch
**Час:** 1h (після рішення User)
**Пріоритет:** 🟡 P1

---

### 8. Issue #5: WebSocket Error Notification (Phase 2)

**Проблема:** `manager.send_error()` не перевірено вручну

**Ризик:**
- Frontend може не отримати повідомлення про помилку
- User не дізнається що generation failed

**Рішення (20 min):**
```bash
# 1. Встановити агресивні thresholds:
export QUALITY_MAX_REGENERATE_ATTEMPTS=0
export QUALITY_MIN_PLAGIARISM_UNIQUENESS=99.0

# 2. Запустити test generation
# 3. Відкрити Browser DevTools → WebSocket
# 4. Перевірити чи приходить error message:
{
    "error": "quality_threshold_not_met",
    "section": 5,
    "message": "Section 5 quality validation failed..."
}
```

**Очікуваний результат:**
- WebSocket повідомлення приходить ✅
- Frontend показує error message ✅
- Job status в DB = "failed_quality" ✅

**Дедлайн:** Перед Phase 4
**Час:** 20 min
**Пріоритет:** 🟡 P1

---

### 9. Issue #7: Time Impact UI (Phase 2)

**Проблема:** User очікує 10 хв → отримує 13.5 хв (+35%)

**Ризик:**
- User думає "Why so slow?"
- Негативний feedback

**Рішення (1h):**
```typescript
// Frontend: apps/web/components/GenerationProgress.tsx

const estimateTime = (sections: number) => {
    const baseTime = sections * 2.0;  // 2 min per section
    const regenerationBuffer = sections * 0.5;  // 25% regeneration rate
    return baseTime + regenerationBuffer;
}

// Show realistic estimate:
<p>Estimated time: {estimateTime(sections)} minutes</p>
<p className="text-sm text-gray-500">
    We're ensuring high quality - worth the wait! ✨
</p>

// Update WebSocket handler:
case "regenerating_section":
    showMessage("Improving section quality...");
    // Don't show as error, show as progress
```

**Файли:**
- `apps/web/components/GenerationProgress.tsx` (~30 lines)
- `apps/web/lib/websocket.ts` (update handler)

**Дедлайн:** Перед public beta
**Час:** 1h
**Пріоритет:** 🟡 P1

---

## 🟢 ОПЦІОНАЛЬНО (Nice to Have)

### 10. Risk #4: Defensive Checks for final_content (Phase 2)

**Проблема:** 3 bugs в regeneration loop logic

**Bug 1:** No validation that final_content was set
```python
# Line 538: Direct use without check
section.content = final_content  # Could be None if loop logic broken ❌
```

**Bug 2:** Scores не ініціалізовані якщо gates disabled
```python
if not settings.QUALITY_GATES_ENABLED:
    final_content = humanized_content
    break  # Exit immediately

# Line 538: Save to DB
section.grammar_score = final_grammar_score  # None ❌
```

**Bug 3:** Gates check short-circuit (якщо grammar failed → plagiarism не виконується)

**Рішення (10 min):**
```python
# After regeneration loop (line 530)
if final_content is None:
    logger.error(f"❌ BUG: final_content is None after regeneration loop!")
    raise RuntimeError(
        f"Section {section_index} generation completed but content is None."
    )

# Before DB save
section.content = final_content  # Safe now ✅
```

**Файли:**
- `app/services/background_jobs.py` (defensive check після line 530)

**Дедлайн:** Before production
**Час:** 10 min
**Пріоритет:** 🟢 P2 (bugs are theoretical, not observed)

---

### 11. Risk #9: Context Sections Limit Config (Phase 2)

**Проблема:** Section 100 завантажує 99 previous sections = 198 KB context

**Ризик:**
- Повільна генерація (+5-10 sec)
- Високі AI costs (+$1.00 per doc)
- Token limit risk (для 150+ sections)

**Рішення (15 min) - ✅ RECOMMENDED:**
```python
# 1. Додати в config.py:
QUALITY_GATES_MAX_CONTEXT_SECTIONS: int = Field(
    default=10,
    description="Max previous sections for context (prevents context explosion)"
)

# 2. Змінити query в background_jobs.py (line ~352):
context_result = await db.execute(
    select(DocumentSection)
    .where(
        DocumentSection.document_id == document_id,
        DocumentSection.section_index < section_index,
        DocumentSection.section_index >= max(0, section_index - settings.QUALITY_GATES_MAX_CONTEXT_SECTIONS),
        DocumentSection.status == "completed",
    )
    .order_by(DocumentSection.section_index.desc())
    .limit(settings.QUALITY_GATES_MAX_CONTEXT_SECTIONS)
)
```

**Impact:**
- Section 100 context: 10 sections × 2 KB = 20 KB (замість 198 KB)
- Faster generation: +5-10 sec saved
- Lower AI costs: -$1.00 per document

**Файли:**
- `app/core/config.py` (+5 lines)
- `app/services/background_jobs.py` (query update)

**Дедлайн:** Before 100+ section documents
**Час:** 15 min
**Пріоритет:** 🟢 P2 (optimization, not requirement)

---

### 12. Issue #4: Context Limit Test (Phase 2)

**Проблема:** `.limit(10)` не перевірено на реальному документі

**Рішення (15 min):**
```bash
# Створити test document з 15 sections
# Перевірити що query працює

# Expected: Last 10 sections loaded
# No errors in logs
```

**Дедлайн:** Коли буде час
**Час:** 15 min
**Пріоритет:** 🟢 P2

---

### 13. Issue #6: NULL Scores (Phase 2)

**Проблема:** API error → scores = NULL → admin stats "N/A"

**Рішення (1h):**
```typescript
// Admin UI: Handle NULLs gracefully
{score === null ? (
    <Badge variant="warning">API Check Failed</Badge>
) : (
    <span>{score.toFixed(1)}%</span>
)}

// Average calculation: Skip NULLs
const avgScore = scores
    .filter(s => s !== null)
    .reduce((a, b) => a + b, 0) / scores.length;
```

**Дедлайн:** Before admin panel launch
**Час:** 1h
**Пріоритет:** 🟢 P2

---

## 📊 Priority Summary

| Priority | Count | Issues | Deadline |
|----------|-------|--------|----------|
| 🔴 P0 | 2 | #1 (STRICT_MODE), #2 (Rate limits) | Before production |
| 🟡 P1 | 7 | #3 (Partial CRITICAL), #4 (Heartbeats MUST), #5 (State persist), #6 (Tests), #7 (User decision), #8 (WS test), #9 (UI time) | Before beta |
| 🟢 P2 | 4 | #10 (Risk #4 defensive), #11 (Risk #9 context), #12 (Context test), #13 (NULL scores) | When time allows |

**Total:** 13 активних ризиків

---

## 🎯 Action Plan

### Week 1 (Before Production - CRITICAL)
- [ ] 🔴 #1: STRICT_MODE для API errors (2h)
- [ ] 🔴 #2: Rate limiter + queue (3h)
- [ ] 🟡 #3: **Partial completion fallback** (1h після user approval) - **CRITICAL Strategy 1**
- [ ] 🟡 #4: **WebSocket heartbeats** (20 min) - **MUST IMPLEMENT Strategy 1**
- [ ] 🟡 #5: **State persistence in DB** (30 min) - **RECOMMENDED Strategy 3**

### Week 2 (Before Beta)
- [ ] 🟡 #6: Run pytest + fix (30 min)
- [ ] 🟡 #7: User decision on threshold (5 min discussion + doc)
- [ ] 🟡 #8: Manual WebSocket test (20 min)
- [ ] 🟡 #9: UI time estimates (1h)

### Week 3 (Polish)
- [ ] 🟢 #10: Risk #4 defensive checks (10 min)
- [ ] 🟢 #11: Risk #9 context limit config (15 min)
- [ ] 🟢 #12: Context limit test (15 min)
- [ ] 🟢 #13: Admin UI NULL handling (1h)

**Total time:** ~10h 20min

---

## 🚫 Що НЕ включено (вже вирішено або неактуально)

### Phase 2 Issues (RESOLVED)
- ✅ Issue #9: Section order - False alarm, verified OK

### Phase 3 Risks (ALL MITIGATED)
- ✅ Risk #1: Redis failure - Try/catch handled
- ✅ Risk #2: DB sync - Idempotency prevents
- ✅ Risk #3: TTL too short - Acceptable ($0.00015/doc)
- ✅ Risk #4: Race condition - Job table prevents
- ✅ Risk #5: JSON parsing - Try/catch handled
- ✅ Risk #6: Memory usage - Non-issue (200 bytes/doc)
- ✅ Risk #7: Not cleared - TTL auto-cleanup

### General Risks (ACCEPTED)
- ⏸️ Risk #1: Performance Impact - Trade-off accepted for quality
- ⏸️ Risk #3: WebSocket Timeout - Partial solution, acceptable

---

## 📞 Contact

**Critical issues:** @maxmaxvel
**Technical questions:** AI Agent
**User decisions needed:**
- Issue #3 (partial completion threshold: 80%? 85%? 90%?)
- Issue #7 (same as #3 - user approval needed)

---

**Last Updated:** 02.12.2025 00:15 (додано 3 CRITICAL strategies з Risk #2 та Risk #3)
**Next Review:** After fixing P0 issues + implementing heartbeats + user decision
