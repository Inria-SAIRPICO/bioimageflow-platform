# BioImageFlow Frontend State Map

This map helps agents connect frontend editing state to backend API behavior. It is documentation only.

## Workflow stores

- `frontend/src/stores/workflow.ts` owns the saved workflow list, active workflow metadata, missing packages/tools, import/export, save, rename, delete, and version rebind actions.
- `currentName` is the workflow context used by graph validation, execution, and workflow-local tool APIs.
- `useAutoSave` stores local browser autosaves and the last opened workflow. These are frontend recovery state, not saved backend workflow files.

## Graph State

- `frontend/src/composables/useGraphSync.ts` serializes Vue Flow nodes/edges into backend `GraphState`.
- `syncGraph` debounces `PUT /api/v1/graph` and sends `{ graph, workflow_name }`.
- `currentGraph` is the latest serialized graph seen by graph sync; run and save flows should use serialized graph state, not raw Vue Flow objects.
- `patchParameters` calls `PATCH /api/v1/graph/nodes/{node_id}/parameters` for constant parameter changes and relies on a later full graph validation for authoritative status.

## Execution State

- `frontend/src/stores/execution.ts` owns run state, progress, last result, node statuses, conflict flags, and validation errors from execution attempts.
- `fetchStatus` reads `GET /api/v1/execution/status`.
- `run` posts `graph`, optional `nodes`, and `workflow_name` to `/api/v1/execution/run`.
- `clear` posts selected nodes and workflow context to `/api/v1/execution/clear`.
- WebSocket messages update the same store through `applyStatusSnapshot`, `applyProgress`, `applyNodeState`, and `applyExecutionComplete`.

## Tool Registry State

- `frontend/src/stores/toolRegistry.ts` owns tool metadata, package metadata, environment statuses, and workflow-local custom tool mutations.
- `currentWorkflowRequestConfig` adds `workflow_name` from `useWorkflowStore().currentName` for custom tool create, usage, rename, and delete calls.
- Tool reload and removal WebSocket messages update local tool/package lists without requiring a full refresh.

## Agent Guidance

- Use frontend store state to understand the active editing context, but use backend validation/results as the source of truth.
- Do not treat saved workflow JSON as current canvas state while edits are unsaved or validation is pending.
- After graph or tool changes, refresh relevant stores and validate the graph before running or saving.
