---
orphan: true
---

# Platform test campaign issues

Use the [campaign escalation protocol](platform-test-plan.md).
Statuses: `open`, `sol-investigating`, `astra-review`, `safe-to-fix`, `needs-owner`, `externally-blocked`, `resolved`, or `not-a-defect`.
Record the actual specialist model/reasoning and disposition; an unassigned queue entry is not completed Astra review.
Owner decisions and product intent take precedence over an agent's proposed fix.

## ISSUE-001 — Source-update preview and replaced workflow identity

Status: resolved after GPT-6 Astra/high `safe-to-fix` assessment and bounded Sol/medium repair.
At platform `353b425` with BioImageFlow 0.7.1, core 0.3.1, and Wetlands 2.4.1, a disposable supported-lifecycle reproduction showed an old generation-1 preview successfully mutating an exactly recreated generation-3 destination whose original and recreated artifact hashes were both `sha256:9256f7d81e082034f47aa62edbd9892a3687f944782dc4c49e3fcee66da25061`.
No existing lifecycle invalidation removed prepared tokens, and Apply captured only the current generation after the preview boundary.
The specialist found v2 §§10 and 12, v1 §2.4.2, and `PLATFORM_CONTEXT.md` decisive: the delayed operation must conflict without mutation, and a private captured-generation comparison inside the existing mutation lock is sufficient.

The repair stores the destination generation for both source-refresh and Python-rebuild previews, captures it atomically with the destination document, and compares it inside Apply's mutation lock before reads, staging, or writes.
It raises the existing `WorkflowSourceConflict`, preserving HTTP 409 and leaving artifact hashing and public schemas unchanged.
Regressions prove exact same-artifact recreation rejection with unchanged graph, hash, generation, and owned files, plus lifecycle serialization during preview.
Focused source tests passed and `scripts/test check backend` passed in 82s at `6d42c05` plus the settled backend diff: 1,577 deterministic tests passed, 9 deselected, and 7 logging-order tests passed; external package certification was intentionally not run by this lane.
The fix commit is discoverable with `git log -1 -- backend/src/bioimageflow_server/services/workflow_sources.py`.
Workspace switching and source-workflow recreation were not reproduced and are not claimed as resolved defects.

## ISSUE-002 — Logging specification versus contextual-log tests

Status: resolved as a stale specification row; no product behavior changed.
At `fcb4408`, the v1 WebSocket log-event table around line 910 describes logs as intentionally unscoped without execution/canvas context.
The audit reported deliberate contextual execution-log behavior in the logging bridge and `frontend/tests/e2e/error-handling.spec.ts`, while environment logs remain global.
Commit `a8d9533` intentionally introduced that behavior together with the v2 §1.8 normative requirement, typed WebSocket validation, source-time provenance safeguards, frontend filtering, and regression coverage.
The older v1 §2.5 table row was therefore stale and has been aligned with the established contract: execution-attributed BioImageFlow and Wetlands records carry the complete immutable execution context, while non-execution tool, environment, thumbnail, and platform logs omit it.
Affected files: `platform_specs_v1.md`, `PLATFORM_CONTEXT.md`, and the runtime coverage inventory.
Validation: `scripts/test check docs` passed in 2s at `353b425` plus the ISSUE-002 documentation diff; an initial sandboxed attempt was externally blocked fetching `furo` and is not counted as a test failure.
The resolution commit is discoverable with `git log -1 -- docs/developer/platform-test-issues.md`.

## ISSUE-003 — Tools Panel row click did not create a node

Status: resolved after GPT-6 Astra/high `safe-to-fix` assessment and bounded Sol/medium repair.
At `87fe704`, the named `SeedNumbers` browser journey clicked the rendered catalog row but observed zero nodes.
Static and reproduced evidence showed `ToolsPanel.vue` emitted `add-tool`, while its raw Dockview registration had no listener and Vue component events do not bubble.
V1 §§3.3.1 and 3.4 explicitly require click creation, and the existing state-free active-canvas command facade already owns synchronous root/nested routing, viewport projection, execution locks, undo, and persistence.

