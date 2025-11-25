# Integration Tests Suite

Comprehensive integration tests for TesiGo API covering full user journeys, security, error handling, and performance.

## Structure

- `test_full_user_journey.py` - Complete user flow: registration → document creation → generation → payment → export
- `test_security_suite.py` - Security tests: IDOR protection, JWT security, file security, rate limiting
- `test_error_handling.py` - Error handling: retry mechanisms, payment failures, DB connection loss
- `test_performance.py` - Performance tests: concurrent users, large documents, memory monitoring

## Running Tests

### Run all integration tests:
```bash
cd apps/api
pytest tests/integration/ -v -m integration
```

### Run specific test file:
```bash
pytest tests/integration/test_full_user_journey.py -v
```

### Run without slow tests:
```bash
pytest tests/integration/ -v -m integration -m "not slow"
```

### Run only slow tests:
```bash
pytest tests/integration/ -v -m slow
```

### Run with coverage:
```bash
pytest tests/integration/ -v --cov=app --cov-report=html
```

## Dependencies

Required packages (already in requirements.txt):
- `pytest`
- `pytest-asyncio`
- `httpx`
- `faker` - for generating test data
- `psutil` - for memory monitoring (performance tests)

If missing, install:
```bash
pip install pytest pytest-asyncio httpx faker psutil
```

## Test Categories

### 1. Full User Journey (`test_full_user_journey.py`)
- Complete user workflow from registration to document export
- Multiple documents workflow
- Document export flow

### 2. Security Suite (`test_security_suite.py`)
- **IDOR Protection**: Tests that users cannot access other users' resources
- **JWT Security**: Token expiration, signature validation, malformed tokens
- **File Security**: Executable file rejection, ZIP bomb detection
- **Rate Limiting**: Rate limit enforcement
- **CSRF Protection**: State-changing request protection

### 3. Error Handling (`test_error_handling.py`)
- **Retry Mechanisms**: Exponential backoff, circuit breaker patterns
- **Payment Failures**: Payment intent creation failures, webhook idempotency
- **Database Errors**: Connection loss handling
- **API Failures**: OpenAI rate limit retry logic
- **Invalid Inputs**: Validation error handling

### 4. Performance (`test_performance.py`)
- **Concurrent Users**: 10+ concurrent document operations
- **Large Documents**: Handling of 200+ page documents
- **Memory Monitoring**: Memory usage tracking during operations
- **Load Handling**: Sustained load over time

## Load Testing

Load testing is configured using Locust. See `tests/load/locustfile.py` for configuration.

### Install Locust:
```bash
pip install locust
```

### Run load test (Web UI):
```bash
cd apps/api/tests/load
locust -f locustfile.py --host=http://localhost:8000
```

Then open http://localhost:8089 in browser

### Run load test (headless):
```bash
locust -f locustfile.py --host=http://localhost:8000 --users=50 --spawn-rate=5 --headless --run-time=5m
```

### Success Criteria:
- Response time (p95) < 2s
- Error rate < 1%
- RPS > 100

## Notes

- Tests use separate test databases (`test_*.db`)
- Rate limiting may be disabled in test environment
- Some tests may skip if dependencies (like Stripe/OpenAI) are not configured
- Performance tests are marked with `@pytest.mark.slow` and can take several minutes
