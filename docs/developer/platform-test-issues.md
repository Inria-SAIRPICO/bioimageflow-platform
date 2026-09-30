---
orphan: true
---

# Active platform test campaign issues

Read only the issue relevant to the assigned task.
Completed decisions and detailed history for ISSUE-001–ISSUE-017 are retained in the [issue archive](archive/platform-test-issues-through-tier-1b.md); do not load it during an ordinary restart.
The current [checkpoint](platform-test-progress.md) owns ordering and the [plan](platform-test-plan.md) owns escalation rules.
These open issues carry forward into the new campaign without a new diagnosis or closure; historical tier labels describe their earlier scheduling only.

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

Status: reproduced; isolated N1 repair passes the exact scenario once in Chromium and Firefox, but combined completion and integration remain pending.
At source-equivalent readiness base `261ee56` plus N1 test changes, `napari-output-chooser.spec.ts` selector `napari inactive visible dock` failed in Chromium: a real row click changed projection query count from 1 to 2 and dispatched zero opens.
The worker's narrow visibility callback correction preserves the projection during focus and refreshes when the dock becomes visible; corrected wheel/viewport geometry avoids a sticky-header fixture error.
Owner: N1 worker; next: validate the coherent visibility and identity patch, then required frontend/cross-browser completion before integration.
See [Wave 2 evidence](platform-test-evidence.md#wave-2-observed-defects-and-preparation).

## ISSUE-020 — Napari chooser can combine replacement identity with retained actions

Status: reproduced; bounded component repair in progress, not yet accepted.
At N1 base `261ee56`, six real DOM unit reproductions in `NapariOutputChooser.test.ts` show an enabled stale clear action during replacement, a delayed favorite retry targeting the replacement preference key, an old menu overwriting current preference state, an undispatched favorite surviving unmount, an old pending toggle blocking its replacement owner, and a retained candidate callback pairing the new result with the old reader even when the environment UUID matches.
The tests defer actual API promises and change mounted props or dispose the owner; they do not invoke private component methods.
Two dedicated plan passes improved captured selection and operation ownership; a fresh third reviewer could not be created because the tool reached its agent-thread limit, so convergence is not claimed.
Owner: N1 worker; next: exact distinguishing unit passes, coherent two-browser validation and required completion; no backend or native launch claim follows from mocked client evidence.
See [Wave 2 evidence](platform-test-evidence.md#wave-2-observed-defects-and-preparation).

## ISSUE-021 — GUI local worker dispatch bypasses stale-generation preparation

Status: reproduced in the real GUI/worker path; bounded repair planning in progress.
At E1 base `4b58e44` plus task fixtures, Chromium selector `GUI Run replaces one real stale worker generation with visible setup and reuses it` in `stale-processing-environment.spec.ts` failed against a genuinely older owned recipe with the authoritative Core 0.4.1 requirement.
Ordinary `ExecutionManager._run_sync` calls `workflow.compute()`, which submits directly through `_ExecutionEnvironmentManager` without entering `WetlandsBackend.prepare_node`; the shared manager rejects the stale pool with `already provisioned with a different recipe` and no adapter preparation occurs.
Earlier stepwise real worker tests prove the preparation adapter boundary only and do not close this GUI dispatch defect.
Owner: E1 worker; next: independent review of the smallest public adapter submit/map repair, direct-submit regression, actual compute-path external acceptance and exact repaired GUI selectors in both browsers.
No library implementation change or older incompatible Core seed is currently required.
See [Wave 2 evidence](platform-test-evidence.md#wave-2-observed-defects-and-preparation).

## Resolved issue lookup

ISSUE-001–ISSUE-012 and ISSUE-015–ISSUE-016 are closed in the [issue archive](archive/platform-test-issues-through-tier-1b.md); ISSUE-006 has a reviewed `not-a-defect` disposition.
ISSUE-018 is resolved in the [Wave 1 issue archive](archive/platform-test-issues-wave-1-2026-09-30.md), with the startup/Open causal diagnosis and passing repair evidence.
Use the stable ID to search the relevant archive only when a specific historical decision matters to the current task.

## New issue record

Record stable ID, status, supported user path and impact, exact selector/browser/revision, observed versus expected state, owner, next focused action, and links to evidence.
Move resolved details to a dated archive at a milestone; leave only open decisions and a short lookup here.
