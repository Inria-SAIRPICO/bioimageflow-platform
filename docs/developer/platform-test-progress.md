---
orphan: true
---

# Platform test campaign checkpoint

Last updated: 2026-09-14.
Status: campaign active; the tool-catalog interaction contract is implemented and ISSUE-005 remains the next product-repair decision.
The owner requires every resolved issue or bounded task to be committed immediately, with dedicated worktrees for parallel writable agents; the [plan](platform-test-plan.md) and [restart prompt](platform-test-start.md) now make this explicit.

## Resume here

1. Follow [Restart instructions](platform-test-start.md), reconcile Git, and verify that ISSUE-004 and the T05 backend scope batch are committed independently.
2. Finish T05's audited frontend-unit and browser per-case local-scope selection in a dedicated worktree, then commit it before starting another writable task.
3. Continue tasks T03–T06 using the partial inventories, without repeating completed inspection or validation work blindly.

No worker or test process remains active from the audit.
The preceding audit changed only the three coverage Markdown inventories; those were authored by campaign agents, not unrelated user edits, and are included in this requested durable handoff.
No product or test repair for the new audit findings has begun.
The handoff documentation is committed separately; find its revision with `git log -1 -- docs/developer/platform-test-progress.md` and use actual `git status`, not this historical cleanliness note.

## Milestones and queue

| ID | State | Scope and evidence | Next action / owner |
| --- | --- | --- | --- |
| T01 | Complete | Wetlands 2.4.1; published BioImageFlow 0.7.1/core 0.3.1; platform constraints and specifications updated. | No release work unless a new issue requires it. |
| T02 | Complete | Generate drag readiness fixed; genuine metadata, whole-DataFrame edge, accepted validation, exact rows, and separate real sequential worker regression. | Preserve these fixtures and assertions. |
| T03 | Partial audit | [Workflow inventory](coverage-workflows.md), [GUI inventory](coverage-gui.md), [Runtime inventory](coverage-runtime.md); inspected bodies, not new passing results. | Sol workers finish missing feature/boundary rows; master owns integration. |
| T04 | Complete | Hot-reload fixture enforcement, sequential cache/output repairs, valid browser fallback recovery, ToolsPanel inspection/add gestures, and ISSUE-004 mutation serialization are repaired and independently validated. | Preserve the repaired fixtures and contracts while extending acceptance coverage. |
| T05 | In progress | Exact backend, frontend-unit, Chromium, and Firefox campaign-local selection is committed and drift-audited; dedicated complete GUI journeys remain. | Add the next missing in-scope GUI journey as one isolated, commit-ready task. |
| T06 | Pending | Comprehensive in-scope backend/frontend/browser certification, real sequential worker, common-tools compatibility, manual boundary reconciliation. | Master schedules once large changes are ready; do not run full on every increment. |
| ISSUE-001 | Resolved | Astra/high reproduced the same-artifact replacement defect and established the contract; Sol/medium added atomic destination-generation capture/checks and no-mutation regressions. | Backend completion passed; fix commit is path-discoverable. |
| ISSUE-002 | Resolved documentation discrepancy | Commit `a8d9533` and v2 §1.8 establish contextual execution logs and global background logs; the stale v1 WebSocket row is reconciled. | `scripts/test check docs` passed in 2s; resolution commit is path-discoverable. |
| ISSUE-004 | Resolved | Ordinary mutations serialize through execution admission; only actual starting/running execution produces the 423 lock. | `scripts/test check app` passed in 140s and all 57 Chromium tests passed in 106s; fix commit is path-discoverable. |
| ISSUE-005 | Astra review | Run Selected rejects a valid selected branch because a disconnected node has a missing tool; exact request identity/graph/revision are proven. | Freeze the T05 journey; Astra/high determines contract and safe repair boundary. |

Active write owner: `/root/t05_run_selected`, Sol/medium, has frozen its test-only Run Selected journey in `.worktrees/t05_run_selected` on `campaign/t05-run-selected`; Astra/high owns the read-only ISSUE-005 contract assessment before any production repair.

## Current-session completion evidence

