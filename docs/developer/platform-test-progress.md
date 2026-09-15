---
orphan: true
---

# Platform test campaign checkpoint

Last updated: 2026-09-15.
Objective: establish objective basic-use readiness through the fixed gate, then complete systematic coverage of all implemented in-scope features unless the owner explicitly pauses with a durable backlog.
Orchestrator: GPT-5.6 Sol/high with focused context; ordinary workers: Sol/medium; specialist: Astra/high.
The [plan](platform-test-plan.md) defines priorities, coverage obligations, commit/worktree rules, and the final completion gate.
The campaign is incomplete; this checkpoint is a planning update, not a new application certification.

The owner approved an obligation-based inventory denominator before Wave 6, immediate durable recording of remote milestones, a visible headed or artifact-backed browser confidence checkpoint at each major GUI-wave boundary, reachability-first blocker classification, and a distinct Basic-Use Readiness Gate before lower-priority campaign work.
The plan and restart prompt contain the normative rules; this checkpoint records their activation without duplicating their detail.

## Next three actions

1. Recompute the fixed 73-cell Basic-Use matrix from the integrated dashboard and verify its exact selectors in Chromium and Firefox on one current revision.
2. Complete the required backend, frontend, and documentation checks plus the headed or artifact-backed confidence run without intervening product changes.
3. If every gate condition passes, commit the durable evidence and ask the owner whether to continue into Tier 1B or pause with the systematic campaign explicitly incomplete.

Use the current catalog contract: single-click opens/toggles bottom tool information, double-click adds one node, and drag is a separate creation gesture.
Commit `eb0dc74` implements and tests this owner-approved change; earlier single-click creation evidence is historical.
Do not restart completed library releases, source-identity repairs, or the existing backend/frontend/browser scope-selection infrastructure.

## Feature priorities and milestones

| ID / wave | State | Evidence or remaining obligation |
| --- | --- | --- |
| T01 dependencies | Complete | Published BioImageFlow 0.7.1/core 0.3.1 and Wetlands 2.4.1 integration; retained release and worker evidence in [Campaign evidence](platform-test-evidence.md). |
| T02 fixture foundations | Complete | Genuine Generate metadata, compatible whole-DataFrame wiring, exact results, and sequential worker fixture established. |
| T03 systematic inventory | Audited dashboard established; closure incomplete | The [obligation dashboard](platform-test-dashboard.md) maps all 98 inventory rows by stable ID to explicit scenario contracts and is mechanically verified by `scripts/test check docs`. After correcting applicability and crediting the integrated image/export, grouping, and workflow CRUD evidence, 172/457 overall obligations are verified (37.6%) and 150/220 primary-GUI obligations are verified (68.2%). |
| T04 known maintenance | Completed batch | Hot reload, recovery/cache fixtures, ToolsPanel routing, and mutation serialization repaired; new findings retain their own issue status. |
| T05 scope selection | Implemented | Backend, frontend-unit, Chromium, and Firefox selectors are drift-audited; browser collection evidence alone does not certify execution. |
| Wave 1 / ISSUE-005 | Verified | Commits `38e14f2` and `8908388` implement the Astra boundary, exact manager/compiler regressions, dangling-edge guard, and exact Chromium/Firefox GUI journey; integrated `scripts/test check app` passes. |
| Wave 2 / main workflow | Verified | Commit `4208769` covers create/open, exact tool information, double-click/drag creation, pointer connection, parameter persistence, real Direct execution, exact GUI rows, Save, workflow switching, and identical graph reopen; the exact journey passes Chromium and Firefox. |
| Wave 3 / editing | Primary batch verified | Commits through `dd20821` verify node state, connection/history, clipboard identity/structure, active-root shortcuts, text-entry focus safety, typed parameters, Shift-drag box selection, atomic bulk Delete with Undo/Redo, accepted root output Clear/refusal, accepted backend-draft recovery, sibling switching, close Cancel, visible CAS conflict, Keep my canvas, and exact Discard/reopen. Lower-priority inventory boundaries remain for final systematic closure. |
| Wave 4 / nested workflows | Primary batch verified | Commits through `e817d77` verify private Apply/discard, stale-parent refusal, destructive port confirmation, forwarded-interface reconciliation, failed-write retry with unrelated parent edits, concurrent newer private state, remount dirtiness, real nested Direct execution with scoped durable results, and recursive agent-copy ownership with same-class/different-byte sources and independent copied execution. Commit `3422e1c` resolves nested DataFrame publication remaining dirty after accepted Save and passes the complete Chromium browser lane plus the exact Firefox journey. Packaged-crash and other lower-priority recursive boundaries remain for final closure. |
| Wave 5 / execution and results lifecycle | Primary execution/results batches verified | Commits through `d1072ce` verify the primary real GUI result-table filter/sort/page/direct-page/CSV journey. Commits `c050207` and `d8bd740` add real merged/stacked multi-selection, exact source attribution/navigation, persistent/reset widths, and bounded subpixel drag assertions. BioImageFlow 0.7.2 and integrated `da2ced2` verify real cooperative Stop and successful rerun. Commit `4676ffb` adds the real sequential failure, single enriched contextual error, unlocked GUI correction, successful rerun, exact rows, and output-file bytes. Commits `624d986` through `7ab16e6` add real typed image/file viewing, the actual Avivator GUI action, and byte-level mixed-latest versus pinned-run export verification. A visible headed Chromium run of the primary create/run/inspect/save/reopen journey passed at `8574adc`. True thumbnail provisioning and native viewer/dialog checks remain later external/manual boundaries. |
| Wave 6 / tiered remaining features | Tier 1A evidence integrated; gate validation pending | Current main includes the Save As identity repair, independent copy/results/switch/reload and deletion evidence, permanent-P0 multi-node grouping/rewiring/undo/save/reload evidence, and the reconciled dashboard. Content credit is not a current-revision gate pass; run the gate checks before the owner decision. |
| T06 / wave 7 final coverage | Pending | Every implemented in-scope feature/scenario mapped and verified, all required suites executed, manual/external boundaries completed or explicit limitations accepted. |

