# PHASE 0: CRITICAL BUGS - IMPLEMENTATION PLAN
## TesiGo AI Thesis Platform - Execution Plan

**Дата:** 01.11.2025  
**Версія:** 1.0  
**Статус:** READY FOR EXECUTION  
**Owner:** Backend Lead (AI Assistant)  
**Reviewer:** Max (Product Owner)

---

## 🎯 EXECUTIVE SUMMARY

**Мета Phase 0:** Виправити критичні баги що блокують всі інші фази

**Тривалість:** 1 день  
**Пріоритет:** P0 - BLOCKS ALL OTHER PHASES

**Exit Criteria:**
- ✅ All bug fixes implemented
- ✅ All unit tests pass
- ✅ MyPy shows 0 blocking errors
- ✅ Code review approved

---

## 📋 TASK BREAKDOWN

### Task 0.1: Fix `export_document()` SQL Issues

**File:** `apps/api/app/services/document_service.py`  
**Lines:** 437-574  
**Complexity:** Medium  
**Risk:** High

**Bugs Found:**
1. Line 425: `timestamp: time.time()` → returns `float`, SQLite expects `int`
2. MinIO error handling incomplete
3. No validation for empty sections

**Fix Plan:**
```python
# Line 425: Convert to int
timestamp: int = int(time.time())

# Add proper MinIO error handling
try:
    client = Minio(...)
    client.put_object(...)
except (S3Error, ConnectionError) as e:
    logger.error(f"MinIO upload failed: {e}")
    raise ValidationError("Failed to upload document to storage") from e

# Add empty sections check
if not document.sections and not document.content:
    raise ValidationError("Cannot export empty document")
```

**Testing:**
- Unit test: export empty document → 422 error
- Unit test: export with sections → success
- Unit test: MinIO unavailable → graceful error

---

### Task 0.2: Replace `time.time()` with `datetime.utcnow()`

**File:** `apps/api/app/services/ai_service.py`  
**Lines:** 49, 56, 130  
**Complexity:** Low  
**Risk:** Medium

**Bugs Found:**
1. Line 49: `start_time = time.time()` → float timestamp
2. Line 56: `generation_time = int(time.time() - start_time)` → OK
3. Line 130: `generation_time = int(time.time() - start_time)` → OK

**Current Code:**
```python
import time
start_time = time.time()
# ... generation ...
generation_time = int(time.time() - start_time)
```

**Fix Plan:**
```python
from datetime import datetime
start_time = datetime.utcnow()
# ... generation ...
generation_time = int((datetime.utcnow() - start_time).total_seconds())
```

**Changes Required:**
- Files: `apps/api/app/services/ai_service.py`
- Remove `import time`
- Add `from datetime import datetime`
- Replace all `time.time()` calls

**Testing:**
- Verify no performance regression
- Verify timing accuracy
- Check database storage

---

### Task 0.3: Fix `get_user_usage()` SQL using SQLAlchemy `func`

**File:** `apps/api/app/services/ai_service.py`  
**Lines:** 187-208  
**Complexity:** Medium  
**Risk:** High

**Current Code:**
```python
async def get_user_usage(self, user_id: int) -> dict[str, Any]:
    result = await self.db.execute(
        select(
            func.coalesce(User.total_documents_created, 0).label('total_documents'),
            func.coalesce(User.total_tokens_used, 0).label('total_tokens')
        ).where(User.id == user_id)
    )
    stats = result.first()
    return {
        "user_id": user_id,
        "total_documents": stats.total_documents if stats else 0,
        "total_tokens_used": stats.total_tokens if stats and stats.total_tokens else 0,
        "last_updated": datetime.utcnow().isoformat()
    }
```

**BUG:** Already using `func.coalesce()` correctly! ✅

**Wait, let me check document_service.py...**

**Actual Bug in document_service.py Line 58:**
```python
# WRONG:
await self.db.execute(
    update(User)
    .where(User.id == user_id)
    .values(total_documents_created=User.total_documents_created + 1)
)
```

**Fix:**
```python
from sqlalchemy import func

await self.db.execute(
    update(User)
    .where(User.id == user_id)
    .values(
        total_documents_created=func.coalesce(User.total_documents_created, 0) + 1
    )
)
```

**Testing:**
- Unit test: increment from NULL → 1
- Unit test: increment from 5 → 6
- Integration test: check actual DB values

---

