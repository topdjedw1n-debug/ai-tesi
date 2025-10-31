# Звіт про дослідження помилок CI: SQLite pool params та MyPy explicit-package-bases

## Дата створення
2025-01-XX (поточна сесія)

## Початкова проблема

### Помилка 1: SQLite pool_size/max_overflow TypeError
```
TypeError: Invalid argument(s) 'pool_size', 'max_overflow' sent to create_engine(), 
using configuration SQLiteDialect_aiosqlite/NullPool/Engine. 
Please check that the keyword arguments are appropriate for this combination of components.
```

**Файли, де виникала:**
- `apps/api/tests/test_auth_no_token.py`
- `apps/api/tests/test_health_endpoint.py`
- `apps/api/tests/test_rate_limit_init.py`

**Джоб:** `Smoke Tests (Pytest)`

### Помилка 2: MyPy explicit-package-bases
```
mypy: error: Can only use --explicit-package-bases with --namespace-packages, 
since otherwise examining __init__.py's is sufficient to determine module names for files
```

**Джоб:** `Typecheck (MyPy)`

---

## Хронологія спроб виправлення

### Спроба 1: Додавання exception chaining (B904)
**Файл:** `apps/api/app/core/config.py`, `apps/api/app/core/dependencies.py`
- Додано `from e` до `raise` statements
- **Результат:** Не вирішило проблему SQLite/MyPy

### Спроба 2: Умовна логіка для SQLite в database.py
**Файл:** `apps/api/app/core/database.py`

**Зміни:**
```python
# Перевірка is_sqlite перед створенням engine
is_sqlite = "sqlite" in db_url.lower()

if is_sqlite:
    engine_kwargs = {
        "echo": False,
        "future": True,
    }
else:
    engine_kwargs = {
        "echo": False,
        "pool_pre_ping": True,
        "pool_size": 20,
        "max_overflow": 40,
        # ...
    }
```

**Проблема:** Engine все одно створювався з pool params для SQLite

**Причина:**
- `os.environ.get("DATABASE_URL")` перевірявся під час імпорту модуля
- Якщо `DATABASE_URL` не встановлений на момент імпорту, використовувався `settings.DATABASE_URL` (який може бути PostgreSQL)
- `is_sqlite` перевірка не спрацьовувала правильно

### Спроба 3: Пріоритет os.environ над settings
**Файл:** `apps/api/app/core/database.py`

**Зміни:**
```python
def _create_engine():
    # CRITICAL: ALWAYS check os.environ FIRST
    db_url = os.environ.get("DATABASE_URL")
    
    # Only import settings if DATABASE_URL not in environment
    if not db_url:
        from app.core.config import settings
        db_url = getattr(settings, 'DATABASE_URL', None) or ""
```

**Результат:** Помилка продовжувала виникати

**Причина:** 
- Під час імпорту `database.py` через `from main import app`, модуль імпортується ДО того, як тести встановлюють `os.environ`
- Навіть з `setdefault`, якщо модуль вже імпортований, значення не оновлюється

### Спроба 4: Lazy initialization через __getattr__
**Файл:** `apps/api/app/core/database.py`

**Зміни:**
```python
# Global engine instance (lazy initialized)
_engine: AsyncEngine | None = None

def _create_engine_safe() -> AsyncEngine:
    global _engine
    if _engine is not None:
        return _engine
    # ... створення engine
    return _engine

def get_engine() -> AsyncEngine:
    return _create_engine_safe()

# Module-level __getattr__ for lazy engine access (Python 3.7+)
def __getattr__(name: str) -> Any:
    if name == 'engine':
        return get_engine()
    if name == 'AsyncSessionLocal':
        # lazy init AsyncSessionLocal
    raise AttributeError(...)
```

**Очікування:** Engine створюється тільки при доступі до `database.engine`, не при імпорті

**Результат:** Помилка все ще виникала

**Причина:**
- Python `__getattr__` викликається при `from module import attr`, але можливо якийсь код викликав `engine` під час імпорту
- Або `AsyncSessionLocal` викликав `get_engine()` під час імпорту через `get_db()`

### Спроба 5: Додавання conftest.py
**Файл:** `apps/api/tests/conftest.py` (новий файл)

**Зміни:**
```python
import os

# Set environment variables BEFORE any test imports
os.environ.setdefault("SECRET_KEY", "...")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test.db")
# ...
```

