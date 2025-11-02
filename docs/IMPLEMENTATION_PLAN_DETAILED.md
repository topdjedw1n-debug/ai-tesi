# 🚀 ДЕТАЛЬНИЙ ПЛАН ІМПЛЕМЕНТАЦІЇ - TesiGo v2.3

**Дата створення:** 2025-11-02  
**Версія:** 1.0  
**Тривалість:** 3-4 дні до MVP, 1-2 тижні до Production

---

## 📋 ФАЗА 1: КРИТИЧНІ SECURITY ФІКСИ (День 1)

### ✅ Task 1.1: IDOR Protection (2 години)

#### Крок 1: Створити helper функцію
**Файл:** `apps/api/app/api/v1/endpoints/documents.py`

**Промпт для розробки:**
```
Додай helper функцію check_document_ownership в файл documents.py:
1. Функція має приймати document_id, user_id, та db session
2. Перевірити чи документ існує
3. Перевірити чи документ належить користувачу
4. Якщо ні - повертати 404 (не 403, щоб не розкривати існування)
5. Використати цю функцію у всіх endpoints: GET, PUT, DELETE, /export

Приклад:
async def check_document_ownership(
    document_id: int,
    user_id: int, 
    db: AsyncSession
) -> Document:
    document = await db.get(Document, document_id)
    if not document or document.user_id != user_id:
        raise HTTPException(404, "Document not found")
    return document
```

**Промпт для QA:**
```
Протестуй IDOR protection:
1. Створи 2 користувачів (user1, user2)
2. Створи документ як user1
3. Спробуй отримати документ як user2 - має бути 404
4. Спробуй оновити документ як user2 - має бути 404
5. Спробуй видалити документ як user2 - має бути 404
6. Перевір що user1 все ще має доступ до свого документа

Напиши integration тест для цього в test_idor_protection.py
```

#### Крок 2: Оновити payment endpoints
**Файл:** `apps/api/app/api/v1/endpoints/payment.py`

**Промпт для розробки:**
```
Додай ownership check для payment endpoints:
1. В GET /payment/{payment_id} перевір що payment.user_id == current_user.id
2. В GET /payment/history фільтруй тільки платежі поточного користувача
3. Використовуй той самий патерн - 404 замість 403
```

---

### ✅ Task 1.2: JWT Security (30 хвилин)

#### Крок 1: Генерація сильних ключів

**Промпт для розробки:**
```
1. Створи скрипт scripts/generate_secrets.py:
   - Генеруй SECRET_KEY (32+ символів)
   - Генеруй JWT_SECRET (32+ символів, інший ніж SECRET_KEY)
   - Виведи в консоль з інструкціями для .env

2. Оновити apps/api/app/core/config.py:
   - Додай валідатор для SECRET_KEY та JWT_SECRET
   - Мінімум 32 символи
   - Не можуть містити слова: secret, password, test, admin
   - JWT_SECRET має відрізнятися від SECRET_KEY

3. В auth_service.py:
   - Додай expiration до JWT payload (1 година для access, 7 днів для refresh)
   - Додай iss (issuer) та aud (audience) claims
```

**Промпт для QA:**
```
Протестуй JWT security:
1. Спробуй запустити з коротким SECRET_KEY (< 32 chars) - має бути помилка
2. Спробуй з SECRET_KEY="secretpassword123" - має бути відхилено
3. Спробуй з однаковими SECRET_KEY та JWT_SECRET - має бути помилка
4. Перевір що токен експайриться через 1 годину
5. Перевір що refresh токен працює 7 днів
```

---

### ✅ Task 1.3: File Magic Bytes Validation (2 години)

#### Крок 1: Створити валідатор

**Файл:** `apps/api/app/services/file_validator.py`

