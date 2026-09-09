---
orphan: true
---

# Platform test campaign checkpoint

Last updated: 2026-09-09.
Status: ready for a fresh Sol/medium session; first action is Astra/high assessment of ISSUE-001.
The owner replaced immediate escalation to the owner with the [Sol → Astra → owner protocol](platform-test-plan.md).
This checkpoint records a documentation handoff, not resumed feature implementation or completed certification.

## Resume here

1. Follow [Restart instructions](platform-test-start.md), reconcile Git, and verify package versions.
2. Assign ISSUE-001 from [Campaign issues](platform-test-issues.md) to Astra/high with fresh context for a bounded isolated reproduction and contract assessment.
3. If safe to fix, implement its prescribed bounded repair and regressions; if not a defect, record the evidence; if intent remains unresolved, pause the entire campaign for the owner.
4. Continue tasks T03–T06 below using the partial inventories, without repeating their completed inspection work blindly.

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
| T04 | In progress | Hot-reload fixture enforcement, sequential cache/output repairs, and valid browser fallback recovery are committed. ISSUE-003 repaired ToolsPanel click creation and exact click/drag journeys pass cross-browser; completion is blocked only by ISSUE-004 ordinary-mutation contention. | Commit ISSUE-003 independently, then resolve ISSUE-004 and rerun its invalidated gates. |
| T05 | Pending | Explicit per-case local scope selection and dedicated complete GUI journeys, including nested edits, source updates, results, actual failure/cancellation, and persistence. | Audit selection before broad execution; no working local-profile command exists yet. |
| T06 | Pending | Comprehensive in-scope backend/frontend/browser certification, real sequential worker, common-tools compatibility, manual boundary reconciliation. | Master schedules once large changes are ready; do not run full on every increment. |
| ISSUE-001 | Resolved | Astra/high reproduced the same-artifact replacement defect and established the contract; Sol/medium added atomic destination-generation capture/checks and no-mutation regressions. | Backend completion passed; fix commit is path-discoverable. |
| ISSUE-002 | Resolved documentation discrepancy | Commit `a8d9533` and v2 §1.8 establish contextual execution logs and global background logs; the stale v1 WebSocket row is reconciled. | `scripts/test check docs` passed in 2s; resolution commit is path-discoverable. |

Active write owners: `/root/issue_004_fix`, GPT-5.6 Sol/medium, owns `execution.py`, the root workflow Save router, and their focused backend tests; `/root/t05_backend_scope`, GPT-5.6 Sol/medium, owns the disjoint backend campaign marker/manifest/conftest files and audited excluded test files. Both started from `dfd5917`; ISSUE-004 depends on Astra's safe-to-fix disposition, while T05 is independent.

## Current-session completion evidence

- Hot-reload fixture enforcement: the exact watcher test passed once in Chromium in 11s and Firefox in 13s at `353b425` plus its one-file diff. `scripts/test check frontend` passed lint, type checking, build, and 1,243 executed unit tests, but one unrelated `LoggerPanel.test.ts` suite hit a Vitest worker-loader timeout; its exact 14-test file passed in 2s without an edit. `scripts/test check browser` passed the changed hot-reload test and 53 other Chromium tests before an unrelated execution-lock failure; that exact workflow-interface test passed in 14s in a fresh runtime, and the one test not run after fail-fast passed separately in 11s. `scripts/test check docs` passed in 3s. Initial sandbox attempts that could not fetch documentation dependencies or bind local browser servers were blocked before collection. The task commit is discoverable with `git log -1 -- frontend/tests/e2e/hot-reload.spec.ts`.
- ISSUE-001: the new exact source-refresh selectors and the whole six-test file passed. `scripts/test check backend` passed in 82s at `6d42c05` plus the settled backend diff: 1,577 deterministic tests passed, 9 deselected, and 7 logging-order tests passed; external certification was intentionally omitted by the lane. The repair commit is discoverable by its service path.
- Sequential cache/output fixtures: the shared-downstream exact selector passed in 2s and its full 13-test file passed in 3s; the cache-parity and output-template files passed 10 tests in 5s. The settled `scripts/test check backend` result above covers all three files. The task commit is discoverable with `git log -1 -- backend/tests/test_services/test_cache_clearer.py`.
- Valid fallback recovery graph: the exact journey passed in Chromium in 14s and Firefox in 17s at `87fe704` plus its one-file diff. The settled frontend completion passed lint, type checking, 1,257 tests, and build in 30s before later unrelated T04 test edits. A subsequent settled-tree frontend completion passed lint, 1,260 tests, and build but exposed only ISSUE-003 test-mock type errors; the corrected exact type-check passed. The Chromium completion run passed the changed recovery journey before later failing from ISSUE-004 lock contamination; exact failed and fail-fast-deselected workflow-interface cases passed separately. `scripts/test check docs` passed in 2s. The task commit is discoverable with `git log -1 -- frontend/tests/e2e/graph-persistence.spec.ts`.
- ISSUE-003 ToolsPanel click: the focused unit files passed 96 tests in 6s; exact Chromium click/drag passed in 15s/16s and Firefox in 14s/17s, with no skips. The frontend completion passed lint, 1,260 tests, and build; its test-only type errors were corrected and the exact type-check passed. The Chromium completion passed both changed cases among 55 successes before ISSUE-004 stopped the lane. `scripts/test check docs` passed in 3s. The task commit is discoverable with `git log -1 -- frontend/src/components/panels/ToolsPanel.vue`.

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