**Очікування:** `conftest.py` виконується pytest ПЕРЕД будь-якими імпортами

**Результат:** Помилка продовжувала виникати

### Спроба 6: Try-except safety net
**Файл:** `apps/api/app/core/database.py`

**Зміни:**
```python
# SAFETY NET: Try creating engine, if it fails with unsupported params, retry without them
try:
    _engine = create_async_engine(db_url, **engine_kwargs)
except (TypeError, ValueError) as e:
    error_msg = str(e).lower()
    if 'pool_size' in error_msg or 'max_overflow' in error_msg or 'sqlite' in error_msg:
        # Retry without pool parameters
        safe_kwargs = {k: v for k, v in engine_kwargs.items() 
                      if k not in {'pool_size', 'max_overflow', 'pool_pre_ping', 'pool_recycle', 'connect_args'}}
        _engine = create_async_engine(db_url, **safe_kwargs)
```

**Результат:** Помилка все ще виникала на етапі collection, не виконання

### Спроба 7: Подвійна перевірка та фільтрація
**Файл:** `apps/api/app/core/database.py`

**Зміни:**
```python
# DOUBLE-CHECK: If somehow pool params got through for SQLite, filter them out
if is_sqlite:
    sqlite_unsupported = {'pool_size', 'max_overflow', 'pool_pre_ping', 'pool_recycle', 'connect_args'}
    engine_kwargs = {k: v for k, v in engine_kwargs.items() if k not in sqlite_unsupported}
```

**Результат:** Помилка продовжувала виникати

---

## MyPy explicit-package-bases помилка

### Спроба 1: Видалення explicit_package_bases з mypy.ini
**Файл:** `apps/api/mypy.ini`
- Видалено рядок `explicit_package_bases = true` (якщо він був)

**Результат:** Помилка продовжувала виникати

### Спроба 2: Видалення --no-explicit-package-bases з CI
**Файл:** `.github/workflows/ci.yml`
- Видалено флаг `--no-explicit-package-bases` з команди mypy

**Результат:** Помилка продовжувала виникати

### Спроба 3: Явне встановлення explicit_package_bases = false
**Файли:** `apps/api/mypy.ini`, `apps/api/pyproject.toml`

**Зміни:**
```ini
[mypy]
explicit_package_bases = false
```

**Результат:** Не відомо (не було можливості перевірити)

---

## Поточний стан коду

### Файл: `apps/api/app/core/database.py`

**Ключові частини:**

1. **Lazy initialization:**
```python
_engine: AsyncEngine | None = None
_events_registered = False
_AsyncSessionLocal: async_sessionmaker[AsyncSession] | None = None

def _create_engine_safe() -> AsyncEngine:
    global _engine, _events_registered
    if _engine is not None:
        return _engine
    
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        from app.core.config import settings  # noqa: E402
        db_url = getattr(settings, 'DATABASE_URL', None) or ""
    
    if not db_url:
        db_url = "sqlite+aiosqlite:///:memory:"
    
    is_sqlite = "sqlite" in db_url.lower()
    
    engine_kwargs: dict[str, Any] = {
        "echo": False,
        "future": True,
    }
    
    if is_sqlite:
        logger.debug(f"Creating SQLite engine: {db_url[:50]}...")
    else:
        engine_kwargs.update({
            "pool_pre_ping": True,
            "pool_size": 20,
            "max_overflow": 40,
            "pool_recycle": 3600,
            "connect_args": {...},
        })
    
    # DOUBLE-CHECK: Filter out SQLite-unsupported params
    if is_sqlite:
        sqlite_unsupported = {'pool_size', 'max_overflow', 'pool_pre_ping', 'pool_recycle', 'connect_args'}
        engine_kwargs = {k: v for k, v in engine_kwargs.items() if k not in sqlite_unsupported}
    
    # SAFETY NET: Try-except with retry
    try:
        _engine = create_async_engine(db_url, **engine_kwargs)
    except (TypeError, ValueError) as e:
        error_msg = str(e).lower()
        if 'pool_size' in error_msg or 'max_overflow' in error_msg or 'sqlite' in error_msg:
            logger.warning(f"Engine creation failed, retrying without pool params: {e}")
            safe_kwargs = {k: v for k, v in engine_kwargs.items() 
                          if k not in {'pool_size', 'max_overflow', 'pool_pre_ping', 'pool_recycle', 'connect_args'}}
            _engine = create_async_engine(db_url, **safe_kwargs)
        else:
            raise
    
    return _engine

def __getattr__(name: str) -> Any:
    if name == 'engine':
        return get_engine()
    if name == 'AsyncSessionLocal':
        global _AsyncSessionLocal
        if _AsyncSessionLocal is None:
            _AsyncSessionLocal = async_sessionmaker(
                get_engine(),
                class_=AsyncSession,
                expire_on_commit=False,
                autoflush=False,
                autocommit=False,
            )
        return _AsyncSessionLocal
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
```

