# 1️⃣ ПЕРЕВІРКА ІНФРАСТРУКТУРИ

> **Категорія:** Infrastructure & DevOps
> **Час виконання:** ~10-15 хвилин
> **Залежності:** Docker Desktop встановлено та запущено
> **Критичність:** 🔴 ВИСОКА - Без інфраструктури проект не працюватиме

---

## 🎯 МЕТА ПЕРЕВІРКИ

Переконатися що всі базові сервіси інфраструктури (Docker, PostgreSQL, Redis, MinIO) запущені, доступні та готові приймати з'єднання. Ця перевірка є фундаментом для всіх наступних тестів.

**Що перевіряємо:**
- ✅ Docker daemon активний і контейнери можна запускати
- ✅ PostgreSQL база даних доступна і приймає підключення
- ✅ Redis cache працює і відповідає на команди
- ✅ MinIO object storage доступний для зберігання файлів
- ✅ Всі сервіси "healthy" згідно Docker health checks

---

## ✅ ПЕРЕДУМОВИ

**Необхідне ПЗ:**
- [ ] Docker Desktop >= 20.10 встановлено
- [ ] Docker Compose >= 2.0 встановлено
- [ ] Мінімум 4GB RAM доступно
- [ ] Порти вільні: 5432 (PostgreSQL), 6379 (Redis), 9000/9001 (MinIO)

**Перевірка передумов:**
```bash
# Перевірити версію Docker
docker --version
# Очікується: Docker version 20.10.x або новіша

# Перевірити Docker Compose
docker-compose --version
# Очікується: Docker Compose version 2.x.x

# Перевірити вільні порти
lsof -i :5432 -i :6379 -i :9000 -i :9001
# Очікується: порожній вивід (порти вільні)
```

---

## 📋 ПОКРОКОВА ІНСТРУКЦІЯ

### Крок 1: Перевірка Docker Daemon

**Що робимо:** Переконуємося що Docker запущено і працює

**Команда:**
```bash
docker info
```

**Очікуваний результат:**
```
Server Version: 20.10.x
Storage Driver: overlay2
Containers: X
 Running: X
 Paused: 0
 Stopped: X
...
```

**Критерій успішності:**
- ✅ Команда виконується без помилок
- ✅ Виводиться інформація про Docker engine
- ✅ Server Version присутня

**Що робити якщо помилка:**
| Помилка | Причина | Рішення |
|---------|---------|---------|
| `Cannot connect to the Docker daemon` | Docker не запущено | Запустити Docker Desktop |
| `permission denied` | Немає прав доступу | Додати користувача в групу docker: `sudo usermod -aG docker $USER` |
| `command not found` | Docker не встановлено | Встановити Docker Desktop з офіційного сайту |

---

### Крок 2: Перехід в директорію з Docker Compose

**Що робимо:** Переходимо в папку з конфігурацією інфраструктури

**Команда:**
```bash
cd /Users/maxmaxvel/.claude-worktrees/AI\ TESI/stupefied-fermat/infra/docker
pwd
```

**Очікуваний результат:**
```
/Users/maxmaxvel/.claude-worktrees/AI TESI/stupefied-fermat/infra/docker
```

**Перевірка наявності файлів:**
```bash
ls -la
```

**Очікується:**
- `docker-compose.yml` (основна конфігурація)
- `.env` або `.env.example` (змінні середовища)

---

### Крок 3: Запуск контейнерів

**Що робимо:** Запускаємо всі сервіси через Docker Compose

**Команда:**
```bash
docker-compose up -d
```

**Параметри:**
- `-d` = detached mode (запуск у фоні)

**Очікуваний результат:**
```
Creating network "docker_default" with the default driver
Creating ai-thesis-postgres ... done
Creating ai-thesis-redis    ... done
Creating ai-thesis-minio    ... done
```

**Альтернативна команда (без детач режиму для дебагу):**
```bash
docker-compose up
# Ctrl+C для зупинки
```

**Що робити якщо помилка:**
| Помилка | Причина | Рішення |
|---------|---------|---------|
| `port is already allocated` | Порт зайнятий | Знайти процес: `lsof -i :<PORT>` і зупинити |
| `network not found` | Docker мережа не створена | `docker network create docker_default` |
| `image not found` | Образ не завантажено | `docker-compose pull` перед запуском |

