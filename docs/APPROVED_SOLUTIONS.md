# 📋 ЗАТВЕРДЖЕНІ РІШЕННЯ - TesiGo v2.3
**Дата створення:** 2025-11-02  
**Статус:** Активний документ

---

## 📌 ВАЖЛИВІ ДОМОВЛЕНОСТІ

### Бізнес-модель
- **Модель:** Оплата за сторінку (НЕ підписка)
- **Ціна:** €0.50 за сторінку (базова, може змінюватись через admin panel)
- **Валюта:** Тільки EUR
- **Мови:** Без української (поки що)
- **Фокус:** Технічна реалізація (НЕ обговорюємо ROI, податки, маркетинг)

### Технічні обмеження
- **Max сторінок:** 200 на документ
- **Min ціна:** €0.10 (захист від негативних цін)
- **Генерація:** По логічних розділах, НЕ технічних chunks
- **Email:** Регістр не важливий, але john.doe@gmail.com ≠ johndoe@gmail.com

---

## ✅ ЗАТВЕРДЖЕНІ РІШЕННЯ

### 1. AI COST CONTROL
**Проблема:** Неконтрольовані витрати на AI API, один користувач може спалити весь бюджет

**Рішення:**
```python
# Pre-checker перед генерацією
async def estimate_cost(pages: int, model: str) -> Decimal:
    tokens_per_page = 1500  # average
    total_tokens = pages * tokens_per_page
    cost_per_1k = MODEL_COSTS[model]
    return (total_tokens / 1000) * cost_per_1k

# Перевірка балансу
if estimated_cost > available_balance:
    raise InsufficientFundsError()
```

**Компоненти:**
- Pre-estimation витрат перед генерацією
- Динамічне ціноутворення (оплата за сторінку)
- Моніторинг балансу з алертами для адміна
- Smart caching (ТІЛЬКИ технічні дані: search results, terminology, templates)
- ❌ НЕ кешуємо контент (ризик плагіату)

**Нюанси:**
- Український текст дорожчий (більше токенів)
- Різні моделі = різні ціни
- Fallback на дешевшу модель при перевищенні бюджету

**Статус:** ✅ Затверджено

---

### 2. RETRY МЕХАНІЗМИ
**Проблема:** Один збій API = втрата всієї роботи

**Рішення:**
```python
class RetryStrategy:
    # Exponential backoff
    delays = [2, 4, 8, 16, 32]  # секунди
    
    # Provider fallback
    fallback_chain = [
        "gpt-4",
        "gpt-4-turbo", 
        "gpt-3.5-turbo",
        "claude-3.5-sonnet"
    ]
    
    # Checkpoints кожні 5 хвилин
    checkpoint_interval = 300
```

**Компоненти:**
- Exponential backoff з jitter
- Provider fallback (GPT-4 → GPT-3.5 → Claude)
- Progress saving з checkpoints
- Circuit breaker pattern
- Idempotency keys

**Проблеми які виявили:**
- Fallback на іншу модель = інша якість тексту
- Користувач може відмінити під час retry
- Потрібна idempotency щоб уникнути дублікатів

**Статус:** ✅ Затверджено

---

### 3. MEMORY LEAKS
**Проблема:** OutOfMemory при великих документах (80+ сторінок)

**Рішення:**
```python
class MemoryOptimizedGeneration:
    MAX_PAGES_PER_DOCUMENT = 200
    
    # Генерація по ЛОГІЧНИХ розділах
    async def generate_by_sections(outline):
        for section in outline["sections"]:
            content = await generate_section(section)
            await save_to_storage(content)  # Одразу в БД
            del content  # Звільняємо RAM
            gc.collect()
```

**Компоненти:**
- Генерація по логічних розділах (НЕ chunks!)
- Streaming в БД/MinIO (не тримаємо в RAM)
- Максимум 200 сторінок на документ
- Очищення пам'яті після кожного розділу
- File-based storage для великих документів

**Критична домовленість:**
- НЕ розбиваємо розділи посередині
- Малі розділи (<30 стор) - генеруємо цілком
- Великі розділи (>50 стор) - розбиваємо на логічні підрозділи

**Проблеми які виявили:**
- Зображення/графіки теж займають RAM
- Concurrent генерації множать memory usage
- Кеш проміжних результатів теж в RAM

**Статус:** ✅ Затверджено

---

### 4. ТРАНЗАКЦІЇ БД
**Проблема:** Неконсистентні дані при збоях (платіж є, документа немає)

**Рішення:**
```python
class TransactionalService:
    @asynccontextmanager
    async def atomic_transaction(self):
        async with self.db.begin():
            try:
                yield self.db
                # Auto-commit якщо OK
            except Exception:
                # Auto-rollback при помилці
                await self.db.rollback()
                raise
```

**Компоненти:**
- Atomic transactions (все або нічого)
- Saga pattern для multi-step операцій
- Idempotency keys для безпечних retry
- Event sourcing для відновлення
- Compensation логіка для відкату

