"""
Configuration Management

This module handles all application configuration using Pydantic Settings.
Settings are loaded from environment variables with validation and type checking.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, field_validator
from typing import List, Literal
import json


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.

    All settings are loaded from .env file and environment variables.
    Type validation is automatic via Pydantic.
    """

    # ========================================================================
    # APPLICATION SETTINGS
    # ========================================================================

    app_name: str = Field(
        default="FCA Multi-Agent Support System",
        description="Application name",
    )

    app_version: str = Field(
        default="0.1.0",
        description="Application version (semantic versioning)",
    )

    environment: Literal["development", "staging", "production"] = Field(
        default="development",
        description="Current environment",
    )

    debug: bool = Field(
        default=False,
        description="Enable debug mode (detailed errors, API docs)",
    )

    # ========================================================================
    # DATABASE SETTINGS
    # ========================================================================

    database_url: str = Field(
        default="postgresql+asyncpg://fca_user:fca_password@localhost:5432/fca_support",
        description="PostgreSQL connection URL",
    )

    database_echo: bool = Field(
        default=False,
        description="Echo SQL queries to console (debugging)",
    )

    database_pool_size: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Database connection pool size",
    )

    database_max_overflow: int = Field(
        default=10,
        ge=0,
        le=50,
        description="Max connections above pool_size",
    )

    # ========================================================================
    # REDIS SETTINGS
    # ========================================================================

    redis_url: str = Field(
        default="redis://localhost:6379/0",
        description="Redis connection URL",
    )

    redis_enabled: bool = Field(
        default=False,
        description="Enable Redis caching",
    )

    # ========================================================================
    # GROQ AI SETTINGS
    # ========================================================================

    groq_api_key: str = Field(
        default="",
        description="Groq AI API key (required for LLM)",
    )

    groq_model: str = Field(
        default="mixtral-8x7b-32768",
        description="Groq AI model name",
    )

    groq_temperature: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="LLM temperature (0=deterministic, 1=creative)",
    )

    groq_max_tokens: int = Field(
        default=1024,
        ge=1,
        le=32768,
        description="Maximum tokens in response",
    )

    groq_timeout: int = Field(
        default=30,
        ge=5,
        le=300,
        description="API request timeout (seconds)",
    )

    # ========================================================================
    # SECURITY SETTINGS
    # ========================================================================

    secret_key: str = Field(
        default="your-secret-key-change-in-production",
        min_length=32,
        description="Secret key for encryption (min 32 chars)",
    )

    cors_origins: List[str] = Field(
        default=["http://localhost:3000", "http://localhost:8000"],
        description="Allowed CORS origins",
    )

    # ========================================================================
    # RATE LIMITING SETTINGS
    # ========================================================================

    rate_limit_calls: int = Field(
        default=10,
        ge=1,
        description="Max requests per period",
    )

    rate_limit_period: int = Field(
        default=60,
        ge=1,
        description="Rate limit period (seconds)",
    )

    # ========================================================================
    # LOGGING SETTINGS
    # ========================================================================

    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO",
        description="Minimum log level",
    )

    log_file: str = Field(
        default="logs/app.log",
        description="Log file path",
    )

    log_format: Literal["json", "text"] = Field(
        default="json",
        description="Log output format",
    )

    # ========================================================================
    # REQUEST VALIDATION SETTINGS
    # ========================================================================

    max_body_size: int = Field(
        default=10485760,  # 10 MB
        ge=1024,  # Min 1 KB
        le=52428800,  # Max 50 MB
        description="Maximum request body size (bytes)",
    )

    # ========================================================================
    # PYDANTIC CONFIGURATION
    # ========================================================================

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,  # Environment variables are case-insensitive
        extra="ignore",  # Ignore extra environment variables
    )

    # ========================================================================
    # VALIDATORS
    # ========================================================================

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v):
        """
        Parse CORS origins from JSON string or list.

        Supports both:
        - List: ["http://localhost:3000"]
        - JSON string: '["http://localhost:3000"]'

        Args:
            v: Value to parse

        Returns:
            List[str]: Parsed origins
        """
        if isinstance(v, str):
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                return [v]  # Single origin as string
        return v

    @field_validator("secret_key")
    @classmethod
    def validate_secret_key(cls, v, info):
        """
        Validate secret key in production.

        Ensures secret key is changed from default in production.

        Args:
            v: Secret key value
            info: Validation context

        Returns:
            str: Validated secret key

        Raises:
            ValueError: If using default key in production
        """
        environment = info.data.get("environment", "development")

        if environment == "production" and v == "your-secret-key-change-in-production":
            raise ValueError(
                "CRITICAL SECURITY: Must change SECRET_KEY in production! "
                "Generate with: openssl rand -hex 32"
            )

        return v

    @field_validator("groq_api_key")
    @classmethod
    def validate_groq_key(cls, v, info):
        """
        Warn if Groq API key is missing.

        Note: Doesn't raise error to allow app to start,
        but agents won't work without key.

        Args:
            v: API key value
            info: Validation context

        Returns:
            str: API key
        """
        if not v or v == "":
            print("⚠️  WARNING: GROQ_API_KEY not set. AI agents will not function.")
            print("   Get free API key: https://console.groq.com")

        return v

    # ========================================================================
    # COMPUTED PROPERTIES
    # ========================================================================

    @property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.environment == "production"

    @property
    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.environment == "development"

    @property
    def database_url_sync(self) -> str:
        """
        Get synchronous database URL (for Alembic migrations).

        Alembic doesn't support asyncpg, so replace with psycopg2.

        Returns:
            str: Synchronous PostgreSQL URL
        """
        return self.database_url.replace("+asyncpg", "")

    def get_log_config(self) -> dict:
        """
        Get logging configuration dictionary.

        Returns:
            dict: Python logging configuration
        """
        return {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "default": {
                    "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                },
                "json": {
                    "()": "pythonjsonlogger.jsonlogger.JsonFormatter",
                    "format": "%(asctime)s %(name)s %(levelname)s %(message)s",
                },
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "formatter": "default" if self.log_format == "text" else "json",
                    "stream": "ext://sys.stdout",
                },
                "file": {
                    "class": "logging.handlers.RotatingFileHandler",
                    "formatter": "json",
                    "filename": self.log_file,
                    "maxBytes": 10485760,  # 10 MB
                    "backupCount": 5,
                },
            },
            "root": {
                "level": self.log_level,
                "handlers": ["console", "file"],
            },
        }


