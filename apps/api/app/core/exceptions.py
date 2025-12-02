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


class QualityThresholdNotMetError(APIException):
    """
    Quality thresholds not met after maximum regeneration attempts

    Raised when section quality fails to meet standards after all retry attempts:
    - Grammar errors > QUALITY_MAX_GRAMMAR_ERRORS
    - Plagiarism score > (100 - QUALITY_MIN_PLAGIARISM_UNIQUENESS)
    - AI detection score > QUALITY_MAX_AI_DETECTION_SCORE

    This is a 422 Unprocessable Entity error.
    User should be notified and potentially offered refund.

    Example:
        Section failed after 2 regeneration attempts:
        - Grammar: 15 errors (threshold: 10)
        - Plagiarism: 75% unique (threshold: 85%)
        → raise QualityThresholdNotMetError("Quality standards not met")
    """

    def __init__(
        self, detail: str = "Quality standards not met after regeneration attempts"
    ):
        super().__init__(
            detail, status.HTTP_422_UNPROCESSABLE_ENTITY, "QUALITY_THRESHOLD_NOT_MET"
        )


class AllProvidersFailedError(APIException):
    """
    All AI providers in fallback chain failed

    Raised when all configured AI providers (OpenAI, Anthropic)
    have been attempted and all failed.
    This is a 503 Service Unavailable error indicating temporary issue.

    Example:
        Fallback chain: GPT-4 → GPT-3.5 → Claude
        All 3 failed → raise AllProvidersFailedError
    """

    def __init__(self, detail: str = "All AI providers failed"):
        super().__init__(
            detail, status.HTTP_503_SERVICE_UNAVAILABLE, "ALL_PROVIDERS_FAILED"
        )
