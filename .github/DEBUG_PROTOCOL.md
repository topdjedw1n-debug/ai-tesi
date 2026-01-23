# Systematic Debugging Protocol

> **Adapted from obra/superpowers for TesiGo Platform**
> Single source of truth for debugging approach in this project.

**Version:** 1.0 | **Updated:** 2026-01-22 | **Status:** ACTIVE

---

## 🚨 THE IRON LAW

```
❌ NO FIXES WITHOUT ROOT CAUSE INVESTIGATION FIRST
```

**If you haven't completed Phase 1, you CANNOT propose fixes.**

Random fixes waste time and create new bugs. Quick patches mask underlying issues.

**Core principle:** ALWAYS find root cause before attempting fixes. Symptom fixes are failure.

---

## 📋 WHEN TO USE

Use for ANY technical issue:
- ✅ Test failures (pytest, mypy, ruff)
- ✅ Bugs in production/development
- ✅ Unexpected API behavior
- ✅ Database query issues
- ✅ AI generation quality problems
- ✅ Background job failures
- ✅ Integration issues (Stripe, MinIO, Redis)

**Use ESPECIALLY when:**
- Under time pressure (emergencies make guessing tempting)
- "Just one quick fix" seems obvious
- You've already tried multiple fixes
- Previous fix didn't work
- You don't fully understand the issue

**DON'T skip when:**
- Issue seems simple (simple bugs have root causes too)
- You're in a hurry (rushing guarantees rework)
- Manager wants it fixed NOW (systematic is faster than thrashing)

---

## 🔄 THE FOUR PHASES

**You MUST complete each phase before proceeding to the next.**

### Phase 1: Root Cause Investigation

**BEFORE attempting ANY fix:**

#### 1. Read Error Messages Carefully
```python
# FastAPI/Pydantic errors are descriptive
ValidationError: 1 validation error for DocumentCreate
page_count
  ensure this value is greater than or equal to 3
  (type=value_error.number.not_ge; limit_value=3)

# SQLAlchemy async errors
RuntimeError: greenlet_spawn has not been called; can't call await_only()
# → Mixing sync/async operations

# Alembic migration errors
sqlalchemy.exc.IntegrityError: (psycopg2.errors.ForeignKeyViolation)
# → Check migration order
```

- Don't skip past errors or warnings
- Read stack traces COMPLETELY (every line)
- Note line numbers, file paths, error codes
- Check logs: `logs/api.log`, `docker logs tesigo-api`

#### 2. Reproduce Consistently
```bash
# For tests
cd apps/api && pytest tests/test_specific.py::test_name -v

# For API endpoints
curl -X POST http://localhost:8000/api/v1/endpoint \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"data": "test"}'

# For background jobs
# Check Redis logs, job status in DB
```

**Questions to answer:**
- Can you trigger it reliably?
- What are the exact steps?
- Does it happen every time?
- If not reproducible → gather more data, DON'T guess

#### 3. Check Recent Changes
```bash
# What changed that could cause this?
git log --oneline -10
git diff HEAD~5

# Database migrations
cd apps/api && alembic history
alembic current

# Dependency changes
git diff HEAD~5 -- apps/api/pyproject.toml
```

#### 4. Gather Evidence in Multi-Component Systems

**TesiGo has multiple components:**
- Frontend (Next.js) → API (FastAPI) → Services → Database (PostgreSQL)
- Background Jobs (Redis/Celery) → AI Services (OpenAI/Anthropic) → RAG (Tavily)
- Storage (MinIO) → Export (DOCX/PDF)

**BEFORE proposing fixes, add diagnostic instrumentation:**

```python
# Layer 1: API endpoint
@router.post("/generate")
async def generate_document(request: DocumentCreate):
    logger.info("Generate request received", extra={
        "topic": request.topic,
        "page_count": request.page_count,
        "language": request.language,
        "user_id": request.user_id
    })
    # ... rest of code

# Layer 2: Service
async def create_document(db, data, user_id):
    logger.info("Service: Creating document", extra={
        "data": data.dict(),
        "user_id": user_id
    })
    # ... database operation
    logger.info("Service: Document created", extra={
        "doc_id": doc.id
    })

# Layer 3: Background job
async def generate_sections(doc_id):
    logger.info("Job: Starting generation", extra={
        "doc_id": doc_id,
        "worker_id": os.getpid()
    })
    # ... AI generation
    logger.info("Job: Generation complete", extra={
        "doc_id": doc_id,
        "sections_count": len(sections)
    })
```

