"""Tests for the thin BioImageFlow MCP transport layer."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock

import httpx
import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from bioimageflow_server.app import create_app
from bioimageflow_server.agent_mcp import (
    BioImageFlowMCPGateway,
    SUPPORTED_MCP_TOOLS,
    SUPPORTED_OPERATION_TYPES,
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

    def get_status(self) -> Any:
        class _Status:
            node_statuses: dict[str, Any] = {}

            def model_dump(self) -> dict[str, Any]:
                return {
                    "state": "idle",
                    "last_result": None,
                    "progress": None,
                    "node_statuses": {},
                }

        return _Status()


def _write_state(tmp_path: Path, *, workflow_id: str = "folder/wf") -> Path:
    state = tmp_path / ".bioimageflow" / "agent-state.json"
    state.parent.mkdir()
    state.write_text(
        json.dumps(
            {
                "api_base_url": "http://bif.test/api/v1",
                "active_workflow_id": workflow_id,
                "current_draft_revision": 7,
                "workspace_path": str(tmp_path),
                "workflows_root": str(tmp_path / "workflows"),
                "agent_state_path": str(state),
            }
        ),
        encoding="utf-8",
    )
    return state


def _workflow_info(workflow_id: str, *, display_name: str | None = None) -> dict[str, Any]:
    name = workflow_id.rsplit("/", maxsplit=1)[-1]
    folder = workflow_id.rsplit("/", maxsplit=1)[0] if "/" in workflow_id else ""
    return {
        "id": workflow_id,
        "name": name,
        "folder": folder,
        "display_name": display_name or workflow_id,
        "description": None,
        "path": f"/workspace/workflows/{workflow_id}/workflow.json",
        "storage_path": f"/workspace/results/{workflow_id}",
        "output_path": f"/workspace/results/{workflow_id}",
        "workspace_path": "/workspace",
        "last_modified": "2026-01-01T00:00:00Z",
    }


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
    assert set(server.tools) == set(SUPPORTED_MCP_TOOLS)


async def test_agent_mcp_module_entrypoint_initializes_stdio_server(tmp_path: Path) -> None:
    state_path = _write_state(tmp_path)
    env = {
        "BIOIMAGEFLOW_AGENT_STATE": str(state_path),
        "PYTHONPATH": os.pathsep.join(
            (
                str(Path(__file__).parents[2] / "src"),
                os.environ.get("PYTHONPATH", ""),
            )
        ),
    }
    server = StdioServerParameters(
        command=sys.executable,
        args=["-m", "bioimageflow_server.agent_mcp"],
        cwd=str(tmp_path),
        env=env,
    )

    async with stdio_client(server) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            tools = await session.list_tools()

    assert {tool.name for tool in tools.tools} == set(SUPPORTED_MCP_TOOLS)


async def test_workflow_lifecycle_tools_call_backend_workflow_api(
    tmp_path: Path,
) -> None:
    state_path = _write_state(tmp_path, workflow_id="wf")
    requests: list[tuple[str, str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content.decode() or "{}")
        requests.append((request.method, request.url.path, payload))
        if request.method == "GET" and request.url.path == "/api/v1/workflows":
            return httpx.Response(
                200,
                json=[
                    _workflow_info("wf"),
                    _workflow_info("folder/other", display_name="Other"),
                ],
            )
        if request.method == "GET" and request.url.path == "/api/v1/workflows/wf":
            return httpx.Response(
                200,
                json={
                    "info": _workflow_info("wf"),
                    "graph": {
                        "nodes": [{"id": "load_1"}],
                        "edges": [],
                        "published_inputs": [],
                        "published_outputs": [],
                    },
                    "missing_packages": [],
                    "missing_tools": [],
                },
            )
        if request.method == "POST" and request.url.path == "/api/v1/workflows":
            assert payload == {"name": "new", "display_name": "New"}
            return httpx.Response(200, json=_workflow_info("new", display_name="New"))
        if request.method == "PATCH" and request.url.path == "/api/v1/workflows/wf":
            assert payload == {
                "action": "duplicate",
                "new_name": "copy",
                "display_name": "Copy",
            }
            return httpx.Response(200, json=_workflow_info("copy", display_name="Copy"))
        if request.method == "PATCH" and request.url.path == "/api/v1/workflows/copy":
            assert payload == {
                "action": "update",
                "new_id": "renamed",
                "display_name": "Renamed",
            }
            return httpx.Response(
                200,
                json=_workflow_info("renamed", display_name="Renamed"),
            )
        if request.method == "DELETE" and request.url.path == "/api/v1/workflows/renamed":
            return httpx.Response(200, json={"deleted": True})
        if request.method == "GET" and request.url.path == "/api/v1/workflow-drafts/copy":
            return httpx.Response(
                200,
                json={
                    "workflow_id": "copy",
                    "draft_revision": 3,
                    "dirty_against_saved": False,
                    "validation": {"valid": True, "errors": []},
                    "graph": {"nodes": [], "edges": []},
                },
            )
        return httpx.Response(500, json={"detail": f"Unexpected {request.method} {request.url.path}"})

    gateway = BioImageFlowMCPGateway(
        state_path=state_path,
        transport=httpx.MockTransport(handler),
    )

    context = await gateway.get_workspace_context()
    workflows = await gateway.list_workflows()
    info = await gateway.get_workflow_info("wf", include_graph=True)
    created = await gateway.create_workflow("new", display_name="New")
    duplicate = await gateway.duplicate_workflow(
        "wf",
        "copy",
        display_name="Copy",
        set_active=True,
    )
    renamed = await gateway.rename_workflow("copy", "renamed", display_name="Renamed")
    delete_mismatch = await gateway.delete_workflow("renamed", "wrong")
    deleted = await gateway.delete_workflow("renamed", "renamed")

    assert context == {
        "ok": True,
        "active_workflow_id": "wf",
        "current_draft_revision": 7,
        "workspace_path": str(tmp_path),
        "workflows_root": str(tmp_path / "workflows"),
        "agent_state_path": str(state_path),
        "mcp_contract_version": 2,
        "workflow_count": 2,
        "workflow_ids": ["wf", "folder/other"],
    }
    assert workflows["ok"] is True
    assert workflows["count"] == 2
    assert workflows["workflows"][1]["display_name"] == "Other"
    assert info["ok"] is True
    assert info["graph_summary"] == {
        "node_count": 1,
        "edge_count": 0,
        "published_input_count": 0,
        "published_output_count": 0,
    }
    assert info["graph"]["nodes"] == [{"id": "load_1"}]
    assert created == {
        "ok": True,
        "workflow": {
            "id": "new",
            "name": "new",
            "folder": "",
            "display_name": "New",
            "description": None,
            "storage_path": "/workspace/results/new",
            "output_path": "/workspace/results/new",
            "workspace_path": "/workspace",
            "last_modified": "2026-01-01T00:00:00Z",
        },
    }
    assert duplicate["ok"] is True
    assert duplicate["source_workflow_id"] == "wf"
    assert duplicate["workflow"]["id"] == "copy"
    assert duplicate["active_workflow"] == {
        "ok": True,
        "active_workflow_id": "copy",
        "draft_revision": 3,
        "dirty_against_saved": False,
        "validation": {"valid": True, "error_count": 0},
    }
    assert renamed["ok"] is True
    assert renamed["previous_workflow_id"] == "copy"
    assert renamed["workflow"]["id"] == "renamed"
    assert delete_mismatch == {
        "ok": False,
        "error": "delete_confirmation_mismatch",
        "detail": "confirm_workflow_id must match workflow_id",
        "workflow_id": "renamed",
    }
    assert deleted == {"ok": True, "workflow_id": "renamed", "deleted": True}
    assert requests[-1] == ("DELETE", "/api/v1/workflows/renamed", {})
    assert requests.count(("DELETE", "/api/v1/workflows/renamed", {})) == 1


async def test_workflow_lifecycle_tools_return_compact_backend_errors(
    tmp_path: Path,
) -> None:
    state_path = _write_state(tmp_path, workflow_id="wf")

    gateway = BioImageFlowMCPGateway(
        state_path=state_path,
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(
                423,
                json={"detail": "Workflow editing is locked while execution is running."},
            )
        ),
    )

    result = await gateway.rename_workflow("wf", "renamed")

    assert result == {
        "ok": False,
        "status_code": 423,
        "error": "workflow_locked",
        "detail": "Workflow editing is locked while execution is running.",
    }


async def test_rename_active_workflow_refreshes_agent_state_context(
    tmp_path: Path,
) -> None:
    state_path = _write_state(tmp_path, workflow_id="wf")
    requests: list[tuple[str, str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content.decode() or "{}")
        requests.append((request.method, request.url.path, payload))
        if request.method == "PATCH" and request.url.path == "/api/v1/workflows/wf":
            assert payload == {"action": "update", "new_id": "renamed"}
            return httpx.Response(200, json=_workflow_info("renamed"))
        if request.method == "GET" and request.url.path == "/api/v1/workflow-drafts/renamed":
            return httpx.Response(
                200,
                json={
                    "workflow_id": "wf",
                    "draft_revision": 8,
                    "dirty_against_saved": True,
                    "validation": {"valid": False, "errors": [{"type": "missing_tool"}]},
                },
            )
        return httpx.Response(500, json={"detail": f"Unexpected {request.method} {request.url.path}"})

    gateway = BioImageFlowMCPGateway(
        state_path=state_path,
        transport=httpx.MockTransport(handler),
    )

    result = await gateway.rename_workflow("wf", "renamed")

    assert result == {
        "ok": True,
        "previous_workflow_id": "wf",
        "workflow": {
            "id": "renamed",
            "name": "renamed",
            "folder": "",
            "display_name": "renamed",
            "description": None,
            "storage_path": "/workspace/results/renamed",
            "output_path": "/workspace/results/renamed",
            "workspace_path": "/workspace",
            "last_modified": "2026-01-01T00:00:00Z",
        },
        "active_workflow": {
            "ok": True,
            "active_workflow_id": "renamed",
            "draft_revision": 8,
            "dirty_against_saved": True,
            "validation": {
                "valid": False,
                "error_count": 1,
                "errors": [{"type": "missing_tool"}],
            },
            "draft_workflow_id": "wf",
        },
    }
    assert requests == [
        ("PATCH", "/api/v1/workflows/wf", {"action": "update", "new_id": "renamed"}),
        ("GET", "/api/v1/workflow-drafts/renamed", {}),
    ]


async def test_delete_active_workflow_is_rejected_before_backend_delete(
    tmp_path: Path,
) -> None:
    state_path = _write_state(tmp_path, workflow_id="wf")
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"deleted": True})

    gateway = BioImageFlowMCPGateway(
        state_path=state_path,
        transport=httpx.MockTransport(handler),
    )

    result = await gateway.delete_workflow("wf", "wf")

    assert result == {
        "ok": False,
        "error": "active_workflow_delete_forbidden",
        "detail": "Call set_active_workflow with another workflow before deleting the current active workflow.",
        "workflow_id": "wf",
    }
    assert requests == []


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


async def test_set_node_enabled_calls_backend_operation_api(
    tmp_path: Path,
) -> None:
    state_path = _write_state(tmp_path, workflow_id="wf")
    requests: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content.decode() or "{}")
        if request.method == "GET":
            return httpx.Response(
                200,
                json={"draft_revision": 4, "graph": {"nodes": [], "edges": []}},
            )
        requests.append(payload)
        return httpx.Response(
            200,
            json={
                "workflow_id": "wf",
                "draft_revision": 5,
                "validation": {"valid": True, "errors": []},
            },
        )

    gateway = BioImageFlowMCPGateway(
        state_path=state_path,
        transport=httpx.MockTransport(handler),
    )

    assert await gateway.set_node_enabled(node_id="n1", enabled=False) == {
        "ok": True,
        "workflow_id": "wf",
        "draft_revision": 5,
        "validation_valid": True,
    }
    assert requests == [
        {
            "expected_revision": 4,
            "updated_by": "agent",
            "validate": True,
            "operations": [
                {"type": "set_node_enabled", "node_id": "n1", "enabled": False}
            ],
        }
    ]


async def test_move_node_calls_backend_operation_api(tmp_path: Path) -> None:
    state_path = _write_state(tmp_path, workflow_id="wf")
    requests: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content.decode() or "{}")
        if request.method == "GET":
            return httpx.Response(
                200,
                json={"draft_revision": 8, "graph": {"nodes": [], "edges": []}},
            )
        requests.append(payload)
        return httpx.Response(
            200,
            json={
                "workflow_id": "wf",
                "draft_revision": 9,
                "validation": {"valid": True, "errors": []},
            },
        )

    gateway = BioImageFlowMCPGateway(
        state_path=state_path,
        transport=httpx.MockTransport(handler),
    )

    assert await gateway.move_node(node_id="n1", position=[120, 240]) == {
        "ok": True,
        "workflow_id": "wf",
        "draft_revision": 9,
        "validation_valid": True,
    }
    assert requests == [
        {
            "expected_revision": 8,
            "updated_by": "agent",
            "validate": True,
            "operations": [
                {"type": "move_node", "node_id": "n1", "position": [120, 240]}
            ],
        }
    ]


async def test_move_nodes_calls_backend_operation_api(tmp_path: Path) -> None:
    state_path = _write_state(tmp_path, workflow_id="wf")
    requests: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content.decode() or "{}")
        if request.method == "GET":
            return httpx.Response(
                200,
                json={"draft_revision": 8, "graph": {"nodes": [], "edges": []}},
            )
        requests.append(payload)
        return httpx.Response(
            200,
            json={
                "workflow_id": "wf",
                "draft_revision": 9,
                "validation": {"valid": True, "errors": []},
            },
        )

    gateway = BioImageFlowMCPGateway(
        state_path=state_path,
        transport=httpx.MockTransport(handler),
    )

    assert await gateway.move_nodes(
        moves=[
            {"node_id": "a", "position": [100, 120]},
            {"node_id": "b", "position": [300, 120]},
        ]
    ) == {
        "ok": True,
        "workflow_id": "wf",
        "draft_revision": 9,
        "validation_valid": True,
    }
    assert requests == [
        {
            "expected_revision": 8,
            "updated_by": "agent",
            "validate": True,
            "operations": [
                {
                    "type": "move_nodes",
                    "moves": [
                        {"node_id": "a", "position": [100, 120]},
                        {"node_id": "b", "position": [300, 120]},
                    ],
                }
            ],
        }
    ]


async def test_layout_tools_pass_scope_to_backend_operation_api(tmp_path: Path) -> None:
    state_path = _write_state(tmp_path, workflow_id="wf")
    requests: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content.decode() or "{}")
        if request.method == "GET":
            return httpx.Response(
                200,
                json={"draft_revision": 8, "graph": {"nodes": [], "edges": []}},
            )
        requests.append(payload)
        return httpx.Response(
            200,
            json={
                "workflow_id": "wf",
                "draft_revision": 9,
                "validation": {"valid": True, "errors": []},
            },
        )

    gateway = BioImageFlowMCPGateway(
        state_path=state_path,
        transport=httpx.MockTransport(handler),
    )

    await gateway.move_node(
        node_id="inner",
        position=[100, 120],
        scope={"sub_workflow_path": ["outer"]},
    )
    await gateway.move_nodes(
        moves=[{"node_id": "inner", "position": [300, 120]}],
        scope={"sub_workflow_path": ["outer"]},
    )

    assert [request["operations"][0] for request in requests] == [
        {
            "type": "move_node",
            "node_id": "inner",
            "position": [100, 120],
            "scope": {"sub_workflow_path": ["outer"]},
        },
        {
            "type": "move_nodes",
            "moves": [{"node_id": "inner", "position": [300, 120]}],
            "scope": {"sub_workflow_path": ["outer"]},
        },
    ]


async def test_published_interface_tools_call_backend_operation_api(
    tmp_path: Path,
) -> None:
    state_path = _write_state(tmp_path, workflow_id="wf")
    requests: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content.decode() or "{}")
        if request.method == "GET":
            return httpx.Response(
                200,
                json={"draft_revision": 8, "graph": {"nodes": [], "edges": []}},
            )
        requests.append(payload)
        return httpx.Response(
            200,
            json={
                "workflow_id": "wf",
                "draft_revision": 9,
                "validation": {"valid": True, "errors": []},
            },
        )

    gateway = BioImageFlowMCPGateway(
        state_path=state_path,
        transport=httpx.MockTransport(handler),
    )

    await gateway.set_published_input(
        name="image",
        internal_node_id="n1",
        internal_field="input_image",
        kind="input",
        schema={"type": "ImageFile"},
    )
    await gateway.delete_published_input(name="image")
    await gateway.set_published_output(
        name="mask",
        internal_node_id="n1",
        internal_output="output_image",
        schema={"type": "ImageFile"},
    )
    await gateway.delete_published_output(name="mask")

    assert [request["operations"][0] for request in requests] == [
        {
            "type": "set_published_input",
            "name": "image",
            "internal_node_id": "n1",
            "internal_field": "input_image",
            "kind": "input",
            "schema": {"type": "ImageFile"},
        },
        {"type": "delete_published_input", "name": "image"},
        {
            "type": "set_published_output",
            "name": "mask",
            "internal_node_id": "n1",
            "internal_output": "output_image",
            "schema": {"type": "ImageFile"},
        },
        {"type": "delete_published_output", "name": "mask"},
    ]


async def test_published_interface_mcp_tools_can_clear_nullable_fields(
    tmp_path: Path,
) -> None:
    state_path = _write_state(tmp_path, workflow_id="wf")
    requests: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content.decode() or "{}")
        if request.method == "GET":
            return httpx.Response(
                200,
                json={"draft_revision": 8, "graph": {"nodes": [], "edges": []}},
            )
        requests.append(payload)
        return httpx.Response(
            200,
            json={
                "workflow_id": "wf",
                "draft_revision": 9,
                "validation": {"valid": True, "errors": []},
            },
        )

    gateway = BioImageFlowMCPGateway(
        state_path=state_path,
        transport=httpx.MockTransport(handler),
    )

    await gateway.set_published_input(
        name="image",
        internal_node_id="n1",
        internal_field="input_image",
        kind="input",
        schema=None,
        default=None,
        set_schema=True,
        set_default=True,
    )
    await gateway.set_published_output(
        name="mask",
        internal_node_id="n1",
        internal_output="output_image",
        schema=None,
        set_schema=True,
    )

    assert [request["operations"][0] for request in requests] == [
        {
            "type": "set_published_input",
            "name": "image",
            "internal_node_id": "n1",
            "internal_field": "input_image",
            "kind": "input",
            "schema": None,
            "default": None,
        },
        {
            "type": "set_published_output",
            "name": "mask",
            "internal_node_id": "n1",
            "internal_output": "output_image",
            "schema": None,
        },
    ]


async def test_registered_enable_and_move_tools_delegate_to_backend_operations(
    tmp_path: Path,
) -> None:
    state_path = _write_state(tmp_path, workflow_id="wf")
    requests: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content.decode() or "{}")
        if request.method == "GET":
            return httpx.Response(
                200,
                json={"draft_revision": 11, "graph": {"nodes": [], "edges": []}},
            )
        requests.append(payload)
        return httpx.Response(
            200,
            json={
                "workflow_id": "wf",
                "draft_revision": 12,
                "validation": {"valid": True, "errors": []},
            },
        )

    server = create_mcp_server(
        gateway=BioImageFlowMCPGateway(
            state_path=state_path,
            transport=httpx.MockTransport(handler),
        ),
        mcp_factory=_FakeFastMCP,
    )

    await server.tools["set_node_enabled"](node_id="n1", enabled=True)
    await server.tools["move_node"](node_id="n1", position=[10, 20])
    await server.tools["move_nodes"](
        moves=[
            {"node_id": "n1", "position": [40, 50]},
            {"node_id": "n2", "position": [80, 50]},
        ]
    )
    await server.tools["set_published_output"](
        name="mask",
        internal_node_id="n1",
        internal_output="mask",
        schema={"type": "ImageFile"},
    )

    assert requests == [
        {
            "expected_revision": 11,
            "updated_by": "agent",
            "validate": True,
            "operations": [
                {"type": "set_node_enabled", "node_id": "n1", "enabled": True}
            ],
        },
        {
            "expected_revision": 11,
            "updated_by": "agent",
            "validate": True,
            "operations": [
                {"type": "move_node", "node_id": "n1", "position": [10, 20]}
            ],
        },
        {
            "expected_revision": 11,
            "updated_by": "agent",
            "validate": True,
            "operations": [
                {
                    "type": "move_nodes",
                    "moves": [
                        {"node_id": "n1", "position": [40, 50]},
                        {"node_id": "n2", "position": [80, 50]},
                    ],
                }
            ],
        },
        {
            "expected_revision": 11,
            "updated_by": "agent",
            "validate": True,
            "operations": [
                {
                    "type": "set_published_output",
                    "name": "mask",
                    "internal_node_id": "n1",
                    "internal_output": "mask",
                    "schema": {"type": "ImageFile"},
                }
            ],
        },
    ]


async def test_validation_run_status_and_stop_call_execution_endpoints(
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
        if request.url.path.endswith("/execution/status"):
            return httpx.Response(
                200,
                json={
                    "state": "idle",
                    "last_result": None,
                    "progress": None,
                    "node_statuses": {},
                },
            )
        return httpx.Response(200, json={"status": "stopping"})

    gateway = BioImageFlowMCPGateway(
        state_path=state_path,
        transport=httpx.MockTransport(handler),
    )

    validation = await gateway.validate_workflow()
    run = await gateway.run_workflow(nodes=["n1"])
    status = await gateway.get_execution_status()
    stop = await gateway.stop_execution()

    assert validation == {"ok": True, "valid": True, "error_count": 0}
    assert run == {"ok": True, "status": "started"}
    assert status == {
        "ok": True,
        "state": "idle",
        "last_result": None,
        "progress": None,
        "node_statuses": {},
    }
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
        ("GET", "/api/v1/execution/status", {}),
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

        capabilities = await server.tools["get_bioimageflow_capabilities"]()
        draft_read = await server.tools["get_workflow_draft"](include_graph=True)
        operation_result = await server.tools["apply_workflow_operations"](
            operations=[
                {
                    "type": "create_node",
                    "node_id": "n1",
                    "tool_name": "MissingTool",
                    "name": "Node",
                    "position": [0, 0],
                    "parameters": {},
                }
            ],
        )
        validation = await server.tools["validate_workflow"]()
        run = await server.tools["run_workflow"](nodes=["n1"])
        status = await server.tools["get_execution_status"]()
        stop = await server.tools["stop_execution"]()

    assert capabilities["ok"] is True
    assert capabilities["mcp_contract_version"] == 2
    assert capabilities["active_workflow_id"] == "wf"
    assert capabilities["current_draft_revision"] == 0
    assert capabilities["backend_reachable"] is True
    assert {
        "get_bioimageflow_capabilities",
        "get_workflow_draft",
        "apply_workflow_operations",
        "get_execution_status",
    }.issubset(set(capabilities["supported_tools"]))
    assert set(capabilities["supported_tools"]) == set(SUPPORTED_MCP_TOOLS)
    assert set(capabilities["supported_operation_types"]) == set(SUPPORTED_OPERATION_TYPES)
    assert capabilities["max_operation_batch_size"] == 10
    assert capabilities["supports_execution_status"] is True
    assert capabilities["workflow_management"] == {
        "supports_list": True,
        "supports_create": True,
        "supports_duplicate": True,
        "supports_rename": True,
        "supports_delete": True,
        "supports_set_active": True,
    }
    assert draft_read["ok"] is True
    assert draft_read["workflow_id"] == "wf"
    assert draft_read["draft_revision"] == 0
    assert draft_read["graph_included"] is True
    assert draft_read["graph"] == {
        "nodes": [],
        "edges": [],
        "published_inputs": [],
        "published_outputs": [],
    }
    assert operation_result["ok"] is True
    assert operation_result["draft_revision"] == 1
    assert operation_result["validation_valid"] is False
    assert operation_result["validation_errors"]
    assert "graph" not in operation_result
    assert validation["ok"] is True
    assert validation["valid"] is False
    assert validation["errors"][0]["type"] == "missing_tool"
    assert run == {"ok": True, "status": "started"}
    assert status["ok"] is True
    assert status["state"] == "idle"
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
        "error": "not_found",
        "detail": "no",
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
        "error": "workflow_locked",
        "detail": "locked",
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


async def test_create_node_promotes_draft_revision_conflict(tmp_path: Path) -> None:
    state_path = _write_state(tmp_path, workflow_id="wf")

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(
                200,
                json={"draft_revision": 2, "graph": {"nodes": [], "edges": []}},
            )
        return httpx.Response(
            409,
            json={
                "error": "draft_revision_conflict",
                "detail": "Draft revision conflict",
                "expected_revision": 2,
                "current_revision": 3,
                "current_updated_by": "frontend",
                "current_updated_at": "2026-01-01T00:00:00Z",
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
        "status_code": 409,
        "error": "draft_revision_conflict",
        "detail": "Draft revision conflict",
        "expected_revision": 2,
        "current_revision": 3,
        "current_updated_by": "frontend",
        "current_updated_at": "2026-01-01T00:00:00Z",
    }


async def test_create_node_promotes_workflow_locked(tmp_path: Path) -> None:
    state_path = _write_state(tmp_path, workflow_id="wf")

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(
                200,
                json={"draft_revision": 2, "graph": {"nodes": [], "edges": []}},
            )
        return httpx.Response(
            423,
            json={
                "error": "workflow_locked",
                "detail": "Workflow editing is locked while execution is in progress",
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
        "status_code": 423,
        "error": "workflow_locked",
        "detail": "Workflow editing is locked while execution is in progress",
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


async def test_connect_nodes_returns_structured_error_for_missing_named_fields(
    tmp_path: Path,
) -> None:
    gateway = BioImageFlowMCPGateway(state_path=_write_state(tmp_path, workflow_id="wf"))

    assert await gateway.connect_nodes(
        source_node="source",
        target_node="target",
    ) == {
        "ok": False,
        "error": "invalid_connect_nodes_arguments",
        "detail": (
            "source_output and target_input are required when positional_index "
            "is not provided"
        ),
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
        "error": "not_found",
        "detail": "Workflow not found",
    }


async def test_validation_and_run_return_structured_error_for_missing_graph(
    tmp_path: Path,
) -> None:
    state_path = _write_state(tmp_path, workflow_id="wf")
    gateway = BioImageFlowMCPGateway(
        state_path=state_path,
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(200, json={"draft_revision": 1})
        ),
    )

    expected = {
        "ok": False,
        "error": "malformed_backend_response",
        "detail": "Backend draft response did not include a graph object",
    }
    assert await gateway.validate_workflow() == expected
    assert await gateway.run_workflow() == expected


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


def _contract_draft_response(
    *, workflow_id: str = "folder/wf", revision: int = 6
) -> dict[str, Any]:
    return {
        "draft_version": 1,
        "workflow_id": workflow_id,
        "base_saved_revision": "sha256:abc123",
        "draft_revision": revision,
        "updated_at": "2026-07-01T12:00:00Z",
        "updated_by": "agent",
        "dirty_against_saved": True,
        "graph": {
            "nodes": [
                {
                    "id": "segment_1",
                    "name": "Segment",
                    "tool_name": "SegmentCells",
                    "enabled": False,
                    "position": [10, 20],
                    "parameters": {"threshold": 0.4, "method": "otsu"},
                    "output_templates": {"mask": "mask.tif"},
                    "published_inputs": [{"name": "image"}],
                    "published_outputs": [{"name": "mask"}],
                }
            ],
            "edges": [
                {
                    "id": "edge_1",
                    "source": "load_1",
                    "target": "segment_1",
                    "source_output": "image",
                    "target_input": "image",
                }
            ],
            "published_inputs": [
                {
                    "name": "image",
                    "internal_node_id": "segment_1",
                    "internal_field": "image",
                    "kind": "input",
                    "schema": {"type": "ImageFile"},
                    "default": None,
                }
            ],
            "published_outputs": [
                {
                    "name": "mask",
                    "internal_node_id": "segment_1",
                    "internal_output": "mask",
                    "schema": {"type": "ImageFile"},
                }
            ],
        },
        "validation": {
            "valid": False,
            "errors": [
                {
                    "type": "missing_input",
                    "detail": "Image input is not connected.",
                    "node": "segment_1",
                    "field": "image",
                }
            ],
            "node_statuses": {"segment_1": "invalid"},
        },
    }


def _contract_tool_response() -> dict[str, Any]:
    return {
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
        "outputs": {"mask": {"type": "path", "default": "mask.tif"}},
        "environment": {"status": "ready"},
        "source_kind": "package",
        "editable": False,
    }


async def test_capabilities_include_contract_tools_and_reachable_draft(
    tmp_path: Path,
) -> None:
    state_path = _write_state(tmp_path, workflow_id="folder/wf")

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == "/api/v1/workflow-drafts/folder/wf"
        return httpx.Response(200, json=_contract_draft_response(revision=12))

    gateway = BioImageFlowMCPGateway(
        state_path=state_path,
        transport=httpx.MockTransport(handler),
    )

    result = await gateway.get_bioimageflow_capabilities()

    assert result["ok"] is True
    assert result["mcp_contract_version"] == 2
    assert result["active_workflow_id"] == "folder/wf"
    assert result["current_draft_revision"] == 12
    assert result["backend_reachable"] is True
    assert result["backend_status"] == "reachable"
    assert set(result["supported_tools"]) == set(SUPPORTED_MCP_TOOLS)
    assert set(result["supported_operation_types"]) == set(SUPPORTED_OPERATION_TYPES)
    assert result["max_operation_batch_size"] == 10
    assert result["supports_execution_status"] is True
    assert result["workflow_management"] == {
        "supports_list": True,
        "supports_create": True,
        "supports_duplicate": True,
        "supports_rename": True,
        "supports_delete": True,
        "supports_set_active": True,
    }
    assert "draft_revision_conflict" in result["error_codes"]
    assert "workflow_locked" in result["error_codes"]


async def test_get_workflow_draft_includes_graph_metadata_summary_and_validation(
    tmp_path: Path,
) -> None:
    state_path = _write_state(tmp_path, workflow_id="folder/wf")
    seen_paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_paths.append(request.url.path)
        return httpx.Response(200, json=_contract_draft_response())

    gateway = BioImageFlowMCPGateway(
        state_path=state_path,
        transport=httpx.MockTransport(handler),
    )

    result = await gateway.get_workflow_draft(include_graph=True)

    assert seen_paths == ["/api/v1/workflow-drafts/folder/wf"]
    assert result["ok"] is True
    assert result["workflow_id"] == "folder/wf"
    assert result["draft_version"] == 1
    assert result["draft_revision"] == 6
    assert result["base_saved_revision"] == "sha256:abc123"
    assert result["dirty_against_saved"] is True
    assert result["graph_summary"] == {
        "node_count": 1,
        "edge_count": 1,
        "published_input_count": 1,
        "published_output_count": 1,
    }
    assert result["graph_included"] is True
    assert result["graph"] == _contract_draft_response()["graph"]
    assert result["validation"] == {
        "valid": False,
        "error_count": 1,
        "errors": [
            {
                "type": "missing_input",
                "detail": "Image input is not connected.",
                "node": "segment_1",
                "field": "image",
            }
        ],
        "node_statuses": {"segment_1": "invalid"},
    }


async def test_get_workflow_draft_can_omit_graph(tmp_path: Path) -> None:
    state_path = _write_state(tmp_path, workflow_id="folder/wf")
    gateway = BioImageFlowMCPGateway(
        state_path=state_path,
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(200, json=_contract_draft_response())
        ),
    )

    result = await gateway.get_workflow_draft(include_graph=False)

    assert result["ok"] is True
    assert result["workflow_id"] == "folder/wf"
    assert result["graph_summary"]["node_count"] == 1
    assert result["graph_included"] is False
    assert "graph" not in result


async def test_describe_workflow_compacts_graph_without_parameters(
    tmp_path: Path,
) -> None:
    state_path = _write_state(tmp_path, workflow_id="folder/wf")
    gateway = BioImageFlowMCPGateway(
        state_path=state_path,
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(200, json=_contract_draft_response())
        ),
    )

    result = await gateway.describe_workflow(include_parameters=False)

    assert result["ok"] is True
    assert result["workflow_id"] == "folder/wf"
    assert result["draft_revision"] == 6
    assert result["nodes"] == [
        {
            "id": "segment_1",
            "name": "Segment",
            "tool_name": "SegmentCells",
            "enabled": False,
            "position": [10, 20],
            "parameter_names": ["threshold", "method"],
            "output_template_names": ["mask"],
            "has_sub_workflow": False,
            "published_input_names": ["image"],
            "published_output_names": ["mask"],
        }
    ]
    assert "parameters" not in result["nodes"][0]
    assert result["edges"] == _contract_draft_response()["graph"]["edges"]
    assert result["published_inputs"] == _contract_draft_response()["graph"][
        "published_inputs"
    ]
    assert result["published_outputs"] == _contract_draft_response()["graph"][
        "published_outputs"
    ]


async def test_describe_workflow_includes_parameters_when_requested(
    tmp_path: Path,
) -> None:
    state_path = _write_state(tmp_path, workflow_id="folder/wf")
    gateway = BioImageFlowMCPGateway(
        state_path=state_path,
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(200, json=_contract_draft_response())
        ),
    )

    result = await gateway.describe_workflow(include_parameters=True)

    assert result["nodes"][0]["parameters"] == {
        "threshold": 0.4,
        "method": "otsu",
    }


async def test_describe_bioimageflow_tool_returns_one_normalized_tool(
    tmp_path: Path,
) -> None:
    state_path = _write_state(tmp_path, workflow_id="wf")
    requested_paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested_paths.append(request.url.path)
        return httpx.Response(200, json=[_contract_tool_response()])

    gateway = BioImageFlowMCPGateway(
        state_path=state_path,
        transport=httpx.MockTransport(handler),
    )

    result = await gateway.describe_bioimageflow_tool("SegmentCells")

    assert requested_paths == ["/api/v1/tools"]
    assert result["ok"] is True
    assert result["tool"]["name"] == "SegmentCells"
    assert result["tool"]["inputs"] == _contract_tool_response()["inputs"]
    assert result["tool"]["outputs"] == _contract_tool_response()["outputs"]
    assert result["tool"]["creation"] == {
        "default_parameters": {"method": "otsu"},
        "required_unconnected_inputs": ["threshold"],
        "connectable_inputs": ["image", "method"],
        "default_output_templates": {"mask": "mask.tif"},
    }


async def test_describe_bioimageflow_tool_returns_tool_not_found(
    tmp_path: Path,
) -> None:
    state_path = _write_state(tmp_path, workflow_id="wf")
    gateway = BioImageFlowMCPGateway(
        state_path=state_path,
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(200, json=[_contract_tool_response()])
        ),
    )

    assert await gateway.describe_bioimageflow_tool("MissingTool") == {
        "ok": False,
        "error": "tool_not_found",
        "tool_name": "MissingTool",
    }


async def test_apply_workflow_operations_fetches_revision_and_posts_batch(
    tmp_path: Path,
) -> None:
    state_path = _write_state(tmp_path, workflow_id="folder/wf")
    requests: list[tuple[str, str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content.decode() or "{}")
        requests.append((request.method, request.url.path, payload))
        if request.method == "GET":
            return httpx.Response(200, json=_contract_draft_response(revision=12))
        return httpx.Response(
            200,
            json={
                "workflow_id": "folder/wf",
                "draft_revision": 13,
                "validation": {
                    "valid": False,
                    "errors": [
                        {
                            "type": "missing_tool",
                            "detail": "Tool not found: MissingTool",
                            "node": "new_1",
                            "edge_id": None,
                            "field": None,
                        }
                    ],
                },
                "graph": {"nodes": [{"id": "new_1"}], "edges": []},
            },
        )

    gateway = BioImageFlowMCPGateway(
        state_path=state_path,
        transport=httpx.MockTransport(handler),
    )
    operations = [
        {
            "type": "create_node",
            "node_id": "new_1",
            "tool_name": "MissingTool",
            "name": "New",
            "position": [0, 0],
            "parameters": {},
        },
        {"type": "move_node", "node_id": "new_1", "position": [40, 80]},
    ]

    result = await gateway.apply_workflow_operations(
        operations=operations,
        validate=False,
    )

    assert requests == [
        ("GET", "/api/v1/workflow-drafts/folder/wf", {}),
        (
            "POST",
            "/api/v1/workflow-draft-operations/folder/wf",
            {
                "expected_revision": 12,
                "updated_by": "agent",
                "validate": False,
                "operations": operations,
            },
        ),
    ]
    assert result == {
        "ok": True,
        "workflow_id": "folder/wf",
        "draft_revision": 13,
        "validation_valid": False,
        "validation_errors": [
            {
                "type": "missing_tool",
                "detail": "Tool not found: MissingTool",
                "node": "new_1",
                "edge_id": None,
                "field": None,
            }
        ],
    }
    assert "graph" not in result


def test_mcp_tools_have_descriptions(tmp_path: Path) -> None:
    state_path = _write_state(tmp_path)
    server = create_mcp_server(state_path=state_path, mcp_factory=_FakeFastMCP)

    for tool in server.tools.values():
        assert tool.__doc__
