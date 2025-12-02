"""
Pydantic schemas for settings management
"""

from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field


class SettingsResponse(BaseModel):
    """Response schema for settings"""

    category: str
    settings: dict[str, Any]


class PricingSettingsUpdate(BaseModel):
    """Schema for updating pricing settings"""

    price_per_page: Decimal = Field(..., description="Price per page in EUR", gt=0)
    min_pages: int = Field(..., description="Minimum pages", ge=1)
    max_pages: int = Field(..., description="Maximum pages", le=200)
    currencies: list[str] = Field(default=["EUR"], description="Supported currencies")

    model_config = {
        "json_schema_extra": {
            "example": {
                "price_per_page": "0.50",
                "min_pages": 3,
                "max_pages": 200,
                "currencies": ["EUR"],
            }
        }
    }


class AISettingsUpdate(BaseModel):
    """Schema for updating AI settings"""

    default_provider: str = Field(..., description="Default AI provider")
    default_model: str = Field(..., description="Default AI model")
    fallback_models: list[str] = Field(
        default_factory=list, description="Fallback models"
    )
    max_retries: int = Field(default=3, description="Maximum retries", ge=1, le=10)
    timeout_seconds: int = Field(
        default=300, description="Timeout in seconds", ge=30, le=600
    )
    temperature_default: float = Field(
        default=0.7, description="Default temperature", ge=0.0, le=2.0
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "default_provider": "openai",
                "default_model": "gpt-4",
                "fallback_models": ["gpt-3.5-turbo"],
                "max_retries": 3,
                "timeout_seconds": 300,
                "temperature_default": 0.7,
            }
        }
    }


class LimitSettingsUpdate(BaseModel):
    """Schema for updating limit settings"""

    max_concurrent_generations: int = Field(
        ..., description="Max concurrent generations", ge=1
    )
    max_documents_per_user: int = Field(..., description="Max documents per user", ge=1)
    max_pages_per_document: int = Field(
        ..., description="Max pages per document", ge=1, le=200
    )
    daily_token_limit: int | None = Field(
        default=None, description="Daily token limit per user (None = unlimited)"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "max_concurrent_generations": 5,
                "max_documents_per_user": 100,
                "max_pages_per_document": 200,
                "daily_token_limit": 1000000,
            }
        }
    }


class MaintenanceSettingsUpdate(BaseModel):
    """Schema for updating maintenance mode settings"""

    enabled: bool = Field(..., description="Enable maintenance mode")
    message: str = Field(
        default="System maintenance in progress",
        description="Maintenance message",
        max_length=500,
    )
    allowed_ips: list[str] = Field(
        default_factory=list,
        description="IP addresses allowed during maintenance",
    )
    estimated_end_time: datetime | None = Field(
        default=None, description="Estimated end time"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "enabled": True,
                "message": "System maintenance in progress. We'll be back soon!",
                "allowed_ips": ["192.168.1.1", "10.0.0.1"],
                "estimated_end_time": "2025-11-03T12:00:00Z",
            }
        }
    }


class SettingHistoryEntry(BaseModel):
    """Schema for setting history entry"""

    version: int
    value: Any
    updated_by: int
    updated_at: datetime | None


class SettingHistoryResponse(BaseModel):
    """Response schema for setting history"""

    key: str
    history: list[SettingHistoryEntry]
