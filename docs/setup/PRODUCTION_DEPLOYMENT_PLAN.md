# План тестування та деплою на зовнішньому сервері

**Дата створення:** 31 жовтня 2025
**Оновлено:** 23 лютого 2026
**Статус:** 🟢 Active (Strict Go-Live)

> **Важливо:** Для актуального release-рішення використовуйте:
> - `docs/RELEASE_GO_NO_GO_2026-02-23.md`
> - `docs/MASTER_COMPLIANCE_MATRIX.md`
> - `docs/MVP_PLAN.md`

---

## 📅 Коли можемо тестувати на зовнішньому сервері?

### ✅ Поточний підхід (Strict Go-Live):
- Спочатку green mandatory gates (backend + web).
- Потім runtime smoke в prod-like Docker.
- Потім manual UI smoke sign-off.

### ⏱️ Орієнтовний час:
- **Підготовка до staging:** 2-4 години
- **Налаштування сервера:** 1-2 години
- **Деплой та первинне тестування:** 1-2 години
- **Повноцінне тестування:** 1-2 дні

**Загалом:** Можемо почати тестування на зовнішньому сервері **через 4-8 годин після початку підготовки**

---

## ✅ Поточний стан готовності

### Що вже готово:

#### Backend
- ✅ Dockerfile для production
- ✅ Health checks налаштовані
- ✅ Production конфігурація (`ENVIRONMENT=production`)
- ✅ Валідація production вимог (SECRET_KEY, DATABASE_URL, тощо)
- ✅ Безпека (rate limiting, CSRF, CORS, TrustedHost)
- ✅ Моніторинг (Prometheus metrics)
- ✅ Audit logging
- ✅ Structured error handling

#### Frontend
- ✅ Dockerfile для production
- ✅ Next.js production build налаштований
- ✅ Environment variables для production
- ✅ Health check endpoint

#### Інфраструктура
- ✅ `docker-compose.prod.yml` для production
- ✅ Налаштування для PostgreSQL, Redis, MinIO
- ✅ Скрипт `setup-prod.sh` для запуску

#### Безпека
- ✅ Валідація API ключів у production
- ✅ Перевірка SECRET_KEY
- ✅ CORS налаштування для production
- ✅ Rate limiting
- ✅ CSRF protection

---

## 🔧 Що потрібно зробити перед деплоєм

### 1. Актуальні pre-deploy дії (високий пріоритет)

#### ⚠️ Release gates
- [ ] `pytest tests/ -q` (backend)
- [ ] `npm run lint` (web)
- [ ] `npm run type-check` (web)
- [ ] `npm run test -- --runInBand` (web)
- [ ] `npm run build` (web)
- [ ] Runtime smoke (`scripts/runtime_smoke.sh`) у prod-like Docker

**Час:** ~30-60 хв після готового середовища

#### 🔧 Safety checks
- [ ] Переконатися, що kill-switch env flags явно задані для релізу:
  - `NEXT_PUBLIC_ENABLE_USER_PAYMENT_FLOW`
  - `NEXT_PUBLIC_ENABLE_USER_REFUND_FLOW`
- [ ] Перевірити відсутність backup/artefact/secret файлів у diff.
- [ ] Оновити release report і Go/No-Go статус.

### 2. Налаштування для production

#### 📝 Environment Variables
Потрібно створити `.env` файл на сервері з такими змінними:

```env
# Environment
ENVIRONMENT=production
DEBUG=false

# Database
DATABASE_URL=postgresql+asyncpg://user:password@host:5432/dbname
POSTGRES_DB=ai_thesis_platform
POSTGRES_USER=your_user
POSTGRES_PASSWORD=strong_password

# Security (ОБОВ'ЯЗКОВО!)
SECRET_KEY=generate-strong-random-key-min-32-chars
JWT_SECRET=generate-strong-random-key-min-32-chars
JWT_ISS=https://your-domain.com
JWT_AUD=https://your-domain.com

# CORS (ОБОВ'ЯЗКОВО!)
CORS_ALLOWED_ORIGINS=https://your-domain.com,https://www.your-domain.com

# AI Providers (хоча б один)
OPENAI_API_KEY=sk-your-openai-key
# АБО
ANTHROPIC_API_KEY=sk-ant-your-anthropic-key

# Redis
REDIS_URL=redis://redis:6379

# MinIO/S3 (ОБОВ'ЯЗКОВО змінити!)
MINIO_ENDPOINT=minio:9000
MINIO_ACCESS_KEY=your-secure-access-key
MINIO_SECRET_KEY=your-secure-secret-key-min-8-chars
MINIO_BUCKET=ai-thesis-documents
MINIO_SECURE=false

# Email (якщо планується використання)
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USER=your-email@example.com
SMTP_PASSWORD=your-smtp-password
SMTP_TLS=true
EMAILS_FROM_EMAIL=noreply@your-domain.com
EMAILS_FROM_NAME=AI Thesis Platform

# Monitoring (опціонально)
SENTRY_DSN=https://your-sentry-dsn
ENABLE_METRICS=true

# Rate Limiting
RATE_LIMIT_PER_MINUTE=60
RATE_LIMIT_MAGIC_LINK_PER_HOUR=3
DISABLE_RATE_LIMIT=false

# Next.js Frontend
NEXT_PUBLIC_API_URL=https://api.your-domain.com
```

