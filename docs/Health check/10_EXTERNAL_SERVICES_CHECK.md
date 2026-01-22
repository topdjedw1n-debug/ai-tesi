# 🔟 ПЕРЕВІРКА ЗОВНІШНІХ СЕРВІСІВ

> **Категорія:** External Services Integration
> **Час виконання:** ~15-20 хвилин
> **Залежності:** API keys configured + Test accounts
> **Критичність:** 🔴 КРИТИЧНА - Core business logic

---

## 🎯 МЕТА ПЕРЕВІРКИ

Переконатися що всі зовнішні API коректно інтегровані та доступні.

**Критичні сервіси:**
- 🤖 **AI APIs:** OpenAI, Anthropic
- 💳 **Payment:** Stripe
- 📧 **Email:** SMTP/SendGrid
- 🔍 **Search:** Tavily, Perplexity, Serper
- 📚 **Academic:** Semantic Scholar
- ✅ **Quality:** GPTZero, Originality.AI, LanguageTool

---

## ✅ ПЕРЕДУМОВИ

- [ ] API keys в `.env` налаштовані
- [ ] Test accounts створені
- [ ] Rate limits відомі
- [ ] Webhook endpoints налаштовані

---

## 📋 ПОКРОКОВА ІНСТРУКЦІЯ

### Крок 1: OpenAI API Test

**Команда:**
```bash
# Test OpenAI connection
curl https://api.openai.com/v1/models \
  -H "Authorization: Bearer $OPENAI_API_KEY" | jq '.data[0].id'

# Очікується: "gpt-4-turbo" або інша модель
```

**Python test:**
```python
# test_openai.py
from openai import OpenAI
import os

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def test_openai_connection():
    try:
        # Simple completion test
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "user", "content": "Say 'hello'"}
            ],
            max_tokens=10
        )
        print(f"✅ OpenAI response: {response.choices[0].message.content}")
        print(f"✅ Tokens used: {response.usage.total_tokens}")
        return True
    except Exception as e:
        print(f"❌ OpenAI error: {e}")
        return False

if __name__ == "__main__":
    test_openai_connection()
```

**Запуск:**
```bash
cd /Users/maxmaxvel/.claude-worktrees/AI\ TESI/stupefied-fermat/apps/api
python test_openai.py
```

**Success criteria:**
- ✅ Connection successful (200)
- ✅ Model list accessible
- ✅ Simple completion works
- ✅ Token usage tracked

---

### Крок 2: Anthropic Claude API Test

**Команда:**
```bash
# Test Anthropic connection
curl https://api.anthropic.com/v1/messages \
  -H "x-api-key: $ANTHROPIC_API_KEY" \
  -H "anthropic-version: 2023-06-01" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "claude-3-sonnet-20240229",
    "messages": [{"role": "user", "content": "Hello"}],
    "max_tokens": 10
  }' | jq '.content[0].text'

# Очікується: "Hello! How can I assist you today?"
```

**Python test:**
```python
# test_anthropic.py
from anthropic import Anthropic
import os

client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

def test_anthropic_connection():
    try:
        response = client.messages.create(
            model="claude-3-sonnet-20240229",
            max_tokens=10,
            messages=[
                {"role": "user", "content": "Say 'hello'"}
            ]
        )
        print(f"✅ Anthropic response: {response.content[0].text}")
        print(f"✅ Tokens: in={response.usage.input_tokens}, out={response.usage.output_tokens}")
        return True
    except Exception as e:
        print(f"❌ Anthropic error: {e}")
        return False

if __name__ == "__main__":
    test_anthropic_connection()
```

**Success criteria:**
- ✅ Connection successful
- ✅ Claude responds
- ✅ Token tracking works

---

### Крок 3: Stripe Payment Test

**Команда:**
```bash
# Test Stripe connection
curl https://api.stripe.com/v1/customers \
  -u $STRIPE_SECRET_KEY: \
  -d "email=test@example.com" | jq '.id'

# Очікується: "cus_..."
```

**Create test payment intent:**
```bash
# Create test PaymentIntent
curl https://api.stripe.com/v1/payment_intents \
  -u $STRIPE_SECRET_KEY: \
  -d "amount=500" \
  -d "currency=eur" \
  -d "payment_method_types[]=card" \
  | jq '{id, status, amount, currency}'

# Очікується:
# {
#   "id": "pi_...",
#   "status": "requires_payment_method",
#   "amount": 500,
#   "currency": "eur"
# }
```

