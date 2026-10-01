---
orphan: true
---

# Active platform test campaign issues

Read only the issue relevant to the assigned task.
Completed decisions and detailed history for ISSUE-001–ISSUE-017 are retained in the [issue archive](archive/platform-test-issues-through-tier-1b.md); do not load it during an ordinary restart.
The current [checkpoint](platform-test-progress.md) owns ordering and the [plan](platform-test-plan.md) owns escalation rules.
Earlier open observations retain their original evidence limits; newly reproduced architecture defects are recorded separately below, and historical tier labels describe earlier scheduling only.

## ISSUE-013 — Napari probe output bound reports timeout

Status: open, Tier 2/native integration; no supported GUI impact established.
`tests/test_services/test_napari_environments.py::test_probe_runner_enforces_time_and_output_bounds` expected `napari_probe_output_limit` but received `napari_probe_timeout` at its one-second subprocess deadline, including an isolated reproduction after browser load ended.
Next: reproduce that exact backend selector on the current revision, inspect output/deadline ordering, then change only the proven Napari implementation or test threshold; do not call a broader backend lane green meanwhile.

## ISSUE-014 — Workflow title intermittently remains “No workflow”

Status: open, not yet attributed to product code.
An earlier Chromium critical smoke run failed `frontend/tests/e2e/critical-operation-races.spec.ts:453` after seven passes; an isolated run passed on a prior batch, while another attempt never collected due to the former 60-second backend startup limit.
Next: if it recurs, capture workflow-open command, backend request/response, execution-lock state, and tab activation; compare with ISSUE-017 before changing code.

## ISSUE-017 — Workflow-tree double-click can leave the previous workflow active

Status: open, not reproduced in focused follow-up; no speculative product fix.
A full Firefox lane on `7990c67` passed 23 tests then failed `frontend/tests/e2e/critical-operation-races.spec.ts:377`: the target row was selected but the previous workflow title remained active; 80 tests were unrun.
The exact selector passed 1/1 and 5/5 repeated, and a preceding clipboard-to-critical sequence passed 3/3.
The failed screenshot does not prove whether the double-click event, command, or async load was lost.
Next recurrence: capture those event/API breadcrumbs on the exact failed browser run and preserve the real workflow-list double-click contract; do not replace its main-GUI coverage with the separate Open button.

## ISSUE-019 — Focusing a visible inactive result dock refreshes during the click