2. **Використання:**
```python
async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:  # type: ignore[name-defined]
        # ...

async def init_db():
    async with engine.begin() as conn:  # type: ignore[name-defined]
        # ...
```

### Файл: `apps/api/tests/conftest.py` (новий)

```python
import os

os.environ.setdefault("SECRET_KEY", "test-secret-key-minimum-32-chars-long-1234567890")
os.environ.setdefault("JWT_SECRET", os.environ["SECRET_KEY"])
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test.db")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("DISABLE_RATE_LIMIT", "true")
```

### Файл: `.github/workflows/ci.yml`

**Smoke Tests job:**
```yaml
- name: Pytest Smoke Tests
  working-directory: apps/api
  env:
    SECRET_KEY: test-secret-key-minimum-32-chars-long-1234567890
    JWT_SECRET: test-jwt-secret-minimum-32-chars-long-1234567890
    DATABASE_URL: sqlite+aiosqlite:///./test.db
    REDIS_URL: redis://localhost:6379/0
    ENVIRONMENT: test
    DISABLE_RATE_LIMIT: "true"
  run: |
    pytest tests -q
```

**Typecheck job:**
```yaml
- name: MyPy Type Check
  working-directory: apps/api
  run: |
    mypy . --config-file mypy.ini
```

### Файл: `apps/api/mypy.ini`

```ini
[mypy]
python_version = 3.11
explicit_package_bases = false
# ... інші налаштування
```

### Файл: `apps/api/pyproject.toml`

```toml
[tool.mypy]
python_version = "3.11"
explicit_package_bases = false
# ... інші налаштування
```

---

## Аналіз проблеми

### Чому не працює:

1. **Порядок імпортів:**
   - Коли pytest імпортує `from main import app`, це викликає ланцюжок імпортів:
     - `main.py` → `from app.core.database import init_db`
     - `database.py` імпортується і виконується код модуля
   - Навіть з `__getattr__`, якщо десь у коді є прямий доступ до `engine` або `AsyncSessionLocal` під час імпорту, це викликає створення engine

2. **os.environ vs Settings:**
   - Якщо `database.py` імпортується ДО встановлення `os.environ["DATABASE_URL"]` в тестах
   - `os.environ.get("DATABASE_URL")` повертає `None`
   - Використовується `settings.DATABASE_URL`, який може бути `None` або PostgreSQL URL
   - Якщо `settings.DATABASE_URL = None`, використовується fallback `sqlite+aiosqlite:///:memory:`, але це може відбуватися занадто пізно

3. **conftest.py виконання:**
   - `conftest.py` виконується pytest, але можливо не настільки рано, щоб встановити env vars перед імпортом `main.py`
   - Або якийсь інший код імпортує `database.py` раніше

4. **Try-except не спрацьовує:**
   - Помилка виникає на етапі **collection** (коли pytest збирає тести), а не на етапі виконання
   - Якщо помилка виникає під час імпорту модуля, try-except не може її перехопити, бо помилка виникає ДО того, як функція викликається

---

## Можливі рішення (не спробовані)

### Варіант A: Використання pytest-env або pytest.ini
```ini
# pytest.ini
[pytest]
env =
    DATABASE_URL = sqlite+aiosqlite:///./test.db
    SECRET_KEY = test-secret-key-minimum-32-chars-long-1234567890
```

### Варіант B: Встановлення env vars у CI workflow ПЕРЕД командою pytest
```yaml
- name: Set test environment
  run: |
    export DATABASE_URL=sqlite+aiosqlite:///./test.db
    export SECRET_KEY=test-secret-key-minimum-32-chars-long-1234567890
    # ...

- name: Pytest Smoke Tests
  run: pytest tests -q
```

### Варіант C: Використання pytest fixtures для мокування database
```python
@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test.db"
```

