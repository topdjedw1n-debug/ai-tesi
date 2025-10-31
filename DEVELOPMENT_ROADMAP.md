# Покроковий план дій для продовження розробки проекту

**Дата створення:** 31 січня 2025  
**Поточна версія:** MVP 1.0 (65% готовності)  
**Ціль:** Повноцінний MVP згідно з PROJECT_INSTRUCTION.md

---

## 📊 Загальний огляд

**Поточний стан:** 65% готовності  
**Цільовий стан:** 100% MVP функціональність  
**Орієнтовний час:** 3-4 тижні інтенсивної роботи

---

## 🎯 Етапи розробки

### **ЕТАП 0: Виправлення критичних багів** (2-3 дні)
**Мета:** Зробити базовий функціонал робочим

---

### **ЕТАП 1: Завершення базової функціональності** (1 тиждень)
**Мета:** Реалізувати експорт та інтеграцію компонентів

---

### **ЕТАП 2: Система оплати та монетизація** (1 тиждень)
**Мета:** Додати можливість приймати оплату від користувачів

---

### **ЕТАП 3: Перевірка плагіату та якість** (3-4 дні)
**Мета:** Гарантувати якість згенерованого контенту

---

### **ЕТАП 4: Покращення та полірування** (3-4 дні)
**Мета:** Покращити UX, додати деталі з інструкції

---

### **ЕТАП 5: Тестування та підготовка до production** (2-3 дні)
**Мета:** Готовність до публічного запуску

---

## 📋 Детальний план дій

---

## 🔧 ЕТАП 0: Виправлення критичних багів (2-3 дні)

**Пріоритет:** 🔴 КРИТИЧНО  
**Орієнтовний час:** 2-3 дні

### Крок 0.1: Виправити помилки типів та дат (2-3 години)

#### Задача 0.1.1: Виправити `time.time()` → `datetime.utcnow()`

**Файл:** `apps/api/app/services/ai_service.py`

**Дії:**
1. Знайти всі використання `time.time()` для дат
2. Замінити на `datetime.utcnow()`
3. Перевірити, що всі імпорти є

**Код:**
```python
# Було:
import time
section.completed_at = time.time()

# Стало:
from datetime import datetime
section.completed_at = datetime.utcnow()
```

**Перевірка:**
- Запустити тести
- Перевірити, що розділи зберігаються в БД

---

#### Задача 0.1.2: Виправити type annotation в exceptions.py

**Файл:** `apps/api/app/core/exceptions.py`

**Дії:**
```python
# Було:
error_code: str = None

# Стало:
from typing import Optional
error_code: Optional[str] = None
```

**Перевірка:**
- `mypy apps/api/app/core/exceptions.py` має проходити

---

### Крок 0.2: Виправити SQL запити (1-2 години)

#### Задача 0.2.1: Виправити `get_user_usage()`

**Файл:** `apps/api/app/services/ai_service.py:184-201`

**Дії:**
```python
# Було:
result = await self.db.execute(
    select(
        Document.total_documents_created,  # ❌
        Document.total_tokens_used          # ❌
    ).where(Document.user_id == user_id)
)

# Стало:
from sqlalchemy import func
result = await self.db.execute(
    select(
        func.count(Document.id).label('total_documents'),
        func.sum(Document.tokens_used).label('total_tokens')
    ).where(Document.user_id == user_id)
)
stats = result.first()
return {
    "user_id": user_id,
    "total_documents": stats.total_documents if stats else 0,
    "total_tokens_used": stats.total_tokens if stats and stats.total_tokens else 0,
    "last_updated": datetime.utcnow().isoformat()
}
```

**Перевірка:**
- Тестовий запит: `GET /api/v1/generate/usage/{user_id}`

---

#### Задача 0.2.2: Видалити код з `total_documents_created` в create_document()

**Файл:** `apps/api/app/services/document_service.py:52-56`

