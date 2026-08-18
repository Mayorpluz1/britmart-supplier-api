"""FastAPI application entry point for BritMart."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.responses import RedirectResponse

from app.api.health import router as health_router
from app.api.v1.router import api_v1_router
from app.core.config import settings
from app.core.exceptions import (
    register_exception_handlers,
)
from app.core.logging import (
    StructuredRequestLoggingMiddleware,
    configure_logging,
)
from app.core.middleware import (
    RequestContextMiddleware,
)
from app.db.session import check_database_connection


@asynccontextmanager
async def lifespan(
    application: FastAPI,
) -> AsyncIterator[None]:
    """Manage application startup and shutdown."""

    if not check_database_connection():
        raise RuntimeError(
            "BritMart API startup failed: "
            "operational database unavailable."
        )

    application.state.database_available = True

    yield

    application.state.database_available = False


# Configure logging before application startup.
configure_logging()


app = FastAPI(
    title=settings.app_name,
    summary=(
        "BritMart supplier and procurement "
        "operational system"
    ),
    description=settings.app_description,
    version=settings.app_version,
    docs_url=settings.docs_url,
    redoc_url=settings.redoc_url,
    openapi_url=settings.openapi_url,
    lifespan=lifespan,
    contact={
        "name": (
            "BritMart Data Platform Engineering"
        ),
    },
    license_info={
        "name": "Portfolio demonstration project",
    },
)


register_exception_handlers(app)


# RequestContextMiddleware creates and preserves:
# - X-Request-ID
# - X-Response-Time-Ms
app.add_middleware(RequestContextMiddleware)


# This middleware is registered afterwards so it wraps
# RequestContextMiddleware and captures its response headers.
app.add_middleware(
    StructuredRequestLoggingMiddleware
)


app.include_router(health_router)

app.include_router(
    api_v1_router,
    prefix=settings.api_prefix,
)


@app.get(
    "/",
    include_in_schema=False,
    response_class=RedirectResponse,
)
def documentation_redirect() -> RedirectResponse:
    """Redirect the root to Swagger documentation."""

    return RedirectResponse(
        url=settings.docs_url or "/docs",
        status_code=307,
    )