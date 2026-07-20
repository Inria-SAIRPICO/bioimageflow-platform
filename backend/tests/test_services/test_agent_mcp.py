"""Focused contract tests for the workflow MCP gateway."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx
import pytest

from bioimageflow_server.agent_mcp import (
    SUPPORTED_MCP_TOOLS,
    SUPPORTED_OPERATION_TYPES,
    BioImageFlowMCPGateway,
    create_mcp_server,
)
from tests.graph_factory import graph_document

pytestmark = pytest.mark.anyio


def _state(path: Path) -> Path:
    path.write_text(
        json.dumps(
            {
                "api_base_url": "http://test/api/v1",
                "active_workflow_id": "wf",
                "current_draft_revision": 4,
            }
        ),
        encoding="utf-8",
    )
    return path


def _gateway(
    tmp_path: Path,
    handler: Any,
) -> BioImageFlowMCPGateway:
    return BioImageFlowMCPGateway(
        state_path=_state(tmp_path / "agent-state.json"),
        transport=httpx.MockTransport(handler),
    )


def _draft(graph: dict[str, Any] | None = None, revision: int = 4) -> dict[str, Any]:
    return {
        "workflow_id": "wf",
        "draft_revision": revision,
        "dirty_against_saved": True,
        "graph": graph or graph_document(name="wf", display_name="Workflow"),
        "validation": {"valid": True, "errors": [], "node_statuses": {}},
    }


def test_capability_inventory_uses_only_recursive_workflow_operations() -> None:
    assert "create_tool_node" in SUPPORTED_MCP_TOOLS
    assert "create_workflow_node" in SUPPORTED_MCP_TOOLS
    assert "expose_workflow_input" in SUPPORTED_OPERATION_TYPES
    assert "connect_column_edge" in SUPPORTED_OPERATION_TYPES
    assert "connect_dataframe_edge" in SUPPORTED_OPERATION_TYPES


async def test_create_tool_and_workflow_nodes_send_typed_operations(tmp_path: Path) -> None:
    posted: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(200, json=_draft())
        posted.append(json.loads(request.content))
        return httpx.Response(200, json=_draft(revision=5))

    gateway = _gateway(tmp_path, handler)
    tool = await gateway.create_tool_node(
        node_id="tool_1",
        tool_name="Blur",
        name="Blur",
        position=[0, 0],
        parameters={"sigma": 2},
    )
    child_graph = graph_document(name="child", display_name="Child")
    child = await gateway.create_workflow_node(
        node_id="child_1",
        name="Child",
        position=[100, 0],
        workflow=child_graph,
    )

    assert tool["ok"] is True
    assert child["ok"] is True
    assert posted[0]["operations"][0]["type"] == "create_tool_node"
    assert posted[1]["operations"][0]["type"] == "create_workflow_node"
    assert posted[1]["operations"][0]["workflow"] == child_graph


async def test_interface_tools_address_stable_ids_and_structural_scope(tmp_path: Path) -> None:
    posted: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(200, json=_draft())
        posted.append(json.loads(request.content))
        return httpx.Response(200, json=_draft(revision=5))

    gateway = _gateway(tmp_path, handler)
    scope = {"workflow_path": ["child_1"]}
    await gateway.expose_workflow_input(
        input_port={
            "id": "input-1",
            "name": "image",
            "kind": "field",
            "targets": [
                {
                    "node": "tool_1",
                    "port": {"kind": "field", "name": "image"},
                }
            ],
        },
        scope=scope,
    )
    await gateway.delete_workflow_input(input_id="input-1", scope=scope)
    await gateway.expose_workflow_output(
        output_port={
            "id": "output-1",
            "name": "mask",
            "source": {"node": "tool_1", "column": "mask"},
        },
        scope=scope,
    )
    await gateway.delete_workflow_output(output_id="output-1", scope=scope)

    operations = [payload["operations"][0] for payload in posted]
    assert [item["type"] for item in operations] == [
        "expose_workflow_input",
        "delete_workflow_input",
        "expose_workflow_output",
        "delete_workflow_output",
    ]
    assert all(item["scope"] == scope for item in operations)
    assert operations[1]["input_id"] == "input-1"
    assert operations[3]["output_id"] == "output-1"


async def test_connections_select_explicit_edge_variant(tmp_path: Path) -> None:
    posted: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(200, json=_draft())
        posted.append(json.loads(request.content))
        return httpx.Response(200, json=_draft(revision=5))

    gateway = _gateway(tmp_path, handler)
    await gateway.connect_nodes(
        source_node="a",
        target_node="b",
        source_output="image",
        target_input="input-1",
    )
    await gateway.connect_nodes(
        source_node="a",
        target_node="b",
        target_position=0,
    )

    operations = [payload["operations"][0] for payload in posted]
    assert operations[0]["type"] == "connect_column_edge"
    assert operations[1]["type"] == "connect_dataframe_edge"
    assert operations[1]["target_position"] == 0


async def test_describe_workflow_reports_recursive_node_and_interface(tmp_path: Path) -> None:
    child_graph = graph_document(
        name="child",
        display_name="Child",
        interface={
            "inputs": [
                {
                    "id": "input-1",
                    "name": "image",
                    "kind": "field",
                    "targets": [],
                }
            ],
            "outputs": [],
        },
    )
    graph = graph_document(
        name="wf",
        display_name="Workflow",
        nodes=[
            {
                "type": "workflow",
                "id": "child_1",
                "name": "Child instance",
                "position": [0, 0],
                "workflow": child_graph,
                "bindings": {},
            }
        ],
    )

    gateway = _gateway(
        tmp_path,
        lambda _request: httpx.Response(200, json=_draft(graph)),
    )
    result = await gateway.describe_workflow()

    assert result["interface"] == {"inputs": [], "outputs": []}
    assert result["nodes"][0]["type"] == "workflow"
    assert result["nodes"][0]["workflow_input_ids"] == ["input-1"]


class _Registrar:
    def __init__(self, _name: str) -> None:
        self.names: list[str] = []

    def tool(self, **_kwargs: Any):
        def decorate(function: Any) -> Any:
            self.names.append(function.__name__)
            return function

        return decorate


def test_server_registration_matches_declared_inventory(tmp_path: Path) -> None:
    server = create_mcp_server(
        state_path=_state(tmp_path / "agent-state.json"),
        mcp_factory=_Registrar,
    )
    assert isinstance(server, _Registrar)
    assert set(server.names) == set(SUPPORTED_MCP_TOOLS)
    assert len(server.names) == len(SUPPORTED_MCP_TOOLS)


async def test_missing_agent_state_is_machine_readable(tmp_path: Path) -> None:
    gateway = BioImageFlowMCPGateway(state_path=tmp_path / "missing.json")
    result = await gateway.get_active_workflow()
    assert result["ok"] is False
    assert result["error"] == "agent_state_missing"
