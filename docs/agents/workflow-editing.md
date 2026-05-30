# Workflow Editing Cookbook

Read root `AGENTS.md` first. Prefer MCP tools for workflow edits. Use operation
REST when MCP is unavailable. Use raw full-DAG draft replacement only as a
diagnostic fallback.

Set helpers from `.bioimageflow/agent-state.json`:

```sh
STATE=.bioimageflow/agent-state.json
API=$(jq -r .api_base_url "$STATE")
WF=$(jq -r .active_workflow_id "$STATE")
curl -sS "$API/health"
```

`api_base_url` is written by the running backend and includes the actual port
and `/api/v1`. Do not guess or hardcode `localhost:8008`. If the health check
cannot reach localhost or 127.0.0.1 because the agent is sandboxed, request
permission to run the same `curl` command outside the sandbox, then continue
with the same `API` value.

## MCP First

Start the MCP server when your environment supports MCP tools:

```sh
bioimageflow-mcp
```

Use `get_active_workflow` and `list_tools` before graph edits. For common graph
edits, use MCP tools such as `create_node`, `rename_node`,
`update_node_parameters`, `connect_nodes`, `delete_edge`, and `delete_node`.
`create_node` fetches the current draft revision internally when you omit
`expected_revision`, so adding a node can be one MCP tool call.

## Operation REST Second

If MCP is unavailable, apply semantic edits through the backend-owned operation
API:

```sh
curl -s "$API/workflow-drafts/$WF" > /tmp/bif-draft.json
REV=$(jq -r .draft_revision /tmp/bif-draft.json)

jq -n \
  --argjson rev "$REV" \
  '{
    expected_revision: $rev,
    updated_by: "agent",
    validate: true,
    operations: [{
      type: "create_node",
      node_id: "blur_1",
      tool_name: "GaussianBlur",
      name: "Blur",
      position: [100, 120],
      parameters: {}
    }]
  }' \
  | curl -s -X POST "$API/workflow-draft-operations/$WF" \
      -H 'Content-Type: application/json' \
      --data-binary @-
```

The backend operation API owns graph mutation semantics. Do not reimplement
create/delete/connect rules in client code.

## Raw Full-DAG Fallback

Always re-read before a raw full-DAG write. Temp files under `/tmp` are
snapshots and become stale after any frontend edit, agent write, or conflict
retry.

```sh
curl -s "$API/workflow-drafts/$WF" > /tmp/bif-draft.json
REV=$(jq -r .draft_revision /tmp/bif-draft.json)
jq .graph /tmp/bif-draft.json > /tmp/bif-graph.json
```

## Discover Tools And Fields

Before creating or connecting nodes, inspect tool metadata:

```sh
curl -s "$API/tools" > /tmp/bif-tools.json
jq '.[].name' /tmp/bif-tools.json
```

Use exact `tool_name`, input names, output names, and parameter names from tool
metadata. Do not guess names from labels, filenames, or UI text.

## Graph Shape

The complete graph object has these top-level fields. Preserve all of them on a
full-draft write:

```json
{
  "nodes": [],
  "edges": [],
  "published_inputs": [],
  "published_outputs": []
}
```

Minimal node:

```json
{
  "id": "blur_1",
  "name": "Blur",
  "tool_name": "GaussianBlur",
  "position": [100, 120],
  "parameters": {},
  "resources": {},
  "output_templates": {},
  "enabled": true,
  "collapsed": false
}
```

Keep `id` stable after creation. If you change an id, you must update every edge
that references it.

## Create Node Fallback

Append a node to `graph.nodes`. Use a unique `id`, a human-readable `name`, and
a valid `tool_name` from `GET /tools`.

Then write the whole graph back with the latest `draft_revision`.

After a successful write, the frontend is notified. If the canvas is clean it
should update automatically; if the user has local edits, BioImageFlow asks the
user how to resolve the conflict.

## Edit Node Fallback

Change only the intended fields:

- `name` for display rename.
- `parameters` for constant parameter values.
- `enabled` to include or skip the node in future executions.
- `resources` for execution resource overrides.
- `output_templates` for output naming.
- `position` and `collapsed` for canvas UI state.

## Enable Or Disable Node Fallback

Set `enabled` to `true` to include a node in future runs, or `false` to skip it.
Then save the whole draft with the latest `draft_revision`.

This does not stop an execution that is already running. Use
`POST /execution/stop` for the current run.

## Connect Nodes Fallback

Column-reference edge, for a named output connected to a named input:

```json
{
  "type": "column_ref",
  "id": "edge_1",
  "source_node": "load_1",
  "source_output": "image",
  "target_node": "blur_1",
  "target_input": "image"
}
```

Positional edge, for ordered upstream inputs:

```json
{
  "type": "positional",
  "id": "edge_2",
  "source_node": "blur_1",
  "target_node": "segment_1",
  "positional_index": 0
}
```

Keep edge ids unique. For a column input, remove any old edge with the same
`target_node` and `target_input` before adding a replacement. For positional
inputs, avoid duplicate `target_node` plus `positional_index` edges.

## Delete Fallback

Delete an edge by removing it from `graph.edges`.

Delete a node by removing it from `graph.nodes` and removing every edge where
`source_node` or `target_node` equals that node id.

## Execute Nodes

Execution is a separate API call. It does not save the draft. Send the full
graph to `POST /execution/run`; add `nodes` when you only want to run selected
node ids:

```json
{
  "graph": {},
  "workflow_name": "wf",
  "nodes": ["blur_1"]
}
```

Use `GET /execution/status` to watch progress and `POST /execution/stop` to stop
the current run.

## Validate Current Graph

Validation does not persist anything:

```sh
jq -n   --argjson graph "$(cat /tmp/bif-graph.json)"   --arg workflow "$WF"   '{graph: $graph, workflow_name: $workflow}'   | curl -s -X PUT "$API/graph"       -H 'Content-Type: application/json'       --data-binary @-
```

## Write Draft Fallback

`PUT /workflow-drafts/{workflow_id}` replaces the full graph. Do not send only
changed nodes or edges. Prefer MCP or operation REST for normal edits.

```sh
jq -n   --argjson graph "$(cat /tmp/bif-graph.json)"   --argjson rev "$REV"   '{graph: $graph, expected_revision: $rev, updated_by: "agent", validate: true}'   | curl -s -X PUT "$API/workflow-drafts/$WF"       -H 'Content-Type: application/json'       --data-binary @-
```

On `409 draft_revision_conflict`, discard the stale temp graph, re-read the
latest draft, reapply only your intended logical change, then retry with the new
`draft_revision`.

On `423 workflow_locked`, execution is running. Check status, stop or wait, then
re-read the draft before writing.
