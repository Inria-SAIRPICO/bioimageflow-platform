# Agent Docs

Start with the workspace root `AGENTS.md`.
It is the shortest contract for editing the active workflow through BioImageFlow MCP tools.

These pages expand the same MCP-only agent contract:

- `api-reference.md`: MCP tool groups, required first calls, arguments, responses, and error handling.
- `workflow-editing.md`: MCP examples for inspecting, creating, connecting, updating, batching, publishing, and deleting workflow graph elements.
- `execution.md`: MCP validation, full-run and selected-node execution, locks, status, and stopping behavior.
- `troubleshooting.md`: MCP failure recovery, stale revisions, frontend conflicts, validation problems, and missing tool metadata.

## Required First Calls

Before editing a workflow, call:

1. `get_bioimageflow_capabilities` with `{}`.
2. `describe_workflow` with `{}` for compact graph state, or `get_workflow_draft` when the full graph is needed.
3. `list_tools` with `{}` or `describe_bioimageflow_tool` for each BioImageFlow tool you plan to use.

Use exact tool names, input names, output names, and parameter names from MCP metadata.
Do not infer names from labels, filenames, or saved JSON.
Use `apply_workflow_operations` for small ordered batches of related graph edits.
Use `get_execution_status` to inspect progress or the latest execution result after starting or stopping a run.

## MCP Client Setup

Configure the MCP server with command `bioimageflow-mcp`.
Run it from the workspace root so it can read `.bioimageflow/agent-state.json`, or set `BIOIMAGEFLOW_AGENT_STATE` to the absolute state file path.

```json
{
  "command": "bioimageflow-mcp",
  "cwd": "<workspace root>",
  "env": {
    "BIOIMAGEFLOW_AGENT_STATE": "<workspace root>/.bioimageflow/agent-state.json"
  }
}
```

The state file includes `mcp_contract_version`, `active_workflow_id`, `current_draft_revision`, `workspace_path`, `active_draft_path`, and `mcp_client_config`.
Treat `current_draft_revision` as informational unless the MCP tool asks for an `expected_revision`.

## Agent Rules

Use MCP tools for workflow inspection, editing, validation, and execution.
Do not edit saved `workflow.json` to change the open workflow.
Do not edit `.bioimageflow/platform-source/`; it is a read-only reference copy.
Do not use REST or shell request procedures for agent workflow actions.
If MCP fails, report the tool name, error code, and detail instead of changing files directly.

Workflow-local tool source belongs to the active workflow, not `.bioimageflow/platform-source/`.
Use the MCP metadata and platform docs to identify editable workflow-local tools before changing tool code.