**Дії:**
- Видалити або закоментувати блок:
```python
# Видалити цей код:
await self.db.execute(
    update(Document)
    .where(Document.user_id == user_id)
    .values(total_documents_created=Document.total_documents_created + 1)
)
```

**Або:** Додати поле `total_documents_created` в модель `User` (якщо потрібна статистика)

---

### Крок 0.3: Виправити Rate Limit initialization (30 хвилин)

**Файл:** `apps/api/app/middleware/rate_limit.py`

**Дії:**
```python
# Знайти рядок з storage_options=None
# Замінити на:
storage_options={}  # Для memory storage
```

**Перевірка:**
- Перевірити, що rate limiting ініціалізується без помилок
- Логи не мають містити AttributeError

---

### Результат Етапу 0:
✅ Всі критичні баги виправлені  
✅ Базовий функціонал працює  
✅ Немає помилок типів, які блокують роботу

**Тестування:**
- Запустити всі тести: `pytest apps/api/tests/`
- Перевірити health check: `curl http://localhost:8000/health`
- Перевірити генерацію розділу (має зберігатися в БД)

---

## 🚀 ЕТАП 1: Завершення базової функціональності (1 тиждень)

**Пріоритет:** 🔴 ВИСОКО  
**Орієнтовний час:** 5-7 днів

### Крок 1.1: Реалізувати експорт документів (2-3 дні)

#### Задача 1.1.1: Створити метод `export_document()` для .docx (1 день)

**Файл:** `apps/api/app/services/document_service.py`

**Дії:**

1. Додати метод `export_document()`:
```python
async def export_document(
    self,
    document_id: int,
    format: str,  # "docx" або "pdf"
    user_id: int
) -> dict[str, Any]:
    """
    Експортує документ у .docx або .pdf формат
    
    Args:
        document_id: ID документа
        format: Формат експорту ("docx" або "pdf")
        user_id: ID користувача для перевірки доступу
        
    Returns:
        dict з download_url, expires_at, file_size, format
    """
    # 1. Отримати документ
    document = await self.get_document(document_id, user_id)
    
    # 2. Згенерувати файл
    if format == "docx":
        file_path = await self._create_docx(document)
    elif format == "pdf":
        file_path = await self._create_pdf(document)
    else:
        raise ValidationError(f"Unsupported format: {format}")
    
    # 3. Завантажити в MinIO
    s3_url = await self._upload_to_minio(file_path, document_id, format)
    
    # 4. Оновити документ в БД
    field = f"{format}_path"
    await self.db.execute(
        update(Document)
        .where(Document.id == document_id)
        .values(**{field: s3_url})
    )
    await self.db.commit()
    
    # 5. Повернути URL для завантаження
    return {
        "download_url": s3_url,
        "expires_at": (datetime.utcnow() + timedelta(days=30)).isoformat(),
        "file_size": os.path.getsize(file_path),
        "format": format
    }
```