**Сценарії які покриваємо:**
1. Платіж без документа
2. Дублікати через retry
3. Частковий стан (неповний документ)

**Проблеми які виявили:**
- Deadlocks при concurrent транзакціях
- Long-running транзакції блокують таблиці
- Event sourcing = величезний розмір БД

**Статус:** ✅ Затверджено

---

### 5. АСИНХРОННА ГЕНЕРАЦІЯ
**Проблема:** HTTP timeout при довгих генераціях (30-60 сек)

**Рішення:**
```python
# Використовуємо існуючий BackgroundJobService!
@router.post("/generate/document")
async def generate_async(request, background_tasks: BackgroundTasks):
    job_id = await create_job(document_id)
    
    background_tasks.add_task(
        background_job_service.generate_document_async,
        document_id, job_id
    )
    
    return {
        "job_id": job_id,
        "status": "queued",
        "check_url": f"/api/v1/jobs/{job_id}/status"
    }
```

**Компоненти:**
- Background jobs (BackgroundJobService ВЖЕ Є!)
- WebSocket для real-time updates
- Smart queue з пріоритетами (малі документи першими)
- Auto-scaling workers (2-10)
- Checkpoints кожні 5 хвилин

**Проблеми які виявили:**
- WebSocket reconnection при обриві
- Прогрес з іншого браузера
- Queue overflow при масових запитах
- BackgroundJobService є але НЕ ВИКОРИСТОВУЄТЬСЯ в endpoints!

**Статус:** ✅ Затверджено

---

### 6. ІЗОЛЯЦІЯ КОНТЕКСТІВ
**Проблема:** 10 користувачів = змішування контекстів між документами

**Рішення:**
```python
class IsolatedAIService:
    async def generate_with_isolation(
        self, document_id: int, prompt: str
    ):
        # Кожен документ = окрема сесія
        session_id = f"doc_{document_id}_{uuid.uuid4()}"
        
        # Новий AI client для кожного!
        ai_client = OpenAI()  
        
        messages = [{
            "role": "system",
            "content": f"""
            SESSION: {session_id}
            DOCUMENT: {document_id}
            You are generating for ONE document only.
            DO NOT reference other documents.
            """
        }]
        
        response = await ai_client.chat.completions.create(
            messages=messages,
            seed=document_id  # Консистентність в межах документа
        )
        
        del ai_client  # Очищаємо після використання
```

**Компоненти:**
- Унікальна сесія для кожного документа
- Новий AI client instance для кожного
- Thread-safe через ContextVar
- Валідація на cross-contamination
- Ізольовані prompts

**Реальні сценарії змішування:**
- User 1: медицина, User 2: криптовалюти → змішаний контент
- Різні мови в одночасних генераціях
- Витік персональних даних між документами

**Статус:** ✅ Затверджено

---

### 7. МАСШТАБУВАННЯ
**Проблема:** Система впаде вже при 5+ одночасних користувачах

**Рішення:**
| Користувачів | Інфраструктура | Вартість/міс |
|-------------|----------------|--------------|
| 1-20 | 1 сервер (4GB RAM) | $40 |
| 20-50 | 2 сервери + Load Balancer | $120 |
| 50-100 | 4 сервери + Redis Cluster | $300 |
| 100+ | Kubernetes cluster | $800+ |

**Компоненти:**
- Multiple OpenAI API keys (round-robin)
- Connection pooling (20 connections, не 100)
- Redis cluster для distributed cache
- Horizontal scaling з load balancer
- Memory streaming (не тримати в RAM)

**Bottlenecks:**
1. OpenAI API limits (500 rpm для GPT-4)
2. PostgreSQL connections (max 100)
3. RAM при concurrent генераціях

**Статус:** ✅ Затверджено

---

### 8. EMAIL VERIFICATION
**Проблема:** Magic link без перевірки = spam на чужі emails

**Рішення:**
```python
class SecureEmailVerification:
    # Double opt-in
    async def request_magic_link(email: str):
        # НЕ створюємо користувача!
        verification_request = EmailVerificationRequest(
            email=email,
            code=secrets.token_urlsafe(32),
            status="pending"
        )
        # Тільки після верифікації створюємо user
    
    # Email canonicalization
    def normalize_email(email: str):
        local, domain = email.rsplit('@', 1)
        # lowercase але НЕ ігноруємо крапки!
        return f"{local.lower()}@{domain.lower()}"
```

**Компоненти:**
- Double opt-in (верифікація → створення user)
- Rate limiting (IP: 5/hour, email: 3/day, domain: 20/hour)
- Email canonicalization
- Anti-spam (блокування temp emails)
- Захист від enumeration attacks
- Захист від timing attacks
- Multi-factor magic link (код + link + fingerprint)

**Критичні уточнення:**
- ✅ JOHN@GMAIL.COM = john@gmail.com
- ❌ john.doe@gmail.com ≠ johndoe@gmail.com (НЕ ігноруємо крапки!)
- Gmail aliases: john+work@gmail.com → john@gmail.com

