# Execution For Agents

Use MCP tools for validation, execution, status checks, and stopping.
Do not run saved `workflow.json` directly and do not submit raw graph payloads through shell or REST procedures.

## Before Running

Refresh context:

```json
{"tool": "describe_workflow", "arguments": {"include_parameters": false}}
```

Validate the latest draft:

```json
{"tool": "validate_workflow", "arguments": {}}
```

Fix validation errors through MCP editing tools before running unless the user explicitly asks to run despite warnings and the capability contract allows it.
Disabled nodes are skipped when the latest draft is built for execution.

## Run Latest Draft

Run the current draft:

```json
{"tool": "run_workflow", "arguments": {}}
```

The execution uses the draft captured by the MCP tool at run start.
Later workflow edits do not alter an already started run.

## Run Selected Nodes

Run selected target nodes from the latest draft:

```json
{
  "tool": "run_workflow",
  "arguments": {
    "nodes": ["blur_1", "threshold_1"]
  }
}
```

Selected-node execution still depends on the current workflow graph and its upstream dependencies.
Use exact node ids from `describe_workflow`.

## Frontend Execution Modes

The desktop frontend exposes additional commands in the Run Workflow split-button menu.
Retry Failed Execution addresses the latest failed execution for the active workflow, preserves its original full-workflow or selected-node target set, and reuses successful cached results.
Invalidate Failed Nodes and Retry invalidates failed nodes plus their downstream selections before starting that retry under the same execution reservation.
Recompute Workflow invalidates every enabled node and then runs the complete workflow; disabled nodes remain untouched.
Cache invalidation does not delete retained record data or immediately reclaim disk space.

These frontend commands currently use the execution REST contract and are not separate MCP tools.

## Status

Use `get_execution_status` for progress and final state.

Expected status information may include state, progress, active node, last result, and per-node statuses.

## Stop

Stop the current execution:

```json
{"tool": "stop_execution", "arguments": {}}
```

Stopping is cooperative.
Poll status with `get_execution_status` until execution is no longer running when the task requires confirmation.

## Locks

While execution is running, graph edits and validation may return `workflow_locked`.
Wait for completion, call `stop_execution`, or ask the user which behavior they want.
After the lock clears, call `describe_workflow` again before retrying any edit.

## Frontend Conflicts

The frontend blocks run actions while a user-visible draft conflict is unresolved.
Agents should not resolve that conflict by editing saved files.
Ask the user to resolve the frontend choice, then refresh with `describe_workflow`.
