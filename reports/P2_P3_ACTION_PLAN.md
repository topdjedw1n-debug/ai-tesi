# 📋 P2 та P3 Action Plan - TesiGo v2.3

**Дата:** 2025-11-02  
**Мета:** Детальний план дій для завершення P2 (MVP Features) та P3 (Code Quality)

---

## 📊 Поточний Стан

### P2 (MVP Features) - ЧАСТКОВО ГОТОВО
- ✅ Core features працюють (documents, auth, generation)
- ✅ Background jobs інтегровані
- ✅ DOCX export працює
- ❌ Payment system: 0% (не реалізовано)
- ❌ Custom requirements upload: 0% (не реалізовано)
- ⚠️ Coverage: 44% (ціль: 70-80%)
- ❌ E2E тести: 0% (відсутні)

### P3 (Code Quality) - НЕ ГОТОВО
- ⚠️ Ruff warnings: 114 (UP045, E712)
- ❌ test.db в repo
- ❌ Frontend TODOs: 8 items
- ⚠️ MyPy: 152 errors (ціль: ≤50)
- ❌ Ruff config deprecation

---

## 🎯 P2: MVP FEATURES ACTION PLAN

### Phase 2.1: Payment System (Week 1) 🔴 CRITICAL

**Мета:** Реалізувати повний payment workflow для монетизації MVP

#### Task 2.1.1: Stripe Integration Setup
**Час:** 4-6 годин  
**Пріоритет:** P2 Critical

**Дії:**

1. **Install Stripe SDK:**
```bash
cd apps/api
pip install stripe==7.6.0
pip freeze > requirements.txt
```

2. **Create Payment Model:**
```python
# apps/api/app/models/payment.py
from sqlalchemy import Column, Integer, String, Numeric, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from app.core.database import Base

class Payment(Base):
    __tablename__ = "payments"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    amount = Column(Numeric(10, 2), nullable=False)
    currency = Column(String(3), default="USD")
    status = Column(String(20), nullable=False)  # pending, completed, failed, refunded
    stripe_payment_intent_id = Column(String(255), unique=True)
    stripe_customer_id = Column(String(255))
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="payments")

# Update User model to add relationship
# apps/api/app/models/user.py
payments = relationship("Payment", back_populates="user")
```

3. **Create Payment Schemas:**
```python
# apps/api/app/schemas/payment.py
from pydantic import BaseModel, Field
from datetime import datetime
from decimal import Decimal

class PaymentCreate(BaseModel):
    amount: Decimal = Field(..., gt=0, description="Payment amount")
    currency: str = "USD"
    product_id: str | None = None

class PaymentResponse(BaseModel):
    id: int
    user_id: int
    amount: Decimal
    currency: str
    status: str
    stripe_payment_intent_id: str | None
    created_at: datetime
    
    class Config:
        from_attributes = True

class PaymentWebhookEvent(BaseModel):
    type: str
    data: dict

class StripeClientSecretResponse(BaseModel):
    client_secret: str
    payment_intent_id: str
```

**Верифікація:**
```bash
pytest tests/ -k payment -v  # Коли тести готові
```

**Acceptance Criteria:**
- ✅ Payment model створено
- ✅ Alembic migration створено
- ✅ Schemas визначено
- ✅ Stripe SDK встановлено

---

#### Task 2.1.2: Payment Service Implementation
**Час:** 6-8 годин  
**Пріоритет:** P2 Critical

**Дії:**

