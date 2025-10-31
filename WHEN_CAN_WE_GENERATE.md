# Коли ми зможемо генерувати роботи?

**Коротка відповідь:** ✅ **Вже зараз!** Вся функціональність реалізована. Потрібно лише налаштувати середовище та додати API ключі.

---

## ✅ Поточний статус

### Що вже готово:
- ✅ **Backend API** — повністю реалізований
  - Ендпоінти для генерації структури та розділів
  - Інтеграція з OpenAI та Anthropic
  - Сервіси для управління документами
  - Аутентифікація користувачів
  
- ✅ **Frontend** — повністю реалізований
  - Dashboard для створення документів
  - Форми генерації
  - Перегляд результатів
  
- ✅ **Інфраструктура** — налаштована
  - Docker Compose конфігурація
  - База даних PostgreSQL
  - Redis для кешування
  - MinIO для зберігання файлів

---

## 🚀 Швидкий старт (за 3 кроки)

### Крок 1: Налаштувати середовище

**Варіант А: Docker (рекомендовано)**
```bash
cd infra/docker
docker-compose up -d postgres redis minio
```

**Варіант Б: Локальна розробка**
```bash
# Використати скрипт налаштування
./setup-dev.sh
```

### Крок 2: Додати API ключі

Створити файл `apps/api/.env` з наступним вмістом:
```env
# Database
DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5432/ai_thesis_platform

# Security
SECRET_KEY=your-secret-key-min-32-chars
JWT_SECRET=your-jwt-secret-key

# AI Providers (обов'язково додати хоча б один!)
OPENAI_API_KEY=sk-your-openai-api-key-here
# АБО
ANTHROPIC_API_KEY=sk-ant-your-anthropic-api-key-here

# Redis
REDIS_URL=redis://localhost:6379

# MinIO
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_BUCKET=ai-thesis-documents
MINIO_SECURE=false

# Environment
ENVIRONMENT=development
DEBUG=true
```

**🔑 Де отримати API ключі:**
- **OpenAI:** https://platform.openai.com/api-keys
- **Anthropic:** https://console.anthropic.com/settings/keys

### Крок 3: Запустити сервіси

**Backend:**
```bash
cd apps/api
source venv/bin/activate  # або venv\Scripts\activate на Windows
uvicorn main:app --reload
```

**Frontend:**
```bash
cd apps/web
npm install  # якщо ще не встановлено
npm run dev
```

---

## 📋 Процес генерації

### Після налаштування ви зможете:

1. **Зареєструватися/увійти** через magic link
2. **Створити документ:**
   - Вказати тему дипломної роботи
   - Вибрати мову (en/uk/ru)
   - Вказати цільову кількість сторінок
   - Вибрати AI провайдера (OpenAI або Anthropic)
   - Вибрати модель (gpt-4, claude-3-5-sonnet, тощо)

3. **Згенерувати структуру:**
   - API: `POST /api/v1/generate/outline`
   - AI створить детальний план з розділами та підрозділами

4. **Генерувати розділи по черзі:**
   - API: `POST /api/v1/generate/section`
   - Для кожного розділу в структурі можна згенерувати контент
   - AI пише академічний текст з цитатами та структурою

5. **Експортувати результат:**
   - API: `GET /api/v1/documents/{id}/export/docx` або `/export/pdf`
   - Отримати готовий документ у Word або PDF

---

## ⚠️ Вимоги для генерації

### Обов'язкові:
1. ✅ **API ключ** — хоча б один (OpenAI АБО Anthropic)
2. ✅ **База даних** — PostgreSQL запущена
3. ✅ **Redis** — для rate limiting (опціонально, може працювати без нього)
4. ✅ **MinIO** — для зберігання експортованих файлів

### Опціональні (працюють з моками/заглушками):
- Email сервіс (для magic links — можна тестувати через логи)
- Sentry (моніторинг помилок)

---

## 🔍 Перевірка готовності

### Перевірити, що все працює:

1. **Health Check:**
   ```bash
   curl http://localhost:8000/health
   ```
   Має повернути: `{"status": "healthy", ...}`

2. **Перевірити API ключі:**
   ```bash
   # В backend логах після запуску не має бути помилок про відсутність API ключів
   # Якщо ключі встановлені правильно — помилок не буде
   ```

3. **Тестовий запит генерації (після аутентифікації):**
   ```bash
   # 1. Створити документ
   POST /api/v1/documents
   {
     "title": "Test Thesis",
     "topic": "Artificial Intelligence in Education",
     "language": "en",
     "target_pages": 10
   }
   
   # 2. Згенерувати структуру
   POST /api/v1/generate/outline
   {
     "document_id": 1
   }
   ```

---

## 💰 Вартість генерації

**Орієнтовні витрати на API:**

| Провайдер | Модель | Приблизна вартість на 10-сторінкову роботу |
|-----------|--------|--------------------------------------------|
| OpenAI | GPT-4 | ~$2-5 USD |
| OpenAI | GPT-4 Turbo | ~$1-3 USD |
| OpenAI | GPT-3.5 Turbo | ~$0.50-1 USD |
| Anthropic | Claude 3.5 Sonnet | ~$2-4 USD |
| Anthropic | Claude 3 Opus | ~$10-15 USD |

**Примітка:** Вартість залежить від складності теми, кількості токенів та моделі.

---

## 🐛 Відомі обмеження

### Поточні:
1. ⚠️ **Email сервіс** — magic links поки не надсилаються (потрібна інтеграція SMTP)
   - **Обхід:** Перевірка токенів через логи або тестовий ендпоінт
   
2. ⚠️ **RAG система** — базовий функціонал (пошук джерел через Semantic Scholar)
   - Працює, але може потребувати налаштування API ключа Semantic Scholar

3. ⚠️ **Експорт PDF** — потребує WeasyPrint або подібну бібліотеку
   - Може потребувати додаткових системних залежностей

---

## 📅 Планована функціональність

### Що ще в розробці:
- 🔄 Покращена система цитат з автоматичним форматуванням
- 🔄 Розширена RAG система з векторним пошуком
- 🔄 Колaboration (спільна робота над документами)
- 🔄 Шаблони документів
- 🔄 Покращена система експорту

---

## ✅ Висновок

**Відповідь:** Генерувати документи можна **вже зараз**, якщо:
1. ✅ Додано API ключ (OpenAI або Anthropic)
2. ✅ Запущені сервіси (PostgreSQL, Redis, MinIO)
3. ✅ Backend та Frontend запущені

**Час на налаштування:** ~10-15 хвилин
- Встановлення Docker сервісів: ~5 хв
- Додавання API ключів: ~2 хв
- Запуск додатків: ~3-5 хв

**Перша генерація:** ~30 секунд - 2 хвилини (залежить від моделі)

---

## 🆘 Допомога

### Якщо щось не працює:

1. **Перевірити логи:**
   ```bash
   # Backend логи
   tail -f apps/api/logs/app.log
   
   # Docker логи
   docker-compose logs -f api
   ```

2. **Перевірити з'єднання з БД:**
   ```bash
   docker-compose exec postgres psql -U postgres -d ai_thesis_platform
   ```

3. **Перевірити Redis:**
   ```bash
   docker-compose exec redis redis-cli ping
   ```

4. **Тестувати API ключі:**
   - Перевірити формат (OpenAI: `sk-...`, Anthropic: `sk-ant-...`)
   - Перевірити баланс на акаунті провайдера
   - Перевірити обмеження rate limits

---

**Останнє оновлення:** 31 жовтня 2025  
**Статус:** ✅ Готово до використання


