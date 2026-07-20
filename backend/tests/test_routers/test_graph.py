"""Integration tests for the graph router."""
# pyright: reportInvalidTypeForm=false
# Rationale: image file fields use ``Annotated[Path, ImageSpec(...)]`` metadata;
# pyright can't evaluate this runtime metadata statically.

from collections.abc import AsyncIterator
from pathlib import Path
from typing import Annotated, Any
from unittest.mock import MagicMock

import httpx
import pytest
from httpx import ASGITransport

from bioimageflow.dataframe_tool import DataFrameTool
from bioimageflow_core.environment import EnvironmentSpec
from bioimageflow_core.tool import IOModel, ProcessingTool
from bioimageflow_core.types import ImageSpec, Semantic
from bioimageflow_server.app import create_app
from bioimageflow_server.models.tools import AppConfig, ToolMetadata
from bioimageflow_server.services.tool_registry import ToolRegistryService
from tests.common_tools import load_common_tools_class

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


class _ProcInputs(IOModel):
    input_image: Annotated[Path, ImageSpec(semantics={Semantic.INTENSITY})]
    diameter: float = 30.0


class _ProcOutputs(IOModel):
    mask: Annotated[Path, ImageSpec(semantics={Semantic.LABEL})]


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
    input_image: Annotated[Path, ImageSpec(semantics={Semantic.INTENSITY})]
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
    workflow_store: Any | None = None,
) -> httpx.AsyncClient:
    config = AppConfig(
        tool_registry=_test_registry(),
        storage_path=tmp_path,
        execution_manager=execution_manager,
        workflow_store=workflow_store,
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
    c = await _make_client(tmp_path=tmp_path, execution_manager=_FakeExecManager(running=True))
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


async def test_put_graph_resolves_workflow_storage_path(tmp_path: Path) -> None:
    workflow_store = MagicMock()
    workflow_storage = tmp_path / "workflows" / "wf_a"
    workflow_store.get_storage_path.return_value = workflow_storage
    c = await _make_client(tmp_path=tmp_path, workflow_store=workflow_store)
    body = {
        "graph": {
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
        },
        "workflow_name": "wf_a",
    }
    async with c:
        resp = await c.put("/api/v1/graph", json=body)

    assert resp.status_code == 200
    assert workflow_store.get_storage_path.call_args_list == [
        (("wf_a",), {}),
        (("wf_a",), {}),
    ]


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
            {
                "id": "a",
                "name": "a",
                "tool_name": "MockProcessingTool",
                "position": [0, 0],
                "parameters": {"input_image": "/a"},
            },
            {
                "id": "b",
                "name": "b",
                "tool_name": "MockProcessingTool",
                "position": [0, 0],
                "parameters": {"input_image": "/b"},
            },
        ],
        "edges": [
            {
                "type": "column_ref",
                "id": "e1",
                "source_node": "a",
                "target_node": "b",
                "source_output": "mask",
                "target_input": "input_image",
            },
            {
                "type": "column_ref",
                "id": "e2",
                "source_node": "b",
                "target_node": "a",
                "source_output": "mask",
                "target_input": "input_image",
            },
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
    assert any(e["type"] == "parameter_invalid" and e["field"] == "n" for e in data["errors"])


async def test_put_empty_graph(client: httpx.AsyncClient) -> None:
    resp = await client.put("/api/v1/graph", json={"nodes": [], "edges": []})
    assert resp.status_code == 200
    data = resp.json()
    assert data["valid"] is True


async def test_put_duplicate_node_ids(client: httpx.AsyncClient) -> None:
    body = {
        "nodes": [
            {
                "id": "dup",
                "name": "a",
                "tool_name": "MockProcessingTool",
                "position": [0, 0],
                "parameters": {"input_image": "/a"},
            },
            {
                "id": "dup",
                "name": "b",
                "tool_name": "MockProcessingTool",
                "position": [0, 0],
                "parameters": {"input_image": "/b"},
            },
        ],
        "edges": [],
    }
    resp = await client.put("/api/v1/graph", json=body)
    data = resp.json()
    assert any(e["type"] == "invalid_node_id" for e in data["errors"])


async def test_put_returns_423_when_locked(client_locked: httpx.AsyncClient) -> None:
    resp = await client_locked.put("/api/v1/graph", json={"nodes": [], "edges": []})
    assert resp.status_code == 423


async def test_put_with_no_execution_manager_is_unlocked(
    client: httpx.AsyncClient,
) -> None:
    resp = await client.put("/api/v1/graph", json={"nodes": [], "edges": []})
    assert resp.status_code == 200


# ---- Removed PATCH /graph/nodes/{id}/parameters ----------------------------


async def test_parameter_patch_endpoint_is_removed(client: httpx.AsyncClient) -> None:
    resp = await client.patch(
        "/api/v1/graph/nodes/n1/parameters",
        params={"tool_name": "IntTool"},
        json={"parameters": {"n": 5}},
    )
    assert resp.status_code == 404


# ---- POST /graph/nodes/{node_id}/output_schema ----------------------------

# Build a registry with real common-tools (Generate, Files, CrossJoin,
# JoinOnColumn) so that serialize_resolved_outputs returns meaningful results.


def _common_tools_registry() -> ToolRegistryService:
    reg = ToolRegistryService()
    # Register the standard test tool classes
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
    # Register real common-tools
    for tool_name in ("Files", "Generate", "CrossJoin", "JoinOnColumn"):
        cls, version = load_common_tools_class(tool_name)
        reg._register_tool_from_class(
            cls,
            tool_name,
            "bioimageflow_common_tools",
            version,
        )
    return reg


async def _make_common_client(
    tmp_path: Path,
) -> httpx.AsyncClient:
    config = AppConfig(
        tool_registry=_common_tools_registry(),
        storage_path=tmp_path,
    )
    app = create_app(config)
    transport = ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


@pytest.fixture
async def common_client(tmp_path: Path) -> AsyncIterator[httpx.AsyncClient]:
    c = await _make_common_client(tmp_path=tmp_path)
    async with c:
        yield c


@pytest.mark.external
@pytest.mark.common_tools
class TestOutputSchema:
    """POST /graph/nodes/{node_id}/output_schema — parity with library tests."""

    async def test_generate_resolved(self, common_client: httpx.AsyncClient) -> None:
        body = {
            "nodes": [
                {
                    "id": "gen_1",
                    "name": "gen_1",
                    "tool_name": "Generate",
                    "position": [0, 0],
                    "parameters": {"column_name": "sensitivity", "values": [1, 2]},
                }
            ],
            "edges": [],
        }
        resp = await common_client.post(
            "/api/v1/graph/nodes/gen_1/output_schema",
            json=body,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["resolved"] is True
        assert "sensitivity" in data["columns"]
        assert data["columns"]["sensitivity"]["type"] == "any"

    async def test_generate_unresolved_no_column_name(
        self,
        common_client: httpx.AsyncClient,
    ) -> None:
        # Generate requires column_name; omitting it makes it unresolvable.
        # However, Generate's column_name is a required param, so the graph
        # build may fail. The endpoint should return resolved=false, not 4xx.
        body = {
            "nodes": [
                {
                    "id": "gen_1",
                    "name": "gen_1",
                    "tool_name": "Generate",
                    "position": [0, 0],
                    "parameters": {},
                }
            ],
            "edges": [],
        }
        resp = await common_client.post(
            "/api/v1/graph/nodes/gen_1/output_schema",
            json=body,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["resolved"] is False
        assert data["columns"] == {}

    async def test_cross_join_four_columns(
        self,
        common_client: httpx.AsyncClient,
        tmp_path: Path,
    ) -> None:
        body = {
            "nodes": [
                {
                    "id": "files_1",
                    "name": "files_1",
                    "tool_name": "Files",
                    "position": [0, 0],
                    "parameters": {"path": str(tmp_path)},
                },
                {
                    "id": "gen_sens",
                    "name": "gen_sens",
                    "tool_name": "Generate",
                    "position": [100, 0],
                    "parameters": {"column_name": "sensitivity", "values": [0.1, 0.2]},
                },
                {
                    "id": "gen_size",
                    "name": "gen_size",
                    "tool_name": "Generate",
                    "position": [200, 0],
                    "parameters": {"column_name": "size", "values": [10, 20]},
                },
                {
                    "id": "cross_1",
                    "name": "cross_1",
                    "tool_name": "CrossJoin",
                    "position": [300, 0],
                    "parameters": {},
                },
            ],
            "edges": [
                {
                    "type": "positional",
                    "id": "e1",
                    "source_node": "files_1",
                    "target_node": "cross_1",
                    "positional_index": 0,
                },
                {
                    "type": "positional",
                    "id": "e2",
                    "source_node": "gen_sens",
                    "target_node": "cross_1",
                    "positional_index": 1,
                },
                {
                    "type": "positional",
                    "id": "e3",
                    "source_node": "gen_size",
                    "target_node": "cross_1",
                    "positional_index": 2,
                },
            ],
        }
        resp = await common_client.post(
            "/api/v1/graph/nodes/cross_1/output_schema",
            json=body,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["resolved"] is True
        assert {"path", "sensitivity", "size"}.issubset(data["columns"].keys())

    async def test_join_on_column_unresolved_then_resolved(
        self,
        common_client: httpx.AsyncClient,
        tmp_path: Path,
    ) -> None:
        # Two Files as left/right; JoinOnColumn without join_column -> unresolved
        body_no_jc = {
            "nodes": [
                {
                    "id": "files_l",
                    "name": "files_l",
                    "tool_name": "Files",
                    "position": [0, 0],
                    "parameters": {"path": str(tmp_path)},
                },
                {
                    "id": "files_r",
                    "name": "files_r",
                    "tool_name": "Files",
                    "position": [100, 0],
                    "parameters": {"path": str(tmp_path)},
                },
                {
                    "id": "joc_1",
                    "name": "joc_1",
                    "tool_name": "JoinOnColumn",
                    "position": [200, 0],
                    "parameters": {},
                },
            ],
            "edges": [
                {
                    "type": "positional",
                    "id": "e1",
                    "source_node": "files_l",
                    "target_node": "joc_1",
                    "positional_index": 0,
                },
                {
                    "type": "positional",
                    "id": "e2",
                    "source_node": "files_r",
                    "target_node": "joc_1",
                    "positional_index": 1,
                },
            ],
        }
        resp1 = await common_client.post(
            "/api/v1/graph/nodes/joc_1/output_schema",
            json=body_no_jc,
        )
        assert resp1.status_code == 200
        data1 = resp1.json()
        assert data1["resolved"] is False
        assert data1["columns"] == {}

        # Now set join_column — should resolve
        body_with_jc = {
            **body_no_jc,
            "nodes": [
                *body_no_jc["nodes"][:2],
                {
                    **body_no_jc["nodes"][2],
                    "parameters": {"join_column": "path"},
                },
            ],
        }
        resp2 = await common_client.post(
            "/api/v1/graph/nodes/joc_1/output_schema",
            json=body_with_jc,
        )
        assert resp2.status_code == 200
        data2 = resp2.json()
        assert data2["resolved"] is True


async def test_unknown_output_schema_node_id_returns_404(client: httpx.AsyncClient) -> None:
    body = {"nodes": [], "edges": []}
    resp = await client.post(
        "/api/v1/graph/nodes/nonexistent/output_schema",
        json=body,
    )
    assert resp.status_code == 404


async def test_malformed_graph_output_schema_is_unresolved(client: httpx.AsyncClient) -> None:
    """Build failures return an unresolved schema during transient invalid edits."""
    body = {
        "nodes": [
            {
                "id": "bad_1",
                "name": "bad_1",
                "tool_name": "NoSuchTool",
                "position": [0, 0],
                "parameters": {},
            },
        ],
        "edges": [],
    }
    resp = await client.post(
        "/api/v1/graph/nodes/bad_1/output_schema",
        json=body,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["resolved"] is False
    assert data["columns"] == {}