### Варіант D: Перезавантаження модуля database після встановлення env vars
```python
import importlib
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test.db"
import app.core.database
importlib.reload(app.core.database)
```

### Варіант E: Використання SQLAlchemy URL object для перевірки діалекту
```python
from sqlalchemy.engine.url import make_url
url = make_url(db_url)
is_sqlite = url.drivername in ('sqlite', 'sqlite+pysqlite', 'sqlite+aiosqlite')
```

### Варіант F: Створення окремого тестового engine (не використовувати глобальний)
```python
# В тестах використовувати окремий engine для тестів
@pytest.fixture
def test_engine():
    return create_async_engine("sqlite+aiosqlite:///./test.db")
```

### Варіант G: Використання pytest-asyncio та перезапис database.py під час тестів
- Мокування або патчінг `create_async_engine` для тестів

### Варіант H: Винесення engine creation в окрему функцію, яка приймає URL як параметр
```python
def create_engine_from_url(db_url: str) -> AsyncEngine:
    # ... логіка з перевіркою SQLite
```

### Варіант I: Перевірка через URL parsing перед будь-яким створенням
```python
from urllib.parse import urlparse
parsed = urlparse(db_url)
is_sqlite = parsed.scheme.startswith('sqlite')
```

---

## MyPy explicit-package-bases - можливі рішення

### Варіант A: Додавання namespace_packages = true
```ini
[mypy]
explicit_package_bases = true
namespace_packages = true
```

### Варіант B: Використання --namespace-packages флагу в CI
```yaml
mypy . --config-file mypy.ini --namespace-packages
```

### Варіант C: Видалення всіх згадок explicit_package_bases
- Перевірити всі конфігураційні файли
- Можливо, встановлюється десь автоматично MyPy

---

## Структура проекту

```
apps/api/
├── app/
│   ├── core/
│   │   ├── database.py  # Основна проблема тут
│   │   ├── config.py
│   │   └── dependencies.py
│   ├── api/v1/endpoints/
│   └── models/
├── tests/
│   ├── conftest.py  # Новий файл
│   ├── test_auth_no_token.py
│   ├── test_health_endpoint.py
│   └── test_rate_limit_init.py
├── main.py
├── mypy.ini
├── pyproject.toml
└── requirements.txt
```

---

## Версії залежностей (з requirements.txt)

```
sqlalchemy[asyncio]==2.0.23
aiosqlite==0.19.0
pydantic>=2.0.1,<3.0.0
pytest==7.4.3
pytest-asyncio==0.21.1
```

---

## Ключові моменти для дослідження

1. **Чи викликається `_create_engine_safe()` під час імпорту?**
   - Додати `print()` або `logger.debug()` на початку функції
   - Перевірити стек викликів

2. **Що повертає `os.environ.get("DATABASE_URL")` на момент виклику?**
   - Додати логування значення
   - Перевірити, чи встановлений env var в CI

3. **Чи спрацьовує `__getattr__` при `from app.core.database import engine`?**
   - Python `__getattr__` викликається при доступі до атрибута через модуль
   - Але `from module import attr` може обійти `__getattr__` в деяких випадках

4. **Чи імпортується `database.py` до виконання `conftest.py`?**
   - Перевірити порядок виконання pytest

5. **Чи може `settings.DATABASE_URL` бути встановлений до того, як os.environ встановлюється?**
   - Pydantic Settings може читати з env vars автоматично
   - Можливо, конфлікт між pydantic-settings та os.environ

---

## Додаткові файли для перевірки

- `.github/workflows/ci.yml` - повна конфігурація CI
- `apps/api/app/core/config.py` - як налаштовується Settings
- `apps/api/main.py` - як імпортується database
- `apps/api/tests/test_*.py` - всі тестові файли

---

## Висновок

Основна проблема: **Engine створюється з неправильними параметрами під час імпорту модуля**, навіть з lazy initialization та всіма перевірками. Помилка виникає на етапі **collection** pytest, що означає, що вона виникає під час імпорту тестових модулів, а не під час їх виконання.

Можливі причини:
1. Якийсь код викликає `engine` або `AsyncSessionLocal` під час імпорту
2. Порядок імпортів не дозволяє встановити env vars на час
3. `conftest.py` виконується не настільки рано, як очікується
4. Проблема з Python `__getattr__` та імпортами

Рекомендація: Спробувати варіанти A, B, E або F з розділу "Можливі рішення".

