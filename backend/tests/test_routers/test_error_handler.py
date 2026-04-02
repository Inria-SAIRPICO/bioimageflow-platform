"""Tests for custom exception handlers."""

import pytest

import httpx


pytestmark = pytest.mark.anyio


async def test_http_404_returns_error_format(client: httpx.AsyncClient) -> None:
    resp = await client.get("/api/v1/nonexistent")
    assert resp.status_code == 404
    data = resp.json()
    assert "error" in data
    assert "detail" in data
    assert data["error"] == "not_found"


async def test_http_exception_returns_error_format(client: httpx.AsyncClient) -> None:
    """A 404 from a missing route should have the standardized shape."""
    resp = await client.get("/totally/missing/route")
    assert resp.status_code == 404
    data = resp.json()
    assert set(data.keys()) == {"error", "detail", "field"}


async def test_validation_error_returns_422(client: httpx.AsyncClient) -> None:
    """Trigger a validation error by sending invalid data to the health endpoint via query params.

    We'll add a test route in conftest for this purpose.
    """
    # POST to health with invalid content-type to trigger validation
    # Instead, we rely on a dedicated test route added for validation testing.
    resp = await client.get("/api/v1/test-validation", params={"value": "not_an_int"})
    assert resp.status_code == 422
    data = resp.json()
    assert "error" in data
    assert data["error"] == "validation_error"
    assert "detail" in data
