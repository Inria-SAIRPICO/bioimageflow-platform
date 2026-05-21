# Agents Feature Plan

## Goal

Add first-class agent support so a user can open VS Code at the BioImageFlow workspace and run Codex or Claude Code from the integrated terminal. The agent must see the user's current workflow state, understand the platform contract, and modify workflows through validated platform operations such as adding nodes, deleting nodes, renaming nodes, connecting outputs, and changing parameters.

The first implementation should preserve the current architecture from `platform_specs_v1.md`: the frontend remains the editing owner, the backend remains the validation and execution authority, and saved workflow files keep their current manual-save semantics.

## Current Architecture Constraints

- The Vue frontend owns graph state in memory.
- `PUT /api/v1/graph` validates a submitted full `GraphState`; it does not persist the graph.
- `PUT /api/v1/workflows/{id}` persists `workspace/workflows/<id>/workflow.json` on explicit save.
- The frontend autosaves dirty state to IndexedDB, which terminal agents cannot read.
- The backend can already serialize canonical workflow files through `WorkflowStoreService.save_workflow()` and `graph_state_to_persisted_sections()`.
- `EditorService` already opens the workspace as the editor project, which is the correct project root for VS Code-based agents.

## Recommended Architecture

Introduce a backend-mediated live draft layer and an agent command/API bridge.

The frontend continues to own interactive editing, but every meaningful graph change also writes a canonical draft through the backend. Agents read and mutate that draft through platform commands or local HTTP endpoints. The frontend receives draft revision events and applies agent edits when safe.

This gives agents current unsaved state without making `workflow.json` autosave on every edit and without refactoring the backend into the complete graph source of truth.

## Storage Layout

For each workflow:

```text
workspace/workflows/<workflow_id>/
  workflow.json
  tools/
  .bioimageflow/
    draft.json
    agent-state.json
    AGENTS.md
    CLAUDE.md
```

`workflow.json` remains the manually saved workflow.

`draft.json` stores the current live draft and is updated atomically by the backend. It should contain:

```json
{
  "draft_version": 1,
  "workflow_id": "segmentation/nuclei",
  "base_saved_revision": "2026-05-21T12:00:00.000000Z",
  "draft_revision": 42,
  "updated_at": "2026-05-21T12:05:10.000000Z",
  "updated_by": "frontend",
  "dirty_against_saved": true,
  "graph": {},
  "validation": {
    "valid": true,
    "errors": [],
    "node_statuses": {}
  }
}
```

`agent-state.json` stores operational metadata for agents:

- API base URL.
- Active workflow id.
- Current draft revision.
- Workspace paths.
- Recommended command usage.
- Lock state while execution is running.

`AGENTS.md` and `CLAUDE.md` give platform-specific instructions to Codex and Claude Code. They should direct agents to use the BioImageFlow command/API bridge and avoid hand-editing derived workflow sections.

## Backend API Additions

Add draft endpoints under a non-conflicting prefix:

```text
/api/v1/workflow-drafts/{workflow_id:path}
```

Do not add `/api/v1/workflows/{id}/draft` in the MVP. The existing workflow router already has catch-all routes such as `/workflows/{name:path}` for nested workflow ids, so a suffix route is easy to shadow accidentally. A separate `/workflow-drafts` router keeps route matching predictable and must be covered by router tests for nested ids such as `folder/example`.

### `GET /workflow-drafts/{workflow_id:path}`

Returns the live draft if present. If no draft exists, returns a draft synthesized from `workflow.json`.

Response fields:

- `workflow_id`
- `draft_revision`
- `base_saved_revision`
- `dirty_against_saved`
- `graph`
- `validation`
- `updated_at`
- `updated_by`

When a draft is synthesized from `workflow.json`, its initial `draft_revision` is `0`, `dirty_against_saved` is `false`, and the first successful write with `expected_revision: 0` creates revision `1`.

### `PUT /workflow-drafts/{workflow_id:path}`

Frontend writes the latest full graph after meaningful edits.

Request fields:

- `graph`
- `expected_revision: int`
- `updated_by: "frontend" | "agent" | "system"`
- `validate`: default `true`

Behavior:

- Reject with `423 Locked` while workflow execution is running.
- Reject with `409 Conflict` if `expected_revision` is stale.
- Validate through the same graph validator used by `PUT /graph`.
- Atomically write `.bioimageflow/draft.json`.
- Broadcast a WebSocket draft event.

Standard conflict response:

