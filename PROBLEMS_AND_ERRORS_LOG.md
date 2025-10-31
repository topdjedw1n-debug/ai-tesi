# Документ про всі проблеми та помилки в проекті

**Дата створення:** 31 січня 2025  
**Статус проекту:** MVP в розробці  
**Мета:** Детальний опис всіх виявлених проблем, багів, спроб виправлення та невирішених питань

---

## 📋 Зміст

1. [Критичні баги (що не працюють)](#критичні-баги-що-не-працюють)
2. [Відсутні реалізації](#відсутні-реалізації)
3. [Помилки типу та логіки](#помилки-типу-та-логіки)
4. [Інтеграційні проблеми](#інтеграційні-проблеми)
5. [Проблеми конфігурації](#проблеми-конфігурації)
6. [Frontend проблеми](#frontend-проблеми)
7. [Історія спроб виправлення](#історія-спроб-виправлення)
8. [Невирішені питання](#невирішені-питання)

---

## 🔴 Критичні баги (що не працюють)

### 1. Відсутня реалізація `export_document()` в DocumentService

**Файл:** `apps/api/app/services/document_service.py`

**Проблема:**
- Метод `export_document()` викликається в endpoint `/api/v1/documents/{id}/export/{format}`
- Метод не реалізований у класі `DocumentService`
- При виклику endpoint повертає `AttributeError: 'DocumentService' object has no attribute 'export_document'`

**Код виклику (документи.py:185):**
```python
result = await document_service.export_document(
    document_id,
    export_request.format,
    current_user.id
)
```

**Очікувана реалізація:**
Метод повинен:
1. Отримати документ з БД
2. Згенерувати .docx або .pdf файл
3. Завантажити в MinIO/S3
4. Повернути URL для завантаження

**Вплив:** ❌ **КРИТИЧНО** - Користувачі не можуть завантажити готові роботи

**Статус:** ❌ Не вирішено

---

### 2. Помилка з `time.time()` замість `datetime` в AIService

**Файл:** `apps/api/app/services/ai_service.py:143`

**Проблема:**
```python
section.completed_at = time.time()  # ❌ Помилка!
```

**Деталі:**
- `time.time()` повертає `float` (timestamp)
- Поле `completed_at` в моделі `DocumentSection` має тип `DateTime`
- SQLAlchemy очікує `datetime.datetime` об'єкт

**Очікуване виправлення:**
```python
from datetime import datetime
section.completed_at = datetime.utcnow()
```

**Вплив:** ❌ **КРИТИЧНО** - Помилка при збереженні розділу в БД

**Помилка при виконанні:**
```
TypeError: expected datetime.datetime object, got float
```

**Статус:** ❌ Не вирішено

---

### 3. Неправильний SQL запит в `get_user_usage()`

**Файл:** `apps/api/app/services/ai_service.py:188-192`

**Проблема:**
```python
result = await self.db.execute(
    select(
        Document.total_documents_created,  # ❌ Це поле не існує!
        Document.total_tokens_used          # ❌ Це поле не існує!
    ).where(Document.user_id == user_id)
)
```

**Деталі:**
- Поля `total_documents_created` та `total_tokens_used` не існують у моделі `Document`
- Потрібно рахувати через агрегацію

**Очікуване виправлення:**
```python
from sqlalchemy import func
result = await self.db.execute(
    select(
        func.count(Document.id).label('total_documents'),
        func.sum(Document.tokens_used).label('total_tokens')
    ).where(Document.user_id == user_id)
)
```

**Вплив:** ❌ **КРИТИЧНО** - Endpoint `/api/v1/generate/usage/{user_id}` не працює

**Помилка при виконанні:**
```
AttributeError: type object 'Document' has no attribute 'total_documents_created'
```

**Статус:** ❌ Не вирішено

---

### 4. Проблема в `DocumentService.create_document()` - неіснуюче поле

**Файл:** `apps/api/app/services/document_service.py:52-56`

**Проблема:**
```python
await self.db.execute(
    update(Document)
    .where(Document.user_id == user_id)
    .values(total_documents_created=Document.total_documents_created + 1)
)
```

**Деталі:**
- `Document.total_documents_created` не існує
- Потрібно оновлювати через модель `User` або видалити цей код

**Вплив:** ⚠️ **ПОМИЛКА** - Код викличе помилку при створенні документа

**Статус:** ❌ Не вирішено

---

### 5. Rate Limit Initialization Bug

**Файл:** `apps/api/app/middleware/rate_limit.py:226`

**Проблема:**
```python
storage_options=None  # ❌ Викликає AttributeError
```

**Деталі:**
- `storage_options=None` викликає `AttributeError` при використанні memory storage
- Потрібно замінити на `storage_options={}`

**Очікуване виправлення:**
```python
storage_options={}  # Для memory storage
```

**Вплив:** ⚠️ **ПРОБЛЕМА** - Rate limiting може не ініціалізуватися

**Статус:** ❌ Не вирішено (відзначено в PROJECT_UPDATE.md)

---

## 🟡 Відсутні реалізації

### 1. Система оплати (Payment Integration)

**Статус:** ❌ **НЕ РЕАЛІЗОВАНО**

**Що має бути:**
- Endpoint `/api/v1/payment/create` - створення платежу
- Endpoint `/api/v1/payment/webhook` - обробка webhook від Stripe/Fondy
- Модель `Payment` в БД
- Сервіс `PaymentService`
- Frontend сторінка оплати

**Згідно з інструкцією:**
- Розділ 2.3: "Інтеграція оплати"
- Потрібна інтеграція з Stripe або Fondy
- Оплата за роботу (без підписок)

**Вплив:** ❌ **КРИТИЧНО** - Неможливо монетизувати проект

**Статус:** ❌ Не реалізовано

---

### 2. Перевірка плагіату (Plagiarism Check)

**Статус:** ❌ **НЕ РЕАЛІЗОВАНО**

**Що має бути:**
- Endpoint `/api/v1/plagiarism/check`
- Інтеграція з Copyleaks або PlagiarismSearch
- Модель `PlagiarismReport` в БД
- Збереження звіту після перевірки
- Frontend для показу результатів

**Згідно з інструкцією:**
- Розділ 2.6: "Перевірка плагіату"
- Один з ключових вимог MVP: рівень плагіату ≤ 15%

**Вплив:** ❌ **КРИТИЧНО** - Неможливо гарантувати якість

**Статус:** ❌ Не реалізовано

---

### 3. Генерація документів .docx та .pdf

**Статус:** ⚠️ **ЧАСТКОВО РЕАЛІЗОВАНО**

**Що є:**
- ✅ Endpoint `/api/v1/documents/{id}/export/{format}` існує
- ✅ Модель `Document` має поля `docx_path` та `pdf_path`
- ✅ Бібліотеки встановлені (`python-docx`, `weasyprint`, `reportlab`)

**Що відсутнє:**
- ❌ Метод `export_document()` в `DocumentService` не реалізований
- ❌ Генерація .docx з правильним форматуванням:
  - Титульна сторінка
  - Зміст (Table of Contents)
  - Розділи з правильними відступами
  - Список літератури
  - Форматування цитат
- ❌ Генерація .pdf:
  - Конвертація з .docx або пряма генерація
  - Правильні шрифти та відступи

**Згідно з інструкції:**
- Розділ 2.7: "Генерація документів"
- Приклад коду для створення .docx (рядки 1098-1172)

**Вплив:** ❌ **КРИТИЧНО** - Користувачі не можуть завантажити роботи

**Статус:** ❌ Не вирішено

---

### 4. Email сервіс для Magic Links

**Файл:** `apps/api/app/services/auth_service.py:67`

**Проблема:**
```python
# TODO: Send email with magic link
# For now, we'll just return the token for development
magic_link = f"http://localhost:3000/auth/verify?token={token}"
```

**Деталі:**
- Email не надсилається
- Токен повертається в response (тільки для development)
- В production це небезпечно

**Вплив:** ⚠️ **ПРОБЛЕМА** - Magic links не працюють в production

**Статус:** ❌ Не вирішено (TODO залишено)

---

### 5. Валідація цитат на hallucinations

**Статус:** ❌ **НЕ РЕАЛІЗОВАНО**

**Що має бути:**
- Функція `validate_citations()` згідно з інструкцією (рядки 1191-1217)
- Перевірка, що всі цитати в тексті є у списку джерел
- Відкидання неіснуючих цитат

**Вплив:** ⚠️ **ВАЖЛИВО** - AI може вигадувати джерела

**Статус:** ❌ Не реалізовано

---

## 🟠 Помилки типу та логіки

### 1. Type Annotation Issue в exceptions.py

**Файл:** `apps/api/app/core/exceptions.py:11`

**Проблема:**
```python
error_code: str = None  # ❌ Помилка типу
```

**Деталі:**
- `error_code: str` з default `None` повинен бути `Optional[str]`

**Очікуване виправлення:**
```python
from typing import Optional
error_code: Optional[str] = None
```

**Вплив:** ⚠️ **ПОМИЛКА ТИПУ** - MyPy показує помилку

**Статус:** ❌ Не вирішено (відзначено в PROJECT_UPDATE.md)

---

### 2. Проблема з парсингом outline в `generate_outline()`

**Файл:** `apps/api/app/services/ai_service.py:46-50`

**Проблема:**
```python
outline_data = await self._call_ai_provider(...)
```

**Деталі:**
- `_call_ai_provider()` повертає `{"content": str, "tokens_used": int}`
- Але `generate_outline()` очікує структурований JSON з outline
- Немає парсингу JSON з відповіді AI

**Очікуване виправлення:**
```python
import json
response = await self._call_ai_provider(...)
outline_data = json.loads(response["content"])
```

**Вплив:** ⚠️ **ПРОБЛЕМА** - Outline зберігається як текст, а не структура

**Статус:** ❌ Не вирішено

---

### 3. Відсутня інтеграція RAG у AIService

**Проблема:**
- `SectionGenerator` існує та інтегрує RAG, citations та humanizer
- `AIService.generate_section()` НЕ використовує `SectionGenerator`
- RAG не викликається при генерації розділів

**Файли:**
- `apps/api/app/services/ai_pipeline/generator.py` - `SectionGenerator` реалізовано
- `apps/api/app/services/ai_service.py` - не використовує `SectionGenerator`

**Вплив:** ❌ **КРИТИЧНО** - Генерація розділів не використовує реальні джерела → hallucinations

**Очікуване виправлення:**
```python
# В AIService.generate_section()
from app.services.ai_pipeline.generator import SectionGenerator

generator = SectionGenerator()
result = await generator.generate_section(
    document=document,
    section_title=section_title,
    section_index=section_index,
    provider=document.ai_provider,
    model=document.ai_model,
    citation_style=CitationStyle.APA,  # або з документа
    humanize=False
)
```

**Статус:** ❌ Не вирішено

---

## 🔵 Інтеграційні проблеми

### 1. Frontend не використовує реальні API endpoints

**Файл:** `apps/web/components/dashboard/GenerateSectionForm.tsx:77-92`

**Проблема:**
```typescript
// TODO: Replace with actual API call
const response = await fetch('/api/v1/generate/outline', {
  // TODO: Add authentication header
})
```

**Деталі:**
- Використовується `/api/v1/generate/outline` без базового URL
- Немає authentication header
- Немає обробки помилок

**Очікуване виправлення:**
```typescript
const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/v1/generate/outline`, {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${token}` // з localStorage або context
  },
  body: JSON.stringify(data)
})
```

**Вплив:** ⚠️ **ПРОБЛЕМА** - Frontend не може викликати backend

**Статус:** ❌ Не вирішено (TODO залишено)

---

### 2. AuthProvider не перевіряє токен з backend

**Файл:** `apps/web/components/providers/AuthProvider.tsx:52`

**Проблема:**
```typescript
// TODO: Verify token with backend
// For now, just check if token exists
```

**Деталі:**
- Токен не перевіряється через `/api/v1/auth/me`
- Використовується тільки localStorage

**Вплив:** ⚠️ **ПРОБЛЕМА** - Неможливо визначити валідність токену

**Статус:** ❌ Не вирішено (TODO залишено)

---

### 3. Відсутні реальні дані в Dashboard компонентах

**Файли:**
- `apps/web/components/dashboard/DocumentsList.tsx:45` - `// TODO: Fetch real documents from API`
- `apps/web/components/dashboard/StatsOverview.tsx:23` - `// TODO: Fetch real stats from API`
- `apps/web/components/dashboard/RecentActivity.tsx:49` - `// TODO: Fetch real activities from API`

**Вплив:** ⚠️ **ПРОБЛЕМА** - Dashboard показує пусті дані

**Статус:** ❌ Не вирішено (TODO залишено)

---

## ⚙️ Проблеми конфігурації

### 1. Відсутні поля в моделі Document

**Файл:** `apps/api/app/models/document.py`

**Відсутні поля:**
- ❌ `work_type` (bachelor/master/coursework)
- ❌ `citation_style` (APA/MLA/Chicago)

**Згідно з інструкцією:**
- Розділ 2.1: Форма має поля для типу роботи та стилю цитування

**Вплив:** ⚠️ **ПРОБЛЕМА** - Неможливо зберігати тип роботи та стиль цитування

**Статус:** ❌ Не вирішено

---

### 2. Промпти не відповідають інструкції

**Файли:**
- `apps/api/app/services/ai_service.py:285-317` - `_build_outline_prompt()`
- `apps/api/app/services/ai_pipeline/prompt_builder.py:15-53` - `build_outline_prompt()`

**Проблеми:**
- ❌ Немає української локалізації
- ❌ Немає детальної структури вступу (актуальність, мета, завдання, об'єкт, предмет)
- ❌ Немає JSON формату відповіді
- ❌ Немає підтримки типів робіт (бакалаврська, магістерська, курсова)

**Згідно з інструкцією:**
- Розділ AI-пайплайн, Крок 1 (рядки 639-698)
- Детальна структура з JSON форматом

**Очікуваний промпт (з інструкції):**
```python
def build_outline_prompt(topic: str, work_type: str, pages: int, citation_style: str) -> str:
    work_types_ua = {
        "bachelor": "бакалаврська робота",
        "master": "магістерська дисертація",
        "coursework": "курсова робота"
    }
    return f"""Ти - експерт з академічного письма. Створи детальний план для {work_types_ua[work_type]}...
    """
```

**Вплив:** ⚠️ **ВАЖЛИВО** - AI генерує не те, що очікується

**Статус:** ❌ Не вирішено

---

## 📱 Frontend проблеми

### 1. Відсутній Ukrainian language у формі

**Файл:** `apps/web/components/dashboard/GenerateSectionForm.tsx:22-33`

**Проблема:**
```typescript
const languages = [
  { value: 'en', label: 'English' },
  // ... інші мови
  // ❌ Немає української ('uk')
]
```

**Вплив:** ⚠️ **ПРОБЛЕМА** - Неможливо вибрати українську мову

**Статус:** ❌ Не вирішено

---

### 2. Відсутні поля типу роботи та стилю цитування

**Файл:** `apps/web/components/dashboard/GenerateSectionForm.tsx:11-18`

**Проблема:**
Схема валідації не містить:
- `workType` (bachelor/master/coursework)
- `citationStyle` (APA/MLA/Chicago)

**Вплив:** ⚠️ **ПРОБЛЕМА** - Неможливо вибрати тип роботи та стиль цитування

**Статус:** ❌ Не вирішено

---

## 📚 Історія спроб виправлення

### Batch #1 та #2 (Security)

**Що робилося:**
- Реалізація безпеки (CSRF, rate limiting, CORS)
- Структуроване логування
- Prometheus metrics
- Admin endpoints

**Результат:** ✅ Успішно реалізовано

---

### Phase 1.1 (Ruff Auto-fix)

**Що робилося:**
- Автоматичне виправлення помилок Ruff
- Форматування коду

**Результат:** ✅ Успішно виправлено багато помилок

**Файли логів:** `logs/tasks/ruff-autofix/`

---

### Phase 1.2 (Quality Gate)

**Що робилося:**
- Python 3.11 enforcement
- Pytest smoke tests
- MyPy blocking errors fix
- CI workflow setup

**Результат:** ✅ Успішно проходять quality gates

**Файл:** `apps/api/QA_SUMMARY.md`

---

### Manual Fixes (logs/tasks/manual-fix/)

**Що робилося:**
- Виправлення помилок E402, F401, B028, B904
- Оновлення Python environment

**Результат:** ⚠️ Частково виправлено (деякі помилки залишилися)

---

## ❓ Невирішені питання

### 1. Чи повинна бути окрема таблиця для Payment?

**Питання:** Як зберігати інформацію про платежі?

**Варіанти:**
- Окрема таблиця `payments`
- Поле `payment_status` в таблиці `documents`
- Інтеграція з зовнішнім сервісом (Stripe/Fondy)

**Статус:** ❓ Не вирішено

---

### 2. Як інтегрувати Semantic Scholar API без API ключа?

**Питання:** Semantic Scholar API має безкоштовний tier, але з rate limits

**Варіанти:**
- Використовувати без API ключа (обмеження 100 req/5min)
- Отримати API ключ для більшого ліміту
- Кешування результатів (вже реалізовано в RAGRetriever)

**Статус:** ⚠️ Працює без ключа, але з обмеженнями

---

### 3. Як обробляти помилки AI API (rate limits, timeout)?

**Питання:** Що робити, коли OpenAI/Anthropic API повертає помилку?

**Поточний стан:**
- Базова обробка в `_call_openai()` та `_call_anthropic()`
- Помилки логуються, але немає retry logic

**Потрібно:**
- Retry logic з exponential backoff
- Fallback на інший провайдер (якщо доступний)
- Queue system для великих генерацій

**Статус:** ❓ Не вирішено

---

### 4. Як тестувати генерацію без реальних API ключів?

**Питання:** Unit тести потребують моків для AI провайдерів

**Поточний стан:**
- Немає моків для OpenAI/Anthropic
- Тести не покривають AI функціональність

**Потрібно:**
- Моки для AI провайдерів
- Integration тести з тестовими ключами
- Відокремлення тестів від production

**Статус:** ❓ Не вирішено

---

## 📊 Статистика проблем

| Категорія | Кількість | Критичність |
|-----------|-----------|-------------|
| Критичні баги | 5 | 🔴 Високо |
| Відсутні реалізації | 5 | 🔴 Високо |
| Помилки типу | 3 | 🟠 Середньо |
| Інтеграційні | 3 | 🟠 Середньо |
| Конфігурація | 2 | 🟡 Низько |
| Frontend | 2 | 🟡 Низько |
| **Всього** | **20** | |

---

## 🎯 Пріоритети виправлення

### Пріоритет 1 (Критично - блокують роботу)
1. ✅ Реалізувати `export_document()` в DocumentService
2. ✅ Виправити `time.time()` → `datetime.utcnow()` в ai_service.py
3. ✅ Виправити SQL запит в `get_user_usage()`
4. ✅ Видалити/виправити код з `total_documents_created` в create_document()

### Пріоритет 2 (Важливо - для функціональності)
5. ✅ Інтегрувати SectionGenerator в AIService
6. ✅ Реалізувати систему оплати
7. ✅ Реалізувати перевірку плагіату
8. ✅ Додати парсинг JSON для outline
9. ✅ Виправити type annotation в exceptions.py

### Пріоритет 3 (Покращення)
10. ✅ Оновити промпти згідно з інструкцією
11. ✅ Додати поля work_type та citation_style в модель Document
12. ✅ Налаштувати email сервіс для magic links
13. ✅ Виправити frontend API інтеграцію
14. ✅ Реалізувати валідацію цитат

---

## 📝 Висновок

Проект має **міцну технічну основу**, але є **20+ проблем**, які блокують повноцінну роботу:

**Критичні:**
- Відсутня реалізація експорту документів
- Помилки в коді (time.time, SQL запити)
- Відсутня система оплати
- Відсутня перевірка плагіату

**Важливі:**
- RAG не інтегрований у основний сервіс
- Промпти не відповідають інструкції
- Frontend не інтегрований з backend

**Рекомендація:** Спочатку виправити критичні баги (Пріоритет 1), потім додати відсутні функції (Пріоритет 2).

**Орієнтовний час:** 2-3 тижні для виправлення всіх критичних проблем.

---

**Останнє оновлення:** 31 січня 2025  
**Документ створено для:** Пошуку рішень у зовнішніх джерелах

