#!/usr/bin/env python3
"""
JWT Refresh Token Runtime Test Script
Tests all aspects of the JWT refresh token functionality
"""

import requests
import json
import time
from typing import Dict, Any, List

API_BASE = "http://localhost:8000"
TEST_EMAIL = "test@example.com"

# CSRF token for testing (required by CSRFMiddleware)
CSRF_TOKEN = "test-csrf-token-1234567890"

def get_headers(include_auth: str = None) -> Dict[str, str]:
    """Get headers with CSRF token and optional auth"""
    headers = {
        "X-CSRF-Token": CSRF_TOKEN,
        "Content-Type": "application/json"
    }
    if include_auth:
        headers["Authorization"] = f"Bearer {include_auth}"
    return headers

class TestResults:
    def __init__(self):
        self.results = []
        self.passed = 0
        self.failed = 0

    def add(self, name: str, passed: bool, details: str = ""):
        self.results.append({
            "test": name,
            "status": "PASS" if passed else "FAIL",
            "details": details
        })
        if passed:
            self.passed += 1
        else:
            self.failed += 1

    def print_summary(self):
        print("\n" + "="*80)
        print("TEST SUMMARY")
        print("="*80)
        for r in self.results:
            status_icon = "✓" if r["status"] == "PASS" else "✗"
            print(f"{status_icon} {r['test']}: {r['status']}")
            if r["details"]:
                print(f"  → {r['details']}")
        print("="*80)
        print(f"Total: {len(self.results)} | Passed: {self.passed} | Failed: {self.failed}")
        print("="*80)

def test_magic_link_request(results: TestResults) -> Dict[str, Any]:
    """Test requesting a magic link"""
    print("\n[1/9] Testing magic link request...")
    try:
        response = requests.post(
            f"{API_BASE}/api/v1/auth/magic-link",
            json={"email": TEST_EMAIL},
            headers=get_headers(),
            timeout=10
        )

        if response.status_code == 200:
            data = response.json()
            results.add("Magic Link Request", True, f"Magic link generated for {TEST_EMAIL}")
            return data
        else:
            results.add("Magic Link Request", False, f"Status: {response.status_code}, Response: {response.text}")
            return {}
    except Exception as e:
        results.add("Magic Link Request", False, f"Exception: {str(e)}")
        return {}

def test_magic_link_verification(results: TestResults, magic_link_data: Dict[str, Any]) -> Dict[str, Any]:
    """Test verifying magic link and getting tokens"""
    print("\n[2/9] Testing magic link verification...")
    try:
        if not magic_link_data or "magic_link" not in magic_link_data:
            results.add("Magic Link Verification", False, "No magic link data available")
            return {}

        # Extract token from magic link
        magic_link = magic_link_data["magic_link"]
        token = magic_link.split("token=")[1] if "token=" in magic_link else ""

        if not token:
            results.add("Magic Link Verification", False, "Could not extract token from magic link")
            return {}

        response = requests.post(
            f"{API_BASE}/api/v1/auth/verify-magic-link",
            params={"token": token},
            headers=get_headers(),
            timeout=10
        )

        if response.status_code == 200:
            data = response.json()
            if "access_token" in data and "refresh_token" in data:
                results.add("Magic Link Verification", True, "Tokens received successfully")
                return data
            else:
                results.add("Magic Link Verification", False, "Response missing tokens")
                return {}
        else:
            results.add("Magic Link Verification", False, f"Status: {response.status_code}, Response: {response.text}")
            return {}
    except Exception as e:
        results.add("Magic Link Verification", False, f"Exception: {str(e)}")
        return {}

def test_refresh_token_valid(results: TestResults, tokens: Dict[str, Any]) -> Dict[str, Any]:
    """Test refreshing token with valid refresh token"""
    print("\n[3/9] Testing valid refresh token...")
    try:
        if not tokens or "refresh_token" not in tokens:
            results.add("Valid Refresh Token", False, "No refresh token available")
            return {}

        refresh_token = tokens["refresh_token"]

        response = requests.post(
            f"{API_BASE}/api/v1/auth/refresh",
            params={"refresh_token": refresh_token},
            headers=get_headers(),
            timeout=10
        )

        if response.status_code == 200:
            data = response.json()
            if "access_token" in data:
                results.add("Valid Refresh Token", True, "New access token received")
                return data
            else:
                results.add("Valid Refresh Token", False, "Response missing access_token")
                return {}
        else:
            results.add("Valid Refresh Token", False, f"Status: {response.status_code}, Response: {response.text}")
            return {}
    except Exception as e:
        results.add("Valid Refresh Token", False, f"Exception: {str(e)}")
        return {}

def test_refresh_token_invalid(results: TestResults):
    """Test refreshing token with invalid refresh token"""
    print("\n[4/9] Testing invalid refresh token...")
    try:
        invalid_token = "invalid_token_12345"

        response = requests.post(
            f"{API_BASE}/api/v1/auth/refresh",
            params={"refresh_token": invalid_token},
            headers=get_headers(),
            timeout=10
        )

        if response.status_code == 401:
            results.add("Invalid Refresh Token Rejection", True, "Invalid token properly rejected")
        else:
            results.add("Invalid Refresh Token Rejection", False, f"Expected 401, got {response.status_code}")
    except Exception as e:
        results.add("Invalid Refresh Token Rejection", False, f"Exception: {str(e)}")

