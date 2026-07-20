# Agent MCP Reference

This page describes the BioImageFlow MCP contract for agents.
Use these tools for workflow inspection, editing, validation, and execution.

## State Metadata

`.bioimageflow/agent-state.json` is runtime metadata, not workflow data.
Useful fields include `mcp_contract_version`, `active_workflow_id`, `current_draft_revision`, `workspace_path`, `workflows_root`, `active_draft_path`, `agent_state_path`, and `mcp_client_config`.

## Required First Calls

For workspace lifecycle tasks, use this sequence:

`get_bioimageflow_capabilities`

```json
{"tool": "get_bioimageflow_capabilities", "arguments": {}}
```

Returns supported contract version, available MCP tools, operation limits, and error conventions.
Use this response to decide whether optional tools such as batch edit or execution status are available.

`get_workspace_context`

```json
{"tool": "get_workspace_context", "arguments": {}}
```

Returns workspace paths, active workflow id, current draft revision, workflow count, and workflow ids.

`list_workflows`

```json
{"tool": "list_workflows", "arguments": {}}
```

Returns compact metadata for all workflows in the workspace.

For active graph edits, validation, or execution, call the same first two tools, then inspect the active workflow and tool metadata:

`describe_workflow`

```json
{"tool": "describe_workflow", "arguments": {"include_parameters": false}}
```

Returns the live workflow draft description and revision metadata.
Use this instead of reading saved `workflow.json`.

`get_workflow_draft`

```json
{"tool": "get_workflow_draft", "arguments": {"include_graph": true}}
```

Returns draft metadata, graph summary, validation summary, and optionally the full graph.
Use this only when the compact `describe_workflow` response is not enough.

`list_tools`

```json
{"tool": "list_tools", "arguments": {}}
```

Returns available BioImageFlow tool metadata.
Call it before creating nodes, connecting fields, publishing interfaces, or interpreting validation errors.

`describe_bioimageflow_tool`

```json
{"tool": "describe_bioimageflow_tool", "arguments": {"tool_name": "GaussianBlur"}}
```

Returns detailed metadata for one BioImageFlow tool.
Use exact names from this response.

## Context And Inspection Tools

`get_active_workflow`

```json
{"tool": "get_active_workflow", "arguments": {}}
```

Returns the active workflow id and current draft revision when available.

`describe_workflow`

```json
{
  "tool": "describe_workflow",
  "arguments": {
    "include_parameters": true
  }
}
```

Use the default compact description for orientation.
Set `include_parameters` only when parameter values are needed for the task.

## Workflow Management Tools

`list_workflows`

```json
{"tool": "list_workflows", "arguments": {}}
```

Returns compact metadata for all workflows in the workspace.

`get_workflow_info`

```json
{"tool": "get_workflow_info", "arguments": {"workflow_id": "segmentation-demo", "include_graph": false}}
```

Returns metadata, missing package/tool diagnostics, and a graph summary for one workflow.
Set `include_graph: true` only when the saved graph is required.

`create_workflow`

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

Creates an empty workflow.
Optional arguments are `display_name`, `description`, `storage_path`, and `set_active`.

`duplicate_workflow`

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

Copies an existing workflow to a new workflow id.
Optional arguments are `display_name`, `description`, `storage_path`, and `set_active`.
This copies the saved workflow and workflow-local tools, not unsaved active draft edits.

`rename_workflow`

```json
{
  "tool": "rename_workflow",
  "arguments": {
    "workflow_id": "segmentation-demo-copy",
    "new_workflow_id": "examples/segmentation-demo-copy",
    "display_name": "Segmentation Demo Copy"
  }
}
```

Renames or moves one workflow.
Optional arguments are `display_name` and `description`.

`delete_workflow`

```json
{
  "tool": "delete_workflow",
  "arguments": {
    "workflow_id": "examples/segmentation-demo-copy",
    "confirm_workflow_id": "examples/segmentation-demo-copy"
  }
}
```