1. **Create Payment Service:**
```python
# apps/api/app/services/payment_service.py
import stripe
from typing import Any
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.payment import Payment
from app.models.user import User

class PaymentService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.stripe_secret_key = settings.STRIPE_SECRET_KEY
        
    async def create_payment_intent(
        self, 
        user_id: int, 
        amount: Decimal
    ) -> dict[str, Any]:
        """Create Stripe payment intent"""
        try:
            user = await self.db.get(User, user_id)
            if not user:
                raise NotFoundError("User not found")
            
            # Create Stripe customer if needed
            customer_id = await self._get_or_create_customer(user)
            
            # Create payment intent
            intent = stripe.PaymentIntent.create(
                amount=int(amount * 100),  # Convert to cents
                currency='usd',
                customer=customer_id,
                metadata={
                    'user_id': user_id,
                    'user_email': user.email
                }
            )
            
            # Store payment record
            payment = Payment(
                user_id=user_id,
                amount=amount,
                status='pending',
                stripe_payment_intent_id=intent.id,
                stripe_customer_id=customer_id
            )
            self.db.add(payment)
            await self.db.commit()
            
            return {
                'client_secret': intent.client_secret,
                'payment_intent_id': intent.id
            }
        except stripe.StripeError as e:
            logger.error(f"Stripe error: {e}")
            raise ValueError(f"Payment creation failed: {str(e)}")
    
    async def _get_or_create_customer(self, user: User) -> str:
        """Get or create Stripe customer"""
        if user.stripe_customer_id:
            return user.stripe_customer_id
        
        customer = stripe.Customer.create(
            email=user.email,
            name=user.email,
            metadata={'user_id': user.id}
        )
        
        # Update user record
        user.stripe_customer_id = customer.id
        await self.db.commit()
        
        return customer.id
    
    async def handle_webhook(
        self, 
        payload: dict, 
        signature: str
    ) -> Payment:
        """Process Stripe webhook"""
        try:
            event = stripe.Webhook.construct_event(
                payload, signature, settings.STRIPE_WEBHOOK_SECRET
            )
            
            if event['type'] == 'payment_intent.succeeded':
                return await self._handle_payment_success(event)
            elif event['type'] == 'payment_intent.payment_failed':
                return await self._handle_payment_failed(event)
            
        except stripe.error.SignatureVerificationError:
            raise ValueError("Invalid webhook signature")
    
    async def _handle_payment_success(self, event: dict) -> Payment:
        intent = event['data']['object']
        payment_intent_id = intent['id']
        
        result = await self.db.execute(
            select(Payment).where(
                Payment.stripe_payment_intent_id == payment_intent_id
            )
        )
        payment = result.scalar_one_or_none()
        
        if payment:
            payment.status = 'completed'
            payment.updated_at = datetime.utcnow()
            await self.db.commit()
            
            # Grant user credits/subscription
            await self._grant_user_access(payment.user_id, payment.amount)
        
        return payment
```

2. **Add Config Settings:**
```python
# apps/api/app/core/config.py
STRIPE_SECRET_KEY: Optional[str] = None
STRIPE_WEBHOOK_SECRET: Optional[str] = None
STRIPE_PUBLISHABLE_KEY: Optional[str] = None  # For frontend
```

**Верифікація:**
- ✅ Unit tests для payment service
- ✅ Integration test з Stripe test mode
- ✅ Webhook handling працює

**Acceptance Criteria:**
- ✅ Payment intent створюється
- ✅ Webhook обробляє success/failed
- ✅ User credits оновлюються
- ✅ Error handling працює

---

#### Task 2.1.3: Payment Endpoints
**Час:** 4-6 годин  
**Пріоритет:** P2 Critical

**Дії:**

1. **Create Payment Endpoints:**
```python
# apps/api/app/api/v1/endpoints/payment.py
from fastapi import APIRouter, Depends, HTTPException, Request, Header
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.middleware.rate_limit import rate_limit
from app.models.auth import User
from app.schemas.payment import (
    PaymentCreate,
    PaymentResponse,
    StripeClientSecretResponse,
)
from app.services.payment_service import PaymentService

router = APIRouter()

@router.post("/create", response_model=StripeClientSecretResponse)
@rate_limit("20/hour")
async def create_payment(
    request: Request,
    payment_data: PaymentCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create payment intent"""
    service = PaymentService(db)
    result = await service.create_payment_intent(
        user_id=current_user.id,
        amount=payment_data.amount
    )
    return result

@router.post("/webhook")
async def stripe_webhook(
    request: Request,
    stripe_signature: str = Header(None),
    db: AsyncSession = Depends(get_db),
):
    """Handle Stripe webhook"""
    payload = await request.body()
    service = PaymentService(db)
    
    try:
        payment = await service.handle_webhook(payload, stripe_signature)
        return {"status": "success"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/history", response_model=list[PaymentResponse])
@rate_limit("30/hour")
async def get_payment_history(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get user payment history"""
    service = PaymentService(db)
    return await service.get_user_payments(current_user.id)
```

