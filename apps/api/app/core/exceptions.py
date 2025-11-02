"""
Custom exceptions for the application
"""


from fastapi import status


class APIException(Exception):
    """Base API exception"""

    def __init__(
        self, detail: str, status_code: int = 500, error_code: str | None = None
    ):
        self.detail = detail
        self.status_code = status_code
        self.error_code = error_code
        super().__init__(detail)


class NotFoundError(APIException):
    """Resource not found exception"""

    def __init__(self, detail: str = "Resource not found"):
        super().__init__(detail, status.HTTP_404_NOT_FOUND, "NOT_FOUND")


class ValidationError(APIException):
    """Validation error exception"""

    def __init__(self, detail: str = "Validation error"):
        super().__init__(
            detail, status.HTTP_422_UNPROCESSABLE_ENTITY, "VALIDATION_ERROR"
        )


class AuthenticationError(APIException):
    """Authentication error exception"""

    def __init__(self, detail: str = "Authentication failed"):
        super().__init__(detail, status.HTTP_401_UNAUTHORIZED, "AUTHENTICATION_ERROR")


class AuthorizationError(APIException):
    """Authorization error exception"""

    def __init__(self, detail: str = "Insufficient permissions"):
        super().__init__(detail, status.HTTP_403_FORBIDDEN, "AUTHORIZATION_ERROR")


class AIProviderError(APIException):
    """AI provider error exception"""

    def __init__(self, detail: str = "AI provider error"):
        super().__init__(detail, status.HTTP_502_BAD_GATEWAY, "AI_PROVIDER_ERROR")


class RateLimitError(APIException):
    """Rate limit exceeded exception"""

    def __init__(self, detail: str = "Rate limit exceeded"):
        super().__init__(detail, status.HTTP_429_TOO_MANY_REQUESTS, "RATE_LIMIT_ERROR")
