# ⚡ ШВИДКИЙ ГАЙД: Виправлення Критичних P0 Багів

**Час:** 2-3 години
**Складність:** Початкова-Середня
**Все, що потрібно знати для виправлення критичних помилок**

---

## 🎯 4 КРИТИЧНІ ЗАДАЧІ

### 1️⃣ Email Magic Link (45 хв)

**Проблема:** Magic link надсилається тільки в лог, а не на email

**ЩО РОБИТИ:**

#### Крок 1: Вибері SMTP провайдера (15 хв)

**Найпростіше - Mailtrap (FREE):**
1. Зареєструйся на https://mailtrap.io
2. Отримай credentials в Sandbox → SMTP Settings
3. Додай в `apps/api/.env`:
   ```
   SMTP_HOST=sandbox.smtp.mailtrap.io
   SMTP_PORT=2525
   SMTP_TLS=false
   SMTP_USER=your-mailtrap-user
   SMTP_PASSWORD=your-mailtrap-password
   EMAILS_FROM_EMAIL=noreply@tesigo.local
   EMAILS_FROM_NAME=TesiGo
   ```

#### Крок 2: Створи Email Service (15 хв)

**Файл:** `apps/api/app/services/email_service.py`

**Скопіюй ЦІЛИЙ ФАЙЛ:**

```python
"""Email service for sending emails"""
import logging
from typing import Any
from fastapi_mail import FastMail, MessageSchema, ConnectionConfig
from app.core.config import settings

logger = logging.getLogger(__name__)

class EmailService:
    def __init__(self):
        self.conf = ConnectionConfig(
            MAIL_USERNAME=settings.SMTP_USER or "",
            MAIL_PASSWORD=settings.SMTP_PASSWORD or "",
            MAIL_FROM=settings.EMAILS_FROM_EMAIL or "noreply@tesigo.local",
            MAIL_PORT=settings.SMTP_PORT or 587,
            MAIL_SERVER=settings.SMTP_HOST or "localhost",
            MAIL_FROM_NAME=settings.EMAILS_FROM_NAME or "TesiGo",
            MAIL_STARTTLS=settings.SMTP_TLS,
            MAIL_SSL_TLS=False,
            USE_CREDENTIALS=True,
            VALIDATE_CERTS=False,  # Disable for Mailtrap
        )
        self.fm = FastMail(self.conf)

    async def send_magic_link_email(self, email: str, magic_link: str) -> bool:
        try:
            html = f"""<html><body>
                <h2>Welcome to TesiGo</h2>
                <p>Click: <a href="{magic_link}">{magic_link}</a></p>
                <p>Expires in 10 minutes.</p>
            </body></html>"""

            message = MessageSchema(
                subject="Your TesiGo Sign-In Link",
                recipients=[email],
                body=html,
                subtype="html",
            )
            await self.fm.send_message(message)
            logger.info(f"Magic link sent to {email}")
            return True
        except Exception as e:
            logger.error(f"Email failed: {e}")
            return False

_email_service: EmailService | None = None

def get_email_service() -> EmailService:
    global _email_service
    if _email_service is None:
        _email_service = EmailService()
    return _email_service
```

#### Крок 3: Інтегруй в Auth (15 хв)

**Файл:** `apps/api/app/services/auth_service.py`

**Знайди рядок 60 та заміни:**

**БУЛО:**
```python
# TODO: Send email with magic link
# For now, we'll just return the token for development
magic_link = f"http://localhost:3000/auth/verify?token={token}"
```

**СТАЛО:**
```python
# Send email with magic link
from app.services.email_service import get_email_service

email_service = get_email_service()
magic_link = f"http://localhost:3000/auth/verify?token={token}"

# Send email
email_sent = await email_service.send_magic_link_email(email, magic_link)
if not email_sent:
    logger.warning(f"Email failed, but token generated: {token}")
```

#### Крок 4: Тест (5 хв)

```bash
# Запусти API
cd apps/api && uvicorn main:app --reload

# В іншому терміналі:
curl -X POST http://localhost:8000/api/v1/auth/magic-link \
  -H "Content-Type: application/json" \
  -d '{"email": "test@example.com"}'

# Перевір Mailtrap inbox - там має бути лист!
```

**Очікуваний результат:** ✅ Лист в Mailtrap inbox

---

### 2️⃣ Daily Token Limit (10 хв)

**Проблема:** Логується warning, але генерація продовжується

**Файл:** `apps/api/app/services/ai_service.py`

**Знайди рядок 57-62:**

**БУЛО:**
```python
if today_tokens >= settings.DAILY_TOKEN_LIMIT:
    logger.warning(f"Daily token limit exceeded: {today_tokens}/{settings.DAILY_TOKEN_LIMIT}")
    # Note: According to task, we can continue or raise error
    # For now, just log a warning and continue
```

**СТАЛО:**
```python
if today_tokens >= settings.DAILY_TOKEN_LIMIT:
    logger.error(f"Daily token limit exceeded: {today_tokens}/{settings.DAILY_TOKEN_LIMIT}")
    from app.core.exceptions import AIProviderError
    raise AIProviderError(f"Daily token limit exceeded. Current: {today_tokens}, Limit: {settings.DAILY_TOKEN_LIMIT}")
```