**Промпт для розробки:**
```
Створи новий файл file_validator.py з класом FileValidator:

1. Визнач magic bytes для різних типів:
   PDF_MAGIC = b'%PDF'
   DOCX_MAGIC = b'PK\x03\x04'  # ZIP signature
   TXT_MAGIC = [b'\xef\xbb\xbf', b'']  # UTF-8 BOM або без

2. Визнач заборонені signatures:
   FORBIDDEN = [
     b'MZ',       # Windows EXE
     b'\x7fELF',  # Linux executable
     b'#!/',      # Shell script
     b'<?php',    # PHP
   ]

3. Метод validate_file_content(file: UploadFile, expected_type: str):
   - Прочитай перші 1024 байти
   - Перевір на заборонені signatures
   - Перевір що magic bytes відповідають expected_type
   - Для DOCX додатково перевір ZIP структуру

4. Метод check_zip_bomb(file: UploadFile):
   - Для ZIP/DOCX перевір compression ratio
   - Якщо ratio > 100 - відхили як potential zip bomb

5. Інтегруй в CustomRequirementsService.extract_text()
```

**Промпт для QA:**
```
Створи тести для file validation:

1. test_valid_pdf() - завантаж справжній PDF
2. test_valid_docx() - завантаж справжній DOCX
3. test_fake_pdf() - створи файл з .pdf розширенням але текстовим вмістом
4. test_executable_upload() - спробуй завантажити .exe (має бути відхилено)
5. test_script_upload() - спробуй завантажити .sh скрипт
6. test_zip_bomb() - створи файл з високим compression ratio

Всі тести в test_file_security.py
```

---

### ✅ Task 1.4: Basic Backup Script (1 година)

#### Крок 1: Створити backup скрипт

**Файл:** `scripts/backup.sh`

**Промпт для розробки:**
```
Створи backup.sh скрипт:

1. Конфігурація:
   BACKUP_DIR="/backups"
   TIMESTAMP=$(date +%Y%m%d_%H%M%S)
   
2. PostgreSQL backup:
   pg_dump з параметрами:
   - --format=custom
   - --compress=9
   - Збереження в $BACKUP_DIR/db/postgres_$TIMESTAMP.dump

3. MinIO backup:
   tar -czf для /minio/data/documents/

4. Видалення старих (> 7 днів):
   find $BACKUP_DIR -type f -mtime +7 -delete

5. Створи scripts/restore.sh:
   - Приймає шлях до backup файлу
   - Питає підтвердження
   - Відновлює через pg_restore

6. Додай до crontab інструкцію:
   0 2 * * * /scripts/backup.sh
```

**Промпт для QA:**
```
Протестуй backup/restore:

1. Створи тестові дані (користувач, документ, платіж)
2. Запусти backup.sh
3. Перевір що файли створені в /backups
4. Видали тестові дані з БД
5. Запусти restore.sh з backup файлом
6. Перевір що дані відновлені
7. Перевір що старі backups видаляються через 7 днів
```

---

## 📋 ФАЗА 2: ФУНКЦІОНАЛЬНІ ФІКСИ (День 2-3)

### ✅ Task 2.1: Інтеграція BackgroundJobService з WebSocket (5 годин)

#### Крок 1: Створити WebSocket manager

**Файл:** `apps/api/app/services/websocket_manager.py`

**Промпт для розробки:**
```
Створи WebSocket manager для real-time прогресу:

1. WebSocket Manager:
   from fastapi import WebSocket
   from typing import Dict, List
   from contextvars import ContextVar
   
   # Ізоляція контекстів через ContextVar
   user_context: ContextVar[dict] = ContextVar('user_context', default={})
   
   class ConnectionManager:
     def __init__(self):
       self.active_connections: Dict[int, List[WebSocket]] = {}
     
     async def connect(self, websocket: WebSocket, user_id: int):
       await websocket.accept()
       if user_id not in self.active_connections:
         self.active_connections[user_id] = []
       self.active_connections[user_id].append(websocket)
       
       # Ізольований контекст для користувача
       user_context.set({"user_id": user_id, "session_id": str(uuid.uuid4())})
     
     async def send_progress(self, user_id: int, message: dict):
       if user_id in self.active_connections:
         for connection in self.active_connections[user_id]:
           await connection.send_json(message)
   
   manager = ConnectionManager()

2. WebSocket endpoint:
   @router.websocket("/ws/generation/{document_id}")
   async def generation_progress(
     websocket: WebSocket,
     document_id: int,
     current_user: User = Depends(get_current_user_ws)
   ):
     await manager.connect(websocket, current_user.id)
     try:
       while True:
         # Keep connection alive
         await websocket.receive_text()
     except WebSocketDisconnect:
       manager.disconnect(websocket, current_user.id)
```

