"""Tests for structured API request logging."""

from __future__ import annotations

import logging

from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app


client = TestClient(app)


def authenticated_headers() -> dict[str, str]:
    """Return valid authentication headers."""

    return {
        settings.api_key_header_name: (
            settings.api_key.get_secret_value()
        ),
        "X-Request-ID": "logging-test-001",
    }


def test_successful_request_is_logged(
    caplog,
) -> None:
    """Confirm successful API requests are logged."""

    with caplog.at_level(
        logging.INFO,
        logger="britmart.api.requests",
    ):
        response = client.get(
            "/api/v1/shipments?page=1&page_size=1",
            headers=authenticated_headers(),
        )

    assert response.status_code == 200

    matching_records = [
        record
        for record in caplog.records
        if getattr(
            record,
            "event",
            None,
        )
        == "http_request_completed"
    ]

    assert matching_records

    record = matching_records[-1]

    assert record.request_id == "logging-test-001"
    assert record.http_method == "GET"
    assert record.endpoint == "/api/v1/shipments"
    assert record.response_status == 200
    assert record.response_time_ms >= 0
    assert record.environment == settings.environment


def test_failure_response_is_logged(
    caplog,
) -> None:
    """Confirm simulated failures are logged."""

    headers = authenticated_headers()
    headers["X-Simulate-Status"] = "503"

    with caplog.at_level(
        logging.ERROR,
        logger="britmart.api.requests",
    ):
        response = client.get(
            "/api/v1/shipments?page=1&page_size=1",
            headers=headers,
        )

    assert response.status_code == 503

    matching_records = [
        record
        for record in caplog.records
        if getattr(
            record,
            "request_id",
            None,
        )
        == "logging-test-001"
        and getattr(
            record,
            "response_status",
            None,
        )
        == 503
    ]

    assert matching_records


def test_unauthorised_request_is_logged(
    caplog,
) -> None:
    """Confirm authentication failures are logged."""

    with caplog.at_level(
        logging.WARNING,
        logger="britmart.api.requests",
    ):
        response = client.get(
            "/api/v1/shipments?page=1&page_size=1",
            headers={
                "X-Request-ID": "logging-auth-001"
            },
        )

    assert response.status_code == 401

    matching_records = [
        record
        for record in caplog.records
        if getattr(
            record,
            "request_id",
            None,
        )
        == "logging-auth-001"
        and getattr(
            record,
            "response_status",
            None,
        )
        == 401
    ]

    assert matching_records