**Тест:**
```bash
# Додай в .env: DAILY_TOKEN_LIMIT=100
# Спробуй згенерувати > 100 токенів
# Має бути помилка
```

---

### 3️⃣ Webhook Idempotency (30 хв)

**Проблема:** Stripe може надіслати подію двічі = подвійний платіж

#### Крок 1: Додай поле в БД

**Файл:** `apps/api/app/models/payment.py`

**Знайди модель Payment, додай після рядка 32:**
```python
stripe_event_id = Column(String(255), unique=True, nullable=True, index=True)
```

#### Крок 2: Створи migration

```bash
cd apps/api
alembic revision -m "add_stripe_event_id"
```

**Відкрий останній файл в `alembic/versions/`, додай:**

**В upgrade():**
```python
def upgrade():
    op.add_column('payments', sa.Column('stripe_event_id', sa.String(255), nullable=True))
    op.create_index('ix_payments_stripe_event_id', 'payments', ['stripe_event_id'], unique=True)
```

**В downgrade():**
```python
def downgrade():
    op.drop_index('ix_payments_stripe_event_id', 'payments')
    op.drop_column('payments', 'stripe_event_id')
```

**Запусти:**
```bash
alembic upgrade head
```

#### Крок 3: Додай перевірку

**Файл:** `apps/api/app/services/payment_service.py`

**Знайди метод `handle_webhook`, додай на початку:**

```python
async def handle_webhook(self, payload: bytes, signature: str):
    """Handle Stripe webhook with idempotency"""
    import stripe

    # Verify signature
    event = stripe.Webhook.construct_event(
        payload, signature, settings.STRIPE_WEBHOOK_SECRET
    )

    # IDEMPOTENCY: Check if already processed
    event_id = event.get('id')
    if event_id:
        existing = await self.db.execute(
            select(Payment).where(Payment.stripe_event_id == event_id)
        )
        if existing.scalar_one_or_none():
            logger.info(f"Event {event_id} already processed")
            return None  # Skip

    # ... existing code ...

    # AFTER success, save event_id
    if event_id and payment:
        payment.stripe_event_id = event_id
        await self.db.commit()
```

---

### 4️⃣ PDF Export (30 хв)

**Проблема:** PDF створюється, але не працює коректно

#### Крок 1: Перевір WeasyPrint

```bash
cd apps/api
python3 -c "import weasyprint; print('OK')"

# Якщо помилка на macOS:
brew install python-weasyprint

# Якщо помилка на Ubuntu:
sudo apt install python3-dev libcairo2 libpango-1.0-0 libpangocairo-1.0-0
pip install --force-reinstall weasyprint
```

#### Крок 2: Додай PDF метод

**Файл:** `apps/api/app/services/document_service.py`

**Додай метод:**

```python
async def _create_pdf(self, document: Document) -> str:
    """Create PDF from document"""
    from weasyprint import HTML
    import os

    html = f"""<html><head><meta charset="UTF-8"><title>{document.title}</title>
    <style>body{{font-family:'Times New Roman';font-size:12pt;margin:1in;}}</style>
    </head><body><h1>{document.title}</h1><div>{document.content.replace(chr(10),'<br>')}</div></body></html>"""

    pdf_dir = "uploads/pdfs"
    os.makedirs(pdf_dir, exist_ok=True)
    pdf_path = f"{pdf_dir}/document_{document.id}.pdf"

    HTML(string=html).write_pdf(pdf_path)
    logger.info(f"PDF created: {pdf_path}")
    return pdf_path
```

#### Крок 3: Інтегруй в export

**В методі `export_document` знайди if format == "pdf":**

```python
if format.lower() == "pdf":
    pdf_path = await self._create_pdf(document)

    # Upload to MinIO
    file_key = f"pdfs/document_{document_id}.pdf"
    await upload_to_storage(pdf_path, file_key)  # Implement this

    document.pdf_path = file_key
    await self.db.commit()

    return {
        "format": "pdf",
        "file_url": f"/api/v1/documents/{document_id}/download/pdf",
        "file_path": file_key
    }
```

---

## ✅ ШВИДКИЙ ТЕСТ ВСЬОГО

```bash
# 1. Перезапусти API
cd apps/api && uvicorn main:app --reload

# 2. Test email
curl -X POST http://localhost:8000/api/v1/auth/magic-link \
  -d '{"email":"test@example.com"}'
# → Перевір Mailtrap inbox

# 3. Test PDF
curl -X POST http://localhost:8000/api/v1/documents/1/export \
  -H "Authorization: Bearer TOKEN" \
  -d '{"format":"pdf"}'
# → Перевір що PDF створюється

# 4. Test token limit
# Додай DAILY_TOKEN_LIMIT=100 в .env
# Згенеруй > 100 токенів → має бути помилка
```

---

## 🎯 РЕЗУЛЬТАТ

**Після цих 4 виправлень:**

✅ Email працює
✅ Token limit блокує
✅ Webhook idempotent
✅ PDF працює
✅ Production Ready!

**Час:** ~2 години
**Складність:** ⭐⭐☆☆☆ (Початкова)

---

**Детальна інструкція:** `docs/STEP_BY_STEP_PRODUCTION_GUIDE.md`
**Повний аудит:** `reports/FULL_AUDIT_REPORT_2025_11_02.md`