- Hot-reload fixture enforcement: the exact watcher test passed once in Chromium in 11s and Firefox in 13s at `353b425` plus its one-file diff. `scripts/test check frontend` passed lint, type checking, build, and 1,243 executed unit tests, but one unrelated `LoggerPanel.test.ts` suite hit a Vitest worker-loader timeout; its exact 14-test file passed in 2s without an edit. `scripts/test check browser` passed the changed hot-reload test and 53 other Chromium tests before an unrelated execution-lock failure; that exact workflow-interface test passed in 14s in a fresh runtime, and the one test not run after fail-fast passed separately in 11s. `scripts/test check docs` passed in 3s. Initial sandbox attempts that could not fetch documentation dependencies or bind local browser servers were blocked before collection. The task commit is discoverable with `git log -1 -- frontend/tests/e2e/hot-reload.spec.ts`.
- ISSUE-001: the new exact source-refresh selectors and the whole six-test file passed. `scripts/test check backend` passed in 82s at `6d42c05` plus the settled backend diff: 1,577 deterministic tests passed, 9 deselected, and 7 logging-order tests passed; external certification was intentionally omitted by the lane. The repair commit is discoverable by its service path.
- Sequential cache/output fixtures: the shared-downstream exact selector passed in 2s and its full 13-test file passed in 3s; the cache-parity and output-template files passed 10 tests in 5s. The settled `scripts/test check backend` result above covers all three files. The task commit is discoverable with `git log -1 -- backend/tests/test_services/test_cache_clearer.py`.
- Valid fallback recovery graph: the exact journey passed in Chromium in 14s and Firefox in 17s at `87fe704` plus its one-file diff. The settled frontend completion passed lint, type checking, 1,257 tests, and build in 30s before later unrelated T04 test edits. A subsequent settled-tree frontend completion passed lint, 1,260 tests, and build but exposed only ISSUE-003 test-mock type errors; the corrected exact type-check passed. The Chromium completion run passed the changed recovery journey before later failing from ISSUE-004 lock contamination; exact failed and fail-fast-deselected workflow-interface cases passed separately. `scripts/test check docs` passed in 2s. The task commit is discoverable with `git log -1 -- frontend/tests/e2e/graph-persistence.spec.ts`.
- ISSUE-003 ToolsPanel routing and the revised catalog interaction contract, based on `df883c0` plus this bounded task diff: single-click now toggles the bottom documentation panel, double-click creates exactly one node, and catalog secondary actions are isolated from both row gestures. The focused ToolsPanel unit file passed 64 tests in 14s; the exact browser journey passed once in Chromium in 64s and Firefox in 26s; `scripts/test check frontend` passed lint, type checking, build, and all 1,273 unit tests in 37s; `scripts/test check cross-browser-smoke` passed 10 Chromium and 10 Firefox cases in 67s; and the final `scripts/test check docs` passed in 4s. No cases were skipped, deselected, or retried. The first post-edit documentation recheck was blocked before collection because sandbox DNS could not fetch `myst-parser`; the permitted rerun above succeeded. The task commit is discoverable with `git log -1 -- frontend/src/components/panels/ToolsPanel.vue`.
- ISSUE-004 ordinary mutation contention: three exact deterministic regressions passed in 3s. `scripts/test check app` passed in 140s: backend lint, 1,590 deterministic tests with 9 deselected, 7 logging-order tests, frontend lint/type-check/build, 1,260 unit tests, and 10 critical Chromium journeys. `scripts/test check browser` then passed all 57 Chromium tests in 106s, including the formerly failing workflow-interface case at position 56. The task commit is discoverable with `git log -1 -- backend/src/bioimageflow_server/services/execution.py`.
- T05 backend campaign scope: `scripts/test focus backend --campaign-local` collected 1,599 tests, selected 1,489, and passed 1,480 with 9 external tests skipped and exactly 110 audited exclusions in 78s. The batch was also present for ISSUE-004's successful `scripts/test check app` and full Chromium completion, so the ordinary unscoped collection and cross-stack lanes remain valid. The task commit is discoverable with `git log -1 -- backend/tests/campaign_scope.py`.
- T05 frontend/browser campaign scope: the isolated worktree commit was reviewed, corrected to reject duplicate identities and unsupported partial selectors, and integrated as `f2eb9d8`. On main, `scripts/test check all` passed in 228s with backend lint, 1,590 deterministic tests and 9 deselected, 7 logging-order tests, frontend lint/type-check/build, all 1,271 unit tests, and all 58 Chromium journeys; external certification and Firefox execution were intentionally omitted by that lane. `scripts/test focus unit --campaign-local` passed 1,227 selected tests with exactly 44 audited skips in 29s. `scripts/test focus e2e --campaign-local --list --project=chromium --project=firefox` passed in 2s and independently reported 56 selected and 2 excluded cases for each browser.

## Completed revisions