The three inventories own detailed rows; this summary must not become a competing feature list.
Ordering is not a reduction in final scope.

## Basic-Use Readiness Gate status

The dashboard-content tally is **73 V / 73 required (100.0%)** with 0 runnable gaps, 0 in-progress cells, 0 externally blocked cells, and 0 unassessed cells.
This tally was recomputed after integrated workflow CRUD evidence changed the former seven `WF-LIF-003` and `WF-LIF-010` gate cells to `V`; the dashboard verifier passes and a direct lookup of all 73 named `ID.cell` entries finds no non-`V` state.
The gate itself has **not passed**: the 73 credited cells have not yet been re-executed through every required exact Chromium and Firefox selector together with the backend, frontend, documentation, and headed or artifact-backed current-revision checks defined by the plan.
Grouping evidence remains important Primary-GUI Tier 1B coverage and is intentionally outside the smaller 73-cell denominator.
Do not present the owner decision until the current-revision execution evidence and reachable-blocker audit are durably recorded.

## Ownership and unresolved decisions

The ISSUE-005 implementation and old failing reproduction worktrees were archived under `/private/tmp`, pruned, and their integrated or superseded branches deleted.
The Wave 2 worktree was archived under `/private/tmp`, pruned, and its patch-equivalent branch deleted after integration.
The first Wave 3 worktree was archived under `/private/tmp`, pruned, and its patch-equivalent branch deleted after integration.
The destructive nested-interface worktree was archived under `/private/tmp`, pruned, and its patch-equivalent branch deleted after integrating `b2e1152`, `f59419b`, and `cf794fb`.
The bulk-delete/output-clear worktree was archived under `/private/tmp`, pruned, and its patch-equivalent branch deleted after integrating `5aaac41` and `30faeb6`.
The recursive-source worktree was archived under `/private/tmp`, pruned, and its patch-equivalent branch deleted after integrating `13a384b`, `9561b25`, `c911eb3`, and `e817d77`.
The root-discard worktree was archived under `/private/tmp`, pruned, and its patch-equivalent branch deleted after integrating `dd20821`.
The ISSUE-007 platform and sibling-library worktrees were archived under `/private/tmp`, pruned, and their integrated branches deleted after BioImageFlow 0.7.2 publication and platform integration at `da2ced2`.
The execution failure/correction/rerun worktree was archived under `/private/tmp`, pruned, and its integrated branch deleted after commit `4676ffb` passed the applicable completion lane.
The image/file/export worktree was archived under `/private/tmp`, pruned, and its integrated branch deleted after commits `624d986`, `8c3b19d`, `4a5015d`, and `7ab16e6` passed the applicable completion lane.
The first obligation-dashboard worktree was archived under `/private/tmp`, pruned, and its integrated branch deleted after commits `65d1d84` and `01ddbd9` established the provisional denominator.
The dashboard-correction worktree was archived under `/private/tmp`, pruned, and its integrated branch deleted after commits `c679bab` and `6ea986c` completed the semantic audit, stable-ID mapping, and mechanical verifier.
The workflow CRUD worktree was archived under `/private/tmp`, pruned, and its integrated branch deleted after commits `a25ac17` and `0b3ee1e` landed.
The multi-node grouping worktree was archived under `/private/tmp`, pruned, and its integrated branch deleted after commits `a36a4cb`, `da0ded6`, and `152c82b` landed.
The result multi-selection/width worktree was archived under `/private/tmp`, pruned, and its integrated branch deleted after commits `c050207` and `d8bd740` reached main.
The ISSUE-008 worktree was archived under `/private/tmp`, pruned, and its integrated branch deleted after commit `3422e1c` passed the applicable completion lanes.
The result-table worktree was archived under `/private/tmp`, pruned, and its patch-equivalent branch deleted after integrating `ec0e32f`, `52006ae`, and `d1072ce`.
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
