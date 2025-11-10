# 🚀 Автоматичний запуск AI TESI

## ⚡ Для Cursor AI: 3 простих кроки

### Крок 1: Запустіть інфраструктуру (якщо ще не запущена)

```bash
cd infra/docker
docker-compose up -d postgres redis minio minio-setup
```

Чекайте поки контейнери запустяться (10-15 секунд).

### Крок 2: Налаштуйте .env файли

```bash
./setup-env.sh
```

Цей скрипт автоматично створить:
- `apps/api/.env` (Backend конфігурація)
- `apps/web/.env.local` (Frontend конфігурація)

### Крок 3: Запустіть Development сервери

```bash
./start-dev.sh
```

Цей скрипт автоматично:
1. ✅ Перевірить .env файли
2. ✅ Перевірить Docker контейнери
3. ✅ Створить Python virtualenv (якщо потрібно)
4. ✅ Встановить залежності (pip install)
5. ✅ Встановить npm пакети
6. ✅ Запустить Backend (port 8000)
7. ✅ Запустить Frontend (port 3000)

---

## 🎯 Готово!

Після запуску відкрийте в браузері:

- **Frontend:** http://localhost:3000
- **Backend API:** http://localhost:8000/docs
- **Health Check:** http://localhost:8000/health

---

## 🔍 Перевірка стану

```bash
./check-health.sh
```

Показує статус всіх сервісів.

---

## 🛑 Зупинка

Натисніть `Ctrl+C` в терміналі де запущений `start-dev.sh`

---

## 📝 Логи

```bash
# Backend
tail -f logs/backend.log

# Frontend
tail -f logs/frontend.log
```

---

## ⚠️ Можливі помилки

### Помилка: "port already in use"

```bash
# Знайти процес на порту 8000
lsof -ti:8000 | xargs kill -9

# Знайти процес на порту 3000
lsof -ti:3000 | xargs kill -9
```

### Помилка: "Docker контейнери не запущені"

```bash
cd infra/docker
docker-compose down
docker-compose up -d postgres redis minio minio-setup
```

### Помилка: "Module not found"

```bash
# Backend
cd apps/api
source venv/bin/activate
pip install -r requirements.txt

# Frontend
cd apps/web
rm -rf node_modules
npm install
```

---

## 🎮 Всі команди

| Команда | Опис |
|---------|------|
| `./setup-env.sh` | Створити .env файли |
| `./start-dev.sh` | Запустити сервери |
| `./check-health.sh` | Перевірити статус |
| `docker-compose ps` | Docker контейнери |
| `docker-compose logs postgres` | Логи PostgreSQL |

---

## 🐛 Виправлені баги

✅ Всі 4 критичні баги виправлено:
1. PostgreSQL type mismatch (JWT user_id)
2. Double-wrapping exceptions
3. SlowAPI rate limiter parameter
4. Refresh token body parameter

Детальніше: `apps/api/SETUP.md`

---

## 📞 Підтримка

Якщо виникають проблеми:
1. Перевірте що Docker запущений
2. Запустіть `./check-health.sh`
3. Перегляньте логи: `tail -f logs/*.log`