**Python test:**
```python
# test_stripe.py
import stripe
import os

stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

def test_stripe_connection():
    try:
        # Test API key
        account = stripe.Account.retrieve()
        print(f"✅ Stripe account: {account.id}")

        # Create test customer
        customer = stripe.Customer.create(
            email="test-e2e@example.com",
            description="E2E Test Customer"
        )
        print(f"✅ Test customer: {customer.id}")

        # Create test payment intent
        intent = stripe.PaymentIntent.create(
            amount=500,  # €5.00
            currency="eur",
            customer=customer.id
        )
        print(f"✅ Payment intent: {intent.id}, status: {intent.status}")

        # Cleanup
        stripe.Customer.delete(customer.id)
        print(f"✅ Test customer deleted")

        return True
    except Exception as e:
        print(f"❌ Stripe error: {e}")
        return False

if __name__ == "__main__":
    test_stripe_connection()
```

**Success criteria:**
- ✅ Account retrievable
- ✅ Customer creation works
- ✅ PaymentIntent creation works
- ✅ Cleanup successful

---

### Крок 4: Email Service Test (SMTP)

**Python test:**
```python
# test_email.py
import smtplib
from email.mime.text import MIMEText
import os

def test_email_connection():
    try:
        smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
        smtp_port = int(os.getenv("SMTP_PORT", "587"))
        smtp_user = os.getenv("SMTP_USER")
        smtp_pass = os.getenv("SMTP_PASSWORD")

        # Connect to SMTP
        server = smtplib.SMTP(smtp_host, smtp_port)
        server.ehlo()
        server.starttls()
        server.login(smtp_user, smtp_pass)

        print(f"✅ SMTP connection: {smtp_host}:{smtp_port}")

        # Send test email
        msg = MIMEText("E2E test email from TesiGo")
        msg["Subject"] = "TesiGo E2E Test"
        msg["From"] = smtp_user
        msg["To"] = smtp_user  # Відправити собі

        server.send_message(msg)
        print(f"✅ Test email sent to {smtp_user}")

        server.quit()
        return True

    except Exception as e:
        print(f"❌ Email error: {e}")
        return False

if __name__ == "__main__":
    test_email_connection()
```

**Success criteria:**
- ✅ SMTP connection successful
- ✅ Authentication works
- ✅ Email delivered (перевірити inbox)

---

### Крок 5: Semantic Scholar API Test

**Команда:**
```bash
# Test Semantic Scholar
curl "https://api.semanticscholar.org/graph/v1/paper/search?query=artificial+intelligence&limit=5" \
  | jq '.data[0] | {title, authors: .authors[0].name}'

# Очікується результат з papers
```

**Python test:**
```python
# test_semantic_scholar.py
import requests

def test_semantic_scholar():
    try:
        url = "https://api.semanticscholar.org/graph/v1/paper/search"
        params = {
            "query": "machine learning",
            "limit": 5,
            "fields": "title,authors,year,citationCount"
        }

        response = requests.get(url, params=params, timeout=10)
        data = response.json()

        if data.get("data"):
            print(f"✅ Found {len(data['data'])} papers")
            for paper in data["data"][:2]:
                print(f"  - {paper.get('title')} ({paper.get('year')})")
            return True
        else:
            print("❌ No papers found")
            return False

    except Exception as e:
        print(f"❌ Semantic Scholar error: {e}")
        return False

if __name__ == "__main__":
    test_semantic_scholar()
```

**Success criteria:**
- ✅ API accessible (200)
- ✅ Papers returned
- ✅ Metadata complete

---

### Крок 6: Tavily Search API Test

**Команда:**
```bash
# Test Tavily (якщо є API key)
curl -X POST https://api.tavily.com/search \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TAVILY_API_KEY" \
  -d '{
    "query": "latest AI research",
    "max_results": 3
  }' | jq '.results[0].title'
```