---

### Крок 4: Перевірка статусу контейнерів

**Що робимо:** Перевіряємо що всі контейнери запущені і "healthy"

**Команда:**
```bash
docker-compose ps
```

**Очікуваний результат:**
```
NAME                 COMMAND                  SERVICE    STATUS         PORTS
ai-thesis-postgres   "docker-entrypoint.s…"   postgres   Up X minutes   0.0.0.0:5432->5432/tcp
ai-thesis-redis      "docker-entrypoint.s…"   redis      Up X minutes   0.0.0.0:6379->6379/tcp
ai-thesis-minio      "/usr/bin/docker-ent…"   minio      Up X minutes   0.0.0.0:9000-9001->9000-9001/tcp
```

**Критерії успішності:**
- ✅ Всі контейнери в статусі "Up"
- ✅ Немає контейнерів в статусі "Restarting" або "Exited"
- ✅ Порти mapped правильно

**Детальна перевірка:**
```bash
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
```

**Що робити якщо проблеми:**
| Проблема | Діагностика | Рішення |
|----------|-------------|---------|
| Контейнер "Restarting" | `docker logs <container_name>` | Перевірити логи помилок |
| Контейнер "Exited" | `docker-compose logs <service>` | Перевірити конфігурацію в docker-compose.yml |
| Порти не mapped | `docker inspect <container_name>` | Перевірити PORTS в docker-compose.yml |

---

### Крок 5: PostgreSQL - Перевірка доступності

**Що робимо:** Тестуємо підключення до бази даних

**Команда 1: Перевірка порту**
```bash
nc -zv localhost 5432
```

**Очікуваний результат:**
```
Connection to localhost port 5432 [tcp/postgresql] succeeded!
```

**Команда 2: Підключення через psql**
```bash
docker exec -it ai-thesis-postgres psql -U postgres -d ai_thesis_platform -c "SELECT 1 AS test;"
```

**Очікуваний результат:**
```
 test
------
    1
(1 row)
```

**Команда 3: Перевірка таблиць (міграції застосовано)**
```bash
docker exec -it ai-thesis-postgres psql -U postgres -d ai_thesis_platform -c "\dt"
```

**Очікуваний результат:**
```
                    List of relations
 Schema |           Name            | Type  |  Owner
--------+---------------------------+-------+----------
 public | alembic_version           | table | postgres
 public | users                     | table | postgres
 public | documents                 | table | postgres
 public | payments                  | table | postgres
 public | ai_generation_jobs        | table | postgres
 public | refund_requests           | table | postgres
 ...
```

**Команда 4: Health check**
```bash
docker exec ai-thesis-postgres pg_isready
```

**Очікуваний результат:**
```
/var/run/postgresql:5432 - accepting connections
```

**Що робити якщо помилка:**
| Помилка | Причина | Рішення |
|---------|---------|---------|
| `Connection refused` | PostgreSQL не запущено | `docker-compose restart postgres` |
| `FATAL: database does not exist` | База не створена | Перевірити docker-compose.yml POSTGRES_DB |
| `no pg_hba.conf entry` | Проблема з аутентифікацією | Перевірити POSTGRES_PASSWORD в .env |
| Таблиці відсутні | Міграції не застосовано | Запустити: `cd apps/api && alembic upgrade head` |

---

### Крок 6: Redis - Перевірка роботи cache

**Що робимо:** Тестуємо Redis команди і доступність

**Команда 1: Перевірка порту**
```bash
nc -zv localhost 6379
```

**Очікуваний результат:**
```
Connection to localhost port 6379 [tcp/*] succeeded!
```

**Команда 2: PING тест**
```bash
docker exec ai-thesis-redis redis-cli PING
```

**Очікуваний результат:**
```
PONG
```

**Команда 3: SET/GET операції**
```bash
# Записати значення
docker exec ai-thesis-redis redis-cli SET test_key "health_check_ok"

# Прочитати значення
docker exec ai-thesis-redis redis-cli GET test_key

# Видалити тестовий ключ
docker exec ai-thesis-redis redis-cli DEL test_key
```

