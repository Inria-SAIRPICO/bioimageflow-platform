---
orphan: true
---

# New platform confidence campaign checkpoint

Prepared and started 2026-09-30; **RUNNING — M1 meticulous whole-codebase review OPEN; repairs and campaign tests held; Wave 1/N1/E1 accepted, I1/T1 preserved**.
The user authorized the 2026-10-01 campaign revision following an independent GPT-6.1 Sol Ultra retrospective, then continued execution.
J1–J4 now pass in Chromium and Firefox on the repaired baseline; J3 also passed five deliberate race repetitions in each browser.
Readiness frontend composite acceptance, two-browser critical smoke, independent implementation review and documentation milestone validation are complete; the task-only main commit is `4b58e44404b7502f2df7b3f1f1b7bbaa9d0d3117`; native checks are not yet credited, and no historical candidate branch has been integrated.
The [plan](platform-test-plan.md) now requires whole-system architecture/test reconnaissance and prioritized repairs before systematic coverage expansion.
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
At that documentation-only milestone, application, browser, worker, published-package, and native certification phases had not run and readiness was 0/4; the subsequent execution sections supersede that hold.

Known doc-versus-code debts remain for later owned packets: consume generated draft response/conflict types, create the required setup-needed Napari default recipe when no legacy installation exists, and preserve exact submitted original-filename metadata.
The reviewed specs retain those requirements rather than weakening them to match current gaps.
Future v3 storage roots/migration, summary join policy, shared read-only tool-store installation, and deployment security remain explicit design decisions outside this campaign preparation.

## Application execution baseline — 2026-09-30

Platform `29733fafb7a27ccc749db0b78490e2bada35edd8`, with the named readiness assertion diff in `canvas-interactions.spec.ts` and `nested-execution.spec.ts`, is the executing source baseline.
Reviewed specs are integrated in that platform revision and library `dff04e3eb7c15ded7984aa6b0befa44febe4cb37`.
The library checkout is clean; installed editable BioImageFlow 0.8.6 and Core 0.4.1 resolve to its sibling packages and match `backend/uv.lock`, including its transitive editable Core source; Wetlands 2.4.2 is registry-installed.
Backend Python is 3.13.2 and Bun is 1.4.2; this checkout already has independent backend/frontend development dependencies, reused without resync while the lock/source metadata remains unchanged.
The orchestrator owns main readiness repair, integration and shared campaign records.
Two isolated ordinary workers own N1 (`.worktrees/campaign-n1-current`, branch `campaign/n1-current`) and E1 (`.worktrees/campaign-e1-current`, branch `campaign/e1-current`), originally created from `29733fa`.
Both now include the integrated readiness source: N1 cherry-picked its source-equivalent `261ee566d9efd9ac70251e42cd609ff4945566b1`; E1 rebased onto main `4b58e44`.
There are eighteen registered worktrees including these two; the sixteen pre-existing worktrees remain preserved.
The reserved specialist completed the J3 implementation review and two material N1 captured-identity plan passes; fresh pass 3 could not be created because the collaboration tool reached its agent-thread limit, so N1 plan convergence is not claimed.
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

## Current Wave 2 execution and next actions

N1 is integrated in main `884be6e11eb09783f80a1de0174af1f49c65e84d` from feature `45adbebc9b5f07dd16f3f85ba792d8d51df486cc`; readiness cherry-pick parent `261ee56` was excluded.
The combined inactive-dock and captured-identity repair passes all six distinguishing deferred unit regressions, seven separate client scenarios in both browsers, frontend completion and 36-test cross-browser smoke.
ISSUE-019/020 are resolved; its original Firefox stress remains 5 passed / 1 failed / 4 unrun before chooser interaction, retained as unattributed root-owned ISSUE-022.
Five RT-RES-012 obligations are now credited with explicit intercepted-client versus actual CAS storage boundaries; native RT-RES-011 remains unassessed.
Accumulated dashboard evidence is 276/500 (starting historical 266 plus N1 five and E1 five); the remaining historical cells are not a current-revision certification.
E1's real worker adapter-only test passed, but the actual GUI Run exposed a dispatch defect: ordinary `workflow.compute()` task submission bypasses adapter preparation and reaches the stale shared pool unchanged.
That failed GUI path governs E1 acceptance; reviewed task submission, shared startup/Run preparation and lazy shared-manager ownership repairs have distinguishing red/green tests and actual compute-path acceptance.
E1 rebased onto combined main `884be6e`, retaining unchanged backend/dependency digests; the three exact GUI journeys now pass in both browsers, including visible actual worker replacement/reuse, injected Pixi failure/retry and Core refusal without mutation.
The Core browser fixture initially expected dispatch despite the correct frontend validation refusal; its corrected assertion separates the real GUI refusal from the actual revision-addressed API 422, without a product change.
E1 is integrated in main `2290c67f963980f6325c93c5076c6f6e373f6129` from feature `8cc9187b3fbd5eeeaaf9fbe56e027541791f21bf`; combined-source `check app` passed in 268 s.
ISSUE-021 is resolved; ISSUE-022 remains open.
The clean integrated E1 worktree was retired intact to Trash after artifact preservation and source equivalence checks; its worker now owns T1 at `.worktrees/campaign-t1-current` from `2290c67`.
The completed clean N1 worktree was moved to Trash, registration pruned and task branch deleted after source-equivalent integration; its artifacts were preserved in `/private/tmp/bioimageflow-n1-artifacts/`.
Its worker now owns I1 in fresh `.worktrees/campaign-i1-current`, branch `campaign/i1-current` from `884be6e`, now aligned to combined `2290c67`, with independent dependencies and archive/readiness assertions.
I1 has implemented the reviewed captured-guidance/form-provenance correction in its isolated worktree; six coherent GUI checks pass across Chromium/Firefox in 34 s and 101 affected units pass in 11 s.
Its backend and frontend completion evidence is composite with original failed phases retained; the final sibling stress, cross-browser smoke, commit and integration remain pending.
T1 has reviewed isolated ownership/alias/recipe, admission, preflight and cancellation corrections; 214 focused owner tests pass in 31 s, but lifecycle/browser/app completion and integration remain pending.
Actual force-Recreate provisioning failed in 86 s: installed Wetlands 2.4.2 reuses a matching ready generation with `replace_existing=True`, contrary to the platform's forced-rebuild promise.
No private-state deletion, recipe nonce or feature narrowing was applied; this public contract boundary is the first reconnaissance priority.
Both workers preserved their WIP and artifacts without committing before the retrospective; no browser or provisioning process remains from those packets.

