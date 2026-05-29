# Agent Features Completion Plan

## Goal

Finish the agent workflow-editing feature so terminal agents can safely modify the open BioImageFlow workflow and the frontend updates without a manual page reload.

The intended end state is:

- The backend draft is the workflow source of truth for the open workflow.
- The frontend canvas is a projection of that draft and notices external agent writes.
- Agent writes update the canvas automatically when there is no frontend conflict.
- If both the frontend and an agent changed the workflow, the user gets a simple conflict choice.
- Agent-facing docs explain the platform clearly enough for a fresh local model.

## Conflict Policy

Use three conflict actions now. Keep richer visual diff support for later.

### 1. Apply Agent Changes

The frontend replaces the current canvas graph with the latest backend draft graph.

Use when:

- The user has no meaningful local edits, or
- The user decides the agent change should win.

Behavior:

- Fetch latest draft.
- Apply `draft.graph` to the canvas.
- Update tracked draft revision.
- Mark the canvas dirty/clean from `dirty_against_saved`.
- Clear pending frontend autosave state for the previous graph.

Pros:

- Simple mental model.
- Best default when the user asked an agent to edit the workflow.
- Avoids stale frontend overwrites.

Cons:

- Discards local canvas edits if the user explicitly chooses it during conflict.

### 2. Discard Agent Changes

The frontend keeps the current canvas graph and writes it back as a new backend draft revision.

Use when:

- The user wants their current canvas edits to win.

Behavior:

- Fetch latest draft to get its newest `draft_revision`.
- PUT the current frontend graph with `expected_revision` set to that newest revision and `updated_by: "frontend"`.
- Keep the current canvas visible.
- Clear the remote-change warning after the write succeeds.

Pros:

- Simple.
- Preserves the user's visible work.

Cons:

- Agent edits are overwritten, except for recovery through history/backups if later added.

### 3. Clone Workflow With Agent Changes

Keep the current frontend workflow open, but save the agent draft graph into a new workflow copy.

Suggested naming:

- Start with `<current_name>_agent_2` or `<current_name>_version_2`.
- Increment the suffix until the workflow name is free.
- Prefer a clear generated display name, for example `<display name> (agent version 2)`.

Behavior:

- Fetch latest backend draft graph.
- Create a new workflow with the generated name.
- Save the agent draft graph into that new workflow/draft.
- Restore or keep the original workflow's current frontend graph as the open canvas.
- Notify the user where the agent version was saved.

Pros:

- Preserves both versions without requiring a merge UI.
- Good fallback when both sides changed substantially.

Cons:

- Produces extra workflows.
- Does not help the user merge differences yet.

### Deferred: Show Diff In VS Code

Do not implement now. It is probably useful later, but it needs a stable textual representation, temp-file lifecycle rules, VS Code command integration, and a decision about how to apply chosen hunks back to the graph.

## Execution Strategy

Use a master/worker/reviewer model. The master coordinates worktrees, keeps this
plan aligned with reality, integrates reviewed branches, and runs final
cross-slice validation. Implementation agents work in dedicated git worktrees so
parallel edits do not trample each other. Review agents review the completed
worktree before the master integrates it.

All implementation work is TDD:

- Each worker writes or updates failing tests first in its worktree.
- The worker implements the smallest production change that makes those tests
  pass.
- The worker runs the focused test set and relevant lint checks before handing
  off.
- The reviewer runs or inspects the same focused tests, checks that the tests
  would have failed without the production change, and looks for integration
  risks.
- The master integrates only reviewed work, then reruns the broader affected
  tests from the main workspace.

Suggested worktrees:

- `../bioimageflow-agent-backend-events`: Milestone 1.
- `../bioimageflow-agent-frontend-store`: Milestone 2.
- `../bioimageflow-agent-canvas-refresh`: Milestone 3.
- `../bioimageflow-agent-conflict-ui`: Milestone 4.
- `../bioimageflow-agent-guardrails`: Milestone 5.
- `../bioimageflow-agent-docs`: Milestone 6.

Parallelization rules:

- Start Milestone 1 and Milestone 6 immediately in parallel. They touch mostly
  disjoint files.
- Start Milestone 2 after the backend event payload contract is stable enough
  to type against. It may run in parallel with late Milestone 1 cleanup if the
  payload schema is fixed.
- Start Milestone 3 after Milestone 2 exposes stable draft-store methods.
- Start Milestone 4 after Milestone 3 defines the apply-latest-draft path and
  conflict-state shape.
- Start Milestone 5 after Milestones 3 and 4 establish the shared conflict
  resolution API.
- Keep docs updated in parallel after every milestone, but final docs polish
  happens after the code behavior is known.

Review gates:

- Every worker gets a dedicated review agent that has the worker branch/worktree,
  the relevant milestone section, and no unrelated conversation history.
