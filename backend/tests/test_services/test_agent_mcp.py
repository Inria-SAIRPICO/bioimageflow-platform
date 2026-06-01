"""Tests for the thin BioImageFlow MCP transport layer."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock

import httpx
import pytest

from bioimageflow_server.app import create_app
from bioimageflow_server.agent_mcp import (
    BioImageFlowMCPGateway,
    create_mcp_server,
    read_agent_state,
)
from bioimageflow_server.models.tools import AppConfig
from bioimageflow_server.services.tool_registry import ToolRegistryService
from bioimageflow_server.services.workflow_store import WorkflowStoreService

pytestmark = pytest.mark.anyio


class _FakeFastMCP:
    def __init__(self, name: str) -> None:
        self.name = name
        self.tools: dict[str, Any] = {}

    def tool(self, **_kwargs: Any) -> Any:
        def decorator(fn: Any) -> Any:
            self.tools[fn.__name__] = fn
            return fn

        return decorator


class _FakeExecutionManager:
    is_running = False

    def __init__(self) -> None:
        self.start = AsyncMock()
        self.stop = AsyncMock()


def _write_state(tmp_path: Path, *, workflow_id: str = "folder/wf") -> Path:
    state = tmp_path / ".bioimageflow" / "agent-state.json"
    state.parent.mkdir()
    state.write_text(
        json.dumps(
            {
                "api_base_url": "http://bif.test/api/v1",
                "active_workflow_id": workflow_id,
                "current_draft_revision": 7,
            }
        ),
        encoding="utf-8",
    )
    return state


def _workspace_state_path(tmp_path: Path) -> Path:
    return tmp_path / "workspace" / ".bioimageflow" / "agent-state.json"


def test_read_agent_state_discovers_active_workflow(tmp_path: Path) -> None:
    state_path = _write_state(tmp_path)

    state = read_agent_state(state_path)

    assert state.api_base_url == "http://bif.test/api/v1"
    assert state.active_workflow_id == "folder/wf"
    assert state.current_draft_revision == 7


def test_create_mcp_server_registers_expected_tools(tmp_path: Path) -> None:
    state_path = _write_state(tmp_path)
    created: list[_FakeFastMCP] = []

    def factory(name: str) -> _FakeFastMCP:
        server = _FakeFastMCP(name)
        created.append(server)
        return server

    server = create_mcp_server(state_path=state_path, mcp_factory=factory)

    assert server is created[0]
    assert set(server.tools) == {
        "get_active_workflow",
        "list_tools",
        "create_node",
        "delete_node",
        "rename_node",
        "update_node_parameters",
        "connect_nodes",
        "delete_edge",
        "validate_workflow",
        "run_workflow",
        "stop_execution",
    }


async def test_create_node_calls_backend_operation_api_with_auto_revision(
    tmp_path: Path,
) -> None:
    state_path = _write_state(tmp_path, workflow_id="folder/wf")
    requests: list[tuple[str, str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content.decode() or "{}")
        requests.append((request.method, str(request.url), payload))
        if request.method == "GET":
            return httpx.Response(
                200,
                json={"draft_revision": 12, "graph": {"nodes": [], "edges": []}},
            )
        return httpx.Response(
            200,
            json={
                "workflow_id": "folder/wf",
                "draft_revision": 13,
                "validation": {"valid": False, "errors": []},
                "graph": {"nodes": [{"id": "blur_1"}], "edges": []},
            },
        )

    gateway = BioImageFlowMCPGateway(
        state_path=state_path,
        transport=httpx.MockTransport(handler),
    )

    result = await gateway.create_node(
        node_id="blur_1",
        tool_name="GaussianBlur",
        name="Blur",
        position=[10, 20],
        parameters={"sigma": 2},
    )

    assert result == {
        "ok": True,
        "workflow_id": "folder/wf",
        "draft_revision": 13,
        "validation_valid": False,
    }
    assert requests[0] == (
        "GET",
        "http://bif.test/api/v1/workflow-drafts/folder/wf",
        {},
    )
    assert requests[1] == (
        "POST",
        "http://bif.test/api/v1/workflow-draft-operations/folder/wf",
        {
            "expected_revision": 12,
            "updated_by": "agent",
            "validate": True,
            "operations": [
                {
                    "type": "create_node",
                    "node_id": "blur_1",
                    "tool_name": "GaussianBlur",
                    "name": "Blur",
                    "position": [10, 20],
                    "parameters": {"sigma": 2},
                }
            ],
        },
    )


async def test_list_tools_returns_registry_metadata_and_creation_hints(
    tmp_path: Path,
) -> None:
    state_path = _write_state(tmp_path, workflow_id="wf")

    tool = {
        "name": "SegmentCells",
        "display_name": "Segment Cells",
        "package": "bioimageflow-common-tools",
        "package_version": "1.0.0",
        "tool_type": "ProcessingTool",
        "accepts_upstream": True,
        "dynamic_outputs": False,
        "dataframe_output": True,
        "documentation": "Segment cells from an image.",
        "tags": ["segmentation"],
        "categories": ["image processing"],
        "inputs": {
            "image": {
                "type": "path",
                "required": True,
                "nullable": False,
                "connectable": "by_default",
                "default": None,
                "display_name": "Image",
            },
            "sigma": {
                "type": "number",
                "required": False,
                "nullable": False,
                "connectable": "never",
                "default": 2.0,
                "min": 0.0,
                "max": 10.0,
                "step": 0.5,
            },
            "threshold": {
                "type": "number",
                "required": True,
                "nullable": False,
                "connectable": "never",
                "default": None,
            },
            "method": {
                "type": "string",
                "required": False,
                "nullable": False,
                "connectable": "not_by_default",
                "default": "otsu",
                "choices": ["otsu", "manual"],
            },
        },
        "outputs": {
            "mask": {"type": "path", "default": "mask.tif"},
            "table": {"type": "path", "default": "measurements.csv"},
        },
        "environment": {"status": "ready"},
        "source_kind": "package",
        "editable": False,
    }

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == "/api/v1/tools"
        return httpx.Response(200, json=[tool])

    gateway = BioImageFlowMCPGateway(
        state_path=state_path,
        transport=httpx.MockTransport(handler),
    )

    result = await gateway.list_tools()

    assert result["ok"] is True
    assert result["count"] == 1
    assert result["tools"] == [
        {
            "name": "SegmentCells",
            "display_name": "Segment Cells",
            "documentation": "Segment cells from an image.",
            "package": "bioimageflow-common-tools",
            "package_version": "1.0.0",
            "tool_type": "ProcessingTool",
            "accepts_upstream": True,
            "dynamic_outputs": False,
            "dataframe_output": True,
            "tags": ["segmentation"],
            "categories": ["image processing"],
            "inputs": tool["inputs"],
            "outputs": tool["outputs"],
            "environment": {"status": "ready"},
            "source_kind": "package",
            "editable": False,
            "creation": {
                "default_parameters": {"sigma": 2.0, "method": "otsu"},
                "required_unconnected_inputs": ["threshold"],
                "connectable_inputs": ["image", "method"],
                "default_output_templates": {
                    "mask": "mask.tif",
                    "table": "measurements.csv",
                },
            },
        }
    ]
    assert "description" not in result["tools"][0]


async def test_list_tools_handles_passthrough_outputs_without_template_defaults(
    tmp_path: Path,
) -> None:
    state_path = _write_state(tmp_path, workflow_id="wf")
    gateway = BioImageFlowMCPGateway(
        state_path=state_path,
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(
                200,
                json=[
                    {
                        "name": "MergeTables",
                        "display_name": "Merge Tables",
                        "package": "pkg",
                        "package_version": "1",
                        "tool_type": "DataFrameTool",
                        "accepts_upstream": True,
                        "dynamic_outputs": True,
                        "dataframe_output": True,
                        "documentation": "",
                        "tags": [],
                        "categories": [],
                        "inputs": {},
                        "outputs": {"_passthrough": True},
                        "source_kind": "package",
                        "editable": False,
                    }
                ],
            )
        ),
    )

    result = await gateway.list_tools()

    assert result["tools"][0]["outputs"] == {"_passthrough": True}
    assert result["tools"][0]["creation"]["default_output_templates"] == {}


async def test_graph_editing_tools_do_not_mutate_graph_locally(tmp_path: Path) -> None:
    state_path = _write_state(tmp_path)
    called_paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        called_paths.append(request.url.path)
        if request.method == "GET":
            return httpx.Response(
                200,
                json={"draft_revision": 2, "graph": {"nodes": [{"id": "a"}], "edges": []}},
            )
        return httpx.Response(
            200,
            json={
                "workflow_id": "folder/wf",
                "draft_revision": 3,
                "validation": {"valid": True, "errors": []},
                "graph": {"nodes": [{"id": "a"}], "edges": []},
            },
        )

    gateway = BioImageFlowMCPGateway(
        state_path=state_path,
        transport=httpx.MockTransport(handler),
    )

    await gateway.rename_node(node_id="a", name="New")

    assert called_paths == [
        "/api/v1/workflow-drafts/folder/wf",
        "/api/v1/workflow-draft-operations/folder/wf",
    ]


async def test_validation_run_and_stop_call_existing_rest_endpoints(
    tmp_path: Path,
) -> None:
    state_path = _write_state(tmp_path, workflow_id="wf")
    calls: list[tuple[str, str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content.decode() or "{}")
        calls.append((request.method, request.url.path, payload))
        if request.url.path.endswith("/workflow-drafts/wf"):
            return httpx.Response(
                200,
                json={"draft_revision": 1, "graph": {"nodes": [], "edges": []}},
            )
        if request.url.path.endswith("/graph"):
            return httpx.Response(200, json={"valid": True, "errors": []})
        if request.url.path.endswith("/execution/run"):
            return httpx.Response(202, json={"status": "started"})
        return httpx.Response(200, json={"status": "stopping"})

    gateway = BioImageFlowMCPGateway(
        state_path=state_path,
        transport=httpx.MockTransport(handler),
    )

    validation = await gateway.validate_workflow()
    run = await gateway.run_workflow(nodes=["n1"])
    stop = await gateway.stop_execution()

    assert validation == {"ok": True, "valid": True, "error_count": 0}
    assert run == {"ok": True, "status": "started"}
    assert stop == {"ok": True, "status": "stopping"}
    assert calls == [
        ("GET", "/api/v1/workflow-drafts/wf", {}),
        ("PUT", "/api/v1/graph", {"graph": {"nodes": [], "edges": []}, "workflow_name": "wf"}),
        ("GET", "/api/v1/workflow-drafts/wf", {}),
        (
            "POST",
            "/api/v1/execution/run",
            {"graph": {"nodes": [], "edges": []}, "workflow_name": "wf", "nodes": ["n1"]},
        ),
        ("POST", "/api/v1/execution/stop", {}),
    ]


async def test_mcp_registered_tools_smoke_against_asgi_app(tmp_path: Path) -> None:
    registry = ToolRegistryService()
    workflow_store = WorkflowStoreService(
        root_dir=tmp_path / "workspace" / "workflows",
        tool_registry=registry,
        storage_base_dir=tmp_path / "workspace" / "outputs",
    )
    execution_manager = _FakeExecutionManager()
    app = create_app(
        AppConfig(
            tool_registry=registry,
            workflow_store=workflow_store,
            execution_manager=execution_manager,
            storage_path=tmp_path / "bif-data",
            disable_hot_reload=True,
        )
    )
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        create = await client.post(
            "/api/v1/workflows",
            json={"name": "wf", "display_name": "wf"},
        )
        assert create.status_code == 201
        draft = await client.get("/api/v1/workflow-drafts/wf")
        assert draft.status_code == 200

        server = create_mcp_server(
            gateway=BioImageFlowMCPGateway(
                state_path=_workspace_state_path(tmp_path),
                transport=transport,
            ),
            mcp_factory=_FakeFastMCP,
        )

        active = await server.tools["get_active_workflow"]()
        created = await server.tools["create_node"](
            node_id="n1",
            tool_name="MissingTool",
            name="Node",
            position=[0, 0],
        )
        validation = await server.tools["validate_workflow"]()
        run = await server.tools["run_workflow"](nodes=["n1"])
        stop = await server.tools["stop_execution"]()

    assert active == {
        "ok": True,
        "api_base_url": "http://test/api/v1",
        "active_workflow_id": "wf",
        "current_draft_revision": 0,
    }
    assert created["ok"] is True
    assert created["draft_revision"] == 1
    assert created["validation_valid"] is False
    assert created["validation_errors"]
    assert validation["ok"] is True
    assert validation["valid"] is False
    assert validation["errors"][0]["type"] == "missing_tool"
    assert run == {"ok": True, "status": "started"}
    assert stop == {"ok": True, "status": "stopping"}
    execution_manager.start.assert_awaited_once()
    execution_manager.stop.assert_awaited_once()


async def test_create_node_returns_compact_error_when_draft_fetch_fails(
    tmp_path: Path,
) -> None:
    state_path = _write_state(tmp_path, workflow_id="missing")

    gateway = BioImageFlowMCPGateway(
        state_path=state_path,
        transport=httpx.MockTransport(lambda _request: httpx.Response(404, json={"detail": "no"})),
    )

    result = await gateway.create_node(
        node_id="n1",
        tool_name="Tool",
        name="Node",
        position=[0, 0],
    )

    assert result == {
        "ok": False,
        "status_code": 404,
        "error": {"detail": "no"},
    }


async def test_validate_workflow_preserves_backend_validation_error(
    tmp_path: Path,
) -> None:
    state_path = _write_state(tmp_path, workflow_id="wf")

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/workflow-drafts/wf"):
            return httpx.Response(
                200,
                json={"draft_revision": 1, "graph": {"nodes": [], "edges": []}},
            )
        return httpx.Response(423, json={"detail": "locked"})

    gateway = BioImageFlowMCPGateway(
        state_path=state_path,
        transport=httpx.MockTransport(handler),
    )

    assert await gateway.validate_workflow() == {
        "ok": False,
        "status_code": 423,
        "error": {"detail": "locked"},
    }


async def test_validate_workflow_returns_backend_validation_errors(
    tmp_path: Path,
) -> None:
    state_path = _write_state(tmp_path, workflow_id="wf")

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/workflow-drafts/wf"):
            return httpx.Response(
                200,
                json={
                    "draft_revision": 1,
                    "graph": {
                        "nodes": [
                            {
                                "id": "n1",
                                "name": "Node",
                                "tool_name": "MissingTool",
                                "position": [0, 0],
                                "parameters": {},
                            }
                        ],
                        "edges": [],
                    },
                },
            )
        return httpx.Response(
            200,
            json={
                "valid": False,
                "errors": [
                    {
                        "type": "missing_tool",
                        "detail": "Tool not found: MissingTool",
                        "node": "n1",
                        "edge_id": None,
                        "field": None,
                    }
                ],
            },
        )

    gateway = BioImageFlowMCPGateway(
        state_path=state_path,
        transport=httpx.MockTransport(handler),
    )

    assert await gateway.validate_workflow() == {
        "ok": True,
        "valid": False,
        "error_count": 1,
        "errors": [
            {
                "type": "missing_tool",
                "detail": "Tool not found: MissingTool",
                "node": "n1",
                "edge_id": None,
                "field": None,
            }
        ],
    }


async def test_create_node_promotes_operation_validation_error_fields(
    tmp_path: Path,
) -> None:
    state_path = _write_state(tmp_path, workflow_id="wf")

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(
                200,
                json={"draft_revision": 2, "graph": {"nodes": [], "edges": []}},
            )
        return httpx.Response(
            422,
            json={
                "error": "operation_validation_error",
                "operation_index": 0,
                "code": "duplicate_node_id",
                "detail": "Node id already exists: n1",
            },
        )

    gateway = BioImageFlowMCPGateway(
        state_path=state_path,
        transport=httpx.MockTransport(handler),
    )

    assert await gateway.create_node(
        node_id="n1",
        tool_name="Tool",
        name="Node",
        position=[0, 0],
    ) == {
        "ok": False,
        "status_code": 422,
        "error": "operation_validation_error",
        "operation_index": 0,
        "code": "duplicate_node_id",
        "detail": "Node id already exists: n1",
    }


async def test_create_node_result_surfaces_validation_errors(tmp_path: Path) -> None:
    state_path = _write_state(tmp_path, workflow_id="wf")

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(
                200,
                json={"draft_revision": 2, "graph": {"nodes": [], "edges": []}},
            )
        return httpx.Response(
            200,
            json={
                "workflow_id": "wf",
                "draft_revision": 3,
                "validation": {
                    "valid": False,
                    "errors": [
                        {
                            "type": "missing_tool",
                            "detail": "Tool not found: MissingTool",
                            "node": "n1",
                            "edge_id": None,
                            "field": None,
                        }
                    ],
                },
            },
        )

    gateway = BioImageFlowMCPGateway(
        state_path=state_path,
        transport=httpx.MockTransport(handler),
    )

    result = await gateway.create_node(
        node_id="n1",
        tool_name="MissingTool",
        name="Node",
        position=[0, 0],
    )

    assert result == {
        "ok": True,
        "workflow_id": "wf",
        "draft_revision": 3,
        "validation_valid": False,
        "validation_errors": [
            {
                "type": "missing_tool",
                "detail": "Tool not found: MissingTool",
                "node": "n1",
                "edge_id": None,
                "field": None,
            }
        ],
    }


async def test_run_workflow_returns_compact_error_when_draft_fetch_fails(
    tmp_path: Path,
) -> None:
    state_path = _write_state(tmp_path, workflow_id="missing")
    gateway = BioImageFlowMCPGateway(
        state_path=state_path,
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(404, json={"detail": "Workflow not found"})
        ),
    )

    assert await gateway.run_workflow() == {
        "ok": False,
        "status_code": 404,
        "error": {"detail": "Workflow not found"},
    }


async def test_missing_agent_state_returns_structured_error(tmp_path: Path) -> None:
    gateway = BioImageFlowMCPGateway(state_path=tmp_path / "missing-state.json")

    assert await gateway.get_active_workflow() == {
        "ok": False,
        "error": "agent_state_missing",
        "detail": f"Agent state file not found: {tmp_path / 'missing-state.json'}",
    }


async def test_malformed_agent_state_returns_structured_error(tmp_path: Path) -> None:
    state_path = tmp_path / ".bioimageflow" / "agent-state.json"
    state_path.parent.mkdir()
    state_path.write_text("{not json", encoding="utf-8")
    gateway = BioImageFlowMCPGateway(state_path=state_path)

    result = await gateway.get_active_workflow()

    assert result["ok"] is False
    assert result["error"] == "agent_state_invalid"
    assert "Invalid JSON" in result["detail"]


async def test_backend_unavailable_returns_structured_error(tmp_path: Path) -> None:
    state_path = _write_state(tmp_path, workflow_id="wf")

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    gateway = BioImageFlowMCPGateway(
        state_path=state_path,
        transport=httpx.MockTransport(handler),
    )

    assert await gateway.list_tools() == {
        "ok": False,
        "error": "backend_unavailable",
        "detail": "connection refused",
    }


async def test_backend_timeout_returns_structured_error(tmp_path: Path) -> None:
    state_path = _write_state(tmp_path, workflow_id="wf")

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out", request=request)

    gateway = BioImageFlowMCPGateway(
        state_path=state_path,
        transport=httpx.MockTransport(handler),
    )

    assert await gateway.list_tools() == {
        "ok": False,
        "error": "backend_timeout",
        "detail": "timed out",
    }


async def test_malformed_backend_response_returns_structured_error(
    tmp_path: Path,
) -> None:
    state_path = _write_state(tmp_path, workflow_id="wf")
    gateway = BioImageFlowMCPGateway(
        state_path=state_path,
        transport=httpx.MockTransport(lambda _request: httpx.Response(200, text="not json")),
    )

    assert await gateway.list_tools() == {
        "ok": False,
        "error": "malformed_backend_response",
        "detail": "Backend returned non-JSON response",
        "body": "not json",
    }


def test_mcp_tools_have_descriptions(tmp_path: Path) -> None:
    state_path = _write_state(tmp_path)
    server = create_mcp_server(state_path=state_path, mcp_factory=_FakeFastMCP)

    for tool in server.tools.values():
        assert tool.__doc__