**Час:** ~30 хвилин

#### 🔐 Генерація секретних ключів

```bash
# Генерація SECRET_KEY
python -c 'import secrets; print(secrets.token_urlsafe(48))'

# Генерація JWT_SECRET
python -c 'import secrets; print(secrets.token_urlsafe(48))'

# Генерація MinIO credentials
python -c 'import secrets; print(secrets.token_urlsafe(16))'
```

**Час:** ~5 хвилин

### 3. Серверні вимоги

#### Мінімальні вимоги:
- **CPU:** 2 cores
- **RAM:** 4GB
- **Disk:** 20GB SSD
- **OS:** Ubuntu 22.04 LTS або Debian 12 (рекомендовано)

#### Рекомендовані вимоги:
- **CPU:** 4 cores
- **RAM:** 8GB
- **Disk:** 50GB SSD
- **OS:** Ubuntu 22.04 LTS

#### Потрібне ПЗ:
- ✅ Docker 24.0+
- ✅ Docker Compose v2.0+
- ✅ Git
- ✅ Налаштований firewall (ufw або iptables)

**Час налаштування сервера:** ~1-2 години

### 4. Додаткові налаштування

#### 🌐 Domain & SSL
- [ ] Зареєструвати домен (наприклад: `ai-thesis.com`)
- [ ] Налаштувати DNS записи (A record до IP сервера)
- [ ] Налаштувати SSL сертифікат (Let's Encrypt через certbot)
- [ ] Налаштувати Nginx або Traefik як reverse proxy

**Час:** ~1 година

#### 🔒 Безпека сервера
- [ ] Налаштувати firewall (дозволити порти 80, 443, 22)
- [ ] Налаштувати SSH key-based authentication
- [ ] Відключити password authentication для SSH
- [ ] Налаштувати fail2ban для захисту від brute force
- [ ] Налаштувати автоматичні оновлення безпеки

**Час:** ~1 година

#### 📊 Моніторинг
- [ ] Налаштувати Prometheus exporter (якщо окремий сервер моніторингу)
- [ ] Налаштувати логування (ELK stack або подібне)
- [ ] Налаштувати алерти (якщо використовується Sentry)

**Час:** ~2-4 години (опціонально)

---

## 🚀 Кроки для деплою на staging сервер

### Крок 1: Підготовка сервера

```bash
# 1. Підключитися до сервера
ssh user@your-server-ip

# 2. Оновити систему
sudo apt update && sudo apt upgrade -y

# 3. Встановити Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# 4. Встановити Docker Compose
sudo apt install docker-compose-plugin -y

# 5. Додати користувача до групи docker
sudo usermod -aG docker $USER
# Потрібно вийти і зайти знову

# 6. Налаштувати firewall
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
```

**Час:** ~30 хвилин

### Крок 2: Клонування репозиторію

```bash
# 1. Клонувати репозиторій
git clone https://github.com/your-org/ai-thesis-platform.git
cd ai-thesis-platform

# 2. Перейти до production конфігурації
cd infra/docker
```

**Час:** ~5 хвилин

### Крок 3: Налаштування environment variables

```bash
# Створити .env файл
nano .env

# Вставити всі необхідні змінні (див. вище)
# Зберегти та вийти (Ctrl+O, Enter, Ctrl+X)
```

**Час:** ~15 хвилин

### Крок 4: Білд та запуск

```bash
# 1. Створити Docker images
cd ../../apps/api
docker build -t ai-thesis-api:latest .

cd ../web
docker build -t ai-thesis-web:latest .

# 2. Повернутися до docker директорії
cd ../../infra/docker

# 3. Запустити production stack
export API_IMAGE=ai-thesis-api:latest
export WEB_IMAGE=ai-thesis-web:latest
./setup-prod.sh
```

**Час:** ~15-30 хвилин (залежить від швидкості інтернету)

### Крок 5: Перевірка

```bash
# Перевірити статус контейнерів
docker compose -f docker-compose.prod.yml ps

# Перевірити логи
docker compose -f docker-compose.prod.yml logs api
docker compose -f docker-compose.prod.yml logs web

# Перевірити health check
curl http://localhost:8000/health
curl http://localhost:3000/api/health
```

**Час:** ~10 хвилин

### Крок 6: Налаштування Nginx (reverse proxy)

```bash
# Встановити Nginx
sudo apt install nginx -y

# Створити конфігурацію
sudo nano /etc/nginx/sites-available/ai-thesis
```

```nginx
# /etc/nginx/sites-available/ai-thesis
server {
    listen 80;
    server_name your-domain.com www.your-domain.com;

    # Frontend
    location / {
        proxy_pass http://localhost:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Backend API
    location /api {
        proxy_pass http://localhost:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Health check
    location /health {
        proxy_pass http://localhost:8000/health;
    }
}
```

```bash
# Активувати конфігурацію
sudo ln -s /etc/nginx/sites-available/ai-thesis /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx

# Налаштувати SSL (Let's Encrypt)
sudo apt install certbot python3-certbot-nginx -y
sudo certbot --nginx -d your-domain.com -d www.your-domain.com
```

**Час:** ~30 хвилин

---

## ✅ Чек-лист перед повноцінним тестуванням

### Підготовка
- [ ] Виправлено критичні баги (rate_limit.py, exceptions.py)
- [ ] Виправлено форматування коду
- [ ] Оновлено критичні вразливості
- [ ] Створено `.env` файл з усіма змінними
- [ ] Згенеровано сильні секретні ключі
- [ ] Налаштовано домен та DNS
- [ ] Налаштовано SSL сертифікат

### Сервер
- [ ] Docker та Docker Compose встановлено
- [ ] Firewall налаштовано
- [ ] SSH безпека налаштована
- [ ] Репозиторій склоновано
- [ ] Docker images збудовано
- [ ] Сервіси запущені та працюють

### Функціональність
- [ ] Health checks проходять
- [ ] Аутентифікація працює
- [ ] Створення документів працює
- [ ] Генерація структури працює
- [ ] Генерація розділів працює
- [ ] Експорт документів працює
- [ ] Rate limiting працює
- [ ] CORS працює правильно

### Безпека
- [ ] API ключі налаштовані
- [ ] SECRET_KEY не використовує placeholder
- [ ] MinIO credentials змінені з дефолтних
- [ ] CORS налаштований правильно
- [ ] Rate limiting активний
- [ ] SSL/TLS працює

---

## 🧪 План тестування на зовнішньому сервері

### Етап 1: Smoke Tests (1-2 години)

**Мета:** Перевірити базову функціональність

1. **Health Checks**
   ```bash
   curl https://your-domain.com/health
   curl https://your-domain.com/api/health
   ```

2. **Аутентифікація**
   - Запит magic link
   - Верифікація magic link
   - Отримання токену
   - Перевірка `/api/v1/auth/me`

3. **Створення документа**
   ```bash
   POST /api/v1/documents
   {
     "title": "Test Document",
     "topic": "AI in Education",
     "language": "en",
     "target_pages": 5
   }
   ```

4. **Генерація структури**
   ```bash
   POST /api/v1/generate/outline
   {
     "document_id": 1
   }
   ```

**Очікуваний результат:** Всі тести проходять успішно

---

### Етап 2: Функціональне тестування (4-8 годин)

**Мета:** Перевірити повний цикл генерації

1. **Повний цикл генерації**
   - Створити документ
   - Згенерувати структуру
   - Згенерувати 2-3 розділи
   - Експортувати в DOCX
   - Експортувати в PDF

2. **Різні сценарії**
   - Різні мови (en, uk, ru)
   - Різні AI провайдери (OpenAI, Anthropic)
   - Різні моделі (gpt-4, gpt-3.5-turbo, claude-3-5-sonnet)
   - Різні довжини документів (5, 10, 20 сторінок)

3. **Edge cases**
   - Довгі теми
   - Спеціальні символи
   - Великі додаткові вимоги
   - Множинні одночасні запити

**Очікуваний результат:** Всі сценарії працюють коректно

---

### Етап 3: Навантажувальне тестування (2-4 години)

**Мета:** Перевірити продуктивність та стабільність

1. **Rate Limiting**
   - Перевищити rate limits
   - Перевірити блокування

2. **Одночасні запити**
   - 10 користувачів одночасно
   - 50 запитів на хвилину
   - Довгі генерації (20+ сторінок)

3. **Навантаження на БД**
   - Створення багатьох документів
   - Читання великої кількості документів
   - Перевірка продуктивності запитів

4. **Навантаження на storage**
   - Створення великих файлів
   - Експорт багатьох документів
   - Перевірка MinIO продуктивності

**Очікуваний результат:** Система стабільно працює під навантаженням

---

### Етап 4: Тестування безпеки (2-4 години)

**Мета:** Перевірити всі аспекти безпеки

1. **Авторизація**
   - Доступ без токену → 401
   - Доступ з невалідним токеном → 401
   - Доступ до чужих документів → 403

2. **XSS та SQL Injection**
   - Спроби XSS атак
   - Спроби SQL injection
   - Перевірка санітизації

3. **CORS**
   - Запити з недозволених доменів → блокується
   - Запити з дозволених доменів → працює

4. **Rate Limiting**
   - Швидкі послідовні запити → блокується
   - Нормальне використання → працює

**Очікуваний результат:** Всі перевірки безпеки проходять

---

### Етап 5: Моніторинг та логування (1-2 години)

**Мета:** Перевірити моніторинг та логи

1. **Prometheus Metrics**
   ```bash
   curl https://your-domain.com/metrics
   ```
   - Перевірити наявність метрик
   - Перевірити правильність значень

2. **Audit Logging**
   ```bash
   # Перевірити audit.log
   docker compose -f docker-compose.prod.yml exec api tail -f logs/audit.log
   ```
   - Перевірити логування подій
   - Перевірити формат JSON

3. **Application Logs**
   ```bash
   docker compose -f docker-compose.prod.yml logs api
   ```
   - Перевірити помилки
   - Перевірити warnings

**Очікуваний результат:** Моніторинг та логування працюють правильно

---

### Етап 6: Тестування відновлення після збоїв (1-2 години)

**Мета:** Перевірити стійкість системи

1. **Перезапуск контейнерів**
   ```bash
   docker compose -f docker-compose.prod.yml restart api
   ```

2. **Перезапуск БД**
   ```bash
   docker compose -f docker-compose.prod.yml restart postgres
   ```

3. **Перезапуск Redis**
   ```bash
   docker compose -f docker-compose.prod.yml restart redis
   ```

4. **Повний перезапуск**
   ```bash
   docker compose -f docker-compose.prod.yml down
   docker compose -f docker-compose.prod.yml up -d
   ```

**Очікуваний результат:** Система коректно відновлюється

---

## 📊 Метрики успішності

### Мінімальні вимоги для production:
- ✅ Uptime > 99%
- ✅ Response time < 2 секунд для більшості запитів
- ✅ Success rate > 99.5%
- ✅ Rate limiting працює коректно
- ✅ Всі security checks проходять
- ✅ Логування та моніторинг працюють

---

## 🔄 Після тестування

### Якщо все працює:
1. ✅ Фіксуємо версію (git tag)
2. ✅ Документуємо конфігурацію
3. ✅ Налаштовуємо автоматичні backup
4. ✅ Налаштовуємо моніторинг та алерти
5. ✅ Готуємо до production release

### Якщо є проблеми:
1. ⚠️ Фіксуємо баги
2. ⚠️ Виправляємо критичні проблеми
3. ⚠️ Повторюємо тестування
4. ⚠️ Ітераційно покращуємо

---

## 📅 Рекомендований план

### Тиждень 1: Підготовка
- **День 1-2:** Виправлення багів та покращення якості коду
- **День 3:** Налаштування staging сервера
- **День 4-5:** Деплой та smoke tests

### Тиждень 2: Тестування
- **День 1-2:** Функціональне тестування
- **День 3:** Навантажувальне тестування
- **День 4:** Тестування безпеки
- **День 5:** Фінальні перевірки та виправлення

### Тиждень 3: Production
- **День 1:** Фінальна підготовка
- **День 2:** Production деплой
- **День 3-5:** Моніторинг та виправлення проблем

---

## 🆘 Troubleshooting

### Часті проблеми:

1. **Сервіси не запускаються**
   ```bash
   # Перевірити логи
   docker compose -f docker-compose.prod.yml logs

   # Перевірити environment variables
   docker compose -f docker-compose.prod.yml config
   ```

2. **Помилки підключення до БД**
   - Перевірити DATABASE_URL
   - Перевірити доступність PostgreSQL
   - Перевірити credentials

3. **CORS помилки**
   - Перевірити CORS_ALLOWED_ORIGINS
   - Перевірити формат (comma-separated)

4. **Rate limiting не працює**
   - Перевірити REDIS_URL
   - Перевірити DISABLE_RATE_LIMIT=false

---

## 📞 Контакти та підтримка

**При проблемах:**
1. Перевірити логи: `docker compose -f docker-compose.prod.yml logs`
2. Перевірити health checks
3. Перевірити конфігурацію

---

**Останнє оновлення:** 31 жовтня 2025
**Статус:** 🟡 Готово до підготовки, потребує виконання чек-листу