**Run once to gather evidence showing WHERE it breaks.**

#### 5. Trace Data Flow (Root Cause Tracing)

**WHEN error is deep in call stack:**

Example: Document generation fails with "Invalid page count"

```python
# Symptom: Error in AI service
AIServiceError: Invalid page count: 0

# Trace backwards:
# 5. ai_service.generate() receives page_count=0
# 4. generate_sections() passes doc.page_count (0)
# 3. document_service.create() saves with page_count=0
# 2. API endpoint receives request.page_count=0
# 1. Frontend sends {page_count: null} → Pydantic converts to 0

# ROOT CAUSE: Frontend validation missing
```

**Keep tracing up until you find the source. Fix at source, not at symptom.**

---

### Phase 2: Pattern Analysis

**Find the pattern before fixing:**

#### 1. Find Working Examples
```bash
# Locate similar working code
grep_search "async def create_document" apps/api/

# Find working tests
find apps/api/tests -name "*document*test.py"
```

#### 2. Compare Against References
- Read FastAPI docs for pattern
- Check SQLAlchemy 2.0 async patterns
- Review our existing implementations (AI_PLAYBOOK.md)

#### 3. Identify Differences
```python
# ✅ Working code
async def working_function(db: AsyncSession):
    result = await db.execute(select(User))
    return result.scalars().all()

# ❌ Broken code
async def broken_function(db: AsyncSession):
    result = db.execute(select(User))  # Missing await!
    return result.scalars().all()
```

#### 4. Understand Dependencies
- Async vs sync (all DB operations must be async)
- DB session management (endpoint vs background job)
- ENV variables (check .env.example)
- Service dependencies (Redis up? MinIO accessible?)

---

### Phase 3: Hypothesis and Testing

**Scientific method:**

#### 1. Form Single Hypothesis
```
"I think the error occurs because SQLAlchemy session is not committed
in background jobs, causing the document to not be visible to the
export service."
```

**Write it down. Be specific, not vague.**

#### 2. Test Minimally
```python
# Make the SMALLEST possible change
async def background_task():
    async with AsyncSessionLocal() as db:
        doc = await create_document(db, data)
        await db.commit()  # ← ONLY change
        await db.refresh(doc)
```

**One variable at a time. Don't fix multiple things at once.**

#### 3. Verify Before Continuing
```bash
# Run specific test
pytest tests/test_document_creation.py -v

# Check logs
tail -f logs/api.log

# Did it work?
# YES → Phase 4
# NO → Form NEW hypothesis (don't add more fixes on top)
```

#### 4. When You Don't Know
- Say "I don't understand why X happens"
- Don't pretend to know
- Ask for help in team chat
- Research more (docs, GitHub issues)

---

### Phase 4: Implementation

**Fix the root cause, not the symptom:**

#### 1. Create Failing Test Case
```python
# tests/test_document_service.py
@pytest.mark.asyncio
async def test_background_job_document_visibility():
    """Test that document created in background job is visible."""
    async with AsyncSessionLocal() as db:
        # Create document in background context
        doc = await document_service.create(db, data)
        await db.commit()
        doc_id = doc.id

    # Verify in new session (simulates different service)
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Document).where(Document.id == doc_id)
        )
        doc = result.scalar_one_or_none()
        assert doc is not None  # This should pass
```

**MUST have test before fixing.**

#### 2. Implement Single Fix
```python
# Fix the root cause identified
async def create_document_background(data):
    async with AsyncSessionLocal() as db:
        doc = await document_service.create(db, data)
        await db.commit()  # ← Fix: explicit commit
        await db.refresh(doc)
        return doc
```

**ONE change at a time. No "while I'm here" improvements.**

