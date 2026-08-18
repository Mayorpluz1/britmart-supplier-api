"""Integration tests for version 1 supplier API endpoints."""

from __future__ import annotations

from collections.abc import Generator
from datetime import datetime
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app


@pytest.fixture(scope="module")
def client() -> Generator[TestClient, None, None]:
    """Create an API client with lifespan processing enabled."""

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(scope="module")
def authenticated_headers() -> dict[str, str]:
    """Return valid API authentication and tracing headers."""

    return {
        settings.api_key_header_name: (
            settings.api_key.get_secret_value()
        ),
        "X-Request-ID": "supplier-api-tests",
    }


def get_supplier_page(
    client: TestClient,
    authenticated_headers: dict[str, str],
    *,
    page: int = 1,
    page_size: int = 10,
) -> dict:
    """Return a successful supplier collection response."""

    response = client.get(
        "/api/v1/suppliers",
        params={
            "page": page,
            "page_size": page_size,
        },
        headers=authenticated_headers,
    )

    assert response.status_code == 200

    return response.json()


def test_supplier_endpoint_requires_api_key(
    client: TestClient,
) -> None:
    """Confirm anonymous supplier extraction is rejected."""

    response = client.get("/api/v1/suppliers")

    assert response.status_code == 401

    body = response.json()

    assert body["status_code"] == 401
    assert body["error"]["code"] == "API_KEY_MISSING"


