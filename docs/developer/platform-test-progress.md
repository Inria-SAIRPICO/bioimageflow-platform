---
orphan: true
---

# Platform test campaign checkpoint

Last updated: 2026-09-17.
Objective: establish objective basic-use readiness through the fixed gate, then complete systematic coverage of all implemented in-scope features unless the owner explicitly pauses with a durable backlog.
Orchestrator: GPT-5.6 Sol/high with focused context; ordinary workers: Sol/medium; specialist: Astra/high.
The [plan](platform-test-plan.md) defines priorities, coverage obligations, commit/worktree rules, and the final completion gate.
**Basic-use gate passed; owner chose to continue with Tier 1B; systematic campaign incomplete.**
The fixed Basic-Use gate passed on evaluated revision `50c1af485edef8ebfaca7971ee99e8717694f85e`; on 2026-09-16, the owner chose to continue with Tier 1B.

The owner approved an obligation-based inventory denominator before Wave 6, immediate durable recording of remote milestones, a visible headed or artifact-backed browser confidence checkpoint at each major GUI-wave boundary, reachability-first blocker classification, and a distinct Basic-Use Readiness Gate before lower-priority campaign work.
The plan and restart prompt contain the normative rules; this checkpoint records their activation without duplicating their detail.

## Next actions

1. Resume the highest-reach remaining Tier 1B shell, root editing, recursive workflow, execution, and result gaps in the [GUI](coverage-gui.md), [workflow](coverage-workflows.md), and [runtime](coverage-runtime.md) inventories; ISSUE-011 is resolved by the integrated read-time status projection.
2. Preserve the observed BioImageFlow 0.7.2 sequential row-progress timing as a documented limitation; assess user impact before classifying it as a defect or dependency change.
3. After all broader Primary-GUI obligations are verified, proceed to Tier 2 important extensions before Tier 3 advanced/native/external checks.

Use the current catalog contract: single-click opens/toggles bottom tool information, double-click adds one node, and drag is a separate creation gesture.
Commit `eb0dc74` implements and tests this owner-approved change; earlier single-click creation evidence is historical.
Do not restart completed library releases, source-identity repairs, or the existing backend/frontend/browser scope-selection infrastructure.

## Feature priorities and milestones

| ID / wave | State | Evidence or remaining obligation |
| --- | --- | --- |
| T01 dependencies | Complete | Published BioImageFlow 0.7.1/core 0.3.1 and Wetlands 2.4.1 integration; retained release and worker evidence in [Campaign evidence](platform-test-evidence.md). |
| T02 fixture foundations | Complete | Genuine Generate metadata, compatible whole-DataFrame wiring, exact results, and sequential worker fixture established. |
| T03 systematic inventory | Audited dashboard established; closure incomplete | The [obligation dashboard](platform-test-dashboard.md) maps all 98 inventory rows by stable ID to explicit scenario contracts and is mechanically verified by `scripts/test check docs`. After real Direct failure/recovery, 227/457 overall obligations are verified (49.7%) and 205/220 primary-GUI obligations are verified (93.2%). |
| T04 known maintenance | Completed batch | Hot reload, recovery/cache fixtures, ToolsPanel routing, and mutation serialization repaired; new findings retain their own issue status. |
| T05 scope selection | Implemented | Backend, frontend-unit, Chromium, and Firefox selectors are drift-audited; browser collection evidence alone does not certify execution. |
| Wave 1 / ISSUE-005 | Verified | Commits `38e14f2` and `8908388` implement the Astra boundary, exact manager/compiler regressions, dangling-edge guard, and exact Chromium/Firefox GUI journey; integrated `scripts/test check app` passes. |
| Wave 2 / main workflow | Verified | Commit `4208769` covers create/open, exact tool information, double-click/drag creation, pointer connection, parameter persistence, real Direct execution, exact GUI rows, Save, workflow switching, and identical graph reopen; the exact journey passes Chromium and Firefox. |
| Wave 3 / editing | Primary batch verified | Commits through `dd20821` verify node state, connection/history, clipboard identity/structure, active-root shortcuts, text-entry focus safety, typed parameters, Shift-drag box selection, atomic bulk Delete with Undo/Redo, accepted root output Clear/refusal, accepted backend-draft recovery, sibling switching, close Cancel, visible CAS conflict, Keep my canvas, and exact Discard/reopen. Lower-priority inventory boundaries remain for final systematic closure. |
| Wave 4 / nested workflows | Primary batch verified | Commits through `e817d77` verify private Apply/discard, stale-parent refusal, destructive port confirmation, forwarded-interface reconciliation, failed-write retry with unrelated parent edits, concurrent newer private state, remount dirtiness, real nested Direct execution with scoped durable results, and recursive agent-copy ownership with same-class/different-byte sources and independent copied execution. Commit `3422e1c` resolves nested DataFrame publication remaining dirty after accepted Save and passes the complete Chromium browser lane plus the exact Firefox journey. Packaged-crash and other lower-priority recursive boundaries remain for final closure. |
| Wave 5 / execution and results lifecycle | Primary execution/results batches verified | Commits through `d1072ce` verify the primary real GUI result-table filter/sort/page/direct-page/CSV journey. Commits `c050207` and `d8bd740` add real merged/stacked multi-selection, exact source attribution/navigation, persistent/reset widths, and bounded subpixel drag assertions. BioImageFlow 0.7.2 and integrated `da2ced2` verify real cooperative Stop and successful rerun. Commit `4676ffb` adds the real sequential failure, single enriched contextual error, unlocked GUI correction, successful rerun, exact rows, and output-file bytes. Commits `624d986` through `7ab16e6` add real typed image/file viewing, the actual Avivator GUI action, and byte-level mixed-latest versus pinned-run export verification. A visible headed Chromium run of the primary create/run/inspect/save/reopen journey passed at `8574adc`. True thumbnail provisioning and native viewer/dialog checks remain later external/manual boundaries. |
| Wave 6 / tiered remaining features | Tier 1B milestone: primary GUI above 80% | The fixed 73-cell gate passed at `50c1af485edef8ebfaca7971ee99e8717694f85e`, and the owner chose to continue. Commits through `4a03750` add canvas/nested/result/workflow refusal and recovery coverage; ISSUE-012's stale workflow-collision suggestion is fixed. The integrated `4a03750` Chromium browser lane passed 89/89, and the representative create/build/run/inspect/save/reopen journey passed headed. Commits `0043397` and `58520b5` resolve ISSUE-011's backend-restart status projection with separate process-level HTTP and browser evidence. Primary GUI reached 179/220 (81.4%); Tier 1B and later systematic obligations remain incomplete. |
| T06 / wave 7 final coverage | Pending | Every implemented in-scope feature/scenario mapped and verified, all required suites executed, manual/external boundaries completed or explicit limitations accepted. |

