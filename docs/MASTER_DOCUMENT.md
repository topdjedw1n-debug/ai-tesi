# 📚 TesiGo Technical Documentation v3.0

> **Single Source of Truth** - Вся технічна документація проекту в одному місці

**Останнє оновлення:** 2026-02-23 (Wave 3B)
**Версія проекту:** 2.3
**Статус:** 🟢 Release Candidate (Strict Go-Live)

> **Release note (23.02.2026):**
> User payment/refund flows are enabled by default after Wave 3B restore.
> Feature flags remain available as runtime kill-switches
> (`NEXT_PUBLIC_ENABLE_USER_PAYMENT_FLOW`, `NEXT_PUBLIC_ENABLE_USER_REFUND_FLOW`).
>
> **Compliance matrix:** `docs/MASTER_COMPLIANCE_MATRIX.md`

---

## 📑 Table of Contents

1. [Project Overview](#1-project-overview)
2. [Architecture](#2-architecture)
3. [Technology Stack](#3-technology-stack)
4. [API Reference](#4-api-reference)
5. [AI Pipeline](#5-ai-pipeline)
6. [Security & Compliance](#6-security--compliance)
7. [Setup & Deployment](#7-setup--deployment)
8. [Monitoring & Debugging](#8-monitoring--debugging)
9. [Known Issues & Solutions](#9-known-issues--solutions)
10. [Roadmap](#10-roadmap)

---

## 1. Project Overview

### 1.1 What is TesiGo

TesiGo - це AI-powered платформа для генерації академічних робіт (дипломні, курсові, дисертації). Система використовує найновіші LLM моделі для створення унікального, якісного контенту з гарантією проходження перевірки на плагіат.

### 1.2 Business Model

- **Модель:** Pay-per-page (оплата за сторінку)
- **Ціна:** €0.50 за сторінку (базова, динамічна через admin panel)
- **Мінімум сторінок:** 3 (менше не приймаємо)
- **Валюта:** Тільки EUR
- **Платіжна система:** Stripe
- **Політика повернень:**
  - Автоматичне повернення при технічній помилці системи
  - Повернення за запитом користувача (з обґрунтуванням) - тільки після апруву адміністратора
  - БЕЗ автоматичної відміни після оплати
- **Цільова аудиторія:** Студенти, аспіранти, дослідники

### 1.3 Core Features

- ✅ AI генерація академічних робіт (повний документ, без окремих секцій)
- ✅ Гарантія унікальності (plagiarism check)
- ✅ Підтримка різних типів робіт
- ✅ Експорт в DOCX/PDF (БЕЗ редагування після генерації)
- ✅ Real-time прогрес генерації
- ✅ Auto-save структури документа
- ✅ Єдиний оптимізований AI pipeline (без вибору моделі користувачем)

### 1.4 Key Constraints

- **Python:** 3.11+ (строго)
- **Мови контенту:** EN, DE, FR, ES, IT, CS, UK
- **AI провайдери:** OpenAI, Anthropic (вибір автоматичний системою)
- **Search APIs:** Perplexity API, Tavily API, Serper API, Semantic Scholar (для RAG)
- **Min документ:** 3 сторінки
- **Max документ:** 200 сторінок
- **Min ціна:** €0.50 за сторінку (3 сторінки = €1.50 мінімум)

---

## 2. Architecture

### 2.1 System Design

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Next.js   │────▶│   FastAPI   │────▶│ PostgreSQL  │
│   Frontend  │     │   Backend   │     │   Database  │
└─────────────┘     └─────────────┘     └─────────────┘
                            │
                    ┌───────┴────────┐
                    ▼                ▼
              ┌─────────┐     ┌─────────┐
              │  Redis  │     │  MinIO  │
              │  Cache  │     │ Storage │
              └─────────┘     └─────────┘
                    │
            ┌───────┴────────┐
            ▼                ▼
      ┌─────────┐     ┌─────────┐
      │ OpenAI  │     │Anthropic│
      │   API   │     │   API   │
      └─────────┘     └─────────┘
```

### 2.2 Components

| Component | Technology | Purpose | Port |
|-----------|-----------|---------|------|
| Frontend | Next.js 14 | User Interface | 3000 |
| Backend | FastAPI | API Server | 8000 |
| Database | PostgreSQL 15 | Data Storage | 5432 |
| Cache | Redis 7 | Session/Cache | 6379 |
| Storage | MinIO | File Storage | 9000 |
| AI | OpenAI/Anthropic | Content Generation | - |

### 2.3 Database Schema

```sql
-- Core Tables
users (id, email, full_name, created_at, is_active)
documents (id, user_id, title, content, status, pages, created_at)
payments (id, user_id, document_id, amount, status, stripe_intent_id)
jobs (id, document_id, status, progress, error, created_at)

-- Support Tables
email_verifications (id, email, code, status, created_at)
audit_logs (id, user_id, action, details, ip_address, created_at)
pricing_config (id, price_per_page, currency, updated_at)
```

### 2.4 Key Design Decisions

- **Async everywhere:** Всі I/O операції асинхронні
- **Type safety:** Strict typing з Pydantic
- **Stateless:** Сесії в Redis, не в пам'яті
- **Streaming:** Великі файли через streaming
- **Background jobs:** Генерація в background

---

## 3. Technology Stack

### 3.1 Backend Stack

```python
# Core
fastapi==0.104.1          # Web framework
uvicorn==0.24.0          # ASGI server
python-multipart==0.0.6  # File uploads

# Database
sqlalchemy==2.0.23       # ORM
asyncpg==0.29.0         # PostgreSQL driver
alembic==1.12.1         # Migrations

# Validation
pydantic==2.5.0         # Data validation
email-validator==2.1.0  # Email validation

# AI/ML
openai==1.3.5           # OpenAI API
anthropic==0.7.0        # Claude API
langchain==0.0.340      # AI orchestration

# Storage
redis==5.0.1            # Cache
minio==7.2.0            # Object storage

# Security
python-jose[cryptography]==3.3.0  # JWT
passlib[bcrypt]==1.7.4           # Password hashing
python-decouple==3.8              # Environment vars

# Monitoring
prometheus-client==0.19.0  # Metrics
loguru==0.7.2             # Logging
sentry-sdk==1.38.0        # Error tracking
```

### 3.2 Frontend Stack

```json
{
  "dependencies": {
    "next": "14.0.3",
    "react": "18.2.0",
    "typescript": "5.3.2",
    "@tanstack/react-query": "5.8.4",
    "axios": "1.6.2",
    "zustand": "4.4.7",
    "react-hook-form": "7.48.2",
    "tailwindcss": "3.3.6",
    "@stripe/stripe-js": "2.2.0"
  }
}
```

### 3.3 Infrastructure

```yaml
# Docker Services
postgres:15-alpine     # Database
redis:7-alpine        # Cache
minio/minio:latest    # Object storage

# Deployment
Docker Compose        # Local/Staging
Kubernetes           # Production (optional)
```

---

## 4. API Reference

### 4.1 Authentication Endpoints

```python
POST   /api/v1/auth/magic-link          # Request magic link
POST   /api/v1/auth/verify-magic-link   # Verify magic link
POST   /api/v1/auth/refresh              # Refresh JWT token
POST   /api/v1/auth/logout               # Logout user
GET    /api/v1/auth/me                   # Get current user
```

### 4.2 Document Endpoints

```python
POST   /api/v1/documents                 # Create document
GET    /api/v1/documents                 # List documents
GET    /api/v1/documents/{id}           # Get document
PUT    /api/v1/documents/{id}           # Update document
DELETE /api/v1/documents/{id}           # Delete document
POST   /api/v1/documents/{id}/export    # Export to DOCX/PDF
```

### 4.3 Generation Endpoints

```python
POST   /api/v1/generate/outline         # Generate outline
POST   /api/v1/generate/section         # Generate section
POST   /api/v1/generate/full-document   # Generate full document
GET    /api/v1/generate/models          # Available models
GET    /api/v1/generate/usage/{user_id} # Usage statistics
```

### 4.4 Payment Endpoints

```python
POST   /api/v1/payment/create-intent    # Create payment
POST   /api/v1/payment/create-checkout  # Create Stripe checkout session
GET    /api/v1/payment/verify           # Verify checkout session
POST   /api/v1/payment/webhook          # Stripe webhook
GET    /api/v1/payment/history          # Payment history
GET    /api/v1/payment/{id}            # Payment details
```

### 4.5 Refund Endpoints

```python
POST   /api/v1/refunds                  # Create refund request (user)
GET    /api/v1/refunds                  # List own refunds (user)
GET    /api/v1/refunds/{id}             # Refund details (user)
GET    /api/v1/admin/refunds            # List refunds (admin)
GET    /api/v1/admin/refunds/{id}       # Refund details (admin)
POST   /api/v1/admin/refunds/{id}/approve # Approve refund (admin)
POST   /api/v1/admin/refunds/{id}/reject  # Reject refund (admin)
```

### 4.6 Admin Endpoints

```python
POST   /api/v1/admin/auth/login         # Admin login
POST   /api/v1/admin/auth/logout        # Admin logout
GET    /api/v1/admin/stats              # System statistics
GET    /api/v1/admin/users              # User management
PUT    /api/v1/admin/users/{id}/block   # Block user
PUT    /api/v1/admin/users/{id}/unblock # Unblock user
POST   /api/v1/admin/users/{id}/make-admin # Elevate user role
GET    /api/v1/admin/documents          # Document moderation
GET    /api/v1/admin/payments           # Payment management
GET    /api/v1/admin/refunds/stats      # Refund analytics
GET    /api/v1/admin/settings           # Platform settings
```

---

## 5. AI Pipeline

### 5.1 Supported Models

| Provider | Model | Use Case |
|----------|-------|----------|
| OpenAI | GPT-4 | High quality, academic papers |
| OpenAI | GPT-4 Turbo | Balanced speed/quality |
| OpenAI | GPT-3.5 Turbo | Fast generation, drafts |
| Anthropic | Claude 3.5 Sonnet | Creative writing |
| Anthropic | Claude 3 Opus | Research papers |

### 5.2 Search APIs for RAG

| API | Purpose | Status |
|-----|---------|--------|
| **Perplexity API** | Real-time web search | To implement |
| **Tavily API** | Academic search | To implement |
| **Serper API** | Google search results | To implement |
| **Semantic Scholar** | Academic papers | ✅ Implemented |
| **ArXiv API** | Scientific papers | Optional |
| **CrossRef API** | DOI resolution | Optional |
| **CORE API** | Open access papers | Optional |

### 5.3 Generation Flow

```python
1. Input Processing
   ├── Validate requirements
   ├── Estimate costs
   └── Check user balance

2. Source Research (RAG)
   ├── Search via Perplexity/Tavily/Serper
   ├── Retrieve academic papers (Semantic Scholar)
   ├── Format citations
   └── Build context

3. Outline Generation
   ├── Create structure
   ├── Define sections
   └── Allocate pages

4. Content Generation
   ├── Generate by sections (not chunks!)
   ├── Include sources from RAG
   ├── Stream to storage
   ├── Save checkpoints
   └── Clear memory after each section

5. Quality Assurance
   ├── Grammar check (LanguageTool)
   ├── Plagiarism check (Copyscape)
   └── Formatting validation

6. Delivery
   ├── Export to DOCX/PDF
   ├── Store in MinIO
   └── Send notification
```

### 5.4 Token Tracking

```python
# Simple token tracking
document.tokens_used += response.usage.total_tokens
await db.commit()

# Logging for monitoring
logger.info(f"AI usage: doc={document_id}, model={model}, tokens={tokens}")

# Admin statistics
GET /api/v1/admin/stats  # Shows total_tokens_used
```

### 5.5 Retry Strategy

```python
class RetryStrategy:
    delays = [2, 4, 8, 16, 32]  # Exponential backoff

    fallback_chain = [
        "gpt-4",
        "gpt-4-turbo",
        "gpt-3.5-turbo",
        "claude-3.5-sonnet"
    ]

    checkpoint_interval = 300  # 5 minutes
```

### 5.6 AI Self-Learning System (Planned)

**Концепція:** Система автоматичного покращення якості генерації на основі історії успішних документів.

#### Збір даних для навчання:
```python
# Критерії для включення документа в training dataset:
training_criteria = {
    "min_quality_score": 4.0,     # Мінімум 4/5 зірок
    "plagiarism_passed": True,    # < 15% плагіату
    "ai_detection_passed": True,  # < 55% AI detection
    "user_satisfied": True,       # Користувач задоволений
}
```

#### Процес self-learning:
1. **Data Collection:** Автоматичний збір успішних документів
2. **Quality Filtering:** Фільтрація за критеріями якості
3. **Training Dataset:** Формування JSONL для fine-tuning
4. **Monthly Retraining:** Автоматичне перенавчання раз на місяць
5. **A/B Testing:** Тестування нової моделі на 10% трафіку
6. **Deployment:** Розгортання після підтвердження покращення

#### Технічна реалізація:
```python
# Експорт даних для навчання
async def export_training_data():
    documents = await get_high_quality_documents(
        min_score=4.0,
        limit=1000
    )

    training_data = []
    for doc in documents:
        training_data.append({
            "messages": [
                {"role": "system", "content": get_system_prompt(doc)},
                {"role": "user", "content": doc.topic},
                {"role": "assistant", "content": doc.final_content}
            ],
            "metadata": {
                "language": doc.language,
                "quality_score": doc.quality_score,
                "work_type": doc.work_type
            }
        })

    return save_as_jsonl(training_data)
```

#### Переваги:
- ✅ Постійне покращення якості
- ✅ Адаптація до потреб користувачів
- ✅ Зниження кількості регенерацій
- ✅ Краще розуміння локальних вимог

#### Статус: **🟡 Заплановано** (після досягнення 100+ успішних документів)

---

## 6. Security & Compliance

### 6.1 Authentication

- **Method:** JWT with magic links
- **Token expiration:** 1 hour
- **Refresh tokens:** 7 days
- **Session storage:** Redis
- **Email verification:** Double opt-in

### 6.2 Critical Security Fixes (TODO)

```python
# 1. IDOR Protection (2 hours)
async def check_document_ownership(document_id, user_id):
    if document.user_id != user_id:
        raise HTTPException(404, "Not found")

# 2. JWT Hardening (30 min)
SECRET_KEY = secrets.token_urlsafe(32)  # Min 32 chars
JWT_EXPIRATION = 3600  # 1 hour

# 3. File Validation (2 hours)
PDF_MAGIC = b"%PDF"
if not content.startswith(PDF_MAGIC):
    raise ValidationError("Invalid file")

# 4. Backup Script (1 hour)
pg_dump + encryption + 3-2-1 rule
```

### 6.3 GDPR Compliance

- **Right to be forgotten:** Анонімізація даних
- **Data portability:** Export в JSON/CSV
- **Consent management:** Explicit consent
- **Data retention:** Auto-deletion після 90 днів
- **Privacy by design:** Sanitized logs

### 6.4 Security Headers

```python
# Implemented in middleware
Content-Security-Policy: default-src 'self'
X-Frame-Options: DENY
X-Content-Type-Options: nosniff
Strict-Transport-Security: max-age=31536000
```

### 6.5 Rate Limiting

```python
# Current implementation
IP: 100 requests/minute
User: 1000 requests/hour
Email: 3 magic links/day
```

---

## 7. Setup & Deployment

### 7.1 Quick Start (5 minutes)

```bash
# 1. Clone repository
git clone https://github.com/tesigo/tesigo-app.git
cd tesigo-app

# 2. Start infrastructure
cd infra/docker
docker-compose up -d

# 3. Setup backend
cd apps/api
cp .env.example .env
pip install -r requirements.txt
uvicorn main:app --reload

# 4. Setup frontend
cd apps/web
cp .env.local.example .env.local
npm install
npm run dev

# 5. Open browser
http://localhost:3000
```

### 7.2 Environment Variables

```bash
# Required for production
DATABASE_URL=postgresql://user:pass@host/db
REDIS_URL=redis://localhost:6379
SECRET_KEY=<32+ chars random>
JWT_SECRET=<32+ chars random>

# AI Providers
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...

# Storage
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_ENDPOINT=localhost:9000

# Payments
STRIPE_SECRET_KEY=sk_live_...
STRIPE_WEBHOOK_SECRET=whsec_...

# Monitoring (optional)
SENTRY_DSN=https://...
PROMETHEUS_PORT=9090
```

### 7.3 Production Deployment

```bash
# 1. Prepare server (Ubuntu 22.04)
sudo apt update && sudo apt upgrade -y
sudo apt install docker docker-compose nginx certbot

# 2. Setup SSL
sudo certbot --nginx -d tesigo.com

# 3. Deploy application
cd infra/docker
docker-compose -f docker-compose.prod.yml up -d

# 4. Run migrations
docker exec tesigo-api alembic upgrade head

# 5. Create admin user
docker exec tesigo-api python scripts/create_admin.py

# 6. Setup monitoring
docker-compose -f docker-compose.monitoring.yml up -d
```

### 7.4 Health Checks

```python
# Backend: http://localhost:8000/health
{
  "status": "healthy",
  "database": "connected",
  "redis": "connected",
  "storage": "connected",
  "version": "2.3.0"
}

# Frontend: http://localhost:3000/api/health
{
  "status": "ok",
  "timestamp": "2025-11-02T10:00:00Z"
}
```

---

## 8. Monitoring & Debugging

### 8.1 Logging

```python
# Structured JSON logging
{
  "timestamp": "2025-11-02T10:00:00Z",
  "level": "INFO",
  "correlation_id": "abc-123",
  "user_id": 42,
  "action": "document.created",
  "details": {...}
}

# Log locations
Backend: logs/app.log
Audit: logs/audit.log
Error: Sentry dashboard
```

### 8.2 Metrics

```python
# Prometheus metrics (port 9090)
http_requests_total
http_request_duration_seconds
document_generation_duration_seconds
ai_api_calls_total
ai_api_costs_total
```

### 8.3 Debugging

```python
# Correlation ID tracking
X-Correlation-ID: abc-123-def-456

# Debug endpoints (dev only)
GET /api/v1/debug/config
GET /api/v1/debug/cache
GET /api/v1/debug/jobs

# Common issues
1. Memory leak → Restart workers
2. Slow generation → Check AI API limits
3. Payment fails → Check Stripe webhook
```

### 8.4 Alerts

```python
# Critical alerts (Telegram/Email)
- API error rate > 5%
- Response time > 2s (p95)
- Memory usage > 85%
- Disk space < 10GB
- Database connections > 80
- AI API failures > 3 in row
```

---

## 9. Known Issues & Solutions

### 9.1 Critical Issues (Must Fix)

| Issue | Impact | Solution | Time |
|-------|--------|----------|------|
| IDOR vulnerability | Security | Add ownership checks | 2h |
| Weak JWT keys | Security | Generate strong keys | 30m |
| No file validation | Security | Check magic bytes | 2h |
| No backups | Data loss | Implement 3-2-1 backup | 1h |
| BackgroundJobService not integrated | Performance | Wire up endpoints | 2h |

### 9.2 Performance Issues

```python
# Memory leaks
- Problem: OOM after 80+ pages
- Solution: Stream generation, clear memory

# Slow queries
- Problem: N+1 queries in documents list
- Solution: Add eager loading

# Connection pool
- Problem: Database connection exhaustion
- Solution: Limit pool to 20 connections
```

### 9.3 Common Errors

```python
# "Insufficient funds"
- User balance too low
- Solution: Top up balance

# "Generation timeout"
- Document too large
- Solution: Split into smaller sections

# "API rate limit"
- Too many requests
- Solution: Implement retry with backoff
```

---

## 10. Roadmap

### 10.1 Immediate (Before Launch)

- [ ] Fix IDOR vulnerability
- [ ] Implement JWT hardening
- [ ] Add file magic bytes validation
- [ ] Setup basic backup script
- [ ] Integrate BackgroundJobService
- [ ] Add webhook signature verification

### 10.2 Short Term (Month 1)

- [ ] Implement retry mechanisms
- [ ] Add cost pre-estimation
- [ ] Setup monitoring dashboards
- [ ] Implement auto-save
- [ ] Add progress tracking
- [ ] Customer support system

### 10.3 Medium Term (Months 2-3)

- [ ] Performance optimization
- [ ] Advanced analytics
- [ ] A/B testing framework
- [ ] Content moderation
- [ ] API documentation
- [ ] Mobile responsive design

### 10.4 Long Term (Future)

- [ ] Mobile apps
- [ ] Multi-language UI
- [ ] Alternative AI providers
- [ ] Collaboration features
- [ ] API for third parties
- [ ] Self-hosted models (maybe)

---

## Appendix A: Quick Commands

```bash
# Docker
docker-compose up -d              # Start all services
docker-compose logs -f api        # View API logs
docker-compose restart api        # Restart API
docker exec -it tesigo-db psql    # Database console

# Database
alembic upgrade head              # Run migrations
alembic revision --autogenerate   # Create migration

# Testing
pytest tests/                     # Run all tests
pytest tests/test_api.py -v      # Specific test
pytest --cov=app                 # Coverage report

# Linting
ruff check .                      # Lint code
ruff format .                     # Format code
mypy app/                        # Type checking

# Production
./scripts/deploy.sh              # Deploy to production
./scripts/backup.sh              # Backup database
./scripts/health-check.sh        # Check health
```

## Appendix B: Common Issues

```bash
# Port already in use
lsof -i :8000
kill -9 <PID>

# Docker permissions
sudo usermod -aG docker $USER
newgrp docker

# Database connection refused
docker-compose restart postgres
docker-compose logs postgres

# Redis connection error
docker-compose restart redis
redis-cli ping

# MinIO not accessible
docker-compose logs minio
Check firewall rules for port 9000
```

## Appendix C: Contact & Support

- **Documentation:** This file
- **Repository:** github.com/tesigo/tesigo-app
- **Email:** support@tesigo.com
- **Monitoring:** grafana.tesigo.com
- **Logs:** sentry.tesigo.com

## Appendix D: Known Technical Debt

### MyPy Issues (167 errors)
- SQLAlchemy ORM false positives: ~41
- Missing type annotations: ~40-50
- Unused type ignores: ~10
- Config/decorator issues: ~10-20

### Low Test Coverage Modules
- `admin_service.py`: 25%
- `humanizer.py`: 20%
- `background_jobs.py`: 20%
- **Overall coverage:** 44% (target: 80%)

### Specific Bugs
- `rate_limit.py` line 226: Handle None storage_options
- `exceptions.py`: Change error_code to Optional[str]

### Missing CI/CD
- No MyPy CI gate
- No coverage threshold enforcement
- No pre-commit hooks configured

---

**Last Updated:** 2025-11-02 by AI Assistant
**Next Review:** Before production deployment