#### Крок 2: Додати Smart Queue з пріоритетами

**Файл:** `apps/api/app/services/job_queue.py`

**Промпт для розробки:**
```
Створи Smart Queue для пріоритизації:

1. Queue Manager:
   from queue import PriorityQueue
   from dataclasses import dataclass, field
   
   @dataclass(order=True)
   class JobItem:
     priority: int
     job_id: str = field(compare=False)
     document_id: int = field(compare=False)
     pages: int = field(compare=False)
     created_at: datetime = field(compare=False)
   
   class SmartQueue:
     def __init__(self):
       self.queue = PriorityQueue()
       self.processing = set()
       
     def add_job(self, job: AIGenerationJob):
       # Пріоритет: менші документи першими
       priority = job.target_pages  # 10 pages = priority 10
       if job.user.is_premium:
         priority -= 1000  # Premium users first
       
       item = JobItem(
         priority=priority,
         job_id=job.id,
         document_id=job.document_id,
         pages=job.target_pages
       )
       self.queue.put(item)
     
     async def get_next_job(self) -> JobItem:
       if not self.queue.empty():
         return self.queue.get()
       return None

2. Auto-scaling workers:
   class WorkerPool:
     MIN_WORKERS = 2
     MAX_WORKERS = 10
     
     def __init__(self):
       self.workers = []
       self.scale_to(self.MIN_WORKERS)
     
     def scale_to(self, count: int):
       count = max(self.MIN_WORKERS, min(count, self.MAX_WORKERS))
       
       # Add workers
       while len(self.workers) < count:
         worker = BackgroundWorker()
         self.workers.append(worker)
         asyncio.create_task(worker.run())
       
       # Remove workers
       while len(self.workers) > count:
         worker = self.workers.pop()
         await worker.stop()
     
     async def auto_scale(self):
       # Scale based on queue size
       queue_size = smart_queue.queue.qsize()
       
       if queue_size > 20:
         self.scale_to(10)  # Max workers
       elif queue_size > 10:
         self.scale_to(5)   # Medium load
       else:
         self.scale_to(2)   # Min workers
```

#### Крок 3: Створити endpoint для async генерації

**Файл:** `apps/api/app/api/v1/endpoints/generate.py`

**Промпт для розробки:**
```
Додай новий endpoint POST /generate/document-async:

1. Прийми параметри:
   - title: str
   - pages: int
   - model: str
   - requirements: Optional[str]

2. Створи job в БД:
   job = AIGenerationJob(
     document_id=document.id,
     status="queued",
     progress=0
   )

3. Запусти background task:
   background_tasks.add_task(
     background_job_service.generate_document_async,
     document.id, job.id
   )

4. Поверни:
   {
     "job_id": job.id,
     "status": "queued",
     "check_url": f"/api/v1/jobs/{job.id}/status"
   }

5. Додай endpoint GET /jobs/{job_id}/status:
   - Повертай поточний статус та прогрес
   - Якщо completed - додай document_id
```

**Промпт для QA:**
```
Тест async генерації:

1. Створи запит на генерацію через /generate/document-async
2. Отримай job_id
3. Перевіряй статус кожні 2 секунди через /jobs/{job_id}/status
4. Переконайся що progress змінюється (0 -> 25 -> 50 -> 75 -> 100)
5. Коли status="completed", перевір що document_id повернувся
6. Отримай документ через GET /documents/{document_id}
7. Перевір що контент згенерований

Напиши async тест з asyncio.sleep між перевірками
```

