"""Tests for the thin BioImageFlow MCP transport layer."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx
import pytest

from bioimageflow_server.agent_mcp import (
    BioImageFlowMCPGateway,
    create_mcp_server,
    read_agent_state,
)

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


def test_mcp_tools_have_descriptions(tmp_path: Path) -> None:
    state_path = _write_state(tmp_path)
    server = create_mcp_server(state_path=state_path, mcp_factory=_FakeFastMCP)

    for tool in server.tools.values():
        assert tool.__doc__
