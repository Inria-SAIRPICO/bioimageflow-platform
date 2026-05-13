"""Tests for workflow draft endpoints."""

from collections.abc import AsyncIterator
from pathlib import Path
from typing import Annotated, Any

import httpx
import pytest

from bioimageflow_core.environment import EnvironmentSpec
from bioimageflow_core.tool import IOModel, ProcessingTool
from bioimageflow_core.types import ImageSpec, Semantic
from bioimageflow_server.app import create_app
from bioimageflow_server.models.tools import AppConfig, ToolMetadata
from bioimageflow_server.services.tool_registry import ToolRegistryService

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


class _ProcInputs(IOModel):
    input_image: Annotated[Path, ImageSpec(semantics={Semantic.INTENSITY})]
    threshold: float = 0.5


class _ProcOutputs(IOModel):
    mask: Annotated[Path, ImageSpec(semantics={Semantic.LABEL})]


class MockProcessingTool(ProcessingTool):
    environment = EnvironmentSpec(name="test", dependencies={})
    Inputs = _ProcInputs
    Outputs = _ProcOutputs

    def process_row(self, arguments: Any) -> Any:
        return {}


def _test_registry() -> ToolRegistryService:
    reg = ToolRegistryService()
    reg.register_tool(
        "MockProcessingTool",
        ToolMetadata(
            name="MockProcessingTool",
            display_name="MockProcessingTool",
            package="test-pkg",
            package_version="1.0.0",
            tool_type="ProcessingTool",
        ),
        tool_class=MockProcessingTool,
    )
    return reg


async def _make_client(tmp_path: Path) -> httpx.AsyncClient:
    app = create_app(
        AppConfig(
            tool_registry=_test_registry(),
            storage_path=tmp_path,
        )
    )
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


@pytest.fixture
async def client(tmp_path: Path) -> AsyncIterator[httpx.AsyncClient]:
    c = await _make_client(tmp_path)
    async with c:
        yield c


def _graph(node_id: str = "n1", threshold: Any = 0.5) -> dict[str, Any]:
    return {
        "nodes": [
            {
                "id": node_id,
                "name": node_id,
                "tool_name": "MockProcessingTool",
                "position": [0, 0],
                "parameters": {
                    "input_image": "/tmp/x.tif",
                    "threshold": threshold,
                },
            }
        ],
        "edges": [],
    }


async def test_create_get_and_update_revisions(client: httpx.AsyncClient) -> None:
    create = await client.post("/api/v1/workflow-drafts", json={"graph": _graph()})

    assert create.status_code == 201, create.text
    created = create.json()
    assert created["draft_id"]
    assert created["revision"] == 1
    assert created["dirty"] is False
    assert created["validation"]["valid"] is True

    get = await client.get(f"/api/v1/workflow-drafts/{created['draft_id']}")
    assert get.status_code == 200
    assert get.json()["revision"] == 1
    assert get.json()["graph"]["nodes"][0]["id"] == "n1"

    updated_graph = _graph(node_id="n2")
    update = await client.put(
        f"/api/v1/workflow-drafts/{created['draft_id']}",
        json={
            "graph": updated_graph,
            "base_revision": 1,
            "client_seq": 7,
        },
    )

    assert update.status_code == 200, update.text
    body = update.json()
    assert body["revision"] == 2
    assert body["client_seq"] == 7
    assert body["dirty"] is True
    assert body["graph"]["nodes"][0]["id"] == "n2"
    assert body["validation"]["valid"] is True


async def test_stale_update_returns_409(client: httpx.AsyncClient) -> None:
    create = await client.post("/api/v1/workflow-drafts", json={"graph": _graph()})
    draft_id = create.json()["draft_id"]
    assert (
        await client.put(
            f"/api/v1/workflow-drafts/{draft_id}",
            json={"graph": _graph("n2"), "base_revision": 1, "client_seq": 1},
        )
    ).status_code == 200

    stale = await client.put(
        f"/api/v1/workflow-drafts/{draft_id}",
        json={"graph": _graph("n3"), "base_revision": 1, "client_seq": 2},
    )

    assert stale.status_code == 409
    assert stale.json()["detail"] == "Stale draft base_revision"
    assert stale.json()["field"] == "base_revision"
    assert stale.json()["current_revision"] == 2


async def test_patch_parameters_requires_base_revision(client: httpx.AsyncClient) -> None:
    create = await client.post("/api/v1/workflow-drafts", json={"graph": _graph()})
    draft_id = create.json()["draft_id"]

    response = await client.patch(
        f"/api/v1/workflow-drafts/{draft_id}/nodes/n1/parameters",
        json={"parameters": {"threshold": 0.7}},
    )

    assert response.status_code == 422


async def test_patch_parameters_updates_graph_and_validation(
    client: httpx.AsyncClient,
) -> None:
    create = await client.post("/api/v1/workflow-drafts", json={"graph": _graph()})
    draft_id = create.json()["draft_id"]

    patched = await client.patch(
        f"/api/v1/workflow-drafts/{draft_id}/nodes/n1/parameters",
        json={
            "parameters": {"threshold": "not-a-float"},
            "base_revision": 1,
            "client_seq": 3,
        },
    )

    assert patched.status_code == 200, patched.text
    body = patched.json()
    assert body["revision"] == 2
    assert body["client_seq"] == 3
    assert body["graph"]["nodes"][0]["parameters"]["threshold"] == "not-a-float"
    assert body["validation"]["valid"] is False
    assert any(
        error["type"] == "parameter_invalid" and error["field"] == "threshold"
        for error in body["validation"]["errors"]
    )

    validate = await client.post(f"/api/v1/workflow-drafts/{draft_id}/validate")
    assert validate.status_code == 200
    assert validate.json()["validation"]["valid"] is False