---

### ✅ Task 2.2: Webhook Signature Verification (2 години)

**Файл:** `apps/api/app/api/v1/endpoints/payment.py`

**Промпт для розробки:**
```
Оновити POST /payment/webhook:

1. Отримай signature з headers:
   sig_header = request.headers.get('Stripe-Signature')

2. Верифікуй signature:
   try:
     event = stripe.Webhook.construct_event(
       payload=await request.body(),
       sig_header=sig_header,
       secret=settings.STRIPE_WEBHOOK_SECRET
     )
   except stripe.error.SignatureVerificationError:
     raise HTTPException(400, "Invalid signature")

3. Обробляй тільки верифіковані events:
   if event['type'] == 'payment_intent.succeeded':
     # Оновити статус платежу
   elif event['type'] == 'payment_intent.failed':
     # Обробити невдалий платіж

4. Додай idempotency:
   - Збережи event_id в БД
   - Якщо event вже оброблений - return 200 без повторної обробки
```

**Промпт для QA:**
```
Тест webhook security:

1. Спробуй POST на /payment/webhook без signature - має бути 400
2. Спробуй з невірною signature - має бути 400
3. Створи валідний webhook з правильною signature
4. Відправ той самий webhook двічі - має обробитися тільки раз
5. Перевір що платіж оновлюється тільки для верифікованих webhooks
```

---

### ✅ Task 2.3: Retry Механізми з Circuit Breaker (3 години)

**Файл:** `apps/api/app/services/ai_service.py`

**Промпт для розробки:**
```
Додай retry логіку з Circuit Breaker в AIService:

1. Створи Circuit Breaker:
   from enum import Enum
   from datetime import datetime, timedelta
   
   class CircuitState(Enum):
     CLOSED = "closed"  # Normal operation
     OPEN = "open"      # Failing, reject requests
     HALF_OPEN = "half_open"  # Testing recovery
   
   class CircuitBreaker:
     def __init__(self, failure_threshold=5, recovery_timeout=60):
       self.failure_threshold = failure_threshold
       self.recovery_timeout = recovery_timeout
       self.failure_count = 0
       self.last_failure_time = None
       self.state = CircuitState.CLOSED
     
     def call(self, func, *args, **kwargs):
       if self.state == CircuitState.OPEN:
         if self._should_attempt_reset():
           self.state = CircuitState.HALF_OPEN
         else:
           raise Exception("Circuit breaker is OPEN")
       
       try:
         result = func(*args, **kwargs)
         self._on_success()
         return result
       except Exception as e:
         self._on_failure()
         raise e
     
     def _on_success(self):
       self.failure_count = 0
       self.state = CircuitState.CLOSED
     
     def _on_failure(self):
       self.failure_count += 1
       self.last_failure_time = datetime.now()
       if self.failure_count >= self.failure_threshold:
         self.state = CircuitState.OPEN
     
     def _should_attempt_reset(self):
       return (datetime.now() - self.last_failure_time).seconds >= self.recovery_timeout

2. Створи RetryStrategy з Circuit Breaker:
   class RetryStrategy:
     delays = [2, 4, 8, 16, 32]  # exponential backoff
     max_retries = 5
     circuit_breaker = CircuitBreaker()
     
     fallback_models = {
       "gpt-4": ["gpt-4-turbo", "gpt-3.5-turbo"],
       "claude-3.5-sonnet": ["claude-3-opus", "gpt-4"]
     }

2. Декоратор @with_retry:
   - Лови RateLimitError, APIError
   - Чекай згідно delays[attempt]
   - Після 3 невдач - спробуй fallback модель
   - Логуй кожну спробу

3. Оновити generate_content():
   @with_retry
   async def generate_content(self, prompt, model):
     try:
       response = await openai_client.chat.completions.create(...)
     except RateLimitError as e:
       logger.warning(f"Rate limit hit: {e}")
       raise  # Декоратор обробить
     except Exception as e:
       logger.error(f"Unexpected error: {e}")
       raise

4. Додай детальний checkpoint saving:
   class CheckpointManager:
     CHECKPOINT_INTERVAL = 300  # 5 minutes
     
     async def save_checkpoint(self, job_id: str, data: dict):
       checkpoint = {
         "job_id": job_id,
         "document_id": data["document_id"],
         "progress": data["progress"],
         "generated_sections": data["generated_sections"],
         "current_section": data["current_section"],
         "tokens_used": data["tokens_used"],
         "timestamp": datetime.now().isoformat()
       }
       
       # Зберігаємо в Redis для швидкого доступу
       await redis_client.setex(
         f"checkpoint:{job_id}",
         3600,  # TTL 1 hour
         json.dumps(checkpoint)
       )
       
       # Backup в БД
       await db.execute(
         "INSERT INTO checkpoints (job_id, data) VALUES ($1, $2) "
         "ON CONFLICT (job_id) DO UPDATE SET data = $2",
         job_id, json.dumps(checkpoint)
       )
     
     async def load_checkpoint(self, job_id: str):
       # Спробуй Redis першим
       data = await redis_client.get(f"checkpoint:{job_id}")
       if data:
         return json.loads(data)
       
       # Fallback на БД
       result = await db.fetchone(
         "SELECT data FROM checkpoints WHERE job_id = $1",
         job_id
       )
       return json.loads(result["data"]) if result else None
     
     async def auto_checkpoint(self, job_id: str):
       while job_is_running:
         await asyncio.sleep(self.CHECKPOINT_INTERVAL)
         await self.save_checkpoint(job_id, current_state)
```