def test_supplier_endpoint_rejects_invalid_api_key(
    client: TestClient,
) -> None:
    """Confirm incorrect credentials are rejected."""

    response = client.get(
        "/api/v1/suppliers",
        headers={settings.api_key_header_name: "incorrect-key"},
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "API_KEY_INVALID"


def test_supplier_collection_returns_expected_total(
    client: TestClient,
    authenticated_headers: dict[str, str],
) -> None:
    """Confirm the API exposes all loaded suppliers."""

    body = get_supplier_page(
        client,
        authenticated_headers,
        page=1,
        page_size=10,
    )

    assert len(body["items"]) == 10
    assert body["pagination"]["page"] == 1
    assert body["pagination"]["page_size"] == 10
    assert body["pagination"]["total_records"] == 50
    assert body["pagination"]["total_pages"] == 5
    assert body["pagination"]["has_next"] is True
    assert body["pagination"]["has_previous"] is False


def test_supplier_final_page_metadata_is_correct(
    client: TestClient,
    authenticated_headers: dict[str, str],
) -> None:
    """Confirm pagination metadata is correct on the final page."""

    body = get_supplier_page(
        client,
        authenticated_headers,
        page=5,
        page_size=10,
    )

    assert len(body["items"]) == 10
    assert body["pagination"]["has_next"] is False
    assert body["pagination"]["has_previous"] is True


def test_supplier_summary_contract_is_complete(
    client: TestClient,
    authenticated_headers: dict[str, str],
) -> None:
    """Confirm collection items expose the controlled summary contract."""

    body = get_supplier_page(
        client,
        authenticated_headers,
        page=1,
        page_size=1,
    )

    supplier = body["items"][0]

    assert set(supplier) == {
        "supplier_id",
        "supplier_code",
        "supplier_name",
        "supplier_type",
        "country_code",
        "default_currency_code",
        "risk_rating",
        "supplier_status",
        "active_flag",
        "updated_at",
        "version_number",
    }

    assert UUID(supplier["supplier_id"])
    assert supplier["supplier_code"].startswith("SUP-")
    assert supplier["version_number"] >= 1


def test_supplier_collection_has_stable_incremental_ordering(
    client: TestClient,
    authenticated_headers: dict[str, str],
) -> None:
    """Confirm results are ordered by updated_at and supplier_id."""

    body = get_supplier_page(
        client,
        authenticated_headers,
        page=1,
        page_size=50,
    )

    ordering_keys = [
        (
            item["updated_at"],
            item["supplier_id"],
        )
        for item in body["items"]
    ]

    assert ordering_keys == sorted(ordering_keys)


def test_supplier_pages_do_not_overlap(
    client: TestClient,
    authenticated_headers: dict[str, str],
) -> None:
    """Confirm deterministic pagination does not duplicate suppliers."""

    first_page = get_supplier_page(
        client,
        authenticated_headers,
        page=1,
        page_size=10,
    )
    second_page = get_supplier_page(
        client,
        authenticated_headers,
        page=2,
        page_size=10,
    )

    first_ids = {
        item["supplier_id"]
        for item in first_page["items"]
    }
    second_ids = {
        item["supplier_id"]
        for item in second_page["items"]
    }

    assert first_ids.isdisjoint(second_ids)


def test_supplier_can_be_retrieved_by_id(
    client: TestClient,
    authenticated_headers: dict[str, str],
) -> None:
    """Confirm the detail endpoint returns the selected supplier."""

    page = get_supplier_page(
        client,
        authenticated_headers,
        page=1,
        page_size=1,
    )
    supplier_id = page["items"][0]["supplier_id"]

    response = client.get(
        f"/api/v1/suppliers/{supplier_id}",
        headers=authenticated_headers,
    )

    assert response.status_code == 200

    supplier = response.json()

    assert supplier["supplier_id"] == supplier_id
    assert "category_codes" in supplier
    assert "target_otif_rate" in supplier
    assert "target_quality_acceptance_rate" in supplier
    assert "contact_email" in supplier


def test_supplier_can_be_retrieved_by_code_case_insensitively(
    client: TestClient,
    authenticated_headers: dict[str, str],
) -> None:
    """Confirm operational supplier-code lookup is normalised."""

    page = get_supplier_page(
        client,
        authenticated_headers,
        page=1,
        page_size=1,
    )
    supplier_code = page["items"][0]["supplier_code"]

    response = client.get(
        f"/api/v1/suppliers/by-code/{supplier_code.lower()}",
        headers=authenticated_headers,
    )

    assert response.status_code == 200
    assert response.json()["supplier_code"] == supplier_code


def test_unknown_supplier_id_returns_controlled_404(
    client: TestClient,
    authenticated_headers: dict[str, str],
) -> None:
    """Confirm an unknown valid UUID returns a traceable 404."""

    unknown_supplier_id = (
        "00000000-0000-0000-0000-000000000000"
    )

    response = client.get(
        f"/api/v1/suppliers/{unknown_supplier_id}",
        headers=authenticated_headers,
    )

    assert response.status_code == 404

    body = response.json()

    assert body["error"]["code"] == "SUPPLIER_NOT_FOUND"
    assert body["error"]["field"] == "supplier_id"


def test_invalid_supplier_id_returns_controlled_422(
    client: TestClient,
    authenticated_headers: dict[str, str],
) -> None:
    """Confirm malformed supplier identifiers fail validation."""

    response = client.get(
        "/api/v1/suppliers/not-a-valid-uuid",
        headers=authenticated_headers,
    )

    assert response.status_code == 422

    body = response.json()

    assert body["error"]["code"] == "REQUEST_VALIDATION_ERROR"
    assert body["error"]["field"] == "supplier_id"


def test_supplier_status_filter_is_applied(
    client: TestClient,
    authenticated_headers: dict[str, str],
) -> None:
    """Confirm supplier status filtering is enforced by the query."""

    unfiltered = get_supplier_page(
        client,
        authenticated_headers,
        page=1,
        page_size=1,
    )
    selected_status = unfiltered["items"][0]["supplier_status"]

    response = client.get(
        "/api/v1/suppliers",
        params={
            "supplier_status": selected_status,
            "page": 1,
            "page_size": 50,
        },
        headers=authenticated_headers,
    )

    assert response.status_code == 200

    items = response.json()["items"]

    assert items
    assert all(
        item["supplier_status"] == selected_status
        for item in items
    )


def test_country_filter_is_case_normalised(
    client: TestClient,
    authenticated_headers: dict[str, str],
) -> None:
    """Confirm lowercase country filters match uppercase stored codes."""

    unfiltered = get_supplier_page(
        client,
        authenticated_headers,
        page=1,
        page_size=1,
    )
    country_code = unfiltered["items"][0]["country_code"]

    response = client.get(
        "/api/v1/suppliers",
        params={
            "country_code": country_code.lower(),
            "page": 1,
            "page_size": 50,
        },
        headers=authenticated_headers,
    )

    assert response.status_code == 200

    items = response.json()["items"]

    assert items
    assert all(
        item["country_code"] == country_code
        for item in items
    )


def test_incremental_updated_since_filter_is_inclusive(
    client: TestClient,
    authenticated_headers: dict[str, str],
) -> None:
    """Confirm Fabric can extract using an inclusive lower watermark."""

    unfiltered = get_supplier_page(
        client,
        authenticated_headers,
        page=1,
        page_size=1,
    )
    watermark = unfiltered["items"][0]["updated_at"]

    response = client.get(
        "/api/v1/suppliers",
        params={
            "updated_since": watermark,
            "page": 1,
            "page_size": 50,
        },
        headers=authenticated_headers,
    )

    assert response.status_code == 200

    items = response.json()["items"]

    assert items
    assert all(
        datetime.fromisoformat(
            item["updated_at"].replace("Z", "+00:00")
        )
        >= datetime.fromisoformat(
            watermark.replace("Z", "+00:00")
        )
        for item in items
    )


def test_invalid_incremental_window_is_rejected(
    client: TestClient,
    authenticated_headers: dict[str, str],
) -> None:
    """Confirm an invalid extraction window returns HTTP 422."""

    boundary = "2026-08-17T00:00:00Z"

    response = client.get(
        "/api/v1/suppliers",
        params={
            "updated_since": boundary,
            "updated_before": boundary,
        },
        headers=authenticated_headers,
    )

    assert response.status_code == 422
    assert (
        response.json()["error"]["code"]
        == "REQUEST_VALIDATION_ERROR"
    )


def test_invalid_page_size_is_rejected(
    client: TestClient,
    authenticated_headers: dict[str, str],
) -> None:
    """Confirm the collection endpoint enforces its page-size limit."""

    response = client.get(
        "/api/v1/suppliers",
        params={
            "page": 1,
            "page_size": 501,
        },
        headers=authenticated_headers,
    )

    assert response.status_code == 422


def test_supplier_endpoints_are_published_in_openapi(
    client: TestClient,
) -> None:
    """Confirm supplier contracts are visible to API consumers."""

    response = client.get("/openapi.json")

    assert response.status_code == 200

    paths = response.json()["paths"]

    assert "/api/v1/suppliers" in paths
    assert "/api/v1/suppliers/{supplier_id}" in paths
    assert "/api/v1/suppliers/by-code/{supplier_code}" in paths