### Task 0.4: Fix Type Annotations

**Files to Check:**
- `apps/api/app/services/ai_pipeline/generator.py` (missing `Optional` import)
- All service files for proper return types

**Bugs Found:**
1. `generator.py` Line 24: `Optional[RAGRetriever]` but `Optional` not imported

**Fix Plan:**
```python
# generator.py Line 2
from typing import Any, Optional  # ADD Optional
```

**Also check:**
- `ai_service.py`: All public methods have return types? ✅
- `document_service.py`: All public methods have return types? ✅
- `generator.py`: All public methods have return types? ⚠️ Check

**Testing:**
- Run: `mypy apps/api/app/services/` → 0 errors
- Run: `mypy apps/api/app/` → check all files

---

## 🧪 TESTING PLAN

### Test 0.5: Unit Test for `export_document()`

**File:** `apps/api/tests/test_document_export.py` (create)

```python
import pytest
from unittest.mock import Mock, patch, MagicMock
from app.services.document_service import DocumentService
from app.core.exceptions import ValidationError, NotFoundError

@pytest.mark.asyncio
async def test_export_document_success(db_session):
    """Test successful DOCX export"""
    service = DocumentService(db_session)
    
    # Create mock document
    mock_doc = create_mock_document(has_sections=True)
    
    with patch('app.services.document_service.Minio') as mock_minio:
        result = await service.export_document(
            document_id=1,
            format="docx",
            user_id=1
        )
        
        assert result["format"] == "docx"
        assert "download_url" in result
        assert "expires_at" in result

@pytest.mark.asyncio
async def test_export_document_empty(db_session):
    """Test export fails on empty document"""
    service = DocumentService(db_session)
    
    mock_doc = create_mock_document(has_sections=False, has_content=False)
    
    with pytest.raises(ValidationError):
        await service.export_document(1, "docx", 1)

@pytest.mark.asyncio
async def test_export_document_minio_failure(db_session):
    """Test graceful MinIO failure"""
    service = DocumentService(db_session)
    
    with patch('app.services.document_service.Minio') as mock_minio:
        mock_minio.side_effect = ConnectionError("MinIO unavailable")
        
        with pytest.raises(ValidationError) as exc_info:
            await service.export_document(1, "docx", 1)
        
        assert "storage" in str(exc_info.value).lower()
```

---

### Test 0.6: Unit Test for `get_user_usage()`

**File:** Update existing tests

```python
@pytest.mark.asyncio
async def test_get_user_usage_success(db_session):
    """Test user usage retrieval"""
    service = AIService(db_session)
    
    # Create user with usage
    user = create_user(total_documents=5, total_tokens=1000)
    
    usage = await service.get_user_usage(user.id)
    
    assert usage["total_documents"] == 5
    assert usage["total_tokens_used"] == 1000
    assert usage["user_id"] == user.id

@pytest.mark.asyncio
async def test_get_user_usage_null_values(db_session):
    """Test handling NULL values"""
    service = AIService(db_session)
    
    # Create user with NULL values
    user = create_user(total_documents=None, total_tokens=None)
    
    usage = await service.get_user_usage(user.id)
    
    assert usage["total_documents"] == 0
    assert usage["total_tokens_used"] == 0
```

---

## 🔧 IMPLEMENTATION STEPS

### Step 1: Set Up Environment ✅

**Prerequisites:**
- ✅ Python 3.11 installed
- ✅ Virtual environment activated
- ✅ Dependencies installed
- ✅ Database accessible

**Commands:**
```bash
cd apps/api
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r requirements.txt
```

---

### Step 2: Run Current Tests (Baseline)

**Command:**
```bash
cd apps/api
pytest tests/ -v
```

**Expected:**
- 1 test passes (health check)
- May see some failures

**Record baseline metrics.**

---

### Step 3: Fix Bug 0.1 - export_document()

**File:** `apps/api/app/services/document_service.py`

**Changes:**
1. Line 425: `timestamp: time.time()` → `timestamp: int = int(time.time())`
2. Add MinIO error handling
3. Add empty sections validation

**After fix, run:**
```bash
mypy apps/api/app/services/document_service.py
pytest tests/ -k export
```

---

### Step 4: Fix Bug 0.2 - time.time() → datetime

**File:** `apps/api/app/services/ai_service.py`

**Changes:**
1. Remove `import time`
2. Add `from datetime import datetime`
3. Replace `time.time()` → `datetime.utcnow()`
4. Fix timing calculations

