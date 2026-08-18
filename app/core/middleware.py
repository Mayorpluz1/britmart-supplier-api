"""Request tracing, timing and operational logging middleware."""

from __future__ import annotations

import logging
import time
from contextvars import ContextVar, Token
from typing import Final
from uuid import uuid4

from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send


LOGGER: Final = logging.getLogger("britmart.api")

REQUEST_ID_HEADER: Final = "X-Request-ID"
RESPONSE_TIME_HEADER: Final = "X-Response-Time-Ms"
MAX_REQUEST_ID_LENGTH: Final = 128

_request_id_context: ContextVar[str | None] = ContextVar(
    "request_id",
    default=None,
)


def get_request_id() -> str | None:
    """Return the request identifier for the current execution context."""

    return _request_id_context.get()


def _is_valid_request_id(value: str) -> bool:
    """Confirm that a caller-supplied request identifier is safe to log."""

    return (
        bool(value)
        and len(value) <= MAX_REQUEST_ID_LENGTH
        and value.isprintable()
        and "\r" not in value
        and "\n" not in value
    )


def _resolve_request_id(scope: Scope) -> str:
    """Use a valid incoming request ID or generate a new UUID."""

    headers = MutableHeaders(scope=scope)
    supplied_request_id = headers.get(REQUEST_ID_HEADER)

    if (
        supplied_request_id is not None
        and _is_valid_request_id(supplied_request_id)
    ):
        return supplied_request_id

    return str(uuid4())


def _client_identity(scope: Scope) -> str:
    """Return the network identity of the calling client."""

    client = scope.get("client")

    if client is None:
        return "unknown"

    host, port = client
    return f"{host}:{port}"


class RequestContextMiddleware:
    """
    Add request tracing, timing and structured operational logging.

    The middleware is implemented directly against ASGI so it remains
    lightweight and works correctly with streaming responses.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(
        self,
        scope: Scope,
        receive: Receive,
        send: Send,
    ) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = _resolve_request_id(scope)
        context_token: Token[str | None] = _request_id_context.set(request_id)

        method = scope.get("method", "UNKNOWN")
        path = scope.get("path", "")
        client = _client_identity(scope)
        started_at = time.perf_counter()
        response_status = 500

        async def send_with_context(message: Message) -> None:
            nonlocal response_status

            if message["type"] == "http.response.start":
                response_status = int(message["status"])
                elapsed_ms = round(
                    (time.perf_counter() - started_at) * 1000,
                    3,
                )

                response_headers = MutableHeaders(scope=message)
                response_headers[REQUEST_ID_HEADER] = request_id
                response_headers[RESPONSE_TIME_HEADER] = f"{elapsed_ms:.3f}"

            await send(message)

        try:
            await self.app(scope, receive, send_with_context)
        except Exception:
            elapsed_ms = round(
                (time.perf_counter() - started_at) * 1000,
                3,
            )

            LOGGER.exception(
                "request_failed request_id=%s method=%s path=%s "
                "status=%s response_time_ms=%.3f client=%s",
                request_id,
                method,
                path,
                response_status,
                elapsed_ms,
                client,
            )
            raise
        else:
            elapsed_ms = round(
                (time.perf_counter() - started_at) * 1000,
                3,
            )

            LOGGER.info(
                "request_completed request_id=%s method=%s path=%s "
                "status=%s response_time_ms=%.3f client=%s",
                request_id,
                method,
                path,
                response_status,
                elapsed_ms,
                client,
            )
        finally:
            _request_id_context.reset(context_token)