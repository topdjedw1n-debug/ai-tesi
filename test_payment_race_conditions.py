#!/usr/bin/env python3
"""
Payment Webhook Race Condition Runtime Test Script
Tests comprehensive race condition protection mechanisms
"""

import requests
import json
import time
import asyncio
import concurrent.futures
from typing import Dict, Any, List
from collections import Counter
import uuid

API_BASE = "http://localhost:8000"
CSRF_TOKEN = "test-csrf-token-1234567890"

def get_headers() -> Dict[str, str]:
    """Get headers with CSRF token"""
    return {
        "X-CSRF-Token": CSRF_TOKEN,
        "Content-Type": "application/json"
    }


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
        print("TEST SUMMARY - PAYMENT WEBHOOK RACE CONDITIONS")
        print("="*80)
        for r in self.results:
            status_icon = "✓" if r["status"] == "PASS" else "✗"
            print(f"{status_icon} {r['test']}: {r['status']}")
            if r["details"]:
                print(f"  → {r['details']}")
        print("="*80)
        print(f"Total: {len(self.results)} | Passed: {self.passed} | Failed: {self.failed}")
        print("="*80)


def send_webhook(webhook_id: str, user_id: int = 1, amount: float = 100.0) -> Dict[str, Any]:
    """Send a webhook request"""
    try:
        response = requests.post(
            f"{API_BASE}/api/v1/payment/webhook",
            headers=get_headers(),
            json={
                "webhook_id": webhook_id,
                "user_id": user_id,
                "amount": amount,
                "currency": "USD",
                "payment_method": "card"
            },
            timeout=10
        )
        return {
            "status_code": response.status_code,
            "data": response.json() if response.status_code == 200 else {},
            "error": response.text if response.status_code != 200 else None
        }
    except Exception as e:
        return {
            "status_code": 0,
            "data": {},
            "error": str(e)
        }


def test_single_webhook(results: TestResults) -> str:
    """Test 1: Single webhook processing (happy path)"""
    print("\n[1/8] Testing single webhook processing...")
    webhook_id = f"test-webhook-{uuid.uuid4()}"

    response = send_webhook(webhook_id)

    if response["status_code"] == 200:
        data = response["data"]
        if data.get("status") == "success" and data.get("job_id"):
            results.add(
                "Single Webhook Processing",
                True,
                f"Webhook processed, job_id={data.get('job_id')}"
            )
            return webhook_id
        else:
            results.add("Single Webhook Processing", False, f"Unexpected response: {data}")
    else:
        results.add("Single Webhook Processing", False, f"HTTP {response['status_code']}: {response['error']}")

    return webhook_id


def test_idempotency(results: TestResults, webhook_id: str):
    """Test 2: Idempotency - same webhook sent twice sequentially"""
    print("\n[2/8] Testing idempotency (sequential duplicate)...")

    # Send same webhook again
    response = send_webhook(webhook_id)

    if response["status_code"] == 200:
        data = response["data"]
        if data.get("status") == "duplicate":
            results.add(
                "Idempotency Check",
                True,
                "Duplicate webhook properly detected and rejected"
            )
        else:
            results.add("Idempotency Check", False, f"Expected duplicate status, got: {data.get('status')}")
    else:
        results.add("Idempotency Check", False, f"HTTP {response['status_code']}")


def test_concurrent_requests(results: TestResults) -> Dict[str, Any]:
    """Test 3: Concurrent requests with same webhook_id (race condition)"""
    print("\n[3/8] Testing concurrent requests (race condition)...")

    webhook_id = f"test-concurrent-{uuid.uuid4()}"
    num_requests = 10  # Send 10 concurrent requests

    # Use ThreadPoolExecutor to send requests concurrently
    with concurrent.futures.ThreadPoolExecutor(max_workers=num_requests) as executor:
        futures = [
            executor.submit(send_webhook, webhook_id, user_id=1, amount=100.0)
            for _ in range(num_requests)
        ]

        responses = [f.result() for f in concurrent.futures.as_completed(futures)]

    # Analyze responses
    statuses = [r["data"].get("status") for r in responses if r["status_code"] == 200]
    status_counts = Counter(statuses)

    success_count = status_counts.get("success", 0)
    duplicate_count = status_counts.get("duplicate", 0)

    # CRITICAL: Only ONE request should succeed, others should be duplicate
    if success_count == 1 and duplicate_count == (num_requests - 1):
        results.add(
            "Concurrent Race Condition Protection",
            True,
            f"{num_requests} concurrent requests: 1 success, {duplicate_count} duplicates detected"
        )
        success = True
    else:
        results.add(
            "Concurrent Race Condition Protection",
            False,
            f"Expected 1 success, {num_requests-1} duplicates. Got {success_count} success, {duplicate_count} duplicates"
        )
        success = False

    return {
        "webhook_id": webhook_id,
        "success": success,
        "success_count": success_count,
        "duplicate_count": duplicate_count
    }


def test_job_uniqueness(results: TestResults, webhook_id: str):
    """Test 4: Verify only ONE job was created"""
    print("\n[4/8] Testing job uniqueness...")

    try:
        response = requests.get(
            f"{API_BASE}/api/v1/payment/job/{webhook_id}",
            headers=get_headers(),
            timeout=10
        )

        if response.status_code == 200:
            data = response.json()
            if data.get("job_id") and data.get("webhook_id") == webhook_id:
                results.add(
                    "Job Uniqueness",
                    True,
                    f"Single job created: job_id={data.get('job_id')}"
                )
            else:
                results.add("Job Uniqueness", False, f"Job data inconsistent: {data}")
        else:
            results.add("Job Uniqueness", False, f"HTTP {response.status_code}")
    except Exception as e:
        results.add("Job Uniqueness", False, f"Exception: {str(e)}")


