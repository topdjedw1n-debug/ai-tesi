# 📧 НАЛАШТУВАННЯ AWS SES ДЛЯ EMAIL

**Для AWS хостингу - рекомендований вибір!**

---

## 🎯 ЧОМУ AWS SES ЗАМІСТЬ SENDGRID?

### Переваги AWS SES:
- ✅ **Дешевше:** $0.10 за 1,000 листів (vs SendGrid $19.95/міс)
- ✅ **Все в AWS:** Один провайдер для хостингу + email
- ✅ **Без обмежень:** Немає денних лімітів на платному плані
- ✅ **Масштабується:** Автоматично росте з навантаженням
- ✅ **Інтеграція:** Легко інтегрується з іншими AWS сервісами

### Коли SendGrid краще:
- ⚠️ Якщо не використовуєте AWS
- ⚠️ Якщо потрібні готові email templates
- ⚠️ Якщо потрібні advanced analytics з коробки

---

## 🚀 НАЛАШТУВАННЯ AWS SES

### КРОК 1: Верифікація Email (Development)

**Для швидкого старту:**

1. AWS Console → SES → Verified identities
2. Натисніть "Create identity"
3. Оберіть "Email address"
4. Введіть email: `noreply@tesigo.com` (або ваш)
5. Перевірте email inbox → підтвердіть

**✅ Готово для development!**

---

### КРОК 2: Верифікація Домену (Production)

**Для production з власним доменом:**

1. AWS Console → SES → Verified identities
2. Натисніть "Create identity"
3. Оберіть "Domain"
4. Введіть домен: `tesigo.com`

**AWS автоматично генерує DNS записи:**
- SPF
- DKIM
- CNAME для верифікації

5. Додайте записи в DNS:
   - Перейдіть в ваш DNS провайдер
   - Додайте записи які показав AWS
   - Чекайте propagation (1-24 години)

6. Перевірте в AWS → Status має бути "Verified" ✅

---

### КРОК 3: Створити SMTP Credentials

**AWS SES використовує SMTP для відправки:**

1. AWS Console → SES → SMTP settings
2. Натисніть "Create SMTP credentials"
3. Введіть IAM user name: `tesigo-smtp-user`
4. AWS створить:
   - SMTP Username (IAM username)
   - SMTP Password (автоматично згенерований)
5. **⚠️ ВАЖЛИВО:** Скопіюйте обидва зараз!

**Формат:**
- Username: `AKIAIOSFODNN7EXAMPLE` (IAM access key)
- Password: `wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY` (автоматично згенерований)

---

### КРОК 4: Вийти з Sandbox Mode (Production)

**AWS SES починає в Sandbox режимі:**
- ⚠️ Можна відправляти ТІЛЬКИ на верифіковані email
- ⚠️ Для production потрібно вийти з Sandbox

**Як вийти:**

1. AWS Console → SES → Account dashboard
2. Натисніть "Request production access"
3. Заповніть форму:
   - **Use case:** Select "Transactional" → "Account management emails"
   - **Website URL:** `https://tesigo.com`
   - **Describe your use case:**
     ```
     TesiGo Platform - AI-powered thesis generation service.
     Sending:
     - Magic link authentication emails
     - Document generation completion notifications
     - System alerts
     ```
   - **Additional contact email:** Ваш email
4. Натисніть "Submit"

**Час затвердження:** 1-2 дні

**Після затвердження:**
- ✅ Можна відправляти на будь-які email
- ✅ Ліміт: 50,000 листів/день (автоматично)
- ✅ Можна збільшити через Service Quotas

---

## 🔧 НАЛАШТУВАННЯ В КОДІ

### Оновити `.env` файл:

```bash
# Email - AWS SES
SMTP_HOST=email-smtp.us-east-1.amazonaws.com  # Замініть us-east-1 на ваш region
SMTP_PORT=587
SMTP_USER=AKIAIOSFODNN7EXAMPLE  # Ваш SMTP Username з AWS
SMTP_PASSWORD=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY  # Ваш SMTP Password
SMTP_TLS=true
EMAILS_FROM_EMAIL=noreply@tesigo.com  # Верифікований email/домен
EMAILS_FROM_NAME=TesiGo Platform
```

