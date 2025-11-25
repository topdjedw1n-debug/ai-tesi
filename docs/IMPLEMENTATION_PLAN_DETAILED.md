# 🚀 ДЕТАЛЬНИЙ ПЛАН ІМПЛЕМЕНТАЦІЇ - TesiGo v2.4

**Дата оновлення:** 2025-11-03
**Статус:** Критичні компоненти відсутні
**Тривалість до MVP:** 7-10 днів

---

## ⚠️ ПОТОЧНИЙ СТАН ПЛАТФОРМИ

### ✅ ВЖЕ РЕАЛІЗОВАНО:
- **Security:** IDOR Protection, JWT Security, File validation, Backup scripts
- **Backend:** Background jobs, Retry mechanisms, Token tracking, DraftService
- **Services:** GDPR service (базовий), CircuitBreaker, RetryStrategy
- **Testing:** Integration tests suite, Load testing (частково)
- **AI:** OpenAI/Anthropic інтеграція, базовий RAG (Semantic Scholar)

### ❌ НЕ РЕАЛІЗОВАНО (блокери для production):
1. **Адмін-панель** - ПОВНІСТЮ ВІДСУТНЯ
2. **Система повернень** - RefundService НЕ ІСНУЄ
3. **Платіжна інтеграція з frontend** - форма оплати відсутня
4. **WebSocket real-time** - частково реалізовано
5. **Search APIs** - код є, але не інтегровано (Perplexity, Tavily)
6. **Динамічне ціноутворення** - відсутнє
7. **Валідація мінімум 3 сторінки** - відсутня
8. **Frontend-Backend інтеграція** - багато mock даних

---

## 📋 ФАЗА 1: КРИТИЧНІ БЛОКЕРИ (3-4 дні)

### 🔴 Task 1.1: АДМІН-ПАНЕЛЬ (2-3 дні) - **НАЙВИЩИЙ ПРІОРИТЕТ!**

**Без адмін-панелі НЕМОЖЛИВО:**
- Обробляти запити на повернення
- Блокувати порушників
- Змінювати ціни
- Моніторити платформу

#### Frontend компоненти для створення:

**Файл:** `apps/web/app/admin/layout.tsx`
```typescript
export default function AdminLayout({ children }) {
  return (
    <div className="admin-layout">
      <AdminSidebar>
        <NavLink href="/admin/dashboard">Dashboard</NavLink>
        <NavLink href="/admin/users">Користувачі</NavLink>
        <NavLink href="/admin/refunds">
          Повернення <Badge>{pendingCount}</Badge>
        </NavLink>
        <NavLink href="/admin/payments">Платежі</NavLink>
        <NavLink href="/admin/settings">Налаштування</NavLink>
      </AdminSidebar>
      <main>{children}</main>
    </div>
  )
}
```

**Файл:** `apps/web/app/admin/dashboard/page.tsx`
```typescript
export default function AdminDashboard() {
  const [stats, setStats] = useState({
    totalUsers: 0,
    todayRevenue: 0,
    activeJobs: 0,
    pendingRefunds: 0
  })

  useEffect(() => {
    fetch('/api/v1/admin/dashboard/stats')
      .then(res => res.json())
      .then(setStats)
  }, [])

  return (
    <div>
      <h1>Адмін панель</h1>

      {/* Статистичні картки */}
      <StatsGrid>
        <StatCard title="Користувачів" value={stats.totalUsers} />
        <StatCard title="Виручка сьогодні" value={`€${stats.todayRevenue}`} />
        <StatCard title="Активні генерації" value={stats.activeJobs} />
        <StatCard
          title="Запити на повернення"
          value={stats.pendingRefunds}
          alert={stats.pendingRefunds > 0}
        />
      </StatsGrid>

      {/* Графіки */}
      <ChartsSection>
        <RevenueChart period="week" />
        <DocumentsChart period="month" />
      </ChartsSection>
    </div>
  )
}
```

