"""Controlled API failure simulation for development and testing."""

from __future__ import annotations

import asyncio
from typing import Annotated

from fastapi import Header, HTTPException, status

from app.core.config import settings
from app.dependencies.security import RequireAPIKey


SIMULATED_STATUS_HEADER = "X-Simulate-Status"
SIMULATED_DELAY_HEADER = "X-Simulate-Delay-Ms"

ALLOWED_SIMULATED_STATUSES = {500, 503}
ALLOWED_ENVIRONMENTS = {
    "development",
    "testing",
    "test",
}


async def simulate_controlled_failure(
    _api_key: RequireAPIKey,
    simulated_status: Annotated[
        int | None,
        Header(alias=SIMULATED_STATUS_HEADER),
    ] = None,
    simulated_delay_ms: Annotated[
        int | None,
        Header(alias=SIMULATED_DELAY_HEADER),
    ] = None,
) -> None:
    """Apply an authorised and controlled delay or HTTP failure."""

    simulation_requested = (
        simulated_status is not None
        or simulated_delay_ms is not None
    )

    if not simulation_requested:
        return

    current_environment = settings.environment.strip().lower()

    if (
        not settings.failure_simulation_enabled
        or current_environment not in ALLOWED_ENVIRONMENTS
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "FAILURE_SIMULATION_DISABLED",
                "message": (
                    "Controlled failure simulation is disabled "
                    "for this environment."
                ),
                "field": None,
            },
        )

    if simulated_delay_ms is not None:
        if simulated_delay_ms < 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": "INVALID_SIMULATED_DELAY",
                    "message": (
                        "X-Simulate-Delay-Ms cannot be negative."
                    ),
                    "field": SIMULATED_DELAY_HEADER,
                },
            )

        if (
            simulated_delay_ms
            > settings.failure_simulation_max_delay_ms
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": "SIMULATED_DELAY_LIMIT_EXCEEDED",
                    "message": (
                        "The requested simulated delay exceeds "
                        f"the configured limit of "
                        f"{settings.failure_simulation_max_delay_ms} "
                        "milliseconds."
                    ),
                    "field": SIMULATED_DELAY_HEADER,
                },
            )

        await asyncio.sleep(simulated_delay_ms / 1000)

    if simulated_status is not None:
        if simulated_status not in ALLOWED_SIMULATED_STATUSES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": "INVALID_SIMULATED_STATUS",
                    "message": (
                        "X-Simulate-Status must be either "
                        "500 or 503."
                    ),
                    "field": SIMULATED_STATUS_HEADER,
                },
            )

        error_code = (
            "SIMULATED_INTERNAL_SERVER_ERROR"
            if simulated_status == 500
            else "SIMULATED_SERVICE_UNAVAILABLE"
        )

        message = (
            "A controlled internal server error was generated."
            if simulated_status == 500
            else (
                "A controlled service-unavailable response "
                "was generated."
            )
        )

        raise HTTPException(
            status_code=simulated_status,
            detail={
                "code": error_code,
                "message": message,
                "field": SIMULATED_STATUS_HEADER,
            },
        )
