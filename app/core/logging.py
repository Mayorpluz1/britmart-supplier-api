"""Structured logging for the BritMart API."""

from __future__ import annotations

import json
import logging
import sys
from datetime import UTC, datetime
from time import perf_counter
from typing import Any

from app.core.config import settings


REQUEST_ID_HEADER = b"x-request-id"


class JSONLogFormatter(logging.Formatter):
    """Format log records as JSON."""

    excluded_attributes = {
        "name",
        "msg",
        "args",
        "levelname",
        "levelno",
        "pathname",
        "filename",
        "module",
        "exc_info",
        "exc_text",
        "stack_info",
        "lineno",
        "funcName",
        "created",
        "msecs",
        "relativeCreated",
        "thread",
        "threadName",
        "processName",
        "process",
        "taskName",
    }

    def format(
        self,
        record: logging.LogRecord,
    ) -> str:
        """Convert one log record to JSON."""

        payload: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        for key, value in record.__dict__.items():
            if (
                key not in self.excluded_attributes
                and not key.startswith("_")
            ):
                payload[key] = value

        if record.exc_info:
            payload["exception"] = (
                self.formatException(record.exc_info)
            )

        return json.dumps(
            payload,
            default=str,
            ensure_ascii=False,
        )


def configure_logging() -> None:
    """Configure root application logging."""

    root_logger = logging.getLogger()
    root_logger.setLevel(settings.log_level)

    handler = logging.StreamHandler(sys.stdout)

    if settings.log_json:
        handler.setFormatter(JSONLogFormatter())
    else:
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s %(levelname)s "
                "%(name)s %(message)s"
            )
        )

    root_logger.handlers.clear()
    root_logger.addHandler(handler)

    logging.getLogger(
        "britmart.api.requests"
    ).setLevel(settings.log_level)

    logging.getLogger("uvicorn.access").disabled = True


class StructuredRequestLoggingMiddleware:
    """Log every HTTP request with operational context."""

    def __init__(self, app) -> None:
        self.app = app
        self.logger = logging.getLogger(
            "britmart.api.requests"
        )

    async def __call__(
        self,
        scope,
        receive,
        send,
    ) -> None:
        """Process and log one ASGI request."""

        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        started_at = perf_counter()
        response_status = 500
        response_request_id: str | None = None
        error_message: str | None = None

        request_headers = {
            key.lower(): value
            for key, value in scope.get(
                "headers",
                [],
            )
        }

        supplied_request_id = request_headers.get(
            REQUEST_ID_HEADER
        )

        if supplied_request_id is not None:
            response_request_id = (
                supplied_request_id.decode(
                    "utf-8",
                    errors="replace",
                )
            )

        user_agent = request_headers.get(
            b"user-agent",
            b"",
        ).decode(
            "utf-8",
            errors="replace",
        )

        client = scope.get("client")
        client_address = (
            client[0]
            if client is not None
            else "unknown"
        )

        async def send_with_logging(message) -> None:
            nonlocal response_status
            nonlocal response_request_id

            if message["type"] == "http.response.start":
                response_status = message["status"]

                response_headers = {
                    key.lower(): value
                    for key, value in message.get(
                        "headers",
                        [],
                    )
                }

                returned_request_id = (
                    response_headers.get(
                        REQUEST_ID_HEADER
                    )
                )

                if returned_request_id is not None:
                    response_request_id = (
                        returned_request_id.decode(
                            "utf-8",
                            errors="replace",
                        )
                    )

            await send(message)

        try:
            await self.app(
                scope,
                receive,
                send_with_logging,
            )
        except Exception as exc:
            error_message = str(exc)
            raise
        finally:
            response_time_ms = round(
                (
                    perf_counter()
                    - started_at
                )
                * 1000,
                3,
            )

            log_context = {
                "event": "http_request_completed",
                "request_id": response_request_id,
                "http_method": scope.get(
                    "method",
                    "UNKNOWN",
                ),
                "endpoint": scope.get("path", ""),
                "query_string": scope.get(
                    "query_string",
                    b"",
                ).decode(
                    "utf-8",
                    errors="replace",
                ),
                "response_status": response_status,
                "response_time_ms": response_time_ms,
                "client": client_address,
                "user_agent": user_agent,
                "error_message": error_message,
                "environment": settings.environment,
                "service": settings.app_name,
            }

            if response_status >= 500:
                self.logger.error(
                    "HTTP request completed",
                    extra=log_context,
                )
            elif response_status >= 400:
                self.logger.warning(
                    "HTTP request completed",
                    extra=log_context,
                )
            else:
                self.logger.info(
                    "HTTP request completed",
                    extra=log_context,
                )