**Файл:** `apps/web/app/admin/refunds/page.tsx`
```typescript
export default function RefundRequests() {
  const [requests, setRequests] = useState([])
  const [filter, setFilter] = useState('pending')

  const approveRefund = async (requestId) => {
    const response = await fetch(`/api/v1/admin/refunds/${requestId}/approve`, {
      method: 'POST',
      body: JSON.stringify({ comment: 'Approved by admin' })
    })
    if (response.ok) {
      toast.success('Повернення схвалено')
      fetchRequests()
    }
  }

  const rejectRefund = async (requestId, reason) => {
    const response = await fetch(`/api/v1/admin/refunds/${requestId}/reject`, {
      method: 'POST',
      body: JSON.stringify({ reason })
    })
    if (response.ok) {
      toast.success('Запит відхилено')
      fetchRequests()
    }
  }

  return (
    <div>
      <Tabs value={filter} onChange={setFilter}>
        <Tab value="pending">Очікують ({requests.filter(r => r.status === 'pending').length})</Tab>
        <Tab value="approved">Схвалені</Tab>
        <Tab value="rejected">Відхилені</Tab>
      </Tabs>

      <Table>
        {requests.map(request => (
          <TableRow key={request.id}>
            <TableCell>{request.user_email}</TableCell>
            <TableCell>€{request.amount}</TableCell>
            <TableCell>{request.reason}</TableCell>
            <TableCell>{request.created_at}</TableCell>
            <TableCell>
              {request.status === 'pending' && (
                <>
                  <Button onClick={() => approveRefund(request.id)}>
                    Схвалити
                  </Button>
                  <Button onClick={() => rejectRefund(request.id)}>
                    Відхилити
                  </Button>
                </>
              )}
            </TableCell>
          </TableRow>
        ))}
      </Table>
    </div>
  )
}
```

#### Backend endpoints для розширення:

**Файл:** `apps/api/app/api/v1/endpoints/admin.py` (додати до існуючого)
```python
@router.get("/admin/dashboard/stats")
async def get_dashboard_stats(admin: User = Depends(get_admin_user)):
    """Повна статистика для dashboard"""
    stats = {
        "users": {
            "total": await db.query(User).count(),
            "today": await db.query(User).filter(
                User.created_at >= datetime.now().date()
            ).count(),
            "active_last_7_days": await db.query(User).filter(
                User.last_login >= datetime.now() - timedelta(days=7)
            ).count()
        },
        "revenue": {
            "today": await calculate_revenue("day"),
            "week": await calculate_revenue("week"),
            "month": await calculate_revenue("month")
        },
        "documents": {
            "total": await db.query(Document).count(),
            "generating": await db.query(Document).filter(
                Document.status == "generating"
            ).count()
        },
        "refunds": {
            "pending": await db.query(RefundRequest).filter(
                RefundRequest.status == "pending"
            ).count()
        }
    }
    return stats

@router.post("/admin/users/{user_id}/block")
async def block_user(
    user_id: int,
    reason: str,
    admin: User = Depends(get_admin_user)
):
    user = await db.get(User, user_id)
    user.is_active = False
    user.blocked_reason = reason
    user.blocked_by = admin.id
    await db.commit()

    # Audit log
    await log_admin_action(admin.id, "block_user", user_id, {"reason": reason})
    return {"status": "user_blocked"}

@router.get("/admin/refunds")
async def list_refund_requests(
    status: str = "pending",
    admin: User = Depends(get_admin_user)
):
    requests = await db.query(RefundRequest).filter(
        RefundRequest.status == status
    ).all()
    return requests
```

---

### 🔴 Task 1.2: СИСТЕМА ПОВЕРНЕНЬ (2 дні)

**Критично для EU compliance!**

#### Створення RefundService:

