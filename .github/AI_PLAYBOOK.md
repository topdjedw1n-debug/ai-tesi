# TesiGo AI Playbook

> **Cookbook of patterns, examples, and "how we do X" in this project.**
> Reference this when you need implementation details, not rules.

**Version:** 1.0 | **Updated:** 2026-01-22

---

## 📖 When to Use This Playbook

- You need to implement something similar to existing code
- You want to see "how we do X" in this project
- You're looking for code examples and patterns
- You want to avoid common anti-patterns

**For rules and workflow, see:** `.github/copilot-instructions.md`

---

## 🔐 Authentication Patterns

### Magic Link Flow (Users)
```python
# 1. Request magic link
POST /api/v1/auth/magic-link
{"email": "user@example.com"}

# 2. Backend creates token, sends email
token = secrets.token_urlsafe(32)
# Store in DB with 15 min expiration

# 3. User clicks link
GET /auth/verify?token=abc123

# 4. Backend validates, returns JWT
{
    "access_token": "eyJ...",      # 30 min
    "refresh_token": "eyJ...",     # 7 days
    "token_type": "bearer"
}
```

### JWT Validation
```python
from app.core.security import get_current_user

@router.get("/protected")
async def protected_endpoint(
    current_user: User = Depends(get_current_user)
):
    # current_user is already validated
    return {"user_id": current_user.id}
```

### Admin Authentication
```python
# Admins use password, not magic link
from app.core.dependencies import get_admin_user

@router.get("/admin/stats")
async def admin_stats(
    admin: User = Depends(get_admin_user)
):
    # Requires is_admin=True or is_super_admin=True
    pass
```

### Token Refresh (Frontend)
```typescript
// apps/web/lib/api.ts handles this automatically
// On 401 → try refresh → retry original request → if fail → logout
```

---

## 🗄️ Database Patterns

### Async Session in Endpoints
```python
from app.core.database import get_db
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

@router.get("/documents/{doc_id}")
async def get_document(
    doc_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    result = await db.execute(
        select(Document).where(Document.id == doc_id)
    )
    doc = result.scalar_one_or_none()

    # IDOR CHECK - MANDATORY
    if not doc or doc.user_id != current_user.id:
        raise HTTPException(404, "Document not found")

    return doc
```

### Async Session in Background Jobs
```python
from app.core.database import AsyncSessionLocal

async def process_document(document_id: int):
    async with AsyncSessionLocal() as db:
        # Explicit session management
        doc = await db.get(Document, document_id)
        doc.status = "processing"
        await db.commit()  # Must commit explicitly!

        # Do work...

        doc.status = "completed"
        await db.commit()
```

### Transactions with SELECT FOR UPDATE
```python
# Prevent race conditions (e.g., duplicate payments)
async with db.begin():
    result = await db.execute(
        select(Payment)
        .where(Payment.document_id == doc_id)
        .with_for_update()  # Locks the row
    )
    existing = result.scalar_one_or_none()
    if existing:
        return  # Already processed

    # Create new payment within lock
    payment = Payment(...)
    db.add(payment)
    # Commits on context exit
```

### Migrations
```bash
# Create new migration after model changes
cd apps/api
alembic revision --autogenerate -m "Add user_preferences table"

# ALWAYS review generated migration!
# migrations/versions/xxx_add_user_preferences_table.py

# Apply
alembic upgrade head

# Rollback
alembic downgrade -1
```

---

## 💳 Payment Patterns

### Create Payment Intent
```python
@router.post("/create-intent")
async def create_payment_intent(
    data: PaymentCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Calculate amount
    amount_cents = int(data.pages * settings.PRICE_PER_PAGE * 100)

    # Create Stripe intent
    intent = stripe.PaymentIntent.create(
        amount=amount_cents,
        currency="eur",
        metadata={
            "user_id": current_user.id,
            "document_id": data.document_id,
            "pages": data.pages
        }
    )

    # Store in DB
    payment = Payment(
        user_id=current_user.id,
        document_id=data.document_id,
        amount=Decimal(str(amount_cents / 100)),
        stripe_intent_id=intent.id,
        status="pending"
    )
    db.add(payment)
    await db.commit()

    return {"client_secret": intent.client_secret}
```

