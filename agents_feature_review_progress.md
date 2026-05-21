# Agents Feature Review Progress

## Baseline

Created the initial plan around a backend-mediated live draft plus an agent command bridge. The baseline intentionally preserves the existing frontend-owned graph architecture while giving terminal agents access to current unsaved workflow state.

Key baseline decisions:

- Keep `workflow.json` as the manual-save artifact.
- Store current unsaved state in `.bioimageflow/draft.json`.
- Add draft endpoints with optimistic revision checks.
- Add an agent CLI/API bridge so agents avoid hand-editing workflow JSON.
- Add frontend reconciliation for agent-originated draft updates.

Baseline commit: pending.