2. Створити допоміжний метод `_create_docx()`:
```python
async def _create_docx(self, document_data: dict) -> str:
    """Створює .docx файл з документом"""
    from docx import Document
    from docx.shared import Pt, Inches
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    
    doc = Document()
    
    # Налаштування сторінки
    sections = doc.sections
    for section in sections:
        section.page_height = Inches(11.69)  # A4
        section.page_width = Inches(8.27)
        section.left_margin = Inches(1.18)
        section.right_margin = Inches(0.59)
        section.top_margin = Inches(0.79)
        section.bottom_margin = Inches(0.79)
    
    # Титульна сторінка
    title = doc.add_heading(document_data["title"], level=0)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    doc.add_page_break()
    
    # Вступ
    if document_data.get("introduction"):
        doc.add_heading("ВСТУП", level=1)
        doc.add_paragraph(document_data.get("introduction", ""))
    
    # Розділи
    for chapter in document_data.get("outline", {}).get("chapters", []):
        doc.add_page_break()
        doc.add_heading(f"РОЗДІЛ {chapter.get('number', '')}. {chapter.get('title', '').upper()}", level=1)
        
        # Отримати секції для цього розділу
        sections_data = document_data.get("sections", [])
        chapter_sections = [s for s in sections_data if s.get("chapter_number") == chapter.get("number")]
        
        for section in chapter_sections:
            doc.add_heading(f"{section.get('section_index', '')}. {section.get('title', '')}", level=2)
            paragraph = doc.add_paragraph(section.get("content", ""))
            paragraph.style.font.name = "Times New Roman"
            paragraph.style.font.size = Pt(14)
            paragraph.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    
    # Висновки
    if document_data.get("conclusion"):
        doc.add_page_break()
        doc.add_heading("ВИСНОВКИ", level=1)
        doc.add_paragraph(document_data.get("conclusion", ""))
    
    # Список літератури (якщо є)
    if document_data.get("bibliography"):
        doc.add_page_break()
        doc.add_heading("СПИСОК ВИКОРИСТАНИХ ДЖЕРЕЛ", level=1)
        for i, source in enumerate(document_data.get("bibliography", []), 1):
            doc.add_paragraph(f"{i}. {source}")
    
    # Зберегти файл
    filename = f"document_{document_data['id']}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.docx"
    filepath = f"/tmp/{filename}"
    doc.save(filepath)
    
    return filepath
```

3. Створити метод `_upload_to_minio()`:
```python
async def _upload_to_minio(self, file_path: str, document_id: int, format: str) -> str:
    """Завантажує файл в MinIO та повертає URL"""
    from minio import Minio
    from app.core.config import settings
    
    client = Minio(
        settings.MINIO_ENDPOINT,
        access_key=settings.MINIO_ACCESS_KEY,
        secret_key=settings.MINIO_SECRET_KEY,
        secure=settings.MINIO_SECURE
    )
    
    object_name = f"documents/{document_id}/{datetime.utcnow().strftime('%Y/%m')}/document_{document_id}.{format}"
    
    client.fput_object(
        settings.MINIO_BUCKET,
        object_name,
        file_path
    )
    
    return f"s3://{settings.MINIO_BUCKET}/{object_name}"
```

**Ресурси для навчання:**
- python-docx документація: https://python-docx.readthedocs.io/
- Приклад з інструкції: PROJECT_INSTRUCTION.md рядки 1098-1172

**Тестування:**
- Створити тестовий документ
- Викликати `POST /api/v1/documents/{id}/export` з `{"format": "docx"}`
- Перевірити, що файл створюється та завантажується

---

#### Задача 1.1.2: Створити метод `_create_pdf()` (1 день)

**Дії:**

1. Використати WeasyPrint або ReportLab (обидва встановлені)
2. Створити PDF з того ж контенту, що і .docx
3. Або конвертувати .docx → .pdf

**Варіант 1: Пряма генерація PDF (WeasyPrint)**
```python
async def _create_pdf(self, document_data: dict) -> str:
    """Створює .pdf файл з документом"""
    from weasyprint import HTML, CSS
    from weasyprint.text.fonts import FontConfiguration
    
    # Створити HTML з контенту
    html_content = self._document_to_html(document_data)
    
    # Генерувати PDF
    filename = f"document_{document_data['id']}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.pdf"
    filepath = f"/tmp/{filename}"
    
    HTML(string=html_content).write_pdf(filepath)
    
    return filepath
```

**Варіант 2: Конвертація .docx → .pdf (простіше)**
- Спочатку створити .docx
- Використати LibreOffice або pandoc для конвертації

**Ресурси:**
- WeasyPrint: https://weasyprint.org/
- ReportLab: https://www.reportlab.com/docs/reportlab-userguide.pdf

---

#### Задача 1.1.3: Інтегрувати з MinIO та тестування (4-6 годин)

**Дії:**
1. Перевірити підключення до MinIO
2. Тестувати завантаження файлів
3. Створити тести для export endpoint
4. Перевірити, що файли доступні через URL

---

### Крок 1.2: Інтегрувати SectionGenerator в AIService (1 день)

