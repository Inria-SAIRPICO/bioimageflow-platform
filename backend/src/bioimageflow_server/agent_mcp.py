"""MCP tools for agent operation against a running BioImageFlow workspace."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from json import JSONDecodeError
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import quote

import httpx
from pydantic import BaseModel, ValidationError


class AgentState(BaseModel):
    api_base_url: str
    active_workflow_id: str
    current_draft_revision: int | None = None


class ToolRegistrar(Protocol):
    def tool(self, **kwargs: Any) -> Any: ...


SUPPORTED_MCP_TOOLS = [
    "get_bioimageflow_capabilities",
    "get_active_workflow",
    "get_workflow_draft",
    "describe_workflow",
    "list_tools",
    "describe_bioimageflow_tool",
    "apply_workflow_operations",
    "create_node",
    "delete_node",
    "rename_node",
    "update_node_parameters",
    "set_node_enabled",
    "move_node",
    "move_nodes",
    "set_published_input",
    "delete_published_input",
    "set_published_output",
    "delete_published_output",
    "connect_nodes",
    "delete_edge",
    "validate_workflow",
    "run_workflow",
    "get_execution_status",
    "stop_execution",
]

SUPPORTED_OPERATION_TYPES = [
    "create_node",
    "delete_node",
    "rename_node",
    "update_node_parameters",
    "set_node_enabled",
    "move_node",
    "move_nodes",
    "set_published_input",
    "delete_published_input",
    "set_published_output",
    "delete_published_output",
    "connect_column_ref",
    "connect_positional",
    "delete_edge",
]

MCP_ERROR_CODES = [
    "agent_state_missing",
    "agent_state_invalid",
    "backend_timeout",
    "backend_unavailable",
    "malformed_backend_response",
    "operation_validation_error",
    "draft_revision_conflict",
    "workflow_locked",
]


def default_state_path() -> Path:
    configured = os.environ.get("BIOIMAGEFLOW_AGENT_STATE")
    if configured:
        return Path(configured)
    return Path.cwd() / ".bioimageflow" / "agent-state.json"


def read_agent_state(path: Path | None = None) -> AgentState:
    state_path = path or default_state_path()
    return AgentState.model_validate_json(state_path.read_text(encoding="utf-8"))


@dataclass
class BioImageFlowMCPGateway:
    """Thin REST transport used by MCP tools."""

    state_path: Path | None = None
    transport: httpx.AsyncBaseTransport | None = None

    async def get_bioimageflow_capabilities(self) -> dict[str, Any]:
        state = _read_state_or_error(self.state_path)
        if _is_error(state):
            return state
        draft = await self._draft(state)
        payload: dict[str, Any] = {
            "ok": not _is_error(draft),
            "mcp_contract_version": 2,
            "active_workflow_id": state.active_workflow_id,
            "current_draft_revision": state.current_draft_revision,
            "supported_tools": SUPPORTED_MCP_TOOLS,
            "supported_operation_types": SUPPORTED_OPERATION_TYPES,
            "max_operation_batch_size": 10,
            "supports_execution_status": True,
            "error_codes": MCP_ERROR_CODES,
            "backend_reachable": not _is_error(draft),
            "backend_status": "reachable",
        }
        if _is_error(draft):
            payload["backend_reachable"] = "status_code" in draft
            payload["backend_status"] = (
                "error_response" if payload["backend_reachable"] else "unreachable"
            )
            payload["backend_error"] = draft
            return payload
        payload["current_draft_revision"] = draft.get(
            "draft_revision", state.current_draft_revision
        )
        return payload

    async def get_active_workflow(self) -> dict[str, Any]:
        state = _read_state_or_error(self.state_path)
        if _is_error(state):
            return state
        return {
            "ok": True,
            "api_base_url": state.api_base_url,
            "active_workflow_id": state.active_workflow_id,
            "current_draft_revision": state.current_draft_revision,
        }

    async def list_tools(self) -> dict[str, Any]:
        tools = await self._request("GET", "/tools")
        if _is_error(tools):
            return tools
        return {
            "ok": True,
            "count": len(tools),
            "tools": [_tool_discovery_result(tool) for tool in tools],
        }

    async def get_workflow_draft(self, include_graph: bool = True) -> dict[str, Any]:
        state = _read_state_or_error(self.state_path)
        if _is_error(state):
            return state
        draft = await self._draft(state)
        if _is_error(draft):
            return draft
        graph = _draft_graph(draft)
        payload = {
            "ok": True,
            **_draft_metadata(draft),
            "graph_summary": _graph_summary(graph),
            "graph_included": include_graph,
            "validation": _validation_summary(draft.get("validation")),
        }
        if include_graph:
            payload["graph"] = graph
        return payload

    async def describe_workflow(
        self, include_parameters: bool = False
    ) -> dict[str, Any]:
        state = _read_state_or_error(self.state_path)
        if _is_error(state):
            return state
        draft = await self._draft(state)
        if _is_error(draft):
            return draft
        graph = _draft_graph(draft)
        return {
            "ok": True,
            "workflow_id": draft.get("workflow_id", state.active_workflow_id),
            "draft_revision": draft.get("draft_revision"),
            "dirty_against_saved": draft.get("dirty_against_saved"),
            "nodes": [
                _compact_node(node, include_parameters=include_parameters)
                for node in graph.get("nodes", [])
            ],
            "edges": graph.get("edges", []),
            "published_inputs": [
                _compact_published_input(item)
                for item in graph.get("published_inputs", [])
            ],
            "published_outputs": [
                _compact_published_output(item)
                for item in graph.get("published_outputs", [])
            ],
            "validation": _validation_summary(draft.get("validation")),
        }

    async def describe_bioimageflow_tool(self, tool_name: str) -> dict[str, Any]:
        tools = await self._request("GET", "/tools")
        if _is_error(tools):
            return tools
        for tool in tools:
            normalized = _tool_discovery_result(tool)
            if normalized.get("name") == tool_name:
                return {"ok": True, "tool": normalized}
        return {
            "ok": False,
            "error": "tool_not_found",
            "tool_name": tool_name,
        }

    async def apply_workflow_operations(
        self,
        operations: list[dict[str, Any]],
        expected_revision: int | None = None,
        validate: bool = True,
    ) -> dict[str, Any]:
        return await self._apply_operations(
            operations,
            expected_revision=expected_revision,
            validate=validate,
        )

    async def create_node(
        self,
        *,
        node_id: str,
        tool_name: str,
        name: str,
        position: list[float],
        parameters: dict[str, Any] | None = None,
        expected_revision: int | None = None,
    ) -> dict[str, Any]:
        return await self._apply_operations(
            [
                {
                    "type": "create_node",
                    "node_id": node_id,
                    "tool_name": tool_name,
                    "name": name,
                    "position": position,
                    "parameters": parameters or {},
                }
            ],
            expected_revision=expected_revision,
        )

    async def delete_node(
        self,
        *,
        node_id: str,
        expected_revision: int | None = None,
    ) -> dict[str, Any]:
        return await self._apply_operations(
            [{"type": "delete_node", "node_id": node_id}],
            expected_revision=expected_revision,
        )

    async def rename_node(
        self,
        *,
        node_id: str,
        name: str,
        expected_revision: int | None = None,
    ) -> dict[str, Any]:
        return await self._apply_operations(
            [{"type": "rename_node", "node_id": node_id, "name": name}],
            expected_revision=expected_revision,
        )

    async def update_node_parameters(
        self,
        *,
        node_id: str,
        parameters: dict[str, Any],
        expected_revision: int | None = None,
    ) -> dict[str, Any]:
        return await self._apply_operations(
            [
                {
                    "type": "update_node_parameters",
                    "node_id": node_id,
                    "parameters": parameters,
                }
            ],
            expected_revision=expected_revision,
        )

    async def set_node_enabled(
        self,
        *,
        node_id: str,
        enabled: bool,
        expected_revision: int | None = None,
    ) -> dict[str, Any]:
        return await self._apply_operations(
            [
                {
                    "type": "set_node_enabled",
                    "node_id": node_id,
                    "enabled": enabled,
                }
            ],
            expected_revision=expected_revision,
        )

    async def move_node(
        self,
        *,
        node_id: str,
        position: list[float],
        scope: dict[str, Any] | None = None,
        expected_revision: int | None = None,
    ) -> dict[str, Any]:
        operation: dict[str, Any] = {
            "type": "move_node",
            "node_id": node_id,
            "position": position,
        }
        if scope is not None:
            operation["scope"] = scope
        return await self._apply_operations(
            [operation],
            expected_revision=expected_revision,
        )

    async def move_nodes(
        self,
        *,
        moves: list[dict[str, Any]],
        scope: dict[str, Any] | None = None,
        expected_revision: int | None = None,
    ) -> dict[str, Any]:
        operation: dict[str, Any] = {"type": "move_nodes", "moves": moves}
        if scope is not None:
            operation["scope"] = scope
        return await self._apply_operations(
            [operation],
            expected_revision=expected_revision,
        )

    async def set_published_input(
        self,
        *,
        name: str,
        internal_node_id: str,
        internal_field: str,
        kind: str,
        schema: dict[str, Any] | None = None,
        default: Any | None = None,
        set_schema: bool = False,
        set_default: bool = False,
        expected_revision: int | None = None,
    ) -> dict[str, Any]:
        operation: dict[str, Any] = {
            "type": "set_published_input",
            "name": name,
            "internal_node_id": internal_node_id,
            "internal_field": internal_field,
            "kind": kind,
        }
        if schema is not None or set_schema:
            operation["schema"] = schema
        if default is not None or set_default:
            operation["default"] = default
        return await self._apply_operations(
            [operation],
            expected_revision=expected_revision,
        )

    async def delete_published_input(
        self,
        *,
        name: str,
        expected_revision: int | None = None,
    ) -> dict[str, Any]:
        return await self._apply_operations(
            [{"type": "delete_published_input", "name": name}],
            expected_revision=expected_revision,
        )

    async def set_published_output(
        self,
        *,
        name: str,
        internal_node_id: str,
        internal_output: str,
        schema: dict[str, Any] | None = None,
        set_schema: bool = False,
        expected_revision: int | None = None,
    ) -> dict[str, Any]:
        operation: dict[str, Any] = {
            "type": "set_published_output",
            "name": name,
            "internal_node_id": internal_node_id,
            "internal_output": internal_output,
        }
        if schema is not None or set_schema:
            operation["schema"] = schema
        return await self._apply_operations(
            [operation],
            expected_revision=expected_revision,
        )

    async def delete_published_output(
        self,
        *,
        name: str,
        expected_revision: int | None = None,
    ) -> dict[str, Any]:
        return await self._apply_operations(
            [{"type": "delete_published_output", "name": name}],
            expected_revision=expected_revision,
        )

    async def connect_nodes(
        self,
        *,
        source_node: str,
        target_node: str,
        source_output: str | None = None,
        target_input: str | None = None,
        positional_index: int | None = None,
        edge_id: str | None = None,
        expected_revision: int | None = None,
    ) -> dict[str, Any]:
        if positional_index is not None:
            operation: dict[str, Any] = {
                "type": "connect_positional",
                "source_node": source_node,
                "target_node": target_node,
                "positional_index": positional_index,
            }
        else:
            if source_output is None or target_input is None:
                return {
                    "ok": False,
                    "error": "invalid_connect_nodes_arguments",
                    "detail": (
                        "source_output and target_input are required when "
                        "positional_index is not provided"
                    ),
                }
            operation = {
                "type": "connect_column_ref",
                "source_node": source_node,
                "target_node": target_node,
                "source_output": source_output,
                "target_input": target_input,
            }
        if edge_id is not None:
            operation["edge_id"] = edge_id
        return await self._apply_operations(
            [operation],
            expected_revision=expected_revision,
        )

    async def delete_edge(
        self,
        *,
        edge_id: str,
        expected_revision: int | None = None,
    ) -> dict[str, Any]:
        return await self._apply_operations(
            [{"type": "delete_edge", "edge_id": edge_id}],
            expected_revision=expected_revision,
        )

    async def validate_workflow(self) -> dict[str, Any]:
        state = _read_state_or_error(self.state_path)
        if _is_error(state):
            return state
        draft = await self._draft(state)
        if _is_error(draft):
            return draft
        graph = _draft_graph_or_error(draft)
        if _is_error(graph):
            return graph
        result = await self._request(
            "PUT",
            "/graph",
            json={"graph": graph, "workflow_name": state.active_workflow_id},
        )
        if _is_error(result):
            return result
        errors = result.get("errors") or []
        payload = {
            "ok": True,
            "valid": bool(result.get("valid")),
            "error_count": len(errors),
        }
        if errors:
            payload["errors"] = errors
        return payload

    async def run_workflow(self, *, nodes: list[str] | None = None) -> dict[str, Any]:
        state = _read_state_or_error(self.state_path)
        if _is_error(state):
            return state
        draft = await self._draft(state)
        if _is_error(draft):
            return draft
        graph = _draft_graph_or_error(draft)
        if _is_error(graph):
            return graph
        payload: dict[str, Any] = {
            "graph": graph,
            "workflow_name": state.active_workflow_id,
        }
        if nodes is not None:
            payload["nodes"] = nodes
        result = await self._request("POST", "/execution/run", json=payload)
        if _is_error(result):
            return result
        return {"ok": True, **result}

    async def get_execution_status(self) -> dict[str, Any]:
        result = await self._request("GET", "/execution/status")
        if _is_error(result):
            return result
        return {"ok": True, **result}

    async def stop_execution(self) -> dict[str, Any]:
        result = await self._request("POST", "/execution/stop")
        if _is_error(result):
            return result
        return {"ok": True, **result}

    async def _apply_operations(
        self,
        operations: list[dict[str, Any]],
        *,
        expected_revision: int | None,
        validate: bool = True,
    ) -> dict[str, Any]:
        state = _read_state_or_error(self.state_path)
        if _is_error(state):
            return state
        if expected_revision is None:
            draft = await self._draft(state)
            if _is_error(draft):
                return draft
            expected_revision = int(draft["draft_revision"])
        result = await self._request(
            "POST",
            f"/workflow-draft-operations/{_workflow_url(state.active_workflow_id)}",
            json={
                "expected_revision": expected_revision,
                "updated_by": "agent",
                "validate": validate,
                "operations": operations,
            },
        )
        return _operation_result(result)

    async def _draft(self, state: AgentState) -> dict[str, Any]:
        return await self._request(
            "GET",
            f"/workflow-drafts/{_workflow_url(state.active_workflow_id)}",
        )

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
    ) -> Any:
        state = _read_state_or_error(self.state_path)
        if _is_error(state):
            return state
        url = f"{state.api_base_url.rstrip('/')}{path}"
        try:
            async with httpx.AsyncClient(transport=self.transport, timeout=10.0) as client:
                response = await client.request(method, url, json=json)
        except httpx.TimeoutException as exc:
            return {
                "ok": False,
                "error": "backend_timeout",
                "detail": str(exc),
            }
        except httpx.TransportError as exc:
            return {
                "ok": False,
                "error": "backend_unavailable",
                "detail": str(exc),
            }
        if response.is_error:
            return _http_error_result(response)
        try:
            return response.json()
        except JSONDecodeError:
            return {
                "ok": False,
                "error": "malformed_backend_response",
                "detail": "Backend returned non-JSON response",
                "body": response.text,
            }


def create_mcp_server(
    *,
    state_path: Path | None = None,
    gateway: BioImageFlowMCPGateway | None = None,
    mcp_factory: Any | None = None,
) -> ToolRegistrar:
    if mcp_factory is None:
        from mcp.server.fastmcp import FastMCP

        mcp_factory = FastMCP
    server = mcp_factory("BioImageFlow")
    gateway = gateway or BioImageFlowMCPGateway(state_path=state_path)

    @server.tool()
    async def get_bioimageflow_capabilities() -> dict[str, Any]:
        """Return the BioImageFlow MCP contract for this workspace."""
        return await gateway.get_bioimageflow_capabilities()

    @server.tool()
    async def get_active_workflow() -> dict[str, Any]:
        """Return the active workflow id and current draft revision."""
        return await gateway.get_active_workflow()

    @server.tool()
    async def list_tools() -> dict[str, Any]:
        """List available BioImageFlow tool schemas."""
        return await gateway.list_tools()

    @server.tool()
    async def get_workflow_draft(include_graph: bool = True) -> dict[str, Any]:
        """Return the active workflow draft metadata, graph summary, and validation."""
        return await gateway.get_workflow_draft(include_graph=include_graph)

    @server.tool()
    async def describe_workflow(
        include_parameters: bool = False,
    ) -> dict[str, Any]:
        """Return a compact description of the active workflow draft."""
        return await gateway.describe_workflow(include_parameters=include_parameters)

    @server.tool()
    async def describe_bioimageflow_tool(tool_name: str) -> dict[str, Any]:
        """Return one BioImageFlow tool definition by exact registry name."""
        return await gateway.describe_bioimageflow_tool(tool_name=tool_name)

    @server.tool()
    async def apply_workflow_operations(
        operations: list[dict[str, Any]],
        expected_revision: int | None = None,
        validate: bool = True,
    ) -> dict[str, Any]:
        """Apply one batch of workflow draft operations."""
        return await gateway.apply_workflow_operations(
            operations=operations,
            expected_revision=expected_revision,
            validate=validate,
        )

    @server.tool()
    async def create_node(
        node_id: str,
        tool_name: str,
        name: str,
        position: list[float],
        parameters: dict[str, Any] | None = None,
        expected_revision: int | None = None,
    ) -> dict[str, Any]:
        """Create one workflow node."""
        return await gateway.create_node(
            node_id=node_id,
            tool_name=tool_name,
            name=name,
            position=position,
            parameters=parameters,
            expected_revision=expected_revision,
        )

    @server.tool()
    async def delete_node(
        node_id: str,
        expected_revision: int | None = None,
    ) -> dict[str, Any]:
        """Delete one workflow node."""
        return await gateway.delete_node(
            node_id=node_id,
            expected_revision=expected_revision,
        )

    @server.tool()
    async def rename_node(
        node_id: str,
        name: str,
        expected_revision: int | None = None,
    ) -> dict[str, Any]:
        """Rename one workflow node."""
        return await gateway.rename_node(
            node_id=node_id,
            name=name,
            expected_revision=expected_revision,
        )

    @server.tool()
    async def update_node_parameters(
        node_id: str,
        parameters: dict[str, Any],
        expected_revision: int | None = None,
    ) -> dict[str, Any]:
        """Shallow-patch one node parameter mapping."""
        return await gateway.update_node_parameters(
            node_id=node_id,
            parameters=parameters,
            expected_revision=expected_revision,
        )

    @server.tool()
    async def set_node_enabled(
        node_id: str,
        enabled: bool,
        expected_revision: int | None = None,
    ) -> dict[str, Any]:
        """Enable or disable one workflow node."""
        return await gateway.set_node_enabled(
            node_id=node_id,
            enabled=enabled,
            expected_revision=expected_revision,
        )

    @server.tool()
    async def move_node(
        node_id: str,
        position: list[float],
        scope: dict[str, Any] | None = None,
        expected_revision: int | None = None,
    ) -> dict[str, Any]:
        """Move one workflow node on the canvas."""
        return await gateway.move_node(
            node_id=node_id,
            position=position,
            scope=scope,
            expected_revision=expected_revision,
        )

    @server.tool()
    async def move_nodes(
        moves: list[dict[str, Any]],
        scope: dict[str, Any] | None = None,
        expected_revision: int | None = None,
    ) -> dict[str, Any]:
        """Move multiple workflow nodes on the canvas."""
        return await gateway.move_nodes(
            moves=moves,
            scope=scope,
            expected_revision=expected_revision,
        )

    @server.tool()
    async def set_published_input(
        name: str,
        internal_node_id: str,
        internal_field: str,
        kind: str,
        schema: dict[str, Any] | None = None,
        default: Any | None = None,
        set_schema: bool = False,
        set_default: bool = False,
        expected_revision: int | None = None,
    ) -> dict[str, Any]:
        """Create or update a published workflow input."""
        return await gateway.set_published_input(
            name=name,
            internal_node_id=internal_node_id,
            internal_field=internal_field,
            kind=kind,
            schema=schema,
            default=default,
            set_schema=set_schema,
            set_default=set_default,
            expected_revision=expected_revision,
        )

    @server.tool()
    async def delete_published_input(
        name: str,
        expected_revision: int | None = None,
    ) -> dict[str, Any]:
        """Delete a published workflow input."""
        return await gateway.delete_published_input(
            name=name,
            expected_revision=expected_revision,
        )

    @server.tool()
    async def set_published_output(
        name: str,
        internal_node_id: str,
        internal_output: str,
        schema: dict[str, Any] | None = None,
        set_schema: bool = False,
        expected_revision: int | None = None,
    ) -> dict[str, Any]:
        """Create or update a published workflow output."""
        return await gateway.set_published_output(
            name=name,
            internal_node_id=internal_node_id,
            internal_output=internal_output,
            schema=schema,
            set_schema=set_schema,
            expected_revision=expected_revision,
        )

    @server.tool()
    async def delete_published_output(
        name: str,
        expected_revision: int | None = None,
    ) -> dict[str, Any]:
        """Delete a published workflow output."""
        return await gateway.delete_published_output(
            name=name,
            expected_revision=expected_revision,
        )

    @server.tool()
    async def connect_nodes(
        source_node: str,
        target_node: str,
        source_output: str | None = None,
        target_input: str | None = None,
        positional_index: int | None = None,
        edge_id: str | None = None,
        expected_revision: int | None = None,
    ) -> dict[str, Any]:
        """Connect two nodes."""
        return await gateway.connect_nodes(
            source_node=source_node,
            target_node=target_node,
            source_output=source_output,
            target_input=target_input,
            positional_index=positional_index,
            edge_id=edge_id,
            expected_revision=expected_revision,
        )

    @server.tool()
    async def delete_edge(
        edge_id: str,
        expected_revision: int | None = None,
    ) -> dict[str, Any]:
        """Delete one workflow edge."""
        return await gateway.delete_edge(
            edge_id=edge_id,
            expected_revision=expected_revision,
        )

    @server.tool()
    async def validate_workflow() -> dict[str, Any]:
        """Validate the active workflow draft."""
        return await gateway.validate_workflow()

    @server.tool()
    async def run_workflow(nodes: list[str] | None = None) -> dict[str, Any]:
        """Run the active workflow draft."""
        return await gateway.run_workflow(nodes=nodes)

    @server.tool()
    async def get_execution_status() -> dict[str, Any]:
        """Return current execution state, progress, and latest result."""
        return await gateway.get_execution_status()

    @server.tool()
    async def stop_execution() -> dict[str, Any]:
        """Stop the current execution."""
        return await gateway.stop_execution()

    return server


def main() -> None:
    server = create_mcp_server()
    run = getattr(server, "run")
    run()


def _operation_result(result: dict[str, Any]) -> dict[str, Any]:
    if result.get("ok") is False:
        return result
    validation = result.get("validation") or {}
    validation_errors = validation.get("errors") or []
    payload = {
        "ok": True,
        "workflow_id": result.get("workflow_id"),
        "draft_revision": result.get("draft_revision"),
        "validation_valid": validation.get("valid"),
    }
    if validation_errors:
        payload["validation_errors"] = validation_errors
    return payload


def _draft_metadata(draft: dict[str, Any]) -> dict[str, Any]:
    return {
        key: draft.get(key)
        for key in (
            "draft_version",
            "workflow_id",
            "base_saved_revision",
            "draft_revision",
            "updated_at",
            "updated_by",
            "dirty_against_saved",
        )
        if key in draft
    }


def _draft_graph(draft: dict[str, Any]) -> dict[str, Any]:
    graph = draft.get("graph")
    if isinstance(graph, dict):
        return graph
    return {}


def _draft_graph_or_error(draft: dict[str, Any]) -> dict[str, Any]:
    graph = draft.get("graph")
    if isinstance(graph, dict):
        return graph
    return {
        "ok": False,
        "error": "malformed_backend_response",
        "detail": "Backend draft response did not include a graph object",
    }


def _graph_summary(graph: dict[str, Any]) -> dict[str, int]:
    return {
        "node_count": len(graph.get("nodes") or []),
        "edge_count": len(graph.get("edges") or []),
        "published_input_count": len(graph.get("published_inputs") or []),
        "published_output_count": len(graph.get("published_outputs") or []),
    }


def _validation_summary(validation: Any) -> dict[str, Any]:
    if not isinstance(validation, dict):
        return {"valid": None, "error_count": 0}
    errors = validation.get("errors") or []
    payload = {
        "valid": validation.get("valid"),
        "error_count": len(errors),
    }
    if errors:
        payload["errors"] = errors
    if "node_statuses" in validation:
        payload["node_statuses"] = validation.get("node_statuses") or {}
    return payload


def _compact_node(
    node: dict[str, Any], *, include_parameters: bool = False
) -> dict[str, Any]:
    parameters = node.get("parameters") or {}
    output_templates = node.get("output_templates") or {}
    payload = {
        "id": node.get("id"),
        "name": node.get("name"),
        "tool_name": node.get("tool_name"),
        "enabled": node.get("enabled", True),
        "position": node.get("position"),
        "parameter_names": list(parameters),
        "output_template_names": list(output_templates),
        "has_sub_workflow": node.get("sub_workflow") is not None,
        "published_input_names": [
            item.get("name")
            for item in node.get("published_inputs", [])
            if isinstance(item, dict)
        ],
        "published_output_names": [
            item.get("name")
            for item in node.get("published_outputs", [])
            if isinstance(item, dict)
        ],
    }
    if include_parameters:
        payload["parameters"] = parameters
    return payload


def _compact_published_input(item: dict[str, Any]) -> dict[str, Any]:
    return {
        key: item.get(key)
        for key in (
            "name",
            "internal_node_id",
            "internal_field",
            "kind",
            "schema",
            "default",
        )
        if key in item
    }


def _compact_published_output(item: dict[str, Any]) -> dict[str, Any]:
    return {
        key: item.get(key)
        for key in ("name", "internal_node_id", "internal_output", "schema")
        if key in item
    }


def _read_state_or_error(path: Path | None) -> AgentState | dict[str, Any]:
    state_path = path or default_state_path()
    try:
        return read_agent_state(state_path)
    except FileNotFoundError:
        return {
            "ok": False,
            "error": "agent_state_missing",
            "detail": f"Agent state file not found: {state_path}",
        }
    except (OSError, JSONDecodeError, ValidationError) as exc:
        return {
            "ok": False,
            "error": "agent_state_invalid",
            "detail": str(exc),
        }


def _http_error_result(response: httpx.Response) -> dict[str, Any]:
    payload = _json_or_text(response)
    if isinstance(payload, dict) and payload.get("error") == "operation_validation_error":
        result: dict[str, Any] = {
            "ok": False,
            "status_code": response.status_code,
            "error": payload["error"],
        }
        for key in ("operation_index", "code", "detail"):
            if key in payload:
                result[key] = payload[key]
        return result
    if isinstance(payload, dict) and payload.get("error") in {
        "draft_revision_conflict",
        "workflow_locked",
    }:
        return {
            "ok": False,
            "status_code": response.status_code,
            **payload,
        }
    return {
        "ok": False,
        "status_code": response.status_code,
        "error": payload,
    }


def _tool_discovery_result(tool: dict[str, Any]) -> dict[str, Any]:
    inputs = tool.get("inputs") or {}
    outputs = tool.get("outputs") or {}
    result = {
        "name": tool.get("name"),
        "display_name": tool.get("display_name"),
        "documentation": tool.get("documentation", ""),
        "package": tool.get("package"),
        "package_version": tool.get("package_version"),
        "tool_type": tool.get("tool_type"),
        "accepts_upstream": tool.get("accepts_upstream"),
        "dynamic_outputs": tool.get("dynamic_outputs"),
        "dataframe_output": tool.get("dataframe_output"),
        "tags": tool.get("tags") or [],
        "categories": tool.get("categories") or [],
        "inputs": inputs,
        "outputs": outputs,
        "environment": tool.get("environment"),
        "source_kind": tool.get("source_kind"),
        "editable": tool.get("editable"),
    }
    result["creation"] = {
        "default_parameters": _default_parameters(inputs),
        "required_unconnected_inputs": _required_unconnected_inputs(inputs),
        "connectable_inputs": _connectable_inputs(inputs),
        "default_output_templates": _default_output_templates(outputs),
    }
    return result


def _default_parameters(inputs: dict[str, Any]) -> dict[str, Any]:
    return {
        name: schema.get("default")
        for name, schema in inputs.items()
        if isinstance(schema, dict) and schema.get("default") is not None
    }


def _required_unconnected_inputs(inputs: dict[str, Any]) -> list[str]:
    return [
        name
        for name, schema in inputs.items()
        if isinstance(schema, dict)
        and schema.get("required") is True
        and schema.get("connectable") != "by_default"
        and schema.get("default") is None
    ]


def _connectable_inputs(inputs: dict[str, Any]) -> list[str]:
    return [
        name
        for name, schema in inputs.items()
        if isinstance(schema, dict) and schema.get("connectable") != "never"
    ]


def _default_output_templates(outputs: dict[str, Any]) -> dict[str, str]:
    templates: dict[str, str] = {}
    for name, schema in outputs.items():
        if not isinstance(schema, dict):
            continue
        default = schema.get("default")
        if isinstance(default, str) and default:
            templates[name] = default
    return templates


def _is_error(result: Any) -> bool:
    return isinstance(result, dict) and result.get("ok") is False


def _json_or_text(response: httpx.Response) -> Any:
    try:
        return response.json()
    except json.JSONDecodeError:
        return response.text


def _workflow_url(workflow_id: str) -> str:
    return "/".join(quote(part, safe="") for part in workflow_id.split("/"))
