# Agents Feature Plan

## Status

Implemented through the backend-draft source-of-truth plan. The durable source of truth for an open editable workflow is the backend live draft, not stale frontend memory and not direct edits to `workflow.json`.

`workflow.json` remains the saved/exportable workflow artifact. Save and export flows promote or save the current draft first, then use the existing workflow serialization/export path.

## Implemented Architecture

- Workflow-local drafts live at `workspace/workflows/<workflow_id>/.bioimageflow/draft.json`.
- Workspace-root agent context lives under `.bioimageflow/` and points agents to the active workflow, API base URL, health URL, backend/session identity, draft revision, and recommended commands.
- Drafts store canonical `GraphState` plus validation metadata. Agents must not hand-edit derived workflow/export sections.
- Draft reads synthesize revision `0` from `workflow.json` when no dirty draft exists.
- Draft writes and structured operations use optimistic `expected_revision` checks.
- Draft validation is isolated from the active canvas validation/session state.
- Execution locks reject draft writes and mutations.
- Agent context is rejected when stale, including backend restart, port change, workspace switch, or active-workflow mismatch.
- Invalid draft operations fail cleanly and do not partially mutate the graph.

## API And UX Contract

- `GET /api/v1/workflow-drafts/{workflow_id:path}` returns the current draft or a synthesized clean draft.
- `PUT /api/v1/workflow-drafts/{workflow_id:path}` replaces the draft after revision and validation checks.
- Structured draft mutation operations are validated platform operations; agents do not construct full workflow files by hand for common edits.
- Run flushes/checks the draft and executes the selected draft revision.
- Save/new/save-as creation flows promote or save the draft through the platform save path.
- Dirty export saves the draft before exporting.
- Remote draft conflicts are user-mediated:
  - `Apply Remote` loads and applies the remote draft graph.
  - `Keep Mine` clears the remote notice and schedules the local graph for autosave/draft save.
  - `Review JSON` fetches and displays the remote draft graph without applying it.

No new backend `workflow_saved` WebSocket event is part of the implemented contract.

## Completed Milestones

| Milestone | Result | Evidence |
|-----------|--------|----------|
| 1 | Dirty export saves the draft before export. | `ee91b46`; MenuBar dirty-export test coverage. |
| 2 | Workflow execution runs drafts by revision. | `ef06d96`; backend draft-run and frontend `RunButton`/`execution` tests. |
| 3 | Workflow creation, new workflow, and save-as flows promote/save drafts. | `82885d6`; `MenuBar` suite passed 33 tests. |
| 4 | Agent CLI/context rejects stale context. | `b72c0ee`; agent CLI suite passed 11 tests. |
| 5 | Invalid draft operations are rejected. | `cb2f761`; backend draft router passed 25 tests, backend agent/draft regression passed 37 tests, and `ruff` passed. |
| 6 | Remote draft conflict UX residual was closed with direct component coverage. | `423064d`; `CanvasView.test.ts` passed 81 tests, focused frontend suite passed 139 tests, `bun run type-check` and `bun run lint` passed. |

## Remaining Residuals

- Automatic merge of concurrent graph edits is intentionally not implemented; users choose between local and remote draft state.
- Nested sub-workflow mutation addressing remains deferred. Current draft operations are root-graph scoped unless a future `scope` model is added.
- A separate `workflow_saved` WebSocket event is explicitly deferred/not needed for this implementation.