The repair calls `addToolNode(toolName)` once through that facade and retains the existing local event contract; App, canvas sessions, APIs, and backend remain unchanged.
Unit regressions cover a real rendered row, non-creating secondary actions, active nested/root routing, missing ownership, and disposed resources.
Distinct real click and drag journeys assert named metadata/schema, unchanged first-click viewport, exact pins/panel content, accepted persistence, and requested drag position in Chromium and Firefox.
The focused unit files passed 96 tests in 6s; Chromium click/drag passed in 15s/16s and Firefox in 14s/17s.
Frontend lint, all 1,260 unit tests, and build passed in the completion run; its only failure was new test-mock type declarations, whose exact type-check passed after correction.
The Chromium completion run passed both changed journeys before later failing from independent ISSUE-004 mutation contention.
The fix commit is discoverable with `git log -1 -- frontend/src/components/panels/ToolsPanel.vue`.
The owner later changed the interaction contract: single-click now toggles catalog information and double-click creates the node; the original event-routing defect remains relevant to the double-click creation path.

## ISSUE-004 — Ordinary mutation contention reported as execution lock

Status: resolved.
Two Chromium completion runs passed 54 or 55 preceding cases, then the child-port workflow-interface save received HTTP 423 claiming execution was in progress; the exact case passed in a fresh runtime.
GPT-6 Astra/high disproved an execution lifecycle leak and reproduced the exact 423 with no execution ever started by holding an ordinary draft validation while issuing Save.
`ExecutionManager.is_running` includes the ordinary idle-mutation reservation even while status is `idle` with no execution identity, and Save immediately rejects that aggregate flag.
The established repair boundary is to queue ordinary Save behind an admitted mutation while retaining Run exclusion during mutations and mutation rejection during actual starting/running execution.
No arbitrary browser wait, forced unlock, or early execution ownership release is authorized.
The repair distinguishes actual execution activity from idle mutation reservations, queues root Save through the existing admission lease, and preserves Run exclusion while a mutation owns that lease.
Deterministic manager and router regressions prove that ordinary mutations serialize, Save waits and succeeds after held draft validation, Run remains excluded, and actual execution still rejects mutation.
`scripts/test check app` passed in 140s with 1,590 backend tests and 9 deselected, 1,260 frontend units, and 10 critical Chromium journeys; the full Chromium lane then passed all 57 tests in 106s, including the formerly suite-order-dependent child-port case at position 56.
The fix commit is discoverable with `git log -1 -- backend/src/bioimageflow_server/services/execution.py`.

## ISSUE-005 — Run Selected rejects an unrelated invalid branch

Status: resolved in `38e14f2` plus robustness follow-up `8908388`; GPT-6 Astra/high returned `safe-to-fix` and Sol/medium implemented the bounded repair.
At `b6072f5`, the isolated Run Selected journey builds an accepted three-node graph containing valid `SeedNumbers(seed_valid) -> IncrementNumbers(increment_valid)` DataFrame work and a disconnected `MissingCampaignTool(unrelated_invalid)` node.
The UI verifies the exact workflow, graph, edge, missing-dependency modal, and validation state, then the public Run Selected action submits `nodes: ["increment_valid"]`, the exact accepted draft revision, and the complete graph.
Chromium reaches that request but receives HTTP 422 and surfaces only the unrelated missing-tool validation error.
Inspection points to `ExecutionManager._start_reserved`: it compiles the complete graph as required, then rejects every validation error without limiting acceptance to the selected node plus its upstream dependencies.
V1 §2.4.5 and v2 §§8–9 require selected-plus-upstream admission while still compiling the full accepted graph without destructive pruning; the existing router regression mocks the manager and therefore does not cover this boundary.
The specialist reproduced exact `(1, one, 2)`, `(2, two, 3)`, and `(3, three, 4)` output through the public library compiler after the manager rejected two `missing_tool` diagnostics scoped only to `unrelated_invalid`.
The safe boundary derives selected roots and transitive upstream IDs from the accepted graph, filters only diagnostics proven outside that scope, retains unscoped or unresolved diagnostics, blocks invalid or unknown requested targets, and leaves full Run, draft validation, locking, source capture, and public library execution unchanged.
Orchestrator review reproduced a pre-integration `KeyError` for dangling edge endpoints; `8908388` makes scope traversal total while preserving compiler-produced global edge diagnostics as blocking.
Fifteen selected manager cases, the real compiler/manager regression, and the exact Chromium/Firefox GUI journey pass on the integrated revision; `scripts/test check app` passes all cross-stack phases.

