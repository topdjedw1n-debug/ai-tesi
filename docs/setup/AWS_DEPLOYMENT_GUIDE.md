# 🚀 AWS EC2 Deployment Guide

## Покрокова інструкція для деплою AI Thesis на AWS EC2

---

## 📋 Що вам знадобиться

- ✅ AWS EC2 інстанс (Ubuntu 20.04/22.04)
- ✅ SSH доступ до сервера (.pem ключ)
- ✅ Публічна IP адреса EC2
- ✅ GitHub репозиторій з кодом
- ✅ API ключі (OpenAI, Anthropic, Stripe, Resend)

---

## 🎯 Процес деплою (3 кроки)

### Крок 1: Налаштування EC2 сервера (одноразово)
### Крок 2: Налаштування GitHub Secrets
### Крок 3: Автоматичний деплой через Git

---

## 📦 Крок 1: Початкове налаштування сервера

### 1.1 Підключитись до EC2

```bash
# На вашому локальному комп'ютері
ssh -i /path/to/your-key.pem ubuntu@YOUR_EC2_IP
```

> Замініть:
> - `/path/to/your-key.pem` на шлях до вашого AWS ключа
> - `YOUR_EC2_IP` на публічну IP адресу вашого EC2

### 1.2 Завантажити setup скрипт

```bash
# На EC2 сервері
wget https://raw.githubusercontent.com/topdjedw1n-debug/ai-tesi/main/scripts/setup-ec2-server.sh
chmod +x setup-ec2-server.sh
```

Або скопіюйте вручну:
```bash
# На локальному комп'ютері
scp -i /path/to/your-key.pem scripts/setup-ec2-server.sh ubuntu@YOUR_EC2_IP:~/
```

### 1.3 Запустити setup скрипт

```bash
# На EC2 сервері
./setup-ec2-server.sh
```

**Скрипт встановить:**
- Docker & Docker Compose
- Git
- Firewall (UFW)
- Monitoring tools (htop, iotop)
- Системні оптимізації

**⚠️ ВАЖЛИВО:** Після завершення скрипта:
```bash
exit  # вийти з SSH
ssh -i /path/to/your-key.pem ubuntu@YOUR_EC2_IP  # зайти знову
```

### 1.4 Перевірити, що Docker працює

```bash
docker --version
docker-compose --version
docker ps  # має працювати без sudo
```

---

## 🔐 Крок 2: Налаштування GitHub Secrets

### 2.1 Згенерувати SSH ключ для GitHub Actions

```bash
# На вашому локальному комп'ютері
ssh-keygen -t rsa -b 4096 -f ~/.ssh/ai-thesis-deploy -N ""
```

Це створить:
- `~/.ssh/ai-thesis-deploy` (приватний ключ) → для GitHub
- `~/.ssh/ai-thesis-deploy.pub` (публічний ключ) → для EC2

### 2.2 Додати публічний ключ на EC2

```bash
# На локальному комп'ютері
ssh-copy-id -i ~/.ssh/ai-thesis-deploy.pub ubuntu@YOUR_EC2_IP
```

Або вручну:
```bash
# Показати публічний ключ
cat ~/.ssh/ai-thesis-deploy.pub

# Підключитись до EC2 і додати його
ssh -i /path/to/your-key.pem ubuntu@YOUR_EC2_IP
echo "PASTE_PUBLIC_KEY_HERE" >> ~/.ssh/authorized_keys
exit
```

### 2.3 Додати Secrets в GitHub

Перейдіть на: `https://github.com/topdjedw1n-debug/ai-tesi/settings/secrets/actions`

Натисніть **"New repository secret"** і додайте:

#### Обов'язкові Secrets:

| Secret Name | Value | Опис |
|------------|-------|------|
| `EC2_HOST` | `YOUR_EC2_IP` | IP адреса вашого EC2 |
| `EC2_USER` | `ubuntu` | Користувач (зазвичай `ubuntu` або `ec2-user`) |
| `EC2_SSH_KEY` | (вміст приватного ключа) | Весь вміст файлу `~/.ssh/ai-thesis-deploy` |

**Як отримати вміст ключа:**
```bash
cat ~/.ssh/ai-thesis-deploy
# Скопіювати ВСЕ (включно з BEGIN і END)
```

#### Секрети бази даних:

| Secret Name | Value | Приклад |
|------------|-------|---------|
| `POSTGRES_DB` | `ai_thesis` | Назва бази даних |
| `POSTGRES_USER` | `postgres` | Користувач БД |
| `POSTGRES_PASSWORD` | `your_strong_password_123` | Пароль (генеруйте складний!) |

#### MinIO секрети:

| Secret Name | Value | Приклад |
|------------|-------|---------|
| `MINIO_ROOT_USER` | `minio_admin` | MinIO логін |
| `MINIO_ROOT_PASSWORD` | `minio_password_456` | MinIO пароль |

#### Security:

| Secret Name | Value | Як згенерувати |
|------------|-------|----------------|
| `SECRET_KEY` | (random string) | `openssl rand -hex 32` |

#### AI API Keys:

| Secret Name | Value | Де взяти |
|------------|-------|----------|
| `OPENAI_API_KEY` | `sk-...` | https://platform.openai.com/api-keys |
| `ANTHROPIC_API_KEY` | `sk-ant-...` | https://console.anthropic.com/settings/keys |

#### Stripe (Payment):

| Secret Name | Value | Де взяти |
|------------|-------|----------|
| `STRIPE_SECRET_KEY` | `sk_test_...` або `sk_live_...` | https://dashboard.stripe.com/apikeys |
| `STRIPE_PUBLISHABLE_KEY` | `pk_test_...` або `pk_live_...` | https://dashboard.stripe.com/apikeys |
| `STRIPE_WEBHOOK_SECRET` | `whsec_...` | https://dashboard.stripe.com/webhooks |