**Файл:** `apps/api/app/services/refund_service.py`
```python
from decimal import Decimal
import stripe
from datetime import datetime, timedelta

class RefundService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.stripe = stripe

    async def request_refund(
        self,
        user_id: int,
        payment_id: int,
        reason_category: str,
        reason_text: str
    ) -> RefundRequest:
        """Створити запит на повернення"""

        # Валідація
        payment = await self.db.get(Payment, payment_id)
        if not payment or payment.user_id != user_id:
            raise ValidationError("Payment not found")

        if payment.status == "refunded":
            raise ValidationError("Already refunded")

        # Перевірка часу (24 години)
        time_passed = datetime.utcnow() - payment.created_at
        if time_passed.total_seconds() > 86400:
            raise ValidationError("Refund period expired (24 hours)")

        # Створення запиту
        refund_request = RefundRequest(
            payment_id=payment_id,
            user_id=user_id,
            reason_category=reason_category,
            reason_text=reason_text,
            status="pending"
        )

        self.db.add(refund_request)
        await self.db.commit()

        # Email адміністраторам
        await self._notify_admins(refund_request)

        return refund_request

    async def process_refund(
        self,
        request_id: int,
        approved: bool,
        admin_id: int,
        comment: str = None
    ):
        """Обробити рішення адміністратора"""
        request = await self.db.get(RefundRequest, request_id)

        if approved:
            # Stripe refund
            payment = await self.db.get(Payment, request.payment_id)
            refund = stripe.Refund.create(
                payment_intent=payment.stripe_payment_intent_id,
                reason="requested_by_customer"
            )

            request.status = "approved"
            request.stripe_refund_id = refund.id
            request.refunded_at = datetime.utcnow()

            payment.status = "refunded"
            payment.refunded_amount = payment.amount
        else:
            request.status = "rejected"

        request.reviewed_by = admin_id
        request.review_comment = comment
        request.reviewed_at = datetime.utcnow()

        await self.db.commit()

        # Email користувачу
        await self._notify_user(request, approved)
```

#### База даних - таблиця refund_requests:

**Файл:** `apps/api/alembic/versions/xxx_add_refund_requests.py`
```python
def upgrade():
    op.create_table(
        'refund_requests',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('payment_id', sa.Integer(), sa.ForeignKey('payments.id')),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id')),
        sa.Column('reason_category', sa.String(50), nullable=False),
        sa.Column('reason_text', sa.Text(), nullable=False),
        sa.Column('status', sa.String(20), default='pending'),
        sa.Column('reviewed_by', sa.Integer(), sa.ForeignKey('users.id')),
        sa.Column('review_comment', sa.Text()),
        sa.Column('reviewed_at', sa.DateTime()),
        sa.Column('stripe_refund_id', sa.String(255)),
        sa.Column('refunded_at', sa.DateTime()),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now())
    )

    op.create_index('idx_refund_requests_status', 'refund_requests', ['status'])
    op.create_index('idx_refund_requests_user', 'refund_requests', ['user_id'])
```

#### Frontend форма запиту:

**Файл:** `apps/web/components/RefundRequestForm.tsx`
```typescript
export function RefundRequestForm({ paymentId, onSuccess }) {
  const [reason, setReason] = useState('')
  const [category, setCategory] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    setIsSubmitting(true)

    const response = await fetch('/api/v1/refunds/request', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
      },
      body: JSON.stringify({
        payment_id: paymentId,
        reason_category: category,
        reason_text: reason
      })
    })

    if (response.ok) {
      toast.success('Запит на повернення відправлено')
      onSuccess()
    } else {
      toast.error('Помилка при створенні запиту')
    }
    setIsSubmitting(false)
  }

  return (
    <form onSubmit={handleSubmit}>
      <h3>Запросити повернення</h3>
      <p className="text-sm text-gray-500">
        Повернення можливе протягом 24 годин після оплати
      </p>

      <select
        value={category}
        onChange={(e) => setCategory(e.target.value)}
        required
      >
        <option value="">Оберіть причину</option>
        <option value="technical_issue">Технічна проблема</option>
        <option value="quality_issue">Незадовільна якість</option>
        <option value="wrong_content">Невідповідний контент</option>
        <option value="other">Інша причина</option>
      </select>

      <textarea
        value={reason}
        onChange={(e) => setReason(e.target.value)}
        placeholder="Детально опишіть причину (мінімум 50 символів)"
        minLength={50}
        required
        rows={4}
      />

      <Button type="submit" disabled={isSubmitting}>
        {isSubmitting ? 'Відправлення...' : 'Відправити запит'}
      </Button>
    </form>
  )
}
```

---