The three inventories own detailed rows; this summary must not become a competing feature list.
Ordering is not a reduction in final scope.

## Basic-Use Readiness Gate status

The dashboard-content tally is **73 V / 73 required (100.0%)** with 0 runnable gaps, 0 in-progress cells, 0 externally blocked cells, and 0 unassessed cells.
This tally was recomputed after integrated workflow CRUD evidence changed the former seven `WF-LIF-003` and `WF-LIF-010` gate cells to `V`; the dashboard verifier passes and a direct lookup of all 73 named `ID.cell` entries finds no non-`V` state.
The gate passed on the one clean evaluated revision `50c1af485edef8ebfaca7971ee99e8717694f85e`: the audited collection contained 28 exact selectors per browser, all 28 passed in Chromium and all 28 passed in Firefox, the backend/frontend/documentation completion gates passed, and the representative create/edit/connect/run/inspect/save/reopen journey passed headed in Chromium on the available display.
The reachable-blocker audit found no supported-path critical or high-impact basic-use defect: all ten recorded campaign issues are resolved except ISSUE-006's reviewed `not-a-defect` disposition, and no required gate cell, selector, retry, skip, or unresolved flake remains.
The gate-evaluated dashboard was **172 / 457 overall verified (37.6%)** and **150 / 220 primary-GUI verified (68.2%)**; the current dashboard is **227 / 457 overall (49.7%)** and **205 / 220 primary GUI (93.2%)**, with 0 blocked cells and 6 unassessed overall cells. Neither set of broader denominators makes a systematic-completion claim.
Grouping evidence remains important Primary-GUI Tier 1B coverage and is intentionally outside the smaller 73-cell denominator.
Full browser lanes, external package certification, Tier 1B–3 selectors, native/external application checks, and final systematic certification were not run for this fixed gate and remain owned by their existing campaign inventories and final completion gate.
The exact commands, durations, environment-only blocked first attempts, and exclusions are retained in [Campaign evidence](platform-test-evidence.md).

## Ownership and unresolved decisions

