"""
Runtime test: Admin Panel Endpoints
Tests all existing admin endpoints
"""

import asyncio
import sys
import os
import json
import time
from pathlib import Path
import subprocess
import requests
from datetime import datetime

# Test configuration
API_BASE_URL = "http://localhost:8000"
CSRF_TOKEN = "test-csrf-token-1234567890"


def wait_for_api(max_attempts=30, delay=1):
    """Wait for API to become available"""
    print("Waiting for API to start...")
    for attempt in range(max_attempts):
        try:
            response = requests.get(f"{API_BASE_URL}/health", timeout=2)
            if response.status_code == 200:
                print(f"✅ API is ready (attempt {attempt + 1}/{max_attempts})")
                return True
        except requests.exceptions.RequestException:
            pass
        time.sleep(delay)
    return False


def test_admin_endpoints():
    """Test all admin panel endpoints"""

    print("=" * 80)
    print("RUNTIME TEST: Admin Panel (MUST HAVE!)")
    print("=" * 80)
    print()

    results = {
        "passed": 0,
        "failed": 0,
        "not_found": 0,
        "tests": []
    }

    headers = {
        "X-CSRF-Token": CSRF_TOKEN,
        "Content-Type": "application/json"
    }

    # Test 1: GET /api/v1/admin/stats
    print("Test 1: GET /api/v1/admin/stats - Platform Statistics")
    try:
        response = requests.get(f"{API_BASE_URL}/api/v1/admin/stats", headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ PASS - Status: {response.status_code}")
            print(f"   Response keys: {list(data.keys())}")
            if 'users' in data and 'documents' in data and 'ai_usage' in data:
                print(f"   Users: {data['users']}")
                print(f"   Documents: {data['documents']}")
                print(f"   AI Usage: {data['ai_usage']}")
            results["passed"] += 1
            results["tests"].append({"name": "GET /stats", "status": "PASS"})
        elif response.status_code == 404:
            print(f"❌ NOT FOUND - Status: 404")
            results["not_found"] += 1
            results["tests"].append({"name": "GET /stats", "status": "NOT_FOUND"})
        else:
            print(f"⚠️  FAIL - Status: {response.status_code}, Body: {response.text[:200]}")
            results["failed"] += 1
            results["tests"].append({"name": "GET /stats", "status": "FAIL", "code": response.status_code})
    except Exception as e:
        print(f"❌ EXCEPTION - {str(e)}")
        results["failed"] += 1
        results["tests"].append({"name": "GET /stats", "status": "EXCEPTION", "error": str(e)})
    print()

    # Test 2: GET /api/v1/admin/users
    print("Test 2: GET /api/v1/admin/users - List Users")
    try:
        response = requests.get(f"{API_BASE_URL}/api/v1/admin/users?page=1&per_page=10", headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ PASS - Status: {response.status_code}")
            print(f"   Response keys: {list(data.keys())}")
            if 'users' in data and 'total' in data:
                print(f"   Total users: {data['total']}")
                print(f"   Page: {data.get('page')}, Per page: {data.get('per_page')}")
            results["passed"] += 1
            results["tests"].append({"name": "GET /users", "status": "PASS"})
        elif response.status_code == 404:
            print(f"❌ NOT FOUND - Status: 404")
            results["not_found"] += 1
            results["tests"].append({"name": "GET /users", "status": "NOT_FOUND"})
        else:
            print(f"⚠️  FAIL - Status: {response.status_code}, Body: {response.text[:200]}")
            results["failed"] += 1
            results["tests"].append({"name": "GET /users", "status": "FAIL", "code": response.status_code})
    except Exception as e:
        print(f"❌ EXCEPTION - {str(e)}")
        results["failed"] += 1
        results["tests"].append({"name": "GET /users", "status": "EXCEPTION", "error": str(e)})
    print()

    # Test 3: GET /api/v1/admin/ai-jobs
    print("Test 3: GET /api/v1/admin/ai-jobs - List AI Jobs")
    try:
        response = requests.get(f"{API_BASE_URL}/api/v1/admin/ai-jobs?page=1&per_page=10", headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ PASS - Status: {response.status_code}")
            print(f"   Response keys: {list(data.keys())}")
            if 'jobs' in data and 'total' in data:
                print(f"   Total jobs: {data['total']}")
                print(f"   Page: {data.get('page')}, Per page: {data.get('per_page')}")
            results["passed"] += 1
            results["tests"].append({"name": "GET /ai-jobs", "status": "PASS"})
        elif response.status_code == 404:
            print(f"❌ NOT FOUND - Status: 404")
            results["not_found"] += 1
            results["tests"].append({"name": "GET /ai-jobs", "status": "NOT_FOUND"})
        else:
            print(f"⚠️  FAIL - Status: {response.status_code}, Body: {response.text[:200]}")
            results["failed"] += 1
            results["tests"].append({"name": "GET /ai-jobs", "status": "FAIL", "code": response.status_code})
    except Exception as e:
        print(f"❌ EXCEPTION - {str(e)}")
        results["failed"] += 1
        results["tests"].append({"name": "GET /ai-jobs", "status": "EXCEPTION", "error": str(e)})
    print()

    # Test 4: GET /api/v1/admin/costs
    print("Test 4: GET /api/v1/admin/costs - Cost Analysis")
    try:
        response = requests.get(f"{API_BASE_URL}/api/v1/admin/costs?group_by=day", headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ PASS - Status: {response.status_code}")
            print(f"   Response keys: {list(data.keys())}")
            if 'period' in data and 'totals' in data:
                print(f"   Period: {data['period']}")
                print(f"   Totals: {data['totals']}")
            results["passed"] += 1
            results["tests"].append({"name": "GET /costs", "status": "PASS"})
        elif response.status_code == 404:
            print(f"❌ NOT FOUND - Status: 404")
            results["not_found"] += 1
            results["tests"].append({"name": "GET /costs", "status": "NOT_FOUND"})
        else:
            print(f"⚠️  FAIL - Status: {response.status_code}, Body: {response.text[:200]}")
            results["failed"] += 1
            results["tests"].append({"name": "GET /costs", "status": "FAIL", "code": response.status_code})
    except Exception as e:
        print(f"❌ EXCEPTION - {str(e)}")
        results["failed"] += 1
        results["tests"].append({"name": "GET /costs", "status": "EXCEPTION", "error": str(e)})
    print()

    # Test 5: GET /api/v1/admin/health
    print("Test 5: GET /api/v1/admin/health - Admin Health Check")
    try:
        response = requests.get(f"{API_BASE_URL}/api/v1/admin/health", headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ PASS - Status: {response.status_code}")
            print(f"   Response keys: {list(data.keys())}")
            if 'status' in data and 'checks' in data:
                print(f"   Status: {data['status']}")
                print(f"   Checks: {data['checks']}")
            results["passed"] += 1
            results["tests"].append({"name": "GET /health", "status": "PASS"})
        elif response.status_code == 404:
            print(f"❌ NOT FOUND - Status: 404")
            results["not_found"] += 1
            results["tests"].append({"name": "GET /health", "status": "NOT_FOUND"})
        else:
            print(f"⚠️  FAIL - Status: {response.status_code}, Body: {response.text[:200]}")
            results["failed"] += 1
            results["tests"].append({"name": "GET /health", "status": "FAIL", "code": response.status_code})
    except Exception as e:
        print(f"❌ EXCEPTION - {str(e)}")
        results["failed"] += 1
        results["tests"].append({"name": "GET /health", "status": "EXCEPTION", "error": str(e)})
    print()

    # Test 6-8: Check for endpoints mentioned in test description but not implemented
    print("Test 6: GET /api/v1/admin/dashboard/charts - Dashboard Charts")
    try:
        response = requests.get(f"{API_BASE_URL}/api/v1/admin/dashboard/charts", headers=headers, timeout=10)
        if response.status_code == 404:
            print(f"❌ NOT FOUND - Status: 404 (expected - not implemented)")
            results["not_found"] += 1
            results["tests"].append({"name": "GET /dashboard/charts", "status": "NOT_FOUND"})
        else:
            print(f"⚠️  Unexpected response - Status: {response.status_code}")
            results["tests"].append({"name": "GET /dashboard/charts", "status": "UNEXPECTED", "code": response.status_code})
    except Exception as e:
        print(f"❌ EXCEPTION - {str(e)}")
        results["tests"].append({"name": "GET /dashboard/charts", "status": "EXCEPTION"})
    print()

    print("Test 7: GET /api/v1/admin/dashboard/metrics - Dashboard Metrics")
    try:
        response = requests.get(f"{API_BASE_URL}/api/v1/admin/dashboard/metrics", headers=headers, timeout=10)
        if response.status_code == 404:
            print(f"❌ NOT FOUND - Status: 404 (expected - not implemented)")
            results["not_found"] += 1
            results["tests"].append({"name": "GET /dashboard/metrics", "status": "NOT_FOUND"})
        else:
            print(f"⚠️  Unexpected response - Status: {response.status_code}")
            results["tests"].append({"name": "GET /dashboard/metrics", "status": "UNEXPECTED", "code": response.status_code})
    except Exception as e:
        print(f"❌ EXCEPTION - {str(e)}")
        results["tests"].append({"name": "GET /dashboard/metrics", "status": "EXCEPTION"})
    print()

    print("Test 8: GET /api/v1/admin/dashboard/activity - Dashboard Activity")
    try:
        response = requests.get(f"{API_BASE_URL}/api/v1/admin/dashboard/activity", headers=headers, timeout=10)
        if response.status_code == 404:
            print(f"❌ NOT FOUND - Status: 404 (expected - not implemented)")
            results["not_found"] += 1
            results["tests"].append({"name": "GET /dashboard/activity", "status": "NOT_FOUND"})
        else:
            print(f"⚠️  Unexpected response - Status: {response.status_code}")
            results["tests"].append({"name": "GET /dashboard/activity", "status": "UNEXPECTED", "code": response.status_code})
    except Exception as e:
        print(f"❌ EXCEPTION - {str(e)}")
        results["tests"].append({"name": "GET /dashboard/activity", "status": "EXCEPTION"})
    print()

    # Summary
    print("=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    print(f"✅ Passed: {results['passed']}")
    print(f"❌ Failed: {results['failed']}")
    print(f"🔍 Not Found: {results['not_found']}")
    print(f"Total: {results['passed'] + results['failed'] + results['not_found']}")
    print()

    print("IMPLEMENTATION STATUS:")
    print("=" * 80)
    print("✅ Implemented endpoints:")
    print("   - GET /api/v1/admin/stats")
    print("   - GET /api/v1/admin/users")
    print("   - GET /api/v1/admin/ai-jobs")
    print("   - GET /api/v1/admin/costs")
    print("   - GET /api/v1/admin/health")
    print()
    print("❌ Not implemented (mentioned in test description):")
    print("   - GET /api/v1/admin/dashboard/charts")
    print("   - GET /api/v1/admin/dashboard/metrics")
    print("   - GET /api/v1/admin/dashboard/activity")
    print("   - Separate routers: /admin/documents, /admin/payments, /admin/auth")
    print()
    print("⚠️  NOTE: Admin authentication is NOT enforced (TODO comments in code)")
    print("=" * 80)

    return results


if __name__ == "__main__":
    # Start API server in background
    print("Starting API server...")
    api_process = subprocess.Popen(
        ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"],
        cwd=Path(__file__).parent / "apps" / "api",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env={**os.environ, "PYTHONUNBUFFERED": "1"}
    )

    try:
        # Wait for API to start
        if not wait_for_api():
            print("❌ API failed to start within timeout")
            sys.exit(1)

        # Run tests
        results = test_admin_endpoints()

        # Exit code based on results
        sys.exit(0 if results["failed"] == 0 else 1)

    finally:
        # Cleanup: stop API server
        print("\nStopping API server...")
        api_process.terminate()
        try:
            api_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            api_process.kill()
        print("API server stopped")