## ISSUE-006 — Nested stale-parent conflict has no explicit resolution path

Status: `not-a-defect`; GPT-6 Astra/high confirmed the baseline stale-parent refusal satisfies v2 §7, and the uncommitted overwrite proposal must not be integrated.
At worktree base `299eebe`, applying an accepted private nested snapshot after the owning parent child graph changes correctly refuses the mutation, but only reports an error and leaves the editor dirty without exposing the v2 §7 choice between latest parent content and the user's private changes.
The Sol reproduction proposes identity-bound `Use latest parent` and `Keep my changes` actions that recheck the exact conflicting parent child graph before replacing the private snapshot or applying local content.
The proposed graph comparison did not guard workflow generation, surrounding bindings/edges, newer private edits during awaits, lock/remount state, or a second parent change; its `use-parent` path could label never-applied private edits clean.
The safe boundary is to retain conflict refusal, durable dirty private state, and the already specified confirmed Discard/reopen workflow; add browser evidence for those existing semantics without overwrite controls.
Destructive connected-port removal is independent because v2 §§5 and 7 explicitly require confirmation, but it needs captured effects, cancel-as-zero-mutation, post-await identity/content/connection/lock checks, and awaited application.

## ISSUE-007 — Stop does not reach an active cooperative Wetlands task

Status: resolved through BioImageFlow 0.7.2 and platform integration `da2ced2` after GPT-6 Astra/high established the upstream defect, reviewed the repair, and returned `safe-as-is` for release.
Scope: platform branch `campaign/execution-failure-cancel` at `cb5b881`, based on platform `9cfa76d`, with installed BioImageFlow 0.7.1, bioimageflow-core 0.3.1, and Wetlands 2.4.1.
The deterministic GUI journey runs a real sequential Wetlands ProcessingTool in a distinct worker process, uses a socket handshake instead of arbitrary sleeps, and exposes the library-supported injected task cancellation flag.
Before Stop it proves exact workflow, accepted draft revision, execution identity, completed upstream source, running worker, worker/backend PID isolation, reload/WebSocket recovery of the same running identity, and visibly disabled Save and Clear actions without draft mutation.
The GUI Stop request returns HTTP 200, but a 15-second state-based poll receives `{state: running, cancellationAcknowledged: false}` instead of idle plus a worker acknowledgment; the cooperative tool never observes `task.cancel_requested`.
The final clean Chromium reproduction is `scripts/test focus e2e --project=chromium tests/e2e/execution-cancellation.spec.ts` at `cb5b881`: it fails only at the terminal cancellation assertion in 47s, then explicitly releases the worker, waits for idle, verifies workflow deletion, and closes without worker error or leaked runtime state.
The focused real-worker fixture contract passes 2 tests in 14s, and frontend E2E lint passes; Firefox and broader lanes were correctly not run while the exact Chromium selector remains red.

V1 §§2.4.5 and 3.5.6 require Stop to cancel the active execution, discard the current node's partial output, retain completed outputs, unlock later mutations, and show the stopped terminal state.
The platform already follows its public boundary: `ExecutionManager._stop_expected()` calls `Workflow.cancel()`.
BioImageFlow 0.7.1 sets only its execution-context cancel event; row and batch dispatch check that event before entering Wetlands `task.wait_for()` and do not observe it while the active task is waiting.
Wetlands task cancellation is cooperative, and the corrected fixture implements that contract by accepting the injected task, polling its cancellation flag through bounded socket timeouts, acknowledging cancellation, and producing no partial output.
The initial non-cooperative fixture was rejected by Astra and is not evidence for the defect.

