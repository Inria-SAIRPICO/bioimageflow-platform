"""Integration tests for the graph router."""
# pyright: reportInvalidTypeForm=false
# Rationale: library factory types like ``ImagePath(semantics={...})`` return
# ``Annotated[Path, spec]`` at runtime; pyright can't evaluate them statically.

from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import httpx
import pytest
from httpx import ASGITransport

from bioimageflow_server.app import create_app
from bioimageflow_server.models.tools import AppConfig, ToolMetadata
from bioimageflow_server.services.tool_registry import ToolRegistryService

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


# ---- Mock tool fixtures -----------------------------------------------------
# Tool classes must be defined at module level so ``Workflow.from_dict``
# can re-import them via the module's ``__name__``.

from bioimageflow.dataframe_tool import DataFrameTool
from bioimageflow_core.environment import EnvironmentSpec
from bioimageflow_core.tool import IOModel, ProcessingTool
from bioimageflow_core.types import ImagePath, Semantic


class _ProcInputs(IOModel):
    input_image: ImagePath(semantics={Semantic.INTENSITY})
    diameter: float = 30.0


class _ProcOutputs(IOModel):
    mask: ImagePath(semantics={Semantic.LABEL})


class MockProcessingTool(ProcessingTool):
    environment = EnvironmentSpec(name="test", dependencies={})
    Inputs = _ProcInputs
    Outputs = _ProcOutputs

    def process_row(self, arguments: Any) -> Any:
        return {}


class _DFInputs(IOModel):
    threshold: float = 0.5


class MockDataFrameTool(DataFrameTool):
    Inputs = _DFInputs


class _IntInputs(IOModel):
    input_image: ImagePath(semantics={Semantic.INTENSITY})
    n: int = 1


class IntTool(ProcessingTool):
    environment = EnvironmentSpec(name="test", dependencies={})
    Inputs = _IntInputs
    Outputs = _ProcOutputs

    def process_row(self, arguments: Any) -> Any:
        return {}


_TOOL_CLASSES: dict[str, type] = {
    "MockProcessingTool": MockProcessingTool,
    "MockDataFrameTool": MockDataFrameTool,
    "IntTool": IntTool,
}


def _test_registry() -> ToolRegistryService:
    reg = ToolRegistryService()
    for name, cls in _TOOL_CLASSES.items():
        reg.register_tool(
            name,
            ToolMetadata(
                name=name,
                display_name=name,
                package="test-pkg",
                package_version="1.0.0",
                tool_type="ProcessingTool",
            ),
            tool_class=cls,
        )
    return reg


class _FakeExecManager:
    def __init__(self, running: bool) -> None:
        self.is_running = running


async def _make_client(
    tmp_path: Path | None = None,
    execution_manager: Any | None = None,
) -> httpx.AsyncClient:
    config = AppConfig(
        tool_registry=_test_registry(),
        storage_path=tmp_path,
        execution_manager=execution_manager,
    )
    app = create_app(config)
    transport = ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


@pytest.fixture
async def client(tmp_path: Path) -> AsyncIterator[httpx.AsyncClient]:
    c = await _make_client(tmp_path=tmp_path)
    async with c:
        yield c


@pytest.fixture
async def client_locked(tmp_path: Path) -> AsyncIterator[httpx.AsyncClient]:
    c = await _make_client(
        tmp_path=tmp_path, execution_manager=_FakeExecManager(running=True)
    )
    async with c:
        yield c


# ---- PUT /graph ------------------------------------------------------------


async def test_put_valid_graph(client: httpx.AsyncClient) -> None:
    body = {
        "nodes": [
            {
                "id": "n1",
                "name": "n1",
                "tool_name": "MockProcessingTool",
                "position": [0, 0],
                "parameters": {"input_image": "/tmp/x.tif"},
            }
        ],
        "edges": [],
    }
    resp = await client.put("/api/v1/graph", json=body)
    assert resp.status_code == 200
    data = resp.json()
    assert data["valid"] is True
    assert "n1" in data["node_statuses"]


async def test_put_missing_tool(client: httpx.AsyncClient) -> None:
    body = {
        "nodes": [
            {
                "id": "n1",
                "name": "n1",
                "tool_name": "NoSuchTool",
                "position": [0, 0],
                "parameters": {},
            }
        ],
        "edges": [],
    }
    resp = await client.put("/api/v1/graph", json=body)
    assert resp.status_code == 200
    data = resp.json()
    assert data["valid"] is False
    assert any(e["type"] == "missing_tool" for e in data["errors"])


