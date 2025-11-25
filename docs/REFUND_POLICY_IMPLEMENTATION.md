# 💰 Політика повернень TesiGo - Технічна реалізація

> Детальний опис політики повернень та технічна реалізація

**Дата створення:** 2025-11-03
**Версія:** 1.0
**Статус:** До реалізації

---

## 📋 Політика повернень

### Основні принципи:
1. **БЕЗ автоматичної відміни** після успішної оплати
2. **Автоматичне повернення** тільки при технічних помилках
3. **Ручне повернення** тільки після апруву адміністратора
4. **Обов'язкове обґрунтування** для запиту повернення

---

## 🔄 Сценарії повернення

### 1. Автоматичне повернення (без участі адміністратора)

#### Умови:
- ✅ Генерація failed після 3 спроб
- ✅ Технічна помилка системи (500 errors)
- ✅ Неможливість почати генерацію протягом 1 години
- ✅ Критична помилка AI провайдера

#### Процес:
```python
async def handle_generation_failure(payment_id: int):
    # 1. Перевірка статусу документа
    if document.status == "failed" and document.retry_count >= 3:
        # 2. Ініціація повернення через Stripe
        refund = stripe.Refund.create(
            payment_intent=payment.stripe_payment_intent_id,
            reason="requested_by_customer"  # або "duplicate" чи "fraudulent"
        )
        # 3. Оновлення статусу в БД
        payment.status = "refunded"
        payment.refund_reason = "technical_failure"
        payment.refunded_at = datetime.utcnow()
        # 4. Email повідомлення користувачу
        send_refund_notification(user, payment, reason="technical")
```

---

### 2. Повернення за запитом користувача

#### Умови для подачі запиту:
- ⏰ Протягом 24 годин після оплати
- 📄 Документ НЕ завантажено користувачем
- 🔄 Не більше 1 запиту на повернення для замовлення

#### Форма запиту повернення:

```typescript
interface RefundRequest {
  payment_id: number;          // ID платежу
  order_id: number;            // ID замовлення
  reason_category: string;     // Категорія причини
  reason_text: string;         // Детальний опис (мін. 50 символів)
  user_email: string;          // Email для зв'язку
  screenshots?: File[];        // Додаткові докази
  submitted_at: Date;          // Час подачі
}
```

#### Категорії причин:
- `technical_issue` - Технічна проблема
- `quality_issue` - Незадовільна якість
- `wrong_content` - Невідповідний контент
- `duplicate_payment` - Дублювання платежу
- `other` - Інша причина

---

## 👨‍💼 Адмін-панель для розгляду

### Інтерфейс адміністратора:

```python
# Новий endpoint для отримання запитів на повернення
@router.get("/admin/refund-requests")
async def get_refund_requests(
    status: str = "pending",  # pending, approved, rejected
    admin_user: User = Depends(get_admin_user)
):
    return await RefundService.get_refund_requests(status)

# Апрув/відхилення запиту
@router.post("/admin/refund-requests/{request_id}/review")
async def review_refund_request(
    request_id: int,
    decision: RefundDecision,
    admin_user: User = Depends(get_admin_user)
):
    return await RefundService.process_refund_decision(
        request_id,
        decision,
        admin_id=admin_user.id
    )
```

### Дані для адміністратора:
```python
class RefundRequestAdmin:
    # Інформація про замовлення
    order_id: int
    payment_amount: Decimal
    document_status: str
    generation_time: int
    pages_generated: int

    # Інформація про користувача
    user_email: str
    user_registration_date: datetime
    total_orders: int
    previous_refunds: int

    # Деталі запиту
    reason_category: str
    reason_text: str
    screenshots: List[str]

    # Рекомендація системи
    ai_recommendation: str  # "approve" / "reject" / "review"
    risk_score: float       # 0.0 - 1.0
```

---

## 💾 База даних

### Нова таблиця `refund_requests`:

```sql
CREATE TABLE refund_requests (
    id SERIAL PRIMARY KEY,
    payment_id INTEGER REFERENCES payments(id),
    user_id INTEGER REFERENCES users(id),

    -- Request details
    reason_category VARCHAR(50) NOT NULL,
    reason_text TEXT NOT NULL,
    screenshots JSONB,

    -- Status
    status VARCHAR(20) DEFAULT 'pending',  -- pending, approved, rejected, expired

    -- Admin review
    reviewed_by INTEGER REFERENCES users(id),
    review_comment TEXT,
    reviewed_at TIMESTAMP,

    -- Refund details
    refund_amount DECIMAL(10,2),
    stripe_refund_id VARCHAR(255),
    refunded_at TIMESTAMP,

    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Індекси для швидкого пошуку
CREATE INDEX idx_refund_requests_status ON refund_requests(status);
CREATE INDEX idx_refund_requests_user ON refund_requests(user_id);
CREATE INDEX idx_refund_requests_payment ON refund_requests(payment_id);
```

---

## 🔧 Технічна реалізація

### 1. RefundService (`app/services/refund_service.py`):

