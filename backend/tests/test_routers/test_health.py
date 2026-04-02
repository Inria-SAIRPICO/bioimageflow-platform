"""Tests for the health endpoint."""

import httpx
import pytest


pytestmark = pytest.mark.anyio


async def test_health_returns_200(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/v1/health")
    assert response.status_code == 200


async def test_health_returns_expected_payload(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/v1/health")
    data = response.json()
    assert data["status"] == "ok"
    assert "version" in data