A platform workaround that marks the run idle, cancels only the asyncio wrapper, reaches into private task state, or kills an environment could unlock mutation while a worker still writes and is not authorized.
The required repair was assigned to the sibling BioImageFlow library: propagate cancellation to unfinished active tasks, drain every possible writer before returning or reuse, retain the corrected platform regression, run the library's required CI, publish an updated dependency, then adopt it here and run the exact Chromium and Firefox journey plus affected completion lanes.
No platform semantic-contract decision remained unclear; the owner authorized expanding the campaign back into the sibling library and release workflow on 2026-09-14.
Before integration, the clean platform worktree preserved commits `4318814`, `7912ab9`, and `cb5b881` and the exact red GUI evidence.
BioImageFlow commits `bdfb777`, `1cf95f4`, and `cf2efd4` propagate cancellation to active row and batch tasks, register every returned handle immediately, stop later submissions, drain partial submissions and interrupted waits, ignore late results, and place the real held-writer regressions in the blocking Complete Wetlands gate.
The release commit `659acda` prepared BioImageFlow 0.7.2; exact GitHub CI run `34863426923` and manually selected Complete Wetlands run `34863450754` passed, publication run `34864151902` succeeded, and the package index reported 0.7.2 available.
The platform adopted the published wheel in `da2ced2` together with the deterministic held-worker fixture and GUI regression.
The exact cancellation journey passed Chromium 1/1 in 27s and Firefox 1/1 in 24s, and `scripts/test check app` passed in 111s with 1,609 backend tests and 9 deselected, 1,295 frontend tests, 7 logging-order tests, and 13 critical Chromium journeys; the lane intentionally omitted external certification and non-critical browser tests.
The journey proves an isolated worker PID, exact workflow/revision/run identity, reload recovery, locked Save/Clear controls, HTTP 200 Stop, cooperative acknowledgement before idle, retained exact completed-source rows, absent partial worker results, and a successful rerun with exact values from one non-backend worker PID.
An initial exact Chromium attempt was blocked before collection by sandbox port allocation and is not a test failure.
The final Astra reachability review classified Wetlands' theoretical BaseException-listener ordering hazard as a dependency follow-up rather than a blocker: BioImageFlow's internal listener performs no user callback on the cancellation event, and the platform does not expose the artificial listener used by the probe.
No claim is made that cancellation is immune to interruption at every possible dependency instruction.
Both completed worktrees were archived under `/private/tmp`, pruned, and their integrated branches deleted.

## ISSUE-008 — Nested Save remains dirty after successful accepted writes

Status: resolved by commit `3422e1c` after GPT-6 Astra/high independently reproduced the failure on unmodified main `215a5fc`, established the exact canonicalization mismatch, and bounded the repair.
The exact Chromium selector `frontend/tests/e2e/workflow-interface.spec.ts:352` completes both the nested accepted-snapshot PUT and parent draft PUT with HTTP 200, but the nested title remains `Child *` instead of becoming clean.
It failed 1/1 with a 6.1s test duration in a 40s runner; the initial sandbox attempt was blocked before collection by port allocation.
The first trace and error context were archived with the investigation worktree under `/private/tmp/nested-save-review-3422e1c/frontend/test-results/workflow-interface-workflo-99a22-hrough-the-parent-interface-chromium/`.

The two DataFrame input constructors in `CanvasView.vue` omit `default`, while backend graph validation supplies `default: null`; the adjacent field-input constructor already emits the canonical property.
Both writes persist the accepted child into the parent, but `acknowledgeApplied` correctly retains the local draft for concurrent-edit safety and strict `graphDocumentsEqual` therefore sees the omitted property as a difference.
Using the production comparator, adding only `default: null` in memory makes the local and accepted graphs equal.
The temporarily unbound parent input can remain validation-invalid because the v1 workflow PUT contract allows saving invalid graphs; it is not the cause of the failed clean state.

V2 §§5, 7, 12, and 15 require ordinary publication, private editing, and Save applying the accepted snapshot.
The repair adds `default: null` to both DataFrame input constructors, preserves strict equality and the newer-private-edit/retry/identity/conflict guards, and covers positional publication plus child-port forwarding inside a nested editor.
The unchanged exact clean-title journey passed Chromium and Firefox, `scripts/test check frontend` passed 1,297 tests plus lint, typecheck, and build, and `scripts/test check browser` passed all 81 Chromium journeys.
The integrated worktree was archived and pruned after completion.