```python
class RefundService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.stripe = stripe

    async def request_refund(
        self,
        user_id: int,
        payment_id: int,
        reason_category: str,
        reason_text: str,
        screenshots: List[str] = None
    ) -> RefundRequest:
        """Створити запит на повернення"""
        # 1. Валідація
        await self._validate_refund_eligibility(payment_id, user_id)

        # 2. Створення запиту
        refund_request = RefundRequest(
            payment_id=payment_id,
            user_id=user_id,
            reason_category=reason_category,
            reason_text=reason_text,
            screenshots=screenshots,
            status="pending"
        )

        # 3. Збереження в БД
        self.db.add(refund_request)
        await self.db.commit()

        # 4. Повідомлення адміністраторів
        await self._notify_admins(refund_request)

        return refund_request

    async def process_refund(
        self,
        request_id: int,
        approved: bool,
        admin_id: int,
        comment: str = None
    ) -> RefundRequest:
        """Обробити рішення адміністратора"""
        # 1. Отримати запит
        request = await self._get_request(request_id)

        if approved:
            # 2a. Виконати повернення через Stripe
            refund = await self._stripe_refund(request.payment_id)

            # 3a. Оновити статуси
            request.status = "approved"
            request.stripe_refund_id = refund.id
            request.refunded_at = datetime.utcnow()

            # 4a. Оновити статус платежу
            await self._update_payment_status(request.payment_id, "refunded")

        else:
            # 2b. Відхилити запит
            request.status = "rejected"

        # 5. Зберегти рішення
        request.reviewed_by = admin_id
        request.review_comment = comment
        request.reviewed_at = datetime.utcnow()

        await self.db.commit()

        # 6. Повідомити користувача
        await self._notify_user(request, approved)

        return request

    async def _validate_refund_eligibility(
        self,
        payment_id: int,
        user_id: int
    ) -> None:
        """Перевірити чи можливе повернення"""
        payment = await self._get_payment(payment_id)

        # Перевірки
        if payment.user_id != user_id:
            raise ValidationError("Payment not found")

        if payment.status == "refunded":
            raise ValidationError("Already refunded")

        if payment.status != "completed":
            raise ValidationError("Payment not completed")

        # Перевірка часу (24 години)
        time_passed = datetime.utcnow() - payment.created_at
        if time_passed.total_seconds() > 86400:  # 24 hours
            raise ValidationError("Refund period expired")

        # Перевірка чи документ не завантажено
        document = await self._get_document(payment.document_id)
        if document.download_count > 0:
            raise ValidationError("Document already downloaded")

        # Перевірка на дублікати
        existing = await self._check_existing_request(payment_id)
        if existing:
            raise ValidationError("Refund request already exists")
```

---

## 📧 Email повідомлення

### Для користувача:

#### При поданні запиту:
```
Subject: Ваш запит на повернення отримано

Шановний користувачу,

Ми отримали ваш запит на повернення для замовлення #[ORDER_ID].

Деталі запиту:
- Сума: €[AMOUNT]
- Причина: [REASON]
- Статус: На розгляді

Ми розглянемо ваш запит протягом 24 годин.

З повагою,
Команда TesiGo
```

#### При апруві:
```
Subject: Повернення схвалено ✅

Ваш запит на повернення схвалено!

Кошти будуть повернені на вашу картку протягом 5-10 робочих днів.

Сума повернення: €[AMOUNT]
Номер повернення: [REFUND_ID]
```

#### При відхиленні:
```
Subject: Запит на повернення відхилено

На жаль, ваш запит на повернення відхилено.

Причина: [ADMIN_COMMENT]

Якщо у вас є питання, зв'яжіться з підтримкою.
```

### Для адміністратора:
```
Subject: 🔔 Новий запит на повернення

Новий запит на повернення #[REQUEST_ID]

Користувач: [USER_EMAIL]
Сума: €[AMOUNT]
Причина: [REASON_CATEGORY]

Переглянути в адмін-панелі: [ADMIN_LINK]
```

---

## 📊 Метрики та моніторинг

### KPI для відстеження:
- **Refund Rate** - % повернень від загальної кількості
- **Approval Rate** - % схвалених запитів
- **Processing Time** - середній час розгляду
- **Reason Distribution** - розподіл за причинами

### Алерти:
- Refund Rate > 5% - попередження
- Refund Rate > 10% - критичний алерт
- Processing Time > 24h - алерт адміністраторам

---

## ✅ Checklist для реалізації

### Backend:
- [ ] Створити таблицю `refund_requests`
- [ ] Реалізувати `RefundService`
- [ ] Додати endpoints для користувачів
- [ ] Додати admin endpoints
- [ ] Інтегрувати Stripe Refund API
- [ ] Налаштувати email повідомлення
- [ ] Додати валідацію та перевірки

### Frontend:
- [ ] Форма запиту повернення
- [ ] Сторінка історії повернень
- [ ] Адмін-панель для розгляду
- [ ] Статуси в історії замовлень

### Testing:
- [ ] Unit тести для RefundService
- [ ] Integration тести для endpoints
- [ ] E2E тести для повного флоу

### Documentation:
- [ ] Оновити Terms of Service
- [ ] Додати Refund Policy сторінку
- [ ] FAQ про повернення

---

## 🚨 Важливі моменти

1. **Безпека:**
   - Перевірка ownership платежу
   - Rate limiting для запитів
   - Аудит лог всіх дій

2. **Stripe:**
   - Використовувати Stripe Refund API
   - Обробляти webhook події
   - Зберігати refund_id

3. **UX:**
   - Чіткі повідомлення про статус
   - Прозорі умови повернення
   - Швидкий розгляд запитів

4. **Юридичні аспекти:**
   - Відповідність EU законодавству
   - Чіткі Terms of Service
   - Документування всіх рішень

---

**Цей документ є основою для реалізації системи повернень в TesiGo**