**Додаткові проблеми:**
- Email bombing (1000 emails на одну адресу)
- Unicode/homograph attacks
- Case sensitivity issues
- Delivery tracking
- Replay attacks

**Статус:** ✅ Затверджено

---

### 9. ПЛАТІЖНА СИСТЕМА
**Проблема:** Платежі не захищені, можливі фінансові втрати

**Технічні рішення (БЕЗ бізнес-логіки):**
```python
class SecurePaymentService:
    # Обов'язковий зв'язок платіж-документ
    async def create_payment(document_id: int):  # НЕ optional!
        payment = Payment(
            document_id=document_id,
            stripe_payment_intent_id=intent.id
        )
    
    # Idempotency
    payment_intent = stripe.PaymentIntent.create(
        idempotency_key=unique_key  # Захист від дублікатів
    )
    
    # Webhook security
    event = stripe.Webhook.construct_event(
        payload, sig_header, WEBHOOK_SECRET
    )
```

**Компоненти:**
- Обов'язковий document_id (немає платежів без документа)
- Idempotency для захисту від подвійних платежів
- Refund policy (auto при технічних збоях)
- State machine для контролю статусів
- Webhook signature verification
- ~~Price quotes (фіксуємо ціну на 30 хв)~~ (відхилено)
- Timeout handling для Stripe API
- Concurrent webhooks processing
- Cleanup abandoned payments
- 3D Secure support
- Stripe rate limiting

**ЩО НЕ РОБИМО:**
- ❌ Податки (VAT/GST) - бізнес вирішить
- ❌ Pricing strategy - маркетинг вирішить
- ❌ ROI/окупність - не наша задача

**Технічні проблеми які виявили:**
- Webhook можна підробити без signature verification
- Stripe API timeout → не знаємо чи створився платіж
- 2 webhooks одночасно → race condition
- Payment stuck in pending назавжди
- 3D Secure вимагає додаткову дію
- Stripe rate limits (100 req/s)

**Статус:** ✅ Затверджено

---

### 10. ДИНАМІЧНІ ЦІНИ
**Проблема:** Hardcoded ціни, маркетинг не може змінити без розробників

**Рішення:**
```python
class PricingConfiguration(Base):
    __tablename__ = "pricing_config"
    
    price_per_page = Column(Numeric(10, 4))
    currency = Column(String(3), default="EUR")
    discount_percentage = Column(Numeric(5, 2))
    bulk_pricing_json = Column(JSON)  # {"50+": 0.45}
    promo_codes_json = Column(JSON)   # {"STUDENT20": 20}
    
    # Admin може змінити через UI
```

**Компоненти:**
- PricingConfiguration модель в БД
- Admin panel для зміни цін
- Distributed cache в Redis (5 хв TTL)
- ~~Price quotes для фіксації ціни користувача~~ (відхилено)
- Захист від негативних цін (min €0.10)
- Валідація змін з попередженнями
- Rollback при помилках
- A/B testing support

**Edge cases які виявили:**
1. **Race condition:** User бачить €25, admin змінює, user платить €50
2. **Negative price:** Знижка 60% + promo 70% = негативна ціна
3. **Cache inconsistency:** Різні сервери → різні ціни
4. **Promo abuse:** Один код використано 100 разів
5. **Float errors:** 0.1 + 0.2 = 0.30000000000000004
6. **Timezone chaos:** Акція до 23:59 - в якому часовому поясі?

**Рішення edge cases:**
- ~~Price quotes на 30 хв~~ (відхилено)
- Max total discount 95%
- Centralized Redis cache
- Promo limits per IP/email
- Decimal precision (не float!)
- UTC storage для всіх дат

**Статус:** ✅ Затверджено

---

### 11. GDPR COMPLIANCE
**Проблема:** Порушення GDPR = штрафи до €20 млн або 4% обороту

**Рішення:**
```python
class GDPRCompliance:
    # Right to be forgotten
    async def delete_user_data(user_id: int):
        # Анонімізація замість видалення
        user.email = f"deleted_{user_id}@deleted.com"
        user.full_name = "DELETED USER"
        # Видаляємо файли
        await delete_from_storage(documents)
    
    # Data portability
    async def export_user_data(user_id: int):
        return {
            "user": user_data,
            "documents": all_documents,
            "payments": payment_history,
            "activity_log": all_activities
        }
    
    # Consent management
    consents = ["essential", "analytics", "marketing"]
```

**Компоненти:**
- Right to be forgotten (анонімізація даних)
- Data portability (експорт JSON/CSV)
- Consent management (явні згоди)
- Data retention policy (auto-deletion)
- Privacy by design (sanitized logs)
- Audit trail всіх операцій

**Що реалізуємо:**
- Анонімізація замість видалення (для цілісності БД)
- Експорт ВСІХ даних користувача
- Окрема таблиця для згод
- Cronjob для видалення старих даних
- Маскування PII в логах