**Очікуваний результат:**
```
OK
"health_check_ok"
(integer) 1
```

**Команда 4: Перевірка TTL (Time To Live)**
```bash
# Записати з TTL 10 секунд
docker exec ai-thesis-redis redis-cli SETEX test_ttl 10 "expires_soon"

# Перевірити залишковий час
docker exec ai-thesis-redis redis-cli TTL test_ttl

# Почекати 11 секунд і перевірити
sleep 11
docker exec ai-thesis-redis redis-cli GET test_ttl
```

**Очікуваний результат:**
```
OK
(integer) 9  # або менше
(nil)  # ключ видалено після TTL
```

**Команда 5: Перевірка пам'яті**
```bash
docker exec ai-thesis-redis redis-cli INFO memory | grep used_memory_human
```

**Очікуваний результат:**
```
used_memory_human:1.23M
```

**Що робити якщо помилка:**
| Помилка | Причина | Рішення |
|---------|---------|---------|
| `Could not connect` | Redis не запущено | `docker-compose restart redis` |
| `NOAUTH Authentication required` | Потрібен пароль | Перевірити REDIS_PASSWORD в .env |
| `OOM command not allowed` | Закінчилась пам'ять | Збільшити maxmemory в конфігурації |

---

### Крок 7: MinIO - Перевірка object storage

**Що робимо:** Перевіряємо доступність MinIO для зберігання файлів

**Команда 1: Перевірка API порту (9000)**
```bash
nc -zv localhost 9000
```

**Очікуваний результат:**
```
Connection to localhost port 9000 [tcp/*] succeeded!
```

**Команда 2: Перевірка Console порту (9001)**
```bash
curl -s http://localhost:9001 | head -n 5
```

**Очікуваний результат:**
```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width,initial-scale=1" />
```

**Команда 3: Health endpoint**
```bash
curl -s http://localhost:9000/minio/health/live
```

**Очікуваний результат:**
```
200 OK
```

**Команда 4: Перевірка через MinIO Client (mc)**

**Встановлення mc (якщо потрібно):**
```bash
# macOS
brew install minio/stable/mc

# Linux
wget https://dl.min.io/client/mc/release/linux-amd64/mc
chmod +x mc
sudo mv mc /usr/local/bin/
```

**Налаштування alias:**
```bash
mc alias set local http://localhost:9000 minioadmin minioadmin
```

**Перевірка buckets:**
```bash
mc ls local
```

**Очікуваний результат:**
```
[2025-12-03 10:00:00 UTC]     0B ai-thesis-documents/
```

**Тестове завантаження файлу:**
```bash
# Створити тестовий файл
echo "Health check test" > /tmp/health_check.txt

# Завантажити в MinIO
mc cp /tmp/health_check.txt local/ai-thesis-documents/

# Перевірити наявність
mc ls local/ai-thesis-documents/

# Завантажити назад
mc cp local/ai-thesis-documents/health_check.txt /tmp/health_check_downloaded.txt

# Перевірити вміст
cat /tmp/health_check_downloaded.txt

# Видалити тестовий файл
mc rm local/ai-thesis-documents/health_check.txt
rm /tmp/health_check.txt /tmp/health_check_downloaded.txt
```

**Що робити якщо помилка:**
| Помилка | Причина | Рішення |
|---------|---------|---------|
| `Connection refused` | MinIO не запущено | `docker-compose restart minio` |
| `Access Denied` | Невірні credentials | Перевірити MINIO_ROOT_USER/PASSWORD в docker-compose.yml |
| `Bucket does not exist` | Bucket не створено | Створити: `mc mb local/ai-thesis-documents` |
| Console не відкривається | Порт 9001 зайнятий | Змінити порт в docker-compose.yml |

---

### Крок 8: Перевірка логів (діагностика)

**Що робимо:** Перевіряємо логи контейнерів на помилки

**Команда: Всі логи**
```bash
docker-compose logs
```

**Команда: Логи конкретного сервісу**
```bash
# PostgreSQL
docker-compose logs postgres

# Redis
docker-compose logs redis

# MinIO
docker-compose logs minio
```

