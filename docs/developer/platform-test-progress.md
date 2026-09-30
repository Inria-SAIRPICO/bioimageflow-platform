---
orphan: true
---

# New platform confidence campaign checkpoint

Prepared 2026-09-30; **execution not started**.
No new campaign application/browser/native checks have run, no defect has been closed, and no candidate branch has been integrated for this redesign.
The [plan](platform-test-plan.md) replaces the previous resume queue with current-baseline readiness, focused risk batches, then systematic extensions.
The [previous checkpoint](archive/platform-test-progress-before-2026-09-30.md) preserves the old outcomes and next actions as history only.

## Observed baseline to reconcile before execution

- Main inspected at `973e3a80`; the source inventory audit stops at `15c5cc7`.
- Installed backend metadata: BioImageFlow `0.8.6` and Core `0.4.1`, both editable from sibling `bioimageflow/packages/*`; Wetlands `2.4.2`.
- Sibling library was clean at `00a0e67c06c48f6a53d36cc3ab34bcb8b874bf59`; verify again at execution. Declared dependency sources and installed editable Core are separate facts to reconcile.
- Sixteen registered worktrees were observed. Dirty `campaign-napari-chooser` at `3e2a647` and dirty `campaign-stale-env` at `650ddd7` are preserved candidates, with no active execution ownership assigned by this campaign.
- Napari candidate documents prospectively claim verified cells without a passing completion record; the latest inspected Chromium artifact failed. These are unverified edits, not evidence to promote.
- Main contains unrelated untracked `.vtt` files at the repository root and in `frontend/`; leave them untouched. Recheck actual status instead of relying on the obsolete historical `presentation/` warning.

The historical dashboard remains **266/500 overall and 224/224 primary GUI**, with 228 gaps and six unassessed obligations.
These are accumulated historical evidence counts, not current readiness or a current-revision lane pass.
The old 73-cell gate passed at `50c1af4`; it does not pass the new four-outcome gate.
Current gate: **0/4 outcomes executed**, with both Chromium and Firefox still required for each.

## Next three actions when execution starts

1. Establish the reproducible baseline described in the plan: Git/worktree disposition, installed and declared dependency state, changes since `15c5cc7`, affected inventory/evidence, and clean task ownership. No old release needs rerunning merely to start.
2. Map each repair's changed files through owners/callers/storage/events/library consumers to exact selectors and its required completion scope, then run J1–J4 in Chromium and Firefox; repair demonstrated reachable failures with focused evidence and the applicable completion check before claiming readiness.
3. Start N1 Napari chooser/favorite with independently runnable launch, favorite/persistence, dock/scroll, and refusal/recovery cases; compare candidate changes with main first. E1 stale processing environments, I1 import guidance, and T1 Manage Tools follow.

## Carry-forward concerns and working set

[ISSUE-013, ISSUE-014, and ISSUE-017](platform-test-issues.md) remain open with their existing evidence limits.
No new diagnosis is established for intermittent workflow activation/selection or broad-lane failures.
Record event/API breadcrumbs on relevant recurrence and preserve prior red/interrupted lanes as such.
Native Napari smoke and real provisioning remain separate from mocked GUI/API scenarios.

Ordinary restarts need this file, the assigned plan section, the relevant inventory rows, and matching open issue only.
[Evidence](platform-test-evidence.md) owns new executed results; the [dashboard](platform-test-dashboard.md) owns the stable scenario denominator; source inventories own assertions and gaps.
Shared campaign status belongs to the orchestrator; no worker currently owns a new-campaign task.
Follow the plan's per-edit, feature, wave, and final validation schedule; record observed setup/test costs and unchanged-phase reuse without repeating Sphinx for routine status drafts or presenting unmeasured savings.
The next baseline record must replace these observations with current facts and mark invalidated evidence without erasing its historical source.
