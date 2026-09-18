---
orphan: true
---

# Platform test campaign checkpoint

Updated 2026-09-18. Basic-Use Gate passed at `50c1af4`; the owner continued the campaign.
Tier 1B primary-GUI coverage is **219/219 applicable cells verified**; overall systematic coverage is **241/456 (52.9%)**, with 209 gaps and six unassessed cells.
These are [dashboard](platform-test-dashboard.md) obligation counts, not a passing full-suite certificate.
Tier 1B broad browser acceptance was attempted but remained red or interrupted; focused tests and scoped completion checks retain their exact evidence.
ISSUE-013, ISSUE-014, and ISSUE-017 remain [open](platform-test-issues.md), with no confirmed high-impact basic-use defect from the latter two.
No campaign worker or task worktree is active at this checkpoint; reconcile Git before assigning one.

## Next three actions

1. Run the focused headed primary-GUI confidence journey at the next GUI-wave boundary if a display is available; do not restart a full browser project merely to seek a green Tier 1B label.
2. Start Tier 2 with the highest-reach runnable P1 inventory gap, choosing one real user journey and the smallest applicable `scripts/test` check; keep Chromium and Firefox exact selectors for changed GUI behavior.
3. Investigate open issues only on a relevant recurrence or when their Tier 2 feature is scheduled; capture event/API breadcrumbs for ISSUE-014 or ISSUE-017 before changing the workflow-open path.

## Working set for a fresh orchestrator

Read this checkpoint, the relevant section of the [plan](platform-test-plan.md), the target row in [GUI](coverage-gui.md), [workflow](coverage-workflows.md), or [runtime](coverage-runtime.md), and only the matching open issue.
Use the [dashboard](platform-test-dashboard.md) for counts and evidence revisions; workers need their own bounded packet, not the campaign history.
The catalog contract is single-click for bottom tool information, double-click for one canvas node, and drag for a separate creation gesture.
Use `scripts/test focus` on an exact failing selector, fix it, run that selector once, then advance to the next unrun check; use five repeats only for a suspected race.
Run a broad browser or full lane only at the next scheduled milestone, for a change that truly requires it, or at final certification; retain successful unchanged phases after a late failure.
Commit each validated task promptly and archive completed worktree state as required by `AGENTS.md`.

Completed Tier 1A–1B ownership notes and checkpoint history are in the [progress archive](archive/platform-test-progress-through-tier-1b.md); commands, durations, limitations, and release records are in the [evidence archive](archive/platform-test-evidence-through-tier-1b.md).
Do not read these archives during an ordinary restart; open one only to audit a specific historical claim.