async def test_put_cycle(client: httpx.AsyncClient) -> None:
    body = {
        "nodes": [
            {"id": "a", "name": "a", "tool_name": "MockProcessingTool",
             "position": [0, 0], "parameters": {"input_image": "/a"}},
            {"id": "b", "name": "b", "tool_name": "MockProcessingTool",
             "position": [0, 0], "parameters": {"input_image": "/b"}},
        ],
        "edges": [
            {"type": "column_ref", "id": "e1", "source_node": "a",
             "target_node": "b", "source_output": "mask",
             "target_input": "input_image"},
            {"type": "column_ref", "id": "e2", "source_node": "b",
             "target_node": "a", "source_output": "mask",
             "target_input": "input_image"},
        ],
    }
    resp = await client.put("/api/v1/graph", json=body)
    assert resp.status_code == 200
    data = resp.json()
    assert any(e["type"] == "cycle_detected" for e in data["errors"])


async def test_put_parameter_invalid(client: httpx.AsyncClient) -> None:
    body = {
        "nodes": [
            {
                "id": "n1",
                "name": "n1",
                "tool_name": "IntTool",
                "position": [0, 0],
                "parameters": {"input_image": "/a", "n": "not-an-int"},
            }
        ],
        "edges": [],
    }
    resp = await client.put("/api/v1/graph", json=body)
    data = resp.json()
    assert resp.status_code == 200
    assert any(
        e["type"] == "parameter_invalid" and e["field"] == "n"
        for e in data["errors"]
    )


async def test_put_empty_graph(client: httpx.AsyncClient) -> None:
    resp = await client.put("/api/v1/graph", json={"nodes": [], "edges": []})
    assert resp.status_code == 200
    data = resp.json()
    assert data["valid"] is True


async def test_put_duplicate_node_ids(client: httpx.AsyncClient) -> None:
    body = {
        "nodes": [
            {"id": "dup", "name": "a", "tool_name": "MockProcessingTool",
             "position": [0, 0], "parameters": {"input_image": "/a"}},
            {"id": "dup", "name": "b", "tool_name": "MockProcessingTool",
             "position": [0, 0], "parameters": {"input_image": "/b"}},
        ],
        "edges": [],
    }
    resp = await client.put("/api/v1/graph", json=body)
    data = resp.json()
    assert any(e["type"] == "invalid_node_id" for e in data["errors"])


async def test_put_returns_423_when_locked(client_locked: httpx.AsyncClient) -> None:
    resp = await client_locked.put(
        "/api/v1/graph", json={"nodes": [], "edges": []}
    )
    assert resp.status_code == 423


async def test_put_with_no_execution_manager_is_unlocked(
    client: httpx.AsyncClient,
) -> None:
    resp = await client.put("/api/v1/graph", json={"nodes": [], "edges": []})
    assert resp.status_code == 200


# ---- PATCH /graph/nodes/{id}/parameters ------------------------------------


async def test_patch_valid_parameters(client: httpx.AsyncClient) -> None:
    resp = await client.patch(
        "/api/v1/graph/nodes/n1/parameters",
        params={"tool_name": "IntTool"},
        json={"parameters": {"n": 5}},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["valid"] is True
    assert list(data["node_statuses"].keys()) == ["n1"]


async def test_patch_invalid_parameters(client: httpx.AsyncClient) -> None:
    resp = await client.patch(
        "/api/v1/graph/nodes/n1/parameters",
        params={"tool_name": "IntTool"},
        json={"parameters": {"n": "not-an-int"}},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["valid"] is False
    assert any(e["type"] == "parameter_invalid" for e in data["errors"])


async def test_patch_missing_tool_name(client: httpx.AsyncClient) -> None:
    resp = await client.patch(
        "/api/v1/graph/nodes/n1/parameters",
        json={"parameters": {"n": 5}},
    )
    assert resp.status_code == 400


async def test_patch_with_binding_shape_rejected(
    client: httpx.AsyncClient,
) -> None:
    resp = await client.patch(
        "/api/v1/graph/nodes/n1/parameters",
        params={"tool_name": "MockProcessingTool"},
        json={
            "parameters": {"input_image": {"node_id": "up", "output": "mask"}}
        },
    )
    assert resp.status_code == 400


async def test_patch_returns_423_when_locked(
    client_locked: httpx.AsyncClient,
) -> None:
    resp = await client_locked.patch(
        "/api/v1/graph/nodes/n1/parameters",
        params={"tool_name": "IntTool"},
        json={"parameters": {"n": 5}},
    )
    assert resp.status_code == 423


async def test_patch_unknown_tool_surfaces_missing_tool(
    client: httpx.AsyncClient,
) -> None:
    resp = await client.patch(
        "/api/v1/graph/nodes/n1/parameters",
        params={"tool_name": "NoSuchTool"},
        json={"parameters": {}},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert any(e["type"] == "missing_tool" for e in data["errors"])