#### Задача 1.2.1: Замінити простий AI виклик на SectionGenerator

**Файл:** `apps/api/app/services/ai_service.py`

**Дії:**

1. Оновити `generate_section()`:
```python
async def generate_section(
    self,
    document_id: int,
    section_title: str,
    section_index: int,
    user_id: int,
    additional_requirements: str | None = None
) -> dict[str, Any]:
    """Generate a specific section using AI with RAG"""
    from app.services.ai_pipeline.generator import SectionGenerator
    from app.services.ai_pipeline.citation_formatter import CitationStyle
    
    # Отримати документ
    result = await self.db.execute(
        select(Document).where(
            Document.id == document_id,
            Document.user_id == user_id
        )
    )
    document = result.scalar_one_or_none()
    
    if not document:
        raise NotFoundError("Document not found")
    
    # Отримати попередні секції для контексту
    sections_result = await self.db.execute(
        select(DocumentSection)
        .where(DocumentSection.document_id == document_id)
        .order_by(DocumentSection.section_index)
    )
    previous_sections = [
        {"title": s.title, "content": s.content[:200]}
        for s in sections_result.scalars().all()
        if s.section_index < section_index
    ]
    
    # Створити generator та згенерувати секцію
    generator = SectionGenerator()
    result = await generator.generate_section(
        document=document,
        section_title=section_title,
        section_index=section_index,
        provider=document.ai_provider,
        model=document.ai_model,
        citation_style=CitationStyle.APA,  # TODO: Отримати з документа
        humanize=False,
        context_sections=previous_sections,
        additional_requirements=additional_requirements
    )
    
    # Зберегти секцію
    section = DocumentSection(
        document_id=document_id,
        title=section_title,
        section_index=section_index,
        content=result["content"],
        status="completed",
        tokens_used=len(result.get("citations", [])) * 100,  # Приблизна оцінка
        completed_at=datetime.utcnow()
    )
    self.db.add(section)
    await self.db.commit()
    
    return {
        "document_id": document_id,
        "section_title": section_title,
        "section_index": section_index,
        "content": result["content"],
        "citations": result.get("citations", []),
        "bibliography": result.get("bibliography", []),
        "status": "completed"
    }
```

2. Додати поле `citation_style` в модель `Document` (або отримувати з параметрів)

**Тестування:**
- Згенерувати секцію
- Перевірити, що використовуються реальні джерела з Semantic Scholar
- Перевірити, що цитати правильно форматуются

---

### Крок 1.3: Покращити промпти згідно з інструкцією (1 день)

#### Задача 1.3.1: Оновити `build_outline_prompt()` з українською та детальною структурою

**Файл:** `apps/api/app/services/ai_pipeline/prompt_builder.py`

**Дії:**

1. Оновити метод `build_outline_prompt()`:
```python
@staticmethod
def build_outline_prompt(
    document: Document,
    additional_requirements: str | None = None
) -> str:
    """Build prompt for outline generation with Ukrainian support"""
    
    work_types_ua = {
        "bachelor": "бакалаврська робота",
        "master": "магістерська дисертація",
        "coursework": "курсова робота"
    }
    
    work_type_ua = work_types_ua.get(document.work_type, "дипломна робота") if hasattr(document, 'work_type') else "дипломна робота"
    
    citation_styles_ua = {
        "apa": "APA",
        "mla": "MLA",
        "chicago": "Chicago"
    }
    citation_style = citation_styles_ua.get(document.citation_style, "APA") if hasattr(document, 'citation_style') else "APA"
    
    prompt = f"""Ти - експерт з академічного письма. Створи детальний план для {work_type_ua} на тему:

"{document.topic}"

Вимоги:
- Обсяг роботи: приблизно {document.target_pages} сторінок
- Стиль цитування: {citation_style}
- Мова: {document.language}
- Структура має відповідати стандартам української академічної роботи

План повинен містити:
1. Вступ (актуальність, мета, завдання, об'єкт, предмет)
2. Розділи (2-3 основних)
   - Кожен розділ з 2-3 підрозділами
   - Короткий опис змісту (2-3 речення)
3. Висновки
4. Список використаних джерел (мінімум 15 джерел)

Формат відповіді (JSON):
{{
  "title": "Повна назва роботи",
  "introduction": {{
    "relevance": "Текст актуальності",
    "goal": "Мета дослідження",
    "tasks": ["Завдання 1", "Завдання 2", ...],
    "object": "Об'єкт дослідження",
    "subject": "Предмет дослідження"
  }},
  "chapters": [
    {{
      "number": 1,
      "title": "Назва розділу",
      "description": "Опис змісту розділу",
      "sections": [
        {{"number": 1.1, "title": "Назва підрозділу", "description": "Опис"}},
        ...
      ]
    }},
    ...
  ],
  "conclusion": "Короткий опис того, що має бути у висновках"
}}

Додаткові вимоги: {additional_requirements or 'Немає'}

Пиши українською мовою. Використовуй академічний стиль. Відповідай ТІЛЬКИ JSON, без додаткового тексту."""
    
    return prompt.strip()
```

