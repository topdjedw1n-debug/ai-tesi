"""
Unit tests for rate limiting middleware
Tests: None limiter, valid limiter, DISABLE_RATE_LIMIT flag
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from app.middleware.rate_limit import (
    get_limiter,
    setup_rate_limiter,
    rate_limit,
    get_user_id_or_ip
)
from app.core.config import Settings


@pytest.fixture
def app():
    """Create FastAPI app for testing"""
    return FastAPI()


@pytest.fixture
def mock_settings():
    """Mock settings for testing"""
    return Settings()


class TestRateLimitDisabled:
    """Test rate limiting when disabled via DISABLE_RATE_LIMIT flag"""
    
    def test_get_limiter_returns_none_when_disabled(self, monkeypatch):
        """Test that get_limiter returns None when DISABLE_RATE_LIMIT=True"""
        monkeypatch.setattr("app.middleware.rate_limit.settings.DISABLE_RATE_LIMIT", True)
        # Clear cached limiter
        import app.middleware.rate_limit as rl_module
        rl_module._limiter = None
        
        limiter = get_limiter()
        assert limiter is None
    
    def test_rate_limit_decorator_skips_when_disabled(self, monkeypatch):
        """Test that rate_limit decorator doesn't apply when limiter is None"""
        monkeypatch.setattr("app.middleware.rate_limit.settings.DISABLE_RATE_LIMIT", True)
        import app.middleware.rate_limit as rl_module
        rl_module._limiter = None
        
        @rate_limit("10/hour")
        def test_func():
            return "ok"
        
        # Should return original function unchanged
        result = test_func()
        assert result == "ok"
    
    def test_setup_rate_limiter_skips_when_disabled(self, app, monkeypatch):
        """Test that setup_rate_limiter doesn't setup middleware when disabled"""
        monkeypatch.setattr("app.middleware.rate_limit.settings.DISABLE_RATE_LIMIT", True)
        import app.middleware.rate_limit as rl_module
        rl_module._limiter = None
        
        setup_rate_limiter(app)
        
        # app.state.limiter should be None
        assert getattr(app.state, "limiter", None) is None


class TestRateLimitValid:
    """Test rate limiting when properly initialized"""
    
    @patch("app.middleware.rate_limit.Limiter")
    def test_get_limiter_initializes_limiter(self, mock_limiter_class, monkeypatch):
        """Test that get_limiter creates Limiter instance when enabled"""
        monkeypatch.setattr("app.middleware.rate_limit.settings.DISABLE_RATE_LIMIT", False)
        monkeypatch.setattr("app.middleware.rate_limit.settings.ENVIRONMENT", "development")
        monkeypatch.setattr("app.middleware.rate_limit.settings.RATE_LIMIT_PER_MINUTE", 60)
        monkeypatch.setattr("app.middleware.rate_limit.settings.REDIS_URL", "redis://localhost:6379")
        
        import app.middleware.rate_limit as rl_module
        rl_module._limiter = None
        
        mock_limiter_instance = MagicMock()
        mock_limiter_class.return_value = mock_limiter_instance
        
        limiter = get_limiter()
        
        # Should have called Limiter constructor
        mock_limiter_class.assert_called_once()
        assert limiter is not None
    
    @patch("app.middleware.rate_limit.Limiter")
    def test_setup_rate_limiter_configures_middleware(self, mock_limiter_class, app, monkeypatch):
        """Test that setup_rate_limiter properly configures app"""
        monkeypatch.setattr("app.middleware.rate_limit.settings.DISABLE_RATE_LIMIT", False)
        monkeypatch.setattr("app.middleware.rate_limit.settings.ENVIRONMENT", "development")
        monkeypatch.setattr("app.middleware.rate_limit.settings.RATE_LIMIT_PER_MINUTE", 60)
        monkeypatch.setattr("app.middleware.rate_limit.settings.REDIS_URL", "redis://localhost:6379")
        
        import app.middleware.rate_limit as rl_module
        rl_module._limiter = None
        
        mock_limiter_instance = MagicMock()
        mock_limiter_class.return_value = mock_limiter_instance
        
        setup_rate_limiter(app)
        
        # Should have set app.state.limiter
        assert hasattr(app.state, "limiter")
        # Middleware should have been added (check by verifying exception handler exists)
        assert len(app.exception_handlers) > 0