**Промпт для QA:**
```
Тест retry механізмів:

1. Mock OpenAI API щоб повертав RateLimitError перші 2 рази
2. Перевір що генерація успішна на 3-й раз
3. Перевір що delays правильні (2, 4, 8 секунд)
4. Mock повний failure для gpt-4
5. Перевір що fallback на gpt-3.5-turbo працює
6. Симулюй crash після 50% генерації
7. Перевір що checkpoint зберігся і генерація продовжується

Використовуй pytest-mock для мокування API
```

---

### ✅ Task 2.4: Simple Token Tracking (1 година)

**Файл:** `apps/api/app/services/ai_service.py`

**Промпт для розробки:**
```
Додай простий tracking токенів в AIService без складної логіки цін:

1. Після кожного виклику AI зберігай токени в документ:
   async def generate_content(self, prompt, model, document_id):
     response = await openai_client.chat.completions.create(...)
     
     # Оновити токени
     if response.usage:
       document = await db.get(Document, document_id)
       document.tokens_used += response.usage.total_tokens
       await db.commit()
       
       # Простий лог для моніторингу
       logger.info(f"AI usage: doc={document_id}, model={model}, tokens={response.usage.total_tokens}")
     
     return response.choices[0].message.content

2. Додай простий daily limit (опціонально):
   # В settings.py
   DAILY_TOKEN_LIMIT = 1000000  # 1M токенів на день (або None щоб вимкнути)
   
   # Перевірка (якщо потрібна)
   if settings.DAILY_TOKEN_LIMIT:
     today_tokens = await db.query(
       func.sum(Document.tokens_used)
     ).filter(
       Document.created_at >= datetime.now().date()
     ).scalar()
     
     if today_tokens > settings.DAILY_TOKEN_LIMIT:
       logger.warning(f"Daily limit exceeded: {today_tokens}")
       # Можна продовжити або raise error - як вирішите

3. Admin статистика (вже є в admin_service.py):
   # Endpoint вже існує: GET /api/v1/admin/stats
   # Просто переконайся що показує total_tokens_used
```