The Tier 1B real Direct recovery worktree integrated at `9698d5b` from task commit `adc6ce5`; it was archived under `/private/tmp`, pruned, and its branch deleted. The integrated exact browser and dev-registry selectors passed after the concurrent Napari environment merge; no complete post-merge scoped lane is claimed.
The Tier 1B nested-edit recovery worktree integrated at `14582d0` from task commit `d2d175e`; its exact browser and cross-browser smoke selectors passed, and its clean worktree was archived under `/private/tmp`, pruned, and branch deleted.
The Tier 1B clipboard failed-write worktree was patch-equivalently integrated at `26551d6` from task commit `2f8617c`, archived under `/private/tmp`, pruned, and its branch deleted.
The Tier 1B depth-two nested cleanup worktree was patch-equivalently integrated at `7575d0e` from task commit `e46f0d3`, archived under `/private/tmp`, pruned, and its branch deleted. The confirmed GUI feedback gap was fixed without changing child-first disposal or adding recursive discard.
The Tier 1B catalog-add recovery worktree integrated at `a44851e` verifies failed draft-write/Retry behavior after a real tool double-click; its worktree was archived under `/private/tmp`, pruned, and its merged branch deleted.
The Tier 1B root interrupted-write recovery task was patch-equivalently integrated at `301c19c` from task commit `051dcaf`, staging only its own spec hunk while preserving concurrent unrelated spec edits. Its exact Chromium/Firefox selectors passed again on the integrated working tree; the task's later cross-browser-smoke run failed in unrelated Chromium workflow CRUD and Firefox editable-import selectors, each of which then passed an exact isolated rerun. Do not claim a passing smoke lane from that interrupted run.
The Tier 1B workflow-dialog worktree integrated at `4a03750` verifies Create/Save As invalid/collision refusal and lossless cancellation, fixes ISSUE-012, and was archived with its merged branch deleted.
The Tier 1B editing worktree integrated at `1d7cbd7` verifies that redundant bulk Enable leaves the accepted draft and Undo history unchanged; its worktree was archived under `/private/tmp`, pruned, and its merged branch deleted.
The Tier 1B grouping worktree integrated at `0dc71b5` verifies failed draft-write recovery through the visible GUI Retry; its worktree was archived under `/private/tmp`, pruned, and its merged branch deleted. Grouping invalid-operation refusal remains open.
The Tier 1B nested-port worktree integrated at `bcedaec` verifies duplicate/blank port-name refusal and failed positional-compaction write recovery with stable IDs; its worktree was archived under `/private/tmp`, pruned, and its merged branch deleted.
The Tier 1B image-viewer worktree integrated at `af1951b` verifies durable result/viewer source identity after reload and a limited manual close/reopen after simulated external viewer HTTP 503; its worktree was archived under `/private/tmp`, pruned, and its merged branch deleted.
The Tier 1B image-backend-recovery worktree integrated at `bfb6197` fixes and verifies visible backend-offset failure/no-panel/retry behavior and stale-cell identity fencing; its worktree was archived under `/private/tmp`, pruned, and its merged branch deleted.
The Tier 1B edge-recovery worktree integrated at `bd92dfc` verifies whole-DataFrame pointer disconnect/reconnect and connected-column-input failure/Retry with exact edge identity; its worktree was archived under `/private/tmp`, pruned, and its merged branch deleted.
The Tier 1B recursive-port worktree integrated at `dd9e231` verifies forwarded-port invalid-name refusal and failed-write recovery plus exposed-node deletion failure/Retry; its worktree was archived under `/private/tmp`, pruned, and its merged branch deleted. Exposed-node invalid-deletion refusal remains open.
The Tier 1B nested-shortcuts worktree integrated at `4ec5dbc` verifies private/root Undo history isolation and active nested/root Save routing; its worktree was archived under `/private/tmp`, pruned, and its merged branch deleted.
The Tier 1B result-selection worktree integrated at `7d9de88` verifies source-pure unrelated-lineage fallback after reload; its worktree was archived and branch deleted.
The Tier 1B cache-lifecycle worktree integrated at `fe0cf9d` verifies downstream invalidation and selected-result clearing across same-process browser reload; its worktree was archived and branch deleted.
ISSUE-011 and `RT-EXE-009.P` are resolved by `0043397` and `58520b5` after GPT-6 Astra/high returned `safe-to-fix`; the Sol/medium implementation worktree was integrated, archived under `/private/tmp`, pruned, and its merged branch deleted.
The Tier 1B result-boundaries worktree integrated at `168b487` verifies numeric filter refusal and recovery with exact source-row identity; its worktree was archived and branch deleted.
The Tier 1B shell-recovery worktree integrated at `75be9c2` verifies the empty-workspace chooser and obsolete startup preference; its worktree was archived and branch deleted.
The Tier 1B everyday-canvas worktree was archived under `/private/tmp`, pruned, and its integrated branch deleted after commit `4456435` verified real incompatible connection refusal and retained graph identity.
The Tier 1B nested-interface worktree was archived under `/private/tmp`, pruned, and its integrated branch deleted after commit `1e84421` verified durable positional publication and atomic exposed-node interface pruning.
The Tier 1B nested-conflict worktree was archived under `/private/tmp`, pruned, and its integrated branch deleted after commit `d86c9b0` verified both explicit GUI conflict choices and parent/private state isolation.
The Tier 1B execution-progress worktree was archived under `/private/tmp`, pruned, and its integrated branch deleted after commit `2c1ff72` verified real worker context through rerun, progress, completion, and reload.
The formerly unrelated `.claude/CLAUDE.md` edit was independently committed by the owner as `aaece1e` and was outside this campaign task.

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