### Webhook Handler (CRITICAL)
```python
@router.post("/webhook")
async def stripe_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    payload = await request.body()
    sig = request.headers.get("stripe-signature")

    # Verify signature
    try:
        event = stripe.Webhook.construct_event(
            payload, sig, settings.STRIPE_WEBHOOK_SECRET
        )
    except ValueError:
        raise HTTPException(400, "Invalid payload")
    except stripe.error.SignatureVerificationError:
        raise HTTPException(400, "Invalid signature")

    if event["type"] == "payment_intent.succeeded":
        intent = event["data"]["object"]
        document_id = int(intent["metadata"]["document_id"])

        # CRITICAL: Prevent duplicate processing
        async with db.begin():
            existing_job = await db.execute(
                select(AIGenerationJob)
                .where(AIGenerationJob.document_id == document_id)
                .with_for_update()
            )
            if existing_job.scalar_one_or_none():
                return {"status": "already_processed"}

            # Create job within lock
            job = AIGenerationJob(
                document_id=document_id,
                status="queued"
            )
            db.add(job)

        # Start generation AFTER commit
        background_tasks.add_task(
            generate_document, document_id, job.id
        )

    return {"status": "ok"}
```

---

## 🤖 AI Pipeline Patterns

### Section Generation
```python
from app.services.ai_pipeline.generator import SectionGenerator

async def generate_section(
    outline_item: dict,
    context_sections: list[dict],
    db: AsyncSession
):
    generator = SectionGenerator()

    result = await generator.generate_section(
        title=outline_item["title"],
        requirements=outline_item["requirements"],
        target_pages=outline_item["pages"],
        previous_sections=context_sections,  # For continuity
        language="en"
    )

    return {
        "title": outline_item["title"],
        "content": result["content"],
        "sources": result["sources"]
    }
```

### RAG Retrieval
```python
from app.services.ai_pipeline.rag_retriever import RAGRetriever

async def search_sources(query: str, limit: int = 5):
    retriever = RAGRetriever()

    # Search academic sources
    results = await retriever.search(
        query=query,
        sources=["semantic_scholar"],  # Add more as implemented
        limit=limit
    )

    return [
        {
            "title": r.title,
            "authors": r.authors,
            "year": r.year,
            "url": r.url,
            "relevance": r.score
        }
        for r in results
    ]
```

### Progress Updates via WebSocket
```python
from app.core.websocket import manager

async def generate_with_progress(document_id: int, user_id: int):
    # Send progress updates
    await manager.send_progress(user_id, {
        "document_id": document_id,
        "stage": "outline",
        "progress": 10,
        "message": "Generating outline..."
    })

    # ... do work ...

    await manager.send_progress(user_id, {
        "document_id": document_id,
        "stage": "section_1",
        "progress": 25,
        "message": "Writing section 1 of 5..."
    })
```

### Checkpoints (Recovery)
```python
import redis.asyncio as redis

async def save_checkpoint(document_id: int, section_index: int):
    """Save progress for crash recovery."""
    r = redis.from_url(settings.REDIS_URL)
    await r.set(
        f"checkpoint:doc:{document_id}",
        json.dumps({
            "last_section": section_index,
            "timestamp": datetime.utcnow().isoformat()
        }),
        ex=3600  # 1 hour TTL
    )

async def load_checkpoint(document_id: int) -> dict | None:
    """Load checkpoint if exists."""
    r = redis.from_url(settings.REDIS_URL)
    data = await r.get(f"checkpoint:doc:{document_id}")
    return json.loads(data) if data else None
```

---

## 📝 Logging Patterns

### Structured Logging
```python
from loguru import logger

# Add context to all logs in a request
logger.bind(
    correlation_id=request.headers.get("X-Correlation-ID"),
    user_id=current_user.id if current_user else None
)

# Log levels
logger.debug("Detailed info for debugging")
logger.info("Normal operation", document_id=doc_id)
logger.warning("Something unexpected but handled")
logger.error("Something failed", exc_info=True)
logger.critical("System cannot continue")
```

### Audit Logging
```python
async def log_audit_event(
    db: AsyncSession,
    user_id: int,
    action: str,
    details: dict,
    ip_address: str
):
    audit = AuditLog(
        user_id=user_id,
        action=action,
        details=json.dumps(details),
        ip_address=ip_address,
        created_at=datetime.utcnow()
    )
    db.add(audit)
    await db.commit()

# Usage
await log_audit_event(db, user.id, "document.created",
    {"document_id": doc.id, "pages": 50}, request.client.host)
```

---

## 🧪 Testing Patterns

### Async Test Setup
```python
import pytest
from httpx import AsyncClient
from app.main import app

@pytest.fixture
async def client():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac

@pytest.fixture
async def auth_headers(client):
    # Create test user and get token
    response = await client.post("/api/v1/auth/test-login",
        json={"email": "test@test.com"})
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
```

### Testing Endpoints
```python
@pytest.mark.asyncio
async def test_create_document(client, auth_headers):
    response = await client.post(
        "/api/v1/documents",
        json={"title": "Test Thesis", "pages": 50, "language": "en"},
        headers=auth_headers
    )
    assert response.status_code == 201
    assert response.json()["title"] == "Test Thesis"

@pytest.mark.asyncio
async def test_unauthorized_access(client):
    response = await client.get("/api/v1/documents")
    assert response.status_code == 401
```