### 🔴 Task 1.3: ПЛАТІЖНА ІНТЕГРАЦІЯ З FRONTEND (2 дні)

**Backend працює, але frontend НЕ МАЄ форми оплати!**

#### Stripe Checkout інтеграція:

**Файл:** `apps/web/components/PaymentForm.tsx`
```typescript
import { loadStripe } from '@stripe/stripe-js'
import { Elements, CardElement, useStripe, useElements } from '@stripe/react-stripe-js'

const stripePromise = loadStripe(process.env.NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY)

export function PaymentForm({ documentId, pages, onSuccess }) {
  const stripe = useStripe()
  const elements = useElements()
  const [isProcessing, setIsProcessing] = useState(false)

  const amount = pages * 0.50 // €0.50 за сторінку

  const handleSubmit = async (e) => {
    e.preventDefault()
    setIsProcessing(true)

    // Створити checkout session
    const response = await fetch('/api/v1/payment/create-checkout', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
      },
      body: JSON.stringify({
        document_id: documentId,
        pages: pages
      })
    })

    const { checkout_url } = await response.json()

    // Перенаправити на Stripe Checkout
    window.location.href = checkout_url
  }

  return (
    <div className="payment-form">
      <h3>Оплата документа</h3>

      <div className="price-breakdown">
        <div className="flex justify-between">
          <span>Кількість сторінок:</span>
          <span>{pages}</span>
        </div>
        <div className="flex justify-between">
          <span>Ціна за сторінку:</span>
          <span>€0.50</span>
        </div>
        <div className="flex justify-between font-bold text-lg">
          <span>Загальна вартість:</span>
          <span>€{amount.toFixed(2)}</span>
        </div>
      </div>

      <div className="mt-6">
        <p className="text-sm text-gray-600 mb-4">
          ⚠️ Після оплати автоматична відміна неможлива.
          Повернення можливе тільки протягом 24 годин за запитом.
        </p>

        <Button
          onClick={handleSubmit}
          disabled={isProcessing}
          className="w-full"
        >
          {isProcessing ? 'Обробка...' : `Оплатити €${amount.toFixed(2)}`}
        </Button>
      </div>
    </div>
  )
}
```

#### Success/Cancel сторінки:

**Файл:** `apps/web/app/payment/success/page.tsx`
```typescript
export default function PaymentSuccess() {
  const searchParams = useSearchParams()
  const sessionId = searchParams.get('session_id')
  const [status, setStatus] = useState('verifying')

  useEffect(() => {
    // Перевірити статус платежу
    fetch(`/api/v1/payment/verify?session_id=${sessionId}`)
      .then(res => res.json())
      .then(data => {
        if (data.success) {
          setStatus('success')
          toast.success('Оплата успішна! Генерація почалась.')
          // Перенаправити на сторінку документа
          setTimeout(() => {
            router.push(`/documents/${data.document_id}`)
          }, 3000)
        }
      })
  }, [sessionId])

  return (
    <div className="text-center py-20">
      {status === 'verifying' && (
        <>
          <Spinner size="lg" />
          <p>Перевіряємо платіж...</p>
        </>
      )}
      {status === 'success' && (
        <>
          <CheckCircleIcon className="w-20 h-20 text-green-500 mx-auto" />
          <h1 className="text-2xl font-bold mt-4">Оплата успішна!</h1>
          <p>Ваш документ генерується. Перенаправляємо...</p>
        </>
      )}
    </div>
  )
}
```

---

## 📋 ФАЗА 2: ВАЖЛИВІ КОМПОНЕНТИ (3-4 дні)

### 🟡 Task 2.1: УНІФІКАЦІЯ AI ГЕНЕРАЦІЇ (1 день)

**Проблема:** Два методи генерації - AIService (без RAG) та SectionGenerator (з RAG)

**Рішення:** Використовувати тільки SectionGenerator

**Файл:** `apps/api/app/services/ai_pipeline/generator.py` (оновити)
```python
# Змінити метод retrieve() на retrieve_sources()
async def generate_section(self, ...):
    # Замість:
    # source_docs = await self.rag_retriever.retrieve(query, limit=10)

    # Використовувати:
    source_docs = await self.rag_retriever.retrieve_sources(query, limit=20)
    # Це включить Perplexity, Tavily, Semantic Scholar
```

