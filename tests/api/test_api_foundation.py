"""Integration tests for the BritMart FastAPI application foundation."""

from __future__ import annotations

from uuid import UUID

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.core.config import settings
from app.dependencies.security import verify_api_key
from app.main import app
from app.schemas.common import IncrementalQueryParameters


@pytest.fixture(scope="module")
def client() -> TestClient:
    """Create an API client with application lifespan processing enabled."""

    with TestClient(app) as test_client:
        yield test_client


def test_application_metadata_is_configured() -> None:
    """Confirm the application exposes the expected identity."""

    assert app.title == "BritMart Supplier and Procurement API"
    assert app.version == "1.0.0"
    assert app.docs_url == "/docs"
    assert app.redoc_url == "/redoc"
    assert app.openapi_url == "/openapi.json"


def test_root_redirects_to_swagger_documentation(
    client: TestClient,
) -> None:
    """Confirm the application root redirects to Swagger."""

    response = client.get("/", follow_redirects=False)

    assert response.status_code == 307
    assert response.headers["location"] == "/docs"


def test_liveness_endpoint_returns_healthy(
    client: TestClient,
) -> None:
    """Confirm the API process reports healthy."""

    response = client.get("/health/live")

    assert response.status_code == 200

    body = response.json()

    assert body["status"] == "healthy"
    assert body["service"] == settings.app_name
    assert body["environment"] == settings.environment
    assert body["version"] == "1.0.0"
    assert body["timestamp"].endswith("Z")


def test_readiness_endpoint_confirms_database_availability(
    client: TestClient,
) -> None:
    """Confirm the API is ready to serve database-backed requests."""

    response = client.get("/health/ready")

    assert response.status_code == 200

    body = response.json()

    assert body["status"] == "healthy"
    assert body["database_status"] == "available"


def test_request_id_is_generated_when_not_supplied(
    client: TestClient,
) -> None:
    """Confirm every response receives a generated UUID request ID."""

    response = client.get("/health/live")

    request_id = response.headers["X-Request-ID"]

    assert UUID(request_id)
    assert response.json()["status"] == "healthy"


def test_valid_caller_request_id_is_preserved(
    client: TestClient,
) -> None:
    """Confirm upstream systems can provide their own correlation ID."""

    supplied_request_id = "fabric-pipeline-run-0001"

    response = client.get(
        "/health/live",
        headers={"X-Request-ID": supplied_request_id},
    )

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == supplied_request_id


def test_response_time_header_is_numeric(
    client: TestClient,
) -> None:
    """Confirm every response includes non-negative processing time."""

    response = client.get("/health/live")

    response_time_ms = float(response.headers["X-Response-Time-Ms"])

    assert response_time_ms >= 0


def test_unknown_endpoint_uses_standard_error_contract(
    client: TestClient,
) -> None:
    """Confirm router-generated 404 errors use the BritMart envelope."""

    response = client.get(
        "/unknown-resource",
        headers={"X-Request-ID": "not-found-test-001"},
    )

    assert response.status_code == 404

    body = response.json()

    assert body["request_id"] == "not-found-test-001"
    assert body["status_code"] == 404
    assert body["error"]["code"] == "RESOURCE_NOT_FOUND"
    assert body["error"]["message"] == "Not Found"
    assert body["error"]["field"] is None


def test_missing_api_key_is_rejected() -> None:
    """Confirm protected endpoints reject missing credentials."""

    with pytest.raises(HTTPException) as exception_information:
        verify_api_key(None)

    exception = exception_information.value

    assert exception.status_code == 401
    assert exception.detail["code"] == "API_KEY_MISSING"


def test_invalid_api_key_is_rejected() -> None:
    """Confirm protected endpoints reject incorrect credentials."""

    with pytest.raises(HTTPException) as exception_information:
        verify_api_key("incorrect-api-key")

    exception = exception_information.value

    assert exception.status_code == 401
    assert exception.detail["code"] == "API_KEY_INVALID"


def test_configured_api_key_is_accepted() -> None:
    """Confirm the configured API key passes authentication."""

    configured_api_key = settings.api_key.get_secret_value()

    result = verify_api_key(configured_api_key)

    assert result == configured_api_key


def test_incremental_parameters_apply_safe_defaults() -> None:
    """Confirm Fabric extraction parameters use controlled defaults."""

    parameters = IncrementalQueryParameters()

    assert parameters.updated_since is None
    assert parameters.updated_before is None
    assert parameters.page == 1
    assert parameters.page_size == 100


@pytest.mark.parametrize(
    ("page", "page_size"),
    [
        (0, 100),
        (1, 0),
        (1, 501),
    ],
)
def test_invalid_pagination_parameters_are_rejected(
    page: int,
    page_size: int,
) -> None:
    """Confirm pagination cannot exceed the API contract."""

    with pytest.raises(ValidationError):
        IncrementalQueryParameters(
            page=page,
            page_size=page_size,
        )


def test_openapi_contract_contains_health_endpoints(
    client: TestClient,
) -> None:
    """Confirm operational endpoints are published in OpenAPI."""

    response = client.get("/openapi.json")

    assert response.status_code == 200

    paths = response.json()["paths"]

    assert "/health/live" in paths
    assert "/health/ready" in paths