Deletes one workflow.
`confirm_workflow_id` must exactly match `workflow_id`.
The active workflow cannot be deleted; call `set_active_workflow` with another workflow before deleting the current active workflow.

`set_active_workflow`

```json
{"tool": "set_active_workflow", "arguments": {"workflow_id": "segmentation-demo"}}
```

Sets the active workflow for subsequent MCP calls by refreshing the workflow draft context.

## Graph Mutation Tools

`create_node`

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

`connect_nodes`

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

For positional connections:

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

`update_node_parameters`

```json
{"tool": "update_node_parameters", "arguments": {"node_id": "blur_1", "parameters": {"sigma": 3.0}}}
```

`rename_node`

```json
{"tool": "rename_node", "arguments": {"node_id": "blur_1", "name": "Smooth image"}}
```

`set_node_enabled`

```json
{"tool": "set_node_enabled", "arguments": {"node_id": "blur_1", "enabled": false}}
```

`move_node`

```json
{"tool": "move_node", "arguments": {"node_id": "blur_1", "position": [320, 160]}}
```

`move_nodes`

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

`delete_edge`

```json
{"tool": "delete_edge", "arguments": {"edge_id": "edge_1"}}
```

`delete_node`

```json
{"tool": "delete_node", "arguments": {"node_id": "blur_1"}}
```

## Batch Edit Tool

`apply_workflow_operations`

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
        "type": "connect_column_edge",
        "source_node": "blur_1",
        "source_output": "image",
        "target_node": "threshold_1",
        "target_input": "image"
      }
    ]
  }
}
```

Keep batches small and ordered.
If the tool reports an operation index, fix that operation and retry after refreshing workflow state.

## Workflow Interface Tools

`expose_workflow_input`

```json
{
  "tool": "expose_workflow_input",
  "arguments": {
    "input_port": {
      "id": "input-image",
      "name": "image",
      "kind": "field",
      "schema": {"type": "ImageFile"},
      "targets": [
        {"node": "load_1", "port": {"kind": "field", "name": "path"}}
      ]
    }
  }
}
```

`expose_workflow_output`

```json
{
  "tool": "expose_workflow_output",
  "arguments": {
    "output_port": {
      "id": "output-mask",
      "name": "mask",
      "schema": {"type": "LabelImage"},
      "source": {"node": "threshold_1", "column": "mask"}
    }
  }
}
```

`delete_workflow_input`

```json
{"tool": "delete_workflow_input", "arguments": {"input_id": "input-image"}}
```

`delete_workflow_output`

```json
{"tool": "delete_workflow_output", "arguments": {"output_id": "output-mask"}}
```

## Validation And Execution Tools

`validate_workflow`

```json
{"tool": "validate_workflow", "arguments": {}}
```

Returns whether the latest draft is valid and reports validation errors when present.

`run_workflow`

```json
{"tool": "run_workflow", "arguments": {}}
```

Runs the latest draft.
For selected-node execution:

```json
{"tool": "run_workflow", "arguments": {"nodes": ["blur_1", "threshold_1"]}}
```

`stop_execution`

```json
{"tool": "stop_execution", "arguments": {}}
```

Stops the current execution cooperatively.

`get_execution_status`

```json
{"tool": "get_execution_status", "arguments": {}}
```

Returns current execution state, progress, node statuses, and the latest result when available.

## Error Handling

On `draft_revision_conflict`, call `describe_workflow`, reapply the intended logical change to the new draft, and retry through MCP.
On `workflow_locked`, execution is running; wait, stop through MCP, or ask the user, then refresh workflow state before editing.
On `operation_validation_error`, fix the reported operation instead of editing graph JSON.
On `backend_unavailable`, `backend_timeout`, MCP transport failure, or malformed response, stop and report the exact MCP failure.
Do not use REST or saved-file edits for agent workflow actions.
