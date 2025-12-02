# TesiGo - AI Coding Agent Instructions

## 🔴 КРИТИЧНЕ: Правила якості роботи

**⚠️ ПЕРЕД КОЖНОЮ ЗАДАЧЕЮ:**
1. **ПРОЧИТАТИ:** `/.github/AGENT_QUALITY_RULES.md` (200 lines - work methodology)
2. **ПЕРЕВІРИТИ:** Відповідність 5 core documents (listed in "Documentation Hierarchy")
3. **ЗАСТОСУВАТИ:** Quality checklist (питання до себе перед підтвердженням)

**Головне правило:** ❌ **НЕ робити задачу "щоб просто зробити"**

### Мінімальний чеклист з AGENT_QUALITY_RULES.md:
- [ ] Зрозумів що треба? Є сумніви? → ЗАПИТАТИ
- [ ] Перевірив РЕАЛЬНИЙ код (read_file/grep_search)?
- [ ] Відповідає документації (MASTER_DOCUMENT, DECISIONS_LOG)?
- [ ] Можу довести правильність (показати докази)?
- [ ] Оновив документацію (MVP_PLAN якщо треба)?

**Якщо хоча б один "НІ" → ЗУПИНИТИСЯ і уточнити. Якість > Швидкість.**

---

## Project Overview

**TesiGo** is an AI-powered academic paper generation platform (theses, dissertations, coursework). Full-stack SaaS: FastAPI backend (Python 3.11) + Next.js 14 frontend (App Router).

**Business Model:** Pay-per-page (€0.50/page base, dynamic via admin panel), EUR only, 3-200 pages, magic link auth, Stripe payments.

**Refund Policy:**
- Auto-refund on technical system errors
- User-requested refunds require admin approval with justification  
- NO automatic cancellation after payment

**Last Updated:** 28 листопада 2025 | **Version:** 2.3 | **Status:** 🟡 Core functionality focus

## 🔴 CRITICAL: Temporary Solutions Protocol

**SACRED RULE:** Every temporary solution MUST be documented in `/docs/MVP_PLAN.md` → "⚠️ ТИМЧАСОВІ РІШЕННЯ"

**When creating ANY temporary solution (mock data, hardcode, skip validation):**
1. ✅ Add entry to `/docs/MVP_PLAN.md` with date, file, reason, TODO
2. ✅ Add `TODO` comment in code referencing MVP_PLAN entry
3. ✅ Estimate priority (🔴 HIGH / 🟡 MEDIUM / 🟢 LOW) and time

**Example:**
```python
# ⚠️ TEMPORARY: Mock data - See /docs/MVP_PLAN.md → "ТИМЧАСОВІ РІШЕННЯ" → #1
# TODO: Replace with real DB query (Priority: 🟡 MEDIUM, Time: 1-2h)
return {"total_users": 0}
```

**Full protocol:** `/docs/TEMPORARY_SOLUTIONS_PROTOCOL.md` | **NO EXCEPTIONS.**

## Architecture & Data Flow

```
Frontend (Next.js 14)
    ↓ HTTP/WS
FastAPI Backend (:8000)
    ↓ async queries
PostgreSQL (:5432) + Redis (:6379) + MinIO (:9000)
    ↓ AI calls
OpenAI/Anthropic APIs → RAG → Section Generation
```

**Key Structure:**
- `apps/api/app/api/v1/endpoints/` - REST API routes
- `apps/api/app/services/` - Business logic (MUST use async)
- `apps/api/app/services/ai_pipeline/` - RAG + generation orchestration
- `apps/api/app/models/` - SQLAlchemy ORM (all async)
- `apps/api/app/core/database.py` - Session management (lazy init, connection pooling)
- `apps/web/app/` - Next.js routes (App Router)
- `apps/web/lib/api.ts` - Centralized API client with auto-refresh

## Critical Workflows

### 1. Database Session Management
**ALWAYS use dependency injection, NEVER create sessions manually:**
```python
from app.core.database import get_db
from sqlalchemy.ext.asyncio import AsyncSession

async def my_endpoint(db: AsyncSession = Depends(get_db)):
    # Session automatically managed by FastAPI
    result = await db.execute(select(User).where(User.id == 1))
    user = result.scalar_one_or_none()
    # Auto-commit on success, auto-rollback on exception
```

