---
orphan: true
---

# New platform confidence campaign checkpoint

Prepared and started 2026-09-30; **RUNNING — M1 agreed-scope review COMPLETE; M2 first-wave delivery and separate selection repair; full/browser/published/native certification OPEN**.
The user authorized the October 2 retrospective update and continued execution; the [current queue and gates](#october-2-strategic-checkpoint-and-first-wave-delivery) supersede earlier dated status statements.
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

### Complete frozen-source review checkpoint and final-control reopening

All frozen source/test/specification/held-WIP and dependency inputs have now received an individual full review or explicit producer/consumer classification, subject to final current-control reconciliation and independent acceptance.
A's354, B's438 and root's390 assigned inputs are complete; the shared reviewer has611 previously accepted snapshot judgments, with six pending controls and the changed architecture audit explicitly reopened.
The installed Wetlands2.4.2 three-seam review is a newly captured current snapshot because the initial reconnaissance lacked hashes; all three full installed bodies match their source checkout bytes, without claiming historical runtime baseline equality.
All740 frozen platform,909 library and118 Wetlands tracked entries remain inventoried;28 held WIP and3 installed dependency inputs plus the newly authored findings register complete the1,799-input scope.
The signing row addresses only its identical canonical tracked gitlink descriptor, with private signing content excluded; packaged icons/VSIX/lockfiles/generated schemas have individual producer/consumer limits.
Reviewed rows no longer retain stale inventory-only depth; the conservative minimum is read, with prior traced/deep evidence retained, while classified rows explicitly record their producer boundary.
The ledger's generated self-input uses SHA256 of its canonical LF TSV after replacing only its own content_sha256 cell with a literal dash; this avoids an impossible recursive hash and is verified separately from raw human-input SHA256.
The register and audit are human review deliverables, with the already-reviewed base plus every changed delta requiring final exact-content reconciliation.
There are1,792 accepted snapshot inputs (1,643 reviewed /149 classified) and seven pending/reopened current controls, with573 canonical identified candidates.
These candidates include source-established behavior, qualified risks, test/doc discrepancies and unmeasured cost debt; they are not573 reproduced bugs or approved fixes.
Cross-subsystem synthesis is recorded above, including public force-Recreate, executable authority, destructive publication, invocation ownership, scientific/result semantics and proportionate test/documentation lanes.
Independent review samples other owners; A does not independently accept its own354 judgments, which B cross-checks separately.
M1 remains OPEN while the current controls and independent method/evidence gate finish; all repairs, new diagnostic tests and application/external/native acceptance remain held.
Desktop native acceptance stays final M5.

### Authorized worktree and environment retirement — 2026-10-01

The delegated cleanup owner reconciled all20 registered platform worktrees against main `41641d61bec32595ab17afc3ffff73196fa24fc2`, tracked/untracked state, merged-HEAD ancestry and active process paths.
Only clean merged unused `.worktrees/napari-environments` at `efb56f977a3b0ca647862082b6e9e82f816c63a3` and detached `.worktrees/napari-review` at `28b17f06bc2cefd01c656afc1bf2e3e53108cd7d` were retired.
Their exclusive backend `.venv` and frontend `node_modules` directories, plus `napari-environments/frontend/dist` and `napari-environments/docs/_build`, were removed: six rebuildable stores with1,217,171,456 allocated bytes before removal, each confirmed absent afterward.
Remaining source and test evidence were moved with `mv` to `/Users/amasson/.Trash/bioimageflow-completed-worktrees-20261001-170149`; these45,408,256 retained allocated bytes are not counted as reclaimed space.
`git worktree prune` succeeded, and only the merged `feature/napari-environments` branch was deleted; the detached tree had no branch to delete.
Observed volume free space increased59,875,328 bytes across the operation; concurrent writes/APFS accounting prevent equating that observation with the1,217,171,456 bytes of removed stores.
All held I1/T1/dataset/tool-binding work, dirty or unmerged historical platform/library worktrees, main dependencies/runtime and developer processes were preserved.
The campaign plan/start/context now require a cleanup owner, evidence retention, physical process retirement, exclusive-store deletion after clean integration, and overdue-retirement reconciliation at each major checkpoint.
This housekeeping supplies no product, diagnostic, browser, worker or native acceptance and does not itself close M1.

### M1 complete-review closure — 2026-10-01

All 1,799 agreed-scope inputs are accepted: 1,649 complete human reviews and 150 explicit generated/asset classifications, with zero pending, missing, duplicate, unmatched or current-hash-mismatched entries.
The scope remains 740 platform tracked paths, 909 library/Core paths, 118 entire Wetlands checkout paths, 3 current installed seams, 28 held WIP inputs and 1 new human findings register.
Final ownership is A 354, B 437, root 390 and shared reviewer 618; the cleanup-policy Context control was formally transferred from B to the reviewer, adding no source credit.
The reviewer read all nine current human controls completely, including the complete 7,656-line register, recovered truncation holes and all terminal deltas, and classified the ledger through complete row/producer reconciliation plus its documented nonrecursive selfdigest.
The independent method review supports other owners' source/oracle samples and exact membership; B separately cross-checks A, avoiding self-acceptance and any claim of a second full reading of every input.
Its specificity, historical/current wording and selfdigest concerns were corrected and reconciled before closure.
All 573 canonical candidates and their qualifications remain in the register; this is agreed-scope review completeness, not proof of defect absence, 573 reproduced bugs or blanket repair approval.
The prioritized cross-subsystem synthesis preserves essential project features and defines bounded repair/retain/deepen/defer decisions, proportionate existing test/docs lanes and low-frequency strategic retrospectives.
No product fixes, new tests, dependency provisioning or application/browser/worker/external/native acceptance occurred during M1; accumulated dashboard evidence remains 276/500 with its historical limits.
Next is the M1 strategic retrospective and M2 packet prioritization: reconcile demonstrated portable-authority/dataset-publication reds, reachable destructive/credential risks and public force-Recreate ownership before dependent repairs, retaining accepted N1/E1 and held I1/T1 evidence.
Every later source change reopens its affected review/contract/oracle claims; unchanged review inputs and valid equivalent passing phases are retained rather than blindly repeated.
Desktop application execution remains final M5.

`env UV_OFFLINE=1 scripts/test check docs` passed, exit 0, for the complete-review/cleanup-policy documentation milestone: 6 s runner-reported and 6.49 s measured at source revision `41641d61bec32595ab17afc3ffff73196fa24fc2` plus the eight reviewed documentation changes, source-manifest SHA256 `90e2a50de17aac5f7b99624681cc500187026b0cd2cae36c0813bfeb1a5a67d3` before this result-only entry.
Dashboard consistency: 108 rows/500 applicable/276 historical verified/224 primary verified, all 64 local links in 10 active campaign files, and Sphinx 9.1.0 with warnings treated as failures passed.
`git diff --check` passed; the final generated-ledger and current-content reconciliation retain 1,799 accepted inputs with zero pending/missing/drift/duplicate/unmatched entries and 573 unique canonical candidates.
No documentation phase was skipped, deselected, flaky or externally blocked; no application/backend/frontend/browser/worker/external/published-compatibility/native phase was run or certified by this documentation-only command.
This result-only metadata delta was separately reviewed against the accepted source snapshot; no structural documentation change required another Sphinx run.

## M1 strategic retrospective and first bounded M2 queue — 2026-10-01

This retrospective starts from clean platform `b6dabfa34371218228d2d13729ee86c8a991f1c2`, product source `2290c67`, accepted library `dff04e3`, and reviewed Wetlands checkout `874febd`; installed Wetlands 2.4.2 equivalence is the preceding M1 snapshot, to be rechecked before an executable packet.
The accepted 1,799-input review and 573 qualified candidates supply a complete agreed-scope backlog, not 573 reproduced defects or blanket implementation approval.
The [audit synthesis](platform-test-architecture-audit.md#cross-subsystem-synthesis-before-the-completeness-gate), [canonical findings](platform-code-review-findings.md) and [per-file ledger](platform-test-file-review.tsv) remain the evidence authorities; this queue selects decisions and dependencies without copying or relabelling their individual statuses.
No production repair, new diagnostic execution, provisioning, browser or native result is supplied by this retrospective.

### Consequential priorities and impact ownership

The strongest new evidence is the held actual portable-authority and dataset-publication reds, alongside source-established arbitrary-target deletion and credential rollback loss.
These take precedence over optional suite cleanup, documentation polish, and resuming coverage by inventory order.
The repeated architectural causes are competing executable identities, mutation admission that does not prove the selected owner, publication before complete physical work, and losing cleanup ownership before physical retirement.
Resolve those seams in bounded packets; a common symptom is insufficient reason to introduce a global coordinator or merge independent persistence domains.

| Priority and owner | Source → affected consumers and authority | Evidence and decision required | Packet boundary and preserved behavior |
| --- | --- | --- | --- |
| First: A, portable executable authority, A-F001–003/A-F066 | `graph_translator`/`workflow_artifacts` → `graph_builder`/validator → public library materialization; requirements/rebind, source metadata, resource/engine and structural-output consumers | Held public two-version and owned-source controls distinguish carried Processing identity/floors from same-name catalog DataFrame/higher-floor classes. Decide one bound-class authority and serialize-only versus materializing consumers before implementation; current public materialization ignores DataFrame `resource_overrides`, so delegation alone cannot preserve that refusal. | Carried package/module/class/version and recursive owned source remain authoritative; ordinary unbound catalog discovery and explicit rebind remain supported. Keep serialization free of source imports; actual compiled public `node.tool` can distinguish applicability/engine and the public Processing setter validates floors without compiling twice. Trace output/editor/import consumers and decide A-F003 locality/availability explicitly; do not copy executable class state into a second registry. |
| First: B, destructive package admission, B-F168 and A-F124 extension | DELETE tools router → `PypiPackageInstaller.uninstall` → selected tool-store path/Trash fallback → registry/hot-reload; analogous install cleanup belongs to the public library loader | Source shows raw absolute/traversal version can retarget removal; existing real installer tests cover legitimate temporary targets while router mocks conceal this admission. Establish component, resolved containment and selected-store ownership refusal before any removal. | Preserve selected-version/all-version removal, legitimate install pins and refresh. Diagnose using disposable sentinels and a recording removal seam; no user filesystem deletion or network install is needed. Keep install publication/rollback as a separately scoped follow-up unless it is required to close the same admission boundary. |
| First: orchestrator, dataset publication/mutation decision, ROOT-F006–010/011 | datasets upload/list/delete routes → `DatasetStore` → complete staged bytes, SQLite catalog/revision and legacy reconciliation → dataset panel/API clients | ISSUE-023 supplies two causal store/real disk-spooled HTTP reds. Shared catalog admission also affects compatibility delete membership, pre-lock CAS and mixed containment failure bookkeeping; these adjacent risks are source findings, not reproduced reds. | First produce one independently reviewed mutation/publication plan; then split publication and deletion implementations only if they preserve that same cooperating-writer boundary. Preserve cancellation/progress, legacy complete files, folders, stable IDs, collision disambiguation and actionable per-file failures. |
| Next urgent: orchestrator, credential/deployment admission, ROOT-F001–003 | settings PATCH/load → `SettingsStore`/credential protocol and `WorkspaceService` → credential preimages, disk/memory settings and configured-capability consumers | Existing rollback tests start with empty credentials. Diagnose populated-key/alias/mutate-then-raise restoration with the injected protocol; separately distinguish mutable settings mode/root from process-configured policy at actual consumers. | Credentials need unique-key preimages before mutation, original-error preservation and secret-free restoration failure reporting, without an infallible OS-keyring transaction claim. Deployment repair preserves desktop controls and configured webapp roots; future-v3 auth is not its prerequisite. |
| Dependency blocker: B plus library owner, force/lifetime, B-F001–002/ROOT-F069/A-F007 | T1 manual route and E1 startup/Run admission → physical service worker → same injected library wrapper → public Wetlands remove/provision/start and retained cleanup owner | ISSUE-024 proves matching-generation reuse. The held force plan proposes destructive public removal/reprovision, not atomic generation CAS/rollback; strict-close retry ownership and interrupted terminal waits still need high-impact independent review. T1's manual cancellation oracle does not certify adjacent graph/refresh/thumbnail callers. | Preserve explicit force rebuild and ordinary/E1 reuse, exact recipe/Core guards, unrelated environments, callback attribution, physical admission retention and failed-owner retry. No private deletion, recipe nonce or narrowing to stale-only replacement. T1 remains held pending this dependency decision. |
| Dependent: A plus orchestrator, root incarnation, A-F004/A-F072 | root draft/save wire and nested-session Open → backend mutation admission → accepted graph/storage and generated OpenAPI/client types | Revision CAS and during-validation generation rechecks already protect useful boundaries; source suggests old-caller first admission after same-ID recreation remains indistinguishable. Specify absent legacy versus explicitly stale ownership compatibility before a schema change. | Preserve accepted drafts, independent canvases, owner chains and exact sibling bytes. Consume generated draft types with any contract change; do not turn the type debt alone into an unrelated API rewrite. |
| Independent follow-up: affected client owner, invocation/presentation, ROOT-F016–017/093–094 | dataset retry/refresh, captured dynamic-output propagation and retained-run dialogs → request/attempt publication → their own store/canvas/dialog consumers | Source findings describe obsolete continuations publishing over newer accepted state; root-incarnation wire changes do not settle these distinct client boundaries. Diagnose each with its existing deferred-request fixtures and actual consumer, preserving backend commit and plan-digest defenses. | Keep these as separately bounded client packets when their source/contract prerequisites are clear, without waiting for the root schema decision. Preserve upload progress/concurrency, per-canvas metadata ownership, exact committed operation identity and no replay after ambiguous/committed work; ROOT-F094's managed-run execution remains outside campaign scope. |
| Later bounded: result/scientific owner, B-F043–045/188 and ROOT-F036/080/096 | immutable selected records/clear/read projection and scientific adapters → cache/provenance/table/image/lineage consumers | Separate immediate Clear from authoritative read, absent legacy provenance from corrupt present provenance, and declared scientific meaning from ordinal/shape guesses. Existing exact numerical/cache/readback oracles remain essential. | Prioritize a demonstrated wrong result when one is established; otherwise deepen the specific seam before repair. Preserve retained downstream outputs/history/siblings, explicit row/cardinality contracts and feature-specific prerequisites. |
| Cross-cutting: orchestrator with reserved independent reviewer, suite/specification cost | existing selectors/fixtures/runner and authoritative specs → real gesture/storage/worker claims, completion scopes and retained evidence | Empty-search, copied shortcut harness and missing navigation witnesses are assertion debts; setup similarity does not establish redundant coverage or measured savings. | Improve affected assertions in place and consolidate shared controlled helpers only after acquisition/timeout/drain ownership is clear. Keep mock/client, actual storage, real GUI and real worker oracles distinct; no new runner or global parallelization. |

### Three possible independent first packets

These are bounded diagnosis/contract packets, not three simultaneous implementation assignments.
The orchestrator may assign A and B in isolated task worktrees while owning the dataset decision and shared records, with one fresh specialist reserved for consequential plan review.
Before assigning writable or executable work, recheck platform/library/held-worktree hashes, installed editable locations/lock metadata, active processes and each packet's affected contracts; the M1 ledger remains accepted history, while changed inputs reopen only their affected claims.
Use current-source tests or selectively port reviewed diagnostics to fresh aligned worktrees; preserve original WIP, red logs and untouched held files rather than merge stale worktrees wholesale.

| Packet | First deliverable and distinguishing evidence | Release, completion and dependencies |
| --- | --- | --- |
| A: carried executable/resource authority | A bounded owner/caller map and proposed authority repair, reusing held `test_portable_version_binding_uses_public_loaded_class_and_engine` and parameterized `test_owned_processing_resources_follow_captured_source_not_catalog` in the tool-binding worktree; retain recursive requirements/rebind and resource-floor controls. Verify the preserved red selectors and bytes before adding a missing distinction. | Independent review must settle public load/materialization, bound engine/resource behavior, explicit DataFrame override refusal, A-F003 locality/availability and serialize-only consumers. Implementation uses exact focused owner tests, then directly selects the documented `full` completion for package-loading changes; `full` subsumes `check app`, so these commands are not stacked. Changed GUI contracts need exact Chromium/Firefox evidence, not an unconditional readiness replay. |
| B: selected uninstall target confinement | Trace package/version admission through the real injected installer and router. Extend the existing single/all-version temporary-target tests only for absent distinctions: absolute/traversal/symlink refusal before the recording removal seam, valid sibling isolation, and unchanged refresh/error behavior. No destructive live-target experiment. | Independently review destructive admission and its error/deployment contract before repair. Use backend focused selectors and `check backend` if confined to backend admission; use `check app` if API/schema/runtime/dependency changes broaden the packet. Coordinate with A before touching shared tools routes, installer/loader or normative documents. Force-Recreate is B's next separate decision, not an incidental addition. |
| Orchestrator: staged dataset publication and shared catalog admission | Reconcile the held C3 plan/review with actual current store/router bytes and ISSUE-023's exact `test_streaming_upload_is_not_published_by_a_concurrent_store` and `test_spooled_upload_is_hidden_from_concurrent_dataset_listing`. Resolve commit/cleanup ownership, write-all/zero-progress behavior, cooperating-writer serialization, supported crash recovery and per-file transport failures. Name a separate safe deletion diagnostic for catalog membership/CAS if required by the shared boundary. | Independent high-impact plan review precedes publication/deletion code. No recognized final placeholder, deletion after successful/ambiguous commit, or universal external-writer/power-loss guarantee. After repair run the exact distinguishing tests once, then `check app`; add exact browser evidence only for affected panel behavior. Original-filename fidelity remains separate unless the decided publication contract necessarily changes it. |

These packets can prepare independently because they own different services; file/specification overlap and shared library authority still require explicit coordination before edits.
Only the orchestrator grants the browser or real-provisioning runtime token, so those phases remain sequential even when lower-level preparation overlaps.
If the dataset decision blocks, the orchestrator can prepare the credential rollback packet independently; an unresolved destructive/publication contract must not be bypassed by labelling its implementation routine.
Routine fixes may proceed with their assigned worker once cause, intended contract, negative/recovery oracles and smallest applicable completion scope are clear; high-impact authority, destructive, credential and physical-lifetime changes require the reserved review first.
After this retrospective converges and a packet's independent plan review resolves its release conditions, proceed directly with that authorized bounded implementation and validation; no second global reconnaissance or user confirmation is required by this queue.
The next short queue is populated-key rollback and configured-policy admission, public force-Recreate/T1, then root-incarnation/result decisions and independently runnable client invocation packets; a newly reproduced security/data-loss/wrong-result failure can reorder it explicitly.
I1's reviewed captured-guidance changes remain held for current-source and completion-phase reconciliation; resume them as a separate bounded packet when first-priority owners are established, without claiming their unrun stress/smoke/integration phases passed.
Accepted N1/E1 remain integrated, while wrapper/resource/identity changes rerun only affected consumers and justify reuse of other passing evidence.
ISSUE-022 remains unattributed; repair it only after recurrence identifies the first missing command/API/presentation boundary.

### Evidence, suite, specification and retirement decisions

Record source/fixture/dependency/runtime equivalence per retained phase, exact selectors/projects, tested and integrated revisions, durations, artifacts and failed/skipped/flaky/unrun portions.
Controlled causal reds need no five-repeat ritual; use five repeats only for an actual timing/race defect, retain late-failure successful phases, and do not stack quick immediately before a subsuming completion check.
Use existing focused/scoped lanes; ordinary runtime/API changes use `check app`, broad architecture/runner changes use `check all`, and broad browser infrastructure uses `check browser-all`.
Published compatibility, real required worker/external and final native M5 evidence remain separate obligations; campaign execution exclusions do not authorize removing delivered distributed/parallel capabilities or their regressions.
Use retained timings to identify one concrete fixture/setup or assertion improvement per affected repair family, collect only missing comparable measurements, and claim cost savings only after an equivalent before/after measurement.
No deletion of tests or weaker assertions follows from the review count; deterministic ownership failures and actual end-to-end witnesses often protect different contracts.

Update every affected normative specification and Context in each behavior/contract repair, resolving misleading examples/status against actual intent and distinguishing tests rather than silently replacing requirements with current defects.
Prefer references to the existing canonical authority and removal of genuinely contradictory duplicate prose; preserve recursive sources, explicit dependency install-all, selected/parallel execution, force rebuild, exports and viewer favorites.
This retrospective itself changes campaign sequencing only, not product/library contracts.
Consolidate routine checkpoint/evidence updates under `check campaign`; this substantial planning milestone requires `check docs` once after independent review, with its exact revision/diff and duration recorded separately from application evidence.

Every task packet names its integration and cleanup owner at creation.
At clean source-equivalent integration preserve actionable red/completion artifacts, retire task servers/workers physically, remove only exclusive rebuildable dependency/runtime/build stores, move source to Trash with `mv`, prune and delete only the merged task branch as the plan and AGENTS require.
Held/dirty/unmerged work, user data, credentials and managed/shared/adopted environments retain their owners and lifecycle rules; report removed versus merely trashed bytes separately.
The next strategic retrospective is after several coherent priority repairs or a major architectural integration, before M3 systematic expansion; exceptional public-contract/permission/lifetime blockers get targeted review while unrelated safe work continues.
M2 is complete only with validated integrated repairs or explicit contract blockers, measured justified suite changes and consistent affected specs; this queue alone does not close M2 or change the historical 276/500 dashboard.

The retrospective converged after three fresh dedicated review passes; the third found no meaningful remaining change within scope.
`env UV_OFFLINE=1 scripts/test check docs` passed (exit 0; runner 4s, measured 3.96s) at `b6dabfa34371218228d2d13729ee86c8a991f1c2` plus the two reviewed campaign-document changes, captured before validation in `/private/tmp/bioimageflow-m2-retrospective/source-before-doc-check.json` (SHA-256 `c01c428ff465c7066ba395f677638e923a01ab50eba32f138741a72eebfabe34`); the log is `/private/tmp/bioimageflow-m2-retrospective/docs-check.log`.
This records documentation acceptance only, supplies no product/browser/worker/native evidence, and leaves M2 open.

### D1 compatibility dataset deletion — accepted, 2026-10-01

D1 (ROOT-F008) changes exact catalog deletion authority and lexical entry ownership at main `878cfbae1ce09c03c1efbde3b1790c4e24f32fe3` plus five reviewed source/test/specification/Context files; the product bytes remain fixed during completion validation.
The independent applied review accepted catalog ID/stored-name lookup under the writer transaction, contained-link entry deletion, unchanged 404/400/204 behavior, sibling/catalog byte preservation and listed legacy-file deletion; filesystem unlink and SQLite commit still have no atomic rollback guarantee.
The exact disposable unmanaged-entry selector `env UV_OFFLINE=1 scripts/test focus backend 'tests/test_services/test_dataset_store.py::test_delete_unknown_raises[unmanaged]'` first failed with DID NOT RAISE (exit 1; runner 4 s, measured 4.59 s), then passed after correction (exit 0; 1 passed; runner 3 s, measured 3.10 s).
`env UV_OFFLINE=1 scripts/test focus backend tests/test_services/test_dataset_store.py tests/test_routers/test_datasets.py` passed all 59 owner tests (exit 0; runner 15 s, measured 14.93 s); exact five-file hashes and command evidence are retained in `/private/tmp/bioimageflow-m2-retrospective/dataset-d1-source-and-evidence.json`.
`env UV_OFFLINE=1 scripts/test check app` passed at that exact five-file source snapshot (exit 0; runner 348 s, measured 348.55 s): lint/type/build, 1,845 backend tests, 7 logging-order controls, 1,337 frontend tests and 18 critical Chromium tests; 10 external backend tests were intentionally deselected, with no selected skip or flake reported.
The current runtime rule conservatively requires this lane for the destructive API admission change despite unchanged wire shapes; it subsumes a separate backend completion check.
`env UV_OFFLINE=1 scripts/test check docs` passed (exit 0; runner 5 s, measured 4.75 s), with warning-clean Sphinx and campaign validation; result-only checkpoint/findings prose and generated ledger metadata are recorded afterward without repeating the subsumed documentation phases.
Logs are `/private/tmp/bioimageflow-m2-retrospective/dataset-d1-app-check.log` and `dataset-d1-docs-check.log`; the independent source-equivalence/applied review is `dataset-d1-applied-review.md` and its five-file snapshot.
Full, non-critical Chromium, Firefox, external/published compatibility and native acceptance were not selected or credited for D1.
Retain the completion lane's observed cost for later proportionate-boundary review, without claiming a measured suite optimization or weakening this acceptance check.
D2 upload publication/shared catalog admission remains held for its separate physical commit/cleanup and concurrency decision; its preserved historical reds and source findings are not credited by D1.

### B destructive package admission — integrated and retired, 2026-10-02

B-F168 is repaired within its reviewed boundary: uninstall admits exact contained stored selectors independently of imports/registry membership and rechecks captured root/package/target identity before physical removal or failed-trash fallback.
Omitted version still removes the whole selected package, explicit empty version is refused, configured-root links and exact stored version spelling remain supported, and sibling packages/versions and Wetlands environments retain their owners.
Task commit `4d0e1403ab84763cbce76d7e1011a5cb8c67f0b0` was integrated as `670200c3596d429c705f7dc473a91f25f6345e69`; ancestry-record merge `1ca3ff26571d5f341ce67ac8097cd7a6b9fb01e4` makes the original task HEAD a merged ancestor without another product change.
The exact disposable absolute-version refusal failed before the fix without performing deletion, then passed; the later directory-redirection selector likewise failed safely and passed after the reviewed ancestry correction.
The original `scripts/test check app` passed in 361 s at base `878cfbae1ce09c03c1efbde3b1790c4e24f32fe3` plus the original five-file snapshot: 1,861 backend tests, 7 logging-order controls, 1,337 frontend units and 18 critical Chromium tests, with 10 external backend tests intentionally deselected.
`scripts/test check docs` passed in 7 s at that original snapshot, with campaign validation and warning-clean Sphinx.
The late resolved-ancestry correction changed only the installer and its service tests; corrected `scripts/test check backend` passed in 191 s on the exact bytes committed as `4d0e140`: 1,863 backend tests, 10 external tests intentionally deselected and 7 logging-order controls; corrected owner checks passed all 119 tests in 18 s.
Independent review accepted retaining the original unchanged frontend lint/type/unit/build, critical Chromium and documentation phases using exact source/fixture/lock/runtime equivalence; the original app invocation is not a same-source final app pass for the corrected installer.
Exact hashes, red/fixed commands, phase logs and equivalence evidence remain in `/private/tmp/bioimageflow-uninstall-worker-report.md` and `/private/tmp/bioimageflow-m2-retrospective/package-uninstall-ancestry-applied-review.md`; these B results do not validate the separate uncommitted D2 source.
Full, published/external compatibility, broad cross-browser, OS Trash/native Windows junction and packaged desktop acceptance were not run or credited; raw-task physical cancellation and arbitrary external-filesystem races remain separate obligations.

The delegated retirement owner verified clean tracked/untracked state, merged HEAD, preserved actionable receipts and no process paths/commands referencing `.worktrees/campaign-package-uninstall-current` before retirement.
Only its exclusive `backend/.venv`, `frontend/node_modules`, `frontend/dist` and `docs/_build` were deleted: 630,939,648 allocated bytes of file references, with removal taking 580.77 s; shared blocks mean this is not a claim of equal recovered volume space.
Residual source, ignored caches and test evidence occupy 21,536,768 allocated bytes and were moved with `mv` to `/Users/amasson/.Trash/bioimageflow-uninstall-completed-20261002-113043-e1e913ce`, which retains those bytes.
Observed volume-free space increased by 104,169,472 bytes over the interval, without attributing concurrent writes or APFS/shared-block effects to this cleanup alone.
`git worktree prune` succeeded, only merged branch `campaign/package-uninstall-current` was deleted, and registered platform worktrees decreased from 20 to 19; all held/dirty/unmerged trees, main dependencies/runtime, user data and managed/shared/adopted environments remain preserved.
The complete retirement receipt is `/private/tmp/bioimageflow-uninstall-cleanup-receipt.json`, with filtered process and pre-deletion allocation companions; runtime/browser metadata was preserved before removal.
`env UV_OFFLINE=1 scripts/test check campaign` passed for this routine B integration/retirement checkpoint at `1ca3ff26571d5f341ce67ac8097cd7a6b9fb01e4` plus this progress-only documentation delta (exit 0; runner 2 s, measured 2.28 s; dashboard and 68 active local links); the log is `/private/tmp/bioimageflow-uninstall-cleanup-campaign-check.log`, and no product/Sphinx phase was rerun or credited by this checkpoint.

## October 2 strategic checkpoint and first-wave delivery

Independent strategic review confirms a real architecture-driven campaign and recommends closing bounded packets before accumulating more integration state.
M1's accepted historical scope remains 1,799 inputs: 1,649 reviewed and 150 classified; the 573 recorded candidates are qualified findings, not 573 proved bugs or mandatory rewrites.
The frozen platform set remains 740 inputs.
The integrated materialized-resource helper is a separately named current M2 source addition; the current ledger has 1,800 entries (1,650 reviewed / 150 classified), without changing the frozen M1 history.

| Packet | Current state and next gate |
| --- | --- |
| D1 exact dataset deletion; B confined uninstall | Integrated; bounded source/results and B retirement recorded above |
| A executable/resource authority; D2 staged dataset publication | Independently accepted scoped phase assembly; separate commits integrated by ordinary merge `df675a9`, exact combined source proved |
| C imported-layout fixture | Independently accepted exact Chromium/Firefox controls and lint; separate fixture commit `56db73d` integrated |
| Startup/Browse selection ownership | Existing-component deterministic RED preserved outside first-wave delivery; next bounded product/spec repair maps every actual presentation writer |
| Credentials, configured deployment policy, public force-Recreate/lifetime | Urgent next owner-contract packets before M3 expansion; force-Recreate is unresolved across public owners, not assigned to Wetlands by inference |
| Suite optimization | No measured suite-wide speedup; evaluate one costed artifact/fixture candidate after architecture repair, retaining distinct oracles |
| Published compatibility and native desktop | Release/pin/wheel prerequisites remain open; desktop only at final M5 |

### First-wave completion evidence and open certification

The combined `scripts/test full` at base `670200c3596d429c705f7dc473a91f25f6345e69` plus the frozen A/D2 source manifest `e4e4f199489bd03e857bd471d2bc19a0176a49135b2b24555a1375112f097edc` FAILED in 1,069 s.
Its successful unchanged phases are retained: backend 1,914 tests with branch coverage, frontend 1,337 units with branch coverage, 7 logging-order controls, lint/types/build, published common-tools 0.2.1 compatibility and real worker/stale-generation/failure-retry controls.
This used frozen editable BioImageFlow/Core sources and published common-tools; it is not certification of future published BioImageFlow/Core or CommonTools fixes.
Original Chromium stopped after 61 passes at the imported-layout failure; original Firefox failed initial mount before its remaining 123 cases, with its original cause still unexplained.
The later Firefox completion and both browser tails also FAILED and remain recorded; isolated single/five timing passes do not erase those failures or establish the original request order.

C's frozen manifest is `75239bcc0148b5ccea1a8ff5f5e267e1e8ac7521df1b07366334a9e05d3d0c48`.
The five missing native critical Chromium selectors (`workflow-crud.spec.ts:87,:114,:208,:243` and `workflow-interface.spec.ts:396`) passed through `scripts/test focus e2e --project=chromium` with those exact selectors and `--trace=on`: runner 33 s, measured 32.979 s, no skipped/unrun cases.
Their before/after source manifest is `38a07a15b99ac177e8b86074f0ee38349b7c77266bd6df80bb249ec5e70aa98b`; its sole product-snapshot difference from C is the separately held jsdom selection RED, with E2E product/config/locks/library/metadata unchanged.
The native critical collection is now 18/18 unique actual successes: 13 retained plus these five; independent review accepted the bounded scoped phase assembly and source applicability.
Current conservative unique browser coverage is 74/124 Chromium and 73/124 Firefox, with 50/51 remaining gaps; original tails' 55/51 unrun counts remain historical outcomes.
Repeats contribute stability evidence, not extra unique cases.
The completion proof is `/private/tmp/bioimageflow-m2-retrospective/firstwave-critical-five-completion-proof.json`; independent acceptance is `independent-first-wave-assembly-and-strategy-acceptance.md` beside it, with source/identity/phase logs and original failures.

The integration owner and peer must verify each phase's source, fixture, generated artifacts, editable library, installed dependency and runtime applicability before accepting the scoped assembly.
This satisfies only the reviewed first-wave task scope, not M2 completion or a monolithic app/full PASS.
Preserve the selection RED patch independently; stage D2's exact six-file patch first, then A-only shared-file residuals, then C-only fixture changes, each separately reviewable.
Snapshot and stash only main's six owned D2 paths before cherry-picking accepted commits; preserve the B cleanup and verified gh-release documentation commits and all recovery evidence.
Verify final combined source equivalence before updating accepted source ledger rows, then retire only the committed, clean, merged, physically inactive task worktree and exclusive rebuildable stores.

### Next sequence and durable gates

Repair selection through the public presentation owners and distinguishing deferred-startup/explicit-intent tests, retaining normal Create/Open/Save As/Duplicate/Import and root/nested activation.
A frontend ownership change invalidates affected frontend/browser evidence; preserve backend/external phases only with equivalence and run the exact failures before broader affected completion.
Then address credential rollback, configured policy, force-Recreate and physical lifetime in their actual owning repositories before expanding coverage.
Before published certification, reconcile editable library baseline `dff04e3` with upstream `7c718a0`, address the unpublished BioImageFlow parallel-name fix `9ae7b2c` and CommonTools LabelOverlaps fix `fd6d53e`, release affected packages through the [verified gh flow](platform-test-plan.md#dependency-pypi-releases-with-gh), update platform and worker Core pins, and validate actual published wheels.
The platform DataFrame override guard does not close the upstream materialization defect; prior BioImageFlow 0.8.6 and Wetlands 2.4.2 publications are not campaign releases.
No publication is performed automatically by this campaign update.
Use targeted development regressions and owner checks, broader integration/docs/browser at coherent milestones, and a low-frequency strategic review after accepted repair integration or material scope change.
The effort split in the plan is a heuristic; no measured allocation or suite optimization is claimed.

### First-wave integration result — October 2

Independent scoped acceptance and one `env UV_OFFLINE=1 scripts/test check docs` PASS (runner 3 s, measured 3.538 s, exit 0) accepted the strategic documentation at `40c62b8` plus its three-file delta, committed as `23882ec`.
D2 is task commit `be90dd5`; A is `afb1b3a`; C is `56db73d`; ordinary merge `df675a9b953d1b639dfff55f731751f48394adec` preserves their ancestry and the B cleanup/verified release-instruction commits.
All 742 accepted C manifest entries match integrated main except the three accepted campaign documents; the editable library remains clean at `dff04e3`, and all five recorded installed dependency metadata files remain unchanged in the acceptance environment.
Receipts are `firstwave-premerge-source-equivalence.json` and `firstwave-main-source-equivalence.json` in `/private/tmp/bioimageflow-m2-retrospective`.
Main's exact six D2 paths were preserved as patch SHA-256 `724ef000a55bd7fae4d6bae4fd09ab0fb5e940f5dcf77fd76ef05bb7a1dbdb55` and recovery stash `79e7619494ffb31499cf21cac44aa9fcec9bc39a`; the prior alignment stash remains intact.
The held selection RED remains independently preserved as `napari-selection-unit-red.patch`, SHA-256 `e8629508b50be4c283d8effad7025e02ad35718f1c0a191cb16f66b8e39f50d6`, with its original file and failure log, excluded from first-wave commits.

Five live Wetlands checkout inputs have changed beyond the frozen review: `CHANGELOG.md`, `RELEASING.md`, `pyproject.toml`, `src/wetlands/protocol.py` and `uv.lock`.
Their M1 rows and historical judgments remain frozen; independent current five-path source review at clean Wetlands `3ee2ffe1da7b6f1cfe97a8d88e6de67797d031d1` is recorded separately in `independent-wetlands-five-path-drift-review.md`.
The live revision/status/exact hashes are recorded in `wetlands-current-drift-boundary.json`; this does not retroactively invalidate M1 or the unchanged installed-package first-wave evidence.
The current M2 ledger checker binds platform source to accepted `df675a9`, preserves frozen membership and separately inventories the new helper; the five Wetlands drift hashes remain historical comparisons with their separate dated source-delta review.
That delta is release documentation and a consistent package/runtime/lock 2.4.2→2.4.3 bump, with protocol integers unchanged; published 2.4.3 wheel/host-worker compatibility has not been executed and requires compatible pins and recreated persistent workers.
Full/browser/published/native gates and the 50/51 browser gaps remain open after this integration.

## Selection and credential repair checkpoint — October 2

The bounded selection packet and ROOT-F001 credential rollback are independently accepted with qualified completion on `3fb17ac` plus their exact 15-path source union.
The selection-only 11-path patch is SHA-256 `9d49802160857f6a645d55a7e7943f046418b97f76fc5219dd0c163697b528bc`; the sequential credential six-path patch is `70e0d56581aadab59fe22079d56495832378c8871c0a006bac4b89a796dde726`.
The overlapping Context/v1 ownership is proved by applying selection first and credential second in disposable scratch files; all 15 hashes match the accepted final source in `/private/tmp/bioimageflow-m2-credential-rollback/selection-credential-final-union-proof.json`.
The existing per-file ledger remains explicitly bound to first-wave `df675a9`; this current accepted-source manifest is separate and does not rewrite the frozen M1 history or rebind all 1,800 rows.

Credential controls distinguish populated-key loss, mutate-then-raise and preimage-read failure before the repair (one FAIL and two FAIL), then the same three selectors pass; measured commands took 5.833 s, 21.910 s and 42.711 s respectively.
Focused SettingsStore/settings-route/credential owners pass all 71 tests in 20 s (measured 19.295 s), with no skipped cases or live keyring/account access.
The bounded contract captures all distinct planned password-write preimages before attempts, restores each attempted key once including mutate-then-raise, preserves the original BaseException and continues best-effort provider restoration with a fixed count-only warning.
Shared aliases retain ordered last-explicit-password behavior and credentials until their last referencing record is removed; known pre-replacement failure preserves disk/memory independently of provider restoration success.
No guarantee covers accepted replacement, acknowledgement ambiguity, process termination, noncooperating writers or native keyring atomicity.

The one `env UV_OFFLINE=1 scripts/test check app` invocation FAILED in 289 s; backend had 1,912 PASS, one subprocess-boundary failure and 10 external tests intentionally deselected, while frontend units passed all 1,350 tests.
The unchanged exact Napari probe selector subsequently passed in 3 s (measured 2.545 s, pytest 0.11 s); backend acceptance is 1,912 retained plus this recovered case, not a successful original backend invocation.
The original concurrent-run five-second output-probe timeout remains unresolved; isolated recovery does not establish its startup/read/termination cause.
Two selection test-static defects were corrected; their two owner controls passed in 4 s with 38 title-filtered skips, and frontend lint/type recovery passed with durations not captured.
Retained backend lint (PASS, 10 s), frontend production build (PASS, 42 s), and all 1,350 frontend units in 134 files (zero skipped), plus the corrected exact Chromium witness (one PASS, 11 s), logging-order controls (seven PASS, 3 s), and canonical critical Chromium cases (18 PASS, 82 s) complete the independently accepted scoped phase assembly.
The final Firefox witness/smoke is externally blocked by an independently observed Mach subprocess/page-admission crash before application setup; it supplies no new cross-browser completion credit and is not retried without a changed admission environment.
Original app/full/browser failures, contextual probe uncertainty, historical coverage/gaps, published compatibility and native final-M5 gates remain open; this is qualified repair delivery, not monolithic app/full/browser certification.
Phase logs and final source/static recovery manifests remain in `/private/tmp/bioimageflow-m2-retrospective/` and the credential receipt directory.

The clean merged first-wave acceptance tree was retired after preserving the held RED/alignment evidence and proving no consumers: only exclusive `.venv`, `node_modules` and production build stores were removed, totaling 616,853,504 allocated file-reference bytes.
Residual source/caches/evidence retain 140,771,328 allocated file-reference bytes in `/Users/amasson/.Trash/bioimageflow-firstwave-completed-20261002-130401-85dc7bb5`; prune and merged-branch deletion completed, with registered worktrees reduced from 19 to 18.
Observed volume-free space changed by −219,131,904 bytes during concurrent activity; no recovered-volume attribution is made from file allocations, shared/APFS blocks or that observation.
The exact retirement receipts are `firstwave-retirement-before.json`, `firstwave-retirement-removal.json` and `firstwave-retirement-final.json` in the retrospective directory; held/shared/adopted/user environments and recovery stashes remain preserved.
Configured-policy ROOT-F002/003 is the next bounded owner packet; public force-Recreate/lifetime, suite cost measurement and published dependency reconciliation remain separate obligations.

The one consolidated `scripts/test check docs` passed in 4 s (exit 0; campaign dashboard/links and warning-clean Sphinx) at `3fb17ac` plus the accepted packet/specification/result-record bytes; the exact log is `selection-credential-final-docs.log` in the retrospective directory.
Selection is task commit `40958bffa6a0daf80390e679f3eb52d767bbd716`; credential rollback is `3f4a20765eced75e878902b02336caac70115291`, preserving exact sequential shared-file ownership.

## Configured-policy repair checkpoint — October 2

ROOT-F002/003 are repaired within process-mode authority and generic webapp administrator-root refusal on `e5a3d0c` plus the frozen ten-path policy source/specification manifest `policy-app-frozen-source.json` in `/private/tmp/bioimageflow-m2-configured-policy/`.
Twelve distinguishing controls reproduced the owner/load/typed-write/injected-mismatch/fallback-consumer/router defects before source repair and now pass; two initial unloaded-root fixtures failed at `/data` setup before correction and receive no causal policy credit.
The exact GREEN has pytest 1.58 s and measured 9.696 s but runner output 412 s; that unexplained discrepancy is preserved, not a measured optimization or diagnosed clock shift.
Focused owners pass all 131 controls in 22 s (measured 22.131 s, pytest 17.41 s, no skipped cases), preserving desktop workspace editing, legitimate web preferences, live development/file-only unsafe behavior and captured new-workflow scheduling.
Actual frontend callers send sparse preference fields, so no frontend adaptation or duplicate UI regression was added.

The one `env UV_OFFLINE=1 scripts/test check app` FAILED in 177 s (measured 177.616 s): backend 1,923 PASS, two localhost-bind failures and ten external tests intentionally deselected; backend lint passed in 1 s and frontend lint/types/build in 9/1/6 s, with all 1,350 units in 134 files passing in 25 s and zero skipped.
The app was mistakenly run in the restricted sandbox; both failed held-fixture controls reached EPERM at `socket.create_server(127.0.0.1:0)` before threaded/current-PID worker admission.
The same two unchanged selectors passed with required local-loopback escalation in 2 s (measured 2.780 s, pytest 0.16 s); these are fixture/thread controls, not spawned Wetlands worker certification.
Previously unrun logging-order controls passed all seven in 4 s (measured 4.007 s); `env UV_OFFLINE=1 scripts/test check browser-smoke` passed all 18 native critical Chromium cases in 80 s (measured 79.739 s), with required local-server/browser escalation.
The qualified assembly is 1,923 retained backend successes plus two recovered cases and all app phase obligations; the original app invocation remains FAIL, and no app/full/browser-all repeat was run.
All ten source/specification hashes remained unchanged; six lock/config files, five installed dependency metadata files and clean editable library `dff04e3` match the preceding accepted main baseline, recorded in `policy-source-dependency-applicability.json`.
Native titles distinguish 18 cases across 17 source locations because the viewport location has separate small/large parameters; `policy-native-critical-runtime-proof.json` records these exact identities and unchanged fixture sources.
The final Firefox gate remains externally blocked before application admission, with no retries or new Firefox credit; original full/browser failures, published compatibility and native final-M5 gates remain open.
The existing per-file ledger stays bound to first-wave `df675a9`; this current dated policy manifest remains separate without rewriting frozen M1 membership/history or the 1,800 rows.

For this policy packet, no new environment or worktree was created: private main dependencies were reused, browser-owned scratch cleanup follows the runner's exit trap, actionable logs/last-run metadata are preserved outside scratch, and the known completed server/runner PIDs and localhost listeners are absent.
No new recovered-storage claim is made; the preceding first-wave retirement measurements remain the checkpoint above.
The initial/distributed service graph's pre-load workspace-root capture, ROOT-F022 inert settings metadata and independent-writer ROOT-F004 remain separate open seams.
The next force/lifetime packet is library-owned explicit-force semantics rather than an inferred Wetlands reuse defect: preserve/reconcile the observed four-ahead/two-behind library histories and dirty held library/T1 trees before bounded source assembly, then strict selected-owner close → public managed removal → provision with replacement false → worker start → successful cache publication.
False matching warm reuse and established best-effort stop remain supported; close failure retains the retry owner, physical cancellation retains admission until completion, and no compound generation CAS or availability rollback is promised.
Library-only preservation/reconciliation and repair are authorized for that next packet; its conditional readiness receipts in the retrospective directory are not implementation, runtime, release or published-pin acceptance.

The one consolidated `env UV_OFFLINE=1 scripts/test check docs` passed in 5 s (measured 4.562 s, Sphinx phase 4 s, exit 0) at `e5a3d0c` plus the reviewed thirteen-path source/specification/record snapshot; `policy-check-docs.log` and `policy-docs-frozen-source.json` retain the exact gate.
Policy source, existing-family controls and affected specifications are task commit `07d02a90055f17a5c95711cc339b4120db84c38c`; the separate campaign records preserve the qualified limits without changing accepted product bytes.

## Common-task performance investigation — October 2

The read-only batch at clean `dc6e976e2af7a512800a323ad51d1f988bec817a` reused the main private environment and production frontend build with disposable synthetic data; source, dependencies and developer state remained unchanged.
The actual ASGI routes used 20/100 current-schema empty workflows with five folders and zero sources, and 100/1,000 managed files of 16 bytes with no folders; five sequential warm request medians were draft GET 163.508/682.175 ms, workflow tree 33.878/150.038 ms and dataset list 11.782/61.435 ms.
The first call is route-first rather than process/OS-cold; folder calls follow catalog initialization and draft calls follow saved reads, while the retained initial unregistered-filename dataset fixture supplies only scan evidence.
The production headless Chromium batch used 100 flat empty workflows, 1,000 managed files and six fixture tools, real platform lifespan with offline package metadata, no injected response delays and no native desktop.
Server/build/seeding and search-reset work are outside gesture timers; trace/snapshot recording and Playwright gesture/oracle overhead remain included; graph tasks require the matching post-application canvas event, visible active canvas and two animation frames, and search tasks require the correct painted row.

| Measured task | Actual baseline |
| --- | --- |
| First browser navigation to accepted graph/paint | 3,483.916 ms, one observation |
| Warm reload to accepted graph/paint | median 2,773.944 ms, five observations (2,615–3,444 ms) |
| Fresh Browse Open | median 829.097 ms, five distinct targets (812–871 ms) |
| Workflow search, 100 flat rows | median 41.315 ms, five observations |
| Dataset search, 1,000 flat rows | median 171.034 ms, five observations (159–183 ms) |

Every measured startup sends two workflow-tree GETs with identical 47,965-byte responses; this proves redundant work rather than twice the user latency.
Synthesized-draft GET performs eight saved reads and eleven workspace format scans; sharing one saved capture within each existing lock would remove five repeated reads/scans while retaining six format-plan evaluations and all fresh authority checks.
The nonnested scan span supports a conditional equal-pass opportunity of about 64/298 ms at 20/100 workflows; these are allocation-model estimates, not measured improvements or guaranteed speedups, and nested read spans are not added.
Dataset list reconciles twice per request; at 1,000 managed files the total reconciliation span is 28.082 ms, suggesting roughly 14 ms if one equally costly pass is removed while preserving fresh external-file visibility.
Tool environment discovery repeats per tool, including shared names; its latency and folder-index, dynamic-schema, results-page, dense/source graph, process startup and cold/warm worker gains remain unmeasured.

The authorized gesture batch passed in measured 35.180 s with 21 tasks and zero page errors; a preceding fixture-only admission failure consumed SettingsStore before load, yielded no gesture result and is retained separately after exact harness correction.
Exact harnesses, request starts/body sizes, traces, source/build manifests and cleanup proof remain in `/private/tmp/bioimageflow-m2-performance/`; the benchmark is investigation evidence, not a new product completion or full/browser certification.
Only disposable synthetic runtime was retired, with its server PID/listener independently absent; the 57,667,584-byte stat-based file-reference enumeration can follow links and is not exclusive allocation or recovered-volume evidence.
No existing environment/worktree cleanup is claimed.
The frozen M1/first-wave ledger and prior qualified acceptance remain unchanged; independent review precedes implementation, then the same request batch measures actual before/after gains.

### Draft snapshot reuse: observed repair result — October 2

The reviewed internal helper captures one saved `WorkflowFile` per existing locked synthesis phase; graph, base hash and timestamp derive from that capture, which does not retain current authority after lock release.
All later saved/draft, identity-generation and storage checks, whole-workspace format admission, actual compilation/source binding and agent-context updates remain; no cross-request cache, API/schema, dependency or frontend change was made.
The public graph/hash/mtime/purity/no-persistence control failed with eight reads instead of three before repair, while both held-validation saved/draft authority controls already passed; the same three controls then passed in 3 s (measured 2.731 s, pytest 0.58 s).
All 38 targeted public-draft, CAS/reset, format/migration, validation, compile-generation/storage, Clear/restart and source-binding owners passed in 8 s (measured 8.343 s, pytest 6.12 s), including exact durable draft byte preservation.

The unchanged request harness verifies eight→three saved reads and eleven→six format scans; five warm draft medians at 20/100 workflows changed 163.508→110.869 ms and 682.175→449.708 ms.
The same source-pinned production build, real isolated app, 100 empty workflows/1,000 managed 16-byte files and matching graph/paint oracle measured fresh Browse Open 829.097→587.439 ms (five distinct targets per cohort): an observed 241.658 ms/~29% reduction in this fixture, compared with the prior conditional 298 ms model.
Post-repair headless batch passed in measured 33.058 s with 21 tasks and zero page errors, against the original 35.180 s investigation batch; total harness duration is not a user-task latency.
Warm startup medians 2,773.944→2,731.356 ms have overlapping broad ranges; workflow search 41.315→42.122 ms and dataset search 171.034→168.249 ms provide no established improvement.
Unchanged tree and saved-route timing drift also demonstrates machine/batch variability; this sequential synthetic comparison is not a randomized benchmark or universal speedup guarantee.
Before/after artifacts and exact seven-path accepted-source delta are preserved in `draft-performance-before-after-comparison.json` and `draft-performance-after-frozen-source.json`, with immutable `.before` route/headless/trace/build records in the performance receipt directory.
Both production cohorts retired their owned synthetic roots and server PIDs/listeners; existing main dependencies remain in place.
Their pre-retirement enumeration reports 57,667,584 stat-based file-reference bytes per cohort, but follows links and does not establish exclusive allocation or recovered-volume bytes.
The next independently bounded frontend packet is pending-only workflow-tree singleflight with exact freshness epochs, explicit post-mutation refresh, stale-response fences and retry semantics; tool-catalog epochs and broader caches remain separate.

The documented `env UV_OFFLINE=1 scripts/test check backend` passed in 135 s (measured 135.007 s, exit 0): 1,928 tests passed, 10 external cases were intentionally deselected, and seven logging-order controls passed; lint passed.
The frozen source is `dc6e976` plus the exact seven-path manifest, and all six lock/configuration files, five installed dependency metadata files and clean editable BioImageFlow `dff04e3` remain unchanged.
This scoped backend acceptance adds no full, cross-browser, published-package, worker-provisioning or native final-M5 certification; prior qualified failures and the final Firefox admission block remain recorded.

The one consolidated `env UV_OFFLINE=1 scripts/test check docs` passed in 4 s (measured 4.016 s, Sphinx phase 3 s, exit 0) at `dc6e976` plus the reviewed seven-path source/specification/record snapshot.
A subsequent reviewed plain-prose lane clarification follows the existing smallest-scope rule and adds no link, structure or product-contract change.

The internal source/test/specification repair is task commit `5653800902db35a78dea89e55aaa0660f6322916`; its separate campaign record commit retains the measured workload and certification limits.


### October 2 owning Wetlands completion prerequisite — local checks complete, release gates open

The next force/lifetime gate now fixes the completion boundary in its owning Wetlands repository; repeated terminal exception identity is not accepted as a public completion guarantee.
Installed Wetlands 2.4.2 and live `3ee2ffe1da7b6f1cfe97a8d88e6de67797d031d1` operation source are identical; the currently published GitHub/PyPI version is 2.4.3, verified October 2 before work began.
This extends existing B-F007's notification-before-completion seam without adding a frozen M1 row or changing historical review credit.
The isolated `campaign/wetlands-completion` candidate adds `Operation.wait_for_completion(timeout=None) -> None`, keeps `wait_for()` result/stored-error behavior, isolates callback `BaseException` during live delivery and replay, and refuses incomplete self-wait by the runner or live notification publisher.
A `KeyboardInterrupt` inside callback execution is also isolated; outside waiter interruption still propagates, and completion does not independently certify every thread, PID or deferred reclamation.

Actual manager-returned public operation controls on original source produced nine failures: terminal listener escape stranded the completion wait, progress changed the outcome, replay escaped the caller, and self-wait timed out; the other five failures identified the missing completion-only API.
The original bounded RED log retains one expected unhandled-thread warning; no physical worker/Pixi certification was performed.
The same nine controls then passed with fourteen unrelated controls deselected (pytest 0.34 seconds); final owner coverage, including cleanup-safe fixtures, ordinary/stored interrupt outcomes, completed replay and runner self-wait, passed 51 tests (pytest 0.94 seconds).
Private fast/static dependencies were prepared from the frozen owning lock; main remains at `d8a50bb`, installed platform dependencies and all protected held inputs are unchanged.

The additive API makes 2.5.0 a candidate next minor version under the owning release guide, not a prepared or published release and not a supported dependency floor yet.
Owning fast/static/strict-doc checks, independent applied review and task-only source acceptance precede version preparation; cross-platform/real-Pixi release CI, gh release/PyPI confirmation, library/platform/worker pin alignment and published compatibility remain separate required gates.
No push, tag, release, publication, desktop or Firefox retry is authorized or credited by this packet.


The owning README fast lane `uv run --frozen --no-sync --extra shared-memory pytest -m "not integration and not compat and not manual"` passed: 616 tests, three platform skips and twelve integration/compat/manual deselections (pytest 53.19 seconds; measured command 53.550 seconds).
Two skipped controls require a case-sensitive filesystem and one requires Windows native file IDs.
`uv run --frozen --no-sync ruff check`, `ruff format --check` and `mypy src/wetlands` passed; individual static durations were not captured.
The strict owning docs command `uv run --frozen --python 3.14 --extra docs --no-dev mkdocs build --strict` passed in 142.435 seconds including its private environment replacement; MkDocs build reported 7.20 seconds.
Fast/static checks used private Python 3.13; strict docs replaced only that worktree's `.venv` with frozen Python 3.14 docs dependencies, preserving locks, source and all platform environments.
These results bind `3ee2ffe` plus the six-file `wetlands-completion-applied.json` source manifest; public API candidate acceptance is distinct from release CI, published wheels, pins and worker certification.

The reviewed owning six-file candidate is committed as `0652aa5ede5bed10e189be7db328da0c8d6e419e` on `campaign/wetlands-completion`; it is not merged to the owning release branch or published.
The separate routine platform `scripts/test check campaign` checkpoint check passed in 0.127 seconds against main `d8a50bb` plus this progress append; no platform runtime or full certification was repeated.


### October 2 Wetlands 2.5.0 local candidate — draft PR open, required CI passed

The independently reviewed completion implementation is prepared as a clean 2.5.0 candidate at `f4409ce8b551be6dff62e26ee535ccdd9b47c131` on the local `campaign/wetlands-completion` branch.
Package, worker-runtime and owning lock versions match; execution/management protocols remain 1, and all other 105-package lock content is unchanged.
Three affected handshake/runtime controls passed (pytest 2.22 seconds; command wall duration not separately captured, with Python 3.14 pytest/pluggy SyntaxWarnings retained); unchanged implementation retains its prior 616-test/static/strict-doc evidence.
Clean wheel and sdist build passed in 3.531 seconds and Twine accepted both artifacts; all 29 Python modules plus `py.typed` in the wheel match the candidate source, and sdist required/excluded contents were verified.
Separate source-disabled Python 3.14 installs each passed nine public completion/outcome/callback controls, with eighteen unrelated controls deselected, plus package/worker-version, module-origin and CLI checks; measured installation/control batches were 3.961 seconds for wheel and 13.540 seconds for sdist.
Artifact/source/dependency closure is frozen in `wetlands-250-artifacts-proof.json` and the installed-wheel/sdist receipts; these are local candidate checks, not published package or physical worker acceptance.

The initial release-only reconciliation of the mixed private environment remained silent at an observed 4 minutes 10 seconds before the owned command chain was stopped; its setup boundary is preserved and no cause is attributed.
The same frozen release preparation succeeded in a fresh minimal `.venv-release` (27 locked tools installed in 1.34 seconds), without repeating the unchanged fast suite.
The unused mixed environment and both completed artifact-smoke environments were removed after library runtime stopped; all three paths are absent, while candidate artifacts/source and receipts remain preserved.
Cleanup removed 126,672,838 regular-file reference bytes (147,038,208 stat-block reference bytes) in 137.251 seconds; these are reference counts, not attributed reclaimed allocation.
The observed free-space deltas were /Users/amasson/Travail/bioimageflow-platform: +18,927,616 bytes, /private/tmp: +18,927,616 bytes; observations may describe the same volume and are not summed or attributed to deletion.
The unmerged candidate worktree and minimal release tools remain owned for candidate/release handoff; platform installed dependencies and all protected roots are unchanged.

Automatic approval review rejected branch upload and draft-PR creation before execution because exporting candidate source to `arthursw/wetlands` requires explicit trusted-user authorization.
The user then explicitly approved source push and draft-PR creation; the SSH attempt failed before upload (0.922 seconds, public-key/askpass authentication), and the same authorized destination succeeded through per-command existing gh HTTPS authentication (push 2.687 seconds, PR creation 2.520 seconds).
[Draft PR #5](https://github.com/arthursw/wetlands/pull/5) is open at exact head `f4409ce8b551be6dff62e26ee535ccdd9b47c131`; no global authentication configuration or credentials were printed or changed.
The exact-head [CI run 37048171797](https://github.com/arthursw/wetlands/actions/runs/37048171797) has all 25 required jobs present: lint, eighteen three-OS/Python 3.9–3.14 fast jobs, Python 3.9 compatibility, three real-Pixi jobs, strict docs and package validation.
The final independently inspected exact-head run passed all 25 required jobs; the push-only documentation deployment is intentionally skipped for a pull request and is outside that gate.
Local library development may consume the frozen unpublished wheel in its own private environment after handoff; passed upstream CI does not establish publication, a supported dependency floor or platform/worker certification.
At this October 2 checkpoint the user had merged PR #5 but tagging, GitHub release and PyPI publication still awaited authorization; the October 3 standing authorization below supersedes that gate.
No tag, GitHub release, PyPI publication or platform-pin change was credited by that October 2 checkpoint.


### Local library public-completion adaptation — qualified WIP checkpoint

The isolated library at `3859b318dbdf69271f1d3fd6f5f7d7df7e8b0a96` has six reviewed source/test/specification working inputs frozen in `public-completion-final-source.json`; it is not integrated or committed as a supported release.
Only its private environment installs the unpublished Wetlands 2.5.0 wheel (`17cdfb01e3bba26218b1580dc4b752d7fc86083f5d6e824b7b5781b6d469c062`), with all 29 modules plus `py.typed` matching the candidate and module origins outside source.
The force-only unsupported-runtime refusal failed once before repair, then seven exact unit controls passed in pytest 1.13 seconds (measured 1.491 seconds); five affected owner families passed 76 tests with no skips in pytest 1.21 seconds (measured 1.593 seconds).
The first owner invocation's optional `atlas_env` collection error is preserved; recovery exposes only own-tree fixture code, not a published-tool compatibility result.
Force controls/shared fakes were split into an existing core family, a focused recreation family and testkit to meet the mandatory size/import guards; historical→current selector mapping is preserved without duplicate coverage credit.
The initial Ruff unused-import failure is retained; its behavior-neutral correction recovered whole-tree Ruff in 0.066 seconds, while scoped env-manager Pyright passed in 1.709 seconds and size/import guards passed in 0.191/0.516 seconds.
Strict whole-library Sphinx `-W --keep-going` passed in 53.192 seconds; these are qualified source-development results, not another whole-library suite or physical worker/process certification.
Current library source version 0.8.7, root/package Wetlands floor ≥2.4.2 and committed lock 2.4.2 remain unaligned with the new public API; release metadata/floor/lock alignment against published Wetlands and subsequent published-wheel/platform/worker acceptance still block supported source delivery.
Platform installed dependencies remain unchanged; original full/browser failures, final Firefox admission block and desktop-final-M5 restriction remain open.


### Workflow-tree pending request coalescing — October 2

Two passive startup consumers now share one pending tree request only within the same catalog authority and structural generation.
Accepted same-ID metadata changes and deliberate post-mutation/workspace/migration/reconnect refreshes invalidate that authority; tree and flat-list endpoints retain their own response contracts, request-owned loading/error finalizers and at most one stale retry per caller.
Successful results are not cached, and stale retry never awaits its own expired flight.
The original six public-store controls failed on unchanged source, and the reverse flat/tree interleave failed separately; all seven controls passed after the repair, with 135 affected owner tests passing in seven files (no skips, measured 3.226 seconds).

The same frozen production harness used 100 empty workflows, 1,000 managed 16-byte files and six fixture tools, with accepted-graph/paint and search-row oracles unchanged.
Every first-navigation/warm-reload observation reduced identical tree GETs from two to one, and decoded tree response-body bytes from 95,930 to 47,965 per startup.
The second baseline request was created while the first was still pending; later post-settlement reads remain uncached.

| Measured task | Before | After |
| --- | --- | --- |
| First navigation, one observation | 3,055.096 ms | 2,628.775 ms |
| Warm reload, five-observation median (range) | 2,829.650 ms (2,576.708–3,281.462) | 2,533.470 ms (2,382.890–2,915.163) |
| Fresh Browse Open, five-observation median (range) | 543.009 ms (538.385–587.633) | 545.075 ms (531.754–582.267) |
| Workflow search, five-observation median (range) | 41.571 ms (33.535–50.119) | 40.618 ms (38.910–47.555) |
| Dataset search, five-observation median (range) | 175.106 ms (161.449–179.512) | 174.014 ms (161.095–253.220) |

Warm-startup median improved by an observed 296.180 ms (~10.5%) in these sequential synthetic cohorts, with overlapping ranges; this is not a randomized or universal latency guarantee.
Repeatability beyond these cohorts remains unverified.
Request-work reduction is established independently of latency, while unchanged Browse Open and search tasks show no established improvement.
Both 21-task headless Chromium batches passed with zero page errors (measured 34.983/30.976 seconds); their owned servers and synthetic roots were retired, preserving traces and exact source/build/runtime/harness manifests under `/private/tmp/bioimageflow-m2-performance/`.
Main installed BioImageFlow `dff04e3`, Wetlands 2.4.2, dependency metadata and locks remain unchanged; the unpublished candidate library environment is separate and untouched.

The one `env UV_OFFLINE=1 scripts/test check frontend` invocation remains **FAIL** (exit 1, measured 23.949 seconds) because the new test fixture omitted required `WorkflowInfo.folder`.
Its unchanged lint (10 seconds), production build (6 seconds) and all 1,357 units in 135 files (24 seconds, no skips) passed and are retained.
Adding only the required empty folder recovered all seven exact controls in measured 1.936 seconds, type checking in 5.628 seconds and lint in 5.169 seconds; no frontend lane or build was repeated.
This is qualified assembled frontend completion, not a monolithic passing check invocation or full/browser certification.
The one consolidated `env UV_OFFLINE=1 scripts/test check docs` passed (exit 0, runner 3 seconds, measured 2.811 seconds) at `788d67b` plus the exact reviewed source/specification/record snapshot.
The separate product/test/specification task is committed as `f32c9b4`; this record adds only its disposition and observed evidence.
Prior full/browser failures, final Firefox admission block, published-package/worker acceptance and native desktop-final-M5 gates remain open.


### Wetlands user merge verified — October 2

The user merged [PR #5](https://github.com/arthursw/wetlands/pull/5) at 19:15:53 UTC as main `3cda2236fe000b30dabf42a04e9ad347265630a0`, preserving reviewed head `f4409ce8b551be6dff62e26ee535ccdd9b47c131` as its second parent.
Both commits have identical full tracked Git tree `eb14911f8f8b7ddae54dfdc7f4c13c4f0379bc52`, so candidate source, metadata, lock and package bytes are unchanged.
The exact merged-head [main CI run 37052970686](https://github.com/arthursw/wetlands/actions/runs/37052970686) passed all 25 required jobs and the additional main documentation-deployment job (26 successes, no skips or failures); unchanged local candidate tests/builds were not repeated.
Read-only primary checks at 19:59:59 UTC found no `v2.5.0` tag or GitHub release and no PyPI 2.5.0 version; PyPI latest remains 2.4.3.
That verification preceded the October 3 explicit publication authorization; no agent publication action had yet been taken.
The frozen library WIP/private candidate environment, platform installed dependencies and protected owning roots remain unchanged; published-wheel acceptance, library floor/lock alignment and subsequent platform/worker certification remain open.


### Performance-review retrospective — October 2

M1's completed file-review coverage did not establish common-task performance assurance: the static synthesis missed repeated saved-workflow reads/format plans within draft synthesis, the two startup tree loads and dataset-list double reconciliation.
It recorded related stale-generation collection risk (`A-F068`) but missed same-ID Save freshness and request-owned error/loading/finalizer effects; shared environment inventory (`B-F020`) and Core codec duplication (`B-F137`) were already recorded as unmeasured P3/deferred work.
Performance magnitude required later comparable task measurements; those static duplication and ownership omissions could have been identified before profiling, while folder/index improvements remain conditional candidates rather than demonstrated bottlenecks.
The correction adds shared end-to-end startup/Open/edit-Save/dataset-browse/Run-start maps with work multiplicity and authority/freshness/error/loading ownership, lead/cross-owner synthesis and explicit deferred-finding dispositions; bounded user-task measurement sets magnitude and priority at coherent milestones.
`B-F020` remains queued with library/platform environment owners for measured Run-start inventory multiplicity; `B-F137` remains with the Core owner until supported task-payload cost and transport controls justify repair, without blanket P3 promotion.
Frozen M1 file-ledger counts and history remain intact; reuse accepted evidence and review only uncovered paths, without repeating the entire audit or suite.


### Wetlands 2.5.0 publication and next architecture gate — October 3

The user explicitly authorized publication and future necessary campaign package releases without renewed confirmation; the plan and resume instructions retain this standing authorization together with technical owning-repository review/CI/artifact/published-compatibility gates.
An annotated `v2.5.0` tag targets reviewed merge `3cda2236fe000b30dabf42a04e9ad347265630a0`; the single [GitHub release](https://github.com/arthursw/wetlands/releases/tag/v2.5.0) triggered [release workflow 37116004043](https://github.com/arthursw/wetlands/actions/runs/37116004043), whose validation/build and trusted-publishing jobs passed.
[PyPI Wetlands 2.5.0](https://pypi.org/project/wetlands/2.5.0/) publishes wheel SHA256 `17cdfb01e3bba26218b1580dc4b752d7fc86083f5d6e824b7b5781b6d469c062` and sdist `5172cfb846776763d41e61a8cdfad18d3252d630ec3e47528b4e2fb61099b84e`; both match the independently reviewed candidate artifacts byte for byte.
Tag push passed in 1.969 seconds and release creation in 1.107 seconds; the published-wheel source-disabled batch passed nine public completion/outcome/callback controls with eighteen unrelated controls deselected (pytest 0.22 seconds, command 3.853 seconds), plus CLI/origin/version/runtime checks; retained Python 3.14 pluggy SyntaxWarnings are not suppressed.
All 29 installed Python modules plus `py.typed` match the published wheel and exact release source; package/worker versions are 2.5.0, protocols remain 1, and the minimal installed dependency closure is retained in the identity receipt.
The exclusive smoke environment had no active consumers and was removed in 0.181 seconds, preserving artifacts/logs/closure proof; 6,569,361 file-reference bytes and 7,397,376 stat-block reference bytes are not claimed reclaimed allocation, and the observed free-space change +3,231,744 bytes is unattributed.
No unchanged 616-test/build/strict-doc candidate phases or source-identical sdist install were repeated; published upload and these public controls do not certify physical worker/process lifecycle, the library’s still-unaligned floor/lock or platform/worker pins.

The supplemental gate is now planned before further repair/integration: three coordinated reviewers produce five detailed current task maps, a cross-repository module/ownership overview, all 573 candidate IDs grouped by family/disposition and a dedicated suite/specification assessment, then source-validate high-risk/current-task/cross-layer candidates and cross-review coverage/known unknowns before fixes; deferred qualified candidates retain owners/triggers rather than becoming presumed defects.
Preparatory read-only traces are not completed gate acceptance; the intended report and final consequential record will be delivered after independent review, preserving frozen M1 history, current library WIP/private environment and all protected roots.

The one consolidated `env UV_OFFLINE=1 scripts/test check docs` passed against `ec65a54` plus the reviewed three-file plan/resume/publication snapshot (exit 0, runner 3 seconds, measured 3.100 seconds, Documentation phase 2 seconds); this sentence records its result without changing the accepted gate or published source.


### Supplemental architecture findings gate — October 3

Three coordinated read-only packets now supply the intended [supplemental report](platform-supplemental-architecture-review.md) and [original candidate dispositions](platform-architecture-candidate-dispositions.tsv): detailed startup/Open/edit-Save and dataset/Run task chains, cross-package ownership/contract maps, broader high-risk families, normative disagreements and a dedicated suite/fixture/lane/oracle assessment.
The exact original573 candidates remain A181/B195/ROOT97/reviewer100;144 distinct current keyed annotations cover all56 highest original severity candidates with specific owners/mitigations, while429 without current annotations retain historical qualifications and responsible owners/triggers.
Annotation is not synonymous with reproduction or confirmation;21 unranked headings retain body priority or explicit unranked treatment, and reviewer084 accessibility remains annotated but historical/deferred.
Current source-qualified open mechanisms include recovery deletion on editable-list omission, explicit stale nested-owner generation replacement, Save promotion/acknowledgement choices, raw execution cancellation/physical admission, dataset attempt/publication, public source/transport/export and scientific lineage boundaries.
A-F061/A-F004 receive concise existing-finding extensions; new ROOT-F099 is a qualified P3 diagnostic projection candidate with no reproduced wrong badge, separate from the frozen573 set.
The five maps are navigation into broader architectural families, not certification of all engines, packages, security, viewers or numerical behavior.
No product code/tests, new profiling, environments or runtime checks were added; frozen M1 coverage and prior failed/unrun/blocked/native gates remain unchanged.
Root and independent intended-byte completeness acceptance passed on October 3 within the report’s explicit scope; this accepts the recorded findings/triage gate, not all573 source confirmation or an architectural safety guarantee.
The one consolidated `env UV_OFFLINE=1 scripts/test check docs` passed against `04f9588` plus these six reviewed documentation paths (exit 0, runner 4 seconds, measured 4.442 seconds): dashboard, 74 active local links and warning-clean Sphinx.
No test/runtime phase was run or reclassified; subsequent repair starts only against the selected owning contract and explicit dependency/publication prerequisites after this durable task delivery.


### First owning public-release repairs and retirement — October 3

The supplemental architecture findings gate remains accepted at `feb128b`; its frozen 573-ID inventory/history and qualified report are unchanged.
A-F024 is committed separately as `d4ba925f58ce1576939bcaf4803131a7d18d2382`, then B-F115 as `86a84fd6904818d1c10f10ef6644e3f1d76c3bb1`, on the same clean isolated `campaign/library-source-containment` tree with sequential source/runtime ownership.
The library loader captures/admit-checks complete immutable source paths/bytes before custom writes/imports, preserving nested helpers/assets, defaults and safe Unicode/hyphen IDs; Core rejects object-containing dtypes before shared-memory create/attach, including structured object storage.
Owning specifications changed with each repair; trusted Python remains executable, and neither repair closes cache-origin, general array-format, physical-worker or published compatibility gates.

All commands below use that tree’s frozen private Python 3.12.9 environment; `.venv/bin/python -m pytest` is the admitted owning README pytest equivalent and does not resync its 104-package closure.

| Owning command/scope | Actual result and measured duration | Source |
| --- | --- | --- |
| `.venv/bin/python -m pytest tests/integration/test_custom_source_containment.py -q` | Original 4 causal FAIL + 1 valid PASS, pytest 44.05s / command 50.180s; final 6 PASS, no skips, pytest 1.60s / command 2.256s | Frozen `3859b318` plus tests → reviewed four-path snapshot committed `d4ba925` |
| Same file’s exact reserved-device selector | 1 causal FAIL, 1.726s; staging sentinel prevents any device open; included in final six GREEN | Unchanged baseline → `d4ba925` |
| README mapped ten workflow owner families | 117 PASS, 10 retained declaration warnings, pytest 27.64s / command 28.336s | Exact `d4ba925` source/spec/test bytes |
| `pytest tests/unit/test_development_workflow.py tests/unit/test_complete_test_gating.py tests/unit/test_release_tooling.py -q` through private Python | 61 PASS, 10.187s | Same archive snapshot |
| `.venv/bin/ruff check .`; private Python file-size/import-boundary guards; scoped `.venv/bin/pyright packages/bioimageflow/bioimageflow/workflow/custom_sources.py` | PASS 1.302s / 0.479s / 0.685s / 2.179s; typing is owner-only | Same archive snapshot |
| Private Python `docs/generate_tool_package_docs.py`, then `.venv/bin/sphinx-build -W --keep-going docs/source docs/_build/html` | Generation PASS 3.493s; original strict docs FAIL 67.089s, exactly two intersphinx DNS warnings; unchanged incremental permitted-network recovery PASS 5.630s | Same archive snapshot, no source edit or warning suppression |
| Private Python exact `test_object_dtype_refused_before_shared_memory` + `test_structured_object_dtype_refused_before_creation` selectors | 4 causal FAIL, 1.985s → same 4 PASS, 1.848s | `d4ba925` plus tests → reviewed five-path snapshot committed `86a84fd` |
| Private Python `test_shared_memory.py`, both runtime-cache shared-memory families, `test_core_package_metadata.py` and `test_validation.py` | 65 PASS, no skips, 9.628s | Exact `86a84fd` bytes |
| Core full Ruff, file/import guards, scoped Pyright `shm.py io.py`, unchanged strict Sphinx command | PASS 0.119s / 0.450s / 0.667s / 0.835s / 5.483s | Same Core snapshot; archive generation retained |

These are proportionate localized owning checks, not full-fast/full-workspace, complete/resource, native or published-worker acceptance; original full/browser failures and final Firefox admission block remain open.
The archive setup first failed at package-scoped `--group dev` (0.389s; the group belongs to the workspace root), then prepared the frozen root group in 92.177s.
An exact UV invocation failed before pytest at sandbox cache access (0.038s), and default/interpreter replacement runs were stopped with zero test admission at 73.992s and 241.246s; the exclusive partial environment was preserved, a fresh same-lock Python 3.12 closure completed in 13.028s, and all subsequent controls used its private interpreter.
Preflight chosen interpreter versus `.python-version`, locked closure/cache access and network-dependent docs permissions before starting; these setup/permission failures are retained and supply no product RED credit.

After all archive runtimes stopped, the merged Wetlands release tree’s exclusive release/build/cache stores and the unused partial interpreter environment were retired in 68.198s; clean merged source moved to unique Trash, worktree metadata was pruned and only its merged branch deleted.
Removed stores total 346,497,715 file-reference bytes and 368,353,280 stat-block reference bytes; these are not unique reclaimed allocation, retained Trash source is not recovered space, and observed volume-free change +36,204,544 bytes is unattributed.
Artifact/log receipts, owning mains, platform source, held force WIP and the active containment environment are preserved; that environment/tree remains owned for follow-up repairs until integration/retirement gates are met.

Platform installed BioImageFlow `dff04e3`, Core 0.4.1 and Wetlands 2.4.2, platform locks and the held force source/private candidate environment remain unchanged.
Published Wetlands 2.5.0 proof remains valid, but the archive/Core repairs are unpublished isolated source and not yet a current platform dependency.
The user superseded the earlier B-F134 V1 passthrough/optional-frame direction before implementation: one clean current public task/result/value contract, unambiguous literal dictionaries and type-faithful values; no duplicated legacy DTOs, dual wire or old-producer compatibility tests.
Core 0.5 remains an intended truthful minor, with actual current public bidirectional worker/source/artifact proof and a coherent nine-tool dependency-bounds/metadata-release cohort required before pins/releases.
Campaign-wide legacy-only migration/alias/fallback obligations become reviewed redesign/retirement candidates; essential features, current workspace recovery/durable state and scientific/ownership invariants remain required, and frozen historical evidence is not rewritten.
A-F026 now has one actual public causal RED on unchanged `86a84fd`: the same source ID with newly verified bundle content executes stale A value 1 instead of B value 9 (pytest 2.31s, command 4.645s); the source fix remains pending separate review.
After the pending A-F026/B-F134 source gates, reconcile accepted source/held force work, published Core/Wetlands floors, library release and platform T1; no new version, floor, package release, blind bounds widening or renewed architecture audit is claimed.
Evidence is retained in `/private/tmp/bioimageflow-a024-containment/` and `/private/tmp/bioimageflow-supplemental-architecture/core-next-readiness/`, including exact committed-path/closure identities and cleanup protection proof.
The one main `env UV_OFFLINE=1 scripts/test check docs` passed on `feb128b` plus these five reviewed documentation paths (exit 0, runner 5s, measured 4.605s; Sphinx phase 4s), including dashboard, 74 local links and warning-clean documentation; no application/runtime test was run.


### Campaign throughput and bounded executors — October 3

The A-F026 throughput audit records eight actual subprocess commands totaling 16.583 seconds (approximately 15.379 seconds on a parallel static-check critical path) within a 657.917-second first-patch-to-final-proof artifact timestamp envelope.
The envelope is not a complete attribution of idle time, model latency or handoff cost; it identifies a coordination opportunity without proving a test/runtime regression or a model speedup.
The plan/resume now use one upfront scope/oracle packet, autonomous exact RED/fix/GREEN/mapped checks, one final independent coherent review and writer-owned task-only index verification/commit, reusing unchanged closure evidence and permitting immutable-artifact/disjoint-file parallelism.
Already-decided mechanical batches may use an actually available lighter executor with literal repository/HEAD/paths/hashes/commands/preconditions/permissions/ownership/cleanup/evidence instructions; mismatches stop and return to the capable owner, which retains architecture, debugging, test/version selection and releases.
No executor was spawned, running model/configuration changed, test case removed or measurable model saving claimed by this documentation task.
Process-only campaign changes use one campaign consistency/link gate; API/specification/navigation and substantive documentation gates remain as documented, with all current clean-design and standing release authorization instructions preserved.
Library/Core source work, artifact/worker runtimes, installed dependencies and their existing release gates are unchanged by these three main campaign-documentation paths.
The one `env UV_OFFLINE=1 scripts/test check campaign` passed (exit0, measured0.112 seconds, runner0s) against main `749f1a0` plus the reviewed three-path process-documentation snapshot: dashboard consistency and74 active local links; no product, runtime or Sphinx phase was selected.


### Current source transport acceptance and lifetime release gate — October 3

A-F026 is now separately source-accepted at `063d81ce9a8534716d13d9de1097d720274368a7`: a content-scoped runtime namespace retains independent same-ID executable snapshots, source hashes and valid archive roundtrips.
Its unchanged exact public selector `tests/integration/test_custom_source_containment.py::test_same_source_id_changed_bundle_keeps_independent_executable_snapshots` changed from 1 FAIL (4.645s) to 1 PASS (2.425s); 23 mapped containment/recursive-roundtrip/Parsl-materialization owners passed without skips (3.445s), affected static checks passed and one strict owning Sphinx build passed (3.903s).
B-F134 is committed at `8c1e668a2163394501fcee80213dfbe1d2d3fe7c`: exactly 19 source/spec/test paths, clean isolated tree and empty index, independently accepted as one current v2 task/result contract with typed dictionaries/containers, Path, SharedArray references and scientific NumPy arrays/scalars; recursive remote host-local-reference refusal remains required.
The existing-API codec baseline had one causal task FAIL and one local result PASS (0.587s), not two failures; a separate actual public worker executed the tool then refused its SharedArray output with `ValueEncodingError` (expected-failure harness passed, 29.702s).
The first two file-URL provisioning attempts failed before worker admission (8.175s/0.957s); the task-owned immutable-wheel HTTP recipe admitted the real baseline worker, so setup failures receive no causal transport credit.

| B-F134 owning command/scope | Actual result and measured duration | Exact source qualification |
| --- | --- | --- |
| Private Python exact task/result descriptor, numeric, object-array no-send and malformed-reference no-attach selectors | 11 PASS, no skips, 0.928s | Reviewed current source before a typing-only cast correction |
| `.venv/bin/python -m pytest tests/unit/worker_protocol tests/unit/test_processing_output_validation.py tests/unit/parsl/test_submission.py tests/unit/parsl/test_submission_failures.py -q --tb=short` | 105 PASS, no skips, 3.109s | Same 19-path candidate; later cast changes typing only |
| Private Python complete `test_codecs.py` after the cast; full Ruff then changed-helper Ruff; file-size/import guards | 44 PASS, 0.695s; Ruff PASS 0.150s/0.066s; guards PASS 0.340s/0.721s | Final committed codec/runtime semantics; retained unaffected owner results |
| Scoped Pyright on seven changed implementation owners; `.venv/bin/sphinx-build -W --keep-going docs/source docs/_build/html` | Initial typing FAIL 1.549s, cast-only recovery PASS 1.326s; one strict docs PASS 3.860s | Exact final source/spec bytes; no full-project typing claim |
| Source-disabled developer Core 0.5 wheel through public managed WorkerPool, input/output/combined typed/scientific values | Final no-attach 3 cases PASS, 17.773s; exact schemas/correlation, separate PID and all 14 Core source-file hashes, clean pool/server/parent-segment cleanup | Serialization-only witness; wheel `e32fcd5dcef329f34e170beec7e6644ab42a3a8cde1b1024c5ae0d4299b77ba1` uses a transparent version-only export overlay, not committed release metadata or published Core |

The earlier attached-worker command had all three transport/type/correlation cases succeed but the overall command FAILED (16.499s): after public pool shutdown, worker resource tracking had removed the parent's segment and parent unlink raised `FileNotFoundError`; its warnings/failure remain a mandatory prepublication lifetime gate.
The final no-attach fixture does not certify consumer attachment lifetime; its first changed-URL recipe attempt was refused before admission (1.068s), then the public task-owned `replace_existing=True` recovery passed.
Root selected a single uniform file/mmap plus controller-owner lifetime proposal preserving essential current Python/OS scientific capabilities; this is pending owning design/implementation, not a Python-3.13-only restriction, private unregister workaround or duplicated legacy backend.
This is a distinct B-F134 lifetime extension, not B-F116's existing scalar/empty-array-format finding.
The held six-path force patch remains byte-preserved and its exact apply-check passed against the preceding source projection; it has not been integrated, and fake-owner acceptance does not certify physical worker shutdown.
Platform installed `dff04e3`/Core 0.4.1/Wetlands 2.4.2, platform pins, owning metadata/lock and nine tool bounds remain unchanged; Core 0.5/BioImageFlow 0.9 current-cohort and published Wetlands floor adoption, source-disabled package checks, normal exact-head CI and platform published-worker certification remain pending.
The frozen 573-ID review inventory and its historical disposition bins remain unchanged; no full-fast/full-workspace, complete/native/HPC, app/full or cross-browser phase is claimed by these localized source checks.
The exclusive artifact host and managed package cache are retained only for the next assigned lifetime consumer (28,060/720,964 KiB reference accounting); retire them after reuse/proof consumers finish, without deleting the active owning dev environment, unmerged source, artifacts/logs, main or held force work.
Exact source/check/artifact receipts are in `/private/tmp/bioimageflow-b134-transport/`, including `final-delivery-proof.json` and `independent-final-applied-review.json`; A-F026 proof remains under `/private/tmp/bioimageflow-supplemental-architecture/core-next-readiness/a026/`.
The one `scripts/test check campaign` passed against main `aee28e0` plus these four campaign-only paths (exit0, measured0.115s); it selects dashboard/local-link consistency, with no product, runtime, Sphinx or publication phase.

### Uniform shared-array lifetime source acceptance — October 3

The 41-path owning implementation is independently source-accepted and committed at `6551f0bd492cd77a6934ae575f5b6f3156a6ed03`, parent `8c1e668`; exact committed/working bytes match the reviewed final manifest, with clean owning index/status and no live task runtime.
It replaces tracked named segments with one scoped numeric NPY2/file-mmap backing, strong locally bound output ownership, same-FD header/map admission, finite allocation budgets and explicit pending cleanup.
Automatic execution, Workflow/context exit and GC only unbind; returned references remain eligible for new opens until explicit release, while live NumPy views and already-admitted worker grants retain backing until physical drain.
Worker/result decoding attaches nothing, parent shutdown does not steal worker-created outputs and worker shutdown cannot delete parent buffers.

| Actual candidate evidence | Result/duration | Limits and retained failure |
| --- | --- | --- |
| Source-disabled Core developer wheel + public Wetlands 2.5 WorkerPool; input/output/combined/failure/closed-grant cases | Five PASS, 21.762 seconds; current 16 Python modules equal in host/worker; actual worker exit before grant drain; input/output bytes survive; retained views drain before explicit physical cleanup; orphan cleanup/outside sentinel intact | macOS/Python 3.12 only; candidate wheel SHA256 `112424599456302a67965d8b95cbdaae245a9798802702e6025e48c06e960530`, transparent 0.5 development overlay; package README precision edit after build is not claimed artifact equality. Original attached-worker overall FAIL at 16.499 seconds remains. |
| Cache identity excludes local owner binding without attachment | Exact 1 FAIL in 1.604 seconds → 1 PASS in 1.393 seconds; 16 cache owners PASS in 1.600 seconds; 17 controller/return/source-and-column hydration owners PASS in 9.601 seconds | Logical scoped reference identity remains; owner locks/leases do not enter cache identity. Counts overlap other owner commands and are not summed. |
| Affected integration and consumer controls | Initial 170 PASS/5 FAIL, pytest 9.69 seconds; stale manager/timeout fixtures corrected, exact recovery 6 PASS, pytest 1.43 seconds; current type/output/Parsl consumer 80 PASS in 1.766 seconds | Initial failed command remains failed; no monolithic owner/full-suite PASS is invented. Fixtures required new mandatory scope/grant fields, with no legacy constructor fallback. |
| Pending result disposition remains independent of physical worker drain | Exact 1 FAIL in 2.553 seconds → 1 PASS in 24.844 seconds; 13 affected controller/cancellation owners PASS in 25.466 seconds; invalidated static guards PASS | Unpublished output stays retained until controller acceptance or explicit rejection, even when the pool physically drains first; no timing cause inferred. Core wheel bytes were unchanged, so the five-worker artifact proof remains valid. |
| Scoped final quality/typing/strict owning docs | Ruff/size/import/scoped Pyright PASS; strict docs initially FAIL in 23.288 seconds with two title-underline warnings, corrected exact docs PASS in 6.216 seconds | Full-project typing is not credited; coherent final candidate/source projection is bound by the manifest, not the old dev package version. |

Evidence is `/private/tmp/bioimageflow-uniform-lifetime/final-manifest.json`, `independent-final-review.json`, `final-delivery-proof.json`, `public-worker.json` and the actual command/log receipts; original B134 failures remain under `/private/tmp/bioimageflow-b134-transport/`.
The existing private 104-dependency closure, owning metadata Core 0.4.1/BIF 0.8.7/Wetlands 2.4.2 lock, platform installed `dff04e3` and all platform/tool pins remain unchanged; installed candidate artifact identity is not released-package equivalence.
The held six-path force WIP still matches its accepted hashes/patch `3c7a1cb…` at `3859b318`; current read-only applicability now FAILS manager/core-dependency fixture hunks because lifetime added grant ownership.
Next merge those hunks semantically onto the clean lifetime commit, retaining pool/cache/grants on close failure and physical close→selected-grant drain→public removal on success, then align Core 0.5/BIF 0.9/current tool floors/lock, current artifact/resolver and exact-head CI/release gates, dependency-ordered publication and platform T1.
Actual Windows/Linux and Python 3.9/NumPy 1.26 numeric mmap lifetime remain named essential prepublication gates with narrow owning-CI artifact/owner controls; the Ubuntu-only normal CI and current macOS/Python 3.12 witness do not prove them.
The v1 Section 2.8 shutdown target now requires explicit application-owned scope release after physical grant/reader drain with pending/error reporting and no global prefix deletion; installed platform runtime adoption remains deferred to T1.
Phasor source/features remain preserved, with first-project publication/publisher readiness separate from the base cohort.
The frozen 573 inventory/dispositions remain unchanged; no platform product/full/browser/native/HPC or current published-package certification is credited here, and desktop stays final M5.
Active owning dev/artifact environments and public package cache remain intentionally retained for the next consumer; no cleanup or reclaimed-byte claim is added.
The one applicable `env UV_OFFLINE=1 scripts/test check docs` passed against main `5bab8c6` plus these six documentation paths: exit 0, runner 6 seconds, measured 5.534 seconds, campaign dashboard/local links and warning-clean Sphinx.
This check validates the developer-context/shutdown-target/checkpoint documentation projection; no product tests, preliminary campaign check or repeated Sphinx check were run, and only this factual result sentence was appended afterward.


### Highest-priority current library/Core phase — October 4

The user's new priority supersedes the prior publication/platform-integration queue: conduct a deep current-library/Core architecture, whole in-scope suite and specification review, main features first and secondary features next, before any further fixes.
The current owning baseline is clean committed `2cd79a24c59cf1093e934da9aa97744d2f8709c8` in `.worktrees/campaign-library-source-containment`; semantic force/cohort integration is delivered, including declared Core 0.5/BioImageFlow 0.9 bounds/lock and the narrow array capability CI job.
The four local source-disabled artifact families passed on macOS/Python 3.12 (1.100 seconds), and the current five managed cases passed (19.949 seconds); initial harness admission failures/corrections remain in their owning receipts, and none proves the unexecuted Linux/Windows/Python 3.9 jobs or published cohort loading.
Source/delivery evidence is `/private/tmp/bioimageflow-force-cohort/final-delivery-proof.json`; preserve earlier failures, current candidate artifacts/metadata, original held force source/environment and unrelated user trees.
No metadata rollback, publication, platform dependency change or new product checks are part of this priority-documentation task.

Phase 1 establishes the actual primary/secondary/excluded file-feature-test-spec map, then completes primary source/flow/suite review followed by secondary review and a global recorded findings/mitigation/unknown synthesis accepted independently before any source fixes or test additions.
The owner supplied the actual initial map: primary Core/contracts, workflow construction and local engine/cache/storage/results; secondary public API/support, nine scientific tool implementations and package/suite/release architecture.
Core 16/orchestrator 159/root test 194/tool test 22/tool production 55 are mechanical counts, not review coverage; complete-file ledger status and cross-module essential-flow review remain separate qualified evidence.
Local export/launcher return/assets/routes/schema/download/bundle owners are explicitly retained inside mixed directories; the suite map must identify exact local nodes and focused opt-in managed-worker controls rather than assume the README fast lane or a not-parsl marker supplies that scope.
Phase 2 implements and causally validates bounded primary architecture/features first, then secondary repairs/tests; suite assertions, redundancy, fixtures and lane ownership must be assessed before choosing new tests.
Phase 3 executes one applicable local-library milestone with an explicit non-distributed collection proof and remaining technical gates reported honestly.
Within-machine managed WorkerPool/Direct processing is primary; Parsl, Dask, remote and distributed engine implementations/testing/certification are excluded, while essential shared local API seams remain reviewed and excluded delivered features are preserved.
Historical M1/supplemental results, accepted patches and frozen 573 classifications are preserved but do not substitute for this new deep current-library gate.
Publication/platform T1 and platform testing remain paused through acceptance of the completed Phase 3 library milestone; actual supported-OS/artifact/current resolver/exact-head CI/local Complete Wetlands and published-package obligations remain deferred, not passed or canceled.
Future task packets must explicitly carry this priority, phase, main-first class, read-before-fix gate and exclusions alongside focused/subsumed checks, environment reuse, literal executor stop-on-mismatch, cleanup-after-consumers, standing release authorization and desktop-last.
One independent changed-plan review accepted this priority/phase authority, including the clarification that releases/platform work wait for the completed Phase 3 milestone.
The one offline `env UV_OFFLINE=1 scripts/test check campaign` passed against main `ce419b38` plus these four process/authority/status documentation paths (exit 0, runner 0 seconds, measured 0.134 seconds); dashboard and active local links passed, with no Sphinx, product, network or capability phase.
Only this factual result sentence was added after the check; no library review completion or runtime certification is credited by this record.


### Ordered library review refinement — October 4

The user's later ordering supersedes the production-first review sequence above: resume Phase 1 at S, reviewing current in-scope library/Core specifications and public developer examples, recording accepted essential feature/domain/API/ownership intent, contradictions and a finite feature-flow catalog before T.
T then reviews the whole applicable suite/fixtures/oracles/selectors against that intent; C follows causal main-feature paths and then secondary paths, from trigger through public API/state/data/effects/error/cancellation/cleanup/return with cross-module ownership and lifetimes.
Spec → test oracle → code-path traceability, differential confidence and explicit gaps are the primary synthesis; the path/hash ledger remains a supplemental completeness check.
The prior read-only production/test/spec notes at unchanged `2cd79a2`, including fourteen workflow candidates, are retained as provisional evidence to reconcile rather than discarded or presented as completed ordered S/T gates or causal closure; no new runtime checks or fixes have begun.
Independent acceptance of S, T, both C passes and all main/secondary findings precedes repairs; S critically resolves intent rather than canonizing stale specs/code, separates editorial consolidation from semantic decisions and may authorize coherent owning specification clarification before T, while behavior-changing choices remain findings through global synthesis.
The actual S specification deliverable is a separate increment from this process update, with no code-fix or runtime claim.
Current Core 0.5/BioImageFlow 0.9 metadata/artifacts, protected held WIP and the preceding qualified local results remain preserved; supported-OS/exact-head CI/Complete local Wetlands/publication gates remain unexecuted or pending as already recorded.
Publication, platform adoption/T1 and further platform testing stay paused until the completed library milestone is accepted; local Direct/managed WorkerPool and shared local result/export/launcher seams remain in scope, while distributed-only symbols, implementations and capability testing remain excluded.
Standing release authorization, one clean current design without backward-only layers, focused/subsumed checks, environment reuse/cleanup after consumers, literal batched executor rules, one upfront/final review and desktop-last are unchanged.
This four-path process/authority/checkpoint update changes no library/Core source, dependency/runtime or public API/specification behavior.


### Accepted library specification intent and clarification — October 4

The [S intent review](library-specification-intent-review.md) is accepted against owning library source `2cd79a24c59cf1093e934da9aa97744d2f8709c8` after one cross-domain critique and focused essential-feature corrections.
The thirteen merged decisions and sixteen finite main/secondary flows preserve dynamic DataFrame tools without Outputs, isolated whole-batch training/inference/aggregation and empty-input artifacts, all nine scientific packages, exact origin/data/provenance and controller lifetime ownership.
Whole assigned normative sections and public guides were read; section/file ledgers supply completeness evidence, not code conformance, scientific accuracy or OS certification.
The ensuing docs-only increment updates the shared specification and disjoint workflow/Core/runtime/public guides, distinguishing editorial correction from accepted semantic targets and T/C verification obligations without inventing lifecycle methods or aggregate wire fields.
Known source/runtime/artifact proofs remain qualified; changing documentation means candidate docs/sdist bytes no longer match older artifact receipts, while unchanged source-module bytes retain their original bounded proof.
No product source, tests, dependency bounds, lock, environment or installed platform runtime is changed by this task.
Next is whole in-scope T oracle/fixture/selector review, then causal main→secondary C and global findings acceptance before code fixes; publication, platform adoption/T1 and platform testing remain paused until the accepted scoped library milestone.
Windows/Linux, actual Python3.9/NumPy1.26 annotation/numeric lifetime, optional models/binaries/pinned scientific references, current-cohort normal installs and exact-head CI remain named later capability gates, not passed by S.
Owning clarification commit `e0f41b11e62defcd84b913db12b14e481b7c9a0b` contains exactly 48 reviewed documentation paths over `2cd79a24`; committed/working hashes match, with a clean tree and empty index.
`.venv/bin/python docs/generate_tool_package_docs.py --check` passed in 0.409s; `.venv/bin/sphinx-build -W --keep-going docs/source docs/_build/html` passed initially in 12.175s and after the named reciprocal-review prose/example corrections in 4.243s.
Platform `env UV_OFFLINE=1 scripts/test check docs` failed overall in 0.996s at `daf4300` plus the five-document snapshot: dashboard and 77 local links passed; only Documentation admission failed because the declared Furo package was unavailable offline.
The exact Documentation argv from `scripts/test` recovered with network enabled in 23.834s against unchanged content, retaining the successful dashboard/link phases and original overall FAIL; this is qualified phase assembly, not a full command PASS.
Warning-clean owning/platform Sphinx supplied documentation evidence only; no product tests, source/API implementation conformance, scientific/OS certification, source fix or test addition was run/credited.
The final result/commit sentences are factual updates after the validated projection; T is ready next against the accepted S intent, while C/global findings and milestone gates remain open.


### Accepted library test-quality review — October 4

The [T review](library-test-quality-review.md) is accepted after one independent cross-domain critique and two bounded schema/exclusion clarifications, against owning documentation `e0f41b1` and unchanged production/test source `2cd79a24`.
Three domain packets were deduplicated: 145 of 194 root test modules have full-body evidence, 49 distributed/remote modules are explicitly excluded without a full-body claim, and all 22 scientific tool test modules were read; mixed local launcher/Direct/resource/result contracts remain covered.
The 210 unique hashed review inputs match once with no drift; input counts overlap and AST selector stems are not collected/parameter-expanded cases or executed tests.
Keep exact atomic refusal/source identity/numeric/view/grant/selected-record/concurrent-publication and scientific expected-value controls; named weak/vacuous assertions, stale expectations and lane omissions have explicit keep/merge/retire/strengthen priorities for C.
The README Wetlands smoke command lacks `--run-complete`, while the complete job's `complete and wetlands` predicate omits wetlands-only positive smoke/task-API cases; these are source-inspected selection defects, not newly run skip results.
Known heterogeneous int/str concat may honestly publish Any/dynamic schema, independently of unavailable/failed schema fabricated as successful empty/Any.
No runtime/collection/import, product source/test/dependency/environment change, OS/model/binary capability or new defect reproduction is credited; the historical 351 PASS/1 skip remains historical and its uncaptured skip reason UNKNOWN.
Next is C main causal review against S/T, then secondary only after all main packets are ready, then global findings acceptance before repairs; publication/platform/T1 remain paused through the accepted scoped library milestone.
`scripts/test check docs` passed once (exit 0, runner 23s / measured 23.594982s) at platform `0500b25` plus the five-document projection: dashboard, 80 active local links and warning-clean Sphinx passed; no product lane or T runtime test ran.


### Accepted causal library architecture and global findings — October 4

The [C review](library-causal-architecture-review.md) is accepted by root after one independent cross-domain synthesis review and three bounded precision corrections, against owning documentation `e0f41b11e62defcd84b913db12b14e481b7c9a0b` and unchanged production/test source `2cd79a24c59cf1093e934da9aa97744d2f8709c8`.
Both MAIN and SECONDARY followed the sixteen accepted S flows through actual current APIs, state/data/effects/refusal/cancellation/cleanup/return and T oracle judgments before any repair.
The source union has 230 package modules (159 BIF, 16 Core, 55 scientific) with zero unassigned local paths; exact full-body, prior-byte-matched reuse, range/classification and distributed-feature exclusion remain separate, not 230 complete audits or runtime tests.
All nine scientific implementations, 45 example/declarative resources and the executable preview utility have their domain's whole-body evidence; actual model/binary/plugin/data behavior is not thereby certified.
Thirteen consolidated families retain graph/schema/config/default authority; exact source/origin; collective association; scientific values/selected records; immutable accepted resources; ordinary group/repeat/quota and physical retirement; setup/callback/outcome; owned archive/export/native publication; metadata/tooling and finite scientific mechanisms.
Phasor harmonic admission has pinned official API support but independent h2 numerical truth remains unrun; units/axes/singleton model/cached weights/late model admission/surface/empty collision/native association examples remain qualified owned subcases, without invented new mathematics or native PASS.
Current strong typed correlation, output-only scopes, numeric/contained admission, physical disposition/grant retry, derived-view lifetime, A/B source coexistence, first-valid/corruption and independent numerical science controls are explicitly preserved.
No source/test fixes, application imports, product tests, installs, environments, CI or publication were performed during C; B's one authorized official PhasorPy reference check is separately disclosed.
The historical 351 PASS/1 skip retains UNKNOWN for its uncaptured skip reason; Mac/Python3.12 prior artifacts and published Wetlands do not prove current Linux/Windows/Python3.9/NumPy1.26, named native scientific, normal cohort or released Core/BIF closure.
Next freeze one shared interface across admitted origin/identity, collective DTO/assembly and resource/group access, then implement/test finite MAIN waves before SECONDARY; one scoped local-library milestone later unlocks publication/platform/T1.
Necessary candidate-source capability-only uploads/jobs may validate repaired milestone requirements while source release merge/tag/PyPI/platform actions stay paused; existing standing publication authority persists after technical gates.
The low-frequency reflection records the concrete improvement over file coverage: causal authority/effect review found live default/config, collective association, selected frame/pointer, ordinary cleanup and public destination gaps, while S-first revealed a previously successful writable-input transport oracle contradicting accepted immutability.
Focused independent counterexamples, repaired vacuous/wrong-stage assertions and one frozen interface/final review are justified; no new per-file approval bureaucracy or broad re-audit is added.
This five-document checkpoint changes no owning source/API/specification behavior, dependency bounds, lock, installed platform runtime or held WIP.
The one `env UV_OFFLINE=1 scripts/test check docs` passed against main `b9cc0d8` plus the five-document projection: exit 0, runner 4s / measured 4.616208s, dashboard/local links and warning-clean Sphinx passed.
No product lane, test skip/deselection, OS/native/artifact capability or repeated documentation phase was run; only factual completion/provenance sentences follow the validated projection.

### First coherent MAIN capture/transaction/schema increment — October 4

The accepted combined interface design's first increment is committed at owning `936c44003f759075a16629d290bb3a5a227fe194`, parent `e0f41b11e62defcd84b913db12b14e481b7c9a0b`: exactly 43 reviewed task paths, 1,865 additions/761 removals, clean working tree and empty index.
Callable definitions and root/explicit-target/eager-step admission now own detached graph/default/environment/configuration/root-input values before execution effects; mapped targets remain in the owned graph, while original reservations, execution context and bound SharedArray owner identity stay intact.
Graph/interface/session changes stage refusal before publication; central resolved declarations retain Optional/Annotated metadata, Passthrough additions and configured dynamic DataFrame resolver authority, admit the single current graph/constant representation and report registry schema failure honestly.
Captured declaration facades remain on the tool instance, retaining its actual executable class/origin; this does not establish later executable-content closure, accepted-array immutability or full resource cleanup.
Public causal failures precede fixes: mutable default/configuration/root values, graph transactions and declaration/schema failures; corrected wrong-stage dict/transform fixtures and intermediate missing-import/owner-status failures remain separately recorded without causal credit.
The one combined focused owner command remained **FAIL**: 287 PASS/5 FAIL, 20.879813s measured (20.31s pytest), zero skips and eleven ImageSpec declaration warnings.
Exact five failures were reproduced in 1.451811s, then recovered with 5 PASS in 2.409369s; only invalidated graph/session/runtime/metadata families were rerun, 158 PASS in 20.700687s (18.63s pytest), zero skips and the same eleven warnings.
One added diagnostic admission discriminator passed in 1.323670s; unchanged successful original owner projections were retained, forming qualified scoped completion rather than relabeling the failed overall command or claiming a full suite.
The corrected session fixture executes its explicit old target because it publishes no root outputs; the corrected planning/configuration fixture asserts no run-view or numeric-file publication, retaining meaningful routing authority.
Planning's array-owner metadata acquisition is pre-existing at production `2cd79a2` (planner→cache activation→runtime owner construction) and remains deferred C08; this increment does not certify effect-free planning or complete S10 ownership.
README Ruff initially failed three named issues in 0.132151s; scoped typing initially failed in 2.072978s.
Named import/predicate/unused-local and equivalent typing corrections recovered final scoped typing in 1.868640s, Ruff in 0.113155s, size in 0.296453s and import boundaries in 0.602406s, all PASS.
The one prepared-interpreter strict documentation build passed: package-document generation 2.515949s, `sphinx-build -W --keep-going` 21.672809s, warning-clean; no environment reconciliation or repeated broad product lane was run.
The frozen 43-path projection, eight unchanged closure files and 104 installed dependency metadata receipts bind the reviewed checks and exact committed bytes; actual editable development metadata is BioImageFlow 0.9.0/Core 0.5.0/Wetlands 2.5.0/NumPy 2.4.2, supplying source-development evidence rather than new artifact/PyPI equivalence.
Reciprocal review covered the other writers' final changes, including bound-reference capture, first-publication canonical type facts, diagnostic refusal and literal typing corrections; all original failures and source projections remain in the retained task receipts.
This is the first coherent C01–03 increment, not closure of every declaration/parser/context candidate or the library milestone.
Continue the accepted shared-interface MAIN waves through admitted executable origin, collective/empty aggregate association, scientific cache/selected-record identity, immutable accepted resources, ordinary group/discard/quota/physical cleanup and outcome/source/publication boundaries, then SECONDARY tooling/native/science.
Windows/Linux/Python 3.9/NumPy 1.26, real current scientific/native recipes, applicable local managed WorkerPool/Complete, fresh candidate artifact/current resolver and exact-source capability CI remain unexecuted for this increment; publication, merge/tag and platform adoption/T1/testing remain paused until the accepted scoped library milestone.
No tag, push, release, dependency/environment reconciliation, platform runtime adoption or held-WIP modification occurred; prepared development/artifact environments and evidence are retained for their next consumers.
This four-document checkpoint updates existing status/authority prose only; it adds no navigation, API contract or documentation structure.
The one `env UV_OFFLINE=1 scripts/test check campaign` passed against main `acc7246e` plus this four-document projection: exit 0, runner 0s/measured 0.154670s, dashboard and 84 active local links verified; no product phase, test skip/deselection or repeated Sphinx phase was run.


### Bounded MAIN numerical identity, pinned selection and loader admission — October 4

Owning commit `d6865b1206747655ac93b280c7a61866aee466f2`, parent `936c44003f759075a16629d290bb3a5a227fe194`, delivers exactly 32 reviewed task paths (1,109 additions/324 removals), with committed/working/approved bytes equal, clean tree and empty index.
Canonical DataFrame identity now reads each column's scalar without row-Series float promotion; independent signed/unsigned adjacent values above 2**53 beside float data distinguish digests, while the existing actual large-integer ProcessingTool argument/result guard remains intact.
Numeric-looking strings such as `001` stay strings unless a workflow explicitly converts them; ordered lists/tuples retain recipe dependency/channel precedence while true sets and dictionary keys stay canonical.
One SelectedResult binds the loaded frame, key, record ID, detached manifest metadata and public record address once; both lookup and first-valid publication select that actual winner's frame.
Planning, provider outcomes, progress, run views, downstream provenance and local result export consume the same binding without reselecting a moving current pointer.
A removed pointer after admission preserves that record's reuse; actual selected parquet absence before admission refuses before downstream dispatch and preserves downstream current bytes.
This does not seal the mutable frame or accepted array values (C07), and the formerly pointer-removal-based transient fixtures no longer certify a genuine unselected-provider execution.
The owner packet found and fixed an inherited Wave1 dynamic DataFrame declaration regression: default Outputs=None remains unknown/dynamic, while an explicit configured empty schema remains known-empty and refuses nonexistent selectors.
A cached NodeStep executed after its iterator finalized the context now preserves its valid cached value without recording into the finished context; active execution still records the pinned provider outcome.
SourceFile admission hashes and compiles the same captured bytes, verifies class/module membership, refuses foreign same-path namespaces unless the exact module is loader-owned, preserves legitimate repeat loads and publishes ownership only after success.
Version-store cached imports must match the selected module/root, including legitimate PEP420 child paths; standalone source archives and failed initialization preserve existing namespace/import-path owners.
Ordinary programmatic/installed/versioned caching remains enabled; full admitted executable/dependency content as cache-key authority is still open, not supplied by selector/version labels or this bounded loader change.

All command durations below are measured wall time against parent `936c440` plus the named working projections; exact final 32-path bytes and eight closure files bind the accepted completion assembly.
The numeric baseline had four genuine failures/one retained processing precision PASS (3.624755s); the public pointer-switch baseline had one genuine identity failure (3.125097s), with separate in-flight import collection failures carrying no causal credit.
The original combined command remains **FAIL**, 199 PASS/25 FAIL in 14.491131s (13.98s pytest); failures included dynamic admission, internal SelectedResult return-shape fixtures and obsolete pointer-removal assumptions.
The focused recovery remains **FAIL**, 29 PASS/2 FAIL in 8.478s; cached late-step source behavior and failed-attempt fixture correlation then recovered with exact 2 PASS in 4.890s.
The one invalidated-owner command remains **FAIL**, 145 PASS/1 FAIL in 14.754s; its remaining regex-filter chain was adapted to explicit conversion, independently checking extracted identifiers remain strings and declaring the changed slice:int output.
That exact final selector passed in 2.151s (1.60s pytest); the earlier corrected exact conversion PASS in 3.224s is retained separately.
These are qualified focused-owner completion, not a relabeled original command or full-suite certification; zero skips were reported, and no new warning summary appeared in these owner receipts.
Original numeric/pinning GREEN was 5 PASS/one incorrect export-path fixture FAIL in 2.054403s; the exact corrected pin test passed in 1.546675s with consumed A=4, downstream=8, current B=99 and outcome/progress/runview/export/provenance all A.
Core loader causal baselines (four Core and two loader failures) precede exact recoveries; the final named namespace/reuse controls passed 11/0 skips in 1.588392s.

| Completion command | Result and measured duration |
| --- | --- |
| Prepared `.venv/bin/python -m pytest` affected runtime/cache/storage/loader owner packet | Overall FAIL, 199 PASS/25 FAIL, 14.491131s; unchanged successes retained |
| Exact affected dynamic/publication/provenance/step/pinning recovery | Overall FAIL, 29 PASS/2 FAIL, 8.478s; exact final two PASS, 4.890s |
| `.venv/bin/python -m pytest` invalidated column/shared-array/DataFrame/recursive/steps/pinning/Node-plan/loader families | Overall FAIL, 145 PASS/1 FAIL, 14.754s; exact remaining conversion selector PASS, 2.151s |
| `.venv/bin/ruff check .` | PASS, 0.128s; initial named unused-import attempt retained |
| `.venv/bin/python scripts/check_file_sizes.py` | PASS, 0.413s |
| `.venv/bin/python scripts/check_import_boundaries.py` | PASS, 0.809s |
| `.venv/bin/pyright --pythonversion 3.12` on the 17 changed production paths | Original 3-error FAIL, 2.227s; equivalent path/narrowing correction PASS, 1.938s |
| `.venv/bin/python docs/generate_tool_package_docs.py` | PASS, 1.673208s |
| `.venv/bin/sphinx-build -W --keep-going docs/source docs/_build/html` | PASS, 20.487194s, no warnings/errors |
| `uv build --package bioimageflow-core --python .venv/bin/python --no-sources --wheel --out-dir <task artifacts>` | Final normal candidate PASS, 8.831374s; pre-typing build PASS8.612260s retained superseded |
| `uv pip install --python .venv-b134-core-artifact/bin/python --no-sources --reinstall-package bioimageflow-core <current wheel>` | PASS, 1.149s, existing exclusive artifact host reused |
| Existing artifact interpreter `-I <public worker witness> --wheel … --root … --manager-root … --receipt …`, outside checkout | PASS, 25.632s; one actual SourceFile scalar task 4→8, physical worker exit and owned HTTP/manager cleanup |

Normal Core0.5 candidate wheel SHA-256 `9b5943959d031fe81b3669828646a650e411bca17f904343a0ca93791ab4ee57` contains all 17 actual current Core Python modules equal to source, noneditable host and actual worker; no py.typed marker or source/version overlay is invented.
The worker proof directly invokes current Core's public entry point; unchanged older artifact-host BioImageFlow/tool wheels do not certify every current library source or a newly installed complete cohort.
The eight source/dependency/configuration closure files and all 104 development METADATA hashes remain unchanged; original held six-path force WIP, saved patch, source and environment stay protected.
Reciprocal review accepted other writers' final source, the late terminal-context guard, truthful exact record fixtures, explicit conversion metadata and equivalent typing corrections; final source bytes and retained commands are bound in the task delivery receipt.
Next is C05 true isolated collective/all-consumed and empty aggregation with actual auxiliary inputs, then C07/C08 immutable access/exact group/discard/repeated-run/quota/physical cleanup and remaining MAIN source/outcome obligations before SECONDARY.
Windows/Linux/Python 3.9/NumPy 1.26, native/scientific recipes, current full-cohort artifacts/resolver, broader Complete/CI/published gates remain unexecuted here; no collective, accepted-array/lifetime or library-milestone closure is claimed.
No tag/push/release/merge, metadata/floor/lock change, dependency reconciliation, platform adoption/testing or distributed/native execution occurred; retained environments/artifacts remain available to their next consumers.
This main four-document checkpoint changes existing authority/status prose only; one offline check campaign is the applicable completion lane, without repeated Sphinx/product checks.

The retained [byte-bound completion command receipts](/private/tmp/bioimageflow-library-deep-review/architecture-repair-design/wave2/completion-summary.json), [32-path source/closure manifest](/private/tmp/bioimageflow-library-deep-review/architecture-repair-design/wave2/final-manifest.json), [exact committed delivery proof](/private/tmp/bioimageflow-library-deep-review/architecture-repair-design/wave2/final-delivery-proof.json) and [actual installed-worker/cleanup receipt](/private/tmp/bioimageflow-library-deep-review/architecture-repair-design/wave2/public-worker-origin-proof.json) provide exact argv, command result/duration, final bytes and intermediate-projection qualifications.
The one offline `env UV_OFFLINE=1 scripts/test check campaign` passed on main `8c01f20` plus the initial four-document status projection: exit0/measured0.206766s, dashboard and84active links; the later provenance links invalidate only the cheap link phase, recovered once on the final document projection: `python3 scripts/verify-platform-test-links.py` PASS/exit0/measured0.086311s, 88 active links, without repeating product or Sphinx checks.
