# 📧 Email Setup Guide

> **Налаштування email для TesiGo Platform**

**Updated:** 2026-01-22

---

## 🎯 Quick Start (Development)

### Option 1: Gmail (5 min)

1. Go to: https://myaccount.google.com/apppasswords
2. Create App Password: "Mail" → "Other" → "TesiGo"
3. Copy 16-character password

Add to `apps/api/.env`:
```bash
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=abcd efgh ijkl mnop
SMTP_TLS=true
EMAILS_FROM_EMAIL=your-email@gmail.com
EMAILS_FROM_NAME=TesiGo Platform
```

### Option 2: Mailtrap (Testing)

1. Register at https://mailtrap.io
2. Get credentials: Sandbox → SMTP Settings

```bash
SMTP_HOST=sandbox.smtp.mailtrap.io
SMTP_PORT=2525
SMTP_TLS=false
SMTP_USER=your-mailtrap-user
SMTP_PASSWORD=your-mailtrap-password
EMAILS_FROM_EMAIL=noreply@tesigo.local
EMAILS_FROM_NAME=TesiGo
```

---

## 🚀 Production Setup

### Option A: SendGrid

**Best for:** Non-AWS hosting, ready templates

1. Register at https://sendgrid.com
2. Settings → API Keys → Create API Key

```bash
SMTP_HOST=smtp.sendgrid.net
SMTP_PORT=587
SMTP_USER=apikey
SMTP_PASSWORD=SG.your_api_key
SMTP_TLS=true
EMAILS_FROM_EMAIL=noreply@your-domain.com
EMAILS_FROM_NAME=TesiGo Platform
```

**Pricing:** $19.95/month for 50K emails

---

### Option B: AWS SES (Recommended for AWS)

**Best for:** AWS hosting, cost-effective ($0.10 per 1,000 emails)

#### Step 1: Verify Domain

1. AWS Console → SES → Verified identities
2. Click "Create identity" → Select "Domain"
3. Enter: `tesigo.com`
4. Add DNS records (SPF, DKIM, CNAME) to your DNS provider
5. Wait for verification (1-24 hours)

#### Step 2: Create SMTP Credentials

1. AWS Console → SES → SMTP settings
2. Click "Create SMTP credentials"
3. Name: `tesigo-smtp-user`
4. **Save credentials immediately!**

```bash
SMTP_HOST=email-smtp.eu-central-1.amazonaws.com
SMTP_PORT=587
SMTP_USER=AKIAIOSFODNN7EXAMPLE
SMTP_PASSWORD=your-generated-password
SMTP_TLS=true
EMAILS_FROM_EMAIL=noreply@tesigo.com
EMAILS_FROM_NAME=TesiGo Platform
```

#### Step 3: Exit Sandbox Mode

**Required for production (sending to unverified emails)**

1. AWS Console → SES → Account dashboard
2. Click "Request production access"
3. Fill form:
   - Use case: "Transactional" → "Account management emails"
   - Website: `https://tesigo.com`
   - Description: "Magic link authentication, document notifications"
4. Wait for approval (24-48 hours)

---

## 🧪 Testing

```bash
# Restart API
cd apps/api
uvicorn main:app --reload

# Test login flow
# 1. Go to http://localhost:3000
# 2. Enter email
# 3. Check inbox for magic link
```

---

## 🔧 Troubleshooting

### Email not arriving?

1. **Check spam folder**
2. **Verify .env loaded:** `echo $SMTP_HOST` in terminal
3. **Check logs:** `tail -f apps/api/logs/app.log | grep email`
4. **Test SMTP connection:**
   ```python
   import smtplib
   server = smtplib.SMTP('smtp.gmail.com', 587)
   server.starttls()
   server.login('user', 'password')
   ```

### AWS SES specific

- **Sandbox mode:** Can only send to verified emails
- **Sending limits:** 200/day in sandbox, request increase
- **Bounce rate:** Keep under 5% or account suspended

---

## 📊 Provider Comparison

| Feature | Gmail | Mailtrap | SendGrid | AWS SES |
|---------|-------|----------|----------|---------|
| **Cost** | Free | Free | $19.95/mo | $0.10/1K |
| **Setup** | 5 min | 5 min | 10 min | 30 min |
| **Best for** | Dev | Testing | Production | AWS hosting |
| **Limits** | 500/day | Test only | 50K/mo | Unlimited |