**Промпт для QA:**
```
Тест простого token tracking:

1. Тест збереження токенів:
   - Згенеруй контент для документа
   - Перевір що tokens_used оновився в БД
   - Перевір що токени додаються (не перезаписуються)
   
2. Тест daily limits:
   - Створи користувача з daily_token_limit=1000
   - Згенеруй контент що використає 800 токенів
   - Спробуй згенерувати ще 300 токенів - має бути 429 error
   
3. Тест admin статистики:
   - Створи 3 документи з різними tokens_used
   - Виклич GET /admin/stats
   - Перевір total_tokens_all_time
   - Перевір average_tokens_per_document
```

---

### ✅ Task 2.5: Search APIs Integration (2 години)

**Файл:** `apps/api/app/services/ai_pipeline/rag_retriever.py`

**Промпт для розробки:**
```
Додай інтеграцію Search APIs до існуючого RAG retriever:

1. Додай Perplexity API для real-time search:
   async def search_perplexity(self, query: str):
     headers = {
       "Authorization": f"Bearer {settings.PERPLEXITY_API_KEY}",
       "Content-Type": "application/json"
     }
     
     data = {
       "model": "pplx-7b-online",
       "messages": [
         {"role": "user", "content": f"Search for: {query}"}
       ]
     }
     
     async with httpx.AsyncClient() as client:
       response = await client.post(
         "https://api.perplexity.ai/chat/completions",
         headers=headers,
         json=data
       )
     
     return response.json()

2. Додай Tavily API для academic search:
   async def search_tavily(self, query: str):
     # Similar structure for Tavily API
     pass

3. Комбінуй результати:
   async def retrieve_sources(self, query: str):
     results = []
     
     # Existing Semantic Scholar
     if settings.SEMANTIC_SCHOLAR_ENABLED:
       results.extend(await self.search_semantic_scholar(query))
     
     # New APIs
     if settings.PERPLEXITY_API_KEY:
       results.extend(await self.search_perplexity(query))
     
     if settings.TAVILY_API_KEY:
       results.extend(await self.search_tavily(query))
     
     return results[:20]  # Top 20 sources
```

**Промпт для QA:**
```
Тест Search APIs:

1. Mock всі API responses
2. Перевір що retrieve_sources комбінує результати
3. Перевір fallback якщо один API недоступний
4. Перевір дедуплікацію джерел
5. Перевір форматування citations
```

---

### ✅ Task 2.6: Auto-save Implementation (3 години)

**Файл:** `apps/api/app/services/draft_service.py`

**Промпт для розробки:**
```
Створи DraftService для auto-save:

1. Модель DocumentDraft:
   class DocumentDraft(Base):
     __tablename__ = "document_drafts"
     
     id = Column(Integer, primary_key=True)
     document_id = Column(Integer, ForeignKey("documents.id"))
     user_id = Column(Integer, ForeignKey("users.id"))
     content = Column(Text)
     version = Column(Integer, default=1)
     created_at = Column(DateTime, default=func.now())
     auto_save = Column(Boolean, default=True)

2. Endpoint POST /documents/{id}/draft:
   - Приймає частковий контент
   - Зберігає як draft
   - Повертає version number

3. Endpoint GET /documents/{id}/draft/latest:
   - Повертає останній draft
   - Include timestamp

4. Auto-delete старих drafts:
   - Зберігати максимум 10 версій
   - Видаляти drafts старші 30 днів

5. Recovery endpoint GET /documents/recover:
   - Знайти документи зі статусом "generating"
   - Повернути список з можливістю відновлення
```

**Промпт для QA:**
```
Тест auto-save:

1. Створи документ
2. Збережи draft 15 разів
3. Перевір що тільки останні 10 версій збереглися
4. Отримай latest draft - має бути версія 15
5. Симулюй crash (змінити статус на "generating")
6. Виклич /documents/recover
7. Перевір що документ в списку для відновлення
8. Перевір auto-delete через 30 днів (змінити created_at в БД)
```

---

### ✅ Task 2.7: GDPR Consent Implementation (2 години)

