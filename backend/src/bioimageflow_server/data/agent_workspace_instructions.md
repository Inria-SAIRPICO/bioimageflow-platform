# BioImageFlow Agent Instructions

Use BioImageFlow MCP tools for workflow inspection, editing, validation, and execution.
Do not use REST, shell requests, saved `workflow.json` edits, or raw graph replacement as agent workflow actions.

## Workspace Files

- `.bioimageflow/agent-state.json`: runtime metadata for MCP clients, including `mcp_contract_version`, `mcp_client_config`, `active_workflow_id`, `current_draft_revision`, workspace paths, and optional human diagnostics.
- `workflow.json`: saved/exported artifact. Never edit this file to change the open workflow.
- `.bioimageflow/platform-source/`: {{SOURCE_STATUS}}. Treat every file under it as read-only; editing it will not change the running app or workflow.
- Expanded agent docs may be available in `.bioimageflow/platform-source/docs/agents/`.

## Required First Calls

Call these MCP tools before any workflow edit:

1. `get_bioimageflow_capabilities` with `{}`.
2. `describe_workflow` with `{}`.
3. `list_tools` with `{}` or `describe_bioimageflow_tool` for every tool you plan to create, edit, connect, publish, validate, or execute.

If any required call fails, stop and report the MCP tool name, error code, and detail.
Do not switch to REST, edit local workflow files, or guess tool schemas.

## MCP client setup

Run from the workspace root so `bioimageflow-mcp` can read `.bioimageflow/agent-state.json`, or set `BIOIMAGEFLOW_AGENT_STATE` to the absolute state file path.

Generic MCP server config:

```json
{
  "command": "bioimageflow-mcp",
  "cwd": "<workspace root>",
  "env": {
    "BIOIMAGEFLOW_AGENT_STATE": "<workspace root>/.bioimageflow/agent-state.json"
  }
}
```

If the client does not support `cwd`, set `BIOIMAGEFLOW_AGENT_STATE` explicitly.

## MCP Tool Reference

Context:

- `get_bioimageflow_capabilities`: returns supported tool names, contract version, limits, and error semantics.
- `get_active_workflow`: returns the active workflow id and current draft revision when available.

Inspection:

- `get_workflow_draft`: returns draft metadata, graph summary, validation summary, and optionally the full graph.
- `describe_workflow`: returns the current live draft summary, nodes, edges, published interface, validation summary, and revision metadata.

BioImageFlow tool discovery:

- `list_tools`: lists available BioImageFlow tools with names, inputs, outputs, parameters, and mutability summaries.
- `describe_bioimageflow_tool`: returns detailed metadata for one BioImageFlow tool name.

Graph mutation:

- `create_node`, `delete_node`, `rename_node`, `update_node_parameters`, `set_node_enabled`, `move_node`, `move_nodes`, `connect_nodes`, `delete_edge`.
- `apply_workflow_operations`: applies a small ordered batch of graph operations through backend-owned mutation rules.

Published interface:

- `set_published_input`, `delete_published_input`, `set_published_output`, `delete_published_output`.

Validation and execution:

- `validate_workflow`, `run_workflow`, `get_execution_status`, and `stop_execution`.

## MCP Call Examples

Inspect the active workflow:

```json
{"tool": "describe_workflow", "arguments": {"include_parameters": false}}
```

Create a node:

```json
{"tool": "create_node", "arguments": {"node_id": "blur_1", "tool_name": "GaussianBlur", "name": "Blur", "position": [240, 160], "parameters": {"sigma": 2.0}}}
```

Connect nodes by named output and input:

```json
{"tool": "connect_nodes", "arguments": {"source_node": "load_1", "source_output": "image", "target_node": "blur_1", "target_input": "image"}}
```

Update parameters:

```json
{"tool": "update_node_parameters", "arguments": {"node_id": "blur_1", "parameters": {"sigma": 3.0}}}
```

Apply a batch edit:

```json
{"tool": "apply_workflow_operations", "arguments": {"operations": [{"type": "create_node", "node_id": "threshold_1", "tool_name": "Threshold", "name": "Threshold", "position": [480, 160], "parameters": {"method": "otsu"}}, {"type": "connect_column_ref", "source_node": "blur_1", "source_output": "image", "target_node": "threshold_1", "target_input": "image"}]}}
```

Validate the latest draft:

```json
{"tool": "validate_workflow", "arguments": {}}
```

Run selected nodes from the latest draft:

```json
{"tool": "run_workflow", "arguments": {"nodes": ["blur_1", "threshold_1"]}}
```

## Revision And Conflict Rules

Prefer omitting `expected_revision` when an MCP tool can fetch the latest revision itself.
When you pass `expected_revision`, use the value from the most recent `describe_workflow` or successful mutation response.
On `draft_revision_conflict`, call `describe_workflow` again, reapply only your intended logical change to the new draft, and retry through MCP.
On `workflow_locked`, execution is running; use MCP execution status or `stop_execution`, then call `describe_workflow` before retrying edits.
After successful edits, the frontend is notified automatically; if the user has local canvas edits, the UI owns that conflict resolution.

## Workflow-local tool authoring

Workflow-local tools belong to the active workflow, not `.bioimageflow/platform-source/`.
Inspect tool metadata with `describe_bioimageflow_tool` before using or changing workflow-local tools.
Change workflow-local tool source only when explicitly asked and when the platform exposes the editable source path through the supported tool-authoring workflow.
After source changes, expect the platform to report `tool_reload` or `tool_reload_failed`; fix tool source before continuing when reload fails.

## MCP Failure Behavior

If a tool returns `ok: false`, an MCP transport error, `backend_unavailable`, `backend_timeout`, `operation_validation_error`, or malformed response, stop and report the exact tool, error code, and detail.
Do not switch to REST, shell requests, direct JSON file edits, or `.bioimageflow/platform-source/` edits to continue.
If tool metadata is missing or ambiguous, call `list_tools` or `describe_bioimageflow_tool` again and ask for clarification when names still do not match.
