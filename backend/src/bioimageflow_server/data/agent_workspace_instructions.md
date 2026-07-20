# BioImageFlow Agent Instructions

Use BioImageFlow MCP tools for workflow inspection, editing, validation, and execution.
Do not use REST, shell requests, saved `workflow.json` edits, or raw graph replacement as agent workflow actions.

## Workspace Files

- `.bioimageflow/agent-state.json`: runtime metadata for MCP clients, including `mcp_contract_version`, `mcp_client_config`, `active_workflow_id`, `current_draft_revision`, workspace paths, and optional human diagnostics.
- `.codex/config.toml`: generated Codex MCP startup config for the `bioimageflow` MCP server.
- `.mcp.json`: generated project MCP config for Claude Code and generic MCP-aware clients.
- `opencode.json`: generated OpenCode project config entry for the `bioimageflow` MCP server.
- `.omp/mcp.json`: generated oh-my-pi/OMP project MCP config.
- `.bioimageflow/mcp-client-config.json`: generated shared MCP JSON config for clients that can import standard `mcpServers` entries.
- `workflow.json`: saved/exported artifact. Never edit this file to change the open workflow.
- `.bioimageflow/platform-source/`: {{SOURCE_STATUS}}. Treat every file under it as read-only; editing it will not change the running app or workflow.
- Expanded agent docs may be available in `.bioimageflow/platform-source/docs/agents/`.

## Required First Calls

For workspace lifecycle tasks such as listing, creating, duplicating, renaming, deleting, or switching workflows, call:

1. `get_bioimageflow_capabilities` with `{}`.
2. `get_workspace_context` with `{}`.
3. `list_workflows` with `{}`.

For active workflow graph edits, validation, or execution, call:

1. `get_bioimageflow_capabilities` with `{}`.
2. `get_workspace_context` with `{}`.
3. `describe_workflow` with `{}`.
4. `list_tools` with `{}` or `describe_bioimageflow_tool` for every BioImageFlow tool you plan to create, edit, connect, publish, validate, or execute.

If any required call fails, stop and report the MCP tool name, error code, and detail.
Do not switch to REST, edit local workflow files, or guess tool schemas.

## MCP client setup

Use the generated client config for your agent: `.codex/config.toml`, `.mcp.json`, `opencode.json`, `.omp/mcp.json`, or `.bioimageflow/mcp-client-config.json`.
These files are generated from `.bioimageflow/agent-state.json` and pin MCP to the same Python environment as the running backend.
Restart the MCP client after these files are generated or changed.
If you must configure manually, copy the `mcp_client_config` from `.bioimageflow/agent-state.json`, run from the workspace root, and set `BIOIMAGEFLOW_AGENT_STATE` to the absolute state file path.

Generic MCP server config:

```json
{
  "command": "<running backend Python executable>",
  "args": ["-m", "bioimageflow_server.agent_mcp"],
  "cwd": "<workspace root>",
  "env": {
    "BIOIMAGEFLOW_AGENT_STATE": "<workspace root>/.bioimageflow/agent-state.json",
    "PYTHONPATH": "<backend package parent>"
  }
}
```

If the client does not support `cwd`, set `BIOIMAGEFLOW_AGENT_STATE` explicitly.

## MCP Tool Reference

Context:

- `get_bioimageflow_capabilities`: returns supported tool names, contract version, limits, and error semantics.
- `get_workspace_context`: returns workspace paths, active workflow id, revision metadata, workflow count, and workflow ids.
- `get_active_workflow`: returns the active workflow id and current draft revision when available.

Workflow management:

- `list_workflows`: returns the workspace workflow list.
- `get_workflow_info`: returns metadata for one workflow, and optionally the full saved graph.
- `create_workflow`: creates an empty workflow. Pass `set_active: true` when subsequent MCP calls should target it.
- `duplicate_workflow`: copies the saved workflow and workflow-local tools to a new workflow id. Unsaved active draft edits are not copied. Pass `set_active: true` when subsequent MCP calls should target the copy.
- `rename_workflow`: renames or moves one workflow to a new workflow id.
- `delete_workflow`: deletes one non-active workflow. `confirm_workflow_id` must exactly match `workflow_id`; call `set_active_workflow` with another workflow before deleting the current active workflow.
- `set_active_workflow`: makes one workflow the active workflow for subsequent MCP calls by refreshing its draft context.

Inspection:

- `get_workflow_draft`: returns draft metadata, graph summary, validation summary, and optionally the full graph.
- `describe_workflow`: returns the current live draft summary, nodes, edges, workflow interface, validation summary, and revision metadata.

BioImageFlow tool discovery:

- `list_tools`: lists available BioImageFlow tools with names, inputs, outputs, parameters, and mutability summaries.
- `describe_bioimageflow_tool`: returns detailed metadata for one BioImageFlow tool name.

Graph mutation:

- `create_node`, `delete_node`, `rename_node`, `update_node_parameters`, `set_node_enabled`, `move_node`, `move_nodes`, `connect_nodes`, `delete_edge`.
- `apply_workflow_operations`: applies a small ordered batch of graph operations through backend-owned mutation rules.

Workflow interface:

- `expose_workflow_input`, `delete_workflow_input`, `expose_workflow_output`, `delete_workflow_output`.

Validation and execution:

- `validate_workflow`, `run_workflow`, `get_execution_status`, and `stop_execution`.

## MCP Call Examples

Inspect the active workflow:

```json
{"tool": "describe_workflow", "arguments": {"include_parameters": false}}
```

List workspace workflows:

```json
{"tool": "list_workflows", "arguments": {}}
```

Create and activate a new workflow:

```json
{"tool": "create_workflow", "arguments": {"workflow_id": "segmentation-demo", "display_name": "Segmentation Demo", "set_active": true}}
```

Duplicate and activate a workflow:

```json
{"tool": "duplicate_workflow", "arguments": {"source_workflow_id": "segmentation-demo", "new_workflow_id": "segmentation-demo-copy", "display_name": "Segmentation Demo Copy", "set_active": true}}
```

Rename or move a workflow:

```json
{"tool": "rename_workflow", "arguments": {"workflow_id": "segmentation-demo-copy", "new_workflow_id": "examples/segmentation-demo-copy", "display_name": "Segmentation Demo Copy"}}
```

Delete a workflow:

```json
{"tool": "delete_workflow", "arguments": {"workflow_id": "examples/segmentation-demo-copy", "confirm_workflow_id": "examples/segmentation-demo-copy"}}
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
{"tool": "apply_workflow_operations", "arguments": {"operations": [{"type": "create_tool_node", "node_id": "threshold_1", "tool_name": "Threshold", "name": "Threshold", "position": [480, 160], "parameters": {"method": "otsu"}}, {"type": "connect_column_edge", "source_node": "blur_1", "source_output": "image", "target_node": "threshold_1", "target_input": "image"}]}}
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
