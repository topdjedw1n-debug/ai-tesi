"""
Application configuration
"""

from typing import Any
from urllib.parse import urlparse

from pydantic import ConfigDict, Field, field_validator, model_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings"""

    # Environment
    ENVIRONMENT: str = "development"
    DEBUG: bool = True

    # API
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "AI Thesis Platform"

    # Database
    # CRITICAL: No default value - must be provided via ENV in production
    DATABASE_URL: str | None = None

    # Security
    # CRITICAL: No default value - must be provided via ENV in production
    SECRET_KEY: str | None = None

    # JWT Configuration (ENV-based, no defaults)
    JWT_SECRET: str | None = None  # Prefer JWT_SECRET over SECRET_KEY if set
    JWT_ALG: str = "HS256"  # Algorithm for JWT signing/verification
    JWT_ISS: str | None = None  # Issuer claim (optional but recommended)
    JWT_AUD: str | None = None  # Audience claim (optional but recommended)
    JWT_EXP_MIN: int = 30  # Token expiration in minutes

    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # CORS - CRITICAL: Must be explicitly set from ENV (CORS_ALLOWED_ORIGINS)
    # Defaults only for development
    CORS_ALLOWED_ORIGINS: str | None = None  # Comma-separated list from ENV
    # ALLOWED_ORIGINS is set via model_validator, not from ENV directly
    # This prevents pydantic-settings from trying to parse it as JSON
    # Use Field with validation_alias to prevent env parsing
    ALLOWED_ORIGINS: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://localhost:3001",
            "http://127.0.0.1:3001",
        ],
        validation_alias="__IGNORE__",  # This alias doesn't exist, so it won't be parsed from ENV
    )
    ALLOWED_HOSTS: list[str] = ["localhost", "127.0.0.1", "0.0.0.0", "test"]

    # AI Providers
    OPENAI_API_KEY: str | None = None
    ANTHROPIC_API_KEY: str | None = None

    # AI Retry & Fallback Configuration (Task 3.1-3.2)
    AI_MAX_RETRIES: int = 3  # Number of retry attempts per provider
    AI_RETRY_DELAYS: str = (
        "2,4,8"  # Comma-separated delays in seconds (exponential backoff)
    )
    AI_ENABLE_FALLBACK: bool = True  # Enable fallback to other providers
    # Fallback chain: Try providers in order until one succeeds
    # Format: "provider:model,provider:model,..."
    # Default: GPT-4 → GPT-3.5 Turbo → Claude 3.5 Sonnet
    AI_FALLBACK_CHAIN: str = (
        "openai:gpt-4," "openai:gpt-3.5-turbo," "anthropic:claude-3-5-sonnet-20241022"
    )

    # Quality Thresholds Configuration (Task 3.2 - Quality Gates)
    # Grammar check threshold: max errors before regeneration
    QUALITY_MAX_GRAMMAR_ERRORS: int = 10  # LanguageTool error count threshold

    # Plagiarism check threshold: min uniqueness percentage
    QUALITY_MIN_PLAGIARISM_UNIQUENESS: float = (
        85.0  # 85% unique = 15% plagiarism allowed
    )

    # AI detection threshold: max AI-generated percentage
    QUALITY_MAX_AI_DETECTION_SCORE: float = (
        55.0  # Above 55% triggers multi-pass humanization
    )

    # Regeneration limits: max attempts to regenerate failing section
    QUALITY_MAX_REGENERATE_ATTEMPTS: int = 2  # Try initial + 2 regenerations = 3 total

    # Enable/disable quality gates (for testing/debugging)
    QUALITY_GATES_ENABLED: bool = True  # Set False to disable rejection logic

    # Context limit: max previous sections to include in context (prevents token explosion)
    QUALITY_GATES_MAX_CONTEXT_SECTIONS: int = 10  # Last 10 sections = ~30KB context

    # Partial Completion (Decision: 85% threshold, 01.12.2025)
    PARTIAL_COMPLETION_ENABLED: bool = True
    PARTIAL_COMPLETION_THRESHOLD: float = 0.85  # 85% - deliver if 43/50 sections OK

    # Search APIs for RAG
    SEMANTIC_SCHOLAR_API_KEY: str | None = None
    SEMANTIC_SCHOLAR_ENABLED: bool = True
    PERPLEXITY_API_KEY: str | None = None
    TAVILY_API_KEY: str | None = None
    SERPER_API_KEY: str | None = None

    # Plagiarism Check API
    COPYSCAPE_API_KEY: str | None = None
    COPYSCAPE_USERNAME: str | None = None

    # Grammar Check API
    LANGUAGETOOL_API_URL: str = "https://api.languagetool.org/v2"
    LANGUAGETOOL_API_KEY: str | None = None
    LANGUAGETOOL_ENABLED: bool = True

    # Training Data Collection (AI Self-Learning)
    TRAINING_DATA_COLLECTION_ENABLED: bool = False
    TRAINING_DATA_DIR: str = "/tmp/training_data"

    # Payment
    STRIPE_SECRET_KEY: str | None = None
    STRIPE_WEBHOOK_SECRET: str | None = None
    STRIPE_PUBLISHABLE_KEY: str | None = None
    FRONTEND_URL: str = "http://localhost:3000"  # Frontend URL for payment redirects

    # Monitoring
    SENTRY_DSN: str | None = None

    # Redis
    REDIS_URL: str = "redis://localhost:6379"

    # MinIO/S3
    MINIO_ENDPOINT: str = "localhost:9000"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin"
    MINIO_BUCKET: str = "ai-thesis-documents"
    MINIO_SECURE: bool = False

    # Email
    SMTP_TLS: bool = True
    SMTP_PORT: int | None = None
    SMTP_HOST: str | None = None
    SMTP_USER: str | None = None
    SMTP_PASSWORD: str | None = None
    EMAILS_FROM_EMAIL: str | None = None
    EMAILS_FROM_NAME: str | None = None

    # Rate limiting - ENV configurable thresholds
    RATE_LIMIT_PER_MINUTE: int = 60
    RATE_LIMIT_MAGIC_LINK_PER_HOUR: int = 3
    RATE_LIMIT_VERIFY_MAGIC_LINK_PER_HOUR: int = 10
    RATE_LIMIT_REFRESH_PER_HOUR: int = 20
    RATE_LIMIT_AUTH_LOCKOUT_THRESHOLD: int = 5  # Failed attempts before lockout
    RATE_LIMIT_AUTH_LOCKOUT_MIN_MINUTES: int = 15  # Minimum lockout duration
    RATE_LIMIT_AUTH_LOCKOUT_MAX_MINUTES: int = 30  # Maximum lockout duration
    DISABLE_RATE_LIMIT: bool = False  # Flag to disable rate limiting entirely

    # Admin Panel Configuration
    ADMIN_EMAIL: str | None = None  # Primary admin email (for notifications)
    ADMIN_SESSION_TIMEOUT_MINUTES: int = 30  # Admin session timeout
    ADMIN_SESSION_UPDATE_ON_ACTIVITY: bool = (
        True  # Update last_activity on each request
    )
    ADMIN_MAX_CONCURRENT_SESSIONS: int = 5  # Maximum concurrent sessions per admin
    ADMIN_IP_WHITELIST: str | None = (
        None  # Comma-separated list: "192.168.1.1,10.0.0.1" (empty = all IPs allowed)
    )
    ADMIN_2FA_REQUIRED: bool = False  # Require 2FA for admins (not implemented yet)
    ADMIN_AUDIT_LOG_RETENTION_DAYS: int = 90  # How long to keep audit logs
    ADMIN_RATE_LIMIT_PER_MINUTE: int = (
        60  # More restrictive rate limit for admin endpoints
    )
    ADMIN_RATE_LIMIT_PER_HOUR: int = 300

    # Maintenance Mode
    MAINTENANCE_MODE_ENABLED: bool = False
    MAINTENANCE_MODE_MESSAGE: str = "System maintenance in progress"
    MAINTENANCE_ALLOWED_IPS: str | None = (
        None  # Comma-separated list of IPs allowed during maintenance
    )

    # Token usage limits (optional - set to None to disable)
    DAILY_TOKEN_LIMIT: int | None = None  # 1M tokens per day default (None = disabled)

    model_config = ConfigDict(
        env_file=".env",
        case_sensitive=True,
        env_ignore_empty=True,  # Ignore empty env vars
        # Exclude ALLOWED_ORIGINS from env file parsing - it's set via model_validator
        env_prefix="",  # No prefix needed
    )  # type: ignore[typeddict-unknown-key,assignment]

    @field_validator("SECRET_KEY")
    @classmethod
    def validate_secret_key(cls, v: str | None, info) -> str | None:  # type: ignore[override]
        """Validate SECRET_KEY - CRITICAL: must be set via ENV (no auto-generation)"""
        env = (
            info.data.get("ENVIRONMENT", "development")
            if hasattr(info, "data")
            else "development"
        )
        is_prod = env.lower() in {"production", "prod"}

        if is_prod:
            if not v or v.strip() == "":
                raise ValueError(
                    "SECRET_KEY must be set via environment variable in production"
                )
            if len(v) < 32:
                raise ValueError(
                    "SECRET_KEY must be at least 32 characters in production"
                )
            # Reject common insecure defaults
            if v in [
                "your-secret-key-change-in-production",
                "secret",
                "password",
                "changeme",
            ]:
                raise ValueError(
                    "SECRET_KEY must not use default/insecure values in production"
                )
        else:
            # Development: require explicit .env (no auto-generation for session stability)
            if not v or v.strip() == "":
                raise ValueError(
                    "SECRET_KEY must be set via environment variable or .env file. "
                    "Auto-generation is disabled to maintain session/token stability. "
                    "Set JWT_SECRET or SECRET_KEY in .env"
                )
            if v == "your-secret-key-change-in-production" or (v and len(v) < 32):
                raise ValueError(
                    "SECRET_KEY must be at least 32 characters and not use default values. "
                    "Set JWT_SECRET or SECRET_KEY in .env with a stable, secure value"
                )

        return v

    @field_validator("JWT_SECRET")
    @classmethod
    def validate_jwt_secret(cls, v: str | None, info) -> str | None:  # type: ignore[override]
        """Validate JWT_SECRET - must meet security requirements"""
        env = (
            info.data.get("ENVIRONMENT", "development")
            if hasattr(info, "data")
            else "development"
        )
        is_prod = env.lower() in {"production", "prod"}
        is_test = env.lower() == "test"

        # Skip validation for test environment
        if is_test:
            return v

        # Check for forbidden words (only for non-test envs)
        forbidden_words = ["secret", "password", "admin", "changeme", "default"]

        if is_prod:
            if not v or v.strip() == "":
                # In production, JWT_SECRET or SECRET_KEY must be set
                # This is validated later in model_validator
                return v
            if len(v) < 32:
                raise ValueError(
                    "JWT_SECRET must be at least 32 characters in production"
                )
            if any(word in v.lower() for word in forbidden_words):
                raise ValueError(
                    f"JWT_SECRET must not contain forbidden words: {forbidden_words}"
                )
        else:
            # Development: warn if weak but don't fail
            if v:
                if len(v) < 32:
                    raise ValueError("JWT_SECRET must be at least 32 characters")
                if any(word in v.lower() for word in forbidden_words):
                    raise ValueError(
                        f"JWT_SECRET must not contain forbidden words: {forbidden_words}"
                    )

        return v

    @field_validator("ALLOWED_ORIGINS")
    @classmethod
    def validate_allowed_origins(cls, v: list[str], info):  # type: ignore[override]
        """Strengthened CORS validation: reject wildcards in any env, validate URLs, reject localhost in prod"""
        env = (
            info.data.get("ENVIRONMENT", "development")
            if hasattr(info, "data")
            else "development"
        )
        is_prod = env.lower() in {"production", "prod"}

        # Check if CORS_ALLOWED_ORIGINS is set - if so, skip localhost validation
        # because model_validator will override ALLOWED_ORIGINS with CORS_ALLOWED_ORIGINS
        cors_allowed_origins = (
            info.data.get("CORS_ALLOWED_ORIGINS") if hasattr(info, "data") else None
        )
        skip_localhost_check = bool(cors_allowed_origins)

        # Reject wildcards in ANY environment
        if any(origin.strip() == "*" for origin in v):
            raise ValueError("Wildcard origins (*) are not allowed in any environment")

        # Validate each origin is a valid URL
        validated_origins = []
        for origin in v:
            origin = origin.strip()
            if not origin:
                continue

            # Validate URL format (must start with http:// or https://)
            if not origin.startswith(("http://", "https://")):
                raise ValueError(
                    f"Invalid CORS origin format: {origin}. Must start with http:// or https://"
                )

            # Parse and validate URL structure
            try:
                parsed = urlparse(origin)
                if not parsed.netloc:
                    raise ValueError(f"Invalid CORS origin URL: {origin}")
            except Exception as e:
                raise ValueError(f"Invalid CORS origin URL: {origin} - {str(e)}") from e

            # In production: reject localhost, 127.0.0.1, 0.0.0.0
            # BUT skip if CORS_ALLOWED_ORIGINS is set (model_validator will override)
            if is_prod and not skip_localhost_check:
                localhost_patterns = ["localhost", "127.0.0.1", "0.0.0.0", "::1"]
                if any(
                    pattern in parsed.netloc.lower() for pattern in localhost_patterns
                ):
                    raise ValueError(
                        f"Localhost/0.0.0.0 origins are not allowed in production: {origin}"
                    )

            validated_origins.append(origin)

        # Production: require explicit list (cannot be empty)
        if is_prod and not validated_origins:
            raise ValueError(
                "ALLOWED_ORIGINS must be explicitly set via CORS_ALLOWED_ORIGINS environment variable in production"
            )

        return validated_origins

    @field_validator("DATABASE_URL")
    @classmethod
    def validate_database_url(cls, v: str | None, info):  # type: ignore[override]
        """Validate DATABASE_URL - CRITICAL: must be set and secure in production"""
        env = (
            info.data.get("ENVIRONMENT", "development")
            if hasattr(info, "data")
            else "development"
        )
        is_prod = env.lower() in {"production", "prod"}

        if is_prod:
            if not v or v.strip() == "":
                raise ValueError(
                    "DATABASE_URL must be set via environment variable in production"
                )
            # Reject default credentials and placeholder URLs
            default_patterns = [
                ":password@",
                ":postgres@",
                ":admin@",
                "localhost",
                "127.0.0.1",
                "postgresql://postgres:",
                "changeme",
                "default",
                "placeholder",
            ]
            if any(pattern.lower() in v.lower() for pattern in default_patterns):
                raise ValueError(
                    "DATABASE_URL must not contain default credentials or placeholder values in production"
                )
            # Ensure it's a valid postgresql URL format
            if not v.startswith(("postgresql://", "postgresql+asyncpg://")):
                raise ValueError(
                    "DATABASE_URL must be a valid PostgreSQL connection string in production"
                )

        # Development: allow defaults but warn if placeholder detected
        if not is_prod and v:
            if ":password@" in v or ":postgres@" in v:
                import warnings

                warnings.warn(
                    "Using default database credentials in development",
                    UserWarning,
                    stacklevel=2,
                )

        return v

    @field_validator("STRIPE_SECRET_KEY")
    @classmethod
    def validate_stripe_key(cls, v: str | None, info) -> str | None:  # type: ignore[override]
        """Warn if Stripe not configured"""
        if not v:
            import logging

            logging.warning("⚠️ STRIPE_SECRET_KEY not set - payments disabled")
        return v

    @model_validator(mode="after")
    def validate_production_requirements(self):  # type: ignore[override]
        """Final validation: ensure critical ENV vars are set in production"""
        is_prod = self.ENVIRONMENT.lower() in {"production", "prod"}

        # Process CORS_ALLOWED_ORIGINS from ENV if provided (required in production)
        if self.CORS_ALLOWED_ORIGINS:
            origins_list = [
                origin.strip()
                for origin in self.CORS_ALLOWED_ORIGINS.split(",")
                if origin.strip()
            ]
            if origins_list:
                object.__setattr__(self, "ALLOWED_ORIGINS", origins_list)
        elif is_prod:
            # Production: require explicit CORS_ALLOWED_ORIGINS from ENV
            if not self.ALLOWED_ORIGINS or len(self.ALLOWED_ORIGINS) == 0:
                raise ValueError(
                    "CORS_ALLOWED_ORIGINS must be explicitly set via environment variable in production. "
                    "Cannot use default values."
                )

        if is_prod:
            object.__setattr__(self, "DEBUG", False)

            # Ensure at least one secret key is set (JWT_SECRET or SECRET_KEY)
            if not self.JWT_SECRET and not self.SECRET_KEY:
                raise ValueError(
                    "Either JWT_SECRET or SECRET_KEY must be set via environment variable in production"
                )

            # JWT_SECRET takes precedence - validate if set
            if self.JWT_SECRET:
                if len(self.JWT_SECRET) < 32:
                    raise ValueError(
                        "JWT_SECRET must be at least 32 characters in production"
                    )
                # Ensure JWT_SECRET differs from SECRET_KEY if both are set
                if self.SECRET_KEY and self.JWT_SECRET == self.SECRET_KEY:
                    raise ValueError(
                        "JWT_SECRET must be different from SECRET_KEY for security"
                    )

            # Ensure DATABASE_URL is set
            if not self.DATABASE_URL or self.DATABASE_URL.strip() == "":
                raise ValueError(
                    "DATABASE_URL must be set via environment variable in production"
                )

            # Validate API keys & service secrets (fail-fast)
            self._validate_api_keys_and_secrets()
        else:
            # Development: provide fallback default only if not set (for backwards compatibility)
            # This allows .env to override, but provides a sensible default for local dev
            if not self.DATABASE_URL or self.DATABASE_URL.strip() == "":
                object.__setattr__(
                    self,
                    "DATABASE_URL",
                    "postgresql+asyncpg://postgres:password@localhost:5432/ai_thesis_platform",
                )

            # Development: warn if JWT_SECRET and SECRET_KEY are the same
            if (
                self.JWT_SECRET
                and self.SECRET_KEY
                and self.JWT_SECRET == self.SECRET_KEY
            ):
                import warnings

                warnings.warn(
                    "JWT_SECRET and SECRET_KEY are the same. For better security, use different values.",
                    UserWarning,
                    stacklevel=2,
                )

        return self

    def _validate_api_keys_and_secrets(self) -> None:
        """Validate API keys and service secrets - fail-fast on missing/invalid secrets"""
        # AI Provider API keys: required if provider enabled
        # Validate that if OPENAI_API_KEY or ANTHROPIC_API_KEY is set, it must be valid
        if self.OPENAI_API_KEY:
            if not self.OPENAI_API_KEY.strip() or len(self.OPENAI_API_KEY.strip()) < 20:
                raise ValueError(
                    "OPENAI_API_KEY must be a valid API key (minimum 20 characters)"
                )
            # Reject placeholder values
            invalid_values = [
                "sk-...",
                "your-openai-api-key",
                "changeme",
                "OPENAI_API_KEY",
                "",
            ]
            if self.OPENAI_API_KEY.strip() in invalid_values:
                raise ValueError(
                    "OPENAI_API_KEY must not use placeholder or default values in production"
                )
            # OpenAI keys should start with "sk-"
            if not self.OPENAI_API_KEY.strip().startswith("sk-"):
                raise ValueError(
                    "OPENAI_API_KEY must be a valid OpenAI API key format (starts with 'sk-')"
                )

        if self.ANTHROPIC_API_KEY:
            if (
                not self.ANTHROPIC_API_KEY.strip()
                or len(self.ANTHROPIC_API_KEY.strip()) < 20
            ):
                raise ValueError(
                    "ANTHROPIC_API_KEY must be a valid API key (minimum 20 characters)"
                )
            # Reject placeholder values
            invalid_values = [
                "sk-ant-...",
                "your-anthropic-api-key",
                "changeme",
                "ANTHROPIC_API_KEY",
                "",
            ]
            if self.ANTHROPIC_API_KEY.strip() in invalid_values:
                raise ValueError(
                    "ANTHROPIC_API_KEY must not use placeholder or default values in production"
                )
            # Anthropic keys should start with "sk-ant-"
            if not self.ANTHROPIC_API_KEY.strip().startswith("sk-ant-"):
                raise ValueError(
                    "ANTHROPIC_API_KEY must be a valid Anthropic API key format (starts with 'sk-ant-')"
                )

        # MinIO/S3: reject "minioadmin" in production
        if (
            self.MINIO_ACCESS_KEY == "minioadmin"
            or self.MINIO_SECRET_KEY == "minioadmin"
        ):
            raise ValueError(
                "MINIO_ACCESS_KEY and MINIO_SECRET_KEY must not use default 'minioadmin' value in production"
            )
        if not self.MINIO_ACCESS_KEY or not self.MINIO_SECRET_KEY:
            raise ValueError(
                "MINIO_ACCESS_KEY and MINIO_SECRET_KEY must be set in production"
            )
        if len(self.MINIO_ACCESS_KEY) < 8 or len(self.MINIO_SECRET_KEY) < 8:
            raise ValueError(
                "MINIO_ACCESS_KEY and MINIO_SECRET_KEY must be at least 8 characters in production"
            )

        # SMTP: password required if email active
        # Email is considered active if SMTP_HOST is set
        if self.SMTP_HOST:
            if not self.SMTP_PASSWORD or not self.SMTP_PASSWORD.strip():
                raise ValueError(
                    "SMTP_PASSWORD must be set when SMTP_HOST is configured in production"
                )
            if not self.SMTP_PORT:
                raise ValueError(
                    "SMTP_PORT must be set when SMTP_HOST is configured in production"
                )
            if not self.SMTP_USER:
                raise ValueError(
                    "SMTP_USER must be set when SMTP_HOST is configured in production"
                )

    @property
    def jwt_secret_key(self) -> str:
        """Get JWT secret key - prefer JWT_SECRET over SECRET_KEY"""
        return self.JWT_SECRET if self.JWT_SECRET else self.SECRET_KEY  # type: ignore

    @property
    def AI_RETRY_DELAYS_LIST(self) -> list[int]:
        """
        Parse retry delays from comma-separated string to list of integers.

        Example:
            AI_RETRY_DELAYS="2,4,8" → [2, 4, 8]

        Returns:
            List of delay values in seconds
        """
        try:
            return [
                int(x.strip()) for x in self.AI_RETRY_DELAYS.split(",") if x.strip()
            ]
        except (ValueError, AttributeError):
            # Fallback to default if parsing fails
            return [2, 4, 8]

    @property
    def AI_FALLBACK_CHAIN_LIST(self) -> list[tuple[str, str]]:
        """
        Parse fallback chain from comma-separated string to list of (provider, model) tuples.

        Example:
            AI_FALLBACK_CHAIN="openai:gpt-4,anthropic:claude-3-5-sonnet"
            → [("openai", "gpt-4"), ("anthropic", "claude-3-5-sonnet")]

        Returns:
            List of (provider, model) tuples
        """
        try:
            chain = []
            for item in self.AI_FALLBACK_CHAIN.split(","):
                item = item.strip()
                if ":" in item:
                    provider, model = item.split(":", 1)
                    chain.append((provider.strip(), model.strip()))
            return chain if chain else [("openai", "gpt-4")]
        except (ValueError, AttributeError):
            # Fallback to default if parsing fails
            return [("openai", "gpt-4")]


# Create settings instance
settings = Settings()


def reload_settings() -> dict[str, Any]:
    """
    Reload settings from environment variables.

    This method allows for runtime config reloading (e.g., for secrets rotation).
    Note: Some settings (e.g., DATABASE_URL) may require application restart to take effect.

    Returns:
        dict with validation_passed (bool) and warnings (list)
    """
    warnings = []

    try:
        # Re-read environment variables by creating new Settings instance
        new_settings = Settings()

        # Update the global settings instance attributes
        for key in new_settings.model_fields:
            if hasattr(new_settings, key):
                value = getattr(new_settings, key)
                object.__setattr__(settings, key, value)

        # Run validation
        try:
            settings.validate_production_requirements()  # type: ignore[misc]
            validation_passed = True
        except ValueError as e:
            validation_passed = False
            warnings.append(f"Validation warning: {str(e)}")

        return {"validation_passed": validation_passed, "warnings": warnings}
    except Exception as e:
        return {
            "validation_passed": False,
            "warnings": [f"Error reloading settings: {str(e)}"],
        }
