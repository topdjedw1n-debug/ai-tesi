# 🔧 Fix Plan: TesiGo v2.3 Bug Remediation

**Generated:** 2025-11-02  
**Based On:** BUG_AUDIT_REPORT_v2.3.md

---

## 📋 Fix Strategy

This plan organizes bug fixes by severity and estimated effort. Fixes should be applied in priority order to maximize production readiness.

---

## 🔴 Priority 0: Critical Fixes (Blocks Production)

### 1. Fix Logging Exception Handler
**Effort:** 1 hour  
**Files:** `apps/api/main.py:107`  
**Test:** Verify integration tests show real errors

**Code Change:**
```python
# BEFORE (line 107)
logger.exception(
    f"Unhandled exception: {type(exc).__name__} - {str(exc)}",
    correlation_id=correlation_id
)

# AFTER
import re
exception_str = str(exc)
# Escape any curly braces to prevent format string interpolation
escaped_msg = exception_str.replace("{", "{{").replace("}", "}}")
logger.exception(
    f"Unhandled exception: {type(exc).__name__} - {escaped_msg}",
    correlation_id=correlation_id
)
```

**Verification:**
```bash
cd apps/api && pytest tests/test_api_integration.py -v
```

---

### 2. Fix Response Schema Mismatches
**Effort:** 2 hours  
**Files:** 
- `apps/api/app/schemas/document.py`
- `apps/api/app/schemas/user.py`
- `apps/api/app/schemas/auth.py`

**Changes:**

**DocumentResponse:**
```python
class DocumentResponse(DocumentBase):
    id: int
    user_id: int  # ADD
    status: str
    is_archived: bool = False  # ADD
    created_at: datetime
    updated_at: datetime  # ADD
    word_count: int = 0  # ADD
    estimated_reading_time: int = 0  # ADD
```

**UserResponse:**
```python
class UserResponse(UserBase):
    id: int
    email: str
    full_name: str
    is_active: bool = True  # ADD
    is_verified: bool
    is_admin: bool
    created_at: datetime
    updated_at: datetime  # ADD
    total_tokens_used: int
    total_documents_created: int
    total_cost: float = 0.0  # ADD
```

**MagicLinkResponse:**
```python
class MagicLinkResponse(BaseModel):
    message: str
    email: str
    expires_in: int  # Keep
    expires_in_minutes: int  # ADD
    magic_link: str
```

**Verification:**
```bash
cd apps/api && pytest tests/test_api_integration*.py -v
```

---

### 3. Fix SQLAlchemy Column vs ORM Type Issues
**Effort:** 4 hours  
**Files:** 
- `apps/api/app/services/auth_service.py`
- `apps/api/app/services/document_service.py`
- `apps/api/app/services/ai_service.py`

**Pattern to Fix:**
```python
# WRONG - Direct assignment to Column descriptor
user.is_verified = True  # Line 105
user.last_login = datetime.now()  # Line 106

# CORRECT - Update through ORM object
from sqlalchemy import update
await db.execute(
    update(User)
    .where(User.id == user.id)
    .values(is_verified=True, last_login=datetime.now())
)
await db.commit()
```

**Locations:**
- `auth_service.py`: 105-106, 179
- `document_service.py`: 277-287
- `ai_service.py`: 167-170

**Verification:**
```bash
cd apps/api && mypy app/services/ --config-file mypy.ini
```

---

## 🟠 Priority 1: High Priority (Blocks Features)

### 4. Fix Document Update Exception Logic
**Effort:** 30 minutes  
**File:** `apps/api/app/services/document_service.py:196-219`

**Code Change:**
```python
# BEFORE - Line 196-219
if not document:
    raise NotFoundError("Document not found")

# ... later ...
try:
    # update logic
except Exception as e:  # TOO BROAD
    await self.db.rollback()
    logger.error(f"Error updating document: {e}")
    raise ValidationError(f"Failed to update document: {str(e)}") from e

# AFTER - Only catch specific exceptions
if not document:
    raise NotFoundError("Document not found")

try:
    await self.db.execute(update_stmt)
    await self.db.commit()
except SQLAlchemyError as e:  # More specific
    await self.db.rollback()
    logger.error(f"Error updating document: {e}")
    raise ValidationError(f"Database error updating document") from e
# NotFoundError will propagate naturally
```

**Verification:**
```bash
cd apps/api && pytest tests/test_document_service.py::test_update_document_not_found -v
```

---

### 5. Fix Magic Link Test
**Effort:** 1 hour  
**File:** `tests/test_auth_service_extended.py:80`

**Issue:** Test doesn't create token before verifying

**Code Change:**
```python
@pytest.mark.asyncio
async def test_verify_magic_link_success(db_session):
    service = AuthService(db_session)
    
    # FIRST: Send magic link to create token
    send_result = await service.send_magic_link("test@example.com")
    assert send_result["message"] == "Magic link sent successfully"
    
    # Extract token from magic_link URL
    magic_link_url = send_result["magic_link"]
    token = magic_link_url.split("token=")[1]
    
    # THEN: Verify the token
    result = await service.verify_magic_link(token)
    assert result["access_token"] is not None
```

