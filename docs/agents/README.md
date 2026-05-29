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

Workflow editing is API-first through `api_base_url` in
`.bioimageflow/agent-state.json`.

After an agent writes a draft, the frontend is notified. A clean canvas should
update automatically; a canvas with local edits will ask the user to resolve the
conflict.

If `.bioimageflow/platform-source/` is present in a workspace, treat it as a
read-only reference copy. Do not edit files there to change the running app or a
workflow.
