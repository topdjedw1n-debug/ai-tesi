#!/usr/bin/env python3
"""Test OpenAI with requests library directly"""
import os

import requests
from dotenv import load_dotenv

load_dotenv()


def test_openai_with_requests():
    """Test OpenAI using requests (not SDK)"""
    print("\n🤖 Testing OpenAI with requests library...")

    api_key = os.getenv("OPENAI_API_KEY")

    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}

    data = {
        "model": "gpt-3.5-turbo",
        "messages": [{"role": "user", "content": "Say 'OpenAI works!'"}],
        "max_tokens": 10,
    }

    try:
        response = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers=headers,
            json=data,
            timeout=30,
        )

        if response.status_code == 200:
            result = response.json()
            content = result["choices"][0]["message"]["content"]
            print(f"✅ Response: {content}")
            print(f"✅ Model: {result['model']}")
            print(f"✅ Tokens: {result['usage']['total_tokens']}")
            return True
        else:
            print(f"❌ Status: {response.status_code}")
            print(f"❌ Error: {response.text}")
            return False

    except Exception as e:
        print(f"❌ Exception: {e}")
        return False


if __name__ == "__main__":
    test_openai_with_requests()
