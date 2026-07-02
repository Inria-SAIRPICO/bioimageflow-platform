# Workflow Editing Cookbook

Read root `AGENTS.md` first.
All workflow inspection and mutation in this guide uses BioImageFlow MCP tools.

## Start Every Graph Editing Session

Call the required context tools before active workflow graph edits:

```json
{"tool": "get_bioimageflow_capabilities", "arguments": {}}
```

```json
{"tool": "get_workspace_context", "arguments": {}}
```

```json
{"tool": "describe_workflow", "arguments": {"include_parameters": false}}
```

Use `get_workflow_draft` with `include_graph` only when the full graph is needed instead of the compact workflow description.

```json
{"tool": "list_tools", "arguments": {}}
```

For a specific BioImageFlow tool, inspect detailed metadata before using its inputs, outputs, or parameters:

```json
{"tool": "describe_bioimageflow_tool", "arguments": {"tool_name": "GaussianBlur"}}
```

## Create A Node

Use a stable `node_id`, a valid `tool_name`, a display `name`, a two-number `position`, and only parameters that appear in tool metadata.

```json
{
  "tool": "create_node",
  "arguments": {
    "node_id": "blur_1",
    "tool_name": "GaussianBlur",
    "name": "Blur",
    "position": [240, 160],
    "parameters": {
      "sigma": 2.0
    }
  }
}
```

Omit `expected_revision` when the MCP tool can fetch the latest revision itself.
If you pass `expected_revision`, use the value from the latest `describe_workflow` or successful mutation response.

## Connect Nodes

Use named output-to-input connections when both sides have named fields:

```json
{
  "tool": "connect_nodes",
  "arguments": {
    "source_node": "load_1",
    "source_output": "image",
    "target_node": "blur_1",
    "target_input": "image"
  }
}
```

Use positional connections only for ordered upstream inputs:

```json
{
  "tool": "connect_nodes",
  "arguments": {
    "source_node": "blur_1",
    "target_node": "measure_1",
    "positional_index": 0
  }
}
```

Do not invent `source_output`, `target_input`, or positional indexes.
Confirm them with `list_tools` or `describe_bioimageflow_tool`.

## Update Parameters

`update_node_parameters` shallow-patches one node parameter mapping.
Send only the parameters you intend to change.

```json
{
  "tool": "update_node_parameters",
  "arguments": {
    "node_id": "blur_1",
    "parameters": {
      "sigma": 3.0
    }
  }
}
```

## Rename, Enable, Disable, And Layout

Rename a node:

```json
{"tool": "rename_node", "arguments": {"node_id": "blur_1", "name": "Smooth image"}}
```

Disable a node for future runs:

```json
{"tool": "set_node_enabled", "arguments": {"node_id": "blur_1", "enabled": false}}
```

Move one node:

```json
{"tool": "move_node", "arguments": {"node_id": "blur_1", "position": [320, 160]}}
```

Move several nodes without touching parameters, edges, or published interfaces:

```json
{
  "tool": "move_nodes",
  "arguments": {
    "moves": [
      {"node_id": "load_1", "position": [80, 160]},
      {"node_id": "blur_1", "position": [320, 160]}
    ]
  }
}
```

For nested sub-workflow layout, pass `scope.sub_workflow_path` as the list of node ids from the root graph to the nested graph:

```json
{
  "tool": "move_node",
  "arguments": {
    "node_id": "inner_step",
    "position": [180, 120],
    "scope": {
      "sub_workflow_path": ["outer_workflow_node"]
    }
  }
}
```

Scoped graph mutations are layout-only unless `get_bioimageflow_capabilities` explicitly advertises broader scoped edit support.

## Apply A Batch Edit

Use the batch edit tool for a small ordered set of related graph operations.
Keep batches focused and let the backend validate mutation semantics.

```json
{
  "tool": "apply_workflow_operations",
  "arguments": {
    "operations": [
      {
        "type": "create_node",
        "node_id": "threshold_1",
        "tool_name": "Threshold",
        "name": "Threshold",
        "position": [520, 160],
        "parameters": {
          "method": "otsu"
        }
      },
      {
        "type": "connect_column_ref",
        "source_node": "blur_1",
        "source_output": "image",
        "target_node": "threshold_1",
        "target_input": "image"
      }
    ]
  }
}
```