2. **Register Router:**
```python
# apps/api/app/api/v1/__init__.py
from app.api.v1.endpoints import admin, auth, documents, generate, payment

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(documents.router, prefix="/documents", tags=["documents"])
api_router.include_router(generate.router, prefix="/generate", tags=["generate"])
api_router.include_router(admin.router, prefix="/admin", tags=["admin"])
api_router.include_router(payment.router, prefix="/payment", tags=["payment"])  # NEW
```

**Верифікація:**
```bash
# Test endpoints
curl -X POST http://localhost:8000/api/v1/payment/create \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"amount": 10.00}'
```

**Acceptance Criteria:**
- ✅ POST /payment/create працює
- ✅ POST /payment/webhook обробляє events
- ✅ GET /payment/history повертає список
- ✅ Rate limiting працює

---

#### Task 2.1.4: Payment Tests
**Час:** 4-6 годин  
**Пріоритет:** P2 High

**Дії:**

1. **Create Test File:**
```python
# apps/api/tests/test_payment_service.py
import pytest
from decimal import Decimal
from unittest.mock import Mock, patch

from app.services.payment_service import PaymentService

@pytest.mark.asyncio
async def test_create_payment_intent_success(db_session):
    service = PaymentService(db_session)
    
    with patch('stripe.PaymentIntent.create') as mock_intent:
        mock_intent.return_value = Mock(
            id='pi_123',
            client_secret='secret_123',
            amount=1000
        )
        
        result = await service.create_payment_intent(
            user_id=1,
            amount=Decimal('10.00')
        )
        
        assert result['client_secret'] == 'secret_123'
        assert result['payment_intent_id'] == 'pi_123'

@pytest.mark.asyncio
async def test_webhook_payment_success(db_session):
    service = PaymentService(db_session)
    
    event = {
        'type': 'payment_intent.succeeded',
        'data': {
            'object': {
                'id': 'pi_123',
                'status': 'succeeded'
            }
        }
    }
    
    with patch('stripe.Webhook.construct_event') as mock_webhook:
        mock_webhook.return_value = event
        
        payment = await service.handle_webhook(
            b'{}',
            'signature'
        )
        
        assert payment.status == 'completed'
```

**Верифікація:**
```bash
pytest tests/test_payment_service.py -v
pytest tests/test_api_payment.py -v  # Integration tests
```

**Acceptance Criteria:**
- ✅ Unit tests: 10+ tests passing
- ✅ Integration tests: 3+ tests passing
- ✅ Mock Stripe API правильно налаштовано

---

### Phase 2.2: Custom Requirements Upload (Week 1-2) 🟠 HIGH

#### Task 2.2.1: File Upload Endpoint
**Час:** 4-6 годин  
**Пріоритет:** P2 High

**Дії:**

1. **Add File Upload Schema:**
```python
# apps/api/app/schemas/document.py
from fastapi import UploadFile

class CustomRequirementsUpload(BaseModel):
    document_id: int
    file_type: Literal["pdf", "docx"]
```

2. **Create Upload Endpoint:**
```python
# apps/api/app/api/v1/endpoints/documents.py
from fastapi import File, UploadFile, Depends
import aiofiles

@router.post("/{document_id}/custom-requirements/upload")
@rate_limit("10/hour")
async def upload_custom_requirements(
    document_id: int,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Upload custom requirements file"""
    # Validate file type
    if not file.content_type in ["application/pdf", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"]:
        raise HTTPException(400, "Invalid file type")
    
    # Validate file size (max 10MB)
    if file.size > 10 * 1024 * 1024:
        raise HTTPException(400, "File too large")
    
    # Save to MinIO
    service = DocumentService(db)
    url = await service.upload_custom_requirements(
        document_id=document_id,
        user_id=current_user.id,
        file=file
    )
    
    return {"url": url}
```

