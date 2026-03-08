#!/usr/bin/env python3
"""Quick API key validation check"""
import os

from dotenv import load_dotenv

load_dotenv()


def check_key_format(key_name, expected_prefix):
    """Check if API key looks valid"""
    key = os.getenv(key_name, "")

    print(f"\n{key_name}:")
    print(f"  Present: {'Yes' if key else 'No'}")
    print(f"  Length: {len(key)}")
    print(f"  Prefix: {key[:15]}...")

    if "your-" in key.lower() or "here" in key.lower():
        print("  Status: ❌ PLACEHOLDER (contains 'your-' or 'here')")
        return False
    elif key.startswith(expected_prefix) and len(key) > 40:
        print("  Status: ✅ LOOKS VALID (correct format)")
        return True
    else:
        print("  Status: ⚠️ UNKNOWN FORMAT")
        return None


print("=" * 60)
print("API KEY FORMAT CHECK")
print("=" * 60)

results = {
    "OpenAI": check_key_format("OPENAI_API_KEY", "sk-proj-"),
    "Anthropic": check_key_format("ANTHROPIC_API_KEY", "sk-ant-"),
    "Stripe": check_key_format("STRIPE_SECRET_KEY", "sk_test_"),
}

print("\n" + "=" * 60)
print("SUMMARY")
print("=" * 60)

valid = sum(1 for v in results.values() if v is True)
invalid = sum(1 for v in results.values() if v is False)

for service, status in results.items():
    icon = "✅" if status else "❌" if status is False else "⚠️"
    print(f"{icon} {service}")

print(f"\nValid: {valid}, Invalid: {invalid}")

if invalid > 0:
    print("\n💡 TIP: Replace placeholder keys with real keys:")
    print("  - OpenAI: https://platform.openai.com/api-keys")
    print("  - Anthropic: https://console.anthropic.com/settings/keys")
    print("  - Stripe: https://dashboard.stripe.com/test/apikeys")
