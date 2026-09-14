---
orphan: true
---

# Platform test campaign checkpoint

Last updated: 2026-09-14.
Objective: strengthen the platform through main GUI journeys and bug fixes, then complete systematic coverage of all implemented in-scope features.
Orchestrator: GPT-5.6 Sol/high with focused context; ordinary workers: Sol/medium; specialist: Astra/high.
The [plan](platform-test-plan.md) defines priorities, coverage obligations, commit/worktree rules, and the final completion gate.
The campaign is incomplete; this checkpoint is a planning update, not a new application certification.

## Next three actions

1. Reconcile Git/worktrees and preserve the unfinished ISSUE-005 Run Selected reproduction, then assign its bounded Astra/high contract assessment; no disposition is recorded yet.
2. Complete the main GUI create/open → inspect tool → add/connect → edit → run → inspect exact results → save/reopen journey, reusing adequate existing tests and independently continuing while ISSUE-005 is assessed if their contracts permit.
3. Complete everyday editing/persistence, followed by nested workflow editing; use the plan's ordered feature waves and keep all remaining feature obligations in the inventories.

Use the current catalog contract: single-click opens/toggles bottom tool information, double-click adds one node, and drag is a separate creation gesture.
Commit `eb0dc74` implements and tests this owner-approved change; earlier single-click creation evidence is historical.
Do not restart completed library releases, source-identity repairs, or the existing backend/frontend/browser scope-selection infrastructure.

## Feature priorities and milestones

| ID / wave | State | Evidence or remaining obligation |
| --- | --- | --- |
| T01 dependencies | Complete | Published BioImageFlow 0.7.1/core 0.3.1 and Wetlands 2.4.1 integration; retained release and worker evidence in [Campaign evidence](platform-test-evidence.md). |
| T02 fixture foundations | Complete | Genuine Generate metadata, compatible whole-DataFrame wiring, exact results, and sequential worker fixture established. |
| T03 systematic inventory | Partial | [GUI](coverage-gui.md), [Workflow](coverage-workflows.md), and [Runtime](coverage-runtime.md) inventories need stable feature IDs and completion of all applicable scenario obligations. |
| T04 known maintenance | Completed batch | Hot reload, recovery/cache fixtures, ToolsPanel routing, and mutation serialization repaired; new findings retain their own issue status. |
| T05 scope selection | Implemented | Backend, frontend-unit, Chromium, and Firefox selectors are drift-audited; browser collection evidence alone does not certify execution. |
| Wave 1 / ISSUE-005 | Open | Exact Run Selected request received unrelated missing-tool errors; specialist assessment queued, test-only work preserved. |
| Wave 2 / main workflow | Partial coverage | Existing real tool/wiring/run/CRUD journeys provide a foundation; prove the complete GUI path and exact result/persistence assertions. |
| Wave 3 / editing | Gaps | Reconnect, parameter controls, rename, clipboard, undo/redo, shortcuts, persistence, and switching remain to reconcile and cover. |
| Wave 4 / nested workflows | Gaps | Private edit/apply/discard/reopen and connected-parent behavior need complete journeys. |
| Waves 5–6 / lifecycle and remaining features | Gaps | Failure/cancellation/rerun/cache/results plus settings, datasets, authoring, integrations, and remaining user actions. |
| T06 / wave 7 final coverage | Pending | Every implemented in-scope feature/scenario mapped and verified, all required suites executed, manual/external boundaries completed or explicit limitations accepted. |

The three inventories own detailed rows; this summary must not become a competing feature list.
Ordering is not a reduction in final scope.

## Ownership and unresolved decisions

The preserved `campaign/t05-run-selected` worktree is at `.worktrees/t05_run_selected`, based on `b6072f5`, with an unfinished change to `frontend/tests/e2e/execution.spec.ts`.
Its prior Sol/medium worker reported a reproducible HTTP 422 in Chromium; Firefox and completion gates were not run because the product issue remained unresolved.
Confirm worktree contents and worker/process state before resuming; a historical agent name does not establish active ownership.
The reproduction predates the new catalog gesture contract, so reconcile affected setup before reuse.
ISSUE-005 is queued for Astra assessment, not reviewed; other resolved issue decisions are in [Campaign issues](platform-test-issues.md).
No implementation worker is assigned by this documentation update.

## Retained evidence and restart discipline

Completed runs, exact historical counts/durations, revisions, release identities, and limitations are in [Campaign evidence](platform-test-evidence.md).
Latest catalog behavior validation is associated with `eb0dc74`; prior broad completion is associated with `f2eb9d8`, not a blanket certificate for newer code.
Use actual Git state, the issue record, and applicable evidence to decide which checks are invalidated.
Keep only active tasks, next actions, and open decisions here; update evidence and inventory rows at each integrated feature boundary.
Commit every resolved task promptly, isolate parallel writers in dedicated worktrees, and preserve unfinished ownership/evidence at interruption.
For this checkpoint's commit, use `git log -1 -- docs/developer/platform-test-progress.md`.