3. **Add to Document Service:**
```python
# apps/api/app/services/document_service.py
async def upload_custom_requirements(
    self, 
    document_id: int,
    user_id: int,
    file: UploadFile
) -> str:
    """Upload custom requirements to MinIO"""
    # Verify ownership
    doc = await self.get_document(document_id, user_id)
    
    # Upload to MinIO
    import aiofiles
    from minio import Minio
    
    client = Minio(...)
    file_content = await file.read()
    
    bucket = "custom-requirements"
    filename = f"{document_id}/{file.filename}"
    
    client.put_object(
        bucket,
        filename,
        io.BytesIO(file_content),
        length=len(file_content)
    )
    
    url = f"https://minio.example.com/{bucket}/{filename}"
    
    # Store URL in document
    doc.custom_requirements_url = url
    await self.db.commit()
    
    return url
```

**Верифікація:**
```bash
curl -X POST http://localhost:8000/api/v1/documents/1/custom-requirements/upload \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@requirements.pdf"
```

**Acceptance Criteria:**
- ✅ Upload PDF/DOCX працює
- ✅ File validation працює
- ✅ MinIO storage працює
- ✅ URL зберігається в document

---

#### Task 2.2.2: File Parsing Service
**Час:** 6-8 годин  
**Пріоритет:** P2 High

**Дії:**

1. **Create Parsing Service:**
```python
# apps/api/app/services/file_parser_service.py
import PyPDF2
from docx import Document
from typing import Any

class FileParserService:
    @staticmethod
    def parse_pdf(file_content: bytes) -> str:
        """Extract text from PDF"""
        pdf_file = io.BytesIO(file_content)
        pdf_reader = PyPDF2.PdfReader(pdf_file)
        
        text = ""
        for page in pdf_reader.pages:
            text += page.extract_text() + "\n"
        
        return text
    
    @staticmethod
    def parse_docx(file_content: bytes) -> str:
        """Extract text from DOCX"""
        docx_file = io.BytesIO(file_content)
        doc = Document(docx_file)
        
        text = ""
        for paragraph in doc.paragraphs:
            text += paragraph.text + "\n"
        
        return text
    
    @staticmethod
    def extract_text(file_content: bytes, file_type: str) -> str:
        """Extract text from file"""
        if file_type == "pdf":
            return FileParserService.parse_pdf(file_content)
        elif file_type == "docx":
            return FileParserService.parse_docx(file_content)
        else:
            raise ValueError(f"Unsupported file type: {file_type}")
```

2. **Integrate with Generation:**
```python
# apps/api/app/services/document_service.py
async def get_custom_requirements_text(
    self, 
    document_id: int
) -> str | None:
    """Retrieve and parse custom requirements"""
    doc = await self.get_document(document_id, user_id=None)
    
    if not doc.custom_requirements_url:
        return None
    
    # Download from MinIO
    file_content = await self._download_from_minio(
        doc.custom_requirements_url
    )
    
    # Parse based on extension
    file_type = doc.custom_requirements_url.split('.')[-1]
    parser = FileParserService()
    text = parser.extract_text(file_content, file_type)
    
    return text
```

**Додати до requirements.txt:**
```
PyPDF2==3.0.1
python-docx==1.1.0  # Вже є
```

**Верифікація:**
```bash
pytest tests/test_file_parser_service.py -v
```

**Acceptance Criteria:**
- ✅ PDF parsing працює
- ✅ DOCX parsing працює
- ✅ Text extraction точний
- ✅ Error handling для corrupted files

---

### Phase 2.3: Coverage Improvement (Week 2) 🟡 MEDIUM

#### Task 2.3.1: AI Pipeline Tests
**Час:** 8-10 годин  
**Ціль:** AI pipeline coverage: 0% → 70%+

**Приоритетні Модулі:**
1. `citation_formatter.py` (0% → 80%)
2. `generator.py` (0% → 80%)
3. `humanizer.py` (0% → 80%)
4. `rag_retriever.py` (0% → 80%)
5. `prompt_builder.py` (0% → 80%)

