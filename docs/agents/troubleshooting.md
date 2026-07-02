# Agent Troubleshooting

Use this page when a BioImageFlow MCP tool fails or returns an unexpected result.
Do not switch to REST, shell request procedures, saved `workflow.json` edits, or `.bioimageflow/platform-source/` edits for agent workflow actions.

## MCP Server Cannot Start

Confirm the agent is using the generated project config for its client: `.codex/config.toml`, `.mcp.json`, `opencode.json`, `.omp/mcp.json`, or `.bioimageflow/mcp-client-config.json`.
Read `.bioimageflow/agent-state.json` and use its exact `mcp_client_config`, including `command`, `args`, `cwd`, and `env`.
If a client ignores `args` or resolves a different Python environment, report the mismatch.
Run the MCP server from `mcp_client_config.cwd`, or set `BIOIMAGEFLOW_AGENT_STATE` to `agent_state_path`.
If the MCP client cannot start the server, report the startup error and the state path.
Restart the MCP client after generated config files change.

## Required First Call Fails

The required first calls are `get_bioimageflow_capabilities`, `describe_workflow`, and then `list_tools` or `describe_bioimageflow_tool`.
If one fails, stop and report the tool name, error code, and detail.
Do not continue by guessing workflow shape or tool metadata.

## Backend Unavailable Or Timeout

MCP tools may report `backend_unavailable`, `backend_timeout`, a transport error, or a malformed backend response.
Report the exact MCP failure.

## Stale State

`agent-state.json` contains runtime pointers, not workflow data.
`current_draft_revision` is informational unless a tool asks for `expected_revision`.
Call `describe_workflow` before edits and after conflicts, locks, or user changes.

## Draft Revision Conflict

On `draft_revision_conflict`, your view of the draft is stale.
Call `describe_workflow`, reapply only your intended logical change, and retry through MCP.
Do not reuse cached graph JSON or edit saved files.

## Workflow Locked

On `workflow_locked`, execution is running.
Use `get_execution_status`, wait, or call `stop_execution`.
After the lock clears, call `describe_workflow` before editing.

## Operation Validation Error

On `operation_validation_error`, read `operation_index`, `code`, and `detail`.
Fix the failing MCP operation or batch operation.
Do not bypass backend mutation rules by editing graph JSON.

## Validation Errors

Call `validate_workflow` and inspect reported errors.
Common causes are typoed `tool_name`, typoed input or output names, missing required parameters, deleted node ids still referenced by edges, and non-connectable fields.
Use `list_tools`, `describe_bioimageflow_tool`, and `describe_workflow` to repair the graph through MCP mutation tools.

## Missing Tool Names Or Fields

Call `list_tools` for the available BioImageFlow tool set.
Call `describe_bioimageflow_tool` for exact parameter, input, and output names.
If the expected tool is still missing, report the missing name and ask whether a workflow-local tool or package needs to be installed.

## Frontend Did Not Update

After a successful MCP draft edit, connected frontends receive a draft-change event.
If the user has no local canvas edits, the canvas should update automatically.
If the user has local canvas edits, the frontend asks them to apply agent changes, keep their canvas, or save the agent version as a copy.
Agents should not resolve that conflict by editing `workflow.json`.

## Read-Only Platform Source

`.bioimageflow/platform-source/` is context only.
Use it to inspect docs or implementation patterns when needed.
Editing it will not change the running app, active workflow, or workflow-local tools.
