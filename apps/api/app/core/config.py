"""
Application configuration
"""

from pydantic_settings import BaseSettings
from typing import List, Optional
import os
import secrets
from pydantic import field_validator, model_validator


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
    DATABASE_URL: Optional[str] = None
    
    # Security
    # CRITICAL: No default value - must be provided via ENV in production
    SECRET_KEY: Optional[str] = None
    
    # JWT Configuration (ENV-based, no defaults)
    JWT_SECRET: Optional[str] = None  # Prefer JWT_SECRET over SECRET_KEY if set
    JWT_ALG: str = "HS256"  # Algorithm for JWT signing/verification
    JWT_ISS: Optional[str] = None  # Issuer claim (optional but recommended)
    JWT_AUD: Optional[str] = None  # Audience claim (optional but recommended)
    JWT_EXP_MIN: int = 30  # Token expiration in minutes
    
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # CORS
    ALLOWED_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
    ]
    ALLOWED_HOSTS: List[str] = ["localhost", "127.0.0.1", "0.0.0.0"]
    
    # AI Providers
    OPENAI_API_KEY: Optional[str] = None
    ANTHROPIC_API_KEY: Optional[str] = None

    # Monitoring
    SENTRY_DSN: Optional[str] = None
    
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
    SMTP_PORT: Optional[int] = None
    SMTP_HOST: Optional[str] = None
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    EMAILS_FROM_EMAIL: Optional[str] = None
    EMAILS_FROM_NAME: Optional[str] = None
    
    # Rate limiting
    RATE_LIMIT_PER_MINUTE: int = 60
    
    class Config:
        env_file = ".env"
        case_sensitive = True

    @field_validator("SECRET_KEY")
    @classmethod
    def validate_secret_key(cls, v: Optional[str], info) -> Optional[str]:  # type: ignore[override]
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
    def validate_allowed_origins(cls, v: List[str], info):  # type: ignore[override]
        # Disallow wildcard in production
        env = info.data.get("ENVIRONMENT", "development") if hasattr(info, "data") else "development"
        if env.lower() in {"production", "prod"}:
            if any(origin.strip() == "*" for origin in v):
                raise ValueError("Wildcard origins are not allowed in production")
            if not v:
                raise ValueError("ALLOWED_ORIGINS must be set in production")
        return v

    @field_validator("DATABASE_URL")
    @classmethod
    def validate_database_url(cls, v: Optional[str], info):  # type: ignore[override]
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


# Create settings instance
settings = Settings()