**Дії:**

1. **Citation Formatter Tests:**
```python
# apps/api/tests/test_citation_formatter.py
def test_format_apa_intext():
    formatter = CitationFormatter()
    result = formatter.format(
        authors=["Smith", "Jones"],
        year=2023,
        style=CitationStyle.APA
    )
    assert result == "Smith & Jones (2023)"

def test_format_mla_intext():
    formatter = CitationFormatter()
    result = formatter.format(
        authors=["Smith", "Jones"],
        year=2023,
        style=CitationStyle.MLA
    )
    assert result == "(Smith and Jones 42)"
```

2. **Generator Tests:**
```python
# apps/api/tests/test_generator.py
@pytest.mark.asyncio
async def test_generate_section_with_mock():
    generator = SectionGenerator()
    # Mock AI calls
    # Test generation flow
```

**Верифікація:**
```bash
pytest tests/test_ai_pipeline/ -v --cov=app/services/ai_pipeline
```

**Acceptance Criteria:**
- ✅ AI pipeline coverage ≥70%
- ✅ All citation styles covered
- ✅ Generator mocked properly
- ✅ RAG retriever tested

---

#### Task 2.3.2: Background Jobs Tests
**Час:** 6-8 годин  
**Ціль:** background_jobs coverage: 0% → 80%

**Дії:**

1. **Create Tests:**
```python
# apps/api/tests/test_background_jobs.py
@pytest.mark.asyncio
async def test_generate_full_document_async(db_session):
    # Test background job execution
    # Mock AI calls
    # Verify section creation
    
@pytest.mark.asyncio
async def test_process_custom_requirement(db_session):
    # Test PDF parsing
    # Test integration with generation
```

**Acceptance Criteria:**
- ✅ Background jobs coverage ≥80%
- ✅ Error handling tested
- ✅ Job status updates verified

---

#### Task 2.3.3: E2E Tests
**Час:** 8-10 годин  
**Ціль:** 10+ E2E test scenarios

**Дії:**

1. **Create E2E Test Suite:**
```python
# apps/api/tests/test_e2e.py
@pytest.mark.e2e
@pytest.mark.asyncio
async def test_complete_generation_flow():
    """Test full document generation workflow"""
    # 1. Create user
    # 2. Send magic link
    # 3. Verify and get token
    # 4. Create document
    # 5. Generate outline
    # 6. Generate section
    # 7. Export document
    
@pytest.mark.e2e
@pytest.mark.asyncio
async def test_payment_flow():
    """Test payment workflow"""
    # 1. Create payment intent
    # 2. Verify webhook
    # 3. Check credits updated
```

**Верифікація:**
```bash
pytest tests/test_e2e.py -m e2e -v
```

**Acceptance Criteria:**
- ✅ 10+ E2E scenarios
- ✅ All critical flows covered
- ✅ Payment flow tested
- ✅ Generation flow tested

---

## 🎨 P3: CODE QUALITY ACTION PLAN

### Phase 3.1: Ruff Fixes (Day 1) 🟢 LOW

#### Task 3.1.1: Ruff Auto-fix
**Час:** 2-4 години  
**Пріоритет:** P3 Low

**Дії:**

1. **Run Auto-fix:**
```bash
cd apps/api
ruff check . --fix --unsafe-fixes
ruff check .  # Verify 0 errors
```

2. **Manual Fixes:**
```bash
# Fix Optional[X] → X | None (107 instances)
ruff check . --select UP045 --fix

# Fix equality comparisons
ruff check . --select E712 --fix
```

**Верифікація:**
```bash
ruff check .
# Should show 0 errors, possibly 0 warnings
```

**Acceptance Criteria:**
- ✅ Ruff: 0 errors
- ✅ Ruff: <50 warnings (acceptable)
- ✅ All files reformatted
- ✅ Tests still passing

---

#### Task 3.1.2: Ruff Config Modernization
**Час:** 1-2 години  
**Пріоритет:** P3 Low

