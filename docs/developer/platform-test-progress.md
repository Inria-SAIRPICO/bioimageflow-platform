---
orphan: true
---

# New platform confidence campaign checkpoint

Prepared and started 2026-09-30; **RUNNING — Wave 1 accepted; Wave 2 delegated**.
The user requested execution after the specification revision; the model-choice hold is lifted, and the session's model settings are unchanged.
J1–J4 now pass in Chromium and Firefox on the repaired baseline; J3 also passed five deliberate race repetitions in each browser.
Readiness frontend composite acceptance, two-browser critical smoke, independent implementation review and documentation milestone validation are complete; the task-only main commit is being integrated; native checks are not yet credited, and no historical candidate branch has been integrated.
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

## Application execution baseline — 2026-09-30

Platform `29733fafb7a27ccc749db0b78490e2bada35edd8`, with the named readiness assertion diff in `canvas-interactions.spec.ts` and `nested-execution.spec.ts`, is the executing source baseline.
Reviewed specs are integrated in that platform revision and library `dff04e3eb7c15ded7984aa6b0befa44febe4cb37`.
The library checkout is clean; installed editable BioImageFlow 0.8.6 and Core 0.4.1 resolve to its sibling packages and match `backend/uv.lock`, including its transitive editable Core source; Wetlands 2.4.2 is registry-installed.
Backend Python is 3.13.2 and Bun is 1.4.2; this checkout already has independent backend/frontend development dependencies, reused without resync while the lock/source metadata remains unchanged.
The orchestrator owns main readiness repair, integration and shared campaign records.
Two isolated ordinary workers now prepare N1 (`.worktrees/campaign-n1-current`, branch `campaign/n1-current`) and E1 (`.worktrees/campaign-e1-current`, branch `campaign/e1-current`) from `29733fa`; a reserved read-only specialist reviews the J3 implementation.
Each worker prepares independent dependencies/runtime; the new `.worktrees/bioimageflow` link exposes only the clean editable library source.
The orchestrator grants browser/real-provisioning runtime ownership explicitly, keeping browser-heavy lanes sequential while independent preparation and lower-level focused work proceed.
The two pre-existing root/frontend VTT files are preserved.
All sixteen registered platform worktrees were inspected without mutation: main, eleven clean historical worktrees (including detached `napari-review`), and four dirty preserved worktrees: `campaign-napari-chooser`, `campaign-stale-env`, `napari-frontend`, and `tool-package-no-deps`.
Every non-main worktree is preserved; only the two named campaign candidates may be inspected for later selective porting, with no ownership or passing credit inferred.
The process inspection found the long-running main-checkout Vite/esbuild developer process, code-server Python language helpers, and Playwright MCP; no competing campaign runner was observed.
Tests allocate fresh local ports and disposable runtime roots, and leave those developer processes intact.

The bounded change scan since inventory audit `15c5cc7` covers 99 files, including 43 current/removed backend/frontend implementation paths and later documentation/test records.
Affected claims remain historical until their actual assertions and execution are reconciled: napari inventory/fingerprint removal maps to GUI-SHL-009/RT-RES-011/012; source images and workflow bindings map to WF-REC-001/012 and image/result obligations; migration/result pinning/corruption maps to WF-LIF-015/RT-EXE-009/010/017 and RT-RES families; scoped execution/status and demo consolidation map to RT-EXE-003/005/007 and workflow/demo storage obligations.
The scan also contains parallel Fish Analysis changes excluded from this campaign's execution scope; their delivered contracts and tests remain intact.
No current percentage or blanket equivalence is inferred from those historical rows; the next batches reconcile affected claims individually, retaining old evidence links and the 500-cell denominator.
The known generated-draft-type, missing Napari first-use recipe, original-filename fidelity, and library image-adapter debts belong to the orchestrator's bounded future repair queue with their specification-defined acceptance; none affects the assertions of the four current readiness journeys.
The J1/J3 assertion packet follows real GUI commands through accepted root drafts, captured execution records, scoped projection requests and exact tables, with test-only changes and no production/schema/dependency changes.
Its completion scope is focused two-browser journeys plus frontend lint/types/units/build and the localized cross-browser smoke; no worker/native claim follows from Direct execution.

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
Current focused gate: **4/4 outcomes passed in both browsers**; J3 has a causally confirmed, independently reviewed repair with frontend composite and two-browser critical-smoke completion; documentation acceptance passed (2.91 s), and the task-only main commit supplies the workers' integrated baseline.

## Next three actions when execution starts

1. Send the validated main readiness commit to N1/E1, then release N1 browser ownership for its exact independent scenarios. Preserve all unfinished candidates and existing developer processes.
2. Release one worker's browser token at a time after main completion; review N1/E1 results against their impact maps and real evidence boundaries before task-only integration. Keep the reserved specialist slot for unresolved contract or identity/loss questions.
3. Finish N1 and E1 acceptance, then assign I1 import guidance and T1 Manage Tools to the available isolated workers. Reconcile obligation-level evidence without promoting mocked client results into worker/native certification.

## Carry-forward concerns and working set

[ISSUE-013, ISSUE-014, and ISSUE-017](platform-test-issues.md) remain open with their existing evidence limits.
ISSUE-018 has a reviewed causal repair and is retained in the Wave 1 archive; its resolution does not attribute or close the older intermittent observations.
No new diagnosis is established for the older intermittent workflow activation/selection or broad-lane failures.
Record event/API breadcrumbs on relevant recurrence and preserve prior red/interrupted lanes as such.
Native Napari smoke and real provisioning remain separate from mocked GUI/API scenarios.

Ordinary restarts need this file, the assigned plan section, the relevant inventory rows, and matching open issue only.
[Evidence](platform-test-evidence.md) owns new executed results; the [dashboard](platform-test-dashboard.md) owns the stable scenario denominator; source inventories own assertions and gaps.
Shared campaign status belongs to the orchestrator; N1 and E1 workers own only their isolated feature packets, with scoped validation and commits required before reviewed integration.
Follow the plan's per-edit, feature, wave, and final validation schedule; record observed setup/test costs and unchanged-phase reuse without repeating Sphinx for routine status drafts or presenting unmeasured savings.
The next baseline record must replace these observations with current facts and mark invalidated evidence without erasing its historical source.