2. Додати парсинг JSON в `generate_outline()`:
```python
import json

# Після отримання відповіді від AI:
try:
    outline_data = json.loads(response["content"])
except json.JSONDecodeError:
    # Спробувати витягнути JSON з тексту
    import re
    json_match = re.search(r'\{.*\}', response["content"], re.DOTALL)
    if json_match:
        outline_data = json.loads(json_match.group())
    else:
        raise AIProviderError("Failed to parse outline JSON from AI response")
```

**Тестування:**
- Згенерувати outline для тестового документа
- Перевірити, що структура правильна
- Перевірити, що JSON парситься

---

### Крок 1.4: Додати поля work_type та citation_style в модель (4-6 годин)

#### Задача 1.4.1: Створити міграцію Alembic

**Дії:**

1. Створити міграцію:
```bash
cd apps/api
alembic revision -m "add_work_type_and_citation_style_to_documents"
```

2. У файлі міграції:
```python
def upgrade():
    op.add_column('documents', sa.Column('work_type', sa.String(50), nullable=True))
    op.add_column('documents', sa.Column('citation_style', sa.String(50), nullable=True, server_default='apa'))

def downgrade():
    op.drop_column('documents', 'work_type')
    op.drop_column('documents', 'citation_style')
```

3. Оновити модель `Document`:
```python
work_type = Column(String(50), default="bachelor")  # bachelor, master, coursework
citation_style = Column(String(50), default="apa")  # apa, mla, chicago
```

4. Оновити схему `DocumentCreate`:
```python
work_type: Literal["bachelor", "master", "coursework"] = Field(default="bachelor")
citation_style: Literal["apa", "mla", "chicago"] = Field(default="apa")
```

**Тестування:**
- Запустити міграцію
- Створити документ з новими полями
- Перевірити, що дані зберігаються

---

### Результат Етапу 1:
✅ Експорт документів працює (.docx та .pdf)  
✅ RAG інтегрований у генерацію розділів  
✅ Промпти відповідають інструкції  
✅ Модель Document має всі необхідні поля

---

## 💳 ЕТАП 2: Система оплати та монетизація (1 тиждень)

**Пріоритет:** 🔴 ВИСОКО  
**Орієнтовний час:** 5-7 днів

### Крок 2.1: Вибір та налаштування платіжної системи (1 день)

#### Задача 2.1.1: Вибрати платіжну систему

**Варіанти:**
1. **Stripe** (рекомендовано)
   - ✅ Глобальна підтримка
   - ✅ Українські картки працюють
   - ✅ Добра документація
   - ⚠️ Комісія: 3.4% + ₴2.50 за транзакцію

2. **Fondy**
   - ✅ Українська система
   - ✅ Нижчі комісії для UA карток
   - ⚠️ Менша документація

