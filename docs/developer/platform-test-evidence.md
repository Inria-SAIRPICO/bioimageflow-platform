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
