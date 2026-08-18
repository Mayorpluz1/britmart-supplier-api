"""Authentication dependencies for the BritMart API."""

from __future__ import annotations

import secrets
from typing import Annotated

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import APIKeyHeader

from app.core.config import settings


api_key_header = APIKeyHeader(
    name=settings.api_key_header_name,
    scheme_name="BritMartAPIKey",
    description=(
        "API key required to access protected BritMart supplier and "
        "procurement endpoints."
    ),
    auto_error=False,
)


def verify_api_key(
    supplied_api_key: Annotated[
        str | None,
        Security(api_key_header),
    ],
) -> str:
    """
    Validate the API key supplied in the configured request header.

    A constant-time comparison is used to reduce timing-attack exposure.
    """

    if supplied_api_key is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "API_KEY_MISSING",
                "message": (
                    f"The {settings.api_key_header_name} header is required."
                ),
            },
        )

    configured_api_key = settings.api_key.get_secret_value()

    if not secrets.compare_digest(
        supplied_api_key.encode("utf-8"),
        configured_api_key.encode("utf-8"),
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "API_KEY_INVALID",
                "message": "The supplied API key is invalid.",
            },
        )

    return supplied_api_key


RequireAPIKey = Annotated[str, Depends(verify_api_key)]