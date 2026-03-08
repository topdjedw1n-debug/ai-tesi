#!/usr/bin/env python3
"""Quick real API test with actual keys"""
import os

from dotenv import load_dotenv

load_dotenv()


def test_openai_real():
    """Test OpenAI with real API call"""
    print("\n🤖 Testing OpenAI API (real call)...")
    try:
        from openai import OpenAI

        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            print("❌ No API key found in environment")
            return False

        client = OpenAI(api_key=api_key, timeout=30.0, max_retries=2)

        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": "Say 'OpenAI works!'"}],
            max_tokens=10,
        )

        print(f"✅ Response: {response.choices[0].message.content}")
        print(f"✅ Tokens: {response.usage.total_tokens}")
        print(f"✅ Model: {response.model}")
        return True

    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def test_anthropic_real():
    """Test Anthropic with real API call"""
    print("\n🤖 Testing Anthropic Claude API (real call)...")
    try:
        from anthropic import Anthropic

        client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

        response = client.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=10,
            messages=[{"role": "user", "content": "Say 'Claude works!'"}],
        )

        print(f"✅ Response: {response.content[0].text}")
        print(
            f"✅ Tokens: in={response.usage.input_tokens}, out={response.usage.output_tokens}"
        )
        print(f"✅ Model: {response.model}")
        return True

    except Exception as e:
        print(f"❌ Error: {e}")
        return False


if __name__ == "__main__":
    print("=" * 60)
    print("🔬 REAL API CONNECTION TEST")
    print("=" * 60)

    openai_ok = test_openai_real()
    anthropic_ok = test_anthropic_real()

    print("\n" + "=" * 60)
    print("📊 RESULTS")
    print("=" * 60)

    if openai_ok and anthropic_ok:
        print("✅ All AI services operational!")
        print("🎉 Platform ready for document generation!")
    elif openai_ok or anthropic_ok:
        print("⚠️ Some services working, some failed")
    else:
        print("❌ All services failed - check API keys")