## ISSUE-009 — Preliminary worker failure duplicates the contextual error log

Status: resolved by commit `4676ffb` after the real sequential failure journey reproduced two node-attributed contextual ERROR rows.
Wetlands first publishes a failed progress update without a message or traceback, then the terminal run callback receives the enriched worker exception and remote traceback.
The execution manager previously formatted the empty preliminary update as a generic “Execution failed” node log and later published the useful terminal log, so Error History and Logger presented the same failure twice at different detail levels.

V1 §§3.7 and 3.11 require contextual failure presentation and readable logs.
The repair retains the immediate failed node state, omits only the empty-detail preliminary ERROR, and leaves the terminal callback responsible for the single enriched node-attributed traceback.
A focused manager regression asserts one contextual ERROR with node provenance and remote traceback.
The real GUI journey additionally proves the failed node has no partial result, completed upstream output remains, editing unlocks, a GUI parameter correction persists at the next draft revision, and a distinct successful rerun returns exact rows and file bytes.
It passed Chromium and Firefox, the existing cancellation journey remained green, and `scripts/test check app` passed on the patch-equivalent pre-rebase revision.

## ISSUE-010 — Save As reapplies the source graph identity to the destination

Status: resolved by integrated commit `a25ac17` (task-equivalent `4789238`).
At the pre-fix Wave 6 revision, the exact Chromium selector `frontend/tests/e2e/workflow-crud.spec.ts`, “save-as creates an independent graph without copying results and switches exactly”, failed in 33s because the destination workflow showed and persisted the source graph's name/display identity instead of the requested destination identity.
The Save As UI first called the duplicate endpoint, then issued a second destination Save with the source canvas graph and locally applied that same source graph under destination presentation metadata.
That second write overwrote the duplicate service's canonical destination-owned graph identity and split the displayed workflow identity from the graph authority, contrary to v2 §12 and the `PLATFORM_CONTEXT.md` graph-owned identity invariant.

The repair passes the captured canvas graph in the atomic duplicate request, then loads and applies the destination's canonical workflow presentation; it removes the second destination PUT and does not change backend or public API schemas.
The focused MenuBar selector “saves a copy from the canvas that opened Save As after activation changes” proves the initiating canvas graph is sent despite later activation changes, no extra PUT occurs, and the loaded destination graph is applied.
The browser regression proves destination graph-owned name/display name, distinct artifact identity, absent copied results, exact original graph/result retention, independent copy-only rename/save, workflow switching, and both saved/draft graphs after reload.
It passed Chromium 1/1 in 13s and Firefox 1/1 in 15s; `scripts/test check frontend` passed 1,297 tests plus lint, type checking, and build in 19s; and `scripts/test check browser` passed all 83 Chromium journeys in 222s with no failures, skips, or retries.
Invalid destination input, duplicate-service failure/rollback, stale identity refusal, and source-owning copy variants were not exercised by this repair and remain separate dashboard gaps.

## ISSUE-011 — Clear status reverts after backend restart