**Рекомендація:** Stripe (краща документація та інтеграція)

---

#### Задача 2.1.2: Встановити Stripe SDK

```bash
cd apps/api
pip install stripe
# Додати в requirements.txt: stripe>=7.0.0
```

---

### Крок 2.2: Створити модель Payment (4-6 годин)

#### Задача 2.2.1: Створити модель та міграцію

**Файл:** `apps/api/app/models/payment.py` (новий файл)

```python
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Numeric, Boolean
from sqlalchemy.sql import func
from app.core.database import Base

class Payment(Base):
    """Payment model"""
    __tablename__ = "payments"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=True)
    
    # Stripe дані
    stripe_payment_intent_id = Column(String(255), unique=True, nullable=True)
    stripe_customer_id = Column(String(255), nullable=True)
    
    # Сума та валюта
    amount = Column(Numeric(10, 2), nullable=False)  # Сума в доларах
    currency = Column(String(3), default="USD")
    
    # Статус
    status = Column(String(50), default="pending")  # pending, succeeded, failed, refunded
    payment_method = Column(String(50))  # card, bank_transfer, etc.
    
    # Метадані
    description = Column(String(500))
    metadata = Column(JSON)  # Додаткові дані
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    paid_at = Column(DateTime(timezone=True), nullable=True)
```

**Міграція:**
```bash
alembic revision -m "create_payments_table"
```

---

### Крок 2.3: Створити PaymentService (1 день)

#### Задача 2.3.1: Реалізувати створення платежу

**Файл:** `apps/api/app/services/payment_service.py` (новий файл)

```python
import stripe
from app.core.config import settings
from app.models.payment import Payment
from app.models.document import Document

class PaymentService:
    def __init__(self, db: AsyncSession):
        self.db = db
        stripe.api_key = settings.STRIPE_SECRET_KEY  # Додати в config.py
    
    async def create_payment(
        self,
        user_id: int,
        document_id: int,
        amount: float,
        currency: str = "USD"
    ) -> dict[str, Any]:
        """Створює платіж через Stripe"""
        
        # Отримати документ
        document = await self._get_document(document_id, user_id)
        
        # Створити Payment Intent в Stripe
        intent = stripe.PaymentIntent.create(
            amount=int(amount * 100),  # Stripe використовує центи
            currency=currency.lower(),
            metadata={
                "user_id": user_id,
                "document_id": document_id,
                "document_title": document.title
            },
            description=f"Payment for document: {document.title}"
        )
        
        # Зберегти в БД
        payment = Payment(
            user_id=user_id,
            document_id=document_id,
            stripe_payment_intent_id=intent.id,
            amount=amount,
            currency=currency,
            status="pending",
            description=f"Payment for document: {document.title}"
        )
        self.db.add(payment)
        await self.db.commit()
        
        return {
            "payment_id": payment.id,
            "client_secret": intent.client_secret,
            "amount": amount,
            "currency": currency
        }
```

---

#### Задача 2.3.2: Реалізувати webhook handler

**Файл:** `apps/api/app/api/v1/endpoints/payment.py` (новий файл)

```python
from fastapi import APIRouter, Request, Header, HTTPException
import stripe
from app.core.config import settings

router = APIRouter()

@router.post("/webhook")
async def stripe_webhook(
    request: Request,
    stripe_signature: str = Header(None)
):
    """Обробка webhook від Stripe"""
    payload = await request.body()
    
    try:
        event = stripe.Webhook.construct_event(
            payload, 
            stripe_signature, 
            settings.STRIPE_WEBHOOK_SECRET
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid signature")
    
    # Обробити подію
    if event.type == "payment_intent.succeeded":
        payment_intent = event.data.object
        # Оновити статус платежу в БД
        await update_payment_status(payment_intent.id, "succeeded")
        # Оновити статус документа
        await unlock_document(payment_intent.metadata.document_id)
    
    return {"status": "ok"}
```

---

### Крок 2.4: Створити frontend інтеграцію (1 день)

