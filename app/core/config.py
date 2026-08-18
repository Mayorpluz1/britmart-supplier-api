"""Central application configuration for the BritMart Supplier API."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


EnvironmentName = Literal[
    "development",
    "test",
    "staging",
    "production",
]

LogLevel = Literal[
    "DEBUG",
    "INFO",
    "WARNING",
    "ERROR",
    "CRITICAL",
]


class Settings(BaseSettings):
    """Environment-driven application settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        validate_default=True,
    )

    # Application identity
    app_name: str = (
        "BritMart Supplier and Procurement API"
    )
    app_description: str = (
        "Operational supplier, procurement, shipment and "
        "delivery-management API for BritMart."
    )
    app_version: str = "1.0.0"
    environment: EnvironmentName = "development"
    debug: bool = False
    timezone: str = "UTC"

    # API contract
    api_version: str = "v1"
    api_prefix: str = "/api/v1"
    docs_url: str | None = "/docs"
    redoc_url: str | None = "/redoc"
    openapi_url: str | None = "/openapi.json"

    # Database
    database_url: str = (
        "sqlite:///./britmart_supplier.db"
    )
    database_echo: bool = False
    database_pool_pre_ping: bool = True
    database_pool_size: int = Field(
        default=5,
        ge=1,
        le=50,
    )
    database_max_overflow: int = Field(
        default=10,
        ge=0,
        le=100,
    )
    database_pool_timeout_seconds: int = Field(
        default=30,
        ge=1,
        le=300,
    )

    # API-key authentication
    api_key_header_name: str = "X-API-Key"
    api_key: SecretStr = SecretStr(
        "development-only-change-me"
    )
    authentication_enabled: bool = True

    # Pagination
    default_page_size: int = Field(
        default=100,
        ge=1,
        le=1000,
    )
    maximum_page_size: int = Field(
        default=1000,
        ge=1,
        le=5000,
    )

    # Incremental extraction
    incremental_default_lookback_days: int = Field(
        default=30,
        ge=1,
        le=365,
    )
    incremental_maximum_window_days: int = Field(
        default=366,
        ge=1,
        le=3660,
    )

    # Controlled failure simulation
    failure_simulation_enabled: bool = False

    failure_simulation_rate: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
    )

    failure_simulation_status_code: int = Field(
        default=503,
        ge=400,
        le=599,
    )

    failure_simulation_delay_seconds: float = Field(
        default=0.0,
        ge=0.0,
        le=60.0,
    )

    failure_simulation_max_delay_ms: int = Field(
        default=10_000,
        ge=0,
        le=60_000,
    )

    # Request and logging controls
    request_timeout_seconds: int = Field(
        default=30,
        ge=1,
        le=300,
    )
    log_level: LogLevel = "INFO"
    log_json: bool = True
    request_id_header_name: str = "X-Request-ID"

    # Health checks
    health_check_database_enabled: bool = True

    @model_validator(mode="after")
    def validate_settings(self) -> "Settings":
        """Validate interdependent settings."""

        if (
            self.default_page_size
            > self.maximum_page_size
        ):
            raise ValueError(
                "default_page_size cannot exceed "
                "maximum_page_size."
            )

        development_key = (
            "development-only-change-me"
        )

        if (
            self.environment
            in {"staging", "production"}
            and self.authentication_enabled
            and self.api_key.get_secret_value()
            == development_key
        ):
            raise ValueError(
                "A secure API_KEY must be supplied in "
                "staging and production."
            )

        if (
            self.failure_simulation_enabled
            and self.environment == "production"
        ):
            raise ValueError(
                "Failure simulation cannot be enabled "
                "in production."
            )

        return self

    @property
    def is_sqlite(self) -> bool:
        """Return whether the database is SQLite."""

        return self.database_url.startswith("sqlite")

    @property
    def is_production(self) -> bool:
        """Return whether this is production."""

        return self.environment == "production"


@lru_cache
def get_settings() -> Settings:
    """Return one cached settings instance."""

    return Settings()


settings = get_settings()