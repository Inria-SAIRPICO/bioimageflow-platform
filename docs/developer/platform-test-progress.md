---
orphan: true
---

# Platform test campaign checkpoint

Updated 2026-09-24 after a read-only change scan through `15c5cc7` and ten newly recorded inventory rows; the owner continued the campaign.
The Basic-Use Gate passed on historical revision `50c1af4`, and the September 18 Tier 1B dashboard recorded 219/219 primary-GUI cells; later code changes require focused current-revision revalidation.
The reconciled [dashboard](platform-test-dashboard.md) now records **224/224 primary-GUI cells** and **254/500 overall (50.8%)**, with 240 gaps and six unassessed cells.
These are obligation counts with historical evidence revisions, not a passing current-revision full-suite certificate.
The code scan added distinct obligations for progress, workflow-format migration, Image Viewers, Napari chooser/favorites, Manage Tools environments, imported-graph layout, corrupt-cache recovery, stale environment rebuild, Logger copying, and previously omitted import-viewing guidance; scenario-level checks remain to be executed.
Tier 1B broad browser acceptance was attempted but remained red or interrupted; focused tests and scoped completion checks retain their exact evidence.
ISSUE-013, ISSUE-014, and ISSUE-017 remain [open](platform-test-issues.md), with no confirmed high-impact basic-use defect from the latter two.
The source inventory was audited through `15c5cc7`; integrated `3fb04d1` and `0be3417` close RT-EXE-016 with real-worker progress, selected/cached branch, stale-context refusal, and controlled setup presentation evidence.
Integrated `2ce96a0` closes WF-LIF-015 with visible saved-workflow migration and backend recursive saved/draft/private-snapshot authority, backup, identity, and interrupted-recovery assertions; the GUI claim does not extend to an OS crash or packaged restart.
Integrated `38ac552` closes GUI-EDT-014 with exact recursive imported-graph positions, visible canvas separation, edited layout persistence, and sibling isolation in Chromium and Firefox.
Its broad Chromium completion attempt stopped on an unrelated one-off catalog-add assertion; that exact selector passed in isolation, so 103 unrun browser cases remain unclaimed.
Exact nested-instance Node Data and browser image-viewer GUI rechecks passed in Chromium and Firefox at `9c4a435`; those focused results do not replace later broad browser certification.
The scoped cross-browser smoke passed on the progress task; the earlier backend completion attempt stayed red from one corrected fixture assertion and two sandbox-denied sockets, then the exact three-test fixture selection passed with local sockets permitted.
Reconcile Git, worker state, and installed versions before assigning new work; preserve the unrelated untracked `presentation/` directory.

## Next three actions

1. Finish RT-XCT-007 Logger filter/select/copy as an ordinary GUI path, then reconcile its dashboard cells.
2. Continue Tier 2 through the newly recorded P1 journeys for cache/environment recovery, Image Viewers, Napari chooser/favorite, import guidance, and Manage Tools environments before lower-frequency P2/native boundaries.
3. Investigate ISSUE-014/017 or the one-off catalog-add completion failure only on a relevant recurrence, with event/API breadcrumbs; reserve broad browser/full lanes for their scheduled milestones or a change that actually requires them.

## Working set for a fresh orchestrator

Read this checkpoint, the relevant section of the [plan](platform-test-plan.md), the target row in [GUI](coverage-gui.md), [workflow](coverage-workflows.md), or [runtime](coverage-runtime.md), and only the matching open issue.
Use the [dashboard](platform-test-dashboard.md) for counts and evidence revisions; workers need their own bounded packet, not the campaign history.
The catalog contract is single-click for bottom tool information, double-click for one canvas node, and drag for a separate creation gesture.
Use `scripts/test focus` on an exact failing selector, fix it, run that selector once, then advance to the next unrun check; use five repeats only for a suspected race.
Run a broad browser or full lane only at the next scheduled milestone, for a change that truly requires it, or at final certification; retain successful unchanged phases after a late failure.
When stale code or a refactor need appears, get a concise plan from Astra/high or Sol/high and an independent high-reasoning review before implementation.
Commit each validated task promptly and archive completed worktree state as required by `AGENTS.md`.

Completed Tier 1A–1B ownership notes and checkpoint history are in the [progress archive](archive/platform-test-progress-through-tier-1b.md); commands, durations, limitations, and release records are in the [evidence archive](archive/platform-test-evidence-through-tier-1b.md).
Do not read these archives during an ordinary restart; open one only to audit a specific historical claim.
