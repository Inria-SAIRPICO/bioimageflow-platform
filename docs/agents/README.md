# Agent Docs

Start with the workspace root `AGENTS.md`. It gives the shortest safe path for
editing the active workflow. These files add task-oriented detail for agents
that need examples, endpoint shapes, or recovery steps.

Files:

- `api-reference.md`: endpoints, request payloads, response fields, and common
  error codes.
- `workflow-editing.md`: graph mutation cookbook for creating, editing,
  connecting, enabling, disabling, executing, deleting nodes, and authoring
  workflow-local tools.
- `execution.md`: run semantics, selected-node execution, locks, status, stop
  behavior, and draft-vs-run graph rules.
- `troubleshooting.md`: quick fixes for offline API, stale state, 409, 423,
  validation errors, missing tools, and stale temp files.

Workflow editing order:

1. MCP first: use `bioimageflow-mcp` when MCP tools are available.
2. Operation REST second: use `POST /workflow-draft-operations/{workflow_id}`
   for semantic graph edits.
3. Raw full-DAG HTTP fallback: use `GET/PUT /workflow-drafts/{workflow_id}` only
   as the canonical diagnostic escape hatch.

## MCP client setup

Configure the MCP server with command `bioimageflow-mcp`. Run it from the
workspace root so it can read `.bioimageflow/agent-state.json`, or set
`BIOIMAGEFLOW_AGENT_STATE` to the absolute state file path.

Generic MCP config:

```json
{
  "command": "bioimageflow-mcp",
  "cwd": "<workspace root>",
  "env": {
    "BIOIMAGEFLOW_AGENT_STATE": "<workspace root>/.bioimageflow/agent-state.json"
  }
}
```

The API port is dynamic. Agents must read `api_base_url` from
`.bioimageflow/agent-state.json`; they must not guess or hardcode a port such
as `8008`. If `curl -sS "$API/health"` fails because the agent is sandboxed
from localhost or 127.0.0.1, retry the same command with the agent's normal
permission/escalation flow.

After an agent writes a draft, the frontend is notified. A clean canvas should
update automatically; a canvas with local edits will ask the user to resolve the
conflict.

If `.bioimageflow/platform-source/` is present in a workspace, treat it as a
read-only reference copy. Do not edit files there to change the running app or a
workflow.

## Workflow-local tool authoring

Agents may create and edit workflow-local tools for the active workflow. Use the
active workflow id from `.bioimageflow/agent-state.json` as `$WF`.

- Create a scaffold with `POST /tools?workflow_name=$WF`.
- Resolve editable source with
  `GET /tools/{tool_name}/source?workflow_name=$WF`.
- Edit the returned Python file path directly when changing tool behavior.
- Verify the backend saw the edit with `GET /tools` or MCP `list_tools`; a valid
  edit should produce `tool_reload`, and deletion should produce `tool_removed`.
- Fix Python syntax/import errors if the platform reports `tool_reload_failed`.

Do not edit `.bioimageflow/platform-source/` for workflow-local tool changes;
that copy is read-only reference material.