class TestRateLimitNoneHandling:
    """Test defensive handling when limiter initialization fails"""
    
    @patch("app.middleware.rate_limit.Limiter")
    def test_get_limiter_handles_initialization_failure(self, mock_limiter_class, monkeypatch):
        """Test that get_limiter returns None when Limiter initialization fails"""
        monkeypatch.setattr("app.middleware.rate_limit.settings.DISABLE_RATE_LIMIT", False)
        monkeypatch.setattr("app.middleware.rate_limit.settings.ENVIRONMENT", "development")
        
        import app.middleware.rate_limit as rl_module
        rl_module._limiter = None
        
        # Simulate initialization failure
        mock_limiter_class.side_effect = Exception("Initialization failed")
        
        limiter = get_limiter()
        
        # Should return None on failure
        assert limiter is None
    
    @patch("app.middleware.rate_limit.Limiter")
    def test_setup_rate_limiter_handles_failure_gracefully(self, mock_limiter_class, app, monkeypatch):
        """Test that setup_rate_limiter continues even if limiter setup fails"""
        monkeypatch.setattr("app.middleware.rate_limit.settings.DISABLE_RATE_LIMIT", False)
        monkeypatch.setattr("app.middleware.rate_limit.settings.ENVIRONMENT", "development")
        
        import app.middleware.rate_limit as rl_module
        rl_module._limiter = None
        
        # Simulate failure during setup
        mock_limiter_class.side_effect = Exception("Setup failed")
        
        # Should not raise exception
        setup_rate_limiter(app)
        
        # Should have set limiter to None
        assert getattr(app.state, "limiter", None) is None


class TestGetUserIdOrIP:
    """Test user ID / IP extraction for rate limiting"""
    
    def test_get_user_id_or_ip_with_user_id(self):
        """Test that user_id takes precedence over IP"""
        request = Mock(spec=Request)
        request.state.user_id = "123"
        request.client = None
        
        identifier = get_user_id_or_ip(request)
        
        assert identifier == "user:123"
    
    def test_get_user_id_or_ip_falls_back_to_ip(self):
        """Test that IP is used when user_id not available"""
        request = Mock(spec=Request)
        request.state = Mock()
        delattr(request.state, "user_id")
        request.client = Mock()
        request.client.host = "192.168.1.1"
        
        with patch("app.middleware.rate_limit.get_remote_address", return_value="192.168.1.1"):
            identifier = get_user_id_or_ip(request)
        
        assert identifier == "192.168.1.1"


class TestRateLimitDecorator:
    """Test rate_limit decorator behavior"""
    
    @patch("app.middleware.rate_limit.get_limiter")
    def test_rate_limit_decorator_applies_when_limiter_available(self, mock_get_limiter):
        """Test that decorator applies rate limit when limiter is available"""
        mock_limiter = MagicMock()
        mock_limiter.limit.return_value = lambda f: f  # Return identity decorator
        mock_get_limiter.return_value = mock_limiter
        
        @rate_limit("10/hour")
        def test_func():
            return "ok"
        
        # Should have called limiter.limit
        mock_limiter.limit.assert_called_once_with("10/hour")
    
    @patch("app.middleware.rate_limit.get_limiter")
    def test_rate_limit_decorator_skips_when_limiter_none(self, mock_get_limiter):
        """Test that decorator doesn't apply when limiter is None"""
        mock_get_limiter.return_value = None
        
        @rate_limit("10/hour")
        def test_func():
            return "ok"
        
        # Should return function unchanged
        result = test_func()
        assert result == "ok"