```json
{
  "error": "draft_revision_conflict",
  "expected_revision": 10,
  "current_revision": 11,
  "current_updated_by": "agent",
  "current_updated_at": "2026-05-21T12:05:10.000000Z"
}
```

### `PATCH /workflow-drafts/{workflow_id:path}`

Agent-facing mutation endpoint for structured graph operations.

Initial operations:

- `add_node`
- `delete_node`
- `rename_node`
- `set_param`
- `unset_param`
- `set_enabled`
- `set_output_template`
- `connect_column`
- `connect_positional`
- `delete_edge`
- `move_node`

Every operation uses `expected_revision` and returns the updated graph, validation result, and new revision.

Request shape:

```json
{
  "expected_revision": 42,
  "updated_by": "agent",
  "operations": [
    {
      "op": "set_param",
      "node_id": "segment_cells",
      "param": "diameter",
      "value": 35
    }
  ]
}
```

Response shape:

```json
{
  "workflow_id": "segmentation/nuclei",
  "draft_revision": 43,
  "graph": {},
  "validation": {
    "valid": true,
    "errors": [],
    "node_statuses": {}
  },
  "updated_at": "2026-05-21T12:05:10.000000Z",
  "updated_by": "agent"
}
```

Operation payload details:

- `add_node`: `{op, tool_name, node_id?, name?, position?}`. If `node_id` is omitted, the backend generates a safe unique id from `name` or `tool_name`. If `position` is omitted, use `[0, 0]`; the frontend may reposition later.
- `delete_node`: `{op, node_id}` and deletes all incident edges.
- `rename_node`: `{op, node_id, name}` and preserves the stable node id.
- `set_param`: `{op, node_id, param, value}` using JSON values.
- `unset_param`: `{op, node_id, param}`.
- `set_enabled`: `{op, node_id, enabled}`.
- `set_output_template`: `{op, node_id, output_name, template}`.
- `connect_column`: `{op, source_node, source_output, target_node, target_input, edge_id?}`.
- `connect_positional`: `{op, source_node, target_node, positional_index?, edge_id?}`.
- `delete_edge`: `{op, edge_id}`.
- `move_node`: `{op, node_id, position}`.

Edge ids are generated by the same deterministic convention currently used by the frontend when `edge_id` is omitted:

- Column edge: `e-{source_node}-{source_output}-{target_node}-{target_input}`
- Positional edge: `e-{source_node}-__dataframe_out-{target_node}-__positional_{index}`

If the generated id already exists, the backend appends a numeric suffix.

### `POST /workflow-drafts/{workflow_id:path}/promote`

Promotes the draft to `workflow.json`, equivalent to manual save.

Behavior:

- Requires `expected_revision`.
- Persists through the existing workflow store serialization path.
- Clears or updates `dirty_against_saved`.
- Broadcasts `workflow_saved` and `draft_updated`.

### `POST /workflow-drafts/{workflow_id:path}/revert`

Replaces the draft with the current saved `workflow.json`.

Behavior:

- Requires `expected_revision` unless forced.
- Broadcasts a draft update.
- Frontend applies the reverted graph after user confirmation if local dirty edits exist.

## Draft Models

Add Pydantic models rather than untyped dictionaries:

- `WorkflowDraftFile`
- `WorkflowDraftInfo`
- `WorkflowDraftGetResponse`
- `WorkflowDraftPutRequest`
- `WorkflowDraftMutationRequest`
- discriminated union `WorkflowDraftOperation`
- `WorkflowDraftConflictResponse`
- `DraftUpdatedMessage`

`WorkflowDraftOperation` should use `op` as the discriminator so generated OpenAPI docs are usable by agent tooling.

## WebSocket Events

Add:

```json
{
  "type": "draft_updated",
  "workflow_id": "segmentation/nuclei",
  "draft_revision": 43,
  "updated_by": "agent",
  "summary": "Set CellposeSegmenter.diameter to 35"
}
```

Rules:

- Add a typed backend WebSocket model and frontend dispatch case. The current WebSocket schema enumerates message types, so an unmodeled `draft_updated` event would be rejected or ignored.
- The event is an invalidation notice, not the full graph payload. The frontend loads `GET /workflow-drafts/{workflow_id}` before applying the graph.
- Frontend ignores events it originated if it already holds the same revision.
- If an agent update arrives while no frontend edit is pending, apply it automatically.
- If local frontend edits are pending or a validation request is in flight, show a conflict banner with Apply Remote, Keep Mine, and Review JSON actions.
- If execution is running, queue the notice and resolve it after execution completes.