Status: resolved by `0043397` and `58520b5` after a GPT-6 Astra/high `safe-to-fix` read-only review; the earlier same-process reconnect repair was `fe0cf9d`.
In a two-node Direct workflow, Run followed by Clear on the upstream node removes only its latest result and marks it `unexecuted` with its dependent `out_of_date`; the live UI and same-process browser reload now agree.
The stored accepted root draft still contains pre-Clear `validation.node_statuses`, because `_read_validated_authority_snapshot()` returns an existing draft verbatim, while a new `ExecutionManager` starts with empty live statuses; the new read-time projection corrects the response without rewriting that durable draft.
Before the repair, stopping and restarting the backend against the same workspace could therefore display the cleared source as `executed` even though its latest result query returned 404.
The pre-fix restart regression reproduced the false `executed` source status; a separate OS Python process then reproduced and verified the repaired HTTP GET against the same workspace with fresh backend services.
The repair must keep the accepted graph/revision and CAS contract unchanged, preserve historical `last_result`, and avoid resurrecting selected output pointers.
The repair projects fresh cache statuses on authoritative accepted-draft reads, using the compiled accepted graph, public workflow plan, and retained latest-output metadata rather than persisting Clear-adjusted validation.
An enabled `pending_upstream` node with a retained latest output must present `out_of_date`; without retained output it remains `unexecuted`, so globally remapping that library plan state would be wrong.
Compile outside the workflow mutation lock, then recheck workflow generation, storage path, accepted graph and revision and project plan/latest status under the same lock used by Clear commit; retry a changed snapshot.
This was moderate backend correctness work without a new schema or owner decision, not a one-line fix: writing status into the draft after cache deletion would leave a crash/write-failure gap, and Clear has no accepted draft revision with which to fence that write.
The source revision is `fe0cf9d`; authoritative contracts include v1 §2.4.5, v2 execution/cache semantics, and `PLATFORM_CONTEXT.md` result-lifecycle invariants.
The first GPT-6 Astra/high request did not execute because of a usage limit; a subsequent read-only review returned `safe-to-fix` on current product revision `d5e45ee` and supplied the bounded design above.
The Sol/medium worker added process-restart, accepted-revision race, delete/recreate identity, storage-path switch, disabled downstream, slash-scoped latest-record, and exact GUI Clear/rerun regressions; the dedicated worktree was integrated and archived with its branch deleted.
On integrated `58520b5`, the exact backend restart selector passed 1/1 in 6s and the exact Chromium/Firefox GUI Clear selector passed 2/2 in 29s.
The worker's `scripts/test check backend` passed 1,618 selected tests plus seven logging-order tests with nine external deselections in 102s; frontend, docs, and Chromium browser-smoke checks passed separately on patch-equivalent content.
The attempted combined `scripts/test check app` did not pass because the sandbox denied two backend socket binds; those exact fixtures passed 3/3 with authorized local access, followed by the successful backend and browser-smoke checks.
No single Playwright session spans an actual backend-process restart: process-level HTTP and same-process browser reload evidence are separate; full/external certification and nested-canvas scoped clearing remain separate campaign obligations.

## ISSUE-012 — Workflow collision suggestion survives a later name edit

Status: resolved by `4a03750` with a bounded Sol/medium repair; no specialist review was needed because the dialog contract and local cause were clear.
The Create/Save As collision path offered an alternative workflow ID after HTTP 409, but the dialog kept that suggestion as a persistent prop override when the user subsequently changed the display name.
The preview and submitted destination could therefore remain tied to the old collision rather than the newly entered name.
The repair keeps the suggestion active only until the user edits the display name, then derives a fresh ID; it preserves the server's collision proposal before that edit and does not alter the backend collision contract.
A focused dialog unit asserts the new preview and submitted ID; a real Chromium/Firefox Create and Save As journey proves invalid-name refusal, occupied-ID 409, suggestion replacement, cancellation, unchanged source and occupied workflow state, absent canceled destination, and exact reload identity.
At patch-equivalent task revision `4823752`, the focused unit passed in 2s, exact Chromium in 14s, exact Firefox in 19s, `scripts/test check frontend` passed 1,299 units plus lint/typecheck/build in 28s, and cross-browser smoke passed 16/16 in each browser in 109s; the integrated Chromium browser lane passed 89/89 at `4a03750` in 347s.
V1 workflow-dialog behavior was clarified in the same task.

## ISSUE-013 — Napari probe output bound reports timeout at a one-second deadline

Status: open; separate from Tier 1B export behavior, queued for focused Napari test/implementation ownership before a broad backend certification claim.
After merge `7b0b937` of the Napari environment feature, the export batch's elevated `scripts/test check backend` passed 1,724 tests with nine external deselections but failed `tests/test_services/test_napari_environments.py::test_probe_runner_enforces_time_and_output_bounds`: the output-bound subcase expected `napari_probe_output_limit` and received `napari_probe_timeout` at its one-second subprocess deadline.
The exact selector reproduced the mismatch in isolation after browser load ended, so this is not credited as a passing backend lane or dismissed as a one-off export failure.
No supported GUI user impact or cause is yet established; keep the classification as a test/runtime regression, not a Tier 1B release blocker or a confirmed Napari product defect.
The next owner should inspect probe output/deadline ordering and reproduce the exact selector on the current revision before changing the Napari-owned implementation or test threshold.