**Background jobs use context manager:**
```python
from app.core.database import AsyncSessionLocal

async def background_task():
    async with AsyncSessionLocal() as db:
        # Explicit session lifecycle for background tasks
        await db.execute(...)
        await db.commit()  # Must commit explicitly
```

### 2. Background Job Pattern
**Location:** `apps/api/app/services/background_jobs.py`
```python
# API endpoint starts job
@router.post("/generate")
async def start_generation(
    document_id: int,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    job = AIGenerationJob(document_id=document_id, status="queued")
    db.add(job)
    await db.flush()  # Get job.id before commit
    await db.commit()
    
    # Start in background AFTER commit
    background_tasks.add_task(
        BackgroundJobService.generate_full_document_async,
        document_id, user_id, job.id
    )
    return {"job_id": job.id, "status": "queued"}

# Background task updates job status
async def generate_full_document_async(document_id, user_id, job_id):
    async with AsyncSessionLocal() as db:
        # Update to "running"
        await db.execute(update(AIGenerationJob).where(...).values(status="running"))
        await db.commit()
        
        # Do work, send WebSocket updates
        await manager.send_progress(user_id, {"progress": 45})
        
        # Mark complete
        await db.execute(update(AIGenerationJob).where(...).values(status="completed"))
        await db.commit()
```

### 3. AI Generation Pipeline
**Entry:** `apps/api/app/services/ai_pipeline/generator.py` → `SectionGenerator.generate_section()`

