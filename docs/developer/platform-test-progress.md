---
orphan: true
---

# New platform confidence campaign checkpoint

Prepared 2026-09-30; **PREPARED / NOT EXECUTED**.
Application checks remain held pending the user's model choice after the interruption; specification review and documentation checks do not restart them.
No new campaign application/browser/native checks have run, no defect has been closed, and no candidate branch has been integrated for this redesign.
The [plan](platform-test-plan.md) replaces the previous resume queue with current-baseline readiness, focused risk batches, then systematic extensions.
The [previous checkpoint](archive/platform-test-progress-before-2026-09-30.md) preserves the old outcomes and next actions as history only.

## Documentation reconciliation baseline — 2026-09-30

Static inspection for the bounded specification revision used platform `7a86007752bd0974b31ccbc635abab7ef83df81a` and sibling library `00a0e67c06c48f6a53d36cc3ab34bcb8b874bf59`.
The backend's installed metadata still identifies editable BioImageFlow `0.8.6` and Core `0.4.1` from the sibling packages, plus Wetlands `2.4.2`; this is source/installation evidence, not published-package or native certification.
The main status initially contained only the two unrelated untracked VTTs, which remain preserved.
The platform still has sixteen registered worktrees; no application repair ownership or disposition is inferred from their existence.
Documentation review and acceptance completed against the platform parent above plus reviewed documentation diff SHA-256 `384c45074016ddaf0c75899205e02e5692c0ab27686f60fbf5bbaa26e957edcf`, before this status-only result entry.
The accepted library documentation is commit `dff04e3eb7c15ded7984aa6b0befa44febe4cb37`, equivalent to the library parent above plus reviewed diff SHA-256 `be003d4cf9144518a53d27ebdf177f6cf4cdbff832912fc658f0ed1dba305ec8`, now integrated into the clean sibling main.
Reconcile the actual application/code/dependency/worktree/process baseline again before any application assertion; documentation source equivalence is not an application baseline.
No application/browser/native result, inventory cell, dashboard credit, defect closure, or candidate integration is supplied by this revision.

Documentation-only acceptance results, all exit 0:

- Platform: `/usr/bin/time -p env UV_OFFLINE=1 scripts/test check docs` passed in 3 seconds reported by the lane, 3.10 seconds elapsed, against the platform parent and reviewed diff above; historical dashboard consistency, 48 active local links, and Sphinx 9.1.0 with warnings as failures passed.
- Library: `/usr/bin/time -p env UV_CACHE_DIR=/private/tmp/bif-spec-docs-hvbwhdoj/cache uv run --no-sync --offline python docs/generate_tool_package_docs.py --check` passed in 0.32 seconds elapsed against the accepted library source above.
- Library: `/usr/bin/time -p env UV_CACHE_DIR=/private/tmp/bif-spec-docs-hvbwhdoj/cache uv run --no-sync --offline sphinx-build -W --keep-going docs/source docs/_build/html` passed in 46.08 seconds elapsed against the same accepted source; Sphinx 8.1.3 built 187 fresh pages with warnings as failures.

Library documentation setup used an isolated Python 3.10.8 environment and about 55 seconds of measured cached preparation without network; Sphinx used its configured Python/pandas intersphinx network access.
Application, browser, worker, published-package, and native certification phases were not run; the new campaign remains held with 0/4 readiness outcomes executed.

Known doc-versus-code debts remain for later owned packets: consume generated draft response/conflict types, create the required setup-needed Napari default recipe when no legacy installation exists, and preserve exact submitted original-filename metadata.
The reviewed specs retain those requirements rather than weakening them to match current gaps.
Future v3 storage roots/migration, summary join policy, shared read-only tool-store installation, and deployment security remain explicit design decisions outside this campaign preparation.

## Historical observed baseline to reconcile before execution

- Earlier campaign preparation inspected main at `973e3a80`; this is a dated historical observation, superseded for docs inspection by the baseline above. The source inventory audit still stops at `15c5cc7`.
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

1. After the user's model choice and execution request, record the accepted specification-review revisions and establish the reproducible actual baseline described in the plan: contracts, Git/worktree/process disposition, installed/declared dependency state, changes since `15c5cc7`, affected inventory/evidence, and clean task ownership. No old release needs rerunning merely to start.
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
