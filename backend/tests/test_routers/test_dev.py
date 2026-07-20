"""Tests for the dev router (seed endpoint)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

import httpx
import pytest
from httpx import ASGITransport

from bioimageflow_server.app import create_app
from bioimageflow_server.models.tools import AppConfig
from bioimageflow_server.services.tool_registry import ToolRegistryService
from tests.graph_factory import graph_document

pytestmark = pytest.mark.anyio


@pytest.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    config = AppConfig(tool_registry=ToolRegistryService(), enable_dev_router=True)
    app = create_app(config=config)
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


async def test_seed_populates_registry(client: httpx.AsyncClient):
    resp = await client.get("/api/v1/tools")
    initial_tool_names = {tool["name"] for tool in resp.json()}

    # Seed
    resp = await client.post("/api/v1/dev/seed")
    assert resp.status_code == 200
    data = resp.json()
    assert data["tools"] == 5
    assert data["packages"] == 3

    # Now tools and packages are populated
    resp = await client.get("/api/v1/tools")
    tools = resp.json()
    tool_names = {t["name"] for t in tools}
    assert tool_names.issuperset(initial_tool_names)
    assert "SeedNumbers" in tool_names
    assert "IncrementNumbers" in tool_names
    assert "CellposeSegmenter" in tool_names
    assert "GaussianBlur" in tool_names
    seed_tool = next(t for t in tools if t["name"] == "SeedNumbers")
    assert seed_tool["tool_type"] == "DataFrameTool"
    assert seed_tool["accepts_upstream"] is False
    assert seed_tool["outputs"] == {
        "number": {"type": "int", "default": None, "image_spec": None},
        "label": {"type": "str", "default": None, "image_spec": None},
    }
    increment_tool = next(t for t in tools if t["name"] == "IncrementNumbers")
    assert increment_tool["tool_type"] == "DataFrameTool"
    assert increment_tool["accepts_upstream"] is True
    assert increment_tool["inputs"]["number"]["type"] == "int"
    assert increment_tool["inputs"]["number"]["required"] is True
    assert increment_tool["inputs"]["number"]["connectable"] == "by_default"
    assert (
        increment_tool["inputs"]["number"]["description"]
        == "Number column to increment"
    )
    assert increment_tool["outputs"] == {
        "number_plus_one": {"type": "int", "default": None, "image_spec": None},
    }

    resp = await client.get("/api/v1/tools/packages")
    packages = resp.json()
    package_names = {package["name"] for package in packages}
    assert {"bioimageflow-dev-seed", "bioimageflow-cellpose", "bioimageflow-filters"}.issubset(
        package_names
    )


async def test_seed_registers_executable_source_tool(client: httpx.AsyncClient):
    await client.post("/api/v1/dev/seed")

    resp = await client.put(
        "/api/v1/graph",
        json={
            "graph": graph_document(
                nodes=[
                    {
                        "type": "tool",
                        "id": "seed_numbers_1",
                        "name": "Seed Numbers",
                        "tool_name": "SeedNumbers",
                        "position": [0, 0],
                        "parameters": {},
                    },
                ]
            ),
        },
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["valid"] is True
    assert data["node_statuses"]["seed_numbers_1"]["status"] in {
        "unexecuted",
        "cached",
    }


async def test_seed_image_output_writes_v1_latest_view(tmp_path: Path):
    config = AppConfig(
        tool_registry=ToolRegistryService(),
        enable_dev_router=True,
        storage_path=tmp_path,
    )
    app = create_app(config=config)
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/v1/dev/seed-image-output")
        assert resp.status_code == 200
        payload = resp.json()

        latest = (
            tmp_path
            / "views"
            / "latest"
            / f"{payload['node_id']}.bioimageflow-link.json"
        )
        assert latest.is_file()
        assert not (tmp_path / "data").exists()
        assert list((tmp_path / "cache" / "v1" / "results").glob("*/*/rk_*/current.json"))
        assert list((tmp_path / "cache" / "v1" / "results").glob("*/*/rk_*/records/rec_*/manifest.json"))

        data_resp = await client.get(f"/api/v1/nodes/{payload['node_id']}/data")
        assert data_resp.status_code == 200
        rows = data_resp.json()["rows"]
        assert rows[0][payload["column"]] == payload["source_path"]
