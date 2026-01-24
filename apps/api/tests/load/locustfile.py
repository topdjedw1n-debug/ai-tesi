"""
Locust load testing configuration for TesiGo API

Usage:
    # Install locust first:
    pip install locust

    # Run with 50 users, spawn rate 5/sec:
    locust -f locustfile.py --host=http://localhost:8000 --users=50 --spawn-rate=5

    # Headless mode:
    locust -f locustfile.py --host=http://localhost:8000 --users=50 --spawn-rate=5 --headless --run-time=5m

    # Web UI:
    locust -f locustfile.py --host=http://localhost:8000
"""
import random

from locust import between, events, task
from locust.contrib.fasthttp import FastHttpUser


class TesiGoUser(FastHttpUser):
    """
    Simulates a TesiGo user making API requests

    Wait time between requests: 1-3 seconds
    """

    wait_time = between(1, 3)

    def on_start(self):
        """Called when a user starts - authenticate"""
        # Set default headers
        self.client.headers.update(
            {
                "X-CSRF-Token": "test-csrf-token-locust",
                "X-Requested-With": "XMLHttpRequest",
                "Content-Type": "application/json",
            }
        )

        # Register/login (simplified - in real test you'd need actual auth flow)
        # For load testing, we'll skip auth if not available
        # In production, you'd want to pre-create test users with tokens
        self.auth_token = None

        # Try to get auth token (if auth endpoints are available)
        try:
            # Request magic link
            self.client.post(
                "/api/v1/auth/magic-link",
                json={"email": f"locust_user_{random.randint(1000, 9999)}@locust.test"},
                catch_response=True,
            )

            # For load testing, we might not wait for actual verification
            # This is a simplified version
        except Exception:
            pass  # Continue without auth for public endpoints

    @task(3)
    def list_documents(self):
        """List documents - most common operation"""
        headers = {}
        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"

        with self.client.get(
            "/api/v1/documents/",
            headers=headers,
            catch_response=True,
            name="/documents/list",
        ) as response:
            if response.status_code in [200, 401]:
                response.success()
            else:
                response.failure(f"Unexpected status: {response.status_code}")

    @task(2)
    def get_health(self):
        """Health check endpoint - lightweight"""
        with self.client.get(
            "/health", catch_response=True, name="/health"
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Health check failed: {response.status_code}")

    @task(1)
    def create_document(self):
        """Create document - less frequent but more resource-intensive"""
        headers = {"X-CSRF-Token": "test-csrf-token-locust"}
        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"

        document_data = {
            "title": f"Load Test Document {random.randint(1, 10000)}",
            "topic": f"Load testing topic number {random.randint(1, 10000)} with sufficient length",
            "language": "en",
            "target_pages": random.randint(5, 50),
        }

        with self.client.post(
            "/api/v1/documents/",
            json=document_data,
            headers=headers,
            catch_response=True,
            name="/documents/create",
        ) as response:
            if response.status_code in [200, 201, 401, 422]:
                response.success()
            else:
                response.failure(f"Unexpected status: {response.status_code}")

    @task(1)
    def get_document(self):
        """Get single document - assumes documents exist"""
        # Try a range of IDs (some will fail, that's expected)
        doc_id = random.randint(1, 1000)

        headers = {}
        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"

        with self.client.get(
            f"/api/v1/documents/{doc_id}",
            headers=headers,
            catch_response=True,
            name="/documents/get",
        ) as response:
            if response.status_code in [200, 404, 401]:
                response.success()
            else:
                response.failure(f"Unexpected status: {response.status_code}")

    @task(1)
    def generate_outline(self):
        """Generate outline - resource-intensive operation"""
        # This requires a valid document_id, so may fail often
        doc_id = random.randint(1, 100)

        headers = {}
        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"

        with self.client.post(
            "/api/v1/generate/outline",
            json={"document_id": doc_id, "additional_requirements": None},
            headers=headers,
            catch_response=True,
            name="/generate/outline",
        ) as response:
            # Accept various status codes (success, not found, auth errors)
            if response.status_code in [200, 201, 404, 401, 400, 422, 503]:
                response.success()
            else:
                response.failure(f"Unexpected status: {response.status_code}")

    @task(1)
    def get_usage_stats(self):
        """Get usage statistics"""
        user_id = random.randint(1, 100)

        headers = {}
        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"

        with self.client.get(
            f"/api/v1/generate/usage/{user_id}",
            headers=headers,
            catch_response=True,
            name="/generate/usage",
        ) as response:
            if response.status_code in [200, 401, 404]:
                response.success()
            else:
                response.failure(f"Unexpected status: {response.status_code}")


# Custom metrics tracking
@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """Called when test starts"""
    print("Starting load test...")


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Called when test stops"""
    print("Load test completed!")

    # Print summary statistics
    stats = environment.stats
    print("\n=== Load Test Summary ===")
    print(f"Total requests: {stats.total.num_requests}")
    print(f"Total failures: {stats.total.num_failures}")
    print(f"Average response time: {stats.total.avg_response_time:.2f}ms")
    print(f"Min response time: {stats.total.min_response_time:.2f}ms")
    print(f"Max response time: {stats.total.max_response_time:.2f}ms")
    print(f"Median response time: {stats.total.median_response_time:.2f}ms")
    print(f"95th percentile: {stats.total.get_response_time_percentile(0.95):.2f}ms")
    print(f"99th percentile: {stats.total.get_response_time_percentile(0.99):.2f}ms")

    if stats.total.num_requests > 0:
        failure_rate = (stats.total.num_failures / stats.total.num_requests) * 100
        print(f"Failure rate: {failure_rate:.2f}%")

        # Success criteria
        print("\n=== Success Criteria ===")
        p95 = stats.total.get_response_time_percentile(0.95)
        print(f"✓ Response time (p95) < 2s: {p95 < 2000} ({p95:.0f}ms)")
        print(f"✓ Error rate < 1%: {failure_rate < 1} ({failure_rate:.2f}%)")
        print(f"✓ Requests/sec: {stats.total.total_rps:.1f}")


# Alternative user class for authenticated requests only
class AuthenticatedTesiGoUser(TesiGoUser):
    """
    User class that requires authentication
    For use when you have pre-authenticated users
    """

    def on_start(self):
        """Authenticate before starting tasks"""
        # In production, you'd load a valid auth token from a file or environment
        # For now, skip auth-dependent tasks if token not available
        super().on_start()

        # If you have test tokens, set them here:
        # self.auth_token = "your_test_token_here"
        if not self.auth_token:
            # Skip authenticated tasks
            self.tasks = [self.get_health]
