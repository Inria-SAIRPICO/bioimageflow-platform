# Agent Docs

Start with the workspace root `AGENTS.md`. It gives the shortest safe path for
editing the active workflow. These files add task-oriented detail for agents
that need examples, endpoint shapes, or recovery steps.

Files:

- `api-reference.md`: endpoints, request payloads, response fields, and common
  error codes.
- `workflow-editing.md`: graph mutation cookbook for creating, editing,
  connecting, enabling, disabling, executing, and deleting nodes.
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
