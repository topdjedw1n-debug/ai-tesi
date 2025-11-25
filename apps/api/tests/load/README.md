# Load Testing with Locust

Load testing configuration for TesiGo API using Locust.

## Installation

Install Locust:
```bash
pip install locust
```

Or add to requirements.txt:
```
locust>=2.17.0
```

## Usage

### Web UI Mode (Recommended for first run)

Start Locust web interface:
```bash
cd apps/api/tests/load
locust -f locustfile.py --host=http://localhost:8000
```

Then open http://localhost:8089 in your browser to access the web UI where you can:
- Set number of users
- Set spawn rate (users per second)
- Start/stop tests
- View real-time statistics

### Headless Mode (CI/CD)

Run load test without web UI:
```bash
locust -f locustfile.py \
  --host=http://localhost:8000 \
  --users=50 \
  --spawn-rate=5 \
  --headless \
  --run-time=5m \
  --html=report.html
```

Options:
- `--users`: Total number of concurrent users
- `--spawn-rate`: Users spawned per second
- `--run-time`: Duration of test (e.g., `5m`, `1h`)
- `--html`: Generate HTML report
- `--csv`: Generate CSV report (prefix only, e.g., `--csv=results`)

### Example: Production-like Load

```bash
# 100 users, spawn 10/sec, run for 10 minutes
locust -f locustfile.py \
  --host=https://api.tesigo.com \
  --users=100 \
  --spawn-rate=10 \
  --headless \
  --run-time=10m \
  --html=load_test_report.html
```

## Success Criteria

According to Phase 3 requirements:
- **Response time (p95)**: < 2 seconds
- **Error rate**: < 1%
- **Requests per second**: > 100 RPS

## Test Scenarios

The `TesiGoUser` class simulates:
- Document listing (weight: 3) - most common
- Health checks (weight: 2)
- Document creation (weight: 1)
- Document retrieval (weight: 1)
- Outline generation (weight: 1)
- Usage statistics (weight: 1)

## Authentication

For authenticated endpoints, you can:
1. Pre-create test users with valid tokens
2. Modify `on_start()` to use test tokens
3. Use `AuthenticatedTesiGoUser` class for auth-only tests

## Monitoring

During load tests, monitor:
- API response times
- Error rates
- Database connection pool
- Memory usage
- CPU usage
- Network I/O

## Reports

Locust generates:
- **HTML report**: Interactive dashboard with charts
- **CSV reports**: For analysis in spreadsheet tools
  - `results_stats.csv`: Request statistics
  - `results_failures.csv`: Failure details
  - `results_exceptions.csv`: Exception details

## Tips

1. Start with low user count (10-20) and gradually increase
2. Monitor server metrics during tests
3. Run tests during low-traffic periods
4. Save reports for comparison over time
5. Test both authenticated and unauthenticated endpoints

## Troubleshooting

**Connection errors**: Check that API is running and accessible
**Rate limiting**: May need to adjust rate limits or use multiple IPs
**Timeouts**: Increase timeout values in locustfile.py
**Authentication failures**: Ensure test tokens are valid