**After fix, run:**
```bash
mypy apps/api/app/services/ai_service.py
pytest tests/ -k ai_service
```

---

### Step 5: Fix Bug 0.3 - SQL func imports

**Files:** `apps/api/app/services/document_service.py`

**Changes:**
1. Add `from sqlalchemy import func` if missing
2. Fix `total_documents_created` increment

**After fix, run:**
```bash
mypy apps/api/app/services/document_service.py
```

---

### Step 6: Fix Bug 0.4 - Type Annotations

**Files:** `apps/api/app/services/ai_pipeline/generator.py`

**Changes:**
1. Add `from typing import Optional`
2. Check all public methods have return types

**After fix, run:**
```bash
mypy apps/api/app/
```

**Target:** 0 blocking errors

---

### Step 7: Write New Tests

**Files:**
- `apps/api/tests/test_document_export.py` (create)
- Update existing test files

**Run:**
```bash
pytest tests/ -v --cov=app --cov-report=term-missing
```

---

### Step 8: Full Validation

**Commands:**
```bash
# Ruff lint
ruff check apps/api/

# MyPy
mypy apps/api/app/ --config-file mypy.ini

# Pytest with coverage
pytest tests/ -v --cov=app --cov-fail-under=10

# Integration test (if docker-compose available)
docker-compose -f docker-compose.test.yml up --abort-on-container-exit
```

---

### Step 9: Code Review

**Check:**
- ✅ All bugs fixed
- ✅ All tests pass
- ✅ MyPy = 0 errors
- ✅ No new issues introduced
- ✅ Code follows style guide

---

### Step 10: Merge

**After approval:**
```bash
git add .
git commit -m "fix(phase0): Fix critical bugs

- Fix export_document() timestamp and error handling
- Replace time.time() with datetime.utcnow()
- Fix SQL func imports and usage
- Add missing type annotations
- Add unit tests for export and usage functions

Closes Phase 0 critical bugs"
git push
```

---

## 📊 SUCCESS METRICS

### Before Phase 0:
- MyPy errors: ? (need to run)
- Unit tests: 1 passing
- Integration tests: 0
- Code coverage: ~0%

### After Phase 0:
- MyPy errors: **0**
- Unit tests: **≥4 passing**
- Integration tests: **≥1**
- Code coverage: **≥10%**

---

## ⚠️ RISKS & MITIGATION

### Risk 1: Breaking Changes
**Mitigation:** Run tests after each fix

### Risk 2: Database Migration Needed
**Mitigation:** These fixes are code-only, no DB changes

### Risk 3: Missing Dependencies
**Mitigation:** Check requirements.txt before starting

### Risk 4: Time Overrun
**Mitigation:** Focus on critical bugs first, defer nice-to-haves

---

## 📝 DEPENDENCIES

**None - Phase 0 can start immediately**

**But requires:**
- Access to codebase ✅
- Development environment ✅
- Database connection available ✅

---

## ✅ EXIT CRITERIA CHECKLIST

Before marking Phase 0 complete:

- [ ] Task 0.1: `export_document()` fixed and tested
- [ ] Task 0.2: All `time.time()` replaced with `datetime.utcnow()`
- [ ] Task 0.3: SQL `func` properly used
- [ ] Task 0.4: All type annotations complete
- [ ] Task 0.5: Unit test for export written and passing
- [ ] Task 0.6: Unit test for usage written and passing
- [ ] Task 0.7: MyPy shows 0 blocking errors
- [ ] Task 0.8: All timestamps verified as datetime objects
- [ ] Task 0.9: Code review complete
- [ ] Task 0.10: Changes merged to develop

---

## 🎯 NEXT PHASE

**After Phase 0 complete → Phase 1: Database Migration**

Phase 1 prerequisites:
- ✅ Phase 0 bugs fixed (ensures clean baseline)
- ⏳ Staging database accessible
- ⏳ Alembic configured

---

## 📞 SUPPORT

**For issues:**
1. Check this document first
2. Review CRITICAL_AUDIT_REPORT.md for context
3. Check EXECUTION_MAP_v2.3.md for overall plan
4. Escalate to Max if blocked

---

**END OF PHASE 0 IMPLEMENTATION PLAN**

**Ready to execute:** YES  
**Estimated time:** 1 day  
**Confidence:** HIGH

