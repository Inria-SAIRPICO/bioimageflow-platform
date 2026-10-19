"""Drive the installed MCP server from its generated workspace client config."""

from __future__ import annotations

import argparse
from datetime import timedelta
import json
from pathlib import Path
import sys
from typing import Any

import anyio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def exercise(config_path: Path, workflow_id: str, mode: str) -> dict[str, Any]:
    config = json.loads(config_path.read_text())["mcpServers"]["bioimageflow"]
    assert Path(config["command"]).resolve() == Path(sys.executable).resolve()
    state_path = Path(config["env"]["BIOIMAGEFLOW_AGENT_STATE"])
    state = json.loads(state_path.read_text())
    assert state["active_workflow_id"] == workflow_id
    assert state["mcp_client_config"] == config
    transcript = []
    async with stdio_client(StdioServerParameters(**config)) as (read, write):
        async with ClientSession(read, write) as session:
            initialized = await session.initialize()
            advertised = {tool.name for tool in (await session.list_tools()).tools}
            required = {
                "get_bioimageflow_capabilities", "get_workspace_context", "describe_workflow",
                "get_workflow_draft", "list_tools", "describe_bioimageflow_tool",
                "apply_workflow_operations", "rename_node",
            }
            assert required <= advertised

            async def call(name, arguments=None):
                response = await session.call_tool(
                    name, arguments or {}, read_timeout_seconds=timedelta(seconds=10),
                )
                assert not response.isError, response.model_dump(mode="json")
                payload = response.structuredContent
                assert isinstance(payload, dict), response.model_dump(mode="json")
                transcript.append({"tool": name, "arguments": arguments or {}, "result": payload})
                return payload

            capabilities = await call("get_bioimageflow_capabilities")
            assert capabilities["ok"] and capabilities["mcp_contract_version"] == 2
            assert capabilities["max_operation_batch_size"] == 10
            context = await call("get_workspace_context")
            assert context["ok"] and context["active_workflow_id"] == workflow_id
            described = await call("describe_workflow")
            assert described["ok"] and described["workflow_id"] == workflow_id
            before = await call("get_workflow_draft")
            assert before["ok"] and before["workflow_id"] == workflow_id

            if mode == "edit":
                assert before["graph"]["nodes"] == []
                catalog = await call("list_tools")
                assert catalog["ok"]
                assert {"SeedNumbers", "IncrementNumbers"} <= {tool["name"] for tool in catalog["tools"]}
                seed = (await call("describe_bioimageflow_tool", {"tool_name": "SeedNumbers"}))["tool"]
                increment = (await call("describe_bioimageflow_tool", {"tool_name": "IncrementNumbers"}))["tool"]
                assert seed["tool_type"] == increment["tool_type"] == "DataFrameTool"
                assert seed["accepts_upstream"] is False and increment["accepts_upstream"] is True
                assert seed["outputs"]["number"]["type"] == "int"
                assert increment["inputs"]["number"]["type"] == "int"
                assert increment["inputs"]["number"]["connectable"] == "never"
                assert increment["outputs"]["number_plus_one"]["type"] == "int"
                operations = [
                    {"type": "create_tool_node", "node_id": "agent_seed_1", "tool_name": seed["name"],
                     "name": "Agent Seed", "position": [160, 120], "parameters": {}},
                    {"type": "create_tool_node", "node_id": "agent_increment_1", "tool_name": increment["name"],
                     "name": "Agent Increment", "position": [480, 120], "parameters": {"number": 1}},
                    {"type": "connect_dataframe_edge", "edge_id": "mcp-table-edge",
                     "source_node": "agent_seed_1", "target_node": "agent_increment_1", "target_position": 0},
                    {"type": "expose_workflow_input", "input": {
                        "id": "mcp-number-input", "name": "Input number", "kind": "field",
                        "schema": {"type": increment["inputs"]["number"]["type"]},
                        "default": {"__type__": "int", "value": 1},
                        "targets": [{"node": "agent_increment_1", "port": {"kind": "field", "name": "number"}}],
                    }},
                    {"type": "expose_workflow_output", "output": {
                        "id": "mcp-number-output", "name": "Incremented number",
                        "schema": {"type": increment["outputs"]["number_plus_one"]["type"]},
                        "source": {"node": "agent_increment_1", "column": "number_plus_one"},
                    }},
                ]
                assert len(operations) == 5 <= capabilities["max_operation_batch_size"]
                original_revision = before["draft_revision"]
                accepted = await call("apply_workflow_operations", {
                    "expected_revision": original_revision, "operations": operations,
                })
                assert accepted["ok"] and accepted["validation_valid"] is True
                assert accepted["draft_revision"] == original_revision + 1
                accepted_draft = await call("get_workflow_draft")
                assert accepted_draft["draft_revision"] == accepted["draft_revision"]
                rename = {"node_id": "agent_increment_1", "name": "MCP accepted increment"}
                refusal = await call("rename_node", {**rename, "expected_revision": original_revision})
                assert refusal["ok"] is False and refusal["status_code"] == 409
                assert refusal["error"] == "draft_revision_conflict"
                unchanged = await call("get_workflow_draft")
                assert unchanged["graph"] == accepted_draft["graph"]
                assert unchanged["draft_revision"] == accepted_draft["draft_revision"]
                renamed = await call("rename_node", {
                    **rename, "expected_revision": unchanged["draft_revision"],
                })
                assert renamed["ok"] and renamed["validation_valid"] is True
                assert renamed["draft_revision"] == unchanged["draft_revision"] + 1

            final = await call("get_workflow_draft")
            assert final["ok"] and final["workflow_id"] == workflow_id
            graph = final["graph"]
            assert {node["id"] for node in graph["nodes"]} == {"agent_seed_1", "agent_increment_1"}
            assert next(node for node in graph["nodes"] if node["id"] == "agent_increment_1")["name"] == "MCP accepted increment"
            assert graph["interface"]["inputs"][0]["id"] == "mcp-number-input"
            assert graph["interface"]["outputs"][0]["id"] == "mcp-number-output"
            return {
                "protocol_version": initialized.protocolVersion,
                "server_info": initialized.serverInfo.model_dump(mode="json"),
                "before": before, "final": final, "transcript": transcript,
            }


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--workflow", required=True)
    parser.add_argument("--mode", choices=("edit", "read"), required=True)
    arguments = parser.parse_args()
    with anyio.fail_after(20):
        report = await exercise(arguments.config, arguments.workflow, arguments.mode)
    print(json.dumps(report))


if __name__ == "__main__":
    anyio.run(main)