#### 3. Verify Fix
```bash
# Test passes now?
pytest tests/test_document_service.py::test_background_job_document_visibility -v

# No other tests broken?
pytest tests/ -v

# Issue actually resolved?
# Run manual test in development
```

#### 4. If Fix Doesn't Work
**STOP. Count: How many fixes have you tried?**

- **If < 3:** Return to Phase 1, re-analyze with new information
- **If ≥ 3:** STOP and question the architecture (step 5 below)
- **DON'T attempt Fix #4 without architectural discussion**

#### 5. If 3+ Fixes Failed: Question Architecture

**Pattern indicating architectural problem:**
- Each fix reveals new shared state/coupling/problem in different place
- Fixes require "massive refactoring" to implement
- Each fix creates new symptoms elsewhere

**STOP and question fundamentals:**
- Is this pattern fundamentally sound?
- Are we "sticking with it through sheer inertia"?
- Should we refactor architecture vs. continue fixing symptoms?

**Discuss with team before attempting more fixes.**

**This is NOT a failed hypothesis - this is a wrong architecture.**

---

## 🚩 RED FLAGS - STOP AND FOLLOW PROCESS

If you catch yourself thinking:

- ❌ "Quick fix for now, investigate later"
- ❌ "Just try changing X and see if it works"
- ❌ "Add multiple changes, run tests"
- ❌ "Skip the test, I'll manually verify"
- ❌ "It's probably X, let me fix that"
- ❌ "I don't fully understand but this might work"
- ❌ "Pattern says X but I'll adapt it differently"
- ❌ "Here are the main problems: [lists fixes without investigation]"
- ❌ Proposing solutions before tracing data flow
- ❌ **"One more fix attempt" (when already tried 2+)**
- ❌ **Each fix reveals new problem in different place**

**ALL of these mean: STOP. Return to Phase 1.**

**If 3+ fixes failed:** Question the architecture (see Phase 4.5)

---

## 🎯 TESIGO-SPECIFIC DEBUGGING

### FastAPI Issues

```python
# Check if endpoint is async
@router.get("/endpoint")
async def endpoint():  # ← Must be async if using await inside
    await db.execute(...)

# Check dependency injection
async def endpoint(
    db: AsyncSession = Depends(get_db),  # ← Correct order
    user: User = Depends(get_current_user)
):
    pass

# Check exception handling
from app.core.exceptions import ValidationError
raise ValidationError("Message")  # Not HTTPException
```

### SQLAlchemy Async Issues

```python
# ✅ Correct: Async all the way
result = await db.execute(select(User))
users = result.scalars().all()

# ❌ Wrong: Missing await
result = db.execute(select(User))  # Error!

# ✅ Correct: Background job session
async with AsyncSessionLocal() as db:
    await db.execute(...)
    await db.commit()  # Explicit commit

# ❌ Wrong: Using get_db() in background
async def background_task(db = Depends(get_db)):  # Error!
```

### Background Job Issues

```python
# Check Redis connection
redis_client.ping()

# Check job status
from app.core.database import AsyncSessionLocal
async with AsyncSessionLocal() as db:
    result = await db.execute(
        select(Document).where(Document.id == doc_id)
    )
    doc = result.scalar_one()
    print(f"Status: {doc.status}")

# Check logs
tail -f logs/api.log | grep "job_id"
```

### AI Service Issues

```python
# Check API keys
import os
assert os.getenv("OPENAI_API_KEY"), "Missing OpenAI key"
assert os.getenv("ANTHROPIC_API_KEY"), "Missing Anthropic key"

# Check rate limits
# OpenAI: 10 req/min in free tier
# Implement exponential backoff

# Check response format
logger.debug("AI response", extra={"response": response.dict()})
```

---

## 🛡️ DEFENSE-IN-DEPTH VALIDATION

**After finding root cause, add validation at EVERY layer.**

### Example: Empty Directory Bug