**Дії:**

1. **Update pyproject.toml:**
```toml
[tool.ruff]
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "I", "N", "UP", "W"]
ignore = []

[tool.ruff.lint.isort]
known-first-party = ["app"]

[tool.ruff.lint.per-file-ignores]
"__init__.py" = ["F401"]  # Allow unused imports
```

2. **Remove Top-level Settings:**
```toml
# DELETE these old top-level settings:
# select = ["E", "F", "I", "N", "UP", "W"]
# isort.known-first-party = ["app"]
```

**Верифікація:**
```bash
ruff check . --output-format=json | jq '.warnings'
# Should show no deprecated warnings
```

**Acceptance Criteria:**
- ✅ No deprecation warnings
- ✅ Config modernized
- ✅ Ruff still functional

---

### Phase 3.2: Repository Cleanup (Day 1) 🟢 LOW

#### Task 3.2.1: Remove test.db
**Час:** 1 година  
**Пріоритет:** P3 Low

**Дії:**

1. **Add to .gitignore:**
```bash
# .gitignore
*.db
*.sqlite
*.sqlite3
test.db
```

2. **Remove from Repo:**
```bash
git rm apps/api/test.db
git commit -m "Remove test.db from repository"
```

3. **Verify:**
```bash
git status
# Should not show test.db
```

**Acceptance Criteria:**
- ✅ test.db not in git
- ✅ .gitignore updated
- ✅ Tests use in-memory DB

---

#### Task 3.2.2: Frontend TODOs
**Час:** 4-6 годин  
**Пріоритет:** P3 Low

**TODO Items:**
1. `GenerateSectionForm.tsx:77` - "Replace with actual API call"
2. `GenerateSectionForm.tsx:82` - "Add authentication header"
3. `DocumentsList.tsx:45` - "Fetch real documents from API"
4. `RecentActivity.tsx:49` - "Fetch real activities from API"
5. `StatsOverview.tsx:23` - "Fetch real stats from API"
6. `AuthProvider.tsx:52` - "Verify token with backend"
7. `AuthProvider.tsx:71` - "Call backend API to send magic link"
8. `AuthProvider.tsx:133` - "Call backend API to invalidate session"
9. `Settings page:15` - "Implement settings save"

**Дії для кожного:**

1. **GenerateSectionForm.tsx:77-82:**
```typescript
// BEFORE (TODO)
const response = await fetch('/api/v1/generate/outline', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    // TODO: Add authentication header
  },
})

// AFTER
const token = localStorage.getItem('auth_token')
const response = await fetch('/api/v1/generate/outline', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${token}`,
  },
  body: JSON.stringify(data),
})
```

2. **DocumentsList.tsx:45:**
```typescript
// BEFORE
// TODO: Fetch real documents from API

// AFTER
useEffect(() => {
  const fetchDocuments = async () => {
    const token = localStorage.getItem('auth_token')
    const response = await fetch('/api/v1/documents', {
      headers: { 'Authorization': `Bearer ${token}` }
    })
    const data = await response.json()
    setDocuments(data.items)
  }
  fetchDocuments()
}, [])
```

**Верифікація:**
```bash
cd apps/web
npm run build  # Should succeed
npm run test   # Should pass
```

**Acceptance Criteria:**
- ✅ All 9 TODOs fixed
- ✅ Frontend API calls working
- ✅ Build succeeds
- ✅ No console errors

---

### Phase 3.3: MyPy Improvement (Day 2-3) 🟡 MEDIUM

#### Task 3.3.1: Add Type Ignores for ORM
**Час:** 4-6 годин  
**Мета:** MyPy errors: 152 → 100

**Проблемні файли:**
- `app/services/auth_service.py`
- `app/services/ai_service.py`
- `app/services/document_service.py`
- `app/api/v1/endpoints/admin.py`

**Дії:**

1. **Add Targeted Ignores:**
```python
# apps/api/app/services/auth_service.py

# BEFORE
user = await self.db.get(User, user_id)
if user.some_field == value:  # MyPy error

