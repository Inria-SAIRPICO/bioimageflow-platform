# Agent Docs

Start with the workspace root `AGENTS.md`.
It is the shortest contract for editing the active workflow through BioImageFlow MCP tools.

These pages expand the same MCP-only agent contract:

- `api-reference.md`: MCP tool groups, required first calls, arguments, responses, and error handling.
- `workflow-editing.md`: MCP examples for inspecting, creating, connecting, updating, batching, publishing, and deleting workflow graph elements.
- `execution.md`: MCP validation, full-run and selected-node execution, locks, status, and stopping behavior.
- `troubleshooting.md`: MCP failure recovery, stale revisions, frontend conflicts, validation problems, and missing tool metadata.

## Required First Calls

Before workspace lifecycle tasks such as listing, creating, duplicating, renaming, deleting, or switching workflows, call:

1. `get_bioimageflow_capabilities` with `{}`.
2. `get_workspace_context` with `{}`.
3. `list_workflows` with `{}`.

Before active workflow graph edits, validation, or execution, call:

1. `get_bioimageflow_capabilities` with `{}`.
2. `get_workspace_context` with `{}`.
3. `describe_workflow` with `{}` for compact graph state, or `get_workflow_draft` when the full graph is needed.
4. `list_tools` with `{}` or `describe_bioimageflow_tool` for each BioImageFlow tool you plan to use.

Use exact tool names, input names, output names, and parameter names from MCP metadata.
Do not infer names from labels, filenames, or saved JSON.
Use `list_workflows`, `get_workflow_info`, `create_workflow`, `duplicate_workflow`, `rename_workflow`, `delete_workflow`, and `set_active_workflow` for workspace workflow lifecycle tasks.
`duplicate_workflow` copies the saved workflow and workflow-local tools, not unsaved active draft edits.
`delete_workflow` refuses to delete the active workflow; call `set_active_workflow` with another workflow first.
Use `apply_workflow_operations` for small ordered batches of related graph edits.
Use `get_execution_status` to inspect progress or the latest execution result after starting or stopping a run.

## MCP Client Setup

Use the generated project config for your MCP client when available:

- Codex: `.codex/config.toml`
- Claude Code and generic MCP clients: `.mcp.json`
- OpenCode: `opencode.json`
- oh-my-pi/OMP: `.omp/mcp.json`
- Importable shared MCP JSON: `.bioimageflow/mcp-client-config.json`

These files are generated from `.bioimageflow/agent-state.json` and pin the MCP server to the same Python environment as the running BioImageFlow backend.
Restart the MCP client after these files are generated or changed.
If you must configure manually, copy `mcp_client_config` from `.bioimageflow/agent-state.json`, run from the workspace root, and set `BIOIMAGEFLOW_AGENT_STATE` to the absolute state file path.

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
