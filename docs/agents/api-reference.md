# Agent API Reference

Use `api_base_url` from `.bioimageflow/agent-state.json`; it already includes
`/api/v1`. The port is dynamic. Do not guess or hardcode ports such as `8008`.

Recommended setup:

```sh
STATE=.bioimageflow/agent-state.json
API=$(jq -r .api_base_url "$STATE")
WF=$(jq -r .active_workflow_id "$STATE")
curl -sS "$API/health"
```

If localhost or 127.0.0.1 is blocked by the agent sandbox, request permission
to run the same `curl` command outside the sandbox. Do not use a different port
unless `agent-state.json` changed.

## Preferred Editing Paths

Use MCP first when available:

```sh
bioimageflow-mcp
```

The MCP graph-editing tools call the backend operation API. They do not mutate
workflow graph JSON locally.

Use operation REST second:

`POST /workflow-draft-operations/{workflow_id}`

```json
{
  "expected_revision": "<latest draft_revision>",
  "updated_by": "agent",
  "validate": true,
  "operations": [
    {
      "type": "create_node",
      "node_id": "blur_1",
      "tool_name": "GaussianBlur",
      "name": "Blur",
      "position": [240, 160],
      "parameters": {}
    }
  ]
}
```

Success returns `WorkflowDraftResponse`. Semantic operation failures return:

```json
{
  "error": "operation_validation_error",
  "operation_index": 0,
  "code": "missing_node",
  "detail": "Node not found: missing"
}
```

Use raw full-DAG HTTP fallback only when MCP and operation REST are unavailable
or when you need to inspect/diagnose the complete draft contract.

## State

`GET /health`

Returns backend health. Use this before editing.

`GET /tools`

Returns available tool metadata. Use tool names from this response when setting
`node.tool_name`.

## Full-DAG Draft Fallback

`GET /workflow-drafts/{workflow_id}`

Returns:

```json
{
  "draft_version": 1,
  "workflow_id": "wf",
  "base_saved_revision": "sha256:...",
  "draft_revision": 0,
  "updated_at": "...",
  "updated_by": "system",
  "dirty_against_saved": false,
  "graph": {
    "nodes": [],
    "edges": [],
    "published_inputs": [],
    "published_outputs": []
  },
  "validation": {}
}
```

`PUT /workflow-drafts/{workflow_id}`

Full-graph replacement, not patch. This remains the canonical source-of-truth
contract and escape hatch. Preserve unchanged `nodes`, `edges`,
`published_inputs`, and `published_outputs`.

```json
{
  "graph": {
    "nodes": [],
    "edges": [],
    "published_inputs": [],
    "published_outputs": []
  },
  "expected_revision": "<latest draft_revision>",
  "updated_by": "agent",
  "validate": true
}
```

Success returns the same shape as `GET` with an incremented `draft_revision`.
It also notifies connected frontends that the draft changed. A clean canvas can
auto-refresh from the new draft; a canvas with local edits asks the user to
resolve the conflict.

Errors:

- `404`: workflow not found.
- `409 draft_revision_conflict`: stale `expected_revision`. Re-read, reapply,
  retry.
- `422`: invalid workflow id, graph shape, or request body.
- `423 workflow_locked`: execution is running; wait or stop execution first.

## Validation

`PUT /graph`

Validate without persisting.

```json
{
  "graph": {"nodes": [], "edges": []},
  "workflow_name": "wf"
}
```

The response is a validation result; graph problems are reported there. HTTP
errors include `404` for unknown workflow storage, `422` for malformed request
body, and `423` while execution locks graph editing.

## Execution

`POST /execution/run`

Runs the submitted graph. Add `nodes` to execute only selected node ids. Omit
`nodes` to execute the graph normally.

```json
{
  "graph": {"nodes": [], "edges": []},
  "workflow_name": "wf",
  "nodes": ["optional_node_id"]
}
```

Returns `202` with `{"status": "started"}`.

`GET /execution/status`

Returns current state, progress, last result, and node statuses.

`POST /execution/stop`

Returns `{"status": "stopping"}`. Stop is cooperative; poll status until the
state is no longer running.

Execution errors:

- `409`: another run is already active.
- `422 validation_error`: graph failed to build or validate.
- `503`: execution manager is unavailable.

## Frontend Conflict Expectations

Agents do not resolve frontend conflicts directly. If the user has local canvas
edits when an agent writes a newer draft, the frontend offers:

- Apply agent changes.
- Keep my canvas.
- Save agent version as copy.

Save, run, and export are blocked until the user resolves that choice. Export
also confirms that the workflow will be saved before the export archive is
created.