**Python test:**
```python
# test_tavily.py
import requests
import os

def test_tavily_search():
    try:
        api_key = os.getenv("TAVILY_API_KEY")
        if not api_key:
            print("⚠️ TAVILY_API_KEY not set")
            return False

        url = "https://api.tavily.com/search"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }
        payload = {
            "query": "artificial intelligence healthcare",
            "max_results": 3
        }

        response = requests.post(url, json=payload, headers=headers, timeout=10)
        data = response.json()

        if data.get("results"):
            print(f"✅ Tavily: {len(data['results'])} results")
            return True
        else:
            print("❌ No results from Tavily")
            return False

    except Exception as e:
        print(f"❌ Tavily error: {e}")
        return False

if __name__ == "__main__":
    test_tavily_search()
```

---

### Крок 7: Perplexity API Test

**Python test:**
```python
# test_perplexity.py
import requests
import os

def test_perplexity():
    try:
        api_key = os.getenv("PERPLEXITY_API_KEY")
        if not api_key:
            print("⚠️ PERPLEXITY_API_KEY not set")
            return False

        url = "https://api.perplexity.ai/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": "llama-3.1-sonar-small-128k-online",
            "messages": [
                {"role": "user", "content": "What is AI?"}
            ]
        }

        response = requests.post(url, json=payload, headers=headers, timeout=15)
        data = response.json()

        if data.get("choices"):
            print(f"✅ Perplexity response: {data['choices'][0]['message']['content'][:100]}...")
            return True
        else:
            print("❌ No response from Perplexity")
            return False

    except Exception as e:
        print(f"❌ Perplexity error: {e}")
        return False

if __name__ == "__main__":
    test_perplexity()
```

---

### Крок 8: LanguageTool Grammar Check

**Команда:**
```bash
# Test LanguageTool public API
curl -X POST https://api.languagetool.org/v2/check \
  -d "text=This are an test." \
  -d "language=en-US" | jq '.matches[0].message'

# Очікується: "Subject-Verb Agreement error"
```

**Python test:**
```python
# test_languagetool.py
import requests

def test_languagetool():
    try:
        url = "https://api.languagetool.org/v2/check"
        data = {
            "text": "This are an grammar test.",
            "language": "en-US"
        }

        response = requests.post(url, data=data, timeout=10)
        result = response.json()

        if result.get("matches"):
            print(f"✅ LanguageTool: {len(result['matches'])} errors detected")
            for match in result["matches"][:2]:
                print(f"  - {match['message']}")
            return True
        else:
            print("⚠️ No errors detected (expected some)")
            return False

    except Exception as e:
        print(f"❌ LanguageTool error: {e}")
        return False

if __name__ == "__main__":
    test_languagetool()
```

---

### Крок 9: GPTZero AI Detection Test

**Python test:**
```python
# test_gptzero.py
import requests
import os

def test_gptzero():
    try:
        api_key = os.getenv("GPTZERO_API_KEY")
        if not api_key:
            print("⚠️ GPTZERO_API_KEY not set")
            return False

        url = "https://api.gptzero.me/v2/predict/text"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "document": "This is a test document to check AI detection."
        }

        response = requests.post(url, json=payload, headers=headers, timeout=15)
        data = response.json()

        if "completely_generated_prob" in data:
            prob = data["completely_generated_prob"]
            print(f"✅ GPTZero AI probability: {prob*100:.1f}%")
            return True
        else:
            print("❌ GPTZero response invalid")
            return False

    except Exception as e:
        print(f"❌ GPTZero error: {e}")
        return False

if __name__ == "__main__":
    test_gptzero()
```

---

### Крок 10: All Services Health Check

**Unified test script:**
```python
# test_all_services.py
import sys
from test_openai import test_openai_connection
from test_anthropic import test_anthropic_connection
from test_stripe import test_stripe_connection
from test_email import test_email_connection
from test_semantic_scholar import test_semantic_scholar
from test_languagetool import test_languagetool

services = [
    ("OpenAI", test_openai_connection),
    ("Anthropic", test_anthropic_connection),
    ("Stripe", test_stripe_connection),
    ("Email (SMTP)", test_email_connection),
    ("Semantic Scholar", test_semantic_scholar),
    ("LanguageTool", test_languagetool),
]

def main():
    print("=" * 60)
    print("EXTERNAL SERVICES HEALTH CHECK")
    print("=" * 60)

    results = {}
    for name, test_func in services:
        print(f"\nTesting {name}...")
        try:
            results[name] = test_func()
        except Exception as e:
            print(f"❌ {name} exception: {e}")
            results[name] = False

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    for name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} - {name}")

    total = len(results)
    passed = sum(1 for v in results.values() if v)
    print(f"\nTotal: {passed}/{total} services operational")

    if passed < total:
        print("\n⚠️ Some services failed - check logs above")
        sys.exit(1)
    else:
        print("\n✅ All services operational")
        sys.exit(0)

if __name__ == "__main__":
    main()
```