**Файл:** `apps/api/app/api/v1/endpoints/generate.py` (оновити)
```python
# Використовувати SectionGenerator замість AIService
from app.services.ai_pipeline.generator import SectionGenerator

@router.post("/generate/section")
async def generate_section(request: SectionRequest, ...):
    generator = SectionGenerator()
    result = await generator.generate_section(
        document=document,
        section_title=request.section_title,
        section_index=request.section_index,
        provider=document.ai_provider,
        model=document.ai_model,
        humanize=True  # Завжди humanize
    )
    return result
```

### 🟡 Task 2.2: ІНТЕГРАЦІЯ SEARCH APIs (1 день)

**Файл:** `apps/api/app/services/ai_pipeline/rag_retriever.py` (активувати існуючий код)
```python
async def retrieve_sources(self, query: str, limit: int = 20):
    """Використати ВСІ доступні search APIs"""
    results = []

    # Паралельні запити до всіх APIs
    tasks = []

    if settings.SEMANTIC_SCHOLAR_API_KEY:
        tasks.append(self.search_semantic_scholar(query))

    if settings.PERPLEXITY_API_KEY:
        tasks.append(self.search_perplexity(query))

    if settings.TAVILY_API_KEY:
        tasks.append(self.search_tavily(query))

    if settings.SERPER_API_KEY:
        tasks.append(self.search_serper(query))  # Додати новий метод

    # Виконати всі паралельно
    all_results = await asyncio.gather(*tasks, return_exceptions=True)

    # Об'єднати результати
    for result in all_results:
        if not isinstance(result, Exception):
            results.extend(result)

    # Дедуплікація та сортування
    return self._deduplicate_sources(results)[:limit]
```

### 🟡 Task 2.3: ДИНАМІЧНЕ ЦІНОУТВОРЕННЯ (1 день)

**Файл:** `apps/api/app/models/pricing.py` (створити)
```python
class PricingConfig(Base):
    __tablename__ = "pricing_config"

    id = Column(Integer, primary_key=True)
    price_per_page = Column(Decimal(10, 2), default=0.50)
    currency = Column(String(3), default="EUR")
    min_pages = Column(Integer, default=3)
    max_pages = Column(Integer, default=200)
    updated_at = Column(DateTime, default=func.now())
    updated_by = Column(Integer, ForeignKey("users.id"))
```

**Файл:** `apps/api/app/services/pricing_service.py` (створити)
```python
class PricingService:
    async def get_current_price(self) -> Decimal:
        config = await self.db.query(PricingConfig).first()
        return config.price_per_page if config else Decimal("0.50")

    async def update_price(self, price: Decimal, admin_id: int):
        config = await self.db.query(PricingConfig).first()
        if not config:
            config = PricingConfig()
            self.db.add(config)

        config.price_per_page = price
        config.updated_by = admin_id
        config.updated_at = datetime.utcnow()
        await self.db.commit()
```

### 🟡 Task 2.4: ВАЛІДАЦІЯ МІНІМУМ 3 СТОРІНКИ (0.5 дня)

**Backend валідація:**

**Файл:** `apps/api/app/schemas/document.py`
```python
class DocumentCreate(BaseModel):
    title: str
    topic: str
    language: str = "en"
    target_pages: int = Field(ge=3, le=200)  # Мінімум 3, максимум 200

    @validator('target_pages')
    def validate_pages(cls, v):
        if v < 3:
            raise ValueError("Мінімум 3 сторінки для замовлення")
        return v
```

**Frontend валідація:**

**Файл:** `apps/web/components/DocumentForm.tsx`
```typescript
const [pages, setPages] = useState(3)  // Default 3

<input
  type="number"
  min={3}
  max={200}
  value={pages}
  onChange={(e) => {
    const value = parseInt(e.target.value)
    if (value < 3) {
      toast.error('Мінімум 3 сторінки')
      setPages(3)
    } else if (value > 200) {
      toast.error('Максимум 200 сторінок')
      setPages(200)
    } else {
      setPages(value)
    }
  }}
/>
<p className="text-sm text-gray-500">Мінімальне замовлення: 3 сторінки (€1.50)</p>
```

