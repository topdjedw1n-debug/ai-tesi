# 🎨 Структура користувацького досвіду (UX) TesiGo

> **Повний опис користувацького досвіду на платформі генерації академічних робіт**

**Версія:** 1.0
**Дата:** 2025-01-14
**Статус:** Актуальна

---

## 📑 Зміст

1. [Перший візіт та онбординг](#1-перший-візіт-та-онбординг)
2. [Автентифікація](#2-автентифікація)
3. [Dashboard та навігація](#3-dashboard-та-навігація)
4. [Створення документа](#4-створення-документа)
5. [Оплата](#5-оплата)
6. [Генерація та відстеження](#6-генерація-та-відстеження)
7. [Результат та експорт](#7-результат-та-експорт)
8. [Профіль користувача](#8-профіль-користувача)
9. [Адмін-панель](#9-адмін-панель)
10. [Помилки та edge cases](#10-помилки-та-edge-cases)

---

## 1. Перший візіт та онбординг

### 1.1 Головна сторінка (`/`)

**Ціль:** Залучити користувача та пояснити цінність платформи

**Елементи:**
- **Hero секція:**
  - Заголовок: "Generate High-Quality Academic Papers with AI"
  - Підзаголовок: "Plagiarism-free guarantee, export to DOCX/PDF"
  - CTA: "Get Started" (веде на `/dashboard` або реєстрацію)
  - Візуалізація: Приклад готового документа або анімація генерації

- **Features секція:**
  - AI-powered outline generation
  - Smart section writing
  - Multiple AI models (автоматичний вибір системою)
  - Time-saving automation
  - Multi-language support (EN, DE, FR, ES, IT, CS, UK)
  - Secure & private

- **How It Works секція:**
  1. Create Your Project (введення теми, довжини, мови)
  2. Generate Outline (AI створює структуру)
  3. Write Sections (генерація контенту з цитатами)
  4. Export & Share (експорт в DOCX/PDF)

- **Pricing секція:**
  - Pay-per-page модель: €0.50 за сторінку
  - Мінімум: 3 сторінки (€1.50)
  - Максимум: 200 сторінок
  - Валюта: Тільки EUR
  - Stripe integration

- **Footer:**
  - Посилання на документацію
  - Support email
  - Terms & Privacy

**UX принципи:**
- ✅ Простий, зрозумілий інтерфейс
- ✅ Чіткий CTA на кожному етапі
- ✅ Мінімум інформації, максимум цінності
- ✅ Mobile-responsive дизайн

---

## 2. Автентифікація

### 2.1 Magic Link Authentication

**Метод:** Безпарольна автентифікація через email

**Flow:**

1. **Користувач натискає "Get Started" або "Sign In"**
   - Перехід на `/auth/login` або `/dashboard` (якщо не авторизований)

2. **Введення email (`/auth/login`)**
   - Форма з одним полем: email
   - Валідація email формату
   - Кнопка: "Send Magic Link"
   - Rate limit: 3 magic links на день на email

3. **Відправка magic link**
   - Показ повідомлення: "Check your email for the magic link"
   - Таймер: "Link expires in 15 minutes"
   - Опція: "Resend link" (після 60 секунд)

4. **Email з magic link**
   - Тема: "Your TesiGo Magic Link"
   - Зміст:
     - Персональне привітання
     - Кнопка: "Sign in to TesiGo"
     - Посилання дійсне 15 хвилин
     - Якщо не ви запитували - ігноруйте

5. **Клік по magic link**
   - Перехід на `/auth/verify?token=...`
   - Автоматична верифікація токену
   - Створення JWT сесії (1 година)
   - Рефреш токен (7 днів)
   - Перенаправлення на `/dashboard`

**Стани:**
- ✅ Email відправлено
- ⏳ Чекаємо кліку
- ✅ Верифікація успішна → Dashboard
- ❌ Токен прострочений → Повторна відправка
- ❌ Невірний токен → Помилка

**Безпека:**
- Токен одноразовий
- Токен дійсний 15 хвилин
- Rate limiting: 3 запити/день
- JWT з коротким TTL (1 година)
- Refresh token для продовження сесії

---

## 3. Dashboard та навігація

### 3.1 Dashboard (`/dashboard`)

**Ціль:** Центральний хаб для управління документами

**Компоненти:**

1. **Header (загальний для всіх сторінок):**
   - Logo (ліворуч)
   - Навігація: Dashboard, Documents, Profile, Settings
   - User menu (праворуч): Email, Logout
   - Індикатор онлайну (якщо є WebSocket)

2. **Stats Overview:**
   - Total documents: X
   - Completed: Y
   - In progress: Z
   - Total spent: €X.XX

3. **Create Document Form:**
   - Швидка форма створення документа
   - Поля:
     - Title (обов'язкове)
     - Topic (обов'язкове, textarea)
     - Language (dropdown: EN, DE, FR, ES, IT, CS, UK)
     - Target pages (3-200, slider або input)
     - Additional requirements (опціонально, textarea)
   - Кнопка: "Create Document"
   - Валідація перед відправкою

4. **Documents List:**
   - Таблиця/Картки документів:
     - Title
     - Status (draft, generating, completed, failed)
     - Pages (target / actual)
     - Created at
     - Actions: View, Delete
   - Фільтри: Status, Language, Date
   - Сортування: Newest, Oldest, Status
   - Пагінація (якщо > 10 документів)

5. **Recent Activity:**
   - Останні події:
     - Document created
     - Generation started
     - Generation completed
     - Payment processed
   - Timestamp для кожної події

**Навігація:**
- `/dashboard` - Головна сторінка
- `/dashboard/documents` - Всі документи
- `/dashboard/documents/[id]` - Деталі документа
- `/dashboard/profile` - Профіль користувача
- `/dashboard/settings` - Налаштування

**UX принципи:**
- ✅ Швидкий доступ до створення документа
- ✅ Візуальний статус кожного документа
- ✅ Мінімум кліків до основної дії
- ✅ Responsive grid layout

---

## 4. Створення документа

### 4.1 Форма створення (`/dashboard` або `/dashboard/documents/new`)

**Етапи:**

1. **Основна інформація:**
   ```
   Title: [________________] (required)
   Topic: [________________] (required, multi-line)
   Language: [EN ▼] (dropdown)
   Target Pages: [10] [3-200] (slider)
   ```

2. **Додаткові вимоги (опціонально):**
   ```
   Additional Requirements:
   [________________]
   [________________]
   [________________]
   (e.g., specific structure, citation style, etc.)
   ```

3. **Завантаження файлу (опціонально):**
   ```
   [Upload custom requirements file]
   Supports: PDF, DOCX, TXT (max 5MB)
   ```

4. **Попередній перегляд вартості:**
   ```
   Calculation:
   Pages: 10
   Price per page: €0.50
   Total: €5.00
   ```

5. **Кнопка: "Create Document"**
   - Валідація перед відправкою
   - Лоадер під час створення
   - Після створення → Redirect на `/dashboard/documents/[id]`

### 4.2 Створення документа (API flow)

1. **POST `/api/v1/documents`**
   - Валідація даних
   - Створення запису в БД (status: "draft")
   - Збереження файлу (якщо є) в MinIO
   - Повернення document_id

2. **Redirect на сторінку документа**
   - `/dashboard/documents/[id]`

### 4.3 Сторінка документа (`/dashboard/documents/[id]`)

**Стани документа:**

**A. Draft (чернетка):**
- Показує введені дані
- Кнопка: "Generate Outline" (безкоштовно)
- Кнопка: "Start Generation" (потребує оплати)

**B. Outline Generated (структура створена):**
- Показує outline (дерево секцій)
- Можливість редагувати структуру (майбутнє)
- Кнопка: "Start Full Generation" (потребує оплати)
- Показує розрахунок вартості

**C. Payment Required (потрібна оплата):**
- Кнопка: "Pay & Generate" (€X.XX)
- Redirect на `/payment/[document_id]`

**D. Generating (генерація):**
- Real-time progress bar
- Поточний етап: "Generating section X of Y"
- Прогрес: 45%
- Оцінка часу: "~5 minutes remaining"
- WebSocket для real-time оновлень

**E. Completed (готово):**
- Показує повний контент
- Кнопки експорту: "Export DOCX", "Export PDF"
- Статистика: Tokens used, Generation time

**F. Failed (помилка):**
- Показує повідомлення про помилку
- Кнопка: "Retry Generation"
- Кнопка: "Request Refund" (якщо оплачено)

---

## 5. Оплата

### 5.1 Сторінка оплати (`/payment/[document_id]`)

**Елементи:**

1. **Інформація про документ:**
   ```
   Title: [Document Title]
   Pages: 10
   Language: English
   ```

2. **Розрахунок вартості:**
   ```
   Price breakdown:
   Pages: 10 × €0.50 = €5.00
   Total: €5.00
   ```

3. **Stripe Payment Form:**
   - Credit card input (Stripe Elements)
   - Валідація в реальному часі
   - Підтримка: Visa, Mastercard, Amex

4. **Кнопка: "Pay €5.00"**
   - Створює PaymentIntent через Stripe
   - Показує лоадер під час обробки

5. **Успішна оплата:**
   - Redirect на `/payment/success?session_id=...`

### 5.2 Payment Success (`/payment/success`)

**Flow:**
1. Верифікація session_id через API
2. Показ статусу: "Payment Successful!"
3. Автоматичний redirect на `/dashboard` через 3 секунди
4. Старт генерації документа (background job)

**Елементи:**
- ✅ Checkmark іконка
- Сума оплати
- Document ID
- Кнопка: "Go to Dashboard"

### 5.3 Payment Cancel (`/payment/cancel`)

**Flow:**
1. Користувач скасував оплату
2. Показ повідомлення: "Payment cancelled"
3. Опції:
   - "Try Again" → `/payment/[document_id]`
   - "Go to Dashboard" → `/dashboard`

### 5.4 Payment History (`/dashboard/payments`)

**Елементи:**
- Таблиця платежів:
  - Date
  - Document title
  - Amount
  - Status (completed, failed, refunded)
  - Actions: View details, Request refund

---

## 6. Генерація та відстеження

### 6.1 Real-time Progress Tracking

**Технологія:** WebSocket connection

**Етапи генерації:**

1. **Initialization (0-5%)**
   - "Preparing generation..."
   - Завантаження моделі
   - Підготовка контексту

2. **Research Phase (5-15%)**
   - "Searching academic sources..."
   - Perplexity/Tavily/Serper API
   - Semantic Scholar lookup
   - Формування citations

3. **Outline Generation (15-25%)**
   - "Generating document structure..."
   - Створення outline
   - Розподіл сторінок по секціях

4. **Content Generation (25-95%)**
   - "Writing section 1 of 5..." (25%)
   - "Writing section 2 of 5..." (45%)
   - "Writing section 3 of 5..." (65%)
   - "Writing section 4 of 5..." (85%)
   - "Writing section 5 of 5..." (95%)

5. **Quality Assurance (95-100%)**
   - "Checking grammar..." (97%)
   - "Checking plagiarism..." (99%)
   - "Finalizing document..." (100%)

**UI компоненти:**
- Progress bar (linear, від 0 до 100%)
- Поточний етап (текст)
- Оцінка часу: "~5 minutes remaining"
- WebSocket connection status (індикатор)

### 6.2 WebSocket Events

**Client → Server:**
```javascript
{
  type: "subscribe",
  document_id: 123
}
```

**Server → Client:**
```javascript
{
  type: "progress",
  document_id: 123,
  progress: 45,
  stage: "Generating section 2 of 5",
  estimated_time: 300 // seconds
}
```

```javascript
{
  type: "completed",
  document_id: 123,
  status: "completed"
}
```

```javascript
{
  type: "error",
  document_id: 123,
  error: "AI API timeout"
}
```

### 6.3 Сторінка генерації (`/dashboard/documents/[id]` під час генерації)

**Елементи:**
- Progress bar
- Current stage text
- Estimated time
- Cancel button (опціонально, якщо дозволено)
- Background job ID (для debug)

**UX принципи:**
- ✅ Чіткий прогрес
- ✅ Реалістичні оцінки часу
- ✅ Можливість закрити сторінку (генерація продовжиться)
- ✅ Нотифікації (email/web push) при завершенні

---

## 7. Результат та експорт

### 7.1 Сторінка готового документа (`/dashboard/documents/[id]` - status: completed)

**Елементи:**

1. **Document Header:**
   - Title
   - Status badge: "Completed"
   - Created at, Completed at
   - Pages: 10 (actual)

2. **Document Content:**
   - Full text preview (scrollable)
   - Syntax highlighting (якщо є код)
   - Formatting: headings, paragraphs, lists

3. **Statistics:**
   ```
   Generation Stats:
   - Tokens used: 45,230
   - Generation time: 8 minutes 32 seconds
   - AI Model: GPT-4
   - Language: English
   ```

4. **Export Options:**
   - Кнопка: "Export DOCX"
   - Кнопка: "Export PDF"
   - Лоадер під час експорту
   - Автоматичне завантаження файлу

5. **Actions:**
   - "Regenerate" (потребує повторної оплати)
   - "Delete Document"
   - "Request Refund" (якщо не задоволений)

### 7.2 Експорт документа

**API Flow:**
1. **POST `/api/v1/documents/[id]/export`**
   ```json
   {
     "format": "docx" | "pdf"
   }
   ```

2. **Backend:**
   - Генерація DOCX через `python-docx`
   - Генерація PDF через `reportlab` або `weasyprint`
   - Збереження в MinIO
   - Повернення download URL

3. **Frontend:**
   - Автоматичне завантаження файлу
   - Toast notification: "Document exported successfully"

**Формати:**
- **DOCX:**
  - Збереження форматування
  - Headings, paragraphs, lists
  - Citations (якщо є)

- **PDF:**
  - Академічний формат
  - Шрифти: Times New Roman або Arial
  - Поля: 2.5cm з усіх сторін
  - Нумерація сторінок

---

## 8. Профіль користувача

### 8.1 Profile Page (`/dashboard/profile`)

**Елементи:**

1. **Personal Information:**
   - Email (незмінний)
   - Full Name (editable)
   - Preferred Language (dropdown)
   - Timezone (dropdown)

2. **Statistics:**
   ```
   Account Stats:
   - Total documents: 15
   - Completed: 12
   - Total spent: €67.50
   - Member since: Jan 1, 2025
   ```

3. **Usage Tracking:**
   - Total tokens used: 234,567
   - Average tokens per document: 15,637

4. **Stripe Information:**
   - Customer ID (якщо є)
   - Payment methods (якщо збережено)

### 8.2 Settings Page (`/dashboard/settings`)

**Елементи:**

1. **Notifications:**
   - Email notifications (toggle)
   - Generation completed (toggle)
   - Payment updates (toggle)

2. **Privacy:**
   - Data retention: 90 days
   - Delete account (button)

3. **API Keys (майбутнє):**
   - API access для сторонніх додатків

---

## 9. Адмін-панель

### 9.1 Admin Dashboard (`/admin/dashboard`)

**Доступ:** Тільки для користувачів з `is_admin=True` або `is_super_admin=True`

**Елементи:**

1. **System Statistics:**
   ```
   - Total users: 1,234
   - Active users (30d): 567
   - Total documents: 5,678
   - Total revenue: €12,345.67
   - AI tokens used: 45,678,901
   ```

2. **Recent Activity:**
   - New registrations
   - Completed documents
   - Failed generations
   - Payment issues

3. **Quick Actions:**
   - Update pricing
   - View logs
   - System health

### 9.2 Admin - Users Management (`/admin/users`)

**Елементи:**
- Таблиця користувачів:
  - ID, Email, Name
  - Status (active, inactive)
  - Documents count
  - Total spent
  - Created at
  - Actions: View, Edit, Ban

### 9.3 Admin - Documents Management (`/admin/documents`)

**Елементи:**
- Таблиця документів:
  - ID, Title, User
  - Status
  - Pages
  - Created at
  - Actions: View, Delete

### 9.4 Admin - Payments Management (`/admin/payments`)

**Елементи:**
- Таблиця платежів:
  - ID, User, Document
  - Amount, Status
  - Created at
  - Actions: View, Refund, Export

### 9.5 Admin - Refunds Management (`/admin/refunds`)

**Елементи:**
- Таблиця запитів на повернення:
  - ID, User, Payment
  - Reason, Status (pending, approved, rejected)
  - Amount
  - Actions: Approve, Reject

### 9.6 Admin - Settings (`/admin/settings`)

**Елементи:**
- **Pricing Configuration:**
  - Price per page: €0.50 (editable)
  - Currency: EUR (fixed)
  - Min pages: 3
  - Max pages: 200

- **System Configuration:**
  - AI provider settings
  - Rate limits
  - Email settings

---

## 10. Помилки та edge cases

### 10.1 Помилки автентифікації

**Magic link не прийшов:**
- Показ: "Check spam folder"
- Кнопка: "Resend link" (через 60 секунд)
- Rate limit повідомлення: "Too many requests. Try again tomorrow."

**Токен прострочений:**
- Показ: "Link expired. Request a new one."
- Кнопка: "Request New Link"

**Невірний токен:**
- Показ: "Invalid link. Request a new one."
- Redirect на `/auth/login`

### 10.2 Помилки генерації

**AI API timeout:**
- Показ: "Generation timeout. Retrying..."
- Автоматичний retry (3 рази)
- Якщо не вдалося: "Generation failed. Please try again or request a refund."

**Недостатньо коштів:**
- Показ: "Insufficient funds. Please top up your balance."
- Кнопка: "Add Funds" (майбутнє) або "Pay Now"

**Документ занадто великий:**
- Показ: "Document exceeds maximum size (200 pages)."
- Рекомендація: "Split into multiple documents."

### 10.3 Помилки оплати

**Stripe payment failed:**
- Показ: "Payment failed. Please try again."
- Кнопка: "Retry Payment"
- Причина помилки (якщо доступна)

**Webhook verification failed:**
- Логування помилки
- Admin notification
- Manual verification через admin panel

### 10.4 Помилки експорту

**Export failed:**
- Показ: "Export failed. Please try again."
- Кнопка: "Retry Export"
- Логування помилки

**File too large:**
- Показ: "Document too large for export. Please contact support."
- Link to support

### 10.5 Edge Cases

**Користувач закрив браузер під час генерації:**
- ✅ Генерація продовжується в background
- Email notification при завершенні
- Документ доступний в dashboard

**Множинні одночасні генерації:**
- Rate limit: 1 генерація на користувача одночасно
- Показ: "Another generation in progress. Please wait."

**Неактивний користувач:**
- Auto-logout після 7 днів неактивності
- Email з reminder

---

## 11. UX Best Practices

### 11.1 Загальні принципи

1. **Простота:**
   - Мінімум кроків до основної дії
   - Чіткі CTA кнопки
   - Зрозуміла навігація

2. **Швидкість:**
   - Швидкий початковий завантаження
   - Lazy loading для великих списків
   - Оптимізовані зображення

3. **Прозорість:**
   - Чіткий прогрес генерації
   - Прозорі ціни
   - Відкритий статус помилок

4. **Надійність:**
   - Auto-save форм
   - Retry механізми
   - Graceful error handling

5. **Доступність:**
   - ARIA labels
   - Keyboard navigation
   - Screen reader support

### 11.2 Mobile Experience

- ✅ Responsive design
- ✅ Touch-friendly buttons (min 44x44px)
- ✅ Simplified navigation
- ✅ Mobile-optimized forms

### 11.3 Performance Targets

- First Contentful Paint: < 1.5s
- Time to Interactive: < 3s
- Largest Contentful Paint: < 2.5s
- Cumulative Layout Shift: < 0.1

---

## 12. Будущі покращення

### 12.1 Заплановані функції

1. **Collaboration:**
   - Спільна робота над документами
   - Коментарі та reviews

2. **Templates:**
   - Готові шаблони для різних типів робіт
   - Custom templates

3. **Version Control:**
   - Історія змін
   - Rollback до попередніх версій

4. **Advanced Export:**
   - Custom formatting
   - Citation styles (APA, MLA, Chicago)
   - Bibliography generation

5. **Mobile App:**
   - iOS/Android apps
   - Push notifications

6. **API Access:**
   - REST API для сторонніх інтеграцій
   - Webhooks для подій

---

## Додаток A: User Journey Map

```
1. Discovery (Google/Social) → Landing Page
2. Interest → Features/How It Works
3. Decision → Pricing
4. Sign Up → Email Magic Link
5. First Login → Dashboard
6. Create Document → Form
7. Payment → Stripe Checkout
8. Generation → Real-time Progress
9. Completion → Export
10. Satisfaction → Repeat Usage / Referral
```

---

## Додаток B: Key Metrics

**Engagement:**
- Daily Active Users (DAU)
- Weekly Active Users (WAU)
- Monthly Active Users (MAU)
- Session duration
- Pages per session

**Conversion:**
- Sign up rate
- Document creation rate
- Payment conversion rate
- Completion rate

**Retention:**
- Day 1 retention
- Day 7 retention
- Day 30 retention
- Churn rate

**Revenue:**
- Average Revenue Per User (ARPU)
- Lifetime Value (LTV)
- Monthly Recurring Revenue (MRR)

---

**Останнє оновлення:** 2025-01-14
**Версія документу:** 1.0
**Автор:** AI Assistant (запит користувача)