Platform baseline for the latest code and audit is `fcb4408dd994a31567042b691eff85f3b268c5ab`.
Relevant platform commits: `f8c39de` Wetlands floor; `ea6abed` fail stale diagnostic/snapshot regressions explicitly; `b8a805c` drag readiness and pre-cleanup evidence; `306737f` published library adoption/contracts; `83ab981` fixture/worker certification; `fcb4408` GUI whole-DataFrame journey.
`c675e4a` and `11907b3` establish the original campaign and separate library release CI from platform scope.

Sibling library baseline is `bb74097` in `../bioimageflow`, with tags `bioimageflow-core-v0.3.1` and `bioimageflow-v0.7.1`.
Library fixes include constant-only DataFrame parameters, annotation resolution, installed-version fixtures, synchronized failure-selection regression, and flushed log fixture output.
Direct remains supported.
[Required library CI](https://github.com/Inria-SAIRPICO/bioimageflow/actions/runs/34349497763) passed 12 jobs; [publication](https://github.com/Inria-SAIRPICO/bioimageflow/actions/runs/34349799812) succeeded.
The platform environment was verified to import regular installed wheels for `bioimageflow==0.7.1`, `bioimageflow-core==0.3.1`, and `wetlands==2.4.1`, without editable overrides.
The old library task worktree was removed; do not reference it or share environments across worktrees.

## Retained validation evidence

These are historical results from `11907b3` plus the changes subsequently committed through `fcb4408`, not tests rerun during the inventory or handoff.
For all five rows below, the recorded code identity is the uncommitted tree based on `11907b3` whose completed changes are now in `306737f`, `83ab981`, and `fcb4408`; no per-run tree hash was preserved.
Compare the relevant paths against `fcb4408` before retaining these results; if their applicability cannot be established, rerun the exact relevant check instead of assuming certification.
Commands ran with `UV_NO_SYNC` and `BIOIMAGEFLOW_USE_LOCAL_CORE` unset and the temporary platform uv cache.
Durations are runner wall time.

| Command | Result | Duration |
| --- | --- | --- |
| `scripts/test focus backend tests/test_integration/test_platform_fixture_contracts.py::test_processing_fixture_runs_in_real_sequential_wetlands_worker --run-external` | 1 passed, no cleanup warning | 39s |
| `scripts/test focus backend tests/test_integration/test_platform_fixture_contracts.py tests/test_integration/test_real_execution.py` | 7 passed, external worker skipped here and passed separately | 5s |
| `scripts/test focus e2e tests/e2e/canvas-interactions.spec.ts --project=chromium --project=firefox --grep 'new dynamic tools connect cleanly'` | 2 passed | 24s |
| `scripts/test focus e2e --project=chromium --project=firefox --grep @critical --grep-invert 'managed execution resolves paths, retains its run, downloads results, and cleans up'` | 18 passed, managed journey excluded | 52s |
| `scripts/test certification` | 8 passed, 1,576 deselected; common-tools 0.2.0 | 13s |

Earlier scoped backend completion passed 1,454 deterministic tests, 19 deselected, and 7 logging-order tests in 73s; five additional local-runtime cases passed in 3s.
Earlier frontend completion selected 119 files and passed 1,213 tests with six excluded cases in 19s; lint, type checking, build, and documentation also passed.
Those selections used temporary command files/broad exclusions and are not a reproducible complete local-profile certificate.
Do not reuse their counts as proof of complete coverage; T05 must establish audited per-case selection.
Temporary `/private/tmp/bif-published-*.log` and `/private/tmp/bif-platform-*.log` may exist locally but are not required to resume.
Older unused runner/evidence drafts under ignored `backend/.pytest_cache/unfinished-test-plan/` are unfinished and must not be restored as functioning infrastructure.

For every new completion, append or replace the relevant task evidence with the exact command (including selectors/environment), source revision or diff identity, result, wall duration, skips/deselections/retries, external blockers, and resulting commit.
Preserve successful unchanged phases after a late failure; rerun only invalidated checks.
Before session handoff, update active ownership, dirty paths, issue dispositions, and the next action; archive resolved detail as concise commit references.

## Handoff validation

`scripts/test check docs` passed in 2s at `fcb4408` plus this documentation-only handoff diff, after a Sol/medium review of the restart protocol.
An initial sandbox attempt was blocked fetching a Sphinx dependency; the network-enabled run then exposed two out-of-tree specification links, which were corrected before the passing check.
No application, browser, or library tests were run for this documentation-only change; no such phase is claimed as newly certified.
The final handoff commit is discoverable with the path-specific Git command above.