**Файл:** `apps/api/app/services/gdpr_service.py`

**Промпт для розробки:**
```
Створи GDPR consent management:

1. Модель для consent:
   class UserConsent(Base):
     __tablename__ = "user_consents"
     
     id = Column(Integer, primary_key=True)
     user_id = Column(Integer, ForeignKey("users.id"))
     consent_type = Column(String)  # 'essential', 'analytics', 'marketing'
     granted = Column(Boolean)
     granted_at = Column(DateTime)
     ip_address = Column(String)
     user_agent = Column(String)

2. При реєстрації через magic link:
   @router.post("/auth/magic-link/verify")
   async def verify_magic_link(
     code: str,
     gdpr_consent: bool = False,
     analytics_consent: bool = False,
     marketing_consent: bool = False
   ):
     # Перевір що essential consent = true
     if not gdpr_consent:
       raise HTTPException(400, "GDPR consent is required")
     
     # Створи користувача
     user = await create_user(email)
     
     # Збережи consents
     consents = [
       UserConsent(user_id=user.id, consent_type="essential", granted=True),
       UserConsent(user_id=user.id, consent_type="analytics", granted=analytics_consent),
       UserConsent(user_id=user.id, consent_type="marketing", granted=marketing_consent)
     ]
     db.add_all(consents)
     await db.commit()

3. Data export endpoint:
   @router.get("/user/export-data")
   async def export_user_data(current_user: User = Depends(get_current_user)):
     data = {
       "user": user.dict(),
       "documents": [d.dict() for d in user.documents],
       "payments": [p.dict() for p in user.payments],
       "consents": [c.dict() for c in user.consents]
     }
     return JSONResponse(content=data, headers={
       "Content-Disposition": f"attachment; filename=user_data_{user.id}.json"
     })

4. Right to be forgotten:
   @router.delete("/user/delete-account")
   async def delete_account(current_user: User = Depends(get_current_user)):
     # Анонімізація замість видалення
     user.email = f"deleted_{user.id}@deleted.com"
     user.full_name = "DELETED USER"
     
     # Видалити документи з MinIO
     for doc in user.documents:
       await delete_from_storage(doc.docx_path)
       await delete_from_storage(doc.pdf_path)
     
     # Видалити sensitive data
     await db.execute("DELETE FROM user_consents WHERE user_id = $1", user.id)
     
     await db.commit()
     return {"status": "account_deleted"}
```

**Промпт для QA:**
```
Тест GDPR compliance:

1. Спробуй зареєструватись без gdpr_consent=true - має бути помилка
2. Зареєструйся з consent
3. Експортуй дані через /user/export-data
4. Перевір що JSON містить всі дані користувача
5. Видали акаунт через /user/delete-account
6. Перевір що email анонімізований
7. Перевір що файли видалені з MinIO
```

---

## 📋 ФАЗА 3: TESTING & QA (День 3-4)

### ✅ Task 3.1: Integration Tests Suite

**Промпт для розробки:**
```
Створи comprehensive integration test suite в tests/integration/:

1. test_full_user_journey.py:
   - Реєстрація через magic link
   - Створення документа
   - Генерація контенту
   - Оплата
   - Експорт документа

2. test_security_suite.py:
   - IDOR tests (спроби доступу до чужих ресурсів)
   - JWT expiration tests
   - File upload security tests
   - Rate limiting tests

3. test_error_handling.py:
   - API failures з retry
   - Payment failures
   - Invalid inputs
   - Database connection loss

4. test_performance.py:
   - Concurrent user tests (10 користувачів одночасно)
   - Large document generation (200 сторінок)
   - Memory usage monitoring

Використовуй pytest-asyncio, pytest-mock, faker для тестових даних
```

---

### ✅ Task 3.2: Load Testing

