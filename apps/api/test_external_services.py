#!/usr/bin/env python3
"""
External Services Integration Test
Tests all critical external APIs for TesiGo platform
"""

import os
import sys

from dotenv import load_dotenv

# Load environment variables
load_dotenv()


def test_openai():
    """Test OpenAI API connection"""
    print("\n🤖 Testing OpenAI API...")
    try:
        from openai import OpenAI

        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

        # Simple completion test
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": "Say 'hello'"}],
            max_tokens=10,
        )

        print(f"✅ OpenAI response: {response.choices[0].message.content}")
        print(f"✅ Tokens used: {response.usage.total_tokens}")
        return True

    except Exception as e:
        print(f"❌ OpenAI error: {e}")
        return False


def test_anthropic():
    """Test Anthropic Claude API connection"""
    print("\n🤖 Testing Anthropic Claude API...")
    try:
        from anthropic import Anthropic

        client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

        response = client.messages.create(
            model="claude-3-haiku-20240307",  # Cheapest model for testing
            max_tokens=10,
            messages=[{"role": "user", "content": "Say 'hello'"}],
        )

        print(f"✅ Anthropic response: {response.content[0].text}")
        print(
            f"✅ Tokens: in={response.usage.input_tokens}, out={response.usage.output_tokens}"
        )
        return True

    except Exception as e:
        print(f"❌ Anthropic error: {e}")
        return False


def test_stripe():
    """Test Stripe API connection"""
    print("\n💳 Testing Stripe API...")
    try:
        import stripe

        stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

        # Test API key validity
        account = stripe.Account.retrieve()
        print(f"✅ Stripe account: {account.id}")
        print(f"✅ Account email: {account.email or 'N/A'}")

        # Create test customer
        customer = stripe.Customer.create(
            email="test-external-check@tesigo.com",
            description="External Services Health Check",
        )
        print(f"✅ Test customer created: {customer.id}")

        # Create test payment intent
        intent = stripe.PaymentIntent.create(
            amount=100,  # €1.00
            currency="eur",
            customer=customer.id,
            description="Health check test payment",
        )
        print(f"✅ Payment intent: {intent.id}, status: {intent.status}")

        # Cleanup
        stripe.Customer.delete(customer.id)
        print("✅ Test customer deleted")

        return True

    except Exception as e:
        print(f"❌ Stripe error: {e}")
        return False


def test_email():
    """Test Email/SMTP connection"""
    print("\n📧 Testing Email Service...")
    try:
        import smtplib

        smtp_host = os.getenv("SMTP_HOST")
        smtp_port = int(os.getenv("SMTP_PORT", "587"))
        smtp_user = os.getenv("SMTP_USER")
        smtp_pass = os.getenv("SMTP_PASSWORD")

        if not all([smtp_host, smtp_user, smtp_pass]):
            print("⚠️ SMTP credentials not configured (optional for testing)")
            return None

        # Connect to SMTP
        server = smtplib.SMTP(smtp_host, smtp_port, timeout=10)
        server.ehlo()
        server.starttls()
        server.login(smtp_user, smtp_pass)

        print(f"✅ SMTP connection: {smtp_host}:{smtp_port}")
        print("✅ Authentication successful")

        server.quit()
        return True

    except Exception as e:
        print(f"❌ Email error: {e}")
        return False


def test_semantic_scholar():
    """Test Semantic Scholar API"""
    print("\n📚 Testing Semantic Scholar API...")
    try:
        import requests

        url = "https://api.semanticscholar.org/graph/v1/paper/search"
        params = {
            "query": "machine learning",
            "limit": 3,
            "fields": "title,authors,year",
        }

        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()

        data = response.json()
        if data.get("data"):
            paper = data["data"][0]
            print(f"✅ Found papers: {len(data['data'])}")
            print(f"✅ Sample: {paper['title'][:60]}...")
            return True
        else:
            print("❌ No results returned")
            return False

    except Exception as e:
        print(f"❌ Semantic Scholar error: {e}")
        return False


def test_minio():
    """Test MinIO storage connection"""
    print("\n💾 Testing MinIO Storage...")
    try:
        from minio import Minio

        endpoint = os.getenv("MINIO_ENDPOINT", "localhost:9000")
        access_key = os.getenv("MINIO_ACCESS_KEY")
        secret_key = os.getenv("MINIO_SECRET_KEY")
        use_ssl = os.getenv("MINIO_USE_SSL", "false").lower() == "true"

        if not all([access_key, secret_key]):
            print("⚠️ MinIO credentials not configured (optional for testing)")
            return None

        client = Minio(
            endpoint, access_key=access_key, secret_key=secret_key, secure=use_ssl
        )

        # List buckets to verify connection
        buckets = list(client.list_buckets())
        print(f"✅ MinIO connection: {endpoint}")
        print(f"✅ Buckets found: {len(buckets)}")
        if buckets:
            print(f"✅ Sample bucket: {buckets[0].name}")

        return True

    except Exception as e:
        print(f"❌ MinIO error: {e}")
        return False


def main():
    """Run all external service tests"""
    print("=" * 60)
    print("🔬 EXTERNAL SERVICES HEALTH CHECK")
    print("=" * 60)

    results = {}

    # Test all services
    results["OpenAI"] = test_openai()
    results["Anthropic"] = test_anthropic()
    results["Stripe"] = test_stripe()
    results["Email"] = test_email()
    results["Semantic Scholar"] = test_semantic_scholar()
    results["MinIO"] = test_minio()

    # Summary
    print("\n" + "=" * 60)
    print("📊 SUMMARY")
    print("=" * 60)

    passed = sum(1 for v in results.values() if v is True)
    failed = sum(1 for v in results.values() if v is False)
    skipped = sum(1 for v in results.values() if v is None)

    for service, status in results.items():
        icon = "✅" if status is True else "❌" if status is False else "⚠️"
        status_text = (
            "PASS" if status is True else "FAIL" if status is False else "SKIPPED"
        )
        print(f"{icon} {service}: {status_text}")

    print(f"\nTotal: {passed} passed, {failed} failed, {skipped} skipped")

    # Exit code
    if failed > 0:
        print("\n❌ Some services failed!")
        sys.exit(1)
    elif passed == 0:
        print("\n⚠️ No services tested!")
        sys.exit(2)
    else:
        print("\n✅ All critical services operational!")
        sys.exit(0)


if __name__ == "__main__":
    main()