## Agent Command Bridge

Add a CLI entrypoint, for example `bioimageflow-agent`, that wraps the local API.

Required commands:

```text
bioimageflow-agent status
bioimageflow-agent current-workflow
bioimageflow-agent get-graph
bioimageflow-agent validate
bioimageflow-agent list-tools
bioimageflow-agent tool-schema <tool_name>
bioimageflow-agent add-node --tool <tool_name> --name <name>
bioimageflow-agent delete-node <node_id>
bioimageflow-agent rename-node <node_id> <name>
bioimageflow-agent set-param <node_id> <param> <json_value>
bioimageflow-agent connect-column <source_node> <source_output> <target_node> <target_input>
bioimageflow-agent connect-positional <source_node> <target_node>
bioimageflow-agent save
```

The CLI should:

- Resolve API base URL from `.bioimageflow/agent-state.json`.
- Include the latest `expected_revision`.
- Print validation errors in a concise, agent-readable format.
- Exit non-zero on validation or conflict failures.
- Never require agents to construct full `GraphState` by hand for common edits.

## Frontend Changes

### Draft Autosave

Replace or supplement IndexedDB autosave with backend draft writes:

- On meaningful graph changes, call `PUT /workflows/{id}/draft`.
- Keep the current debounce behavior, initially 500 ms.
- Keep IndexedDB as a fallback only when the backend is unavailable.
- Flush the draft before run, save, export, and editor open.

### Draft Reconciliation

Add a small draft state store:

- current draft revision
- last draft writer
- pending local write
- conflict state
- last applied remote revision

When a `draft_updated` event arrives:

- If no local pending changes: load and apply draft graph.
- If local pending changes: show a non-modal conflict banner.
- If execution is running: defer applying until execution completes.

Before save or run:

- Flush pending frontend draft writes.
- Check that the frontend's applied draft revision equals the backend's current draft revision.
- If the backend has a newer agent-authored revision, block save/run and ask the user to apply or keep local edits first.

This guard must ship before writable agent CLI commands. Otherwise an open frontend can silently overwrite agent mutations with stale in-memory graph state.

### Unsaved Indicator

The asterisk should mean "draft differs from saved workflow", not merely "frontend memory differs from saved workflow".

Manual save promotes the current draft to `workflow.json`.

### Agent Launch UX

Add commands to open VS Code / embedded code-server at the workspace:

- Open workspace.
- Open current workflow folder.
- Open terminal instructions for Codex.
- Open terminal instructions for Claude Code.

Before opening, flush the draft and regenerate `.bioimageflow/AGENTS.md`, `.bioimageflow/CLAUDE.md`, and `.bioimageflow/agent-state.json`.

## Backend Services

Add `WorkflowDraftService`.

Responsibilities:

- Locate draft paths under workflow directories.
- Create draft from saved workflow when missing.
- Atomically read/write draft JSON.
- Maintain monotonic `draft_revision`.
- Validate graphs on write.
- Apply structured mutation operations.
- Emit WebSocket events.
- Guard writes while execution is running.

Keep operation application isolated from FastAPI routers so it can be unit-tested without HTTP.

## Graph Mutation Rules

Structured operations should use existing frontend/backend semantics:

- Node ids must follow existing validation rules.
- Node display names must remain unique.
- Edges must use the existing `ColumnRefEdge` and `PositionalEdge` wire formats.
- `set_param` cannot set a parameter that is currently connected by an incoming column edge unless the operation also deletes that edge.
- `connect_column` removes any existing incoming edge for the target field.
- `delete_node` deletes incident edges.
- Dynamic output schemas should be refreshed by validation; the frontend then updates rendered pins from the returned graph/validation context.
- MVP mutations are root-graph-only. If a node contains an embedded `sub_workflow`, `published_inputs`, or `published_outputs`, operations may preserve those fields but must not mutate inside them. Nested sub-workflow edits require a later addressing model such as `scope: ["parent_node_id", ...]`.

## Conflict Model

Use optimistic concurrency with `draft_revision`.

Every draft write includes `expected_revision`.

Conflict cases:

- Frontend writes revision 10, agent has already written revision 11: return `409`.
- Agent writes revision 10, frontend has already written revision 11: return `409`.
- Saved `workflow.json` changes while draft exists: mark draft as based on an older saved revision and require explicit promote or rebase.

First version can resolve conflicts manually through UX prompts. Do not attempt automatic graph merges in the MVP.

## Execution And Save Semantics

