# Agent API Reference

Use `api_base_url` from `.bioimageflow/agent-state.json`; it already includes
`/api/v1`.

## State

`GET /health`

Returns backend health. Use this before editing.

`GET /tools`

Returns available tool metadata. Use tool names from this response when setting
`node.tool_name`.

## Drafts

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

Full-graph replacement, not patch. Preserve unchanged `nodes`, `edges`,
`published_inputs`, and `published_outputs`.

```json
{
  "graph": {
    "nodes": [],
    "edges": [],
    "published_inputs": [],
    "published_outputs": []
  },
  "expected_revision": 0,
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