## ISSUE-014 — Workflow title intermittently remains “No workflow” in Chromium smoke

Status: open; source of intermittent behavior is not yet established.
At task revision `1f0dfb3`, `scripts/test check cross-browser-smoke` passed seven Chromium critical journeys then failed `frontend/tests/e2e/critical-operation-races.spec.ts:453` because the workflow title remained “No workflow” after opening; the same smoke lane passed Firefox 18/18.
Earlier Tier 1B smoke runs showed the same late Chromium title symptom, while an isolated exact selector passed on a prior batch. The current task's isolated exact attempt never collected the test because backend application startup timed out after 60s, so it does not establish a passing or failing current-revision title behavior.
No supported-path data loss, wrong graph, or root cause has been demonstrated; do not classify this yet as a product identity defect or dismiss the repeated smoke failure as passing.
Next: isolate the exact Chromium selector after backend startup is stable, then reproduce the preceding suite order or use a five-repeat exact run if timing is suspected; inspect tab/open readiness and distinguish a real workflow-open race from a test oracle race. Keep the smoke lane red until a passing rerun on the relevant revision.

## ISSUE-015 — Late progress callback can overwrite a newer execution's status

Status: resolved by `f09a8a7` with a bounded Sol/medium repair; the execution-context contract was explicit, so no specialist redesign was needed.
A focused manager reproduction retained the completed first run's progress callback, started a distinct second run, then invoked the first callback: before the fix it changed the second run's status and retained progress.
The repair checks that the callback's captured immutable execution context is still the active running context before projecting status or publishing progress; stale events are dropped without changing the later run's status or event bus.
The exact focused regression passed after the repair, and real sequential-worker browser refusal/cancellation/rerun journeys passed Chromium and Firefox. This test injects a late callback and does not assert Wetlands itself emits one.
The cross-stack app completion command remains red for unrelated ISSUE-013, and browser smoke timed out before collection at the 60s E2E backend startup limit; neither lane is claimed as passing evidence for this fix.

## ISSUE-016 — Startup selects another workflow's recovery before the valid last-opened workflow

Status: open; a dedicated Sol/medium worktree owns a narrow startup-selection fix and exact browser regressions.
At integrated source `0ab6bac`, `scripts/test check browser-all` failed Firefox `frontend/tests/e2e/agent-draft-sync.spec.ts:287` after opening an agent-copy workflow: reload showed the original dirty workflow instead of the copy. The same run failed Chromium `frontend/tests/e2e/nested-execution.spec.ts:173` because reload opened an older clipboard workflow rather than the newly chosen recursive workflow. The lane passed 62 Chromium tests before that failure, left 41 unrun, and had an additional runner-level error; Firefox failed early. Neither browser project passed.
V1 §4.3 requires startup to load the valid last-opened workflow first, then consider a newer IndexedDB recovery snapshot for that same workflow. `frontend/src/services/startupWorkflow.ts` currently puts `loadMostRecentAutoSave().name` ahead of the valid last-opened ID in its candidate list. A focused startup unit regression fails before the fix, selecting `recovered` instead of `last-opened`; same-workflow recovery is separately covered. App tab activation also writes the last-opened preference asynchronously, so the exact contribution of preference-write timing to each browser failure still needs isolated reproduction.
Next: run the exact failed Firefox selector before editing the product, restore contract ordering while retaining same-workflow recovery, validate exact Chromium/Firefox affected journeys and a scoped completion check, then rerun invalidated milestone browser acceptance. This issue is not a result-table width defect; that test explicitly reopened its intended workflow after reload.

## New issue record template

Use a stable ISSUE-NNN heading with status, task/dependency scope, source revision and packages, observed versus expected behavior, authoritative references, exact reproduction/selector/browser, evidence paths, attempted changes, and unresolved question.
Add specialist model/reasoning, disposition and rationale, owner decision if needed, implementation/test/specification files, completion evidence, commit, and resume condition.
For resolved issues, retain the decision and commit references without carrying full logs into the master checkpoint.
