#!/usr/bin/env python3
"""
Runtime тестування використання JWT token
Тестує endpoint /api/v1/auth/me з реальним JWT token на запущеному сервері
"""

import os
import sys
import requests
import json
from typing import Optional, Dict, Any

# Додаємо шлях до API для імпорту
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'apps', 'api'))

# Налаштування
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
TEST_EMAIL = os.getenv("TEST_EMAIL", "test@example.com")

# Кольори для виводу
GREEN = '\033[0;32m'
RED = '\033[0;31m'
YELLOW = '\033[1;33m'
BLUE = '\033[0;34m'
NC = '\033[0m'  # No Color


def print_header(text: str):
    """Друкує заголовок тесту"""
    print(f"\n{BLUE}{'=' * 70}{NC}")
    print(f"{BLUE}{text}{NC}")
    print(f"{BLUE}{'=' * 70}{NC}\n")


def print_success(text: str):
    """Друкує успішний результат"""
    print(f"{GREEN}✅ {text}{NC}")


def print_error(text: str):
    """Друкує помилку"""
    print(f"{RED}❌ {text}{NC}")


def print_warning(text: str):
    """Друкує попередження"""
    print(f"{YELLOW}⚠️  {text}{NC}")


def test_health() -> bool:
    """Перевірка чи сервер працює"""
    print_header("ТЕСТ 1: Перевірка health endpoint")
    try:
        response = requests.get(f"{API_BASE_URL}/health", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print_success(f"Сервер працює: {data.get('status', 'unknown')}")
            print(f"   Version: {data.get('version', 'unknown')}")
            print(f"   Environment: {data.get('environment', 'unknown')}")
            return True
        else:
            print_error(f"Сервер повернув статус {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print_error(f"Не вдалося підключитися до сервера {API_BASE_URL}")
        print("   Переконайтеся, що сервер запущено")
        return False
    except Exception as e:
        print_error(f"Помилка підключення до сервера: {e}")
        return False


def get_jwt_token_via_magic_link() -> Optional[Dict[str, Any]]:
    """Отримує JWT token через magic link"""
    print_header("ТЕСТ 2: Отримання JWT token через magic link")

    # Крок 1: Запит magic link
    print(f"\n📤 Крок 1: Запит magic link для {TEST_EMAIL}")
    try:
        response = requests.post(
            f"{API_BASE_URL}/api/v1/auth/magic-link",
            json={"email": TEST_EMAIL},
            headers={
                "Content-Type": "application/json",
                "X-CSRF-Token": "test-csrf-token-runtime-test-12345678"  # CSRF token для тестування
            },
            timeout=10
        )

        if response.status_code == 200:
            data = response.json()
            print_success("Magic link запит успішний")
            print(f"   Message: {data.get('message', 'N/A')}")

            # У dev режимі може повертатися magic_link
            magic_link = data.get('magic_link')
            if magic_link:
                print(f"   Magic link: {magic_link[:50]}...")
                # Витягуємо token з magic link
                if 'token=' in magic_link:
                    token = magic_link.split('token=')[1].split('&')[0]
                    return verify_magic_link_token(token)
        else:
            print_warning(f"Magic link запит повернув статус {response.status_code}")
            print(f"   Response: {response.text[:200]}")
            return None

    except Exception as e:
        print_error(f"Помилка при запиті magic link: {e}")
        return None


def verify_magic_link_token(token: str) -> Optional[Dict[str, Any]]:
    """Верифікує magic link token і отримує JWT tokens"""
    print("\n📤 Крок 2: Верифікація magic link token")
    try:
        response = requests.post(
            f"{API_BASE_URL}/api/v1/auth/verify-magic-link",
            json={"token": token},
            headers={
                "Content-Type": "application/json",
                "X-CSRF-Token": "test-csrf-token-runtime-test-12345678"
            },
            timeout=10
        )

        if response.status_code == 200:
            data = response.json()
            print_success("Magic link верифіковано успішно")

            access_token = data.get('access_token')
            refresh_token = data.get('refresh_token')
            user = data.get('user', {})

            if access_token:
                print(f"   Access token отримано: {access_token[:30]}...")
                print(f"   User ID: {user.get('id', 'N/A')}")
                print(f"   Email: {user.get('email', 'N/A')}")
                return {
                    'access_token': access_token,
                    'refresh_token': refresh_token,
                    'user': user
                }
            else:
                print_error("Access token не знайдено в відповіді")
                return None
        else:
            print_error(f"Верифікація повернула статус {response.status_code}")
            print(f"   Response: {response.text[:300]}")
            return None

    except Exception as e:
        print_error(f"Помилка при верифікації magic link: {e}")
        return None


def check_auth_me_endpoint(access_token: str) -> bool:
    """Тестує endpoint /api/v1/auth/me з JWT token"""
    print_header("ТЕСТ 3: Тестування /api/v1/auth/me з JWT token")

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

    try:
        print(f"\n📤 Запит: GET {API_BASE_URL}/api/v1/auth/me")
        print(f"   Token: {access_token[:30]}...")

        response = requests.get(
            f"{API_BASE_URL}/api/v1/auth/me",
            headers=headers,
            timeout=10
        )

        print(f"\n📥 Status Code: {response.status_code}")
        response_text = response.text

        # КРИТИЧНА ПЕРЕВІРКА: чи є помилка типів даних
        if response.status_code == 200:
            try:
                data = response.json()
                print_success("✅ Endpoint працює! Помилка типів НЕ виникає!")
                print("\n   User data:")
                print(f"   - ID: {data.get('id', 'N/A')}")
                print(f"   - Email: {data.get('email', 'N/A')}")
                print(f"   - Full Name: {data.get('full_name', 'N/A')}")
                print(f"   - Is Verified: {data.get('is_verified', 'N/A')}")
                print(f"   - Is Active: {data.get('is_active', 'N/A')}")
                return True
            except json.JSONDecodeError:
                print_error("Відповідь не є валідним JSON")
                print(f"   Response: {response_text[:300]}")
                return False
        else:
            # Перевірка на помилку типів даних
            if "integer = character varying" in response_text or "VARCHAR" in response_text:
                print_error("КРИТИЧНО: Помилка типів даних все ще існує!")
                print("   Помилка: integer = character varying")
                print(f"   Response: {response_text[:500]}")
                return False
            elif "Invalid or expired token" in response_text or "401" in str(response.status_code):
                print_warning("Token невалідний або прострочений")
                print(f"   Response: {response_text[:300]}")
                return False
            else:
                print_error(f"Endpoint повернув помилку (статус {response.status_code})")
                print(f"   Response: {response_text[:300]}")
                return False

    except requests.exceptions.Timeout:
        print_error("Таймаут запиту")
        return False
    except Exception as e:
        print_error(f"Помилка: {e}")
        return False


def test_with_existing_token() -> Optional[str]:
    """Спробує використати існуючий токен з environment variable"""
    token = os.getenv("ACCESS_TOKEN")
    if token:
        print_warning("Використовується токен з ACCESS_TOKEN environment variable")
        return token
    return None


def main():
    """Головна функція тестування"""
    print(f"\n{BLUE}{'=' * 70}{NC}")
    print(f"{BLUE}RUNTIME ТЕСТУВАННЯ: Використання JWT Token{NC}")
    print(f"{BLUE}{'=' * 70}{NC}")
    print(f"\nAPI Base URL: {API_BASE_URL}")
    print(f"Test Email: {TEST_EMAIL}\n")

    # Тест 1: Health check
    if not test_health():
        print(f"\n{RED}❌ Сервер не доступний. Завершення тестування.{NC}")
        sys.exit(1)

    # Спробуємо використати існуючий токен
    access_token = test_with_existing_token()

    # Якщо токену немає, отримуємо через magic link
    if not access_token:
        token_data = get_jwt_token_via_magic_link()
        if not token_data:
            print(f"\n{YELLOW}⚠️  Не вдалося отримати JWT token. Завершення тестування.{NC}")
            print(f"\n{YELLOW}Підказка: Можна встановити ACCESS_TOKEN environment variable для використання існуючого токена{NC}")
            sys.exit(1)
        access_token = token_data['access_token']

    # Тест 3: Використання JWT token
    result = check_auth_me_endpoint(access_token)

    # Підсумок
    print_header("ПІДСУМОК ТЕСТУВАННЯ")
    if result:
        print_success("ТЕСТ ПРОЙДЕНО: JWT token працює правильно!")
        print_success("Помилка типів даних НЕ виявлена")
        print(f"\n{GREEN}✅ Всі перевірки пройдені успішно!{NC}")
        sys.exit(0)
    else:
        print_error("ТЕСТ НЕ ПРОЙДЕНО: Проблеми з використанням JWT token")
        print(f"\n{RED}❌ Потрібно виправити проблеми перед продовженням{NC}")
        sys.exit(1)


if __name__ == "__main__":
    main()
