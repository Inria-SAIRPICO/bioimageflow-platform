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

1. Begin Wave 5 real failure, cancellation, correction/rerun, and mutation-lock recovery journeys with deterministic synchronization.
2. Extend result lifecycle coverage through cache reuse/staleness, table operations, and exact exported content.
3. Continue Wave 6 settings, datasets, authoring, integrations, and remaining user actions without dropping the final systematic inventory obligations.

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
| Wave 1 / ISSUE-005 | Verified | Commits `38e14f2` and `8908388` implement the Astra boundary, exact manager/compiler regressions, dangling-edge guard, and exact Chromium/Firefox GUI journey; integrated `scripts/test check app` passes. |
| Wave 2 / main workflow | Verified | Commit `4208769` covers create/open, exact tool information, double-click/drag creation, pointer connection, parameter persistence, real Direct execution, exact GUI rows, Save, workflow switching, and identical graph reopen; the exact journey passes Chromium and Firefox. |
| Wave 3 / editing | Primary batch verified | Commits through `dd20821` verify node state, connection/history, clipboard identity/structure, active-root shortcuts, text-entry focus safety, typed parameters, Shift-drag box selection, atomic bulk Delete with Undo/Redo, accepted root output Clear/refusal, accepted backend-draft recovery, sibling switching, close Cancel, visible CAS conflict, Keep my canvas, and exact Discard/reopen. Lower-priority inventory boundaries remain for final systematic closure. |
| Wave 4 / nested workflows | Primary batch verified | Commits through `e817d77` verify private Apply/discard, stale-parent refusal, destructive port confirmation, forwarded-interface reconciliation, failed-write retry with unrelated parent edits, concurrent newer private state, remount dirtiness, real nested Direct execution with scoped durable results, and recursive agent-copy ownership with same-class/different-byte sources and independent copied execution. Packaged-crash and other lower-priority recursive boundaries remain for final closure. |
| Waves 5–6 / lifecycle and remaining features | Gaps | Failure/cancellation/rerun/cache/results plus settings, datasets, authoring, integrations, and remaining user actions. |
| T06 / wave 7 final coverage | Pending | Every implemented in-scope feature/scenario mapped and verified, all required suites executed, manual/external boundaries completed or explicit limitations accepted. |

The three inventories own detailed rows; this summary must not become a competing feature list.
Ordering is not a reduction in final scope.

## Ownership and unresolved decisions

The ISSUE-005 implementation and old failing reproduction worktrees were archived under `/private/tmp`, pruned, and their integrated or superseded branches deleted.
The Wave 2 worktree was archived under `/private/tmp`, pruned, and its patch-equivalent branch deleted after integration.
The first Wave 3 worktree was archived under `/private/tmp`, pruned, and its patch-equivalent branch deleted after integration.
The destructive nested-interface worktree was archived under `/private/tmp`, pruned, and its patch-equivalent branch deleted after integrating `b2e1152`, `f59419b`, and `cf794fb`.
The bulk-delete/output-clear worktree was archived under `/private/tmp`, pruned, and its patch-equivalent branch deleted after integrating `5aaac41` and `30faeb6`.
The recursive-source worktree was archived under `/private/tmp`, pruned, and its patch-equivalent branch deleted after integrating `13a384b`, `9561b25`, `c911eb3`, and `e817d77`.
The root-discard worktree was archived under `/private/tmp`, pruned, and its patch-equivalent branch deleted after integrating `dd20821`.
The nested-execution worktree was archived under `/private/tmp`, pruned, and its patch-equivalent branch deleted after integrating `fd96f8f`.
The clipboard/shortcut worktree was archived under `/private/tmp`, pruned, and its patch-equivalent branch deleted after integrating `3bb5a10` and `790345a`.
The parameter-controls worktree was archived under `/private/tmp`, pruned, and its patch-equivalent branch deleted after integrating `1261326`.
ISSUE-006 has a `not-a-defect` disposition; no overwrite-control implementation is authorized, and its uncommitted proposal must be discarded.
The first Wave 4 worktree was archived under `/private/tmp`, pruned, and its patch-equivalent branch deleted after integration.
The second Wave 3 worktree was archived under `/private/tmp`, pruned, and its patch-equivalent branch was deleted after integrating six commits.
ISSUE-005 is resolved on main; other resolved issue decisions are in [Campaign issues](platform-test-issues.md).

## Retained evidence and restart discipline

Completed runs, exact historical counts/durations, revisions, release identities, and limitations are in [Campaign evidence](platform-test-evidence.md).
Latest catalog behavior validation is associated with `eb0dc74`; prior broad completion is associated with `f2eb9d8`, not a blanket certificate for newer code.
Use actual Git state, the issue record, and applicable evidence to decide which checks are invalidated.
Keep only active tasks, next actions, and open decisions here; update evidence and inventory rows at each integrated feature boundary.
Commit every resolved task promptly, isolate parallel writers in dedicated worktrees, and preserve unfinished ownership/evidence at interruption.
For this checkpoint's commit, use `git log -1 -- docs/developer/platform-test-progress.md`.
