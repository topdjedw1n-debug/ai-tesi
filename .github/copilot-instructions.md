# TesiGo - AI Coding Agent Instructions

## Project Overview

**TesiGo** is an AI-powered platform for generating academic papers (theses, dissertations, coursework). Built as a full-stack SaaS with FastAPI backend and Next.js 14 frontend.

## Architecture

```
apps/
├── api/          # FastAPI backend (Python 3.11)
│   ├── app/
│   │   ├── api/v1/endpoints/    # REST API routes
│   │   ├── services/            # Business logic
│   │   ├── models/              # SQLAlchemy ORM
│   │   ├── schemas/             # Pydantic validation
│   │   └── core/                # Config, DB, security
│   └── main.py                  # FastAPI app entry
└── web/          # Next.js 14 frontend (App Router)
    ├── app/                     # Next.js routes
    ├── components/              # React components
    └── lib/                     # Client utilities
```

## Critical Patterns

### Backend (FastAPI)

**Always async for I/O operations:**
```python
# ✅ Correct
async def generate_document(user_id: int, pages: int) -> Document:
    async with db.Session() as session:
        result = await session.execute(query)
        return result.scalars().first()

# ❌ Wrong - sync in async context
def sync_function():
    return db.query(Document).all()
```

**Type hints are mandatory:**
```python
# All functions must have complete type annotations
async def create_payment(
    user_id: int,
    amount: Decimal,
    pages: int
) -> Payment:
    pass
```

**Ownership checks on every user data endpoint:**
```python
# CRITICAL: Prevent IDOR vulnerabilities
async def get_document(doc_id: int, current_user: User):
    doc = await db.get(Document, doc_id)
    if doc.user_id != current_user.id:
        raise HTTPException(403, "Not authorized")
    return doc
```

### Frontend (Next.js 14)

**Server vs Client Components:**
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

**API calls use centralized client:**
```typescript
// lib/api-client.ts
import { apiClient } from '@/lib/api-client'

const response = await apiClient.post('/documents/generate', {
  title: 'My Thesis',
  pages: 50
})
```

## Key Business Rules

- **Payment Model:** Pay-per-page (€0.50/page base price)
- **Currency:** EUR only
- **Min/Max Pages:** 3 minimum, 200 maximum
- **Supported Languages:** EN, DE, FR, ES, IT, CS, UK
- **AI Models:** OpenAI GPT-4 and Anthropic Claude (auto-selected)
- **No Refunds After Generation:** Payment is final once AI starts generating

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
cd apps/api && pytest
cd apps/web && npm test

# Database migrations
cd apps/api
alembic revision -m "description"
alembic upgrade head
```

## Common Tasks

### Adding a New API Endpoint

1. **Define schema** in `app/schemas/`:
```python
class DocumentCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    pages: int = Field(..., ge=3, le=200)
    language: str = Field(..., pattern=r'^(en|de|fr|es|it|cs|uk)$')
```

2. **Add service logic** in `app/services/`:
```python
async def create_document(data: DocumentCreate, user_id: int) -> Document:
    # Business logic here
```

3. **Create endpoint** in `app/api/v1/endpoints/`:
```python
@router.post("/", response_model=DocumentResponse)
async def create(
    data: DocumentCreate,
    current_user: User = Depends(get_current_user)
):
    return await document_service.create_document(data, current_user.id)
```

### AI Generation Pipeline

Located in `app/services/ai_pipeline/`:
- `outline_generator.py` - Creates document structure
- `section_writer.py` - Writes individual sections
- `citation_finder.py` - Finds and formats citations
- `quality_checker.py` - Validates output quality

All AI calls use circuit breaker pattern for resilience.

## Documentation Hierarchy

1. **Primary:** [`docs/MASTER_DOCUMENT.md`](../docs/MASTER_DOCUMENT.md) - Complete technical reference
2. **Setup:** [`docs/QUICK_START.md`](../docs/QUICK_START.md) - Local development setup
3. **Decisions:** [`docs/sec/DECISIONS_LOG.md`](../docs/sec/DECISIONS_LOG.md) - Architecture decisions
4. **UX:** [`docs/USER_EXPERIENCE_STRUCTURE.md`](../docs/USER_EXPERIENCE_STRUCTURE.md) - User flows

**Ignore:** Everything in `/docs/archive/` and `/reports/` (outdated)

## Tech Stack Versions

**CRITICAL - Must match these versions:**
- Python: **3.11** (NOT 3.12+ - breaks dependencies)
- Node.js: 18+
- PostgreSQL: 15
- Redis: 7
- FastAPI: 0.104+
- Next.js: 14.0+

## Anti-Patterns to Avoid

```python
# ❌ Don't use sync code in async endpoints
def sync_function(): pass

# ❌ Don't expose secrets
API_KEY = "sk-..."

# ❌ Don't skip ownership checks
doc = await db.get(Document, doc_id)  # Missing user check!

# ❌ Don't use mutable defaults
def func(items: list = []): pass

# ❌ Don't ignore type hints
def process(data): pass  # Missing types
```

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

## Philosophy

- **Ship working code, not perfect code**
- **Simple solutions over clever ones**
- **Security is non-negotiable**
- **User data is sacred - always check ownership**
- **Explicit is better than implicit**

---

**When in doubt:** Check [`MASTER_DOCUMENT.md`](../docs/MASTER_DOCUMENT.md) or follow existing patterns in the codebase.