- Execution remains locked against graph edits.
- Run executes the latest frontend-visible graph only after the draft revision guard passes.
- Before run, frontend flushes pending draft writes, validates the resulting revision, and sends the same graph body the execution endpoint currently expects. Do not switch execution to load from disk until frontend reconciliation is stable.
- Save promotes draft to `workflow.json` through `POST /workflow-drafts/{workflow_id}/promote`; during the transition, the existing `PUT /workflows/{id}` path may remain for compatibility but the UI should use draft promotion.
- Export should either export saved workflow or prompt to save/promote draft first.
- Delete workflow deletes `.bioimageflow/` draft metadata with the workflow directory.

## Testing Plan

Backend unit tests:

- Draft creation from saved workflow.
- Draft routes do not collide with `/workflows/{name:path}`, including nested workflow ids.
- Atomic draft write shape.
- Revision increments.
- Stale `expected_revision` returns conflict.
- Execution lock rejects writes.
- Each mutation operation transforms graph correctly.
- Validation errors are returned but invalid drafts can still be stored if the product decision matches current save behavior.
- Rename, duplicate, move, and delete workflow lifecycle behavior keeps `.bioimageflow` metadata consistent.

Frontend unit tests:

- Graph changes call draft save.
- IndexedDB fallback still works when draft save fails.
- WebSocket agent update applies when no local edit is pending.
- Conflict banner appears when local edit is pending.
- Save/run are blocked when backend draft revision is newer than frontend-applied revision.
- Save promotes draft and clears dirty indicator.

E2E tests:

- User edits graph, launches editor, terminal reads current draft.
- Simulated agent adds a node via API; frontend canvas updates.
- Simulated conflict between frontend edit and agent edit shows banner.
- Simulated agent edit before user save/run cannot be silently overwritten by stale frontend memory.
- Save writes agent-modified draft into `workflow.json`.

CLI tests:

- Commands discover API URL from `agent-state.json`.
- Commands include expected revisions.
- Validation errors produce non-zero exits.
- `set-param` and `connect-column` work against a test server.

## Rollout Milestones

### Milestone 1: Readable Live Draft

- Add draft storage service.
- Add `GET` and `PUT` draft endpoints.
- Frontend writes draft on changes.
- Agent context files are generated.
- Agents can inspect current unsaved state.

### Milestone 2: Agent Mutations

- Add structured `PATCH` draft endpoint.
- Add CLI commands for common graph edits.
- Add validation and revision conflict handling.
- Add the minimal frontend remote-update guard before enabling writable CLI commands: if an agent revision exists and the frontend has not applied it, save/run are blocked until the user resolves it.
- Agents can safely modify workflows without being silently overwritten by an open frontend.

### Milestone 3: Frontend Reconciliation

- Add WebSocket `draft_updated`.
- Add frontend draft revision store.
- Auto-apply safe agent edits.
- Show conflict banner for concurrent edits.
- Add typed WebSocket models on both backend and frontend.

### Milestone 4: Save/Run Integration

- Save promotes draft.
- Run flushes and executes draft.
- Export handles dirty drafts explicitly.
- Remove or downgrade IndexedDB to offline fallback.

### Milestone 5: Polish And Documentation

- Add UI entry points for Codex and Claude Code.
- Improve `AGENTS.md` and `CLAUDE.md`.
- Add troubleshooting messages for conflicts, unavailable backend, and execution locks.
- Document the agent bridge in platform specs.

## Open Decisions

- Whether invalid drafts should be stored. Current manual save allows invalid workflows, so the first version should likely allow invalid drafts while returning validation errors.
- Whether `draft.json` should store only `GraphState` plus validation, or the same full persisted sections as `workflow.json`.
- Whether agent context files live at workspace root or per-workflow. A workspace-root file is easier for VS Code startup; per-workflow files are more precise.
- Whether agent CLI belongs in the backend package or a separate package.
- Whether frontend should auto-apply all agent edits when idle, or always ask the user first.

## Preferred First Slice

Implement Milestone 1 and a minimal subset of Milestone 2:

1. `WorkflowDraftService`.
2. `GET` and `PUT /workflow-drafts/{workflow_id:path}`.
3. Atomic `.bioimageflow/draft.json`.
4. Frontend draft autosave after meaningful graph changes.
5. Agent context file generation when opening the editor.
6. Draft route tests for nested workflow ids.
7. `bioimageflow-agent status`, `get-graph`, `validate`, and `list-tools`.

This proves the most important assumption: agents can see the current unsaved frontend state from VS Code without replacing the platform's frontend-owned editing model.
