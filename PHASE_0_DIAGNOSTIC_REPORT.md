# Phase 0 Diagnostic Report

## A) DIAGNOSTIC CHECKLIST

### 1. export_document() Implementation
**STATUS: MISSING**

- **Location**: `apps/api/app/services/document_service.py` - function does NOT exist
- **Expected**: Function should exist in `DocumentService` class
- **Called from**: 
  - `apps/api/app/api/v1/endpoints/documents.py:185` (POST /{document_id}/export)
  - `apps/api/app/api/v1/endpoints/documents.py:215` (GET /{document_id}/export/{format})
- **Requirements**: 
  - Preconditions: document.status == "completed"
  - Create DOCX via python-docx library
  - Persist to MinIO storage
  - Update document.docx_path field
  - Return ExportResponse with download_url, expires_at, file_size, format
- **Dependencies**: python-docx==1.1.0 (installed), minio==7.2.0 (installed)
- **Root Cause**: Function was never implemented; endpoint exists but calls non-existent method
- **Minimal Fix**: 
  - Implement `async def export_document(self, document_id: int, format: str, user_id: int) -> Dict[str, Any]`
  - Check document exists and status == "completed"
  - Generate DOCX using python-docx
  - Upload to MinIO
  - Update docx_path
  - Generate presigned URL
  - Return ExportResponse structure

### 2. time.time() Usages
**STATUS: 15 OCCURRENCES FOUND**

**Files with time.time() calls:**
1. `apps/api/app/core/database.py`:
   - Line 103: `context._query_start_time = time.time()`
   - Line 107: `total_ms = (time.time() - ...) * 1000`
   - Line 252: `start = time.time()`
   - Line 254: `query_time = time.time() - start`
   - Line 268: `"timestamp": time.time()`
   - Line 276: `"timestamp": time.time()`

2. `apps/api/app/services/document_service.py`:
   - Line 422: `"timestamp": time.time()`
   - Line 431: `"timestamp": time.time()`

3. `apps/api/app/services/ai_service.py`:
   - Line 47: `start_time = time.time()`
   - Line 54: `generation_time = int(time.time() - start_time)`
   - Line 119: `start_time = time.time()`
   - Line 128: `generation_time = int(time.time() - start_time)`
   - Line 144: `section.completed_at = time.time()` **CRITICAL - WRONG TYPE**
   - Line 154: `completed_at=time.time()` **CRITICAL - WRONG TYPE**
   - Line 201: `"last_updated": time.time()`

**Root Cause**: 
- Mixing performance timing with timestamps
- Lines 144/154 in ai_service.py: completed_at expects datetime, not float timestamp
- Other occurrences are performance timing which is acceptable

**Minimal Fix**:
- Lines 144, 154, 201: Replace `time.time()` → `datetime.utcnow()`
- Add proper import: `from datetime import datetime`
- Keep performance timing (query times, generation times) as-is

### 3. get_user_usage() SQL Issues
**STATUS: WRONG MODEL REFERENCES**

**Location**: `apps/api/app/services/ai_service.py:185-206`

**Current Implementation**:
```python
result = await self.db.execute(
    select(
        Document.total_documents_created,
        Document.total_tokens_used
    ).where(Document.user_id == user_id)
)
```

**Root Cause**: 
- Wrong model! Should query `User` model, not `Document`
- `total_documents_created` and `total_tokens_used` are fields on `User` model (line 30-31 in `apps/api/app/models/auth.py`)
- Missing NULL handling
- Not using SQLAlchemy func.* properly

**Minimal Fix**:
```python
from sqlalchemy import func, select
from app.models.auth import User

result = await self.db.execute(
    select(
        func.coalesce(func.sum(User.total_documents_created), 0).label('total_documents'),
        func.coalesce(func.sum(User.total_tokens_used), 0).label('total_tokens')
    ).where(User.id == user_id)
)
stats = result.first()
```

### 4. MyPy Errors
**STATUS: 154 TOTAL ERRORS**

**Key Categories**:
1. **Missing type annotations**: 89 errors (no-untyped-def, missing-return-type)
2. **Column attribute access**: ~30 errors (using model.Column instead of model instance)
3. **Missing attributes**: ~15 errors (referencing non-existent fields)
4. **Type incompatibility**: ~20 errors

**Critical Blocking Errors**:
- `app/services/ai_service.py:144,154`: `completed_at = time.time()` → wrong type
- `app/services/document_service.py:55`: `Document.total_documents_created` → wrong model
- `app/api/v1/endpoints/documents.py:185,215`: `"DocumentService" has no attribute "export_document"`
- `app/services/admin_service.py:35,298`: Boolean comparison issues

**Root Cause**: Mix of missing function annotations, model field access issues, and type mismatches

**Minimal Fix Plan**:
- Add return type annotations to all public functions
- Fix completed_at assignments to use datetime
- Implement export_document with proper types
- Fix get_user_usage to query correct model
- Fix Boolean comparisons: `is True` → `== True` or just `.where(User.is_active)`

## PHASE 0 DIAGNOSTIC CHECKLIST

- [✅] Found export_document implementation point and exporter path - **NO IMPLEMENTATION EXISTS, MUST CREATE**
- [✅] All time.time() call sites enumerated - **15 total, 3 critical, 12 performance timing (OK)**
- [✅] get_user_usage() call sites and expected outputs known - **WRONG MODEL, FIX SQL**
- [✅] MyPy error list captured (files/lines) - **154 errors, ~20 critical blockers**
- [✅] No architectural changes required - **CONFIRMED - all fixes are local to service layer**
- [✅] Rollback plan prepared (git revert + no DB changes) - **SAFE - no schema changes**

**ALL CHECKLIST ITEMS = YES** ✅

---

## DIAGNOSTIC SUMMARY

### Issue 1: export_document()
- **Priority**: P0
- **Complexity**: Medium
- **Files to modify**: `document_service.py`
- **Dependencies**: python-docx, minio (already installed)
- **Tests needed**: Success case, not-completed case

### Issue 2: time.time() → datetime.utcnow()
- **Priority**: P0
- **Complexity**: Low
- **Files to modify**: `ai_service.py` (3 occurrences)
- **Safety**: High - simple replacement

### Issue 3: get_user_usage() SQL
- **Priority**: P0
- **Complexity**: Low
- **Files to modify**: `ai_service.py`
- **Safety**: High - fix query target

### Issue 4: MyPy Type Hints
- **Priority**: P0
- **Complexity**: Medium
- **Files to modify**: Multiple, focus on touched files
- **Safety**: High - additive only

**READY FOR EXECUTION** ✅

