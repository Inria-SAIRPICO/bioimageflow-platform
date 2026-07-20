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
    workspace_path: str | None = None
    workflows_root: str | None = None
    agent_state_path: str | None = None


class ToolRegistrar(Protocol):
    def tool(self, **kwargs: Any) -> Any: ...


SUPPORTED_MCP_TOOLS = [
    "get_bioimageflow_capabilities",
    "get_workspace_context",
    "get_active_workflow",
    "list_workflows",
    "get_workflow_info",
    "create_workflow",
    "duplicate_workflow",
    "rename_workflow",
    "delete_workflow",
    "set_active_workflow",
    "get_workflow_draft",
    "describe_workflow",
    "list_tools",
    "describe_bioimageflow_tool",
    "apply_workflow_operations",
    "create_tool_node",
    "create_workflow_node",
    "delete_node",
    "rename_node",
    "update_tool_parameters",
    "set_node_enabled",
    "move_node",
    "move_nodes",
    "expose_workflow_input",
    "delete_workflow_input",
    "expose_workflow_output",
    "delete_workflow_output",
    "connect_nodes",
    "delete_edge",
    "validate_workflow",
    "run_workflow",
    "get_execution_status",
    "stop_execution",
]

SUPPORTED_OPERATION_TYPES = [
    "create_tool_node",
    "create_workflow_node",
    "delete_node",
    "rename_node",
    "update_tool_parameters",
    "set_node_enabled",
    "move_node",
    "move_nodes",
    "expose_workflow_input",
    "delete_workflow_input",
    "expose_workflow_output",
    "delete_workflow_output",
    "connect_column_edge",
    "connect_dataframe_edge",
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
    "delete_confirmation_mismatch",
    "active_workflow_delete_forbidden",
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
        if isinstance(state, dict):
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
            "workflow_management": {
                "supports_list": True,
                "supports_create": True,
                "supports_duplicate": True,
                "supports_rename": True,
                "supports_delete": True,
                "supports_set_active": True,
            },
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
        if isinstance(state, dict):
            return state
        return {
            "ok": True,
            "api_base_url": state.api_base_url,
            "active_workflow_id": state.active_workflow_id,
            "current_draft_revision": state.current_draft_revision,
        }

    async def get_workspace_context(self) -> dict[str, Any]:
        state = _read_state_or_error(self.state_path)
        if isinstance(state, dict):
            return state
        workflows = await self._request("GET", "/workflows")
        payload: dict[str, Any] = {
            "ok": not _is_error(workflows),
            "active_workflow_id": state.active_workflow_id,
            "current_draft_revision": state.current_draft_revision,
            "workspace_path": state.workspace_path,
            "workflows_root": state.workflows_root,
            "agent_state_path": state.agent_state_path or str(default_state_path()),
            "mcp_contract_version": 2,
        }
        if _is_error(workflows):
            payload["backend_error"] = workflows
            return payload
        payload["workflow_count"] = len(workflows)
        payload["workflow_ids"] = [
            workflow.get("id") or workflow.get("name") for workflow in workflows
        ]
        return payload

    async def list_workflows(self) -> dict[str, Any]:
        workflows = await self._request("GET", "/workflows")
        if _is_error(workflows):
            return workflows
        return {
            "ok": True,
            "count": len(workflows),
            "workflows": [_compact_workflow_info(workflow) for workflow in workflows],
        }

    async def get_workflow_info(
        self,
        workflow_id: str,
        include_graph: bool = False,
    ) -> dict[str, Any]:
        result = await self._request("GET", f"/workflows/{_workflow_url(workflow_id)}")
        if _is_error(result):
            return result
        payload = {
            "ok": True,
            "info": _compact_workflow_info(result.get("info") or {}),
            "missing_packages": result.get("missing_packages") or [],
            "missing_tools": result.get("missing_tools") or [],
        }
        graph = result.get("graph")
        if isinstance(graph, dict):
            payload["graph_summary"] = _graph_summary(graph)
            if include_graph:
                payload["graph"] = graph
        return payload

    async def create_workflow(
        self,
        workflow_id: str,
        display_name: str | None = None,
        description: str | None = None,
        storage_path: str | None = None,
        set_active: bool = False,
    ) -> dict[str, Any]:
        result = await self._request(
            "POST",
            "/workflows",
            json=_without_none(
                {
                    "name": workflow_id,
                    "display_name": display_name,
                    "description": description,
                    "storage_path": storage_path,
                }
            ),
        )
        if _is_error(result):
            return result
        payload: dict[str, Any] = {"ok": True, "workflow": _compact_workflow_info(result)}
        if set_active:
            active = await self.set_active_workflow(workflow_id)
            payload["active_workflow"] = active
            payload["ok"] = not _is_error(active)
        return payload

    async def duplicate_workflow(
        self,
        source_workflow_id: str,
        new_workflow_id: str,
        display_name: str | None = None,
        description: str | None = None,
        storage_path: str | None = None,
        set_active: bool = False,
    ) -> dict[str, Any]:
        result = await self._request(
            "PATCH",
            f"/workflows/{_workflow_url(source_workflow_id)}",
            json=_without_none(
                {
                    "action": "duplicate",
                    "new_name": new_workflow_id,
                    "display_name": display_name,
                    "description": description,
                    "storage_path": storage_path,
                }
            ),
        )
        if _is_error(result):
            return result
        payload: dict[str, Any] = {
            "ok": True,
            "source_workflow_id": source_workflow_id,
            "workflow": _compact_workflow_info(result),
        }
        if set_active:
            active = await self.set_active_workflow(new_workflow_id)
            payload["active_workflow"] = active
            payload["ok"] = not _is_error(active)
        return payload

    async def rename_workflow(
        self,
        workflow_id: str,
        new_workflow_id: str,
        display_name: str | None = None,
        description: str | None = None,
    ) -> dict[str, Any]:
        state = _read_state_or_error(self.state_path)
        if isinstance(state, dict):
            return state
        result = await self._request(
            "PATCH",
            f"/workflows/{_workflow_url(workflow_id)}",
            json=_without_none(
                {
                    "action": "update",
                    "new_id": new_workflow_id,
                    "display_name": display_name,
                    "description": description,
                }
            ),
        )
        if _is_error(result):
            return result
        payload: dict[str, Any] = {
            "ok": True,
            "previous_workflow_id": workflow_id,
            "workflow": _compact_workflow_info(result),
        }
        if workflow_id == state.active_workflow_id:
            active = await self.set_active_workflow(new_workflow_id)
            payload["active_workflow"] = active
            payload["ok"] = not _is_error(active)
        return payload

    async def delete_workflow(
        self,
        workflow_id: str,
        confirm_workflow_id: str,
    ) -> dict[str, Any]:
        state = _read_state_or_error(self.state_path)
        if isinstance(state, dict):
            return state
        if confirm_workflow_id != workflow_id:
            return {
                "ok": False,
                "error": "delete_confirmation_mismatch",
                "detail": "confirm_workflow_id must match workflow_id",
                "workflow_id": workflow_id,
            }
        if workflow_id == state.active_workflow_id:
            return {
                "ok": False,
                "error": "active_workflow_delete_forbidden",
                "detail": "Call set_active_workflow with another workflow before deleting the current active workflow.",
                "workflow_id": workflow_id,
            }
        result = await self._request("DELETE", f"/workflows/{_workflow_url(workflow_id)}")
        if _is_error(result):
            return result
        return {"ok": True, "workflow_id": workflow_id, **result}

    async def set_active_workflow(self, workflow_id: str) -> dict[str, Any]:
        active = await self._request("POST", f"/workflows/{_workflow_url(workflow_id)}/activate")
        if _is_error(active):
            return active
        draft = await self._request("GET", f"/workflow-drafts/{_workflow_url(workflow_id)}")
        if _is_error(draft):
            return draft
        payload: dict[str, Any] = {
            "ok": True,
            "active_workflow_id": workflow_id,
            "draft_revision": draft.get("draft_revision"),
            "dirty_against_saved": draft.get("dirty_against_saved"),
            "validation": _validation_summary(draft.get("validation")),
        }
        draft_workflow_id = draft.get("workflow_id")
        if draft_workflow_id not in (None, workflow_id):
            payload["draft_workflow_id"] = draft_workflow_id
        return payload

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
        if isinstance(state, dict):
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
        if isinstance(state, dict):
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
            "interface": graph.get("interface", {"inputs": [], "outputs": []}),
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

    async def create_tool_node(
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
                    "type": "create_tool_node",
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

    async def update_tool_parameters(
        self,
        *,
        node_id: str,
        parameters: dict[str, Any],
        expected_revision: int | None = None,
    ) -> dict[str, Any]:
        return await self._apply_operations(
            [
                {
                    "type": "update_tool_parameters",
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

    async def create_workflow_node(
        self,
        *,
        node_id: str,
        name: str,
        position: list[float],
        workflow: dict[str, Any],
        bindings: dict[str, Any] | None = None,
        source: dict[str, Any] | None = None,
        expected_revision: int | None = None,
    ) -> dict[str, Any]:
        return await self._apply_operations(
            [{
                "type": "create_workflow_node",
                "node_id": node_id,
                "name": name,
                "position": position,
                "workflow": workflow,
                "bindings": bindings or {},
                "source": source,
            }],
            expected_revision=expected_revision,
        )

    async def expose_workflow_input(
        self,
        *,
        input_port: dict[str, Any],
        scope: dict[str, Any] | None = None,
        expected_revision: int | None = None,
    ) -> dict[str, Any]:
        operation: dict[str, Any] = {
            "type": "expose_workflow_input",
            "input": input_port,
        }
        if scope is not None:
            operation["scope"] = scope
        return await self._apply_operations([operation], expected_revision=expected_revision)

    async def delete_workflow_input(
        self,
        *,
        input_id: str,
        scope: dict[str, Any] | None = None,
        expected_revision: int | None = None,
    ) -> dict[str, Any]:
        operation: dict[str, Any] = {
            "type": "delete_workflow_input",
            "input_id": input_id,
        }
        if scope is not None:
            operation["scope"] = scope
        return await self._apply_operations([operation], expected_revision=expected_revision)

    async def expose_workflow_output(
        self,
        *,
        output_port: dict[str, Any],
        scope: dict[str, Any] | None = None,
        expected_revision: int | None = None,
    ) -> dict[str, Any]:
        operation: dict[str, Any] = {
            "type": "expose_workflow_output",
            "output": output_port,
        }
        if scope is not None:
            operation["scope"] = scope
        return await self._apply_operations([operation], expected_revision=expected_revision)

    async def delete_workflow_output(
        self,
        *,
        output_id: str,
        scope: dict[str, Any] | None = None,
        expected_revision: int | None = None,
    ) -> dict[str, Any]:
        operation: dict[str, Any] = {
            "type": "delete_workflow_output",
            "output_id": output_id,
        }
        if scope is not None:
            operation["scope"] = scope
        return await self._apply_operations([operation], expected_revision=expected_revision)

    async def connect_nodes(
        self,
        *,
        source_node: str,
        target_node: str,
        source_output: str | None = None,
        target_input: str | None = None,
        target_position: int | None = None,
        edge_id: str | None = None,
        expected_revision: int | None = None,
    ) -> dict[str, Any]:
        if target_position is not None:
            operation: dict[str, Any] = {
                "type": "connect_dataframe_edge",
                "source_node": source_node,
                "target_node": target_node,
                "target_position": target_position,
            }
        else:
            if source_output is None or target_input is None:
                return {
                    "ok": False,
                    "error": "invalid_connect_nodes_arguments",
                    "detail": (
                        "source_output and target_input are required when "
                        "target_position is not provided"
                    ),
                }
            operation = {
                "type": "connect_column_edge",
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
        if isinstance(state, dict):
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
        if isinstance(state, dict):
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
            "draft_revision": draft.get("draft_revision"),
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
        if isinstance(state, dict):
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
        if isinstance(state, dict):
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
    async def get_workspace_context() -> dict[str, Any]:
        """Return workspace paths, active workflow, and workflow ids."""
        return await gateway.get_workspace_context()

    @server.tool()
    async def list_workflows() -> dict[str, Any]:
        """List workflows in the current workspace."""
        return await gateway.list_workflows()

    @server.tool()
    async def get_workflow_info(
        workflow_id: str,
        include_graph: bool = False,
    ) -> dict[str, Any]:
        """Return metadata and optional graph for one workflow."""
        return await gateway.get_workflow_info(
            workflow_id=workflow_id,
            include_graph=include_graph,
        )

    @server.tool()
    async def create_workflow(
        workflow_id: str,
        display_name: str | None = None,
        description: str | None = None,
        storage_path: str | None = None,
        set_active: bool = False,
    ) -> dict[str, Any]:
        """Create an empty workflow in the workspace."""
        return await gateway.create_workflow(
            workflow_id=workflow_id,
            display_name=display_name,
            description=description,
            storage_path=storage_path,
            set_active=set_active,
        )

    @server.tool()
    async def duplicate_workflow(
        source_workflow_id: str,
        new_workflow_id: str,
        display_name: str | None = None,
        description: str | None = None,
        storage_path: str | None = None,
        set_active: bool = False,
    ) -> dict[str, Any]:
        """Duplicate one workflow to a new workflow id."""
        return await gateway.duplicate_workflow(
            source_workflow_id=source_workflow_id,
            new_workflow_id=new_workflow_id,
            display_name=display_name,
            description=description,
            storage_path=storage_path,
            set_active=set_active,
        )

    @server.tool()
    async def rename_workflow(
        workflow_id: str,
        new_workflow_id: str,
        display_name: str | None = None,
        description: str | None = None,
    ) -> dict[str, Any]:
        """Rename or move a workflow to a new workflow id."""
        return await gateway.rename_workflow(
            workflow_id=workflow_id,
            new_workflow_id=new_workflow_id,
            display_name=display_name,
            description=description,
        )

    @server.tool()
    async def delete_workflow(
        workflow_id: str,
        confirm_workflow_id: str,
    ) -> dict[str, Any]:
        """Delete one workflow after explicit id confirmation."""
        return await gateway.delete_workflow(
            workflow_id=workflow_id,
            confirm_workflow_id=confirm_workflow_id,
        )

    @server.tool()
    async def set_active_workflow(workflow_id: str) -> dict[str, Any]:
        """Set the active workflow for subsequent MCP calls."""
        return await gateway.set_active_workflow(workflow_id=workflow_id)

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
    async def create_tool_node(
        node_id: str,
        tool_name: str,
        name: str,
        position: list[float],
        parameters: dict[str, Any] | None = None,
        expected_revision: int | None = None,
    ) -> dict[str, Any]:
        """Create one workflow node."""
        return await gateway.create_tool_node(
            node_id=node_id,
            tool_name=tool_name,
            name=name,
            position=position,
            parameters=parameters,
            expected_revision=expected_revision,
        )

    @server.tool()
    async def create_workflow_node(
        node_id: str,
        name: str,
        position: list[float],
        workflow: dict[str, Any],
        bindings: dict[str, Any] | None = None,
        source: dict[str, Any] | None = None,
        expected_revision: int | None = None,
    ) -> dict[str, Any]:
        """Create one embedded workflow snapshot node."""
        return await gateway.create_workflow_node(
            node_id=node_id,
            name=name,
            position=position,
            workflow=workflow,
            bindings=bindings,
            source=source,
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
    async def update_tool_parameters(
        node_id: str,
        parameters: dict[str, Any],
        expected_revision: int | None = None,
    ) -> dict[str, Any]:
        """Shallow-patch one node parameter mapping."""
        return await gateway.update_tool_parameters(
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
    async def expose_workflow_input(
        input_port: dict[str, Any],
        scope: dict[str, Any] | None = None,
        expected_revision: int | None = None,
    ) -> dict[str, Any]:
        """Create or update a workflow input by immutable port ID."""
        return await gateway.expose_workflow_input(
            input_port=input_port,
            scope=scope,
            expected_revision=expected_revision,
        )

    @server.tool()
    async def delete_workflow_input(
        input_id: str,
        scope: dict[str, Any] | None = None,
        expected_revision: int | None = None,
    ) -> dict[str, Any]:
        """Delete a workflow input by immutable port ID."""
        return await gateway.delete_workflow_input(
            input_id=input_id,
            scope=scope,
            expected_revision=expected_revision,
        )

    @server.tool()
    async def expose_workflow_output(
        output_port: dict[str, Any],
        scope: dict[str, Any] | None = None,
        expected_revision: int | None = None,
    ) -> dict[str, Any]:
        """Create or update a workflow output by immutable port ID."""
        return await gateway.expose_workflow_output(
            output_port=output_port,
            scope=scope,
            expected_revision=expected_revision,
        )

    @server.tool()
    async def delete_workflow_output(
        output_id: str,
        scope: dict[str, Any] | None = None,
        expected_revision: int | None = None,
    ) -> dict[str, Any]:
        """Delete a workflow output by immutable port ID."""
        return await gateway.delete_workflow_output(
            output_id=output_id,
            scope=scope,
            expected_revision=expected_revision,
        )

    @server.tool()
    async def connect_nodes(
        source_node: str,
        target_node: str,
        source_output: str | None = None,
        target_input: str | None = None,
        target_position: int | None = None,
        edge_id: str | None = None,
        expected_revision: int | None = None,
    ) -> dict[str, Any]:
        """Connect two nodes."""
        return await gateway.connect_nodes(
            source_node=source_node,
            target_node=target_node,
            source_output=source_output,
            target_input=target_input,
            target_position=target_position,
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
    interface = graph.get("interface") or {}
    return {
        "node_count": len(graph.get("nodes") or []),
        "edge_count": len(graph.get("edges") or []),
        "workflow_input_count": len(interface.get("inputs") or []),
        "workflow_output_count": len(interface.get("outputs") or []),
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
    payload: dict[str, Any] = {
        "type": node.get("type"),
        "id": node.get("id"),
        "name": node.get("name"),
        "enabled": node.get("enabled", True),
        "position": node.get("position"),
    }
    if node.get("type") == "workflow":
        child = node.get("workflow") or {}
        interface = child.get("interface") or {}
        payload.update({
            "workflow_name": child.get("name"),
            "workflow_display_name": child.get("display_name"),
            "workflow_input_ids": [
                item.get("id") for item in interface.get("inputs", [])
            ],
            "workflow_output_ids": [
                item.get("id") for item in interface.get("outputs", [])
            ],
            "source": node.get("source"),
        })
    else:
        payload.update({
            "tool_name": node.get("tool_name"),
            "parameter_names": list(parameters),
            "output_template_names": list(output_templates),
        })
        if include_parameters:
            payload["parameters"] = parameters
    return payload


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
    if response.status_code == 423:
        detail = payload.get("detail") if isinstance(payload, dict) else payload
        return {
            "ok": False,
            "status_code": response.status_code,
            "error": "workflow_locked",
            "detail": detail,
        }
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
    if isinstance(payload, dict) and isinstance(payload.get("error"), str):
        return {
            "ok": False,
            "status_code": response.status_code,
            **payload,
        }
    if isinstance(payload, dict) and "detail" in payload:
        return {
            "ok": False,
            "status_code": response.status_code,
            "error": _http_status_error(response.status_code),
            "detail": payload["detail"],
        }
    return {
        "ok": False,
        "status_code": response.status_code,
        "error": payload,
    }


def _http_status_error(status_code: int) -> str:
    return {
        400: "bad_request",
        404: "not_found",
        409: "conflict",
        422: "validation_error",
    }.get(status_code, "http_error")


def _without_none(payload: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in payload.items() if value is not None}


def _compact_workflow_info(workflow: dict[str, Any]) -> dict[str, Any]:
    return {
        key: workflow.get(key)
        for key in (
            "id",
            "name",
            "folder",
            "display_name",
            "description",
            "storage_path",
            "output_path",
            "workspace_path",
            "last_modified",
        )
        if key in workflow
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


if __name__ == "__main__":
    main()
