"""
Application configuration
"""

from typing import Any
from urllib.parse import urlparse

from pydantic import field_validator, model_validator
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
    ALLOWED_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
    ]
    ALLOWED_HOSTS: list[str] = ["localhost", "127.0.0.1", "0.0.0.0"]

    # AI Providers
    OPENAI_API_KEY: str | None = None
    ANTHROPIC_API_KEY: str | None = None

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

    class Config:
        env_file = ".env"
        case_sensitive = True

    @field_validator("SECRET_KEY")
    @classmethod
    def validate_secret_key(cls, v: str | None, info) -> str | None:  # type: ignore[override]
        """Validate SECRET_KEY - CRITICAL: must be set via ENV (no auto-generation)"""
        env = info.data.get("ENVIRONMENT", "development") if hasattr(info, "data") else "development"
        is_prod = env.lower() in {"production", "prod"}

        if is_prod:
            if not v or v.strip() == "":
                raise ValueError("SECRET_KEY must be set via environment variable in production")
            if len(v) < 32:
                raise ValueError("SECRET_KEY must be at least 32 characters in production")
            # Reject common insecure defaults
            if v in ["your-secret-key-change-in-production", "secret", "password", "changeme"]:
                raise ValueError("SECRET_KEY must not use default/insecure values in production")
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

    @field_validator("ALLOWED_ORIGINS")
    @classmethod
    def validate_allowed_origins(cls, v: list[str], info):  # type: ignore[override]
        """Strengthened CORS validation: reject wildcards in any env, validate URLs, reject localhost in prod"""
        env = info.data.get("ENVIRONMENT", "development") if hasattr(info, "data") else "development"
        is_prod = env.lower() in {"production", "prod"}

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
                raise ValueError(f"Invalid CORS origin format: {origin}. Must start with http:// or https://")

            # Parse and validate URL structure
            try:
                parsed = urlparse(origin)
                if not parsed.netloc:
                    raise ValueError(f"Invalid CORS origin URL: {origin}")
            except Exception as e:
                raise ValueError(f"Invalid CORS origin URL: {origin} - {str(e)}")

            # In production: reject localhost, 127.0.0.1, 0.0.0.0
            if is_prod:
                localhost_patterns = ["localhost", "127.0.0.1", "0.0.0.0", "::1"]
                if any(pattern in parsed.netloc.lower() for pattern in localhost_patterns):
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
        env = info.data.get("ENVIRONMENT", "development") if hasattr(info, "data") else "development"
        is_prod = env.lower() in {"production", "prod"}

        if is_prod:
            if not v or v.strip() == "":
                raise ValueError("DATABASE_URL must be set via environment variable in production")
            # Reject default credentials and placeholder URLs
            default_patterns = [
                ":password@", ":postgres@", ":admin@",
                "localhost", "127.0.0.1", "postgresql://postgres:",
                "changeme", "default", "placeholder"
            ]
            if any(pattern.lower() in v.lower() for pattern in default_patterns):
                raise ValueError("DATABASE_URL must not contain default credentials or placeholder values in production")
            # Ensure it's a valid postgresql URL format
            if not v.startswith(("postgresql://", "postgresql+asyncpg://")):
                raise ValueError("DATABASE_URL must be a valid PostgreSQL connection string in production")

        # Development: allow defaults but warn if placeholder detected
        if not is_prod and v:
            if ":password@" in v or ":postgres@" in v:
                import warnings
                warnings.warn("Using default database credentials in development", UserWarning)

        return v

    @model_validator(mode="after")
    def validate_production_requirements(self):  # type: ignore[override]
        """Final validation: ensure critical ENV vars are set in production"""
        is_prod = self.ENVIRONMENT.lower() in {"production", "prod"}

        # Process CORS_ALLOWED_ORIGINS from ENV if provided (required in production)
        if self.CORS_ALLOWED_ORIGINS:
            origins_list = [origin.strip() for origin in self.CORS_ALLOWED_ORIGINS.split(",") if origin.strip()]
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
                    raise ValueError("JWT_SECRET must be at least 32 characters in production")

            # Ensure DATABASE_URL is set
            if not self.DATABASE_URL or self.DATABASE_URL.strip() == "":
                raise ValueError("DATABASE_URL must be set via environment variable in production")

            # Validate API keys & service secrets (fail-fast)
            self._validate_api_keys_and_secrets()
        else:
            # Development: provide fallback default only if not set (for backwards compatibility)
            # This allows .env to override, but provides a sensible default for local dev
            if not self.DATABASE_URL or self.DATABASE_URL.strip() == "":
                object.__setattr__(
                    self,
                    "DATABASE_URL",
                    "postgresql+asyncpg://postgres:password@localhost:5432/ai_thesis_platform"
                )

        return self

    def _validate_api_keys_and_secrets(self) -> None:
        """Validate API keys and service secrets - fail-fast on missing/invalid secrets"""
        # AI Provider API keys: required if provider enabled
        # Validate that if OPENAI_API_KEY or ANTHROPIC_API_KEY is set, it must be valid
        if self.OPENAI_API_KEY:
            if not self.OPENAI_API_KEY.strip() or len(self.OPENAI_API_KEY.strip()) < 20:
                raise ValueError("OPENAI_API_KEY must be a valid API key (minimum 20 characters)")
            # Reject placeholder values
            invalid_values = ["sk-...", "your-openai-api-key", "changeme", "OPENAI_API_KEY", ""]
            if self.OPENAI_API_KEY.strip() in invalid_values:
                raise ValueError("OPENAI_API_KEY must not use placeholder or default values in production")
            # OpenAI keys should start with "sk-"
            if not self.OPENAI_API_KEY.strip().startswith("sk-"):
                raise ValueError("OPENAI_API_KEY must be a valid OpenAI API key format (starts with 'sk-')")

        if self.ANTHROPIC_API_KEY:
            if not self.ANTHROPIC_API_KEY.strip() or len(self.ANTHROPIC_API_KEY.strip()) < 20:
                raise ValueError("ANTHROPIC_API_KEY must be a valid API key (minimum 20 characters)")
            # Reject placeholder values
            invalid_values = ["sk-ant-...", "your-anthropic-api-key", "changeme", "ANTHROPIC_API_KEY", ""]
            if self.ANTHROPIC_API_KEY.strip() in invalid_values:
                raise ValueError("ANTHROPIC_API_KEY must not use placeholder or default values in production")
            # Anthropic keys should start with "sk-ant-"
            if not self.ANTHROPIC_API_KEY.strip().startswith("sk-ant-"):
                raise ValueError("ANTHROPIC_API_KEY must be a valid Anthropic API key format (starts with 'sk-ant-')")

        # MinIO/S3: reject "minioadmin" in production
        if self.MINIO_ACCESS_KEY == "minioadmin" or self.MINIO_SECRET_KEY == "minioadmin":
            raise ValueError(
                "MINIO_ACCESS_KEY and MINIO_SECRET_KEY must not use default 'minioadmin' value in production"
            )
        if not self.MINIO_ACCESS_KEY or not self.MINIO_SECRET_KEY:
            raise ValueError("MINIO_ACCESS_KEY and MINIO_SECRET_KEY must be set in production")
        if len(self.MINIO_ACCESS_KEY) < 8 or len(self.MINIO_SECRET_KEY) < 8:
            raise ValueError("MINIO_ACCESS_KEY and MINIO_SECRET_KEY must be at least 8 characters in production")

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
            settings.validate_production_requirements()
            validation_passed = True
        except ValueError as e:
            validation_passed = False
            warnings.append(f"Validation warning: {str(e)}")

        return {
            "validation_passed": validation_passed,
            "warnings": warnings
        }
    except Exception as e:
        return {
            "validation_passed": False,
            "warnings": [f"Error reloading settings: {str(e)}"]
        }