## Strategic revision and active reconnaissance — 2026-10-01

The independent read-only retrospective used GPT-6.1 Sol with Ultra reasoning, verified in its run metadata, after the normal collaboration spawn hit the total agent-thread limit.
It inspected representative implementation, tests and evidence at platform `d8bc910`, application `2290c67`, library `dff04e3` and the I1/T1 diffs; it did not claim an exhaustive code audit or run tests.
Its accepted conclusion is that real product/specification gains coexist with missing global architectural and suite-redundancy review; no overall speedup or duplicate removal has been demonstrated.
Retain the accepted fixes and historical red records, insert reconnaissance before coverage expansion, and use subsystem/invariant review with cross-boundary synthesis instead of disconnected per-file tasks.
The campaign's M0–M5 milestones, low-frequency retrospectives, suite-cost measurement and specification-concision rules are now explicit in the plan.
No obligation or inventory denominator changes solely because the strategy changed; the proposed 17 additional applicable omissions remain uncredited until their own reconciliation.

Current reconnaissance baseline is main `d8bc910f34acb00e5e6fb558d1130e5d08a46b10`, application `2290c67`, clean editable library `dff04e3`, and preserved I1/T1 WIP from `2290c67`.
The two unrelated untracked VTTs and historical worktrees remain untouched.
The former I1 worker now reviews graph/draft/identity and tools/sources/archives plus corresponding library contracts and tests.
The former T1 worker now reviews execution/environments/cache/results/images and platform/library/installed-Wetlands contracts and tests.
The orchestrator owns the full file manifest, deployment/persistence/integrations, test architecture/cost and shared records; the reserved reviewer checks the revised plan and then cross-boundary synthesis.
Initial reconnaissance is read-only with no new broad lanes, installation or native actions; depth and unreviewed areas are recorded explicitly rather than granting static-review coverage credit.
The first pass and independent synthesis are now recorded in the [architecture audit](platform-test-architecture-audit.md), including the complete per-file ledger and explicit unreviewed areas.
The earlier bounded synthesis initially released root dataset-publication and A portable tool-binding diagnoses plus B's force-Recreate plan; this release is superseded by the full-audit-first clarification below.
No speculative repair, coverage credit or global speedup follows from that synthesis.
Partial reconnaissance documentation acceptance: `/usr/bin/time -p env UV_OFFLINE=1 scripts/test check docs` passed, exit 0, in 2 s reported / 2.28 s elapsed at `2b945ccc` plus the five-document source manifest SHA-256 `ae85daedcdf25f6c98443d70afe8e4a03f1ceb12f7d04e0ee9ebbd574301f3da`, including the new audit and file ledger, before this status-only entry.
It verified 108 inventory rows / 500 applicable / 276 accumulated verified, 59 local links and warning-clean Sphinx; no product/browser/worker/native phase was run by that documentation check.
Root's new isolated `.worktrees/campaign-dataset-publication-current` retains two exact causally red store/real disk-spooled HTTP diagnostics as [ISSUE-023](platform-test-issues.md#issue-023--dataset-listing-publishes-an-upload-before-completion); no dataset production change is made before independent publication-plan review.
The retained T1 actual force-generation red is now [ISSUE-024](platform-test-issues.md#issue-024--explicit-force-recreate-reuses-the-selected-ready-generation).
The independent plan review found no material gate/acceptance blocker; its one context-navigation inconsistency was corrected before validation.
`/usr/bin/time -p env UV_OFFLINE=1 scripts/test check docs` passed, exit 0, in 3 s reported / 2.53 s elapsed against main `d8bc910` plus reviewed task diff SHA-256 `6d080613542082fc1093d3a6da8e27bb2ee3d63437c0204109e9f822ca3ca1c0`, before this result-only entry.
Dashboard/link checks and warning-clean Sphinx passed; no product/browser/external/native phase was run or credited for this documentation revision.

### User clarification: complete review before fixes

The user explicitly clarified that meticulous review of the entire codebase and test suites, with everything identified to fix recorded, must precede further campaign execution.
The previous 107 platform / 37 library / five Wetlands scoped inspections were selective reconnaissance, not full review; M1 is reopened and no M2 repair is released.
The two dataset red tests, four actual portable-binding red cases and public force-wrapper/publication plans are preserved as held evidence; no production change was made in these new diagnosis tasks.
The reserved C3 plan review is also held and records transaction/cleanup lifetime, short-write completeness and per-file error concerns without implementation authorization.
No new product tests, dependency installation, fixes, I1/T1 completion or native execution occurs while M1 is open.

The refreshed ledger captures platform `29d272d` (740 tracked files), library `dff04e3` (909) and Wetlands `874febd` (118), plus three installed seams and 28 held task files (I1 13, T1 11, portable diagnostics two, dataset diagnostics two).
All 1,798 entries initially have `pending` complete-review status regardless of earlier scoped inspection depth.
Source hashes distinguish frozen task bytes; campaign documents changing during the review must be rechecked at closure.
Owners work through full-file dependency-ordered batches: A 335 graph/tool/source files, B 536 execution/result/environment/Wetlands files, root 541 remaining platform/scientific files, reviewer 386 test-infrastructure/configuration/specification/documentation files.
These are assignment counts, not completed reviews.
First accepted full-content checkpoints cover 59 baseline entries (A 20, root 39), with zero accepted generated/asset classifications and 1,739 entries pending.
That first partial checkpoint is superseded by B/shared-infrastructure batch 1: 104 complete entries (103 reviewed / one classified), 1,694 pending, and 65 identified candidates recorded.
Nine counterpart-test owners were corrected; current owner counts are A 334, B 539, root 533 and reviewer 393, including the newly authored findings register.
That new control document adds one pending input beyond the 1,798 frozen baseline entries: that checkpoint was 1,799 entries / 104 complete / 1,695 pending.
A batches 2–3 now add 17 full-content files (11 platform and six library): current scope is 1,799 entries / 121 complete (120 reviewed / one classified) / 1,678 pending, with 86 identified candidates recorded.
The remaining source and test suites are still substantially unreviewed; this checkpoint does not complete M1.
These counts are review progress, not defect confirmation, code correctness or application coverage.
The [architecture audit](platform-test-architecture-audit.md) and [findings register](platform-code-review-findings.md) own durable coverage and every identified future action.

1. Review complete human-written files and their callers/tests; specifically classify generated output/assets using actual producers and consumers.
2. Merge each evidence-backed batch into the per-file ledger and findings register, retaining unresolved questions and all unreviewed entries.
3. Require zero pending/unmatched/content-hash mismatches, independent completeness sampling and cross-owner synthesis before closing M1.
4. Only then reprioritize and resume repairs/optimization, systematic coverage and certification; desktop remains final M5.

The isolated native QA root `/private/tmp/bioimageflow-campaign-native.czhkjuet` was prepared and verified before application actions at main `4b58e44`.
A current-source desktop launch at `2290c67` served the production build, but Computer Use could not bind the Python-hosted window and refused the disposable wrapper as not approved; no native acceptance is credited.
The user then explicitly moved desktop testing to the very end of the campaign; no campaign native process remains, and app access must be resolved only at that final milestone.
Cocoa/pywebview and Fiji are present; a historical installed BioImageFlow application was inventoried without being credited as the current source build.
The user supplied a live OMERO demo account; explicit headless Chromium login and authenticated read-only API collection queries returned HTTP 200 (projects 0, datasets 1, images 0).
This is an account prerequisite, not a platform/OS-keyring or image-read result; credentials are omitted from records.
A trusted disposable read-only QA package and isolated actual-desktop launcher are prepared outside the repository, with tool metadata validated; the package has not been installed/executed, and native application checks are deferred until final campaign acceptance.

## Carry-forward concerns and working set

[ISSUE-013, ISSUE-014, ISSUE-017 and ISSUE-022](platform-test-issues.md) remain open with their respective evidence limits.
ISSUE-018 has a reviewed causal repair and is retained in the Wave 1 archive; its resolution does not attribute or close the older intermittent observations.
No new diagnosis is established for the older intermittent workflow activation/selection or broad-lane failures.
Record event/API breadcrumbs on relevant recurrence and preserve prior red/interrupted lanes as such.
Native Napari smoke and real provisioning remain separate from mocked GUI/API scenarios.

Ordinary restarts need this file, the assigned plan section, the relevant inventory rows, and matching open issue only.
[Evidence](platform-test-evidence.md) owns new executed results; the [dashboard](platform-test-dashboard.md) owns the stable scenario denominator; source inventories own assertions and gaps.
Shared campaign status belongs to the orchestrator; N1/E1 are integrated and the two ordinary workers now own read-only reconnaissance while preserving isolated I1/T1 packets.
Follow the plan's per-edit, feature, wave, and final validation schedule; record observed setup/test costs and unchanged-phase reuse without repeating Sphinx for routine status drafts or presenting unmeasured savings.
The next baseline record must replace these observations with current facts and mark invalidated evidence without erasing its historical source.

### Complete-review administrative checkpoint validation

`env UV_OFFLINE=1 scripts/test check docs` passed in 3 s (2.95 s measured) at source revision `29d272dbb4d87d98e2bf236923f92dfa939018c8` plus seven audit-document changes, source-manifest SHA-256 `ae253295b28551862492358194dd9eec224e89c406df68196536297140e430d4`; the manifest precedes this result-only log entry.
The preceding runs failed in 2.86 s and 5.59 s on the same two MyST heading-fragment links; clearing the generated doctree did not repair them, and those reds remain failures.
The correction uses the actual source-heading slugs rather than rendered HTML IDs; warnings were not suppressed.
The campaign dashboard/file-existence guards and Sphinx passed; backend, frontend, browser, worker, external, published-compatibility and native phases were not run for this documentation-only checkpoint.
This validates the review records, not the completeness of M1 or application behavior.

### Complete-review source checkpoint: 197 entries

B batch 2 adds 28 complete main/held inputs, A batch 4 adds four public-library inputs, root batch 3 adds 17 scientific implementation/test inputs and shared-infrastructure batch 2 adds 27 release/package/configuration/test inputs.
Every accepted new hash matched its assigned source; held main/WIP versions remain separate inputs.
Current scope is 1,799 entries / 197 complete (196 reviewed / one classified) / 1,602 pending, with 116 identified findings recorded.
Owners have completed A 41/334, B 47/539, root 56/533 and shared reviewer 53/393; these are review judgments, not passing tests or domain certification.
M1 remains OPEN; unreviewed files, cross-owner conclusions, current control-document hashes and independent final completeness acceptance still prevent release of repairs or campaign testing.

`env UV_OFFLINE=1 scripts/test check docs` passed for the 197-entry administrative checkpoint in 3 s at revision `483ff9e` plus four changed audit files, source-manifest SHA-256 `65ae1d7008c3058a60297860089b17d1a7fbd0c51c0e07884fed5c9e3f8f292a` (manifest precedes this result-only log entry).
Only campaign-record guards and Sphinx ran; every application, browser, worker, external and native phase remains held and unrun for this checkpoint.

The first whitespace check for this checkpoint found 16 empty final TSV cells; these were normalized to the existing `-` placeholder convention without changing review judgments.
`git diff --check` then passed, and `scripts/test check campaign` passed in 1 s at `94ce5bd` plus that ledger-format correction (ledger SHA-256 `c12db34471c16559cdec88bf486abfe552903467806a74546cc99659bb73e489`, before this result-only log entry); the original whitespace red is retained separately.
No application phases ran.

### Complete-review source checkpoint: 222 entries

A batch 5 adds six callable/command/session implementation and test inputs, root batch 4 adds eleven complete scientific I/O inputs and B batch 3 adds eight local execution/result implementation and test inputs.
Every new completed hash matches its assigned source.
Current scope is 1,799 inputs / 222 complete (221 reviewed / one classified) / 1,577 pending, with 133 findings recorded.
The pending recovery coordinator test was explicitly reassigned to its complete session-source reviewer to avoid repeated review; reassignment grants no credit.
Owner progress is A 47/335, B 55/539, root 67/532 and shared reviewer 53/393.
M1 remains OPEN, with repairs and application tests held; independent final completeness review and remaining source/specification work are unrun.

### Complete-review source checkpoint: 374 entries

A batches 6–8 add 36 complete graph/persistence/recovery/workflow-store and counterpart inputs, B batches 4–6 add 27 retained-execution/preflight/result/viewer inputs, root batch 5 adds fourteen Core/worker-preflight/external-command and counterpart inputs, and reviewer batches 3–5 add 75 complete collection/reference/package-documentation inputs.
Every accepted input's current hash matches its assigned source; the new judgments include retained protections and uncertainty rather than requiring every finding to become a fix.
Current scope is 1,799 inputs / 374 complete (373 reviewed / one classified) / 1,425 pending, with 206 findings recorded.
Owner progress is A 83/339, B 82/ 541, root 81/522 and shared reviewer 128/397.
Four campaign-collection counterparts, ten engine/frontend helper inputs and three MCP source inputs were explicitly reassigned to their subsystem reviewers; reassignment itself grants no review credit.
Full workflow-store callers materially mitigate A-F053: the retained nested acceptance callback targets the shared session store, so the proposed old-mounted-canvas effect is unproved and observer changes are conditional debt.
The existing planning/cache reference target is confirmed; reviewer-F026 concerns converter/kind drift, not a missing page.
Default node serialization loses infinity/missing-value distinction through JSON null on the inspected dependency baseline; B-F043 does not claim JSONResponse failure or invalidate scientific infinite PSNR.
M1 remains OPEN: 1,425 inputs, current control-document reconciliation, cross-owner synthesis and independent final completeness acceptance remain pending.
Repairs, new diagnostic tests and all application/browser/worker/external/native phases remain held; native desktop acceptance remains final M5.

`env UV_OFFLINE=1 scripts/test check docs` passed for this 374-input administrative checkpoint in 4 s (4.09 s measured) at source revision `bd6f2fa` plus four audit-document changes, source-manifest SHA-256 `50fbc976f710496972ae9c353ebb256f7cabf3ac4e42df8999216a3d0f3c1fcd`; the manifest precedes this result-only log entry.
Campaign-record guards and Sphinx passed; backend/frontend/browser/worker/external/native phases were held and unrun.
This checks document integrity and supplies no full-audit or application acceptance.

### Complete-review source checkpoint: 501 entries

A batches 9–10 add twelve complete nested persistence/recovery/codec and counterpart inputs; B batch 7 adds thirteen full public runtime/engine/Fiji inputs; root batches 6–7 add twenty-one complete MCP/common-tool and counterpart inputs.
Reviewer batches 6–8 add 28 complete human IO/phasor/tracking guides and 53 individually justified generated wrappers; the orchestrator also inspected every classified wrapper's complete content and explicit include/navigation source authority.
Current scope is 1,799 inputs / 501 complete (447 reviewed / 54 classified) / 1,298 pending, with 229 findings recorded.
Owner progress is A 95/338, B95/ 548, root 102/517 and shared reviewer 209/396; helper/engine/test/API ownership transfers grant no incidental review credit.
The public Workflow.plan cycle exception is confirmed consistent; reviewer-F026 remains only catalogue/converter drift.
Root's MCP trace corroborates A-F020 global named-draft context publication; ROOT-F048 separately records incompatible argument/recommendation examples.
ROOT-F050–F052 are qualified image-layout, merged-schema and external table/cache ownership decisions, preserving documented features rather than treating every uncertainty as a confirmed runtime defect.
The full human specifications, remaining source/test suites, current control-document reconciliation, cross-owner synthesis and independent final completeness review remain pending.
M1 remains OPEN; no repair, diagnostic test, application/browser/worker/external/native execution is released by these review counts or generated classifications.

`env UV_OFFLINE=1 scripts/test check docs` passed for the 501-input administrative checkpoint in 4 s (4.73 s measured) at source revision `7f4c211` plus four audit-document changes, source-manifest SHA-256 `a282b25c486eb9ccf07a95b719886db96d93c095fa179d2014a99e369e264335`; the manifest precedes this result-only log entry and prose-spacing cleanup.
Campaign-record guards and Sphinx passed; all backend/frontend/browser/worker/external/native phases remain held and unrun.
This is documentation-integrity evidence only; 1,298 pending inputs and independent completeness still prevent M1 closure.

### Complete-review source checkpoint: 705 entries

A batches 11–14 add fourteen complete workflow-store, generation/migration/demo, CanvasView, App and Save-helper inputs; B batches 8–9 add 52 complete execution-identity/storage/publication and counterpart inputs.
Reviewer batches 9–16 add 92 complete human package/authoring/platform/remote guides and 46 individually justified generated navigation wrappers.
The orchestrator read the complete reports and every new wrapper's full content; all accepted source hashes match the assigned manifest, and borrowed excerpts or complete context without an owned judgment grant no duplicate credit.
Current scope is 1,799 inputs / 705 complete (605 reviewed / 100 classified) / 1,094 pending, with 269 findings recorded.
Owner progress is A 109/338, B 147/465, root 102/600 and shared reviewer 347/396.
The 23 pending storage implementation/test inputs were formally transferred from root to B, and the 106 pending Wetlands checkout inputs from B to root; transfer itself grants no credit.
The source findings include exact mixed-numeric dataframe identity and final no-replace export admission risks, incomplete enclosing-interface grouping, migration validation authority, asynchronous clipboard admission and nonstartup shell lifetime ownership.
These are static findings with their documented mitigations and future discriminating selectors, not newly executed failures.
B-F068 requires pointer invalidation/reselection without documented coordination; ordinary first-winner publication does not prove a default supported Run race.
A-F091 is conditional two-endpoint callback debt: ordinary one-endpoint cross-region gestures are refused.
The full App review further narrows A-F088: ordinary Open activates an existing root rather than replacing its graph, and supplies no explanation of historical ISSUE022.
ROOT-F050 and ROOT-F052 source citations were corrected to Mosaic's actual initial-frame read and WriteTable's actual transform; their qualified behavior/contract findings are unchanged.
The current authoring examples' missing concrete-class declarations/output constructor and stale implemented-tool claims are recorded without weakening essential behavior or implementing roadmap proposals.
M1 remains OPEN: remaining source/tests/specifications, current control-document reconciliation, cross-owner synthesis and independent final completeness acceptance are pending.
Repairs, new diagnostic tests and every application/browser/worker/external/native execution phase remain held; native acceptance remains final M5.

`env UV_OFFLINE=1 scripts/test check docs` passed for the 705-input administrative checkpoint in 4 s (4.05 s measured) at source revision `30a4de1` plus four audit-document changes, source-manifest SHA-256 `cbd5696733d2e172814f275b4e64affd949627425cf9b99699fa63778d73f572`; the manifest precedes this result-only log entry.
Campaign-record guards and Sphinx passed, and `git diff --check` passed; all application/backend/frontend/browser/worker/external/native phases remain held and unrun.
This supplies documentation-integrity evidence only; M1 and independent completeness remain open.

### Complete-review source checkpoint: 913 entries

A batches 15–20 complete 65 additional editor, clipboard, recursive graph, library example/manifest and counterpart inputs; B batches 10–13 complete 76 additional remote submission, launcher/control, typed-return and Core/shared-memory inputs.
Root batches 8–10 complete 49 Wetlands lifetime/protocol/codec, native-entrypoint source, selected-node presentation and complete counterpart inputs.
Reviewer batches 17–21 complete 12 additional human specifications/guides/producers and six individually justified artifact classifications.
The orchestrator fully read the new reports, reconciled named contract disagreements and verified current hashes before accepting distinct owned judgments; borrowed context and ownership transfer grant no duplicate credit.
Current scope is 1,799 inputs / 913 complete (807 reviewed / 106 classified) / 886 pending, with 348 identified findings recorded.
Owner progress is A 174/347, B 223/490, root 151/565 and shared reviewer 365/397.
Four editor implementations and two corresponding tests were transferred to A, the desktop entrypoint to root, the 750-line preview producer to the reviewer, 31 pending Parsl source/counterpart inputs to B and three pending resource/viewer/origin tests to A.
HPC runtime exclusion does not exclude static Parsl engine/future lifetime review; desktop source review performs no native acceptance action, which remains final M5.
The backlog now distinguishes configured-webapp editor guards from mutable-settings policy, physical cancellation acknowledgment from retained cleanup ownership, native destruction retry from harmless already-absent close, and possible live-output EOF/group-identity interleavings from executed failures.
The earlier library Python-floor claims were explicitly withdrawn: Core supports Python >=3.9 and the library >=3.10; the retained platform prerequisite finding is separate.
Type partial-overlap compatibility is explicitly tested existing behavior, and available plain-string schema derives known/viewer=None; neither is reclassified as a confirmed compatibility defect.
Example factory checks establish structural/public-load validity, not declarative quantitative scientific acceptance, while current static previews are illustrations and their precise producer/caption correspondence remains pending.
Test-suite improvements are recorded against actual oracles: unreached failure branches, manually replicated subscriber logic, file-handler/child fixture lifetime and timing coordination; no deletion, new diagnostic test or measured speed gain is claimed.
Full remaining source/tests/specification review, current mutable-control reconciliation, cross-owner synthesis and independent final completeness acceptance remain pending.
M1 remains OPEN; repairs, new diagnostic tests and all application/backend/frontend/browser/worker/external/native execution remain held.

`env UV_OFFLINE=1 scripts/test check docs` passed for the 913-input administrative checkpoint in 4 s (4.68 s measured) at source revision `3cd3ad7` plus four audit-document changes, source-manifest SHA-256 `dafe9629e950c9d99f830547f5ce8f962d8cdee97f353454c7305bc1fc1627e0`; the manifest precedes this result-only log entry.
The preceding documentation-only pass took 8.32 s; a corrected human/classified subtotal required the final 4.68 s recheck.
Campaign-record guards and Sphinx passed, and `git diff --check` passed; backend/frontend/browser/worker/external/published-compatibility/native phases were held and unrun.
These commands establish audit-document integrity only; complete code review, cross-owner synthesis and independent acceptance remain open.

### Complete-review source checkpoint: 1,034 entries

A batches 21–23 complete 22 additional loading, inspection, public registry/session, GUI guidance and counterpart inputs; B batches 14–16 complete 38 additional Parsl, managed-factory, retry and counterpart inputs.
Root batches 11–12 complete nineteen Wetlands provisioning/runtime-registry and scientific wrapper/counterpart inputs; reviewer batches 22–25 complete 21 human inputs and 21 individually justified asset/lock/link classifications.
Every newly accepted owned source hash was checked against actual bytes, and all new reports were read in full before integration.
Current scope is 1,799 inputs / 1,034 complete snapshot judgments (907 reviewed / 127 classified) / 765 pending, with 392 distinct identified findings.
Owner progress is A 196/353, B 261/490, root 170/504 and shared reviewer 407/452.
Fifty-five remaining Wetlands configuration, documentation, CLI/debug/diagnostic, release and counterpart inputs were transferred to the shared reviewer; loader and source/session counterparts were transferred to A.
Transfers supply no review credit, and the library specs.md link classification supplies no human target credit: its complete human target belongs to B and remains pending at this checkpoint.
Canonical finding headers were reconciled so the A-F026 and A-F117 extensions do not inflate the distinct count.
The review distinguishes physical cleanup acknowledgments, malformed registry diagnostics and postinstall lock fidelity from actual new runtime failures; scientific wrapper argument mocks do not certify each external dimensional mode.
Public-loader cache and dependency lifetime, incremental Session wire/cache authority, retry-after-publication replay and concurrent dispatch ownership retain their specific mitigations and future distinguishing diagnostics.
The managed-factory trace corroborates reviewer-F040: the current public route refuses ordinary common-tool recipes at exact runtime attestation, rather than demonstrating execution in a wrong worker.
Five mutable campaign controls were fully reviewed against exact current snapshots; changed administrative deltas still require reopening before final acceptance, and stale historical J1/J3 wording is recorded as reviewer-F052 without releasing repairs.
All remaining human source, tests and specifications, current mutable-control and generated-ledger provenance reconciliation, cross-owner synthesis and independent completeness acceptance remain pending.
M1 remains OPEN; repairs, new diagnostic tests and application/backend/frontend/browser/worker/external/published-compatibility/native execution remain held.
Native desktop acceptance remains final M5.

`scripts/test check campaign` passed for the 1,034-input administrative checkpoint in 0 s (runner-reported) at source revision `c13ff8d140b04fb16ac2d355694be54327560fb8` plus four audit-document changes, source-manifest SHA-256 `3aa5e4e9df22028fe4473834a2c2509b4408ade0fb23161acca63315e8932592`; the manifest precedes this result-only log entry.
Campaign-record guards and all 64 active local links passed, and `git diff --check` passed.
This routine ledger/checkpoint update changes no documentation navigation or product behavior, so the documented scoped campaign check is sufficient; the previous Sphinx pass remains historical and was not rerun.
All application/backend/frontend/browser/worker/external/published-compatibility/native phases remain held and unrun, and no audit or product acceptance follows from this administrative check.

### Complete-review source checkpoint: 1,189 entries

A batches 24–26 add 42 fully reviewed library contract/example/counterpart inputs and seven exact producer-linked wrapper classifications; B batches 17–19 add thirty fully reviewed specification/protocol/validation/counterpart inputs.
Root batches 13–15 add 37 fully reviewed segmentation/tracking/spot runtime/helper and complete numerical/model/worker/mock counterparts; reviewer batches 26–29 add 35 human Wetlands source/tutorial/release-test inputs and four individually justified artifact classifications.
Current scope is 1,799 inputs / 1,189 complete snapshot judgments (1,051 reviewed / 138 classified) / 610 pending, with 426 distinct findings.
Owner progress is A 245/353, B 291/489, root 207/462 and shared reviewer 446/495.
The public cluster source and its 43 root-owned pending counterparts were transferred cohesively to the reviewer; two complete Wetlands protocol counterparts went to B, and the segmentation execution counterpart plus two scientific helper sources went to root.
Ownership transfer itself grants no credit, and all newly accepted source hashes matched actual current bytes.
The complete 3,314-line human library specification is now B-reviewed; the navigational specs.md alias adds no second human body credit.
A's entire assigned library slice and the reviewer's newly transferred Wetlands slice are individually complete, while other library/platform/current-control and held-WIP inputs remain pending; neither subtotal closes the global audit.
Complete scientific counterparts preserve useful sparse-ID, numerical assignment/motion/plateau, empty immutable artifact, cache/readback and distinct mock/actual-runtime oracles.
New scientific findings qualify local-model digest versus reused model ownership, singleton spatial-axis extraction, root versus immediate-image grouping, empty rendering admission and unbalanced assignment matrix costs; no model/binary execution or measured optimization occurred.
The whole specification narrows B-F067: captured custom-source hashes already participate through tool version, so its earlier blanket exclusion was withdrawn in the canonical finding; the remaining equal-version different-origin/output-contract risk is explicit.
Current public authoring grammar, constructor storage scope, inherited image metadata and typed shared-memory task serialization were reconciled against actual consumers without treating a surviving partial plan as permission for invalid execution.
Wetlands suite review identifies existing transport oracles omitted from automatic CI and bounded-versus-total debugger deadlines; the real-Pixi chain's distinct lifetime/oracle/setup amortization remains valuable and unrun.
The review keeps future repairs, diagnostic selectors, documentation reconciliation and unmeasured performance candidates separate from accepted runtime evidence.
All remaining platform/library/cluster/installed-runtime/held-WIP inputs, current mutable-control and generated-ledger provenance reconciliation, cross-owner synthesis and independent completeness acceptance remain pending.
M1 remains OPEN; every repair, new diagnostic test and application/backend/frontend/browser/worker/external/published-compatibility/native execution phase remains held.
Native desktop acceptance stays final M5.

`scripts/test check campaign` passed for the 1,189-input administrative checkpoint in 0 s runner-reported (0.25 s measured), at source revision `42222ad` plus four audit-document changes, source-manifest SHA-256 `7ef3a70a687a78b9399df670860288e291072b2daebecee72f637bb77fc25f6a`; the manifest precedes this result-only log entry.
Dashboard consistency, all 64 active local links and `git diff --check` passed; no document navigation change invalidated the earlier Sphinx result, so Sphinx was not repeated.
Every application/backend/frontend/browser/worker/external/published-compatibility/native phase remained held and unrun, with no audit or product certification claimed.

### Complete-review source checkpoint: 1,292 entries

A batches 27–29 add fifteen complete human platform inputs and one explicitly producer-linked generated API classification; B batches 20–24 add forty-three complete platform/library implementation, test and human-contract inputs.
Root batch16 adds twenty-six complete public authoring/runtime/Core-dependency/path/template/logging source and exact counterpart inputs; reviewer batches30–33 add eighteen complete public cluster value/protocol/preparation/deployment source and counterpart inputs.
Current scope is 1,799 inputs / 1,292 complete snapshot judgments (1,153 reviewed / 139 classified) / 507 pending, with 463 distinct findings.
Owner progress is A 261/353, B 334/492, root 233/459 and shared reviewer 464/495.
Three already completely borrowed query/output-view counterparts were formally transferred from root to B before their pending per-file judgment; ownership transfer itself adds no credit.
All accepted input bytes match their exact owned manifests; no inventory scan or partial source excerpt is counted as a complete human review.
The registry/watcher/UI review identifies stale snapshot/lifetime/admission/display seams while preserving real exact-byte reload and rollback tests; generated API ownership is explicitly classified without claiming regenerated schema equality.
Public authoring review records global automatic-name reset, positional rejected-invocation mutation, Core extras/channel identity classification and genuine DataFrame duplicate-suffix column loss; actual Direct path/template/plan and logging ownership oracles are preserved.
Runtime cache suite and full storage/contracts were reconciled: durable SharedArray assets and Direct cache tests remain essential, while zero-copy/general transport claims and external typed task codec certification stay qualified.
Cluster review records pre-coercion public input refusal, source-open boundedness, cleanup retry ownership and declared project-root capture risks; later refusal, exact confirmation digests and trusted-local limitations remain explicit.
All remaining human source/tests/specs, assets/gitlinks/installed-runtime/held-WIP inputs, current mutable controls and generated-ledger producer provenance, cross-owner synthesis and independent completeness acceptance remain pending.
The finding count includes qualified source risks, documentation/test-oracle discrepancies and unmeasured maintenance/performance candidates; it is not a count of executed failures or approved repairs.
M1 remains OPEN; repairs, new diagnostic tests and application/backend/frontend/browser/worker/external/published-compatibility/native acceptance remain held and unrun.
Native desktop acceptance remains final M5.

`scripts/test check campaign` passed for the 1,292-input administrative checkpoint in 0 s runner-reported (0.35 s measured), at source revision `ed5a61b5bdaa7293fd31669115ce7c2f323b700d` plus four audit-document changes, source-manifest SHA-256 `46b31b3b9dee896a4dd751f152184efa6df15a85bc8117a767e6feb7f0bfb8c0`; the manifest precedes this result-only log entry.
Dashboard consistency, all 64 active local links and `git diff --check` passed.
Sphinx was not repeated for this routine ledger/checkpoint update, which changes no navigation.
Every application/backend/frontend/browser/worker/external/published-compatibility/native phase remained held and unrun; no full suite, completeness gate or product certification is claimed.

### Complete-review source checkpoint: 1,550 entries

Since the1,292-input checkpoint, accepted additions are A65 human, B35 human, root55 human plus5 individual artifact/pointer classifications, and reviewer98 human inputs.
These encompass A batches30–38, B25–30, root17–19 and reviewer34–41.
Current scope is1,799 inputs / 1,550 complete snapshot judgments (1,406 reviewed / 144 classified) / 249 pending, with532 distinct findings.
Owner progress is A 326/354, B 369/493, root 293/365, reviewer 562/587.
Pending coherent UI/utilities/error/WebSocket counterparts and installer/preference tests were formally reassigned before individual review; ownership transfer itself grants no credit.
Complete public runtime/cache/integration and worker/cluster counterpart review distinguishes seeded records, mocked transport and actual Direct execution test bodies without claiming fresh passes.
The unused IndexedDB helper is separated from current recovery storage, and active ImageCell clipboard handling is traced through the real hidden-action PathCell consumer.
Ordinary same-app workspace mutation serialization narrows B-F157/B-F159/B-F161; internal callbacks, draft bypasses and independent writers retain separately qualified concerns.
Source-established uninstall target escape, Tree key collision and demo-removal identity discard join the held backlog; no destructive diagnostic or repair occurred.
The signing pointer hash explicitly addresses its canonical tracked gitlink descriptor, not private signing contents; each visual artifact has an individual producer/consumer qualification with no native rendering claim.
Frozen I1 source review preserves its captured recipe/provenance improvements and distinguishes constructed archive/runtime test bodies from untouched roundtrip or published/native certification.
Documentation/test process findings concern existing selectors and assertion fidelity; no coverage removal or measured speedup is claimed.
All remaining human inputs, current mutable controls and generated-ledger/self-hash provenance, cross-owner synthesis and independent completeness acceptance remain pending.
M1 remains OPEN: repairs, new diagnostic tests and application/backend/frontend/browser/worker/external/published-compatibility/native acceptance remain held and unrun.
Native desktop acceptance remains final M5.

`scripts/test check campaign` passed for the1,550-input administrative checkpoint in0s runner-reported (0.17s measured), at source revision `17fbf13a7eabbd5e4aed36414835e6de1630f8bb` plus four audit-document changes, source-manifest SHA-256 `ccb5e5930a703d28d73df47f361364b07ebf27a37df0119eb5b91152a7c6d71b`; the manifest precedes this result-only entry.
Dashboard consistency and all64 active local links passed; `git diff --check` passed.
This routine consolidation changes no documentation navigation, so Sphinx was not repeated; earlier structural validation remains historical.
All application/backend/frontend/browser/worker/external/published-compatibility/native phases remain held and unrun, with no whole-audit or product certification claimed.

### Complete-review source checkpoint: 1,702 entries

Since the1,550-input checkpoint, individually accepted additions are A20 human, B41 human, root72 human and reviewer19 human inputs.
These encompass A39–46, B31–36, root20–27 and reviewer42–46; reports were read fully before exact-hash integration.
Current scope is1,799 inputs /1,702 complete snapshot judgments (1,558 reviewed /144 classified) /97 pending, with558 distinct identified findings.
Owner progress is A346/354, B410/463, root365/365, reviewer581/617.
The30 pending backend model/service/router sources were formally transferred from B to reviewer; transfer grants no review credit.
Root's frozen owned slice is complete, while the whole review remains open for the other owners, current mutable controls, synthesis and independent completeness gate.
Actual browser source review preserves accepted-draft CAS, real Direct rows, owned recursive source bytes, immutable record quarantine and distinct gesture-to-storage oracles.
Mock execution202, injected diagnostic/progress state, fabricated development metadata and absent navigation assertions remain explicitly qualified rather than accepted as worker/native evidence.
The moved-position Redo oracle gap does not imply globally missing Redo coverage: existing everyday tests assert actual accepted mixed edits, enabled state and atomic deletion through Redo.
Current and held viewer/specification review distinguishes carried authority and managed guidance ownership from ordinary Save's missing requirement-report refresh; dependency-dialog prose contradicts a tested explicit install-all feature and must retain that feature.
Clear's never-run response/read status seam is separate from the useful retained-downstream out_of_date behavior demonstrated by existing real compute/reload/rerun tests.
No tests or product/spec behavior were changed; candidate findings remain qualified source risks, oracle/documentation discrepancies and unmeasured optimization candidates, not558 reproduced failures or approved repairs.
M1 remains OPEN; repairs, new diagnostic tests and application/backend/frontend/browser/worker/external/published-compatibility/native acceptance remain held and unrun.
Native desktop acceptance remains final M5.

`scripts/test check campaign` passed for the1,702-input administrative checkpoint in0s runner-reported (0.17s measured), at source revision `0c723cc57dec569f2f9917e18cdd6c94efdca36a` plus four audit-document changes, source-manifest SHA-256 `6393d673bb7800c4d5b5390e802093110c8babf9c7e64de44f1e5c485ea6a051`; the manifest precedes this result-only entry.
Dashboard consistency and all64 active local links passed; `git diff --check` passed.
Sphinx was not repeated for this routine status consolidation, which changes no navigation; all application and external/native phases remained held and unrun, with no complete-review or product certification claimed.