#### Задача 2.4.1: Додати Stripe Elements на сторінку оплати

**Файл:** `apps/web/app/payment/page.tsx` (новий файл)

```typescript
'use client'

import { loadStripe } from '@stripe/stripe-js'
import { Elements, CardElement, useStripe, useElements } from '@stripe/react-stripe-js'
import { useState } from 'react'

const stripePromise = loadStripe(process.env.NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY!)

export default function PaymentPage({ params }: { params: { documentId: string } }) {
  const [amount, setAmount] = useState(0)
  const [loading, setLoading] = useState(false)
  
  // Отримати суму з API
  useEffect(() => {
    fetch(`/api/v1/payment/calculate/${params.documentId}`)
      .then(res => res.json())
      .then(data => setAmount(data.amount))
  }, [])
  
  return (
    <Elements stripe={stripePromise}>
      <PaymentForm documentId={params.documentId} amount={amount} />
    </Elements>
  )
}
```

---

### Результат Етапу 2:
✅ Платіжна система інтегрована  
✅ Користувачі можуть оплачувати генерацію  
✅ Webhook обробляє успішні платежі  
✅ Документи розблоковуються після оплати

---

## 🔍 ЕТАП 3: Перевірка плагіату та якість (3-4 дні)

**Пріоритет:** 🟡 СЕРЕДНЬО  
**Орієнтовний час:** 3-4 дні

### Крок 3.1: Вибір сервісу перевірки плагіату (4-6 годин)

**Варіанти:**
1. **Copyleaks** (рекомендовано)
   - ✅ API доступний
   - ✅ Хороша документація
   - ⚠️ Платний (≈ $10 за 100 перевірок)

2. **PlagiarismSearch**
   - ✅ Дешевший
   - ⚠️ Менша документація

**Рекомендація:** Copyleaks (краща інтеграція)

---

### Крок 3.2: Створити PlagiarismService (1 день)

**Файл:** `apps/api/app/services/plagiarism_service.py` (новий файл)

```python
import httpx
from app.core.config import settings

class PlagiarismService:
    def __init__(self):
        self.api_key = settings.COPYLEAKS_API_KEY
        self.base_url = "https://api.copyleaks.com/v3"
    
    async def check_plagiarism(self, text: str, document_id: int) -> dict:
        """Перевіряє текст на плагіат"""
        # 1. Створити scan
        # 2. Дочекатися результату
        # 3. Повернути звіт
        pass
```

---

### Крок 3.3: Додати endpoint та інтеграцію (1 день)

**Файл:** `apps/api/app/api/v1/endpoints/documents.py`

Додати:
```python
@router.post("/{document_id}/plagiarism/check")
async def check_plagiarism(...):
    """Перевірити документ на плагіат"""
    pass
```

---

### Результат Етапу 3:
✅ Перевірка плагіату працює  
✅ Звіти зберігаються в БД  
✅ Frontend показує результати

---

## ✨ ЕТАП 4: Покращення та полірування (3-4 дні)

**Пріоритет:** 🟡 СЕРЕДНЬО  
**Орієнтовний час:** 3-4 дні

### Крок 4.1: Виправити frontend інтеграцію (1 день)

#### Задача 4.1.1: Оновити GenerateSectionForm

**Файл:** `apps/web/components/dashboard/GenerateSectionForm.tsx`

**Дії:**
1. Використати правильний API URL
2. Додати authentication header
3. Додати обробку помилок
4. Додати поля work_type та citation_style

---

#### Задача 4.1.2: Оновити AuthProvider

**Файл:** `apps/web/components/providers/AuthProvider.tsx`

**Дії:**
1. Перевіряти токен через `/api/v1/auth/me`
2. Додати refresh token логіку

---

#### Задача 4.1.3: Заповнити Dashboard компоненти реальними даними

**Файли:**
- `DocumentsList.tsx`
- `StatsOverview.tsx`
- `RecentActivity.tsx`

---

### Крок 4.2: Додати валідацію цитат (4-6 годин)

