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

MCP client setup: run from the workspace root or set `BIOIMAGEFLOW_AGENT_STATE`
to the absolute `.bioimageflow/agent-state.json` path.

```json
{
  "command": "bioimageflow-mcp",
  "cwd": "<workspace root>",
  "env": {
    "BIOIMAGEFLOW_AGENT_STATE": "<workspace root>/.bioimageflow/agent-state.json"
  }
}
```

Use `get_active_workflow` and `list_tools` before graph edits. For common graph
edits, use MCP tools such as `create_node`, `rename_node`,
`update_node_parameters`, `set_node_enabled`, `move_node`, `move_nodes`,
`connect_nodes`,
`delete_edge`, and `delete_node`.
`create_node` fetches the current draft revision internally when you omit
`expected_revision`, so adding a node can be one MCP tool call.
Use `move_nodes` for bulk layout when arranging multiple existing nodes. It
updates only canvas positions and preserves parameters, edges, published
interfaces, and other node fields.
For nested sub-workflow layout, pass `scope: {"sub_workflow_path": ["outer"]}`
to `move_node` or `move_nodes`. The path is a list of node ids from the root
graph to the target nested graph. Scoped operations are layout-only; do not use
them for create/delete/connect inside sub-workflows.

Published workflow inputs and outputs are also semantic graph edits. Use
`set_published_input`, `delete_published_input`, `set_published_output`, and
`delete_published_output` instead of editing `published_inputs` or
`published_outputs` JSON locally. `set_published_input` upserts by
`internal_node_id` plus `internal_field`; `set_published_output` upserts by
`internal_node_id` plus `internal_output`. Delete operations remove by the
published interface `name`. To clear a nullable published input/output
`schema` or input `default` through MCP, send `set_schema: true` or
`set_default: true` with the value set to `null`; omitting those fields
preserves the existing value during an upsert.

Published interface targets are checked against backend tool metadata. Use exact
input names and static output names from `list_tools` / `GET /tools`; dynamic or
passthrough outputs may use resolved or inherited output names, but not the
internal `_passthrough` marker. Typoed static target names, missing tool
metadata, and non-connectable `kind: "input"` fields are rejected before any
draft write.

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

Bulk layout REST example:

```sh
jq -n \
  --argjson rev "$REV" \
  '{
    expected_revision: $rev,
    updated_by: "agent",
    validate: true,
    operations: [{
      type: "move_nodes",
      moves: [
        {node_id: "load_1", position: [80, 120]},
        {node_id: "blur_1", position: [300, 120]}
      ]
    }]
  }' \
  | curl -s -X POST "$API/workflow-draft-operations/$WF" \
      -H 'Content-Type: application/json' \
      --data-binary @-
```

Nested sub-workflow layout REST example:

```sh
jq -n \
  --argjson rev "$REV" \
  '{
    expected_revision: $rev,
    updated_by: "agent",
    validate: true,
    operations: [{
      type: "move_node",
      node_id: "inner_step",
      position: [180, 120],
      scope: {sub_workflow_path: ["outer_workflow_node"]}
    }]
  }' \
  | curl -s -X POST "$API/workflow-draft-operations/$WF" \
      -H 'Content-Type: application/json' \
      --data-binary @-
```

Published interface REST example:

```sh
jq -n \
  --argjson rev "$REV" \
  '{
    expected_revision: $rev,
    updated_by: "agent",
    validate: true,
    operations: [{
      type: "set_published_input",
      name: "image",
      internal_node_id: "load_1",
      internal_field: "path",
      kind: "input",
      schema: {"type": "ImageFile"}
    }]
  }' \
  | curl -s -X POST "$API/workflow-draft-operations/$WF" \
      -H 'Content-Type: application/json' \
      --data-binary @-
```

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

## Workflow-local tool authoring

Workflow-local tools are editable Python files attached to the active workflow.
Package/global tools may be read-only or non-deletable. Use workflow-local tools
when an agent needs to create a new tool or edit/delete a custom tool for this
workflow.

Create a scaffold:

```sh
curl -sS -X POST "$API/tools?workflow_name=$WF" \
  -H 'Content-Type: application/json' \
  -d '{"name":"MyTool","tool_type":"ProcessingTool"}'
```

Resolve the source path:

```sh
TOOL=MyTool
curl -sS "$API/tools/$TOOL/source?workflow_name=$WF"
```

API shape: `POST /tools?workflow_name=$WF` creates a workflow-local tool, and
`GET /tools/{tool_name}/source?workflow_name=$WF` returns its editable source
path. Edit that Python file directly. The backend watches workflow-local tool
sources and should publish `tool_reload` after a valid edit or `tool_removed`
after deletion. If the source has syntax/import errors, expect
`tool_reload_failed`; fix the Python file and verify again with `GET /tools` or
MCP `list_tools`.

Do not edit `.bioimageflow/platform-source/` for tool authoring. It is a
read-only reference copy of platform source and docs, not the active workflow.

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