**Статус:** ✅ Затверджено

---

## 🔴 КРИТИЧНІ SECURITY ФІКСИ (1 день роботи)

### 1️⃣ IDOR PROTECTION (1-2 години)
**Проблема:** Будь-хто може читати/змінювати чужі документи

**Рішення:**
```python
# Helper функція для всіх endpoints
async def check_document_ownership(
    document_id: int,
    user_id: int,
    db: AsyncSession
) -> Document:
    document = await db.get(Document, document_id)
    if not document or document.user_id != user_id:
        raise HTTPException(404, "Document not found")
    return document

# Оновити ВСІ endpoints з document_id
```

**Де виправити:**
- `/documents/{id}` (GET, PUT, DELETE)
- `/documents/{id}/export`
- `/documents/{id}/sections`
- `/payment/{payment_id}`

---

### 2️⃣ JWT SECURITY (30 хвилин)
**Проблема:** Слабкі або default ключі = можна підробити токени

**Рішення:**
```bash
# Генерація нових ключів
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

```python
# Валідація в Settings
@validator("SECRET_KEY", "JWT_SECRET")
def validate_secrets(cls, v, field):
    if not v or len(v) < 32:
        raise ValueError(f"{field.name} must be at least 32 characters")
    
    weak_secrets = ["secret", "password", "12345", "admin", "default"]
    if any(weak in v.lower() for weak in weak_secrets):
        raise ValueError(f"{field.name} is too weak!")
    return v

# JWT expiration
payload["exp"] = datetime.utcnow() + timedelta(hours=1)
```

---

### 3️⃣ FILE MAGIC BYTES (2 години)
**Проблема:** Можна завантажити виконуваний файл як PDF

**Рішення:**
```python
class EnhancedFileValidator:
    FILE_SIGNATURES = {
        'pdf': b'%PDF',
        'docx': b'PK\x03\x04',
        'txt': [b'\xef\xbb\xbf', b'']
    }
    
    FORBIDDEN_SIGNATURES = [
        b'MZ',          # Windows EXE/DLL
        b'\x7fELF',     # Linux executable
        b'#!/',         # Shell script
        b'<?php',       # PHP
        b'<script',     # JavaScript
    ]
    
    async def validate_file_content(self, file: UploadFile, expected_type: str):
        content_start = await file.read(1024)
        await file.seek(0)
        
        # Перевірка на виконувані файли
        for forbidden in self.FORBIDDEN_SIGNATURES:
            if forbidden in content_start:
                raise ValidationError("Forbidden file type")
        
        # Перевірка правильного типу
        if expected_type == 'pdf':
            if not content_start.startswith(self.FILE_SIGNATURES['pdf']):
                raise ValidationError("Invalid PDF file")
```

---

### 4️⃣ SIMPLE BACKUP SCRIPT (1 година)
**Проблема:** Немає backup = втрата всього

**Рішення:**
```bash
#!/bin/bash
# scripts/backup.sh

BACKUP_DIR="/backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# PostgreSQL backup
PGPASSWORD=$DB_PASSWORD pg_dump \
    -h localhost -U postgres -d tesigo \
    --format=custom --compress=9 \
    --file=$BACKUP_DIR/db/postgres_$TIMESTAMP.dump

# MinIO backup
tar -czf $BACKUP_DIR/minio/minio_$TIMESTAMP.tar.gz /minio/data/

# Видалення старих (7 днів)
find $BACKUP_DIR -type f -mtime +7 -delete