**Verification:**
```bash
cd apps/api && pytest tests/test_auth_service_extended.py::test_verify_magic_link_success -v
```

---

### 6. Fix Missing Admin Model Attributes
**Effort:** 2 hours  
**File:** `apps/api/app/models/user.py`, `apps/api/app/models/document.py`

**Add Missing Attributes:**

**User Model:**
```python
class User(Base):
    # ... existing fields ...
    total_cost: float = 0.0  # ADD
```

**AIGenerationJob Model (if exists):**
```python
class AIGenerationJob(Base):
    # ... existing fields ...
    input_tokens: int = 0
    output_tokens: int = 0
    duration_ms: int = 0
```

**OR:** Remove references in `admin_service.py` if attributes don't exist

**Verification:**
```bash
cd apps/api && mypy app/services/admin_service.py --config-file mypy.ini
```

---

### 7. Fix Rate Limiter Initialization
**Effort:** 1 hour  
**File:** `apps/api/app/middleware/rate_limit.py:240`

**Code Change:**
```python
# BEFORE
limiter = Limiter(
    key_func=lambda request: request.state.user_id
    if hasattr(request.state, "user_id") else "global",
    storage_uri=storage_options,
    default_limits=["{}/{}".format(settings.RATE_LIMIT_PER_MINUTE, "minute")],
    **storage_options  # ERROR
)

# AFTER
limiter = Limiter(
    key_func=lambda request: request.state.user_id
    if hasattr(request.state, "user_id") else "global",
    storage_uri=redis_url,  # Use string directly
    default_limits=[f"{settings.RATE_LIMIT_PER_MINUTE}/minute"],
    # Remove **storage_options
)
```

**Verification:**
```bash
cd apps/api && mypy app/middleware/rate_limit.py --config-file mypy.ini
cd apps/api && pytest tests/test_rate_limit_init.py -v
```

---

### 8. Add Missing Return Type Annotations
**Effort:** 2 hours  
**Files:** All endpoint files

**Pattern:**
```python
# BEFORE
@router.post("/endpoint")
async def endpoint_func(
    db: AsyncSession = Depends(get_db)
):

# AFTER
from fastapi import Response

@router.post("/endpoint", response_model=EndpointResponse)
async def endpoint_func(
    db: AsyncSession = Depends(get_db)
) -> EndpointResponse:
```

**Locations:**
- `documents.py`: 30, 64, 94, 121, 149, 176, 206
- `auth.py`: 33, 108, 192, 276, 308, 334
- `admin.py`: 26, 71, 121, 175, 225, 271, 323, 370
- `generate.py`: 33, 67, 118, 146

**Verification:**
```bash
cd apps/api && mypy app/api/ --config-file mypy.ini
```

---

## 🟡 Priority 2: Medium Priority (Code Quality)

### 9. Fix Pydantic Config Deprecations
**Effort:** 1 hour  
**Files:** 6 files with deprecated Config class

**Change Pattern:**
```python
# BEFORE
class Settings(BaseSettings):
    ENVIRONMENT: str = "development"
    
    class Config:
        env_file = ".env"
        case_sensitive = True

# AFTER
from pydantic import ConfigDict

class Settings(BaseSettings):
    model_config = ConfigDict(
        env_file=".env",
        case_sensitive=True
    )
    ENVIRONMENT: str = "development"
```

**Files:**
1. `app/core/config.py:14`
2. `app/schemas/user.py:30`
3. `app/schemas/document.py:132`
4. `app/schemas/document.py:216`
5. `app/schemas/auth.py` (if exists)
6. Any other schema files

**Verification:**
```bash
cd apps/api && python -m pytest --collect-only 2>&1 | grep -i pydantic
```

---

### 10. Fix Ruff Config Deprecation
**Effort:** 15 minutes  
**File:** `apps/api/pyproject.toml`

**Change:**
```toml
# BEFORE
[tool.ruff]
line-length = 88
select = ["E", "W", "F", "I", "B", "C4", "UP"]
ignore = ["E501", "B008", "C901"]
per-file-ignores = {"__init__.py" = ["F401"]}

# AFTER
[tool.ruff]
line-length = 88

[tool.ruff.lint]
select = ["E", "W", "F", "I", "B", "C4", "UP"]
ignore = ["E501", "B008", "C901"]
per-file-ignores = {"__init__.py" = ["F401"]}
```

**Verification:**
```bash
cd apps/api && ruff check app/
```

---

### 11. Fix FastAPI Query Deprecation
**Effort:** 5 minutes  
**File:** `apps/api/app/api/v1/endpoints/admin.py:179`

**Change:**
```python
# BEFORE
group_by: str = Query("day", regex="^(day|week|month)$")

# AFTER
group_by: str = Query("day", pattern="^(day|week|month)$")
```