**Промпт для розробки:**
```
Створи load testing скрипти з locust в tests/load/:

1. locustfile.py:
   class UserBehavior(HttpUser):
     wait_time = between(1, 3)
     
     @task(1)
     def create_document(self):
       self.client.post("/api/v1/documents", json={...})
     
     @task(3)
     def list_documents(self):
       self.client.get("/api/v1/documents")
     
     @task(2)
     def generate_content(self):
       self.client.post("/api/v1/generate/outline", json={...})

2. Запуск:
   locust -f locustfile.py --host=http://localhost:8000 --users=50 --spawn-rate=5

3. Метрики для моніторингу:
   - Response time < 2s (p95)
   - Error rate < 1%
   - RPS > 100
```

---

## 📋 ФАЗА 4: DEPLOYMENT PREPARATION (День 4)

### ✅ Task 4.1: Environment Setup

**Промпт для DevOps:**
```
Підготуй production environment:

1. Створи .env.production:
   ENVIRONMENT=production
   DEBUG=false
   SECRET_KEY=[generated 32+ chars]
   JWT_SECRET=[generated 32+ chars]
   DATABASE_URL=postgresql+asyncpg://...
   REDIS_URL=redis://...
   OPENAI_API_KEY=sk-...
   STRIPE_SECRET_KEY=sk_live_...
   STRIPE_WEBHOOK_SECRET=whsec_...

2. Налаштуй Docker:
   docker-compose -f docker-compose.prod.yml build
   docker-compose -f docker-compose.prod.yml up -d

3. SSL сертифікати:
   certbot --nginx -d tesigo.com -d www.tesigo.com

4. Nginx конфігурація для reverse proxy

5. Systemd service для auto-restart
```

---

## 📊 МЕТРИКИ УСПІХУ

### MVP Ready Checklist:
- [ ] Всі 4 security issues виправлені
- [ ] Background jobs працюють
- [ ] Retry механізми активні
- [ ] Cost control впроваджений
- [ ] Auto-save функціонує
- [ ] 50%+ test coverage
- [ ] Load test пройдений (50 users)

### Production Ready Checklist:
- [ ] SSL налаштований
- [ ] Monitoring активний (Prometheus + Grafana)
- [ ] Backup автоматизований
- [ ] Logs централізовані
- [ ] Alerts налаштовані
- [ ] Documentation оновлена
- [ ] 80%+ test coverage

---

## 📊 ПІДСУМОК ОНОВЛЕНИЙ

**Загальний час:** ~4-5 днів (40-48 годин)

**Оновлені компоненти:**
- ✅ **WebSocket** для real-time прогресу
- ✅ **Smart Queue** з пріоритетами (малі документи першими)
- ✅ **Auto-scaling workers** (2-10 воркерів)
- ✅ **Circuit Breaker** pattern для надійності
- ✅ **ContextVar** для ізоляції контекстів
- ✅ **Детальні Checkpoints** (Redis + DB backup)
- ✅ **GDPR Consent** при реєстрації
- ❌ ~~Price quotes~~ (відхилено - не потрібно)

## 🚀 КОМАНДИ ДЛЯ ШВИДКОГО СТАРТУ

```bash
# День 1 - Security
./scripts/fix-security.sh

# День 2-3 - Features + нові компоненти
pytest tests/ -v --cov=app --cov-report=html

# День 3-4 - Testing
locust -f tests/load/locustfile.py --host=http://localhost:8000

# День 4-5 - Deploy
docker-compose -f docker-compose.prod.yml up -d
```

---

## 📝 ШАБЛОНИ ПРОМПТІВ

### Для розробника:
```
Задача: [назва]
Файл: [шлях]
Вимоги:
1. [вимога 1]
2. [вимога 2]
Приклад коду: [якщо є]
Тести: обов'язково додати unit тести
```

### Для QA:
```
Тестувати: [функціональність]
Сценарії:
1. Позитивний: [опис]
2. Негативний: [опис]
3. Edge cases: [опис]
Очікуваний результат: [опис]
Написати тести в: [файл]
```

---

**Документ створено:** 2025-11-02  
**Готовий до виконання!**