### Mocking External Services
```python
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_payment_creation(client, auth_headers):
    with patch("stripe.PaymentIntent.create") as mock_stripe:
        mock_stripe.return_value = Mock(
            id="pi_test123",
            client_secret="secret_test"
        )

        response = await client.post(
            "/api/v1/payment/create-intent",
            json={"document_id": 1, "pages": 50},
            headers=auth_headers
        )

        assert response.status_code == 200
        assert "client_secret" in response.json()
```

---

## 🛡️ Defense-in-Depth Validation

> **After finding a bug's root cause, add validation at EVERY layer.**
> Based on obra/superpowers systematic debugging methodology.

### Why Multiple Layers?

Single validation: "We fixed the bug"
Multiple layers: "We made the bug impossible"

Different layers catch different cases:
- Entry validation catches most bugs
- Business logic catches edge cases
- Environment guards prevent context-specific dangers
- Debug logging helps when other layers fail

### The Four Layers

#### Layer 1: Entry Point Validation
**Purpose:** Reject obviously invalid input at API boundary

```python
from app.core.exceptions import ValidationError

@router.post("/documents")
async def create_document(
    data: DocumentCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    # Layer 1: Entry validation
    if not data.topic or data.topic.strip() == "":
        raise ValidationError("Topic cannot be empty")

    if not 3 <= data.page_count <= 200:
        raise ValidationError("Page count must be 3-200")

    if data.language not in ["en", "de", "fr", "es", "it", "cs", "uk"]:
        raise ValidationError(f"Unsupported language: {data.language}")

    # Proceed to service layer
    doc = await document_service.create(db, data, user.id)
    return doc
```

#### Layer 2: Business Logic Validation
**Purpose:** Ensure data makes sense for this operation

```python
# app/services/document_service.py

async def create_document(
    db: AsyncSession,
    data: DocumentCreate,
    user_id: UUID
) -> Document:
    # Layer 2: Business logic validation
    if not user_id:
        raise ValidationError("User ID required for document creation")

    # Check user exists and is active
    user = await db.get(User, user_id)
    if not user:
        raise NotFoundError("User not found")
    if not user.is_active:
        raise ValidationError("User account is not active")

    # Check user hasn't exceeded quota
    count = await db.execute(
        select(func.count()).select_from(Document)
        .where(Document.user_id == user_id)
        .where(Document.created_at > datetime.utcnow() - timedelta(days=1))
    )
    if count.scalar() >= 10:
        raise ValidationError("Daily document limit exceeded")

    # Create document
    doc = Document(**data.dict(), user_id=user_id)
    db.add(doc)
    await db.commit()
    return doc
```

#### Layer 3: Environment Guards
**Purpose:** Prevent dangerous operations in specific contexts

```python
# app/services/storage_service.py

async def save_document_file(
    file_path: str,
    content: bytes
) -> str:
    # Layer 3: Environment guards
    if settings.ENVIRONMENT == "test":
        # Refuse to save outside temp directory in tests
        import tempfile
        normalized_path = os.path.normpath(os.path.abspath(file_path))
        temp_dir = tempfile.gettempdir()

        if not normalized_path.startswith(temp_dir):
            raise ValueError(
                f"Refusing file save outside temp dir during tests: {file_path}"
            )

    # In production, verify MinIO is accessible
    if settings.ENVIRONMENT == "production":
        try:
            minio_client.bucket_exists(settings.MINIO_BUCKET)
        except Exception as e:
            logger.error("MinIO not accessible", exc_info=True)
            raise ServiceUnavailableError("Storage service unavailable")

    # Proceed with save
    await minio_client.put_object(
        settings.MINIO_BUCKET,
        file_path,
        io.BytesIO(content),
        len(content)
    )
    return file_path
```

#### Layer 4: Debug Instrumentation
**Purpose:** Capture context for forensics when something goes wrong

```python
import traceback
from loguru import logger

async def generate_document_sections(
    document_id: UUID,
    outline: list[dict]
) -> list[dict]:
    # Layer 4: Debug instrumentation
    logger.debug("Starting section generation", extra={
        "document_id": str(document_id),
        "outline_count": len(outline),
        "environment": settings.ENVIRONMENT,
        "worker_pid": os.getpid(),
        "stack": traceback.format_stack()
    })

    sections = []
    for i, item in enumerate(outline):
        logger.debug(f"Generating section {i+1}/{len(outline)}", extra={
            "document_id": str(document_id),
            "section_title": item["title"],
            "target_pages": item["pages"]
        })

        section = await ai_service.generate_section(item)
        sections.append(section)

    logger.info("Section generation complete", extra={
        "document_id": str(document_id),
        "sections_generated": len(sections),
        "total_pages": sum(s.get("pages", 0) for s in sections)
    })

    return sections
```

### Real Example: Empty Directory Bug