**Важливо:**
- `SMTP_HOST` залежить від вашого AWS region:
  - `us-east-1` → `email-smtp.us-east-1.amazonaws.com`
  - `us-west-2` → `email-smtp.us-west-2.amazonaws.com`
  - `eu-west-1` → `email-smtp.eu-west-1.amazonaws.com`
  - `eu-central-1` → `email-smtp.eu-central-1.amazonaws.com`
- Знайдіть ваш region в AWS Console → SES → в URL або в налаштуваннях

---

## 📊 ПОРІВНЯННЯ AWS SES vs SENDGRID

| Параметр | AWS SES | SendGrid |
|----------|---------|----------|
| **Вартість** | $0.10/1,000 листів | $19.95/міс (50K/міс) |
| **Free tier** | 62,000/міс (Sandbox) | 100/день |
| **Обмеження** | Немає (після Sandbox) | 100/день (free) |
| **Налаштування** | Середнє | Легке |
| **Інтеграція з AWS** | ✅ Нативна | ⚠️ Зовнішня |
| **Templates** | ⚠️ Через API | ✅ Built-in |
| **Analytics** | ⚠️ CloudWatch | ✅ Dashboard |

**Висновок для AWS хостингу:** AWS SES краще ✅

---

## 💰 ВАРТІСТЬ РОЗРАХУНКИ

### AWS SES:
- **62,000 листів/міс:** Безкоштовно (Sandbox режим)
- **100,000 листів/міс:** $10/міс
- **1,000,000 листів/міс:** $100/міс

### SendGrid:
- **100 листів/день:** Безкоштовно
- **50,000 листів/міс:** $19.95/міс
- **100,000 листів/міс:** $89.95/міс

**Для 100K листів/міс:**
- AWS SES: $10/міс 💰
- SendGrid: $89.95/міс 💰💰💰

**Економія з AWS SES: ~$80/міс!**

---

## 🎯 РЕКОМЕНДОВАНИЙ ПЛАН ДІЙ

### Development (зараз):
1. ✅ Створити AWS SES identity (email)
2. ✅ Створити SMTP credentials
3. ✅ Додати в `.env` з правильним region
4. ✅ Тестувати на верифікованому email

### Production:
1. ✅ Domain verification (верифікувати домен)
2. ✅ Request production access (вийти з Sandbox)
3. ✅ Оновити `EMAILS_FROM_EMAIL` на доменний email
4. ✅ Налаштувати CloudWatch для моніторингу
5. ✅ Тестувати в production

---

## 🔐 БЕЗПЕКА AWS SES

### SMTP Credentials:
- ✅ Зберігайте в `.env` (не в git!)
- ✅ Використовуйте IAM policy для обмеження прав
- ✅ Ротація ключів кожні 90 днів (рекомендовано)

### IAM Policy (опціонально):
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "ses:SendEmail",
        "ses:SendRawEmail"
      ],
      "Resource": "*"
    }
  ]
}
```

---

## ✅ ПЕРЕКЛЮЧЕННЯ З SENDGRID НА AWS SES

### Якщо вже налаштовано SendGrid:

1. **Створити AWS SES identity** (email або domain)
2. **Отримати SMTP credentials** з AWS
3. **Оновити `.env`:**
   ```bash
   # Замінити SendGrid налаштування:
   SMTP_HOST=email-smtp.us-east-1.amazonaws.com  # Ваш region
   SMTP_PORT=587
   SMTP_USER=AKIAIOSFODNN7EXAMPLE  # AWS SMTP username
   SMTP_PASSWORD=aws_smtp_password  # AWS SMTP password
   ```
4. **Перезапустити API**
5. **Протестувати**

**Код не потрібно змінювати!** `NotificationService` працює з будь-яким SMTP.

---

## 📋 ЧЕКЛИСТ

### Development:
- [ ] AWS Console → SES → Verified identities → Create (email)
- [ ] Перевірити email inbox → підтвердити
- [ ] SES → SMTP settings → Create SMTP credentials
- [ ] Скопіювати Username та Password
- [ ] Додати в `.env` з правильним region
- [ ] Перезапустити API
- [ ] Протестувати відправку

### Production:
- [ ] Domain verification (верифікувати домен)
- [ ] Додати DNS записи з AWS
- [ ] Request production access
- [ ] Оновити `.env` з доменним email
- [ ] Налаштувати CloudWatch alerts
- [ ] Тестувати deliverability

---

**Документ створено:** 2025-01-14
**Для:** AWS хостинг з AWS SES
