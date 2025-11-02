# Type Annotations Guide for TesiGo

## 📋 Правила Типізації

### 1. ВСІ публічні функції мають мати типи

```python
# ✅ Правильно
async def get_document(document_id: int, user_id: int) -> dict[str, Any]:
    """Get document by ID"""
    ...

# ❌ Неправильно
async def get_document(document_id, user_id):
    ...
```

### 2. ВСІ async функції мають мати return types

```python
# ✅ Правильно
async def create_document(data: dict[str, Any]) -> dict[str, Any]:
    ...

# ❌ Неправильно  
async def create_document(data):
    ...
```

### 3. Використовувати конкретні типи замість загальних

```python
# ✅ Правильно
def process_items(items: list[str]) -> dict[str, int]:
    ...

# ❌ Неправильно
def process_items(items) -> dict:
    ...
```

### 4. SQLAlchemy ORM Attributes

Для SQLAlchemy ORM атрибутів, які MyPy неправильно інтерпретує:

```python
# ✅ Правильно (використати type: ignore тільки якщо необхідно)
user.is_verified = True  # type: ignore[assignment]

# ✅ Краще - використати SQLAlchemy 2.0 typing
from sqlalchemy.orm import Mapped, mapped_column

class User(Base):
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
```

### 5. Optional Types

```python
# ✅ Правильно
from typing import Optional

def get_user(user_id: int | None) -> Optional[dict[str, Any]]:
    ...

# Або в Python 3.10+
def get_user(user_id: int | None) -> dict[str, Any] | None:
    ...
```

### 6. Dict Types

```python
# ✅ Правильно
from typing import Any

def process_data(data: dict[str, Any]) -> dict[str, int]:
    ...

# ❌ Неправильно
def process_data(data: dict) -> dict:
    ...
```

## 🔧 Common Patterns

### Service Methods

```python
from typing import Any
from sqlalchemy.ext.asyncio import AsyncSession

class DocumentService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
    
    async def create_document(
        self,
        user_id: int,
        title: str,
        topic: str
    ) -> dict[str, Any]:
        """Create a new document"""
        ...
```

### Endpoint Functions

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.models.auth import User

@router.post("/", response_model=DocumentResponse)
async def create_document(
    document: DocumentCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> DocumentResponse:
    """Create a new document"""
    ...
```

### Exception Handling

```python
from typing import NoReturn

def raise_not_found(message: str) -> NoReturn:
    """Raise NotFoundError"""
    raise NotFoundError(message)
```

## 🚫 Що НЕ Робити

### 1. Не використовувати `type: ignore` без причини

```python
# ❌ Погано
def bad_function(x):  # type: ignore
    ...

# ✅ Добре - виправити тип
def good_function(x: int) -> int:
    ...
```

### 2. Не залишати функції без типів

```python
# ❌ Погано
def process(data):
    ...

# ✅ Добре
def process(data: dict[str, Any]) -> dict[str, Any]:
    ...
```

### 3. Не використовувати `Any` без потреби

```python
# ❌ Погано
def process(data: Any) -> Any:
    ...

# ✅ Добре
def process(data: dict[str, Any]) -> dict[str, str]:
    ...
```

## 📝 Checklist для Додавання Типів

- [ ] Додано типи для всіх параметрів
- [ ] Додано return type
- [ ] Перевірено MyPy: `mypy app/ --config-file mypy.ini`
- [ ] Використано конкретні типи (не `Any` без потреби)
- [ ] SQLAlchemy атрибути оброблені правильно

## 🔗 Ресурси

- [Python Typing Documentation](https://docs.python.org/3/library/typing.html)
- [SQLAlchemy 2.0 Typing](https://docs.sqlalchemy.org/en/20/orm/extensions/mypy.html)
- [MyPy Documentation](https://mypy.readthedocs.io/)

