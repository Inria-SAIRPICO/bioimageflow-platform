"""Tests for the dev router (seed endpoint)."""

from __future__ import annotations

from collections.abc import AsyncIterator

import httpx
import pytest
from httpx import ASGITransport

from bioimageflow_server.app import create_app
from bioimageflow_server.models.tools import AppConfig
from bioimageflow_server.services.tool_registry import ToolRegistryService

pytestmark = pytest.mark.anyio


@pytest.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    config = AppConfig(tool_registry=ToolRegistryService())
    app = create_app(config=config)
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


async def test_seed_populates_registry(client: httpx.AsyncClient):
    # Registry starts empty
    resp = await client.get("/api/v1/tools")
    assert resp.json() == []

    # Seed
    resp = await client.post("/api/v1/dev/seed")
    assert resp.status_code == 200
    data = resp.json()
    assert data["tools"] == 3
    assert data["packages"] == 2

    # Now tools and packages are populated
    resp = await client.get("/api/v1/tools")
    tools = resp.json()
    assert len(tools) == 3
    tool_names = {t["name"] for t in tools}
    assert "CellposeSegmenter" in tool_names
    assert "GaussianBlur" in tool_names

    resp = await client.get("/api/v1/tools/packages")
    packages = resp.json()
    assert len(packages) == 2