# AFTER
user = await self.db.get(User, user_id)
if user is not None and user.some_field == value:  # OK
```

2. **Fix Column vs Instance Issues:**
```python
# BEFORE
result = await self.db.execute(
    select(User).where(User.is_active == True)  # MyPy error
)

# AFTER
result = await self.db.execute(
    select(User).where(User.is_active.is_(True))  # SQLAlchemy 2.0
)
```

**Верифікація:**
```bash
mypy app/ --config-file mypy.ini 2>&1 | wc -l
# Should be ~100 errors
```

**Acceptance Criteria:**
- ✅ MyPy: ~100 errors (from 152)
- ✅ ORM false positives reduced
- ✅ No runtime issues introduced

---

#### Task 3.3.2: Add Return Type Annotations
**Час:** 6-8 годин  
**Мета:** MyPy errors: 100 → ≤50

**Дії:**

1. **Fix Missing Return Types:**
```python
# BEFORE
async def list_users(self, page: int, per_page: int):  # Missing return type
    ...

# AFTER
async def list_users(self, page: int, per_page: int) -> dict[str, Any]:
    ...
```

2. **Fix Decorator Issues:**
```python
# BEFORE
@background_task_error_handler
async def generate_full_document(job_id: int):  # Untyped decorator
    ...

# AFTER
async def _generate_full_document(job_id: int) -> None:
    ...

@background_task_error_handler
def generate_full_document(job_id: int) -> None:
    """Wrapper with typed decorator"""
    return asyncio.create_task(_generate_full_document(job_id))
```

**Верифікація:**
```bash
mypy app/ --config-file mypy.ini 2>&1 | grep "no-untyped-def"
# Should show <10 instances
```

**Acceptance Criteria:**
- ✅ MyPy: ≤50 errors
- ✅ All public functions typed
- ✅ No runtime issues

---

## 📅 Timeline Summary

### P2 Timeline

| Week | Tasks | Total Hours | Deliverables |
|------|-------|-------------|--------------|
| Week 1 | Payment System (Tasks 2.1.1-2.1.4) | 18-26h | Stripe integration, payment endpoints |
| Week 1-2 | Custom Upload (Tasks 2.2.1-2.2.2) | 10-14h | File upload, parsing |
| Week 2 | Coverage (Tasks 2.3.1-2.3.3) | 22-28h | Tests, E2E suite |
| **Total** | **P2 Complete** | **50-68h** | **Full MVP** |

### P3 Timeline

| Day | Tasks | Total Hours | Deliverables |
|-----|-------|-------------|--------------|
| Day 1 | Ruff + Cleanup (Tasks 3.1-3.2) | 8-14h | Ruff fixed, repo clean |
| Day 2-3 | MyPy (Tasks 3.3.1-3.3.2) | 10-14h | MyPy ≤50 errors |
| **Total** | **P3 Complete** | **18-28h** | **Code Quality** |

### Grand Total

**P2 + P3:** 68-96 годин ≈ **2-3 тижні full-time**

---

## ✅ Success Criteria

### P2 Complete When:

- [ ] Payment system functional (Stripe integrated)
- [ ] Custom requirements upload working
- [ ] Coverage ≥70%
- [ ] E2E tests: 10+ scenarios
- [ ] All MVP features documented

### P3 Complete When:

- [ ] Ruff: 0 errors, <50 warnings
- [ ] test.db removed from repo
- [ ] All frontend TODOs fixed
- [ ] MyPy: ≤50 errors
- [ ] Config modernized

---

## 🎯 Priority Ranking

### Critical Path (Must Complete):

1. **Payment System** (P2.1) - БЛОКУЄ MVP launch
2. **Custom Upload** (P2.2) - Core feature
3. **Coverage Improvement** (P2.3) - Risk mitigation

### Nice-to-Have (Can Defer):

1. **P3 Ruff Fixes** - Code quality polish
2. **P3 MyPy** - Type safety improvement
3. **P3 TODOs** - Frontend cleanup

---

**Report Status:** ✅ COMPLETE

**Generated:** 2025-11-02  
**Agent:** Auto (Cursor AI)

