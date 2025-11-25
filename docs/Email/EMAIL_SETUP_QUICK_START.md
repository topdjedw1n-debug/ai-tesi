# 🚀 ШВИДКИЙ СТАРТ: Email Налаштування

**Час:** 10-15 хвилин

---

## ✅ ЩО ПОТРІБНО ВІД ВАС

### Крок 1: Обрати Email Провайдера

**Рекомендація:** Gmail для development, SendGrid для production

#### Варіант 1: Gmail (Development - 5 хвилин)
1. Відкрийте: https://myaccount.google.com/apppasswords
2. Створіть App Password: "Mail" → "Other" → "TesiGo"
3. Скопіюйте 16-значний пароль

#### Варіант 2: SendGrid (Production - 10 хвилин)
1. Реєстрація: https://sendgrid.com/
2. Settings → API Keys → Create API Key
3. Скопіюйте API Key

---

### Крок 2: Додати в .env

Відкрийте `apps/api/.env` і додайте:

```bash
# Для Gmail:
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=abcd efgh ijkl mnop
SMTP_TLS=true
EMAILS_FROM_EMAIL=your-email@gmail.com
EMAILS_FROM_NAME=TesiGo Platform

# Для SendGrid:
SMTP_HOST=smtp.sendgrid.net
SMTP_PORT=587
SMTP_USER=apikey
SMTP_PASSWORD=SG.ваш_api_key
SMTP_TLS=true
EMAILS_FROM_EMAIL=noreply@your-domain.com
EMAILS_FROM_NAME=TesiGo Platform
```

---

### Крок 3: Перезапустити API

```bash
cd apps/api
# Перезапустіть сервер
uvicorn main:app --reload
```

---

### Крок 4: Тестування

1. Відкрийте: http://localhost:3000
2. Спробуйте залогінитись (введіть email)
3. Перевірте inbox - має прийти лист!

---

## ✅ ГОТОВО!

Якщо email прийшов - все працює! 🎉

Якщо ні - дивіться детальну інструкцію: `EMAIL_SETUP_INSTRUCTIONS.md`

---

**Детальна інструкція:** `docs/EMAIL_SETUP_INSTRUCTIONS.md`
