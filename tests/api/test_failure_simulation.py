"""Tests for controlled API failure simulation."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app


client = TestClient(app)


@pytest.fixture(autouse=True)
def enable_failure_simulation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Enable controlled simulation during these tests."""

    monkeypatch.setattr(
        settings,
        "failure_simulation_enabled",
        True,
    )


def authenticated_headers(
    **additional_headers: str,
) -> dict[str, str]:
    """Return valid API authentication headers."""

    headers = {
        settings.api_key_header_name: (
            settings.api_key.get_secret_value()
        ),
        "X-Request-ID": "failure-test-001",
    }
    headers.update(additional_headers)
    return headers


def test_normal_request_is_not_affected() -> None:
    """Confirm ordinary requests continue successfully."""

    response = client.get(
        "/api/v1/shipments?page=1&page_size=1",
        headers=authenticated_headers(),
    )

    assert response.status_code == 200


def test_controlled_503_response() -> None:
    """Confirm a service-unavailable failure can be generated."""

    response = client.get(
        "/api/v1/shipments?page=1&page_size=1",
        headers=authenticated_headers(
            **{"X-Simulate-Status": "503"}
        ),
    )

    body = response.json()

    assert response.status_code == 503
    assert response.headers["X-Request-ID"] == (
        "failure-test-001"
    )
    assert body["error"]["code"] == (
        "SIMULATED_SERVICE_UNAVAILABLE"
    )


def test_controlled_500_response() -> None:
    """Confirm an internal-server failure can be generated."""

    response = client.get(
        "/api/v1/suppliers?page=1&page_size=1",
        headers=authenticated_headers(
            **{"X-Simulate-Status": "500"}
        ),
    )

    assert response.status_code == 500
    assert response.json()["error"]["code"] == (
        "SIMULATED_INTERNAL_SERVER_ERROR"
    )


def test_invalid_simulated_status_is_rejected() -> None:
    """Reject unsupported simulated status codes."""

    response = client.get(
        "/api/v1/shipments?page=1&page_size=1",
        headers=authenticated_headers(
            **{"X-Simulate-Status": "502"}
        ),
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == (
        "INVALID_SIMULATED_STATUS"
    )


def test_controlled_delay_is_applied() -> None:
    """Confirm an authorised response delay can be generated."""

    response = client.get(
        "/api/v1/shipments?page=1&page_size=1",
        headers=authenticated_headers(
            **{"X-Simulate-Delay-Ms": "50"}
        ),
    )

    response_time = float(
        response.headers["X-Response-Time-Ms"]
    )

    assert response.status_code == 200
    assert response_time >= 40


def test_delay_above_limit_is_rejected() -> None:
    """Reject delays above the configured safety limit."""

    excessive_delay = (
        settings.failure_simulation_max_delay_ms + 1
    )

    response = client.get(
        "/api/v1/shipments?page=1&page_size=1",
        headers=authenticated_headers(
            **{
                "X-Simulate-Delay-Ms": str(
                    excessive_delay
                )
            }
        ),
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == (
        "SIMULATED_DELAY_LIMIT_EXCEEDED"
    )