#### Задача 4.2.1: Реалізувати `validate_citations()`

**Файл:** `apps/api/app/services/ai_pipeline/citation_validator.py` (новий файл)

```python
import re
from typing import List, Dict

def validate_citations(text: str, sources: List[Dict]) -> bool:
    """Перевіряє, чи всі цитати в тексті є у списку джерел"""
    # Витягнути всі цитати
    citations = re.findall(r'\(([A-Z][a-z]+(?:\s+et\s+al\.)?),\s*(\d{4})\)', text)
    
    # Створити список валідних цитат
    valid_citations = [
        (source['authors'][0]['name'].split()[-1], str(source['year']))
        for source in sources
    ]
    
    # Перевірити кожну цитату
    for author, year in citations:
        author = author.replace(" et al.", "")
        if (author, year) not in valid_citations:
            return False
    
    return True
```

---

### Крок 4.3: Налаштувати email сервіс (4-6 годин)

#### Задача 4.3.1: Інтегрувати SMTP

**Файл:** `apps/api/app/services/email_service.py` (новий файл)

Використати `fastapi-mail` (вже встановлено)

---

### Результат Етапу 4:
✅ Frontend повністю інтегрований  
✅ Валідація цитат працює  
✅ Email сервіс налаштований

---

## 🧪 ЕТАП 5: Тестування та підготовка до production (2-3 дні)

**Пріоритет:** 🔴 ВИСОКО  
**Орієнтовний час:** 2-3 дні

### Крок 5.1: Написати інтеграційні тести (1 день)

**Дії:**
1. Тести для експорту документів
2. Тести для платежної системи (з моками)
3. Тести для перевірки плагіату (з моками)
4. E2E тести основного workflow

---

### Крок 5.2: Налаштування production environment (1 день)

**Дії:**
1. Оновити `.env.example` з усіма необхідними змінними
2. Перевірити docker-compose.prod.yml
3. Налаштувати SSL сертифікати
4. Налаштувати моніторинг

---

### Крок 5.3: Документація та deployment guide (4-6 годин)

**Дії:**
1. Оновити README.md
2. Створити DEPLOYMENT.md
3. Додати API документацію
4. Створити user guide

---

### Результат Етапу 5:
✅ Всі тести проходять  
✅ Production environment готовий  
✅ Документація оновлена

---

## 📊 Загальний Timeline

| Етап | Час | Статус |
|------|-----|--------|
| Етап 0: Критичні баги | 2-3 дні | ⏳ Потрібно |
| Етап 1: Базова функціональність | 1 тиждень | ⏳ Потрібно |
| Етап 2: Система оплати | 1 тиждень | ⏳ Потрібно |
| Етап 3: Перевірка плагіату | 3-4 дні | ⏳ Потрібно |
| Етап 4: Покращення | 3-4 дні | ⏳ Потрібно |
| Етап 5: Тестування | 2-3 дні | ⏳ Потрібно |
| **Всього** | **3-4 тижні** | |

---

## 🎯 Критичні шляхи

**Мінімальний MVP (без оплати та плагіату):**
1. Етап 0 (2-3 дні)
2. Етап 1 (1 тиждень)
3. Етап 4 (частково, 1-2 дні)
4. Етап 5 (2-3 дні)

**Час:** ~2 тижні

**Повний MVP:**
- Всі етапи (3-4 тижні)

---

## 📝 Чек-лист готовності до production

- [ ] Всі критичні баги виправлені
- [ ] Експорт документів працює
- [ ] Система оплати інтегрована та протестована
- [ ] Перевірка плагіату працює
- [ ] Frontend повністю інтегрований
- [ ] Email сервіс налаштований
- [ ] Всі тести проходять
- [ ] Production environment налаштований
- [ ] Документація оновлена
- [ ] Моніторинг налаштований
- [ ] Backup стратегія реалізована

---

**Останнє оновлення:** 31 січня 2025  
**Версія плану:** 1.0