---

## 📋 ФАЗА 3: ІНТЕГРАЦІЯ ТА ОПТИМІЗАЦІЯ (2-3 дні)

### 🟠 Task 3.1: ПОВНА FRONTEND-BACKEND ІНТЕГРАЦІЯ (2 дні)

**Замінити всі mock дані на реальні API виклики:**

**Файл:** `apps/web/components/dashboard/StatsOverview.tsx`
```typescript
// ЗАМІНИТИ mock дані
useEffect(() => {
  // Замість setTimeout з фейковими даними:
  fetch('/api/v1/admin/stats', {
    headers: { 'Authorization': `Bearer ${token}` }
  })
    .then(res => res.json())
    .then(data => {
      setStats({
        totalDocuments: data.documents.total,
        totalWords: data.documents.total_words,
        totalCost: data.revenue.total,
        totalTokens: data.tokens.total
      })
      setIsLoading(false)
    })
}, [])
```

**Файл:** `apps/web/components/providers/AuthProvider.tsx`
```typescript
// Завершити всі TODO в AuthProvider
const checkAuth = async () => {
  try {
    const token = localStorage.getItem('auth_token')
    if (!token) {
      setIsLoading(false)
      return
    }

    // ЗАМІНИТИ коментар на реальний виклик
    const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/v1/auth/me`, {
      headers: { 'Authorization': `Bearer ${token}` }
    })

    if (response.ok) {
      const userData = await response.json()
      setUser(userData)
    } else {
      localStorage.removeItem('auth_token')
    }
  } catch (error) {
    console.error('Auth check failed:', error)
  } finally {
    setIsLoading(false)
  }
}
```

### 🟠 Task 3.2: WEBSOCKET REAL-TIME ПРОГРЕС (1 день)

**Файл:** `apps/api/app/services/websocket_manager.py` (створити)
```python
from fastapi import WebSocket
from typing import Dict, List
import json

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[int, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, user_id: int):
        await websocket.accept()
        if user_id not in self.active_connections:
            self.active_connections[user_id] = []
        self.active_connections[user_id].append(websocket)

    async def disconnect(self, websocket: WebSocket, user_id: int):
        if user_id in self.active_connections:
            self.active_connections[user_id].remove(websocket)

    async def send_progress(self, user_id: int, message: dict):
        if user_id in self.active_connections:
            for connection in self.active_connections[user_id]:
                await connection.send_json(message)

manager = ConnectionManager()
```

**Файл:** `apps/web/components/GenerationProgress.tsx` (створити)
```typescript
export function GenerationProgress({ documentId }) {
  const [progress, setProgress] = useState({
    percentage: 0,
    currentSection: '',
    estimatedTime: ''
  })

  useEffect(() => {
    const ws = new WebSocket(`ws://localhost:8000/ws/generation/${documentId}`)

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data)
      setProgress({
        percentage: data.progress_percentage,
        currentSection: data.current_section,
        estimatedTime: data.estimated_time
      })
    }

    return () => ws.close()
  }, [documentId])

  return (
    <div>
      <div className="progress-bar">
        <div
          className="progress-fill"
          style={{ width: `${progress.percentage}%` }}
        />
      </div>
      <p>Генерується: {progress.currentSection}</p>
      <p>Залишилось: {progress.estimatedTime}</p>
    </div>
  )
}
```

### 🟠 Task 3.3: EMAIL ПОВІДОМЛЕННЯ (1 день)

**Файл:** `apps/api/app/services/notification_service.py` (створити)
```python
class NotificationService:
    async def notify_document_ready(self, document_id: int):
        document = await self.db.get(Document, document_id)
        user = await self.db.get(User, document.user_id)

        # Email template
        subject = "Ваш документ готовий! ✅"
        body = f"""
        Шановний {user.full_name or 'користувачу'},

        Ваш документ "{document.title}" успішно згенеровано!

        Деталі:
        - Сторінок: {document.pages_generated}
        - Мова: {document.language}

        Переглянути та завантажити:
        {settings.FRONTEND_URL}/documents/{document_id}

        З повагою,
        Команда TesiGo
        """

        await send_email(user.email, subject, body)

    async def notify_generation_failed(self, document_id: int, error: str):
        # Аналогічно для помилок
        pass
