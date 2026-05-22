# Iterative Review Log

## Baseline

- Item: workflow workspace tree implementation and docs/specs in this branch.
- Goal: remove legacy workflow-file compatibility, restore moving folders and workflows, make folder actions toolbar-based, reduce tree indentation, and validate with tests.
- Max iterations: 3.
- Convergence rule: stop when review agents identify no meaningful blockers or remaining work is outside this cleanup.

## Iteration 1

- Reviewer: Sagan (backend audit), Pascal (frontend audit)
- Meaningful: yes
- Changes:
  - Backend audit identified lingering legacy workflow migration/listing/collision paths and tests to remove.
  - Frontend audit identified always-visible folder row buttons, missing selected-folder toolbar actions, stale folder selection after moves, and PrimeVue default indentation.
- Rationale:
  - These findings directly matched the reported failures and shaped the TDD coverage for the cleanup.
- Deferred:
  - Full browser visual regression coverage for exact indentation measurements.

## Iteration 2

- Reviewer: Popper (critical review), Einstein (validation)
- Meaningful: yes
- Changes:
  - Fixed toolbar deletion so a workflow selected inside a folder deletes the workflow, not the parent folder.
  - Preserved selected-folder state after folder rename/move/delete refreshes.
  - Removed JSON workflow import parsing and rejected non-zip imports at the API boundary.
  - Updated the import file picker to accept ZIP archives only.
  - Updated stale panel-layout spec text to describe toolbar folder actions.
- Rationale:
  - These were blocker findings against the user's latest direction and against the no legacy workflow compatibility requirement.
- Deferred:
  - Browser-level drag/drop and visual indentation screenshots.

## Iteration 3

- Reviewer: Boyle (final validation)
- Meaningful: yes
- Changes:
  - Removed stale workflow migration references from planning docs.
  - Updated backend README workspace layout text to describe workflow directories.
- Rationale:
  - The implementation was validated, but docs still contradicted the clean
    workflow layout requirement.
- Deferred:
  - Historical non-workflow compatibility notes in unrelated graph/settings
    documentation remain outside this workspace-tree cleanup.

## Convergence

- Stopped after: 3 iterations
- Reason: review blockers were addressed and targeted backend/frontend checks pass.
- Final item: commit `eb03eb7` amended in `fix/workflow-tree-cleanup`.
- Residual risk: browser-level drag/drop behavior was covered by component tests,
  not by an end-to-end browser drag/drop test.
