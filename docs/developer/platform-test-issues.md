---
orphan: true
---

# Active platform test campaign issues

Read only the issue relevant to the assigned task.
Completed decisions and detailed history for ISSUE-001–ISSUE-017 are retained in the [issue archive](archive/platform-test-issues-through-tier-1b.md); do not load it during an ordinary restart.
The current [checkpoint](platform-test-progress.md) owns ordering and the [plan](platform-test-plan.md) owns escalation rules.

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

## Resolved issue lookup

ISSUE-001–ISSUE-012 and ISSUE-015–ISSUE-016 are closed in the [issue archive](archive/platform-test-issues-through-tier-1b.md); ISSUE-006 has a reviewed `not-a-defect` disposition.
Use the stable ID to search that archive only when a specific historical decision matters to the current task.

## New issue record

Record stable ID, status, supported user path and impact, exact selector/browser/revision, observed versus expected state, owner, next focused action, and links to evidence.
Move resolved details to a dated archive at a milestone; leave only open decisions and a short lookup here.
