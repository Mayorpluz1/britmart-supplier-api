"""Shared request and response schemas for the BritMart API."""

from __future__ import annotations

from datetime import datetime
from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field


class APIModel(BaseModel):
    """Base model containing configuration shared by API schemas."""

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        extra="forbid",
        str_strip_whitespace=True,
    )


class PaginationMetadata(APIModel):
    """Metadata describing a paginated API response."""

    page: int = Field(
        ge=1,
        description="Current page number.",
        examples=[1],
    )
    page_size: int = Field(
        ge=1,
        le=500,
        description="Maximum number of records requested per page.",
        examples=[100],
    )
    total_records: int = Field(
        ge=0,
        description="Total number of records matching the request.",
        examples=[9847],
    )
    total_pages: int = Field(
        ge=0,
        description="Total number of available pages.",
        examples=[99],
    )
    has_next: bool = Field(
        description="Indicates whether another page is available.",
        examples=[True],
    )
    has_previous: bool = Field(
        description="Indicates whether an earlier page is available.",
        examples=[False],
    )


ResponseItem = TypeVar("ResponseItem")


class PaginatedResponse(APIModel, Generic[ResponseItem]):
    """Generic envelope returned by paginated collection endpoints."""

    items: list[ResponseItem] = Field(
        description="Records returned for the current page."
    )
    pagination: PaginationMetadata


class ErrorDetail(APIModel):
    """Machine-readable information describing an API error."""

    code: str = Field(
        min_length=1,
        max_length=100,
        description="Stable machine-readable error code.",
        examples=["SUPPLIER_NOT_FOUND"],
    )
    message: str = Field(
        min_length=1,
        description="Human-readable explanation of the error.",
        examples=["The requested supplier does not exist."],
    )
    field: str | None = Field(
        default=None,
        description="Request field associated with the error, when applicable.",
        examples=["supplier_id"],
    )


class ErrorResponse(APIModel):
    """Standard error envelope returned by the BritMart API."""

    request_id: str = Field(
        min_length=1,
        description="Identifier used to trace the request through application logs.",
        examples=["d02cf219-8d89-4c05-93df-593737120599"],
    )
    timestamp: datetime = Field(
        description="UTC timestamp at which the error response was produced."
    )
    status_code: int = Field(
        ge=400,
        le=599,
        description="HTTP status code associated with the error.",
        examples=[404],
    )
    error: ErrorDetail


class MessageResponse(APIModel):
    """Standard response for a successfully completed operation."""

    message: str = Field(
        min_length=1,
        description="Human-readable operation result.",
        examples=["Operation completed successfully."],
    )
    request_id: str | None = Field(
        default=None,
        description="Request identifier used for tracing.",
    )
    timestamp: datetime


class HealthResponse(APIModel):
    """Response returned by the application liveness endpoint."""

    status: str = Field(
        description="Current application health status.",
        examples=["healthy"],
    )
    service: str = Field(
        description="Application service name.",
        examples=["BritMart Supplier and Procurement API"],
    )
    environment: str = Field(
        description="Runtime environment.",
        examples=["development"],
    )
    version: str = Field(
        description="Application version.",
        examples=["1.0.0"],
    )
    timestamp: datetime


class ReadinessResponse(HealthResponse):
    """Response returned by the application readiness endpoint."""

    database_status: str = Field(
        description="Current database connectivity status.",
        examples=["available"],
    )


class IncrementalQueryParameters(APIModel):
    """Reusable extraction parameters for Microsoft Fabric ingestion."""

    updated_since: datetime | None = Field(
        default=None,
        description=(
            "Return records updated at or after this UTC timestamp. "
            "The API orders incremental results by updated_at and primary key."
        ),
        examples=["2026-08-01T00:00:00Z"],
    )
    updated_before: datetime | None = Field(
        default=None,
        description=(
            "Optional exclusive upper boundary for a controlled extraction window."
        ),
        examples=["2026-08-02T00:00:00Z"],
    )
    page: int = Field(
        default=1,
        ge=1,
        description="Page number to return.",
    )
    page_size: int = Field(
        default=100,
        ge=1,
        le=500,
        description="Number of records to return per page.",
    )