```

---

## 📋 ФАЗА 4: DEPLOYMENT (1-2 дні)

### 🟢 Task 4.1: PRODUCTION ENVIRONMENT (1 день)

**Створити production .env:**
```bash
# .env.production
ENVIRONMENT=production
DEBUG=false
SECRET_KEY=[generate with: python -c 'import secrets; print(secrets.token_urlsafe(48))']
JWT_SECRET=[generate separately]
DATABASE_URL=postgresql+asyncpg://user:pass@localhost/tesigo_prod
REDIS_URL=redis://localhost:6379

# AI Keys
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
PERPLEXITY_API_KEY=pplx-...
TAVILY_API_KEY=tvly_...
SERPER_API_KEY=...

# Stripe
STRIPE_SECRET_KEY=sk_live_...
STRIPE_WEBHOOK_SECRET=whsec_...
STRIPE_PUBLISHABLE_KEY=pk_live_...

# Domains
FRONTEND_URL=https://tesigo.com
BACKEND_URL=https://api.tesigo.com
CORS_ALLOWED_ORIGINS=https://tesigo.com,https://www.tesigo.com
```

**SSL сертифікат:**
```bash
# Install certbot
sudo apt install certbot python3-certbot-nginx

# Get certificate
sudo certbot --nginx -d tesigo.com -d www.tesigo.com -d api.tesigo.com
```

**Docker production:**
```bash
# Build
docker-compose -f docker-compose.prod.yml build

# Run
docker-compose -f docker-compose.prod.yml up -d

# Migrations
docker exec tesigo-api alembic upgrade head
```

### 🟢 Task 4.2: MONITORING (0.5 дня)

**Prometheus + Grafana:**
```yaml
# docker-compose.monitoring.yml
version: '3.8'
services:
  prometheus:
    image: prom/prometheus
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
    ports:
      - "9090:9090"

  grafana:
    image: grafana/grafana
    ports:
      - "3001:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
```

---

## 📊 ЧЕКЛИСТ ГОТОВНОСТІ

### ✅ Вже готово:
- [x] Security (IDOR, JWT, File validation)
- [x] Background jobs
- [x] Retry mechanisms
- [x] Token tracking
- [x] Integration tests
- [x] GDPR service (базовий)

### ❌ Критичні блокери (must have):
- [ ] **Адмін-панель** - без неї неможливо керувати
- [ ] **Система повернень** - EU compliance вимога
- [ ] **Платіжна форма** - без неї немає монетизації

### 🟡 Важливо (should have):
- [ ] Уніфікація AI генерації
- [ ] Інтеграція всіх Search APIs
- [ ] Динамічне ціноутворення
- [ ] Валідація 3 сторінок
- [ ] WebSocket real-time
- [ ] Email повідомлення

### 🟢 Nice to have:
- [ ] 80% test coverage
- [ ] Monitoring dashboards
- [ ] Auto-scaling

---

## ⏱️ TIMELINE

**Загальний час до production: 7-10 днів**

- **Дні 1-3:** Критичні блокери (адмін-панель, повернення, платежі)
- **Дні 4-6:** Важливі компоненти (AI, ціни, інтеграція)
- **Дні 7-8:** Оптимізація та тестування
- **Дні 9-10:** Deployment та monitoring

---

## 🚀 КОМАНДИ ДЛЯ СТАРТУ

```bash
# Міграції для refund_requests
cd apps/api
alembic revision --autogenerate -m "Add refund requests"
alembic upgrade head

# Запуск з адмін-панеллю
cd apps/web
npm run dev

# Backend
cd apps/api
uvicorn main:app --reload

# Тестування
pytest tests/ -v --cov=app
```

---

**Документ оновлено:** 2025-11-03
**Статус:** Готовий до виконання
**Пріоритет:** КРИТИЧНІ компоненти першими!
