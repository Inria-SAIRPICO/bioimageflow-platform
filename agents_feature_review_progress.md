# Agents Feature Review Progress

## Baseline And Plan Reviews

Baseline commit: `d384a7e` (`docs: plan agent workflow draft support`).

The review loop moved the design from a frontend-owned unsaved state with future agent support to a backend-mediated draft model with optimistic revisions, route-safe `/api/v1/workflow-drafts/{workflow_id:path}` endpoints, machine-readable conflicts, isolated draft validation, stale-overwrite guards, and explicit workflow lifecycle rules.

Important corrections made during review:

- Avoided `/workflows/{id}/draft` because it can collide with existing catch-all workflow routes.
- Required initial draft load before frontend autosave so the first write can satisfy `expected_revision`.
- Required save/run/export freshness guards before exposing writable agent edits.
- Settled draft persistence as `GraphState` plus validation metadata; derived workflow/export sections are regenerated on save/export.
- Required per-workflow locking and saved-content revision checks to prevent concurrent writes from both winning.
- Required stale `agent-state.json` detection for backend restart, port/workspace changes, and active-workflow mismatch.
- Kept MVP graph mutation root-scoped; nested sub-workflow addressing is deferred.

## Implementation Status

All backend-draft source-of-truth milestones are implemented.

| Milestone | Implementation result | Validation |
|-----------|-----------------------|------------|
| M1 | Dirty export saves the draft before exporting. Commit `ee91b46`. | MenuBar dirty-export tests passed. |
| M2 | Workflow runs use draft revisions. Commit `ef06d96`. | Backend draft-run tests and frontend `RunButton`/`execution` tests passed. |
| M3 | Workflow creation, new workflow, and save-as flows promote/save drafts. Commit `82885d6`. | `MenuBar` suite passed 33 tests. |
| M4 | Stale agent context is rejected. Commit `b72c0ee`. | Agent CLI suite passed 11 tests. |
| M5 | Invalid draft operations are rejected. Commit `cb2f761`. | Backend draft router passed 25 tests, backend agent/draft regression passed 37 tests, and `ruff` passed. |
| M6 | Existing remote draft conflict UX is covered directly. Commit `423064d`. | `CanvasView.test.ts` passed 81 tests; focused frontend suite passed 139 tests; `bun run type-check` and `bun run lint` passed. |

## Final Review Notes

- The source of truth for an open editable workflow is the backend draft.
- `workflow.json` is still the saved/exported artifact and is updated by save/promotion flows.
- Export does not serialize stale frontend memory; dirty export saves the draft first.
- Milestone 6 did not add a new backend `workflow_saved` WebSocket event. That event is not part of the implemented contract.
- The remaining real deferrals are intentional: no automatic graph merge and no nested sub-workflow mutation addressing.
