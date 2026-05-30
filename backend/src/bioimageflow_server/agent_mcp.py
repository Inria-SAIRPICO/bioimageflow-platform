"""MCP tools for agent operation against a running BioImageFlow workspace."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import quote

import httpx
from pydantic import BaseModel


class AgentState(BaseModel):
    api_base_url: str
    active_workflow_id: str
    current_draft_revision: int | None = None


class ToolRegistrar(Protocol):
    def tool(self, **kwargs: Any) -> Any: ...


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

    async def get_active_workflow(self) -> dict[str, Any]:
        state = read_agent_state(self.state_path)
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
            "tools": [
                {
                    "name": tool.get("name"),
                    "display_name": tool.get("display_name"),
                    "description": tool.get("description"),
                }
                for tool in tools
            ],
        }

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
                raise ValueError(
                    "source_output and target_input are required for column connections"
                )
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
        state = read_agent_state(self.state_path)
        draft = await self._draft(state)
        if _is_error(draft):
            return draft
        result = await self._request(
            "PUT",
            "/graph",
            json={"graph": draft["graph"], "workflow_name": state.active_workflow_id},
        )
        if _is_error(result):
            return result
        errors = result.get("errors") or []
        return {
            "ok": True,
            "valid": bool(result.get("valid")),
            "error_count": len(errors),
        }

    async def run_workflow(self, *, nodes: list[str] | None = None) -> dict[str, Any]:
        state = read_agent_state(self.state_path)
        draft = await self._draft(state)
        if _is_error(draft):
            return draft
        payload: dict[str, Any] = {
            "graph": draft["graph"],
            "workflow_name": state.active_workflow_id,
        }
        if nodes is not None:
            payload["nodes"] = nodes
        result = await self._request("POST", "/execution/run", json=payload)
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
    ) -> dict[str, Any]:
        state = read_agent_state(self.state_path)
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
                "validate": True,
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
        state = read_agent_state(self.state_path)
        url = f"{state.api_base_url.rstrip('/')}{path}"
        async with httpx.AsyncClient(transport=self.transport) as client:
            response = await client.request(method, url, json=json)
        if response.is_error:
            return {
                "ok": False,
                "status_code": response.status_code,
                "error": _json_or_text(response),
            }
        return response.json()


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
    async def get_active_workflow() -> dict[str, Any]:
        """Return the active BioImageFlow API URL and workflow id."""
        return await gateway.get_active_workflow()

    @server.tool()
    async def list_tools() -> dict[str, Any]:
        """List available BioImageFlow tools from the backend REST API."""
        return await gateway.list_tools()

    @server.tool()
    async def create_node(
        node_id: str,
        tool_name: str,
        name: str,
        position: list[float],
        parameters: dict[str, Any] | None = None,
        expected_revision: int | None = None,
    ) -> dict[str, Any]:
        """Create one workflow node through the backend operation API."""
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
        """Delete one workflow node through the backend operation API."""
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
        """Rename one workflow node through the backend operation API."""
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
        """Shallow-patch one node parameter mapping through the operation API."""
        return await gateway.update_node_parameters(
            node_id=node_id,
            parameters=parameters,
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
        """Connect two nodes through the backend operation API."""
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
        """Delete one workflow edge through the backend operation API."""
        return await gateway.delete_edge(
            edge_id=edge_id,
            expected_revision=expected_revision,
        )

    @server.tool()
    async def validate_workflow() -> dict[str, Any]:
        """Validate the active workflow draft through the existing graph REST API."""
        return await gateway.validate_workflow()

    @server.tool()
    async def run_workflow(nodes: list[str] | None = None) -> dict[str, Any]:
        """Run the active workflow draft through the existing execution REST API."""
        return await gateway.run_workflow(nodes=nodes)

    @server.tool()
    async def stop_execution() -> dict[str, Any]:
        """Stop the current execution through the existing execution REST API."""
        return await gateway.stop_execution()

    return server


def main() -> None:
    server = create_mcp_server()
    run = getattr(server, "run")
    run()


def _operation_result(result: dict[str, Any]) -> dict[str, Any]:
    if result.get("ok") is False:
        return result
    return {
        "ok": True,
        "workflow_id": result.get("workflow_id"),
        "draft_revision": result.get("draft_revision"),
        "validation_valid": (result.get("validation") or {}).get("valid"),
    }


def _is_error(result: Any) -> bool:
    return isinstance(result, dict) and result.get("ok") is False


def _json_or_text(response: httpx.Response) -> Any:
    try:
        return response.json()
    except json.JSONDecodeError:
        return response.text


def _workflow_url(workflow_id: str) -> str:
    return "/".join(quote(part, safe="") for part in workflow_id.split("/"))