**Команда: Real-time логи (tail -f)**
```bash
docker-compose logs -f
# Ctrl+C для виходу
```

**Команда: Останні N рядків**
```bash
docker-compose logs --tail=50 postgres
```

**На що звертати увагу:**
- ❌ `ERROR`, `FATAL`, `PANIC` - критичні помилки
- ⚠️ `WARNING`, `WARN` - попередження (можливі проблеми)
- ✅ `INFO`, `DEBUG` - нормальна робота

**Приклад нормальних логів PostgreSQL:**
```
postgres_1  | 2025-12-03 10:00:00.123 UTC [1] LOG:  database system is ready to accept connections
```

**Приклад нормальних логів Redis:**
```
redis_1     | 1:M 03 Dec 2025 10:00:00.123 * Ready to accept connections
```

**Приклад нормальних логів MinIO:**
```
minio_1     | API: http://localhost:9000  http://172.18.0.4:9000
minio_1     | Console: http://localhost:9001 http://172.18.0.4:9001
```

---

### Крок 9: Перевірка мережі Docker

**Що робимо:** Переконуємося що контейнери можуть спілкуватись між собою

**Команда: Список мереж**
```bash
docker network ls
```

**Очікуваний результат:**
```
NETWORK ID     NAME              DRIVER    SCOPE
abc123def456   docker_default    bridge    local
...
```

**Команда: Інспекція мережі**
```bash
docker network inspect docker_default
```

**Перевірити що всі 3 контейнери в одній мережі:**
- ai-thesis-postgres
- ai-thesis-redis
- ai-thesis-minio

**Команда: Тест з'єднання між контейнерами**
```bash
# З postgres до redis
docker exec ai-thesis-postgres ping -c 3 ai-thesis-redis

# З postgres до minio
docker exec ai-thesis-postgres ping -c 3 ai-thesis-minio
```

**Очікуваний результат:**
```
PING ai-thesis-redis (172.18.0.3): 56 data bytes
64 bytes from 172.18.0.3: seq=0 ttl=64 time=0.123 ms
...
3 packets transmitted, 3 packets received, 0% packet loss
```

---

### Крок 10: Фінальна перевірка ресурсів

**Що робимо:** Перевіряємо споживання ресурсів контейнерами

**Команда:**
```bash
docker stats --no-stream
```

**Очікуваний результат:**
```
CONTAINER ID   NAME                CPU %     MEM USAGE / LIMIT     NET I/O           BLOCK I/O
abc123         ai-thesis-postgres  1.23%     64MiB / 2GiB          1.2MB / 890kB     12MB / 8MB
def456         ai-thesis-redis     0.45%     8MiB / 2GiB           450kB / 320kB     0B / 0B
ghi789         ai-thesis-minio     0.89%     128MiB / 2GiB         2.1MB / 1.5MB     5MB / 3MB
```

**Критерії нормальної роботи:**
- ✅ CPU < 50% (в idle стані)
- ✅ Memory < 500MB для кожного контейнера
- ✅ Немає постійного збільшення пам'яті (memory leak)

**Що робити якщо високе споживання:**
| Проблема | Можлива причина | Рішення |
|----------|-----------------|---------|
| PostgreSQL CPU > 50% | Активні запити | Перевірити slow queries |
| Redis Memory > 1GB | Багато закешованих даних | Перевірити TTL policies |
| MinIO Memory > 500MB | Багато файлів | Нормально для production |

---

## 🔍 ПЕРЕВІРКА РЕЗУЛЬТАТІВ

### Чеклист успішного проходження:

- [ ] Docker daemon запущено (`docker info`)
- [ ] Всі 3 контейнери в статусі "Up" (`docker-compose ps`)
- [ ] PostgreSQL відповідає на `SELECT 1` запит
- [ ] Таблиці в БД присутні (міграції застосовано)
- [ ] Redis відповідає `PONG` на `PING`
- [ ] Redis SET/GET операції працюють
- [ ] MinIO API доступний (порт 9000)
- [ ] MinIO Console доступна (порт 9001)
- [ ] MinIO bucket `ai-thesis-documents` існує
- [ ] Логи контейнерів без критичних помилок
- [ ] Docker мережа налаштована (контейнери бачать один одного)
- [ ] Споживання ресурсів в нормі (CPU < 50%, Memory < 500MB)

