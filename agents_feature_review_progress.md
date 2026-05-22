# Agents Feature Review Progress

## Baseline

Created the initial plan around a backend-mediated live draft plus an agent command bridge. The baseline intentionally preserves the existing frontend-owned graph architecture while giving terminal agents access to current unsaved workflow state.

Key baseline decisions:

- Keep `workflow.json` as the manual-save artifact.
- Store current unsaved state in `.bioimageflow/draft.json`.
- Add draft endpoints with optimistic revision checks.
- Add an agent CLI/API bridge so agents avoid hand-editing workflow JSON.
- Add frontend reconciliation for agent-originated draft updates.

Baseline commit: `d384a7e` (`docs: plan agent workflow draft support`).

## Review Iteration 1

Review summary:

- The first writable-agent milestone was unsafe because agent edits could arrive before the frontend had any reconciliation or save/run guard.
- The proposed `/workflows/{id}/draft` routes could be shadowed by the existing `/workflows/{name:path}` catch-all routes.
- Save/run semantics were postponed too late and did not say how stale frontend memory is prevented from overwriting agent edits.
- The draft mutation API needed concrete request/response shapes, conflict payloads, edge id generation rules, and initial revision behavior.
- Sub-workflow mutation scope and WebSocket schema changes were not explicit.

Improvements made:

- Changed the draft API prefix to `/api/v1/workflow-drafts/{workflow_id:path}` to avoid route collision.
- Added explicit draft initialization behavior and standardized `409` conflict payloads.
- Added concrete mutation request/response shapes and per-operation payload details.
- Added Pydantic model requirements, including a discriminated `WorkflowDraftOperation` union and `DraftUpdatedMessage`.
- Added a frontend revision guard before save/run and required that this guard ship before writable agent CLI commands.
- Clarified that MVP mutations are root-graph-only and must not mutate nested sub-workflows.
- Expanded tests for route shadowing, stale overwrite prevention, typed WebSocket handling, and workflow lifecycle metadata.

Why this version is materially better:

The baseline plan could have produced a working draft file while still allowing an open frontend to overwrite agent edits. It also proposed endpoints that may not route correctly with nested workflow ids. The revised plan closes those implementation traps and gives enough schema detail for backend, frontend, and CLI work to proceed consistently.

## Review Iteration 2

Review summary:

- The first revision still required `expected_revision` before the frontend had a draft revision store or initial draft load.
- Writable agent mutations were still scheduled before the frontend could even learn that a remote draft revision existed.
- One frontend section still referenced the rejected `/workflows/{id}/draft` route.
- Several important decisions were left open even though implementation depended on them: draft persistence shape, invalid draft behavior, context file location, and saved revision identity.
- Optimistic revision checks needed a per-workflow critical section to prevent concurrent writes from both winning.
- Workflow lifecycle behavior for rename, duplicate, move, and delete needed product-level rules, not only tests.

Improvements made:

- Moved frontend draft revision state and initial `GET /workflow-drafts` into Milestone 1 before draft autosave.
- Moved typed `draft_updated` invalidation into Milestone 2 before writable CLI commands are enabled.
- Replaced the stale frontend route reference with `PUT /api/v1/workflow-drafts/{workflow_id}` and added segment-encoding guidance.
- Settled draft persistence: `draft.json` stores `GraphState` plus validation metadata; `workflow` and `gui` sections are derived on promotion.
- Settled invalid draft semantics: structurally invalid requests return `422`, while semantically invalid graphs are stored with `validation.valid: false`.
- Added saved content hash revisions, stale promotion checks, and per-workflow locking for draft writes.
- Defined workflow lifecycle behavior for create/import, rename/move, duplicate, delete, and workspace switch.
- Moved agent discovery files to workspace-root `.bioimageflow/`, while keeping workflow-local `draft.json`.

Why this version is materially better:

The previous plan had the right architecture but still had sequencing contradictions: the frontend could not satisfy the API's revision contract during the first milestone, and writable agents could run before invalidation existed. The revised plan makes the first slice internally implementable, removes decisions that would otherwise cause API churn, and adds real concurrency and lifecycle guarantees.

## Review Iteration 3

Review summary:

- Draft validation could accidentally mutate the active `/graph` `SessionManager` state if it reused the existing validation path directly.
- Writable CLI commands were still allowed before all legacy save/run/export UI paths were explicitly guarded against stale draft revisions.
- Edge id generation incorrectly assumed deterministic ids, while the broader platform contract treats edge ids as generated opaque identifiers.
- Dynamic output refresh was under-specified because `ValidationResult` does not contain resolved output schemas.
- Rich draft conflict responses needed explicit response models and router behavior so the global error handler does not discard machine-readable fields.
- `add_node` needed a complete defaulting and validation contract.
- Workspace-root `agent-state.json` needed staleness detection for backend restart, port changes, and workspace switches.

Improvements made:

- Added a requirement that draft validation use an isolated/sessionless or draft-specific validation context and tests proving it does not mutate the active `/graph` session.
- Required existing Save, Run, Export, and compatibility save paths to be guarded or disabled against stale remote draft revisions before writable CLI commands ship.
- Replaced deterministic edge id generation with opaque server-generated ids and duplicate-id rejection.
- Added `schema_refresh_node_ids` to draft mutation responses for dynamic-output schema refresh.
- Required explicit response models/`JSONResponse` handling for machine-readable conflict, lock, and validation errors.
- Expanded `add_node` defaults for parameters, resources, output templates, enabled/collapsed state, name/id generation, duplicate names, and unknown tools.
- Added backend session id, process id, generated timestamp, health URL, and CLI recovery rules to `agent-state.json`.
- Expanded tests for session isolation, legacy save overwrite prevention, OpenAPI discriminators, dynamic-output refresh, and stale agent-state handling.

Why this version is materially better:

The previous version was implementable at a feature level but still left several integration contracts vague enough to create subtle regressions in the current app. The revised plan now calls out shared-session isolation, legacy path protection, exact machine-readable errors, and dynamic schema refresh, which are the kinds of details that determine whether agent edits are safe in the real running platform.

## Implementation Pass 1

Implemented the readable live draft milestone.

Delivered:

- Backend draft models, service, and router for `GET` and `PUT /api/v1/workflow-drafts/{workflow_id:path}`.
- Atomic workflow-local `draft.json` writes.
- Isolated draft validation using a fresh `SessionManager`, preserving the active `/graph` session.
- Machine-readable `409 draft_revision_conflict` and `423 workflow_locked` responses.
- Workspace-root agent context generation with `agent-state.json`, `AGENTS.md`, and `CLAUDE.md`.
- Frontend draft API and `useWorkflowDraftStore`.
- Canvas draft autosave alongside existing IndexedDB fallback.
- Workflow open/startup draft recovery.
- Save/run/export/editor-open draft flush or freshness checks.
- Tests covering draft synthesis, writes, stale revisions, nested workflow ids, execution locks, draft store behavior, and touched component regressions.

Intentional deferrals:

- The read-only `bioimageflow-agent` CLI commands are still pending.
- Draft promotion endpoint is still pending; save currently uses the existing workflow save endpoint and refreshes the draft afterward.
- Typed `draft_updated` WebSocket events and remote draft reconciliation are still pending.
- Structured agent mutation operations are still pending.

Why the plan changed:

The implementation made clear that the first stable slice should be the platform-visible live draft and UI safety guards. The CLI should now build on top of this working API rather than being included in the first implementation commit.