```python
# Layer 1: Entry Point Validation
async def create_document(data: DocumentCreate, user_id: UUID):
    if not data.topic or data.topic.strip() == "":
        raise ValidationError("Topic cannot be empty")
    if not 3 <= data.page_count <= 200:
        raise ValidationError("Page count must be 3-200")

# Layer 2: Service Validation
async def generate_document(doc_id: UUID):
    if not doc_id:
        raise ValidationError("Document ID required")
    doc = await get_document(doc_id)
    if not doc:
        raise NotFoundError("Document not found")

# Layer 3: Environment Guards
async def save_to_minio(file_path: str):
    if settings.ENVIRONMENT == "test":
        # Refuse to save outside temp directory in tests
        import tempfile
        if not file_path.startswith(tempfile.gettempdir()):
            raise ValueError(f"Refusing save outside temp: {file_path}")

# Layer 4: Debug Instrumentation
logger.debug("Saving file", extra={
    "file_path": file_path,
    "cwd": os.getcwd(),
    "env": settings.ENVIRONMENT,
    "stack": traceback.format_stack()
})
```

**Don't stop at one validation point. Add checks at every layer.**

---

## 🔍 SUPPORTING TECHNIQUES

### Root Cause Tracing Template

```python
# 1. Observe symptom
# Error: Document not found in export

# 2. Find immediate cause
# export_service.get_document(doc_id) returns None

# 3. Ask: What called this?
# background_job.export_document(doc_id)
#   → called by generate_document_task(doc_id)
#   → called by API endpoint /generate

# 4. Keep tracing up
# doc_id passed correctly
# Document created in DB but not committed

# 5. Find original trigger
# Background job uses new session without commit
# ROOT CAUSE: Missing await db.commit() in background context
```

### Stack Trace Logging

```python
import traceback

logger.debug("Debug context", extra={
    "doc_id": doc_id,
    "user_id": user_id,
    "status": doc.status,
    "stack": traceback.format_stack()
})
```

---

## 📊 QUICK REFERENCE

| Phase | Key Activities | Success Criteria |
|-------|----------------|------------------|
| **1. Root Cause** | Read errors, reproduce, check changes, gather evidence, trace data flow | Understand WHAT and WHY |
| **2. Pattern** | Find working examples, compare against references | Identify differences |
| **3. Hypothesis** | Form theory, test minimally, verify | Confirmed or new hypothesis |
| **4. Implementation** | Create test, fix once, verify | Bug resolved, tests pass |

---

## ⚠️ COMMON RATIONALIZATIONS (DON'T FALL FOR THESE)

| Excuse | Reality |
|--------|---------|
| "Issue is simple, don't need process" | Simple issues have root causes too. Process is fast. |
| "Emergency, no time for process" | Systematic is FASTER than guess-and-check thrashing. |
| "Just try this first, then investigate" | First fix sets the pattern. Do it right. |
| "I'll write test after confirming fix works" | Untested fixes don't stick. Test first. |
| "Multiple fixes at once saves time" | Can't isolate what worked. Causes new bugs. |
| "I see the problem, let me fix it" | Seeing symptoms ≠ understanding root cause. |
| "One more fix attempt" (after 2+ failures) | 3+ failures = architectural problem. |

---

## ✅ DEFINITION OF DONE

Before claiming a bug is fixed:

- [ ] Root cause identified (not just symptom)
- [ ] Failing test created (pytest)
- [ ] Single fix applied
- [ ] Test passes
- [ ] No other tests broken (`pytest tests/ -v`)
- [ ] No new errors in logs
- [ ] Defense-in-depth validation added (if applicable)
- [ ] Documentation updated (if behavior changed)
- [ ] Code reviewed by another developer

---

## 🔗 RELATED DOCUMENTS

- **Rules & Workflow:** `.github/copilot-instructions.md`
- **Code Patterns:** `.github/AI_PLAYBOOK.md`
- **Architecture:** `docs/MASTER_DOCUMENT.md`
- **Quality Gates:** `QUALITY_GATE.md`
- **Current Tasks:** `docs/MVP_PLAN.md`

---

**Remember:**

```
Quality > Speed
Proof > Assumptions
Ask > Guess
Root Cause > Quick Fix
```

**Original methodology:** [obra/superpowers/systematic-debugging](https://github.com/obra/superpowers/tree/main/skills/systematic-debugging)
