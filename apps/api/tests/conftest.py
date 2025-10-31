"""
Pytest configuration - sets environment variables BEFORE any imports
This ensures DATABASE_URL is set before database.py is imported
"""
import os

# Set environment variables BEFORE any test imports
# This runs BEFORE pytest collects tests, ensuring database.py sees the correct DATABASE_URL
os.environ.setdefault("SECRET_KEY", "test-secret-key-minimum-32-chars-long-1234567890")
os.environ.setdefault("JWT_SECRET", os.environ["SECRET_KEY"])
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test.db")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("DISABLE_RATE_LIMIT", "true")