Common batch operation `type` values are `create_node`, `delete_node`, `rename_node`, `update_node_parameters`, `set_node_enabled`, `move_node`, `move_nodes`, `connect_column_ref`, `connect_positional`, `delete_edge`, `set_published_input`, `delete_published_input`, `set_published_output`, and `delete_published_output`.
Use only operation types advertised by `get_bioimageflow_capabilities`.

## Manage Workspace Workflows

List available workflows before changing the active workflow:

```json
{"tool": "list_workflows", "arguments": {}}
```

Inspect one workflow:

```json
{"tool": "get_workflow_info", "arguments": {"workflow_id": "segmentation-demo", "include_graph": false}}
```

Create a new workflow and make it active:

```json
{
  "tool": "create_workflow",
  "arguments": {
    "workflow_id": "segmentation-demo",
    "display_name": "Segmentation Demo",
    "set_active": true
  }
}
```

Duplicate an existing workflow and continue editing the copy:

```json
{
  "tool": "duplicate_workflow",
  "arguments": {
    "source_workflow_id": "segmentation-demo",
    "new_workflow_id": "segmentation-demo-copy",
    "display_name": "Segmentation Demo Copy",
    "set_active": true
  }
}
```

This copies the saved workflow and workflow-local tools, not unsaved active draft edits.

Rename or move a workflow:

```json
{"tool": "rename_workflow", "arguments": {"workflow_id": "segmentation-demo-copy", "new_workflow_id": "examples/segmentation-demo-copy"}}
```

Delete a workflow only when the request is explicit:

```json
{"tool": "delete_workflow", "arguments": {"workflow_id": "examples/segmentation-demo-copy", "confirm_workflow_id": "examples/segmentation-demo-copy"}}
```

The active workflow cannot be deleted; call `set_active_workflow` with another workflow before deleting the current active workflow.

Switch the active workflow:

```json
{"tool": "set_active_workflow", "arguments": {"workflow_id": "segmentation-demo"}}
```

## Published Inputs And Outputs

Use published interface tools instead of editing graph JSON locally.
Published interface targets are checked against backend tool metadata.

Publish a node field as a workflow input:

```json
{
  "tool": "set_published_input",
  "arguments": {
    "name": "image",
    "internal_node_id": "load_1",
    "internal_field": "path",
    "kind": "input",
    "schema": {
      "type": "ImageFile"
    }
  }
}
```

Publish a node output:

```json
{
  "tool": "set_published_output",
  "arguments": {
    "name": "mask",
    "internal_node_id": "threshold_1",
    "internal_output": "mask",
    "schema": {
      "type": "LabelImage"
    }
  }
}
```

Delete by published interface name:

```json
{"tool": "delete_published_input", "arguments": {"name": "image"}}
```

```json
{"tool": "delete_published_output", "arguments": {"name": "mask"}}
```

When clearing nullable stored metadata, send the explicit clear flag used by the tool, such as `set_schema: true` with `schema: null`.
Omitting nullable fields should preserve existing values.

## Delete Nodes And Edges

Delete an edge by id:

```json
{"tool": "delete_edge", "arguments": {"edge_id": "edge_1"}}
```

Delete a node and its connected edges through backend-owned graph rules:

```json
{"tool": "delete_node", "arguments": {"node_id": "blur_1"}}
```

## Validate Before Running

Validate the latest draft after edits:

```json
{"tool": "validate_workflow", "arguments": {}}
```

Fix validation errors through MCP graph tools.
Do not edit saved `workflow.json` or cached graph snapshots.

## Revision And Conflict Handling

On `draft_revision_conflict`, call `describe_workflow` again, reapply only your intended logical change, and retry through MCP.
On `workflow_locked`, execution is running; check execution status when available or stop execution through MCP, then call `describe_workflow` before editing.
If the frontend has local canvas edits, BioImageFlow asks the user how to resolve that conflict.
Agents should not resolve frontend conflicts by changing saved files.

## Workflow-local Tool Authoring

Create, edit, or delete workflow-local tool source only when the user explicitly asks to change tool code and the MCP capabilities or platform docs advertise the supported workflow-local tool workflow.
Use `list_tools` and `describe_bioimageflow_tool` after source changes to verify metadata reload.
Do not edit `.bioimageflow/platform-source/` for workflow-local tool changes; it is a read-only reference copy.