# ============================================================================
# SETTINGS INSTANCE
# ============================================================================

# Create global settings instance
# Loaded once at import time
settings = Settings()


# ============================================================================
# SETTINGS DISPLAY (for debugging)
# ============================================================================

def display_settings():
    """
    Display current settings (for debugging).

    Masks sensitive values like API keys and passwords.
    """
    print("=" * 60)
    print("APPLICATION SETTINGS")
    print("=" * 60)

    print(f"\nApplication:")
    print(f"  Name: {settings.app_name}")
    print(f"  Version: {settings.app_version}")
    print(f"  Environment: {settings.environment}")
    print(f"  Debug: {settings.debug}")

    print(f"\nDatabase:")
    # Mask password in URL
    db_url = settings.database_url
    if "@" in db_url:
        parts = db_url.split("@")
        credentials = parts[0].split("://")[1]
        user = credentials.split(":")[0]
        db_url = f"postgresql+asyncpg://{user}:****@{parts[1]}"
    print(f"  URL: {db_url}")
    print(f"  Echo: {settings.database_echo}")
    print(f"  Pool Size: {settings.database_pool_size}")

    print(f"\nRedis:")
    print(f"  URL: {settings.redis_url}")
    print(f"  Enabled: {settings.redis_enabled}")

    print(f"\nGroq AI:")
    # Mask API key
    key_display = f"{settings.groq_api_key[:8]}****" if settings.groq_api_key else "NOT SET"
    print(f"  API Key: {key_display}")
    print(f"  Model: {settings.groq_model}")
    print(f"  Temperature: {settings.groq_temperature}")

    print(f"\nSecurity:")
    print(f"  Secret Key: {'SET' if settings.secret_key else 'NOT SET'}")
    print(f"  CORS Origins: {settings.cors_origins}")

    print(f"\nLogging:")
    print(f"  Level: {settings.log_level}")
    print(f"  File: {settings.log_file}")
    print(f"  Format: {settings.log_format}")

    print("=" * 60)


if __name__ == "__main__":
    # Display settings when run directly
    display_settings()