**Verification:**
```bash
cd apps/api && python -m pytest --collect-only 2>&1 | grep -i deprecation
```

---

### 12. Add Type Stubs for Anthropic/OpenAI
**Effort:** 1 hour  
**Files:** `ai_pipeline/generator.py`, `ai_pipeline/humanizer.py`

**Option 1:** Add proper type ignores with justification

```python
# After line imports
from anthropic import AsyncAnthropic

class SectionGenerator:
    async def _call_anthropic(self, model: str, prompt: str) -> str:
        client = AsyncAnthropic(api_key=api_key)
        # type: ignore[attr-defined]  # Anthropic SDK has dynamic attributes
        response = await client.messages.create(...)
        return response.content[0].text
```

**Option 2:** Use stubs or update package

**Verification:**
```bash
cd apps/api && mypy app/services/ai_pipeline/ --config-file mypy.ini
```

---

### 13. Remove Unused Type Ignores
**Effort:** 15 minutes  
**Files:** `app/core/database.py`, `app/middleware/rate_limit.py`

**Locations:**
- `database.py`: 104, 108
- `rate_limit.py`: 269

**Action:** Either remove `# type: ignore` or fix the actual issue

**Verification:**
```bash
cd apps/api && mypy app/core/ app/middleware/ --config-file mypy.ini
```

---

### 14. Add .gitignore for test.db
**Effort:** 5 minutes  
**File:** `.gitignore` or `apps/api/.gitignore`

**Add:**
```gitignore
# Test files
*.db
test.db
*.sqlite
*.sqlite3
```

**Verification:**
```bash
cd apps/api && git status | grep test.db
```

---

## 🟢 Priority 3: Low Priority (Nice to Have)

### 15. Address Frontend TODOs
**Effort:** 4-8 hours  
**Files:** Frontend `.tsx` files

**TODOs:**
1. `GenerateSectionForm.tsx:77` - Implement actual API call
2. `DocumentsList.tsx:45` - Fetch real documents
3. `RecentActivity.tsx:49` - Fetch real activities
4. `StatsOverview.tsx:23` - Fetch real stats
5. `settings/page.tsx:15` - Implement settings save
6. `AuthProvider.tsx:52,71,133` - Backend integration

**Action:** Create tasks in project management or remove TODOs if not planned

---

### 16. Run Dependency Audits
**Effort:** 30 minutes  
**Tools:** `pip-audit`, `npm audit`, `safety`

**Commands:**
```bash
cd apps/api
pip-audit --desc --output-format=json > ../../reports/DEPENDENCY_AUDIT.json

cd apps/web
npm audit --json > ../../reports/NPM_AUDIT.json
```

---

### 17. Complete Documentation Cleanup
**Effort:** 1 hour  

**Actions:**
1. Update `P0_P1_COMPLETION_SUMMARY.md` with correct Python version
2. Update coverage claims to 49%
3. Document test failure counts accurately
4. Add missing migration docs

---

## 📊 Fix Schedule

### Week 1: Critical Fixes
- **Day 1:** Fixes 1-3 (7 hours)
- **Day 2:** Fixes 4-7 (4.5 hours)
- **Day 3:** Fixes 8 (2 hours)
- **Day 4:** Testing and verification
- **Day 5:** P0 bug fixes refinement

**Goal:** All P0 and P1 fixes complete, tests passing

### Week 2: Quality Improvements
- **Day 1-2:** Fixes 9-11 (1.5 hours)
- **Day 3:** Fixes 12-13 (1.25 hours)
- **Day 4:** Coverage improvements to 60%
- **Day 5:** MyPy cleanup to <50 errors

**Goal:** 60% coverage, <50 MyPy errors

### Week 3: Polish & Documentation
- **Day 1-2:** Coverage to 80%
- **Day 3:** Frontend TODOs
- **Day 4:** Dependency audits
- **Day 5:** Documentation updates

**Goal:** Production-ready state

---

## ✅ Verification Checklist

After each phase, verify:

### Phase 1 (P0/P1 Fixes)
- [ ] All 69 tests passing
- [ ] No critical MyPy errors
- [ ] Integration tests working
- [ ] API endpoints return correct schemas
- [ ] No logging KeyErrors

### Phase 2 (Quality)
- [ ] MyPy errors <50
- [ ] Coverage ≥60%
- [ ] No deprecation warnings
- [ ] Ruff passes cleanly

### Phase 3 (Production Ready)
- [ ] Coverage ≥80%
- [ ] All MyPy errors resolved or justified
- [ ] Dependency audit clean
- [ ] Documentation accurate
- [ ] Full system test successful

---

## 🎯 Success Criteria

**Production Ready When:**
1. ✅ 100% test pass rate
2. ✅ 80% code coverage
3. ✅ 0 P0/P1 bugs
4. ✅ All MyPy errors resolved or justified
5. ✅ No security vulnerabilities
6. ✅ Documentation accurate
7. ✅ Performance tests pass

---

**End of Fix Plan**


