# 🚀 MVP ПЛАН - TesiGo Platform

> **Мінімально життєздатний продукт для запуску**

**Створено:** 25 листопада 2025
**Ціль:** Запустити working product за **2 тижні**
**Статус:** 🟡 В процесі (70% готовності)

---

## 📋 ЗМІСТ

1. [MVP Scope](#mvp-scope)
2. [Що УЖЕ працює](#що-вже-працює)
3. [Що ТРЕБА доробити](#що-треба-доробити)
4. [План на 2 тижні](#план-на-2-тижні)
5. [Критерії готовності](#критерії-готовності)

---

## 🎯 MVP SCOPE

### **ЩО ВХОДИТЬ В MVP:**

#### ✅ Core Features (Must Have)
1. **Реєстрація/Логін** - Magic link auth
2. **Створення документа** - Форма з темою, мовою, кількістю сторінок
3. **AI генерація** - Повний документ (outline + content)
4. **Оплата** - Stripe checkout (€0.50/сторінка)
5. **Експорт** - DOCX/PDF download
6. **Admin panel** - Базове управління

#### ❌ Що НЕ входить в MVP (v2.0+)
- ❌ Real-time прогрес WebSocket (показуємо loading)
- ❌ Редагування згенерованого тексту
- ❌ Plagiarism check (робимо в v2.0)
- ❌ Grammar check (робимо в v2.0)
- ❌ Custom requirements upload
- ❌ Multiple AI models (тільки GPT-4)
- ❌ Email notifications (тільки in-app)
- ❌ Advanced analytics

---

## ✅ ЩО ВЖЕ ПРАЦЮЄ (70%)

### **Backend (FastAPI) - 75%**

```
✅ Auth System
   ├── Magic link generation
   ├── Email verification
   ├── JWT tokens (access + refresh)
   └── Session management (Redis)

✅ Document Management
   ├── CRUD operations
   ├── Database models (SQLAlchemy)
   ├── File storage (MinIO)
   └── Status tracking

✅ AI Pipeline (частково)
   ├── OpenAI integration ✅
   ├── Anthropic integration ✅
   ├── Outline generation ✅
   ├── Section writing ✅
   ├── RAG search APIs ⚠️ (не всі підключені)
   └── Quality check ⚠️ (basic)

✅ Payment System
   ├── Stripe integration ✅
   ├── Payment intents ✅
   ├── Webhooks ⚠️ (є race condition!)
   └── Invoice generation ✅

✅ Admin Panel Backend
   ├── User management ✅
   ├── Document management ✅
   ├── Stats/analytics ✅
   └── Settings ⚠️ (pricing не динамічне)

✅ Infrastructure
   ├── PostgreSQL setup ✅
   ├── Redis setup ✅
   ├── MinIO setup ✅
   └── Docker compose ✅
```

### **Frontend (Next.js 14) - 65%**

```
✅ Authentication
   ├── Login/Signup pages ✅
   ├── Magic link flow ✅
   └── Protected routes ✅

✅ Dashboard
   ├── Document list ✅
   ├── Stats overview ⚠️ (mock data)
   └── Navigation ✅

⚠️ Document Creation
   ├── Form UI ✅
   ├── API integration ⚠️ (частково)
   └── Validation ✅

⚠️ Document View
   ├── Content display ✅
   ├── Export buttons ✅
   └── Progress tracking ❌ (відсутнє)

✅ Payment Flow
   ├── Stripe checkout ✅
   ├── Success/cancel pages ✅
   └── Payment history ✅

⚠️ Admin Panel
   ├── Layout ✅
   ├── User management ⚠️ (частково)
   ├── Documents ⚠️ (частково)
   └── Settings ❌ (pricing UI є, backend немає)
```

---

## 🔧 ЩО ТРЕБА ДОРОБИТИ (30%)

### **КРИТИЧНІ БАГИ (Must Fix) - 3 дні**

#### 🔴 P0: Security & Stability

1. ~~**JWT Refresh Token Loop**~~ ✅ **FIXED** (25.11.2025)
   - **Час:** 1 год 15 хв (замість 4 год)
   - **Звіт:** `docs/fixes/BUG_001_JWT_REFRESH.md`
   - **Виконано:**
     * ✅ Backend повертає refresh_token
     * ✅ Session expiration продовжується на +7 днів
     * ✅ Frontend має preemptive refresh (за 5 хв до expiration)
     * ✅ Тестування: 5/5 тестів пройдено
   - **Результат:** Користувачі більше не вилітають кожну годину ✅

2. **Stripe Webhook Race Condition** (2 години)
   - **Проблема:** Дублікати job при повторних webhook
   - **Рішення:**
     ```python
     # Backend: apps/api/app/services/payment_service.py
     # Додати SELECT FOR UPDATE + idempotency key
     async with db.begin():
         job = await db.execute(
             select(Job).where(Job.stripe_event_id == event_id).with_for_update()
         )
     ```

3. **Stripe Signature Verification** (1 година)
   - **Проблема:** Не перевіряється підпис webhook
   - **Рішення:**
     ```python
     stripe.Webhook.construct_event(
         payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
     )
     ```

**Всього P0:** ~3 години (Bug #1 виправлено, залишилось 2+1)

---

### **ВАЖЛИВІ ФІЧІ (Must Have) - 5 днів**

#### 🟡 Priority 1: Frontend-Backend Integration (2 дні)

1. **Replace Mock Data** (4 години)
   ```typescript
   // apps/web/components/dashboard/StatsOverview.tsx
   - const mockStats = { total: 15, completed: 12 }
   + const { data: stats } = useQuery('/api/v1/documents/stats')
   ```

2. **Real API Calls** (4 години)
   - `GenerateSectionForm.tsx` → використати `apiClient`
   - Додати error handling
   - Додати loading states

#### 🟡 Priority 2: AI Generation Flow (2 дні)

1. **Complete RAG Integration** (6 годин)
   - Підключити Perplexity API
   - Підключити Tavily API
   - Підключити Serper API
   - Semantic Scholar вже є ✅

2. **Error Recovery** (2 години)
   - Retry logic при API failures
   - Fallback між моделями (GPT-4 → GPT-3.5 → Claude)
   - Checkpoint система

#### 🟡 Priority 3: Dynamic Pricing (1 день)

1. **Backend** (4 години)
   ```python
   # Model
   class PricingConfig(Base):
       price_per_page = Column(Numeric(10, 2))
       currency = Column(String(3), default="EUR")

   # Service
   async def get_current_price() -> Decimal:
       return await pricing_service.get_price()
   ```

2. **Frontend** (2 години)
   - Admin panel форма вже є ✅
   - Підключити до реального API
   - Показувати ціну на payment page

**Всього Priority 1-3:** ~40 годин (5 днів)

---

### **NICE TO HAVE (Optional) - 2 дні**

#### 🟢 Priority 4: UX Improvements

1. **Loading States** (3 години)
   - Skeleton loaders
   - Progress indicators
   - Toast notifications

2. **Error Handling** (3 години)
   - User-friendly error messages
   - Retry buttons
   - Error boundaries

3. **Basic Testing** (1 день)
   - Smoke tests
   - Critical path testing
   - Manual QA checklist

**Всього Optional:** ~16 годин (2 дні)

---

## 📅 ПЛАН НА 2 ТИЖНІ

### **ТИЖДЕНЬ 1: Критичні фікси + Core features**

#### **День 1-2 (Пн-Вт): Security Fixes**
```bash
День 1 (8 годин):
├── 09:00-13:00 | JWT Refresh Token (4h)
│   ├── Frontend interceptor
│   ├── Backend refresh endpoint
│   └── Testing
└── 14:00-18:00 | Stripe Security (4h)
    ├── Race condition fix
    ├── Signature verification
    └── Testing

День 2 (8 годин):
├── 09:00-13:00 | Testing & Bug fixes (4h)
└── 14:00-18:00 | Frontend-Backend Integration START (4h)
```

#### **День 3-4 (Ср-Чт): Frontend Integration**
```bash
День 3 (8 годин):
├── 09:00-13:00 | Replace mock data (4h)
│   ├── StatsOverview
│   ├── DocumentsList
│   └── UserProfile
└── 14:00-18:00 | Real API calls (4h)
    ├── GenerateSectionForm
    ├── Error handling
    └── Loading states

День 4 (8 годин):
├── 09:00-13:00 | Admin panel integration (4h)
└── 14:00-18:00 | Testing integration (4h)
```

#### **День 5 (Пт): AI Pipeline**
```bash
День 5 (8 годин):
├── 09:00-13:00 | RAG APIs (4h)
│   ├── Perplexity
│   ├── Tavily
│   └── Serper
└── 14:00-18:00 | Error recovery (4h)
    ├── Retry logic
    ├── Fallback chain
    └── Testing
```

**Підсумок Тиждень 1:** Всі критичні баги виправлені, core integration готова

---

### **ТИЖДЕНЬ 2: Polish + Testing + Deploy**

#### **День 6-7 (Пн-Вт): Dynamic Pricing + UX**
```bash
День 6 (8 годин):
├── 09:00-13:00 | Pricing backend (4h)
│   ├── Model + migration
│   ├── Service layer
│   └── Admin endpoints
└── 14:00-18:00 | Pricing frontend (4h)
    ├── Admin UI integration
    └── Payment page update

День 7 (8 годин):
├── 09:00-13:00 | UX improvements (4h)
│   ├── Loading states
│   ├── Error messages
│   └── Toast notifications
└── 14:00-18:00 | Error boundaries (4h)
```

#### **День 8-9 (Ср-Чт): Testing**
```bash
День 8 (8 годин):
├── 09:00-13:00 | Smoke tests (4h)
│   ├── Auth flow
│   ├── Document creation
│   ├── Payment flow
│   └── Export
└── 14:00-18:00 | Critical path testing (4h)
    ├── E2E user journey
    └── Bug fixing

День 9 (8 годин):
├── 09:00-13:00 | Bug fixing (4h)
└── 14:00-18:00 | Final testing (4h)
```

#### **День 10 (Пт): Deploy Preparation**
```bash
День 10 (8 годин):
├── 09:00-11:00 | Environment setup (2h)
│   ├── Production .env
│   ├── Secrets management
│   └── Database migration
├── 11:00-13:00 | Deploy to staging (2h)
├── 14:00-16:00 | Staging testing (2h)
└── 16:00-18:00 | Production deploy (2h)
    └── Monitoring setup
```

**Підсумок Тиждень 2:** MVP готовий до production!

---

## ✅ КРИТЕРІЇ ГОТОВНОСТІ MVP

### **Функціональні вимоги:**

```
✅ 1. AUTHENTICATION
   ├── User can register with email
   ├── User can login with magic link
   ├── User can logout
   └── Session persists 7 days

✅ 2. DOCUMENT CREATION
   ├── User can create document (title, topic, pages, language)
   ├── Validation: 3-200 pages
   ├── Validation: supported languages
   └── Document saved to database

✅ 3. PAYMENT
   ├── User sees price calculation (pages × €0.50)
   ├── User can pay via Stripe
   ├── Payment confirmed via webhook
   └── Invoice generated

✅ 4. AI GENERATION
   ├── System generates outline (5-10 sections)
   ├── System generates full content
   ├── Generation takes 5-15 minutes
   ├── User can see generation status
   └── Content saved to database

✅ 5. EXPORT
   ├── User can download DOCX
   ├── User can download PDF
   ├── Export preserves formatting
   └── Export includes metadata

✅ 6. ADMIN PANEL
   ├── Admin can view all users
   ├── Admin can view all documents
   ├── Admin can see platform stats
   └── Admin can change pricing
```

### **Non-Functional вимоги:**

```
✅ PERFORMANCE
   ├── API response time < 500ms (p95)
   ├── Generation time < 15 min for 50 pages
   └── Frontend load time < 3s

✅ SECURITY
   ├── JWT tokens with refresh
   ├── HTTPS only in production
   ├── Stripe webhook verification
   ├── SQL injection protection (SQLAlchemy)
   └── XSS protection (Next.js built-in)

✅ RELIABILITY
   ├── Database backups daily
   ├── Error tracking (Sentry)
   ├── Health check endpoint
   └── Graceful error handling

✅ USABILITY
   ├── Mobile responsive
   ├── Clear error messages
   ├── Loading indicators
   └── User-friendly forms
```

---

## 🚦 DEFINITION OF DONE

**MVP вважається готовим коли:**

### ✅ Checklist для запуску:

```bash
# 1. Technical
□ All P0 bugs fixed
□ All critical features working
□ Smoke tests passing
□ Production environment configured
□ SSL certificates installed
□ Database backups configured
□ Monitoring set up (health checks)

# 2. Business
□ Stripe account in production mode
□ Email service configured (AWS SES or similar)
□ Terms of Service page
□ Privacy Policy page
□ Pricing page
□ Contact/Support email

# 3. Testing
□ Manual E2E test completed
□ Payment flow tested with real card
□ Generation tested for all languages
□ Export tested (DOCX + PDF)
□ Admin panel tested

# 4. Documentation
□ README updated
□ Environment variables documented
□ Deployment guide ready
□ API keys secured

# 5. Launch
□ Domain configured
□ DNS records set
□ Application deployed
□ Smoke test on production
□ First real payment processed
```

---

## 📊 SUCCESS METRICS

### **Week 1 Goals:**
- ✅ 0 P0 bugs remaining
- ✅ All core features working locally
- ✅ Backend-Frontend integration 100%

### **Week 2 Goals:**
- ✅ Successful staging deployment
- ✅ All smoke tests passing
- ✅ Successful production deployment
- ✅ First real user registration
- ✅ First real document generated

### **Post-Launch (Week 3):**
- 🎯 5 beta users registered
- 🎯 3 documents generated
- 🎯 1 successful payment
- 🎯 0 critical bugs reported

---

## 🔮 POST-MVP ROADMAP (v2.0)

### **Що робимо після запуску:**

**Month 1 (Immediate):**
- Real-time WebSocket progress
- Email notifications
- Plagiarism check integration
- Grammar check (LanguageTool)

**Month 2 (Short-term):**
- User feedback system
- Document history/versions
- Advanced search (user documents)
- Citation management

**Month 3 (Mid-term):**
- Mobile app (React Native)
- Collaborative editing
- Template system
- Social sharing

---

## 🆘 РИСКИ ТА МІТІГАЦІЯ

### **Технічні ризики:**

| Ризик | Ймовірність | Вплив | Мітігація |
|-------|-------------|-------|-----------|
| AI API timeout | Висока | Високий | Retry + fallback моделі |
| Stripe webhook fail | Середня | Критичний | Idempotency + manual retry |
| Database migration fail | Низька | Критичний | Backup before deploy |
| SSL certificate issue | Низька | Високий | LetsEncrypt auto-renewal |

### **Бізнес ризики:**

| Ризик | Ймовірність | Вплив | Мітігація |
|-------|-------------|-------|-----------|
| Low user adoption | Середня | Високий | Beta testing, marketing |
| High AI costs | Середня | Середній | Token usage monitoring |
| Quality complaints | Середня | Високий | Quality checks, refunds |
| Legal issues | Низька | Критичний | Terms of Service, disclaimers |

---

## 📝 DAILY STANDUP FORMAT

**Щоденний чек (15 хвилин):**

```
🎯 Yesterday:
   - What was completed
   - Blockers encountered

🚀 Today:
   - What will be done
   - Estimated hours

⚠️ Blockers:
   - Any issues preventing progress
   - Help needed
```

---

## 🎉 ЗАПУСК!

**Коли все готово:**

1. ✅ Deploy to production
2. 📧 Send to 10 beta testers
3. 📊 Monitor first 24 hours
4. 🐛 Fix any critical issues
5. 📈 Analyze metrics
6. 🚀 Open to public

**LET'S GO! 🚀**

---

**Останнє оновлення:** 25 листопада 2025
**Наступний review:** Кінець тижня 1
