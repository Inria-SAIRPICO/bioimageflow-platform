---
name: bioimageflow-execution-debugging
description: Use when diagnosing BioImageFlow execution failures, node statuses, progress updates, output data, cache behavior, execution locks, or run/stop/clear APIs.
---

# BioImageFlow Execution Debugging

Use this skill when investigating run failures, node statuses, progress updates, cache behavior, or execution locks.

## Source Of Truth

- Execution state is owned by the backend execution manager.
- Use `/api/v1/execution/status` for a REST status snapshot.
- Use WebSocket `status_snapshot`, `progress`, `node_state`, and `execution_complete` messages when observing a live frontend session.
- Agents must never edit platform source to debug execution. Use the workflow-root workspace, and treat the platform reference as a copy and read-only reference.

## Workflow

1. Fetch status before changing graph or workflow state.
2. If a run failed, inspect `last_result`, `node_statuses`, validation errors, and logger entries.
3. Validate the graph with `PUT /api/v1/graph` before retrying.
4. Ask for execution permission when starting or retrying a run. Run with `POST /api/v1/execution/run`, passing the draft graph, optional `nodes`, and `workflow_name`.
5. Clear cache with `POST /api/v1/execution/clear` only for requested nodes and the correct workflow context.
6. Stop a running execution with `POST /api/v1/execution/stop` before making edits that the platform locks.

## Notes

- A `409` from execution run usually means an execution conflict.
- A `422` from execution run may include graph validation errors.
- Node cache and output resolution are workflow-storage scoped when `workflow_name` is provided.
- For `Files > Atlas > Connected Components`, confirm missing package install approval before adding dependencies, then run only after validation succeeds and undo remains available for graph edits made through the current draft id and revision.