**Запуск:**
```bash
cd /Users/maxmaxvel/.claude-worktrees/AI\ TESI/stupefied-fermat/apps/api
python test_all_services.py
```

---

## 🔍 ПЕРЕВІРКА РЕЗУЛЬТАТІВ

### Чеклист успішного проходження:

**Critical Services (Must Pass):**
- [ ] OpenAI API accessible
- [ ] Anthropic API accessible (OR OpenAI backup)
- [ ] Stripe API accessible
- [ ] Email service working

**Important Services (Should Pass):**
- [ ] Semantic Scholar accessible
- [ ] LanguageTool working

**Optional Services (Can Fail):**
- [ ] Tavily API (якщо налаштовано)
- [ ] Perplexity API (якщо налаштовано)
- [ ] GPTZero API (опціонально)

---

## ⚠️ ТИПОВІ ПОМИЛКИ ТА РІШЕННЯ

| Помилка | Причина | Рішення |
|---------|---------|---------|
| `401 Unauthorized` | Invalid API key | Перевірити `.env` |
| `429 Rate Limit` | Too many requests | Wait або use fallback |
| `Timeout` | Slow network | Increase timeout |
| `SSL Certificate Error` | Certificates issue | Update certifi package |
| `Connection refused` | Service down | Check status page |

---

## 📊 КРИТЕРІЇ УСПІШНОСТІ

### ✅ ТЕСТ ПРОЙДЕНО ЯКЩО:

- **OpenAI OR Anthropic** працює (мінімум 1)
- **Stripe** працює
- **Email** працює
- **Semantic Scholar** accessible
- **LanguageTool** accessible

### ❌ ТЕСТ ПРОВАЛЕНО ЯКЩО:

- **ALL AI providers** fail
- **Stripe** fails
- **Email** fails (критично для auth)

**Допустимо:** Tavily/Perplexity/GPTZero fails (опціональні)

---

## 🔧 FALLBACK MECHANISMS

**AI Provider Fallback:**
```python
providers = ["openai", "anthropic"]
for provider in providers:
    try:
        result = call_ai_api(provider)
        return result
    except Exception:
        continue
# If all fail → return error
```

**Search Fallback:**
```python
search_apis = ["tavily", "perplexity", "semantic_scholar"]
# Try in order, use first that works
```

---

## 🔗 ЗВ'ЯЗОК З ІНШИМИ ПЕРЕВІРКАМИ

**⬆️ Залежить від:**
- `02_CONFIGURATION_CHECK.md` - API keys

**⬇️ Впливає на:**
- AI generation pipeline
- Payment processing
- Email notifications
- Quality checks

**Критичність:** 🔴 КРИТИЧНА - без цих сервісів система не працює!

---

## 🚀 ШВИДКИЙ СТАРТ

```bash
# Quick external services check
cd apps/api
python test_all_services.py

# Або через pytest
pytest tests/test_external_services.py -v
```

---

## 📝 RATE LIMITS (Важливо!)

| Service | Free Tier Limit | Production Limit |
|---------|-----------------|------------------|
| OpenAI | 3 RPM | 60 RPM (paid) |
| Anthropic | 5 RPM | 50 RPM (paid) |
| Stripe | No limit | No limit |
| Semantic Scholar | 100 RPM | Same |
| LanguageTool | 20 req/min | Unlimited (self-hosted) |

**Важливо:** Implement retry with exponential backoff!

---

**Дата створення:** 2025-12-03
**Версія:** 1.0
**Автор:** AI Assistant
**Попередня перевірка:** `09_E2E_TESTS_CHECK.md`
**Статус:** ✅ ЗАВЕРШЕНО - Це остання перевірка!
