---
orphan: true
---

# Platform test campaign evidence

The completed Tier 1A–1B runs, revisions, durations, limitations, and release history are retained in the [dated evidence archive](archive/platform-test-evidence-through-tier-1b.md).
Do not read that archive during an ordinary restart; use the [current checkpoint](platform-test-progress.md), [dashboard](platform-test-dashboard.md), and only the feature's relevant inventory row.
Open the archive only to audit a specific historical claim or invalidated check.

Append concise evidence for the current task here: exact command and selector, source revision, outcome and duration, skips or unrun cases, and any limitation.
At the next major milestone, move completed entries to a dated archive and leave this file short.

## Current-code inventory reconciliation — 2026-09-24

A read-only change scan through `15c5cc7` found ten newly tracked in-scope obligations: overall execution progress/setup, confirmed workflow-format migration, Image Viewers settings, Napari result chooser/favorites, Manage Tools environment controls, imported-graph layout, corrupt-cache recovery, stale processing-environment rebuild, Logger copying, and previously omitted import-viewing guidance.
The prior 241/456 overall and 219/219 primary-GUI counts described historical evidence; the expanded dashboard is 241/500 overall and 219/224 primary GUI, with no current-revision application or browser certificate implied.
`scripts/test check campaign` passed on the campaign-documentation diff; no product regression or new feature assertion was run for this inventory reconciliation.

## RT-EXE-016 real-worker progress increment — integrated `3fb04d1`

Task commits `6a3c5df` and `3fb04d1` add opt-in task progress to the held-worker fixture, exact metadata/default/direct-call regressions, and live/retained banner assertions in the existing cancellation GUI journey.
At patch-equivalent task revision, exact Chromium cancellation passed in 39s and Firefox in 38s; the unchanged default-consumer failure/rerun Chromium selector passed in 33s; `scripts/test focus backend tests/test_integration/test_held_worker_fixture.py` passed 3/3 in 2s with localhost access, and targeted Ruff passed.
`scripts/test check frontend` passed in 26s with 1,313 units plus lint/type/build; `scripts/test check cross-browser-smoke` passed 18/18 Chromium and 18/18 Firefox in 112s; `scripts/test check campaign` passed in under 1s at 244/500 overall and 222/224 primary GUI.
An earlier `scripts/test check backend` attempt on intermediate task content ended red in 135s: 1,792 passed, one obsolete fixture metadata assertion failed, two tests could not bind localhost in the restricted sandbox, and nine external tests were deselected. The corrected exact fixture selection passed with local sockets permitted; the full backend lane was not repeated, so it is not claimed as passed.
Sol/high planning and independent Astra/high review approved the opt-in fixture contract; no production refactor was needed. RT-EXE-016.F/P/B are verified; setup-phase and selected/cached plan success plus visible stale-event refusal remain S/R gaps. No full suite or external certification ran.
