"""Consistent production-style exception handling for the BritMart API."""

from __future__ import annotations

import logging
from http import HTTPStatus
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, Request, status
from starlette.exceptions import HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from app.core.middleware import get_request_id
from app.db.base import utc_now
from app.schemas.common import ErrorDetail, ErrorResponse


LOGGER = logging.getLogger("britmart.api")


DEFAULT_ERROR_CODES: dict[int, str] = {
    status.HTTP_400_BAD_REQUEST: "BAD_REQUEST",
    status.HTTP_401_UNAUTHORIZED: "UNAUTHORISED",
    status.HTTP_403_FORBIDDEN: "FORBIDDEN",
    status.HTTP_404_NOT_FOUND: "RESOURCE_NOT_FOUND",
    status.HTTP_405_METHOD_NOT_ALLOWED: "METHOD_NOT_ALLOWED",
    status.HTTP_409_CONFLICT: "RESOURCE_CONFLICT",
    status.HTTP_422_UNPROCESSABLE_CONTENT: "VALIDATION_ERROR",
    status.HTTP_429_TOO_MANY_REQUESTS: "RATE_LIMIT_EXCEEDED",
    status.HTTP_500_INTERNAL_SERVER_ERROR: "INTERNAL_SERVER_ERROR",
    status.HTTP_503_SERVICE_UNAVAILABLE: "SERVICE_UNAVAILABLE",
}


def _request_id(request: Request) -> str:
    """Return the active request ID with safe fallbacks."""

    return (
        get_request_id()
        or request.headers.get("X-Request-ID")
        or str(uuid4())
    )


def _default_message(status_code: int) -> str:
    """Return the standard HTTP explanation for a status code."""

    try:
        return HTTPStatus(status_code).phrase
    except ValueError:
        return "The request could not be completed."


def _error_response(
    *,
    request: Request,
    status_code: int,
    code: str,
    message: str,
    field: str | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    """Build the standard BritMart API error envelope."""

    request_id = _request_id(request)

    response = ErrorResponse(
        request_id=request_id,
        timestamp=utc_now(),
        status_code=status_code,
        error=ErrorDetail(
            code=code,
            message=message,
            field=field,
        ),
    )

    response_headers = dict(headers or {})
    response_headers.setdefault("X-Request-ID", request_id)

    return JSONResponse(
        status_code=status_code,
        content=response.model_dump(mode="json"),
        headers=response_headers,
    )


def _normalise_http_detail(
    exception: HTTPException,
) -> tuple[str, str, str | None]:
    """Convert FastAPI HTTP exception details into the standard structure."""

    default_code = DEFAULT_ERROR_CODES.get(
        exception.status_code,
        f"HTTP_{exception.status_code}",
    )

    if isinstance(exception.detail, dict):
        code = str(exception.detail.get("code", default_code))
        message = str(
            exception.detail.get(
                "message",
                _default_message(exception.status_code),
            )
        )

        raw_field = exception.detail.get("field")
        field = str(raw_field) if raw_field is not None else None

        return code, message, field

    return (
        default_code,
        str(exception.detail or _default_message(exception.status_code)),
        None,
    )


async def http_exception_handler(
    request: Request,
    exception: HTTPException,
) -> JSONResponse:
    """Handle explicitly raised HTTP errors."""

    code, message, field = _normalise_http_detail(exception)

    return _error_response(
        request=request,
        status_code=exception.status_code,
        code=code,
        message=message,
        field=field,
        headers=exception.headers,
    )


async def validation_exception_handler(
    request: Request,
    exception: RequestValidationError,
) -> JSONResponse:
    """Handle invalid path, query, header and request-body values."""

    validation_errors: list[dict[str, Any]] = exception.errors()
    first_error = validation_errors[0] if validation_errors else {}

    location = first_error.get("loc", ())
    field = ".".join(
        str(part)
        for part in location
        if part not in {"body", "query", "path", "header"}
    ) or None

    message = str(
        first_error.get(
            "msg",
            "The request contains invalid data.",
        )
    )

    return _error_response(
        request=request,
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        code="REQUEST_VALIDATION_ERROR",
        message=message,
        field=field,
    )


async def database_exception_handler(
    request: Request,
    exception: SQLAlchemyError,
) -> JSONResponse:
    """Handle unexpected operational database failures."""

    LOGGER.exception(
        "database_error request_id=%s path=%s",
        _request_id(request),
        request.url.path,
        exc_info=exception,
    )

    return _error_response(
        request=request,
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        code="DATABASE_UNAVAILABLE",
        message=(
            "The operational database is temporarily unavailable. "
            "Retry the request later."
        ),
    )


async def unexpected_exception_handler(
    request: Request,
    exception: Exception,
) -> JSONResponse:
    """Handle unexpected errors without exposing internal implementation."""

    LOGGER.exception(
        "unexpected_error request_id=%s path=%s",
        _request_id(request),
        request.url.path,
        exc_info=exception,
    )

    return _error_response(
        request=request,
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        code="INTERNAL_SERVER_ERROR",
        message="An unexpected error occurred while processing the request.",
    )


def register_exception_handlers(application: FastAPI) -> None:
    """Register all BritMart exception handlers."""

    application.add_exception_handler(
        HTTPException,
        http_exception_handler,
    )
    application.add_exception_handler(
        RequestValidationError,
        validation_exception_handler,
    )
    application.add_exception_handler(
        SQLAlchemyError,
        database_exception_handler,
    )
    application.add_exception_handler(
        Exception,
        unexpected_exception_handler,
    )