#### Email (Resend):

| Secret Name | Value | Де взяти |
|------------|-------|----------|
| `RESEND_API_KEY` | `re_...` | https://resend.com/api-keys |

### 2.4 Згенерувати випадкові паролі

```bash
# SECRET_KEY
openssl rand -hex 32

# POSTGRES_PASSWORD
openssl rand -base64 24

# MINIO_ROOT_PASSWORD
openssl rand -base64 24
```

---

## 🚀 Крок 3: Деплой

### Варіант А: Автоматичний (рекомендовано)

Просто зробіть push в репозиторій:

```bash
git add .
git commit -m "Initial deployment setup"
git push origin main
```

GitHub Actions автоматично:
1. Підключиться до вашого EC2
2. Завантажить код
3. Запустить Docker контейнери
4. Виконає міграції БД
5. Перевірить health endpoints

**Перегляньте прогрес:**
https://github.com/topdjedw1n-debug/ai-tesi/actions

### Варіант Б: Ручний деплой

```bash
# Підключитись до EC2
ssh -i /path/to/your-key.pem ubuntu@YOUR_EC2_IP

# Перейти в директорію проекту
cd ~/ai-thesis

# Запустити deployment скрипт
./scripts/deploy.sh
```

---

## ✅ Крок 4: Перевірка

### 4.1 Перевірити статус контейнерів

```bash
# На EC2 сервері
cd ~/ai-thesis/infra/docker
docker-compose -f docker-compose.prod.yml ps
```

Всі контейнери мають бути в статусі `Up (healthy)`.

### 4.2 Перевірити endpoints

```bash
# На локальному комп'ютері
curl http://YOUR_EC2_IP:8000/health
curl http://YOUR_EC2_IP:3000
```

Або відкрийте в браузері:
- Frontend: `http://YOUR_EC2_IP:3000`
- Backend API: `http://YOUR_EC2_IP:8000`
- API Docs: `http://YOUR_EC2_IP:8000/docs`
- MinIO Console: `http://YOUR_EC2_IP:9001`

---

## 🔧 Troubleshooting

### Проблема: Контейнери не запускаються

```bash
# Подивитись логи
cd ~/ai-thesis/infra/docker
docker-compose -f docker-compose.prod.yml logs

# Або конкретного сервісу
docker-compose -f docker-compose.prod.yml logs api
docker-compose -f docker-compose.prod.yml logs postgres
```

### Проблема: Не може підключитись по SSH

```bash
# Перевірити firewall на EC2
ssh -i /path/to/your-key.pem ubuntu@YOUR_EC2_IP
sudo ufw status

# Переконатись що порт 22 відкритий
sudo ufw allow 22
```

### Проблема: GitHub Actions падає з помилкою SSH

1. Перевірте, що `EC2_SSH_KEY` містить **приватний** ключ (не публічний)
2. Переконайтесь, що публічний ключ доданий на EC2:
   ```bash
   ssh ubuntu@YOUR_EC2_IP
   cat ~/.ssh/authorized_keys
   ```

### Проблема: База даних не працює

```bash
# Зайти в контейнер PostgreSQL
docker exec -it ai-thesis-postgres bash

# Перевірити підключення
psql -U postgres -d ai_thesis

# Перевірити міграції
docker-compose -f docker-compose.prod.yml exec api alembic current
```

### Проблема: Frontend не може підключитись до Backend

Перевірте змінну `BACKEND_URL` в `.env.production`:
```bash
ssh ubuntu@YOUR_EC2_IP
cat ~/ai-thesis/.env.production | grep BACKEND_URL
```

Має бути: `BACKEND_URL=http://YOUR_EC2_IP:8000`

---

## 🔄 Оновлення проекту

### Автоматичне оновлення:
```bash
git push origin main  # GitHub Actions зробить все автоматично
```

### Ручне оновлення:
```bash
ssh ubuntu@YOUR_EC2_IP
cd ~/ai-thesis
./scripts/deploy.sh
```

---

## 🛡️ Security Checklist

- [ ] Змінені дефолтні паролі (postgres, minio)
- [ ] Згенерований новий `SECRET_KEY`
- [ ] Використовуються production API ключі (не test)
- [ ] Firewall налаштований (UFW)
- [ ] SSH доступ тільки через ключі (не паролі)
- [ ] Automatic security updates увімкнені
- [ ] Регулярні бекапи бази даних

---

## 📊 Моніторинг

### Перегляд ресурсів:
```bash
ssh ubuntu@YOUR_EC2_IP
htop  # CPU та RAM
docker stats  # Споживання контейнерами
```

### Логи в реальному часі:
```bash
cd ~/ai-thesis/infra/docker
docker-compose -f docker-compose.prod.yml logs -f
```

### Перезапуск сервісу:
```bash
docker-compose -f docker-compose.prod.yml restart api
```

---

## 🎉 Готово!

Тепер кожен push в `main` буде автоматично деплоїтись на ваш EC2 сервер.

**Корисні посилання:**
- GitHub Actions: https://github.com/topdjedw1n-debug/ai-tesi/actions
- AWS EC2 Console: https://console.aws.amazon.com/ec2
- Stripe Dashboard: https://dashboard.stripe.com
- OpenAI Usage: https://platform.openai.com/usage

**Потрібна допомога?**
- Перегляньте логи: `docker-compose logs`
- Перевірте GitHub Actions workflow
- Подивіться troubleshooting секцію вище
