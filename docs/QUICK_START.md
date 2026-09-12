# Thesica — локальне середовище

Оновлено 04.09.2026 за поточною структурою репозиторію.
Команди нижче — інструкція; свіжий запуск нового середовища в межах
перепланування не виконувався.

Спочатку прочитати [бриф](AGENT_SYNC.md) і
[поточні задачі](PRE-RUN-001-TASKS.md). Локальна доступність застосунку
не означає його готовності до реальних замовлень.

## 1. Передумови

Потрібні Python 3.11, Node.js 20, npm, Docker із Docker Compose.
Працювати з наявним checkout; адресу репозиторію брати з його git remote,
а не з історичного прикладу.

Наведений режим: PostgreSQL, Redis та MinIO у Docker; API й web на хості.
Якщо локальні сервіси вже працюють, спочатку перевірити їхні порти й
середовище, не створювати другий набір і не скидати дані.

## 2. Інфраструктура

Із кореня репозиторію:

    docker compose -f infra/docker/docker-compose.yml up -d postgres redis minio
    docker compose -f infra/docker/docker-compose.yml run --rm minio-setup
    docker compose -f infra/docker/docker-compose.yml ps

Поточні локальні значення цього compose:

| Сервіс | Адреса / база |
|---|---|
| PostgreSQL | localhost:5432; база ai_thesis_platform, користувач postgres, локальний пароль password |
| Redis | localhost:6379 |
| MinIO | localhost:9000; консоль localhost:9001; локальні minioadmin/minioadmin |
| Bucket | ai-thesis-documents |

Це лише локальні значення з compose, не реквізити робочого сервера.

Для нової бази потрібна відповідна схема й міграції з apps/api/migrations.
Спочатку визначити початкову схему та вже застосовані зміни; не запускати
сліпо всі історичні SQL поверх існуючої бази. Код наразі очікує зміни
до 027_verified_source_pack.sql включно. Релізна процедура застосовує
лише 024–027 і не є ініціалізатором порожньої бази.

## 3. API

У apps/api створити окреме віртуальне середовище й установити залежності:

    python3.11 -m venv .venv
    source .venv/bin/activate
    python -m pip install -r requirements.txt

Наявний .env зберегти. Якщо його немає, взяти .env.example як початок,
а не як готовий релізний профіль: приклад містить інші назви локальної
бази/bucket та послаблені діагностичні налаштування.

Для описаного локального compose узгодити:

    DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5432/ai_thesis_platform
    REDIS_URL=redis://localhost:6379
    MINIO_ENDPOINT=localhost:9000
    MINIO_BUCKET=ai-thesis-documents
    MINIO_ACCESS_KEY=minioadmin
    MINIO_SECRET_KEY=minioadmin
    MINIO_SECURE=false
    ENVIRONMENT=development
    PUBLIC_REGISTRATION_ENABLED=false
    HUMANIZER_ENABLED=false
    AI_ENABLE_FALLBACK=false
    METHODOLOGY_REQUIRED_FOR_GENERATION=false

Налаштувати стабільні унікальні SECRET_KEY/JWT_SECRET та потрібні
провайдерські ключі. Не переносити приклади ключів у робоче середовище.
Для доказового прогону використовувати
[релізний профіль](setup/PRODUCTION_DEPLOYMENT_PLAN.md), а не послаблені
локальні значення.

Запуск із apps/api:

    python -m uvicorn main:app --reload --host 127.0.0.1 --port 8000

## 4. Web

У apps/web:

    npm ci

Наявний .env.local зберегти. За його відсутності використати .env.example
як довідку й створити .env.local із налаштуваннями локального API.
Файла .env.local.example у поточному репозиторії немає.

    NEXT_PUBLIC_API_URL=http://localhost:8000
    NEXT_PUBLIC_ENABLE_USER_PAYMENT_FLOW=false
    NEXT_PUBLIC_ENABLE_USER_REFUND_FLOW=false

    npm run dev

Відкрити http://localhost:3000. API health: http://localhost:8000/health.
Web health: http://localhost:3000/api/health.

## 5. Вхід і перший сценарій

Використовувати виданий внутрішній логін. Самореєстрація не є шляхом
внутрішнього пілота.

Скрипт scripts/create-managers.py може створити менеджерські логіни,
але повторний запуск змінює паролі наявних користувачів. Це окрема
операція підготовки локальних облікових записів, не healthcheck.
Він створює звичайного користувача, тому сам по собі не надає доступу
до адміністративної видачі; права Тані перевіряються в M0-02.

Перший безкоштовний сценарій перевірки UI — створити чернетку та
переглянути умови. Натискання запуску генерації може витрачати кошти
AI-провайдерів навіть у внутрішньому режимі без оплати замовлення.

## 6. Перевірки

У підготовленому тестовому середовищі apps/api:

    python -m pytest tests --asyncio-mode=auto -q

У apps/web:

    npm run lint
    npm run type-check
    npm run test -- --runInBand
    npm run build

Тест explicit draft → confirm → generate лежить у папці, яку звичайний
Jest пропускає. Запускати його окремо:

    npm test -- --runInBand --watch=false --testPathIgnorePatterns='/node_modules/|/.next/' --runTestsByPath __tests__/e2e/document-creation-flow.test.tsx

Цей тест перевіряє взаємодію компонентів із підміненими відповідями API;
він не заміняє реальний браузерний цикл чи Compilatio.

Для контейнерних перевірок використовувати поточний перевірений образ
і ізольовані тимчасові дані. Тести API створюють локальні тестові файли;
не запускати їх проти бойової бази або файлового сховища.

## 7. Типові розбіжності

- Порт зайнятий: спочатку визначити, який чинний процес його використовує.
- API не бачить базу: звірити схему URL, назву бази й середовище з compose.
- Файл не доступний: звірити MinIO endpoint, bucket і локальні ключі.
- Схема не відповідає коду: визначити відсутні міграції.
- Генерація не стартує: перевірити умови, доступи й профіль; не вимикати
  перевірки як спосіб отримати доказ готовності.

Подальша черга — [M0](PRE-RUN-001-TASKS.md).
