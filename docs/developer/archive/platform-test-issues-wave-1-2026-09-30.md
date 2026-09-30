---
orphan: true
---

# Wave 1 resolved campaign issues — 2026-09-30

## ISSUE-018 — Pending startup and explicit Open compete for root presentation

Status: resolved by the reviewed main readiness repair; owner: executing orchestrator.
Supported path: reload a saved workflow, double-click its ordinary Workflows row while startup is loading, then open a child and inspect its internal result.
On platform `29733fa` plus the distinguishable J3 fixture, the exact Chromium journey failed twice: the correct second-child rows arrived, then the root became visible and Node Data changed to its public-only output.
A controlled real-response diagnostic captured accepted Open at 445.2 ms, startup root mount at 924.0 ms, child activation at 1458.8 ms, and delayed explicit Open applying/activating the existing root at 1547.3–1548.8 ms; the test failed with only `number_plus_one` visible.
The unmodified-latency instrumented attempt passed and remains diagnostic evidence, not a repair pass.
Independent plan review converged after three passes; the bounded correction invalidates App's startup fence when MenuBar accepts named Open, gates late startup store presentation writes, reads speculative drafts without changing the active draft projection, and preserves newer same-workflow recovery in the winning Open.
The exact test and five repetitions passed after correction in each browser; affected J1/J2/J4 rechecks passed 6/6 and the critical smoke passed 18/18 per browser.
Frontend completion is a documented composite: original lint/1330-unit/build passes plus corrected exact unit/type-check/lint subphases.
Read-only implementation review found no material blocking issue; documentation validation passed (2.91 s); the task-only main commit supplies the integrated baseline.
A deferred real-store test also exposed a late saved-load metadata reset before that additional guard, with the original red result retained in [evidence](../platform-test-evidence.md).
This causal finding does not close ISSUE-014 or ISSUE-017, whose earlier observations lack these event breadcrumbs.
Tested source: platform parent `29733fa` plus production/E2E diff SHA-256 `6c6481a636be650e0ed87c8c43816674252615fddb4c6c92ad04e8a9b82b1bae`, clean editable library `dff04e3`; [evidence](../platform-test-evidence.md) preserves exact commands, red diagnostics and limitations.
No native, worker, published-package, excluded execution-family or historical-issue closure follows from this repair.