**Bug:** Empty `working_directory` caused file operations in wrong location

**Data flow traced:**
1. Frontend sends `{working_directory: null}`
2. Pydantic converts to empty string
3. `create_document()` receives empty string
4. `storage_service.save_file('')` uses `process.cwd()`
5. Files saved in source code directory instead of temp

**Four layers added:**

```python
# Layer 1: API Entry Point
@router.post("/documents")
async def create_document(data: DocumentCreate):
    if not data.working_directory or data.working_directory.strip() == "":
        raise ValidationError("working_directory cannot be empty")
    if not os.path.exists(data.working_directory):
        raise ValidationError(f"Directory does not exist: {data.working_directory}")
    # ...

# Layer 2: Service Layer
async def create_document(db, data, user_id):
    if not data.working_directory:
        raise ValidationError("working_directory required")
    if not os.path.isdir(data.working_directory):
        raise ValidationError("working_directory must be a directory")
    # ...

# Layer 3: Storage Layer (Environment Guard)
async def save_file(file_path: str, content: bytes):
    if settings.ENVIRONMENT == "test":
        import tempfile
        if not file_path.startswith(tempfile.gettempdir()):
            raise ValueError(f"Refusing save outside temp: {file_path}")
    # ...

# Layer 4: Debug Logging
logger.debug("File save operation", extra={
    "file_path": file_path,
    "cwd": os.getcwd(),
    "environment": settings.ENVIRONMENT,
    "stack": traceback.format_stack()
})
```

**Result:** Bug impossible to reproduce. All 265 tests passed.

### Applying the Pattern

When you find a bug:

1. **Trace the data flow** - Where does bad value originate? Where used?
2. **Map all checkpoints** - List every point data passes through
3. **Add validation at each layer** - Entry, business, environment, debug
4. **Test each layer** - Try to bypass layer 1, verify layer 2 catches it

**Key insight:** Don't stop at one validation point. Add checks at every layer.

---

## ❌ Anti-Patterns (What NOT to Do)

````

### Database
```python
# ❌ Creating session manually
db = AsyncSessionLocal()  # NEVER in endpoints

# ❌ Sync operations in async
def sync_query():  # Should be async def
    return db.query(User).all()

# ❌ Missing ownership check (IDOR vulnerability)
@router.get("/docs/{id}")
async def get_doc(id: int, db: AsyncSession = Depends(get_db)):
    return await db.get(Document, id)  # MISSING user_id check!
```

### Security
```python
# ❌ SQL injection
query = f"SELECT * FROM users WHERE id = {user_id}"

# ❌ Hardcoded secrets
STRIPE_KEY = "sk_live_abc123"

# ❌ Float for money
price = 10.50  # Use Decimal("10.50")

# ❌ Trusting file extensions
if filename.endswith(".pdf"):  # Check magic bytes instead
```

### Async
```python
# ❌ Blocking I/O
import requests
response = requests.get(url)  # Use httpx.AsyncClient

# ❌ Blocking sleep
import time
time.sleep(5)  # Use await asyncio.sleep(5)
```

### Types
```python
# ❌ Missing type hints
def process(data):  # Add types!
    return data * 2

# ❌ Using Optional (old style)
from typing import Optional
def get(key: str) -> Optional[str]:  # Use str | None
```

---

## 🔧 Troubleshooting

### "Session closed" Errors
```python
# Cause: Using session outside its scope
# Fix: Use Depends(get_db) or context manager

# ❌ Wrong
db = await get_db()  # Not how it works

# ✅ Correct
async def endpoint(db: AsyncSession = Depends(get_db)):
```

### "Event loop closed" Errors
```python
# Cause: Async code running after loop closed
# Fix: Ensure all async tasks complete before shutdown

# In tests, use proper fixtures:
@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()
```

### Background Task Not Running
```bash
# Check if committed before starting task
# await db.commit()  # MUST be before add_task()
# background_tasks.add_task(...)

# Check logs
tail -f /tmp/backend.log | grep "background\|job\|error"
```

### WebSocket Not Connecting
```javascript
// Frontend: Check console for errors
// Backend: Verify CORS settings include WebSocket origins

// Test manually:
wscat -c ws://localhost:8000/ws/user_id
```

---

## 📋 Checklists

### New Endpoint Checklist
- [ ] Schema in `app/schemas/`
- [ ] Service logic in `app/services/`
- [ ] Endpoint in `app/api/v1/endpoints/`
- [ ] Router registered in `__init__.py`
- [ ] IDOR protection (ownership check)
- [ ] Type hints complete
- [ ] Test written

### New Model Checklist
- [ ] Model in `app/models/`
- [ ] Migration created and reviewed
- [ ] Schema for API responses
- [ ] Relationships defined
- [ ] Indexes for common queries

---

**For rules and workflow, see:** `.github/copilot-instructions.md`
