"""Tests for custom exception handlers."""

import logging

import pytest

import httpx
from fastapi import HTTPException
from httpx import ASGITransport

from bioimageflow_server.app import create_app
from bioimageflow_server.models.tools import AppConfig
from bioimageflow_server.services.tool_registry import ToolRegistryService

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


async def test_service_http_exception_is_logged(
    caplog: pytest.LogCaptureFixture,
) -> None:
    app = create_app(AppConfig(tool_registry=ToolRegistryService()))

    @app.get("/api/v1/test-service-failure")
    async def _test_service_failure() -> None:
        try:
            raise RuntimeError("solver unavailable")
        except RuntimeError as exc:
            raise HTTPException(
                status_code=503,
                detail={"error": "service_unavailable", "detail": "solver unavailable"},
            ) from exc

    async with httpx.AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        with caplog.at_level(logging.ERROR, logger="bioimageflow_server.app"):
            resp = await ac.get("/api/v1/test-service-failure")

    assert resp.status_code == 503
    assert resp.json()["error"] == "service_unavailable"
    assert "HTTP 503 returned for GET /api/v1/test-service-failure" in caplog.text
    assert "service_unavailable" in caplog.text


async def test_expected_forbidden_http_exception_is_not_warning_logged(
    caplog: pytest.LogCaptureFixture,
) -> None:
    app = create_app(AppConfig(tool_registry=ToolRegistryService()))

    @app.get("/api/v1/test-feature-gate")
    async def _test_feature_gate() -> None:
        raise HTTPException(status_code=403, detail="Feature disabled")

    async with httpx.AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        with caplog.at_level(logging.WARNING, logger="bioimageflow_server.app"):
            resp = await ac.get("/api/v1/test-feature-gate")

    assert resp.status_code == 403
    assert not caplog.records


async def test_request_validation_error_is_not_warning_logged(
    client: httpx.AsyncClient,
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.WARNING, logger="bioimageflow_server.app"):
        resp = await client.get("/api/v1/test-validation", params={"value": "not_an_int"})

    assert resp.status_code == 422
    assert not caplog.records