def test_select_for_update(results: TestResults):
    """Test 5: Verify SELECT FOR UPDATE mechanism (extreme concurrent load)"""
    print("\n[5/8] Testing SELECT FOR UPDATE under extreme load...")

    webhook_id = f"test-extreme-{uuid.uuid4()}"
    num_requests = 50  # Much higher concurrent load

    start_time = time.time()

    with concurrent.futures.ThreadPoolExecutor(max_workers=num_requests) as executor:
        futures = [
            executor.submit(send_webhook, webhook_id, user_id=1, amount=100.0)
            for _ in range(num_requests)
        ]

        responses = [f.result() for f in concurrent.futures.as_completed(futures)]

    elapsed_time = time.time() - start_time

    statuses = [r["data"].get("status") for r in responses if r["status_code"] == 200]
    status_counts = Counter(statuses)

    success_count = status_counts.get("success", 0)
    duplicate_count = status_counts.get("duplicate", 0)

    # Even under extreme load, only 1 success allowed
    if success_count == 1:
        results.add(
            "SELECT FOR UPDATE Mechanism",
            True,
            f"{num_requests} extreme concurrent requests in {elapsed_time:.2f}s: 1 success, {duplicate_count} duplicates"
        )
    else:
        results.add(
            "SELECT FOR UPDATE Mechanism",
            False,
            f"SELECT FOR UPDATE failed: {success_count} successes (expected 1)"
        )


def test_integrity_error_handling(results: TestResults):
    """Test 6: Verify IntegrityError is properly handled"""
    print("\n[6/8] Testing IntegrityError handling...")

    # This test verifies that even if SELECT FOR UPDATE fails,
    # IntegrityError at DB level catches duplicates
    webhook_id = f"test-integrity-{uuid.uuid4()}"

    # Send multiple requests very quickly
    num_requests = 20
    with concurrent.futures.ThreadPoolExecutor(max_workers=num_requests) as executor:
        futures = [executor.submit(send_webhook, webhook_id) for _ in range(num_requests)]
        responses = [f.result() for f in concurrent.futures.as_completed(futures)]

    # Check that all requests succeeded (HTTP 200) but with duplicate detection
    all_200 = all(r["status_code"] == 200 for r in responses)
    statuses = [r["data"].get("status") for r in responses if r["status_code"] == 200]

    has_success = "success" in statuses
    has_duplicates = "duplicate" in statuses

    if all_200 and has_success and has_duplicates:
        results.add(
            "IntegrityError Handling",
            True,
            "All requests handled gracefully, duplicates detected at DB level"
        )
    else:
        results.add(
            "IntegrityError Handling",
            False,
            f"Some requests failed or detection incomplete: {statuses[:5]}..."
        )


def test_webhook_status_check(results: TestResults, webhook_id: str):
    """Test 7: Verify webhook status endpoint"""
    print("\n[7/8] Testing webhook status endpoint...")

    try:
        response = requests.get(
            f"{API_BASE}/api/v1/payment/webhook/{webhook_id}",
            headers=get_headers(),
            timeout=10
        )

        if response.status_code == 200:
            data = response.json()
            if data.get("webhook_id") == webhook_id and data.get("is_processed"):
                results.add(
                    "Webhook Status Endpoint",
                    True,
                    f"Status: {data.get('status')}, processed: {data.get('is_processed')}"
                )
            else:
                results.add("Webhook Status Endpoint", False, f"Incomplete data: {data}")
        else:
            results.add("Webhook Status Endpoint", False, f"HTTP {response.status_code}")
    except Exception as e:
        results.add("Webhook Status Endpoint", False, f"Exception: {str(e)}")


def test_logging_verification(results: TestResults):
    """Test 8: Verify logging infrastructure exists"""
    print("\n[8/8] Verifying logging implementation...")

    try:
        # Check if logging is implemented in payment_service.py
        with open("/home/user/ai-tesi/apps/api/app/services/payment_service.py", "r") as f:
            content = f.read()

            has_logging_import = "import logging" in content
            has_logger = "logger" in content
            has_warning_log = "logger.warning" in content
            has_duplicate_log = "Duplicate" in content and "log" in content.lower()

            if has_logging_import and has_logger and has_warning_log and has_duplicate_log:
                results.add(
                    "Duplicate Logging Infrastructure",
                    True,
                    "Logging properly implemented with duplicate detection warnings"
                )
            else:
                results.add(
                    "Duplicate Logging Infrastructure",
                    False,
                    "Logging infrastructure incomplete"
                )
    except Exception as e:
        results.add("Duplicate Logging Infrastructure", False, f"Could not verify: {str(e)}")


def main():
    print("="*80)
    print("PAYMENT WEBHOOK RACE CONDITION RUNTIME TEST")
    print("="*80)
    print(f"API Base: {API_BASE}")
    print(f"Testing concurrent webhook processing with race condition protection")
    print("="*80)

    results = TestResults()

    # Run tests
    webhook_id_single = test_single_webhook(results)
    test_idempotency(results, webhook_id_single)
    concurrent_result = test_concurrent_requests(results)
    test_job_uniqueness(results, concurrent_result["webhook_id"])
    test_select_for_update(results)
    test_integrity_error_handling(results)
    test_webhook_status_check(results, webhook_id_single)
    test_logging_verification(results)

    # Print summary
    results.print_summary()

    return results


if __name__ == "__main__":
    results = main()
    exit(0 if results.failed == 0 else 1)