# Crontab: 0 2 * * * /scripts/backup.sh
```

---

## 🚨 КРИТИЧНІ TODO (Блокери)

### НЕГАЙНО (перед будь-яким запуском):
1. **Інтегрувати BackgroundJobService** - є але не використовується!
2. **Webhook signature verification** - інакше хтось підробить платіж
3. ~~**Price quotes system** - інакше користувач заплатить не ту ціну~~ (відхилено)
4. **GDPR consent при реєстрації** - інакше штрафи

### Перед Production:
1. Multiple OpenAI API keys (інакше rate limits)
2. Redis cluster setup (для масштабування)
3. Data retention cronjobs (GDPR вимога)
4. Monitoring & alerting (щоб знати про проблеми)
5. Connection pooling налаштування
6. Memory streaming implementation

### Nice to have:
1. A/B testing для цін
2. Fraud detection
3. Advanced analytics
4. Geographic distribution

### КРИТИЧНІ SECURITY ФІКСИ (найвищий пріоритет):
1. **IDOR Protection** - додати ownership checks (1 день)
   ```python
   # На КОЖНОМУ endpoint з document_id
   if document.user_id != current_user.id:
       raise ForbiddenError()
   ```

2. **JWT Hardening** - сильні ключі (1 година)
   ```python
   SECRET_KEY = secrets.token_urlsafe(32)  # В .env
   JWT_EXPIRATION = 3600  # 1 година
   ```

3. **File Magic Bytes** - перевірка типу файлу (2 години)
   ```python
   PDF_MAGIC = b"%PDF"
   DOCX_MAGIC = b"PK\x03\x04"
   if not content.startswith(expected_magic):
       raise ValidationError("Invalid file type")
   ```
   
4. **File Size** - БЕЗ обмежень (можуть бути 100+ MB файли)
   ```python
   # НЕ обмежуємо розмір!
   # MAX_FILE_SIZE = None  # Користувачі працюють з великими документами
   # Але потрібно:
   - Streaming upload для великих файлів
   - Progress tracking
   - Chunked processing
   ```

---

### 12. SECURITY (XSS, SQL Injection, Path Traversal)
**Проблема:** Критичні вразливості безпеки в системі

**XSS вразливості:**
- Недостатня санітизація HTML/JavaScript
- Regex видаляє теги але не екранує JS
- SVG/IMG з onload/onerror виконають код

**SQL Injection:**
- JSON поля не валідуються
- Raw queries з конкатенацією
- Dynamic queries без whitelist

**Path Traversal:**
- Шляхи файлів не валідуються
- Можливість виходу за межі upload directory
- ../../etc/passwd атаки

**Рішення:**

```python
# XSS Protection
import bleach
ALLOWED_TAGS = ['p', 'br', 'strong', 'em', 'h1', 'h2', 'h3']
cleaned = bleach.clean(content, tags=ALLOWED_TAGS, strip=True)

# SQL Injection Protection
query = text("SELECT * FROM documents WHERE outline @> :search_json")
result = await db.execute(query, {"search_json": json_str})  # Параметризовано!

# Path Traversal Protection
requested_path = Path(file_path).resolve()
requested_path.relative_to(BASE_DIR)  # Перевірка меж
```

**Компоненти:**
- Bleach для санітизації HTML
- Параметризовані запити (НІКОЛИ f-strings!)
- JSON schema validation
- Secure filename generation з UUID
- Path validation relative to base directory
- Security headers (CSP, HSTS, X-Frame-Options)
- Input validation на всіх рівнях

**Edge cases які виявили:**
- JavaScript в data: URLs
- SVG з embedded scripts
- Unicode bypass attempts
- Double encoding attacks
- Null byte injection
- Directory traversal через ZIP uploads

**Статус:** ✅ Затверджено

---

### 13. ДОДАТКОВІ SECURITY VULNERABILITIES
**Проблема:** Критичні вразливості які не були в початковому аналізі

**IDOR (Insecure Direct Object Reference):**
```python
# ПРОБЛЕМА: Доступ до чужих документів
@router.get("/documents/{document_id}")
async def get_document(document_id: int):
    # НЕ перевіряємо ownership!
    return await db.get(Document, document_id)
```

**JWT Token vulnerabilities:**
- Algorithm "none" attack
- Weak secret keys
- No expiration
- Sensitive data в токені

**File Upload vulnerabilities:**
- ✅ ЧАСТКОВО ВИРІШЕНО: є валідація MIME types
- ✅ ЧАСТКОВО ВИРІШЕНО: є перевірка розширень
- ❌ НЕМАЄ: антивірусного сканування
- ❌ НЕМАЄ: перевірки magic bytes
- ❌ НЕМАЄ: захисту від ZIP bombs
- ❌ НЕМАЄ: санітизації SVG

**Rate Limiting bypass:**
- Зміна IP через проксі
- Case variation в endpoints
- Distributed attacks

**Password Reset Poisoning:**
- Host header injection
- Open redirect vulnerabilities

**Timing Attacks:**
- Email enumeration через різницю в часі
- Token comparison timing

**SSRF (Server-Side Request Forgery):**
- При імпорті документів з URL
- Доступ до internal services
- AWS metadata endpoints

**XXE (XML External Entity):**
- При парсингу DOCX файлів
- File disclosure attacks

**Secrets in Source Control:**
- API keys в git history
- Secrets в Docker layers
- Sensitive data в логах

**Рішення:**

```python
# IDOR Protection
async def check_ownership(user_id: int, document_id: int):
    doc = await db.get(Document, document_id)
    if doc.user_id != user_id:
        raise ForbiddenError()

# JWT Security
JWT_CONFIG = {
    "algorithm": "HS256",  # НЕ none!
    "secret_key": secrets.token_urlsafe(32),
    "expiration": timedelta(hours=1)
}

# File Upload Security (доповнення до існуючого)
FILE_SECURITY = {
    "check_magic_bytes": True,
    "max_size": 10 * 1024 * 1024,  # 10MB
    "scan_zip_bombs": True,
    "sanitize_svg": True,
    # Антивірус опціонально (ClamAV)
}

# Constant Time Operations
def constant_time_compare(a: str, b: str) -> bool:
    return hmac.compare_digest(a, b)