def test_refresh_token_empty(results: TestResults):
    """Test refreshing token with empty refresh token"""
    print("\n[5/9] Testing empty refresh token...")
    try:
        response = requests.post(
            f"{API_BASE}/api/v1/auth/refresh",
            params={"refresh_token": ""},
            headers=get_headers(),
            timeout=10
        )

        if response.status_code in [401, 422]:
            results.add("Empty Refresh Token Rejection", True, "Empty token properly rejected")
        else:
            results.add("Empty Refresh Token Rejection", False, f"Expected 401/422, got {response.status_code}")
    except Exception as e:
        results.add("Empty Refresh Token Rejection", False, f"Exception: {str(e)}")

def test_session_validation(results: TestResults, tokens: Dict[str, Any]):
    """Test that refresh validates session is active"""
    print("\n[6/9] Testing session validation...")
    try:
        if not tokens or "refresh_token" not in tokens:
            results.add("Session Validation", False, "No refresh token available")
            return

        # First refresh should work
        response = requests.post(
            f"{API_BASE}/api/v1/auth/refresh",
            params={"refresh_token": tokens["refresh_token"]},
            headers=get_headers(),
            timeout=10
        )

        if response.status_code == 200:
            results.add("Session Validation", True, "Session validated during refresh")
        else:
            results.add("Session Validation", False, f"Session validation failed: {response.status_code}")
    except Exception as e:
        results.add("Session Validation", False, f"Exception: {str(e)}")

def test_rate_limiting(results: TestResults, tokens: Dict[str, Any]):
    """Test rate limiting on refresh endpoint"""
    print("\n[7/9] Testing rate limiting (5/minute in code)...")
    try:
        if not tokens or "refresh_token" not in tokens:
            results.add("Rate Limiting", False, "No refresh token available")
            return

        # Make 6 requests quickly (limit is 5/minute according to code)
        rate_limit_hit = False
        responses = []

        for i in range(7):
            response = requests.post(
                f"{API_BASE}/api/v1/auth/refresh",
                params={"refresh_token": tokens["refresh_token"]},
                headers=get_headers(),
                timeout=10
            )
            responses.append(response.status_code)

            # Check if we hit rate limit (429)
            if response.status_code == 429:
                rate_limit_hit = True
                break

            # Small delay to avoid overwhelming the server
            time.sleep(0.1)

        if rate_limit_hit:
            results.add("Rate Limiting", True, "Rate limit enforced (429 returned)")
        else:
            results.add("Rate Limiting", False, f"Rate limit not enforced. Response codes: {responses}")
    except Exception as e:
        results.add("Rate Limiting", False, f"Exception: {str(e)}")

def test_access_token_usage(results: TestResults, tokens: Dict[str, Any]):
    """Test using access token to access protected endpoint"""
    print("\n[8/9] Testing access token usage...")
    try:
        if not tokens or "access_token" not in tokens:
            results.add("Access Token Usage", False, "No access token available")
            return

        headers = get_headers(include_auth=tokens['access_token'])

        response = requests.get(
            f"{API_BASE}/api/v1/auth/me",
            headers=headers,
            timeout=10
        )

        if response.status_code == 200:
            data = response.json()
            if "email" in data and data["email"] == TEST_EMAIL:
                results.add("Access Token Usage", True, f"Access token valid, user identified: {TEST_EMAIL}")
            else:
                results.add("Access Token Usage", False, "Access token valid but wrong user data")
        else:
            results.add("Access Token Usage", False, f"Status: {response.status_code}")
    except Exception as e:
        results.add("Access Token Usage", False, f"Exception: {str(e)}")

def test_audit_logging(results: TestResults):
    """Check if audit logging is present in code"""
    print("\n[9/9] Checking audit logging implementation...")
    try:
        # Check if logging exists in auth_service.py
        with open("/home/user/ai-tesi/apps/api/app/services/auth_service.py", "r") as f:
            content = f.read()
            has_logging_import = "import logging" in content or "from logging" in content
            has_logger = "logger" in content
            has_refresh_logging = "refresh" in content.lower() and "log" in content.lower()

            if has_logging_import and has_logger:
                results.add("Audit Logging Implementation", True,
                           "Logging infrastructure present in AuthService")
            else:
                results.add("Audit Logging Implementation", False,
                           "Logging infrastructure not properly implemented")
    except Exception as e:
        results.add("Audit Logging Implementation", False, f"Could not check code: {str(e)}")

def main():
    print("="*80)
    print("JWT REFRESH TOKEN RUNTIME TEST")
    print("="*80)
    print(f"API Base: {API_BASE}")
    print(f"Test Email: {TEST_EMAIL}")
    print("="*80)

    results = TestResults()

    # Run tests in sequence
    magic_link_data = test_magic_link_request(results)
    tokens = test_magic_link_verification(results, magic_link_data)
    refreshed_tokens = test_refresh_token_valid(results, tokens)
    test_refresh_token_invalid(results)
    test_refresh_token_empty(results)
    test_session_validation(results, tokens)
    test_rate_limiting(results, tokens if tokens else refreshed_tokens)
    test_access_token_usage(results, tokens if tokens else refreshed_tokens)
    test_audit_logging(results)

    # Print summary
    results.print_summary()

    return results

if __name__ == "__main__":
    results = main()
    exit(0 if results.failed == 0 else 1)