Status: resolved in integrated N1 `884be6e`; exact scenarios, combined Chromium stress and required two-browser completion pass, with the separate ISSUE-022 Open observation retained.
At source-equivalent readiness base `261ee56` plus N1 test changes, `napari-output-chooser.spec.ts` selector `napari inactive visible dock` failed in Chromium: a real row click changed projection query count from 1 to 2 and dispatched zero opens.
The worker's narrow visibility callback correction preserves the projection during focus and refreshes when the dock becomes visible; corrected wheel/viewport geometry avoids a sticky-header fixture error.
Owner: N1 worker; accepted visibility and identity patch supplies frontend completion and 36-test cross-browser smoke; resolution details will move to the Wave 2 archive at its milestone.
See [Wave 2 evidence](platform-test-evidence.md#wave-2-observed-defects-and-preparation).

## ISSUE-020 — Napari chooser can combine replacement identity with retained actions

Status: resolved in integrated N1 `884be6e`, with the recorded plan-review limitation and the separate pre-chooser ISSUE-022 observation retained.
At N1 base `261ee56`, six real DOM unit reproductions in `NapariOutputChooser.test.ts` show an enabled stale clear action during replacement, a delayed favorite retry targeting the replacement preference key, an old menu overwriting current preference state, an undispatched favorite surviving unmount, an old pending toggle blocking its replacement owner, and a retained candidate callback pairing the new result with the old reader even when the environment UUID matches.
The tests defer actual API promises and change mounted props or dispose the owner; they do not invoke private component methods.
Two dedicated plan passes improved captured selection and operation ownership; a fresh third reviewer could not be created because the tool reached its agent-thread limit, so convergence is not claimed.
Owner: N1 worker; all six distinguishing unit regressions and the seven two-browser client scenarios pass, with frontend and critical-smoke completion; separate actual CAS storage remains distinct from mocked client and native launch evidence.
See [Wave 2 evidence](platform-test-evidence.md#wave-2-observed-defects-and-preparation).

## ISSUE-021 — GUI local worker dispatch bypasses stale-generation preparation

Status: resolved by reviewed E1 feature integrated at `2290c67`; real worker, exact two-browser journeys and scoped app completion passed.
At E1 base `4b58e44` plus task fixtures, Chromium selector `GUI Run replaces one real stale worker generation with visible setup and reuses it` in `stale-processing-environment.spec.ts` failed against a genuinely older owned recipe with the authoritative Core 0.4.1 requirement.
Ordinary `ExecutionManager._run_sync` calls `workflow.compute()`, which submits directly through `_ExecutionEnvironmentManager` without entering `WetlandsBackend.prepare_node`; the shared manager rejects the stale pool with `already provisioned with a different recipe` and no adapter preparation occurs.
Earlier stepwise real worker tests prove the preparation adapter boundary only and do not close this GUI dispatch defect.
Owner: E1 worker; accepted preparation-before-submit, shared automatic startup/Run guard and single lazy manager owner have distinguishing red/green regressions. Explicit manual lifecycle semantics remain unchanged; native restart is separately deferred.
No library implementation change or older incompatible Core seed was required.
See [E1 acceptance](platform-test-evidence.md#e1-integrated-acceptance).

## ISSUE-022 — Explicit selected-workflow Open can leave the previous workflow active

Status: one retained Firefox stress observation; cause unproved, root-owned focused diagnosis.
At N1 source-equivalent readiness `261ee56` plus tested diff `e3b4d9e1d10dd8f29d1ba5baa3a10cbe0a5c100b84a3c2763582596e3cb7c0e5`, combined inactive/artifact-replacement Firefox stress produced 5 passed / 1 failed / 4 unrun in 39 s.
The failed artifact-replacement test stopped before any chooser interaction: its real workflow row click and selected-details heading identify the requested workflow, then its explicit **Open workflow** click leaves the prior workflow title/root active.
The original zero-retry run has an error context and screenshot but no first-attempt trace; it does not establish lost admission, loading, presentation, registry activation, or overwrite as the cause.
The exact selector passed once (15 s); separate diagnostic variants passed five times each (46 s and 42 s), and 36-test critical smoke passed; none closes the original observation or relabels the failed command green.
Corrected probes capture actual workflow-command/Open-start/apply-graph, exact workflow-drafts and nested saved metadata, execution state/lock, active-canvas lifecycle guard and operations; the initial diagnostic used incorrect guessed presentation/draft names and has explicit limits.
Owner: orchestrator; next actual recurrence must identify the first missing command/API/presentation/activation boundary before repair, with an exact controlled ordering regression and bounded reviewed plan if needed.
This differs from ISSUE-017's double-click entry and ISSUE-014's empty title; no common cause or closure of either is asserted, and resolved ISSUE-018 remains its separately confirmed startup race.
Retained artifacts are under `/private/tmp/bioimageflow-n1-artifacts/n1-races-stress-firefox/` and the two diagnostic directories; see [N1 acceptance](platform-test-evidence.md#n1-integrated-acceptance).

## ISSUE-023 — Dataset listing publishes an upload before completion

Status: causally reproduced; root-owned staged-publication plan awaiting independent review.
At task base `2b945ccc8198258710d516658ea48a24e5150d81` with tests-only changes in `.worktrees/campaign-dataset-publication-current`, exact `scripts/test focus backend tests/test_services/test_dataset_store.py::test_streaming_upload_is_not_published_by_a_concurrent_store` failed in 39 s reported / 39.44 s elapsed (pytest 0.21 s).
A second real DatasetStore constructor/list reconciles the first upload's final-looking file after only its first chunk; completion then fails with SQLite `UNIQUE constraint failed: datasets.stored_name` and the cleanup path deletes the upload file.
Exact `scripts/test focus backend tests/test_routers/test_datasets.py::test_spooled_upload_is_hidden_from_concurrent_dataset_listing` failed in 3 s / 2.94 s elapsed (pytest 0.49 s).
That real multipart HTTP test uses a disk-spooled UploadFile and a controlled read barrier; a concurrent real GET returns the unfinished dataset before upload completion.
It proves supported HTTP reachability, not that every tiny in-memory upload yields at the same boundary.
No production repair or passing completion result is credited yet.
Next: independently review unpublished staging, catalog/physical publication and cross-instance serialization, no-overwrite, cancellation/folder/refusal and crash ordering, then rerun the exact failures and required scoped checks.
Original logs are preserved at `/private/tmp/bioimageflow-dataset-publication-red.log` and `/private/tmp/bioimageflow-dataset-publication-http-red.log`; [architecture finding C3](platform-test-architecture-audit.md#reviewed-findings-and-next-packets) owns its cross-boundary context.

## ISSUE-024 — Explicit force-Recreate reuses the selected ready generation

Status: actual provisioning failure retained from T1; public library-wrapper plan in progress.
At T1 base `2290c67` plus preserved task WIP, exact `test_manual_flexible_recipe_create_replace_failure_retry_and_worker_isolation` in `backend/tests/test_integration/test_tool_environment_lifecycle.py` failed in 86 s (pytest 83.97 s) at matching Recreate generation inequality.
Creation and matching Start reuse reached the actual public manager; later failure/retry/compute assertions remain unrun, and no GUI/app completion is accepted.
Installed Wetlands 2.4.2 returns a matching ready generation before considering `replace_existing`; public remove/provision can force reconstruction but must be owned by the same BioImageFlow wrapper and is not selected-generation rollback or compound cross-process CAS.
Next: review that public wrapper's preflight/strict closure/cache ownership/progress/failure semantics and reconcile existing replacement documentation while preserving ordinary reuse and E1 stale replacement.
No directory deletion, private-state surgery, fingerprint nonce or stale-only feature narrowing is accepted.
T1 report/checkpoint and real red files are preserved in `/private/tmp/bioimageflow-t1-worker-report.md`, `/private/tmp/bioimageflow-t1-checkpoint-20261001` and `/private/tmp/bioimageflow-t1-red-artifacts`; see [architecture finding B1](platform-test-architecture-audit.md#reviewed-findings-and-next-packets).

## Resolved issue lookup

ISSUE-001–ISSUE-012 and ISSUE-015–ISSUE-016 are closed in the [issue archive](archive/platform-test-issues-through-tier-1b.md); ISSUE-006 has a reviewed `not-a-defect` disposition.
ISSUE-018 is resolved in the [Wave 1 issue archive](archive/platform-test-issues-wave-1-2026-09-30.md), with the startup/Open causal diagnosis and passing repair evidence.
Use the stable ID to search the relevant archive only when a specific historical decision matters to the current task.

## New issue record

Record stable ID, status, supported user path and impact, exact selector/browser/revision, observed versus expected state, owner, next focused action, and links to evidence.
Move resolved details to a dated archive at a milestone; leave only open decisions and a short lookup here.