**Supported Models:**
- OpenAI: GPT-4, GPT-4 Turbo, GPT-3.5 Turbo
- Anthropic: Claude 3.5 Sonnet, Claude 3 Opus
- Selection: Automatic by system (user doesn't choose)

**RAG Sources:**
- ✅ Semantic Scholar (implemented)
- 🔜 Perplexity API (to implement)
- 🔜 Tavily API (to implement) 
- 🔜 Serper API (to implement)

**Flow:**
1. **Input Processing** - Validate requirements, estimate costs
2. **RAG Retrieval** (`rag_retriever.py`) - Search academic sources
3. **Outline Generation** - Create structure, define sections, allocate pages
4. **Content Generation** - Generate by SECTIONS (not chunks!), include sources
5. **Citation Formatting** (`citation_formatter.py`) - APA/MLA/Chicago
6. **Quality Assurance** - Grammar check (LanguageTool), plagiarism check (Copyscape)
7. **Humanization** (`humanizer.py`) - Optional anti-detection pass
8. **Memory Management** - Stream to storage, save checkpoints, `gc.collect()` after each section

**Memory pattern:**
```python
context_sections = []  # Accumulate previous sections
for section in outline:
    result = await generate_section(..., context_sections)
    context_sections.append({"title": ..., "content": result["content"]})
    # Memory cleared after full document, not per-section
```

### 4. Testing Commands
```bash
# Run all tests (uses sqlite in-memory)
cd apps/api && pytest tests/ -v

# Run specific test
pytest tests/test_async_generation.py::test_job_completes_successfully -v

# With coverage
pytest tests/ --cov=app --cov-report=html

# Environment (automatically set by run-tests.sh)
export DATABASE_URL="sqlite+aiosqlite:///./test.db"
export SECRET_KEY="test-secret-key-minimum-32-chars-long-1234567890"
```

### 5. Development Setup (5 min)
```bash
# 1. Start infrastructure
cd infra/docker && docker-compose up -d

# 2. Backend (Terminal 1)
cd apps/api
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000

# 3. Frontend (Terminal 2)
cd apps/web
npm install && npm run dev  # port 3000

# 4. Verify
curl http://localhost:8000/health  # Backend
curl http://localhost:3000/api/health  # Frontend
```

## Critical Security Patterns

### 1. IDOR Protection (MANDATORY)
**Every endpoint accessing user data MUST check ownership:**
```python
async def get_document(doc_id: int, current_user: User, db: AsyncSession):
    doc = await db.get(Document, doc_id)
    if not doc or doc.user_id != current_user.id:
        raise HTTPException(403, "Not authorized")  # Or 404 to hide existence
    return doc
```

### 2. Admin vs User Authentication
**Two separate auth systems:**
```python
# Regular users (magic link, JWT)
@router.get("/user-data")
async def get_user_data(current_user: User = Depends(get_current_user)):
    pass

# Admins (password + session, see admin_auth_service.py)
@router.get("/admin/stats")
async def admin_stats(current_user: User = Depends(get_admin_user)):
    pass
```

### 3. Payment → Generation Race Condition
**Location:** `apps/api/app/api/v1/endpoints/payment.py` webhook handler
```python
# CRITICAL: Use SELECT...FOR UPDATE to prevent duplicate jobs
existing_job = await db.execute(
    select(AIGenerationJob)
    .where(AIGenerationJob.document_id == doc_id, ...)
    .with_for_update()  # Locks rows during transaction
)
if existing_job.scalar_one_or_none():
    logger.info("Job already exists, skipping duplicate")
    return
# Create job within locked transaction
job = AIGenerationJob(...)
db.add(job)
await db.commit()  # Commit BEFORE starting background task
background_tasks.add_task(...)  # Start AFTER commit
```

## Project-Specific Conventions

### Type Hints (Enforced by mypy)
```python
# All functions MUST have complete type annotations
async def process_payment(
    user_id: int,
    amount: Decimal,  # Use Decimal for money, never float
    pages: int
) -> Payment:  # Return type required
    pass

# Use | for unions (Python 3.11+), not Optional/Union
def get_config(key: str) -> str | None:
    pass
```

### Error Handling
```python
from app.core.exceptions import APIException, NotFoundError, ValidationError

# Use custom exceptions, not HTTPException directly
raise ValidationError("Page count must be 3-200")  # 400
raise NotFoundError("Document not found")  # 404
raise APIException(403, error_code="INVALID_OWNER", detail="...")  # Custom

# Frontend receives:
# {"error_code": "INVALID_OWNER", "detail": "...", "status_code": 403, "timestamp": "..."}
```

### Async Everywhere (Backend)
```python
# ✅ Correct - all I/O is async
async def fetch_data(db: AsyncSession):
    result = await db.execute(select(User))
    await redis.set("key", "value")
    await http_client.get("https://api.example.com")

# ❌ Wrong - blocking I/O in async function
async def bad_example():
    time.sleep(1)  # Blocks entire event loop!
    requests.get("...")  # Use httpx.AsyncClient instead
```

### Database Migrations
```bash
# Create migration (after model changes)
cd apps/api
alembic revision --autogenerate -m "Add user_preferences table"

# Review generated migration in migrations/versions/
# Edit if needed (autogenerate isn't perfect)

# Apply migration
alembic upgrade head

# Rollback
alembic downgrade -1
```

## Anti-Patterns (DO NOT DO)

```python
# ❌ Creating session manually
from sqlalchemy.orm import Session
db = Session()  # NEVER! Use Depends(get_db)

# ❌ Mutable default arguments
def process(items: list = []):  # Bug: shared across calls
    items.append(1)

# ❌ Ignoring type hints
def calculate(data):  # Missing types
    return data * 2

# ❌ SQL injection
query = f"SELECT * FROM users WHERE id = {user_id}"  # NEVER!

# ❌ Exposing secrets
OPENAI_API_KEY = "sk-..."  # Use settings.OPENAI_API_KEY

# ❌ Float for currency
price = 10.50  # Use Decimal("10.50")

# ❌ Sync code in async context
def sync_helper():
    return db.query(User).all()  # Must be async
```

## Key Business Rules

- **Payment Model:** Pay-per-page (€0.50/page base price, dynamic via admin panel)
- **Currency:** EUR only (no multi-currency support)
- **Min/Max Pages:** 3 minimum (€1.50 min), 200 maximum
- **Supported Languages:** EN, DE, FR, ES, IT, CS, UK (NOT Ukrainian - model limitations)
- **AI Models:** OpenAI GPT-4 and Anthropic Claude (auto-selected by system)
- **Python Version:** 3.11+ strictly (NOT 3.12+ - breaks dependencies)
- **Document Types:** Full document generation only (no separate sections)
- **Export:** DOCX/PDF only (NO editing after generation)
- **Generation:** Real-time progress, auto-save structure, background jobs

## Frontend Patterns (Next.js 14)

### Server vs Client Components
```typescript
// Server Component (default) - for data fetching
export default async function DocumentPage({ params }) {
  const doc = await fetchDocument(params.id)
  return <DocumentView doc={doc} />
}

// Client Component - for interactivity
'use client'
export function DocumentEditor() {
  const [content, setContent] = useState('')
  // ... interactive logic
}
```

### API Client Pattern
**Location:** `apps/web/lib/api.ts` - Centralized client with auto-refresh
```typescript
import { apiClient } from '@/lib/api'

// Automatically handles token refresh on 401
const response = await apiClient.post('/api/v1/documents/generate', {
  title: 'My Thesis',
  pages: 50
})

// Tokens stored in localStorage: 'auth_token', 'refresh_token'
// Auth state managed by AuthProvider (apps/web/components/providers/AuthProvider.tsx)
```

## Security Requirements

1. **File Upload Validation:**
```python
# Validate magic bytes, not just extensions
import magic
mime = magic.from_buffer(file.read(1024), mime=True)
if mime not in ALLOWED_MIMES:
    raise ValueError("Invalid file type")
```

2. **SQL Safety:**
```python
# ✅ Use SQLAlchemy query builder
query = select(Document).where(Document.id == doc_id)

# ❌ Never use f-strings in SQL
query = f"SELECT * FROM documents WHERE id = {doc_id}"  # SQL INJECTION!
```

3. **JWT Tokens:**
- 30 min expiration for access tokens
- 7 days for refresh tokens
- HS256 algorithm (configurable via JWT_ALG)
- Must validate iss, aud, exp claims
- Stored in localStorage on frontend
- Auto-refresh handled by `apps/web/lib/api.ts`

4. **Rate Limiting:**
```python
# Configured in settings (app/core/config.py):
# - RATE_LIMIT_PER_MINUTE (default: 60)
# - RATE_LIMIT_AUTH_LOCKOUT_THRESHOLD (default: 5 failed attempts)
# - Can be disabled in dev: DISABLE_RATE_LIMIT=true
# Middleware: app/middleware/rate_limit.py
```

5. **CSRF Protection:**
- Enabled in production only
- Requires X-CSRF-Token header for state-changing requests
- Implemented in `app/middleware/csrf.py`

## Development Commands

```bash
# Start infrastructure (PostgreSQL, Redis, MinIO)
cd infra/docker && docker-compose up -d

# Backend development
cd apps/api
source venv/bin/activate  # or: source venv/Scripts/activate (Windows)
uvicorn main:app --reload --port 8000

# Frontend development
cd apps/web
npm run dev  # runs on port 3000

# Run tests
cd apps/api && ./scripts/run-tests.sh  # Backend (uses sqlite in-memory)
cd apps/web && npm test                # Frontend

# Database migrations
cd apps/api
alembic revision --autogenerate -m "description"
alembic upgrade head

# Check backend health
curl http://localhost:8000/health
# Expected: {"status":"healthy","database":"connected","redis":"connected"}

# Admin login (test only)
curl -X POST http://localhost:8000/api/v1/auth/admin-login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@tesigo.com","password":"admin123"}'
```

## Common Tasks

### Adding a New API Endpoint

1. **Define schema** in `app/schemas/`:
```python
from pydantic import BaseModel, Field

class DocumentCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    pages: int = Field(..., ge=3, le=200)
    language: str = Field(..., pattern=r'^(en|de|fr|es|it|cs|uk)$')
```

2. **Add service logic** in `app/services/`:
```python
from sqlalchemy.ext.asyncio import AsyncSession

class DocumentService:
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def create_document(
        self, data: DocumentCreate, user_id: int
    ) -> Document:
        doc = Document(**data.model_dump(), user_id=user_id)
        self.db.add(doc)
        await self.db.commit()
        await self.db.refresh(doc)
        return doc
```

3. **Create endpoint** in `app/api/v1/endpoints/`:
```python
from fastapi import APIRouter, Depends
from app.core.dependencies import get_current_user

router = APIRouter()

@router.post("/", response_model=DocumentResponse)
async def create(
    data: DocumentCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    service = DocumentService(db)
    return await service.create_document(data, current_user.id)
```

4. **Register router** in `app/api/v1/endpoints/__init__.py` and `main.py`

### Troubleshooting Common Issues

**Database session errors:**
```python
# ❌ Wrong: Using global session
from app.core.database import AsyncSessionLocal
db = AsyncSessionLocal()  # DON'T

# ✅ Correct: Use dependency injection
async def endpoint(db: AsyncSession = Depends(get_db)):
    pass
```

**Background task not starting:**
```bash
# Check logs
tail -f /tmp/backend.log | grep "generation\|job\|error"

# Verify job was created
curl http://localhost:8000/api/v1/jobs/{job_id}/status

# Check WebSocket connection
# Frontend console should show: "WebSocket connected"
```

**Port already in use:**
```bash
# Find process using port 8000
lsof -i :8000 | grep LISTEN
# Kill it
kill -9 <PID>
```

**Virtual environment not found:**
```bash
cd apps/api
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### AI Generation Pipeline

Located in `app/services/ai_pipeline/`:
- `outline_generator.py` - Creates document structure
- `section_writer.py` - Writes individual sections
- `citation_finder.py` - Finds and formats citations
- `quality_checker.py` - Validates output quality

All AI calls use circuit breaker pattern for resilience.

## Documentation Hierarchy

**🔴 CRITICAL - Read BEFORE every task:**
0. **Quality Rules:** [`/.github/AGENT_QUALITY_RULES.md`](./AGENT_QUALITY_RULES.md) - **HOW to work** (mandatory checklist)

**📚 Core Documentation - Read for context:**
1. **Primary:** [`docs/MASTER_DOCUMENT.md`](../docs/MASTER_DOCUMENT.md) - Complete technical reference
2. **Setup:** [`docs/QUICK_START.md`](../docs/QUICK_START.md) - Local development setup
3. **Decisions:** [`docs/sec/DECISIONS_LOG.md`](../docs/sec/DECISIONS_LOG.md) - Architecture decisions
4. **UX:** [`docs/USER_EXPERIENCE_STRUCTURE.md`](../docs/USER_EXPERIENCE_STRUCTURE.md) - User flows

**Ignore:** Everything in `/docs/archive/` and `/reports/` (outdated)

## Tech Stack Versions

**CRITICAL - Must match these versions:**
- Python: **3.11+** (NOT 3.12+ - breaks dependencies)
- Node.js: 18+
- PostgreSQL: 15-alpine
- Redis: 7-alpine
- MinIO: latest
- FastAPI: 0.104.1
- Next.js: 14.0.3
- SQLAlchemy: 2.0.23 (async)
- Pydantic: 2.5.0

**Key AI Libraries:**
- OpenAI: 1.3.5
- Anthropic: 0.7.0
- LangChain: 0.0.340

## Code Style

- Python: Black formatter, ruff linter, mypy type checker
- TypeScript: Prettier + ESLint
- Imports: Absolute imports preferred (`from app.services...`)
- Naming: snake_case (Python), camelCase (TypeScript)
- Docstrings: Google style for Python

## Error Handling

```python
from app.core.exceptions import APIException

raise APIException(
    status_code=400,
    error_code="INVALID_PAGE_COUNT",
    detail="Page count must be between 3 and 200"
)
```

Frontend receives:
```json
{
  "error_code": "INVALID_PAGE_COUNT",
  "detail": "Page count must be between 3 and 200",
  "status_code": 400,
  "timestamp": "2025-11-25T12:00:00Z"
}
```

## Testing

```python
# Backend tests use pytest + pytest-asyncio
@pytest.mark.asyncio
async def test_create_document(client, auth_headers):
    response = await client.post(
        "/api/v1/documents",
        json={"title": "Test", "pages": 10},
        headers=auth_headers
    )
    assert response.status_code == 201
```

## AI Generation Pipeline

Located in `app/services/ai_pipeline/`:
- `outline_generator.py` - Creates document structure
- `section_writer.py` - Writes individual sections
- `citation_finder.py` - Finds and formats citations
- `quality_checker.py` - Validates output quality

All AI calls use circuit breaker pattern for resilience.

## Environment Variables

Required in production:
```bash
# Database
DATABASE_URL=postgresql://user:pass@host:5432/tesigo

# Security
SECRET_KEY=<64-char-random-string>
JWT_SECRET=<64-char-random-string>

# AI APIs
OPENAI_API_KEY=sk-proj-...
ANTHROPIC_API_KEY=sk-ant-...

# Payments
STRIPE_SECRET_KEY=sk_live_...
STRIPE_WEBHOOK_SECRET=whsec_...

# CORS
CORS_ALLOWED_ORIGINS=https://tesigo.com,https://www.tesigo.com
```

# CORS
CORS_ALLOWED_ORIGINS=https://tesigo.com,https://www.tesigo.com
```

## Philosophy

- **Ship working code, not perfect code**
- **Simple solutions over clever ones**
- **Security is non-negotiable**
- **User data is sacred - always check ownership**
- **Explicit is better than implicit**

---

**When in doubt:** Check [`MASTER_DOCUMENT.md`](../docs/MASTER_DOCUMENT.md) or follow existing patterns in the codebase.