# SSRF Protection
def validate_url(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.hostname in ["localhost", "127.0.0.1"]:
        return False
    # Check private IPs
    ip = socket.gethostbyname(parsed.hostname)
    if ipaddress.ip_address(ip).is_private:
        return False
    return True
```

**Компоненти:**
- Ownership checks на всіх endpoints
- Strong JWT configuration
- Enhanced file validation (magic bytes, size, structure)
- Constant time string comparisons
- URL validation для SSRF
- XXE protection (disable external entities)
- Secrets management (vault/env)
- Git history cleanup

**Що вже є в системі:**
- ✅ CustomRequirementsService з валідацією MIME types
- ✅ Перевірка розширень файлів
- ✅ Rate limiting (але потребує покращення)
- ✅ JWT authentication (але потребує hardening)
- ⚠️ Safety для Python dependencies (не в CI)

**Що критично відсутнє:**
- ❌ IDOR protection
- ❌ Антивірусне сканування файлів
- ❌ Magic bytes validation
- ❌ SSRF protection
- ❌ XXE protection
- ❌ Constant time operations

**Статус:** ✅ Затверджено

---

### 14. ОБРОБКА ВЕЛИКИХ ФАЙЛІВ (100+ MB)
**Проблема:** Користувачі працюють з великими документами (100+ MB)

**Виклики:**
- Memory overflow при завантаженні
- Timeout при upload
- Повільна обробка
- Втрата прогресу при обриві

**Рішення:**

```python
class LargeFileHandler:
    """
    Обробка великих файлів без обмежень розміру
    """
    
    # БЕЗ обмеження розміру!
    MAX_FILE_SIZE = None  # Користувачі можуть мати 100+ MB
    CHUNK_SIZE = 1024 * 1024  # 1MB chunks для streaming
    
    async def upload_large_file_streaming(
        self,
        file: UploadFile,
        document_id: int
    ):
        """
        Streaming upload для великих файлів
        """
        
        # 1. Створюємо temporary file
        temp_path = f"/tmp/upload_{document_id}_{uuid.uuid4()}"
        bytes_written = 0
        
        try:
            # 2. Streaming write по chunks
            async with aiofiles.open(temp_path, 'wb') as f:
                while chunk := await file.read(self.CHUNK_SIZE):
                    await f.write(chunk)
                    bytes_written += len(chunk)
                    
                    # 3. Progress tracking
                    await self.update_upload_progress(
                        document_id,
                        bytes_written,
                        file.size if file.size else None
                    )
                    
                    # 4. Перевірка перших байтів (magic bytes)
                    if bytes_written == self.CHUNK_SIZE:
                        await self.validate_file_start(temp_path)
            
            # 5. Обробка після завантаження
            await self.process_large_file(temp_path, document_id)
            
        finally:
            # 6. Cleanup
            if os.path.exists(temp_path):
                os.remove(temp_path)
    
    async def process_large_file_chunked(
        self,
        file_path: str,
        document_id: int
    ):
        """
        Обробка великого файлу по частинах
        """
        
        file_size = os.path.getsize(file_path)
        
        # Для PDF - streaming parser
        if file_path.endswith('.pdf'):
            async for page in self.stream_pdf_pages(file_path):
                text = await self.extract_text_from_page(page)
                await self.save_extracted_text(document_id, text)
                
        # Для DOCX - по параграфах
        elif file_path.endswith('.docx'):
            async for paragraph in self.stream_docx_paragraphs(file_path):
                await self.save_extracted_text(document_id, paragraph)
    
    async def stream_pdf_pages(self, file_path: str):
        """
        Streaming читання PDF по сторінках
        """
        
        # PyPDF2 підтримує streaming
        reader = PdfReader(file_path)
        
        for page_num in range(len(reader.pages)):
            yield reader.pages[page_num]
            
            # Звільняємо пам'ять після кожної сторінки
            if page_num % 10 == 0:
                gc.collect()
    
    async def update_upload_progress(
        self,
        document_id: int,
        bytes_uploaded: int,
        total_bytes: int = None
    ):
        """
        WebSocket оновлення прогресу
        """
        
        progress = {
            "document_id": document_id,
            "bytes_uploaded": bytes_uploaded,
            "total_bytes": total_bytes,
            "percentage": (bytes_uploaded / total_bytes * 100) if total_bytes else None
        }
        
        # Відправка через WebSocket
        await websocket_manager.send_progress(document_id, progress)
```

**Додаткові оптимізації для великих файлів:**

```python
# 1. Resumable uploads (якщо обірвалось)
class ResumableUpload:
    async def resume_upload(self, upload_id: str, chunk: bytes, offset: int):
        # Продовжуємо з місця обриву
        pass

# 2. MinIO для зберігання (не в БД!)
async def store_in_minio(file_path: str):
    # Великі файли в object storage
    pass

# 3. Background processing
async def process_in_background(file_path: str):
    # Обробка в background job
    background_tasks.add_task(process_large_file, file_path)

# 4. CDN для download
def get_download_url(document_id: int):
    # Пряме посилання з CDN, не через API
    return f"https://cdn.tesigo.com/documents/{document_id}"
```

**Важливі моменти:**
- ✅ БЕЗ обмеження розміру (користувачі працюють з великими документами)
- ✅ Streaming upload/download
- ✅ Progress tracking через WebSocket
- ✅ Chunked processing (не все в RAM)
- ✅ Resumable uploads для надійності
- ✅ Object storage (MinIO) для великих файлів

**Статус:** ✅ Затверджено

---

### 15. DEBUGGING & MONITORING
**Проблема:** Неможливо відстежити проблеми в production

**Що відсутнє:**
- Distributed tracing
- Correlation ID між сервісами
- Performance profiling
- Детальні метрики
- Real-time alerting

**Рішення:**

```python
# 1. Correlation ID для трасування
class CorrelationMiddleware:
    async def __call__(self, request, call_next):
        correlation_id = request.headers.get('X-Correlation-ID') or str(uuid.uuid4())
        correlation_id_var.set(correlation_id)
        
        with logger.contextualize(correlation_id=correlation_id):
            response = await call_next(request)
        
        response.headers['X-Correlation-ID'] = correlation_id
        return response

# 2. Performance monitoring
@measure_time("operation_name")
async def slow_operation():
    # Автоматично логує якщо > 1 сек
    pass

# 3. Structured logging
logger.add(
    "logs/app_{time}.log",
    rotation="100 MB",
    serialize=True,  # JSON формат
    backtrace=True,
    diagnose=True
)

# 4. Health checks
async def detailed_health_check():
    return {
        "database": check_db(),
        "redis": check_redis(),
        "storage": check_minio(),
        "openai": check_api(),
        "memory": check_memory(),
        "disk": check_disk()
    }

# 5. Real-time alerting
ALERT_RULES = {
    "high_error_rate": lambda m: m["error_rate"] > 0.05,
    "slow_response": lambda m: m["p95_latency"] > 2000,
    "memory_high": lambda m: m["memory_percent"] > 85
}
```

**Компоненти:**
- Correlation ID для всіх запитів
- Structured JSON logging
- Performance metrics (Prometheus)
- Detailed health checks
- Alert rules з Telegram/Email
- Debug endpoints для development

**Додаткові проблеми які виявили:**
- Log rotation при великих файлах
- Sensitive data в логах (потрібна санітизація)
- Метрики можуть сповільнити систему
- Занадто багато алертів = alert fatigue

**Статус:** ✅ Затверджено

---

### 16. BACKUP & DISASTER RECOVERY
**Проблема:** Втрата БД = втрата ВСЬОГО, немає backup стратегії

**Критичні ризики:**
- Випадкове видалення (DELETE без WHERE)
- Ransomware атака
- Hardware failure
- Corruption даних
- Human error

**Рішення - 3-2-1 Rule:**
```python
# 3 копії, 2 різні media, 1 offsite

class BackupStrategy:
    SCHEDULE = {
        "full": "0 2 * * 0",      # Щонеділі о 2:00
        "incremental": "0 2 * * 1-6",  # Щодня
        "wal": "*/15 * * * *"     # WAL кожні 15 хв
    }
    
    async def automated_backup(self):
        # 1. PostgreSQL backup
        pg_dump --format=custom --compress=9
        
        # 2. Encrypt
        gpg --encrypt --recipient backup@tesigo.com
        
        # 3. Upload to 3 locations
        await upload_to_s3(backup)      # AWS S3
        await upload_to_gcs(backup)     # Google Cloud
        await upload_to_nas(backup)     # Local NAS
        
        # 4. Verify
        await verify_backup_integrity()
        
        # 5. Cleanup old (30 days retention)
        await cleanup_old_backups()

# Point-in-time recovery
async def restore_to_point(target_time: datetime):
    base_backup = find_nearest_backup(target_time)
    restore_backup(base_backup)
    apply_wal_until(target_time)  # Max 15 min data loss
```

**Backup компоненти:**
- **PostgreSQL**: pg_dump + WAL streaming
- **MinIO**: mc mirror + tar.gz archives
- **Redis**: BGSAVE snapshots (якщо критичні дані)
- **Encryption**: GPG для всіх backups
- **Compression**: gzip level 9

**Disaster Recovery Plan:**
```python
class DisasterRecovery:
    # Recovery Time Objective (час відновлення)
    RTO = {
        "critical": "1 hour",   # Auth, payments
        "high": "4 hours",      # Document generation
        "medium": "12 hours"    # Other features
    }
    
    # Recovery Point Objective (макс втрата даних)
    RPO = {
        "database": "15 minutes",
        "files": "1 hour",
        "cache": "24 hours"
    }
    
    async def execute_recovery(disaster_type: str):
        # 1. Assess damage
        damage = assess_damage()
        
        # 2. Notify team (Telegram, Email)
        notify_team(damage)
        
        # 3. Recovery by priority
        restore_database()      # Priority 1
        restore_auth()          # Priority 2
        restore_storage()       # Priority 3
        rebuild_cache()         # Priority 4
        
        # 4. Verify integrity
        verify_recovery()
```

**Testing & Monitoring:**
```python
# Monthly restore test
async def monthly_restore_test():
    random_backup = select_random_backup()
    restore_to_staging(random_backup)
    verify_data_integrity()
    alert_if_failed()

# Continuous monitoring
ALERTS = {
    "backup_missed": "No backup in 25 hours",
    "backup_size_anomaly": "Size differs >20%",
    "restore_test_failed": "Monthly test failed"
}
```

**Storage locations:**
- **Primary**: Local NAS (fast restore)
- **Secondary**: AWS S3 (reliable)
- **Tertiary**: Google Cloud Storage (geographic redundancy)
- **Archive**: AWS Glacier (long-term, cheap)

**Важливі деталі:**
- ✅ Всі backups зашифровані (GPG)
- ✅ Retention: 30 днів daily, 12 тижнів weekly, 12 місяців monthly
- ✅ Автоматична верифікація після backup
- ✅ Щомісячні restore tests
- ✅ Monitoring з алертами

**Що НЕ бекапимо:**
- Temporary files
- Cache (можна rebuild)
- Logs старші 30 днів
- Generated thumbnails

**Статус:** ✅ Затверджено

---

### 17. HARDCODED SECRETS
**Проблема:** Secrets в коді/конфігурації

**Рішення:**
- Environment validation (strong keys, no defaults)
- Secrets rotation
- Secure storage (HashiCorp Vault/AWS Secrets Manager)
- Git secrets scanning (pre-commit hooks)
- Docker secrets

**Статус:** ✅ Затверджено

---

## 📊 СТАТУС РЕАЛІЗАЦІЇ

| Компонент | Статус | Критичність | Примітки |
|-----------|--------|-------------|----------|
| BackgroundJobService | ✅ Є, ❌ Не інтегровано | 🔴 CRITICAL | Блокер! |
| Payment Model | ✅ Реалізовано | 🔴 CRITICAL | |
| Payment Service | ✅ Реалізовано | 🔴 CRITICAL | |
| Webhook Security | ❌ Відсутнє | 🔴 CRITICAL | Блокер! |
| Price Quotes | ❌ Відсутнє | 🔴 CRITICAL | Блокер! |
| Email Verification | ⚠️ Частково | 🟡 HIGH | Немає double opt-in |
| GDPR Compliance | ❌ Відсутнє | 🔴 CRITICAL | Legal блокер! |
| Redis Cache | ✅ Є | 🟡 HIGH | |
| Multiple API Keys | ❌ Відсутнє | 🟡 HIGH | Для масштабування |
| Monitoring | ⚠️ Частково | 🟡 HIGH | Тільки логи |

---

### 18. ВТРАТА ПРОГРЕСУ (UX)
**Проблема:** Користувач втрачає всю роботу при refresh/crash

**Рішення:**
- LocalStorage auto-save кожні 30 секунд
- Backend drafts з версіонуванням
- Recovery після крашу браузера
- Попередження перед закриттям вкладки
- Version history (major/minor versions)

**Статус:** ✅ Затверджено

---

### 19. НЕПРОЗОРА ГЕНЕРАЦІЯ (UX)
**Проблема:** Користувач не бачить прогрес генерації

**Рішення:**
- WebSocket real-time прогрес
- Детальні етапи генерації з вагою
- ETA розрахунок і відображення
- ❌ НЕ РОБИМО: Live preview (непотрібно)
- ❌ НЕ РОБИМО: Скасування генерації (непотрібно)

**Статус:** ✅ Затверджено (спрощена версія)

---

### 20. VENDOR LOCK-IN
**Проблема:** Повна залежність від OpenAI/Anthropic

**Рішення:**
- ⏸️ ВІДКЛАДЕНО: Будемо вирішувати якщо/коли виникне проблема
- ⏸️ ВІДКЛАДЕНО: Альтернативні провайдери - в майбутніх апдейтах
- ❌ НЕ РОБИМО: Self-hosted моделі (дорого, складно)
- ❌ НЕ РОБИМО: Fine-tuning (поки немає даних)

**Домовленість:** Фокусуємося на OpenAI/Anthropic згідно проектної документації

**Статус:** ⏸️ Відкладено до майбутніх версій

---

## 📝 ІСТОРІЯ ЗМІН

- **2025-11-02:** Початкова версія документа
- **Session 1:** Обговорено та затверджено 17 критичних рішень
- **Session 2:** Додано 4 критичні security фікси (IDOR, JWT, Magic Bytes, Backup)
- **Session 3:** Додано 3 UX рішення (Auto-save, Progress, Multi-provider)
- **Важливо:** Всі рішення технічні, без бізнес-метрик

---

**Документ підтримується та оновлюється при кожному новому рішенні**