- The review agent must focus on correctness, missed tests, stale plan
  assumptions, and whether the implementation matches the documented behavior.
- If the reviewer finds material issues, the worker fixes them in the same
  worktree and reruns focused validation before integration.
- After integration, the master updates this plan if the actual implementation
  differs from the intended sequence, naming, API shape, or conflict behavior.

## Implementation Plan

### Milestone 1: Backend Draft Change Events

Status: implemented and reviewed.

Add a WebSocket server-to-client message for draft changes.

Backend changes:

- Add `WorkflowDraftChangedMessage` to `backend/src/bioimageflow_server/models/ws.py`.
- Payload fields:
  - `type: "workflow_draft_changed"`
  - `workflow_id`
  - `draft_revision`
  - `updated_by`
  - `updated_at`
  - `dirty_against_saved`
- Add `broadcast_workflow_draft_changed` and `publish_workflow_draft_changed` to the WebSocket manager.
- Wire `WorkflowDraftService.put_draft` or the draft router so a successful PUT publishes the event.
- Do not publish on failed PUT, validation failure response construction, or GET.
- Decide whether frontend writes should also broadcast. Preferred: yes, broadcast all successful writes, and the frontend ignores revisions it already applied.

TDD:

- Backend unit test that `put_workflow_draft` publishes one event after a successful agent write.
- Test that stale-revision 409 does not publish.
- Test message schema rejects malformed payloads.

Acceptance:

- Agent PUT causes connected clients to receive `workflow_draft_changed` without polling.

Implementation notes:

- Added `workflow_draft_changed` to the backend WebSocket schema and manager.
- Successful draft PUTs publish one event for every writer; GET, 409, 423,
  404, and 422 do not publish.
- Integrated after dedicated review; focused backend tests and ruff passed.

### Milestone 2: Frontend Draft Event Ingestion

Status: implemented and reviewed.

Teach the frontend WebSocket dispatcher and draft store to notice external draft revisions.

Frontend changes:

- Add a typed handler for `workflow_draft_changed` in `frontend/src/composables/useWebSocket.ts`.
- Add draft-store methods such as:
  - `noteRemoteChange(message)`
  - `loadLatestDraft(id)` or `fetchLatestDraft(id)`
  - `clearPendingSave()` if needed
- Ignore events for other workflows.
- Ignore revisions less than or equal to the applied/current revision.
- Track `remoteAvailableRevision`, `remoteUpdatedBy`, and enough metadata to display a useful prompt.

TDD:

- Store tests for ignoring old/current revisions.
- Store tests for marking a newer agent revision as remote available.
- WebSocket dispatch test for routing `workflow_draft_changed` to the draft store.

Acceptance:

- When an agent writes to the active workflow, the frontend knows a newer draft exists within the existing WebSocket connection.

Implementation notes:

- The frontend WebSocket dispatcher routes `workflow_draft_changed` into the
  workflow draft store.
- The draft store tracks `remoteAvailableRevision`, remote writer/time/dirty
  metadata, and ignores stale or wrong-workflow events.
- Integrated after dedicated review; focused frontend tests, type-check, and
  eslint passed.

### Milestone 3: No-Conflict Auto-Apply

Status: implemented and reviewed.

Automatically apply agent changes when the user has no local conflict.

Frontend changes:

- In the active canvas layer, watch draft-store remote-change state.
- If the active workflow matches and there are no local unsaved/pending frontend edits, fetch and apply the latest draft graph.
- Reuse the existing `bioimageflow:apply-graph` path or extract a shared apply helper so Vue Flow state, graph-sync state, dirty state, and draft revision stay aligned.
- Ensure applying a remote graph does not trigger an immediate autosave loop back to the backend.

Conflict-free condition:

- No pending debounced save.
- No in-flight save.
- `uiStore.hasUnsavedChanges` is false, or the current dirty state is known to be the same draft revision.
- Active workflow id matches the event workflow id.

TDD:

- Canvas/component test: remote event with clean canvas applies graph.
- Store test: applying latest draft updates `appliedDraftRevision` and clears stale marker.
- Regression test: applying remote graph does not call `scheduleSave`.

Acceptance:

- If an agent adds a node while the user is not editing, the node appears on the canvas without reload.

Implementation notes:

- Active root canvases now auto-load and apply newer remote drafts when no
  frontend draft save is queued or in flight.
- Auto-apply is gated to the active canvas tab and excluded for sub-workflow
  editors.
- Canvas activation tracks the active workflow in the draft store so events for
  the active workflow are accepted.
- Integrated after reviewer-requested scoping fixes; focused canvas/store tests,
  type-check, and eslint passed.

### Milestone 4: Conflict Dialog With Three Actions

Status: implemented and reviewed.

Add a small conflict UI when remote agent changes arrive while the frontend has local edits.

Frontend changes:

- Add a conflict banner/dialog near the canvas or app shell.
- Message should be plain: "This workflow changed outside the canvas." Include writer and revision if useful.
- Actions:
  - Apply agent changes
  - Keep my canvas
  - Save agent version as copy
- Avoid using "backend", "live draft", or other internal phrasing in the UI.

Action behavior:

- Apply agent changes: fetch latest draft and apply it to the current canvas.
- Keep my canvas: fetch latest draft revision, then PUT current canvas graph as a new frontend revision.
- Save agent version as copy: create a new workflow with a free suffix and save the latest agent graph there, while keeping the current canvas open.

TDD:

- Component test for showing conflict only when active workflow has local edits.
- Test each action calls the expected store/API methods.
- Test clone suffix generation avoids existing workflow names.
- Test failed action leaves the dialog open and shows an error.

Acceptance:

- Agent/frontend conflicts can be resolved without reload and without silently losing both versions.

Implementation notes:

- Active root canvases show a conflict banner when a remote draft exists and
  the canvas has local unsaved or pending-save state.
- The three actions are implemented as: apply remote draft, overwrite the
  remote draft with the current canvas, or save the remote draft graph as a
  separate saved workflow copy.
- Saving an agent version as copy does not mark the original conflict handled;
  the original conflict remains until the user chooses apply or keep.
- Integrated after reviewer-requested copy-action fixes; focused frontend
  tests, type-check, eslint, and diff checks passed.

### Milestone 5: Save/Run/Export Guardrails

Status: implemented and reviewed.

Make all critical operations respect remote draft changes.

Frontend changes:

- Ensure save, run, export, and selected-node execution flush pending frontend saves first.
- Then check latest draft revision before proceeding.
- If remote changes exist, show the same conflict dialog instead of throwing a generic error.
- Export keeps the stricter requirement: warn that the workflow will be saved, save the current resolved draft first, then export the saved workflow.

TDD:

- Save/run/export tests for remote change detection.
- Export test: confirmation -> save current draft -> export saved workflow.
- Regression test: no stale `props.graph` is used for execution after a remote apply.

Acceptance:

- The user cannot accidentally run/export an obsolete visible graph when an agent has already updated the draft.

Implementation notes:

- Save, run, run selected, and export now block unresolved remote draft
  conflicts and ask the user to resolve workflow changes first.
- Run and selected-node execution use the current graph-sync graph after
  freshness checks instead of stale props.
- Export now opens a save-before-export confirmation, saves the current
  resolved workflow, then exports the saved workflow.
- Integrated after dedicated review; focused frontend tests, type-check, eslint,
  and diff checks passed.

### Milestone 6: Documentation And Agent Workspace Polish

Status: implemented and reviewed.

Make agent docs match the actual feature behavior.

Changes:

- Rewrite generated `AGENTS.md` in `agent_workspace_context.py` so it starts with a simple platform explanation.
- Use user-facing terms before internal terms.
- Explain that the canvas should update automatically, and what the agent should do after writing a draft.
- Keep `docs/agents/` task-oriented:
  - quick start
  - editing nodes
  - connections
  - execution
  - conflict expectations
  - troubleshooting
- Keep `.bioimageflow/platform-source/` described as read-only reference material.

TDD:

- Update generated-doc tests for the new wording and structure.
- Refresh the live workspace through `ensure_agent_workspace_context` after implementation.

Acceptance:

- A fresh simple agent can understand what BioImageFlow is and perform common edits without prior context.

Implementation notes:

- Generated `AGENTS.md` now mentions frontend auto-refresh, conflict UI choices,
  conflict blocking for save/run/export, and save-before-export.
- Expanded docs under `docs/agents/` were updated to match the implemented
  draft sync, conflict, and export behavior.
- Reviewed with a dedicated docs reviewer; focused docs tests passed.

## Recommended Technical Choices

Use WebSocket events instead of polling for the primary implementation because the platform already has a WebSocket connection and dispatch layer. Polling can remain a fallback if WebSocket is disconnected, but it should not be the main design unless event delivery proves unreliable.

Represent conflict state in the draft store, but keep graph application in the canvas/app-shell layer. The store should know revisions and metadata; the canvas owns Vue Flow mutation.

Do not attempt automatic graph merges in this phase. Full-graph replacement plus three explicit user choices is safer and easier to reason about.

## Residual Risks

- The current dirty flag may not distinguish "unsaved against saved workflow" from "local edits not yet written to backend draft". Milestone 3 must be careful here.
- Debounced frontend saves can race with an agent write. The expected-revision check prevents silent overwrite, but the UI must surface the conflict cleanly.
- Cloning the agent version needs clear workflow naming and should avoid changing the active workflow unexpectedly.
- A future diff view should use a stable graph serialization and explicit apply semantics; it should not depend on arbitrary temp files.