---

## ⚠️ ТИПОВІ ПОМИЛКИ ТА РІШЕННЯ

### Топ-10 частих проблем:

| # | Проблема | Симптом | Рішення |
|---|----------|---------|---------|
| 1 | Порти зайняті | `port is already allocated` | `lsof -i :<PORT>` → kill процес |
| 2 | Docker не запущено | `Cannot connect to Docker daemon` | Запустити Docker Desktop |
| 3 | Недостатньо RAM | Контейнери "killed" | Виділити більше RAM в Docker Desktop |
| 4 | PostgreSQL не стартує | Контейнер "Restarting" | `docker logs ai-thesis-postgres` |
| 5 | Redis memory limit | `OOM command not allowed` | Збільшити maxmemory |
| 6 | MinIO credentials невірні | `Access Denied` | Перевірити MINIO_ROOT_USER/PASSWORD |
| 7 | Міграції не застосовано | Таблиці відсутні в БД | `alembic upgrade head` |
| 8 | Мережа не створена | Контейнери не бачать один одного | `docker network create docker_default` |
| 9 | Volume permissions | `permission denied` | `docker-compose down -v` → up |
| 10 | Старі контейнери | Конфлікт версій | `docker-compose down && docker-compose up -d` |

---

## 📊 КРИТЕРІЇ УСПІШНОСТІ

### ✅ ТЕСТ ПРОЙДЕНО ЯКЩО:

1. **Всі контейнери запущені:**
   - PostgreSQL: `Up X minutes` + health check OK
   - Redis: `Up X minutes` + PONG response
   - MinIO: `Up X minutes` + API accessible

2. **Базові операції працюють:**
   - PostgreSQL: `SELECT 1` повертає результат
   - Redis: `SET/GET` операції успішні
   - MinIO: файли можна завантажувати/скачувати

3. **Логи чисті:**
   - Немає ERROR/FATAL повідомлень
   - Всі сервіси "ready to accept connections"

4. **Ресурси в нормі:**
   - CPU < 50% (idle)
   - Memory < 500MB на контейнер

### ❌ ТЕСТ ПРОВАЛЕНО ЯКЩО:

- Хоча б один контейнер не запущено
- PostgreSQL/Redis/MinIO не відповідають
- В логах критичні помилки
- Контейнери постійно перезапускаються
- Ресурси вичерпані (OOM killer активний)

---

## 🔗 ЗВ'ЯЗОК З ІНШИМИ ПЕРЕВІРКАМИ

**⬆️ Залежить від:**
- Немає (це перша базова перевірка)

**⬇️ Впливає на:**
- `02_CONFIGURATION_CHECK.md` - потребує працюючої інфраструктури
- `03_BACKEND_CHECK.md` - Backend підключається до PostgreSQL/Redis
- `05_UNIT_TESTS_CHECK.md` - Тести використовують БД
- `06_INTEGRATION_TESTS_CHECK.md` - Інтеграційні тести потребують всіх сервісів
- `07_API_ENDPOINTS_CHECK.md` - API працює з БД/Redis/MinIO

**Критичність:** 🔴 НАЙВИЩА - без інфраструктури нічого не працюватиме!

---

## 🚀 ШВИДКИЙ СТАРТ (для досвідчених)

```bash
# 1. Запуск всього в одній команді
cd infra/docker && docker-compose up -d

# 2. Швидка перевірка (all-in-one)
docker-compose ps && \
docker exec ai-thesis-postgres psql -U postgres -c "SELECT 1" && \
docker exec ai-thesis-redis redis-cli PING && \
curl -s http://localhost:9000/minio/health/live

# 3. Якщо все OK, виводиться:
# All containers Up ✅
# 1 (PostgreSQL) ✅
# PONG (Redis) ✅
# 200 OK (MinIO) ✅
```

---

**Дата створення:** 2025-12-03
**Версія:** 1.0
**Автор:** AI Assistant
**Наступна перевірка:** `02_CONFIGURATION_CHECK.md`
